"""Snapshot every changed generation of every file in a game save directory.

MEASURED PROBLEM, 2026-08-09: one save file the game writes,
``StandaloneSlot_<roleId>.sav``, is TRANSIENT. A stopgap poller
(``arm_save_snapshot.py``, session scratchpad) watched it appear at 2,190
bytes and grow through 33,610 / 35,062 / 36,514 / 41,133 / 43,801 / 44,517
bytes over roughly 70 seconds - then the game deletes the file entirely,
about 13 minutes after it first appears. A previous session lost the file
outright because no watcher was armed in advance.

A watcher that copies only on first sight captures a truncated file the
moment the source is still being written. This module instead copies EVERY
observed generation - identity is ``(name, size, mtime_ns)`` - so a caller
never has to guess whether the copy it has is the final one; the size is
embedded in the snapshot's own filename.

Two things this module refuses to do, both load-bearing:

1. It never writes to, deletes from, or otherwise modifies the source
   directory. Every operation against ``source_dir`` is read-only:
   ``iterdir()``, ``stat()``, and the read side of ``shutil.copy2``.
2. It refuses to construct a watcher whose destination sits inside a git
   working directory, mechanically, in ``__init__`` - not as a documented
   convention someone has to remember. Save files carry the operator's
   roleId in their filename and platform identifiers in their bytes; see
   the PII HAZARD block in ``.gitignore``. ``is_inside_repo_working_directory``
   walks up from the destination looking for a ``.git`` entry, which is a
   file in a linked worktree and a directory in the primary checkout - both
   are checked, and neither requires the ``git`` executable to be on PATH.

The API deliberately separates one deterministic pass (:meth:`SaveWatcher.
poll_once`, which a test can call directly with an injected timestamp) from
the looping wrapper (:meth:`SaveWatcher.run`, which takes an injectable sleep
function so a caller - including a test - never has to block on a real poll
interval).
"""

from __future__ import annotations

import contextlib
import shutil
import stat as stat_module
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__all__ = [
    "DestinationInsideRepoError",
    "SaveWatcher",
    "Snapshot",
    "is_inside_repo_working_directory",
]

#: The marker git leaves at the root of every working directory it manages -
#: a directory in the primary checkout, a file (``gitdir: <path>``) in a
#: linked worktree. Checking for its mere existence covers both shapes
#: without needing to tell them apart.
_GIT_MARKER_NAME = ".git"


class DestinationInsideRepoError(ValueError):
    """Raised when a snapshot destination sits inside a git working directory.

    This is the refusal that keeps operator PII - SteamID64, Steam persona,
    platform ids, a roleId - out of anything that could end up committed or
    pushed. See the PII HAZARD block in ``.gitignore``.
    """


@dataclass(frozen=True)
class Snapshot:
    """One captured generation of one source file.

    ``size`` and ``mtime_ns`` are the values observed at capture time, copied
    verbatim from :func:`os.stat` on the source - not re-derived from the
    destination, so a snapshot always testifies to what was actually seen.
    """

    source: Path
    destination: Path
    size: int
    mtime_ns: int


def is_inside_repo_working_directory(path: Path | str) -> bool:
    """True if ``path`` is at or under a directory containing a git marker.

    Walks upward from ``path`` (which need not exist) checking for a
    ``.git`` entry at every ancestor, all the way to the filesystem root.
    No subprocess, no dependency on ``git`` being installed or on PATH - a
    machine with a corrupted or missing git install must still refuse the
    write, since the hazard being guarded against (operator PII landing in a
    working directory that might later be committed) does not depend on git
    being functional right now.
    """
    resolved = Path(path).resolve()
    return any(
        (ancestor / _GIT_MARKER_NAME).exists() for ancestor in (resolved, *resolved.parents)
    )


def _stamp(when: datetime) -> str:
    """Format a local timestamp for a snapshot filename.

    Second resolution, matching the stopgap this module replaces. The
    generations actually measured (see module docstring) were roughly ten
    seconds apart at the closest, so a same-second collision for the same
    file has never been observed; the size embedded alongside the timestamp
    disambiguates even if one ever did.
    """
    return when.strftime("%Y%m%d-%H%M%S")


def _entry_identity(path: Path) -> tuple[str, int, int] | None:
    """Return ``(name, size, mtime_ns)`` for a regular file, or ``None``.

    ``None`` covers both "not a regular file" (directories, junk) and "could
    not be stat'd at all" - which on this machine mostly means the entry
    vanished between being listed by ``iterdir()`` and being examined here.
    That is the NORMAL case for ``StandaloneSlot_<roleId>.sav``, which
    deletes itself, so this is not an edge case to merely tolerate - it is
    the expected shape of a successful capture near the end of the file's
    life.
    """
    try:
        st = path.stat()
    except OSError:
        return None
    if not stat_module.S_ISREG(st.st_mode):
        return None
    return (path.name, st.st_size, st.st_mtime_ns)


