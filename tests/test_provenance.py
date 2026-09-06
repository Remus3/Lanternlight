"""`OPS-28`: provenance must travel with the ROW, not only with the document.

WHAT THIS FILE IS WRITTEN AGAINST, measured 2026-09-06 before any code existed.
An outside consumer does not read a document, it lifts a table. Slicing the
`Affix Level ladder` out of `docs/AFFIXES.md` the way a scraper would - the
pipe-delimited rows and nothing else - yields seven rows of percentages that
cannot answer which build they were read on, by what method, on what date, or
whether the 2026-08-19T08:06:36Z patch invalidated them. All four questions come
back UNANSWERABLE. Downstream those rows are indistinguishable from a
fandom-wiki number and a stranger is correct to treat them that way.

**`docs/AFFIXES.md` is NOT under-sourced, and saying so is a withdrawn
misreading this file must not repeat.** The provenance is there in the prose:
the section is headed `Affix Level ladder, stated`, it names frame `f0749`, it
quotes the tooltip it came from, and it records its own withdrawn misreading of
the Level Distribution row. The defect is that none of that survives
extraction. Provenance that does not TRAVEL is the bug.

`docs/OBSERVED_IDS.md` is the good case and it still loses half. Its class-id
rows carry a per-row `How established` column, so method survives extraction and
date survives for four of six rows - but the buildid and the
never-reconfirmed-since-the-patch warning live in a prose paragraph above the
table, and both are gone the moment the table is lifted.

So the fix is not "add provenance to the documents" - they have it. The fix is a
row-scoped emission, generated FROM the markdown, in which every single row
carries its own build, method, date and reconfirmation status. The markdown
stays authoritative; :class:`TestTheMarkdownStaysAuthoritative` fails if the two
ever drift, so the emission can never quietly become a second source of truth.

Every negative assertion below is paired with a positive one. A test that only
proves the naked rows answer nothing would pass just as happily against an empty
file, so each loss is asserted alongside the emitted record answering the same
question.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import provenance  # noqa: E402  (path bootstrap must run first)

AFFIXES_MD = REPO_ROOT / "docs" / "AFFIXES.md"
OBSERVED_IDS_MD = REPO_ROOT / "docs" / "OBSERVED_IDS.md"
DATA_FILE = REPO_ROOT / "docs" / "data" / "provenance.json"


# --------------------------------------------------------------------------
# the outside consumer, simulated without touching the module under test
# --------------------------------------------------------------------------
#
# Deliberately does NOT import the parser. This is what a scraper sees, and a
# scraper does not have our code.


def lift_table_blocks(text: str) -> list[list[str]]:
    """Return every contiguous run of markdown table rows - rows only."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            current.append(line)
        else:
            if len(current) >= 3:
                blocks.append(current)
            current = []
    if len(current) >= 3:
        blocks.append(current)
    return blocks


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


#: Full header rows, because a FIRST cell is not unique in either document.
#: `docs/OBSERVED_IDS.md` has three tables whose first header cell is `classId`
#: and `docs/AFFIXES.md` has five whose first cell is `Level`, so slicing on the
#: first cell alone would silently lift the wrong table.
LADDER_HEADER = ("Level", "Physical Damage", "Magic Damage", "Effective Range")
CLASS_ID_HEADER = ("classId", "Class", "How established")


def block_with_header(text: str, header: tuple[str, ...]) -> list[str]:
    matches = [b for b in lift_table_blocks(text) if tuple(cells(b[0])) == header]
    assert len(matches) == 1, (
        f"expected exactly one table with header {header!r}, found "
        f"{len(matches)} - the anchor this test slices on has moved"
    )
    return matches[0]


