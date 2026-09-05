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
on Windows, and the ordinary signal-0 probe only on POSIX.

What it asks THROUGH that handle changed in ``OPS-18``, and the reason is worth
keeping. ``GetExitCodeProcess`` reports "has not exited" by writing 259 into
the same ``DWORD`` it otherwise fills with the real exit code, and 259 is a
legal exit code. A process that exited with 259 was therefore reported alive
for as long as anything held its process object open - which for the loop guard
means refusing to start forever, and for ``ops/loop/watch.py`` means refusing
to re-arm a watcher that is not there. The probe now reads the EXIT time out of
``GetProcessTimes`` instead: it is zero until the process exits and a real
timestamp afterwards, it is a different field from the exit code so no exit
code can impersonate it, and it is answerable under the right this module
already holds - ``ops/loop/watch.py`` reads the CREATION time out of the same
call under exactly that right.

The one caveat, written down rather than only known: Microsoft documents
``lpExitTime`` as "If the process has not exited, the content of this structure
is undefined." Measured on this machine, every one of 312 RUNNING processes
reported exactly zero, as did a live child. A child that had exited with 259
reported a real non-zero timestamp, which is the reading the fix turns on.

What happens when the handle does not open at all is ``OPS-19``, and it is a
separate fact from any of the above. ``OpenProcess`` fails for more than one
reason: ``ERROR_INVALID_PARAMETER`` (87) means the pid names nothing, but
``ERROR_ACCESS_DENIED`` (5) means the process is THERE, running, and this token
may not ask about it. Reading both as "gone" made a running process owned by a
scheduled task, another user or an elevated session read DEAD - measured with
``SeDebugPrivilege`` dropped, 13 running pids did exactly that, all 13 still
enumerated half a second later - and ``acquire`` reclaims a lock whose owner
reads dead. The probe therefore consults ``GetLastError`` and only 87 answers
False. Everything else, characterised or not, answers True.

The alternative - ``WaitForSingleObject`` - has fully defined semantics but
needs the ``SYNCHRONIZE`` right, and **with ``SeDebugPrivilege`` dropped from
the probing token** 77 of those same processes deny it while granting
``PROCESS_QUERY_LIMITED_INFORMATION``, so that route answers a strictly smaller
set of pids than this module can answer today. That condition is part of the
measurement, not a footnote to it: a token that HOLDS ``SeDebugPrivilege``
bypasses the DACL check in ``OpenProcess`` and sees zero denials, so the same
sweep run from an elevated session reads 0 of 338 and proves nothing. Widening
the probe's reach was judged worth more than trading a measured-but-undocumented
zero for a documented constant that cannot be asked for a quarter of them.

``OPS-21`` is a fail-OPEN in the same direction as ``OPS-19``, and the only one
of the three items above that never reaches Windows at all - it is in the
reading of the lock FILE. (``OPS-18`` was not a fail-open: reading 259 as alive
made the guard refuse to start, which is the safe direction and merely
permanent.) ``read_owner`` answered ``None`` for a missing file and for a
corrupt one alike - truncated by a power loss, holding valid JSON that is not
an object, holding a ``pid`` that is not an integer - and ``pid_is_alive(None)``
is False, so ``acquire`` unlinked and retook a lock it had failed to read. The
owner may have been alive and mid-commit; the file had simply stopped saying
so. :func:`owner_of` now separates the two, because they are opposite facts: no
lock file is genuinely unheld and must stay takeable, or a fresh machine could
never start a loop, while an unparseable one rules nothing out.
:func:`read_owner` keeps its old ``int | None`` contract for callers that only
want a pid.
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
    "UNREADABLE",
    "LockBusy",
    "acquire",
    "default_lock_path",
    "is_locked",
    "owner_of",
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

#: ``GetLastError`` after a failed ``OpenProcess``. These two are DIFFERENT
#: FACTS and folding them together was ``OPS-19``: 87 means no process bears
#: this pid, 5 means one does and this token may not open it. Only 87 licenses
#: a False.
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87

