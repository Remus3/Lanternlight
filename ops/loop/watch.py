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

ROADMAP item ``4e`` - the WRAP side
-----------------------------------

Everything above answers "was a watcher armed on the way IN". Item ``4e`` is
the next failure along, and ledger ``LL-0117`` measured it: on 2026-09-01 a
watcher was armed as pid 17568, correctly REFUSED two re-arm attempts during
the session because it was still alive, and was found DEAD at the wrap. For an
unmeasured stretch nothing was archiving the log, the saves or the market
cache. **A refusal to re-arm is only as good as the process it deferred to**,
and nothing re-checked that process between the arming and the next session
entry - which is precisely when a session hands the machine back to an operator
who is about to launch the client.

:func:`check_watcher` and :func:`ensure_armed_at_wrap` close that, and they add
two things a naive liveness re-check would miss.

**Liveness is not identity.** A pid can be RECYCLED, so "a process with this
number exists" is strictly weaker than "the watcher is running". The evidence
used here is the process CREATION TIME compared against the record's ``started``
stamp - see :func:`process_creation_time`. Command line would be the other
admissible evidence and is deliberately not used: reading another process's
command line on Windows means WMI (a COM dependency this repo does not have,
against ``dependencies = []``) or ``PROCESS_VM_READ`` against the PEB, which is
a strictly stronger right than the one this module is willing to acquire.
``PROCESS_QUERY_LIMITED_INFORMATION`` grants no power to affect the process at
all, and it is enough to answer the question.

**Liveness is not function.** At the cycle 37 wrap pid 23628 was alive AND
identity-confirmed and had archived nothing in over 24 hours. That was the
CORRECT result - the client was closed, the sources did not change, and the
watcher copies each file once - and it is indistinguishable from a watcher that
wedged five minutes after arming. So the watcher writes a heartbeat and
:func:`check_watcher` reads it, and a heartbeat that has stopped advancing is
reported as ``STALE``.

**Still nothing is terminated.** No signal, no ``taskkill``, no stop path, not
even for a ``STALE`` watcher. Item ``4e`` says so in terms: killing is NOT in
scope. This module refuses, re-arms, and reports.
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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ops.loop import guard

__all__ = [
    "HEARTBEAT_FILENAME",
    "HEARTBEAT_FLUSH_THROTTLE_S",
    "HEARTBEAT_STALE_AFTER_S",
    "HEARTBEAT_STALE_MULTIPLE",
    "IDENTITY_TOLERANCE_S",
    "REARM_STATES",
    "SLOWEST_POLL_INTERVAL_S",
    "STATE_ARMED",
    "STATE_DEAD",
    "STATE_IMPOSTOR",
    "STATE_NO_HEARTBEAT",
    "STATE_NO_RECORD",
    "STATE_STALE",
    "WATCH_RECORD_FILENAME",
    "ArmResult",
    "WatchRecord",
    "WatcherStatus",
    "WrapResult",
    "armed_pid",
    "check_watcher",
    "default_spawn",
    "ensure_armed",
    "ensure_armed_at_wrap",
    "heartbeat_path",
    "is_armed",
    "process_creation_time",
    "read_heartbeat",
    "read_record",
    "record_path",
    "session_armed",
    "temp_prefix_for",
    "write_record",
]

#: Name of the arming record inside the runtime directory.
WATCH_RECORD_FILENAME = "armwatch.json"

#: Name of the watcher's heartbeat file, beside the arming record. This layer
#: owns the path and hands it down to the child as ``--heartbeat``; the
#: lanternlight layer never computes it, because :mod:`ops.loop.watch` already
#: imports :mod:`lanternlight.armwatch` and the reverse would be a cycle.
HEARTBEAT_FILENAME = "armwatch_heartbeat.json"

#: Prefix given to every temporary file this module creates. Tests assert on it
#: to prove the temp-then-replace path was actually taken.
TEMP_PREFIX = ".armwatch-"

#: Windows creation flags that detach a child from this console and give it its
#: own process group, so the watcher survives the session that armed it and
#: does not receive this console's Ctrl-C.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200

