"""Tests for the merge gate - the thing that refuses to take an agent's word.

These tests are deliberately built from output shapes MEASURED on this machine
on 2026-08-09, not from what pytest is assumed to print. Two of those shapes
are load-bearing and would break a naive parser:

- every line pytest writes here is **CR-terminated**, and the final summary
  line carries no trailing newline at all
- ``--collect-only -q`` prints a per-file ``path: count`` list and **no grand
  total**, so the total has to be summed rather than read

The most important behaviour under test is the count-regression guard. A suite
that goes green after an agent deleted or weakened a test is the exact failure
this module exists to catch, and it is invisible to an exit code.
"""

import builtins
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import merge_gate, store_drift  # noqa: E402
from ops.loop import state as state_mod  # noqa: E402

# Measured verbatim from `python -m pytest --collect-only -q` on 2026-08-09,
# CRs included. Assembled with explicit \r so the shape survives any editor.
COLLECT_REAL = (
    "tests/test_ascii_hygiene.py: 4\r\n"
    "tests/test_logparse.py: 27\r\n"
    "tests/test_loop_guard.py: 22\r\n"
    "tests/test_loop_state.py: 22\r\n"
    "tests/test_no_pii.py: 4\r\n"
    "tests/test_overlay_anchors.py: 43\r\n"
    "tests/test_overlay_render.py: 37\r\n"
    "tests/test_redact.py: 23\r\n"
    "\r\n"
)

# Measured verbatim from `python -m pytest`: CR-terminated, no trailing LF.
SUMMARY_PASS = (
    "........................................ [100%]\r\n182 passed in 0.78s\r"
)


class TestCollectParsing:
    def test_sums_the_per_file_counts_because_pytest_prints_no_total(self):
        assert merge_gate.total_collected(COLLECT_REAL) == 182

    def test_per_file_counts_are_returned_individually(self):
        counts = merge_gate.parse_collect_counts(COLLECT_REAL)
        assert counts["tests/test_redact.py"] == 23
        assert counts["tests/test_overlay_anchors.py"] == 43
        assert len(counts) == 8

    def test_carriage_returns_do_not_leak_into_the_parsed_paths(self):
        for path in merge_gate.parse_collect_counts(COLLECT_REAL):
            assert "\r" not in path
            assert not path.endswith(" ")

    def test_empty_collect_output_is_zero_not_a_crash(self):
        assert merge_gate.total_collected("") == 0

    def test_a_line_that_is_not_a_count_is_ignored(self):
        noisy = "ERROR tests/test_x.py - ImportError: boom\r\n" + COLLECT_REAL
        assert merge_gate.total_collected(noisy) == 182


class TestSummaryParsing:
    def test_parses_the_cr_terminated_summary_with_no_trailing_newline(self):
        result = merge_gate.parse_summary(SUMMARY_PASS)
        assert result.passed == 182
        assert result.failed == 0
        assert result.errors == 0

    def test_parses_a_mixed_failure_summary(self):
        text = "3 failed, 179 passed, 2 errors in 1.20s\r"
        result = merge_gate.parse_summary(text)
        assert result.passed == 179
        assert result.failed == 3
        assert result.errors == 2

    def test_missing_summary_is_reported_as_absent_not_as_zero(self):
        # "no summary" and "zero tests passed" are different facts. Conflating
        # them is how a gate starts approving runs that never happened.
        result = merge_gate.parse_summary("......\r\n")
        assert result.passed is None
        assert not result.found


class TestCountRegressionGuard:
    def test_a_dropped_test_is_a_finding(self):
        findings = merge_gate.check_test_count(current=181, baseline=182)
        assert findings
        assert any("181" in f.detail and "182" in f.detail for f in findings)

    def test_an_equal_count_is_clean(self):
        assert merge_gate.check_test_count(current=182, baseline=182) == []

    def test_a_higher_count_is_clean_because_agents_add_tests(self):
        assert merge_gate.check_test_count(current=200, baseline=182) == []

    def test_the_guard_is_not_vacuous_without_a_baseline(self):
        # No baseline means the check cannot run. It must say so rather than
        # silently passing - a gate that quietly no-ops is worse than none.
        findings = merge_gate.check_test_count(current=182, baseline=None)
        assert findings
        assert any(f.kind == "no-baseline" for f in findings)


class TestPerFileRegressionGuard:
    """The global-total check is not safe once lanes commit concurrently.

    If lane A deletes 15 tests from its own file while lane B adds 20 to a
    different file, the repository total goes UP by 5 and a total-only guard
    reports success - while coverage in A's file actually fell. Only a per-file
    comparison sees that, and per-file is the shape the lane architecture
    needs.
    """

    def test_a_drop_in_one_file_is_caught_even_when_the_total_rises(self):
        baseline = {"tests/test_a.py": 40, "tests/test_b.py": 10}
        current = {"tests/test_a.py": 25, "tests/test_b.py": 30}
        assert sum(current.values()) > sum(baseline.values())  # total went UP
        findings = merge_gate.check_per_file_counts(current, baseline)
        assert findings
        assert any("test_a.py" in f.detail for f in findings)
        assert not any("test_b.py" in f.detail for f in findings)

    def test_a_file_that_vanished_entirely_is_caught(self):
        findings = merge_gate.check_per_file_counts({}, {"tests/test_a.py": 4})
        assert findings
        assert findings[0].kind == "file-vanished"

    def test_unchanged_counts_are_clean(self):
        counts = {"tests/test_a.py": 4}
        assert merge_gate.check_per_file_counts(counts, counts) == []

    def test_a_brand_new_file_is_clean(self):
        findings = merge_gate.check_per_file_counts(
            {"tests/test_a.py": 4, "tests/test_new.py": 9}, {"tests/test_a.py": 4}
        )
        assert findings == []

    def test_missing_baseline_is_reported_rather_than_silently_passing(self):
        findings = merge_gate.check_per_file_counts({"tests/test_a.py": 4}, None)
        assert findings
        assert findings[0].kind == "no-baseline"

    def test_the_finding_names_both_numbers(self):
        findings = merge_gate.check_per_file_counts(
            {"tests/test_a.py": 1}, {"tests/test_a.py": 7}
        )
        assert any("1" in f.detail and "7" in f.detail for f in findings)


