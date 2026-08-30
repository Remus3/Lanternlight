"""Per-lane on-disk state, and the per-lane ledger fragment that replaces a race.

A lane is described everywhere in this project as a "persistent specialist".
Agent context does not survive a session, so without something on disk that
word is decoration: every lane starts from zero each time, rediscovers what it
already knew, and re-asks questions it already answered. This module is what
makes the word true.

Each writing lane gets two files of its own directly under ``lanes/``, with
deliberately different characters:

``lanes/<lane_id>.STATE.json``
    **Mutable live state.** Session counter, a one-line note saying where to
    resume, and the lane's open items. Open items get closed, so this file is
    rewritten in place - it is a snapshot of now, not a record of history.

``lanes/<lane_id>.LEDGER.md``
    **Immutable completed work.** Append-only, newest first, every entry
    carrying acceptance evidence. Never edited, never reordered.

That split mirrors the one the loop already makes at the repository level -
``ops/runtime/loop_state.json`` is mutable live state and ``docs/LEDGER.md`` is
the immutable record - so a reader who understands one understands the other.

One difference is deliberate: a lane's ``STATE.json`` is **committed**, where
``loop_state.json`` is gitignored. A lane's open items have to survive a
reclone and be visible to whoever reviews the branch, and because each file has
exactly one writer, committing it cannot race. The honest cost: the file lives
on the lane's branch, so a session sitting on ``main`` does not see it until
the branch is merged. The lane itself resumes from its own worktree, which is
where it needs the file.

Why fragments, and why not a lock
---------------------------------

``ROADMAP.md`` item 1b names the problem - eight lanes and one
``docs/LEDGER.md`` will race - and lists two candidate answers: a lock modelled
on ``ops/loop/guard.py``, or a per-lane fragment merged on integration.

**A lock does not fix this, and it is worth writing down why so nobody
re-proposes it.** A lock serialises writes *in time within one filesystem*. The
lanes are not in one filesystem location: each is in its own worktree on its
own branch. Lane A can append at 10:00 and lane B at 10:05, perfectly
serialised, and the two branches still conflict when both are merged - because
git merges *content*, and both edits inserted different text immediately below
the same anchor line of the same file. The lock addresses an axis the problem
does not live on.

So the shared mutable file is removed instead. Each lane appends only to
``lanes/<lane_id>.LEDGER.md``, a file no other lane may touch. Disjoint files
merge without conflict by construction rather than by discipline.
``docs/LEDGER.md`` then keeps exactly one writer forever - the integrator, on
``main``, calling :func:`integrate`.

``tests/test_lane_state.py`` measures both halves of that claim against real
git merges: the shared-file shape is asserted to CONFLICT and the fragment
shape to merge cleanly. Showing only the second would prove the change
happened without proving it mattered.

Note on duplication
-------------------

:func:`integrate` inserts pre-rendered Markdown blocks below
:data:`ops.loop.ledger.ENTRIES_MARKER` rather than calling
:func:`ops.loop.ledger.append_entry`, which takes a
:class:`~ops.loop.ledger.LedgerEntry`. Round-tripping a rendered block back
through the dataclass would risk changing bytes that were already reviewed and
committed, and re-rendering a record is exactly what an append-only file must
never do. The marker itself is imported rather than restated, so the two cannot
drift apart on the thing that matters.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ops import lanes, mdscan
from ops.loop import ledger

__all__ = [
    "FRAGMENT_MARKER",
    "IdClaim",
    "LaneState",
    "LedgerIdCollision",
    "MalformedLedgerHeading",
    "NotAFragment",
    "OpenItem",
    "ReadOnlyLane",
    "SCHEMA",
    "EDITED_AFTER_INTEGRATION",
    "TWO_LANES_COLLIDED",
    "add_open_item",
    "classify_claim",
    "claim_path",
    "claimants_of",
    "release_path",
    "stale_claims",
    "unowned_paths",
    "append_fragment",
    "close_open_item",
    "duplicate_claims",
    "format_duplicate_claims",
    "fragment_entry_ids",
    "fragment_path",
    "integrate",
    "lane_prefix",
    "lanes_dir",
    "load",
    "render",
    "save",
    "start_session",
    "state_path",
]

#: The checkout this code is running from. Inside a lane worktree that is the
#: worktree, which is correct here - a lane reads and writes its OWN state, in
#: its own working directory.
REPO_ROOT = lanes.REPO_ROOT

#: Top-level directory holding every lane's files, FLAT - one file per lane per
#: kind, never a subdirectory per lane.
#:
#: Deliberately NOT under ``ops/``. The ops lane owns ``ops/**``, so a state
#: file at ``ops/lane_state/ingest.json`` would be owned by both the ingest
#: lane and the ops lane, and ``tests/test_lanes.py`` would go red on the one
#: invariant the whole architecture rests on. The same argument rules out
#: ``docs/`` for the fragments.
#:
#: Flat rather than ``lanes/<lane_id>/`` for a measured reason. The first cut
#: used a directory per lane, and ``lanes/capture/`` was rejected by TWO
#: independent safety guards - ``.gitignore``'s bare ``capture/`` rule and the
#: pre-commit hook's ``*/capture/*`` rule - both of which exist to stop
#: captured game frames being committed and both of which were behaving
#: exactly as intended. The lane directory was a false positive against a
#: correct rule, and the cheap fix is to not create a directory of that name
#: rather than to punch a hole in two PII guards.
#:
#: It also removes the whole collision class rather than one instance:
#: ``logs``, ``frames``, ``captures``, ``screenshots``, ``private``, ``pii``,
#: ``tmp``, ``build`` and ``dist`` are all blocked bare directory names too, so
#: a future lane named after any of them would have failed the same way and
#: nobody would have connected the symptom to the cause.
LANES_DIRNAME = "lanes"

#: Suffix of the mutable per-lane state file: ``lanes/<lane_id>.STATE.json``.
STATE_SUFFIX = ".STATE.json"

#: Suffix of the append-only per-lane ledger fragment: ``lanes/<lane_id>.LEDGER.md``.
FRAGMENT_SUFFIX = ".LEDGER.md"

#: Schema marker for ``STATE.json``. An unrecognised value is treated as
#: unreadable rather than guessed at.
SCHEMA = 1

#: Insertion anchor in a lane fragment. An HTML comment, so it renders as
#: nothing, and matched exactly for the same reason as the repository ledger's.
FRAGMENT_MARKER = "<!-- LANE ENTRIES BELOW - NEWEST FIRST -->"

#: Prefix for temporary files written here, so stray debris is identifiable.
TEMP_PREFIX = ".lane_state-"

#: A rendered entry heading: ``### LL-0007 - 2026-08-09 - summary``.
_HEADING_RE = re.compile(r"^### (?P<item_id>\S+) - ", re.MULTILINE)

#: An id-shaped token: LL-0031, SAF-0002, OPS-7, and the shapes a typo produces.
#: Deliberately permissive about case, prefix length, digit count and the
#: hyphen, because this decides only whether a `#` line was TRYING to be an
#: entry heading - never how to parse one. A narrow version of this pattern was
#: itself a hole: an id it did not recognise fell through into silence.
#: Either a hyphen with any digits (``OPS-7``, ``LL-0044``) or no hyphen and at
#: least two (``LL0044``). One un-hyphenated digit is left out on purpose so an
#: ordinary sub-heading like ``#### Section2 overview`` is not called a broken
#: entry - the guard must fire on an entry ATTEMPT, not on prose.
_ID_TOKEN_RE = re.compile(r"[A-Za-z]{1,8}(?:-\d+|\d{2,})\Z")


def _fragment_text(path: Path | str) -> str | None:
    """Read a lane fragment, or None when it legitimately does not exist yet.

    `OPS-7`. Absence and nonsense used to be one answer. Fragments are created
    lazily on a lane's first entry, so a missing one is the NORMAL state for
    most lanes and must stay silent - but the same tolerance swallowed a real
    caller mistake: ``integrate("ops")``, passing a lane ID where a fragment
    PATH belongs, landed on a directory and surfaced a bare
    ``PermissionError: [Errno 13] Permission denied: 'ops'`` on Windows.

    An errno is not a diagnosis, and the two cases sit a hair apart - get the
    name slightly wrong and you got a silent ``[]``, get it wrong another way
    and you got an unrelated OS error. Neither said "that is not a fragment".

    So: missing is None, and anything that cannot be a fragment raises with the
    path it should probably have been.

    **A limit that is still live, in the present tense.** A MISTYPED fragment
    name is indistinguishable from a missing one and still returns None
    silently - ``integrate("lanes/opss.LEDGER.md")`` gives ``[]``. Closing it
    needs a filename convention, which was measured against the existing tests
    and rejected because they legitimately pass names like ``LEDGER.md``, or a
    caller-supplied lane id. Neither is free, and lazy creation is load-bearing.
    """
    target = Path(path)

    known = {lane.lane_id for lane in lanes.LANES if not lane.read_only}
    if str(path) in known:
        raise NotAFragment(
            f"{path!r} is a LANE ID, not a fragment path. This function takes a "
            f"path to a lane's ledger fragment.\n"
            f"  did you mean: {fragment_path(str(path))}\n"
            f"Passing the id reached a directory of the same name and used to "
            f"surface a bare OS error instead of saying this."
        )
    if target.is_dir():
        raise NotAFragment(
            f"{target} is a directory, not a lane ledger fragment. A fragment is "
            f"a Markdown file, normally lanes/<lane_id>{FRAGMENT_SUFFIX}."
        )

    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError:
        # The ordinary case: this lane has recorded nothing yet.
        return None
    except NotADirectoryError:
        # A parent component is a file, so the path cannot ever exist. Still
        # absence rather than corruption.
        return None
    except IsADirectoryError as exc:  # pragma: no cover - POSIX twin of is_dir
        raise NotAFragment(f"{target} is a directory, not a lane fragment") from exc


@dataclass(frozen=True)
class _RegionScan:
    """One reading of an entry region, shared by the guard and the splitter.

    `OPS-9` existed because those two had **separate** readings: the guard
    skipped fenced lines and the splitter used ``_HEADING_RE.finditer`` over the
    whole region, which knows nothing about fences. So a well-formed heading
    inside a code block became a real entry while a malformed one beside it was
    ignored. Two halves of one parser disagreeing is the shape of every bug this
    module has had, so there is now exactly one scan and both callers use it.

    Attributes:
        headings: ``(char_offset, item_id)`` for each heading OUTSIDE a fence,
            in document order. The offset indexes into the region body.
        suspect: The first ``(line_number, line)`` that looks like an entry
            heading and does not parse, or None.
        open_fence_at: Line number of a fence that is never closed, or 0.
    """

    headings: tuple[tuple[int, str], ...]
    suspect: tuple[int, str] | None
    open_fence_at: int


def _scan_entry_region(body: str) -> _RegionScan:
    """Walk ``body`` once, tracking fences, and report what is in it.

    A fence is closed only by the delimiter that opened it, which is what
    Markdown does and which means a mismatched delimiter leaves the fence open
    - caught by :attr:`_RegionScan.open_fence_at` rather than silently ending
    the fenced span early.
    """
    headings: list[tuple[int, str]] = []
    suspect: tuple[int, str] | None = None
    container = 0

    scan = mdscan.scan_unfenced(body)
    for number, offset, line in scan.lines:
        container = _container_column(line, container)
        if not line.lstrip().startswith("#"):
            continue
        match = _HEADING_RE.match(line)
        if match:
            headings.append((offset, match["item_id"]))
        elif suspect is None and _looks_like_an_entry_attempt(line, container):
            suspect = (number, line)

    return _RegionScan(
        headings=tuple(headings),
        suspect=suspect,
        open_fence_at=scan.open_fence_at,
    )


#: Markdown expands a leading tab to the next four-column stop, and four
#: columns of indentation opens a code block. Below that, an ATX heading is
#: still a heading.
_INDENTED_CODE_COLUMNS = 4


#: A bullet or ordered-list marker, and the whitespace that follows it. The
#: content column of the item is the marker's indent plus this match's width.
_LIST_MARKER_RE = re.compile(r"(?:[-*+]|\d{1,9}[.)])\s+")


def _container_column(line: str, current: int) -> int:
    """Track the content column of the innermost enclosing list item.

    **`LL-0081`, and the reason the first `OPS-11` fix was wrong.** CommonMark
    measures indentation RELATIVE to the containing block's content column, not
    from column 0. A ``- `` bullet opens content column 2, so a line indented
    four ABSOLUTE columns inside it sits at two RELATIVE columns and is a
    HEADING, not a code block. Comparing absolute columns therefore read a real
    heading as code and dropped the entry in silence - the one failure
    :func:`_assert_headings_parse` exists to catch.

    Blank lines do not close a list item, so they leave ``current`` alone. A
    non-blank line dedented to or past the current content column closes it.
    """
    if not line.strip():
        return current
    indent = _indent_columns(line)
    if indent < current:
        current = 0
    marker = _LIST_MARKER_RE.match(line.lstrip())
    if marker and indent >= current:
        return indent + len(marker.group(0))
    return current


def _indent_columns(line: str) -> int:
    """Leading whitespace of ``line`` measured in Markdown columns.

    A tab advances to the next multiple of four, which is what makes a single
    leading tab equivalent to four spaces for block-structure purposes.
    """
    columns = 0
    for char in line:
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += _INDENTED_CODE_COLUMNS - (columns % _INDENTED_CODE_COLUMNS)
        else:
            break
    return columns


def _looks_like_an_entry_attempt(line: str, container: int = 0) -> bool:
    """True when ``line``'s first token after the hashes is an id.

    Tested on the FIRST token rather than anywhere in the line, so a sub-heading
    that cites an id in passing is not mistaken for a broken entry. That
    distinction is what keeps the guard from crying wolf, and a guard that cries
    wolf is one somebody eventually deletes.

    **`OPS-11`: indented code is code, and it is the SECOND code form.** This
    scan already skips FENCED blocks, but Markdown also makes a block out of
    four columns of indentation, and that form carries no delimiter for a fence
    scanner to see. A quoted example indented into a code block was therefore
    read as a broken heading and the whole fragment was refused - a false
    positive, found by the refutation pass on `LL-0038`.

    **`LL-0081` corrects the justification that first shipped with that fix,
    which was stated as a proof and was false.** It claimed "a line indented
    four or more columns cannot be a heading at all". CommonMark measures
    indentation RELATIVE to the containing block's content column, so inside a
    ``- `` bullet - which opens content column 2 - four absolute columns is two
    relative columns and IS a heading. The absolute comparison therefore
    silently dropped real entries in list context, which is this repository's
    own house format for an entry body. ``container`` is the content column of
    the innermost enclosing list item, from :func:`_container_column`, and the
    comparison below is relative to it.

    Three relative columns still counts as a heading, and is still refused.
    """
    if _indent_columns(line) - container >= _INDENTED_CODE_COLUMNS:
        return False
    text = line.lstrip().lstrip("#").strip()
    if not text:
        return False
    return bool(_ID_TOKEN_RE.match(text.split()[0].strip(":.,;")))


class ReadOnlyLane(RuntimeError):
    """A read-only lane asked for somewhere to write.

    Refused rather than granted-and-documented. ``verify`` writes nothing,
    ever; handing it a state file would be the first crack in that, and the
    crack would be invisible until the day it graded its own work.
    """


class MalformedLedgerHeading(RuntimeError):
    """An entry heading does not parse, so it would be skipped in silence."""


class NotAFragment(RuntimeError):
    """A fragment path is not a fragment, and not merely a missing one."""


class LedgerIdCollision(RuntimeError):
    """One item id claimed by two DIFFERENT entries.

    Deliberately fatal, and deliberately not fixed automatically. The three
    tempting alternatives are all worse:

    * **Skip it** - what :func:`integrate` used to do, because a skip is
      indistinguishable from an idempotent re-run when only the id is compared.
      That is the defect this exception exists to end: a lane's whole session
      record disappeared and the only symptom was an empty return value.
    * **Overwrite it** - rewrites a record in an append-only file.
    * **Renumber it** - quietly rewrites a record too, and the new id is
      already cited by a roadmap item, a branch name and a commit message that
      this function cannot see. Renumbering is a human decision.
    """


def _now() -> str:
    """Return the current UTC time as a second-resolution ISO 8601 string."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _today() -> str:
    """Return today's UTC date as ``YYYY-MM-DD``."""
    return datetime.now(UTC).date().isoformat()


