"""Single-instance guard for the unattended loop.

Two loops running at once is not a performance problem, it is a correctness
problem: they interleave commits, race each other's ledger appends, and each
one reads a state file the other is rewriting. The second one must simply not
start.

The mechanism is a lock file created with ``O_CREAT | O_EXCL``, which is the
one filesystem primitive that is atomic against a concurrent creator on both
POSIX and Windows: exactly one caller gets the file, everyone else gets
``FileExistsError``. The file carries the owning pid so a stale lock - left by
a loop that was killed, or by a machine that lost power mid-cycle - can be
identified and reclaimed instead of blocking every future run forever.

**This module never kills anything.** It has no terminate path, no
``Stop-Process`` equivalent, and no way to signal the owner. If the recorded
pid is alive, :func:`acquire` raises :class:`LockBusy` and the caller declines
to start. Deciding that another process is unwanted is an operator decision,
and an unattended loop is exactly the wrong thing to be making it.

Liveness on Windows deserves a note. ``os.kill(pid, 0)`` is the usual POSIX
existence probe, but on Windows CPython maps ``os.kill`` for any signal other
than the two console-control events onto ``TerminateProcess`` - so the
conventional "harmless" probe would kill the process it is asking about. This
module therefore uses ``OpenProcess`` with ``PROCESS_QUERY_LIMITED_INFORMATION``
plus ``GetExitCodeProcess`` on Windows, and the ordinary signal-0 probe only on
POSIX.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "LOCK_FILENAME",
    "LockBusy",
    "acquire",
    "default_lock_path",
    "is_locked",
    "pid_is_alive",
    "read_owner",
    "release",
    "released",
    "runtime_dir",
]

#: Repository root, resolved from this file's location: ops/loop/guard.py.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Name of the lock file inside the runtime directory.
LOCK_FILENAME = "loop.lock"

#: Windows access right that is enough to ask whether a process exists without
#: acquiring any right to affect it.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: Windows ``GetExitCodeProcess`` sentinel meaning "has not exited".
_STILL_ACTIVE = 259


class LockBusy(RuntimeError):
    """Raised when the lock is held by a process that is still alive.

    Attributes:
        path: The lock file that is held.
        pid: The owning pid, or ``None`` when the file was unreadable but a
            live owner could not be ruled out.
    """

    def __init__(self, path: Path, pid: int | None) -> None:
        owner = f"pid {pid}" if pid is not None else "an unreadable owner record"
        super().__init__(
            f"loop lock {path} is held by {owner}; refusing to start a second loop. "
            "This guard never terminates the holder - stop it yourself, or delete the "
            "lock file if you know the holder is gone."
        )
        self.path = path
        self.pid = pid


def runtime_dir() -> Path:
    """Return the runtime directory (``ops/runtime``), which is gitignored."""
    return REPO_ROOT / "ops" / "runtime"


def default_lock_path() -> Path:
    """Return the default lock file path."""
    return runtime_dir() / LOCK_FILENAME


def _now() -> str:
    """Return the current UTC time as a second-resolution ISO 8601 string."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _windows_pid_is_alive(pid: int) -> bool:
    """Return True if ``pid`` names a running process, without touching it."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # No such process, or it is gone and unopenable. Either way, not a
        # holder worth blocking on.
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            # The handle opened, so something is there; fail closed and treat
            # it as alive rather than reclaiming a lock we cannot judge.
            return True
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_is_alive(pid: int | None) -> bool:
    """Return True if ``pid`` currently names a running process.

    Fails closed: when existence cannot be determined, the answer is True, so
    an ambiguous case refuses to start rather than trampling a live loop.
    """
    if pid is None or not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False

    if sys.platform == "win32":
        return _windows_pid_is_alive(pid)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # It exists, it just is not ours to signal.
        return True
    return True


def read_owner(path: Path | None = None) -> int | None:
    """Return the pid recorded in the lock file, or ``None``.

    ``None`` covers every unreadable case - no file, invalid JSON, missing or
    non-integer ``pid`` - because the caller treats them identically.
    """
    target = Path(path) if path is not None else default_lock_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        return None
    return pid


def is_locked(path: Path | None = None) -> bool:
    """Return True if a lock file exists and its owner is still alive."""
    target = Path(path) if path is not None else default_lock_path()
    if not target.exists():
        return False
    return pid_is_alive(read_owner(target))


def _write_lock(target: Path, pid: int, label: str) -> None:
    """Create ``target`` exclusively, or raise :class:`FileExistsError`."""
    payload = {
        "pid": pid,
        "acquired": _now(),
        "label": label,
    }
    body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    # O_EXCL is the whole guard: if the file exists, this raises rather than
    # opening it, and the raise is atomic against a concurrent creator.
    handle = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())


def acquire(path: Path | None = None, *, pid: int | None = None, label: str = "loop") -> Path:
    """Take the single-instance lock, or refuse.

    A lock whose recorded owner is no longer running is stale - the previous
    loop died without cleaning up - and is reclaimed by unlinking it and
    retrying the exclusive create exactly once. The retry is bounded on purpose:
    if a second attempt still collides, another process won the race fairly and
    the correct answer is to decline.

    Args:
        path: Lock file to take. Defaults to :func:`default_lock_path`.
        pid: Owner pid to record. Defaults to this process.
        label: Free-text note stored in the lock, to make a stray lock file
            self-explanatory to whoever finds it.

    Returns:
        The path of the lock now held.

    Raises:
        LockBusy: The lock is held by a live process. Nothing is terminated.
    """
    target = Path(path) if path is not None else default_lock_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    owner_pid = os.getpid() if pid is None else pid

    try:
        _write_lock(target, owner_pid, label)
        return target
    except FileExistsError:
        pass

    existing = read_owner(target)
    if pid_is_alive(existing):
        raise LockBusy(target, existing)

    # Stale. Reclaim it - this removes a lock FILE, never a process.
    with suppress(FileNotFoundError):
        target.unlink()

    try:
        _write_lock(target, owner_pid, label)
    except FileExistsError as exc:
        # Someone else reclaimed it between our unlink and our create.
        raise LockBusy(target, read_owner(target)) from exc
    return target


def release(path: Path | None = None, *, pid: int | None = None, force: bool = False) -> bool:
    """Release the lock if this process owns it.

    Args:
        path: Lock file to release. Defaults to :func:`default_lock_path`.
        pid: The pid claiming ownership. Defaults to this process.
        force: Release regardless of who is recorded as the owner. Only for an
            operator clearing a lock by hand.

    Returns:
        True if a lock file was removed, False if there was nothing to remove
        or it belonged to someone else.
    """
    target = Path(path) if path is not None else default_lock_path()
    if not target.exists():
        return False

    claimant = os.getpid() if pid is None else pid
    owner = read_owner(target)
    if not force and owner is not None and owner != claimant:
        return False

    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True


@contextmanager
def released(
    path: Path | None = None,
    *,
    pid: int | None = None,
    label: str = "loop",
) -> Iterator[Path]:
    """Hold the lock for the duration of the block, then guarantee release.

    The name describes the postcondition, which is the property that matters:
    however the block exits - return, exception, ``KeyboardInterrupt`` - the
    lock is released. The stale-reclaim path in :func:`acquire` exists because
    this guarantee cannot cover a hard kill or a power loss.

    Yields:
        The path of the held lock.

    Raises:
        LockBusy: Another live loop holds the lock. The block does not run and
            nothing already held is released.
    """
    target = acquire(path, pid=pid, label=label)
    try:
        yield target
    finally:
        release(target, pid=pid)