class TestClaimedPaths:
    def test_a_path_the_agent_claimed_but_never_created_is_a_finding(self, tmp_path):
        findings = merge_gate.check_claimed_paths(["nope.py"], root=tmp_path)
        assert len(findings) == 1
        assert findings[0].kind == "missing"

    def test_an_empty_file_counts_as_not_delivered(self, tmp_path):
        (tmp_path / "hollow.py").write_text("", encoding="utf-8")
        findings = merge_gate.check_claimed_paths(["hollow.py"], root=tmp_path)
        assert len(findings) == 1
        assert findings[0].kind == "empty"

    def test_a_real_file_is_clean(self, tmp_path):
        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        assert merge_gate.check_claimed_paths(["real.py"], root=tmp_path) == []

    def test_a_directory_is_not_a_delivered_file(self, tmp_path):
        (tmp_path / "adir").mkdir()
        findings = merge_gate.check_claimed_paths(["adir"], root=tmp_path)
        assert findings and findings[0].kind == "not-a-file"


class TestMustContain:
    """A file existing is not evidence the claimed work is in it.

    The gate previously asked only: does this path exist, is it non-empty, is
    it a file. An agent that wrote a stub, edited the wrong file, or created the
    right file with the wrong content passed cleanly. `must_contain` closes
    that by re-reading the file and asserting the claimed content is actually
    present.

    The whole feature is ADDITIVE. `verify(claimed_paths=[...], baseline=...)`
    is quoted verbatim in CLAUDE.md and in all eight generated lane contracts,
    so a plain string must keep working exactly as before.
    """

    def test_a_plain_string_claim_still_works(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        assert merge_gate.check_claimed_paths(["a.py"], root=tmp_path) == []

    def test_a_dict_claim_passes_when_the_content_is_present(self, tmp_path):
        (tmp_path / "a.py").write_text("def parse_gvas():\n    pass\n", encoding="utf-8")
        claims = [{"path": "a.py", "must_contain": ["def parse_gvas"]}]
        assert merge_gate.check_claimed_paths(claims, root=tmp_path) == []

    def test_a_stub_that_lacks_the_claimed_content_is_a_finding(self, tmp_path):
        (tmp_path / "a.py").write_text("pass\n", encoding="utf-8")
        claims = [{"path": "a.py", "must_contain": ["def parse_gvas"]}]
        findings = merge_gate.check_claimed_paths(claims, root=tmp_path)
        assert findings
        assert findings[0].kind == "missing-content"
        assert "parse_gvas" in findings[0].detail

    def test_every_missing_fragment_is_reported_not_just_the_first(self, tmp_path):
        (tmp_path / "a.py").write_text("nothing here\n", encoding="utf-8")
        claims = [{"path": "a.py", "must_contain": ["alpha", "beta", "gamma"]}]
        findings = merge_gate.check_claimed_paths(claims, root=tmp_path)
        assert len(findings) == 3

    def test_a_single_string_fragment_is_accepted_not_only_a_list(self, tmp_path):
        (tmp_path / "a.py").write_text("hello\n", encoding="utf-8")
        claims = [{"path": "a.py", "must_contain": "hello"}]
        assert merge_gate.check_claimed_paths(claims, root=tmp_path) == []

    def test_a_missing_file_is_reported_as_missing_not_as_missing_content(self, tmp_path):
        claims = [{"path": "gone.py", "must_contain": ["anything"]}]
        findings = merge_gate.check_claimed_paths(claims, root=tmp_path)
        assert len(findings) == 1
        assert findings[0].kind == "missing"

    def test_an_unreadable_binary_does_not_crash_the_gate(self, tmp_path):
        (tmp_path / "b.bin").write_bytes(b"\xff\xfe\x00\x01")
        claims = [{"path": "b.bin", "must_contain": ["text"]}]
        findings = merge_gate.check_claimed_paths(claims, root=tmp_path)
        assert findings and findings[0].kind == "missing-content"

    def test_a_dict_without_must_contain_behaves_like_a_plain_path(self, tmp_path):
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        assert merge_gate.check_claimed_paths([{"path": "a.py"}], root=tmp_path) == []

    def test_mixed_plain_and_dict_claims_are_both_honoured(self, tmp_path):
        (tmp_path / "a.py").write_text("alpha\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("nothing\n", encoding="utf-8")
        claims = ["a.py", {"path": "b.py", "must_contain": ["beta"]}]
        findings = merge_gate.check_claimed_paths(claims, root=tmp_path)
        assert len(findings) == 1
        assert "b.py" in findings[0].detail

    def test_the_finding_names_the_file_and_the_fragment(self, tmp_path):
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        claims = [{"path": "a.py", "must_contain": ["needle"]}]
        detail = merge_gate.check_claimed_paths(claims, root=tmp_path)[0].detail
        assert "a.py" in detail and "needle" in detail


class TestAgainstTheRealSuite:
    """The parsers must work on what this machine actually prints, today."""

    def test_total_collected_matches_a_real_collect_only_run(self):
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        total = merge_gate.total_collected(proc.stdout)
        # This file's own tests are part of that number, so the only safe
        # assertion is a floor plus internal consistency - never a hard-coded
        # count, which CLAUDE.md forbids precisely because it goes stale.
        assert total > 0
        assert total == sum(merge_gate.parse_collect_counts(proc.stdout).values())


# Captured VERBATIM on 2026-09-06 from a pytest run deliberately aborted with
# MemoryError inside the terminal-summary phase. Two things about it matter:
# the run printed NO stats line at all, and the FAILURES section echoed this
# file's own sample data - "182 passed in 0.78s" is a literal in SUMMARY_PASS
# above. A parser that greps the whole blob reads that echo as the summary.
ABORTED_IN_TERMINAL_SUMMARY = (
    "..FF                                                           [100%]\r\n"
    "================================= FAILURES ==================================\r\n"
    "___________________________ test_first_failure ______________________________\r\n"
    "tests/test_sample.py:13: in test_first_failure\r\n"
    '    assert SUMMARY_PASS == "sentinel-one"\r\n'
    "E   AssertionError: assert '........ [10...ed in 0.78s' == 'sentinel-one'\r\n"
    "E     - sentinel-one\r\n"
    "E     + ........ [100%]\r\n"
    "E     + 182 passed in 0.78s\r\n"
    "========================= short test summary info ===========================\r\n"
    "FAILED tests/test_sample.py::test_first_failure - AssertionError\r\n"
    "Traceback (most recent call last):\r\n"
    '  File "conftest.py", line 41, in pytest_terminal_summary\r\n'
    "    raise MemoryError()\r\n"
    "MemoryError\r\n"
)

# Captured VERBATIM on 2026-09-06 from a pytest run aborted with MemoryError
# inside _pytest/_code/source.py getstatementrange_ast -> ast.parse, which is
# the exact site ROADMAP OPS-30 path 1 records. Four tests, two of which fail.
# pytest still printed a stats line - and it counts only the tests it got
# through before the abort, so it says "2 passed" and names no failure at all.
ABORTED_MID_RUN_TRUNCATED_SUMMARY = (
    "..Traceback (most recent call last):\r\n"
    '  File "_pytest/_code/source.py", line 191, in getstatementrange_ast\r\n'
    '    astnode = ast.parse(content, "source", "exec")\r\n'
    "MemoryError\r\n"
    "INTERNALERROR> Traceback (most recent call last):\r\n"
    "INTERNALERROR>   MemoryError\r\n"
    "\r\n"
    "2 passed in 0.08s\r"
)

# Measured on 2026-09-06 from a clean full run of this repository. pytest
# appends a wall-clock suffix once a run passes a minute, so the summary line
# is NOT simply "<n> passed in <x>s" and a parser that assumes it is will stop
# recognising this repository's own green runs.
REAL_LONG_RUN_SUMMARY = "1781 passed in 111.56s (0:01:51)\r"


class TestSummaryLineIsAnchoredNotGrepped:
    """The summary must be read off a summary LINE, not grepped out of the blob.

    ``tests/test_merge_gate.py`` carries "182 passed in 0.78s" as sample data,
    so any pytest run that renders a failure in this file echoes a
    summary-shaped string into its own output. A whole-blob search cannot tell
    that echo apart from the real thing, and on an aborted run there is no real
    thing to outrank it.
    """

    def test_echoed_sample_data_is_not_mistaken_for_a_summary(self):
        result = merge_gate.parse_summary(ABORTED_IN_TERMINAL_SUMMARY)
        assert not result.found
        assert result.passed is None

    def test_a_summary_under_the_equals_banner_is_still_found(self):
        text = "=================== 1 failed, 3 passed in 0.05s ===================\r"
        result = merge_gate.parse_summary(text)
        assert result.found
        assert result.passed == 3
        assert result.failed == 1

    def test_the_wall_clock_suffix_on_a_long_run_is_still_a_summary(self):
        result = merge_gate.parse_summary(REAL_LONG_RUN_SUMMARY)
        assert result.found
        assert result.passed == 1781
        assert result.failed == 0

    def test_the_last_summary_line_wins_over_an_earlier_echo(self):
        text = "E     + 182 passed in 0.78s\r\n5 passed in 0.30s\r"
        result = merge_gate.parse_summary(text)
        assert result.passed == 5

    def test_no_tests_ran_is_a_summary_not_an_absence(self):
        result = merge_gate.parse_summary("no tests ran in 0.01s\r")
        assert result.found
        assert result.passed == 0

    def test_a_quoted_ZERO_failed_ahead_of_the_stats_line_does_not_win(self):
        """Found by the cycle 50 RE-AUDIT of the historical sign-offs.

        The pre-fix parser searched the whole blob, so the FIRST `N failed`
        won. That made a COMPLETED failing run reachable, which LL-0145's
        account of the defect did not cover - it named only aborted runs.

        MEASURED end to end with a real pytest run: a suite ending
        `3 failed, 1851 passed in 115.53s`, exit 1, was read by the old parser
        as passed=1772, failed=0, errors=0 - ZERO findings, so the old gate
        signed off on a COMPLETED, FAILING run. The string it latched onto is
        real and still in the tree: `docs/LEDGER.md` carries the prose
        `1772 passed, 0 failed` in the entry describing the OPS-29 near miss.

        THE LIMIT, because this docstring's first draft overstated it and the
        refutation pass caught that: the failing test which rendered that
        prose was written FOR the demonstration. The repo's own
        ledger-scanning tests print the offending TOKEN and the citing
        FILENAME, not the file's text, and under two separate ledger
        corruptions neither emitted `0 failed`. The mechanism is proven; an
        existing in-repo test that triggers it is NOT.

        The anchor already closes this, because the quoted line is indented
        and the real stats line is not. This test is what keeps it closed.
        """
        text = (
            "=================================== FAILURES ==================\n"
            "    quoted from the ledger: `1772 passed, 0 failed` from a run\n"
            "3 failed, 1851 passed in 115.53s\n"
        )
        result = merge_gate.parse_summary(text)
        assert result.failed == 3, (
            "a quoted '0 failed' preempted the run's own stats line"
        )
        assert result.passed == 1851

    def test_an_INDENTED_summary_shaped_line_is_quoted_output_not_a_summary(self):
        """Found by the cycle 49 refutation pass - the fix's own residual hole.

        pytest writes its stats line at column 0. An INDENTED one is quoted
        output: a source line inside a traceback, or captured logging. The
        first cut stripped leading whitespace before anchoring, which threw
        away the one thing that tells the two apart, so this exact blob was
        read as a real summary of 182 passed and - with returncode 0 - drew
        ZERO findings from `check_run_completed`. The gate would have signed
        off on it.

        This is the same defect as the original whole-blob grep, one layer in:
        anchoring that strips first is not anchoring.
        """
        text = "=== FAILURES ===\n    Expected output was:\n    182 passed in 12.00s\n"
        result = merge_gate.parse_summary(text)
        assert not result.found, (
            "an indented, quoted stats line was read as pytest's own summary"
        )
        assert result.passed is None

    def test_and_the_same_line_at_column_zero_IS_a_summary(self):
        """The negative above must not be passing for the wrong reason.

        Without this, deleting the whole summary-matching branch would leave
        the indentation test green - a guard that passes because nothing is
        ever found is decoration.
        """
        result = merge_gate.parse_summary("182 passed in 12.00s\n")
        assert result.found
        assert result.passed == 182

    def test_a_stats_line_with_no_DURATION_tail_is_refused(self):
        """Pins the `in <dur>s` requirement, which was load-bearing and
        unpinned - the refutation pass made the tail optional and all 48
        tests in this file stayed green. Bare "182 passed" appears in prose
        and in assertion text; only the timed form is pytest's own line.
        """
        assert merge_gate.find_summary_line("182 passed\n") is None
        assert merge_gate.find_summary_line("182 passed in 0.78s\n") is not None

    def test_the_scan_runs_BACKWARD_and_the_later_summary_wins(self):
        """Pins the scan DIRECTION, also load-bearing and unpinned - reversing
        it to a forward scan changed the answer from 1849 to 182 while all 48
        tests stayed green. The sibling test above uses an echo that is not
        itself summary-shaped at column 0; this one puts two REAL summaries in
        one blob so only the direction can decide.
        """
        text = "182 passed in 12.00s\n1849 passed in 118.20s\n"
        # `find_summary_line` returns the STATS group, not the whole line, so
        # the duration tail is matched and then dropped. Asserted on the value
        # the function actually returns rather than the one the name suggests -
        # the first cut of this test asserted the latter and went red for a
        # reason that had nothing to do with scan direction.
        assert merge_gate.find_summary_line(text) == "1849 passed"


class TestARunThatDidNotCompleteIsNeverSignedOff:
    """ROADMAP OPS-30 criterion 4, mechanised.

    A pytest run can abort and STILL print a well-formed stats line, because
    the line counts what the run got through rather than what it was asked to
    do. The measured case says "2 passed" for a run of four tests, two of them
    failing, that died with MemoryError and exited 3. Text alone cannot refute
    that; the exit code can.
    """

    def test_a_truncated_summary_from_an_aborted_run_is_a_finding(self):
        run = merge_gate.RunResult(text=ABORTED_MID_RUN_TRUNCATED_SUMMARY, returncode=3)
        findings = merge_gate.check_run_completed(run)
        assert findings
        kinds = {f.kind for f in findings}
        assert "internal-error" in kinds

    def test_a_nonzero_exit_under_a_spotless_summary_is_a_finding(self):
        # No INTERNALERROR marker at all - the exit code is the only witness.
        run = merge_gate.RunResult(text="2 passed in 0.08s\r", returncode=3)
        findings = merge_gate.check_run_completed(run)
        assert findings
        assert any(f.kind == "exit-mismatch" for f in findings)
        assert any("3" in f.detail for f in findings)

    def test_a_clean_green_run_produces_no_findings(self):
        run = merge_gate.RunResult(text=REAL_LONG_RUN_SUMMARY, returncode=0)
        assert merge_gate.check_run_completed(run) == []

    def test_a_summaryless_run_is_a_finding(self):
        run = merge_gate.RunResult(text="......\r\n", returncode=1)
        findings = merge_gate.check_run_completed(run)
        assert any(f.kind == "no-summary" for f in findings)

    def test_an_ordinary_test_failure_is_reported_as_a_failure_not_a_crash(self):
        # exit 1 with failures counted is pytest working correctly. It is a
        # finding, but it must not be dressed up as an aborted run.
        run = merge_gate.RunResult(text="2 failed, 2 passed in 0.08s\r", returncode=1)
        findings = merge_gate.check_run_completed(run)
        kinds = {f.kind for f in findings}
        assert "failed" in kinds
        assert "exit-mismatch" not in kinds
        assert "no-summary" not in kinds

    def test_errors_are_reported_separately_from_failures(self):
        run = merge_gate.RunResult(text="1 failed, 2 errors in 0.5s\r", returncode=1)
        kinds = {f.kind for f in merge_gate.check_run_completed(run)}
        assert kinds == {"failed", "errors"}


def _write_suite_that_dies_with_memoryerror(root):
    """Build a real, runnable pytest project that aborts the way OPS-30 did.

    The injection point is the one the ROADMAP measured: MemoryError raised at
    ``_pytest/_code/source.py`` ``getstatementrange_ast`` -> ``ast.parse``,
    scoped to that module's own ``ast`` lookup so collection and the assertion
    rewriter are untouched. The project has four tests, two of which fail, so
    a run that aborts while rendering the first failure reports "2 passed".
    """
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text(
        "[pytest]\n"
        "testpaths = tests\n"
        "python_files = test_*.py\n"
        "addopts = -q --tb=short -r fE\n",
        encoding="utf-8",
    )
    (root / "conftest.py").write_text(
        "import ast as _realast\n"
        "import _pytest._code.source as _src\n"
        "\n"
        "\n"
        "class _Shim:\n"
        "    def __getattr__(self, name):\n"
        "        return getattr(_realast, name)\n"
        "\n"
        "    def parse(self, *args, **kwargs):\n"
        "        raise MemoryError()\n"
        "\n"
        "\n"
        "_src.ast = _Shim()\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_x.py").write_text(
        "def test_ok_one():\n"
        "    assert 1 == 1\n"
        "\n"
        "\n"
        "def test_ok_two():\n"
        "    assert 2 == 2\n"
        "\n"
        "\n"
        "def test_bad_one():\n"
        "    assert 1 == 2\n"
        "\n"
        "\n"
        "def test_bad_two():\n"
        "    assert 3 == 4\n",
        encoding="utf-8",
    )


class TestVerifyAgainstASuiteThatReallyDies:
    """End to end, with a real subprocess - not a simulated blob.

    ROADMAP OPS-30 criterion 4 says a gate that reports success on a run which
    died without a trustworthy summary is a worse defect than the MemoryError
    itself. This is that check, run against a suite that actually dies.
    """

    def test_verify_refuses_a_suite_that_aborted_with_memoryerror(self, tmp_path):
        _write_suite_that_dies_with_memoryerror(tmp_path)
        report = merge_gate.verify(baseline=4, root=tmp_path)
        assert report.collected == 4, "the collect pass must still see 4 tests"
        assert not report.ok, f"gate signed off on an aborted run: {report.format()}"
        kinds = {f.kind for f in report.findings}
        assert kinds & {"internal-error", "exit-mismatch", "no-summary"}


class TestTheExitCodeIsActuallyCarried:
    """``check_run_completed`` is only as good as the code handed to it.

    Every other test in this file constructs :class:`RunResult` by hand, so
    all of them stay green if ``_run`` quietly reports 0 for every invocation -
    which is exactly what the old code did by discarding ``proc.returncode``.
    This runs a real pytest subprocess and reads the code back, so the wiring
    between the subprocess and the guard is itself under test.
    """

    def _project(self, root, body):
        (root / "tests").mkdir(parents=True, exist_ok=True)
        (root / "pytest.ini").write_text(
            "[pytest]\ntestpaths = tests\npython_files = test_*.py\naddopts = -q\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_x.py").write_text(body, encoding="utf-8")

    def test_a_failing_suite_reports_exit_1_not_0(self, tmp_path):
        self._project(tmp_path, "def test_bad():\n    assert 1 == 2\n")
        run = merge_gate.suite_result(root=tmp_path)
        assert run.returncode == 1, f"exit code lost: {run!r}"
        assert merge_gate.parse_summary(run.text).failed == 1

    def test_a_passing_suite_reports_exit_0(self, tmp_path):
        self._project(tmp_path, "def test_good():\n    assert 1 == 1\n")
        run = merge_gate.suite_result(root=tmp_path)
        assert run.returncode == 0
        assert merge_gate.parse_summary(run.text).passed == 1

    def test_a_usage_error_reports_its_own_code_not_a_guess(self, tmp_path):
        # A rootdir with no tests at all exits 5 (no tests collected). Any
        # code other than 0 or 1 means the run never reached the end, and the
        # gate has to be able to see it.
        (tmp_path / "tests").mkdir()
        (tmp_path / "pytest.ini").write_text(
            "[pytest]\ntestpaths = tests\npython_files = test_*.py\naddopts = -q\n",
            encoding="utf-8",
        )
        run = merge_gate.suite_result(root=tmp_path)
        assert run.returncode == 5
        assert any(
            f.kind == "exit-mismatch" for f in merge_gate.check_run_completed(run)
        )


def _write_two_file_project(root, a_count=1, b_count=2):
    """Build a real, runnable pytest project with tests split across two files.

    Two files is the minimum that can express the failure
    :func:`merge_gate.check_per_file_counts` exists for - one file losing
    tests while another gains more, so the repository total RISES and a
    total-only guard reports success. Everything written here passes; the
    thing under test is the COUNT, not the outcome.
    """
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text(
        "[pytest]\ntestpaths = tests\npython_files = test_*.py\naddopts = -q\n",
        encoding="utf-8",
    )
    for stem, count in (("a", a_count), ("b", b_count)):
        body = "\n\n\n".join(
            f"def test_{stem}_{i}():\n    assert True" for i in range(count)
        )
        (root / "tests" / f"test_{stem}.py").write_text(body + "\n", encoding="utf-8")


class TestVerifyActuallyRunsThePerFileGuard:
    """The first structural hole recorded under ROADMAP ``OPS-31``.

    ``check_per_file_counts`` was exported in ``__all__``, cited by all eight
    generated lane contracts, covered by six of its own tests - and NEVER
    CALLED. Nothing outside its own definition and those tests invoked it,
    which is precisely how a check that has never run reads as a live guard.

    The algorithm is already covered by ``TestPerFileRegressionGuard`` above,
    and every one of those tests stayed green for as long as the function was
    dead code. These tests cover the WIRING instead: that ``verify`` reaches
    it, and that the finding survives into the composed report.
    """

    def test_a_per_file_drop_is_caught_although_the_repository_total_ROSE(self, tmp_path):
        # 1 + 5 = 6 collected now, against a baseline of 4. The TOTAL guard is
        # clean by construction, so any finding here can only have come from
        # the per-file comparison - and `check_test_count` never names a path
        # in its detail, so the path assertion below cannot be satisfied by it.
        _write_two_file_project(tmp_path, a_count=1, b_count=5)
        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=4,
            per_file_baseline={"tests/test_a.py": 3, "tests/test_b.py": 1},
            root=tmp_path,
        )
        assert report.collected == 6
        assert not report.ok, f"a per-file drop under a rising total was missed: {report.format()}"
        detail = " ".join(f.detail for f in report.findings)
        assert "tests/test_a.py" in detail, "the finding does not name the file that shrank"
        assert "tests/test_b.py" not in detail, "the file that GREW was reported as a loss"

    def test_a_file_that_vanished_entirely_reaches_the_report(self, tmp_path):
        _write_two_file_project(tmp_path, a_count=1, b_count=2)
        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={
                "tests/test_a.py": 1,
                "tests/test_b.py": 2,
                "tests/test_gone.py": 7,
            },
            root=tmp_path,
        )
        assert not report.ok
        assert any(f.kind == "file-vanished" for f in report.findings), report.format()

    def test_a_clean_per_file_baseline_still_signs_off(self, tmp_path):
        # The companion that stops the two tests above from passing for the
        # wrong reason. If `verify` refused everything the moment a per-file
        # baseline appeared, both would be green and neither would mean
        # anything. A negative assertion rules something out without pinning
        # anything down; this pins it.
        _write_two_file_project(tmp_path, a_count=2, b_count=2)
        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )
        assert report.ok, report.format()