def _require_ascii(label: str, text: str) -> None:
    """Raise unless ``text`` is 7-bit ASCII, naming the offending codepoint.

    Catching a smart quote here names the field it came from. Catching it later
    in ``tests/test_ascii_hygiene.py`` only names the file, and by then a lane
    has already written it.
    """
    if not text.isascii():
        bad = next(ch for ch in text if not ch.isascii())
        raise ValueError(
            f"{label} contains non-ASCII character {ledger.ch_repr(bad)}; this "
            "repository is 7-bit ASCII only - use ' - ' for a clause break and "
            "plain quotes"
        )


def lanes_dir() -> Path:
    """Return ``lanes/``, the flat directory holding every lane's files."""
    return REPO_ROOT / LANES_DIRNAME


def lane_prefix(lane_id: str) -> Path:
    """Return ``lanes/<lane_id>``, the stem both of a lane's files share.

    Pure path arithmetic, and deliberately permissive: this answers for the
    read-only lane too, exactly as :meth:`ops.lanes.Lane.worktree_path` does.
    Computing a path grants nothing. The refusal belongs at the call that hands
    out somewhere to write, which is :func:`state_path` and
    :func:`fragment_path`.

    Raises:
        KeyError: ``lane_id`` is not in the roster.
    """
    lane = lanes.by_id(lane_id)
    return lanes_dir() / lane.lane_id


