"""The on-disk loop state - the loop's entire working memory, in one JSON file.

The file lives at ``ops/runtime/loop_state.json``. That directory is gitignored:
this is live runtime state, not repository content. The durable record of what
happened is ``docs/LEDGER.md`` plus git history; this file only answers "where
was I".

Two properties are load-bearing.

**Writes are atomic.** A reader can poll this file at any moment, including in
the middle of a write. A plain ``open(path, "w")`` truncates the target first,
so a poll landing in that window sees an empty or half-written file and gets a
JSON decode error - or worse, a *valid* JSON prefix. Every write therefore goes
to a temporary file in the same directory and is then moved onto the target
with :meth:`pathlib.Path.replace`, which is atomic on both POSIX and Windows
(``MoveFileEx`` with ``MOVEFILE_REPLACE_EXISTING``). A reader sees either the
whole old file or the whole new one, never a splice of the two.

**Loading never raises.** A loop that crashes on a truncated state file is a
loop that needs an operator, which defeats the point. :func:`load` returns a
fresh default for anything it cannot use and records what happened in
``recovery_note`` so the failure is visible rather than silent.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace as dc_replace
from datetime import UTC, datetime
from pathlib import Path

from ops import store_drift

__all__ = [
    "LoopState",
    "STATE_FILENAME",
    "advance_cycle",
    "credit",
    "default_state_path",
    "dispatch",
    "in_flight_summary",
    "load",
    "retire",
    "runtime_dir",
    "save",
    "temp_prefix_for",
]

#: Repository root, resolved from this file's location: ops/loop/state.py.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Name of the state file inside the runtime directory.
STATE_FILENAME = "loop_state.json"

#: Prefix given to every temporary file this module creates. Tests assert on
#: it to prove the temp-then-replace path was actually taken.
TEMP_PREFIX = ".loop_state-"

#: Schema marker. Bumped only on an incompatible shape change; an unrecognised
#: value is treated as unreadable rather than guessed at.
SCHEMA = 1


def runtime_dir() -> Path:
    """Return the runtime directory (``ops/runtime``), which is gitignored."""
    return REPO_ROOT / "ops" / "runtime"


def default_state_path() -> Path:
    """Return the default path of the loop state file."""
    return runtime_dir() / STATE_FILENAME


def temp_prefix_for(target: Path) -> str:
    """Return the temp-file prefix used when writing ``target``.

    Exposed so a test can prove that a write really did go through a temporary
    file rather than truncating the target in place.
    """
    return f"{TEMP_PREFIX}{target.name}-"


def _now() -> str:
    """Return the current UTC time as a second-resolution ISO 8601 string."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class LoopState:
    """One snapshot of where the unattended loop is.

    Attributes:
        cycle: Monotonic cycle counter. Cycle 0 means nothing has run yet.
        directive: The instruction text driving the current cycle. This is the
            directive chain's live link - a cold session reads it to learn what
            it was told to do, because nothing else remembers.
        item: The roadmap item currently in flight, or ``None`` between items.
            SINGULAR, and that is the defect ``in_flight`` exists beside rather
            than a field to widen: this project's stated default is several
            parallel slices, so one name can only ever describe one of them.
            Kept as-is because every existing reader and every existing state
            file uses it, and because the retry rule in :func:`advance_cycle`
            is defined in terms of it.
        in_flight: Dispatch records for work that is RUNNING - ``OPS-27``. Each
            is a mapping with ``item``, ``at``, and optionally ``lane`` and
            ``paths``. Written when work is dispatched rather than when a
            session is about to compact, because a crash, an interrupt, a
            reboot and running out of context lose exactly the same fact and a
            compaction hook covers none of them.
        updated: ISO 8601 UTC timestamp of the last save.
        completed: Item ids finished so far, oldest first.
        recovered: True when :func:`load` found a file it could not use and
            fell back to a default. Never persisted - it describes this load,
            not the state.
        recovery_note: Human-readable account of what :func:`load` did. Always
            populated on a fallback, empty on a clean load.
    """

    cycle: int = 0
    directive: str = ""
    item: str | None = None
    updated: str = ""
    completed: list[str] = field(default_factory=list)
    in_flight: list[dict] = field(default_factory=list)
    recovered: bool = False
    recovery_note: str = ""

    def to_dict(self) -> dict:
        """Return the persistable payload.

        ``recovered`` and ``recovery_note`` are deliberately excluded: they are
        diagnostics about a particular load, and persisting them would make a
        one-off recovery look permanent on every subsequent read.
        """
        return {
            "schema": SCHEMA,
            "cycle": self.cycle,
            "directive": self.directive,
            "item": self.item,
            "updated": self.updated,
            "completed": list(self.completed),
            # VALIDATED COPIES. Copying the caller's dict made the record
            # shape a description of what dispatch() produces rather than a
            # property of the file, and aliased the rows so a caller could
            # mutate persisted state through the payload it was handed.
            "in_flight": [_checked_record(row) for row in self.in_flight],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> LoopState:
        """Build a state from a decoded payload, coercing each field.

        Raises:
            ValueError: If the payload is not a mapping, carries an unknown
                schema, or holds a field of the wrong type. The caller
                (:func:`load`) turns this into a recovery, never a crash.
        """
        if not isinstance(payload, dict):
            raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

        schema = payload.get("schema", SCHEMA)
        if schema != SCHEMA:
            raise ValueError(f"unsupported schema {schema!r}, this build reads {SCHEMA}")

        cycle = payload.get("cycle", 0)
        if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 0:
            raise ValueError(f"cycle must be a non-negative int, got {cycle!r}")

        directive = payload.get("directive", "")
        if not isinstance(directive, str):
            raise ValueError(f"directive must be a string, got {type(directive).__name__}")

        item = payload.get("item")
        if item is not None and not isinstance(item, str):
            raise ValueError(f"item must be a string or null, got {type(item).__name__}")

        updated = payload.get("updated", "")
        if not isinstance(updated, str):
            raise ValueError(f"updated must be a string, got {type(updated).__name__}")

        completed = payload.get("completed", [])
        if not isinstance(completed, list) or not all(isinstance(x, str) for x in completed):
            raise ValueError("completed must be a list of strings")

        # ABSENT MEANS EMPTY, and the schema is deliberately NOT bumped for
        # this field. A bump would make every state file written before it
        # unreadable, sending a live loop through recovery over a field it does
        # not use - a worse failure than the one this field fixes.
        in_flight = payload.get("in_flight", [])
        if not isinstance(in_flight, list):
            raise ValueError("in_flight must be a list")
        rows = []
        for row in in_flight:
            if not isinstance(row, dict):
                raise ValueError("each in_flight entry must be an object")
            rows.append(_checked_record(row))

        return cls(
            cycle=cycle,
            directive=directive,
            item=item,
            updated=updated,
            completed=list(completed),
            in_flight=rows,
        )


#: What an id may contain. No space, no newline, nowhere for prose to go -
#: which is how ``OPS-27`` criterion 3 is met, by the SHAPE of the record
#: rather than by scanning it. A record that cannot hold a sentence cannot
#: leak a conversation, a log line or an identifier.
_ID_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

#: A repo-relative path. Forward slashes only, no drive letter, no leading
#: slash and no "..", so a record can never name anything outside this tree.
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./-]{1,255}$")

