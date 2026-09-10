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
        """Scoped to HOOK findings, and it was widened to this deliberately.

        Until ``OPS-70`` this asserted ``report.ok``, which was the same thing
        while the guard read nothing but ``hooks.*``. Once the guard also read
        ``permissions.*``, a bare ``report.ok`` here would go red for a
        permission rule under a test named for hook commands - a true verdict
        answering a different question from the one its name asks, which is
        precisely the defect ``OPS-70`` was filed about. So the findings are
        filtered to the ones that are not about a permission rule, and the
        permission property has its own named test below.
        """
        report = hook_command_guard.check_repo()
        assert report.ran, report.reason
        hook_findings = [f for f in report.findings if f.location is None]
        assert hook_findings == [], (
            "a tracked hook command names an absolute path. Such a hook FIRES, "
            "SUCCEEDS, and answers about whatever tree that path points at - "
            "which in a clone or a git worktree is the WRONG tree, reported "
            "without a word of warning:\n" + report.format()
        )


# ---------------------------------------------------------------------------
# OPS-70: the guard also reads permissions.*
#
# The defect OPS-70 is about is one level up from OPS-61's. This module walked
# hooks.* and printed OK while three entries twenty lines away in the same
# document named an absolute repository root. The verdict was TRUE and it
# answered a narrower question than the word OK invites a reader to assume.
#
# Measured for OPS-70 and recorded here because a caveat that lives only in a
# chat log is a lie in the artifact: the permission matcher does NOT expand
# $CLAUDE_PROJECT_DIR. Read and Edit rule content is gitignore syntax with four
# anchors - //path from the filesystem root, ~/path from the home directory,
# /path from the settings source, and a bare or ./-led path from the working
# directory - and no environment variable is substituted into any of them.
# Neither source behind that is an observation of a MATCH on this machine, and
# the reason is written into .claude/settings.json's own $comment.
# ---------------------------------------------------------------------------

#: Permission rules that name no absolute root. The first three are the
#: documented portable anchors - a single leading slash anchors at the SETTINGS
#: SOURCE and is not an absolute path, which is the one place the permission
#: grammar and the hook-command grammar disagree; the last two are rules that
#: carry no path at all, which a scanner must not invent a finding for.
CLEAN_PERMISSION_RULES = (
    "Edit(/src/**/*.py)",
    "Read(docs/**)",
    "Write(./ops/runtime/**)",
    "Bash(python -m pytest*)",
    "WebFetch",
)

#: Absolute roots that are NOT this tree's own string, in permission-rule
#: shape. Same non-vacuity requirement as FOREIGN_ABSOLUTE_COMMANDS above: a
#: guard that only knows C:/Lanternlight is scoped to C:/Lanternlight.
#:
#: The POSIX-shaped entry is written with the DOUBLE leading slash on purpose.
#: ``Read(/opt/elsewhere/**)`` would be settings-source-anchored and portable,
#: so planting it here as a needle would be asserting that the recommended fix
#: is the defect.
FOREIGN_ABSOLUTE_RULES = (
    ("absolute-drive-root", "Edit(D:/Elsewhere/**)"),
    ("absolute-drive-root", "Read(D:\\Elsewhere\\**)"),
    ("absolute-permission-root", "Write(//fileserver/share/repo/**)"),
    ("absolute-permission-root", "Read(//opt/elsewhere/repo/**)"),
)


def _permissions(section: str, *rules: str) -> str:
    """Render a synthetic settings blob carrying ``rules`` under ``section``.

    The blob always carries one clean hook command as well. Without it the
    ``no-commands`` finding fires and every assertion about ``report.ok`` in
    this section would be testing that finding instead of the permission scan -
    a test that goes red for the wrong reason is not a test of what it names.
    """
    return json.dumps(
        {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": CLEAN_COMMANDS[0]}]}
                ]
            },
            "permissions": {section: list(rules)},
        }
    )


