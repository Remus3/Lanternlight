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


#: ``OpenProcess`` failure codes, spelled here rather than imported from
#: ``guard`` for the reason above: an instrument that shares a constant with
#: the thing it measures inherits that thing's mistakes. 5 is
#: ``ERROR_ACCESS_DENIED`` - the process EXISTS and this token may not ask
#: about it. 87 is ``ERROR_INVALID_PARAMETER`` - the pid names nothing.
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87

#: A failure code that is NEITHER of the two the probe recognises, used to pin
#: which way an uncharacterised one falls. ``ERROR_NOT_ENOUGH_MEMORY``, chosen
#: because a resource failure is a real way for ``OpenProcess`` to fail while
#: saying nothing whatever about the pid.
_ERROR_NOT_ENOUGH_MEMORY = 8


def _open_process_last_error(pid: int) -> int:
    """Return the Win32 error a REAL ``OpenProcess`` sets for ``pid``, or 0.

    Ground truth for the constants the injected tests below assert on. An
    injected 87 pins the branch and says nothing about whether Windows
    actually answers 87 for a pid that never existed, and a constant nobody
    ever measured is exactly the kind of thing that reads correct and is not.

    ``use_last_error=True`` is load-bearing: ctypes swaps the thread's error
    around every such call and stashes the real one privately, so
    ``ctypes.get_last_error()`` is the accessor and the system one is not.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ctypes.get_last_error()
    kernel32.CloseHandle(handle)
    return 0


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


class _FakeOpenProcess(_FakeCall):
    """``OpenProcess``, with a settable handle AND the error it left behind.

    The two live on one object on purpose. ``GetLastError`` is only meaningful
    immediately after the call that set it, so a fake that let a test state an
    error independently of the call could go green while the probe never
    consulted the error at all. Here the error is READ off the same object the
    call went through, and :attr:`error_reads` records that it was read.
    """

    def __init__(self, result, last_error=0):
        super().__init__(result)
        self.last_error = last_error
        self.error_reads = 0

    def read_last_error(self):
        """Stand in for ``ctypes.get_last_error()``.

        Counts rather than raises. A spy that raised would be vacuous the
        moment any caller wrapped this in ``except Exception``, which is a
        trap this repo has already paid for; a counter the test asserts on
        cannot be swallowed.
        """
        self.error_reads += 1
        return self.last_error


class _FakeKernel32:
    def __init__(self, *, open_result, times, last_error=0):
        self.OpenProcess = _FakeOpenProcess(open_result, last_error)
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
# OPS-19: a failed OpenProcess is TWO different facts
# ---------------------------------------------------------------------------


def _install(monkeypatch, *, last_error, open_result=0):
    """Install a fake kernel32 whose ``OpenProcess`` fails with ``last_error``.

    Patches ``ctypes.get_last_error`` alongside ``ctypes.WinDLL``, because
    with the library faked no real call happens and the genuine accessor would
    hand back whatever some earlier, unrelated call left in the slot - a stale
    reading that could make any of these tests pass for no reason.
    """
    import ctypes

    fake = _FakeKernel32(
        open_result=open_result,
        times=_FakeGetProcessTimes(1, exit_raw=0),
        last_error=last_error,
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)
    monkeypatch.setattr(ctypes, "get_last_error", fake.OpenProcess.read_last_error)
    return fake


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_access_denied_on_open_reads_ALIVE(monkeypatch) -> None:
    """``ERROR_ACCESS_DENIED`` means it EXISTS, so the answer is True.

    This is ``OPS-19``. The probe used to read any failed ``OpenProcess`` as
    "not a holder worth blocking on", folding "no such process" together with
    "running, and this token may not ask" - a fail-OPEN inside a function
    whose contract promises fail-closed. Measured with ``SeDebugPrivilege``
    dropped, 13 running processes read DEAD through it.

    Injected, not provoked, and said plainly: a genuine denial needs a
    protected or other-user subject AND the privilege dropped from the probing
    token, and this session's token holds it, which bypasses the DACL check in
    ``OpenProcess`` and measures zero denials. The mirror below is what stops
    the injection from being satisfied by a function hardwired to True, and
    ``test_a_pid_that_never_existed_reads_dead_through_the_real_api`` is what
    ties the injected constants back to what Windows actually answers.
    """
    fake = _install(monkeypatch, last_error=_ERROR_ACCESS_DENIED)

    assert guard_mod.pid_is_alive(1234) is True, (
        "a process this token may not open is UNDECIDED, and undecided fails CLOSED"
    )
    assert fake.OpenProcess.calls == 1
    assert fake.OpenProcess.error_reads == 1, "the failure code was never consulted"
    assert fake.GetProcessTimes.calls == 0, "there was no handle to ask through"
    assert fake.CloseHandle.calls == 0, "a null handle must not be closed"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_no_such_process_on_open_reads_DEAD(monkeypatch) -> None:
    """``ERROR_INVALID_PARAMETER`` means the pid names nothing: False.

    The mirror, and the half that must not regress. Without it the test above
    would pass against a probe that answered True for every open failure,
    which would wedge ``acquire`` on any stale lock forever - the exact
    failure the reclaim path exists to prevent.
    """
    fake = _install(monkeypatch, last_error=_ERROR_INVALID_PARAMETER)

    assert guard_mod.pid_is_alive(1234) is False
    assert fake.OpenProcess.error_reads == 1, "the failure code was never consulted"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_an_uncharacterised_open_failure_reads_ALIVE(monkeypatch) -> None:
    """A third code is not a third answer: anything unrecognised fails CLOSED.

    There are far more than two possible values and only one of them is known
    to mean "no such process". Treating an unfamiliar code as "gone" would
    reclaim a live loop's lock on the strength of an error nobody has
    characterised; treating it as undecided costs a refusal the operator can
    clear by deleting the lock file, which :class:`LockBusy` already says.
    """
    fake = _install(monkeypatch, last_error=_ERROR_NOT_ENOUGH_MEMORY)

    assert guard_mod.pid_is_alive(1234) is True
    assert fake.OpenProcess.error_reads == 1, "the failure code was never consulted"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_a_pid_that_never_existed_reads_dead_through_the_real_api() -> None:
    """No fake anywhere: 999999 must still read DEAD, and 87 is why.

    ``_dead_pid``'s whole contract rests on a gone pid reading dead, and
    ``tests/test_loop_watch.py`` uses 999999 as a stand-in pid too, so this is
    the regression that the ``OPS-19`` fix must not cause. It also grounds the
    injected constant: the first assertion is Windows itself saying 87 for a
    pid that has never named a process. Windows pids are multiples of four, so
    999999 is one that never has.
    """
    assert _open_process_last_error(999999) == _ERROR_INVALID_PARAMETER
    assert guard_mod.pid_is_alive(999999) is False


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_acquire_does_not_steal_a_lock_from_an_owner_it_cannot_open(
    monkeypatch, lock_path: Path
) -> None:
    """The consumer, which is the only reason any of this matters.

    Editing the probe proves the probe changed; it does not prove the caller's
    behaviour changed. A loop under a different token - a scheduled task,
    another user, an elevated session - holds a lock whose owner this token
    cannot open. Before ``OPS-19`` that owner read dead and the lock was
    unlinked and retaken SILENTLY, which is the two-loops-interleaving-commits
    failure the module exists to prevent.
    """
    foreign = 4  # the System process: unopenable even from an elevated token.
    lock_path.write_text(
        json.dumps({"pid": foreign, "acquired": "2026-09-04T00:00:00+00:00", "label": "other"}),
        encoding="utf-8",
    )
    _install(monkeypatch, last_error=_ERROR_ACCESS_DENIED)

    with pytest.raises(LockBusy) as excinfo:
        guard_mod.acquire(lock_path)

    assert excinfo.value.pid == foreign
    assert guard_mod.read_owner(lock_path) == foreign, "the foreign lock was overwritten"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_acquire_still_reclaims_a_lock_whose_owner_does_not_exist(
    monkeypatch, lock_path: Path
) -> None:
    """The mirror at the consumer: a genuinely gone owner is still reclaimed.

    Fail-closed must not become fail-shut. A probe that answered True for
    every open failure would pass the test above and wedge every future run
    against any stale lock, which is worse than the defect being fixed.
    """
    lock_path.write_text(
        json.dumps({"pid": 999999, "acquired": "2026-09-04T00:00:00+00:00", "label": "gone"}),
        encoding="utf-8",
    )
    _install(monkeypatch, last_error=_ERROR_INVALID_PARAMETER)

    assert guard_mod.acquire(lock_path) == lock_path
    assert guard_mod.read_owner(lock_path) == os.getpid()


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


# ---------------------------------------------------------------------------
# a corrupt lock is not an absent one - OPS-21
# ---------------------------------------------------------------------------

#: Every shape of lock file that exists on disk and carries no readable owner
#: pid. Each is a separate way for the file to survive a crash without
#: surviving intact, and every one of them used to be reclaimed in silence:
#: ``read_owner`` answered ``None``, ``pid_is_alive(None)`` answered False, and
#: ``acquire`` unlinked a lock it had not read and took it.
#:
#: The last entry is not a JSON defect at all. ``UnicodeDecodeError`` is a
#: ``ValueError``, not an ``OSError``, and the old ``except`` clause named
#: ``json.JSONDecodeError`` specifically - so a lock file carrying one stray
#: non-UTF-8 byte did not return ``None``, it RAISED out through
#: ``read_owner``, ``is_locked`` and ``acquire``. Measured on this machine
#: before the fix.
_CORRUPT_LOCKS = [
    pytest.param(b"", id="empty file"),
    pytest.param(b"\x00" * 64, id="NUL bytes - a power-loss truncation"),
    pytest.param(b"{not json", id="truncated JSON"),
    pytest.param(b"[1, 2, 3]", id="valid JSON, not an object"),
    pytest.param(b'"loop"', id="valid JSON, a bare string"),
    pytest.param(b"null", id="valid JSON null"),
    pytest.param(b'{"label": "loop"}', id="an object with no pid at all"),
    pytest.param(b'{"pid": "1234"}', id="pid is a string"),
    pytest.param(b'{"pid": true}', id="pid is a bool"),
    pytest.param(b'{"pid": 12.5}', id="pid is a float"),
    pytest.param(b'{"pid": null}', id="pid is null"),
    pytest.param(b'{"pid": 1234, "label": "\xff\xfe"}', id="not valid UTF-8"),
]


@pytest.mark.parametrize("body", _CORRUPT_LOCKS)
def test_a_corrupt_lock_is_unreadable_and_read_owner_still_answers_None(
    body: bytes, lock_path: Path
) -> None:
    """The classifier separates the fact; ``read_owner``'s contract does not move.

    ``read_owner`` is called from four places and asserted on in a dozen tests,
    so it keeps returning ``int | None`` exactly as before. The new bit - file
    present but unreadable, as against file absent - is carried by
    :func:`guard.owner_of`, and nothing that only wants a pid has to care.
    """
    lock_path.write_bytes(body)

    assert guard_mod.owner_of(lock_path) is guard_mod.UNREADABLE
    assert guard_mod.read_owner(lock_path) is None


@pytest.mark.parametrize("body", _CORRUPT_LOCKS)
def test_a_corrupt_lock_file_makes_acquire_refuse(body: bytes, lock_path: Path) -> None:
    """The consumer, which is the only reason the classifier matters.

    A lock file this code cannot parse is not a licence to take the lock. The
    owner may be alive and mid-commit; the file simply no longer says so. That
    is the undecided case, and ``OPS-19`` already settled which way undecided
    resolves in this module: refusing to start beats trampling a live loop.

    The refusal must also leave the evidence alone - an ``acquire`` that
    refused and then unlinked the file would be the same defect with an extra
    step.
    """
    lock_path.write_bytes(body)

    with pytest.raises(LockBusy) as excinfo:
        guard_mod.acquire(lock_path)

    assert excinfo.value.pid is None
    assert excinfo.value.path == lock_path
    assert lock_path.read_bytes() == body, "the corrupt lock was overwritten"


def test_a_lock_path_that_cannot_be_opened_at_all_is_unreadable(lock_path: Path) -> None:
    """The ``OSError`` arm, which no JSON payload can reach.

    A directory where the lock file should be is the cheapest real way to make
    ``read_text`` fail with something that is not ``FileNotFoundError`` - it
    raises ``PermissionError`` on Windows and ``IsADirectoryError`` on POSIX,
    and both mean the same thing here: something IS at that path and this code
    cannot read it. ``FileNotFoundError`` is the only ``OSError`` that is
    allowed to answer "absent", and this test is what stops that clause being
    widened back to a bare ``except OSError``.
    """
    lock_path.mkdir()

    assert guard_mod.owner_of(lock_path) is guard_mod.UNREADABLE
    assert guard_mod.read_owner(lock_path) is None
    assert guard_mod.is_locked(lock_path) is True


@pytest.mark.parametrize("impossible", [0, -1, -4321])
def test_a_readable_but_impossible_pid_is_still_folded_with_a_dead_owner(
    impossible: int, lock_path: Path
) -> None:
    """The case this fix deliberately does NOT close, pinned so the claim is checkable.

    ``owner_of``'s docstring says a lock recording a pid that is readable but
    impossible - zero or negative - is returned as that pid and reclaimed like
    a crashed loop. A sentence like that is worth nothing unheld by a test:
    cycle 42 shipped three docstring sentences that were simply false. So this
    is what the module does today, asserted rather than described.

    Why it is left alone: the record IS readable, and reading it is the whole
    of what ``owner_of`` promises. ``_write_lock`` cannot produce such a file -
    it writes ``os.getpid()`` - so reaching it takes a hand edit or a
    corruption that damaged the number while leaving the JSON intact. Closing
    it means deciding that ``read_owner`` may withhold a pid it successfully
    read, which is a wider contract change than ``OPS-21`` asked for.
    """
    lock_path.write_text(
        json.dumps({"pid": impossible, "acquired": "2026-09-04T00:00:00+00:00", "label": "odd"}),
        encoding="utf-8",
    )

    assert guard_mod.owner_of(lock_path) == impossible
    assert guard_mod.read_owner(lock_path) == impossible
    assert guard_mod.pid_is_alive(impossible) is False
    assert guard_mod.is_locked(lock_path) is False

    assert guard_mod.acquire(lock_path) == lock_path
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_is_locked_calls_a_corrupt_lock_held(lock_path: Path) -> None:
    lock_path.write_text("{not json", encoding="utf-8")
    assert guard_mod.is_locked(lock_path) is True


def test_is_locked_is_false_when_there_is_no_lock_file(lock_path: Path) -> None:
    """The mirror. Fail-closed must not become fail-shut."""
    assert not lock_path.exists()
    assert guard_mod.is_locked(lock_path) is False


def test_a_missing_lock_file_is_still_free_to_take(lock_path: Path) -> None:
    """The case that must not break, stated on its own so a break is obvious.

    Folding "unreadable" into "absent" was the defect. Folding "absent" into
    "unreadable" would be a worse one - the loop could never start at all, on a
    machine that has never run it.
    """
    assert not lock_path.exists()
    assert guard_mod.owner_of(lock_path) is None

    assert guard_mod.acquire(lock_path) == lock_path
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_a_lock_that_vanishes_before_we_read_it_is_still_free_to_take(
    monkeypatch, lock_path: Path
) -> None:
    """Absent-at-read-time is absent, not unreadable, and the race is real.

    ``acquire`` learns the file exists from a ``FileExistsError`` and then
    reads it in a separate call. The incumbent can release between the two, and
    the second loop is then entitled to the lock. A refusal keyed on
    "``read_owner`` said None" would have wedged on that benign race; a refusal
    keyed on "the file is there and I cannot read it" does not.
    """
    real_write = guard_mod._write_lock
    calls: list[Path] = []

    def flaky_write(target: Path, pid: int, label: str) -> None:
        calls.append(target)
        if len(calls) == 1:
            # Someone else held it a moment ago and has since let it go.
            raise FileExistsError(17, "File exists", str(target))
        real_write(target, pid, label)

    monkeypatch.setattr(guard_mod, "_write_lock", flaky_write)

    assert guard_mod.acquire(lock_path) == lock_path
    assert calls == [lock_path, lock_path], "the bounded retry did not happen"
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_deleting_a_corrupt_lock_file_clears_it(lock_path: Path) -> None:
    """The operator's way out, tested rather than asserted in prose.

    An unparseable lock that could never be cleared would be its own denial of
    service, so the escape hatch is load-bearing. It is the one
    :class:`LockBusy` already documents, it needs no new flag, and it is
    exactly as destructive as it looks: it removes a FILE, never a process.
    """
    lock_path.write_bytes(b"{not json")
    with pytest.raises(LockBusy):
        guard_mod.acquire(lock_path)

    lock_path.unlink()

    assert guard_mod.acquire(lock_path) == lock_path
    assert guard_mod.read_owner(lock_path) == os.getpid()


def test_release_still_clears_an_unreadable_lock(lock_path: Path) -> None:
    """The second way out: the programmatic one, unchanged by this fix.

    ``release`` refuses only when the file names an owner that is somebody
    else. A corrupt lock names nobody, so any claimant may clear it and no
    ``force=True`` is needed. That is deliberate - it is what keeps the refusal
    above recoverable from inside Python.
    """
    lock_path.write_bytes(b"{not json")

    assert guard_mod.release(lock_path) is True
    assert not lock_path.exists()


def test_lock_busy_for_an_unreadable_owner_says_so_and_names_the_way_out(
    lock_path: Path,
) -> None:
    """The message is the whole operator interface for this refusal."""
    lock_path.write_bytes(b"{not json")

    with pytest.raises(LockBusy) as excinfo:
        guard_mod.acquire(lock_path)

    message = str(excinfo.value)
    assert "unreadable owner record" in message
    assert "delete the" in message and "lock file" in message
    assert str(lock_path) in message


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
