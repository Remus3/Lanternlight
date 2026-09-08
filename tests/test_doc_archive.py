"""Tests for the continuity-document splitter engine - ROADMAP ``OPS-57``.

WHY THIS EXISTS. ``ROADMAP.md`` and ``docs/LEDGER.md`` are the two documents a
cold session reads to find out where it is, and both are on a growth curve that
outran their size budgets. ``OPS-57`` criterion 4 forbids deleting a word and
forbids editing, reordering or reflowing any ledger entry, so the only
acceptable answer is to MOVE text, verbatim, into an archive the roadmap points
at. ``tools/doc_archive.py`` is the engine for that move. It is pure: every
function takes text and returns text, and nothing in it writes to disk, so the
planning step can be re-run and inspected as many times as anyone likes before
a byte of either document changes.

CONSERVATION IS THE WHOLE POINT, so it is tested against REAL text and not only
against fixtures. A toy fixture proves the algorithm is self-consistent; it
cannot prove the algorithm survives the shapes that are actually in
``ROADMAP.md`` - a heading whose title contains the word ``OPEN`` in a phrase
like "fails OPEN", a heading whose closure line names a successor item that is
still open, an ``OPS-33`` and an ``OPS-33 follow-up`` that must not collapse to
the same index key, and headings carrying backticks, commas, parentheses and
periods that all have to survive anchor derivation. Each of those was found by
reading the real file, and each has a test below.

WHAT THE REAL SUBJECT IS, AND WHY IT IS THE PAIR AND NOT THE LIVE FILE. This is
a tool whose tests measure the documents the tool MOVES TEXT OUT OF, so the
first time the split was actually applied, on 2026-09-08, seven tests here went
red at once: they had pinned pre-split facts - 84 sections, 65 archivable, 195
ledger entries, an ``OPS-33 follow-up`` heading in ``ROADMAP.md`` - about files
the tool had since changed underneath them.

Editing those numbers down to whatever the live files hold today would produce a
suite that passes this afternoon and fails the next time the split runs, which
is a suite somebody has to edit every session and will eventually edit
carelessly. It is also not even stable within one session: the live roadmap
gained a section between two runs of this file while the repair was being
written, because another lane was editing it.

So the real-text subject is the PAIR - the live document with its archive's body
concatenated back on - reconstructed by :func:`read_roadmap_corpus` and
:func:`read_ledger_corpus`. The pair is what makes the properties re-runnable,
because a split MOVES sections between the two halves and therefore leaves the
pair invariant. Nothing but new authoring changes it, and new authoring only
ever adds. That is why every count below is a FLOOR (``>=`` the value measured
on 2026-09-08, the last moment the pre-split whole existed as one file) and
every exact assertion is a relationship that carries no literal count at all:
ids are unique, the outcome-segment rule agrees with a whole-line scan, ledger
entry numbers descend without a gap across the cut. Those never need editing.

The costs, stated because a caveat dropped from the artifact is a lie in the
artifact:

* The ledger corpus IS the pre-split document, byte for byte - that split was a
  contiguous tail cut - so ledger conservation is still measured against a real
  whole document.
* The roadmap corpus is NOT a valid document. It is the live sections followed
  by the archived sections, so the archived items no longer sit in their
  original positions and the generated ``## Archive index`` section is in the
  middle of it. It is a corpus of real sections with real punctuation, which is
  what the classification, id, anchor and conservation tests need; it is not
  evidence about how ``ROADMAP.md`` itself is ordered.
* A floor is weaker than an equality. It cannot catch a classifier that starts
  archiving MORE than it should. The tests that pin exactly which sections move
  are the number-free ones, and they are the reason the floor is acceptable.

The alternative considered was committing a captured pre-split fixture. It gives
exact counts that the tool cannot move, at the cost of a third file this slice
does not own and of a subject that stops resembling the real document the moment
anyone writes a new roadmap item - so a green suite would stop being evidence
about ``ROADMAP.md`` at all. The pair keeps the real file as the subject.

THE VACUOUS-GUARD TRAP THIS FILE IS BUILT AGAINST. A conservation test that only
checks "the archive is non-empty" passes while an entire section is dropped. So
the conservation assertions here are EQUALITIES over the full text: the new
document concatenated with the archived body must reproduce the original input
exactly, byte for byte. The classification tests are equally specific - they pin
the two ambiguous real headings AND the synthetic both-keywords shapes in each
direction, because a rule that only says "65 headings match" is satisfied by any
65 headings.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import doc_archive  # noqa: E402

ROADMAP_PATH = REPO_ROOT / "ROADMAP.md"
LEDGER_PATH = REPO_ROOT / "docs/LEDGER.md"
ROADMAP_ARCHIVE_PATH = REPO_ROOT / doc_archive.DEFAULT_ROADMAP_ARCHIVE
LEDGER_ARCHIVE_PATH = REPO_ROOT / doc_archive.DEFAULT_LEDGER_ARCHIVE

#: Section count of ``ROADMAP.md`` immediately before the first split was
#: applied, 2026-09-08. A FLOOR for the pair, never an equality - see the module
#: docstring. The pair cannot fall below it, because a split only moves text.
PRE_SPLIT_ROADMAP_SECTIONS = 84

#: Archivable section count at that same moment. Also a floor.
PRE_SPLIT_ROADMAP_ARCHIVABLE = 65

#: Entry count of ``docs/LEDGER.md`` at that same moment. Also a floor. The file
#: carried 196 ``### LL-`` headings, one of which is the format template above
#: the marker and is never an entry.
PRE_SPLIT_LEDGER_ENTRIES = 195

_ROADMAP_SECTION_RE = re.compile(r"^## ", re.MULTILINE)
_LEDGER_ENTRY_RE = re.compile(r"^### LL-", re.MULTILINE)


def read_roadmap() -> str:
    """Return the real ``ROADMAP.md`` text, read-only."""
    return ROADMAP_PATH.read_text(encoding="utf-8")


def read_ledger() -> str:
    """Return the real ``docs/LEDGER.md`` text, read-only."""
    return LEDGER_PATH.read_text(encoding="utf-8")


def _body_after_header(text: str, pattern: re.Pattern[str], path: Path) -> str:
    """Return an archive's entries - everything from its first heading on.

    The archive's own generated header is dropped, because it is this module's
    output rather than moved text, and re-attaching it to the live document
    would put a second document title in the middle of the corpus.
    """
    match = pattern.search(text)
    assert match is not None, f"{path} carries no archived sections to re-attach"
    return text[match.start() :]


def read_roadmap_corpus() -> str:
    """Return the live roadmap with the archived sections re-attached.

    A CORPUS of real sections, not a valid document - the archived items are all
    at the end rather than in their original positions. See the module
    docstring. It is invariant under the split, which is what makes every
    property measured against it re-runnable.
    """
    live = read_roadmap()
    archive = ROADMAP_ARCHIVE_PATH.read_text(encoding="utf-8")
    return live + _body_after_header(archive, _ROADMAP_SECTION_RE, ROADMAP_ARCHIVE_PATH)


def read_ledger_corpus() -> str:
    """Return the live ledger with the archived tail re-attached.

    Unlike the roadmap corpus this IS the pre-split document byte for byte: the
    ledger split is a contiguous tail cut, so re-appending the archived entries
    in order reconstructs exactly what was there before.
    """
    live = read_ledger()
    archive = LEDGER_ARCHIVE_PATH.read_text(encoding="utf-8")
    return live + _body_after_header(archive, _LEDGER_ENTRY_RE, LEDGER_ARCHIVE_PATH)


def ledger_entry_number(heading: str) -> int:
    """Return the numeric part of a ``### LL-0123 - ...`` entry heading."""
    match = re.match(r"^### LL-(\d+)", heading)
    assert match is not None, heading
    return int(match.group(1))