#: The four questions `OPS-28` says a lifted row cannot answer.
QUESTION_PATTERNS = {
    "build": re.compile(r"\b(build|buildid|24619162|24813185|1\.0\.1[45])\b", re.I),
    "method": re.compile(
        r"\b(pixel-join\w*|tooltip|attested|elimination|OCR|measured|"
        r"transcrib\w*|frame)\b",
        re.I,
    ),
    "date": re.compile(r"\b20\d\d-\d\d-\d\d\b"),
    "reconfirmed": re.compile(r"(reconfirm\w*|re-confirm\w*|2026-08-19|patch)", re.I),
}


def answerable_from(blob: str) -> set[str]:
    return {name for name, pat in QUESTION_PATTERNS.items() if pat.search(blob)}


@pytest.fixture(scope="module")
def affixes_md() -> str:
    return AFFIXES_MD.read_text(encoding="ascii")


@pytest.fixture(scope="module")
def observed_ids_md() -> str:
    return OBSERVED_IDS_MD.read_text(encoding="ascii")


@pytest.fixture(scope="module")
def emitted() -> dict:
    """The committed emission, READ - never regenerated by a test.

    A test that regenerated the file before checking it would compare the
    generator against itself and pass over any drift, which is precisely the
    failure `OPS-28` criterion 4 exists to catch.
    """
    return json.loads(DATA_FILE.read_text(encoding="ascii"))


def records_from(dataset: dict, anchor: str) -> list[dict]:
    return [r for r in dataset["records"] if r["source"]["anchor"] == anchor]


# --------------------------------------------------------------------------
# criterion 1 - the loss, kept alive in the suite so it cannot rot
# --------------------------------------------------------------------------


class TestTheExtractionLossIsReal:
    """The demonstration, encoded. Each loss is paired with the emitted row
    answering the same question, so nothing here passes against an empty file."""

    def test_the_affix_ladder_rows_answer_none_of_the_four_questions(self, affixes_md):
        block = block_with_header(affixes_md, LADDER_HEADER)
        assert len(block) == 9, "expected a header, a rule and seven data rows"
        answered = answerable_from("\n".join(block))
        assert answered == set(), (
            "the naked affix rows unexpectedly answered "
            f"{sorted(answered)} - if this is real, OPS-28 is refuted for this "
            "table and the refutation is the result"
        )

    def test_the_emitted_affix_rows_answer_all_four(self, emitted):
        rows = records_from(emitted, "Affix Level ladder, stated")
        assert len(rows) == 7, "the emission lost rows the markdown has"
        for record in rows:
            answered = answerable_from(json.dumps(record))
            assert answered == set(QUESTION_PATTERNS), (
                f"{record['record_id']} still cannot answer "
                f"{sorted(set(QUESTION_PATTERNS) - answered)}"
            )

    def test_the_class_id_rows_lose_build_and_reconfirmation(self, observed_ids_md):
        """The GOOD case, and it still travels only half."""
        block = block_with_header(observed_ids_md, CLASS_ID_HEADER)
        answered = answerable_from("\n".join(block))
        assert "method" in answered, (
            "the How established column is the thing that makes this the good "
            "case; if it is gone, this test is measuring a different table"
        )
        assert "build" not in answered
        assert "reconfirmed" not in answered

    def test_two_of_six_class_rows_do_not_even_carry_their_own_date(
        self, observed_ids_md
    ):
        block = block_with_header(observed_ids_md, CLASS_ID_HEADER)
        dateless = [
            cells(row)[0]
            for row in block[2:]
            if not QUESTION_PATTERNS["date"].search(row)
        ]
        assert dateless == ["12", "15"], (
            "measured 2026-09-06: rows 12 and 15 state a method but no date, "
            f"so the document default has to supply it; got {dateless}"
        )

    def test_the_emitted_class_rows_answer_all_four(self, emitted):
        rows = records_from(emitted, "Class ids")
        assert len(rows) == 6
        for record in rows:
            answered = answerable_from(json.dumps(record))
            assert answered == set(QUESTION_PATTERNS), (
                f"{record['record_id']} still cannot answer "
                f"{sorted(set(QUESTION_PATTERNS) - answered)}"
            )


