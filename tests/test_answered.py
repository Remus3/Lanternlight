"""Tests for :mod:`ops.answered` - the read-and-unanswered reader.

Every fixture here is SYNTHETIC and lives under ``tmp_path``. Nothing in this
file reads the real ``moon_sync_inbox/`` or the real ``ops/runtime/``, because a
test that depends on the live channel passes or fails on what arrived this
morning rather than on the code.

THE TEST THIS FILE EXISTS FOR
-----------------------------
:func:`test_unknown_is_not_vacuous_when_the_record_cannot_say` builds a tree
where a two-bucket implementation would report a confident
"one answered, one unanswered" and asserts that the RECORD reports neither -
both notes land in UNKNOWN, and the only place a number appears is the
separately labelled INFERENCE. That is the defect ``ops/answered.py`` exists to
prevent, so it is the test that must never be allowed to go vacuous.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ops import answered

# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="ascii")


def _seen(root: Path, names) -> None:
    _write_json(
        root / "ops" / "runtime" / "inbox_seen.json",
        {
            "schema": 1,
            "seen": [[name, "0" * 64] for name in names],
            "updated": "2026-10-02T00:00:00Z",
        },
    )


def _row(name: str, *, sent_local: str | None = None, answers=None, **extra) -> dict:
    row = {
        "name": name,
        "digest": "1" * 64,
        "recipients": ["RC"],
        "delivered": ["RC"],
        "failed": [],
        "byte_count": 10,
    }
    if sent_local is not None:
        row["sent_local"] = sent_local
        row["sent_utc"] = sent_local.replace("T", "T") + "Z"
    if answers is not None:
        row["answers"] = list(answers)
    row.update(extra)
    return row


def _deliveries(root: Path, rows) -> None:
    _write_json(
        root / "moon_sync_inbox" / "_outbox" / "DELIVERIES.json",
        {"what": "synthetic", "item": "test", "deliveries": list(rows)},
    )


def _sent_body(root: Path, name: str, text: str) -> None:
    out = root / "moon_sync_inbox" / "_outbox"
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(text, encoding="ascii")


def _snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# filename parsing
# ---------------------------------------------------------------------------


def test_parse_accepts_a_stamped_note() -> None:
    ref = answered.parse_note_name("2026-09-06-1745-from-RC-a-correction.md")
    assert ref is not None
    assert ref.sender == "RC"
    assert ref.stamp == "1745"
    assert ref.slug == "a-correction"
    assert ref.when == datetime(2026, 9, 6, 17, 45)


def test_parse_accepts_a_dateless_note_and_records_the_missing_stamp() -> None:
    ref = answered.parse_note_name("2026-09-11-from-CS-positions-on-Q1-Q5.md")
    assert ref is not None
    assert ref.sender == "CS"
    assert ref.stamp is None
    assert ref.when == datetime(2026, 9, 11, 0, 0)


def test_parse_refuses_an_unknown_sender_and_a_non_note() -> None:
    assert answered.parse_note_name("2026-09-11-from-ZZ-who-is-this.md") is None
    assert answered.parse_note_name("REFERENCE-moon_sync_poller.py.txt") is None
    assert answered.parse_note_name("lw_write_tracer.py.from-lw") is None


def test_known_senders_cover_every_code_in_reply_paths() -> None:
    doc = Path(__file__).resolve().parents[1] / "docs" / "REPLY_PATHS.md"
    codes = set(answered.reply_path_codes(doc.read_text(encoding="ascii")))
    assert codes, "parsed no codes out of REPLY_PATHS.md - check the pattern"
    assert codes <= set(answered.KNOWN_SENDERS)


# ---------------------------------------------------------------------------
# the RECORD - three buckets, never two
# ---------------------------------------------------------------------------


def test_recorded_answered_when_a_row_names_the_note() -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(inbound)],
        answered.sent_rows_from(
            [_row("x.md", sent_local="2026-09-07T10:00:00", answers=[inbound])]
        ),
    )
    assert verdict.recorded_answered == (inbound,)
    assert verdict.recorded_unanswered == ()
    assert verdict.unknown == ()


def test_recorded_unanswered_when_the_field_covers_the_period_and_omits_it() -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    other = "2026-09-06-1700-from-LW-something-else.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(inbound)],
        answered.sent_rows_from(
            [_row("x.md", sent_local="2026-09-07T10:00:00", answers=[other])]
        ),
    )
    assert verdict.recorded_unanswered == (inbound,)
    assert verdict.recorded_answered == ()
    assert verdict.unknown == ()


def test_unknown_when_no_later_row_carries_the_field() -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(inbound)],
        answered.sent_rows_from([_row("x.md", sent_local="2026-09-07T10:00:00")]),
    )
    assert verdict.unknown == (inbound,)
    assert verdict.recorded_answered == ()
    assert verdict.recorded_unanswered == ()


def test_unknown_when_the_only_answers_row_predates_the_note() -> None:
    inbound = "2026-09-20-1200-from-SS-late-arrival.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(inbound)],
        answered.sent_rows_from(
            [_row("x.md", sent_local="2026-09-07T10:00:00", answers=[])]
        ),
    )
    assert verdict.unknown == (inbound,)


def test_unknown_is_not_vacuous_when_the_record_cannot_say(tmp_path: Path) -> None:
    """A tree where a two-bucket reader would print a confident number.

    Two inbound notes, two legacy sent rows with NO ``answers`` key at all, and
    sent bodies rigged so Amberstone's inference matches exactly one of them. A
    reader that treated a missing field as "answered nothing" would report
    1 answered and 1 unanswered. The RECORD must report 0 and 0, with both in
    UNKNOWN, and the 1/1 must appear only under the INFERENCE.
    """
    hit = "2026-09-06-1745-from-RC-a-correction.md"
    miss = "2026-09-06-1746-from-LW-unmentioned.md"
    _seen(tmp_path, [hit, miss])
    _deliveries(
        tmp_path,
        [
            _row("2026-09-07-1000-from-LL-reply-one.md", sent_local="2026-09-07T10:00:00"),
            _row("2026-09-08-1000-from-LL-reply-two.md", sent_local="2026-09-08T10:00:00"),
        ],
    )
    _sent_body(
        tmp_path,
        "2026-09-07-1000-from-LL-reply-one.md",
        "We answered " + hit + " today.\n",
    )
    _sent_body(
        tmp_path, "2026-09-08-1000-from-LL-reply-two.md", "Nothing relevant here.\n"
    )

    report = answered.report(root=tmp_path)

    assert report.record.recorded_answered == ()
    assert report.record.recorded_unanswered == ()
    assert set(report.record.unknown) == {hit, miss}
    assert report.record.counts()[answered.UNKNOWN] == 2

    assert report.inference is not None
    assert report.inference.inferred_answered == (hit,)
    assert report.inference.inferred_unanswered == (miss,)

    text = report.format()
    assert answered.UNKNOWN in text
    assert "INFERENCE" in text


def test_a_mixed_manifest_splits_across_all_three_buckets() -> None:
    early = "2026-09-06-1745-from-RC-legacy-era.md"
    named = "2026-09-10-0900-from-LW-named.md"
    silent = "2026-09-10-0901-from-SS-not-named.md"
    rows = answered.sent_rows_from(
        [
            _row("legacy.md", sent_local="2026-09-07T10:00:00"),
            _row("modern.md", sent_local="2026-09-11T10:00:00", answers=[named]),
        ]
    )
    verdict = answered.classify_record(
        [answered.parse_note_name(n) for n in (early, named, silent)], rows
    )
    assert verdict.recorded_answered == (named,)
    assert verdict.recorded_unanswered == (silent,)
    assert verdict.unknown == (early,)
    assert verdict.counts() == {
        answered.RECORDED_ANSWERED: 1,
        answered.RECORDED_UNANSWERED: 1,
        answered.UNKNOWN: 1,
    }


def test_one_annotated_row_does_not_cover_the_legacy_backlog() -> None:
    """Coverage is EVERY later row, not ANY later row.

    A reply sent today that names nothing from 2026-09-06 says nothing about
    2026-09-06, because a legacy reply in between may have been the answer. An
    "any" rule would flip the whole backlog to RECORDED-UNANSWERED the moment one
    modern reply went out.
    """
    old = "2026-09-06-1745-from-RC-from-the-legacy-window.md"
    rows = answered.sent_rows_from(
        [
            _row("legacy-reply.md", sent_local="2026-09-07T10:00:00"),
            _row("modern-reply.md", sent_local="2026-10-01T10:00:00", answers=[]),
        ]
    )
    verdict = answered.classify_record([answered.parse_note_name(old)], rows)
    assert verdict.unknown == (old,)
    assert verdict.recorded_unanswered == ()


def test_buckets_are_disjoint_by_construction() -> None:
    name = "2026-09-06-1745-from-RC-a-correction.md"
    with pytest.raises(ValueError):
        answered.RecordVerdict(
            recorded_answered=(name,),
            recorded_unanswered=(name,),
            unknown=(),
            unclassifiable_by_our_parser=(),
        )


def test_the_verdict_exposes_no_two_way_figure() -> None:
    """No attribute may answer "how many answered" without saying WHICH record."""
    banned = {"answered", "unanswered", "answered_count", "unanswered_count", "split"}
    assert banned.isdisjoint(set(dir(answered.RecordVerdict)))
    assert banned.isdisjoint(set(dir(answered.AnsweredReport)))


def test_counts_always_carries_all_three_keys_even_at_zero() -> None:
    verdict = answered.classify_record([], answered.sent_rows_from([]))
    assert set(verdict.counts()) == {
        answered.RECORDED_ANSWERED,
        answered.RECORDED_UNANSWERED,
        answered.UNKNOWN,
    }
    text = verdict.format()
    for bucket in verdict.counts():
        assert bucket in text


def test_by_sender_counts_each_bucket_separately() -> None:
    rc = "2026-09-10-0900-from-RC-one.md"
    ss = "2026-09-10-0901-from-SS-two.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(n) for n in (rc, ss)],
        answered.sent_rows_from(
            [_row("m.md", sent_local="2026-09-11T10:00:00", answers=[rc])]
        ),
    )
    assert verdict.by_sender["RC"][answered.RECORDED_ANSWERED] == 1
    assert verdict.by_sender["SS"][answered.RECORDED_UNANSWERED] == 1
    assert verdict.by_sender["RC"][answered.RECORDED_UNANSWERED] == 0


def test_an_answers_entry_matches_with_or_without_the_md_suffix() -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    verdict = answered.classify_record(
        [answered.parse_note_name(inbound)],
        answered.sent_rows_from(
            [_row("x.md", sent_local="2026-09-07T10:00:00", answers=[inbound[:-3]])]
        ),
    )
    assert verdict.recorded_answered == (inbound,)


# ---------------------------------------------------------------------------
# reconstructed rows and other shapes that must not raise
# ---------------------------------------------------------------------------


def test_a_reconstructed_row_uses_its_arrival_time_and_says_so() -> None:
    rows = answered.sent_rows_from(
        [
            _row(
                "r.md",
                reconstructed=True,
                earliest_seen_local="2026-09-06T15:44:41",
                note="recovered from a sibling inbox",
            )
        ]
    )
    assert rows[0].time_source == "earliest_seen_local"
    assert rows[0].when == datetime(2026, 9, 6, 15, 44, 41)
    assert rows[0].has_answers is False


def test_a_row_with_no_usable_timestamp_is_reported_not_raised() -> None:
    rows = answered.sent_rows_from([_row("t.md")])
    assert rows[0].when is None
    assert rows[0].time_source == "none"
    verdict = answered.classify_record(
        [answered.parse_note_name("2026-09-06-1745-from-RC-a-correction.md")], rows
    )
    assert len(verdict.unknown) == 1


def test_unclassifiable_names_are_filed_under_our_own_limitation(tmp_path: Path) -> None:
    _seen(tmp_path, ["REFERENCE-moon_sync_poller.py.txt", "lw_write_tracer.py.from-lw"])
    _deliveries(tmp_path, [])
    report = answered.report(root=tmp_path)
    assert len(report.record.unclassifiable_by_our_parser) == 2
    assert "unclassifiable_by_our_parser" in report.format()
    assert sum(report.record.counts().values()) == 0


# ---------------------------------------------------------------------------
# the INFERENCE - Amberstone's rule, second-class and labelled
# ---------------------------------------------------------------------------


def test_inference_carries_its_attribution_and_its_bias(tmp_path: Path) -> None:
    inf = answered.infer([], answered.sent_rows_from([]), tmp_path)
    assert "Amberstone" in inf.rule_source
    assert "FLOOR" in inf.bias
    assert "2026-09-06" in inf.bias
    assert "FLOOR" in inf.format()


@pytest.mark.parametrize(
    "body",
    [
        "see 2026-09-06-1745-from-RC-a-correction.md for the detail\n",
        "see a-correction for the detail\n",
        "RC said at 1745 that the figure moved\n",
    ],
)
def test_inference_matches_filename_slug_and_code_near_stamp(
    tmp_path: Path, body: str
) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-07T10:00:00")])
    _sent_body(tmp_path, "s.md", body)
    report = answered.report(root=tmp_path)
    assert report.inference is not None
    assert report.inference.inferred_answered == (inbound,)


def test_inference_refuses_a_sent_note_that_is_not_strictly_later(
    tmp_path: Path,
) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-06T17:45:00")])
    _sent_body(tmp_path, "s.md", "see " + inbound + "\n")
    report = answered.report(root=tmp_path)
    assert report.inference is not None
    assert report.inference.inferred_unanswered == (inbound,)


def test_code_near_stamp_window_is_fifteen_characters(tmp_path: Path) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    assert answered.code_near_stamp("RC" + "." * 15 + "1745", "RC", "1745") is True
    assert answered.code_near_stamp("RC" + "." * 16 + "1745", "RC", "1745") is False
    assert answered.code_near_stamp("RC\n" + "." * 2 + "1745", "RC", "1745") is False
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-07T10:00:00")])
    _sent_body(tmp_path, "s.md", "RC" + "." * 16 + "1745\n")
    report = answered.report(root=tmp_path)
    assert report.inference is not None
    assert report.inference.inferred_unanswered == (inbound,)


def test_a_dateless_note_cannot_be_matched_by_code_near_stamp(tmp_path: Path) -> None:
    inbound = "2026-09-11-from-CS-no-stamp-at-all.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-12T10:00:00")])
    _sent_body(tmp_path, "s.md", "CS 1200 said something\n")
    report = answered.report(root=tmp_path)
    assert report.inference is not None
    assert report.inference.inferred_unanswered == (inbound,)


def test_a_missing_sent_body_is_reported_not_raised(tmp_path: Path) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("gone.md", sent_local="2026-09-07T10:00:00")])
    report = answered.report(root=tmp_path)
    assert report.inference is not None
    assert report.inference.sent_text_missing == ("gone.md",)
    assert report.inference.inferred_unanswered == (inbound,)


def test_the_inference_is_never_merged_into_the_record(tmp_path: Path) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-07T10:00:00")])
    _sent_body(tmp_path, "s.md", "see " + inbound + "\n")
    report = answered.report(root=tmp_path)
    assert report.record.unknown == (inbound,)
    assert report.inference is not None
    assert report.inference.inferred_answered == (inbound,)


# ---------------------------------------------------------------------------
# the module is a READER
# ---------------------------------------------------------------------------


def test_report_writes_nothing_and_mutates_nothing(tmp_path: Path) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-07T10:00:00")])
    _sent_body(tmp_path, "s.md", "see " + inbound + "\n")
    before = _snapshot(tmp_path)
    answered.report(root=tmp_path).format()
    assert _snapshot(tmp_path) == before


def test_format_leaks_no_note_body(tmp_path: Path) -> None:
    inbound = "2026-09-06-1745-from-RC-a-correction.md"
    _seen(tmp_path, [inbound])
    _deliveries(tmp_path, [_row("s.md", sent_local="2026-09-07T10:00:00")])
    _sent_body(tmp_path, "s.md", "MARKER-SECRET-SENTENCE and " + inbound + "\n")
    text = answered.report(root=tmp_path).format()
    assert "MARKER-SECRET-SENTENCE" not in text


def test_missing_records_are_absent_not_zero(tmp_path: Path) -> None:
    report = answered.report(root=tmp_path)
    assert report.record.counts() == {
        answered.RECORDED_ANSWERED: 0,
        answered.RECORDED_UNANSWERED: 0,
        answered.UNKNOWN: 0,
    }
    assert "no seen record" in report.format()


class TestTheRefutationPassFindings:
    """Three defects an adversarial pass found at the 2026-10-02 wrap.

    Each one is a case where this module's own docstring promised something its
    code did not do, which is the class this repository calls a lie in the
    artifact.
    """

    def test_an_out_of_range_stamp_returns_None_rather_than_raising(self) -> None:
        """FINDING A. ``parse_note_name`` documents ``None`` for a name it cannot
        read, and only the DATE was inside the try - so a 4-digit stamp that is
        not a time killed the whole report rather than being unclassifiable.
        """
        assert answered.parse_note_name("2026-09-06-9999-from-RC-x.md") is None
        assert answered.parse_note_name("2026-09-06-2599-from-RC-x.md") is None
        assert answered.parse_note_name("2026-09-06-1260-from-RC-x.md") is None
        # The control: a real stamp still parses, so the fix did not simply
        # disable the clause it was meant to harden.
        good = answered.parse_note_name("2026-09-06-1430-from-RC-x.md")
        assert good is not None
        assert good.stamp == "1430"

    def test_an_omitted_answers_key_is_distinguishable_from_an_empty_list(self) -> None:
        """FINDING B. The OMITTED-versus-EMPTY distinction is what makes UNKNOWN
        mean anything, and it was guarded on the WRITE side only: collapsing it in
        ``sent_rows_from`` left all 31 tests passing. This asserts the READ side
        directly, so the distinction cannot be collapsed silently again.
        """
        omitted = answered.sent_rows_from([{"name": "a.md", "sent_utc": "2026-10-01T00:00:00Z"}])
        empty = answered.sent_rows_from(
            [{"name": "b.md", "sent_utc": "2026-10-01T00:00:00Z", "answers": []}]
        )
        assert omitted[0].has_answers is False, (
            "a row with NO answers key is NOT RECORDED"
        )
        assert empty[0].has_answers is True, (
            "a row with answers=[] RECORDED that it answers nothing - a different "
            "fact, and the one a bool() collapse destroys"
        )
        assert omitted[0].answers == ()
        assert empty[0].answers == ()

    def test_a_recorded_answer_to_a_note_outside_the_population_is_REPORTED(self) -> None:
        """FINDING C. A row citing a note that is not in the population was
        silently dropped - the live tree recorded two citations and reported one,
        with no problem line. A citation we cannot place is a statement about our
        population and must not vanish.
        """
        notes = [answered.parse_note_name("2026-10-01-1200-from-RC-seen.md")]
        rows = answered.sent_rows_from(
            [
                {
                    "name": "2026-10-02-0100-from-LL-reply.md",
                    "sent_utc": "2026-10-02T01:00:00Z",
                    "answers": [
                        "2026-10-01-1200-from-RC-seen.md",
                        "2026-10-01-1300-from-RC-not-in-population.md",
                    ],
                }
            ]
        )
        verdict = answered.classify_record(
            [n for n in notes if n is not None], rows, (), ()
        )
        assert "2026-10-01-1200-from-RC-seen.md" in verdict.recorded_answered
        # Assert on the VERDICT, not on a list handed in: classify_record returns
        # a new tuple and does not mutate its argument. The first version of this
        # test asserted on the argument and failed against correct code, which is
        # the "a negative result is a claim about your probe" rule one level down.
        joined = " ".join(verdict.problems)
        assert "not-in-population" in joined, (
            "a cited answer outside the population must be REPORTED, not dropped: "
            f"problems were {verdict.problems!r}"
        )
        # And a citation we CAN place must not be reported as a problem.
        assert "seen.md" not in joined.replace("not-in-population", "")