class TestVerifyDefaultsAreNotSilent:
    """The second structural hole recorded under ROADMAP ``OPS-31``.

    ``verify(claimed_paths=(), baseline=None)`` defaults BOTH arguments to
    something that checks nothing. ``baseline=None`` at least raises a
    ``no-baseline`` finding. An empty ``claimed_paths`` was completely silent:
    the caller got ``ok=True`` with the file-existence probe having examined
    ZERO files, and nothing in the report said so. A gate that reports OK
    after checking nothing is the exact failure this module exists to prevent.
    """

    def test_claiming_nothing_is_a_finding_rather_than_a_quiet_pass(self, tmp_path):
        _write_two_file_project(tmp_path, a_count=1, b_count=2)
        report = merge_gate.verify(
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )
        assert not report.ok, "the gate signed off having examined zero claimed files"
        assert any(f.kind == "no-claims" for f in report.findings), report.format()

    def test_claiming_one_real_file_clears_it(self, tmp_path):
        # Non-vacuity companion: the finding above has to be caused by the
        # empty claim list, not by anything else about this project.
        _write_two_file_project(tmp_path, a_count=1, b_count=2)
        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )
        assert report.ok, report.format()
        assert not any(f.kind == "no-claims" for f in report.findings)

    def test_an_absent_per_file_baseline_is_NAMED_in_an_otherwise_OK_report(self, tmp_path):
        # This one cannot be a finding without breaking nine documents: the
        # invocation quoted in CLAUDE.md and in all eight generated lane
        # contracts passes only `claimed_paths` and `baseline`, so a hard
        # failure here would make the documented call always red. It is
        # recorded as an UNCHECKED note instead - visible in `format()` even
        # on an OK report, which is the difference between a stated limit and
        # a silence.
        _write_two_file_project(tmp_path, a_count=1, b_count=2)
        report = merge_gate.verify(claimed_paths=["pytest.ini"], baseline=3, root=tmp_path)
        assert report.ok, report.format()
        assert report.notes, "an OK report claimed nothing had been left unchecked"
        rendered = report.format()
        assert rendered.startswith("merge gate: OK")
        assert "per-file" in rendered, rendered

    def test_supplying_the_per_file_baseline_leaves_no_PER_FILE_unchecked_note(
        self, tmp_path
    ):
        """Narrowed from ``notes == ()`` when ``OPS-58`` wired the drift check.

        A tmp root has never been dispatched into, so it never has a
        dispatch-time store reading and the drift check honestly reports that
        it did not run. Asserting an EMPTY notes tuple would now be asserting
        that a second unchecked probe stays silent, which is the opposite of
        what this class exists to defend. The assertion is therefore made
        exact rather than loosened: one note, and it is the drift one.
        """
        _write_two_file_project(tmp_path, a_count=1, b_count=2)
        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )
        assert len(report.notes) == 1, report.format()
        assert "per-file" not in report.notes[0], report.notes[0]
        assert "store-drift" in report.notes[0], report.notes[0]

    def test_the_docstring_keeps_the_weakness_the_code_cannot_fix(self):
        """``baseline`` is supplied by the very caller whose work is under test.

        Nothing in this module can close that: the gate has no independent
        record of what the count was before the work started, and deriving one
        after the fact would compare the tree against itself. What it CAN do
        is refuse to let the limit go unwritten, and this pins the TEXT rather
        than a behaviour - said plainly, because a guard that looks like a
        behavioural check and is not is the same species of decoration as the
        dead function above.
        """
        doc = merge_gate.verify.__doc__ or ""
        assert "caller whose work is under test" in doc