# --------------------------------------------------------------------------
# criterion 2 - named required fields, and a guard that reddens on omission
# --------------------------------------------------------------------------


class TestEveryRequiredFieldIsNamedAndEnforced:
    def test_the_required_set_is_pinned_by_name(self):
        """Without this, emptying ``REQUIRED_RECORD_FIELDS`` would make the
        parametrised loop below collect nothing and stay green forever."""
        assert set(provenance.REQUIRED_RECORD_FIELDS) == {
            "record_id",
            "subject",
            "source",
            "source_row",
            "values",
            "method",
            "observed_on",
            "build",
            "claim_type",
            "reconfirmations",
        }
        assert set(provenance.REQUIRED_BUILD_FIELDS) == {"scheme", "buildid"}
        assert set(provenance.REQUIRED_SOURCE_FIELDS) == {"document", "anchor"}

    def test_every_emitted_record_validates(self, emitted):
        provenance.validate_dataset(emitted)
        assert len(emitted["records"]) == 13, (
            "two tables, thirteen rows - a shrinking emission would otherwise "
            "validate vacuously"
        )

    @pytest.mark.parametrize("field", provenance.REQUIRED_RECORD_FIELDS)
    def test_dropping_any_required_field_reddens(self, emitted, field):
        record = copy.deepcopy(emitted["records"][0])
        assert field in record, "anchor check - the field was there to remove"
        del record[field]
        with pytest.raises(provenance.ProvenanceError) as excinfo:
            provenance.validate_record(record)
        assert field in str(excinfo.value), "the failure must NAME the field"

    @pytest.mark.parametrize("field", provenance.REQUIRED_BUILD_FIELDS)
    def test_dropping_any_required_build_field_reddens(self, emitted, field):
        record = copy.deepcopy(emitted["records"][0])
        assert field in record["build"], "anchor check"
        del record["build"][field]
        with pytest.raises(provenance.ProvenanceError) as excinfo:
            provenance.validate_record(record)
        assert field in str(excinfo.value)

    def test_an_empty_required_string_is_not_a_value(self, emitted):
        record = copy.deepcopy(emitted["records"][0])
        assert record["method"], "anchor check"
        record["method"] = "   "
        with pytest.raises(provenance.ProvenanceError):
            provenance.validate_record(record)


# --------------------------------------------------------------------------
# criterion 5 - the buildid guard, watched going red
# --------------------------------------------------------------------------


class TestTheBuildidGuardRedensWhenTheBuildidGoes:
    """`OPS-28` criterion 5, in-suite. The same deletion was also performed on
    the committed file on disk and watched go red; see the session report."""

    def test_deleting_one_records_buildid_fails_the_dataset(self, emitted):
        dataset = copy.deepcopy(emitted)
        victim = dataset["records"][3]
        assert victim["build"]["buildid"], "anchor check - there was one to delete"
        del victim["build"]["buildid"]
        with pytest.raises(provenance.ProvenanceError) as excinfo:
            provenance.validate_dataset(dataset)
        message = str(excinfo.value)
        assert "buildid" in message
        assert victim["record_id"] in message, (
            "a dataset-level failure that does not name the offending record "
            "is not actionable"
        )

    def test_and_the_same_dataset_is_green_with_the_buildid_restored(self, emitted):
        dataset = copy.deepcopy(emitted)
        provenance.validate_dataset(dataset)


# --------------------------------------------------------------------------
# criterion 3 - absent is not null, and unmeasured is not measured zero
# --------------------------------------------------------------------------