class TestThePermissionScanPositiveControl:
    """A scanner that fell back to reporting nothing passes every negative
    control by accident. Only a clean blob it must call OK, over a non-empty
    rule list, catches that.
    """

    def test_clean_permission_rules_are_reported_ok(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", *CLEAN_PERMISSION_RULES)
        )
        assert report.ran, report.reason
        assert report.ok, report.format()

    def test_the_positive_control_actually_scanned_its_rules(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", *CLEAN_PERMISSION_RULES)
        )
        assert len(report.permission_rules_scanned) == len(CLEAN_PERMISSION_RULES), (
            "the walker did not reach every permission rule, so a clean verdict "
            f"covers less than it appears to: {report.permission_rules_scanned}"
        )

    def test_a_single_leading_slash_is_not_read_as_a_filesystem_root(self):
        """THE ONE PLACE THE TWO GRAMMARS DISAGREE, pinned so a later tidy-up
        cannot quietly unify them. ``python /opt/x/tool.py`` as a hook command
        is an absolute path and a finding; ``Read(/opt/x/**)`` as a permission
        rule is anchored at the settings source and is the portable form this
        item recommends. Reusing one scanner for both would report the fix as
        the defect.
        """
        rule_report = hook_command_guard.check_settings_text(
            _permissions("allow", "Read(/opt/elsewhere/repo/**)")
        )
        assert rule_report.ok, rule_report.format()

        command_report = hook_command_guard.check_settings_text(
            _settings("python /opt/elsewhere/repo/tool.py")
        )
        assert not command_report.ok, (
            "the same string stopped being a finding in a hook command, so "
            "this test no longer pins a disagreement: " + command_report.format()
        )

    def test_a_home_anchored_rule_is_not_reported(self):
        """``~/`` travels between clones. Whether a home-anchored permission
        rule is wanted is a different question from whose TREE a rule names,
        and this guard was measured for the second one only.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("deny", "Read(~/.ssh/**)")
        )
        assert report.ok, report.format()

    def test_a_settings_file_without_permissions_still_reads_its_hooks(self):
        """A missing permissions section is legitimate and is not a failure -
        unlike a missing hook corpus. The asymmetry is deliberate and the
        module docstring says why.
        """
        report = hook_command_guard.check_settings_text(_settings(*CLEAN_COMMANDS))
        assert report.ok, report.format()
        assert report.permission_rules_scanned == ()


class TestThePermissionScanNegativeControls:
    def test_each_foreign_absolute_root_is_caught(self):
        for expected_kind, rule in FOREIGN_ABSOLUTE_RULES:
            report = hook_command_guard.check_settings_text(_permissions("allow", rule))
            assert not report.ok, f"{rule!r} was not reported: {report.format()}"
            kinds = {finding.kind for finding in report.findings}
            assert expected_kind in kinds, f"{rule!r} -> {kinds}"

    def test_every_rule_section_is_read_not_only_allow(self):
        """deny and ask carry paths too, and additionalDirectories is a bare
        path rather than a Tool(content) rule.
        """
        for section, rule in (
            ("allow", "Edit(D:/Elsewhere/**)"),
            ("deny", "Read(D:/Elsewhere/**)"),
            ("ask", "Write(D:/Elsewhere/**)"),
            ("additionalDirectories", "D:/Elsewhere"),
        ):
            report = hook_command_guard.check_settings_text(_permissions(section, rule))
            assert not report.ok, f"permissions.{section} was not read"
            locations = {finding.location for finding in report.findings}
            assert f"permissions.{section}[0]" in locations, locations

    def test_the_finding_names_the_location_and_the_path_it_found(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Edit(D:/Elsewhere/**)")
        )
        offender = next(f for f in report.findings if f.kind.startswith("absolute-"))
        assert offender.location == "permissions.allow[0]"
        assert offender.path == "D:/Elsewhere/**"

    def test_the_reported_path_does_not_swallow_the_closing_parenthesis(self):
        """A guard that misquotes its own evidence teaches a reader to distrust
        the parts it got right. The rule's content is split out before the
        scan, so the trailing ``)`` is never part of the reported root.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Write(//fileserver/share/repo/**)")
        )
        offender = next(f for f in report.findings if f.kind.startswith("absolute-"))
        assert not offender.path.endswith(")"), offender.path

    def test_every_offending_rule_is_reported_not_just_the_first(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", *(rule for _, rule in FOREIGN_ABSOLUTE_RULES))
        )
        offenders = [f for f in report.findings if f.kind.startswith("absolute-")]
        assert len(offenders) == len(FOREIGN_ABSOLUTE_RULES), report.format()

    def test_a_malformed_permissions_section_is_reported_rather_than_skipped(self):
        for blob, expected in (
            ('{"hooks": {}, "permissions": "everything"}', "permissions"),
            ('{"hooks": {}, "permissions": {"allow": "Edit"}}', "permissions.allow"),
            ('{"hooks": {}, "permissions": {"allow": [17]}}', "permissions.allow[0]"),
        ):
            report = hook_command_guard.check_settings_text(blob)
            assert not report.ok, blob
            kinds = {finding.kind for finding in report.findings}
            assert "malformed" in kinds, f"{blob} -> {kinds}"
            locations = {finding.location for finding in report.findings}
            assert expected in locations, f"{blob} -> {locations}"


