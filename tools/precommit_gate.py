"""PreToolUse gate for Bash calls that look like a git commit.

Defence in depth only. The AUTHORITATIVE gate is `.githooks/`, wired by
`scripts/install_hooks.py`. This hook exists because a fresh clone runs zero git
hooks until someone runs that script, and because a Claude session can reach for
`git commit` before anyone has.

Reads the tool-call payload on stdin as JSON, and:
  - blocks a commit whose staged set contains a PII-hazard path
  - blocks a commit message carrying a banned glyph
  - blocks `Stop-Process`

Exit 0 allows. Exit 2 blocks and the stderr text is shown to the model.
Never raises - a crashing gate that blocks every command is worse than no gate,
so anything unexpected exits 0 and says why on stderr.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Built with chr() on purpose: this source file is itself subject to the 7-bit
# ASCII rule, so the banned characters must not appear literally here. An
# earlier draft pasted them in and would have failed tests/test_ascii_hygiene.
BANNED_GLYPHS = {
    chr(0x2014): "em-dash",
    chr(0x2013): "en-dash",
    chr(0x2018): "left smart quote",
    chr(0x2019): "right smart quote",
    chr(0x201C): "left smart double quote",
    chr(0x201D): "right smart double quote",
}

PII_HAZARD = re.compile(
    r"(^|/)(frames|logs|scratchpad|_scratch)/|\.sav$|\.log$|\.log\.\d+$",
    re.IGNORECASE,
)


def _staged_paths() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _block(reason: str) -> None:
    sys.stderr.write(f"BLOCKED by tools/precommit_gate.py: {reason}\n")
    sys.exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not command:
        return 0

    if "Stop-Process" in command:
        _block("Stop-Process hangs the MCP pipe. Use taskkill /F /PID instead.")

    if "git commit" not in command:
        return 0

    for glyph, name in BANNED_GLYPHS.items():
        if glyph in command:
            _block(f"commit message contains a {name}. This repo is 7-bit ASCII only.")

    for path in _staged_paths():
        if PII_HAZARD.search(path):
            _block(
                f"staged path '{path}' matches a PII-hazard pattern. "
                "Game logs, saves and capture frames carry the operator's "
                "SteamID64, persona and geolocation and must never be committed."
            )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a gate must never wedge the session
        sys.stderr.write(f"precommit_gate soft-failed, allowing: {exc}\n")
        sys.exit(0)
