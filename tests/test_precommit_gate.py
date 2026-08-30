"""The commit gate must BLOCK even when it cannot say why.

ROADMAP ``OPS-15``, opened by the adversarial pass recorded in `LL-0081`.

WHY THIS FILE EXISTS AT ALL. Before it, **nothing in this repository tested
``tools/precommit_gate.py``** - a guard whose entire job is to refuse commits
had zero coverage, and its one measured failure mode was to fail OPEN. A guard
that is never exercised is a guard nobody has watched go red.

THE DEFECT. ``_block`` wrote its reason to ``sys.stderr`` and only THEN called
``sys.exit(2)``. A PreToolUse hook blocks on exit 2 and on nothing else, so any
path that loses the exit code converts a refusal into a permit. Two such paths
were measured, and the second is the one the item under-described:

1. The write raises, the outer ``except Exception`` handler writes to stderr
   again, raises again, and the process exits 1.
2. The write is buffered and never flushed. CPython flushes the standard
   streams at interpreter shutdown, and **exits 120 if that flush raises** -
   overriding whatever the script exited with. Measured: exit 120 on both
   blocking payloads AND on a benign one.

So the gate did not merely lose its message; it lost its verdict.

WHAT IS DELIBERATELY NOT ASSERTED. That the reason text arrives. The message is
best-effort by design after this fix - if stderr is gone the operator loses the
explanation, and that is the correct trade. What must never be lost is the 2.

These tests spawn the real script as a subprocess, because the bug lives in
process exit codes and interpreter shutdown, neither of which is observable
from inside the same process.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "tools" / "precommit_gate.py"

#: A banned glyph, built with ``chr`` because this file is itself subject to
#: the 7-bit ASCII rule. Blocking on it needs no git state, which keeps these
#: tests independent of the repository they run in.
EM_DASH = chr(0x2014)

#: Payload shapes. The gate reads ``tool_input.command``.
BLOCKING = {"tool_input": {"command": f"git commit -m 'bad {EM_DASH} glyph'"}}
BENIGN = {"tool_input": {"command": "ls -la"}}

#: Runs the gate with a ``sys.stderr`` whose ``write`` and ``flush`` both raise.
#: A wrapper rather than an OS handle trick, so the shape is identical on every
#: platform and does not depend on how the harness spawns hooks.
DEAD_STDERR_WRAPPER = textwrap.dedent(
    f"""
    import sys, runpy

    class DeadStderr:
        def write(self, text):
            raise OSError(22, "Invalid argument")
        def flush(self):
            raise OSError(22, "Invalid argument")
        def isatty(self):
            return False

    sys.stderr = DeadStderr()
    runpy.run_path(r"{GATE.as_posix()}", run_name="__main__")
    """
)


def _run(payload: dict, *, dead_stderr: bool) -> subprocess.CompletedProcess:
    argv = [sys.executable, "-c", DEAD_STDERR_WRAPPER] if dead_stderr else [
        sys.executable,
        str(GATE),
    ]
    return subprocess.run(
        argv,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
    )


class TestTheGateStillBlocksWhenItCannotReport:
    """`OPS-15`. The exit code is the verdict; the message is a courtesy."""

    def test_a_blocking_payload_exits_2_even_with_stderr_unwritable(self):
        """The item's acceptance criterion.

        Measured BEFORE the fix: exit 120, which does not block. A gate that
        silently permits the commit it was built to refuse is worse than no
        gate, because the operator believes they are covered.
        """
        result = _run(BLOCKING, dead_stderr=True)
        assert result.returncode == 2, (
            "the gate FAILED OPEN: a blocking payload exited "
            f"{result.returncode}, and only exit 2 blocks a PreToolUse hook. "
            "The reason could not be written to stderr and the verdict went "
            "with it. Keep the message best-effort and the exit code absolute."
        )

    def test_a_benign_payload_still_exits_0_with_stderr_unwritable(self):
        """The other half. A broken stderr must not invent a refusal either.

        This one also failed before the fix - exit 120 on `ls -la` - because
        the shutdown flush, not the block path, was producing the code.
        """
        result = _run(BENIGN, dead_stderr=True)
        assert result.returncode == 0, (
            f"a benign command exited {result.returncode} with stderr broken; "
            "a gate that cannot write must still get out of the way"
        )

    @pytest.mark.parametrize(
        "payload,expected",
        [(BLOCKING, 2), (BENIGN, 0)],
        ids=["blocking", "benign"],
    )
    def test_the_working_stderr_controls_are_unchanged(self, payload, expected):
        """The positive control.

        Without this the fix could be "always exit 2" or "never exit 2" and
        the two tests above would still pass.
        """
        assert _run(payload, dead_stderr=False).returncode == expected

    def test_the_reason_is_still_reported_when_stderr_works(self):
        """Best-effort must not become never-effort.

        The fix wraps the write in a suppressing handler. That is exactly the
        shape that can silently stop reporting altogether, so pin the happy
        path: the operator still learns WHY on a normal run.
        """
        result = _run(BLOCKING, dead_stderr=False)
        assert result.returncode == 2
        assert "BLOCKED by tools/precommit_gate.py" in result.stderr
        assert "em-dash" in result.stderr
