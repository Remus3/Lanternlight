"""PostToolUse hook: warn when an Edit or Write lands a non-ASCII byte.

Defence in depth for the 7-bit ASCII rule. The authoritative gates are
`tests/test_ascii_hygiene.py` and `.githooks/pre-commit`; this one exists to
catch a violation at the moment it is written rather than at commit time, when
the context that produced it is gone.

Advisory by design. It reports on stderr and always exits 0 - a PostToolUse hook
that blocks would fight an edit that has already happened, and a noisy gate that
wedges the session gets disabled, which is worse than a gate that nags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AUTHORED_SUFFIXES = {".py", ".md", ".toml", ".ini", ".txt", ".sh", ".yml", ".yaml", ".json"}


def offending(path: Path) -> tuple[int, int] | None:
    """Return (byte_offset, byte_value) of the first non-ASCII byte, or None."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    for i, b in enumerate(data):
        if b > 127:
            return (i, b)
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw = payload.get("tool_input", {}).get("file_path")
    if not raw:
        return 0

    path = Path(raw)
    if path.suffix.lower() not in AUTHORED_SUFFIXES:
        return 0

    hit = offending(path)
    if hit is None:
        return 0

    offset, value = hit
    sys.stderr.write(
        f"ASCII VIOLATION in {path}: byte 0x{value:02X} at offset {offset}. "
        "This repo is 7-bit ASCII only - no em-dashes, en-dashes or smart "
        "quotes. Use ' - ' for a clause break. Fix it now; "
        "tests/test_ascii_hygiene.py will fail otherwise.\n"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # advisory hook must never wedge the session
        sys.stderr.write(f"ascii_check soft-failed: {exc}\n")
        sys.exit(0)
