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

ROADMAP item ``4f`` - one wedged surface out of four
----------------------------------------------------

``4e`` judged staleness from the heartbeat's single combined ``written`` stamp,
and ledger ``LL-0122`` named what that misses. The heartbeat also carries a
per-surface map, but nothing compared each surface against its OWN poll
interval, so the two 3 s surfaces keep the combined stamp fresh while ``logs``
- the 300 s surface guarding the 5,080,313-byte log that ``4d`` exists to
protect - has been wedged for an hour. That read ``ARMED``.

The cheap OS-level instrument does not rescue it, which is why the item was not
closed by dropping the heartbeat and sampling the process instead:
``Win32_Process.OtherOperationCount`` is per-PROCESS, and ``logs`` is roughly
0.5 percent of that traffic, so a wedged ``logs`` surface is inside the noise.

So there is a seventh state, :data:`STATE_SURFACE_STALE`, and it is a DIFFERENT
failure from :data:`STATE_STALE` rather than a stricter version of it. ``STALE``
means the heartbeat file itself has stopped advancing. ``SURFACE_STALE`` means
the file is still advancing and at least one polling thread is not. Collapsing
them would lose the interesting one, so the verdict NAMES which surfaces are
stale - in the evidence, and in the sentence an operator reads.

**Still nothing is re-armed and still nothing is terminated.**
:data:`REARM_STATES` is unchanged, ``SURFACE_STALE`` included. Re-arming would
put a second poller on the same four sources, which is worse than the wedge
because now the disk fills too; killing remains out of scope, inherited from
``4e`` and ``4d`` and from :mod:`ops.loop.guard` before them.

TWO DEFECTS IN THE FIRST CUT OF ``4f``, both found by refutation and both fixed
here, because a rule that cannot fire and a sentence that states a falsehood are
worse than the blindness they replaced - they read as coverage.

**The missing-surface rule was DEAD CODE.** A surface that never records must
eventually be caught, and the grace window exists so a watcher's first thirty
seconds do not cry wolf. But the set of surfaces the check EXPECTED was derived
from the heartbeat's own ``surfaces`` and ``intervals`` maps, and
:meth:`lanternlight.armwatch.Heartbeat.record` writes both in one call - so
``intervals`` is always a SUBSET of ``surfaces``, the union collapses to the
present set, and the branch could not run on any payload the writer can emit. A
``logs`` thread that never recorded once read ARMED at 100 s, at 2000 s and at
100000 s. The expectation now comes from
:func:`lanternlight.armwatch.session_plan` - see :func:`_expected_surfaces` -
because a heartbeat cannot be the authority on which surfaces should have
reported when the failure being watched for is a surface that wrote nothing.

**The verdict's prose asserted a mechanism it had not checked.** A real
heartbeat has ``written >= every surface stamp``, so the combined age is the age
of the FRESHEST surface. Any combined age over the smallest surface threshold
(69 s) already puts those surfaces past their own thresholds while the combined
age is under the 900 s of :data:`HEARTBEAT_STALE_AFTER_S` - so a whole-watcher
stall of 70 to 900 seconds landed in ``SURFACE_STALE`` and was told the process
was "alive and flushing" when it had not flushed for the length of the stall.
The verdict now distinguishes SOME surfaces stale, where a still-fresh surface
is named as the evidence that something is advancing, from EVERY judged surface
stale, where nothing observed shows any thread running and the combined stamp's
age is reported as a measurement rather than as a conclusion. See
:func:`_surface_stale_reason` for why that is one state with two sentences and
an explicit :attr:`WatcherStatus.all_surfaces_stale`, rather than an eighth
state or a second route into ``STALE``.

CORRECTED BOUND, measured rather than assumed: the per-surface threshold is
``k * poll + 2 * flush``, but a healthy surface's true worst case is
``poll + flush`` - 33 s, 60 s and 330 s - because a flush fires whenever ANY
surface records and the two 3 s surfaces record ten times per throttle window.
The real margins are 2.1x, 2.5x and 2.9x. The second flush term is kept anyway:
it costs nothing on a report that re-arms nothing, and it absorbs jitter and a
skipped flush. The PRECONDITION is the load-bearing part - that bound holds only
while some surface is still recording, and if every surface stops then no flush
fires at all and the combined stamp freezes with them. ``STALE`` covers exactly
that case, which is why the two states are kept apart.

