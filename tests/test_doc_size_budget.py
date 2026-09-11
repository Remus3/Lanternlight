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

THE PAIR CHANNEL, AND WHY IT IS TESTED AGAINST A GROWN ARCHIVE. ``OPS-62``
added a second channel: the two archives the ``OPS-57`` split created carry no
budget of their own, by decision, and the bound is on each live document and its
archive TOGETHER. The bug that motivated it is a specific, testable shape - a
live document comfortably inside its own budget beside an archive that has grown
large - and :class:`TestArchiveGrowthAloneFiresThePairBudget` builds exactly
that tree and asserts BOTH halves of the claim in one place: the live-only check
reports OK on it while the pair check fails. A single assertion on the new check
would leave "the old guard was blind" as narration; asserting both makes the
blindness itself a measurement, and makes any future regression that stops
looking at the archive show up as a red test rather than as a quiet OK.

The decision not to budget the archives individually is itself pinned, in
:class:`TestArchivesAreUnbudgetedByRecordedDecision`, because criterion 4 asks
for the decision recorded WITH ITS COST where a reader looking for the missing
archive budget will find it - which makes the note a tested artifact rather than
a comment that can rot. And the model rests on ONE split, so
:class:`TestTheProvisionalCaveatIsInTheCodeNotOnlyInAReport` pins that the code
says so and that the rendered report repeats it: a caveat stated in chat but
dropped from the artifact is a lie in the artifact.

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

