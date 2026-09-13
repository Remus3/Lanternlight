"""Guards for ``ops/cycle_cost.py`` - the historical half of ``OPS-87``
criterion 4.

The item asks for a recorded pair of numbers from REAL cycles, not an estimate,
so the thing most worth guarding here is not that a number is produced but that
every number the report prints came out of the rows. The worst defect the
session before this one shipped was ``ops/preflight.py`` printing its coverage
caveat from string literals while the guard beside it asserted only that two
words appeared - ``LL-0241``. So the report guards below rewrite a row and
require the printed total to MOVE, which a literal cannot do.

The second thing guarded is the distinction between a FLOOR and a count. The
suite-run figure is derived from quoted results and can only ever be a lower
bound; a test that accepted it as a count would be encoding the exact lie this
repository's doctrine forbids.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ops import cycle_cost
from tests import _toolguard

REPO_ROOT = Path(__file__).resolve().parents[1]


def _commit(
    sha: str,
    when: int,
    subject: str = "",
    body: str = "",
    evidence: str = "",
) -> cycle_cost.Commit:
    return cycle_cost.Commit(
        sha=sha, committed_at=when, subject=subject, body=body, evidence=evidence
    )


class TestAnchorPhrase:
    """The one verbatim link in the ledger between a fix and what it refuted."""

    def test_anchor_links_the_fix_commit_to_the_commit_it_refuted(self) -> None:
        refuted = _commit("a" * 40, 100, subject="Close OPS-11")
        fix = _commit(
            "b" * 40,
            200,
            subject="Repair OPS-11",
            evidence="+- the refutation pass over " + "a" * 7 + " found it",
        )

        links = cycle_cost.anchor_links((fix, refuted))

        assert len(links) == 1
        assert links[0].fix_sha == "b" * 40
        assert links[0].refuted_sha == "a" * 40
        assert links[0].resolved is True

    def test_anchor_matching_ignores_case_because_the_ledger_shouts_it(
        self,
    ) -> None:
        refuted = _commit("c" * 40, 100)
        fix = _commit(
            "d" * 40, 200, evidence="+- FOUND BY THE REFUTATION PASS over " + "c" * 7
        )

        links = cycle_cost.anchor_links((fix, refuted))

        assert [ln.refuted_sha for ln in links] == ["c" * 40]

    def test_a_commit_may_not_anchor_itself(self) -> None:
        lone = _commit("e" * 40, 100, body="refutation pass over " + "e" * 7)

        assert cycle_cost.anchor_links((lone,)) == ()

    def test_an_anchor_outside_the_window_is_unresolved_not_dropped(self) -> None:
        fix = _commit("f" * 40, 200, body="refutation pass over 0123456")

        links = cycle_cost.anchor_links((fix,))

        assert len(links) == 1
        assert links[0].resolved is False
        assert links[0].refuted_sha == "0123456"


class TestMovedEntriesAreNotEvidence:
    """A document REORGANISATION is not a session's work, and this is measured.

    The first run of this module reported 70 full-suite runs inside one two-commit
    cycle. The cause was ``02a40ed``, the commit that applied the ``OPS-57`` split:
    it CREATED ``docs/LEDGER_ARCHIVE.md``, so every added line of every historical
    entry arrived in that commit's diff and was read as its own evidence. The
    discriminator is the entry's own date - this ledger is append-only and an entry
    is written the day the work landed, so an entry dated well before the commit
    that adds it is being MOVED, not written.
    """

    def test_an_entry_dated_the_commit_day_is_attributed(self) -> None:
        added = [
            "+### LL-0245 - 2026-09-12 - a thing",
            "+- 3274 passed, 1 skipped",
        ]

        kept = cycle_cost.attributable_lines(added, "2026-09-12")

        assert kept == added

    def test_an_entry_dated_long_before_the_commit_is_a_move_not_evidence(
        self,
    ) -> None:
        added = [
            "+### LL-0100 - 2026-08-11 - an archived thing",
            "+- 1416 passed",
            "+### LL-0245 - 2026-09-12 - todays thing",
            "+- 3274 passed",
        ]

        kept = cycle_cost.attributable_lines(added, "2026-09-12")

        assert kept == ["+### LL-0245 - 2026-09-12 - todays thing", "+- 3274 passed"]

    def test_a_session_crossing_midnight_is_still_attributed(self) -> None:
        added = ["+### LL-0245 - 2026-09-12 - a thing", "+- 3274 passed"]

        assert cycle_cost.attributable_lines(added, "2026-09-13") == added

    def test_lines_before_any_heading_are_kept(self) -> None:
        added = ["+preamble edit", "+### LL-0001 - 2020-01-01 - old", "+- 9999 passed"]

        assert cycle_cost.attributable_lines(added, "2026-09-12") == ["+preamble edit"]

    def test_an_undated_heading_is_refused_rather_than_guessed(self) -> None:
        added = ["+### LL-0001 - no date here", "+- 3274 passed"]

        assert cycle_cost.attributable_lines(added, "2026-09-12") == []


class TestGroupingIds:
    """Which OPS ids a commit is allowed to join a cycle on."""

    def test_ids_come_from_the_subject_and_from_added_ledger_headings(self) -> None:
        commit = _commit(
            "1" * 40,
            10,
            subject="Close OPS-11 and file the rest",
            evidence="+### LL-0001 - 2026-09-12 - OPS-22 closed\n+- prose\n",
        )

        assert cycle_cost.grouping_ids(commit) == frozenset({"OPS-11", "OPS-22"})

    def test_an_id_mentioned_only_in_the_body_does_not_group(self) -> None:
        commit = _commit(
            "2" * 40,
            10,
            subject="Close OPS-11",
            body="This is the same shape as OPS-99 one level up.",
            evidence="+- and OPS-98 is cited in passing\n",
        )

        assert cycle_cost.grouping_ids(commit) == frozenset({"OPS-11"})


class TestSuiteFigures:
    """The floor, and everything it refuses to count."""

    def test_distinct_full_suite_pass_figures_are_the_floor(self) -> None:
        text = "3274 passed, 1 skipped. later 3274 passed again. earlier 3231 passed."

        quotes = cycle_cost.full_suite_quotes(text, "passed")

        assert quotes == ("3231 passed", "3274 passed")

    def test_a_module_sized_figure_is_not_a_full_suite_run(self) -> None:
        text = "382 passed in 21 seconds, and 165 passed across both modules"

        assert cycle_cost.full_suite_quotes(text, "passed") == ()

    def test_collected_is_reported_separately_and_never_as_a_run(self) -> None:
        text = "3275 collected across 67 files"

        assert cycle_cost.full_suite_quotes(text, "passed") == ()
        assert cycle_cost.full_suite_quotes(text, "collected") == ("3275 collected",)

    def test_the_threshold_is_a_parameter_and_changing_it_changes_the_answer(
        self,
    ) -> None:
        text = "382 passed"

        assert cycle_cost.full_suite_quotes(text, "passed", minimum=1000) == ()
        assert cycle_cost.full_suite_quotes(text, "passed", minimum=100) == (
            "382 passed",
        )


class TestCycleAssembly:
    """What ``build_cycles`` puts in each of a cycle's two quote columns.

    Added after a mutation SURVIVED: swapping the keyword so that collect-only
    figures were counted as suite runs changed nothing any test could see, which
    means the separation the report leans on was unguarded.
    """

    def test_passed_and_collected_land_in_different_columns(self) -> None:
        commits = (
            _commit("b" * 40, 200, subject="Repair OPS-11", body="3274 passed"),
            _commit(
                "a" * 40,
                100,
                subject="Close OPS-11",
                body="3275 collected across 67 files",
            ),
        )

        cycles = cycle_cost.build_cycles(commits)

        assert len(cycles) == 1
        assert cycles[0].pass_quotes == ("3274 passed",)
        assert cycles[0].collect_quotes == ("3275 collected",)
        assert cycles[0].suite_run_floor == 1

    def test_a_lone_commit_is_not_a_cycle(self) -> None:
        commits = (_commit("a" * 40, 100, subject="Close OPS-11"),)

        assert cycle_cost.build_cycles(commits) == ()

    def test_an_anchored_pair_survives_when_the_ids_do_not_match(self) -> None:
        """The definition doing its work - the fix commit names another item."""
        refuted = _commit("a" * 40, 100, subject="Close OPS-11")
        fix = _commit(
            "b" * 40,
            200,
            subject="Close OPS-22",
            evidence="+- the refutation pass over " + "a" * 7 + " found it",
        )

        cycles = cycle_cost.build_cycles((fix, refuted))

        pairs = {pair for cycle in cycles for pair in cycle.pairs}
        assert pairs == {("a" * 7, "b" * 7)}


class TestSpan:
    """Wall clock, and the human rendering of it."""

    def test_span_is_the_committer_time_difference_across_the_cycle(self) -> None:
        cycle = cycle_cost.Cycle(
            item_id="OPS-11",
            kind="grouped",
            commits=(_commit("a" * 40, 1000), _commit("b" * 40, 4600)),
            pairs=(),
            pass_quotes=(),
            collect_quotes=(),
        )

        assert cycle.span_seconds == 3600
        assert cycle.commit_count == 2
        assert cycle.human_span == "1h 0m 0s"

    def test_human_span_renders_days_hours_minutes_seconds(self) -> None:
        assert cycle_cost.human_span(0) == "0s"
        assert cycle_cost.human_span(59) == "59s"
        assert cycle_cost.human_span(61) == "1m 1s"
        assert cycle_cost.human_span(90061) == "1d 1h 1m 1s"

    def test_the_floor_is_the_number_of_distinct_quotes(self) -> None:
        cycle = cycle_cost.Cycle(
            item_id="OPS-11",
            kind="grouped",
            commits=(_commit("a" * 40, 1),),
            pairs=(),
            pass_quotes=("3231 passed", "3274 passed"),
            collect_quotes=(),
        )

        assert cycle.suite_run_floor == 2


class TestGapsAndOverlap:
    """Two things the first real run of this module showed a span hides."""

    def test_the_longest_gap_between_consecutive_commits_is_reported(self) -> None:
        cycle = cycle_cost.Cycle(
            item_id="OPS-11",
            kind="grouped",
            commits=(
                _commit("a" * 40, 0),
                _commit("b" * 40, 60),
                _commit("c" * 40, 40_000),
            ),
            pairs=(),
            pass_quotes=(),
            collect_quotes=(),
        )

        assert cycle.longest_gap == 39_940
        assert cycle.span_seconds == 40_000

    def test_a_single_commit_cycle_has_no_gap_rather_than_a_zero_pretending(
        self,
    ) -> None:
        cycle = cycle_cost.Cycle(
            item_id="OPS-11",
            kind="grouped",
            commits=(_commit("a" * 40, 5),),
            pairs=(),
            pass_quotes=(),
            collect_quotes=(),
        )

        assert cycle.longest_gap == 0

    def test_the_anchor_sentence_total_counts_DISTINCT_sentences(self) -> None:
        """One anchored pair shared by four cycles is still ONE sentence.

        The first real run printed "5 verbatim refutation sentences" because it
        summed the pairs per cycle; the ledger contains two. A caveat that
        inflates the evidence for its own high-confidence half is worse than no
        caveat.
        """
        pair = ("aaaaaaa", "bbbbbbb")
        cycles = tuple(
            cycle_cost.Cycle(
                item_id=f"OPS-{n}",
                kind="anchored",
                commits=(_commit("a" * 40, 1000), _commit("b" * 40, 2000)),
                pairs=(pair,),
                pass_quotes=(),
                collect_quotes=(),
            )
            for n in (11, 22, 33)
        )

        flat = " ".join(cycle_cost.format_report(cycles, window=40).split())

        assert "Only 1 verbatim refutation sentences" in flat
        assert "Only 3 verbatim" not in flat

    def test_the_report_states_the_overlap_between_cycles(self) -> None:
        """One commit closing three items puts it in three cycles."""
        shared = _commit("a" * 40, 1000)
        cycles = (
            cycle_cost.Cycle(
                item_id="OPS-11",
                kind="grouped",
                commits=(shared, _commit("b" * 40, 2000)),
                pairs=(),
                pass_quotes=(),
                collect_quotes=(),
            ),
            cycle_cost.Cycle(
                item_id="OPS-22",
                kind="grouped",
                commits=(shared, _commit("c" * 40, 3000)),
                pairs=(),
                pass_quotes=(),
                collect_quotes=(),
            ),
        )

        report = cycle_cost.format_report(cycles, window=40)

        # The report is hard-wrapped, so the sentence spans two lines. This
        # repository's own rule: search prose on a whitespace-collapsed copy.
        flat = " ".join(report.split())
        assert "4 commit slots across 2 cycles resolve to 3 distinct" in flat


def _two_cycles() -> tuple[cycle_cost.Cycle, ...]:
    first = cycle_cost.Cycle(
        item_id="OPS-11",
        kind="anchored",
        commits=(_commit("a" * 40, 1000), _commit("b" * 40, 4600)),
        pairs=(("a" * 7, "b" * 7),),
        pass_quotes=("3231 passed", "3274 passed"),
        collect_quotes=("3275 collected",),
    )
    second = cycle_cost.Cycle(
        item_id="OPS-22",
        kind="grouped",
        commits=(_commit("c" * 40, 10_000), _commit("d" * 40, 10_120)),
        pairs=(),
        pass_quotes=(),
        collect_quotes=(),
    )
    return (second, first)


class TestReportIsDerived:
    """Every number in the report comes out of the rows, and moves with them."""

    def test_the_totals_are_summed_from_the_rows(self) -> None:
        cycles = _two_cycles()

        report = cycle_cost.format_report(cycles, window=40)

        total = sum(c.span_seconds for c in cycles)
        assert total == 3720
        assert cycle_cost.human_span(total) in report
        assert f"{total}s" in report

    def test_rewriting_a_row_moves_the_printed_total(self) -> None:
        """The anti-literal arm. A hardcoded total cannot pass both halves."""
        cycles = _two_cycles()
        before = cycle_cost.format_report(cycles, window=40)

        stretched = cycle_cost.Cycle(
            item_id=cycles[1].item_id,
            kind=cycles[1].kind,
            commits=(_commit("a" * 40, 1000), _commit("b" * 40, 8200)),
            pairs=cycles[1].pairs,
            pass_quotes=cycles[1].pass_quotes,
            collect_quotes=cycles[1].collect_quotes,
        )
        after = cycle_cost.format_report((cycles[0], stretched), window=40)

        assert "3720s" in before
        assert "3720s" not in after
        assert "7320s" in after

    def test_the_floor_total_is_summed_and_named_as_a_floor(self) -> None:
        cycles = _two_cycles()

        report = cycle_cost.format_report(cycles, window=40)

        floor = sum(c.suite_run_floor for c in cycles)
        assert floor == 2
        assert f">= {floor}" in report

    def test_the_report_counts_the_cycles_carrying_no_evidence_at_all(self) -> None:
        cycles = _two_cycles()

        report = cycle_cost.format_report(cycles, window=40)

        blind = sum(1 for c in cycles if not c.pass_quotes)
        assert blind == 1
        assert f"{blind} of the {len(cycles)} cycles quote no full-suite" in report

    def test_the_caveat_moves_when_the_rows_move(self) -> None:
        """``LL-0241`` again: a caveat printed from literals is decoration."""
        cycles = _two_cycles()
        one_blind = cycle_cost.format_report(cycles, window=40)
        none_blind = cycle_cost.format_report((cycles[1],), window=40)

        assert "1 of the 2 cycles quote no full-suite" in one_blind
        assert "0 of the 1 cycles quote no full-suite" in none_blind

    def test_an_empty_run_reports_nothing_rather_than_zero_dressed_as_a_result(
        self,
    ) -> None:
        report = cycle_cost.format_report((), window=40)

        assert "no cycle" in report.lower()


class TestAgainstThisRepository:
    """The integration arm. It must find the two verbatim-anchored cycles."""

    def test_both_ledger_anchored_cycles_are_found(self) -> None:
        git = _toolguard.require("git")
        commits = cycle_cost.load_commits(REPO_ROOT, window=40, git_exe=git)
        assert commits, "git log returned nothing for this repository"

        cycles = cycle_cost.build_cycles(commits)
        pairs = {pair for cycle in cycles for pair in cycle.pairs}

        assert ("e646bca", "3959682") in pairs
        assert ("c6b854d", "e646bca") in pairs

    def test_the_anchored_cycles_carry_a_real_span_and_a_real_floor(self) -> None:
        git = _toolguard.require("git")
        commits = cycle_cost.load_commits(REPO_ROOT, window=40, git_exe=git)

        cycles = [c for c in cycle_cost.build_cycles(commits) if c.pairs]
        assert cycles, "no anchored cycle was built from this repository"
        for cycle in cycles:
            assert cycle.span_seconds > 0
            assert cycle.commit_count >= 2
            assert cycle.suite_run_floor >= 1


class TestRunnableAsAModule:
    """``python -m ops.cycle_cost`` has to actually run."""

    def test_main_prints_a_report_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        git = _toolguard.require("git")

        code = cycle_cost.main(["--window", "12", "--git", git])

        captured = capsys.readouterr().out
        assert code == 0
        assert "CYCLE COST" in captured
        assert "committer" in captured

    def test_the_module_entry_point_exists(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "ops.cycle_cost", "--window", "12"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert completed.returncode == 0, completed.stderr
        assert "CYCLE COST" in completed.stdout


def _record(
    started: str,
    duration: float,
    *,
    full: bool = True,
    nested: bool = False,
    pid: int = 1000,
    reasons: tuple[str, ...] = (),
    collected: int = 3357,
    passed: int = 3350,
) -> dict:
    """One suite-recorder record, built by hand.

    Built as a plain dict rather than through ``ops.suite_recorder`` on purpose.
    The schema is that module's docstring and this is a READER of it, so a
    reader test that can only be written by driving the writer proves the two
    agree with each other rather than with the contract.
    """
    return {
        "schema": 1,
        "started_utc": started,
        "duration_s": duration,
        "collected": collected,
        "passed": passed,
        "full": full,
        "nested": nested,
        "filtered_reasons": list(reasons),
        "pid": pid,
    }


#: The boundary every live test below measures from.
_LIVE_START = "2026-09-13T02:00:00+00:00"


def _live(records: list[dict], start: str = _LIVE_START) -> cycle_cost.LiveCycle:
    return cycle_cost.build_live_cycle(
        records, start_epoch=cycle_cost.epoch_of(start), boundary=f"start {start}"
    )


class TestLiveBoundary:
    """The cycle boundary is TIME, and a record either falls inside it or not."""

    def test_a_record_started_before_the_boundary_is_outside_the_cycle(self) -> None:
        cycle = _live(
            [
                _record("2026-09-13T01:59:59+00:00", 300.0),
                _record("2026-09-13T02:00:01+00:00", 400.0),
            ]
        )

        assert cycle.run_count == 1
        assert cycle.suite_seconds == 400.0

    def test_a_nested_full_run_is_excluded_and_the_reason_says_nested(self) -> None:
        cycle = _live(
            [
                _record("2026-09-13T02:10:00+00:00", 300.0),
                _record("2026-09-13T02:20:00+00:00", 9.0, nested=True),
            ]
        )

        assert cycle.run_count == 1
        assert cycle.excluded_count == 1
        assert any("nested" in label for label, _n in cycle.exclusion_reasons)

    def test_a_filtered_run_is_excluded_under_its_own_recorded_reason(self) -> None:
        cycle = _live(
            [
                _record("2026-09-13T02:10:00+00:00", 300.0),
                _record(
                    "2026-09-13T02:20:00+00:00",
                    1.3,
                    full=False,
                    reasons=("collect-only, so nothing was executed",),
                ),
            ]
        )

        assert dict(cycle.exclusion_reasons) == {
            "collect-only, so nothing was executed": 1
        }

    def test_two_target_reasons_differing_only_in_paths_share_one_label(self) -> None:
        """Otherwise every filtered run invents its own reason and nothing tallies."""
        cycle = _live(
            [
                _record(
                    "2026-09-13T02:10:00+00:00",
                    5.0,
                    full=False,
                    reasons=("target arguments narrowed collection: tests/a.py",),
                ),
                _record(
                    "2026-09-13T02:20:00+00:00",
                    6.0,
                    full=False,
                    reasons=("target arguments narrowed collection: tests/b.py",),
                ),
            ]
        )

        assert dict(cycle.exclusion_reasons) == {
            "target arguments narrowed collection": 2
        }

    def test_digit_runs_in_a_reason_are_generalised_into_one_label(self) -> None:
        cycle = _live(
            [
                _record(
                    "2026-09-13T02:10:00+00:00",
                    5.0,
                    full=False,
                    reasons=("14 of 69 test modules on disk did not run",),
                ),
                _record(
                    "2026-09-13T02:20:00+00:00",
                    6.0,
                    full=False,
                    reasons=("3 of 69 test modules on disk did not run",),
                ),
            ]
        )

        assert dict(cycle.exclusion_reasons) == {
            "N of N test modules on disk did not run": 2
        }

    def test_an_unreadable_timestamp_is_counted_rather_than_raising(self) -> None:
        cycle = _live(
            [
                _record("not-a-timestamp", 300.0),
                _record("2026-09-13T02:10:00+00:00", 300.0),
            ]
        )

        assert cycle.run_count == 1
        assert cycle.unreadable == 1

    def test_the_span_runs_from_the_boundary_to_the_newest_record_END(self) -> None:
        cycle = _live(
            [
                _record("2026-09-13T02:10:00+00:00", 100.0),
                _record(
                    "2026-09-13T02:20:00+00:00",
                    50.0,
                    full=False,
                    reasons=("collect-only, so nothing was executed",),
                ),
            ]
        )

        assert cycle.span_seconds == 1250.0

    def test_a_window_with_no_start_keeps_every_record(self) -> None:
        cycle = cycle_cost.build_live_cycle(
            [
                _record("2020-01-01T00:00:00+00:00", 11.0),
                _record("2026-09-13T02:10:00+00:00", 22.0),
            ],
            start_epoch=None,
            boundary="every record on disk",
        )

        assert cycle.run_count == 2
        assert cycle.suite_seconds == 33.0


class TestLiveReportIsDerived:
    """Every number the live report prints moves when the records move."""

    def _two_runs(self, second: float = 200.0) -> list[dict]:
        return [
            _record("2026-09-13T02:10:00+00:00", 100.0, pid=7),
            _record("2026-09-13T02:30:00+00:00", second, pid=7),
        ]

    def test_rewriting_a_duration_moves_the_printed_suite_clock(self) -> None:
        first = cycle_cost.format_live_report(_live(self._two_runs()))
        second = cycle_cost.format_live_report(_live(self._two_runs(500.0)))

        # The FLOOR marker is part of the match on purpose: the elapsed span
        # also ends in "300.0s" here, and a looser pattern passed against the
        # wrong line.
        assert ">= 300.0s" in first
        assert ">= 300.0s" not in second
        assert ">= 600.0s" in second

    def test_the_concurrency_caveat_counts_the_distinct_processes_in_the_rows(
        self,
    ) -> None:
        one = self._two_runs()
        two = [
            _record("2026-09-13T02:10:00+00:00", 100.0, pid=7),
            _record("2026-09-13T02:30:00+00:00", 200.0, pid=8),
        ]

        one_flat = " ".join(cycle_cost.format_live_report(_live(one)).split())
        two_flat = " ".join(cycle_cost.format_live_report(_live(two)).split())

        assert "2 records written by 1 distinct process" in one_flat
        assert "2 records written by 2 distinct process" in two_flat

    def test_the_count_is_labelled_EXACT_and_the_clock_is_labelled_a_FLOOR(
        self,
    ) -> None:
        cycle = _live(self._two_runs())

        flat = " ".join(cycle_cost.format_live_report(cycle).split())

        assert f"full-suite runs: {cycle.run_count} (EXACT" in flat
        assert (
            f"summed suite wall clock (a FLOOR): >= {cycle.suite_seconds:.1f}s" in flat
        )

    def test_the_exclusion_tally_is_printed_with_its_reason_and_its_count(
        self,
    ) -> None:
        cycle = _live(
            [
                *self._two_runs(),
                _record(
                    "2026-09-13T02:40:00+00:00",
                    1.3,
                    full=False,
                    reasons=("collect-only, so nothing was executed",),
                ),
                _record("2026-09-13T02:41:00+00:00", 2.0, nested=True),
            ]
        )

        flat = " ".join(cycle_cost.format_live_report(cycle).split())

        assert "2 records excluded" in flat
        assert "1 x collect-only, so nothing was executed" in flat

    def test_one_record_carrying_two_reasons_is_said_not_to_sum(self) -> None:
        """Otherwise a reader adds the tally up and gets more records than exist."""
        cycle = _live(
            [
                *self._two_runs(),
                _record(
                    "2026-09-13T02:40:00+00:00",
                    1.3,
                    full=False,
                    reasons=(
                        "collect-only, so nothing was executed",
                        "69 of 69 test modules on disk did not run",
                    ),
                ),
            ]
        )

        flat = " ".join(cycle_cost.format_live_report(cycle).split())

        assert "1 records carry 2 reasons between them" in flat

    def test_no_such_note_is_printed_when_each_record_has_one_reason(self) -> None:
        cycle = _live(
            [
                *self._two_runs(),
                _record(
                    "2026-09-13T02:40:00+00:00",
                    1.3,
                    full=False,
                    reasons=("collect-only, so nothing was executed",),
                ),
            ]
        )

        flat = " ".join(cycle_cost.format_live_report(cycle).split())

        assert "reasons between them" not in flat

    def test_an_empty_window_reports_no_runs_rather_than_zero_dressed_as_result(
        self,
    ) -> None:
        report = cycle_cost.format_live_report(_live([]))

        assert "no full-suite run" in report.lower()

    def test_the_live_report_says_a_record_proves_SOME_session_ran_a_suite(
        self,
    ) -> None:
        """The shared-directory caveat has to sit where the number is read."""
        flat = " ".join(cycle_cost.format_live_report(_live(self._two_runs())).split())

        assert "SOME session" in flat


class TestLiveAgainstThisRepository:
    """The integration arm - git supplies the boundary, the disk the records."""

    def test_the_tip_commit_supplies_the_default_boundary(self) -> None:
        git = _toolguard.require("git")

        tip = cycle_cost.tip_commit(REPO_ROOT, git_exe=git)

        assert tip is not None
        sha, stamp = tip
        assert len(sha) == 40
        assert stamp > 0

    def test_every_run_the_live_half_returns_is_full_and_not_nested(self) -> None:
        git = _toolguard.require("git")

        cycle = cycle_cost.load_live_cycle(REPO_ROOT, git_exe=git)

        tip = cycle_cost.tip_commit(REPO_ROOT, git_exe=git)
        assert tip is not None
        assert tip[0][:7] in cycle.boundary
        assert all(run.full and not run.nested for run in cycle.runs)
        assert cycle.suite_seconds == sum(run.duration_s for run in cycle.runs)

    def test_an_explicit_start_overrides_the_tip_commit_boundary(self) -> None:
        git = _toolguard.require("git")

        cycle = cycle_cost.load_live_cycle(
            REPO_ROOT, git_exe=git, since="1970-01-01T00:00:00+00:00"
        )

        assert "1970-01-01" in cycle.boundary


class TestBothHalvesInOneReport:
    """``python -m ops.cycle_cost`` prints the BEFORE and the AFTER together."""

    def test_main_prints_the_historical_and_the_live_half(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        git = _toolguard.require("git")

        code = cycle_cost.main(["--window", "12", "--git", git])

        out = capsys.readouterr().out
        assert code == 0
        assert "CYCLE COST, HISTORICAL" in out
        assert "CYCLE COST, LIVE" in out