STATED COST, written down here rather than left implied in a commit message:
for the two 3 s surfaces the flush term dominates the threshold completely -
69 s, of which 60 s is flush. A fast surface therefore cannot be detected as
wedged any faster than the heartbeat's flush cadence allows, however fast it
polls. That is a real limit of reading a throttled file, not a defect in the
threshold, and the only way to narrow it is to flush the heartbeat more often -
which is the write amplification the throttle exists to avoid.
"""

from __future__ import annotations

import json
import math
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
    "STATE_SURFACE_STALE",
    "SURFACE_STALE_MULTIPLE",
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
    "surface_stale_after_s",
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

#: Consecutive missed passes of a SINGLE surface before that surface is called
#: stale. DERIVED from :data:`HEARTBEAT_STALE_MULTIPLE` rather than re-typed as
#: a second ``3``, because it is the same argument for the same reason: one
#: missed pass is noise - a slow disk, an antivirus scan holding a directory
#: open, a machine that briefly slept - and three consecutive missed passes is a
#: pattern. If the two ever have to differ, somebody has to say why here, rather
#: than let two literals drift apart in silence. That drift is the exact defect
#: ``test_the_slowest_poll_interval_is_the_one_armwatch_actually_uses`` was
#: written for after the ops layer re-typed ``300.0``.
SURFACE_STALE_MULTIPLE = HEARTBEAT_STALE_MULTIPLE

#: Identity confirmed, heartbeat present but not advancing. ARMED.
STATE_STALE = "STALE"

#: Identity confirmed and the COMBINED stamp is fresh, so the process is alive
#: and flushing - but at least one individual surface has stopped advancing
#: against its own poll interval. ARMED. This is ROADMAP ``4f``, and it is a
#: different failure from :data:`STATE_STALE`, not a stricter one.
STATE_SURFACE_STALE = "SURFACE_STALE"

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


# ---------------------------------------------------------------------------
# ROADMAP 4f - judging each surface against its OWN poll interval
# ---------------------------------------------------------------------------


def surface_stale_after_s(poll_seconds: float, flush_interval_s: float) -> float:
    """Return the age at which a surface polling every ``poll_seconds`` is stale.

    ``k * poll + 2 * flush``, and every term is there for a reason that was
    measured rather than guessed:

    * A surface's stamp only advances when a pass COMPLETES, so it is already
      up to ``poll_seconds`` old the instant it is recorded. ``k`` of those is
      the "one missed pass is noise, three is a pattern" argument - see
      :data:`SURFACE_STALE_MULTIPLE`.
    * The heartbeat is flushed at most once every ``flush_interval_s``, so a
      stamp that is perfectly fresh in memory can sit unwritten for that long.
    * The file being READ may itself have been written up to another
      ``flush_interval_s`` ago. That is the SECOND flush term, and it is the one
      an implementation that only counts "the watcher's own worst case" forgets.

    So a perfectly healthy surface can legitimately read as ``poll + 2 * flush``
    old, and this threshold clears that by ``(k - 1) * poll``.

    THE TWO FLUSH TERMS ARE ONE MORE THAN THE MEASURED WORST CASE, and the
    correction is worth writing down rather than leaving the formula to imply
    something false. A flush fires whenever ANY surface records and the throttle
    has elapsed, and the two 3 s surfaces record ten times per 30 s throttle
    window - so a flush lands about every 30 s and the file being read is at
    most one throttle old, not two. The true bound is poll + flush: 33 s, 60 s
    and 330 s for the 3 s, 30 s and 300 s surfaces, against thresholds of 69 s,
    150 s and 960 s. The real margins are therefore 2.1x, 2.5x and 2.9x, not the
    1.1x / 1.7x / 2.7x that ``poll + 2 * flush`` implies.

    The second flush term is KEPT anyway. It costs nothing - the threshold is
    already the loose end of a report that re-arms nothing and stops nothing -
    and it absorbs scheduling jitter and one entirely skipped flush without
    anyone having to reason about either.

    THE PRECONDITION IS THE INTERESTING PART, and it is the best argument for
    keeping ``STALE`` and ``SURFACE_STALE`` as separate verdicts. That bound
    holds only while SOME surface is still recording. If every surface stops, no
    flush fires at all: the combined stamp freezes with them, and ``STALE`` -
    decided earlier in the chain - is what catches it. The two states cover each
    other's blind spot, and neither is a stricter version of the other.

    STATED COST: for the two 3 s surfaces the flush terms dominate completely -
    9 s of poll against 60 s of flush - so a fast surface cannot be detected as
    wedged any faster than the flush cadence allows. That is a limit of reading
    a throttled file, not a defect in this number, and narrowing it means
    flushing more often, which is the write amplification the throttle exists to
    avoid.

    Args:
        poll_seconds: That surface's own poll interval, read from the heartbeat
            or from the watcher's plan. Never re-typed in this module.
        flush_interval_s: The watcher's heartbeat flush interval, read from
            :mod:`lanternlight.armwatch`.

    Returns:
        The age in seconds past which that surface is called stale.
    """
    return SURFACE_STALE_MULTIPLE * float(poll_seconds) + 2.0 * float(flush_interval_s)


def _positive_seconds(value: object) -> float | None:
    """Return ``value`` as a positive finite float, or ``None``. Never raises.

    ``None`` is cannot-tell, and it is a third answer rather than a verdict. An
    interval that is absent, zero, negative, infinite, ``NaN``, a bool or not a
    number at all cannot produce a threshold, and inventing one would settle a
    staleness question with fiction.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _watcher_flush_interval_s() -> float | None:
    """Return the watcher's own heartbeat flush interval, or ``None``.

    Imported inside the function body for the two reasons
    :func:`_default_dest_root_fn` is: this module must stay importable while the
    lanternlight slice is in flight, and the ops loop package takes no
    module-scope dependency on the lanternlight package.

    It is READ rather than re-typed because a re-typed copy of a lanternlight
    number is precisely the drift that made
    ``test_the_slowest_poll_interval_is_the_one_armwatch_actually_uses``
    necessary. :data:`HEARTBEAT_FLUSH_THROTTLE_S` is a documented MIRROR of this
    number for the prose above, and the derivation below never uses it.

    ``None`` when the number cannot be read at all, which makes every surface
    UNJUDGED rather than assumed fresh or assumed stale. That is the honest
    failure: without a flush interval no threshold exists, and a check that
    guessed one would cry wolf about its own missing dependency.

    The exception list is NAMED, never a bare ``except Exception``.
    ``AssertionError`` is an ``Exception``, so a blanket catch here would
    swallow a spying test's own assertion and the spy would go vacuous.
    """
    try:
        from lanternlight.armwatch import HEARTBEAT_FLUSH_INTERVAL_S
    except (ImportError, AttributeError, OSError):
        return None
    return _positive_seconds(HEARTBEAT_FLUSH_INTERVAL_S)