import _toolguard  # noqa: E402

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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
        _write(tmp_path / "under.txt", 1)
        report = doc_size_budget.check_budgets(
            {"under.txt": 100}, repo_root=tmp_path
        )
        rendered = report.format()
        assert "OK" in rendered

    def test_failing_report_format_mentions_every_finding(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
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
        _toolguard.require("git")
        report = doc_size_budget.check_budgets()

        for path in doc_size_budget.BUDGETS:
            left = report.headroom_sessions.get(path)
            assert left is not None, (
                f"{path} has no sessions-of-headroom figure - findings: "
                f"{report.findings}"
            )
            print(f"doc_size_budget: {path} has {left:.2f} session(s) of headroom")


class TestArchivesAreUnbudgetedByRecordedDecision:
    """OPS-62 criterion 4: the archives are deliberately NOT budgeted alone.

    ``OPS-57`` split both continuity documents, and the two archives it created
    are the largest documents in the repository. Giving each of them its own
    byte budget would need a growth rate for a document that gains nothing
    between splits and then takes one large step when a split runs, and there
    has been exactly ONE split - a slope through one point is not a
    measurement, and this repository omits rather than guesses. So the archives
    carry no individual budget and the bound is on the PAIR instead.

    The failure this pins is a documentation failure with teeth: a reader who
    goes looking for the missing archive budget must find the DECISION at the
    archive's own path, not silence. So every archive path must appear in
    ``UNBUDGETED_BY_DECISION``, must NOT appear in ``BUDGETS``, and its recorded
    reason must name where the real bound lives and what the decision costs.
    """

    def test_no_archive_path_has_its_own_byte_budget(self) -> None:
        for name, pair in doc_size_budget.PAIRS.items():
            assert pair.archive not in doc_size_budget.BUDGETS, (
                f"{pair.archive} has its own budget in BUDGETS, which "
                f"contradicts the OPS-62 decision recorded for pair {name}: "
                "archives are bounded through the pair, not individually"
            )

    def test_every_archive_records_the_decision_where_it_will_be_looked_for(
        self,
    ) -> None:
        for pair in doc_size_budget.PAIRS.values():
            reason = doc_size_budget.UNBUDGETED_BY_DECISION.get(pair.archive)
            assert reason, (
                f"{pair.archive} carries no budget and no recorded reason - a "
                "reader looking for the missing archive budget finds silence, "
                "which is exactly what OPS-62 criterion 4 forbids"
            )
            assert "PAIR_BUDGETS" in reason, (
                f"the note for {pair.archive} does not say where the real "
                "bound lives"
            )

    def test_the_recorded_decision_states_its_cost(self) -> None:
        for pair in doc_size_budget.PAIRS.values():
            reason = doc_size_budget.UNBUDGETED_BY_DECISION[pair.archive]
            lowered = reason.lower()
            assert "cost" in lowered, (
                f"the note for {pair.archive} records a decision without its "
                "cost - OPS-62 criterion 4 wants the decision AND the cost, "
                "because a decision without its cost reads as a free lunch"
            )

    def test_every_archive_named_in_a_pair_is_covered_and_no_more(self) -> None:
        archives = {pair.archive for pair in doc_size_budget.PAIRS.values()}
        assert set(doc_size_budget.UNBUDGETED_BY_DECISION) == archives


class TestTheProvisionalCaveatIsInTheCodeNotOnlyInAReport:
    """OPS-62 criterion 2: one split is one data point, and it must say so.

    A caveat stated in chat but dropped from the artifact is a lie in the
    artifact, so the code itself must carry it: each pair's growth model
    declares how many splits it rests on, reports itself provisional while that
    is under two, and the rendered report repeats the caveat next to the number
    it qualifies.
    """

    def test_every_pair_model_declares_how_many_splits_it_rests_on(self) -> None:
        for name, model in doc_size_budget.PAIR_GROWTH.items():
            assert model.splits_measured >= 1, (
                f"pair {name} declares {model.splits_measured} splits - a "
                "model with no measured split is not a measurement at all"
            )

    def test_a_one_split_model_reports_itself_provisional(self) -> None:
        for name, model in doc_size_budget.PAIR_GROWTH.items():
            if model.splits_measured < 2:
                assert model.provisional is True, (
                    f"pair {name} rests on {model.splits_measured} split(s) "
                    "and does not report itself provisional"
                )

    def test_a_two_split_model_would_stop_being_provisional(self) -> None:
        # Pins the boundary rather than only the current state, so the flag
        # cannot quietly become a constant that says "provisional" forever.
        model = doc_size_budget.PairGrowthModel(
            append_median=100,
            live_budget=600,
            live_size_at_split=100,
            split_overhead_bytes=100,
            splits_measured=2,
        )
        assert model.provisional is False

    def test_the_rendered_pair_report_repeats_the_provisional_caveat(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        models = {
            "P": doc_size_budget.PairGrowthModel(
                append_median=100,
                live_budget=600,
                live_size_at_split=100,
                split_overhead_bytes=0,
                splits_measured=1,
            )
        }
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models=models, repo_root=tmp_path
        )
        rendered = report.format()

        assert "provisional" in rendered.lower(), (
            "the sessions figure is printed without the caveat that its split "
            "overhead term rests on a single split"
        )
        assert "1 split" in rendered


class TestPairGrowthModelArithmetic:
    """The pair rate is derived, not declared, so a test can re-derive it.

    The model is: pair bytes grow per session at the LIVE document's measured
    append rate (six sessions, and before the split the live document WAS the
    whole pair, so that rate is a pair rate already), plus the one-off overhead
    a split adds, amortized over the sessions between splits.
    """

    def test_split_interval_is_derived_from_the_live_budget_and_rate(self) -> None:
        model = doc_size_budget.PairGrowthModel(
            append_median=100,
            live_budget=600,
            live_size_at_split=100,
            split_overhead_bytes=0,
        )
        # (600 - 100) / 100 == 5.0 sessions between one split and the next.
        assert model.split_interval_sessions == pytest.approx(5.0)

    def test_effective_rate_adds_the_amortized_split_overhead(self) -> None:
        model = doc_size_budget.PairGrowthModel(
            append_median=100,
            live_budget=600,
            live_size_at_split=100,
            split_overhead_bytes=100,
        )
        # 100 bytes of overhead spread over 5 sessions is 20 bytes a session.
        assert model.per_session_split_overhead == pytest.approx(20.0)
        assert model.effective_rate == pytest.approx(120.0)

    def test_a_zero_overhead_model_falls_back_to_the_append_rate(self) -> None:
        model = doc_size_budget.PairGrowthModel(
            append_median=100,
            live_budget=600,
            live_size_at_split=100,
            split_overhead_bytes=0,
        )
        assert model.effective_rate == pytest.approx(100.0)

    def test_the_overhead_term_shortens_headroom_rather_than_lengthening_it(
        self,
    ) -> None:
        # Direction matters: OPS-57 chose median_high because UNDERestimating
        # the rate is the failure this whole check exists to stop. Every real
        # model must therefore report a rate at or above its append rate.
        for name, model in doc_size_budget.PAIR_GROWTH.items():
            assert model.effective_rate >= model.append_median, (
                f"pair {name} reports a rate below its own append rate, which "
                "would make its headroom read longer than measured"
            )

    def test_every_pair_append_rate_matches_the_live_documents_measured_rate(
        self,
    ) -> None:
        for name, pair in doc_size_budget.PAIRS.items():
            model = doc_size_budget.PAIR_GROWTH[name]
            live_rate = doc_size_budget.SESSION_GROWTH_RATES[pair.live]
            assert model.append_median == live_rate.median, (
                f"pair {name} carries its own copy of a rate that already "
                "exists for its live half - two copies of one measurement is "
                "how the two drift apart"
            )

    def test_every_pair_has_a_budget_and_a_model(self) -> None:
        assert doc_size_budget.PAIRS, "no pairs declared - nothing is guarded"
        for name in doc_size_budget.PAIRS:
            assert name in doc_size_budget.PAIR_BUDGETS
            assert name in doc_size_budget.PAIR_GROWTH


class TestPairTotalIsMeasuredAcrossBothHalves:
    """The measured figure is the sum, and both halves stay visible."""

    def test_the_pair_total_is_the_sum_of_both_halves(self, tmp_path: Path) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 200)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        assert report.ok is True
        assert report.measured["P"] == 300

    def test_both_component_sizes_are_reported_separately(
        self, tmp_path: Path
    ) -> None:
        # A pair total that cannot be attributed is a number nobody can act
        # on, so the halves are printed beside it.
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 200)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )
        rendered = report.format()

        assert report.components["P"] == {"live.md": 100, "arch.md": 200}
        assert "live.md" in rendered
        assert "arch.md" in rendered


