"""PreToolUse gate for Bash calls that look like a git commit.

Defence in depth only. The AUTHORITATIVE gate is `.githooks/`, wired by
`scripts/install_hooks.py`. This hook exists because a fresh clone runs zero git
hooks until someone runs that script, and because a Claude session can reach for
`git commit` before anyone has.

Reads the tool-call payload on stdin as JSON, and:
  - blocks a commit whose staged set contains a PII-hazard path
  - blocks a commit message carrying a banned glyph
  - blocks `Stop-Process`

Exit 0 allows. Exit 2 blocks and the stderr text is shown to the model. The
exit code is the verdict and the stderr text is best-effort - see `_say`, and
`OPS-15` for the fail-open this ordering used to produce.
Never raises - a crashing gate that blocks every command is worse than no gate,
so anything unexpected exits 0 and says why on stderr.
"""

from __future__ import annotations

import contextlib
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


def _say(message: str) -> None:
    """Report ``message`` on stderr, best-effort, without risking the exit code.

    **`OPS-15`, and the coupling it removes.** This gate's verdict IS its exit
    code - a PreToolUse hook blocks on 2 and permits on everything else. The
    reason text is a courtesy. Before this, the two were coupled: :func:`_block`
    wrote first and exited second, so a stderr that could not be written took
    the refusal with it and the gate FAILED OPEN.

    Two distinct paths lost the code, and the second is the one that makes a
    bare ``try``/``except`` at each call site insufficient:

    * the write raises, the outer handler in ``__main__`` writes again, raises
      again, and the process exits 1;
    * the write is merely BUFFERED and never flushed. CPython flushes the
      standard streams at interpreter shutdown and **exits 120 if that flush
      raises**, overriding whatever this script exited with. Measured at exit
      120 on a blocking payload and on a benign one alike.

    **What is actually load-bearing here, corrected after a refutation pass.**
    The ``try``/``except`` is: without it a raising write propagates and the
    exit code goes with it. The ``sys.stderr = None`` inside the handler is
    NOT - it is measurably inert. Replacing that line with ``pass`` leaves
    ``tests/test_precommit_gate.py`` at 5 passed and every behaviour case
    unchanged, because :func:`_exit` detaches an unflushable stream anyway and
    every call site here is immediately followed by ``_exit``.

    An earlier version of this docstring claimed the detach was "the whole
    reason this is a function". That was a behaviour claim the artifact does
    not support, which this repository treats as a defect in its own right. The
    line is kept as defence in depth against a FUTURE call site that does not
    reach ``_exit``; it is not what makes the current code correct. If you
    simplify it away, nothing will fail - so read :func:`_exit` first.

    Losing the message is an acceptable trade. Losing the verdict is not.
    """
    try:
        sys.stderr.write(message)
        sys.stderr.flush()
    except Exception:
        with contextlib.suppress(Exception):
            sys.stderr = None


def _exit(code: int) -> None:
    """Exit with ``code``, making sure interpreter shutdown cannot change it.

    **The other half of `OPS-15`.** :func:`_say` detaches a stderr it failed to
    write, but a run that never NEEDS to report never calls it - and a benign
    command is exactly that run. The stream stays attached and unflushable,
    CPython's shutdown flush raises, and the process exits 120 instead of 0.
    Measured on ``ls -la`` with a broken stderr, after the ``_say`` fix had
    already corrected both blocking paths.

    Exit 120 is not a fail-open - only exit 2 blocks - so this half is noise
    rather than a hole. It is still a gate reporting failure on every command
    it was perfectly happy with, which is how a guard gets switched off.

    Both streams are checked: nothing here writes to stdout, but a broken
    stdout fails the same shutdown flush and produces the same 120.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.flush()
        except Exception:
            with contextlib.suppress(Exception):
                setattr(sys, name, None)
    sys.exit(code)


def _block(reason: str) -> None:
    _say(f"BLOCKED by tools/precommit_gate.py: {reason}\n")
    _exit(2)


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
        _exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a gate must never wedge the session
        _say(f"precommit_gate soft-failed, allowing: {exc}\n")
        _exit(0)
