"""The shared external-tool presence guard, and the end-of-run statement.

ROADMAP ``OPS-78``. Two halves are pinned here and they fail in different
ways, so they are tested separately:

1. ``tests/_toolguard.py`` turning an absent tool into a CLEAN SKIP whose
   reason names the tool, and into the RESOLVED PATH when the tool is present.
   The second half is the bidirectional discipline in ``docs/OPERATIONS.md``:
   a guard that only skips pins nothing down.
2. The end-of-run statement that counts those skips and says so. A skip is
   invisible in a green summary, which is exactly why ``OPS-78`` criterion 3
   exists.

WHY THE DECISIVE TESTS RUN A REAL PYTEST RATHER THAN CALLING THE FORMATTER.
The formatter returning the right list of strings does not prove pytest ever
calls it, and a hook that is never registered is decoration that passes its
own unit tests. So two tests here spawn ``python -m pytest`` over a throwaway
test file in ``tmp_path`` with ``-p _toolguard``, and read the child's stdout
for the banner: once where a test really skips through ``require``, and once
where a test skips for an unrelated reason. The banner must appear in the
first and must NOT appear in the second - a banner that always printed would
be a line nobody reads.

THE CHILD RUN IS DELIBERATELY NOT THIS SUITE. It is handed a single generated
file and never points at ``tests``. Running this repository's suite from
inside this repository's suite is the recursion ``tools/false_red_probe.py``
documents at length, and there is no reason to go near it: the claim under
test is that the hook fires, which one generated test proves as well as three
thousand real ones would.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "tests"))

import _toolguard  # noqa: E402  (sits beside this file in tests/)

TESTS_DIR = REPO_ROOT / "tests"


class _FakeReport:
    """A stand-in for a pytest skipped report, carrying only ``longrepr``.

    A real ``TestReport`` cannot be built without a running item, and the only
    field the counter reads is ``longrepr``. Faking exactly that keeps the
    counter's test honest about its own input shape rather than importing
    private pytest machinery that could change under it.
    """

    def __init__(self, longrepr: object) -> None:
        self.longrepr = longrepr


class TestTheSkipReasonNamesTheTool:
    """The reason is machine-readable, which is what makes the count possible."""

    def test_the_reason_carries_the_tool_name(self) -> None:
        reason = _toolguard.skip_reason("git")
        assert "git" in reason
        assert reason.startswith(_toolguard.SKIP_REASON_PREFIX)

    def test_the_reason_round_trips_back_to_the_tool(self) -> None:
        for tool in ("git", "bash", "ruff"):
            assert _toolguard.tool_from_reason(_toolguard.skip_reason(tool)) == tool

    def test_the_pytest_skipped_wrapper_does_not_break_the_round_trip(self) -> None:
        """pytest renders a skip as ``Skipped: <reason>``, not as the reason."""
        wrapped = "Skipped: " + _toolguard.skip_reason("git")
        assert _toolguard.tool_from_reason(wrapped) == "git"

    def test_an_unrelated_skip_names_no_tool(self) -> None:
        """The load-bearing negative: this suite skips for other reasons too.

        A counter that swept an ordinary skip in would announce a missing tool
        that is sitting on PATH, which is a false alarm in the one place a
        reader has no way to check.
        """
        assert _toolguard.tool_from_reason("Skipped: the game is not installed") is None
        assert _toolguard.tool_from_reason("") is None
        assert _toolguard.tool_from_reason(None) is None
        assert _toolguard.tool_from_reason(_toolguard.SKIP_REASON_PREFIX) is None


class TestRequireSkipsWhenTheToolIsAbsent:
    """The absent direction."""

    def test_an_absent_tool_skips_with_a_reason_naming_it(self, monkeypatch) -> None:
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: None)
        with pytest.raises(pytest.skip.Exception) as excinfo:
            _toolguard.require("git")
        assert "git" in str(excinfo.value)
        assert _toolguard.tool_from_reason(str(excinfo.value)) == "git"

    def test_the_skip_exception_is_not_swallowed_by_except_exception(self) -> None:
        """A skip built on ``Exception`` would be eaten by fail-soft code.

        This repository carries bare ``except Exception`` handlers on purpose -
        the conftest audit hook is one - and a guard whose skip they swallowed
        would become a test that passed without running anything. pytest's own
        ``Skipped`` derives from ``BaseException``; that is asserted here
        rather than assumed, because it is the property the guard depends on.
        """
        assert issubclass(pytest.skip.Exception, BaseException)
        assert not issubclass(pytest.skip.Exception, Exception)


class TestRequireReturnsAUsablePathWhenTheToolIsPresent:
    """The present direction - ``docs/OPERATIONS.md`` bidirectional discipline.

    A guard that skips cleanly when a tool is missing and does nothing when it
    is there is a negative assertion. These tests pin the other half: the guard
    hands back something the caller can actually run.
    """

    def test_a_present_tool_returns_its_resolved_path_and_does_not_skip(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _toolguard.shutil, "which", lambda name: "/somewhere/" + name
        )
        assert _toolguard.require("git") == "/somewhere/git"

    def test_the_returned_path_really_runs_the_tool(self) -> None:
        """The effect chosen is one only git can produce: its own version line.

        An exit code of zero would not do - ``docs/OPERATIONS.md`` says so in
        as many words. The string ``git version`` is written by git and by
        nothing else this test could have accidentally invoked.
        """
        git = _toolguard.require("git")
        completed = subprocess.run(
            [git, "--version"], capture_output=True, text=True, check=True
        )
        assert "git version" in completed.stdout


class TestTheCounterIsPerTool:
    """Counting is per tool, because the banner has to name which one."""

    def test_reports_are_counted_under_the_tool_they_name(self) -> None:
        reports = [
            _FakeReport(("f.py", 1, "Skipped: " + _toolguard.skip_reason("git"))),
            _FakeReport(("f.py", 2, "Skipped: " + _toolguard.skip_reason("git"))),
            _FakeReport(("f.py", 3, "Skipped: " + _toolguard.skip_reason("bash"))),
            _FakeReport(("f.py", 4, "Skipped: no game installed")),
        ]
        assert _toolguard.count_absent_tool_skips(reports) == {"git": 2, "bash": 1}

    def test_a_string_longrepr_is_read_too(self) -> None:
        """A skip raised from a fixture arrives as a bare string, not a triple."""
        reports = [_FakeReport(_toolguard.skip_reason("git"))]
        assert _toolguard.count_absent_tool_skips(reports) == {"git": 1}

    def test_no_absent_tool_skips_counts_nothing(self) -> None:
        assert _toolguard.count_absent_tool_skips([]) == {}
        assert _toolguard.count_absent_tool_skips([_FakeReport(None)]) == {}


class TestTheEndOfRunStatementSaysNothingWhenNothingWasSkipped:
    """A line that always prints is a line nobody reads."""

    def test_an_empty_count_renders_no_lines_at_all(self) -> None:
        assert _toolguard.summary_lines({}) == []

    def test_a_count_renders_the_tool_the_number_and_the_consequence(self) -> None:
        lines = _toolguard.summary_lines({"git": 187})
        rendered = "\n".join(lines)
        assert _toolguard.BANNER_TITLE in rendered
        assert "187" in rendered
        assert "git" in rendered
        assert "did NOT run" in rendered


class TestTheHookIsRegisteredAndReallyFires:
    """The decisive group. A formatter nobody calls is decoration."""

    def _child_env(self) -> dict[str, str]:
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(TESTS_DIR) + (os.pathsep + existing if existing else "")
        # PYTEST_ADDOPTS would be inherited by the child and could point it
        # back at this repository's own testpaths. The child must see exactly
        # the one generated file it is given and nothing else.
        env.pop("PYTEST_ADDOPTS", None)
        return env

    def _run_child(self, tmp_path: Path, body: str) -> subprocess.CompletedProcess:
        target = tmp_path / "test_generated.py"
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(body, encoding="ascii")
        tmp.replace(target)
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-p",
                "_toolguard",
                str(target),
            ],
            cwd=str(tmp_path),
            env=self._child_env(),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_a_skip_through_require_makes_the_statement_appear(
        self, tmp_path: Path
    ) -> None:
        body = (
            "import _toolguard\n"
            "\n"
            "\n"
            "def test_needs_a_tool_that_cannot_exist(monkeypatch):\n"
            "    monkeypatch.setattr(_toolguard.shutil, 'which', lambda name: None)\n"
            "    _toolguard.require('git')\n"
        )
        completed = self._run_child(tmp_path, body)
        assert "1 skipped" in completed.stdout, completed.stdout
        assert _toolguard.BANNER_TITLE in completed.stdout, completed.stdout
        assert "'git'" in completed.stdout, completed.stdout
        assert "1 test(s) were SKIPPED" in completed.stdout, completed.stdout

    def test_an_unrelated_skip_leaves_the_statement_silent(
        self, tmp_path: Path
    ) -> None:
        """The other direction, and what proves the banner is not unconditional."""
        body = (
            "import pytest\n"
            "\n"
            "\n"
            "def test_skips_for_a_reason_that_is_not_a_missing_tool():\n"
            "    pytest.skip('the game is not installed')\n"
        )
        completed = self._run_child(tmp_path, body)
        assert "1 skipped" in completed.stdout, completed.stdout
        assert _toolguard.BANNER_TITLE not in completed.stdout, completed.stdout

    def test_the_hook_is_registered_in_this_very_run(self, pytestconfig) -> None:
        """Registration asserted against pytest's own plugin manager.

        Grepping ``tests/conftest.py`` for the name would prove the text is
        there and nothing more. Asking the plugin manager which functions are
        registered for ``pytest_terminal_summary``, and comparing the FUNCTION
        OBJECT, is the fact that matters: if this assertion holds, the banner
        will be considered at the end of THIS run.
        """
        registered = [
            impl.function
            for impl in pytestconfig.pluginmanager.hook.pytest_terminal_summary.get_hookimpls()
        ]
        assert _toolguard.pytest_terminal_summary in registered


# ---------------------------------------------------------------------------
# ROADMAP OPS-83 - the capability half.
#
# The four files that run a real `git commit` against .githooks/pre-commit do
# not need ONE tool, they need a POSIX userland. Everything below pins that
# second shape: a named capability whose member set is declared in one place,
# whose skip reason is distinct from the single-tool one so the two counters
# cannot double-count the same skip, and whose declared set is checked against
# the hook sources by DERIVATION rather than trusted because someone typed it.
# ---------------------------------------------------------------------------


class TestTheCapabilityReasonCannotBeConfusedWithTheToolReason:
    """The two prefixes are disjoint, which is what keeps the counters apart.

    ``tool_from_reason`` searches for its prefix ANYWHERE in the text, so a
    capability prefix that merely contained the tool prefix - or was contained
    by it - would make every capability skip also count as a tool skip. The
    banner would then name a tool that is sitting on PATH, and the total would
    be double what really happened.
    """

    def test_neither_prefix_contains_the_other(self) -> None:
        tool = _toolguard.SKIP_REASON_PREFIX
        cap = _toolguard.CAPABILITY_SKIP_REASON_PREFIX
        assert tool != cap
        assert tool not in cap
        assert cap not in tool

    def test_a_capability_reason_names_no_tool(self) -> None:
        reason = _toolguard.capability_skip_reason("posix-userland", ("tr", "wc"))
        assert _toolguard.tool_from_reason(reason) is None
        assert _toolguard.tool_from_reason("Skipped: " + reason) is None

    def test_a_tool_reason_names_no_capability(self) -> None:
        reason = _toolguard.skip_reason("git")
        assert _toolguard.capability_from_reason(reason) is None
        assert _toolguard.capability_from_reason("Skipped: " + reason) is None


class TestTheCapabilitySkipReasonRoundTrips:
    """Machine-readable for the same reason the single-tool one is."""

    def test_the_reason_names_the_capability_and_every_missing_member(self) -> None:
        reason = _toolguard.capability_skip_reason("posix-userland", ("tr", "wc"))
        assert "posix-userland" in reason
        assert "tr" in reason
        assert "wc" in reason

    def test_the_round_trip_is_exact(self) -> None:
        for name, missing in (
            ("posix-userland", ("tr",)),
            ("posix-userland", ("grep", "head", "printf", "tr", "wc")),
            ("some-other-capability", ("sed",)),
        ):
            reason = _toolguard.capability_skip_reason(name, missing)
            assert _toolguard.capability_from_reason(reason) == (name, missing)

    def test_the_pytest_skipped_wrapper_does_not_break_the_round_trip(self) -> None:
        reason = _toolguard.capability_skip_reason("posix-userland", ("tr", "wc"))
        assert _toolguard.capability_from_reason("Skipped: " + reason) == (
            "posix-userland",
            ("tr", "wc"),
        )

    def test_an_unrelated_skip_names_no_capability(self) -> None:
        assert _toolguard.capability_from_reason("Skipped: no game installed") is None
        assert _toolguard.capability_from_reason("") is None
        assert _toolguard.capability_from_reason(None) is None
        assert (
            _toolguard.capability_from_reason(_toolguard.CAPABILITY_SKIP_REASON_PREFIX)
            is None
        )


class TestTheDeclaredCapabilityIsWellFormed:
    """Cheap shape checks that would otherwise fail far from their cause."""

    def test_the_capability_name_is_one_whitespace_free_token(self) -> None:
        assert _toolguard.POSIX_USERLAND
        assert _toolguard.POSIX_USERLAND.split() == [_toolguard.POSIX_USERLAND]

    def test_the_member_set_is_a_tuple_with_no_duplicates(self) -> None:
        tools = _toolguard.POSIX_USERLAND_TOOLS
        assert isinstance(tools, tuple)
        assert tools
        assert len(set(tools)) == len(tools)

    def test_sh_is_a_member_because_every_hook_shebang_names_it(self) -> None:
        assert "sh" in _toolguard.POSIX_USERLAND_TOOLS


class TestMissingToolsReportsOnlyTheAbsentOnesInOrder:
    def test_nothing_is_missing_when_everything_resolves(self, monkeypatch) -> None:
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: "/bin/" + name)
        assert _toolguard.missing_tools(("tr", "wc")) == ()

    def test_only_the_absent_members_come_back_and_order_is_preserved(
        self, monkeypatch
    ) -> None:
        absent = {"tr", "printf"}
        monkeypatch.setattr(
            _toolguard.shutil,
            "which",
            lambda name: None if name in absent else "/bin/" + name,
        )
        assert _toolguard.missing_tools(("sh", "printf", "tr", "wc")) == (
            "printf",
            "tr",
        )


class TestRequireCapabilitySkipsWhenAnyMemberIsAbsent:
    """The absent direction."""

    def test_one_absent_member_skips_naming_the_capability_and_the_member(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _toolguard.shutil,
            "which",
            lambda name: None if name == "tr" else "/bin/" + name,
        )
        with pytest.raises(pytest.skip.Exception) as excinfo:
            _toolguard.require_capability("posix-userland", ("sh", "tr", "wc"))
        text = str(excinfo.value)
        assert _toolguard.capability_from_reason(text) == ("posix-userland", ("tr",))

    def test_the_skip_is_not_swallowed_by_a_fail_soft_except_exception(
        self, monkeypatch
    ) -> None:
        """A skip built on ``Exception`` would become a pass that ran nothing.

        The general property is asserted elsewhere; this arm asserts it about
        THIS guard, by putting the guard inside exactly the bare
        ``except Exception`` this repository carries in its fail-soft helpers
        and proving the skip still escapes.
        """
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: None)
        escaped = False
        try:
            try:
                _toolguard.require_capability("posix-userland", ("tr",))
            except Exception:  # the bare handler this repo really carries
                pytest.fail("a bare except Exception swallowed the capability skip")
        except pytest.skip.Exception:
            escaped = True
        assert escaped


class TestRequireCapabilityReturnsUsablePathsWhenEveryMemberIsPresent:
    """The present direction - ``docs/OPERATIONS.md`` bidirectional discipline."""

    def test_every_member_comes_back_mapped_to_its_resolved_path(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _toolguard.shutil, "which", lambda name: "/somewhere/" + name
        )
        paths = _toolguard.require_capability("posix-userland", ("tr", "wc"))
        assert paths == {"tr": "/somewhere/tr", "wc": "/somewhere/wc"}

    def test_the_returned_paths_really_run_the_tools(self) -> None:
        """The effects chosen are ones only these two utilities produce.

        ``wc -c`` answers a byte count and ``tr`` transliterates; an exit code
        of zero would prove neither. This is also the arm that pins the PRESENT
        direction for the real call site name.
        """
        paths = _toolguard.require_posix_userland()
        counted = subprocess.run(
            [paths["wc"], "-c"],
            input="abcd",
            capture_output=True,
            text=True,
            check=True,
        )
        assert counted.stdout.strip() == "4"
        shouted = subprocess.run(
            [paths["tr"], "a-z", "A-Z"],
            input="abcd",
            capture_output=True,
            text=True,
            check=True,
        )
        assert shouted.stdout.strip() == "ABCD"

    def test_the_named_call_site_asks_for_the_declared_member_set(
        self, monkeypatch
    ) -> None:
        seen: list[str] = []

        def fake_which(name: str) -> str:
            seen.append(name)
            return "/bin/" + name

        monkeypatch.setattr(_toolguard.shutil, "which", fake_which)
        paths = _toolguard.require_posix_userland()
        assert tuple(seen) == _toolguard.POSIX_USERLAND_TOOLS
        assert set(paths) == set(_toolguard.POSIX_USERLAND_TOOLS)


class TestRequiresCapabilityMarker:
    """Pins only the ABSENT direction, and says so - see the docstring there."""

    def test_an_absent_member_produces_a_true_skipif_naming_the_capability(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: None)
        marker = _toolguard.requires_capability("posix-userland", ("tr",))
        (condition,) = marker.args
        assert condition is True
        assert _toolguard.capability_from_reason(marker.kwargs["reason"]) == (
            "posix-userland",
            ("tr",),
        )

    def test_a_complete_capability_produces_a_false_skipif(self, monkeypatch) -> None:
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: "/bin/" + name)
        marker = _toolguard.requires_capability("posix-userland", ("tr",))
        (condition,) = marker.args
        assert condition is False


class TestTheCapabilityCounterIsPerCapability:
    def test_reports_are_counted_and_their_missing_members_unioned(self) -> None:
        reports = [
            _FakeReport(
                (
                    "f.py",
                    1,
                    "Skipped: "
                    + _toolguard.capability_skip_reason("posix-userland", ("tr",)),
                )
            ),
            _FakeReport(
                (
                    "f.py",
                    2,
                    "Skipped: "
                    + _toolguard.capability_skip_reason("posix-userland", ("wc", "tr")),
                )
            ),
            _FakeReport(("f.py", 3, "Skipped: " + _toolguard.skip_reason("git"))),
            _FakeReport(("f.py", 4, "Skipped: no game installed")),
        ]
        assert _toolguard.count_absent_capability_skips(reports) == {
            "posix-userland": (2, ("tr", "wc"))
        }

    def test_a_string_longrepr_is_read_too(self) -> None:
        reports = [
            _FakeReport(_toolguard.capability_skip_reason("posix-userland", ("wc",)))
        ]
        assert _toolguard.count_absent_capability_skips(reports) == {
            "posix-userland": (1, ("wc",))
        }

    def test_nothing_relevant_counts_nothing(self) -> None:
        assert _toolguard.count_absent_capability_skips([]) == {}
        assert _toolguard.count_absent_capability_skips([_FakeReport(None)]) == {}

    def test_the_two_counters_do_not_double_count_the_same_skip(self) -> None:
        """OPS-83 criterion 2 depends on the two totals being truthful."""
        reports = [
            _FakeReport(
                _toolguard.capability_skip_reason("posix-userland", ("tr", "wc"))
            ),
            _FakeReport(_toolguard.skip_reason("git")),
        ]
        assert _toolguard.count_absent_tool_skips(reports) == {"git": 1}
        assert _toolguard.count_absent_capability_skips(reports) == {
            "posix-userland": (1, ("tr", "wc"))
        }


class TestTheBannerReportsCapabilitySkipsToo:
    """OPS-83 criterion 2 - a green summary must not conceal these."""

    def test_nothing_at_all_is_emitted_when_nothing_was_skipped(self) -> None:
        assert _toolguard.summary_lines({}) == []
        assert _toolguard.summary_lines({}, {}) == []

    def test_a_capability_skip_renders_the_count_the_name_and_the_members(
        self,
    ) -> None:
        lines = _toolguard.summary_lines({}, {"posix-userland": (49, ("tr", "wc"))})
        rendered = "\n".join(lines)
        assert _toolguard.CAPABILITY_BANNER_TITLE in rendered
        assert "49" in rendered
        assert "posix-userland" in rendered
        assert "tr" in rendered
        assert "wc" in rendered
        assert "did NOT run" in rendered

    def test_the_single_tool_section_is_unchanged_by_the_capability_section(
        self,
    ) -> None:
        lines = _toolguard.summary_lines({"git": 187}, {"posix-userland": (49, ("tr",))})
        rendered = "\n".join(lines)
        assert lines[0] == _toolguard.BANNER_TITLE
        assert (
            "187 test(s) were SKIPPED because the external tool 'git' "
            "was not found on PATH." in rendered
        )
        assert _toolguard.CAPABILITY_BANNER_TITLE in rendered

    def test_a_capability_only_banner_leads_with_the_capability_title(self) -> None:
        lines = _toolguard.summary_lines({}, {"posix-userland": (49, ("tr",))})
        assert lines[0] == _toolguard.CAPABILITY_BANNER_TITLE
        assert _toolguard.BANNER_TITLE not in "\n".join(lines)


class TestTheCapabilityBannerReallyFiresInARealRun:
    """A formatter nobody calls is decoration - the same argument as above."""

    def test_a_capability_skip_makes_the_statement_appear(self, tmp_path: Path) -> None:
        body = (
            "import _toolguard\n"
            "\n"
            "\n"
            "def test_needs_a_userland_that_cannot_exist(monkeypatch):\n"
            "    monkeypatch.setattr(_toolguard.shutil, 'which', lambda name: None)\n"
            "    _toolguard.require_posix_userland()\n"
        )
        completed = TestTheHookIsRegisteredAndReallyFires()._run_child(tmp_path, body)
        assert "1 skipped" in completed.stdout, completed.stdout
        assert _toolguard.CAPABILITY_BANNER_TITLE in completed.stdout, completed.stdout
        assert "'posix-userland'" in completed.stdout, completed.stdout
        assert "1 test(s) were SKIPPED" in completed.stdout, completed.stdout
        for member in _toolguard.POSIX_USERLAND_TOOLS:
            assert member in completed.stdout, completed.stdout

    def test_an_unrelated_skip_leaves_the_capability_statement_silent(
        self, tmp_path: Path
    ) -> None:
        body = (
            "import pytest\n"
            "\n"
            "\n"
            "def test_skips_for_a_reason_that_is_not_a_missing_capability():\n"
            "    pytest.skip('the game is not installed')\n"
        )
        completed = TestTheHookIsRegisteredAndReallyFires()._run_child(tmp_path, body)
        assert "1 skipped" in completed.stdout, completed.stdout
        assert (
            _toolguard.CAPABILITY_BANNER_TITLE not in completed.stdout
        ), completed.stdout


# ---------------------------------------------------------------------------
# ROADMAP OPS-83 - the drift test.
#
# POSIX_USERLAND_TOOLS is a DECLARATION, and this repository already knows what
# happens to a declaration nobody re-derives: ops/docguards.py refuses to keep
# its selection in a file because "a list is silently green over every document
# and every module added after it was written". The same argument applies here.
# A hook that gains a `sed` would, with a declaration alone, keep producing an
# unexplained red on a machine without sed - the exact defect OPS-78 exists to
# remove - and nothing would say so.
#
# So the declared set is checked by re-deriving the utilities from the hook
# sources, and the check fails in BOTH directions. Staleness then presents as a
# red test on a machine that HAS the userland, where it is diagnosable, instead
# of as a false red on a bare box where it is not.
#
# WHY COMMAND POSITION AND NOT A BARE WORD-BOUNDARY SCAN. Measured 2026-09-12
# against these two hooks: a \bWORD\b scan over every non-comment line reports
# `diff` (from `git diff --cached`), `tar` (from the `*.tar` branch of a
# filename case), `sh` (from the `*.sh` branch of another) and `find` (from the
# option `--find-renames`). None of those four is a utility being invoked, and
# declaring them would put four names into the guard whose absence would skip
# 49 tests that would have run - a coverage loss with no cause. Requiring the
# name to sit where a command goes removes all four and keeps everything real.
# Word boundaries are still enforced inside that, which is what stops \bfind\b
# matching the shell function `find_python`.
#
# THIS REPOSITORY HAS ALREADY MADE EXACTLY THIS MOVE ONCE, for the same class of
# false positive. OPS-22 narrowed tools/precommit_gate.py from a bare substring
# test for a forbidden PowerShell cmdlet to COMMAND POSITION, because the
# substring test refused any command that merely QUOTED the name in prose. Read
# tools/precommit_gate.py::CMDLET_CALL and ::_forbidden_cmdlet_reason: the
# regex shape below is deliberately the same idea, and that function's docstring
# is also the honest record of what such a matcher cannot see.
# ---------------------------------------------------------------------------

GITHOOKS_DIR = REPO_ROOT / ".githooks"

#: The hooks whose dependency POSIX_USERLAND describes. Both are `#!/bin/sh`
#: and both are what the four OPS-83 files drive through a real `git commit`.
GUARDED_HOOKS = ("pre-commit", "commit-msg")

#: Candidate vocabulary. Common POSIX utilities that a shell script plausibly
#: calls. Shell BUILT-INS are deliberately absent - `echo`, `test`, `read`,
#: `set`, `unset`, `exec`, `trap`, `exit`, `true`, `false` are provided by the
#: interpreter itself, so their presence in a hook says nothing about the
#: userland and declaring them would be noise. `git` is absent for a different
#: reason: it is not a POSIX utility, and OPS-78 already guards it by name.
POSIX_UTILITY_VOCABULARY = (
    "awk",
    "basename",
    "cat",
    "chmod",
    "chown",
    "cmp",
    "comm",
    "cp",
    "cut",
    "date",
    "dd",
    "diff",
    "dirname",
    "du",
    "env",
    "expand",
    "expr",
    "find",
    "fold",
    "grep",
    "gzip",
    "head",
    "id",
    "join",
    "ln",
    "ls",
    "mkdir",
    "mkfifo",
    "mktemp",
    "mv",
    "nl",
    "od",
    "paste",
    "pr",
    "printf",
    "ps",
    "readlink",
    "realpath",
    "rm",
    "rmdir",
    "sed",
    "seq",
    "sh",
    "sleep",
    "sort",
    "split",
    "stat",
    "tail",
    "tar",
    "tee",
    "touch",
    "tr",
    "uname",
    "uniq",
    "wc",
    "which",
    "xargs",
)

#: Shell KEYWORDS after which the very next word is a command. Every one of
#: these is a reserved word the shell consumes itself, so what follows it is
#: the command and not an argument - which is why the lead can look behind for
#: them without reopening the false-positive class the matcher exists to close.
KEYWORD_INTRODUCERS = ("if", "then", "elif", "else", "while", "until", "do")

#: Command WRAPPERS, which are the matcher's known blind spot. These are not
#: keywords: each is an ordinary command that takes another command as an
#: ARGUMENT. The matcher cannot see through one, and that is a deliberate
#: trade rather than an oversight - see
#: ``TestTheDerivationItselfIsHonest.test_a_command_wrapper_hides_the_utility
#: _it_runs`` for the reasoning and
#: ``test_no_guarded_hook_invokes_a_command_wrapper`` for the guard that keeps
#: the limit theoretical.
COMMAND_WRAPPERS = ("env", "time", "xargs", "command")

#: What may precede a command: start of text, a newline, a pipe, a semicolon,
#: an ampersand, a brace, a backtick, an opening parenthesis (which covers
#: `$(`), or one of :data:`KEYWORD_INTRODUCERS`.
#:
#: WHAT THIS LEAD CANNOT SEE, stated because a caveat known and not written
#: into the artifact is a lie in the artifact. A utility invoked as the
#: ARGUMENT of one of :data:`COMMAND_WRAPPERS` - `xargs grep`, `env LC_ALL=C
#: sed`, `command tr`, `time wc` - is NOT in command position by this
#: definition and is NOT derived. Widening the lead to cover them would mean
#: treating an argument as a command, which is exactly how a bare scan reads
#: the git option `--find-renames` as the utility `find`. The precision is
#: worth more than the coverage here because the four wrappers are absent from
#: both hooks and an arm asserts they stay absent, whereas the false positives
#: were real and measured.
#:
#: Written out rather than generated from :data:`KEYWORD_INTRODUCERS` on
#: purpose. A lead built from that tuple would make the arm that loops over the
#: tuple vacuous - deleting a keyword would delete the case that tests it, and
#: the arm would stay green over the hole it just opened. Two independent
#: spellings mean a keyword dropped from either one reddens.
#:
#: ``elif`` needs its own lookbehind: ``(?<=\bif )`` cannot match inside
#: ``elif `` because the ``\b`` fails against the preceding ``l``.
_COMMAND_LEAD = (
    r"(?:^|[\n|;&(){}`!]"
    r"|(?<=\bif )|(?<=\bthen )|(?<=\belif )|(?<=\belse )"
    r"|(?<=\bwhile )|(?<=\buntil )|(?<=\bdo ))"
)

#: Optional whitespace and any number of `VAR=value` assignment prefixes, so
#: `LC_ALL=C grep` is recognised as an invocation of grep.
#:
#: The assignment VALUE deliberately cannot contain `$`, a backtick or a
#: parenthesis. Measured 2026-09-12 with `[^ \t]*` there instead: the line
#: `staged=$(git diff --cached ...)` was read as the assignment prefix
#: `staged=$(git ` followed by the command `diff`, so the derivation reported
#: `diff` as a required utility. That is an assignment whose value OPENS a
#: command substitution, and treating it as a prefix hands the real command
#: name to the next token.
_COMMAND_PREFIX = r"[ \t]*(?:[A-Za-z_][A-Za-z0-9_]*=[^ \t\n$`();|&]*[ \t]+)*"


def hook_text(name: str) -> str:
    """The full source of one guarded hook, read as ASCII by repo rule."""
    return (GITHOOKS_DIR / name).read_text(encoding="ascii")


def hook_body(text: str) -> str:
    """``text`` with whole-line comments removed.

    These hooks carry more prose than code and the prose names utilities it is
    not calling - `git mv a.py b.py` sits in a comment in pre-commit. A scan
    that read comments would declare `mv` as a required member on the strength
    of a sentence.
    """
    return "\n".join(
        line for line in text.splitlines() if line.lstrip()[:1] != "#"
    )


def utilities_invoked(text: str) -> set[str]:
    """Every vocabulary name appearing in COMMAND POSITION in ``text``."""
    body = hook_body(text)
    found = set()
    for name in POSIX_UTILITY_VOCABULARY:
        pattern = _COMMAND_LEAD + _COMMAND_PREFIX + r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, body):
            found.add(name)
    return found


class TestTheDerivationItselfIsHonest:
    """Anchors. A survivor of a scan is only believable if the scan works.

    Every arm here is about the MATCHER, not about the declaration. If the
    matcher silently found nothing, or silently found everything, the two
    direction tests below would still pass or still fail for reasons that had
    nothing to do with drift.
    """

    def test_the_matcher_finds_the_utilities_that_are_plainly_there(self) -> None:
        found = utilities_invoked(hook_text("pre-commit"))
        assert {"grep", "head", "printf", "tr", "wc"} <= found

    def test_a_word_boundary_stops_a_prefix_match(self) -> None:
        """``\\bfind\\b`` must not match the shell function ``find_python``."""
        assert "find" not in utilities_invoked("find_python() {\n    :\n}\n")
        assert "find" in utilities_invoked("find . -name x\n")

    def test_every_keyword_introducer_puts_the_next_word_in_command_position(
        self,
    ) -> None:
        """Every shell keyword that can stand immediately before a command.

        ``elif``, ``while`` and ``until`` were absent from the lead until the
        OPS-83 refutation pass probed for them. They introduce a command in
        exactly the way ``if``, ``then``, ``else`` and ``do`` already did, so a
        utility invoked after one of them is a real dependency and the
        derivation has to see it. A hook line reading
        ``elif sed -n 1p; then`` would otherwise add a ``sed`` dependency that
        the drift test never reported - the staleness the derivation exists to
        prevent.
        """
        for keyword in KEYWORD_INTRODUCERS:
            line = f"{keyword} sed -n 1p\n"
            assert "sed" in utilities_invoked(line), keyword

    def test_a_command_wrapper_hides_the_utility_it_runs(self) -> None:
        """THE KNOWN LIMIT. Pinned rather than left as a silence.

        The four names in :data:`COMMAND_WRAPPERS` are not keywords - they are
        ordinary commands that take ANOTHER command as an ARGUMENT. Treating an
        argument position as a command position is precisely the
        ``--find-renames`` class of false positive this matcher exists to
        remove, so the trade is deliberate: the matcher keeps its precision and
        pays for it by not seeing through a wrapper. A hook that gained
        ``xargs grep`` would therefore go undetected by the drift test.

        The arm below keeps that from being a theoretical worry as well as a
        documented one: no guarded hook uses any of the four today.
        """
        for wrapper in COMMAND_WRAPPERS:
            assert "sed" not in utilities_invoked(f"{wrapper} sed -n 1p\n"), wrapper
        assert "sed" in utilities_invoked("sed -n 1p\n"), "positive control"

    def test_no_guarded_hook_invokes_a_command_wrapper(self) -> None:
        """So the blind spot above stays theoretical, and says so when it stops.

        This is the test behind the limit. If a hook ever gains an ``env``,
        ``time``, ``xargs`` or ``command`` invocation, the utility it wraps
        becomes an undeclared dependency that the two direction tests cannot
        see - so this arm reddens first and names the hook, which is a
        diagnosable failure rather than a silent one.
        """
        for name in GUARDED_HOOKS:
            body = hook_body(hook_text(name))
            for wrapper in COMMAND_WRAPPERS:
                pattern = (
                    _COMMAND_LEAD + _COMMAND_PREFIX + r"\b" + re.escape(wrapper) + r"\b"
                )
                assert re.search(pattern, body) is None, (
                    f".githooks/{name} now invokes the command wrapper "
                    f"{wrapper!r}. The matcher cannot see the utility a wrapper "
                    "runs, so whatever it wraps must be added to "
                    "POSIX_USERLAND_TOOLS by hand - the drift test will not "
                    "find it."
                )

    def test_the_comment_stripper_really_removes_a_command_in_a_comment(self) -> None:
        """Pinned on a synthetic line, because the real hooks do not exercise it.

        MEASURED 2026-09-12 and written down so nobody mistakes this for a
        load-bearing filter: over these two hooks the stripper changes the
        derived set by NOTHING. Every utility named in their prose sits after a
        ``#`` and is therefore not in command position anyway. An arm that
        asserted ``mv`` is absent from the real hook would pass with the
        stripper deleted - it would be decoration, and it was one until this
        was measured.

        The stripper still earns its place, because a comment CAN put a name in
        command position - after a pipe or a backtick inside quoted prose - and
        the next hook edit may do exactly that. This arm is the case that
        proves it works, and it reddens when the stripper is removed.
        """
        commented = "#!/bin/sh\n# measured: git commit -m x 2>&1 | sed -n 1p\n:\n"
        assert "sed" not in utilities_invoked(commented)
        assert "sed" in utilities_invoked(commented.replace("# measured: ", ""))

    def test_mv_is_prose_in_the_hooks_and_not_an_invocation(self) -> None:
        """Why ``mv`` is not declared, despite the OPS-83 entry naming it.

        This is a claim about the hook, not about the stripper: the only
        occurrence of ``mv`` in either hook is inside a sentence.
        """
        text = hook_text("pre-commit")
        assert "git mv a.py b.py" in text, "anchor text not found - the hook changed"
        assert "mv" not in utilities_invoked(text)
        assert "mv" not in utilities_invoked(hook_text("commit-msg"))

    def test_a_name_outside_command_position_is_not_an_invocation(self) -> None:
        """The four false positives a bare word-boundary scan produces here."""
        text = hook_text("pre-commit")
        body = hook_body(text)
        for word, anchor in (
            ("diff", "git diff --cached"),
            ("tar", "*.tar|"),
            ("find", "--find-renames"),
        ):
            assert anchor in body, f"anchor {anchor!r} not found - the hook changed"
            assert re.search(rf"\b{word}\b", body), f"{word} is in the body"
        invoked = utilities_invoked(text)
        assert "diff" not in invoked
        assert "tar" not in invoked
        assert "find" not in invoked


class TestTheDeclaredPosixUserlandDoesNotDriftFromTheHooks:
    """Both directions. Either one alone would be half a guard."""

    def test_both_guarded_hooks_are_bin_sh(self) -> None:
        """``sh`` is declared because of THIS, not because of the hook bodies."""
        for name in GUARDED_HOOKS:
            first_line = hook_text(name).splitlines()[0]
            assert first_line == "#!/bin/sh", (name, first_line)
        assert "sh" in _toolguard.POSIX_USERLAND_TOOLS

    def test_every_utility_the_hooks_invoke_is_declared(self) -> None:
        """Shell builtins are SUBTRACTED, by name, from a visible constant.

        ``_toolguard.SHELL_BUILTIN_UTILITIES`` is consulted rather than a
        condition written inline here, so the exclusion is something a
        reader can find and re-check instead of something buried in this
        assertion. ``printf`` is the member that exclusion decides.
        """
        declared = set(_toolguard.POSIX_USERLAND_TOOLS)
        invoked: set[str] = set()
        for name in GUARDED_HOOKS:
            invoked |= utilities_invoked(hook_text(name))
        undeclared = sorted(
            invoked - declared - set(_toolguard.SHELL_BUILTIN_UTILITIES)
        )
        assert not undeclared, (
            "the git hooks invoke POSIX utilities that "
            "tests/_toolguard.py does not declare: "
            + ", ".join(undeclared)
            + ". Add them to POSIX_USERLAND_TOOLS, or the guard will keep "
            "producing an unexplained red on a machine that lacks them."
        )

    def test_every_declared_member_is_really_invoked(self) -> None:
        """A declared member nothing needs is a coverage loss, not caution.

        Its absence would skip all 49 tests - tests that would have run and
        would have passed - and the banner would name a utility no hook ever
        calls. ``sh`` is exempt because it comes from the shebang rather than
        from a hook body; the arm above pins that separately.
        """
        invoked: set[str] = set()
        for name in GUARDED_HOOKS:
            invoked |= utilities_invoked(hook_text(name))
        unused = sorted(
            member
            for member in _toolguard.POSIX_USERLAND_TOOLS
            if member != "sh" and member not in invoked
        )
        assert not unused, (
            "tests/_toolguard.py declares POSIX utilities that no guarded git "
            "hook invokes: "
            + ", ".join(unused)
            + ". Remove them from POSIX_USERLAND_TOOLS - a member nothing needs "
            "skips tests that would have run."
        )

    def test_every_declared_member_is_in_the_candidate_vocabulary(self) -> None:
        """Otherwise a member could never be derived and the check is vacuous."""
        for member in _toolguard.POSIX_USERLAND_TOOLS:
            assert member in POSIX_UTILITY_VOCABULARY, member


class TestPrintfIsExcludedBecauseTheShellProvidesIt:
    """The one exclusion that changes the declared set, pinned in both halves."""

    def test_printf_really_is_invoked_by_both_hooks(self) -> None:
        for name in GUARDED_HOOKS:
            assert "printf" in utilities_invoked(hook_text(name)), name

    def test_printf_is_a_declared_builtin_and_not_a_capability_member(self) -> None:
        assert "printf" in _toolguard.SHELL_BUILTIN_UTILITIES
        assert "printf" not in _toolguard.POSIX_USERLAND_TOOLS

    def test_no_declared_member_is_a_shell_builtin(self) -> None:
        overlap = set(_toolguard.POSIX_USERLAND_TOOLS) & set(
            _toolguard.SHELL_BUILTIN_UTILITIES
        )
        assert not overlap, overlap


class TestAWindowsHomonymDoesNotCountAsPresent:
    """MEASURED: `which('find')` answers system32 on a box with no userland.

    A name-only presence probe is a claim about a FILENAME, not about a POSIX
    userland. None of the five declared members is a homonym today, so every
    arm here drives the check through a name that is - which is the point: this
    is armour for the next member added, and an untested guard is decoration
    whether or not anything currently walks into it.
    """

    SYSTEM32_FIND = "C:\\Windows\\system32\\find.EXE"

    def test_the_measured_homonyms_are_declared(self) -> None:
        assert "find" in _toolguard.WINDOWS_HOMONYMS
        assert "sort" in _toolguard.WINDOWS_HOMONYMS

    def test_a_system32_resolution_reads_as_absent_for_a_homonym(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _toolguard.shutil, "which", lambda name: self.SYSTEM32_FIND
        )
        assert _toolguard.find("find") == self.SYSTEM32_FIND
        assert _toolguard.resolve_member("find") is None
        assert _toolguard.missing_tools(("find",)) == ("find",)

    def test_a_real_userland_path_still_reads_as_present_for_a_homonym(
        self, monkeypatch
    ) -> None:
        """The other direction - the check must not condemn every `find`."""
        real = "C:\\Program Files\\Git\\usr\\bin\\find.EXE"
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: real)
        assert _toolguard.resolve_member("find") == real
        assert _toolguard.missing_tools(("find",)) == ()

    EXTENDED_LENGTH_FIND = "\\\\?\\C:\\Windows\\system32\\find.EXE"

    def test_an_extended_length_resolution_reads_as_absent_for_a_homonym(
        self, monkeypatch
    ) -> None:
        """``\\\\?\\C:\\x`` and ``C:\\x`` name the same file.

        pathlib does not: the extended-length form has its own ANCHOR, so the
        plain ``%SystemRoot%`` is not among its ``parents`` and a system32
        homonym written that way read as PRESENT until this arm was added.
        """
        monkeypatch.setattr(
            _toolguard.shutil, "which", lambda name: self.EXTENDED_LENGTH_FIND
        )
        assert _toolguard.find("find") == self.EXTENDED_LENGTH_FIND
        assert _toolguard.resolve_member("find") is None
        assert _toolguard.missing_tools(("find",)) == ("find",)

    def test_the_normaliser_leaves_an_ordinary_path_alone(self) -> None:
        """The other direction - it strips a prefix, it does not rewrite paths."""
        plain = "C:\\Program Files\\Git\\usr\\bin\\find.EXE"
        assert _toolguard._without_extended_length_prefix(plain) == plain

    def test_a_unc_administrative_share_is_a_known_limit_not_a_defence(
        self, monkeypatch
    ) -> None:
        """HONEST LIMIT, pinned rather than papered over.

        ``\\\\host\\C$\\Windows\\system32\\find.EXE`` is the same file as
        ``C:\\Windows\\system32\\find.EXE`` when ``host`` is THIS machine and a
        different machine's file otherwise, and nothing here can tell those
        apart without guessing which of a machine's many names - NetBIOS name,
        FQDN, ``localhost``, ``.``, a loopback literal, an address that
        resolves differently per network - denotes itself. A wrong guess is
        wrong in both dangerous directions. So the UNC form is NOT covered, and
        this arm says so out loud instead of leaving a reader to assume it is.

        What IS settled: the two spellings of the same UNC path agree. The
        extended-length UNC prefix normalises to the plain UNC form, so the
        answer cannot depend on which spelling a ``PATH`` entry used.
        """
        plain_unc = "\\\\somehost\\C$\\Windows\\system32\\find.EXE"
        extended_unc = "\\\\?\\UNC\\somehost\\C$\\Windows\\system32\\find.EXE"
        assert (
            _toolguard._without_extended_length_prefix(extended_unc) == plain_unc
        )
        for form in (plain_unc, extended_unc):
            monkeypatch.setattr(
                _toolguard.shutil, "which", lambda name, form=form: form
            )
            assert _toolguard.resolve_member("find") == form, form

    def test_a_non_homonym_under_system32_is_left_alone(self, monkeypatch) -> None:
        """The check is scoped to the named homonyms, not to a directory.

        A guard that rejected every %SystemRoot% resolution would be a
        different and much broader rule than the one decided, and it would be
        wrong for any tool a machine genuinely installs there.
        """
        monkeypatch.setattr(
            _toolguard.shutil, "which", lambda name: "C:\\Windows\\system32\\tr.EXE"
        )
        assert _toolguard.resolve_member("tr") == "C:\\Windows\\system32\\tr.EXE"

    def test_the_capability_skip_names_a_homonym_that_only_looked_present(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _toolguard.shutil,
            "which",
            lambda name: self.SYSTEM32_FIND if name == "find" else "/bin/" + name,
        )
        with pytest.raises(pytest.skip.Exception) as excinfo:
            _toolguard.require_capability("posix-userland", ("sh", "find"))
        assert _toolguard.capability_from_reason(str(excinfo.value)) == (
            "posix-userland",
            ("find",),
        )

    def test_system_root_is_read_from_the_environment_not_snapshotted(
        self, monkeypatch, tmp_path
    ) -> None:
        """A module-level snapshot would be invisible to this very test."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        planted = str(tmp_path / "System32" / "find.EXE")
        monkeypatch.setattr(_toolguard.shutil, "which", lambda name: planted)
        assert _toolguard.resolve_member("find") is None