def _refuse_read_only(lane_id: str) -> lanes.Lane:
    """Raise :class:`ReadOnlyLane` unless ``lane_id`` may write.

    Called by every function that reads or writes lane state, **including the
    ones handed an explicit path**. That distinction is the whole point and it
    was missed on the first cut: the refusal originally lived only in
    :func:`state_path` and :func:`fragment_path`, so every default route raised
    and every ``path=`` route walked straight past it.
    ``save(LaneState(lane_id="verify"), somewhere)`` wrote a file.

    "Eight entry points raise" is not the same property as "verify writes
    nothing, ever", and only the second is the guarantee that lets a read-only
    lane grade other lanes' work. Found by the refutation pass, which is
    exactly the class of hole an author's own mutation testing misses - the
    mutations were aimed at the code that existed, not at the route around it.
    """
    lane = lanes.by_id(lane_id)
    if lane.read_only:
        raise ReadOnlyLane(
            f"lane {lane.lane_id!r} is read-only and is given nowhere to write - "
            "it reports a verdict and owns no files on purpose. Passing an "
            "explicit path does not change that."
        )
    return lane


def _writable_prefix(lane_id: str) -> Path:
    _refuse_read_only(lane_id)
    return lane_prefix(lane_id)


def state_path(lane_id: str) -> Path:
    """Return the lane's mutable state file. Refuses a read-only lane."""
    prefix = _writable_prefix(lane_id)
    return prefix.with_name(prefix.name + STATE_SUFFIX)


def fragment_path(lane_id: str) -> Path:
    """Return the lane's append-only ledger fragment. Refuses a read-only lane."""
    prefix = _writable_prefix(lane_id)
    return prefix.with_name(prefix.name + FRAGMENT_SUFFIX)


@dataclass
class OpenItem:
    """One thing this lane has not finished.

    Open items are the part of a lane's memory that a cold session most needs
    and is least likely to reconstruct. A finished piece of work leaves a
    commit and a ledger entry; an unfinished one leaves nothing at all unless
    it is written here.

    Attributes:
        item_id: Stable id, unique within the lane.
        text: One line saying what is open.
        opened: ISO 8601 date the item was raised.
        blocked_on: What it is waiting for, when it is waiting on something
            named. Empty means it is merely unfinished, which is a different
            state and worth keeping distinguishable.
    """

    item_id: str
    text: str
    opened: str = field(default_factory=_today)
    blocked_on: str = ""

    def validate(self) -> None:
        """Raise :class:`ValueError` if this item is not fit to be written."""
        if not self.item_id.strip():
            raise ValueError("item_id is required")
        if not self.text.strip():
            raise ValueError(f"{self.item_id}: text is required")
        if "\n" in self.text:
            raise ValueError(f"{self.item_id}: text must be a single line")
        _require_ascii("item_id", self.item_id)
        _require_ascii("text", self.text)
        _require_ascii("opened", self.opened)
        _require_ascii("blocked_on", self.blocked_on)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "text": self.text,
            "opened": self.opened,
            "blocked_on": self.blocked_on,
        }

    @classmethod
    def from_dict(cls, payload: object) -> OpenItem:
        if not isinstance(payload, dict):
            raise ValueError(f"open item must be an object, got {type(payload).__name__}")
        for key in ("item_id", "text", "opened", "blocked_on"):
            value = payload.get(key, "")
            if not isinstance(value, str):
                raise ValueError(f"open item {key} must be a string, got {value!r}")
        return cls(
            item_id=payload.get("item_id", ""),
            text=payload.get("text", ""),
            opened=payload.get("opened", ""),
            blocked_on=payload.get("blocked_on", ""),
        )


