"""Arm, disarm or inspect the scheduled task that runs ``ops/inbox_runner.py``.

OPERATOR RULING, 2026-10-02, ``LL-0317``. This file IS the record of the
trigger's exact definition: one Windows scheduled task, in this project's own
task folder, every 15 minutes, while the operator is logged on (so the runner
can read the USER environment store), running the runner under ``pythonw`` so
no console flashes.

The interpreter and repository paths are resolved at ARM time and written only
into the task, never into a tracked file - the interpreter path carries the
account name.

    python scripts/arm_inbox_runner.py --arm
    python scripts/arm_inbox_runner.py --disarm
    python scripts/arm_inbox_runner.py --status
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "\\Lanternlight\\InboxRunner"
INTERVAL_MINUTES = 15
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "ops" / "inbox_runner.py"


def create_argv(pythonw: str, runner: Path = RUNNER) -> list[str]:
    command = f'"{pythonw}" "{runner}"'
    return [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/SC", "MINUTE", "/MO", str(INTERVAL_MINUTES),
        "/TR", command,
        "/RL", "LIMITED",
    ]


def delete_argv() -> list[str]:
    return ["schtasks", "/Delete", "/F", "/TN", TASK_NAME]


def query_argv() -> list[str]:
    return ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"]


def _pythonw() -> str:
    found = shutil.which("pythonw")
    if not found:
        raise SystemExit("pythonw not on PATH; refusing to arm with a console interpreter")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--arm", action="store_true")
    g.add_argument("--disarm", action="store_true")
    g.add_argument("--status", action="store_true")
    ns = ap.parse_args(argv)
    if ns.arm:
        cmd = create_argv(_pythonw())
    elif ns.disarm:
        cmd = delete_argv()
    else:
        cmd = query_argv()
    done = subprocess.run(cmd, capture_output=True, text=True)
    out = (done.stdout or "") + (done.stderr or "")
    for line in out.splitlines():
        if ns.status and line.strip().startswith(("Task To Run", "Run As User")):
            continue
        print(line)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