class TestArchiveGrowthAloneFiresThePairBudget:
    """OPS-62 criterion 3, the whole point: an archive cannot grow unwatched.

    The tree here is exactly the blindness OPS-62 describes - a live document
    comfortably inside its own budget beside an archive that has grown large.
    The live-only check must report OK on that tree (that is the bug, stated as
    a measurement) while the pair check must fail on the same tree in the same
    run.
    """

    def test_a_large_archive_fires_the_pair_budget(self, tmp_path: Path) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 900)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}

        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        assert report.ok is False
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.kind == "pair_over_budget"
        assert finding.path == "P"
        assert finding.size == 1000
        assert finding.budget == 1000
        assert "arch.md" in finding.detail, (
            "the finding does not say which half carries the bytes, so nobody "
            "reading it knows whether a split would help"
        )

    def test_the_live_only_check_is_green_on_the_very_same_tree(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 900)

        live_only = doc_size_budget.check_budgets(
            {"live.md": 500}, repo_root=tmp_path
        )
        paired = doc_size_budget.check_pair_budgets(
            pairs={"P": doc_size_budget.DocumentPair("live.md", "arch.md")},
            budgets={"P": 1000},
            models={},
            repo_root=tmp_path,
        )

        # Both halves of the claim, in one place: the old guard passes and the
        # new one fails. If the pair check ever stops looking at the archive,
        # the second assertion goes red while the first stays green.
        assert live_only.ok is True
        assert paired.ok is False

    def test_growth_in_the_archive_alone_moves_the_pair_total(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        before = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        _write(tmp_path / "arch.md", 800)  # only the archive changes
        after = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        assert before.measured["P"] == 200
        assert after.measured["P"] == 900
        assert before.ok is True
        assert after.ok is True  # 900 < 1000, still inside

    def test_the_pair_boundary_is_at_or_over_like_the_live_one(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 900)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        at_budget = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        _write(tmp_path / "arch.md", 899)
        one_under = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        assert at_budget.ok is False, "exactly at budget must fail, as for a doc"
        assert one_under.ok is True


class TestPairMissingHalfFailsTheCheck:
    """A half that does not exist is a finding, never a cheap pass."""

    def test_a_missing_archive_is_a_finding_not_a_small_pair(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 1000}, models={}, repo_root=tmp_path
        )

        assert report.ok is False
        assert [f.kind for f in report.findings] == ["missing"]
        assert report.findings[0].path == "arch.md"
        assert "P" not in report.measured, (
            "an unmeasurable pair must be absent from measured, not present "
            "with a total that silently omits a half"
        )

    def test_a_missing_half_does_not_stop_a_later_pair_being_reported(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live_a.md", 100)
        _write(tmp_path / "live_b.md", 100)
        _write(tmp_path / "arch_b.md", 900)
        pairs = {
            "A": doc_size_budget.DocumentPair("live_a.md", "arch_a.md"),
            "B": doc_size_budget.DocumentPair("live_b.md", "arch_b.md"),
        }
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs,
            budgets={"A": 1000, "B": 1000},
            models={},
            repo_root=tmp_path,
        )

        kinds = sorted(f.kind for f in report.findings)
        assert kinds == ["missing", "pair_over_budget"]


