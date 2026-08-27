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
import tempfile
from dataclasses import dataclass, field, replace as dc_replace
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "LoopState",
    "STATE_FILENAME",
    "advance_cycle",
    "default_state_path",
    "load",
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

        return cls(
            cycle=cycle,
            directive=directive,
            item=item,
            updated=updated,
            completed=list(completed),
        )


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

    advanced = dc_replace(
        current,
        cycle=current.cycle + 1,
        directive=directive,
        item=item,
        completed=completed,
        recovered=False,
        recovery_note="",
    )
    save(advanced, path)
    return advanced
