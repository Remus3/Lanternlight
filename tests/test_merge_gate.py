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
