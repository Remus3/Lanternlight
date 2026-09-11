"""The post-edit syntax check must SPEAK, and must never wedge the session.

ROADMAP ``OPS-37`` criterion 1. Claude Code hooks in this repository run under
a windowless interpreter, so a Python file left unparseable by an edit says
nothing at all until some much later test run trips over it. By then the
context that produced the breakage is gone. ``tools/syntax_check_hook.py``
closes that gap by compiling each edited ``.py`` at the moment it is written.

TWO PROPERTIES, AND THE SECOND IS THE ONE THAT BITES.

1. It reports. A file with a syntax error draws a message on stderr naming the
   file, the line and the compiler's own words.
2. **It always exits 0.** A ``PostToolUse`` hook that exits non-zero breaks the
   session it runs in - an advisory check that wedges the operator is worse
   than no check at all. That is the same fail-soft contract
   ``ops/inbox_watch.py`` and ``tools/ascii_check.py`` already carry.

A test that only inspected stderr would pass on a hook that returns 1 and
breaks every edit in the session, so every case below asserts the exit code
EXPLICITLY. That assertion is the point of the file, not decoration on it.

WHY THE MARKER IS ASSERTED RATHER THAN JUST "the line number appears".
``py_compile`` prints its OWN report to stderr when ``doraise`` is false, and
that report already contains the file name and the line number. So an
assertion built only from those two facts stays green when the compile is
mutated to stop raising - a false green hiding a hook that reports nothing of
its own. Asserting our marker string is what makes the failure case detectable.

These tests spawn the real script as a subprocess. The behaviour under test is
a process exit code and what a process writes to stderr, neither of which is
observable from inside the interpreter that is doing the asserting.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "tools" / "syntax_check_hook.py"

#: The string the hook itself prints. See the module docstring for why this is
#: asserted instead of relying on the file name and line number alone.
MARKER = "SYNTAX ERROR"

#: A file whose syntax error sits on line 8, well past line 1, so a report that
#: merely echoed "1" from somewhere could not accidentally satisfy the check.
BROKEN_SOURCE = (
    '"""A module the compiler must refuse."""\n'
    "\n"
    "\n"
    "def fine():\n"
    "    return 1\n"
    "\n"
    "\n"
    "def broken(:\n"
    "    return 2\n"
)
BROKEN_LINE = 8

CLEAN_SOURCE = (
    '"""A module the compiler accepts."""\n'
    "\n"
    "\n"
    "def fine():\n"
    "    return 1\n"
)

#: Distinctive enough that a search of the repository for a stray artifact
#: named after it cannot collide with a real file or with a sibling lane's work.
STEM = "ll_syntax_probe_subject"


def run_hook(stdin_text: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run the hook exactly as the harness would, on the given stdin bytes."""
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
    )


def payload_for(path: Path) -> str:
    """A ``PostToolUse`` payload shaped like the ones Write and Edit produce."""
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(path)},
        }
    )


def write_subject(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="ascii")
    return path


# ---------------------------------------------------------------------------
# the hook exists at the path the settings file will name
# ---------------------------------------------------------------------------


def test_the_hook_script_exists_and_is_not_empty() -> None:
    assert HOOK.is_file(), f"the hook script is missing: {HOOK}"
    assert HOOK.stat().st_size > 0, "the hook script is empty"


# ---------------------------------------------------------------------------
# a broken file is reported - and the session survives it
# ---------------------------------------------------------------------------