#: A zero exit ``FILETIME`` from ``GetProcessTimes`` means the process has not
#: exited. Once it has, the field carries a real timestamp - a count of
#: 100-nanosecond intervals since 1601 - and no exit CODE is involved, which is
#: the whole of ``OPS-18``.
_NOT_EXITED = 0


class _UnreadableOwner:
    """Type of :data:`UNREADABLE`, kept private so the sentinel is a singleton.

    A distinct type rather than a magic pid: no integer is free to mean "the
    file is there and says nothing", ``None`` is already spoken for by "there
    is no file", and a sentinel that is neither cannot be compared equal to
    either by accident.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNREADABLE"


#: A lock file EXISTS at the path and no owner pid can be recovered from it.
#: This is the ``OPS-21`` fact, and it is not the same fact as ``None``: an
#: absent lock is genuinely unheld and must stay takeable, while an unparseable
#: one may perfectly well belong to a live loop that is mid-commit. Only
#: :func:`owner_of` returns it; :func:`read_owner` keeps folding it into
#: ``None`` for callers that only ever wanted a pid.
UNREADABLE = _UnreadableOwner()


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
    """Return True if ``pid`` names a running process, without touching it.

    The oracle is the EXIT time from ``GetProcessTimes``, not the exit CODE
    from ``GetExitCodeProcess``. ``GetExitCodeProcess`` overloads one ``DWORD``
    with both answers - a real exit code, and 259 for "has not exited" - and
    259 is itself a legal exit code, so a process that exited with it read
    ALIVE for as long as anything held its process object open. The exit time
    is a separate field with no such overload: zero until the process exits, a
    timestamp afterwards.

    Follows the ctypes idiom in
    :func:`ops.loop.watch._windows_process_creation_time` exactly - the same
    call, the same access right, the other output field - because a second
    spelling of one probe is a second thing to get wrong.

    ``PROCESS_QUERY_LIMITED_INFORMATION`` remains the ONLY right asked for. It
    grants no power to affect the process, and it is what makes this probe
    answerable for every pid the old one could answer: measured on this machine
    WITH ``SeDebugPrivilege`` DROPPED from the probing token, 77 of the 312
    openable processes GRANT it and DENY ``SYNCHRONIZE``, so a probe built on a
    wait function would have to fall back on a quarter of them. The dropped
    privilege is load-bearing in that sentence - an elevated token bypasses the
    DACL check and measures zero denials.

    WHAT THIS RETURNS FALSE FOR, stated exactly, because a probe that
    mis-describes its own blindness is worse than one with a declared hole.
    Exactly two things: a positive exit timestamp, and an ``OpenProcess``
    failure whose ``GetLastError`` is ``ERROR_INVALID_PARAMETER`` (87), which
    is the code Windows returns when no process bears the pid. Nothing else.

    That second clause is ``OPS-19``, and it USED to read "any ``OpenProcess``
    failure". ``ERROR_ACCESS_DENIED`` (5) lands on the same failed call and
    means the opposite - the process exists, is running, and this token may not
    ask - so a running process owned by another token read DEAD. Measured with
    ``SeDebugPrivilege`` dropped: 13 pids denied access, all 13 still running
    half a second later, all 13 reported dead by this function. That was a
    fail-OPEN inside a function whose contract promises fail-closed, and the
    contract was the half that was right.

    The three failure branches are written out separately rather than folded
    into one inequality. Each names a fact, and each can be mutated on its own
    to prove the test that covers it is not decoration.

    WHAT RETURNS TRUE, therefore, is every undecided reading: a denied open, an
    open that failed with a code nobody here has characterised, and a handle
    that opens but ``GetProcessTimes`` refuses. An unrecognised code is treated
    as undecided on purpose - there are far more than three possible values,
    only one of them is known to mean "gone", and inferring "gone" from an
    error nobody has read would reclaim a live loop's lock. The cost of the
    other error is a refusal, and :class:`LockBusy` already tells the operator
    that deleting the lock file clears it.
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
        # WHY it failed is the whole question. ``use_last_error=True`` above is
        # what makes this readable: ctypes swaps the thread's error around the
        # call and stashes the real one privately, so this accessor - and not
        # the system's - is the one that answers.
        error = ctypes.get_last_error()
        if error == _ERROR_ACCESS_DENIED:
            # It EXISTS and this token may not ask about it. Undecided, so the
            # answer is alive: refusing to start beats trampling a live loop.
            return True
        if error == _ERROR_INVALID_PARAMETER:  # noqa: SIM103
            # The one code that means no process bears this pid.
            return False
        # Uncharacterised. Fail closed with the rest of them.
        #
        # SIM103 would fold these last two into
        # `return error != _ERROR_INVALID_PARAMETER`, and the suppression is
        # deliberate. Each branch NAMES a fact, and - the part that earns its
        # keep - each can be mutated on its own to show the test covering it is
        # not decoration. Folded, the uncharacterised case and the denied case
        # share one expression and no mutation can separate them. `OPS-18`
        # shipped a branch no test reached; this is the cheap defence.
        return True
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
            # The handle opened, so something is there; fail closed and treat
            # it as alive rather than reclaiming a lock we cannot judge.
            return True
        raw = (exited.dwHighDateTime << 32) | exited.dwLowDateTime
        return raw == _NOT_EXITED
    finally:
        kernel32.CloseHandle(handle)


