"""Tests for the single-instance loop guard.

The guard has exactly one job and one prohibition: refuse a second loop, and
never terminate anything. Both are tested here, along with the stale-lock
reclaim that stops a crashed loop from wedging every future run.

Nothing here writes to ``ops/runtime/``. Every test is handed an explicit
``tmp_path`` lock, because a test that stomps the live lock file could let a
second loop start against a running one.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.loop import guard as guard_mod  # noqa: E402
from ops.loop.guard import LockBusy  # noqa: E402


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    """A lock file path inside tmp_path. The file does not exist yet."""
    return tmp_path / "loop.lock"


#: Every child :func:`_dead_pid` has ever reaped, kept referenced on purpose
#: and never emptied. The list IS the mechanism, not bookkeeping: see below.
_PINNED_DEAD: list[subprocess.Popen] = []


def _dead_pid() -> int:
    """Return a pid that is genuinely no longer running, and cannot come back.

    Spawning and reaping a real process beats picking a large number and
    hoping: a guessed pid can be reused, and the test would then flake in the
    one direction that matters (a live lock silently reclaimed). That reasoning
    is unchanged. What follows narrows it, because spawning and reaping alone
    did not actually deliver it - the pid was recyclable by the time it reached
    the caller, so the helper reopened the very hole it was written to close.
    It was seen closing: an unrelated full-suite run went red on a reaped pid
    that the OS had already handed to somebody else.

    Two facts about Windows make the fix a one-liner. A process object survives
    the process, for exactly as long as some handle to it remains open, and the
    pid stays reserved for that whole time. But that surviving object carries a
    real EXIT TIME, so :func:`guard.pid_is_alive` calls it dead. (It read the
    exit CODE until ``OPS-18``, which made this true for every exit code except
    259 - see the collision tests below.) A reaped child whose handle is
    still open is therefore dead and unreissuable at the same time, which is
    the pair of properties every caller below needs and neither of the obvious
    alternatives gives. Leaving the child unreaped would reserve the pid too,
    and would make it read as alive.

    Appending to a module-level list is what holds that handle open.
    ``subprocess.Popen`` owns the process handle and closes it when it is
    deallocated, so the lifetime of the pin is the lifetime of this module -
    which is the whole test session.

    MEASURED, because the mechanism is easy to state wrongly. ``OPS-17`` blames
    ``Popen.__exit__`` for closing the handle, and that is FALSE: ``__exit__``
    closes the std streams and calls ``wait()``, nothing more. With the ``with``
    block exited and the name still bound, the pid was still openable. What
    freed it was the refcount hitting zero - in the old code, at ``return
    proc.pid``, when the frame died. So dropping the ``with`` would have changed
    nothing at all, and only keeping a reference does anything.

    On POSIX this pin buys nothing, and the docstring says so rather than
    implying a guarantee it does not carry: ``waitpid`` frees the pid at the
    moment the zombie is reaped, and there is no handle that outlives it.
    """
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait(timeout=60)
    # Pin BEFORE returning. Doing it after, or not at all, lets the frame drop
    # the last reference and hands back a pid the allocator has already freed.
    _PINNED_DEAD.append(proc)
    return proc.pid


def _dead_pid_exiting_with(code: int) -> subprocess.Popen:
    """Spawn a child that exits with exactly ``code``, reap it, and pin it.

    The pin is :func:`_dead_pid`'s, for :func:`_dead_pid`'s reason, and the
    caller gets the whole ``Popen`` back rather than the bare pid so it can
    assert on ``returncode`` before believing anything the probe says.

    The exit code is the variable ``OPS-18`` turns on: ``GetExitCodeProcess``
    reports a real exit code and a "still running" sentinel through the same
    ``DWORD``, and the sentinel is 259, which a process may also legitimately
    exit with. Only a caller that chooses the code can tell those two apart.
    """
    proc = subprocess.Popen([sys.executable, "-c", f"raise SystemExit({code})"])
    proc.wait(timeout=60)
    _PINNED_DEAD.append(proc)
    return proc


#: Windows access right that asks only whether a process object exists. It
#: carries no right to affect the process, which is why it is safe to point at
#: an arbitrary pid. Spelled out here rather than imported from ``guard`` on
#: purpose: an instrument that shares a constant with the thing it measures
#: inherits that thing's mistakes.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _pid_owns_a_process_object(pid: int) -> bool:
    """Return True if the OS still has a process object under ``pid``.

    This asks the RECYCLABILITY question directly, and it is a different
    question from :func:`guard.pid_is_alive`. On Windows a pid cannot be
    handed out again while a process object still exists under it, and that
    object outlives the process itself for exactly as long as some handle to
    it stays open. So a successful ``OpenProcess`` here means the allocator
    cannot reissue this pid, and a failure means it can - regardless of
    whether the process has exited.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