TOY = (
    "# Title\n"
    "\n"
    "Preamble prose.\n"
    "\n"
    "## 1. First thing - CLOSED 2026-01-01\n"
    "\n"
    "Body one.\n"
    "\n"
    "### A sub-heading that must NOT split\n"
    "\n"
    "More body one.\n"
    "\n"
    "## 2. Second thing - OPEN\n"
    "\n"
    "Body two.\n"
)


class TestSplitSectionsRoundTrips:
    """``split_sections`` must be lossless - everything else rests on this."""

    def test_toy_fixture_round_trips_exactly(self):
        preamble, sections = doc_archive.split_sections(TOY)
        assert preamble + "".join(s.text for s in sections) == TOY

    def test_toy_fixture_splits_on_level_two_only(self):
        preamble, sections = doc_archive.split_sections(TOY)
        assert preamble == "# Title\n\nPreamble prose.\n\n"
        assert [s.heading for s in sections] == [
            "## 1. First thing - CLOSED 2026-01-01",
            "## 2. Second thing - OPEN",
        ]
        assert "### A sub-heading that must NOT split" in sections[0].text

    def test_level_three_split_is_selectable(self):
        _, sections = doc_archive.split_sections(TOY, level=3)
        assert [s.heading for s in sections] == ["### A sub-heading that must NOT split"]

    def test_text_with_no_headings_is_all_preamble(self):
        preamble, sections = doc_archive.split_sections("just prose\n")
        assert preamble == "just prose\n"
        assert sections == []

    def test_real_roadmap_round_trips_exactly(self):
        text = read_roadmap()
        preamble, sections = doc_archive.split_sections(text)
        assert preamble + "".join(s.text for s in sections) == text

    def test_real_roadmap_offsets_address_the_same_bytes(self):
        text = read_roadmap()
        _, sections = doc_archive.split_sections(text)
        assert sections, "the real roadmap must contain level-2 sections"
        for section in sections:
            assert text[section.start : section.end] == section.text
            assert section.text.startswith(section.heading + "\n")

    def test_real_roadmap_section_count_matches_a_direct_line_scan(self):
        # The equality is the real assertion and holds for both the live file
        # and the pair; the floor is only on the pair, which a split cannot
        # shrink. Asserting a floor on the live file would fail the day the
        # split runs, which is the defect this rewrite exists to remove.
        for text in (read_roadmap(), read_roadmap_corpus()):
            direct = sum(1 for line in text.split("\n") if line.startswith("## "))
            _, sections = doc_archive.split_sections(text)
            assert len(sections) == direct
        _, corpus_sections = doc_archive.split_sections(read_roadmap_corpus())
        assert len(corpus_sections) >= PRE_SPLIT_ROADMAP_SECTIONS


