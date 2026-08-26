"""Arm every session watcher from one entry point.

ROADMAP item 4c. This module adds **no copying**. ``lanternlight.savewatch``
already does all of it - copy every changed generation, never write to the
source, refuse a destination inside a git working directory - and the one
thing missing was that arming it was something each session had to REMEMBER.

Two losses came out of exactly that, and both are the reason this file exists
rather than a note in a hand-off:

- The **6.1 MB log of 2026-08-09 is gone.** The game truncates
  ``MistfallHunter.log`` in place on launch. Measured 2026-08-25: the live
  log's creation time is ``2026-08-09 08:18:56`` and has never changed, so it
  is the same file being emptied, not a new one being made.
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
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from lanternlight import paths
from lanternlight.savewatch import DestinationInsideRepoError, SaveWatcher

__all__ = [
    "WatchPlan",
    "arm",
    "main",
    "run",
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
    parser.add_argument(
        "--dest-root",
        type=Path,
        required=True,
        help="where snapshots go - must sit outside every git working directory",
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=None,
        help="stop after this many passes per watcher (default: run until interrupted)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on a clean run, non-zero on a refused destination."""
    args = parse_args(argv)
    try:
        plans = session_plan(args.saved_dir, args.dest_root)
        run(plans, max_passes=args.max_passes)
    except DestinationInsideRepoError as exc:
        print(f"refusing to arm: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via main()
    raise SystemExit(main())
