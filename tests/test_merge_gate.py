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

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import merge_gate  # noqa: E402

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