class TestIsArchivable:
    """Classification, pinned against the real ambiguous headings."""

    def test_plain_closed_and_refuted_headings_are_archivable(self):
        assert doc_archive.is_archivable("## 0. Redactor persona leak - CLOSED 2026-08-09")
        assert doc_archive.is_archivable(
            "## 14. CLOSED 2026-09-01 - the premise is REFUTED, the two bows are two TYPES"
        )

    def test_real_heading_whose_title_contains_the_word_open(self):
        # "fails OPEN" is prose in the TITLE, not a status. The status is read
        # from the outcome segment after the last " - ", where only CLOSED appears.
        heading = (
            "## OPS-15. `precommit_gate._block` fails OPEN when stderr is unusable"
            " - CLOSED 2026-08-30"
        )
        assert doc_archive.is_archivable(heading)

    def test_real_heading_that_closes_itself_and_names_an_open_successor(self):
        heading = (
            "## 4c. Archive the log and the market cache on every session"
            " - CLOSED 2026-08-25b, successor 4d OPEN"
        )
        assert doc_archive.is_archivable(heading)

    def test_open_status_before_a_refuted_premise_is_not_archivable(self):
        # The both-keywords shape in the other direction: the item's own status
        # leads the outcome segment, so the item stays in the roadmap.
        heading = "## 99. Some question - OPEN, its own premise was REFUTED 2026-01-01"
        assert not doc_archive.is_archivable(heading)

    def test_refuted_status_before_an_open_successor_is_archivable(self):
        heading = "## 98. Some question - REFUTED 2026-01-01, successor 98b OPEN"
        assert doc_archive.is_archivable(heading)

    def test_open_ish_headings_from_the_real_file_are_not_archivable(self):
        for heading in (
            "## 5. Sorcerer single-weapon question - OPEN, needs the client",
            "## 4b. Ammo-family and talent measurement - READY, cheap, needs the client",
            "## 1. Raid recon pass - PARTLY DONE, remainder is BLOCKED on a real raid",
            "## 7a. The log carries what the save's window does not - MEASURED 2026-08-11",
            "## OPS-57. Both continuity documents will outgrow their budgets"
            " within days, and raising the numbers is not the fix - OPEN",
        ):
            assert not doc_archive.is_archivable(heading), heading

    def test_the_two_trailing_non_item_sections_are_never_archivable(self):
        assert not doc_archive.is_archivable("## Ordering note")
        assert not doc_archive.is_archivable("## Deliberately not on this list")

    def test_the_generated_index_heading_is_never_archivable(self):
        # Otherwise a second run would archive the index the first run created.
        assert not doc_archive.is_archivable(doc_archive.INDEX_HEADING)

    def test_real_file_archivable_count(self):
        text = read_roadmap_corpus()
        _, sections = doc_archive.split_sections(text)
        archivable = [s for s in sections if doc_archive.is_archivable(s.heading)]
        kept = [s for s in sections if not doc_archive.is_archivable(s.heading)]
        assert len(archivable) >= PRE_SPLIT_ROADMAP_ARCHIVABLE
        # And it is not simply "every section": the survivors are a real
        # remainder. Named rather than counted, because the count of open items
        # changes every time one is closed but these three are never items and
        # can never move.
        kept_headings = {doc_archive._strip_hashes(s.heading) for s in kept}
        for heading in doc_archive.NON_ITEM_HEADINGS:
            assert heading in kept_headings, heading

    def test_the_outcome_segment_rule_agrees_with_a_whole_line_scan(self):
        """The classifier's restriction to the outcome segment costs nothing.

        This is the number-free replacement for asserting "65 headings match".
        The module docstring claims the outcome segment carries a closure word
        for exactly the same headings that carry one anywhere in the line - so
        the segment rule defends against the ambiguous shapes without changing
        any real answer. Measured here as a set equality over real headings,
        which stays true as items are added and never needs a number edited.
        """
        _, sections = doc_archive.split_sections(read_roadmap_corpus())
        by_segment = [s.heading for s in sections if doc_archive.is_archivable(s.heading)]
        by_whole_line = [
            s.heading
            for s in sections
            if doc_archive._strip_hashes(s.heading) not in doc_archive.NON_ITEM_HEADINGS
            and any(word in s.heading for word in doc_archive.CLOSED_WORDS)
        ]
        assert by_segment == by_whole_line
        assert by_segment, "the corpus must contain closed items"

    def test_every_archivable_real_heading_carries_a_closure_word(self):
        text = read_roadmap_corpus()
        _, sections = doc_archive.split_sections(text)
        for section in sections:
            if doc_archive.is_archivable(section.heading):
                assert "CLOSED" in section.heading or "REFUTED" in section.heading