#: Handed to ``session_plan`` so it will build a plan without being pointed at
#: anything real. The name is a placeholder rather than ``.`` so a reader of a
#: stack trace can see immediately that no directory was meant, and so nothing
#: in this module ever names the operator's live ``Saved/`` tree at check time.
#: Only ``name`` and ``poll_seconds`` are read back off the plan and neither
#: depends on the paths.
_PLAN_PLACEHOLDER = "armwatch-plan-placeholder"


def _plan_poll_intervals() -> dict[str, float]:
    """Return ``{surface name: poll_seconds}`` from the watcher's own plan.

    The fallback for a heartbeat that is not self-describing - one written by
    the cycle-38 watcher carries ``surfaces`` but no ``intervals`` - and it
    reads the PLAN rather than re-typing four literals here. Four re-typed
    literals would reintroduce the ``300.0`` drift defect four times over.

    ``session_plan`` is pure data: it builds paths but touches no filesystem, so
    it is handed :data:`_PLAN_PLACEHOLDER` twice rather than the operator's live
    ``Saved/`` directory - and rather than being left to default, which would
    resolve the real one. Only the names and the intervals are read back and
    neither depends on the paths, so nothing here can reach a real directory at
    check time.

    An empty dict is the cannot-tell answer, and every surface it fails to
    describe is reported UNJUDGED rather than assumed anything.
    """
    try:
        from lanternlight.armwatch import session_plan

        plans = session_plan(
            saved_dir=Path(_PLAN_PLACEHOLDER), dest_root=Path(_PLAN_PLACEHOLDER)
        )
    except (ImportError, AttributeError, OSError, ValueError, TypeError):
        return {}

    intervals: dict[str, float] = {}
    for plan in plans:
        name = getattr(plan, "name", None)
        seconds = _positive_seconds(getattr(plan, "poll_seconds", None))
        if isinstance(name, str) and seconds is not None:
            intervals[name] = seconds
    return intervals


def _expected_surfaces(
    present: dict[str, object], planned: dict[str, float]
) -> tuple[frozenset[str], str]:
    """Return the surfaces that SHOULD have reported, and how that was decided.

    THE HEARTBEAT CANNOT BE THE AUTHORITY HERE, and believing it was is what
    made the missing-surface rule dead code.
    :meth:`lanternlight.armwatch.Heartbeat.record` writes ``_surfaces[name]``
    and ``_intervals[name]`` in the same call, so ``intervals`` is always a
    SUBSET of ``surfaces``. A rule deriving its expectations from those two maps
    expects exactly the surfaces that already reported - the union collapses to
    the present set - and its missing-key branch cannot run on any payload the
    writer can emit. Measured against a ``logs`` thread that never recorded
    once: ARMED at 100 s, at 2000 s and at 100000 s past arming.

    So the expectation comes from the PLAN, which is what the watcher was
    started from. A surface that has never completed a pass leaves no trace in
    the heartbeat at all, and the only place its name still exists is the plan.

    Two cases return an EMPTY expectation, and both of them are the
    never-cry-wolf direction:

    * No plan at all - :func:`_plan_poll_intervals` returned nothing. Without it
      a surface that never recorded is indistinguishable from a surface this
      watcher does not run, so nothing is accused. In practice this coincides
      with :func:`_watcher_flush_interval_s` also failing, since both read the
      same module, and that already makes every surface UNJUDGED earlier.
    * The heartbeat names a surface the plan does not. Then this watcher is
      running a plan this module cannot see, and a plan naming threads it never
      started would have the check crying wolf about a thread that never
      existed. That was the real worry behind the original heartbeat-sourced
      rule, and it is answered here rather than by giving up the rule.

    Returns:
        ``(names, note)``. The note goes into the evidence, because a verdict
        about a surface that left no trace has to say where the name came from.
    """
    if not planned:
        return frozenset(), (
            "expected surfaces: none could be determined - "
            "lanternlight.armwatch.session_plan yielded no plan, so a surface that has "
            "never recorded cannot be told from one this watcher does not run, and none "
            "is accused on that basis"
        )

    unplanned = sorted(set(present) - set(planned))
    if unplanned:
        return frozenset(), (
            "expected surfaces: taken from the heartbeat alone - it names "
            f"{', '.join(unplanned)}, which lanternlight.armwatch.session_plan does not, "
            "so this watcher is running a plan this module cannot see and the plan is no "
            "authority on what else it should have reported"
        )

    return frozenset(planned), (
        "expected surfaces: "
        + ", ".join(sorted(planned))
        + " - from lanternlight.armwatch.session_plan, NOT from the heartbeat's own maps: "
        "a heartbeat cannot be the authority on which surfaces should have reported, "
        "because the failure being watched for is a surface that wrote nothing"
    )