class TestPairHeadroomInSessions:
    """The pair states headroom in sessions too, at its own rate."""

    def _model(self, overhead: int = 0) -> object:
        return doc_size_budget.PairGrowthModel(
            append_median=100,
            live_budget=600,
            live_size_at_split=100,
            split_overhead_bytes=overhead,
        )

    def test_exactly_one_session_of_headroom(self) -> None:
        left = doc_size_budget.pair_headroom_sessions(
            "P", total=900, budgets={"P": 1000}, models={"P": self._model()}
        )
        assert left == pytest.approx(1.0)

    def test_exactly_zero_sessions_of_headroom(self) -> None:
        left = doc_size_budget.pair_headroom_sessions(
            "P", total=1000, budgets={"P": 1000}, models={"P": self._model()}
        )
        assert left == pytest.approx(0.0)

    def test_already_over_budget_is_negative_not_clamped(self) -> None:
        left = doc_size_budget.pair_headroom_sessions(
            "P", total=1500, budgets={"P": 1000}, models={"P": self._model()}
        )
        assert left == pytest.approx(-5.0)

    def test_a_pair_with_no_model_returns_none_rather_than_a_guess(self) -> None:
        left = doc_size_budget.pair_headroom_sessions(
            "P", total=100, budgets={"P": 1000}, models={}
        )
        assert left is None

    def test_the_overhead_term_is_used_not_just_the_append_rate(self) -> None:
        # 1000 - 880 == 120 bytes left; at 120 bytes a session that is exactly
        # one session, while the bare append rate would report 1.2 and read as
        # more room than there is.
        left = doc_size_budget.pair_headroom_sessions(
            "P",
            total=880,
            budgets={"P": 1000},
            models={"P": self._model(overhead=100)},
        )
        assert left == pytest.approx(1.0)

    def test_a_pair_report_states_sessions_and_keeps_the_bytes(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 300)
        _write(tmp_path / "arch.md", 400)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs,
            budgets={"P": 1000},
            models={"P": self._model()},
            repo_root=tmp_path,
        )
        rendered = report.format()

        assert report.headroom_sessions["P"] == pytest.approx(3.0)
        assert "700 bytes" in rendered
        assert "3.0 sessions" in rendered