class TestExtractItemId:
    """The stub index keys on this, so collisions are a real failure."""

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("## 0. Redactor persona leak - CLOSED 2026-08-09", "0"),
            ("## 1b. Specialist lane build-out - CLOSED 2026-08-09", "1b"),
            ("## 2. GVAS `.sav` reader - DECODED 2026-08-09, fixture split out to 2b", "2"),
            ("## OPS-15. `precommit_gate._block` fails OPEN - CLOSED 2026-08-30", "OPS-15"),
            (
                "## OPS-33 follow-up. A subagent SessionStart consumed the inbox"
                " backlog - CLOSED 2026-09-07",
                "OPS-33 follow-up",
            ),
            ("## 14. CLOSED 2026-09-01 - the premise is REFUTED", "14"),
        ],
    )
    def test_ids_from_real_heading_shapes(self, heading, expected):
        assert doc_archive.extract_item_id(heading) == expected

    def test_non_item_headings_have_no_id(self):
        assert doc_archive.extract_item_id("## Ordering note") is None
        assert doc_archive.extract_item_id("## Deliberately not on this list") is None

    def test_real_archivable_ids_are_unique(self):
        text = read_roadmap_corpus()
        _, sections = doc_archive.split_sections(text)
        ids = [
            doc_archive.extract_item_id(s.heading)
            for s in sections
            if doc_archive.is_archivable(s.heading)
        ]
        assert None not in ids
        assert len(set(ids)) == len(ids), "two archived sections would share an index key"
        assert "OPS-33" in ids
        assert "OPS-33 follow-up" in ids


class TestAnchorDerivation:
    """GitHub-style anchors, tested against real punctuation from the file."""

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            (
                "## 0. Redactor persona leak - CLOSED 2026-08-09",
                "0-redactor-persona-leak---closed-2026-08-09",
            ),
            (
                "## 2. GVAS `.sav` reader - DECODED 2026-08-09",
                "2-gvas-sav-reader---decoded-2026-08-09",
            ),
            (
                "## 11. Bind the remaining affix ids - TWO LEFT (101, 214)",
                "11-bind-the-remaining-affix-ids---two-left-101-214",
            ),
            (
                "## 13. Page-2 talent NODE TEXT - CLOSED 2026-08-30e,"
                " and its OWN premise was false",
                "13-page-2-talent-node-text---closed-2026-08-30e-and-its-own-premise-was-false",
            ),
        ],
    )
    def test_anchor_for_real_headings(self, heading, expected):
        assert doc_archive.anchor_for(heading) == expected

    def test_real_archivable_anchors_are_unique(self):
        text = read_roadmap_corpus()
        _, sections = doc_archive.split_sections(text)
        anchors = [
            doc_archive.anchor_for(s.heading)
            for s in sections
            if doc_archive.is_archivable(s.heading)
        ]
        assert len(set(anchors)) == len(anchors)


class TestStubLine:
    """One line per archived item, and it must actually point somewhere."""

    def test_stub_carries_id_outcome_and_anchor_link(self):
        _, sections = doc_archive.split_sections(TOY)
        line = doc_archive.stub_line(sections[0], "docs/ROADMAP_ARCHIVE.md")
        assert "\n" not in line
        assert "1" in line
        assert "CLOSED 2026-01-01" in line
        assert "(docs/ROADMAP_ARCHIVE.md#1-first-thing---closed-2026-01-01)" in line

    def test_stub_for_a_real_section_links_to_its_own_anchor(self):
        text = read_roadmap_corpus()
        _, sections = doc_archive.split_sections(text)
        section = next(s for s in sections if s.heading.startswith("## OPS-33 follow-up."))
        line = doc_archive.stub_line(section, "docs/ROADMAP_ARCHIVE.md")
        assert "OPS-33 follow-up" in line
        assert "#" + doc_archive.anchor_for(section.heading) + ")" in line


