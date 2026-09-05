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

#: `OPS-22`. The banned cmdlet is spelled out literally throughout the cases
#: below. That is safe here and nowhere else: this is a FILE ON DISK, and the
#: gate only ever inspects a command STRING handed to it on stdin. Typing any
#: of these into a shell would make the live hook fire on the tool call itself,
#: which is the exact failure this item was opened by.
INVOCATIONS = [
    ("bare", "Stop-Process -Id 1234"),
    ("leading_whitespace", "   Stop-Process -Id 1234"),
    ("pipeline", "Get-Process notepad | Stop-Process"),
    ("pipeline_no_space", "Get-Process notepad |Stop-Process -Force"),
    ("call_operator", "& Stop-Process -Id 1234"),
    ("chain_and", "taskkill /F /PID 1 && Stop-Process -Id 2"),
    ("after_semicolon", "taskkill /F /PID 1 ; Stop-Process -Id 2"),
    ("script_block", "if ($p) { Stop-Process -Id 1 }"),
    ("subexpression", "$(Stop-Process -Id 1)"),
    ("assignment", "$dead = Stop-Process -Id 1 -PassThru"),
    ("lowercase", "stop-process -id 1234"),
    ("uppercase", "STOP-PROCESS -ID 1234"),
    ("mixed_case", "sTOp-PrOcEsS -Id 1234"),
    ("module_qualified", "Microsoft.PowerShell.Management\\Stop-Process -Id 1"),
    ("second_line", "cd C:/Lanternlight\nStop-Process -Id 1"),
    ("alias_spps", "spps -Id 1234"),
    ("quoted_but_handed_to_powershell", 'powershell -Command "Stop-Process -Id 1"'),
    ("quoted_but_handed_to_pwsh", "pwsh -c 'Stop-Process -Id 1'"),
    ("quoted_but_handed_to_iex", "iex 'Stop-Process -Id 1'"),
]

#: Mentions. Each one is a command a session legitimately wants to run, and
#: every one of them was blocked by the bare substring test.
MENTIONS = [
    ("grep_double_quoted", 'grep -n "Stop-Process" tools/precommit_gate.py'),
    ("grep_single_quoted", "grep -n 'Stop-Process' tools/precommit_gate.py"),
    ("grep_unquoted_argument", "grep -rn Stop-Process docs/"),
    ("not_first_after_a_pipe", "cat tools/precommit_gate.py | grep Stop-Process"),
    ("shell_comment", "# Stop-Process is banned - use taskkill /F /PID"),
    ("redirected_echo", 'echo "Stop-Process" >> notes.txt'),
    ("python_string_literal", "python -c \"print('never use Stop-Process')\""),
    ("bash_dash_c_is_not_powershell", "bash -c 'echo Stop-Process'"),
    ("no_word_boundary", "Stop-ProcessNotes.md"),
]

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


class TestACallIsBlockedAndAMentionIsNot:
    """ROADMAP `OPS-22`. A sentinel that is also a legal datum.

    The gate used to decide with ``if "<cmdlet>" in command``. A bare substring
    test cannot tell a CALL from a MENTION, so the name inside a grep pattern,
    a quoted string, a comment or a path was refused exactly as hard as an
    invocation - and it FIRED on the analysis pass that found it.

    The fix is a command-POSITION test, not a parser. Both halves are pinned
    here because only one of them is safe to get wrong: a false block is an
    annoyance, a false pass is the hole this file exists to close. The
    invocation table is therefore the load-bearing half, and it is deliberately
    wider than the old substring check (case variations and the ``spps`` alias
    were NOT caught before).
    """

    @pytest.mark.parametrize(
        "command",
        [c for _, c in INVOCATIONS],
        ids=[name for name, _ in INVOCATIONS],
    )
    def test_an_invocation_is_still_blocked(self, command):
        """The whole point: the guard must not have been weakened.

        Measured before the fix: the case variations, ``spps`` and the
        ``pwsh``/``iex`` forms exited 0 - the old check was case-SENSITIVE and
        knew no aliases. Everything else here already exited 2 and must keep
        doing so.
        """
        result = _run({"tool_input": {"command": command}}, dead_stderr=False)
        assert result.returncode == 2, (
            f"FALSE PASS: {command!r} exited {result.returncode}. This is an "
            "invocation of the banned cmdlet and only exit 2 blocks it."
        )

    @pytest.mark.parametrize(
        "command",
        [c for _, c in MENTIONS],
        ids=[name for name, _ in MENTIONS],
    )
    def test_a_mention_is_not_blocked(self, command):
        """The defect. Every one of these exited 2 before the fix."""
        result = _run({"tool_input": {"command": command}}, dead_stderr=False)
        assert result.returncode == 0, (
            f"FALSE BLOCK: {command!r} exited {result.returncode}. The cmdlet "
            "name appears here as a datum, not in command position."
        )

    def test_the_block_names_the_sanctioned_replacement(self):
        """The refusal has to be actionable, or it just gets worked around."""
        result = _run(
            {"tool_input": {"command": "Stop-Process -Id 1234"}}, dead_stderr=False
        )
        assert result.returncode == 2
        assert "BLOCKED by tools/precommit_gate.py" in result.stderr
        assert "taskkill /F /PID" in result.stderr

    def test_the_cmdlet_check_runs_on_commands_that_are_not_commits(self):
        """Pins the ordering the substring test had.

        The cmdlet check sits ahead of the ``git commit`` early return. If it
        ever slid below that line it would still pass every case above that
        happens to mention a commit, and silently stop guarding every command
        that does not.
        """
        result = _run(
            {"tool_input": {"command": "Get-Process notepad | Stop-Process"}},
            dead_stderr=False,
        )
        assert result.returncode == 2