class TestPairLowHeadroomWarnsEarlierThanTheLiveBudget:
    """The pair warns sooner, because its remedy is not mechanical.

    A live budget firing has a documented mechanical response: re-run the
    split. A PAIR budget firing does not - the split moves bytes between the
    halves and leaves the pair total alone (it nudges it UP, by the split's own
    overhead), so the only responses are an operator ruling or a real reduction
    in content. A gate whose remedy needs the operator has to warn early enough
    for the operator to be asked, which means earlier than two sessions.
    """

    def test_the_pair_threshold_is_further_out_than_the_document_one(
        self,
    ) -> None:
        assert (
            doc_size_budget.PAIR_LOW_HEADROOM_SESSIONS
            > doc_size_budget.LOW_HEADROOM_SESSIONS
        )

    def test_low_pair_headroom_is_flagged_while_still_under_budget(
        self, tmp_path: Path
    ) -> None:
        # 700 bytes left at 100 a session is 7.0 sessions; set the budget so
        # the figure lands just inside the pair threshold.
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        models = {
            "P": doc_size_budget.PairGrowthModel(
                append_median=100,
                live_budget=600,
                live_size_at_split=100,
                split_overhead_bytes=0,
            )
        }
        budget = 200 + int(100 * doc_size_budget.PAIR_LOW_HEADROOM_SESSIONS) - 50
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": budget}, models=models, repo_root=tmp_path
        )

        assert report.ok is True, "a warning must never be a failure"
        assert report.low_headroom == ("P",)
        assert "LOW HEADROOM" in report.format()

    def test_comfortable_pair_headroom_is_not_flagged(self, tmp_path: Path) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        models = {
            "P": doc_size_budget.PairGrowthModel(
                append_median=100,
                live_budget=600,
                live_size_at_split=100,
                split_overhead_bytes=0,
            )
        }
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 100_000}, models=models, repo_root=tmp_path
        )

        assert report.low_headroom == ()
        assert "LOW HEADROOM" not in report.format()

    def test_the_rendered_threshold_is_the_pair_threshold_not_the_doc_one(
        self, tmp_path: Path
    ) -> None:
        _toolguard.require("git")
        _write(tmp_path / "live.md", 100)
        _write(tmp_path / "arch.md", 100)
        pairs = {"P": doc_size_budget.DocumentPair("live.md", "arch.md")}
        models = {
            "P": doc_size_budget.PairGrowthModel(
                append_median=100,
                live_budget=600,
                live_size_at_split=100,
                split_overhead_bytes=0,
            )
        }
        report = doc_size_budget.check_pair_budgets(
            pairs=pairs, budgets={"P": 400}, models=models, repo_root=tmp_path
        )
        rendered = report.format()

        assert f"{doc_size_budget.PAIR_LOW_HEADROOM_SESSIONS:.1f}" in rendered