class TestPlanRoadmapSplit:
    """Conservation, and an index that reaches every archived item.

    The real-text subject here is the corpus rather than the live file, and not
    only for stable counts: once the split has been applied, the live roadmap
    can legitimately hold NO closed items at all, and every test that says "the
    real roadmap must have something to archive" would then fail on a document
    that is perfectly correct. The corpus always has something to archive.
    """

    def test_toy_split_moves_only_the_closed_section(self):
        plan = doc_archive.plan_roadmap_split(TOY, "docs/ROADMAP_ARCHIVE.md")
        assert [s.heading for s in plan.archived] == ["## 1. First thing - CLOSED 2026-01-01"]
        assert [s.heading for s in plan.kept] == ["## 2. Second thing - OPEN"]

    def test_real_split_conserves_every_archived_byte(self):
        text = read_roadmap_corpus()
        plan = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        moved = "".join(s.text for s in plan.archived)
        assert moved, "the corpus must have something to archive"
        # The archive is its header followed by the moved sections, verbatim.
        assert plan.archive_text.endswith(moved)
        assert plan.archive_text[: -len(moved)] == plan.archive_header
        # Nothing was lost between the two outputs.
        preamble, sections = doc_archive.split_sections(text)
        assert preamble + "".join(s.text for s in sections) == text
        assert len(plan.kept) + len(plan.archived) == len(sections)

    def test_real_split_keeps_the_preamble_and_survivors_verbatim(self):
        text = read_roadmap_corpus()
        preamble, _ = doc_archive.split_sections(text)
        plan = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        assert plan.roadmap_text.startswith(preamble)
        for section in plan.kept:
            assert section.text in plan.roadmap_text
        expected_head = preamble + "".join(s.text for s in plan.kept)
        assert plan.roadmap_text.startswith(expected_head)

    def test_no_archived_section_body_survives_in_the_new_roadmap(self):
        text = read_roadmap_corpus()
        plan = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        for section in plan.archived:
            assert section.text not in plan.roadmap_text

    def test_every_archived_section_is_reachable_from_the_new_roadmap(self):
        # OPS-57 criterion 6: the entry point must actually resolve. The index
        # this run generates is the LAST one in the output, and it must carry a
        # link for every section this run moved and not one link more. Counting
        # links across the whole document instead would fold in the stubs an
        # earlier split already wrote, which is a different fact.
        text = read_roadmap_corpus()
        plan = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        assert doc_archive.INDEX_HEADING in plan.roadmap_text
        index = plan.roadmap_text.rsplit(doc_archive.INDEX_HEADING, 1)[1]
        for section in plan.archived:
            anchor = doc_archive.anchor_for(section.heading)
            assert "docs/ROADMAP_ARCHIVE.md#" + anchor + ")" in index
        assert index.count("docs/ROADMAP_ARCHIVE.md#") == len(plan.archived)

    def test_the_new_roadmap_is_smaller_than_the_old_one(self):
        text = read_roadmap_corpus()
        plan = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        assert len(plan.roadmap_text) < len(text)

    def test_running_the_split_again_archives_nothing(self):
        # Deterministic and re-runnable: the index section the first pass adds
        # must not itself look archivable to the second pass.
        text = read_roadmap_corpus()
        first = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        second = doc_archive.plan_roadmap_split(first.roadmap_text, "docs/ROADMAP_ARCHIVE.md")
        assert second.archived == []

    def test_the_split_is_deterministic(self):
        text = read_roadmap_corpus()
        a = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        b = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        assert a.roadmap_text == b.roadmap_text
        assert a.archive_text == b.archive_text

    def test_a_dropped_section_is_caught_by_the_conservation_check(self, monkeypatch):
        # Prove the internal guard is not decoration: make the archive builder
        # lose one section and confirm the function refuses rather than returns.
        real = doc_archive._archive_body

        def lossy(sections):
            return real(sections[1:])

        monkeypatch.setattr(doc_archive, "_archive_body", lossy)
        with pytest.raises(doc_archive.ConservationError):
            doc_archive.plan_roadmap_split(read_roadmap_corpus(), "docs/ROADMAP_ARCHIVE.md")


