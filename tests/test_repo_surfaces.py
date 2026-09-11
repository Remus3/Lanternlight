"""Guards on the public-facing surfaces added 2026-09-06.

These exist because a refutation pass observed that `CITATION.cff`, the CI
workflow, both issue templates, the `moon_sync_inbox/` ignore rule and the
`attribution` keys in `.claude/settings.json` all shipped with **zero new
tests**. Nothing in the suite went red if any of them was reverted, which makes
the unchanged collected count consistent with the work being real AND with it
being entirely untested. Here it was the latter.

Each test below guards a specific way one of those surfaces fails SILENTLY -
not merely that a file exists.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import _toolguard
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
CITATION = REPO_ROOT / "CITATION.cff"
GITIGNORE = REPO_ROOT / ".gitignore"


class TestTheWorkflowCannotSilenceItsOwnSummary:
    """`pytest.ini` already carries ``-q``. A second one makes it ``-qq``,
    which prints NO summary line and still exits 0 - a green tick with nothing
    behind it. That trap is documented in ``CLAUDE.md`` and it is exactly the
    kind of thing a later tidy-up adds back."""

    def test_the_workflow_runs_pytest_without_adding_a_quiet_flag(self):
        text = WORKFLOW.read_text(encoding="ascii")
        runs = re.findall(r"^\s*run:\s*(.+)$", text, re.MULTILINE)
        pytest_runs = [r for r in runs if "pytest" in r]
        assert pytest_runs, "no step in the workflow runs pytest at all"
        offenders = [
            r for r in pytest_runs if re.search(r"(?:^|\s)-q{1,2}(?:\s|$)", r)
        ]
        assert not offenders, (
            "a workflow step passes -q to pytest, which combines with the -q "
            f"already in pytest.ini to make -qq and print no summary: {offenders}"
        )

    def test_the_workflow_actually_invokes_the_suite(self):
        text = WORKFLOW.read_text(encoding="ascii")
        assert re.search(r"^\s*run:\s*python -m pytest\s*$", text, re.MULTILINE), (
            "no step runs `python -m pytest` bare; a workflow that only "
            "collects, or only runs a subset, is not the gate it claims to be"
        )


class TestTheTrailerRuleIsConfigurationNotMemory:
    """``CLAUDE.md`` forbids a Co-Authored-By trailer, and the harness injects
    one by default. Before 2026-09-06 the rule was enforced only by the agent
    remembering it, which failed repeatedly in a single session."""

    def test_settings_parses(self):
        # A single backslash in a Windows path makes this file invalid JSON, at
        # which point NO hook registers and nothing warns. Assert the parse
        # before asserting anything about the contents.
        json.loads(SETTINGS.read_text(encoding="ascii"))

    def test_both_attribution_keys_are_blanked(self):
        d = json.loads(SETTINGS.read_text(encoding="ascii"))
        assert d.get("attribution", {}).get("commit") == "", (
            "attribution.commit is not blank, so the harness will append a "
            "commit trailer that CLAUDE.md forbids"
        )
        assert d.get("attribution", {}).get("pr") == ""

    def test_the_deprecated_key_is_set_too(self):
        # attribution is the current key, includeCoAuthoredBy the deprecated
        # one. An older client reads ONLY the latter, so dropping it would
        # reintroduce the trailer silently on that client and nowhere else.
        d = json.loads(SETTINGS.read_text(encoding="ascii"))
        assert d.get("includeCoAuthoredBy") is False


class TestTheCitationPointsAtSomethingReal:
    def test_the_cited_version_has_a_matching_tag(self):
        text = CITATION.read_text(encoding="ascii")
        m = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
        assert m, "CITATION.cff declares no version"
        version = m.group(1).strip("'\"")
        try:
            tags = subprocess.run(
                ["git", "tag", "--list"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):  # pragma: no cover
            pytest.skip(_toolguard.skip_reason("git"))
        if tags.returncode != 0:
            pytest.skip("git tag failed")
        names = set(tags.stdout.split())
        if not names:
            pytest.skip("no tags in this checkout; a shallow clone has none")
        assert f"v{version}" in names, (
            f"CITATION.cff cites version {version!r} but no tag v{version} "
            f"exists. A citation pointing at a version nobody can check out is "
            f"worse than none. Tags present: {sorted(names)}"
        )

    def test_no_email_address_is_published(self):
        # The repo redacts operator identifiers everywhere else; a citation
        # file is not an exemption, and an address adds nothing to citability.
        text = CITATION.read_text(encoding="ascii")
        assert "@" not in text, "CITATION.cff carries an email address"


class TestTheCrossProjectInboxStaysIgnored:
    """`moon_sync_inbox/` is the sibling projects' note channel. It is not this
    project's, and an untracked note in it made two orphan tests fail before it
    was ignored - in a PUBLIC repo, one `git add -A` from being published."""

    def test_the_ignore_rule_is_present(self):
        assert "moon_sync_inbox/" in GITIGNORE.read_text(encoding="ascii")

    def test_git_agrees_the_directory_is_ignored(self):
        # The rule being in the file is not proof git honours it - a later
        # negation pattern could re-include it.
        try:
            proc = subprocess.run(
                ["git", "check-ignore", "-q", "moon_sync_inbox/probe.md"],
                cwd=REPO_ROOT,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):  # pragma: no cover
            pytest.skip(_toolguard.skip_reason("git"))
        assert proc.returncode == 0, (
            "git does not consider moon_sync_inbox/ ignored, whatever "
            ".gitignore appears to say"
        )
