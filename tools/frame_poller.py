"""Passive desktop frame poller.

Captures the primary display on an interval and writes timestamped PNGs.

Reads pixels only. No input synthesis, no process access, no hooking, nothing
that touches the game. Capturing your own screen is an ordinary desktop
operation and is the sanctioned way this project observes a running game.

Why the filenames carry local wall-clock: the game log timestamps in **UTC**
while these frames are named in **local** time, so the two streams join on the
clock. That join is what turns a screenshot into evidence - it is how class
names rendered on screen were bound to the numeric `setClassGender inclassid`
values in the log. See `docs/OBSERVED_IDS.md`.

Frames are written outside the repository by default, and `frames/` is
gitignored regardless, because a capture of a running game contains the
operator's account name and other on-screen identifiers.

Usage:
    python tools/frame_poller.py [--out DIR] [--interval SECONDS] [--duration SECONDS]

Requires Pillow. It is not a project dependency - install it only if you need
the poller.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_OUT = Path.home() / ".lanternlight" / "frames"
DEFAULT_INTERVAL_S = 3.0
DEFAULT_DURATION_S = 420.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Passive desktop frame poller.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        from PIL import ImageGrab
    except ImportError:
        sys.stderr.write("Pillow is required for the frame poller: pip install pillow\n")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    n = 0
    while time.monotonic() - started < args.duration:
        stamp = datetime.now().strftime("%H.%M.%S")
        try:
            ImageGrab.grab().save(args.out / f"f{n:04d}_{stamp}.png")
        except OSError as exc:
            print(f"frame {n} failed: {exc}", flush=True)
        n += 1
        time.sleep(args.interval)
    print(f"done, {n} frames in {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
