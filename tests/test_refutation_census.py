"""The refutation census must be RE-DERIVED, never recited.

``OPS-87`` criterion 1 asks for a record of the refutation findings recent
items produced, classified into five buckets, "derived at run time from
``docs/LEDGER.md``, ``docs/LEDGER_ARCHIVE.md`` and git history rather than from
memory", with the largest bucket NAMED with its number.

The trap in that sentence is that a classification is a JUDGEMENT and a
judgement cannot be recomputed from the ledger by a program. So the split this
module enforces is:

* the JUDGEMENT is written down once, per event, in
  ``docs/refutation_census.tsv``, each row carrying a VERBATIM quote of the
  ledger sentence it classifies;
* everything else - which entries are in the window, whether each quote still
  exists in the ledger, and every total - is recomputed at run time by
  :mod:`ops.refutation_census` and is never stored.

That makes the census tamper-evident in the direction that matters. If the
ledger sentence a row classifies is edited or removed, the anchor stops
resolving and this module goes red; the row cannot quietly outlive its
evidence. It is the repository's own rule that a mutation which fails to apply
looks exactly like a passing test, one level up: an anchor that no longer
matches is the only way to tell a live classification from a stale recital.

**What this guard is blind to, said out loud rather than in a chat log.** It
cannot tell whether a bucket letter is the RIGHT letter - only that a human
assigned one against a sentence that still exists. It cannot see an event
nobody wrote into the ledger, and this repository's ledger is written by the
party being measured, so the census is a lower bound on events and its (a)/(c)
split is directional. Both limits are restated in the report the tool prints,
because a caveat stated only here is a caveat the reader of the report does not
get.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ops import refutation_census as rc

REPO_ROOT = Path(__file__).resolve().parents[1]


def _row(
    entry_id: str = "LL-0236",
    bucket: str = "a",
    inherited: str = "N",
    fixfix: str = "N",
    uncertain: str = "N",
    quote: str = "some quote",
    reason: str = "some reason",
) -> str:
    return "\t".join((entry_id, bucket, inherited, fixfix, uncertain, quote, reason))


class TestParsing:
    def test_a_well_formed_row_parses_into_its_seven_fields(self) -> None:
        rows = rc.parse_rows(_row(quote="anchor text", reason="because"))
        assert len(rows) == 1
        row = rows[0]
        assert row.entry_id == "LL-0236"
        assert row.bucket == "a"
        assert row.inherited is False
        assert row.fixfix is False
        assert row.uncertain is False
        assert row.quote == "anchor text"
        assert row.reason == "because"

    def test_blank_lines_and_comments_are_skipped(self) -> None:
        text = "\n".join(("# a comment", "", _row(), "   ", "# another"))
        assert len(rc.parse_rows(text)) == 1

    def test_a_short_row_is_refused_rather_than_padded(self) -> None:
        with pytest.raises(rc.CensusFormatError) as excinfo:
            rc.parse_rows("LL-0236\ta\tN\tN\tN\tquote")
        assert "7 fields" in str(excinfo.value)

    def test_an_unknown_bucket_letter_is_refused(self) -> None:
        with pytest.raises(rc.CensusFormatError) as excinfo:
            rc.parse_rows(_row(bucket="f"))
        assert "bucket" in str(excinfo.value)

    def test_a_flag_that_is_not_Y_or_N_is_refused(self) -> None:
        # "true" is the plausible wrong spelling, and a parser that accepted it
        # by truthiness would read "false" as True as well.
        with pytest.raises(rc.CensusFormatError):
            rc.parse_rows(_row(inherited="true"))

    def test_an_entry_id_that_is_not_ll_shaped_is_refused(self) -> None:
        with pytest.raises(rc.CensusFormatError):
            rc.parse_rows(_row(entry_id="OPS-87"))

    def test_an_empty_quote_is_refused_because_it_would_match_everything(
        self,
    ) -> None:
        # An empty anchor would resolve against any text at all, so the guard
        # would report a clean bill for a row pinned to nothing.
        with pytest.raises(rc.CensusFormatError):
            rc.parse_rows(_row(quote=""))

    def test_the_line_number_is_reported_so_a_bad_row_can_be_found(self) -> None:
        text = "\n".join((_row(), _row(bucket="z")))
        with pytest.raises(rc.CensusFormatError) as excinfo:
            rc.parse_rows(text)
        assert "line 2" in str(excinfo.value)


class TestWindow:
    LEDGER = "\n".join(
        (
            "### LL-0236 - 2026-09-12 - newest",
            "body",
            "### LL-0200 - 2026-09-08 - on the boundary",
            "body",
            "### LL-0100 - 2026-09-07 - older than the window",
            "body",
        )
    )

    def test_the_window_is_derived_from_headings_and_includes_the_boundary(
        self,
    ) -> None:
        assert rc.window_entries(self.LEDGER, start="2026-09-08") == (
            "LL-0236",
            "LL-0200",
        )

    def test_an_entry_filed_AFTER_the_census_is_not_in_the_corpus(self) -> None:
        # Measured the moment this census wrote its own ledger entry: a window
        # open at the top swallowed a 65th entry into a measurement of 64 and
        # reddened the coverage check against the session that produced it. A
        # published percentage that moves every time somebody files an entry is
        # not a measurement of anything.
        later = "### LL-0999 - 2026-09-12 - filed after the census" + chr(10)
        assert "LL-0999" not in rc.window_entries(later + self.LEDGER)

    def test_an_entry_outside_the_window_is_reported(self) -> None:
        rows = rc.parse_rows(_row(entry_id="LL-0100"))
        assert rc.out_of_window(rows, rc.window_entries(self.LEDGER)) == rows

    def test_an_entry_inside_the_window_is_not_reported(self) -> None:
        rows = rc.parse_rows(_row(entry_id="LL-0200"))
        assert rc.out_of_window(rows, rc.window_entries(self.LEDGER)) == []

    def test_the_format_template_heading_is_not_an_entry(self) -> None:
        # docs/LEDGER.md documents its own format with a literal
        # "### LL-0000 - YYYY-MM-DD" line. A date parser that accepted it would
        # count a worked example as a session.
        text = "### LL-0000 - YYYY-MM-DD - one-line summary\n" + self.LEDGER
        assert "LL-0000" not in rc.window_entries(text)


class TestExaminedCoverage:
    """An entry with zero events and an entry nobody read look identical.

    The first four extraction slices covered 53 of the 64 entries the window
    derives, and the census file could not tell the difference: eleven entries
    were simply never opened, and every total was quietly computed over a
    corpus 17 per cent smaller than the one the report named. So coverage is
    DECLARED, in the data file, and checked against the window the ledger
    itself yields.
    """

    def test_the_directive_lists_the_entries_that_were_read(self) -> None:
        text = "*".join(("#examined LL-0184 LL-0185", "#examined LL-0186", ""))
        assert rc.examined_entries(text.replace("*", chr(10))) == (
            "LL-0184",
            "LL-0185",
            "LL-0186",
        )

    def test_an_ordinary_comment_is_not_a_directive(self) -> None:
        assert rc.examined_entries("# examined LL-0184 by hand" + chr(10)) == ()

    def test_a_malformed_id_in_the_directive_is_refused(self) -> None:
        with pytest.raises(rc.CensusFormatError):
            rc.examined_entries("#examined LL-0184 OPS-87" + chr(10))

    def test_an_in_window_entry_nobody_examined_is_reported(self) -> None:
        assert rc.unexamined(("LL-0184", "LL-0185"), ("LL-0184",)) == ("LL-0185",)

    def test_an_examined_entry_outside_the_window_is_reported(self) -> None:
        # The mirror direction. A declaration that has drifted PAST the window
        # is a claim about a corpus the report does not describe.
        assert rc.examined_outside(("LL-0184",), ("LL-0184", "LL-0100")) == (
            "LL-0100",
        )


class TestAnchors:
    def test_a_quote_absent_from_the_ledger_is_reported(self) -> None:
        rows = rc.parse_rows(_row(quote="a sentence nobody wrote"))
        assert rc.missing_anchors(rows, "the ledger says something else") == rows

    LEDGER = chr(10).join(
        (
            "### LL-0236 - 2026-09-12 - the entry the row names",
            "we found the guard was vacuous here",
            "### LL-0235 - 2026-09-12 - a different entry",
            "a sentence that lives somewhere else entirely",
        )
    )

    def test_a_quote_present_verbatim_in_its_own_entry_is_not_reported(
        self,
    ) -> None:
        rows = rc.parse_rows(_row(quote="the guard was vacuous"))
        assert rc.missing_anchors(rows, self.LEDGER) == []

    def test_a_quote_that_resolves_in_a_DIFFERENT_entry_is_reported(self) -> None:
        # The false pass a repository-wide substring test allows, and the
        # reason the check is scoped. The row would still be describing an
        # event that no longer exists where it says it does, and the guard
        # would be green on the strength of somebody else's sentence.
        rows = rc.parse_rows(_row(quote="lives somewhere else entirely"))
        assert rc.missing_anchors(rows, self.LEDGER) == rows

    def test_the_unscoped_question_can_still_be_asked_and_answers_differently(
        self,
    ) -> None:
        rows = rc.parse_rows(_row(quote="lives somewhere else entirely"))
        assert rc.missing_anchors(rows, self.LEDGER, scoped=False) == []

    def test_matching_is_case_sensitive_and_not_normalised(self) -> None:
        # A matcher that folded case or collapsed whitespace would keep
        # resolving after the sentence it pins had been meaningfully reworded.
        rows = rc.parse_rows(_row(quote="The Guard Was Vacuous"))
        assert rc.missing_anchors(rows, "the guard was vacuous") == rows


class TestTallies:
    def test_the_tally_counts_rows_and_reports_every_bucket_including_zero(
        self,
    ) -> None:
        rows = rc.parse_rows(
            "\n".join((_row(bucket="a"), _row(bucket="a"), _row(bucket="c")))
        )
        assert rc.tally(rows) == {"a": 2, "b": 0, "c": 1, "d": 0, "e": 0}

    def test_the_largest_bucket_is_named_with_its_number(self) -> None:
        rows = rc.parse_rows(
            "\n".join((_row(bucket="b"), _row(bucket="b"), _row(bucket="e")))
        )
        assert rc.largest_bucket(rc.tally(rows)) == (("b",), 2)

    def test_a_TIE_names_both_buckets_rather_than_picking_one(self) -> None:
        # OPS-87 asks for the largest bucket NAMED with its number. Picking a
        # winner out of a tie by dictionary order would answer the question
        # with a fact about the sort, which is this repository's own "a claim
        # about the tool wearing the costume of a claim about the world".
        rows = rc.parse_rows("\n".join((_row(bucket="a"), _row(bucket="d"))))
        assert rc.largest_bucket(rc.tally(rows)) == (("a", "d"), 1)

    def test_an_empty_census_has_no_largest_bucket(self) -> None:
        assert rc.largest_bucket(rc.tally([])) == ((), 0)

    def test_the_axis_counts_are_separate_from_the_bucket_counts(self) -> None:
        rows = rc.parse_rows(
            "\n".join(
                (
                    _row(bucket="a", inherited="Y"),
                    _row(bucket="a", fixfix="Y", uncertain="Y"),
                )
            )
        )
        assert rc.axis_counts(rows) == {"inherited": 1, "fixfix": 1, "uncertain": 1}


class TestReport:
    def test_the_report_names_the_largest_bucket_with_its_number(self) -> None:
        rows = rc.parse_rows("\n".join((_row(bucket="c"), _row(bucket="c"))))
        text = rc.format_report(rows, ("LL-0236",), missing=[], stray=[])
        assert "LARGEST BUCKET: (c)" in text
        assert "2 of 2" in text

    def test_the_report_carries_the_two_limits_rather_than_leaving_them_here(
        self,
    ) -> None:
        text = rc.format_report(
            rc.parse_rows(_row()), ("LL-0236",), missing=[], stray=[]
        )
        assert "lower bound" in text
        assert "directional" in text

    def test_an_unexamined_in_window_entry_makes_the_report_say_UNSOUND(
        self,
    ) -> None:
        text = rc.format_report(
            rc.parse_rows(_row()),
            ("LL-0236", "LL-0235"),
            missing=[],
            stray=[],
            unread=("LL-0235",),
        )
        assert "UNSOUND" in text
        assert "LL-0235: in window and never examined" in text

    def test_an_unresolved_anchor_makes_the_report_say_UNSOUND(self) -> None:
        rows = rc.parse_rows(_row())
        text = rc.format_report(rows, ("LL-0236",), missing=rows, stray=[])
        assert "UNSOUND" in text


class TestTheRealCensus:
    """The data file itself, the deliverable OPS-87 criterion 1 asks for."""

    def test_the_data_file_exists_and_is_not_empty(self) -> None:
        assert rc.DATA_PATH.exists(), rc.DATA_PATH
        assert rc.DATA_PATH.read_text(encoding="utf-8").strip()

    def test_every_row_parses(self) -> None:
        assert rc.load_rows()

    def test_every_anchor_still_resolves_verbatim_in_the_ledger(self) -> None:
        missing = rc.missing_anchors(rc.load_rows(), rc.ledger_text())
        assert missing == [], [(row.entry_id, row.quote) for row in missing]

    def test_no_row_classifies_an_entry_outside_the_stated_window(self) -> None:
        stray = rc.out_of_window(rc.load_rows(), rc.window_entries(rc.ledger_text()))
        assert stray == [], [row.entry_id for row in stray]

    def test_the_declared_coverage_is_exactly_the_derived_window(self) -> None:
        window = rc.window_entries(rc.ledger_text())
        examined = rc.examined_entries(rc.DATA_PATH.read_text(encoding="utf-8"))
        assert rc.unexamined(window, examined) == ()
        assert rc.examined_outside(window, examined) == ()

    def test_every_examined_entry_is_either_classified_or_declared_empty(
        self,
    ) -> None:
        # Not an assertion that every entry has an event - most do not. It
        # asserts the report can SAY which, so "zero events" is a result rather
        # than an absence of reading.
        rows = rc.load_rows()
        examined = rc.examined_entries(rc.DATA_PATH.read_text(encoding="utf-8"))
        with_events = {row.entry_id for row in rows}
        assert with_events <= set(examined), sorted(with_events - set(examined))

    def test_the_cli_prints_a_report_and_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "ops.refutation_census"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        assert "LARGEST BUCKET:" in completed.stdout