class TestUncheckedNotesRenderOnTheFAILUREBranchToo:
    """`format` appends `[unchecked]` notes in BOTH branches - pin both.

    The docstring on `GateReport.format` claims both branches. The OK branch
    was tested; the FAILURE branch was not, so moving the `lines.extend(...)`
    inside the `if self.ok:` arm left all merge-gate tests green. Found by the
    cycle-51 refutation pass. A claim that is true of the code and untrue of
    the guard is the shape this module exists to refuse.

    Why the failure branch matters despite being the less surprising one: a
    report that has findings AND a probe that never ran is the case where a
    reader is most likely to fix the findings, re-run, see OK, and never learn
    that a check was skipped throughout.
    """

    NOTE = "the per-file regression check did not run - no per_file_baseline"

    def test_a_note_renders_when_the_report_is_OK(self):
        report = merge_gate.GateReport(
            ok=True, findings=(), collected=10, summary=None, notes=(self.NOTE,)
        )
        rendered = report.format()
        assert "merge gate: OK" in rendered
        assert f"[unchecked] {self.NOTE}" in rendered, rendered

    def test_a_note_renders_when_the_report_has_FINDINGS(self):
        report = merge_gate.GateReport(
            ok=False,
            findings=(merge_gate.Finding(kind="no-claims", detail="nothing claimed"),),
            collected=10,
            summary=None,
            notes=(self.NOTE,),
        )
        rendered = report.format()
        assert "1 finding(s)" in rendered
        assert "[no-claims]" in rendered
        assert f"[unchecked] {self.NOTE}" in rendered, (
            "the unchecked note vanished from the FAILURE branch - a probe that "
            "did not run must be visible whether or not other probes found "
            "something:\n" + rendered
        )

    def test_no_note_renders_when_there_is_nothing_unchecked(self):
        """Negative control - the marker must not appear unconditionally."""
        report = merge_gate.GateReport(
            ok=False,
            findings=(merge_gate.Finding(kind="no-claims", detail="nothing claimed"),),
            collected=10,
            summary=None,
            notes=(),
        )
        assert "[unchecked]" not in report.format()