class TestRealDeclaredPairBudgetsCurrentlyPass:
    """Re-measure the real pairs now; never hardcode a byte count here.

    Same shape as the live-document version above and for the same reason: a
    filed count is a hypothesis, so this measures, prints, and asserts the
    measurement clears the declared budget.
    """

    def test_declared_pair_budgets_are_not_exceeded_right_now(self) -> None:
        _toolguard.require("git")
        assert doc_size_budget.PAIR_BUDGETS, "no pair budgets declared"

        report = doc_size_budget.check_pair_budgets()

        for name, budget in doc_size_budget.PAIR_BUDGETS.items():
            total = report.measured.get(name)
            assert total is not None, (
                f"pair {name} was not measured at all - findings: "
                f"{report.findings}"
            )
            print(
                f"doc_size_budget: pair {name} is {total} bytes against a "
                f"{budget}-byte budget ({budget - total} bytes headroom); "
                f"components {report.components.get(name)}"
            )
            assert total < budget, (
                f"pair {name} is {total} bytes, at or over its {budget}-byte "
                "budget - and a split will NOT relieve this one; see the "
                "PAIR_BUDGETS comment for what the operator has to decide"
            )

        assert report.ok is True

    def test_every_real_pair_reports_sessions_of_headroom(self) -> None:
        _toolguard.require("git")
        report = doc_size_budget.check_pair_budgets()

        for name in doc_size_budget.PAIR_BUDGETS:
            left = report.headroom_sessions.get(name)
            assert left is not None, (
                f"pair {name} has no sessions-of-headroom figure - findings: "
                f"{report.findings}"
            )
            print(f"doc_size_budget: pair {name} has {left:.2f} session(s) left")

    def test_the_real_pairs_cover_both_split_documents(self) -> None:
        # Every budgeted live document must be half of a declared pair,
        # otherwise a future split could create a third unwatched archive and
        # nothing here would notice.
        paired_live = {pair.live for pair in doc_size_budget.PAIRS.values()}
        assert set(doc_size_budget.BUDGETS) == paired_live


class TestMainReportsBothChannels:
    """main() must print the pair channel too, or nobody ever sees it."""

    def test_main_prints_documents_and_pairs(self, capsys) -> None:
        """The default run, scoped explicitly - see the OPS-67 note below.

        ``main([])`` and not ``main()``. Since ``OPS-67`` a bare ``main()``
        reads ``sys.argv[1:]``, which inside a test runner is pytest's own
        argument list and is now REFUSED rather than ignored - that refusal is
        the whole point of the item. Passing an empty list asks for the default
        scope, which is what this test was always about. The behaviour of
        ``main()`` with no argument is pinned separately by
        ``TestCommandLineRefusesUnknownArguments.test_argv_none_reads_sys_argv``,
        so nothing was lost by making the scope explicit here.
        """
        _toolguard.require("git")
        code = doc_size_budget.main([])
        out = capsys.readouterr().out

        assert code == 0, f"the real tree is not green:\n{out}"
        for path in doc_size_budget.BUDGETS:
            assert path in out
        for pair in doc_size_budget.PAIRS.values():
            assert pair.archive in out, (
                f"{pair.archive} never appears in the report, so the largest "
                "documents in the repository are still invisible to a reader "
                "running this module"
            )


# ---------------------------------------------------------------------------
# ROADMAP OPS-67: the command line refuses what it does not understand, and the
# one option it grows is REAL.
#
# WHAT WAS MEASURED, AND WHY IT IS THE LOAD-BEARING ONE OF THE FOUR. On
# 2026-09-08 ``python tools/doc_size_budget.py --lanternlight-bogus-flag``
# exited 0 and printed an ordinary green report about ROADMAP.md and
# docs/LEDGER.md. ``main`` took no parameters and never read ``sys.argv``, so
# the flag was not rejected - it was never seen. This module's numbers are
# QUOTED: the repository's own hand-off tells the next session to ask it for
# headroom in SESSIONS rather than repeat a byte figure. A caller who believed
# they had scoped it at a scratch document, and got a confident verdict about
# the live ones, is the OPS-64 failure exactly - a true verdict answering a
# different question than the one asked.
#
# The tests below pin both halves of the answer, because either alone is
# incomplete. Refusing unknown argv without growing a real option would leave
# the tool unable to be scoped at all, and a scoping option that did not
# actually change which files are read would be the same lie with a nicer
# spelling.
# ---------------------------------------------------------------------------


