"""Passive desktop frame poller.

Captures the primary display on an interval and writes timestamped PNGs.
Reads pixels only - no input synthesis, no process access, no hooking.
Filenames carry local wall-clock so frames can be joined to game-log lines.
"""
import time
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

OUT = Path(r"C:\Users\ADMINI~1\AppData\Local\Temp\claude"
           r"\C--Riot-Commander\89593230-c8a1-40c9-a606-6fcfdb8f54b6"
           r"\scratchpad\frames")
INTERVAL_S = 3.0
DURATION_S = 420.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    n = 0
    while time.monotonic() - started < DURATION_S:
        stamp = datetime.now().strftime("%H.%M.%S")
        try:
            img = ImageGrab.grab()
            img.save(OUT / f"f{n:04d}_{stamp}.png")
        except OSError as exc:
            print(f"frame {n} failed: {exc}", flush=True)
        n += 1
        time.sleep(INTERVAL_S)
    print(f"done, {n} frames in {OUT}", flush=True)


if __name__ == "__main__":
    main()
