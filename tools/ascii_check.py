"""PostToolUse hook: warn when an Edit or Write lands a non-ASCII byte.

Defence in depth for the 7-bit ASCII rule. The authoritative gates are
`tests/test_ascii_hygiene.py` and `.githooks/pre-commit`; this one exists to
catch a violation at the moment it is written rather than at commit time, when
the context that produced it is gone.

Advisory by design. It reports on stderr and always exits 0 - a PostToolUse hook
that blocks would fight an edit that has already happened, and a noisy gate that
wedges the session gets disabled, which is worse than a gate that nags.

ARGV IS NOT A CONTRACT HERE, AND THAT IS A DECISION - ROADMAP ``OPS-67``.
Measured 2026-09-08: ``python tools/ascii_check.py --not-a-flag`` exits 0 and
ignores the flag, exactly like the eight other ``tools/`` entry points that
``OPS-64``'s sweep found. ``OPS-64`` fixed that in ``archive_link_guard.py`` by
growing real options and ``OPS-66`` fixed it in ``precommit_gate.py`` by naming
two contracts and refusing everything else. Neither answer is right for this
file, and the reason is the caller, not the taste:

- **This module has exactly one caller and it passes no arguments.** The wiring
  in ``.claude/settings.json`` is ``pythonw "$CLAUDE_PROJECT_DIR/tools/
  ascii_check.py"`` with no trailing token, and the input this hook actually
  reads arrives on stdin as JSON, not in ``argv``. There is no argument a caller
  could pass that this module would be wrong to ignore, because no caller passes
  one. The ``OPS-64`` failure - a confident verdict about a scope the caller did
  not ask for - has no scope here to be wrong about: the file to check is named
  in the payload and nowhere else.
- **Refusing would be actively dangerous.** A ``PostToolUse`` hook that exits
  non-zero breaks the session it runs in. ``precommit_gate.py`` can afford
  ``USAGE_EXIT_CODE = 2`` because its exit codes ARE its verdicts and refusing
  is its job; here a non-zero exit is not a verdict, it is a wedged session
  after an edit that already landed. An unknown-argv refusal would sit one
  harness change away from firing on the path that must never fail.
- **An ``argparse`` parser would import a ``SystemExit`` into a fail-soft
  module.** This file's whole promise is that it returns 0 on every path;
  ``argparse`` raises ``SystemExit(2)`` on a bad token and prints a usage block,
  which is a second exit channel inside a module whose only channel is meant to
  be stderr text.

So the current behaviour stays, on purpose. ``tests/test_syntax_check_hook.py``
pins it, INCLUDING the premise this reasoning rests on: it re-reads
``.claude/settings.json`` and asserts the wiring still passes no arguments. If a
future session adds a flag to that command line, the pin goes red and this
decision is reopened rather than silently outlived - which is the point, because
the argument for ignoring argv is entirely an argument about who calls this.
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