# ---------------------------------------------------------------------------
# the _dead_pid helper itself
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "The pin is a Windows guarantee and only Windows can be asked about it. "
        "POSIX frees a pid at the moment the zombie is reaped, so holding the "
        "Popen buys nothing there and there is no handle to probe."
    ),
)
def test_dead_pid_is_not_recyclable_at_the_moment_it_is_handed_back() -> None:
    """The pid handed back must be dead AND unable to come round again.

    Those two properties pull against each other and holding both at once is
    the entire point of the helper. A pid is only unrecyclable while the OS
    still holds a process object for it, and the obvious way to keep one -
    leaving the child unreaped - would make the pid read as ALIVE and break
    every caller below. A reaped child with an open handle is the one state
    that is both: gone, and not reissuable.

    Asserted on two pids, because pinning only the most recent one would
    satisfy a single-pid check while still letting an earlier pid escape.
    """
    first = _dead_pid()
    second = _dead_pid()

    assert guard_mod.pid_is_alive(first) is False
    assert guard_mod.pid_is_alive(second) is False

    assert _pid_owns_a_process_object(first) is True, (
        "the first pid was released back to the allocator and can be reissued"
    )
    assert _pid_owns_a_process_object(second) is True, (
        "the second pid was released back to the allocator and can be reissued"
    )

    # Control on the instrument itself: it must be capable of saying False, or
    # the two assertions above prove nothing. Windows pids are multiples of
    # four, so this one has never named a process.
    assert _pid_owns_a_process_object(999999) is False


def test_dead_pid_retains_the_reaped_process_object_that_holds_the_pid() -> None:
    """The same mechanism, asserted where the OS cannot be asked.

    The test above is the ground truth and it can only run on Windows, so this
    one states the invariant behind it in a form POSIX can also check: after
    the call, a reaped ``Popen`` for that exact pid is still referenced. That
    reference is what keeps the handle - and therefore the pid - from being
    released.

    Deliberately NOT a check that the helper avoids a ``with`` block. That
    would encode ``OPS-17``'s stated mechanism, which measurement contradicts:
    ``__exit__`` never closed the handle, the refcount drop did, and a helper
    could keep the ``with`` and still be correct.
    """
    before = len(_PINNED_DEAD)

    pid = _dead_pid()

    assert len(_PINNED_DEAD) == before + 1, "the pin is what keeps the pid reserved"
    pinned = _PINNED_DEAD[-1]
    assert pinned.pid == pid
    assert pinned.returncode is not None, (
        "a pinned child that was never reaped would reserve its pid by being ALIVE, "
        "which is the one thing every caller of this helper needs it not to be"
    )
    assert guard_mod.pid_is_alive(pid) is False


# ---------------------------------------------------------------------------
# liveness probe
# ---------------------------------------------------------------------------


def test_pid_is_alive_for_this_process() -> None:
    assert guard_mod.pid_is_alive(os.getpid()) is True


def test_pid_is_alive_false_for_a_reaped_process() -> None:
    assert guard_mod.pid_is_alive(_dead_pid()) is False