@dataclass
class LaneState:
    """Where one lane is, right now.

    Attributes:
        lane_id: The owning lane. Checked on load, because loading one lane's
            state out of another's file would silently graft the wrong open
            items onto the wrong specialist.
        sessions: How many times this lane has been started. A lane on session
            1 that believes it has history is a lane about to repeat itself.
        resume_note: One line: where to pick up. This is the field a cold
            session reads first.
        updated: ISO 8601 UTC timestamp of the last save.
        open_items: Unfinished work this lane owns.
        recovered: True when :func:`load` found a file it could not use.
            Never persisted - it describes this load, not the state.
        recovery_note: What :func:`load` did. Empty on a clean load.
    """

    lane_id: str
    sessions: int = 0
    resume_note: str = ""
    updated: str = ""
    open_items: list[OpenItem] = field(default_factory=list)
    #: Paths this lane is ADDING and has claimed, pending the integrator
    #: writing them into ``ops/lanes.py``. See :func:`claim_path` - `OPS-2`.
    #: A promissory note, never a second ownership map: a claim the roster has
    #: since absorbed is STALE and fails :func:`stale_claims`.
    claimed_paths: tuple[str, ...] = ()
    recovered: bool = False
    recovery_note: str = ""

    def validate(self) -> None:
        """Raise unless every authored field is writable ASCII."""
        _require_ascii("lane_id", self.lane_id)
        for claimed in self.claimed_paths:
            _require_ascii("claimed_paths", claimed)
        _require_ascii("resume_note", self.resume_note)
        if "\n" in self.resume_note:
            raise ValueError("resume_note must be a single line")
        for item in self.open_items:
            item.validate()

    def to_dict(self) -> dict:
        """Return the persistable payload.

        ``recovered`` and ``recovery_note`` are excluded on purpose: they are
        diagnostics about one particular load, and persisting them would make a
        one-off recovery look permanent on every subsequent read.
        """
        return {
            "schema": SCHEMA,
            "lane_id": self.lane_id,
            "sessions": self.sessions,
            "resume_note": self.resume_note,
            "updated": self.updated,
            "open_items": [item.to_dict() for item in self.open_items],
            "claimed_paths": list(self.claimed_paths),
        }

    @classmethod
    def from_dict(cls, payload: object, lane_id: str) -> LaneState:
        """Build a state from a decoded payload, coercing and checking each field.

        Raises:
            ValueError: The payload is unusable. :func:`load` turns this into a
                recovery rather than a crash.
        """
        if not isinstance(payload, dict):
            raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

        schema = payload.get("schema", SCHEMA)
        if schema != SCHEMA:
            raise ValueError(f"unsupported schema {schema!r}, this build reads {SCHEMA}")

        found_id = payload.get("lane_id", lane_id)
        if not isinstance(found_id, str):
            raise ValueError(f"lane_id must be a string, got {type(found_id).__name__}")
        if found_id != lane_id:
            raise ValueError(
                f"this file holds state for lane {found_id!r} but lane {lane_id!r} "
                "asked for it - refusing to graft one lane's open items onto another"
            )

        sessions = payload.get("sessions", 0)
        if not isinstance(sessions, int) or isinstance(sessions, bool) or sessions < 0:
            raise ValueError(f"sessions must be a non-negative int, got {sessions!r}")

        resume_note = payload.get("resume_note", "")
        if not isinstance(resume_note, str):
            raise ValueError(f"resume_note must be a string, got {type(resume_note).__name__}")

        updated = payload.get("updated", "")
        if not isinstance(updated, str):
            raise ValueError(f"updated must be a string, got {type(updated).__name__}")

        raw_items = payload.get("open_items", [])
        if not isinstance(raw_items, list):
            raise ValueError("open_items must be a list")

        raw_claims = payload.get("claimed_paths", [])
        if not isinstance(raw_claims, list):
            raise ValueError("claimed_paths must be a list")
        for one in raw_claims:
            if not isinstance(one, str):
                raise ValueError(f"claimed path must be a string, got {one!r}")

        return cls(
            lane_id=lane_id,
            sessions=sessions,
            resume_note=resume_note,
            updated=updated,
            open_items=[OpenItem.from_dict(item) for item in raw_items],
            claimed_paths=tuple(raw_claims),
        )


def claim_path(lane_id: str, pattern: str, path: Path | None = None) -> LaneState:
    """Claim ``pattern`` for ``lane_id``, pending the roster absorbing it.

    `OPS-2`. The orphan guard fails any file no lane owns, and ownership lives
    in ``ops/lanes.py``, which only the **ops** lane may edit. So a lane adding
    a file was red for its whole session with no in-slice remedy - and a lane
    stuck red is exactly the pressure that gets a guard weakened to go green,
    which ``CLAUDE.md`` forbids outright.

    Neither option the item offered removes that. "ops declares it first" needs
    the filename known before the work starts, which is usually false. "The
    integrator declares it at merge" works for an integrator spanning both
    lanes - it is how ``lanternlight/damage.py`` shipped - but a lane running
    alone still sits red.

    A claim is a **promissory note**, not a second ownership map. The roster
    stays the only source of truth: :func:`ops.lanes.owner_of` is untouched,
    and once the integrator writes the path into ``ops/lanes.py`` the claim is
    STALE and :func:`stale_claims` fails until it is released.
    """
    state = load(lane_id, path)
    _refuse_read_only(lane_id)
    _refuse_overreaching_claim(lane_id, pattern)
    if pattern not in state.claimed_paths:
        state.claimed_paths = (*state.claimed_paths, pattern)
    save(state, path)
    return state


def overreach(pattern: str, lane_id: str = "") -> list[str]:
    """Return roster-owned files ``pattern`` would swallow. Empty is good.

    **A claim is for files nobody owns yet.** Without this, a catch-all made the
    orphan guard vacuous: ``claim_path(lane, "**")`` matched every unowned path
    in the repository, so the guard reported green with a genuinely orphaned
    file on disk. The sanctioned pressure valve opened all the way.

    It also catches the quieter shape - ``lanternlight/*.py`` claimed by
    ``capture`` reaches ``lanternlight/redact.py``, which ``safety`` owns and
    holds a veto over. Neither breaks :func:`ops.lanes.owner_of`, which still
    answers ``safety``, but a lane should not be able to file a note over
    another lane's files at all.

    Checked against the REAL TREE rather than against pattern strings, because
    two patterns can differ textually and still both match one file - the same
    reason ``tests/test_lanes.py`` walks the tree instead of comparing globs.
    """
    reached = []
    for path in lanes.tracked_files():
        if not lanes.path_matches(path, [pattern]):
            continue
        owner = lanes.owner_of(path)
        if owner is not None and owner != lane_id:
            reached.append(f"{path.as_posix()} (owned by {owner})")
    return sorted(reached)