class TestASecondSplitDoesNotDestroyTheFirstOne:
    """Re-running the splitter is the expected case, so it must be safe.

    The splitter exists because a size budget fired, and budgets fire again, so
    the second run is not hypothetical. Before ``existing_archive`` the second
    run planned an archive containing ONLY the sections that run moved, with a
    header reading "Sections in this archive: 1" - and applying that plan the
    way the first one was applied, by overwriting the archive file, would have
    silently DELETED the 65 sections the first run put there. That is precisely
    the loss ``OPS-57`` criterion 4 forbids, produced by the tool built to
    prevent it.

    Passing the current archive back in makes the plan additive: the archive
    keeps everything it already held, and the roadmap ends up with ONE index
    covering old and new items rather than a second index section per run.
    """

    def _first_and_second(self):
        text = read_roadmap_corpus()
        first = doc_archive.plan_roadmap_split(text, "docs/ROADMAP_ARCHIVE.md")
        second = doc_archive.plan_roadmap_split(
            first.roadmap_text + "\n## 500. A later item - CLOSED 2026-12-31\n\nBody.\n",
            "docs/ROADMAP_ARCHIVE.md",
            existing_archive=first.archive_text,
        )
        return first, second

    def test_the_second_archive_still_holds_every_earlier_section(self):
        first, second = self._first_and_second()
        assert first.archived, "the corpus must have something to archive"
        for section in first.archived:
            assert section.text in second.archive_text, section.heading
        assert second.archived, "the second run must have moved the later item"
        for section in second.archived:
            assert section.text in second.archive_text, section.heading

    def test_the_second_index_covers_old_and_new_and_is_the_only_one(self):
        first, second = self._first_and_second()
        assert second.roadmap_text.count(doc_archive.INDEX_HEADING) == 1
        index = second.roadmap_text.split(doc_archive.INDEX_HEADING, 1)[1]
        for section in list(first.archived) + list(second.archived):
            anchor = doc_archive.anchor_for(section.heading)
            assert "docs/ROADMAP_ARCHIVE.md#" + anchor + ")" in index
        assert index.count("docs/ROADMAP_ARCHIVE.md#") == len(first.archived) + len(
            second.archived
        )

    def test_dropping_an_earlier_section_is_caught_by_the_conservation_check(
        self, monkeypatch
    ):
        first = doc_archive.plan_roadmap_split(
            read_roadmap_corpus(), "docs/ROADMAP_ARCHIVE.md"
        )
        real = doc_archive._archive_body

        def lossy(sections):
            return real(sections[1:])

        monkeypatch.setattr(doc_archive, "_archive_body", lossy)
        with pytest.raises(doc_archive.ConservationError):
            doc_archive.plan_roadmap_split(
                first.roadmap_text + "\n## 500. A later item - CLOSED 2026-12-31\n\nBody.\n",
                "docs/ROADMAP_ARCHIVE.md",
                existing_archive=first.archive_text,
            )

    def test_the_second_ledger_archive_prepends_and_keeps_the_older_entries(self):
        text = read_ledger_corpus()
        first = doc_archive.plan_ledger_split(text, keep_entries=40)
        second = doc_archive.plan_ledger_split(
            first.ledger_text, keep_entries=20, existing_archive=first.archive_text
        )
        for entry in first.archived:
            assert entry.text in second.archive_text, entry.heading
        # Newest-first is the ledger's whole ordering contract, and the entries
        # this run moves are NEWER than everything already archived.
        body = second.archive_text[len(second.archive_header) :]
        assert body.endswith("".join(e.text for e in first.archived))
        assert body.startswith("".join(e.text for e in second.archived))
        numbers = [ledger_entry_number(e.heading) for e in second.archived] + [
            ledger_entry_number(e.heading) for e in first.archived
        ]
        assert numbers == sorted(numbers, reverse=True)