class TestAbsentIsNotNullNorZero:
    """ADR-005. A missing field is ABSENT - not null, not 0, not -1 - and
    `unmeasured` stays distinguishable from `measured zero`."""

    def test_a_stated_zero_is_present_and_reads_back_as_zero(self, emitted):
        lv1 = provenance.by_record_id(emitted, "affixes.ranged_ladder.lv1")
        assert provenance.is_measured(lv1, "effective_range_pct")
        assert provenance.measured_value(lv1, "effective_range_pct") == 0
        assert provenance.is_measured_zero(lv1, "effective_range_pct")

    def test_an_unmeasured_quantity_is_absent_and_raises_rather_than_defaulting(
        self, emitted
    ):
        """The tooltip says Impact diminishes past the effective range and
        states no magnitude for it anywhere, so `impact_pct` is unmeasured."""
        lv1 = provenance.by_record_id(emitted, "affixes.ranged_ladder.lv1")
        assert "impact_pct" not in lv1["values"]
        assert not provenance.is_measured(lv1, "impact_pct")
        assert not provenance.is_measured_zero(lv1, "impact_pct")
        with pytest.raises(provenance.Unmeasured):
            provenance.measured_value(lv1, "impact_pct")

    def test_the_two_are_not_the_same_answer(self, emitted):
        """The whole point. If these ever collapse, the engine starts lying."""
        lv1 = provenance.by_record_id(emitted, "affixes.ranged_ladder.lv1")
        assert provenance.is_measured(lv1, "effective_range_pct") is not (
            provenance.is_measured(lv1, "impact_pct")
        )

    def test_a_null_is_rejected_outright(self, emitted):
        record = copy.deepcopy(emitted["records"][0])
        record["values"]["physical_damage_pct"] = None
        with pytest.raises(provenance.ProvenanceError):
            provenance.validate_record(record)

    @pytest.mark.parametrize("sentinel", ["-", "", "n/a", "N/A", "unknown", "?", "TBD"])
    def test_a_placeholder_string_is_rejected_outright(self, emitted, sentinel):
        record = copy.deepcopy(emitted["records"][0])
        key = next(iter(record["values"]))
        record["values"][key] = sentinel
        with pytest.raises(provenance.ProvenanceError):
            provenance.validate_record(record)

    def test_the_guard_does_not_over_reach_onto_real_measurements(self, emitted):
        """0 and -1 are legitimate MEASURED values. The rule is about how
        absence is represented, not about which numbers may be recorded, and a
        guard that rejected them would destroy the measured zero it protects."""
        record = copy.deepcopy(emitted["records"][0])
        key = next(iter(record["values"]))
        for legitimate in (0, -1, 0.0):
            record["values"][key] = legitimate
            provenance.validate_record(record)


# --------------------------------------------------------------------------
# criterion 4 - the markdown stays authoritative
# --------------------------------------------------------------------------