def _refuse_overreaching_claim(lane_id: str, pattern: str) -> None:
    reached = overreach(pattern, lane_id)
    if not reached:
        return
    raise ValueError(
        f"lane {lane_id!r} may not claim {pattern!r}: it reaches "
        f"{len(reached)} file(s) another lane already owns.\n  "
        + "\n  ".join(reached[:5])
        + "\nA claim is a promissory note for a file NOBODY owns yet. A "
        "catch-all would make the orphan guard vacuous, which is the one thing "
        "the claim mechanism must not buy."
    )


def release_path(lane_id: str, pattern: str, path: Path | None = None) -> LaneState:
    """Drop a claim, normally because the roster now carries it."""
    state = load(lane_id, path)
    _refuse_read_only(lane_id)
    state.claimed_paths = tuple(one for one in state.claimed_paths if one != pattern)
    save(state, path)
    return state


def _writing_states(states: dict[str, LaneState] | None) -> dict[str, LaneState]:
    if states is not None:
        return states
    return {
        lane.lane_id: load(lane.lane_id)
        for lane in lanes.LANES
        if not lane.read_only
    }


def claimants_of(
    path: str | Path, states: dict[str, LaneState] | None = None
) -> list[str]:
    """Return the lane ids claiming ``path``, sorted. Normally zero or one.

    More than one is a real fault and is returned rather than resolved: two
    owners for one file is the invariant the whole lane architecture rests on,
    and a pending claim must not become a way around it.
    """
    return sorted(
        lane_id
        for lane_id, state in _writing_states(states).items()
        if lanes.path_matches(path, state.claimed_paths)
    )


def unowned_paths(
    paths: Sequence[str | Path], states: dict[str, LaneState] | None = None
) -> list[str]:
    """Return the paths nothing arbitrates: no roster owner, no single claimant.

    The orphan guard's predicate lives here rather than inside the test so it
    can be exercised on a synthetic tree. Left in the test it was effectively
    unpinned: the real repository currently has no claimed path, so removing
    the claim branch entirely would have left the suite green - a guard whose
    interesting half is never executed.

    A path with TWO claimants is unowned on purpose. Two owners for one file is
    the invariant the lane architecture rests on, and a pending claim must not
    become a way around it.
    """
    resolved = _writing_states(states)
    return [
        Path(path).as_posix()
        for path in paths
        if lanes.owner_of(path) is None
        and not lanes.is_cross_cutting(path)
        and len(claimants_of(path, resolved)) != 1
    ]


def stale_claims(
    states: dict[str, LaneState] | None = None,
) -> list[tuple[str, str]]:
    """Return ``(lane_id, pattern)`` for claims the roster has already absorbed.

    This is what stops a claim becoming permanent. Once ``ops/lanes.py`` owns
    the path, the note has been redeemed and leaving it behind would build the
    shadow ownership map the roster exists to prevent.
    """
    stale = []
    for lane_id, state in sorted(_writing_states(states).items()):
        for pattern in state.claimed_paths:
            # Two conditions, because the pattern-as-a-path check alone missed
            # the case that matters most: `lanternlight/*.py` is not itself an
            # owned path, yet it reaches `lanternlight/redact.py`, which safety
            # owns. Redeemed notes and overreaching notes are both stale.
            if any(lane.owns_path(pattern) for lane in lanes.LANES) or overreach(
                pattern, lane_id
            ):
                stale.append((lane_id, pattern))
    return stale


