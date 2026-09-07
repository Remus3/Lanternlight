"""A reserved-floor lane governor, re-implemented from an observed protocol.

Several projects share this one machine and one Anthropic account, so their
headless loops contend for the same concurrency budget. The sibling projects
coordinate through a directory of lock files and describe the scheme on the
``moon_sync_inbox/`` channel. The operator ruled on 2026-09-07 that Lanternlight
takes a lane slot in that scheme, with the repository key ``ll``. See
``ROADMAP.md`` items ``OPS-35``, ``OPS-36`` and ``OPS-42``, and
``docs/adr/ADR-007-lane-slot-root-is-ours.md``.

**Re-implemented, never vendored.** No file was copied in and nothing is
imported from a sibling tree. What is deliberately held in common is the WIRE:
the lock namespace shape, the key strings and the payload shape. That is a
protocol fact, not source, and this module is written from the protocol as
reconstructed in the ADR rather than from anyone's file.

The scheme
----------

A bucket directory holds two naming schemes at once, because a reservation
cannot be expressed by index alone::

    <bucket>/reserved-rc.lock     only the repo keyed `rc` may take this
    <bucket>/reserved-lw.lock
    <bucket>/reserved-rsc.lock
    <bucket>/reserved-cs.lock
    <bucket>/reserved-ll.lock     ours
    <bucket>/0.lock               surplus, first-come
    <bucket>/1.lock

:func:`try_acquire` tries its OWN reserved slot first and the surplus second.
The consequence is the guarantee: a repository starved of surplus by a busy
neighbour can still always start one lane, and a busy repository can burst into
the surplus.

Four properties carry the design, and every one of them is a test in
``tests/test_lane_slot.py`` rather than a sentence here:

* A repository can never hold more than one RESERVED slot - its own.
* A repository starved of surplus still gets its floor.
* An unknown repository key is REFUSED, never silently given surplus. A silent
  fallback presents exactly as "busy", which hides the misconfiguration behind
  the symptom it causes.
* Reaping understands BOTH naming schemes. A stale reserved lock that cannot be
  reclaimed costs its owner the floor for the whole stale window, which is the
  orphan bug wearing a new address.

Identity, not path
------------------

The reservation is keyed on the repository KEY - a short, lowercase, stable
token - and never on the filesystem path. A sibling measured the alternative:
its locks carried the full checkout path, and a root rename mid-run would have
abandoned the held reservation and claimed a second one while the first sat
orphaned until the stale arm fired. Two repositories would then have been one
reservation short between them. Keying on identity is the fix we adopt; the
defect is not.

Where the bucket lives
----------------------

Deliberately inside this repository by default, and overridable by the
environment variable named in :data:`ROOT_ENV_VAR`. The reasoning, and what it
costs, is in ADR-007. Nothing here binds a port and nothing here is acquired at
import time.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Held",
    "LaneSlotError",
    "LOCK_SUFFIX",
    "NoSlotAvailable",
    "REPO_KEY",
    "REPO_KEYS",
    "RESERVED_PREFIX",
    "ROOT_ENV_VAR",
    "STALE_SECONDS",
    "SURPLUS_WIDTH",
    "UnknownRepoKey",
    "decode_payload",
    "default_root",
    "encode_payload",
    "hold",
    "holders",
    "is_slot_name",
    "is_stale",
    "reap",
    "release",
    "reserved_name",
    "slot_order",
    "surplus_names",
    "try_acquire",
]

#: This repository's key in the cross-project scheme. Assigned in the round the
#: operator ruled on; short, lowercase, no spaces and no path separators.
REPO_KEY = "ll"

#: The agreed set. A key outside it is a configuration error, not a fallback.
REPO_KEYS: tuple[str, ...] = ("rc", "lw", "rsc", "cs", "ll")

RESERVED_PREFIX = "reserved-"
LOCK_SUFFIX = ".lock"

#: Surplus width - the free-for-all slots above the five reserved floors.
SURPLUS_WIDTH = 2

#: The stale arm, in seconds. Four and a half hours, matching the window the
#: siblings' governor uses, so a lock this repository leaves behind is reclaimed
#: on the same schedule a sibling would apply to it.
STALE_SECONDS = 16200.0

#: Set this to point the governor at a different bucket - for example a shared
#: machine-wide one, if the operator ever rules that this repository should join
#: one. Changing buckets is a configuration act, never a code change.
ROOT_ENV_VAR = "LL_LANE_SLOT_ROOT"

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: Relative to the repository root. ``ops/runtime/`` is gitignored, so the
#: bucket never reaches a commit.
_DEFAULT_RELATIVE = Path("ops") / "runtime" / "lane_slots"

_STILL_ACTIVE = 259

#: Windows access right that is enough to ask whether a process exists without
#: acquiring any right to affect it. Declared at MODULE scope, and under this
#: exact name, because the roster-wide access-mask check resolves it on the
#: module object: a function-local copy shadows the call site while the module
#: attribute still reads 0x1000, which is a hole that check exists to close.
#: ``ops/loop/guard.py`` and ``ops/loop/watch.py`` spell the same constant out
#: for themselves - it is a Windows API number rather than a derivation, so
#: there is nothing to keep in sync and nothing to import.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: ``GetLastError`` after a failed ``OpenProcess``. 87 is
#: ``ERROR_INVALID_PARAMETER``, which is what Windows returns when no process
#: bears the pid at all. Every other code - access denied, most of all - says
#: nothing about whether the process is there.
_ERROR_INVALID_PARAMETER = 87


class LaneSlotError(Exception):
    """Base for every error this module raises deliberately."""


class UnknownRepoKey(LaneSlotError):
    """The caller's repository key is not in the agreed set.

    Raised rather than falling back to surplus. A silent fallback is
    indistinguishable from a busy bucket, so the misconfiguration would present
    as contention and be debugged as contention.
    """


class NoSlotAvailable(LaneSlotError):
    """Every slot this repository may take is held. Not raised by default."""


@dataclass(frozen=True)
class Held:
    """One acquired slot.

    ``reserved`` distinguishes the floor from a surplus lane, because "did I get
    my guarantee or did I get lucky" is the question an operator asks when the
    machine is busy.
    """

    path: Path
    name: str
    key: str
    reserved: bool


def default_root() -> Path:
    """The bucket this repository uses, resolved but NOT created.

    Creating it here would make merely importing something that reads the
    default enough to materialise a bucket, which is the import-time side effect
    this module refuses to have.
    """
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return Path(override)
    return _REPO_ROOT / _DEFAULT_RELATIVE


def reserved_name(key: str) -> str:
    """The reserved lock filename for ``key``."""
    return f"{RESERVED_PREFIX}{key}{LOCK_SUFFIX}"


def surplus_names(width: int) -> tuple[str, ...]:
    """The surplus lock filenames, zero-based and in try order."""
    return tuple(f"{index}{LOCK_SUFFIX}" for index in range(max(0, int(width))))


def slot_order(key: str, surplus: int = SURPLUS_WIDTH) -> tuple[str, ...]:
    """Slot names in the order this repository may try them.

    Own floor first. No other repository's reserved name ever appears.
    """
    _require_known_key(key)
    return (reserved_name(key), *surplus_names(surplus))


def is_slot_name(name: str) -> bool:
    """True for a filename this scheme owns, in either naming scheme.

    Deliberately narrow: a stray file in the bucket is left alone, because a
    reaper that deletes what it does not recognise is a reaper that eventually
    deletes someone's notes.
    """
    if not name.endswith(LOCK_SUFFIX):
        return False
    stem = name[: -len(LOCK_SUFFIX)]
    if stem.startswith(RESERVED_PREFIX):
        return stem[len(RESERVED_PREFIX) :] in REPO_KEYS
    return stem.isdigit()


def encode_payload(*, pid: int, repo: str, run_id: str, cycle: int, ts: float | None = None) -> str:
    """Serialise the shared payload.

    The five fields are the wire. ``repo`` is a free-form label for a human
    reading the bucket - it is NOT what the reservation keys on, and writing a
    path there does not move anyone's slot.
    """
    body = {
        "pid": int(pid),
        "ts": float(time.time() if ts is None else ts),
        "repo": str(repo),
        "run_id": str(run_id),
        "cycle": int(cycle),
    }
    return json.dumps(body, sort_keys=True)


def decode_payload(text: str) -> dict | None:
    """Parse a payload, or ``None`` if it is not one.

    ``None`` means unreadable, which callers treat as stale. A lock nobody can
    read is a lock nobody can account for.
    """
    try:
        body = json.loads(text)
    except (ValueError, TypeError):
        return None
    return body if isinstance(body, dict) else None


def _read_payload(path: Path) -> dict | None:
    """Read one lock WITHOUT leaving a handle that blocks its owner's unlink.

    Windows refuses ``unlink`` while any handle is open without
    ``FILE_SHARE_DELETE``, and a reader is exactly what a waiter is. The read is
    therefore opened and closed inside this function and nowhere else, and every
    failure answers ``None`` rather than propagating - an unreadable lock is
    stale, not fatal.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, ValueError):
        return None
    return decode_payload(text)


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness.

    Fails toward ALIVE. A wrong "dead" answer reaps a running session's lane and
    lets a second holder in; a wrong "alive" answer only delays the reclaim
    until the stale arm fires. The costs are not symmetric, so neither is this.

    ``os.kill(pid, 0)`` is NOT portable here: on Windows CPython routes any
    signal other than the two console events to ``TerminateProcess``, so the
    liveness probe would kill the process it is asking about.

    ``restype`` and ``argtypes`` are declared on every entry point, matching
    ``ops/loop/guard.py`` and ``ops/loop/watch.py``, and the reason is measured
    rather than stylistic. A ctypes function with no ``restype`` defaults to
    ``c_int``, so a 64-bit ``HANDLE`` comes back truncated to a signed 32-bit
    value: measured on this machine 2026-09-07, the same kernel32 handle
    answered ``GetModuleHandleW`` with ``-323551232`` under the default and
    with ``0x7ff6ecb70000`` under an explicit ``restype``, and
    ``GetCurrentProcess`` answered ``-1`` rather than
    ``0xffffffffffffffff``. Handle VALUES on this box are currently small
    enough that ``OpenProcess`` was returning an intact number anyway - 388
    under both spellings in the same run - so the defect was latent, not
    visible, and the ``CloseHandle`` that follows would have been handed a
    truncated handle the day it stopped being.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:  # pragma: no cover - ctypes is always present here
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means no such process. Anything else
            # (access denied, for instance) is not evidence of death.
            return ctypes.get_last_error() != _ERROR_INVALID_PARAMETER
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def is_stale(payload: Mapping | None, *, now: float | None = None, pid_alive=None) -> bool:
    """Whether a lock may be reclaimed.

    Two arms, and a missing field fires them rather than suppressing them:

    * no readable payload, or no usable ``ts``, is stale - an absent timestamp
      is absent, never "now";
    * a ``ts`` older than :data:`STALE_SECONDS` is stale;
    * otherwise a dead ``pid`` is stale.

    The pid arm is deliberately the LAST one consulted and the weakest. A
    long-lived controller that runs many cycles under one pid keeps that pid
    alive across a leak, so the pid arm answers "not stale" for exactly the
    orphan it was meant to catch. The ts arm is what actually reclaims those.
    """
    if not isinstance(payload, Mapping):
        return True
    raw_ts = payload.get("ts")
    if not isinstance(raw_ts, (int, float)) or isinstance(raw_ts, bool):
        return True
    reference = time.time() if now is None else now
    if reference - float(raw_ts) > STALE_SECONDS:
        return True
    raw_pid = payload.get("pid")
    if not isinstance(raw_pid, int) or isinstance(raw_pid, bool):
        return True
    alive = _pid_alive if pid_alive is None else pid_alive
    return not alive(raw_pid)