@dataclass(frozen=True)
class _SurfaceReport:
    """What :func:`_judge_surfaces` observed, before it becomes a verdict.

    Attributes:
        stale: Surfaces past their own threshold, sorted.
        fresh: Surfaces whose OWN stamp was read and found inside their own
            threshold, sorted. Kept apart from the rest of ``judged`` because
            this is the only EVIDENCE in the payload that anything is still
            advancing - a surface still inside its grace window has recorded
            nothing and proves nothing. Empty is what turns the verdict's prose
            from "one thread stopped" into "nothing here shows any thread
            running".
        judged: Surfaces a verdict could be reached about at all, fresh or
            stale. The denominator that lets "one of four" be told from "all
            four", which the ``4f`` acceptance asks for by name.
        unjudged: Surfaces no verdict could be reached about.
        freshest_age_s: The age of the most recently stamped fresh surface, or
            ``None`` when none was fresh. Absent, never zero - "unmeasured" and
            "measured zero" are different facts.
        evidence: Lines to append to the status evidence.
        clauses: One sentence per stale surface, for the reason an operator
            reads. A frozen stamp and a never-recorded pass get DIFFERENT
            sentences, because they are different failures.
    """

    stale: tuple[str, ...]
    judged: tuple[str, ...]
    unjudged: tuple[str, ...]
    evidence: tuple[str, ...]
    clauses: tuple[str, ...]
    fresh: tuple[str, ...] = ()
    freshest_age_s: float | None = None