# ---------------------------------------------------------------------------
# store drift reaches the gate - ROADMAP OPS-58
# ---------------------------------------------------------------------------


def _git(repo, *args: str) -> None:
    """Run one git command inside a THROWAWAY repository, with a fabricated
    identity passed by ``-c`` rather than read from this machine.

    Every command here is scoped to ``tmp_path``. None of them may ever be
    aimed at the shared worktree - that is the whole content of
    :data:`ops.store_drift.SHARED_WORKTREE_BAN`.
    """
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Lanternlight Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _snapshot(objects, subjects=None, unreachable=(), errors=(), at="2026-09-08T00:00:00+00:00"):
    """Build a StoreSnapshot by hand, so the comparison logic needs no git."""
    return store_drift.StoreSnapshot(
        root="somewhere",
        at=at,
        objects=dict(objects),
        subjects=dict(subjects or {}),
        unreachable=frozenset(unreachable),
        errors=tuple(errors),
    )


SHA_SEED = "a" * 40
SHA_WIP = "b" * 40
SHA_INDEX = "c" * 40


class TestADriftAnswerReachesTheRenderedReport:
    """``OPS-58`` criterion 1 - the WIRING, not the detector.

    ``OPS-54`` already proves :func:`ops.store_drift.compare` names a stash.
    Every one of those tests stayed green for the whole week the detector was
    called by nothing at all, which is the same shape as the dead per-file
    guard recorded under ``OPS-31``. What is under test here is that the
    answer travels: out of the detector, into a :class:`GateReport`, and out
    of :meth:`GateReport.format` where a merger actually reads it.
    """

    def _stashed(self):
        before = _snapshot({SHA_SEED: "commit"}, {SHA_SEED: "seed"})
        after = _snapshot(
            {SHA_SEED: "commit", SHA_WIP: "commit", SHA_INDEX: "commit"},
            {
                SHA_SEED: "seed",
                SHA_WIP: "WIP on main: 6acc6b7 seed",
                SHA_INDEX: "index on main: 6acc6b7 seed",
            },
        )
        return before, after

    def test_a_stash_between_the_readings_is_named_in_the_rendered_report(self) -> None:
        before, after = self._stashed()

        measurement, notes = merge_gate.describe_store_drift(before, after)

        assert notes == (), notes
        report = merge_gate.GateReport(
            ok=True, findings=(), collected=10, summary=None, measurement=measurement
        )
        rendered = report.format()
        assert SHA_WIP in rendered, rendered
        assert SHA_INDEX in rendered, rendered
        assert "WIP on main" in rendered, rendered

    def test_verify_itself_carries_the_answer_and_not_only_the_helper(
        self, tmp_path, monkeypatch
    ) -> None:
        """The helper being right proves nothing about ``verify`` calling it.

        ``check_per_file_counts`` was right and uncalled for weeks. This
        drives the composed entry point and reads its rendered output.
        """
        before, after = self._stashed()
        monkeypatch.setattr(
            merge_gate,
            "read_store_drift",
            lambda *args, **kwargs: merge_gate.describe_store_drift(before, after),
        )
        _write_two_file_project(tmp_path, a_count=1, b_count=2)

        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )

        assert SHA_WIP in report.format(), report.format()

    def test_a_drift_answer_does_not_by_itself_refuse_the_merge(self) -> None:
        """Drift changes what you check next, not whether you merge.

        Real stashes have been taken in this repository during a session in
        which nothing was lost. Turning that into a refusal would make the
        gate say no on a routine day, and a gate that always says no is a
        gate nobody runs. No count is stated: ``OPS-60`` measured that a
        commit count cannot be converted into a stash count.
        """
        before, after = self._stashed()
        measurement, _ = merge_gate.describe_store_drift(before, after)

        report = merge_gate.GateReport(
            ok=True, findings=(), collected=10, summary=None, measurement=measurement
        )
        assert report.ok
        assert report.format().startswith("merge gate: OK")