class TestThePinIsNarrowAndVisible:
    """The pin exists because OPS-70's measurement says these three rules are
    correct-but-primary-checkout-only and the recorded decision was to keep
    them. A pin that quietly widened into "any absolute rule is fine" would
    hand back the whole defect, so these tests hold it to exact strings.
    """

    def test_each_pinned_rule_passes_on_its_own(self):
        for rule in sorted(hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES):
            report = hook_command_guard.check_settings_text(_permissions("allow", rule))
            assert report.ok, f"{rule!r} is pinned but was reported: {report.format()}"

    def test_a_pinned_rule_is_named_in_the_report_rather_than_hidden(self):
        rule = sorted(hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES)[0]
        report = hook_command_guard.check_settings_text(_permissions("allow", rule))
        assert report.pinned_permission_rules == (rule,)
        assert rule in report.format(), report.format()

    def test_the_pin_is_by_exact_string_not_by_root(self):
        """A sibling rule under the SAME root, not itself pinned, is still a
        finding. Without this the pin would be a licence for the directory.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Bash(//C/Lanternlight/**)")
        )
        assert not report.ok, report.format()

    def test_a_pinned_rule_does_not_launder_an_unpinned_one_beside_it(self):
        rule = sorted(hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES)[0]
        report = hook_command_guard.check_settings_text(
            _permissions("allow", rule, "Edit(D:/Elsewhere/**)")
        )
        assert not report.ok, report.format()
        offenders = [f for f in report.findings if f.kind.startswith("absolute-")]
        assert len(offenders) == 1, report.format()
        assert offenders[0].path == "D:/Elsewhere/**"

    def test_every_pinned_rule_is_absolute_so_the_pin_cannot_creep(self):
        """A pin holding a rule that names no absolute root would be dead
        weight that reads like a decision.
        """
        for rule in hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES:
            content = hook_command_guard.split_permission_rule(rule)
            assert hook_command_guard.absolute_paths_in(content), rule


class TestTheLivePermissionRulesAreReached:
    """OPS-70 criterion 3. A clean verdict over an empty walk is the failure
    mode this whole module is written against, and the permission scan does not
    make an empty section fatal on its own - so the live corpus is pinned here
    instead.
    """

    def test_the_guard_reaches_the_real_permission_rules(self):
        report = hook_command_guard.check_repo()
        assert report.ran, report.reason
        assert len(report.permission_rules_scanned) >= 5, (
            "the guard reached fewer permission rules than this repository "
            f"declares: {report.permission_rules_scanned}"
        )

    def test_every_pin_is_still_exercised_by_the_live_file(self):
        """A pin for a rule the file no longer carries is a stale decision
        nobody is re-reading. This turns that into a red suite.
        """
        report = hook_command_guard.check_repo()
        assert set(report.pinned_permission_rules) == set(
            hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES
        ), (
            "the pinned set and the live file have drifted apart: pinned="
            f"{sorted(hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES)} "
            f"exercised={sorted(report.pinned_permission_rules)}"
        )

    def test_no_unpinned_permission_rule_names_an_absolute_path(self):
        report = hook_command_guard.check_repo()
        assert report.ran, report.reason
        offenders = [
            f
            for f in report.findings
            if f.kind.startswith("absolute-") and f.location is not None
        ]
        assert offenders == [], (
            "a tracked permission rule names an absolute root that is not "
            "pinned. Such a rule matches in the checkout it names and nowhere "
            "else, and the permission matcher does not expand "
            "$CLAUDE_PROJECT_DIR:\n" + report.format()
        )


# ---------------------------------------------------------------------------
# OPS-70 REPAIR: what an independent refuting pass found in the OPS-70 work.
#
# Five defects, each reproduced against the guard BEFORE it was changed, and
# each pinned here. Four were bypasses or inconsistencies in the permission
# scan; the fifth is the one that matters most, because it was not a bug in
# what the guard CHECKS but a false statement in what the guard SAYS.
#
# The refutation itself is recorded rather than only its outcome, because a
# regression test whose reason lives in a chat log is a test a later reader
# deletes as mysterious:
#
# 1. ``Read(//C/Evil/**)`` with a TRAILING SPACE was not reported.
#    ``split_permission_rule`` required ``rule.endswith(")")`` and returned the
#    whole rule unsplit when it did not, after which the filesystem-root
#    pattern - anchored at the start of the content - could never match past
#    the leading ``Read(``. The function's own docstring promised the opposite,
#    that an unrecognised shape "is still scanned, instead of being silently
#    exempted", so the docstring was false as written.
# 2. ``Read(\\srv\share\**)`` was not reported. The permission pattern tuple
#    omitted the only backslash-aware pattern, so the UNC spelling the hook
#    scan already reported went unreported one grammar over - and that blind
#    spot was not in the guard's own disclosed list either.
# 3. ``Bash(cd //C/Evil && ls)`` was missed while ``Bash(cd C:/Evil && ls)``
#    was caught: the same rule, the same tree, two verdicts decided by which
#    pattern happened to carry a ``^`` anchor.
# 4. The module asserted "Measured for OPS-70" in three places, one of them
#    INSIDE the finding text a reader is handed at the moment the guard fires,
#    and it hedged nowhere. Nothing on this machine ever observed a permission
#    rule matching - the claim rests on published documentation and on the
#    shipped client's rule-anchoring code, and the session that wrote it ran in
#    bypass permissions mode, where a did-it-prompt probe cannot tell a MATCHED
#    rule from a BYPASSED one.
# 5. Two sentences in ``.claude/settings.json``'s own ``$comment`` stated the
#    same class of claim flat, outside the attribution the same paragraph
#    carries elsewhere.
#
# NOTHING HERE MUTATES THE LIVE SETTINGS FILE. The guard already takes a
# supplied text through :func:`check_settings_text` and a supplied root through
# :func:`check_repo`, so every planted needle goes into a synthetic blob and the
# live file is only ever READ. That is deliberate: this repository printed a
# green suite twice on 2026-09-08 from a mutation that never applied, and a test
# that does not write cannot fail that way.
# ---------------------------------------------------------------------------


class TestATrailingSpaceDoesNotExemptARule:
    """DEFECT 1. Whitespace around a rule must not decide whether it is read.

    A settings file is hand-edited, and a trailing space is the single most
    likely thing to survive a hand edit unnoticed. A guard that a stray space
    turns off is a guard that reports OK over the exact file a careless edit
    produced.
    """

    def test_a_rule_with_a_trailing_space_is_still_split(self):
        assert (
            hook_command_guard.split_permission_rule("Read(//C/Evil/**) ")
            == "//C/Evil/**"
        )

    def test_a_rule_with_a_trailing_space_is_still_reported(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Read(//C/Evil/**) ")
        )
        assert not report.ok, report.format()
        offenders = [f for f in report.findings if f.kind.startswith("absolute-")]
        assert [f.path for f in offenders] == ["//C/Evil/**"], report.format()

    def test_a_leading_space_is_handled_the_same_way(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", " Read(//C/Evil/**)")
        )
        assert not report.ok, report.format()

    def test_an_unclosed_rule_is_scanned_rather_than_exempted(self):
        """The split docstring's promise, in its own words: a shape this
        function does not recognise is still scanned, instead of being silently
        exempted. Pinned as behaviour so the promise cannot go false again
        while the sentence stays.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Read(//C/Evil/**")
        )
        assert not report.ok, report.format()

    def test_a_pinned_rule_with_a_trailing_space_is_not_laundered_by_the_pin(self):
        """The pin is by EXACT string, so a spaced copy of a pinned rule is a
        different string and must be a finding. Without this, whitespace would
        become a way to smuggle a rule past the pin in EITHER direction.
        """
        rule = sorted(hook_command_guard.PINNED_ABSOLUTE_PERMISSION_RULES)[0] + " "
        report = hook_command_guard.check_settings_text(_permissions("allow", rule))
        assert not report.ok, report.format()