#: Windows access right that is enough to ask when a process started without
#: acquiring any right to affect it. Declared here rather than imported from
#: :mod:`ops.loop.guard`, whose copy is private - this is a Windows API
#: constant, not a derivation, so there is nothing to keep in sync.
#: `tests/test_loop_watch.py` asserts it is the ONLY right this module asks
#: for, which is the restated form of that module's old blanket ban on
#: ``OpenProcess``: the danger was never the call, it was the RIGHT.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: Windows FILETIME counts 100-nanosecond intervals from this instant.
_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=UTC)

#: How far a process's creation time may sit from the record's ``started``
#: stamp and still be the watcher.
#:
#: MEASURED on this machine 2026-09-02: ``armwatch.json`` recorded
#: ``started: 2026-09-02T01:26:36+00:00`` and pid 23628's true creation time was
#: ``2026-09-02T01:26:36.056876Z`` - the process starts a fraction of a second
#: AFTER the stamp. :func:`_now` also truncates microseconds, so the recorded
#: stamp can sit up to a full second EARLIER than the real call.
#:
#: The window is 120 s, which is far wider than either of those needs, and it
#: is wide ON PURPOSE because the two error directions are not symmetric:
#:
#: * A false IMPOSTOR verdict re-arms ALONGSIDE a live watcher. That is the
#:   double-traffic failure :func:`ensure_armed` exists to refuse, and
#:   ``OPS-14`` (9.87 GB across 19,162 files) is still open.
#: * A missed impostor leaves one poller running under a wrong name. Nothing
#:   doubles, and the next wrap gets another chance.
#:
#: So err toward believing the incumbent. Being generous costs almost nothing
#: against the case this is for: a pid cannot be recycled while its process is
#: alive, so a recycled number's process began after the original watcher died,
#: which on the observed record was over 24 hours after the arming stamp. For a
#: recycled pid to slip through, an unrelated process would have to have
#: started within two minutes of the arming - at which point the original
#: watcher was still running and the number was not available to recycle.
#: 120 s is kept well under an hour so the check is not decorative either.
IDENTITY_TOLERANCE_S = 120.0

#: The slowest of the watcher's four poll intervals - the ``logs`` surface, at
#: 300 s. The other three are 3 s, 3 s and 30 s. Staleness is stated as a
#: multiple of THIS one, because a heartbeat that has outlived the slowest pass
#: has outlived all four.
SLOWEST_POLL_INTERVAL_S = 300.0

#: How often the watcher flushes its heartbeat, at most. Pinned with the
#: armwatch slice of item 4e. Recorded here so the threshold below can be shown
#: to clear it rather than merely asserted to.
HEARTBEAT_FLUSH_THROTTLE_S = 30.0

#: Consecutive missed passes before a heartbeat is called stale. One missed
#: pass is noise - a slow disk, an antivirus scan holding a directory open, a
#: machine that briefly slept. Three consecutive missed passes is a pattern.
HEARTBEAT_STALE_MULTIPLE = 3

#: 900 s. Comfortably clears the 30 s flush throttle - it is 30 times it - so
#: throttling alone can never produce a STALE verdict, which would be the
#: check crying wolf about its own design.
#:
#: CAVEAT, written down rather than only said out loud: a machine that
#: SUSPENDED or HIBERNATED produces a FALSE STALE. Wall clock advances while
#: nothing runs, so a watcher that was polling correctly before the sleep and
#: is polling correctly after it reads as stale across the gap. There is no fix
#: for that from this side short of a monotonic clock the watcher does not
#: publish. It is tolerable because STALE is a REPORT: it never re-arms and it
#: never stops anything, so the cost of a false one is a line of prose an
#: operator can discount, not a second poller.
HEARTBEAT_STALE_AFTER_S = SLOWEST_POLL_INTERVAL_S * HEARTBEAT_STALE_MULTIPLE

#: No usable arming record. NOT armed.
STATE_NO_RECORD = "NO_RECORD"

