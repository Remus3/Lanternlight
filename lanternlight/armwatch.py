"""Arm every session watcher from one entry point.

ROADMAP item 4c. This module adds **no copying**. ``lanternlight.savewatch``
already does all of it - copy every changed generation, never write to the
source, refuse a destination inside a git working directory - and the one
thing missing was that arming it was something each session had to REMEMBER.

Two losses came out of exactly that, and both are the reason this file exists
rather than a note in a hand-off:

- The **6.1 MB log of 2026-08-09 is gone.** The game empties
  ``MistfallHunter.log`` on launch. Measured across ONE launch, 2026-08-25:
  afterwards the live log still carried its original ``2026-08-09 08:18:56``
  creation time, so that launch emptied the file that was already there rather
  than making a new one. **One launch, watched once** - nothing here shows the
  timestamp survived any earlier launch, and on NTFS a delete-and-recreate
  inside about 15 seconds restores the original creation time anyway, so this
  evidence does not separate truncate-in-place from delete-and-recreate. See
  ``docs/FINDINGS.md`` 11.12.
- The **market cache emptied itself unobserved.** ``AvgPrice_<id>.ini`` had
  filled to 343 bytes and was back to its empty 37-byte state with nothing
  watching the transition.

MEASURED 2026-08-25, and it is why the plan watches DIRECTORIES rather than
files: the launch at 21:28:59 local left
``MistfallHunter-backup-2026.08.26-01.27.09.log`` beside the live log, created
at the instant of launch and byte-identical (sha256 ``1c44235c...``) to the
previous run's final 5,080,313-byte log. So a launch **copies before it
truncates**. That backup is NOT guaranteed - across 23 listings of ``Logs/``
during the previous session no backup file existed at all, and what decides it
is unmeasured - so it is a windfall to be captured, never a reason to skip
archiving. Watching the directory captures it for free; watching the log file
alone would walk straight past it.

Every interval below is chosen against an observed trigger and carries that
observation in its ``rationale``, because a number with no argument behind it
is what this project calls a confident guess.

ROADMAP item 4d - the dated root has to roll over
-------------------------------------------------

A destination named for a day has to BE that day. Arming on 2026-08-31 with a
literal ``--dest-root C:/ll-captures/2026-08-31`` keeps writing into
``2026-08-31/`` after midnight, so the directory claims to cover a day it does
not - and a MISLABELLED ARCHIVE IS WORSE THAN AN ABSENT ONE, because it gets
believed. ``--dest-base`` derives the dated root from the clock on every pass
instead, so a watcher left running past midnight begins writing into the new
day on its own.

STATED COST, and the reason a rollover RETARGETS a watcher instead of building
a fresh one: a :class:`~lanternlight.savewatch.SaveWatcher` remembers the
``(name, size, mtime_ns)`` identities it has already captured, and a new
instance forgets them. Forgetting would re-copy every unchanged file into
every new dated directory. MEASURED 2026-09-01, the live ``Saved/Logs/`` holds
3 files totalling 10,316,212 bytes (9.84 MB), so that is 10,316,212 bytes of
pure duplication per day - 3,765,417,380 bytes a year, roughly 45x the
80.12 MB across 115 files that the watchers have produced in total to date,
with OPS-14 (disk pressure) open. An unchanged 5 MB log is not a new fact just
because midnight passed. Keeping the instance and moving its destination
preserves savewatch's real contract - every CHANGED generation captured
exactly once - and lets a dated directory honestly answer "what was captured
on this day".

The caveat that buys, written down rather than left implied: a dated directory
then holds what CHANGED that day, not everything that existed that day. A day
whose sources never changed is empty or absent entirely, and reconstructing
the full state of a surface on such a day means reading back to the earlier
directory that last captured it.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lanternlight import paths
from lanternlight.savewatch import DestinationInsideRepoError, SaveWatcher

__all__ = [
    "DEST_DATE_FORMAT",
    "WatchPlan",
    "arm",
    "dated_dest_root",
    "main",
    "run",
    "run_rolling",
    "session_plan",
]

#: Subdirectories of ``Saved/`` that carry something worth keeping. The
#: ``Saved/`` root itself is watched separately - see :func:`session_plan`.
LOGS_DIR_NAME = "Logs"
SAVE_GAMES_DIR_NAME = "SaveGames"
STANDALONE_LEVEL_DIR_NAME = "StandaloneLevel"

#: Poll intervals, seconds. Each one is argued in the matching rationale in
#: :func:`session_plan`; none of them is a round number chosen for looking
#: tidy.
MATCH_LIFETIME_POLL_S = 3.0
SAVED_ROOT_POLL_S = 30.0
LOG_POLL_S = 300.0

#: How a dated destination directory is named. ``%Y-%m-%d`` is the one common
#: date format whose lexical order and chronological order agree, so a plain
#: directory listing is already in session order, and it is what the capture
#: tree on this machine is named in.
DEST_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class WatchPlan:
    """One source directory, where its snapshots go, and how often to look.

    ``rationale`` is a field rather than a comment on purpose. The acceptance
    for ROADMAP 4c asks for intervals "chosen against measured triggers rather
    than guessed", and a comment drifts away from the number it explains while
    a field travels with it.
    """

    name: str
    source: Path
    dest: Path
    poll_seconds: float
    rationale: str


def session_plan(
    saved_dir: Path | str | None = None,
    dest_root: Path | str | None = None,
) -> tuple[WatchPlan, ...]:
    """Build the four-surface plan for one session.

    ``saved_dir`` defaults to the resolved live ``Saved/`` directory and
    ``dest_root`` has no default - a caller naming a destination is the point
    at which the guard in :class:`SaveWatcher` gets something to check.

    Nothing here touches the filesystem. The plan is data, so a test can
    assert against it without the game being installed.
    """
    saved = Path(paths.saved_dir()) if saved_dir is None else Path(saved_dir)
    if dest_root is None:
        raise ValueError("dest_root is required - see the PII HAZARD block in .gitignore")
    dest = Path(dest_root)

    return (
        WatchPlan(
            name="savegames",
            source=saved / SAVE_GAMES_DIR_NAME,
            dest=dest / "savegames",
            poll_seconds=MATCH_LIFETIME_POLL_S,
            rationale=(
                "StandaloneSlot_<roleId>.sav appears 17 s after EnterBattle, grows "
                "through at least 7 generations in about 70 s (2190 -> 44517 bytes), "
                "and the game deletes it roughly 13 minutes later. Sampling that "
                "slower than a few seconds records a handful of frames of a file "
                "that only exists once per run."
            ),
        ),
        WatchPlan(
            name="standalonelevel",
            source=saved / STANDALONE_LEVEL_DIR_NAME,
            dest=dest / "standalonelevel",
            poll_seconds=MATCH_LIFETIME_POLL_S,
            rationale=(
                "Shares the match lifecycle with the transient save, so it shares "
                "its 3 s cadence. Measured empty for the whole 36-minute training "
                "ground session of 2026-08-25, which is a result only because "
                "something was looking."
            ),
        ),
        WatchPlan(
            name="savedroot",
            source=saved,
            dest=dest / "savedroot",
            poll_seconds=SAVED_ROOT_POLL_S,
            rationale=(
                "AvgPrice_<id>.ini is a top-level file in Saved/, not in any "
                "subdirectory. It had filled to 343 bytes and was found back at its "
                "empty 37-byte state with nothing watching the transition, so the "
                "interval only has to be short enough to catch a state change, not "
                "to track growth."
            ),
        ),
        WatchPlan(
            name="logs",
            source=saved / LOGS_DIR_NAME,
            dest=dest / "logs",
            poll_seconds=LOG_POLL_S,
            rationale=(
                "The log reached 5,080,313 bytes in one session, so a 3 s cadence "
                "would copy gigabytes of mostly-identical prefix. A 300 s cadence "
                "took 23 generations across the 2026-08-25 session. The DIRECTORY "
                "is watched rather than the file so that a launch's "
                "MistfallHunter-backup-<UTC>.log is captured too."
            ),
        ),
    )


def dated_dest_root(dest_base: Path | str, *, now: datetime | None = None) -> Path:
    """Return ``dest_base`` with a local date appended, derived on every call.

    Never cached - a day computed once and reused is precisely the defect
    ROADMAP 4d exists to fix, so there is nowhere for a stale day to hide.

    The clock is the LOCAL one. Snapshot filenames are already stamped local
    by ``savewatch._stamp`` and the capture tree on this machine is named in
    local dates; this machine sits at UTC-5, so reading UTC here would file
    the last five hours of every local day under tomorrow.

    ``now`` is the injection point that lets a caller - chiefly a test - cross
    midnight without waiting for one.
    """
    when = datetime.now() if now is None else now
    return Path(dest_base) / when.strftime(DEST_DATE_FORMAT)


def arm(plans: Sequence[WatchPlan]) -> list[SaveWatcher]:
    """Construct one :class:`SaveWatcher` per plan, or refuse the whole set.

    Every watcher is built before any of them is returned, so a bad
    destination anywhere in the plan raises
    :class:`~lanternlight.savewatch.DestinationInsideRepoError` before a
    single directory has been created. Construction never touches the
    filesystem, which is what makes that all-or-nothing property free.
    """
    return [SaveWatcher(plan.source, plan.dest) for plan in plans]


def run(
    plans: Sequence[WatchPlan],
    *,
    max_passes: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    log_fn: Callable[[str], None] | None = None,
) -> list[SaveWatcher]:
    """Arm ``plans`` and poll them.

    ``max_passes=None`` is the production shape: one daemon thread per plan,
    each polling at its own interval, and this call blocks until interrupted.
    A finite ``max_passes`` runs every plan that many passes synchronously
    with no sleeping, which is how a test drives this without threads or
    wall-clock time.

    Returns the armed watchers so a caller can inspect what it got.
    """
    watchers = arm(plans)
    say = log_fn if log_fn is not None else (lambda message: print(message, flush=True))

    for plan in plans:
        say(f"armed {plan.name}: {plan.source} -> {plan.dest} every {plan.poll_seconds:g}s")

    if max_passes is not None:
        for plan, watcher in zip(plans, watchers, strict=True):
            watcher.run(
                poll_seconds=plan.poll_seconds,
                max_passes=max_passes,
                sleep_fn=lambda _seconds: None,
            )
        return watchers

    threads = [
        threading.Thread(
            target=watcher.run,
            kwargs={"poll_seconds": plan.poll_seconds, "sleep_fn": sleep_fn},
            name=f"armwatch-{plan.name}",
            daemon=True,
        )
        for plan, watcher in zip(plans, watchers, strict=True)
    ]
    for thread in threads:
        thread.start()
    say("watching - interrupt to stop")
    try:
        while True:
            sleep_fn(60.0)
    except KeyboardInterrupt:
        say("stopped")
    return watchers


class _RollingSurface:
    """One surface's watcher, RETARGETED when the local day rolls over.

    The watcher INSTANCE survives the rollover on purpose - see the STATED
    COST in the module docstring. Each surface also carries its own day and
    its own watcher rather than sharing one set of state, so the threaded
    shape needs no lock and a snapshot always lands in the directory named for
    the clock reading that produced it, not for whichever day some other
    thread happened to observe first.
    """

    def __init__(
        self,
        name: str,
        saved_dir: Path | str | None,
        dest_base: Path | str,
        *,
        now: datetime,
    ) -> None:
        self._name = name
        self._saved_dir = saved_dir
        self._dest_base = Path(dest_base)
        self.plan = self._plan_for(now)
        self.watcher = SaveWatcher(self.plan.source, self.plan.dest)
        self.day = now.strftime(DEST_DATE_FORMAT)

    def _plan_for(self, now: datetime) -> WatchPlan:
        """This surface's plan against the dated root for ``now``.

        Routed through :func:`session_plan` rather than reconstructing the
        layout here, so the mapping from surface to subdirectory has exactly
        one definition and a renamed surface fails loudly with a ``KeyError``
        instead of quietly archiving into a new directory nobody expected.
        """
        root = dated_dest_root(self._dest_base, now=now)
        return {plan.name: plan for plan in session_plan(self._saved_dir, root)}[self._name]

    def retarget(self, now: datetime) -> bool:
        """Adopt the dated root for ``now``. True when the day actually changed.

        The destination guard is re-run here, never skipped. Constructing a
        ``SaveWatcher`` is the ONLY sanctioned place that check lives, so a
        throwaway one is built purely to run it rather than re-implementing
        the check here where it could drift out of step with ``savewatch``.
        Construction touches no filesystem, so the throwaway costs nothing and
        leaves nothing behind. If it refuses, this surface keeps the
        destination it already had and the refusal propagates: a capture base
        that has acquired a git checkout is a reason to stop, not a reason to
        write roleId-bearing save files into it.
        """
        day = now.strftime(DEST_DATE_FORMAT)
        if day == self.day:
            return False
        plan = self._plan_for(now)
        self.watcher.dest_dir = SaveWatcher(plan.source, plan.dest).dest_dir
        self.plan = plan
        self.day = day
        return True


def _arm_rolling(
    saved_dir: Path | str | None,
    dest_base: Path | str,
    *,
    now: datetime,
) -> list[_RollingSurface]:
    """Build one rolling surface per plan, EAGERLY, or refuse the whole set.

    Eager on purpose. Deferring construction to the first poll would move the
    destination refusal from arm time to poll time - the same guard, fired
    after the operator has gone back to the game instead of while they are
    still watching the console. ``SaveWatcher.__init__`` touches no
    filesystem, so a refusal partway through this list still leaves nothing
    created.
    """
    plans = session_plan(saved_dir, dated_dest_root(dest_base, now=now))
    return [_RollingSurface(plan.name, saved_dir, dest_base, now=now) for plan in plans]


def run_rolling(
    saved_dir: Path | str | None,
    dest_base: Path | str,
    *,
    max_passes: int | None = None,
    now_fn: Callable[[], datetime] = datetime.now,
    sleep_fn: Callable[[float], None] = time.sleep,
    log_fn: Callable[[str], None] | None = None,
) -> list[SaveWatcher]:
    """Arm the session under ``dest_base`` and keep the dated root current.

    Every pass derives the day from ``now_fn()``. When it differs from the day
    a surface is using, that surface is retargeted at the new dated root - not
    rebuilt - and polling continues.

    ``max_passes=None`` is the production shape: one daemon thread per
    surface, each polling at its own interval, blocking until interrupted. A
    finite ``max_passes`` runs every surface that many passes synchronously,
    with no threads and no sleeping, which is how a test drives a midnight
    crossing in no wall-clock time. ``max_passes=0`` arms and polls nothing,
    which is how a test asks whether the refusal really happens at arm time
    rather than on the first poll.

    Returns the armed watchers so a caller can inspect what it got.
    """
    surfaces = _arm_rolling(saved_dir, dest_base, now=now_fn())
    say = log_fn if log_fn is not None else (lambda message: print(message, flush=True))

    for surface in surfaces:
        plan = surface.plan
        say(f"armed {plan.name}: {plan.source} -> {plan.dest} every {plan.poll_seconds:g}s")

    if max_passes is not None:
        for _ in range(max_passes):
            now = now_fn()
            for surface in surfaces:
                if surface.retarget(now):
                    say(f"rolled {surface.plan.name} over to {surface.plan.dest}")
                surface.watcher.poll_once(now=now)
        return [surface.watcher for surface in surfaces]

    def poll_forever(surface: _RollingSurface) -> None:
        while True:
            now = now_fn()
            try:
                if surface.retarget(now):
                    say(f"rolled {surface.plan.name} over to {surface.plan.dest}")
            except DestinationInsideRepoError as exc:
                # A thread that dies silently takes a whole surface's archive
                # with it and nothing on the console says so.
                say(f"stopping {surface.plan.name} - {exc}")
                return
            surface.watcher.poll_once(now=now)
            sleep_fn(surface.plan.poll_seconds)

    threads = [
        threading.Thread(
            target=poll_forever,
            args=(surface,),
            name=f"armwatch-{surface.plan.name}",
            daemon=True,
        )
        for surface in surfaces
    ]
    for thread in threads:
        thread.start()
    say("watching - interrupt to stop")
    try:
        while True:
            sleep_fn(60.0)
    except KeyboardInterrupt:
        say("stopped")
    return [surface.watcher for surface in surfaces]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arm every Lanternlight session watcher from one entry point."
    )
    parser.add_argument(
        "--saved-dir",
        type=Path,
        default=None,
        help="the game's Saved/ directory (default: resolved from LOCALAPPDATA)",
    )
    # Exactly one destination. Neither leaves the watchers with nowhere to
    # archive to; both is a question about which one the operator meant, and
    # guessing at that is how an archive ends up half in each place.
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--dest-root",
        type=Path,
        default=None,
        help=(
            "a LITERAL directory for snapshots, with nothing appended - must "
            "sit outside every git working directory"
        ),
    )
    destination.add_argument(
        "--dest-base",
        type=Path,
        default=None,
        help=(
            "a base directory; snapshots go under a <YYYY-MM-DD> subdirectory "
            "of it that rolls over at local midnight"
        ),
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=None,
        help="stop after this many passes per watcher (default: run until interrupted)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on a clean run, non-zero on a refused destination.

    ``--dest-base`` routes through :func:`run_rolling`, which re-derives the
    dated root as the day changes. ``--dest-root`` keeps its original literal
    meaning exactly: the directory named is the directory written to.
    """
    args = parse_args(argv)
    try:
        if args.dest_base is not None:
            run_rolling(args.saved_dir, args.dest_base, max_passes=args.max_passes)
        else:
            plans = session_plan(args.saved_dir, args.dest_root)
            run(plans, max_passes=args.max_passes)
    except DestinationInsideRepoError as exc:
        print(f"refusing to arm: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via main()
    raise SystemExit(main())