class TestPlanLedgerSplit:
    """Append-only means a tail cut, verbatim, and a head nobody touches."""

    def test_missing_marker_is_refused(self):
        with pytest.raises(doc_archive.LedgerMarkerMissing):
            doc_archive.plan_ledger_split("# Ledger\n\n### LL-0001 - x\n", keep_entries=1)

    def test_real_ledger_head_is_byte_identical_through_the_marker(self):
        text = read_ledger_corpus()
        plan = doc_archive.plan_ledger_split(text, keep_entries=40)
        cut = text.index(doc_archive.LEDGER_MARKER) + len(doc_archive.LEDGER_MARKER)
        assert plan.ledger_text[:cut] == text[:cut]

    def test_real_ledger_split_conserves_every_byte(self):
        text = read_ledger_corpus()
        plan = doc_archive.plan_ledger_split(text, keep_entries=40)
        moved = "".join(e.text for e in plan.archived)
        assert moved
        assert plan.ledger_text + moved == text
        assert plan.archive_text.endswith(moved)

    def test_real_ledger_keeps_the_newest_and_archives_the_oldest(self):
        """Pinned as an ORDER, not as a pair of entry ids.

        The old form named ``LL-0195``, ``LL-0155`` and a total of 195, all
        three of which the next appended entry or the next split invalidates.
        What actually has to be true is that the corpus is one strictly
        descending run of entry numbers, that the cut falls exactly at
        ``keep_entries``, and that the archive ends at the oldest entry the
        ledger has ever had - ``LL-0001``, which cannot change.
        """
        text = read_ledger_corpus()
        plan = doc_archive.plan_ledger_split(text, keep_entries=40)
        assert len(plan.kept) == 40
        assert len(plan.kept) + len(plan.archived) >= PRE_SPLIT_LEDGER_ENTRIES
        # The cut is a cut and not a filter: kept then archived is one unbroken
        # descending run from the newest entry down to LL-0001. That rules out
        # a dropped entry anywhere, at the cut or inside either half, and it
        # carries no literal count - appending a new entry just raises the top.
        numbers = [ledger_entry_number(e.heading) for e in plan.kept + plan.archived]
        assert numbers == list(range(numbers[0], 0, -1))
        assert ledger_entry_number(plan.archived[-1].heading) == 1

    def test_the_template_entry_above_the_marker_stays_in_the_head(self):
        text = read_ledger_corpus()
        plan = doc_archive.plan_ledger_split(text, keep_entries=40)
        assert "### LL-0000 - YYYY-MM-DD" in plan.ledger_text
        assert "### LL-0000 - YYYY-MM-DD" not in plan.archive_text

    def test_keeping_everything_archives_nothing(self):
        text = read_ledger_corpus()
        plan = doc_archive.plan_ledger_split(text, keep_entries=10_000)
        assert plan.archived == []
        assert plan.ledger_text == text

    def test_negative_keep_is_refused(self):
        with pytest.raises(ValueError):
            doc_archive.plan_ledger_split(read_ledger_corpus(), keep_entries=-1)

    def test_a_reordered_tail_is_caught_by_the_conservation_check(self, monkeypatch):
        real = doc_archive._archive_body

        def reordered(entries):
            return real(list(reversed(entries)))

        monkeypatch.setattr(doc_archive, "_archive_body", reordered)
        with pytest.raises(doc_archive.ConservationError):
            doc_archive.plan_ledger_split(read_ledger_corpus(), keep_entries=40)


def _docs_tree_snapshot() -> dict[str, tuple[str, int]]:
    """Return a content hash and mtime for every tracked-shaped file under docs/.

    Keyed by repo-relative path, so a file that APPEARS is a new key and a file
    that changes is a changed value. ``ROADMAP.md`` is included because it lives
    at the repo root and is the other document the splitter reads.
    """
    paths = [*sorted(REPO_ROOT.joinpath("docs").rglob("*.md")), ROADMAP_PATH]
    snapshot: dict[str, tuple[str, int]] = {}
    for path in paths:
        data = path.read_bytes()
        key = path.relative_to(REPO_ROOT).as_posix()
        snapshot[key] = (hashlib.sha256(data).hexdigest(), path.stat().st_mtime_ns)
    return snapshot


class TestMainIsADryRun:
    """``main`` reports; it must not write to either document."""

    def test_main_reports_and_changes_nothing_on_disk(self, capsys):
        before = (
            ROADMAP_PATH.read_bytes(),
            LEDGER_PATH.read_bytes(),
            ROADMAP_PATH.stat().st_mtime_ns,
            LEDGER_PATH.stat().st_mtime_ns,
        )
        assert doc_archive.main([]) == 0
        after = (
            ROADMAP_PATH.read_bytes(),
            LEDGER_PATH.read_bytes(),
            ROADMAP_PATH.stat().st_mtime_ns,
            LEDGER_PATH.stat().st_mtime_ns,
        )
        assert before == after
        out = capsys.readouterr().out
        assert "ROADMAP.md" in out
        assert "docs/LEDGER.md" in out
        assert "DRY RUN" in out

    def test_main_creates_or_modifies_no_document(self, capsys):
        """The dry-run property, re-expressed after the split was applied.

        This test used to assert that ``docs/ROADMAP_ARCHIVE.md`` and
        ``docs/LEDGER_ARCHIVE.md`` do not exist. That was only ever a proxy for
        "main writes nothing", and it stopped being one the moment the split was
        legitimately applied and the two archives appeared - at which point the
        test failed while ``main`` was still behaving perfectly. Worse, it was a
        proxy that could never come back: no correct behaviour would delete
        those files again.

        The property that actually matters is that running ``main`` leaves the
        document tree byte-identical, whether or not the archives exist. A
        snapshot over every Markdown file under ``docs/`` plus ``ROADMAP.md``
        catches a CREATED file as a new key and a rewritten one as a changed
        hash, so it pins both halves of what the old assertion was reaching for.
        """
        before = _docs_tree_snapshot()
        assert doc_archive.main([]) == 0
        after = _docs_tree_snapshot()
        assert after == before
        capsys.readouterr()


