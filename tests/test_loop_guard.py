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


def _dead_pid() -> int:
    """Return a pid that is genuinely no longer running.

    Spawning and reaping a real process beats picking a large number and
    hoping: a guessed pid can be reused, and the test would then flake in the
    one direction that matters (a live lock silently reclaimed).
    """
    with subprocess.Popen([sys.executable, "-c", ""]) as proc:
        proc.wait(timeout=60)
        return proc.pid


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
