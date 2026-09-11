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
