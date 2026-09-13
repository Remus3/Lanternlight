"""The pre-flight must be a RUNNER, and must not become a second suite.

``OPS-87`` criterion 2: the mechanical classes get a pre-flight, not a refuter,
"so a slice self-checks and the merger is not the first thing to notice", and
"the check's own runtime is a STATED NUMBER, because a gate that costs a full
suite run has moved the cost rather than removed it".

WHAT THE MEASUREMENT ACTUALLY SUPPORTS, because the item's own wording assumed
more than the census found. ``OPS-87`` says everything in classes (b) and (c)
"is answerable by a program". The census adjudication refuted that for (c): of
54 stale-recital events, 14 were judged gate-reachable and 35 were not, because
the dominant failure is a wrong MECHANISM or SCOPE rather than a wrong number.
So this module targets class (b) in full and the reachable slice of (c), and it
does that mostly by RUNNING GUARDS THAT ALREADY EXIST at a moment when a slice
can still act on them. Its value is timing and cost, not new logic - the
registration guards that caught ``OPS-75`` were already green-or-red in the
suite, six and a half minutes away from the slice that needed them.

Two properties keep it honest and both are pinned below:

* it must never SILENTLY shrink - a module named in the set but missing from
  the tree is a failure, not a skipped line, because a runner that quietly runs
  fewer checks is the exact defect ``ops/merge_gate.py`` exists to catch one
  level up;
* it must state its own measured runtime, and the statement must be the
  measurement rather than a constant somebody typed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ops import preflight

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestTheModuleSet:
    def test_every_named_module_exists_on_disk(self) -> None:
        missing = [m for m in preflight.MODULES if not (REPO_ROOT / m).exists()]
        assert missing == [], missing

    def test_every_named_module_carries_a_reason(self) -> None:
        # A set nobody can justify is a set nobody can prune. The reason names
        # the finding class the module pre-empts.
        assert set(preflight.MODULES) == set(preflight.WHY)
        assert all(preflight.WHY[m].strip() for m in preflight.MODULES)

    def test_the_set_is_not_the_whole_suite(self) -> None:
        # The point is cost. If the pre-flight ever grows to the full suite it
        # has moved the cost rather than removed it, which is the sentence
        # OPS-87 criterion 2 is written around.
        all_tests = sorted(p.name for p in (REPO_ROOT / "tests").glob("test_*.py"))
        assert len(preflight.MODULES) < len(all_tests) / 2

    def test_a_module_that_vanished_is_a_failure_and_not_a_shrug(self) -> None:
        result = preflight.check_modules_present(
            ("tests/test_lanes.py", "tests/test_this_does_not_exist.py"), REPO_ROOT
        )
        assert result == ("tests/test_this_does_not_exist.py",)


class TestUntrackedNewFiles:
    """Measured live on 2026-09-12, which is why this check exists.

    Three of this repository's guards subtract its own filenames by asking
    ``git ls-files``. A file created but not yet staged is invisible to that
    listing, so ``tests/test_source_register.py`` reported two of this session's
    own new files as unregistered external hosts. Staging them turned the guard
    green with no edit to any denylist. That is a FALSE RED a slice can spend an
    hour on, and it is answerable by one git call.
    """

    def test_an_untracked_unignored_file_is_reported(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "kept.txt").write_text("x", encoding="ascii")
        assert preflight.untracked_new_files(tmp_path) == ("kept.txt",)

    def test_a_staged_file_is_not_reported(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "kept.txt").write_text("x", encoding="ascii")
        subprocess.run(["git", "add", "kept.txt"], cwd=tmp_path, check=True)
        assert preflight.untracked_new_files(tmp_path) == ()

    def test_an_ignored_file_is_not_reported(self, tmp_path: Path) -> None:
        # moon_sync_inbox/ and ops/runtime/ are gitignored by design. Reporting
        # them would make the check cry wolf on every run, and a check that
        # always fires is a check nobody reads.
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".gitignore").write_text("noise/\n", encoding="ascii")
        (tmp_path / "noise").mkdir()
        (tmp_path / "noise" / "x.txt").write_text("x", encoding="ascii")
        assert "noise/x.txt" not in preflight.untracked_new_files(tmp_path)

    def test_a_directory_that_is_not_a_repository_answers_empty(
        self, tmp_path: Path
    ) -> None:
        # Not-answerable must not read as clean-and-answered, but it must also
        # not raise inside a pre-flight whose whole job is to be cheap to run.
        assert preflight.untracked_new_files(tmp_path) == ()


class TestTheReport:
    def test_the_report_states_the_measured_runtime(self) -> None:
        result = preflight.Result(
            returncode=0, summary="12 passed in 1.00s", seconds=1.25, modules=3
        )
        text = preflight.format_report(result, untracked=())
        assert "1.25" in text
        assert "PRE-FLIGHT PASS" in text

    def test_the_stated_runtime_is_the_measurement_and_not_a_constant(self) -> None:
        # Two different measurements must print two different numbers. A report
        # carrying a typed-in figure would pass the test above forever.
        one = preflight.format_report(
            preflight.Result(0, "ok", 1.25, 3), untracked=()
        )
        two = preflight.format_report(
            preflight.Result(0, "ok", 9.75, 3), untracked=()
        )
        assert one != two
        assert "9.75" in two

    def test_a_failing_run_says_REFUSE_and_carries_the_summary(self) -> None:
        result = preflight.Result(
            returncode=1, summary="2 failed, 10 passed in 3.00s", seconds=3.5, modules=3
        )
        text = preflight.format_report(result, untracked=())
        assert "PRE-FLIGHT REFUSE" in text
        assert "2 failed" in text

    def test_untracked_files_are_reported_as_a_WARNING_and_not_as_a_pass(
        self,
    ) -> None:
        # They are not a failure - a slice mid-flight legitimately has new files
        # - but a green line above an unstaged new file is how the false red
        # gets discovered by the merger instead of by the slice.
        text = preflight.format_report(
            preflight.Result(0, "ok", 1.0, 3), untracked=("docs/new.md",)
        )
        assert "docs/new.md" in text
        assert "WARNING" in text

    def test_the_report_says_what_the_pre_flight_does_NOT_cover(self) -> None:
        # The census found 35 of 54 stale-recital events unreachable by any
        # program. A report that did not say so would read as a clean bill for
        # a class it never examined.
        text = preflight.format_report(preflight.Result(0, "ok", 1.0, 3), untracked=())
        assert "does not" in text.lower()
        assert "adversar" in text.lower()


class TestItActuallyRuns:
    @pytest.mark.slow
    def test_the_pre_flight_runs_the_real_subset_and_is_faster_than_the_suite(
        self,
    ) -> None:
        # The claim being pinned is a COST claim, so it is measured rather than
        # asserted. The bound is deliberately loose: the full suite measured
        # 396 seconds on 2026-09-12 and the pre-flight measured 19, so a limit
        # of 120 fails only if the pre-flight has genuinely become a suite.
        result = preflight.run(REPO_ROOT)
        assert result.modules == len(preflight.MODULES)
        assert result.seconds < 120.0, result.seconds
        assert result.summary, "no pytest summary line was parsed"

    def test_the_cli_prints_a_report(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "ops.preflight", "--modules-only"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        assert "tests/test_lanes.py" in completed.stdout