class TestTheBackslashUncSpellingIsRead:
    """DEFECT 2. The hook scan reports three spellings - drive root, UNC root,
    POSIX root. The permission scan reported two and omitted the only
    backslash-aware one, so a share written the Windows way was invisible.
    """

    def test_a_unc_rule_spelled_with_backslashes_is_reported(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Read(\\\\srv\\share\\**)")
        )
        assert not report.ok, report.format()
        offenders = [f for f in report.findings if f.kind.startswith("absolute-")]
        assert offenders, report.format()
        assert offenders[0].path == "\\\\srv\\share\\**", offenders[0].path

    def test_both_unc_spellings_reach_the_same_verdict(self):
        """Two spellings of one thing must not disagree. The forward-slash form
        was already reported; this pins that the pair moves together.
        """
        for rule in ("Write(//srv/share/**)", "Write(\\\\srv\\share\\**)"):
            report = hook_command_guard.check_settings_text(_permissions("allow", rule))
            assert not report.ok, f"{rule!r} was not reported: {report.format()}"

    def test_the_backslash_share_is_reported_in_every_section(self):
        for section in hook_command_guard.PERMISSION_RULE_SECTIONS:
            rule = (
                "\\\\srv\\share"
                if section == "additionalDirectories"
                else "Read(\\\\srv\\share\\**)"
            )
            report = hook_command_guard.check_settings_text(_permissions(section, rule))
            assert not report.ok, f"permissions.{section} missed {rule!r}"


