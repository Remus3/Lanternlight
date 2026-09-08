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

HEADROOM IS STATED IN SESSIONS, AND THAT IS THE POINT OF OPS-57. The budget
that fired on 2026-09-08 had been set with "175,981 bytes of headroom (~41%
above the measured size)" written beside it, and it was exhausted in about a
day. Neither the byte figure nor the percentage was wrong; both were simply
unreadable as a planning number, because nobody carries the growth rate in
their head while reading them. The classes below therefore pin the SESSIONS
figure - :class:`TestHeadroomInSessions` for the arithmetic and its boundaries
(exactly one session left, exactly zero left, already over), and
:class:`TestReportStatesHeadroomInSessions` for the rendered report. A run with
under :data:`tools.doc_size_budget.LOW_HEADROOM_SESSIONS` sessions of headroom
must be visibly flagged, and :class:`TestLowHeadroomIsNotAFailureState` pins
that this flag does NOT change ``ok`` - the pre-commit hook selects this test
module when either budgeted document is staged, so turning a warning into a
failure here would start refusing ordinary commits.

Fixture files live under ``tmp_path`` (never under this repo's own tree) and
are pure ASCII with no line breaks at all, so git's text/eol normalization has
nothing to rewrite and the byte counts chosen here are exactly the byte counts
measured - see :func:`_write` below. ``git_blob_size`` is still asked to
measure them through the real ``git`` binary rather than by re-deriving the
answer in the test, because the thing under test is the PATH from "bytes on
disk" to "a verdict", not just the arithmetic in the middle of it.
"""

from __future__ import annotations

import statistics
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


class TestMeasuredGrowthRatesAreInternallyConsistent:
    """The declared rate must be derivable from the samples beside it.

    A rate is a HYPOTHESIS like any count in this repo, and the defence
    against a hypothesis quietly drifting from its evidence is to keep the
    evidence in the module and re-derive the summary from it here. If someone
    edits ``median`` or ``mean`` without touching ``samples`` - or drops a
    sample without re-deriving - these assertions go red.
    """

    def test_every_budgeted_document_has_a_measured_rate(self) -> None:
        for path in doc_size_budget.BUDGETS:
            assert path in doc_size_budget.SESSION_GROWTH_RATES, (
                f"{path} has a byte budget but no measured per-session growth "
                "rate, so its headroom cannot be stated in sessions - which is "
                "the whole of OPS-57 criterion 5"
            )

    def test_declared_median_is_the_high_median_of_the_samples(self) -> None:
        # median_high, not plain median: with an even sample count the plain
        # median averages the two middle values, and the module deliberately
        # takes the HIGHER of them as the more conservative planning figure.
        # See the comment on SESSION_GROWTH_RATES.
        for path, rate in doc_size_budget.SESSION_GROWTH_RATES.items():
            assert rate.median == statistics.median_high(rate.samples), (
                f"{path}: declared median {rate.median} is not the high median "
                f"of its own samples {rate.samples}"
            )

    def test_declared_mean_is_the_truncated_mean_of_the_samples(self) -> None:
        for path, rate in doc_size_budget.SESSION_GROWTH_RATES.items():
            assert rate.mean == int(statistics.fmean(rate.samples)), (
                f"{path}: declared mean {rate.mean} is not the mean of its own "
                f"samples {rate.samples}"
            )

    def test_samples_are_recorded_so_the_spread_is_visible(self) -> None:
        """A single confident number hides its own spread. Keep the samples."""
        for path, rate in doc_size_budget.SESSION_GROWTH_RATES.items():
            assert len(rate.samples) >= 3, (
                f"{path}: {len(rate.samples)} sample(s) is not a rate, it is an "
                "anecdote"
            )
            assert all(s > 0 for s in rate.samples), f"{path}: non-positive sample"


class TestHeadroomInSessions:
    """The arithmetic, and both boundaries the acceptance criterion names."""

    def test_headroom_is_reported_in_sessions_not_bytes(self) -> None:
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        left = doc_size_budget.headroom_sessions(
            "doc.md", size=700, budgets={"doc.md": 1000}, rates=rates
        )
        assert left == pytest.approx(3.0)

    def test_exactly_one_session_of_headroom(self) -> None:
        """The boundary that matters most: one more session and it fires."""
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        left = doc_size_budget.headroom_sessions(
            "doc.md", size=900, budgets={"doc.md": 1000}, rates=rates
        )
        assert left == pytest.approx(1.0)

    def test_exactly_zero_sessions_of_headroom(self) -> None:
        """At the budget, headroom is 0.0 sessions - not 'a bit left'."""
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        left = doc_size_budget.headroom_sessions(
            "doc.md", size=1000, budgets={"doc.md": 1000}, rates=rates
        )
        assert left == pytest.approx(0.0)

    def test_a_fraction_under_one_means_it_fires_next_session(self) -> None:
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        left = doc_size_budget.headroom_sessions(
            "doc.md", size=950, budgets={"doc.md": 1000}, rates=rates
        )
        assert 0.0 < left < 1.0
        assert left == pytest.approx(0.5)

    def test_already_over_budget_is_negative_not_clamped_to_zero(self) -> None:
        """Clamping would make "just fired" and "far past" look identical."""
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        left = doc_size_budget.headroom_sessions(
            "doc.md", size=1200, budgets={"doc.md": 1000}, rates=rates
        )
        assert left == pytest.approx(-2.0)

    def test_a_document_with_no_measured_rate_returns_none_not_a_guess(
        self,
    ) -> None:
        """CLAUDE.md: omit rather than guess, and keep unmeasured
        distinguishable from measured zero. A document nobody has measured a
        growth rate for has NO sessions figure - it does not have infinite
        headroom, and it does not have zero.
        """
        left = doc_size_budget.headroom_sessions(
            "unmeasured.md", size=10, budgets={"unmeasured.md": 1000}, rates={}
        )
        assert left is None


class TestReportStatesHeadroomInSessions:
    """format() must say sessions for every budgeted document, alongside bytes."""

    def test_format_states_sessions_and_keeps_the_byte_figures(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "doc.md", 700)
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates=rates
        )
        rendered = report.format()

        # Bytes are kept - the criterion says alongside, not instead of.
        assert "700 bytes" in rendered
        assert "session" in rendered
        assert "3.0 sessions" in rendered
        assert report.headroom_sessions["doc.md"] == pytest.approx(3.0)

    def test_low_headroom_is_visibly_flagged_while_still_under_budget(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "doc.md", 950)
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates=rates
        )
        rendered = report.format()

        assert report.ok is True, "under budget must still be ok"
        assert report.low_headroom == ("doc.md",)
        assert "LOW HEADROOM" in rendered

    def test_comfortable_headroom_is_not_flagged(self, tmp_path: Path) -> None:
        _write(tmp_path / "doc.md", 100)
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates=rates
        )
        assert report.low_headroom == ()
        assert "LOW HEADROOM" not in report.format()

    def test_a_document_with_no_rate_says_so_rather_than_inventing_a_figure(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "doc.md", 100)
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates={}
        )
        rendered = report.format()

        assert "doc.md" not in report.headroom_sessions
        assert "no measured growth rate" in rendered
        assert report.ok is True


class TestLowHeadroomIsNotAFailureState:
    """The warning must stay distinct from the failure the hook depends on."""

    def test_low_headroom_alone_does_not_make_the_report_fail(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "doc.md", 999)  # one byte under, ~0.01 sessions left
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates=rates
        )

        assert report.low_headroom == ("doc.md",)
        assert report.ok is True
        assert report.findings == ()

    def test_over_budget_still_fails_exactly_as_before(self, tmp_path: Path) -> None:
        """The failure condition is unchanged by anything added for OPS-57."""
        _write(tmp_path / "doc.md", 1000)
        rates = {"doc.md": doc_size_budget.GrowthRate(100, 100, (100, 100, 100))}
        report = doc_size_budget.check_budgets(
            {"doc.md": 1000}, repo_root=tmp_path, rates=rates
        )

        assert report.ok is False
        assert len(report.findings) == 1
        assert report.findings[0].kind == "over_budget"


class TestRealDeclaredHeadroomInSessionsIsReported:
    """Measure the real documents now and print their sessions figure.

    Deliberately asserts only that a figure EXISTS for every budgeted
    document. It does not assert the figure is above any threshold: the
    pre-commit hook selects this module when either budgeted document is
    staged, so an assertion on remaining sessions would refuse ordinary
    commits the moment a document got close - which is the warning state's
    job, not a guard's.
    """

    def test_every_real_budgeted_document_reports_sessions_of_headroom(
        self,
    ) -> None:
        report = doc_size_budget.check_budgets()

        for path in doc_size_budget.BUDGETS:
            left = report.headroom_sessions.get(path)
            assert left is not None, (
                f"{path} has no sessions-of-headroom figure - findings: "
                f"{report.findings}"
            )
            print(f"doc_size_budget: {path} has {left:.2f} session(s) of headroom")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