def _judge_surfaces(
    payload: dict,
    *,
    when: datetime,
    started: datetime | None,
) -> _SurfaceReport:
    """Judge every surface against its OWN poll interval.

    Called only once the COMBINED ``written`` stamp has been found fresh, so the
    process is known to be alive and flushing and anything found here is one
    thread that stopped rather than the whole watcher.

    Where the intervals come from, in order:

    1. The heartbeat's own ``intervals`` map, when it declares one. A running
       watcher's report of its own cadence beats anything this module can
       re-derive, because the watcher may have been started with a plan this
       module cannot see.
    2. Otherwise :func:`_plan_poll_intervals`, which also fills in any surface
       the heartbeat could not declare one for - and a surface that has never
       recorded is exactly that, since the writer only ever declares an interval
       alongside a stamp.
    3. Otherwise nothing, and that surface is UNJUDGED. An interval is never
       guessed: a guessed threshold produces a confident wrong verdict, and a
       missing one is recoverable.

    THE NAME SET DOES NOT FOLLOW THAT RULE, and it used to, which is what left
    the missing-surface rule below unreachable. See :func:`_expected_surfaces`:
    the surfaces this check EXPECTS come from the plan, never from the payload's
    own two maps, because those two maps can only ever name surfaces that have
    already reported.

    THE MISSING-KEY RULE, and the hole in the obvious version of it. The first
    heartbeat after arming can carry fewer than four ``surfaces`` keys, so a
    missing key must read as "no completed pass yet" or every wrap in a
    watcher's first half-minute cries wolf. But a surface whose thread died
    BEFORE its first pass has a permanently missing key, and the naive rule
    reads that as fine forever. So the innocence is TIMED: a missing key is
    innocent only while the watcher is younger than that surface's own
    threshold, measured from the record's ``started`` stamp, and past that it is
    stale with a DISTINCT reason naming that no pass was ever recorded.

    A thread dying before its first pass is a NAMED path in the watcher, not a
    hypothesis: ``lanternlight.armwatch.arm_rolling`` returns out of a surface's
    ``poll_forever`` on ``DestinationInsideRepoError``, and its own comment says
    the surface "correctly stops advancing here". If that fires on the first
    iteration the key never appears at all.

    The 4e docstring worried that "a source directory the game has not created
    yet may never produce a pass at all", which would have made this rule cry
    wolf for the whole of a session in which the game never starts. Measured,
    and it is FALSE: ``SaveWatcher.poll_once`` catches ``OSError`` from
    ``iterdir`` and returns an empty pass, and the watcher records a stamp after
    ``poll_once`` returns whatever it returned. An absent source directory still
    stamps. What a missing key therefore means is that the THREAD is not
    running, which is worth reporting.

    What this cannot do is say WHY a surface stopped - a wedge, a dead thread,
    or a destination that acquired a git checkout all read identically from
    here. The verdict names the observation, never the cause.

    DIRECTION OF ERROR, stated because it is not symmetric: ``started`` is
    written just BEFORE the child is spawned, and :func:`_stamp` truncates to
    whole seconds, so ``now - started`` OVERSTATES the watcher's true age - by
    the measured 0.06 s spawn gap plus up to 1 s of truncation. The grace window
    therefore closes up to about a second EARLY, which is the crying-wolf
    direction. It is left uncorrected deliberately: about a second of error sits
    inside the 60 s of flush slack the threshold already carries, so a fudge
    factor would buy nothing measurable while adding a constant with no
    measurement behind it. The boundary is inclusive, matching the combined
    threshold's, so exactly-at-window is still innocent.

    Args:
        payload: The heartbeat, already known to be a dict naming this pid.
        when: The moment to measure against, UTC.
        started: The arming stamp, parsed, or ``None`` when it did not parse.

    Returns:
        A :class:`_SurfaceReport`. Nothing is spawned and nothing is stopped.
    """
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, dict):
        return _SurfaceReport(
            stale=(),
            judged=(),
            unjudged=(),
            evidence=(
                "surfaces judged: none - the heartbeat carries no per-surface map, so "
                "which of its threads are still advancing cannot be told from here",
            ),
            clauses=(),
        )

    present = {name: value for name, value in surfaces.items() if isinstance(name, str)}

    flush = _watcher_flush_interval_s()
    if flush is None:
        return _SurfaceReport(
            stale=(),
            judged=(),
            unjudged=tuple(sorted(present)),
            evidence=(
                "surfaces judged: none - lanternlight.armwatch would not yield a heartbeat "
                "flush interval, and without it no per-surface threshold exists. Every "
                "surface is UNJUDGED, which is not a clean bill",
            ),
            clauses=(),
        )

    declared = payload.get("intervals")
    declared_intervals: dict[str, float] = {}
    if isinstance(declared, dict):
        for name, value in declared.items():
            seconds = _positive_seconds(value)
            if isinstance(name, str) and seconds is not None:
                declared_intervals[name] = seconds

    planned = _plan_poll_intervals()
    expected, expected_note = _expected_surfaces(present, planned)
    considered = sorted(set(present) | expected)

    # The plan is the floor and the heartbeat's own report wins over it, so a
    # watcher that re-tuned a cadence is judged against the cadence it reported.
    known: dict[str, float] = dict(planned)
    known.update(declared_intervals)

    if declared_intervals:
        source = "the heartbeat's own 'intervals' map"
        borrowed = [
            name
            for name in considered
            if name not in declared_intervals and name in planned
        ]
        if borrowed:
            source += (
                ", with lanternlight.armwatch.session_plan supplying "
                + ", ".join(borrowed)
                + " - a heartbeat cannot declare an interval for a surface that has "
                "never recorded a pass"
            )
    else:
        source = (
            "lanternlight.armwatch.session_plan - the heartbeat declared no usable "
            "'intervals', so it is not self-describing"
        )

    stale: list[str] = []
    fresh: list[str] = []
    judged: list[str] = []
    unjudged: list[str] = []
    rendered: list[str] = []
    clauses: list[str] = []
    freshest_age_s: float | None = None

    for name in considered:
        interval = known.get(name)
        if interval is None:
            unjudged.append(name)
            rendered.append(f"{name} UNJUDGED - no poll interval known for it")
            continue

        threshold = surface_stale_after_s(interval, flush)
        derivation = f"{SURFACE_STALE_MULTIPLE} x {interval:g} s poll + 2 x {flush:g} s flush"

        if name not in present:
            if started is None:
                unjudged.append(name)
                rendered.append(
                    f"{name} UNJUDGED - no completed pass recorded, and the arming stamp "
                    "does not parse, so its grace window cannot be measured"
                )
                continue
            since_arming = (when - started).total_seconds()
            judged.append(name)
            if since_arming <= threshold:
                rendered.append(
                    f"{name} no completed pass yet, {since_arming:.0f} s since arming, "
                    f"inside its {threshold:.0f} s grace window"
                )
                continue
            stale.append(name)
            rendered.append(
                f"{name} STALE - NO PASS EVER RECORDED, {since_arming:.0f} s since arming, "
                f"past its {threshold:.0f} s grace window ({derivation})"
            )
            clauses.append(
                f"{name} has NEVER recorded a completed pass, {since_arming:.0f} s after "
                f"arming and past its {threshold:.0f} s grace window - its thread looks "
                "like it died before its first pass, which a rule that only watched for a "
                "FROZEN stamp would never see"
            )
            continue

        stamp = _parse_stamp(present[name])
        if stamp is None:
            unjudged.append(name)
            rendered.append(f"{name} UNJUDGED - its stamp does not parse")
            continue

        age = (when - stamp).total_seconds()
        judged.append(name)
        if age <= threshold:
            fresh.append(name)
            if freshest_age_s is None or age < freshest_age_s:
                freshest_age_s = age
            rendered.append(f"{name} {age:.0f} s old, inside its {threshold:.0f} s threshold")
            continue
        stale.append(name)
        rendered.append(
            f"{name} STALE at {age:.0f} s old, past its {threshold:.0f} s threshold "
            f"({derivation})"
        )
        clauses.append(
            f"{name} last completed a pass {age:.0f} s ago, past the {threshold:.0f} s "
            f"threshold for its {interval:g} s poll ({derivation})"
        )

    evidence = [expected_note, f"surface poll intervals read from {source}"]
    if rendered:
        evidence.append("surfaces judged: " + ", ".join(rendered))
    else:
        evidence.append(
            "surfaces judged: none - the heartbeat named no surfaces and no intervals "
            "could be determined"
        )

    return _SurfaceReport(
        stale=tuple(stale),
        judged=tuple(judged),
        unjudged=tuple(unjudged),
        evidence=tuple(evidence),
        clauses=tuple(clauses),
        fresh=tuple(fresh),
        freshest_age_s=freshest_age_s,
    )