class TestTheMarkdownStaysAuthoritative:
    """A drift between the markdown and the emission is a FAILING TEST, not a
    fork. The emission is generated; the table is the source of truth."""

    def test_the_affix_ladder_round_trips_cell_for_cell(self, affixes_md, emitted):
        block = block_with_header(affixes_md, LADDER_HEADER)
        from_markdown = {cells(r)[0]: cells(r) for r in block[2:]}
        from_file = {
            r["source_row"][0]: r["source_row"]
            for r in records_from(emitted, "Affix Level ladder, stated")
        }
        assert from_file == from_markdown

    def test_the_class_id_table_round_trips_cell_for_cell(
        self, observed_ids_md, emitted
    ):
        block = block_with_header(observed_ids_md, CLASS_ID_HEADER)
        from_markdown = {cells(r)[0]: cells(r) for r in block[2:]}
        from_file = {
            r["source_row"][0]: r["source_row"]
            for r in records_from(emitted, "Class ids")
        }
        assert from_file == from_markdown

    def test_a_changed_markdown_cell_would_be_caught(self, affixes_md, emitted):
        """Non-vacuity: mutate the markdown in memory and confirm the
        comparison above would have gone red. Asserts the anchor matched first,
        because a mutation that fails to apply looks exactly like a pass."""
        anchor = "| Lv. 5 | +8% | +8% | +12% |"
        assert anchor in affixes_md, "anchor text did not match - mutation is a no-op"
        mutated = affixes_md.replace(anchor, "| Lv. 5 | +9% | +8% | +12% |")
        assert mutated != affixes_md
        block = block_with_header(mutated, LADDER_HEADER)
        from_markdown = {cells(r)[0]: cells(r) for r in block[2:]}
        from_file = {
            r["source_row"][0]: r["source_row"]
            for r in records_from(emitted, "Affix Level ladder, stated")
        }
        assert from_file != from_markdown

    def test_the_parsed_values_match_the_literal_markdown_text(
        self, affixes_md, emitted
    ):
        """Pins the INTERPRETATION against literal text without routing through
        the parser, so a parser bug cannot agree with itself."""
        assert "| Lv. 5 | +8% | +8% | +12% |" in affixes_md
        assert "| Lv. 1 | +1.6% | +1.6% | - |" in affixes_md
        lv5 = provenance.by_record_id(emitted, "affixes.ranged_ladder.lv5")
        assert lv5["values"]["physical_damage_pct"] == 8.0
        assert lv5["values"]["magic_damage_pct"] == 8.0
        assert lv5["values"]["effective_range_pct"] == 12.0
        lv1 = provenance.by_record_id(emitted, "affixes.ranged_ladder.lv1")
        assert lv1["values"]["physical_damage_pct"] == 1.6
        assert lv1["values"]["effective_range_pct"] == 0

    def test_the_class_names_match_the_literal_markdown_text(
        self, observed_ids_md, emitted
    ):
        assert "| 12 | **Blackarrow** |" in observed_ids_md
        assert "| 15 | **Withered Knight** |" in observed_ids_md
        twelve = provenance.by_record_id(emitted, "observed_ids.class_id.12")
        assert twelve["values"]["class"] == "Blackarrow"
        fifteen = provenance.by_record_id(emitted, "observed_ids.class_id.15")
        assert fifteen["values"]["class"] == "Withered Knight"

    def test_regenerating_from_the_markdown_reproduces_the_committed_file(
        self, affixes_md, observed_ids_md, emitted
    ):
        rebuilt = provenance.build_dataset(
            observed_ids_markdown=observed_ids_md, affixes_markdown=affixes_md
        )
        assert rebuilt == emitted, (
            "the committed emission is stale - regenerate it, and never hand-edit "
            "it: the markdown is authoritative"
        )


# --------------------------------------------------------------------------
# criterion 6 - staleness, answerable from the data alone
# --------------------------------------------------------------------------


class TestStalenessIsAnswerableFromTheDataAlone:
    """Today the fact that every class id was read on a dead build is a
    paragraph only a human can act on. Here it is a query."""

    def test_every_class_id_record_is_flagged_as_read_on_a_superseded_build(
        self, emitted
    ):
        stale = provenance.records_on_superseded_builds(emitted)
        stale_ids = {r["record_id"] for r in stale}
        assert stale_ids == {f"observed_ids.class_id.{n}" for n in range(10, 16)}

    def test_the_affix_rows_are_not_flagged_because_they_are_current(self, emitted):
        current = {r["record_id"] for r in provenance.records_on_current_builds(emitted)}
        assert current == {f"affixes.ranged_ladder.lv{n}" for n in range(1, 8)}

    def test_no_record_falls_into_the_undetermined_bucket(self, emitted):
        """A build scheme with no current-build entry is neither stale nor
        current, and must not silently be counted as either."""
        assert provenance.records_on_undetermined_builds(emitted) == []

    def test_the_query_reads_the_data_rather_than_hardcoding_the_answer(
        self, emitted
    ):
        """Non-vacuity: declare the old build current and the stale set must
        empty out. A function that returned the same six ids either way would
        be reporting a constant, not a query."""
        dataset = copy.deepcopy(emitted)
        entry = next(
            b for b in dataset["current_builds"] if b["scheme"] == "steam_buildid"
        )
        assert entry["buildid"] == "24813185", "anchor check"
        entry["buildid"] = "24619162"
        assert provenance.records_on_superseded_builds(dataset) == []

    def test_a_record_predating_the_patch_is_identifiable(self, emitted):
        """The other half of the fourth question: the class ids were read
        2026-08-09 and the patch landed 2026-08-19T08:06:36Z."""
        predating = provenance.records_predating_latest_patch(emitted)
        assert {r["record_id"] for r in predating} == {
            f"observed_ids.class_id.{n}" for n in range(10, 16)
        }

    def test_never_reconfirmed_is_a_measured_empty_list_not_a_missing_field(
        self, emitted
    ):
        """`OBSERVED_IDS.md` states that NONE of the ids has been reconfirmed.
        That is a measured zero, so the field is present and empty rather than
        omitted - omission would mean nobody looked."""
        for record in records_from(emitted, "Class ids"):
            assert record["reconfirmations"] == []
        record = copy.deepcopy(emitted["records"][0])
        del record["reconfirmations"]
        with pytest.raises(provenance.ProvenanceError):
            provenance.validate_record(record)