@pytest.mark.parametrize("pid", [None, 0, -1, -12345])
def test_pid_is_alive_rejects_nonsense(pid) -> None:
    assert guard_mod.pid_is_alive(pid) is False


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "The collision is a Windows constant - GetExitCodeProcess overloads one "
        "DWORD with both the exit code and STILL_ACTIVE - and only the Windows "
        "branch can hold it. The pin that makes the assertion non-vacuous is a "
        "Windows guarantee too: POSIX frees the pid the moment the zombie is "
        "reaped, so on POSIX this would probe whoever inherited the number."
    ),
)
@pytest.mark.parametrize("exit_code", [0, 1, 42, 258, 259, 260])
def test_a_reaped_child_reads_dead_whatever_exit_code_it_chose(exit_code: int) -> None:
    """A process that has exited is dead, and its exit code is not a vote.

    259 is ``STILL_ACTIVE``, the value ``GetExitCodeProcess`` writes for a
    process that has NOT exited. It is also an exit code a process may pass to
    ``ExitProcess``, so a probe that compares the two is asking a question the
    return value cannot answer. Measured before the fix: 0, 1, 42, 258 and 260
    all read dead, and 259 read ALIVE, 5 of 5.

    The neighbours are in the parameter list because they are what separates a
    fixed collision from a special-cased number. 258 is there deliberately: it
    is ``WAIT_TIMEOUT`` in the wait-status space, which is the constant the
    REJECTED ``WaitForSingleObject`` design would have had to keep apart from
    an exit code. The shipped fix reads the exit TIME instead and touches
    neither space, so 258 is now just a neighbour - but it stays parameterised,
    because a later rewrite that reaches for the wait API would trip on it.

    Consequence, and the reason this is not a curiosity: ``guard.acquire``
    refuses to start when the recorded pid reads alive, and THREE call sites in
    ``ops/loop/watch.py`` reach liveness through here - ``armed_pid``,
    ``ensure_armed`` and ``check_watcher``. A loop or a watcher that exited
    with 259 would be believed alive for as long as anything held its process
    object open, and nothing would ever re-arm.

    That last clause is the honest bound and it matters: the shipped
    ``default_spawn`` drops its ``Popen`` at ``return child.pid``, so in the
    detached topology nothing holds the handle and the pid frees within a
    second. The defect is real and summonable, and it was NOT firing in
    production - a third party holding a handle is what sustains it.
    """
    proc = _dead_pid_exiting_with(exit_code)

    assert proc.returncode == exit_code, (
        "the child did not exit with the code this case is about, so a dead "
        "reading below would be about some other exit"
    )
    assert _pid_owns_a_process_object(proc.pid) is True, (
        "the pin did not hold, so OpenProcess would fail and pid_is_alive would "
        "answer False for the wrong reason entirely - a vacuous pass"
    )

    assert guard_mod.pid_is_alive(proc.pid) is False