def test_a_syntax_error_is_reported_on_stderr(tmp_path: Path) -> None:
    subject = write_subject(tmp_path, f"{STEM}_broken.py", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    assert MARKER in result.stderr, (
        "a file the compiler refuses produced no report of our own: "
        f"stderr={result.stderr!r}"
    )


def test_the_report_names_the_file_and_the_line(tmp_path: Path) -> None:
    subject = write_subject(tmp_path, f"{STEM}_broken.py", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    assert subject.name in result.stderr, (
        f"the report does not name the file: {result.stderr!r}"
    )
    assert f"line {BROKEN_LINE}" in result.stderr, (
        f"the report does not name line {BROKEN_LINE}: {result.stderr!r}"
    )
    assert "invalid syntax" in result.stderr, (
        f"the report drops the compiler's own message: {result.stderr!r}"
    )


def test_a_syntax_error_still_exits_zero(tmp_path: Path) -> None:
    """The whole reason this file spawns processes.

    A hook that exits non-zero breaks the session it runs in, and nothing about
    stderr would reveal that.
    """
    subject = write_subject(tmp_path, f"{STEM}_broken.py", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    assert result.returncode == 0, (
        "the hook exited non-zero on a broken file, which breaks the session: "
        f"rc={result.returncode} stderr={result.stderr!r}"
    )


def test_the_hook_does_not_leak_a_traceback(tmp_path: Path) -> None:
    subject = write_subject(tmp_path, f"{STEM}_broken.py", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    # Paired with a positive assertion on purpose. On its own this rules
    # something out while pinning nothing down - it passes just as happily when
    # the script is missing entirely and the interpreter says so without a
    # traceback.
    assert MARKER in result.stderr, f"no report at all: {result.stderr!r}"
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"the hook crashed instead of reporting: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# silence in every case that is not a broken .py
# ---------------------------------------------------------------------------


def test_a_clean_python_file_produces_no_output(tmp_path: Path) -> None:
    subject = write_subject(tmp_path, f"{STEM}_clean.py", CLEAN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"unexpected stdout: {result.stdout!r}"
    assert result.stderr == "", f"unexpected stderr: {result.stderr!r}"


def test_a_non_python_path_is_ignored(tmp_path: Path) -> None:
    """The suffix filter, pinned with content the compiler WOULD refuse.

    A ``.txt`` holding clean Python would pass this test even with the filter
    deleted, which would make it decoration.
    """
    subject = write_subject(tmp_path, f"{STEM}_notes.txt", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"unexpected stdout: {result.stdout!r}"
    assert result.stderr == "", (
        f"a non-Python path was compiled anyway: {result.stderr!r}"
    )


def test_a_missing_file_exits_zero_quietly(tmp_path: Path) -> None:
    """An edit can be followed by a move or a delete. That is not a defect."""
    subject = tmp_path / f"{STEM}_gone.py"

    result = run_hook(payload_for(subject), tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"unexpected stdout: {result.stdout!r}"
    assert result.stderr == "", f"unexpected stderr: {result.stderr!r}"


# ---------------------------------------------------------------------------
# defensive stdin - every one of these must exit 0
# ---------------------------------------------------------------------------


MALFORMED_STDIN = [
    pytest.param("", id="empty"),
    pytest.param("   \n", id="whitespace"),
    pytest.param("this is not json at all", id="not_json"),
    pytest.param("{", id="truncated_json"),
    pytest.param("[1, 2, 3]", id="json_but_a_list"),
    pytest.param('"a bare string"', id="json_but_a_string"),
    pytest.param("null", id="json_null"),
    pytest.param("{}", id="empty_object"),
    pytest.param('{"tool_input": {}}', id="no_file_path"),
    pytest.param('{"tool_input": {"file_path": ""}}', id="blank_file_path"),
    pytest.param('{"tool_input": {"file_path": null}}', id="null_file_path"),
    pytest.param('{"tool_input": "not-a-dict"}', id="tool_input_not_a_dict"),
    pytest.param('{"tool_input": {"file_path": 17}}', id="file_path_not_a_string"),
]


@pytest.mark.parametrize("stdin_text", MALFORMED_STDIN)
def test_unusable_stdin_exits_zero_and_says_nothing(
    stdin_text: str, tmp_path: Path
) -> None:
    result = run_hook(stdin_text, tmp_path)

    assert result.returncode == 0, (
        f"stdin {stdin_text!r} made the hook exit {result.returncode}, which "
        f"breaks the session: stderr={result.stderr!r}"
    )
    assert result.stdout == "", f"unexpected stdout: {result.stdout!r}"
    assert result.stderr == "", f"unexpected stderr: {result.stderr!r}"


# ---------------------------------------------------------------------------
# no stray artifact - not beside the source, not in the repository
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "source"),
    [
        pytest.param(f"{STEM}_clean.py", CLEAN_SOURCE, id="clean"),
        pytest.param(f"{STEM}_broken.py", BROKEN_SOURCE, id="broken"),
    ],
)
def test_no_artifact_is_left_beside_the_source(
    name: str, source: str, tmp_path: Path
) -> None:
    """A ``.pyc`` dropped next to an edited file is repository litter.

    ``py_compile`` writes beside the source by default, so this is the property
    the temporary compile target exists to buy.
    """
    subject = write_subject(tmp_path, name, source)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    result = run_hook(payload_for(subject), tmp_path)

    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert result.returncode == 0, result.stderr
    assert after == before, f"the hook left something behind: {set(after) - set(before)}"
    assert not (tmp_path / "__pycache__").exists(), "a __pycache__ directory was created"


def test_no_artifact_lands_in_the_repository(tmp_path: Path) -> None:
    """Bounded on purpose.

    Only the two places a stray compile target could plausibly land are
    checked - the repository root and ``tools/__pycache__`` - and only for a
    name derived from the subject file. A whole-tree sweep would go red on any
    unrelated work happening in the checkout at the same time, which would make
    this a flake rather than a guard.
    """
    subject = write_subject(tmp_path, f"{STEM}_broken.py", BROKEN_SOURCE)

    result = run_hook(payload_for(subject), tmp_path)
    assert result.returncode == 0, result.stderr

    strays = [p.as_posix() for p in REPO_ROOT.glob(f"*{STEM}*")]
    strays += [p.as_posix() for p in (REPO_ROOT / "tools").glob(f"*{STEM}*")]
    cache = REPO_ROOT / "tools" / "__pycache__"
    if cache.is_dir():
        strays += [p.as_posix() for p in cache.glob(f"*{STEM}*")]
    assert strays == [], f"the hook wrote into the repository: {strays}"


# ---------------------------------------------------------------------------
# exit 0 is unconditional - even when the streams the hook reports on are
# dead. Reproduces the refutation pass's finding:
#
#     <payload> | python tools/syntax_check_hook.py 2>&-        ->  exit = 1
#
# With stderr closed, the reporting write fails, and the `except Exception`
# handler that exists to make failure safe then tries to write ITS OWN
# diagnostic to the SAME dead stream and raises again, uncaught. Measured
# on this machine: closing a standard fd before the interpreter starts makes
# CPython hand back `None` rather than a live-but-erroring stream object -
# `python -c "print(repr(sys.stderr))" 2>&-` prints `None` - which is the
# exact condition `pythonw.exe` (no console attached) produces too, for a
# different reason. A stderr wired to a PIPE whose reader has already exited
# is a THIRD, distinct failure mode: `sys.stderr` is a live object right up
# until the write, and the write raises only then. Measured separately: a
# script that guards that write in try/except and then calls `sys.exit(0)`
# still exits **120**, not 0, because normal interpreter shutdown performs
# its OWN unconditional stdio flush and a failure in THAT flush - not in this
# module's own code - is what decides the exit status. Only `os._exit(0)`,
# which skips that shutdown sequence, actually reaches 0 in that case.
#
# None of this is reachable by monkeypatching an internal function and
# asserting no exception was raised - the defect is in what the real process,
# spawned for real, with a real dead stream, hands back as its exit code.
# ---------------------------------------------------------------------------


BASH = shutil.which("bash")


def _bash_command(redirect_tokens: list[str]) -> str:
    """The shell command line: the hook, run under ``sys.executable``.

    ``redirect_tokens`` (``"1>&-"``, ``"2>&-"``) are shell syntax, not
    arguments, so they are appended raw rather than through ``shlex.quote``.
    """
    parts = [shlex.quote(sys.executable), shlex.quote(str(HOOK)), *redirect_tokens]
    return " ".join(parts)


def run_hook_with_closed_streams(
    stdin_text: str, cwd: Path, *, close_stdout: bool, close_stderr: bool
) -> subprocess.CompletedProcess:
    """Run the hook with a standard fd closed BEFORE the interpreter starts.

    This is what the refutation pass's own repro does (``2>&-``), and it is
    not the same thing as redirecting to ``os.devnull`` or to a pipe: closing
    the descriptor first is what makes CPython hand the hook a `None`
    stream rather than a live one that merely errors on write - see the
    module-level comment above for the direct measurement.
    ``subprocess``'s own stdio parameters (``PIPE``, ``DEVNULL``, an
    inherited handle) cannot express a genuinely closed descriptor for a
    freshly spawned process, so this shells out to a real POSIX shell -
    present on this machine as part of the same Git for Windows install the
    repo's own ``.githooks`` already require to run at all.
    """
    assert BASH, "bash not found on PATH - needed to close a standard fd for this test"
    tokens = []
    if close_stdout:
        tokens.append("1>&-")
    if close_stderr:
        tokens.append("2>&-")
    return subprocess.run(
        [BASH, "-c", _bash_command(tokens)],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
    )


def run_hook_with_stderr_forced_none(stdin_text: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run the hook with ``sys.stderr`` literally ``None``, as ``pythonw.exe``
    leaves it when no console is attached.

    This hook is registered under ``python.exe``, not ``pythonw.exe``, in
    ``.claude/settings.json`` - but a SIBLING hook in that same file runs
    under ``pythonw.exe``, so a harness handing a hook a ``None`` stderr is a
    live condition on this machine, not a hypothetical dreamed up for this
    test. ``runpy.run_path(..., run_name="__main__")`` re-executes the real
    file, with its own ``if __name__ == "__main__":`` guard firing, inside a
    driver process whose ``sys.stderr`` has already been forced to ``None`` -
    still a real, separate OS process, and still the real script's real exit
    behaviour under test, not a patched-and-inspected function call.
    """
    driver = (
        "import runpy, sys\n"
        "sys.stderr = None\n"
        f"runpy.run_path({str(HOOK)!r}, run_name='__main__')\n"
    )
    return subprocess.run(
        [sys.executable, "-c", driver],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
    )


def run_hook_with_broken_stderr_pipe(stdin_text: str, cwd: Path) -> int:
    """Run the hook with stderr wired to a pipe whose reader has exited.

    Distinct from a closed descriptor: ``sys.stderr`` is a live, valid stream
    object right up until something actually tries to write to it. Closing
    our end of the pipe before the child can write anything, then never
    reading it, reproduces exactly that. Only the exit code is meaningful
    here - once the reader is gone there is nothing left to read stderr from.
    """
    proc = subprocess.Popen(
        [sys.executable, str(HOOK)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
    )
    proc.stderr.close()
    try:
        proc.stdin.write(stdin_text)
        proc.stdin.close()
        proc.stdout.read()
        proc.stdout.close()
        return proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)


DEAD_STREAM_SUBJECTS = [
    pytest.param(f"{STEM}_deadstream_clean.py", CLEAN_SOURCE, id="clean"),
    pytest.param(f"{STEM}_deadstream_broken.py", BROKEN_SOURCE, id="broken"),
]

CLOSED_STREAM_CASES = [
    pytest.param(True, False, id="stderr_closed"),
    pytest.param(False, True, id="stdout_closed"),
    pytest.param(True, True, id="both_closed"),
]


@pytest.mark.parametrize(("close_stderr", "close_stdout"), CLOSED_STREAM_CASES)
@pytest.mark.parametrize(("name", "source"), DEAD_STREAM_SUBJECTS)
def test_exit_is_always_zero_with_a_closed_standard_stream(
    name: str, source: str, close_stderr: bool, close_stdout: bool, tmp_path: Path
) -> None:
    subject = write_subject(tmp_path, name, source)

    result = run_hook_with_closed_streams(
        payload_for(subject), tmp_path, close_stdout=close_stdout, close_stderr=close_stderr
    )

    assert result.returncode == 0, (
        f"closed stream(s) (stdout={close_stdout}, stderr={close_stderr}) made "
        f"the hook exit {result.returncode}, which breaks the session: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


@pytest.mark.parametrize(("name", "source"), DEAD_STREAM_SUBJECTS)
def test_exit_is_always_zero_with_stderr_forced_none(
    name: str, source: str, tmp_path: Path
) -> None:
    subject = write_subject(tmp_path, name, source)

    result = run_hook_with_stderr_forced_none(payload_for(subject), tmp_path)

    assert result.returncode == 0, (
        f"a None sys.stderr made the hook exit {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


@pytest.mark.parametrize(("name", "source"), DEAD_STREAM_SUBJECTS)
def test_exit_is_always_zero_with_a_broken_stderr_pipe(
    name: str, source: str, tmp_path: Path
) -> None:
    subject = write_subject(tmp_path, name, source)

    rc = run_hook_with_broken_stderr_pipe(payload_for(subject), tmp_path)

    assert rc == 0, f"a broken stderr pipe made the hook exit {rc}, not 0"


def test_the_bash_transport_really_runs_the_hook_when_bash_is_present(
    tmp_path: Path,
) -> None:
    """The PRESENT direction of the ``BASH`` presence guard - ``OPS-74`` #5.

    ``BASH = shutil.which("bash")`` above is a presence guard, and every
    closed-stream case in this section asserts one thing about the result: the
    exit code is zero. That is a negative assertion. A shell that resolved,
    started, and ran nothing whatsoever also exits zero, and so does a hook
    that starts and returns without ever compiling the subject. Under a closed
    stderr there is by construction no output to check either, so nothing in
    those cases can tell a working transport apart from an inert one.

    This test closes that hole by running the SAME transport - the same
    ``bash -c`` command line built by :func:`_bash_command` - with both
    standard streams left open, and asserting the effect the guarded path
    exists to produce: the hook's own marker, naming the subject it refused,
    arriving on stderr. If this goes red while the closed-stream cases stay
    green, the transport is the thing that broke and those cases were passing
    on nothing.

    The honest limit, recorded because a caveat kept only in chat is a lie in
    the artifact: this proves the marker travelled back through bash for a
    BROKEN subject. It does not prove the closed-stream cases exercise the
    same code path inside the hook, only that the path they share up to the
    stream redirection is alive.
    """
    assert BASH, "bash must resolve on PATH before this transport can be exercised"
    subject = write_subject(tmp_path, f"{STEM}_bash_transport.py", BROKEN_SOURCE)

    result = run_hook_with_closed_streams(
        payload_for(subject), tmp_path, close_stdout=False, close_stderr=False
    )

    assert result.returncode == 0, (
        f"the hook exited {result.returncode} through an unredirected bash "
        f"transport: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert MARKER in result.stderr, (
        "bash resolved and the run exited 0, but the hook's own marker never "
        "came back - so the transport carried nothing and every closed-stream "
        "case above would be just as green on a hook that never ran: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert subject.name in result.stderr, (
        "the marker arrived but not the subject's name, so the report is not "
        f"about the file this test wrote: stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# OPS-67: BOTH PostToolUse hooks IGNORE an unknown argument, deliberately.
#
# `OPS-64`'s sweep found nine `tools/` entry points that read an unknown flag
# as a pass. Two of them were answered by changing the code - the archive link
# guard grew real options, the pre-commit gate named two contracts and refused
# everything else. The two PostToolUse hooks are answered by NOT changing the
# code, and that is the answer this section exists to make legible.
#
# The reasoning is written out in each module's own docstring; the short form
# is that neither hook takes its subject from argv (it arrives on stdin as
# JSON), neither has a caller that passes an argument, and a non-zero exit from
# a PostToolUse hook breaks the session it runs in - so a usage-error exit code
# would be a loaded gun pointed at the one path that must never fail.
#
# WHY BOTH HOOKS ARE PINNED IN THIS ONE MODULE. `tools/ascii_check.py` has no
# test module of its own, and the property under test here is not the ASCII
# rule - it is the shared PostToolUse fail-soft contract that this module's
# docstring already names ascii_check as carrying. Splitting one contract
# across two files would hide the fact that the two hooks were decided
# together and for the same reason.
#
# THE PREMISE IS PINNED, NOT JUST THE BEHAVIOUR. The whole argument for
# ignoring argv is an argument about who calls these files. So
# `test_the_posttooluse_wiring_passes_no_arguments` re-reads
# `.claude/settings.json` and asserts the real command lines still carry no
# trailing token. If a future session adds a flag there, that test goes red and
# the decision is reopened rather than silently outlived. Without it, this
# section would pin a behaviour whose justification could rot unobserved -
# which is exactly the "unexamined default mistaken for a decision" that
# OPS-67 criterion 3 is about.
# ---------------------------------------------------------------------------


ASCII_HOOK = REPO_ROOT / "tools" / "ascii_check.py"

SETTINGS = REPO_ROOT / ".claude" / "settings.json"

#: The sentence each module must carry to prove the argv behaviour was decided
#: rather than merely inherited. Asserting the module TEXT is the only way to
#: tell those two apart - the runtime behaviour of a decision and of an
#: oversight are byte-identical, which is the whole difficulty OPS-67 names.
ARGV_DECISION_ANCHOR = "ARGV IS NOT A CONTRACT HERE, AND THAT IS A DECISION"

#: Deliberately plausible rather than absurd. A flag a real caller might type
#: after reading a sibling tool's options is the case that matters; `--zzz`
#: would prove less.
UNKNOWN_ARGV = ["--quiet", "--paths", "docs/LEDGER.md"]

#: A module whose only sin is a non-ASCII byte. It must still be valid Python,
#: so that a failure here cannot be confused with a syntax error.
#: The em-dash is written as an ESCAPE, not as a literal byte: this test file
#: is itself subject to the 7-bit rule the hook enforces, and a literal here
#: would make tests/test_ascii_hygiene.py fail on the module that proves the
#: guard works.
NON_ASCII_SOURCE = '"""A docstring with an em-dash \u2014 in it."""\n'

#: The head of the message `tools/ascii_check.py` prints. Asserted for the same
#: reason MARKER is above: it proves OUR tool spoke, not some bystander.
ASCII_MARKER = "ASCII VIOLATION"


def run_script(
    script: Path, stdin_text: str, cwd: Path, argv: list[str]
) -> subprocess.CompletedProcess:
    """Run ``script`` as a real subprocess with ``argv`` appended.

    Both hooks are processes to the harness, and both properties under test -
    an exit code and what reaches stderr - are invisible from inside the
    interpreter doing the asserting.
    """
    return subprocess.run(
        [sys.executable, str(script), *argv],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
    )


def posttooluse_commands() -> list[str]:
    """Every ``PostToolUse`` hook command line in ``.claude/settings.json``.

    The settings file is parsed rather than grepped. A single-backslash Windows
    path makes that file invalid JSON, which registers no hooks at all and
    warns about nothing - so a test that merely searched the text would report
    on a file the harness had already given up on.
    """
    settings = json.loads(SETTINGS.read_text(encoding="ascii"))
    commands = []
    for entry in settings["hooks"]["PostToolUse"]:
        for hook in entry["hooks"]:
            commands.append(hook["command"])
    return commands


def test_the_ascii_hook_script_exists_and_is_not_empty() -> None:
    assert ASCII_HOOK.is_file(), f"the ascii hook script is missing: {ASCII_HOOK}"
    assert ASCII_HOOK.stat().st_size > 0, "the ascii hook script is empty"


def test_the_posttooluse_wiring_passes_no_arguments() -> None:
    """The premise of the OPS-67 decision, checked against the real settings."""
    commands = posttooluse_commands()

    assert commands, "no PostToolUse hook commands found - the parse or the key is wrong"

    scripts_seen = []
    for command in commands:
        tokens = shlex.split(command)
        assert len(tokens) == 2, (
            "a PostToolUse hook command now carries arguments, so the OPS-67 "
            "decision to ignore argv in these hooks rests on a premise that is "
            f"no longer true. Re-open it. Command: {command!r}"
        )
        scripts_seen.append(tokens[1])

    joined = " ".join(scripts_seen)
    assert "tools/ascii_check.py" in joined, (
        f"ascii_check.py is no longer wired as a PostToolUse hook: {scripts_seen!r}"
    )
    assert "tools/syntax_check_hook.py" in joined, (
        f"syntax_check_hook.py is no longer wired as a PostToolUse hook: {scripts_seen!r}"
    )


@pytest.mark.parametrize(
    ("script_name", "script"),
    [("syntax_check_hook.py", HOOK), ("ascii_check.py", ASCII_HOOK)],
)
def test_each_posttooluse_hook_records_its_argv_decision(
    script_name: str, script: Path
) -> None:
    """The reason lives in the module, per OPS-67 criterion 1."""
    text = script.read_text(encoding="ascii")

    assert ARGV_DECISION_ANCHOR in text, (
        f"tools/{script_name} no longer explains why it ignores argv. A later "
        "reader cannot tell a decision from an unexamined default without it."
    )
    assert "OPS-67" in text, f"tools/{script_name} no longer cites the item that decided this"


def test_an_unknown_argument_does_not_change_the_syntax_hook(tmp_path: Path) -> None:
    """It still exits 0 AND still reports - the flag is ignored, not obeyed."""
    subject = write_subject(tmp_path, f"{STEM}_argv.py", BROKEN_SOURCE)

    result = run_script(HOOK, payload_for(subject), tmp_path, UNKNOWN_ARGV)

    assert result.returncode == 0, (
        f"an unknown argument made the syntax hook exit {result.returncode}, "
        "which would wedge the session it ran in: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert MARKER in result.stderr, (
        "an unknown argument silenced the syntax hook's report, so the flag was "
        f"obeyed rather than ignored: stderr={result.stderr!r}"
    )


def test_an_unknown_argument_does_not_change_the_ascii_hook(tmp_path: Path) -> None:
    """Same contract, the sibling hook. See this section's header for why here."""
    subject = tmp_path / f"{STEM}_argv_ascii.py"
    subject.write_text(NON_ASCII_SOURCE, encoding="utf-8")

    result = run_script(ASCII_HOOK, payload_for(subject), tmp_path, UNKNOWN_ARGV)

    assert result.returncode == 0, (
        f"an unknown argument made the ascii hook exit {result.returncode}, "
        "which would wedge the session it ran in: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert ASCII_MARKER in result.stderr, (
        "an unknown argument silenced the ascii hook's report, so the flag was "
        f"obeyed rather than ignored: stderr={result.stderr!r}"
    )


def test_the_ascii_hook_says_nothing_about_an_unknown_argument(tmp_path: Path) -> None:
    """A clean subject plus a bad flag draws NO usage complaint.

    The negative matters because a usage message on stderr from a PostToolUse
    hook is noise injected into the operator's session on every edit, and the
    hook that nags gets disabled.
    """
    subject = write_subject(tmp_path, f"{STEM}_argv_clean.py", CLEAN_SOURCE)

    result = run_script(ASCII_HOOK, payload_for(subject), tmp_path, UNKNOWN_ARGV)

    assert result.returncode == 0, f"exit was {result.returncode}, not 0"
    assert result.stderr == "", f"the ascii hook complained about argv: {result.stderr!r}"
    assert result.stdout == "", f"the ascii hook wrote to stdout: {result.stdout!r}"