def _write_scratch_tree(root: Path) -> dict[str, int]:
    r"""Build a four-document scratch tree and return each file's LF byte size.

    The tree mirrors the real one's SHAPE - the two live documents in
    :data:`tools.doc_size_budget.BUDGETS` and the two archives in
    :data:`tools.doc_size_budget.PAIRS` - so a run pointed at it exercises BOTH
    channels rather than only the per-document one.

    Bytes are written with :meth:`pathlib.Path.write_bytes` and contain no
    carriage returns on purpose. ``Path.write_text`` on Windows turns ``\n``
    into ``\r\n``, and while ``core.autocrlf`` would normalize that back out of
    the blob, a test whose expected size depends on that normalization is a test
    about git configuration rather than about this module. Writing LF bytes
    directly makes each expected size the exact length written.
    """
    sizes = {
        "ROADMAP.md": 100,
        "docs/LEDGER.md": 200,
        "docs/ROADMAP_ARCHIVE.md": 300,
        "docs/LEDGER_ARCHIVE.md": 400,
    }
    for rel_path, size in sizes.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        body = ("scratch " * size).encode("ascii")[: size - 1] + b"\n"
        target.write_bytes(body)
        assert len(body) == size
    return sizes


class TestCommandLineRefusesUnknownArguments:
    """An unknown token is a usage error with its own exit code, never a pass.

    Exit code 2 rather than 1, matching ``tools/archive_link_guard.py``: 1 means
    the check ran and a document is over budget, and a caller that cannot tell
    "you typed something I do not understand" from "the roadmap is too big"
    learns nothing from either.
    """

    def test_the_measured_bogus_flag_is_refused(self, capsys) -> None:
        code = doc_size_budget.main(["--lanternlight-bogus-flag"])
        err = capsys.readouterr().err

        assert code == doc_size_budget.USAGE_EXIT_CODE, (
            "the exact flag measured on 2026-09-08 still exits "
            f"{code}; it must be a usage error"
        )
        assert "--lanternlight-bogus-flag" in err, (
            "the refusal must name the offending token, or a caller cannot "
            "tell which of their arguments was wrong"
        )

    def test_no_report_is_printed_when_argv_is_refused(self, capsys) -> None:
        doc_size_budget.main(["--lanternlight-bogus-flag"])
        out = capsys.readouterr().out

        assert "ROADMAP.md" not in out, (
            "a refused run still printed a verdict about the live documents, "
            "which is the OPS-64 failure the refusal exists to stop"
        )

    def test_a_positional_argument_is_refused(self, capsys) -> None:
        code = doc_size_budget.main(["ROADMAP.md"])
        capsys.readouterr()

        assert code == doc_size_budget.USAGE_EXIT_CODE, (
            "this module takes no positional arguments; accepting one and "
            "ignoring it would measure the defaults while looking scoped"
        )

    def test_abbreviation_is_refused(self, capsys) -> None:
        code = doc_size_budget.main(["--repo-roo", "."])
        capsys.readouterr()

        assert code == doc_size_budget.USAGE_EXIT_CODE, (
            "argparse accepts unambiguous prefixes by default, so --repo-roo "
            "would silently mean --repo-root; that is this item's own defect "
            "one level down and allow_abbrev must be False"
        )

    def test_help_exits_zero(self, capsys) -> None:
        code = doc_size_budget.main(["--help"])
        out = capsys.readouterr().out

        assert code == 0, "--help is not a usage error"
        assert "--repo-root" in out, "help must document the option that exists"

    def test_argv_none_reads_sys_argv(self, capsys, monkeypatch) -> None:
        """``main()`` with no argument reads the process argv, not nothing.

        This is what the ``__main__`` block relies on, and it is the exact path
        that was broken: a flag on the real command line has to reach the
        parser. Asserting it through ``sys.argv`` rather than through an
        explicit list is the point - an explicit list would pass even if
        ``main`` ignored ``sys.argv`` entirely, which is the bug.
        """
        monkeypatch.setattr(
            sys, "argv", ["doc_size_budget.py", "--lanternlight-bogus-flag"]
        )
        code = doc_size_budget.main()
        capsys.readouterr()

        assert code == doc_size_budget.USAGE_EXIT_CODE


