"""No tracked hook command may name an absolute path - ``OPS-61`` criterion 3.

THE PROPERTY, in one sentence: no hook command in ``.claude/settings.json``
names an absolute filesystem path, so every hook reaches its script through the
harness-provided project root or a repo-relative path and therefore resolves the
tree it is actually running in.

WHY A SECOND GUARD, AND WHAT IT ADDS
------------------------------------
``tests/test_no_hardcoded_home_path.py`` (``OPS-38``) is this file's SIBLING and
neither replaces the other. That guard matches the SHAPE of any user home
directory under any account name, and it asks whether a published string carries
machine-specific IDENTITY. ``C:/Lanternlight`` carries no account name, so the
six hook commands ``OPS-61`` measured passed it cleanly while every one of them
named an absolute repository root.

This file asks a different question: does a hook command name a root the running
tree cannot verify is its own. The two properties are independent - a path can
fail either check without failing the other - and the measurement behind this
one is in ``ROADMAP.md`` item ``OPS-61``: in a real clone at a foreign path, such
a hook FIRES, SUCCEEDS, and answers about the ORIGINAL tree without saying so.
A hook that does not fire reports nothing; this one looks like coverage.

THE LIVE-TREE TEST IS EXPECTED TO BE RED UNTIL ``.claude/settings.json`` IS FIXED
--------------------------------------------------------------------------------
:class:`TestTheLiveSettingsFileIsClean` is the assertion that actually closes
``OPS-61``, and it was written BEFORE the fix, deliberately, per this
repository's TDD rule - a guard nobody has watched fail is decoration. On the
tree this file was added to, that class fails with six findings and every other
test here passes. A cold reader finding it red has found the defect, not a
broken test file.

NON-VACUITY IS PROVED BY CONTROLS THAT ARE NOT THIS TREE'S OWN STRING
---------------------------------------------------------------------
``OPS-61`` criterion 3 asks for the guard to be "proved non-vacuous by embedding
a different absolute root and watching it go red", because ``OPS-38`` had to
generalise twice - first past this machine's literal account name, then past one
family of values - and a guard hardened against one string is scoped to one
string. So the negative controls here embed a foreign drive root, a UNC share
and a POSIX root, in synthetic settings blobs that have nothing to do with this
repository, and the positive control is a synthetic blob of CLEAN commands: a
reader that silently fell back to something permissive would pass every negative
control by accident and cannot pass the positive one.

The POSIX control is deliberately NOT under a home directory. A home-shaped
literal in a tracked file is exactly what the sibling guard reports, and this
file is inside the corpus that guard scans - a needle planted for one guard must
not be a leak for another.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import hook_command_guard  # noqa: E402

SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"


def _settings(*commands: str) -> str:
    """Render a synthetic settings blob carrying ``commands`` as hooks.

    One command per event, so a finding's ``event`` field is unambiguous. Built
    through :func:`json.dumps` rather than typed as a JSON string literal: a
    hand-typed blob with a stray backslash is the exact input that makes the
    real file unparseable, and a fixture that failed to parse would make every
    test using it pass or fail for the wrong reason.
    """
    events = ["PreToolUse", "PostToolUse", "SessionStart", "Stop", "UserPromptSubmit"]
    assert len(commands) <= len(events), "add another event name to the fixture"
    return json.dumps(
        {
            "hooks": {
                events[i]: [{"hooks": [{"type": "command", "command": command}]}]
                for i, command in enumerate(commands)
            }
        }
    )


#: Commands written the way ``OPS-61`` measured to actually work. The harness
#: expands ``$CLAUDE_PROJECT_DIR`` itself, so a command through it runs the
#: CLONE's own script - measured in a real clone at a foreign path.
CLEAN_COMMANDS = (
    "python $CLAUDE_PROJECT_DIR/ops/inbox_watch.py",
    "pythonw $CLAUDE_PROJECT_DIR/tools/ascii_check.py --quiet",
    "python ops/inbox_watch.py --on-prompt",
    "pythonw ./tools/syntax_check_hook.py",
    "python %CLAUDE_PROJECT_DIR%/ops/stop_audit.py --stop-hook",
)

#: Absolute roots that are NOT this tree's own string. Criterion 3's
#: non-vacuity requirement: a guard that only knows ``C:/Lanternlight`` is
#: scoped to ``C:/Lanternlight``.
#:
#: The POSIX entry uses ``/opt`` on purpose - see the module docstring on why a
#: home-shaped needle would be a leak for the sibling guard.
FOREIGN_ABSOLUTE_COMMANDS = (
    ("absolute-drive-root", "python D:/Elsewhere/tool.py"),
    ("absolute-drive-root", "python D:\\Elsewhere\\tool.py"),
    ("absolute-unc-root", "python //fileserver/share/repo/tool.py"),
    ("absolute-unc-root", "python \\\\fileserver\\share\\repo\\tool.py"),
    ("absolute-posix-root", "python /opt/elsewhere/repo/tool.py"),
)


class TestThePositiveControl:
    """A reader that fell back to something permissive passes every negative
    control by accident. Only a clean blob it must call OK catches that.
    """

    def test_a_blob_of_clean_commands_is_reported_ok(self):
        report = hook_command_guard.check_settings_text(_settings(*CLEAN_COMMANDS))
        assert report.ran, report.reason
        assert report.ok, report.format()

    def test_the_positive_control_actually_scanned_its_commands(self):
        """OK over nothing is not OK. Pin that the walk reached all five."""
        report = hook_command_guard.check_settings_text(_settings(*CLEAN_COMMANDS))
        assert len(report.commands_scanned) == len(CLEAN_COMMANDS), (
            "the walker did not reach every hook command, so a clean verdict "
            f"covers less than it appears to: {report.commands_scanned}"
        )

    def test_a_windows_style_switch_is_not_read_as_a_posix_root(self):
        """``/F`` shares the shape of a POSIX root and is not one. This
        repository already documents that switch by name.
        """
        report = hook_command_guard.check_settings_text(
            _settings("python ops/kill_helper.py /F 1234")
        )
        assert report.ok, report.format()


class TestTheNegativeControls:
    """Criterion 3: embed a DIFFERENT absolute root and watch it go red."""

    def test_each_foreign_absolute_root_is_caught(self):
        missed = []
        for expected_kind, command in FOREIGN_ABSOLUTE_COMMANDS:
            report = hook_command_guard.check_settings_text(_settings(command))
            kinds = {f.kind for f in report.findings}
            if report.ok or expected_kind not in kinds:
                missed.append((command, sorted(kinds)))
        assert not missed, (
            "the guard is scoped to this tree's own root - a foreign absolute "
            f"root went unreported: {missed}"
        )

    def test_the_finding_names_the_event_and_the_path_it_found(self):
        report = hook_command_guard.check_settings_text(
            _settings("python D:/Elsewhere/tool.py")
        )
        assert not report.ok
        finding = report.findings[0]
        assert finding.event == "PreToolUse", finding
        assert finding.path == "D:/Elsewhere/tool.py", finding
        assert "D:/Elsewhere/tool.py" in finding.detail

    def test_it_also_catches_the_historical_defect_string(self):
        """The shape ``OPS-61`` actually measured. Kept alongside the foreign
        roots rather than instead of them: catching the original and catching a
        generalisation are two different facts.
        """
        report = hook_command_guard.check_settings_text(
            _settings("python C:/Lanternlight/ops/inbox_watch.py")
        )
        assert not report.ok, report.format()

    def test_an_absolutely_named_interpreter_is_also_a_finding(self):
        """DECIDED ON PURPOSE, see the guard module's docstring: an absolute
        INTERPRETER is the same class of defect - ``OPS-38`` recorded four hook
        commands that carried one - and no string can say which absolute path
        was meant to be a repo root.
        """
        report = hook_command_guard.check_settings_text(
            _settings("D:/Tools/Python/python.exe ops/inbox_watch.py")
        )
        assert not report.ok, report.format()

    def test_every_offending_command_is_reported_not_just_the_first(self):
        report = hook_command_guard.check_settings_text(
            _settings(
                "python D:/Elsewhere/one.py",
                "python E:/Elsewhere/two.py",
                "python /opt/elsewhere/three.py",
            )
        )
        assert len(report.findings) == 3, report.format()


class TestTheDeliberateBlindSpots:
    """Each is written up in the guard module's docstring. Measured here so a
    later reader can tell a decision from an oversight.
    """

    def test_a_drive_relative_path_is_not_reported(self):
        report = hook_command_guard.check_settings_text(_settings("python C:ops/x.py"))
        assert report.ok, report.format()

    def test_a_percent_encoded_path_is_not_reported(self):
        report = hook_command_guard.check_settings_text(
            _settings("python D%3A%5CElsewhere%5Ctool.py")
        )
        assert report.ok, report.format()

    def test_a_url_is_not_reported_as_a_unc_share(self):
        report = hook_command_guard.check_settings_text(
            _settings("python ops/fetch.py https://example.invalid/x/y")
        )
        assert report.ok, report.format()


class TestDidNotRunIsNeverAPass:
    def test_a_missing_settings_file_reports_did_not_run(self, tmp_path):
        report = hook_command_guard.check_repo(repo_root=tmp_path)
        assert not report.ran
        assert not report.ok, "did not run must never be reported as a pass"
        assert not report.findings
        assert "does not exist" in report.reason

    def test_a_file_with_no_hook_command_is_a_finding_not_a_pass(self):
        report = hook_command_guard.check_settings_text(json.dumps({"hooks": {}}))
        assert report.ran
        assert not report.ok, (
            "an empty finding list over an empty corpus is the same output as a "
            "clean tree, which is the defect this guard exists to close"
        )
        assert [f.kind for f in report.findings] == ["no-commands"]

    def test_an_unparseable_settings_file_is_a_finding_not_an_exception(self):
        report = hook_command_guard.check_settings_text('{"hooks": {,}}')
        assert report.ran
        assert not report.ok
        assert [f.kind for f in report.findings] == ["unparseable"]

    def test_a_malformed_hook_entry_is_reported_rather_than_skipped(self):
        blob = json.dumps(
            {
                "hooks": {
                    "PreToolUse": [{"hooks": [{"type": "command"}]}],
                    "Stop": "not-a-list",
                }
            }
        )
        report = hook_command_guard.check_settings_text(blob)
        assert not report.ok
        assert {f.kind for f in report.findings} == {"malformed"}, report.format()


class TestTheEntryPointHonoursItsArguments:
    """``OPS-64`` is filed against a sibling guard for accepting any argv and
    silently ignoring it, which makes a mistyped invocation look like a clean
    run. This one refuses instead.
    """

    def test_unexpected_arguments_exit_two_rather_than_being_ignored(self):
        assert hook_command_guard.main(["--pretend-this-does-something"]) == 2

    def test_no_arguments_runs_the_real_check(self, capsys):
        code = hook_command_guard.main([])
        captured = capsys.readouterr().out
        assert "hook command guard:" in captured
        assert code in (0, 1), code


class TestTheLiveSettingsFileParses:
    """``CLAUDE.md``: a single-backslash Windows path makes this file invalid
    JSON, and then NOTHING parses, no hook registers, and nothing warns you.
    """

    def test_the_settings_file_exists_and_parses(self):
        assert SETTINGS_PATH.is_file(), f"{SETTINGS_PATH} is missing"
        json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

    def test_the_guard_reaches_the_real_hook_commands(self):
        """A clean verdict over an empty walk is the failure mode. Pin that the
        real file yields commands at all, separately from whether they pass.
        """
        report = hook_command_guard.check_repo()
        assert report.ran, report.reason
        assert len(report.commands_scanned) >= 5, (
            "the guard reached fewer hook commands than this repository "
            f"declares: {report.commands_scanned}"
        )


class TestTheLiveSettingsFileIsClean:
    """THIS IS THE ASSERTION THAT CLOSES ``OPS-61`` CRITERION 3, and it is
    EXPECTED TO BE RED on the tree this file was added to - six hook commands
    each name ``C:/Lanternlight``. Written before the fix on purpose: a guard
    nobody has watched fail is decoration. It goes green when
    ``.claude/settings.json`` reaches every script through
    ``$CLAUDE_PROJECT_DIR`` or a repo-relative path.
    """

    def test_no_hook_command_names_an_absolute_path(self):
        report = hook_command_guard.check_repo()
        assert report.ran, report.reason
        assert report.ok, (
            "a tracked hook command names an absolute path. Such a hook FIRES, "
            "SUCCEEDS, and answers about whatever tree that path points at - "
            "which in a clone or a git worktree is the WRONG tree, reported "
            "without a word of warning:\n" + report.format()
        )