class TestThePathScanIsUnanchoredAndConsistent:
    """DEFECT 3. ``Bash(cd C:/Evil && ls)`` was a finding and
    ``Bash(cd //C/Evil && ls)`` was not, because the drive pattern scanned the
    whole content while the filesystem-root pattern was anchored with ``^``.

    The decision recorded by these tests: a path inside a rule's argument is IN
    SCOPE wherever it appears. Both spellings now report. The direction was
    chosen because narrowing would have DELETED coverage that already existed,
    and because this module's question - does a rule name a root the running
    tree cannot verify is its own - is answered the same way by a root buried
    in a command as by a root at the front of a glob.
    """

    def test_both_spellings_inside_a_bash_rule_agree(self):
        verdicts = {}
        for rule in ("Bash(cd //C/Evil && ls)", "Bash(cd C:/Evil && ls)"):
            report = hook_command_guard.check_settings_text(_permissions("allow", rule))
            verdicts[rule] = report.ok
        assert set(verdicts.values()) == {False}, (
            "the two spellings disagree, which is the OPS-70 refutation's "
            f"defect 3 back again: {verdicts}"
        )

    def test_a_root_after_a_leading_glob_is_reported(self):
        """Not only the Bash case: any content whose absolute root is not at
        character zero was previously exempt from the filesystem-root pattern.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Read(**|//C/Evil/**)")
        )
        assert not report.ok, report.format()

    def test_a_url_inside_a_rule_is_not_read_as_a_filesystem_root(self):
        """The one shape excluded from the widening, by lookbehind. Reporting
        ``https://host/x`` as a filesystem root would be a false statement
        about what was found, and a guard that misquotes its evidence teaches a
        reader to distrust the parts it got right.
        """
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Bash(curl https://example.invalid/x/y)")
        )
        assert report.ok, report.format()

    def test_the_decision_is_disclosed_where_a_reader_will_find_it(self):
        """Consistency without disclosure is half the requirement. The scanner
        says in its own docstring that the scan is unanchored and what that
        costs.
        """
        doc = hook_command_guard.absolute_roots_in_permission_content.__doc__ or ""
        assert "UNANCHORED" in doc, doc
        assert "Bash" in doc, doc


class TestTheMatcherClaimCarriesItsProvenance:
    """DEFECT 4, and the important one.

    The module said "Measured for OPS-70" three times about a fact nobody
    measured, and one of those three was inside the finding text a reader is
    handed at the moment the guard fires. This repository's rule is that a
    claim carrying its source or its instant is fine and a claim stated FLAT is
    a defect; printing false provenance at failure time is the worst possible
    place to state one flat, because the reader has no way to check it and
    every reason to believe a guard that just caught something real.
    """

    def test_the_provenance_says_plainly_that_it_is_an_inference(self):
        text = hook_command_guard.MATCHER_CLAIM_PROVENANCE
        lowered = text.lower()
        assert "inference" in lowered, text
        assert "not an observation" in lowered, text
        assert "bypass permissions" in lowered, text

    def test_the_provenance_names_both_of_its_actual_sources(self):
        lowered = hook_command_guard.MATCHER_CLAIM_PROVENANCE.lower()
        assert "documentation" in lowered, lowered
        assert "rule-anchoring code" in lowered, lowered

    def test_the_user_facing_finding_does_not_claim_a_measurement(self):
        report = hook_command_guard.check_settings_text(
            _permissions("allow", "Edit(D:/Elsewhere/**)")
        )
        offender = next(f for f in report.findings if f.kind.startswith("absolute-"))
        assert "measured" not in offender.detail.lower(), offender.detail
        assert hook_command_guard.MATCHER_CLAIM_PROVENANCE in offender.detail, (
            "the finding text does not route through the one place the "
            "provenance is written, so the two can drift apart:\n" + offender.detail
        )

    def test_no_permission_finding_anywhere_claims_it_was_measured(self):
        """Every section, so a second copy of the sentence cannot hide in one
        of them.
        """
        for blob in (
            _permissions("allow", "Edit(D:/Elsewhere/**)"),
            _permissions("deny", "Read(//srv/share/**)"),
            _permissions("ask", "Write(D:/Elsewhere/**)"),
            _permissions("additionalDirectories", "D:/Elsewhere"),
        ):
            report = hook_command_guard.check_settings_text(blob)
            for finding in report.findings:
                assert "measured for ops-70" not in finding.detail.lower(), finding

    def test_the_module_docstring_discloses_the_same_thing(self):
        doc = hook_command_guard.__doc__ or ""
        lowered = doc.lower()
        assert "bypass permissions" in lowered, (
            "the module docstring states the matcher claim without saying the "
            "session that established it could not have observed a match"
        )
        assert "not an observation" in lowered, doc


class TestTheSettingsCommentDoesNotOverclaim:
    """DEFECT 5. Two sentences in the live ``$comment`` stated the matcher
    claim and its consequence flat, outside the attribution the same paragraph
    carries elsewhere.

    Read-only. The comment is the operator-facing record of an OPS-70 decision,
    so these pin its content positively as well as negatively - a test that
    only asserts an absence would go green if somebody deleted the paragraph.
    """

    @staticmethod
    def _comment() -> str:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        comment = data.get("$comment")
        assert isinstance(comment, str) and comment.strip(), (
            "the settings file carries no $comment, so every assertion below "
            "would be about nothing"
        )
        return comment

    def test_the_windows_normalisation_sentence_is_attributed(self):
        comment = self._comment()
        assert "matcher normalises a path to POSIX form" in comment, (
            "the sentence these tests pin has been deleted rather than "
            "attributed; restore it with its sources named"
        )
        assert (
            "On Windows the matcher normalises a path to POSIX form" not in comment
        ), (
            "the normalisation claim is stated flat again, outside the "
            "attribution the same paragraph carries elsewhere"
        )
        assert "non-observational sources" in comment

    def test_the_match_consequence_is_not_stated_flat(self):
        comment = self._comment()
        assert "they match in this checkout and nowhere else" not in comment, (
            "the consequence is stated as observed fact again, in tension "
            "with the same paragraph admitting a did-it-prompt test cannot "
            "distinguish MATCHED from BYPASSED"
        )
        assert "expected to match in this checkout and nowhere else" in comment

    def test_the_comment_still_names_what_could_not_be_measured(self):
        comment = self._comment()
        assert "bypass permissions mode" in comment
        assert "NEITHER IS AN OBSERVATION OF A MATCH ON THIS MACHINE" in comment

    def test_the_comment_was_not_shortened_away(self):
        """CLAUDE.md's terseness rule is for chat and never for a committed
        artifact. An attribution pass that trimmed the paragraph would have
        destroyed the record it was meant to correct.
        """
        comment = self._comment()
        assert len(comment) > 6000, len(comment)