class TestRepoRootOptionIsReal:
    """``--repo-root`` changes WHICH documents are measured - OPS-67 criterion 2.

    An option that were accepted and ignored would be worse than one refused,
    because the resulting verdict is true about a corpus the caller did not ask
    about. So these tests do not check that the flag parses; they check that the
    printed byte counts are the scratch tree's and are not the live tree's.
    """

    def test_both_channels_report_the_scratch_sizes(self, tmp_path, capsys) -> None:
        _toolguard.require("git")
        sizes = _write_scratch_tree(tmp_path)
        code = doc_size_budget.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out

        assert code == 0, f"the scratch tree is tiny and must pass:\n{out}"
        # Per-document channel: each live document reports its own scratch size.
        roadmap_size = sizes["ROADMAP.md"]
        ledger_size = sizes["docs/LEDGER.md"]
        assert f"ROADMAP.md: {roadmap_size} bytes" in out, out
        assert f"docs/LEDGER.md: {ledger_size} bytes" in out, out
        # Pair channel: the same flag moved it too, and the totals are sums of
        # the scratch halves rather than of the live ones.
        roadmap_pair = roadmap_size + sizes["docs/ROADMAP_ARCHIVE.md"]
        ledger_pair = ledger_size + sizes["docs/LEDGER_ARCHIVE.md"]
        assert f"ROADMAP: {roadmap_pair} bytes" in out, out
        assert f"LEDGER: {ledger_pair} bytes" in out, out

    def test_the_numbers_differ_from_the_live_tree(self, tmp_path, capsys) -> None:
        """The same assertion stated as a difference, which is what changed.

        Pinning the scratch numbers alone would still pass if the live documents
        happened to be that size. Measuring the real tree in the same test and
        asserting the two runs disagree is the claim that actually matters.
        """
        _toolguard.require("git")
        _write_scratch_tree(tmp_path)
        doc_size_budget.main(["--repo-root", str(tmp_path)])
        scratch_out = capsys.readouterr().out
        doc_size_budget.main([])
        live_out = capsys.readouterr().out

        assert scratch_out != live_out
        live_roadmap = doc_size_budget.git_blob_size(
            doc_size_budget.REPO_ROOT / "ROADMAP.md"
        )
        assert f"ROADMAP.md: {live_roadmap} bytes" in live_out, live_out
        assert f"ROADMAP.md: {live_roadmap} bytes" not in scratch_out, (
            "the scratch run still reported the live ROADMAP.md size, so "
            "--repo-root was parsed and then ignored"
        )

    def test_every_run_prints_the_root_it_read(self, tmp_path, capsys) -> None:
        _toolguard.require("git")
        _write_scratch_tree(tmp_path)
        doc_size_budget.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out

        assert str(tmp_path) in out, (
            "a verdict that does not name its own scope can be mistaken for an "
            "answer about a different tree, which is the whole OPS-64 defect"
        )


class TestMissingDocumentUnderACustomRootStaysLoud:
    """Scoping the tool elsewhere must not turn a missing document into a pass.

    This is the constraint the dispatch named explicitly. An empty directory
    trivially satisfies every byte budget for reasons that have nothing to do
    with any document being small, and a scoping flag that made that a green run
    would have built the textbook vacuous guard on purpose.
    """

    def test_an_empty_root_fails_loudly(self, tmp_path, capsys) -> None:
        code = doc_size_budget.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out

        assert code == 1, f"an empty tree reported success:\n{out}"
        assert "WATCHED PATH DOES NOT EXIST" in out
        assert "OK" not in out, out

    def test_every_missing_path_is_named_in_one_run(self, tmp_path, capsys) -> None:
        doc_size_budget.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out

        for rel_path in doc_size_budget.BUDGETS:
            assert rel_path in out, out
        for pair in doc_size_budget.PAIRS.values():
            assert pair.archive in out, out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