# --------------------------------------------------------------------------
# the parser must not invent, and must notice when its anchors move
# --------------------------------------------------------------------------


class TestTheParserFailsLoudRatherThanQuiet:
    def test_a_missing_document_level_build_line_raises(self, observed_ids_md):
        anchor = "buildid `24619162`"
        assert anchor in observed_ids_md, "anchor check - mutation would be a no-op"
        mutated = observed_ids_md.replace(anchor, "buildid unrecorded")
        with pytest.raises(provenance.ProvenanceError):
            provenance.parse_class_id_records(mutated)

    def test_a_missing_reconfirmation_sentence_raises(self, observed_ids_md):
        # Single-line substring on purpose: the sentence is hard-wrapped after
        # "current", so the full sentence matches nothing and the mutation
        # would be a silent no-op that looks exactly like a passing test.
        anchor = "None of them has been re-confirmed on the current"
        assert anchor in observed_ids_md, "anchor check - mutation would be a no-op"
        mutated = observed_ids_md.replace(anchor, "Some were checked again.")
        with pytest.raises(provenance.ProvenanceError):
            provenance.parse_class_id_records(mutated)

    def test_a_missing_frame_citation_raises(self, affixes_md):
        anchor = "f0749_00.47.32"
        assert anchor in affixes_md, "anchor check - mutation would be a no-op"
        mutated = affixes_md.replace(anchor, "an unnamed frame")
        with pytest.raises(provenance.ProvenanceError):
            provenance.parse_affix_ladder_records(mutated)

    def test_the_claim_types_are_not_conflated(self, emitted):
        """A developer's tooltip claim and a first-party observation are
        different facts. `AFFIXES.md` opens by saying that distinction is the
        whole point of the file."""
        by_anchor = {
            "Affix Level ladder, stated": "game_stated",
            "Class ids": "first_party_observed",
        }
        for anchor, expected in by_anchor.items():
            rows = records_from(emitted, anchor)
            assert rows, f"no records for {anchor}"
            assert {r["claim_type"] for r in rows} == {expected}


# --------------------------------------------------------------------------
# the emission is a new PUBLIC surface
# --------------------------------------------------------------------------


class TestTheEmissionIsSafeToPublish:
    def test_it_is_pure_7_bit_ascii_on_disk(self):
        data = DATA_FILE.read_bytes()
        offenders = [i for i, b in enumerate(data) if b >= 0x80]
        assert not offenders, f"non-ASCII bytes at {offenders[:5]}"

    def test_it_carries_no_identifier_the_redactor_recognises(self):
        from lanternlight.redact import FILE_SCAN_LABELS, iter_sensitive

        text = DATA_FILE.read_text(encoding="ascii")
        hits = list(iter_sensitive(text, labels=FILE_SCAN_LABELS))
        assert not hits, f"the emission carries {hits[:3]}"

    def test_it_says_which_documents_are_authoritative(self, emitted):
        documents = {entry["document"] for entry in emitted["generated_from"]}
        assert documents == {"docs/AFFIXES.md", "docs/OBSERVED_IDS.md"}