#: An ISO 8601 second-resolution stamp, which is what :func:`_now` emits. Shape
#: -checked like everything else in a record: this was the one field typed only
#: as "a string", and a string is exactly where a sentence fits.
_AT_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?$")

#: The complete set of keys a record may carry. Anything else is refused rather
#: than copied through.
_RECORD_KEYS = frozenset({"item", "at", "lane", "paths"})


def _checked_id(value: object, what: str) -> str:
    if not isinstance(value, str) or not _ID_SHAPE.match(value):
        raise ValueError(
            f"{what} must match {_ID_SHAPE.pattern} - got {value!r}. "
            "These records carry ids and paths only: there is deliberately no "
            "free-text field, because a record that cannot hold a sentence "
            "cannot leak one."
        )
    return value


def _checked_path(value: object) -> str:
    if not isinstance(value, str) or not _PATH_SHAPE.match(value) or ".." in value:
        raise ValueError(
            f"a dispatch path must be repo-relative and match "
            f"{_PATH_SHAPE.pattern} with no '..' - got {value!r}"
        )
    return value


def _checked_record(row: dict) -> dict:
    """Validate one dispatch record, raising rather than dropping a bad field.

    Raising, not skipping: a record silently shorn of its paths still looks
    like a record, and a caller would believe an interlock that is no longer
    describing the same work.

    EVERY field is shape-checked and every UNKNOWN field is refused. The first
    version checked ``at`` only for being a string and copied unknown keys
    through, which meant the shape described what :func:`dispatch` produces
    rather than what the FILE can hold - and the file is what a recovering
    session reads. This item's adversarial pass got a newline and a log-shaped
    line onto disk through ``at``, and an arbitrary extra key through the copy.
    """
    unknown = set(row) - _RECORD_KEYS
    if unknown:
        raise ValueError(
            f"a dispatch record may only carry {sorted(_RECORD_KEYS)}; "
            f"refusing unknown key(s) {sorted(unknown)}. There is no free-text "
            "field here on purpose - see OPS-27 criterion 3."
        )
    checked: dict = {"item": _checked_id(row.get("item"), "a dispatch item")}
    at = row.get("at", "")
    if not isinstance(at, str) or (at and not _AT_SHAPE.match(at)):
        raise ValueError(
            f"a dispatch record's 'at' must match {_AT_SHAPE.pattern} - got {at!r}"
        )
    checked["at"] = at
    if row.get("lane") is not None:
        checked["lane"] = _checked_id(row.get("lane"), "a dispatch lane")
    paths = row.get("paths")
    if paths is not None:
        if not isinstance(paths, list):
            raise ValueError("a dispatch record's 'paths' must be a list")
        checked["paths"] = [_checked_path(one) for one in paths]
    return checked