def load(lane_id: str, path: Path | None = None) -> LaneState:
    """Read a lane's state, falling back to a usable default rather than raising.

    Every failure mode - no file, unreadable file, invalid JSON, valid JSON of
    the wrong shape, another lane's state - produces a default with
    ``recovery_note`` set. ``recovered`` is True only when a file existed and
    could not be used, because a lane's first ever run is not a recovery.
    """
    _refuse_read_only(lane_id)
    target = Path(path) if path is not None else state_path(lane_id)

    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return LaneState(
            lane_id=lane_id,
            recovery_note=f"no state file at {target}; lane {lane_id} starts from zero",
        )
    except OSError as exc:
        return LaneState(
            lane_id=lane_id,
            recovered=True,
            recovery_note=(
                f"could not read {target} ({exc.__class__.__name__}: {exc}); starting fresh"
            ),
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return LaneState(
            lane_id=lane_id,
            recovered=True,
            recovery_note=(
                f"{target} is not valid JSON (line {exc.lineno} col {exc.colno}: "
                f"{exc.msg}); starting fresh"
            ),
        )

    try:
        return LaneState.from_dict(payload, lane_id)
    except ValueError as exc:
        return LaneState(
            lane_id=lane_id,
            recovered=True,
            recovery_note=f"{target} parsed but is not usable lane state ({exc}); starting fresh",
        )


def save(state: LaneState, path: Path | None = None) -> Path:
    """Write ``state`` atomically and return the path written.

    The write goes to a uniquely named temporary file in the target's own
    directory - same directory, so the final move is a rename within one
    filesystem, which is what makes it atomic - and is flushed and fsynced
    before the move. ``state.updated`` is stamped here so callers cannot forget.
    """
    _refuse_read_only(state.lane_id)
    state.validate()
    target = Path(path) if path is not None else state_path(state.lane_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    state.updated = _now()
    body = json.dumps(state.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    handle, tmp_name = tempfile.mkstemp(
        prefix=f"{TEMP_PREFIX}{target.name}-", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    return target


def start_session(lane_id: str, resume_note: str = "", path: Path | None = None) -> LaneState:
    """Record that this lane has started again, and where it is picking up.

    Bumping a counter sounds cosmetic and is not: a lane that has run eleven
    times and believes it is on its first will happily redo closed work, which
    is the single failure this whole design exists to prevent.
    """
    state = load(lane_id, path)
    state.sessions += 1
    if resume_note:
        state.resume_note = resume_note
    save(state, path)
    return state


def add_open_item(
    lane_id: str,
    item_id: str,
    text: str,
    *,
    blocked_on: str = "",
    path: Path | None = None,
) -> LaneState:
    """Record something this lane has not finished.

    Raises:
        ValueError: ``item_id`` is already open, or a field is not ASCII. A
            silent overwrite would lose whichever description was written
            first, and the first one is usually the one with the context.
    """
    state = load(lane_id, path)
    if any(item.item_id == item_id for item in state.open_items):
        raise ValueError(
            f"lane {lane_id} already has an open item {item_id!r}; close it or "
            "use a new id rather than overwriting the original description"
        )
    state.open_items.append(OpenItem(item_id=item_id, text=text, blocked_on=blocked_on))
    save(state, path)
    return state


def close_open_item(lane_id: str, item_id: str, path: Path | None = None) -> LaneState:
    """Remove an open item.

    Raises:
        KeyError: No such item. Closing something that is not open means the
            caller and the file disagree about reality, and passing quietly
            would hide that.
    """
    state = load(lane_id, path)
    remaining = [item for item in state.open_items if item.item_id != item_id]
    if len(remaining) == len(state.open_items):
        raise KeyError(
            f"lane {lane_id} has no open item {item_id!r} - open items are "
            f"{[i.item_id for i in state.open_items]}"
        )
    state.open_items = remaining
    save(state, path)
    return state


def render(state: LaneState) -> str:
    """Render a lane's state for a human, or for a session reading it cold.

    Kept as a rendering of the single stored representation rather than a
    second stored file. Two representations of one fact drift, and this project
    has already paid for that once with the generated lane contracts.
    """
    lines = [
        f"lane      : {state.lane_id}",
        f"sessions  : {state.sessions}",
        f"updated   : {state.updated or 'never'}",
        f"resume    : {state.resume_note or 'no note - this lane has not recorded one'}",
    ]
    if state.recovery_note:
        lines.append(f"recovery  : {state.recovery_note}")
    lines.append("open items:")
    if not state.open_items:
        lines.append("  none")
    else:
        for item in state.open_items:
            suffix = f"  [blocked on: {item.blocked_on}]" if item.blocked_on else ""
            lines.append(f"  {item.item_id}  {item.text}  (opened {item.opened}){suffix}")
    return "\n".join(lines)


def _fragment_header(lane_id: str) -> str:
    """Return the preamble a new fragment is created with."""
    return "\n".join(
        [
            f"# Lane ledger fragment - {lane_id}",
            "",
            "Completed work by the `" + lane_id + "` lane, newest first, each entry",
            "carrying its acceptance evidence. **Append-only** - entries are never",
            "edited, reordered or deleted.",
            "",
            "This file exists so that eight lanes on eight branches never all append",
            "to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.",
            "The integrator folds these entries into `docs/LEDGER.md` on `main`, with",
            "`ops.lane_state.integrate`, which is idempotent and safe to re-run.",
            "",
            FRAGMENT_MARKER,
            "",
        ]
    )


def _atomic_write(target: Path, body: str) -> Path:
    """Write ``body`` to ``target`` through a temp file in the same directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        prefix=f"{TEMP_PREFIX}{target.name}-", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


def _insert_below(original: str, marker: str, block: str, where: Path) -> str:
    """Return ``original`` with ``block`` inserted directly below ``marker``.

    Self-checks that every byte already below the marker survives unchanged.
    That is the one promise an append-only file makes, and it is cheaper to
    assert here than to detect later in a diff.
    """
    index = original.find(marker)
    if index < 0:
        raise ledger.MarkerMissingError(
            f"{where} has no line reading {marker!r}; refusing to guess where a "
            "new entry belongs"
        )
    split_at = index + len(marker)
    head = original[:split_at]
    preserved = original[split_at:].lstrip("\n")
    updated = head + "\n\n" + block + "\n\n" + preserved
    if not updated.endswith(preserved):
        raise AssertionError(
            f"append to {where} would have altered existing content; refusing to write"
        )
    return updated


def append_fragment(
    lane_id: str, entry: ledger.LedgerEntry, path: Path | None = None
) -> Path:
    """Append one completed-work entry to this lane's fragment, newest first.

    The entry is rendered by :func:`ops.loop.ledger.render_entry`, so a lane
    fragment and the repository ledger share one definition of what an entry
    looks like - including the rule that an entry with no acceptance evidence
    is refused, because "done" with nothing to check is a claim, not a record.
    """
    _refuse_read_only(lane_id)
    target = Path(path) if path is not None else fragment_path(lane_id)
    block = ledger.render_entry(entry)

    original = (
        target.read_text(encoding="utf-8")
        if target.exists()
        else _fragment_header(lane_id)
    )
    return _atomic_write(target, _insert_below(original, FRAGMENT_MARKER, block, target))


def _entries_below(text: str, marker: str) -> str:
    """Return the part of ``text`` after ``marker``, or "" when absent.

    Everything above the marker is preamble, and preamble in this repository
    contains a worked example: ``docs/LEDGER.md`` carries a ``### LL-0000``
    template inside a code fence. Measured 2026-08-09 (ledger LL-0014), a naive
    count of ``### LL-`` headings over the whole file came out one too high for
    exactly that reason. Anything scanning for real entries must start below
    the marker or it will eventually refuse to write a legitimate entry whose
    id happens to match the template's.
    """
    index = text.find(marker)
    if index < 0:
        return ""
    return text[index + len(marker) :]


def fragment_entry_ids(path: Path) -> list[str]:
    """Return the item ids in a fragment, newest first.

    A missing fragment reads as empty rather than raising: a lane that has
    recorded nothing yet is an ordinary state, not an error.
    """
    target = Path(path)
    text = _fragment_text(path)
    if text is None:
        return []
    # Via the shared scan, not a private `finditer` - this function was a THIRD
    # independent reading of the same region, found while closing OPS-9 on the
    # first two. Three readers, three chances to disagree.
    body = _entries_below(text, FRAGMENT_MARKER)
    _assert_headings_parse(body, target)
    return [item_id for _, item_id in _scan_entry_region(body).headings]


def _assert_headings_parse(body: str, where: Path | str) -> None:
    """Refuse a block that looks like an entry and does not parse as one.

    **This closes LL-0031's defect through a second door.** ``_HEADING_RE``
    wants exactly ``###``, one space, a non-space id, then ``" - "``. Miss that
    by a single character and the entry does not fail loudly - it becomes
    INVISIBLE. ``fragment_entry_ids`` omits it, ``duplicate_claims`` never sees
    the id it claims, and ``integrate`` returns ``[]`` having written nothing.
    An integrator reads that empty list as "already done" and the entry is
    gone, which is exactly the silent data loss LL-0031 was written to end.

    Scoped to lines whose FIRST token is id-shaped, and skipping fenced code,
    because the dangerous false positive here is a rule that fires on ordinary
    prose: a guard that cries wolf gets switched off, and then the real
    collision passes too. A sub-heading that merely cites an id - ``#### Why
    LL-0031 was not enough`` - is not an entry attempt and is left alone.

    **Two holes were found here by a refutation pass and are closed. Both were
    the same mistake: guarding the instance instead of the class.**

    *The fence state used to be a bare toggle*, so an entry that opened a fence
    and never closed it left every following line marked as code and the guard
    silently stood down for the rest of the file. That was WORSE than the bug it
    was written to fix: ``integrate()`` returned a NON-EMPTY list, which reads
    as success, while a whole entry was absorbed into its neighbour's block. An
    unbalanced fence is therefore now itself a refusal.

    *The id pattern used to be* ``[A-Z]{2,6}-\\d{3,}`` *- today's ids*. A
    malformed heading carrying any other shape failed the heading pattern AND
    the id pattern and fell straight through into silence. ``OPS-7`` and
    ``SAF-0001`` both sit outside that pattern and both exist in this
    repository, so it was not hypothetical. The shape is now permissive about
    case, prefix length, digit count and the hyphen.

    No count of conforming lines is quoted here on purpose: it grows with every
    entry, so a number written into this docstring is stale by the next commit.
    Filing one was itself a defect - it was recorded as 46 and measured 51 four
    commits later.
    """
    scan = _scan_entry_region(body)
    if scan.suspect is not None:
        number, line = scan.suspect
        raise MalformedLedgerHeading(
            f"{where}: line {number} looks like an entry heading and does not "
            f"parse as one, so it would be SKIPPED IN SILENCE:\n"
            f"  {line.strip()}\n"
            f"An entry must read exactly '### <id> - <date> - <summary>'. A "
            f"heading that misses that is dropped without an error - the id is "
            f"invisible to the collision check and integrate() returns [] "
            f"having written nothing. Fix the heading; do not widen this rule."
        )
    if scan.open_fence_at:
        raise MalformedLedgerHeading(
            f"{where}: the code fence opened at line {scan.open_fence_at} is "
            f"never closed, so every line below it counts as code and the "
            f"heading guard STANDS DOWN for the rest of the file.\n"
            f"That is worse than a malformed heading: the next entry is absorbed "
            f"into this one's block and integrate() returns a NON-EMPTY list, so "
            f"it reads as success. Close the fence."
        )


def _blocks_below(
    text: str, marker: str, where: Path | str = "<in-memory text>"
) -> list[tuple[str, str]]:
    """Split the entry region below ``marker`` into ``(item_id, block)`` pairs.

    Used for both shapes of file - a lane fragment and the repository ledger -
    because comparing one against the other is only meaningful if both were cut
    up the same way.

    The heading positions come from :func:`_scan_entry_region`, the SAME scan
    the guard uses, so a heading inside a code fence is not an entry here either
    - it stays part of the surrounding entry's body, where its author put it.
    Using ``_HEADING_RE.finditer`` here instead was `OPS-9`.
    """
    body = _entries_below(text, marker)
    _assert_headings_parse(body, where)
    headings = _scan_entry_region(body).headings
    blocks: list[tuple[str, str]] = []
    for position, (start, item_id) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(body)
        blocks.append((item_id, body[start:end].strip("\n")))
    return blocks


def _fragment_blocks(
    text: str, where: Path | str = "<in-memory text>"
) -> list[tuple[str, str]]:
    """Split a fragment's entry region into ``(item_id, rendered_block)`` pairs."""
    return _blocks_below(text, FRAGMENT_MARKER, where)


def _normalise_block(block: str) -> str:
    """Return ``block`` in the form two copies of one entry are compared in.

    The comparison this feeds decides "already integrated" from "collision",
    and both errors it can make are expensive - but they are not symmetric.

    A comparison that is too LOOSE calls two different entries the same and
    silently drops one, which is the defect being fixed. A comparison that is
    too STRICT calls a re-run a collision, and that is WORSE: idempotence is
    what makes :func:`integrate` safe to re-run after a partial merge, so a
    false collision blocks a legitimate recovery and the fix somebody reaches
    for is a force flag - which disarms the guard permanently, for every real
    collision as well.

    So the normalisation removes exactly the differences that carry no meaning
    and can appear without an author touching a character:

    * **Line endings.** ``Path.write_text`` on Windows turns LF into CRLF and
      ``read_text`` hides it again, a hazard this repository has already paid
      for. ``.gitattributes``, a checkout on another platform and an editor can
      each rewrite them too.
    * **Trailing whitespace on a line**, which editors and hooks strip.
    * **Leading and trailing blank lines**, which are an artefact of where the
      block was cut, not of what it says.

    Nothing else. Leading indentation is meaningful in Markdown - it makes code
    blocks and nested list items - and interior blank lines separate paragraphs,
    so neither is touched. Two entries that differ in any character of their
    actual text are two entries.
    """
    flattened = block.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in flattened.split("\n")).strip("\n")


def _heading_of(block: str) -> str:
    """Return a block's first line, for an error message a human can act on."""
    return block.replace("\r\n", "\n").split("\n", 1)[0].strip()


def integrate(
    fragment: Path, ledger_path: Path | None = None
) -> list[str]:
    """Fold a lane fragment's entries into the repository ledger.

    Run by the integrator on ``main``, so ``docs/LEDGER.md`` keeps exactly one
    writer and cannot race with anything. An entry already present **with the
    same content** is skipped, which makes this idempotent and therefore safe
    to re-run after a partial merge - the failure mode of a non-idempotent
    integrator is a duplicated ledger entry, and the ledger's whole value is
    that it is a record.

    An id already present with DIFFERENT content is a collision and raises
    :class:`LedgerIdCollision`. Those two cases used to be indistinguishable -
    only the id was compared - and telling them apart is ROADMAP item 2c.
    Lanes branch from a common base, so two lanes each asking "what is the next
    free id?" get the same answer and both take it; prevention by allocation
    cannot work, and both fragments merge cleanly because they are different
    files. What is guaranteed instead is that the collision never passes in
    silence. Use :func:`duplicate_claims` to see it coming.

    Blocks are moved verbatim rather than re-rendered from a parsed dataclass.
    Re-rendering a record risks changing bytes that were already reviewed, and
    an append-only file must never rewrite what it already holds.

    Insertion runs oldest-first so that the newest entry ends up on top, which
    is the ordering ``docs/LEDGER.md`` promises its readers.

    Args:
        fragment: The lane fragment to read.
        ledger_path: The repository ledger. Defaults to
            :func:`ops.loop.ledger.default_ledger_path`.

    Returns:
        The item ids actually integrated by this call, newest first. An empty
        list means everything was already there.

    Raises:
        MarkerMissingError: The repository ledger has no insertion marker.
        LedgerIdCollision: An id in the fragment is already recorded with
            different content, or the fragment claims one id twice. Nothing is
            written - a half-applied integration is worse than a refused one.
    """
    source = Path(fragment)
    book = Path(ledger_path) if ledger_path is not None else ledger.default_ledger_path()

    fragment_text = _fragment_text(fragment)
    if fragment_text is None:
        return []

    blocks = _fragment_blocks(fragment_text, source)
    if not blocks:
        return []

    original = book.read_text(encoding="utf-8")
    if ledger.ENTRIES_MARKER not in original:
        raise ledger.MarkerMissingError(
            f"{book} has no line reading {ledger.ENTRIES_MARKER!r}; refusing to "
            "guess where a new entry belongs"
        )

    recorded: dict[str, list[str]] = {}
    for item_id, block in _blocks_below(original, ledger.ENTRIES_MARKER, book):
        recorded.setdefault(item_id, []).append(_normalise_block(block))

    pending: list[tuple[str, str]] = []
    taken: dict[str, str] = {}
    for item_id, block in blocks:
        normalised = _normalise_block(block)
        claimed = [*recorded.get(item_id, []), *([taken[item_id]] if item_id in taken else [])]
        if normalised in claimed:
            # Byte-for-byte the entry already in the ledger, modulo line
            # endings: a re-run, which must stay silent.
            continue
        if claimed:
            where = "this fragment already" if item_id in taken else str(book)
            raise LedgerIdCollision(
                f"item id {item_id!r} is claimed twice by DIFFERENT entries and "
                "integrating would lose one of them - nothing has been written.\n"
                f"  in {source}: {_heading_of(block)}\n"
                f"  in {where}: {_heading_of(claimed[-1])}\n"
                "This is not a re-run. It has TWO possible causes with OPPOSITE "
                "remedies, and this function sees only one fragment, so it will "
                "not guess which:\n"
                "  (1) TWO LANES COLLIDED. Lanes branch from one base, so both "
                "got the same answer to 'what is the next free id', and their "
                "fragments merged cleanly because they are different files. "
                "Remedy: renumber ONE fragment's entry by hand, in the fragment "
                "and in every roadmap item, branch and commit citing it.\n"
                "  (2) THE ENTRY WAS EDITED AFTER IT WAS INTEGRATED, so the two "
                "copies drifted. Remedy: restore it, or leave it and append a "
                "NEW entry that corrects it. Do NOT renumber - that records one "
                "piece of work under two ids.\n"
                "ops.lane_state.duplicate_claims() sees every fragment and CAN "
                "tell them apart; format_duplicate_claims() prints which it is."
            )
        taken[item_id] = normalised
        pending.append((item_id, block))

    if not pending:
        return []

    updated = original
    for _, block in reversed(pending):
        updated = _insert_below(updated, ledger.ENTRIES_MARKER, block, book)

    _atomic_write(book, updated)
    return [item_id for item_id, _ in pending]


@dataclass(frozen=True)
class IdClaim:
    """One file's claim on one item id.

    Attributes:
        item_id: The claimed id.
        source: The file claiming it - the repository ledger, or a fragment.
        heading: The entry's first line, which is what a human recognises it by.
        content: The normalised block. Two claims with equal content are one
            record seen twice, not a clash.
    """

    item_id: str
    source: Path
    heading: str
    content: str
    #: True when this claim came from ``docs/LEDGER.md`` rather than a lane
    #: fragment. It is what separates "two lanes took one id" from "somebody
    #: edited an entry after it was integrated" - see :func:`classify_claim`.
    from_ledger: bool = False


def duplicate_claims(
    ledger_path: Path | None = None, fragments: Sequence[Path] | None = None
) -> dict[str, list[IdClaim]]:
    """Report every item id claimed by two entries that are not the same entry.

    :func:`integrate` catches a collision at the moment it would lose data,
    which is late: the integrator finds out by exception, mid-merge. This
    answers the same question cheaply and beforehand, so a wrap ritual can ask
    it while renumbering is still easy.

    **Identical claims are not reported, and that is the whole design.**
    Fragments are not deleted after integration, so every id that has ever been
    integrated legitimately appears in at least two files. Reporting those
    would bury the one real collision under thirty false ones, and a report
    nobody reads is worse than no report - it looks like coverage.

    Args:
        ledger_path: The repository ledger. Defaults to
            :func:`ops.loop.ledger.default_ledger_path`.
        fragments: Fragments to scan. Defaults to every writing lane's
            fragment. Missing files are skipped: a lane that has recorded
            nothing yet is an ordinary state, not an error.

    Returns:
        ``{item_id: [IdClaim, ...]}`` for ids with two or more distinct
        contents, ids in sorted order, each list holding every claim on that id
        including the identical ones - because seeing all three files is what
        tells the integrator which two disagree. Empty means no clash.
    """
    book = Path(ledger_path) if ledger_path is not None else ledger.default_ledger_path()
    sources: list[tuple[Path, str]] = [(book, ledger.ENTRIES_MARKER)]
    if fragments is None:
        sources += [
            (fragment_path(lane.lane_id), FRAGMENT_MARKER)
            for lane in lanes.LANES
            if not lane.read_only
        ]
    else:
        sources += [(Path(one), FRAGMENT_MARKER) for one in fragments]

    claims: dict[str, list[IdClaim]] = {}
    for path, marker in sources:
        text = _fragment_text(path)
        if text is None:
            continue
        for item_id, block in _blocks_below(text, marker, path):
            claims.setdefault(item_id, []).append(
                IdClaim(
                    item_id=item_id,
                    source=path,
                    heading=_heading_of(block),
                    content=_normalise_block(block),
                    from_ledger=marker == ledger.ENTRIES_MARKER,
                )
            )

    return {
        item_id: found
        for item_id, found in sorted(claims.items())
        if len({claim.content for claim in found}) > 1
    }


#: Two lanes independently allocated one id. Remedy: renumber, by hand.
TWO_LANES_COLLIDED = "two-lanes-collided"

#: One lane's entry was integrated and then one of the two copies was edited.
#: Remedy: restore the entry, or append a correcting one. NEVER renumber - that
#: records a single piece of work twice, under two ids.
EDITED_AFTER_INTEGRATION = "edited-after-integration"


def classify_claim(claims: Sequence[IdClaim]) -> str:
    """Say WHICH fault a duplicated id represents. `OPS-8`.

    The two have opposite remedies and used to share one message, which told
    the reader to renumber in both cases. For an edited entry that is actively
    wrong: renumbering records one piece of work under two ids, corrupting the
    record while appearing to repair it.

    The discriminator is where the differing claims live. Two FRAGMENTS holding
    different content under one id means two lanes allocated it independently -
    they branched from a common base, so both got the same answer to "what is
    the next free id". One fragment differing from the LEDGER means the entry
    was integrated and then a copy changed, because nothing else could have put
    it there.

    **Precedence when BOTH are true**, stated because it is otherwise a guess:
    two fragments disagreeing wins, even if the ledger copy was also edited.
    The collision must be renumbered before anything else can be reconciled, so
    reporting it first is the actionable order. The rendered report names every
    source, so the edit is still visible.
    """
    fragments = {claim.content for claim in claims if not claim.from_ledger}
    if len(fragments) > 1:
        return TWO_LANES_COLLIDED
    return EDITED_AFTER_INTEGRATION if any(c.from_ledger for c in claims) else TWO_LANES_COLLIDED


def format_duplicate_claims(found: dict[str, list[IdClaim]]) -> str:
    """Render :func:`duplicate_claims` for a human, or for a wrap ritual's log."""
    if not found:
        return "no id is claimed by two different entries"
    lines = [f"{len(found)} item id(s) claimed by different entries:"]
    for item_id, claims in found.items():
        kind = classify_claim(claims)
        if kind == TWO_LANES_COLLIDED:
            lines.append(
                f"  {item_id} - TWO LANES COLLIDED. Renumber one fragment's entry "
                "by hand, in the fragment and in every roadmap item, branch and "
                "commit citing it, then re-run."
            )
        else:
            lines.append(
                f"  {item_id} - EDITED AFTER INTEGRATION. This entry was already "
                "integrated and one copy has since changed. Do NOT renumber it - "
                "that records one piece of work under two ids. The ledger is "
                "append-only: restore the entry to match, or leave it and append "
                "a NEW entry that corrects it."
            )
        for claim in claims:
            where = "ledger" if claim.from_ledger else "fragment"
            lines.append(f"    {claim.source} ({where}): {claim.heading}")
    return "\n".join(lines)


def integrate_all(
    lane_ids: Sequence[str] | None = None, ledger_path: Path | None = None
) -> dict[str, list[str]]:
    """Integrate every writing lane's fragment, returning what each contributed.

    Convenience for the integrator. Read-only lanes are skipped rather than
    raising, because "integrate everything" should not fail on the one lane
    that is designed to have nothing.
    """
    targets = (
        [lane.lane_id for lane in lanes.LANES if not lane.read_only]
        if lane_ids is None
        else list(lane_ids)
    )
    moved: dict[str, list[str]] = {}
    for lane_id in targets:
        lane = lanes.by_id(lane_id)
        if lane.read_only:
            continue
        moved[lane_id] = integrate(fragment_path(lane_id), ledger_path)
    return moved