def holders(root: Path | str) -> dict[str, dict]:
    """Every readable lock in the bucket, keyed by filename.

    Read-only, and an absent bucket answers ``{}`` rather than raising - a
    session that is not contending must never be blocked by the governor, and
    must not create the namespace merely by looking at it.
    """
    bucket = Path(root)
    report: dict[str, dict] = {}
    try:
        entries = sorted(bucket.iterdir())
    except OSError:
        return report
    for entry in entries:
        if not is_slot_name(entry.name):
            continue
        payload = _read_payload(entry)
        if payload is not None:
            report[entry.name] = payload
    return report


def reap(root: Path | str, *, now: float | None = None, pid_alive=None) -> list[str]:
    """Remove stale locks in BOTH naming schemes. Returns the names removed.

    A reaper that knows only ``0.lock``-style names leaves a stale
    ``reserved-<key>.lock`` in place, and its owner loses the floor the whole
    design exists to guarantee. That is the orphan bug at a new address, and it
    is harder to see there, because a missing reservation reads as a policy
    decision rather than as a leak.
    """
    bucket = Path(root)
    removed: list[str] = []
    try:
        entries = sorted(bucket.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if not is_slot_name(entry.name):
            continue
        payload = _read_payload(entry)
        if not is_stale(payload, now=now, pid_alive=pid_alive):
            continue
        try:
            entry.unlink()
        except OSError:
            continue
        removed.append(entry.name)
    return removed


def _require_known_key(key: str) -> None:
    if key not in REPO_KEYS:
        raise UnknownRepoKey(
            f"repository key {key!r} is not in the agreed set "
            f"{', '.join(REPO_KEYS)} - refusing to start rather than falling "
            "back to a surplus slot, because a silent fallback presents as a "
            "busy bucket and gets debugged as one. Keys are short, lowercase, "
            "and are never a filesystem path."
        )


def _claim(path: Path, payload: str) -> bool:
    """Create one lock atomically. False means somebody else holds it."""
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
    except OSError:
        with contextlib.suppress(OSError):
            path.unlink()
        return False
    return True


def try_acquire(
    root: Path | str,
    key: str = REPO_KEY,
    *,
    repo: str,
    run_id: str,
    cycle: int,
    surplus: int = SURPLUS_WIDTH,
) -> Held | None:
    """Take a lane if one is available. Never blocks; ``None`` means busy.

    Order is own floor, then surplus. The key is validated BEFORE the bucket is
    created, so a misconfigured caller leaves no trace behind.
    """
    _require_known_key(key)
    bucket = Path(root)
    try:
        bucket.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    payload = encode_payload(pid=os.getpid(), repo=repo, run_id=run_id, cycle=cycle)
    for name in slot_order(key, surplus):
        path = bucket / name
        if _claim(path, payload):
            return Held(
                path=path,
                name=name,
                key=key,
                reserved=name == reserved_name(key),
            )
    return None


def _neutralise(path: Path) -> None:
    """Rewrite an undeletable lock so the stale arm fires immediately.

    The direct answer to the orphan a live pid protects: if the lock cannot be
    removed, at least stop it claiming to be fresh. Written non-atomically on
    purpose - the file already exists and a replace would need the unlink that
    just failed.
    """
    body = encode_payload(
        pid=0,
        repo="neutralised",
        run_id="neutralised",
        cycle=0,
        ts=time.time() - (STALE_SECONDS * 2),
    )
    with contextlib.suppress(OSError), path.open("w", encoding="utf-8") as handle:
        handle.write(body)


def release(held: Held, *, retries: int = 5, backoff: float = 0.05, log=None) -> bool:
    """Release a slot. Returns whether the lock is actually gone.

    Three things this does NOT do, each because a sibling measured the cost:

    * it does not report success unconditionally - a release logged outside the
      failing branch makes an ACQUIRED/RELEASED pairing analysis read perfectly
      clean while a lane is stuck;
    * it does not give up on the first ``PermissionError`` - a concurrent
      reader's handle lives for microseconds, so a short bounded retry clears
      the common case;
    * it does not leave an undeletable lock claiming to be fresh.
    """
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        try:
            held.path.unlink()
        except FileNotFoundError:
            if log is not None:
                log(f"lane slot released (already gone): {held.name}")
            return True
        except OSError:
            if attempt + 1 < attempts and backoff > 0:
                time.sleep(backoff)
            continue
        else:
            if log is not None:
                log(f"lane slot released: {held.name}")
            return True
    _neutralise(held.path)
    if log is not None:
        log(
            f"WARNING lane slot {held.name} could not be removed and was "
            "neutralised so it reaps immediately"
        )
    return False


@contextlib.contextmanager
def hold(
    root: Path | str,
    key: str = REPO_KEY,
    *,
    repo: str,
    run_id: str,
    cycle: int,
    surplus: int = SURPLUS_WIDTH,
    log=None,
) -> Iterator[Held | None]:
    """Hold a lane for the duration of the block, or yield ``None`` if busy.

    Yielding ``None`` rather than raising or waiting is deliberate: the caller
    decides what a busy machine means for it, and a governor that blocks by
    default turns a coordination miss into a hang.
    """
    held = try_acquire(
        root, key, repo=repo, run_id=run_id, cycle=cycle, surplus=surplus
    )
    try:
        yield held
    finally:
        if held is not None:
            release(held, log=log)