def _surface_headline(report: _SurfaceReport) -> str:
    """Say how MANY surfaces stopped, so all-four never reads like one-of-four.

    The ``4f`` acceptance asks for exactly this: "every surface stale" and "one
    surface stale" are different failures, and a sentence that renders them
    identically loses the interesting one. All-of-them points at the watcher;
    one-of-them points at a thread.

    The count is only half of that distinction - it says how many stopped, not
    whether anything is still going. The other half is
    :attr:`WatcherStatus.all_surfaces_stale`, which decides which of the two
    verdict sentences is told, and the two are computed from the same report so
    they cannot disagree.
    """
    total = len(report.judged)
    hit = len(report.stale)
    if hit == total and total > 1:
        return f"ALL {total} of its judged surfaces have stopped advancing"
    if hit == total == 1:
        return "its ONLY judged surface has stopped advancing"
    verb = "has" if hit == 1 else "have"
    return f"{hit} of its {total} judged surfaces {verb} stopped advancing"


#: The tail both ``SURFACE_STALE`` sentences end on. One string, because the
#: promise is identical in both and two copies of a promise drift.
_REPORTED_ONLY = (
    "REPORTED ONLY: nothing is re-armed, because a second poller on the same four "
    "sources is worse than a wedged one, and nothing is stopped, because killing is not "
    "in scope."
)