class SaveWatcher:
    """Watches ``source_dir``, copying every changed generation into ``dest_dir``.

    Construction is where the destination is validated - see
    :func:`is_inside_repo_working_directory` - so a misconfigured caller
    fails immediately rather than on the first file it happens to see.

    ``source_dir`` is never validated at construction time: the game may not
    be installed or running, and surviving an absent or unreadable source is
    about ``poll_once`` tolerating that at call time, not about refusing to
    even build a watcher for a directory that does not exist yet.
    """

    def __init__(self, source_dir: Path | str, dest_dir: Path | str) -> None:
        dest_resolved = Path(dest_dir).resolve()
        if is_inside_repo_working_directory(dest_resolved):
            raise DestinationInsideRepoError(
                f"refusing to snapshot into {dest_resolved} - it sits inside a "
                "git working directory. Save files carry the operator's "
                "roleId and platform identifiers; see the PII HAZARD block in "
                ".gitignore. Point dest_dir somewhere outside every checkout, "
                "e.g. C:\\ll-captures\\saves."
            )
        self.source_dir = Path(source_dir)
        self.dest_dir = dest_resolved
        self._seen: set[tuple[str, int, int]] = set()

    def poll_once(self, *, now: datetime | None = None) -> list[Snapshot]:
        """Do exactly one listing-and-copy pass. Never raises.

        Returns the snapshots taken during THIS pass only (not a running
        total). An absent or unreadable ``source_dir``, or a file that
        vanishes between being listed and being copied, both result in that
        entry being silently skipped rather than the pass failing - see the
        module docstring for why that is the expected case here, not a rare
        one.

        ``now`` is accepted so a caller (chiefly a test) can pin the
        timestamp embedded in snapshot filenames instead of depending on
        wall-clock time; production callers can leave it as ``None``.
        """
        when = datetime.now() if now is None else now
        taken: list[Snapshot] = []

        try:
            entries = sorted(self.source_dir.iterdir())
        except OSError:
            # Covers: source_dir does not exist, is not a directory (the
            # portable stand-in for "unreadable" - a NotADirectoryError has
            # the same shape as a PermissionError here), or a real
            # PermissionError from a locked-down ACL.
            return taken

        for src in entries:
            ident = _entry_identity(src)
            if ident is None:
                continue
            if ident in self._seen:
                continue
            name, size, mtime_ns = ident
            snap = self._copy_one(src, name=name, size=size, mtime_ns=mtime_ns, when=when)
            if snap is not None:
                self._seen.add(ident)
                taken.append(snap)

        return taken

    def _copy_one(
        self, src: Path, *, name: str, size: int, mtime_ns: int, when: datetime
    ) -> Snapshot | None:
        """Copy one file into ``dest_dir``, atomically, or return ``None``.

        ``None`` means the copy did not complete - normally because ``src``
        vanished between being stat'd (in :func:`_entry_identity`) and being
        opened here. That identity is deliberately NOT recorded as "seen" in
        this case, so a transient failure gets retried on the next pass
        rather than being silently given up on forever.
        """
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        target = self.dest_dir / f"{_stamp(when)}_{size}_{name}"
        tmp_target = self.dest_dir / f"{target.name}.part"
        try:
            shutil.copy2(src, tmp_target)
        except OSError:
            with contextlib.suppress(OSError):
                tmp_target.unlink(missing_ok=True)
            return None
        tmp_target.replace(target)
        return Snapshot(source=src, destination=target, size=size, mtime_ns=mtime_ns)

    def run(
        self,
        *,
        poll_seconds: float = 3.0,
        max_passes: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> int:
        """Call :meth:`poll_once` repeatedly, sleeping ``poll_seconds`` between passes.

        ``max_passes=None`` loops until interrupted (the production shape).
        A finite ``max_passes`` exists so a caller - and every test in this
        module - can bound the loop deterministically without monkeypatching
        ``time.sleep``; ``sleep_fn`` is the injection point that makes that
        possible. Sleeps happen BETWEEN passes only, never after the last
        one, so a bounded run does not block on a trailing, pointless sleep.

        Returns the total number of snapshots taken across every pass.
        """
        total = 0
        passes = 0
        while max_passes is None or passes < max_passes:
            total += len(self.poll_once())
            passes += 1
            if max_passes is not None and passes >= max_passes:
                break
            sleep_fn(poll_seconds)
        return total
