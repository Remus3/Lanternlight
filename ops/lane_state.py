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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ops import lanes
from ops.loop import ledger

__all__ = [
    "FRAGMENT_MARKER",
    "LaneState",
    "OpenItem",
    "ReadOnlyLane",
    "SCHEMA",
    "add_open_item",
    "append_fragment",
    "close_open_item",
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


class ReadOnlyLane(RuntimeError):
    """A read-only lane asked for somewhere to write.

    Refused rather than granted-and-documented. ``verify`` writes nothing,
    ever; handing it a state file would be the first crack in that, and the
    crack would be invisible until the day it graded its own work.
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
    recovered: bool = False
    recovery_note: str = ""

    def validate(self) -> None:
        """Raise unless every authored field is writable ASCII."""
        _require_ascii("lane_id", self.lane_id)
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

        return cls(
            lane_id=lane_id,
            sessions=sessions,
            resume_note=resume_note,
            updated=updated,
            open_items=[OpenItem.from_dict(item) for item in raw_items],
        )


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
    try:
        text = target.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return []
    return [m["item_id"] for m in _HEADING_RE.finditer(_entries_below(text, FRAGMENT_MARKER))]


def _fragment_blocks(text: str) -> list[tuple[str, str]]:
    """Split a fragment's entry region into ``(item_id, rendered_block)`` pairs."""
    body = _entries_below(text, FRAGMENT_MARKER)
    matches = list(_HEADING_RE.finditer(body))
    blocks: list[tuple[str, str]] = []
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(body)
        blocks.append((match["item_id"], body[match.start() : end].strip("\n")))
    return blocks


def integrate(
    fragment: Path, ledger_path: Path | None = None
) -> list[str]:
    """Fold a lane fragment's entries into the repository ledger.

    Run by the integrator on ``main``, so ``docs/LEDGER.md`` keeps exactly one
    writer and cannot race with anything. Entries already present are skipped,
    which makes this idempotent and therefore safe to re-run after a partial
    merge - the failure mode of a non-idempotent integrator is a duplicated
    ledger entry, and the ledger's whole value is that it is a record.

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
    """
    source = Path(fragment)
    book = Path(ledger_path) if ledger_path is not None else ledger.default_ledger_path()

    try:
        fragment_text = source.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return []

    blocks = _fragment_blocks(fragment_text)
    if not blocks:
        return []

    original = book.read_text(encoding="utf-8")
    if ledger.ENTRIES_MARKER not in original:
        raise ledger.MarkerMissingError(
            f"{book} has no line reading {ledger.ENTRIES_MARKER!r}; refusing to "
            "guess where a new entry belongs"
        )

    already = set(_existing_ids(original))
    pending = [(item_id, block) for item_id, block in blocks if item_id not in already]
    if not pending:
        return []

    updated = original
    for _, block in reversed(pending):
        updated = _insert_below(updated, ledger.ENTRIES_MARKER, block, book)

    _atomic_write(book, updated)
    return [item_id for item_id, _ in pending]


def _existing_ids(ledger_text: str) -> Iterable[str]:
    """Yield the item ids already recorded below the repository ledger's marker."""
    body = _entries_below(ledger_text, ledger.ENTRIES_MARKER)
    return (m["item_id"] for m in _HEADING_RE.finditer(body))


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