def pid_is_alive(pid: int | None) -> bool:
    """Return True if ``pid`` currently names a running process.

    Fails closed: when existence cannot be determined, the answer is True, so
    an ambiguous case refuses to start rather than trampling a live loop.

    That promise is delivered rather than merely stated as of ``OPS-19``. It
    was false on Windows for every process this token could not open, which is
    the case the promise most needed to cover - a loop under a scheduled task,
    another user, or an elevated session. See
    :func:`_windows_pid_is_alive` for the codes and the measurement.
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


def owner_of(path: Path | None = None) -> int | _UnreadableOwner | None:
    """Classify the lock file into the three states it can actually be in.

    This is the ``OPS-21`` split. :func:`read_owner` answered ``None`` for a
    missing file and for a corrupt one alike, :func:`pid_is_alive` answers
    False for ``None``, and :func:`acquire` therefore unlinked and retook a
    lock whose contents it had failed to read - a fail-OPEN in the same module
    and the same direction as ``OPS-19``, reached by a different route.

    Returns:
        The recorded pid; ``None`` when there is no lock file at all; and
        :data:`UNREADABLE` when a lock file is THERE and no owner pid can be
        recovered from it.

    ``FileNotFoundError`` is the only ``OSError`` that answers ``None``. Every
    other one - a directory in the lock's place, a permission failure, an I/O
    error - means something IS at that path and this code cannot read it, which
    is the undecided case, not the empty one.

    ``ValueError`` covers two arrivals, and the second is why it is spelled
    that way rather than as ``json.JSONDecodeError``. Invalid JSON is one.
    ``UnicodeDecodeError`` is the other: it is a ``ValueError``, NOT an
    ``OSError``, so a lock file carrying one stray non-UTF-8 byte used to raise
    straight out through :func:`read_owner`, :func:`is_locked` and
    :func:`acquire` rather than returning anything at all. Measured on this
    machine, and it is the fifth fact in an item that named four.

    What is NOT separated here, said plainly rather than left to be discovered:
    a lock recording a readable but impossible pid - ``0`` or a negative - is
    returned as that pid, and :func:`pid_is_alive` calls it dead, so it is
    reclaimed exactly like a crashed loop. That fold is deliberate, because the
    record IS readable and reading it is what this function promises; it is not
    fixed here.
    """
    target = Path(path) if path is not None else default_lock_path()
    try:
        body = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        # The genuinely unheld case, and the normal one on a fresh machine.
        return None
    except (OSError, ValueError):
        # Something is at that path and it cannot be read.
        return UNREADABLE
    try:
        payload = json.loads(body)
    except ValueError:
        # json.JSONDecodeError is a ValueError; naming the base catches a
        # malformed document and nothing else, since body is already str.
        return UNREADABLE
    if not isinstance(payload, dict):
        return UNREADABLE
    pid = payload.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        return UNREADABLE
    return pid


def read_owner(path: Path | None = None) -> int | None:
    """Return the pid recorded in the lock file, or ``None``.

    ``None`` still covers every case that yields no pid - no file, unreadable
    bytes, invalid JSON, a payload that is not an object, a missing or
    non-integer ``pid``. That fold is kept on purpose, because widening this
    return type would have made every caller decide a question most of them do
    not ask. Two in-module callers are left and neither needs the distinction:
    :func:`acquire`'s lost-the-race branch, which reports whatever the winner
    wrote, and :func:`release`, whose ownership test reads ``None`` as "names
    nobody, so anyone may clear it" - the escape hatch, not an oversight. The
    distinction ``OPS-21`` needed lives in :func:`owner_of`, and :func:`is_locked`
    and :func:`acquire`'s refusal path are what read it.

    One behaviour did change here: a lock file that is not valid UTF-8 used to
    raise ``UnicodeDecodeError`` out of this function. It now returns ``None``,
    which is what the sentence above always claimed.
    """
    owner = owner_of(path)
    return owner if isinstance(owner, int) else None


def is_locked(path: Path | None = None) -> bool:
    """Return True if a lock file exists and its owner cannot be ruled out.

    Three states collapse to two here, and which way the middle one falls is
    the point: no file is False, a readable owner is that owner's liveness, and
    a file this code cannot parse is True. Fail-closed, matching
    :func:`pid_is_alive`'s own promise for an undecidable pid.

    The absent case is answered by :func:`owner_of` itself rather than by a
    prior ``exists()`` check, so there is no window in which the file is seen
    and then read as something else.
    """
    owner = owner_of(path)
    if owner is UNREADABLE:
        return True
    return pid_is_alive(owner)


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

    A lock file that exists and cannot be PARSED is a different matter and is
    refused (``OPS-21``). It is not evidence that anybody is gone - the owner
    may be alive and mid-commit, the file simply no longer says so - and
    reclaiming it was a fail-OPEN. The operator's way out is the one
    :class:`LockBusy` already names: delete the file. No force flag is added
    here, because one already exists in :func:`release` and because a flag that
    means "take the lock anyway" is the exact thing this module refuses to
    decide on an unattended loop's behalf.

    Args:
        path: Lock file to take. Defaults to :func:`default_lock_path`.
        pid: Owner pid to record. Defaults to this process.
        label: Free-text note stored in the lock, to make a stray lock file
            self-explanatory to whoever finds it.

    Returns:
        The path of the lock now held.

    Raises:
        LockBusy: The lock is held by a live process, or by an owner record
            this code cannot read. Nothing is terminated in either case, and
            the lock file is left exactly as it was found.
    """
    target = Path(path) if path is not None else default_lock_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    owner_pid = os.getpid() if pid is None else pid

    try:
        _write_lock(target, owner_pid, label)
        return target
    except FileExistsError:
        pass

    existing = owner_of(target)
    if existing is UNREADABLE:
        # Undecidable, so it is not ours to take. Note what this branch does
        # NOT catch: `owner_of` answers None if the file vanished between the
        # failed create above and this read, and that IS free to take - the
        # incumbent released it in the gap. Keying the refusal on "the file is
        # there and I cannot read it" rather than on "no pid came back" is what
        # keeps that benign race working.
        raise LockBusy(target, None)
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

    Unchanged by ``OPS-21``, and load-bearing because of it: the refusal
    :func:`acquire` now raises for an unreadable lock has to be recoverable
    from inside Python, or an unparseable file would be its own denial of
    service. A corrupt lock names nobody, ``read_owner`` answers ``None``, the
    ownership test below passes, and any claimant may clear it without
    ``force``. That is the second way out; deleting the file is the first.
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