def load(path: Path | None = None) -> LoopState:
    """Read the loop state, falling back to a default rather than raising.

    Every failure mode - no file, unreadable file, invalid JSON, valid JSON of
    the wrong shape - produces a usable default with ``recovery_note`` set.
    ``recovered`` is True only when a file existed and could not be used, which
    is the case worth alerting on; a first run is not a recovery.

    Args:
        path: State file to read. Defaults to :func:`default_state_path`.

    Returns:
        The loaded state, or a fresh default describing why it is fresh.
    """
    target = Path(path) if path is not None else default_state_path()

    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return LoopState(recovery_note=f"no state file at {target}; starting from cycle 0")
    except OSError as exc:
        return LoopState(
            recovered=True,
            recovery_note=(
                f"could not read {target} ({exc.__class__.__name__}: {exc}); starting fresh"
            ),
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return LoopState(
            recovered=True,
            recovery_note=(
                f"{target} is not valid JSON (line {exc.lineno} col {exc.colno}: {exc.msg}); "
                "starting fresh"
            ),
        )

    try:
        return LoopState.from_dict(payload)
    except ValueError as exc:
        return LoopState(
            recovered=True,
            recovery_note=f"{target} parsed but is not a usable loop state ({exc}); starting fresh",
        )


def save(state: LoopState, path: Path | None = None) -> Path:
    """Write ``state`` atomically and return the path written.

    The write goes to a uniquely named temporary file in the target's own
    directory - same directory so the final move is a rename within one
    filesystem, which is what makes it atomic - and is flushed and fsynced
    before the move. A concurrent reader observes the complete old file or the
    complete new one.

    ``state.updated`` is stamped here so callers cannot forget to.

    Args:
        state: The state to persist.
        path: Destination. Defaults to :func:`default_state_path`.

    Returns:
        The path that was written.
    """
    target = Path(path) if path is not None else default_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    state.updated = _now()
    body = json.dumps(state.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    handle, tmp_name = tempfile.mkstemp(
        prefix=temp_prefix_for(target),
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(target)
    except BaseException:
        # Leave no debris behind on any failure, including KeyboardInterrupt.
        tmp_path.unlink(missing_ok=True)
        raise

    return target


def credit(
    *items: str,
    path: Path | None = None,
    state: LoopState | None = None,
) -> LoopState:
    """Record items as completed WITHOUT moving the cycle counter - ``OPS-25``.

    :func:`advance_cycle` can credit at most one item, because it infers that
    completion from a single transition: the previous cycle's in-flight item is
    finished when the loop moves off it. A cycle that closes TWO items therefore
    credited one and silently lost the other. That is not hypothetical - cycle
    43 closed ``OPS-19`` and ``OPS-22`` and recorded only ``OPS-19``; cycle 44
    closed ``OPS-21`` and ``OPS-23`` and recorded only ``OPS-23``. Both were
    repaired by hand, which is a step nobody will remember to take.

    **Why a separate call and not another argument to** :func:`advance_cycle`.
    An ``also_completed=[...]`` parameter on the wrap would work only if the
    merger carried the second closure from the moment it became true to the
    moment it wraps. That is precisely the gap both real losses fell through,
    and this project's continuity design says a fact held in a context window is
    a fact already lost. ``credit`` is callable the instant the second item
    closes and writes through the same atomic path, so a session that dies
    before its wrap still leaves an honest record. It also cannot move the
    counter, so "one cycle, one increment" is structural here rather than a rule
    someone has to remember to obey.

    **How this composes with** ``OPS-7`` **rather than reopening it.**
    :func:`advance_cycle` still INFERS at most one completion from a transition,
    and the retry rule is untouched: ``X -> X`` credits nothing. ``credit`` is an
    ASSERTION by the caller that named items are done. ``OPS-7`` was a bad
    inference - a carry-forward read as a completion - and an assertion cannot
    be a bad inference. Nothing here makes a carried-forward item get credited.

    Ids are stored verbatim, not stripped or normalised, because
    :func:`advance_cycle` stores ``current.item`` verbatim and the two paths
    have to produce the same string or the de-duplication below stops matching.

    **The type check is load-bearing, not decoration.** :func:`save` does not
    validate ``completed``, but :meth:`LoopState.from_dict` does, so a single
    non-string id - ``credit(19)`` for ``OPS-19``, say - writes a file that the
    next :func:`load` rejects wholesale. Measured: the load returns a fresh
    default, ``completed`` comes back empty and ``cycle`` comes back 0, so one
    fat-fingered id destroys the entire completion record rather than adding one
    bad row to it. Every id is therefore checked BEFORE anything is read or
    written, so a rejected call leaves the file byte-for-byte untouched instead
    of half-applying.

    Recovery diagnostics are deliberately NOT cleared, unlike in
    :func:`advance_cycle`. If the state file was unusable, this credit just
    landed on a fresh default whose ``completed`` list is empty - the caller
    needs to see that, because the returned state is the only place it shows.

    Args:
        *items: Item ids to record as completed. At least one, each a non-empty
            string. An id already present is left alone rather than repeated.
        path: State file to read and write. Defaults to the standard location.
        state: Starting state. Defaults to whatever :func:`load` returns.

    Returns:
        The new, already-saved state.

    Raises:
        ValueError: If no items were passed, or an id is empty or blank.
        TypeError: If an id is not a string.
    """
    if not items:
        raise ValueError("credit() needs at least one item id; crediting nothing is a bug")
    for candidate in items:
        if not isinstance(candidate, str):
            raise TypeError(
                f"item ids must be strings, got {type(candidate).__name__}: {candidate!r}"
            )
        if not candidate.strip():
            raise ValueError(f"item ids must be non-empty, got {candidate!r}")

    current = state if state is not None else load(path)

    completed = list(current.completed)
    for candidate in items:
        if candidate not in completed:
            completed.append(candidate)

    # CREDITING IS FINISHING, so the dispatch record goes with it. Found by
    # this item's adversarial pass: an item credited here and then advanced
    # past was never retired and stayed RUNNING forever - on the very path
    # OPS-25 prescribes for a cycle that closes two items.
    remaining = [row for row in current.in_flight if row["item"] not in set(items)]
    credited = dc_replace(current, completed=completed, in_flight=remaining)
    save(credited, path)
    return credited


def advance_cycle(
    directive: str,
    item: str | None = None,
    *,
    complete_current: bool = True,
    path: Path | None = None,
    state: LoopState | None = None,
) -> LoopState:
    """Move the loop to its next cycle and persist the result.

    The in-flight item from the previous cycle is recorded as completed before
    the counter moves, so ``completed`` is the honest answer to "what did this
    loop finish" even if the session that finished it is long gone.

    **Carrying an item forward is a retry, not a completion** - ``OPS-7``. When
    ``item`` equals the item already in flight, nothing is credited, whatever
    ``complete_current`` says. Passing the same item forward is the ordinary
    shape of "I did not get to this", and the old default recorded it as
    finished: measured during the ``LL-0048`` wrap, where ``7b`` was credited
    with nothing done to it and was caught only because the return value
    happened to be printed and read.

    That failure is quiet and it is permanent. A cold session reads ``completed``
    to learn what is already done, skips the item, and there is no operation
    that un-completes anything. Only moving to a DIFFERENT item, or to none,
    says the previous one is finished.

    **This credits at most ONE item, by design** - it infers a completion from a
    transition, and a transition has one previous item. A cycle that closes a
    SECOND item calls :func:`credit` at the moment that item closes; see
    ``OPS-25`` there for why that is a separate call rather than an argument
    here. Crediting first and advancing second is the order that survives a
    session dying between the two.

    Args:
        directive: Instruction text for the new cycle.
        item: The roadmap item the new cycle will work, or ``None``.
        complete_current: Whether the previous cycle's in-flight item counts as
            finished. Pass False to say an item was abandoned even though the
            loop is moving away from it - the one case the rule above cannot
            infer. It cannot force a carried-forward item to be credited,
            because there is no honest reason to want that.
        path: State file to read and write. Defaults to the standard location.
        state: Starting state. Defaults to whatever :func:`load` returns, which
            is the normal case - a fresh session knows nothing and reads disk.

    Returns:
        The new, already-saved state.
    """
    current = state if state is not None else load(path)

    completed = list(current.completed)
    # Advancing to no item at all still finishes the previous one, so only
    # `X -> X` is a retry. `None -> None` compares equal here and needs no
    # special case, because `current.item` is falsy and blocks the credit
    # anyway - an explicit `item is not None` guard was written first and then
    # deleted, because mutating it away killed no test. An inert clause with a
    # confident comment on it is worse than no clause.
    carried_forward = item == current.item
    credit_the_previous_item = (
        complete_current
        and not carried_forward
        and current.item
        and current.item not in completed
    )
    if credit_the_previous_item:
        completed.append(current.item)

    # A CREDITED ITEM IS FINISHED, so leaving its dispatch record standing
    # would make the interlock lie in the one direction that costs most: a
    # recovering session that cannot trust the list stops reading it, and an
    # interlock nobody reads is worse than none, because it looks like cover.
    # Only the credited item is retired - a carried-forward item is a retry and
    # is still running, and a sibling slice's record is not this call's to
    # touch. ``OPS-27``.
    remaining = [
        row
        for row in current.in_flight
        if not (credit_the_previous_item and row["item"] == current.item)
    ]

    advanced = dc_replace(
        current,
        cycle=current.cycle + 1,
        directive=directive,
        item=item,
        completed=completed,
        in_flight=remaining,
        recovered=False,
        recovery_note="",
    )
    save(advanced, path)
    return advanced


def dispatch(
    *items: str,
    lane: str | None = None,
    paths: list[str] | None = None,
    path: Path | None = None,
    state: LoopState | None = None,
) -> LoopState:
    """Record that work is RUNNING, at the moment it is dispatched - ``OPS-27``.

    **Why this exists, and why it is not a compaction hook.** The measurement
    that closed ``OPS-27``'s criterion 1 caught the live tree at an instant when
    three agents were mid-flight: loop state said no item was in flight, no lane
    state carried one, and ``git status`` was empty. Each of those readings was
    true and the conclusion they composed was false, so a session recovering
    from disk would have dispatched the same three items on top of the ones
    already writing. **The thing lost is not a fact, it is an interlock**, and
    its failure mode is a write collision rather than an absence.

    Compaction is only one way to lose it. A crash, an interrupt, a reboot and
    simply running out of context lose exactly the same thing, and a
    ``PreCompact`` hook covers none of them. A write at dispatch covers all of
    them, needs no hook and no new event registration, and goes through the
    atomic writer that is already here.

    **The record's shape is the privacy control.** Ids, a lane and
    repo-relative paths. There is no free-text field, so there is nowhere for
    conversation content, a log line or an identifier to sit. That is
    ``OPS-27`` criterion 3 met structurally rather than by a scan that has to
    be kept current.

    Additive and de-duplicating: dispatching an item already recorded leaves
    one record, so a lane re-dispatched after a retry does not accumulate.

    **Dispatching parallel slices means they share one worktree.** Read the ban
    that :func:`in_flight_summary` renders before handing any of them a file
    list, and pass it on: the list scopes their edits and cannot scope a
    repo-wide git command. ``OPS-54``.
    """
    if not items:
        raise ValueError("dispatch() needs at least one item id")
    target = default_state_path() if path is None else path
    current = load(target) if state is None else state
    existing = {(row["item"], row.get("lane")) for row in current.in_flight}
    now = _now()
    rows = list(current.in_flight)
    for item in items:
        record = {"item": _checked_id(item, "a dispatch item"), "at": now}
        if lane is not None:
            record["lane"] = _checked_id(lane, "a dispatch lane")
        if paths is not None:
            record["paths"] = [_checked_path(one) for one in paths]
        # KEYED ON (item, lane). Two lanes working one item on disjoint files
        # is this project's stated default shape, and de-duplicating on the id
        # alone collapsed that into a single slice - losing exactly the
        # interlock this field exists to hold.
        key = (record["item"], record.get("lane"))
        if key in existing:
            continue
        existing.add(key)
        rows.append(_checked_record(record))
    current.in_flight = rows
    save(current, target)
    return current


def retire(
    *items: str,
    path: Path | None = None,
    state: LoopState | None = None,
) -> LoopState:
    """Drop the dispatch records for ``items``. Unknown ids are ignored.

    ITEM-SCOPED, not lane-scoped: retiring an item clears every lane recorded
    against it. That is the right default for the wrap, where an item is
    finished as a whole, and it is stated here because :func:`dispatch` keys on
    the pair and a reader could reasonably expect the symmetry.

    Ignoring an unknown id rather than raising: retiring is what a caller does
    on the way out of a slice, including one that died, and a wrap that raises
    because a record was already gone would leave the rest of the list stale.
    """
    target = default_state_path() if path is None else path
    current = load(target) if state is None else state
    wanted = set(items)
    current.in_flight = [row for row in current.in_flight if row["item"] not in wanted]
    save(current, target)
    return current


def in_flight_summary(state: LoopState) -> str:
    """One block naming every running slice, for a cold session to act on.

    Written for the reader who has just resumed and needs to know whether
    dispatching an item would collide with work already under way.

    **It also carries the shared-worktree command ban** - ``OPS-54``. The
    file-list rule scopes a slice's EDITS and says nothing about a command whose
    scope is the whole repository, so a slice can obey its list perfectly and
    still stash, reset or clean away every sibling's half-finished work. That
    was measured here on 2026-09-08, twice in one session and twice in the one
    before. The ban is rendered from :data:`ops.store_drift.SHARED_WORKTREE_BAN`
    rather than restated, because two copies of a rule are one stale copy
    waiting to happen.

    **It is printed even when nothing is in flight**, which is the case the
    first version early-returned on. A dispatcher reads this summary precisely
    when it is about to START work, which is usually when the list is still
    empty; a ban shown only once slices are already running is shown too late
    to prevent anything.
    """
    if not state.in_flight:
        lines = ["in flight: nothing recorded as running"]
    else:
        lines = [f"in flight: {len(state.in_flight)} slice(s) recorded as RUNNING"]
        for row in state.in_flight:
            lane = f" lane={row['lane']}" if row.get("lane") else ""
            files = f" paths={','.join(row['paths'])}" if row.get("paths") else ""
            lines.append(f"  {row['item']} dispatched {row.get('at', 'UNKNOWN')}{lane}{files}")
        lines.append(
            "  A record here is not proof the work is still alive - it is proof it "
            "was STARTED and never retired. Reconcile against git and the roadmap "
            "before dispatching any of these again."
        )
    # Rendered VERBATIM, trailing newline and all. Reformatting it here would
    # make this a second, slightly different copy of the rule - which is the
    # exact failure the single-constant arrangement exists to prevent.
    lines.append("")
    lines.append(store_drift.SHARED_WORKTREE_BAN)
    return "\n".join(lines)