def _surface_stale_reason(
    report: _SurfaceReport,
    *,
    confirmed: str,
    beat: Path,
    written_text: object,
    age: float,
) -> str:
    """Build the ``SURFACE_STALE`` sentence - one of two, and they differ in KIND.

    WHAT WAS WRONG. The single sentence this replaces said the combined stamp
    was "still fresh, so the process IS alive and flushing". A real heartbeat
    has ``written >= every surface stamp``, because ``written`` is set at flush
    time and the stamps at or before it, so the combined age is the age of the
    FRESHEST surface. Any combined age over the smallest surface threshold -
    69 s - already puts those surfaces past their own thresholds while the
    combined age is still under :data:`HEARTBEAT_STALE_AFTER_S`. A whole-watcher
    stall of 70 to 900 seconds therefore landed here, and was told that the
    process was flushing when it had not flushed for the length of the stall.
    The root error was asserting a MECHANISM that had not been checked; the fix
    is to say only what the payload was observed to contain.

    HOW THE DISTINCTION IS EXPRESSED, and why not the other two ways:

    * NOT an eighth state. Both cases take exactly the same action - report,
      re-arm nothing, stop nothing - so they are one verdict with two sentences,
      not two verdicts. A new state would put a new branch in
      :data:`REARM_STATES` membership, in :attr:`WatcherStatus.armed` and in
      every consumer, to carry a distinction that no consumer acts on
      differently.
    * NOT ``STALE`` by a second route. ``STALE``'s stated grounds are the
      combined stamp being PAST its own threshold, and in a stall of under
      900 s it is not - so that verdict would be reporting a measurement it
      cannot show. ``STALE`` keeps its own meaning and catches the same stall
      once it passes 900 s.
    * SO: one state, an explicit :attr:`WatcherStatus.all_surfaces_stale`
      derived from what was actually observed, and two sentences whose claims
      differ because their evidence differs.

    STATED COST: a consumer that switches on :attr:`WatcherStatus.state` alone
    still cannot tell a stalled watcher from a wedged thread. It has to read
    ``all_surfaces_stale`` or ``fresh_surfaces``. That is the price of not
    multiplying the state space, and it is written here rather than left for
    the next reader to discover.

    Args:
        report: What :func:`_judge_surfaces` observed. Its ``fresh`` tuple is
            the only evidence in a heartbeat that a thread is still advancing.
        confirmed: The identity clause shared with every other verdict.
        beat: The heartbeat path, named so an operator can go and read it.
        written_text: The combined stamp exactly as the payload spelled it.
        age: Seconds since that stamp.

    Returns:
        The sentence a later session or an operator reads. Nothing is spawned
        and nothing is stopped on either branch.
    """
    opening = f"{confirmed}; its heartbeat at {beat} was written {written_text}, {age:.0f} s ago"
    headline = _surface_headline(report)
    clauses = "; ".join(report.clauses)

    if report.fresh:
        recent = ""
        if report.freshest_age_s is not None:
            recent = (
                ", the most recent completed pass among them "
                f"{report.freshest_age_s:.0f} s ago"
            )
        if len(report.fresh) == 1:
            still_going = f"{report.fresh[0]} is still inside its own threshold{recent}"
        else:
            still_going = (
                f"{', '.join(report.fresh)} are still inside their own thresholds{recent}"
            )
        return (
            f"{opening}, and {still_going} - which is the OBSERVATION that the process is "
            f"still flushing, rather than an inference from the combined stamp. But "
            f"{headline}: {clauses}. That is a DIFFERENT failure from STALE, which is "
            "decided on the combined stamp alone: the combined stamp can be held fresh by "
            "the two 3 s surfaces while a slower one stops, and the slowest of the four is "
            "what guards the 5,080,313-byte log that item 4d exists to protect. The stale "
            "ones are NAMED above rather than implied, because which one stopped is the "
            f"whole question. {_REPORTED_ONLY}"
        )

    return (
        f"{opening}, which is under the {HEARTBEAT_STALE_AFTER_S:.0f} s combined threshold "
        f"- and that is the whole of what the combined stamp says here. {headline}: "
        f"{clauses}. NO judged surface is inside its own threshold, so nothing observed "
        "here shows any thread still advancing. The combined age above is reported as the "
        "measurement it is - when this file was last written - and NOT as evidence about "
        "the process, which is the inference this verdict used to make and which is false "
        "across a whole-watcher stall. STALE is not reported instead because STALE's "
        "grounds are the combined stamp being PAST its own threshold, and here it is not; "
        f"STALE is what catches the same stall once it runs past "
        f"{HEARTBEAT_STALE_AFTER_S:.0f} s. {_REPORTED_ONLY}"
    )


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
        state: One of the seven ``STATE_*`` constants.
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
        stale_surfaces: The surfaces judged stale against their OWN poll
            interval, sorted. Empty on every state but ``SURFACE_STALE``, and a
            ``SURFACE_STALE`` verdict always names at least one. Item ``4f``
            asks the check to say WHICH, and a verdict that only says "a
            surface" leaves an operator guessing between a 3 s save watcher and
            the 300 s surface guarding the log.
        unjudged_surfaces: The surfaces no verdict could be reached about at
            all - no poll interval anywhere, an unreadable stamp, or a flush
            interval that could not be read. Kept SEPARATE from the fresh ones
            on purpose: "unmeasured" and "measured fresh" are different facts,
            and conflating them is how a check starts lying.
        fresh_surfaces: The surfaces whose own stamp was read and found inside
            their own threshold, sorted. This is the ONLY observation in a
            heartbeat that shows a thread still advancing, so it is what the
            ``SURFACE_STALE`` reason cites when it says the process is still
            flushing - rather than inferring that from the combined stamp,
            which was the falsehood ``4f`` shipped with. A surface still inside
            its grace window is not here: it has recorded nothing and proves
            nothing.
    """

    state: str
    pid: int | None
    dest_root: str | None
    evidence: tuple[str, ...]
    heartbeat_age_s: float | None
    reason: str
    stale_surfaces: tuple[str, ...] = ()
    unjudged_surfaces: tuple[str, ...] = ()
    fresh_surfaces: tuple[str, ...] = ()

    @property
    def all_surfaces_stale(self) -> bool:
        """True when something stopped and NOTHING was found still advancing.

        The explicit all-versus-some answer the ``4f`` acceptance asks for, and
        the switch between the two ``SURFACE_STALE`` sentences. It is DERIVED
        from the two tuples rather than stored beside them, exactly as
        :attr:`armed` is derived from :attr:`state`, so the flag and the
        evidence it summarises can never drift apart.

        Note it is not simply "every judged surface is stale". A surface still
        inside its grace window is judged and is not stale, yet it has recorded
        nothing, so a payload where one surface is waiting and the rest have
        stopped still has NO evidence that anything is running. That case
        belongs with the stall, and this definition puts it there.
        """
        return bool(self.stale_surfaces) and not self.fresh_surfaces

    @property
    def armed(self) -> bool:
        """True when something IS polling, whatever else is wrong with it.

        Derived from :attr:`state` rather than stored, so the two can never
        drift apart. ``NO_HEARTBEAT``, ``STALE`` and ``SURFACE_STALE`` are all
        armed: they are reports about a watcher that exists, not grounds to
        start another one.
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

    Seven states, decided in this order, because each one is a precondition for
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
    5. ``STALE`` - identity confirmed, heartbeat present, and the COMBINED
       ``written`` stamp has not advanced within
       :data:`HEARTBEAT_STALE_AFTER_S`. Nothing is flushing at all.
       **Reported, and still ARMED.**
    6. ``SURFACE_STALE`` - the combined stamp is inside its own threshold, but
       one or more INDIVIDUAL surfaces have stopped advancing against their own
       poll intervals. Two sentences come out of this one state, because the
       evidence differs: with a surface still fresh, that surface is NAMED as
       what shows the process is flushing; with every judged surface stale,
       nothing observed shows any thread running and the reason says so. See
       :func:`_surface_stale_reason`, and :attr:`WatcherStatus.all_surfaces_stale`
       for the explicit answer. **Reported, named, and still ARMED.**
    7. ``ARMED`` - identity confirmed, combined stamp fresh, every judged
       surface fresh.

    ``NO_HEARTBEAT`` being ARMED is the load-bearing decision here, and it is
    not a corner case. Pid 23628 was running on this machine when this was
    written, armed before the heartbeat existed and passing the identity check.
    Treating an absent heartbeat as a dead watcher would spawn a second poller
    on the same four sources - the exact thing :func:`ensure_armed` refuses to
    do - so it would be a REGRESSION wearing the clothes of a stricter check.

    That pid is NO LONGER the live watcher: it was found DEAD at the very next
    wrap and re-armed (``LL-0124``). The example stands; the status does not.
    A docstring naming a live pid is stale the moment that process exits, so
    this one names the case and not the machine.

    CAVEAT, written down rather than only said: a machine that SUSPENDED or
    HIBERNATED produces a false ``STALE``, because wall clock advances while
    nothing runs. That is tolerable only because ``STALE`` re-arms nothing and
    stops nothing. See :data:`HEARTBEAT_STALE_AFTER_S`.

    SECOND CAVEAT, and it is the one item ``4f`` closed: staleness USED to be
    judged on the combined ``written`` stamp alone, so a watcher whose two 3 s
    surfaces kept flushing while its 300 s ``logs`` surface had been wedged for
    an hour read as ``ARMED``. Each surface is now judged against its own poll
    interval - see :func:`surface_stale_after_s` and :func:`_judge_surfaces` -
    and the verdict names which ones stopped. What is still true is the flush
    limit: a 3 s surface's threshold is 69 s, of which 60 s is flush, so a fast
    surface cannot be caught any faster than the heartbeat's flush cadence
    allows. That is the price of reading a throttled file.

    THIRD CAVEAT: a surface with no key in the map reads as "no completed pass
    yet" only while the watcher is younger than that surface's own threshold.
    Past that it is ``SURFACE_STALE`` with a distinct reason, because a thread
    that died before its first pass leaves a permanently missing key and the
    naive form of the rule would call that healthy forever. The grace window is
    measured from the record's ``started`` stamp, which slightly PRECEDES the
    real spawn, so it closes about a second early - the crying-wolf direction,
    quantified and deliberately left uncorrected in :func:`_judge_surfaces`.
    The NAME of such a surface comes from the plan, never from the heartbeat -
    see :func:`_expected_surfaces` - because the two maps a heartbeat carries
    can only name surfaces that have already reported, which made the first cut
    of this rule unreachable.

    FOURTH CAVEAT: a stall of 70 to 900 seconds shows up here rather than in
    ``STALE``, because the combined stamp is never older than the freshest
    surface stamp and 900 s is the combined threshold. That case is reported
    with ``all_surfaces_stale`` true and a reason that claims nothing about
    flushing; a consumer switching on ``state`` alone cannot tell it from one
    wedged thread and has to read that flag.

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

    # ROADMAP 4f. Only reached once the COMBINED stamp is fresh, so whatever
    # this finds is one thread that stopped, not a watcher that stopped.
    report = _judge_surfaces(payload, when=when, started=started)
    evidence.extend(report.evidence)

    if report.stale:
        return WatcherStatus(
            state=STATE_SURFACE_STALE,
            pid=record.pid,
            dest_root=record.dest_root,
            evidence=tuple(evidence),
            heartbeat_age_s=age,
            reason=_surface_stale_reason(
                report, confirmed=confirmed, beat=beat, written_text=written_text, age=age
            ),
            stale_surfaces=report.stale,
            unjudged_surfaces=report.unjudged,
            fresh_surfaces=report.fresh,
        )

    unjudged_note = ""
    if report.unjudged:
        unjudged_note = (
            " NOT judged, for want of a poll interval or a readable stamp: "
            f"{', '.join(report.unjudged)} - unjudged is a third answer, not a clean bill."
        )

    return WatcherStatus(
        state=STATE_ARMED,
        pid=record.pid,
        dest_root=record.dest_root,
        evidence=tuple(evidence),
        heartbeat_age_s=age,
        reason=(
            f"{confirmed}; its heartbeat at {beat} was written {written_text}, "
            f"{age:.0f} s ago, inside the {HEARTBEAT_STALE_AFTER_S:.0f} s threshold, and "
            f"every judged surface is inside its own. Alive, identity-confirmed, and still "
            f"polling.{unjudged_note}"
        ),
        unjudged_surfaces=report.unjudged,
        fresh_surfaces=report.fresh,
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
    and leaves alone on ``NO_HEARTBEAT``, ``STALE``, ``SURFACE_STALE`` and
    ``ARMED``, all of which have a live watcher: re-arming any of them would
    start the second poller :func:`ensure_armed` exists to refuse.

    ``SURFACE_STALE`` joining that list is item ``4f``, and it is deliberate
    rather than an omission. A watcher with one wedged thread is still one
    watcher; arming a second one would double the traffic on the three surfaces
    that are working in order to chase the one that is not.

    Nothing is terminated on any path, ``STALE`` and ``SURFACE_STALE``
    included. Item ``4e`` says so in terms - killing is not in scope - and
    :mod:`ops.loop.guard` has the same prohibition for the same reason: deciding
    another process is unwanted is an operator decision, and an unattended loop
    is the wrong thing to make it.

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
