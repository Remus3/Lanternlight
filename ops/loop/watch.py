"""Supervise the session watcher so no session has to remember to arm it.

ROADMAP item ``4d``. Item ``4c`` shipped the entry point
(``python -m lanternlight.armwatch``) and it works. What it never shipped was
its own stated aim - that arming the watcher "is not something a session has to
remember" - and two sessions proved the gap is real, not theoretical:
**2026-08-30 launched the client with nothing armed**, and **2026-08-31 found
the successor log still single-copy**. Both were the same failure: a human
step that had to be recalled, and was not.

So this module is called by a loop cycle at start, unconditionally. A cycle
that arms is a cycle that cannot forget, and the record it leaves behind is
readable by a LATER session, which is the property that makes this continuity
rather than a convenience: continuity lives on disk, never in a context window.

Three properties are load-bearing.

**It refuses to start a second watcher.** If the recorded pid is still alive,
:func:`ensure_armed` returns ``armed=False`` and spawns nothing. Two pollers on
the same four sources double the snapshot traffic, and ``C:/ll-captures`` was
already 9.87 GB across 19,162 files when ``OPS-14`` was opened on 2026-08-31.

**It never terminates anything.** There is no stop path here, no signal, no
``taskkill``, and no way to ask the incumbent watcher to go away. Exactly like
:mod:`ops.loop.guard`, whose prohibition this inherits verbatim: deciding that
another process is unwanted is an operator decision, and an unattended loop is
the wrong thing to be making it. That is also why
:func:`session_armed` has a deliberately empty exit - the watcher is *supposed*
to outlive the session that armed it, so stopping it at the end of a cycle
would defeat the entire point.

**Liveness is delegated, not re-derived.** ``os.kill(pid, 0)`` is the usual
POSIX existence probe, but on Windows CPython ``os.kill`` maps onto
``TerminateProcess`` for any signal other than the two console-control events,
so the conventional "harmless" probe would kill the process it is asking about.
:func:`ops.loop.guard.pid_is_alive` already solves that with ``OpenProcess``
plus ``GetExitCodeProcess``. This module imports it rather than writing a
second one, because a trap that is solved once is still a trap the second time.

CAVEAT, written down rather than only thought: an unreadable record reads as
"nothing armed", so a record corrupted by a power loss mid-write leads to a
second watcher being armed alongside a live one. That is why the record's shape
is kept as small as it can be - four flat fields, no schema marker, no nested
structure - and why every write goes through a temp file and a
:meth:`pathlib.Path.replace`. Fewer ways to be unreadable is the mitigation;
there is no way to make it impossible without a probe of the process table that
this module has no business running.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ops.loop import guard

__all__ = [
    "WATCH_RECORD_FILENAME",
    "ArmResult",
    "WatchRecord",
    "armed_pid",
    "default_spawn",
    "ensure_armed",
    "is_armed",
    "read_record",
    "record_path",
    "session_armed",
    "temp_prefix_for",
    "write_record",
]

#: Name of the arming record inside the runtime directory.
WATCH_RECORD_FILENAME = "armwatch.json"

#: Prefix given to every temporary file this module creates. Tests assert on it
#: to prove the temp-then-replace path was actually taken.
TEMP_PREFIX = ".armwatch-"

#: Windows creation flags that detach a child from this console and give it its
#: own process group, so the watcher survives the session that armed it and
#: does not receive this console's Ctrl-C.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def record_path() -> Path:
    """Return the default arming-record path, inside the gitignored runtime dir."""
    return guard.runtime_dir() / WATCH_RECORD_FILENAME


def temp_prefix_for(target: Path) -> str:
    """Return the temp-file prefix used when writing ``target``.

    Exposed so a test can prove a write really did go through a temporary file
    rather than truncating the target in place.
    """
    return f"{TEMP_PREFIX}{target.name}-"


def _now() -> datetime:
    """Return the current UTC time at second resolution."""
    return datetime.now(UTC).replace(microsecond=0)


def _stamp(when: datetime) -> str:
    """Format ``when`` as a second-resolution ISO 8601 string."""
    return when.replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class WatchRecord:
    """What a later session needs to know about the watcher that is running.

    Attributes:
        pid: The watcher process. Its liveness is the whole refusal test.
        dest_base: The root the watcher was handed. The watcher re-derives its
            dated destination from this on every pass, so this - not
            ``dest_root`` - is the durable fact.
        dest_root: The dated destination as resolved at arming time. Recorded
            so a session can find today's captures without re-deriving them,
            and deliberately NOT treated as authoritative once midnight passes:
            a watcher handed a literal dated path keeps writing to it forever,
            which is how an archive directory comes to claim a day it does not
            cover.
        started: ISO 8601 UTC, second resolution, of the arming.
    """

    pid: int
    dest_base: str
    dest_root: str
    started: str

    def to_dict(self) -> dict:
        """Return the persistable payload - four flat fields, nothing else."""
        return {
            "pid": self.pid,
            "dest_base": self.dest_base,
            "dest_root": self.dest_root,
            "started": self.started,
        }


@dataclass(frozen=True)
class ArmResult:
    """The outcome of one :func:`ensure_armed` call.

    Attributes:
        armed: True only when THIS call started a watcher. A refusal because
            one is already running is not an arming, and conflating the two is
            how a caller ends up believing it owns a process it did not start.
        pid: The watcher's pid - the one just started, or the incumbent's.
        dest_root: Where that watcher archives to.
        reason: Why the call did what it did, in words. This is what a later
            session or an operator reads when the archive looks wrong, so it
            names the pid and the destination rather than a status code.
    """

    armed: bool
    pid: int | None
    dest_root: str | None
    reason: str


def write_record(record: WatchRecord, path: Path | None = None) -> Path:
    """Write ``record`` atomically and return the path written.

    The write goes to a uniquely named temporary file in the target's own
    directory - same directory, so the final move is a rename within one
    filesystem, which is what makes it atomic - and is flushed and fsynced
    before the move. A later session polling this file sees either the whole
    old record or the whole new one, never a splice; a splice with no readable
    pid would read as "nothing armed" and start a second watcher.
    """
    target = Path(path) if path is not None else record_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    body = json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"

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


def read_record(path: Path | None = None) -> WatchRecord | None:
    """Read the arming record, or return ``None``. Never raises.

    ``None`` covers every unusable case - absent, unreadable, invalid JSON,
    valid JSON of the wrong shape, a pid that is not a positive integer -
    because the caller treats them identically. A loop that crashes on a
    truncated record is a loop that needs an operator, which is the thing this
    whole package exists to avoid.

    The file is never repaired or deleted here. A corrupt record is evidence,
    and destroying it is how the next session loses the only clue it had.
    """
    target = Path(path) if path is not None else record_path()

    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, ValueError):
        # OSError covers absent, a directory, and a locked-down ACL. ValueError
        # covers a file whose bytes are not decodable as UTF-8.
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    pid = payload.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None

    fields: dict[str, str] = {}
    for name in ("dest_base", "dest_root", "started"):
        value = payload.get(name)
        if not isinstance(value, str):
            return None
        fields[name] = value

    return WatchRecord(pid=pid, **fields)


def armed_pid(path: Path | None = None) -> int | None:
    """Return the recorded pid if and only if it is still running.

    A record naming a dead pid is stale, not armed - the previous watcher died,
    or the machine rebooted, and nothing is polling. Reporting it as armed
    would be the 2026-08-30 failure with extra steps.
    """
    record = read_record(path)
    if record is None:
        return None
    if not guard.pid_is_alive(record.pid):
        return None
    return record.pid


def is_armed(path: Path | None = None) -> bool:
    """Return True if a watcher recorded at ``path`` is still running."""
    return armed_pid(path) is not None


def _default_dest_root_fn(dest_base: Path, when: datetime) -> Path:
    """Resolve the dated destination for ``dest_base`` at ``when``.

    Imported inside the function body on purpose, twice over. It keeps this
    module importable while ``lanternlight.armwatch`` is being extended by
    another slice of item 4d, and it keeps the ops loop package from taking a
    module-scope dependency on the lanternlight package for a default that most
    callers override anyway.

    ``when`` is converted to LOCAL time first, and the two clocks in play here
    are not a muddle to tidy up - they are both deliberate.
    :attr:`WatchRecord.started` is UTC because it is a moment in time that a
    later session compares against the game log, which timestamps in UTC. The
    dated DIRECTORY is local because snapshot filenames are stamped local and
    the capture tree on this machine is named in local dates. This machine sits
    at UTC-5, so handing a UTC instant straight to ``dated_dest_root`` would
    file the last five hours of every local day under tomorrow - the exact
    mislabelled-archive defect item 4d is about. A naive ``when`` is taken as
    local, which is what :meth:`datetime.astimezone` already assumes.
    """
    from lanternlight.armwatch import dated_dest_root

    return Path(dated_dest_root(dest_base, now=when.astimezone()))


def default_spawn(dest_base: Path, dest_root: Path) -> int:
    """Start the real watcher, detached, and return its pid.

    Detached is the requirement, not a nicety: the watcher must outlive the
    session that armed it, or it dies with the cycle and the next launch is
    unwatched again - which is exactly the failure being fixed. On Windows that
    means ``DETACHED_PROCESS`` plus ``CREATE_NEW_PROCESS_GROUP`` so the child
    has no console of ours and does not receive our Ctrl-C; elsewhere it means
    a new session. Both streams go to the null device so a long-running child
    cannot block on a pipe nobody is draining.

    ``dest_root`` is recorded, not commanded. The child is handed
    ``--dest-base`` and re-derives its dated destination itself, because a
    watcher given a literal dated path keeps writing to it past midnight and
    the archive then claims to cover a day it does not.

    This function is never called by the test suite. Every test injects its own
    ``spawn_fn``, because a leaked default would leave a poller running against
    the operator's real ``Saved/`` directory after the suite exits.
    """
    extra: dict[str, object] = {}
    if sys.platform == "win32":
        extra["creationflags"] = _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    else:
        extra["start_new_session"] = True

    # Fixed argv, no shell, and nothing here is interpolated from untrusted
    # input - the only variable is a destination path the caller chose.
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lanternlight.armwatch",
            "--dest-base",
            str(dest_base),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(guard.REPO_ROOT),
        close_fds=True,
        **extra,
    )
    return child.pid


def ensure_armed(
    dest_base: Path | str,
    *,
    spawn_fn: Callable[[Path, Path], int] | None = None,
    dest_root_fn: Callable[[Path, datetime], Path] | None = None,
    now: datetime | None = None,
    path: Path | None = None,
) -> ArmResult:
    """Make sure a watcher is running, without starting a second one.

    Three outcomes, in the order they are decided:

    1. A record exists and its pid is ALIVE. Nothing is spawned, nothing is
       stopped, and ``armed`` is False. Two pollers on the same four sources
       double the snapshot traffic while ``OPS-14`` is open.
    2. A record exists and its pid is DEAD. It is stale - the previous watcher
       is gone - so a new one is armed and ``reason`` says the record was
       stale, because "armed" and "re-armed after a crash" are different facts
       and an operator reading the record deserves to be told which happened.
    3. There is no usable record at all. Arm.

    Args:
        dest_base: Root under which the watcher archives. The dated
            destination is derived from it per run, never passed once.
        spawn_fn: ``(dest_base, dest_root) -> pid``. Defaults to
            :func:`default_spawn`. Injected by every test so no test starts a
            real process.
        dest_root_fn: ``(dest_base, now) -> Path``. Defaults to
            :func:`_default_dest_root_fn`, which resolves it through
            ``lanternlight.armwatch``.
        now: Arming time, UTC. Defaults to the current time.
        path: Arming record. Defaults to :func:`record_path`.

    Returns:
        An :class:`ArmResult` whose ``armed`` is True only if THIS call started
        a watcher.
    """
    target = Path(path) if path is not None else record_path()
    base = Path(dest_base)
    when = _now() if now is None else now

    existing = read_record(target)
    if existing is not None and guard.pid_is_alive(existing.pid):
        return ArmResult(
            armed=False,
            pid=existing.pid,
            dest_root=existing.dest_root,
            reason=(
                f"a watcher is already running as pid {existing.pid} since "
                f"{existing.started}, archiving into {existing.dest_root}; refusing to "
                "start a second one, which would double the snapshot traffic on the "
                "same four sources. Nothing was stopped and nothing was changed."
            ),
        )

    if existing is None:
        why = f"no usable watcher record at {target}"
    else:
        why = (
            f"the watcher recorded at {target} is stale - pid {existing.pid} is no "
            "longer running"
        )

    resolve = _default_dest_root_fn if dest_root_fn is None else dest_root_fn
    root = Path(resolve(base, when))

    spawn = default_spawn if spawn_fn is None else spawn_fn
    pid = int(spawn(base, root))

    record = WatchRecord(
        pid=pid,
        dest_base=str(base),
        dest_root=str(root),
        started=_stamp(when),
    )
    write_record(record, target)

    return ArmResult(
        armed=True,
        pid=record.pid,
        dest_root=record.dest_root,
        reason=f"{why}; armed a watcher as pid {record.pid} archiving into {record.dest_root}",
    )


@contextmanager
def session_armed(dest_base: Path | str, **kwargs) -> Iterator[ArmResult]:
    """Arm a watcher for the duration of a session, and leave it running.

    The body of the ``with`` block is an ordinary session - a loop cycle,
    a research pass, anything. It never has to know this exists, which is the
    whole acceptance criterion of item 4d.

    The exit is deliberately EMPTY, and that is a decision rather than an
    omission. The watcher is meant to outlive the session: a launch happens
    when the operator launches, not when a cycle happens to be running, so
    tearing it down at the end of the block would restore exactly the failure
    this replaces. And this module never terminates anything in any case.

    A refusal is not an error. When a watcher is already running the block
    still runs, with ``armed=False`` - the session's own work has nothing to do
    with who owns the poller.

    Yields:
        The :class:`ArmResult` from :func:`ensure_armed`.
    """
    yield ensure_armed(dest_base, **kwargs)