class TestAnAbsentBaselineIsNeverReportedAsNoDrift:
    """``OPS-58`` criterion 2, and the ``OPS-53`` defect one level down.

    The dispatch ritual is a ritual: no code calls it for anyone, so for a
    while the common case is that no before-reading exists. A gate that
    answers "no drift" from an empty record has asserted something its record
    cannot support. Saying the check DID NOT RUN is the floor.
    """

    def test_no_baseline_produces_an_unchecked_note_and_no_measurement(self) -> None:
        after = _snapshot({SHA_SEED: "commit"}, {SHA_SEED: "seed"})

        measurement, notes = merge_gate.describe_store_drift(None, after)

        assert measurement == (), measurement
        assert len(notes) == 1, notes
        assert "did not run" in notes[0], notes[0]

    @pytest.mark.parametrize(
        "forbidden",
        ["no drift", "did not move", "no movement", "clean"],
    )
    def test_the_note_never_claims_the_store_held_still(self, forbidden: str) -> None:
        after = _snapshot({SHA_SEED: "commit"})

        _, notes = merge_gate.describe_store_drift(None, after)

        assert forbidden not in notes[0].lower(), notes[0]

    def test_the_note_says_where_the_reading_should_have_come_from(self) -> None:
        _, notes = merge_gate.describe_store_drift(None, _snapshot({}), where="ops/runtime/x.json")

        assert "ops/runtime/x.json" in notes[0], notes[0]
        assert "dispatch" in notes[0], notes[0]

    def test_the_note_renders_in_the_same_unchecked_shape_as_the_per_file_one(self) -> None:
        _, notes = merge_gate.describe_store_drift(None, _snapshot({}))

        report = merge_gate.GateReport(
            ok=True, findings=(), collected=10, summary=None, notes=notes
        )
        assert f"[unchecked] {notes[0]}" in report.format()

    def test_verify_reports_the_unchecked_note_when_no_reading_was_taken(
        self, tmp_path
    ) -> None:
        """End of the wire: a tmp root has never been dispatched into."""
        _write_two_file_project(tmp_path, a_count=1, b_count=2)

        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=tmp_path,
        )

        rendered = report.format()
        assert report.ok, rendered
        assert any("store-drift" in note for note in report.notes), report.notes
        assert "[unchecked]" in rendered, rendered