def test_a_child_that_is_still_running_reads_alive() -> None:
    """The other half of the pair: do not fix the bug by answering dead.

    A probe hardwired to False would satisfy every case above, so this pins a
    process that genuinely IS running. A separate process rather than
    ``os.getpid()``, because our own pid is the one case a broken probe is most
    likely to get right by accident.

    The child is ended by closing the stdin it is blocked on, never by killing
    it - this repo does not terminate processes, not even in its tests.
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
    )
    try:
        assert guard_mod.pid_is_alive(proc.pid) is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)

    # Same pid, same still-open handle, opposite answer now that it has exited.
    assert proc.returncode == 0
    assert guard_mod.pid_is_alive(proc.pid) is False


def test_liveness_probe_does_not_kill_the_process_it_asks_about() -> None:
    """The probe must be read-only.

    On Windows, ``os.kill(pid, 0)`` - the conventional POSIX existence check -
    maps onto ``TerminateProcess``, so the naive implementation of this
    function would kill the process it is asking about. Ask about this very
    process repeatedly and require that it is still here afterwards.
    """
    for _ in range(5):
        assert guard_mod.pid_is_alive(os.getpid()) is True
    assert guard_mod.pid_is_alive(os.getpid()) is True


# ---------------------------------------------------------------------------
# the fail-closed promise
# ---------------------------------------------------------------------------


class _FakeCall:
    """A stand-in for a ctypes function object.

    It must tolerate ``restype`` and ``argtypes`` being assigned, because the
    probe configures marshalling before calling anything, and a fake that
    refused those would fail for the wrong reason.
    """

    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.restype = None
        self.argtypes = None

    def __call__(self, *args):
        self.calls += 1
        return self.result


class _FakeGetProcessTimes(_FakeCall):
    """``GetProcessTimes``, with a settable outcome and exit timestamp."""

    def __init__(self, result, exit_raw=0):
        super().__init__(result)
        self.exit_raw = exit_raw

    def __call__(self, handle, created, exited, in_kernel, in_user):
        self.calls += 1
        if self.exit_raw:
            # byref() hands back a CArgObject; _obj is the structure itself.
            exited._obj.dwLowDateTime = self.exit_raw & 0xFFFFFFFF
            exited._obj.dwHighDateTime = self.exit_raw >> 32
        return self.result


class _FakeKernel32:
    def __init__(self, *, open_result, times):
        self.OpenProcess = _FakeCall(open_result)
        self.GetProcessTimes = times
        self.CloseHandle = _FakeCall(1)


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_a_handle_that_opens_but_will_not_answer_reads_ALIVE(monkeypatch) -> None:
    """A readable handle whose times cannot be read is UNDECIDED, so: alive.

    This is the promise in :func:`guard.pid_is_alive`'s docstring - when
    existence cannot be determined the answer is True, so an ambiguous case
    declines to start rather than trampling a live loop - and until now
    NOTHING asserted it. The refutation pass for ``OPS-18`` flipped this exact
    branch to return False and watched the whole suite stay green.

    Injected rather than provoked, deliberately. There is no reliable way to
    make ``GetProcessTimes`` fail on a handle that opened, so the honest choice
    is a fake that fails on demand and a mirror below proving the fake can also
    produce the opposite answer. A single-direction injection would pass just
    as happily against a function hardwired to return True.
    """
    import ctypes

    fake = _FakeKernel32(open_result=4321, times=_FakeGetProcessTimes(0))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)

    assert guard_mod.pid_is_alive(1234) is True, (
        "an unreadable handle is undecided, and undecided must fail CLOSED"
    )
    assert fake.GetProcessTimes.calls == 1, "the branch under test was never reached"
    assert fake.CloseHandle.calls == 1, "the handle was leaked on the failure path"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_the_injected_probe_can_still_report_dead(monkeypatch) -> None:
    """The mirror: the same fake, answering, reports a real exit as DEAD.

    Without this, the test above would pass against an implementation that
    ignored every reading and returned True unconditionally - which is exactly
    the shape of a vacuous guard.
    """
    import ctypes

    # The value is arbitrary and deliberately small: the probe compares the
    # assembled timestamp against zero and nothing else, so only zero-versus-
    # non-zero carries meaning here. A realistic 18-digit FILETIME was used
    # first and tripped tests/test_no_pii.py's long-identifier rule, which is
    # the guard behaving correctly - the fix is a different constant, never a
    # narrower rule.
    fake = _FakeKernel32(open_result=4321, times=_FakeGetProcessTimes(1, exit_raw=7))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)

    assert guard_mod.pid_is_alive(1234) is False
    assert fake.CloseHandle.calls == 1


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_a_zero_exit_timestamp_reads_alive(monkeypatch) -> None:
    """And the third reading: answered, zero timestamp, still running.

    Pins the constant itself. A probe that read any successful call as "dead"
    would pass both tests above and fail this one.
    """
    import ctypes

    fake = _FakeKernel32(open_result=4321, times=_FakeGetProcessTimes(1, exit_raw=0))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)

    assert guard_mod.pid_is_alive(1234) is True


# ---------------------------------------------------------------------------
# acquire / refuse / reclaim / release
# ---------------------------------------------------------------------------


def test_acquire_creates_a_lock_recording_the_owner(lock_path: Path) -> None:
    held = guard_mod.acquire(lock_path)

    assert held == lock_path
    assert lock_path.exists()

    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert payload["pid"] == os.getpid()
    assert payload["acquired"]
    assert guard_mod.read_owner(lock_path) == os.getpid()
    assert guard_mod.is_locked(lock_path) is True


def test_second_acquire_is_refused_while_the_owner_is_alive(lock_path: Path) -> None:
    guard_mod.acquire(lock_path)

    with pytest.raises(LockBusy) as excinfo:
        guard_mod.acquire(lock_path)

    assert excinfo.value.pid == os.getpid()
    assert excinfo.value.path == lock_path
    # The refusal must not have disturbed the existing lock.
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_second_acquire_is_refused_for_a_live_foreign_owner(lock_path: Path) -> None:
    """A live owner that is not us is still a live owner."""
    guard_mod.acquire(lock_path, pid=os.getpid(), label="first loop")

    with pytest.raises(LockBusy):
        guard_mod.acquire(lock_path, pid=os.getpid() + 100000, label="second loop")

    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_stale_lock_whose_pid_is_gone_is_reclaimed(lock_path: Path) -> None:
    dead = _dead_pid()
    guard_mod.acquire(lock_path, pid=dead, label="crashed loop")
    assert guard_mod.read_owner(lock_path) == dead
    assert guard_mod.is_locked(lock_path) is False, "a dead owner does not hold the lock"

    reclaimed = guard_mod.acquire(lock_path)

    assert reclaimed == lock_path
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_unreadable_lock_file_is_treated_as_stale(lock_path: Path) -> None:
    # A lock truncated by a power loss has no recoverable owner. Blocking on it
    # forever would need an operator, which is the thing we are avoiding.
    lock_path.write_text("{not json", encoding="utf-8")
    assert guard_mod.read_owner(lock_path) is None

    guard_mod.acquire(lock_path)
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_release_removes_our_own_lock(lock_path: Path) -> None:
    guard_mod.acquire(lock_path)

    assert guard_mod.release(lock_path) is True
    assert not lock_path.exists()
    assert guard_mod.is_locked(lock_path) is False

    # And the lock is genuinely available again.
    guard_mod.acquire(lock_path)
    assert lock_path.exists()


def test_release_is_a_no_op_when_there_is_no_lock(lock_path: Path) -> None:
    assert guard_mod.release(lock_path) is False


def test_release_refuses_to_drop_someone_elses_lock(lock_path: Path) -> None:
    other = os.getpid() + 100000
    guard_mod.acquire(lock_path, pid=other)

    assert guard_mod.release(lock_path) is False
    assert lock_path.exists(), "releasing another owner's lock would defeat the guard"

    assert guard_mod.release(lock_path, pid=other) is True
    assert not lock_path.exists()


def test_release_force_clears_a_foreign_lock(lock_path: Path) -> None:
    guard_mod.acquire(lock_path, pid=os.getpid() + 100000)
    assert guard_mod.release(lock_path, force=True) is True
    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# released() context manager
# ---------------------------------------------------------------------------


def test_released_holds_then_frees(lock_path: Path) -> None:
    with guard_mod.released(lock_path) as held:
        assert held == lock_path
        assert lock_path.exists()
        assert guard_mod.read_owner(lock_path) == os.getpid()

    assert not lock_path.exists()


def test_released_frees_the_lock_on_an_exception(lock_path: Path) -> None:
    boom = RuntimeError("cycle blew up")

    with pytest.raises(RuntimeError) as excinfo, guard_mod.released(lock_path):
        assert lock_path.exists()
        raise boom

    assert excinfo.value is boom
    assert not lock_path.exists(), "a crashed cycle must not leave the loop wedged"


def test_released_refuses_to_enter_when_a_live_loop_holds_the_lock(lock_path: Path) -> None:
    guard_mod.acquire(lock_path)

    entered = False
    with pytest.raises(LockBusy), guard_mod.released(lock_path):
        entered = True

    assert entered is False
    # The refused attempt must not have released the incumbent's lock.
    assert lock_path.exists()
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_released_reclaims_a_stale_lock(lock_path: Path) -> None:
    guard_mod.acquire(lock_path, pid=_dead_pid())

    with guard_mod.released(lock_path):
        assert guard_mod.read_owner(lock_path) == os.getpid()

    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# the prohibition
# ---------------------------------------------------------------------------


def test_guard_exposes_no_termination_path() -> None:
    """The guard refuses to start; it never stops anybody.

    This is a structural check, not a style one - a terminate path added here
    would let an unattended loop kill a process nobody was watching it choose.
    """
    exported = set(guard_mod.__all__)
    forbidden = {"kill", "terminate", "stop", "stop_process", "taskkill", "signal"}
    assert not (exported & forbidden)

    # Structural, over the parsed module rather than its text - the docstring
    # names the things it refuses to do, and a raw text scan would flag its own
    # documentation.
    tree = ast.parse(Path(guard_mod.__file__).read_text(encoding="utf-8"))

    called: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            called.append((func.attr, node))
        elif isinstance(func, ast.Name):
            called.append((func.id, node))

    names = {name for name, _ in called}
    forbidden = {
        "TerminateProcess",
        "terminate",
        "taskkill",
        "system",
        "Popen",
        "check_call",
        "check_output",
    }
    assert not (names & forbidden), f"guard must not call {sorted(names & forbidden)}"

    # os.kill exists here only as the POSIX existence probe, and only ever with
    # signal 0. Any other signal would make this module a killer.
    kill_calls = [node for name, node in called if name == "kill"]
    assert kill_calls, "expected the POSIX liveness probe to be present"
    for node in kill_calls:
        assert len(node.args) == 2, ast.dump(node)
        signal_arg = node.args[1]
        assert isinstance(signal_arg, ast.Constant) and signal_arg.value == 0, ast.dump(node)

    # And it does not reach for a shell to do what it will not do in Python.
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "subprocess" not in imported


def test_default_lock_path_points_into_the_gitignored_runtime_dir() -> None:
    default = guard_mod.default_lock_path()
    assert default.name == guard_mod.LOCK_FILENAME
    assert default.parent == guard_mod.runtime_dir()
    assert default.parent.parent.name == "ops"