#: The recorded pid is not running. NOT armed. This is the LL-0117 failure.
STATE_DEAD = "DEAD"

#: The pid is alive but its creation time is outside the identity window, so it
#: is some unrelated process that inherited the number. NOT armed.
STATE_IMPOSTOR = "IMPOSTOR"

#: Identity confirmed, but no heartbeat exists or it is unreadable. ARMED.
STATE_NO_HEARTBEAT = "NO_HEARTBEAT"

#: Identity confirmed, heartbeat present but not advancing. ARMED.
STATE_STALE = "STALE"

#: Identity confirmed and the heartbeat is fresh.
STATE_ARMED = "ARMED"

#: The three states that mean NOTHING is polling, and the only three the wrap
#: re-arms on. The other three are reported and left alone - see
#: :func:`ensure_armed_at_wrap` for why re-arming any of them would be a
#: regression rather than a stricter check.
REARM_STATES = frozenset({STATE_NO_RECORD, STATE_DEAD, STATE_IMPOSTOR})


def record_path() -> Path:
    """Return the default arming-record path, inside the gitignored runtime dir."""
    return guard.runtime_dir() / WATCH_RECORD_FILENAME


def heartbeat_path() -> Path:
    """Return the default heartbeat path, beside the arming record.

    Mirrors :func:`record_path` deliberately: one runtime directory, two files,
    both gitignored, so a session diagnosing the archive has one place to look.
    """
    return guard.runtime_dir() / HEARTBEAT_FILENAME


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

    ``--heartbeat`` is handed down for item ``4e``: this layer owns the path so
    the lanternlight layer never has to compute it, which would mean importing
    :mod:`ops.loop.watch` from :mod:`lanternlight.armwatch` and closing an
    import cycle. Without the flag the watcher's behaviour is unchanged, so an
    older child on the path still runs; it just leaves the wrap-side check
    reporting ``NO_HEARTBEAT``, which is still ARMED.

    This function is never called by the test suite with a real ``Popen``. The
    arming tests inject their own ``spawn_fn`` and the one test that checks the
    argv fakes ``Popen``, because a leaked default would leave a poller running
    against the operator's real ``Saved/`` directory after the suite exits.
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
            "--heartbeat",
            str(heartbeat_path()),
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
    disqualified_pid: int | None = None,
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
        disqualified_pid: A pid the CALLER has already established is not the
            watcher, so its liveness must not count as an incumbent. Added for
            item ``4e``: :func:`check_watcher` can find the recorded pid alive
            but its process creation time far from the arming stamp, which
            means the number was recycled by something unrelated. Without this,
            outcome 1 below would refuse to re-arm on behalf of a process that
            is not the watcher at all, which is exactly the failure ``4e``
            exists to close. Defaults to ``None``, which disqualifies nothing,
            so every existing caller is unaffected.

    Returns:
        An :class:`ArmResult` whose ``armed`` is True only if THIS call started
        a watcher.
    """
    target = Path(path) if path is not None else record_path()
    base = Path(dest_base)
    when = _now() if now is None else now

    existing = read_record(target)
    disqualified = existing is not None and existing.pid == disqualified_pid
    if existing is not None and not disqualified and guard.pid_is_alive(existing.pid):
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
    elif disqualified:
        why = (
            f"pid {existing.pid} recorded at {target} is alive but is NOT the watcher - "
            "the caller established that its identity does not match the record, so the "
            "number was recycled by something unrelated"
        )
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


# ---------------------------------------------------------------------------
# ROADMAP 4e - the wrap-side check
# ---------------------------------------------------------------------------


def _as_utc(when: datetime) -> datetime:
    """Return ``when`` as an aware UTC datetime, treating naive input as UTC."""
    if when.tzinfo is None:
        return when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def _parse_stamp(text: object) -> datetime | None:
    """Parse an ISO 8601 stamp, or return ``None``. Never raises.

    ``None`` means "cannot tell", which is a third answer and not a verdict.
    Every caller here treats it that way.
    """
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _windows_process_creation_time(pid: int) -> datetime | None:
    """Return when ``pid`` started, as aware UTC, or ``None`` if it cannot tell.

    Follows the ctypes idiom in :func:`ops.loop.guard._windows_pid_is_alive`
    exactly - explicit ``restype`` and ``argtypes``, ``use_last_error``, and a
    ``CloseHandle`` in a ``finally`` - because a handle leaked from a check
    that runs every wrap is a handle leaked forever.

    ``PROCESS_QUERY_LIMITED_INFORMATION`` is the only right asked for. It is
    enough for ``GetProcessTimes`` and it grants no power to affect the
    process, which is the property that lets this module keep its promise not
    to terminate anything.

    ``psutil`` would answer this in one line and is installed on this machine.
    It is NOT used: ``dependencies = []`` in ``pyproject.toml`` is deliberate,
    and a standard-library-only repo that quietly relies on an undeclared
    package fails on the first fresh clone rather than here.
    """
    import ctypes
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = (
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
    )
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # No such process, or it is gone and unopenable. Either way there is no
        # creation time to report, and reporting one anyway would be fiction.
        return None
    try:
        created = _FILETIME()
        exited = _FILETIME()
        in_kernel = _FILETIME()
        in_user = _FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(in_kernel),
            ctypes.byref(in_user),
        )
        if not ok:
            return None
        raw = (created.dwHighDateTime << 32) | created.dwLowDateTime
        if raw <= 0:
            return None
        # 100-nanosecond intervals since 1601-01-01 UTC. Split rather than
        # divided by 10.0, because a float microsecond count at this magnitude
        # has lost the sub-second precision the identity comparison reports.
        return _FILETIME_EPOCH + timedelta(
            seconds=raw // 10_000_000,
            microseconds=(raw % 10_000_000) // 10,
        )
    finally:
        kernel32.CloseHandle(handle)


def process_creation_time(pid: int | None) -> datetime | None:
    """Return when ``pid`` started, as aware UTC, or ``None`` for cannot-tell.

    ``None`` is a real third answer, not a failure to be papered over: on any
    platform without the probe, on any error, and for any pid that is not a
    positive integer. A probe that invented a plausible datetime on failure
    would settle the identity question with fiction, and a wrong IMPOSTOR
    verdict re-arms a second poller beside a live watcher.

    The exception list is NAMED rather than a bare ``except Exception``. This
    repo has already paid for that: ``AssertionError`` is an ``Exception``, so
    a blanket catch inside code a test spies on swallows the test's own
    assertion and the spy goes vacuous. These four are the realistic ctypes
    failure modes - a missing DLL or symbol, an argtype mismatch, an integer
    that will not fit a DWORD.
    """
    if pid is None or not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    if sys.platform != "win32":
        # POSIX has no portable creation-time call: /proc/<pid>/stat field 22
        # is Linux-only and is in clock ticks since boot, which needs a boot
        # time this module would then have to trust. Cannot-tell is honest.
        return None
    try:
        return _windows_process_creation_time(pid)
    except (OSError, AttributeError, ValueError, OverflowError):
        return None


def _identity_matches(created: datetime | None, started: datetime | None) -> bool | None:
    """Is ``created`` close enough to ``started`` to be the same process?

    Three answers, and the third one matters most. ``None`` means the question
    could not be asked - no creation time available, or an unparseable arming
    stamp - and it must NOT read as ``False``, because only ``False`` produces
    an IMPOSTOR verdict and only an IMPOSTOR verdict re-arms. See
    :data:`IDENTITY_TOLERANCE_S` for why the window is deliberately generous.
    """
    if created is None or started is None:
        return None
    return abs((created - started).total_seconds()) <= IDENTITY_TOLERANCE_S


def read_heartbeat(path: Path | None = None) -> dict | None:
    """Read the watcher's heartbeat as a plain dict, or return ``None``.

    Never raises, for the same reason :func:`read_record` never raises: a wrap
    that crashes on a half-written file is a wrap that needs an operator.
    ``None`` covers absent, unreadable, invalid JSON, and valid JSON that is
    not an object.

    Only the SHAPE is checked here. Whether the payload's ``written`` stamp
    parses, and whether its ``pid`` is the one that was armed, are decided by
    :func:`check_watcher`, which needs to say WHICH of them was wrong in the
    sentence an operator reads.

    The file is never repaired or deleted. A corrupt heartbeat is evidence.
    """
    target = Path(path) if path is not None else heartbeat_path()

    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


@dataclass(frozen=True)
class WatcherStatus:
    """What :func:`check_watcher` found, and what an operator should read.

    Attributes:
        state: One of the six ``STATE_*`` constants.
        pid: The recorded pid, or ``None`` when there was no usable record.
        dest_root: Where that watcher archives to, as recorded.
        evidence: The observations the verdict rests on, in the order they
            were made. Item ``4e`` asks the check to NAME its evidence, and a
            verdict whose grounds are not written down is a status code with
            extra syllables.
        heartbeat_age_s: Seconds since the heartbeat's ``written`` stamp, or
            ``None`` when there was no readable heartbeat. Absent, not zero -
            "unmeasured" and "measured zero" are different facts.
        reason: Why, in words, naming the pid and the destination the way
            :attr:`ArmResult.reason` does. This is what a later session or an
            operator reads when the archive looks wrong.
    """

    state: str
    pid: int | None
    dest_root: str | None
    evidence: tuple[str, ...]
    heartbeat_age_s: float | None
    reason: str

    @property
    def armed(self) -> bool:
        """True when something IS polling, whatever else is wrong with it.

        Derived from :attr:`state` rather than stored, so the two can never
        drift apart. ``NO_HEARTBEAT`` and ``STALE`` are both armed: they are
        reports about a watcher that exists, not grounds to start another one.
        """
        return self.state not in REARM_STATES


@dataclass(frozen=True)
class WrapResult:
    """The outcome of one :func:`ensure_armed_at_wrap` call.

    Attributes:
        status: What the check found BEFORE anything was re-armed.
        arm: The :class:`ArmResult` from the re-arm, or ``None`` when no re-arm
            was attempted - which is the case for every state that already has
            a watcher.
        reason: The whole story in one string, check and re-arm together.
    """

    status: WatcherStatus
    arm: ArmResult | None
    reason: str

    @property
    def rearmed(self) -> bool:
        """True only when THIS call started a watcher."""
        return self.arm is not None and self.arm.armed


def check_watcher(
    *,
    path: Path | None = None,
    heartbeat: Path | None = None,
    now: datetime | None = None,
    creation_time_fn: Callable[[int], datetime | None] | None = None,
) -> WatcherStatus:
    """Ask whether the recorded watcher is really running, and really polling.

    Six states, decided in this order, because each one is a precondition for
    asking the next:

    1. ``NO_RECORD`` - no usable arming record. NOT armed.
    2. ``DEAD`` - the recorded pid is not alive. NOT armed. This is the
       ``LL-0117`` failure: armed as pid 17568, two later re-arms correctly
       refused while it lived, found dead at the wrap.
    3. ``IMPOSTOR`` - the pid IS alive but its creation time is outside
       :data:`IDENTITY_TOLERANCE_S` of the arming stamp, so the number was
       recycled by something unrelated. NOT armed. A check that stopped at
       liveness would pass here, and that is the gap item ``4e`` names.
    4. ``NO_HEARTBEAT`` - identity confirmed, but no heartbeat exists, or it is
       unreadable, or it names a different pid. **Reported, and still ARMED.**
    5. ``STALE`` - identity confirmed, heartbeat present, not advancing within
       :data:`HEARTBEAT_STALE_AFTER_S`. **Reported, and still ARMED.**
    6. ``ARMED`` - identity confirmed and the heartbeat is fresh.

    ``NO_HEARTBEAT`` being ARMED is the load-bearing decision here, and it is
    not a corner case. Pid 23628 is running on this machine right now, armed
    before the heartbeat existed, and it passes the identity check. Treating an
    absent heartbeat as a dead watcher would spawn a second poller on the same
    four sources - the exact thing :func:`ensure_armed` refuses to do - so it
    would be a REGRESSION wearing the clothes of a stricter check.

    CAVEAT, written down rather than only said: a machine that SUSPENDED or
    HIBERNATED produces a false ``STALE``, because wall clock advances while
    nothing runs. That is tolerable only because ``STALE`` re-arms nothing and
    stops nothing. See :data:`HEARTBEAT_STALE_AFTER_S`.

    SECOND CAVEAT: staleness is judged on the heartbeat's ``written`` stamp
    alone. The per-surface stamps are recorded in ``evidence`` but do NOT
    trigger ``STALE``, so a watcher whose main loop still writes while ONE of
    its four surfaces has wedged reads as ARMED here. That is a known,
    deliberate limit of this pass, not an oversight: the four surfaces poll at
    3 s, 3 s, 30 s and 300 s and a source directory the game has not created
    yet may never produce a pass at all, so a per-surface threshold needs its
    own measured argument before it can be a verdict.

    Args:
        path: Arming record. Defaults to :func:`record_path`.
        heartbeat: Heartbeat file. Defaults to :func:`heartbeat_path`.
        now: The moment to measure against, UTC. Defaults to the current time.
        creation_time_fn: ``(pid) -> datetime | None``. Defaults to
            :func:`process_creation_time`. Injected by tests so the verdict can
            be pinned on a platform without the probe.

    Returns:
        A :class:`WatcherStatus`. Nothing is spawned and nothing is stopped.
    """
    target = Path(path) if path is not None else record_path()
    beat = Path(heartbeat) if heartbeat is not None else heartbeat_path()
    when = _now() if now is None else _as_utc(now)
    creation_of = process_creation_time if creation_time_fn is None else creation_time_fn

    evidence: list[str] = [f"arming record: {target}"]

    record = read_record(target)
    if record is None:
        return WatcherStatus(
            state=STATE_NO_RECORD,
            pid=None,
            dest_root=None,
            evidence=tuple(evidence),
            heartbeat_age_s=None,
            reason=(
                f"no usable watcher record at {target}, so nothing is archiving the log, "
                "the saves or the market cache. Arming one is the whole point of handing "
                "the machine back in a known state."
            ),
        )

    evidence.append(
        f"record: pid {record.pid}, armed {record.started}, archiving into {record.dest_root}"
    )

    if not guard.pid_is_alive(record.pid):
        evidence.append(f"liveness: guard.pid_is_alive({record.pid}) is False")
        return WatcherStatus(
            state=STATE_DEAD,
            pid=record.pid,
            dest_root=record.dest_root,
            evidence=tuple(evidence),
            heartbeat_age_s=None,
            reason=(
                f"the watcher recorded at {target} as pid {record.pid}, archiving into "
                f"{record.dest_root} since {record.started}, is NOT running. This is the "
                "LL-0117 failure exactly: armed, then trusted by every later re-arm "
                "attempt, then dead before the wrap with nothing archiving. Re-arm."
            ),
        )

    evidence.append(f"liveness: guard.pid_is_alive({record.pid}) is True")

    created = creation_of(record.pid)
    started = _parse_stamp(record.started)
    verdict = _identity_matches(created, started)

    if verdict is False:
        offset = abs((created - started).total_seconds())
        evidence.append(
            f"identity: process creation time {created.isoformat()} against recorded "
            f"started {record.started}, {offset:.3f} s apart, OUTSIDE the "
            f"{IDENTITY_TOLERANCE_S:.0f} s window"
        )
        return WatcherStatus(
            state=STATE_IMPOSTOR,
            pid=record.pid,
            dest_root=record.dest_root,
            evidence=tuple(evidence),
            heartbeat_age_s=None,
            reason=(
                f"pid {record.pid} is alive but it is NOT the watcher recorded at "
                f"{target}: that process started {created.isoformat()} while the record "
                f"says the watcher was armed {record.started}, {offset:.0f} s apart and "
                f"outside the {IDENTITY_TOLERANCE_S:.0f} s identity window. The number was "
                f"recycled by something unrelated, and nothing is archiving into "
                f"{record.dest_root}. Re-arm."
            ),
        )

    if verdict is None:
        evidence.append(
            "identity: process creation time unavailable, so identity could be neither "
            "confirmed nor refuted; the incumbent is believed, which is the cheaper error"
        )
    else:
        offset = abs((created - started).total_seconds())
        evidence.append(
            f"identity: process creation time {created.isoformat()} against recorded "
            f"started {record.started}, {offset:.3f} s apart, inside the "
            f"{IDENTITY_TOLERANCE_S:.0f} s window"
        )

    confirmed = (
        f"pid {record.pid} is the watcher recorded at {target}, archiving into "
        f"{record.dest_root} since {record.started}"
    )

    payload = read_heartbeat(beat)
    if payload is None:
        why = "there is no file there" if not beat.exists() else "it is unreadable"
        return _no_heartbeat(record, beat, evidence, confirmed, why)

    beat_pid = payload.get("pid")
    if isinstance(beat_pid, int) and not isinstance(beat_pid, bool) and beat_pid != record.pid:
        return _no_heartbeat(
            record,
            beat,
            evidence,
            confirmed,
            f"it names pid {beat_pid}, not {record.pid}, so its freshness says nothing "
            "about this process",
        )

    written_text = payload.get("written")
    written = _parse_stamp(written_text)
    if written is None:
        return _no_heartbeat(
            record, beat, evidence, confirmed, "it carries no readable 'written' stamp"
        )

    age = (when - written).total_seconds()
    evidence.append(f"heartbeat: {beat} written {written_text}, {age:.0f} s ago")

    passes = payload.get("passes")
    if isinstance(passes, int) and not isinstance(passes, bool):
        evidence.append(f"heartbeat: {passes} passes reported")

    surfaces = payload.get("surfaces")
    if isinstance(surfaces, dict) and surfaces:
        rendered = []
        for name in sorted(surfaces):
            stamp = _parse_stamp(surfaces[name])
            if stamp is None:
                rendered.append(f"{name} unreadable")
            else:
                rendered.append(f"{name} {(when - stamp).total_seconds():.0f} s ago")
        evidence.append("surfaces: " + ", ".join(rendered))

    if age > HEARTBEAT_STALE_AFTER_S:
        return WatcherStatus(
            state=STATE_STALE,
            pid=record.pid,
            dest_root=record.dest_root,
            evidence=tuple(evidence),
            heartbeat_age_s=age,
            reason=(
                f"{confirmed}, but its heartbeat at {beat} has not advanced since "
                f"{written_text} - {age:.0f} s ago, past the "
                f"{HEARTBEAT_STALE_AFTER_S:.0f} s threshold, which is "
                f"{HEARTBEAT_STALE_MULTIPLE} missed passes of the "
                f"{SLOWEST_POLL_INTERVAL_S:.0f} s logs surface. It may be wedged, or the "
                "machine may have slept, which reads identically from here. REPORTED "
                "ONLY: nothing is re-armed, because a second poller on the same four "
                "sources is worse than a wedged one, and nothing is stopped, because "
                "killing is not in scope."
            ),
        )

    return WatcherStatus(
        state=STATE_ARMED,
        pid=record.pid,
        dest_root=record.dest_root,
        evidence=tuple(evidence),
        heartbeat_age_s=age,
        reason=(
            f"{confirmed}; its heartbeat at {beat} was written {written_text}, "
            f"{age:.0f} s ago, inside the {HEARTBEAT_STALE_AFTER_S:.0f} s threshold. "
            "Alive, identity-confirmed, and still polling."
        ),
    )


def _no_heartbeat(
    record: WatchRecord,
    beat: Path,
    evidence: list[str],
    confirmed: str,
    why: str,
) -> WatcherStatus:
    """Build the ``NO_HEARTBEAT`` status, which is still ARMED.

    Factored out because the three ways to have no usable heartbeat - no file,
    an unreadable one, one belonging to a different pid - all land on the same
    verdict and must not drift apart. The verdict is the point: an absent
    heartbeat is an absent OBSERVATION, not an absent watcher.
    """
    evidence.append(f"heartbeat: {beat} - {why}")
    return WatcherStatus(
        state=STATE_NO_HEARTBEAT,
        pid=record.pid,
        dest_root=record.dest_root,
        evidence=tuple(evidence),
        heartbeat_age_s=None,
        reason=(
            f"{confirmed}. No usable heartbeat at {beat} - {why} - so whether it is "
            "still POLLING cannot be told from here. It is ARMED and nothing is "
            "re-armed: a watcher armed before the heartbeat existed passes the identity "
            "check, and re-arming it would put a second poller on the same four sources. "
            "Treating this as a dead watcher would be a regression, not a stricter check."
        ),
    )


def ensure_armed_at_wrap(
    dest_base: Path | str,
    *,
    spawn_fn: Callable[[Path, Path], int] | None = None,
    dest_root_fn: Callable[[Path, datetime], Path] | None = None,
    now: datetime | None = None,
    path: Path | None = None,
    heartbeat: Path | None = None,
    creation_time_fn: Callable[[int], datetime | None] | None = None,
) -> WrapResult:
    """Re-check the watcher on the way OUT, and re-arm only when nothing polls.

    Every session-entry path calls :func:`ensure_armed` on the way IN. This is
    the way OUT, which is precisely when a session hands the machine back to an
    operator who is about to launch the client.

    Re-arms on ``NO_RECORD``, ``DEAD`` and ``IMPOSTOR`` - the three states in
    :data:`REARM_STATES`, and the three that mean nothing is polling. Reports
    and leaves alone on ``NO_HEARTBEAT``, ``STALE`` and ``ARMED``, all of which
    have a live watcher: re-arming any of them would start the second poller
    :func:`ensure_armed` exists to refuse.

    Nothing is terminated on any path, ``STALE`` included. Item ``4e`` says so
    in terms - killing is not in scope - and :mod:`ops.loop.guard` has the same
    prohibition for the same reason: deciding another process is unwanted is an
    operator decision, and an unattended loop is the wrong thing to make it.

    The spawn is delegated to :func:`ensure_armed` rather than re-implemented,
    so there is exactly one place that knows how to start a watcher and write
    its record. On ``IMPOSTOR`` the recorded pid is ALIVE, so ``ensure_armed``
    is told which pid has been disqualified - otherwise its own refusal would
    protect a process that is not the watcher.

    Args:
        dest_base: Root under which the watcher archives.
        spawn_fn: ``(dest_base, dest_root) -> pid``. Injected by every test, so
            no test starts a real detached poller against the operator's real
            ``Saved/`` directory.
        dest_root_fn: ``(dest_base, now) -> Path``.
        now: The moment to measure against, UTC.
        path: Arming record. Defaults to :func:`record_path`.
        heartbeat: Heartbeat file. Defaults to :func:`heartbeat_path`.
        creation_time_fn: ``(pid) -> datetime | None`` identity probe.

    Returns:
        A :class:`WrapResult` whose ``rearmed`` is True only if THIS call
        started a watcher.
    """
    status = check_watcher(
        path=path,
        heartbeat=heartbeat,
        now=now,
        creation_time_fn=creation_time_fn,
    )

    if status.state not in REARM_STATES:
        return WrapResult(status=status, arm=None, reason=status.reason)

    arm = ensure_armed(
        dest_base,
        spawn_fn=spawn_fn,
        dest_root_fn=dest_root_fn,
        now=now,
        path=path,
        disqualified_pid=status.pid if status.state == STATE_IMPOSTOR else None,
    )
    return WrapResult(
        status=status,
        arm=arm,
        reason=f"[{status.state}] {status.reason} At the wrap, therefore: {arm.reason}.",
    )