class TestADriftAnswerIsDistinguishableFromAFindingAboutTheWork:
    """``OPS-58`` criterion 3.

    "a file you claimed is missing" and "your numbers were taken on a moving
    tree" are different KINDS of statement. The first says the work may be
    wrong. The second says nothing whatever about the work, and a merger who
    reads them as one list will either ignore both or block on both.
    """

    def _both(self):
        before = _snapshot({SHA_SEED: "commit"}, {SHA_SEED: "seed"})
        after = _snapshot(
            {SHA_SEED: "commit", SHA_WIP: "commit"},
            {SHA_SEED: "seed", SHA_WIP: "WIP on main: 6acc6b7 seed"},
        )
        measurement, _ = merge_gate.describe_store_drift(before, after)
        return merge_gate.GateReport(
            ok=False,
            findings=(
                merge_gate.Finding(
                    kind="missing", detail="a.py was claimed but does not exist"
                ),
            ),
            collected=10,
            summary=None,
            measurement=measurement,
        )

    def test_the_rendered_report_separates_the_two_with_a_header(self) -> None:
        rendered = self._both().format()

        assert merge_gate.MEASUREMENT_HEADER[0] in rendered, rendered
        finding_at = rendered.index("a.py was claimed")
        header_at = rendered.index(merge_gate.MEASUREMENT_HEADER[0])
        drift_at = rendered.index(SHA_WIP)
        assert finding_at < header_at < drift_at, rendered

    def test_the_header_says_in_words_that_it_is_not_a_verdict_on_the_work(self) -> None:
        header = " ".join(merge_gate.MEASUREMENT_HEADER).lower()

        assert "not a verdict" in header, header
        assert "moving tree" in header, header

    def test_the_header_is_absent_when_there_is_nothing_to_say(self) -> None:
        """Negative control - the separator must not print unconditionally."""
        report = merge_gate.GateReport(
            ok=True, findings=(), collected=10, summary=None
        )

        assert merge_gate.MEASUREMENT_HEADER[0] not in report.format()

    def test_a_drift_line_is_never_counted_as_a_finding(self) -> None:
        report = self._both()

        assert "1 finding(s)" in report.format(), report.format()


