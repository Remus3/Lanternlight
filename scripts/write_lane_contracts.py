"""Regenerate the per-lane contract files from the roster.

Run this after any change to ``ops/lanes.py``. ``tests/test_lane_contract.py``
fails when the files on disk and the roster disagree, so forgetting is caught
by the build rather than by a lane quietly acting on a stale contract.

    python scripts/write_lane_contracts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lane_contract, lanes  # noqa: E402


def main() -> int:
    written = lane_contract.write_all()
    print(f"wrote {len(written)} lane contract(s) to {lane_contract.CONTRACT_DIR}")
    for lane, path in zip(lanes.LANES, written, strict=True):
        marks = []
        if lane.veto:
            marks.append("veto")
        if lane.read_only:
            marks.append("read-only")
        suffix = f"  [{', '.join(marks)}]" if marks else ""
        print(f"  {lane.lane_id:11s} {len(lane.owns):2d} owned pattern(s)  {path.name}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
