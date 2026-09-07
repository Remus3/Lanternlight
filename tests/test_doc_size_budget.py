"""Tests for the document size budget checker - ROADMAP OPS-37 criterion 3.

WHY THIS EXISTS. ``ROADMAP.md`` and ``docs/LEDGER.md`` are append-heavy
documents a cold session must be able to read, and neither carries any size
guard today. But both are ALSO deliberately verbose by this repository's own
rules - a ledger entry is written in full, never compressed - so this is a
REPORTING check, not a hard blocker. ``tools/doc_size_budget.py`` builds the
check and its API; wiring it into a hook is a separate, later decision left to
whoever owns ``.githooks/`` and ``.claude/settings.json``, not this module.

WHAT "GIT BLOB BYTES" MEANS AND WHY IT IS WHAT GETS MEASURED. ``CLAUDE.md``
records that Windows ``write_text`` turns LF into CRLF and that
``.gitattributes`` pins text files to ``eol=lf``, so a working-tree file and
its git blob differ in size - the concrete example there is
``lanternlight/vision_meter.py`` at 26,734 on-disk bytes versus 25,879 as a
blob. A budget measured against the wrong one is a budget nobody else can
reproduce, because the on-disk figure depends on which OS last checked the
file out. ``tools.doc_size_budget.git_blob_size`` asks ``git`` itself - via
``git hash-object`` then ``git cat-file -s`` - rather than re-implementing
git's own CRLF/LF normalization rules in Python, which is exactly the kind of
subtle-and-wrong reimplementation this repo's own history warns about
repeatedly (see CLAUDE.md's grep/taskkill anecdotes). This also means the
measurement reflects CURRENT on-disk content, staged or not - the same thing a
future pre-commit hook would need to see, not last commit's frozen blob.

THE VACUOUS-GUARD TRAP THIS FILE GUARDS AGAINST. A missing watched document
must FAIL the check, not silently satisfy a byte budget it never measured.
:class:`TestMissingWatchedPathFailsTheCheck` pins that directly. Every
over-budget document must be reported in the SAME run, not just the first one
found - :class:`TestMultipleOverBudgetFilesAreAllReported` pins that. And the
"at or over" wording in the ROADMAP acceptance criterion is a real boundary,
not a rounding accident - :class:`TestExactlyAtBudgetIsFlagged` pins the exact
byte count rather than leaving the off-by-one to chance.

Fixture files live under ``tmp_path`` (never under this repo's own tree) and
are pure ASCII with no line breaks at all, so git's text/eol normalization has
nothing to rewrite and the byte counts chosen here are exactly the byte counts
measured - see :func:`_write` below. ``git_blob_size`` is still asked to
measure them through the real ``git`` binary rather than by re-deriving the
answer in the test, because the thing under test is the PATH from "bytes on
disk" to "a verdict", not just the arithmetic in the middle of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import doc_size_budget  # noqa: E402


def _write(path: Path, num_bytes: int) -> Path:
    """Write exactly ``num_bytes`` of newline-free ASCII to ``path``.

    No ``\\n`` or ``\\r`` anywhere in the content, so nothing this repo's
    ``.gitattributes`` (``eol=lf`` on text files) would ever rewrite is
    present, and the git blob byte count equals ``num_bytes`` exactly.
    """
    path.write_bytes(b"x" * num_bytes)
    return path


class TestOverBudgetFixtureIsFlagged:
    """A fixture past its budget must produce an over_budget Finding."""

    def test_over_budget_file_is_flagged(self, tmp_path: Path) -> None:
        _write(tmp_path / "over.txt", 150)
        report = doc_size_budget.check_budgets(
            {"over.txt": 100}, repo_root=tmp_path
        )

        assert report.ok is False
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.kind == "over_budget"
        assert finding.path == "over.txt"
        assert finding.size == 150
        assert finding.budget == 100
        assert report.measured["over.txt"] == 150


class TestUnderBudgetFixtureIsNotFlagged:
    """A fixture comfortably below its budget must produce no finding."""

    def test_under_budget_file_is_not_flagged(self, tmp_path: Path) -> None:
        _write(tmp_path / "under.txt", 50)
        report = doc_size_budget.check_budgets(
            {"under.txt": 100}, repo_root=tmp_path
        )

        assert report.ok is True
        assert report.findings == ()
        assert report.measured["under.txt"] == 50


class TestExactlyAtBudgetIsFlagged:
    """The criterion is "at or over" - pin the boundary, do not leave it loose."""

    def test_exact_boundary_is_flagged_not_waved_through(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "exact.txt", 100)
        report = doc_size_budget.check_budgets(
            {"exact.txt": 100}, repo_root=tmp_path
        )

        # A strictly-greater-than comparison would pass this file. The
        # acceptance criterion says "at or over", so 100 bytes against a
        # 100-byte budget must fail.
        assert report.ok is False
        assert len(report.findings) == 1
        assert report.findings[0].kind == "over_budget"
        assert report.findings[0].size == 100
        assert report.findings[0].budget == 100

    def test_one_byte_under_the_same_boundary_is_not_flagged(
        self, tmp_path: Path
    ) -> None:
        """Companion to the exact-boundary test - proves the edge is a point,
        not a fuzzy band, by checking the byte immediately on the other side.
        """
        _write(tmp_path / "one_under.txt", 99)
        report = doc_size_budget.check_budgets(
            {"one_under.txt": 100}, repo_root=tmp_path
        )

        assert report.ok is True
        assert report.findings == ()


class TestMissingWatchedPathFailsTheCheck:
    """A watched path that does not exist must fail, never pass silently."""

    def test_missing_path_produces_a_failing_finding(self, tmp_path: Path) -> None:
        # Deliberately never created on disk.
        report = doc_size_budget.check_budgets(
            {"does_not_exist.txt": 100}, repo_root=tmp_path
        )

        assert report.ok is False
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.kind == "missing"
        assert finding.path == "does_not_exist.txt"
        assert finding.size is None
        # A missing file must never appear as a measured size - that would be
        # exactly the "silently satisfies the budget" failure mode.
        assert "does_not_exist.txt" not in report.measured

    def test_missing_path_does_not_hide_other_findings_in_the_same_run(
        self, tmp_path: Path
    ) -> None:
        """A missing path must not short-circuit the scan. If it did, an
        over-budget sibling declared later in the same mapping would never
        be seen.
        """
        _write(tmp_path / "also_over.txt", 999)
        report = doc_size_budget.check_budgets(
            {
                "does_not_exist.txt": 100,
                "also_over.txt": 100,
            },
            repo_root=tmp_path,
        )

        assert report.ok is False
        kinds_by_path = {f.path: f.kind for f in report.findings}
        assert kinds_by_path == {
            "does_not_exist.txt": "missing",
            "also_over.txt": "over_budget",
        }


class TestMultipleOverBudgetFilesAreAllReported:
    """Every over-budget document must be reported, not just the first."""

    def test_three_over_budget_files_are_all_reported(self, tmp_path: Path) -> None:
        _write(tmp_path / "first.txt", 101)
        _write(tmp_path / "second.txt", 500)
        _write(tmp_path / "third.txt", 1000)
        _write(tmp_path / "fine.txt", 10)  # under budget - must NOT appear

        report = doc_size_budget.check_budgets(
            {
                "first.txt": 100,
                "second.txt": 100,
                "third.txt": 100,
                "fine.txt": 100,
            },
            repo_root=tmp_path,
        )

        assert report.ok is False
        flagged_paths = {f.path for f in report.findings if f.kind == "over_budget"}
        assert flagged_paths == {"first.txt", "second.txt", "third.txt"}
        assert len(report.findings) == 3


class TestRealDeclaredBudgetsCurrentlyPass:
    """The declared budgets in tools/doc_size_budget.py must be green today.

    This does not hardcode a byte count - CLAUDE.md is explicit that a filed
    count is a hypothesis and goes stale the moment someone else edits the
    file. Instead it re-measures NOW, asserts the measurement clears the
    declared budget, and prints both numbers so a future reader watching this
    test (or its captured output) can see the real headroom shrinking release
    over release, rather than discovering the budget only the day it fires.
    """

    def test_declared_budgets_are_not_exceeded_right_now(self) -> None:
        assert doc_size_budget.BUDGETS, "no budgets declared - nothing is guarded"

        report = doc_size_budget.check_budgets()  # real BUDGETS, real REPO_ROOT

        for path, budget in doc_size_budget.BUDGETS.items():
            size = report.measured.get(path)
            assert size is not None, (
                f"{path} was not measured at all (missing?) - "
                f"findings: {report.findings}"
            )
            headroom = budget - size
            print(
                f"doc_size_budget: {path} is {size} bytes against a "
                f"{budget}-byte budget ({headroom} bytes headroom)"
            )
            assert size < budget, (
                f"{path} is {size} bytes, at or over its {budget}-byte "
                "budget - headroom is gone, the budget needs raising "
                "(or the document needs trimming)"
            )

        assert report.ok is True


class TestGitBlobSizeMeasuresBlobBytesNotWorkingBytes:
    """Directly pin the measurement choice the module docstring commits to.

    A file containing CRLF line endings, on a path this repo's own
    .gitattributes normalizes to LF, must measure SHORTER as a git blob than
    its raw on-disk byte count - one fewer byte per line ending. If this ever
    measured raw ``os.stat`` size instead, this test would catch the
    regression immediately instead of only when a budget silently stops
    meaning anything.
    """

    def test_crlf_content_is_measured_as_its_lf_normalized_blob_size(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "crlf_sample.md"  # .md is eol=lf in .gitattributes
        raw = b"line one\r\nline two\r\nline three\r\n"
        target.write_bytes(raw)
        on_disk = target.stat().st_size
        assert on_disk == len(raw)

        blob_size = doc_size_budget.git_blob_size(target, git_cwd=REPO_ROOT)

        # Three CRLF pairs normalized to LF: three bytes shorter.
        assert blob_size == on_disk - 3


class TestFindingAndReportShapes:
    """Cheap shape/API pins so a future refactor cannot silently drop a field
    another caller (a future hook, or a human reading .format()) relies on.
    """

    def test_ok_report_format_mentions_ok(self, tmp_path: Path) -> None:
        _write(tmp_path / "under.txt", 1)
        report = doc_size_budget.check_budgets(
            {"under.txt": 100}, repo_root=tmp_path
        )
        rendered = report.format()
        assert "OK" in rendered

    def test_failing_report_format_mentions_every_finding(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "over.txt", 200)
        report = doc_size_budget.check_budgets(
            {
                "over.txt": 100,
                "missing.txt": 100,
            },
            repo_root=tmp_path,
        )
        rendered = report.format()
        assert "over.txt" in rendered
        assert "missing.txt" in rendered

    def test_check_budgets_defaults_to_the_module_level_budgets(self) -> None:
        # No explicit `budgets=` argument - must fall back to BUDGETS/REPO_ROOT.
        report = doc_size_budget.check_budgets()
        assert set(report.measured) | {f.path for f in report.findings} == set(
            doc_size_budget.BUDGETS
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