class TestAsciiHygiene:
    """Repo rule: every authored file is 7-bit ASCII."""

    def test_both_files_are_ascii(self):
        for path in (
            REPO_ROOT / "tools/doc_archive.py",
            REPO_ROOT / "tests/test_doc_archive.py",
        ):
            data = path.read_bytes()
            assert all(byte < 128 for byte in data), path


class TestTheSplitterAndTheGuardNameTheSAMEFile:
    """The two modules must agree on the archive's PATH - ``OPS-57``.

    **This is a real defect that shipped and was caught at the merge, not a
    hypothetical.** The splitter defaulted to ``docs/ROADMAP-ARCHIVE.md`` and
    the guard to ``docs/ROADMAP_ARCHIVE.md``. Both modules were internally
    consistent and both were green, because each slice used its OWN constant
    throughout and the adjudication that ran one against the other passed the
    path in EXPLICITLY - so the two defaults never met.

    The failure it would have produced is the one this whole item exists to
    prevent. The splitter writes the hyphen file, the guard looks for the
    underscore file, finds nothing, and reports DID NOT RUN - which reads as
    "no problems" to anyone skimming, while every archived item is in fact
    unreachable through the name the guard checks.

    Agreement between two independently written modules is a hypothesis. This
    pins it.
    """

    def test_the_roadmap_archive_path_is_one_string_in_both_modules(self) -> None:
        from tools import archive_link_guard

        assert doc_archive.DEFAULT_ROADMAP_ARCHIVE == archive_link_guard.ARCHIVE_REL_PATH

    def test_both_archive_paths_follow_the_repo_underscore_convention(self) -> None:
        """``docs/`` uses ``OBSERVED_IDS.md``, ``REPLY_PATHS.md``, ``CLASS_RESEARCH.md``.

        Not a style preference: the guard resolves the archive by NAME, so a
        name chosen by one module and not the other is the defect above.
        """
        for path in (
            doc_archive.DEFAULT_ROADMAP_ARCHIVE,
            doc_archive.DEFAULT_LEDGER_ARCHIVE,
        ):
            stem = path.rsplit("/", 1)[-1].removesuffix(".md")
            assert "-" not in stem, f"{path} uses a hyphen where docs/ uses an underscore"


class TestTheDryRunReportsTheSAFEPlan:
    """`main()` must report the plan a reader would actually apply.

    **The hazard this closes, measured 2026-09-08.** The planners learned to
    carry an existing archive forward, but `existing_archive` defaulted to
    empty - "old behaviour" - and `main()` passed nothing. So the dry run
    reported an archive of 15,502 characters while `docs/ROADMAP_ARCHIVE.md`
    held 475,473, and the plan it described would have replaced 65 carried
    sections with 1.

    That default is backwards for this tool specifically. `ROADMAP.md` and
    `tools/doc_size_budget.py` both instruct the next session to RE-RUN the
    split when a budget fires, so re-running is the documented path and the
    destructive plan was what it printed. A safe default matters more than a
    compatible one when the unsafe one deletes 475 KB of history.

    The report is the only thing anyone reads before deciding, so a report
    describing a plan nobody should apply is worse than no report.
    """

    def test_the_report_counts_the_sections_already_in_the_archive(self, capsys):
        """The live archive holds 65 sections; a report showing ~1 is the bug."""
        archive = REPO_ROOT / "docs" / "ROADMAP_ARCHIVE.md"
        if not archive.exists():
            return
        prior = archive.read_text(encoding="utf-8").count("\n## ")
        assert prior > 1, "control: the live archive must hold sections to carry"
        doc_archive.main([])
        out = capsys.readouterr().out
        line = next(
            row for row in out.splitlines() if doc_archive.DEFAULT_ROADMAP_ARCHIVE in row
        )
        reported = int(line.rsplit(maxsplit=1)[-1])
        assert reported > len(archive.read_text(encoding="utf-8")) * 0.9, (
            f"the dry run reports an archive of {reported} characters while the real "
            f"one is {archive.stat().st_size}; it is describing a plan that DROPS "
            f"the {prior} sections already archived"
        )

    def test_planning_twice_never_shrinks_the_archive(self):
        """The property behind it, on a fixture, independent of today's files."""
        first = doc_archive.plan_roadmap_split(
            "# r\n\n## 1. a - CLOSED 2026-01-01\n\nbody\n\n## 2. b - OPEN\n\nbody\n",
            doc_archive.DEFAULT_ROADMAP_ARCHIVE,
        )
        second = doc_archive.plan_roadmap_split(
            first.roadmap_text + "\n## 3. c - CLOSED 2026-01-02\n\nbody\n",
            doc_archive.DEFAULT_ROADMAP_ARCHIVE,
            existing_archive=first.archive_text,
        )
        assert "## 1. a - CLOSED 2026-01-01" in second.archive_text
        assert "## 3. c - CLOSED 2026-01-02" in second.archive_text