class TestTheGateCannotCrashOnThis:
    """``OPS-58`` criterion 6.

    The gate is consulted at merge time. A merger who cannot run it stops
    running it, and then the claim goes unchecked AND the drift goes
    unwatched. Every failure of the underlying git commands is an
    unanswerable question, never an exception.
    """

    def test_an_unimportable_detector_is_a_note_rather_than_a_traceback(
        self, monkeypatch
    ) -> None:
        real_import = builtins.__import__

        def refuse(name, *args, **kwargs):
            if name.startswith("ops"):
                raise ImportError(f"no module named {name}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", refuse)

        measurement, notes = merge_gate.read_store_drift(REPO_ROOT)

        assert measurement == ()
        assert len(notes) == 1
        assert "did not run" in notes[0], notes[0]

    def test_a_detector_that_raises_outright_is_a_note_rather_than_a_traceback(
        self, monkeypatch
    ) -> None:
        def explode(*args, **kwargs):
            raise RuntimeError("git went away mid-read")

        monkeypatch.setattr(store_drift, "snapshot", explode)
        monkeypatch.setattr(
            state_mod, "load_store_snapshot", lambda path=None: _snapshot({SHA_SEED: "commit"})
        )

        measurement, notes = merge_gate.read_store_drift(REPO_ROOT)

        assert measurement == ()
        assert len(notes) == 1
        assert "did not run" in notes[0], notes[0]

    def test_a_probe_failure_is_reported_as_unanswerable_not_as_clean(self) -> None:
        before = _snapshot({SHA_SEED: "commit"})
        after = _snapshot({}, errors=["git fsck: exit 128: not a git repository"])

        measurement, notes = merge_gate.describe_store_drift(before, after)

        rendered = "\n".join(measurement).lower()
        assert "could not answer" in rendered, rendered
        assert notes == (), notes

    def test_reading_an_unusable_root_answers_rather_than_raising(self, tmp_path) -> None:
        """No repository, no snapshot file, no git objects - and no exception."""
        measurement, notes = merge_gate.read_store_drift(tmp_path)

        assert measurement == ()
        assert len(notes) == 1

    def test_a_clean_pair_says_the_store_held_still_in_so_many_words(self) -> None:
        """Non-vacuity companion for the whole class.

        Every test above asserts something did NOT happen. This one pins the
        positive case, so a describe_store_drift that returned empty tuples
        forever would fail here rather than pass everything.
        """
        before = _snapshot({SHA_SEED: "commit"}, {SHA_SEED: "seed"})
        after = _snapshot({SHA_SEED: "commit"}, {SHA_SEED: "seed"})

        measurement, notes = merge_gate.describe_store_drift(before, after)

        assert notes == (), notes
        assert measurement, "a clean, ANSWERED comparison said nothing at all"
        assert "did not move" in "\n".join(measurement), measurement


class TestEndToEndAgainstARealStashInAThrowawayRepository:
    """``OPS-58`` criterion 5. Real git, real stash, real rendered gate output.

    Everything above builds snapshots by hand, which proves the wiring and
    proves nothing about whether git behaves as the wiring assumes. This runs
    the whole path: a dispatch inside a throwaway repository, a real
    ``git stash``, then ``verify`` rendering the two commits it wrote.

    A measured fact worth keeping, because it is counter-intuitive: while the
    stash EXISTS, ``git fsck --unreachable`` reports nothing, because the
    stash ref keeps the pair reachable. Detection here does not depend on
    reachability - it depends on the pair not being in the earlier reading.
    """

    def _project_repo(self, tmp_path):
        repo = tmp_path / "throwaway"
        repo.mkdir()
        _write_two_file_project(repo, a_count=1, b_count=2)
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")
        return repo

    def test_a_real_stash_reaches_the_rendered_gate_output(self, tmp_path) -> None:
        repo = self._project_repo(tmp_path)
        state_mod.dispatch("OPS-58", path=repo / "loop_state.json")

        (repo / "tests" / "test_a.py").write_text(
            "def test_a_0():\n    assert True\n\n\ndef test_extra():\n    assert True\n",
            encoding="utf-8",
        )
        # No ``-m``. Measured 2026-09-08: a message REPLACES the WIP commit's
        # subject with the operator's own text, so only the ``index on `` half
        # of the pair matches STASH_SUBJECT_PREFIXES. A plain stash is the
        # shape a slice actually produces by accident, and it is the shape
        # that shows both commits.
        _git(repo, "stash", "push")

        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=repo,
            snapshot_path=repo / state_mod.STORE_SNAPSHOT_FILENAME,
        )

        rendered = report.format()
        assert "STASH-SHAPED COMMITS: 2" in rendered, rendered
        assert "WIP on main" in rendered, rendered
        assert merge_gate.MEASUREMENT_HEADER[0] in rendered, rendered
        # And it did NOT refuse the merge. Added after the mutation pass:
        # folding `measurement` into `ok` survived every other test in this
        # file, because they all build a GateReport by hand and none of them
        # drove `verify` with drift actually present. Drift changes what you
        # check next, not whether you merge.
        assert report.ok, rendered

    def test_the_same_path_goes_quiet_when_nothing_stashed(self, tmp_path) -> None:
        """The companion without which the test above proves nothing.

        If the drift block rendered on every run, the stash assertions would
        be satisfied by a report that says the same thing about an untouched
        repository.
        """
        repo = self._project_repo(tmp_path)
        state_mod.dispatch("OPS-58", path=repo / "loop_state.json")

        report = merge_gate.verify(
            claimed_paths=["pytest.ini"],
            baseline=3,
            per_file_baseline={"tests/test_a.py": 1, "tests/test_b.py": 2},
            root=repo,
            snapshot_path=repo / state_mod.STORE_SNAPSHOT_FILENAME,
        )

        rendered = report.format()
        assert "STASH-SHAPED COMMITS" not in rendered, rendered
        assert "did not move" in rendered, rendered
