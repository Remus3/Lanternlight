"""`OPS-` ids must name one item each, and the next free one must be askable.

`OPS-12`. The `OPS-` namespace had no allocator. An id was chosen by a human
reading `ROADMAP.md`, and on 2026-08-26 that produced two collisions at once:
`OPS-7` and `OPS-8` each name two unrelated items, because numbering resumed
from the highest id visible among the OPEN items rather than the highest ever
allocated. `docs/LEDGER.md` already knew about `LL-0039` and `LL-0040`; nothing
asked it.

Two things are pinned here.

**The spent set is derived by walking the documents at run time.** A
checked-in list of spent ids is exactly the filed count this repository has
been burned by - it would go stale the first time an item was added without
touching it. `ops/ops_ids.py` reads `ROADMAP.md`, `docs/LEDGER.md` and the two
archives `OPS-57` split them into, and counts what it finds.

**Every document reader in that module reads all four.** The repair for the
`OPS-57` split was first applied to two of the module's five readers, and the
suite stayed green while `over_allocated()` reported a CLEAN repository -
because both known collisions are closed items whose evidence had moved into
the archives. So the readers are enumerated by signature and held to the rule
as a group rather than one at a time; a sixth reader added without archive
support turns that red without anyone remembering to write a test for it.

**The known collisions are asserted as an exact set.** That is a record of a
measured state, not a list of spent ids: it fails if a THIRD collision appears,
and it fails just as loudly if `OPS-7` or `OPS-8` is ever resolved, so the
exemption cannot outlive the thing it excuses. It is the same shape as
`lane_state.stale_claims()`.
"""

import inspect
import sys
from pathlib import Path
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import ops_ids  # noqa: E402

#: The two collisions measured on 2026-08-26b, and the ONLY two tolerated.
KNOWN_COLLISIONS = {7, 8}


class TestTheScanActuallyReadsTheDocuments:
    """A scanner that finds nothing agrees with a clean repository forever."""

    def test_ids_that_are_definitely_present_are_found(self):
        spent = ops_ids.spent_ids()
        for known in (7, 8, 12):
            assert known in spent, f"OPS-{known} is in the documents and was not found"

    def test_an_id_that_is_definitely_absent_is_not_found(self):
        # The negative half. Without the positive control above this would
        # pass on a regex that matches nothing at all.
        assert 9999 not in ops_ids.spent_ids()

    def test_the_roadmap_heading_scan_finds_the_real_headings(self):
        ids = {item.item_id for item in ops_ids.roadmap_items()}
        assert {7, 8, 12} <= ids, ids

    def test_a_closed_heading_is_distinguished_from_an_open_one(self, tmp_path):
        """On a fixture, deliberately.

        The first version of this asserted the real statuses of OPS-7, OPS-8
        and OPS-12, and went red the moment OPS-12 was closed - which is the
        one thing a status is supposed to do. A test that has to be edited
        every time the documents change correctly is not a guard, it is a
        chore, and it teaches people to edit tests to go green.
        """
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text(
            "## OPS-1. finished with - CLOSED 2026-01-01\n\n## OPS-2. still going - OPEN\n",
            encoding="ascii",
        )
        by_id = {item.item_id: item for item in ops_ids.roadmap_items(roadmap=roadmap)}
        assert by_id[1].closed is True
        assert by_id[2].closed is False

    def test_real_headings_are_found_and_a_closed_one_is_recognised(self):
        """Keeps the real-document path exercised, without asserting workload.

        This is the SECOND time a test here encoded a transient project state.
        The first named OPS-12's status and went red when OPS-12 was closed.
        Its replacement then demanded that both an OPEN and a CLOSED heading
        exist in the real roadmap - and went red the moment OPS-7 was closed,
        because that left no open `OPS-` item at all. Whether any ops item
        happens to be open is a fact about the workload, not about the scanner.

        What is worth pinning on real input is narrower: real headings are
        found at all, and CLOSED is recognised in the wild, where headings carry
        trailing dates and backticks that a fixture does not. A closed item does
        not reopen, so this cannot rot the same way. The OPEN half is covered on
        a fixture, which is where a statement about parsing belongs.
        """
        items = ops_ids.roadmap_items()
        assert items, "no OPS- item headings found in the real roadmap at all"
        assert any(item.closed for item in items), (
            "no CLOSED heading was recognised in the real roadmap"
        )

    def test_the_ledger_closure_scan_finds_the_real_closures(self):
        closures = ops_ids.ledger_closures()
        assert "LL-0040" in closures.get(8, []), closures.get(8)
        assert "LL-0066" in closures.get(8, []), closures.get(8)
        assert "LL-0039" in closures.get(7, []), closures.get(7)

    def test_one_ledger_heading_closing_several_ids_credits_all_of_them(self):
        # LL-0042's heading reads "OPS-1, OPS-3 and OPS-5 closed - ...".
        closures = ops_ids.ledger_closures()
        for item_id in (1, 3, 5):
            assert "LL-0042" in closures.get(item_id, []), (
                f"OPS-{item_id} is closed by LL-0042's heading and was missed"
            )


class TestNextFreeId:
    """The allocator that did not exist.

    These are properties, so they do not go stale the moment an item is added -
    which an assertion that the answer is 13 would.
    """

    def test_it_is_above_every_spent_id(self):
        spent = ops_ids.spent_ids()
        assert spent, "nothing was scanned, so this proves nothing"
        assert ops_ids.next_free_id() > max(spent)

    def test_it_is_not_itself_spent(self):
        assert ops_ids.next_free_id() not in ops_ids.spent_ids()

    def test_it_is_derived_from_the_documents_not_from_a_constant(self, tmp_path):
        # Hand it a tree whose highest id is 41 and it must answer 42.
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("## OPS-41. something - OPEN", encoding="ascii")
        ledger.write_text("nothing here", encoding="ascii")
        assert ops_ids.next_free_id(roadmap=roadmap, ledger=ledger) == 42


class TestCollisionDetection:
    def test_the_detector_fires_on_a_reused_id(self, tmp_path):
        """A new OPEN item taking an id the ledger already closed."""
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("## OPS-3. a brand new concern - OPEN", encoding="ascii")
        ledger.write_text(
            "### LL-0001 - 2026-01-01 - OPS-3 closed - the original concern",
            encoding="ascii",
        )
        assert 3 in ops_ids.over_allocated(roadmap=roadmap, ledger=ledger)

    def test_the_detector_fires_when_one_id_is_closed_twice(self, tmp_path):
        """An item is closed once. A second closure means a second item."""
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("nothing", encoding="ascii")
        ledger.write_text(
            "### LL-0002 - 2026-02-02 - OPS-4 closed - the later one\n"
            "### LL-0001 - 2026-01-01 - OPS-4 closed - the earlier one",
            encoding="ascii",
        )
        assert 4 in ops_ids.over_allocated(roadmap=roadmap, ledger=ledger)

    def test_an_item_opened_then_closed_is_ONE_allocation(self, tmp_path):
        """The negative control, and the one that matters most.

        A detector that flagged the normal lifecycle - an item gets a heading,
        then a ledger entry closes it - would be red on every correct item and
        would be switched off within a week.
        """
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("## OPS-5. a normal item - CLOSED 2026-03-03", encoding="ascii")
        ledger.write_text(
            "### LL-0001 - 2026-03-03 - OPS-5 closed - the normal item",
            encoding="ascii",
        )
        assert ops_ids.over_allocated(roadmap=roadmap, ledger=ledger) == {}

    def test_an_open_item_with_no_closure_is_ONE_allocation(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("## OPS-6. still going - OPEN", encoding="ascii")
        ledger.write_text("nothing", encoding="ascii")
        assert ops_ids.over_allocated(roadmap=roadmap, ledger=ledger) == {}

    def test_two_open_headings_for_one_id_are_caught(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text(
            "## OPS-7. one thing - OPEN\n\n## OPS-7. a different thing - OPEN",
            encoding="ascii",
        )
        ledger.write_text("nothing", encoding="ascii")
        assert 7 in ops_ids.over_allocated(roadmap=roadmap, ledger=ledger)


class TestFencedExamplesAreNotAllocations:
    """A document that DOCUMENTS the id format must not allocate ids.

    Found by an independent refuter on 2026-08-27, one edit away from being
    real: this scanner did its own line matching with no fence tracking, so a
    worked example inside a code block reads as a live heading. The refuter
    built the false positive - a fenced `## OPS-13.` example beside a genuine
    `## OPS-13.` heading reports OPS-13 as over-allocated.

    This repository has closed this exact bug before. `OPS-9` / `LL-0038` was
    the heading GUARD and the heading PARSER disagreeing because only one of
    them tracked fences, and its conclusion was that there must be exactly one
    fence scan that every reader shares. This module was a third private
    reader. It now uses `ops.mdscan`, and so does `ops/lane_state.py`.

    The risk is not hypothetical here. `ROADMAP.md` gained prose quoting the
    heading form when OPS-12 was closed, and `docs/LEDGER.md` line 16 carries a
    fenced entry template that already matches the ledger-heading pattern - it
    is inert only because it happens to carry no id and no closure word.
    """

    def test_a_fenced_roadmap_heading_is_not_an_allocation(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text(
            "## OPS-13. the real item - OPEN\n"
            "\n"
            "Allocate an id like this:\n"
            "\n"
            "```\n"
            "## OPS-13. <title> - OPEN\n"
            "```\n",
            encoding="ascii",
        )
        ledger.write_text("nothing", encoding="ascii")
        assert ops_ids.over_allocated(roadmap=roadmap, ledger=ledger) == {}, (
            "a worked example inside a code fence was counted as a second "
            "allocation - the scanner is not fence-aware"
        )

    def test_a_fenced_ledger_heading_is_not_a_closure(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("## OPS-14. the real item - OPEN", encoding="ascii")
        ledger.write_text(
            "The format is:\n"
            "\n"
            "```\n"
            "### LL-0000 - 2026-01-01 - OPS-14 closed - a worked example\n"
            "```\n",
            encoding="ascii",
        )
        assert ops_ids.ledger_closures(ledger=ledger) == {}, (
            "a fenced template was read as a real closure"
        )
        assert ops_ids.over_allocated(roadmap=roadmap, ledger=ledger) == {}

    def test_a_real_heading_after_a_closed_fence_is_still_found(self, tmp_path):
        # The other direction. A fence-aware reader that swallows the rest of
        # the document is worse than one that ignores fences, and it would pass
        # both tests above.
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text(
            "```\n"
            "## OPS-98. an example - OPEN\n"
            "```\n"
            "\n"
            "## OPS-99. a genuine item - OPEN\n",
            encoding="ascii",
        )
        ids = {item.item_id for item in ops_ids.roadmap_items(roadmap=roadmap)}
        assert ids == {99}, ids


class TestAClosureIsAnnouncedNotMentioned:
    """An entry heading that TALKS about an id has not closed it.

    Found by dogfooding, within a minute of the fence fix landing. LL-0069's
    heading reads "... the same bug OPS-9 closed, rebuilt in a module written
    the day after" - a sentence about history, in which "OPS-9 closed" is
    subject and verb. The first pattern accepted any id anywhere in a heading
    that contained the word "closed" anywhere, so it credited that as a second
    closure of OPS-9 and reported a collision that does not exist.

    The real convention is narrower and every genuine closure follows it: the
    summary BEGINS with the id (or a list of them) and then "closed". Requiring
    that keeps `LL-0042`'s three-id heading working and rejects a mention.

    A false positive matters more than a missed one here. This guard's whole
    value is that a red means "you reused an id"; the first time it means "you
    wrote a sentence", somebody adds an exemption and it stops being read.
    """

    def test_an_id_mentioned_in_a_heading_is_not_a_closure(self, tmp_path):
        ledger = tmp_path / "LEDGER.md"
        ledger.write_text(
            "### LL-0069 - 2026-08-27 - a refuter found the bug OPS-9 closed, rebuilt",
            encoding="ascii",
        )
        assert ops_ids.ledger_closures(ledger=ledger) == {}, (
            "a heading discussing an id was read as closing it"
        )

    def test_a_heading_that_announces_a_closure_still_counts(self, tmp_path):
        ledger = tmp_path / "LEDGER.md"
        ledger.write_text(
            "### LL-0038 - 2026-08-12 - OPS-9 closed - the heading guard and parser share a scan",
            encoding="ascii",
        )
        assert ops_ids.ledger_closures(ledger=ledger) == {9: ["LL-0038"]}

    def test_a_heading_announcing_several_closures_still_counts_them_all(self, tmp_path):
        # LL-0042's real shape. The narrowing must not cost this.
        ledger = tmp_path / "LEDGER.md"
        ledger.write_text(
            "### LL-0042 - 2026-08-12 - OPS-1, OPS-3 and OPS-5 closed - the ledger writer",
            encoding="ascii",
        )
        closures = ops_ids.ledger_closures(ledger=ledger)
        assert closures == {1: ["LL-0042"], 3: ["LL-0042"], 5: ["LL-0042"]}


class TestTheRealRepository:
    def test_the_detector_is_not_vacuous_against_the_real_documents(self):
        # The real-document path must be exercised, not just the fixtures.
        # If this ever legitimately becomes empty, the assertion below is the
        # one that must be updated - and it will fail first and say so.
        assert ops_ids.over_allocated(), (
            "the real documents carry two known collisions - finding none means "
            "the scan is not reading them"
        )

    def test_the_only_collisions_are_the_two_known_ones(self):
        """Fails on a THIRD collision, and fails on a RESOLUTION.

        The second direction is the point. An exemption that silently outlives
        the defect it excuses is how a guard rots, so resolving OPS-7 or OPS-8
        must break this test and force the record to be updated.
        """
        found = set(ops_ids.over_allocated())
        assert found == KNOWN_COLLISIONS, (
            "the set of over-allocated OPS- ids changed.\n"
            f"  expected: {sorted(KNOWN_COLLISIONS)}\n"
            f"  found:    {sorted(found)}\n"
            "A NEW id here means one id now names two items - pick "
            "ops_ids.next_free_id() instead. An id MISSING here means a known "
            "collision was resolved, so remove it from KNOWN_COLLISIONS and say "
            "so in the ledger."
        )

    def test_every_known_collision_still_has_the_evidence_behind_it(self):
        # Not just "the id is flagged" - the report must name what collided,
        # or a future reader cannot check the claim.
        report = ops_ids.over_allocated()
        for item_id in KNOWN_COLLISIONS:
            assert report[item_id].allocations >= 2, report[item_id]
            assert report[item_id].sites, f"OPS-{item_id} is flagged with no sites named"


class TestAnIdSpentOnlyInTheArchiveIsStillSpent:
    """`OPS-57` moved closed items out of the two documents this module reads.

    **Measured on the real split before this was written, because the obvious
    reasoning about it is wrong.** The first guess was that archiving a roadmap
    section hides its id. It does not: `spent_ids` matches any `OPS-<n>`
    mention rather than only headings, and every archived section leaves a stub
    line naming its id, so the roadmap half of the split protects itself.

    The half that does not is the LEDGER, which leaves no stub. An id mentioned
    only in ledger entries - the case `spent_ids` documents in its own
    docstring, an id "discussed in a ledger entry but never given a heading" -
    goes out with the archived tail and nothing is left behind.

    Measured against the real documents at the split: `spent_ids` went from 60
    ids to 55. The five lost were `OPS-1`, `OPS-3`, `OPS-4`, `OPS-5` and
    `OPS-9`. `next_free_id` was unaffected, both before and after, because it
    takes the MAXIMUM and the maximum was recent enough to survive - so this is
    a hole in `spent_ids` today and a hole in `next_free_id` on the day the
    highest id ages out of both live documents.

    That matters because `spent_ids` promises the opposite in writing: erring
    wide "can only ever SKIP an id, never reissue one". After a split and
    without the archives, it can reissue.
    """

    def _write(self, tmp_path, roadmap_text, ledger_text, archive_text):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        archive = tmp_path / "ROADMAP_ARCHIVE.md"
        roadmap.write_text(roadmap_text, encoding="ascii")
        ledger.write_text(ledger_text, encoding="ascii")
        archive.write_text(archive_text, encoding="ascii")
        return roadmap, ledger, archive

    def test_an_id_only_in_the_archived_ledger_tail_is_still_spent(self, tmp_path):
        """The measured case: no stub is left behind for a ledger entry."""
        roadmap, ledger, archive = self._write(
            tmp_path,
            "# roadmap\n\n## 1. A live item - OPEN\n\nbody\n",
            "# ledger\n\n### LL-0002 - 2026-01-02 - something unrelated\n",
            "# archive\n\n### LL-0001 - 2026-01-01 - OPS-70 was discussed here\n",
        )
        assert 70 in ops_ids.spent_ids(
            roadmap=roadmap, ledger=ledger, archives=[archive]
        )

    def test_without_the_archive_that_same_id_reads_as_FREE(self, tmp_path):
        """The control that makes the test above non-vacuous.

        Without it, an implementation that ignored `archives` entirely would
        pass the test above if anything else happened to mention the id. This
        pins that the ARCHIVE is what supplies it, and it is the exact defect
        measured on the real documents.
        """
        roadmap, ledger, archive = self._write(
            tmp_path,
            "# roadmap\n\n## 1. A live item - OPEN\n\nbody\n",
            "# ledger\n\n### LL-0002 - 2026-01-02 - something unrelated\n",
            "# archive\n\n### LL-0001 - 2026-01-01 - OPS-70 was discussed here\n",
        )
        without = ops_ids.spent_ids(roadmap=roadmap, ledger=ledger)
        with_archive = ops_ids.spent_ids(
            roadmap=roadmap, ledger=ledger, archives=[archive]
        )
        assert 70 not in without
        assert 70 in with_archive

    def test_the_highest_id_living_only_in_the_archive_is_not_reissued(self, tmp_path):
        """`next_free_id` is the consumer that actually hands out a number."""
        roadmap, ledger, archive = self._write(
            tmp_path,
            "# roadmap\n\n## 1. A live item - OPEN\n\nbody\n",
            "# ledger\n\n### LL-0002 - 2026-01-02 - something unrelated\n",
            "# archive\n\n### LL-0001 - 2026-01-01 - OPS-70 was discussed here\n",
        )
        assert ops_ids.next_free_id(roadmap=roadmap, ledger=ledger) == 1
        assert (
            ops_ids.next_free_id(roadmap=roadmap, ledger=ledger, archives=[archive])
            == 71
        )

    def test_a_missing_archive_is_not_an_error(self, tmp_path):
        """A fresh clone before any split has no archive and must still work."""
        roadmap, ledger, _ = self._write(
            tmp_path, "# roadmap\n\n## OPS-3. A live item - OPEN\n", "# ledger\n", ""
        )
        assert (
            ops_ids.next_free_id(
                roadmap=roadmap, ledger=ledger, archives=[tmp_path / "nope.md"]
            )
            == 4
        )

    def test_the_live_repo_counts_its_archives_by_default(self):
        """A guard that only works when the caller passes the right argument is
        a guard nobody calls correctly at the moment it matters.
        """
        assert ops_ids.default_archive_paths()


class TestEveryDocumentReaderReadsTheArchives:
    """The lesson of the INCOMPLETE fix, pinned so it cannot recur quietly.

    `OPS-57` split the two documents this module reads. The first repair taught
    `spent_ids` and `next_free_id` about the archives and stopped there, so the
    module was left half-migrated: `roadmap_items`, `ledger_closures` and
    `over_allocated` still saw only the live documents. The visible symptom was
    the worst one this repository knows - `over_allocated()` returned `{}` and
    reported a CLEAN repository, because both known collisions had moved into
    the archives. A detector that answers "nothing is wrong" because it stopped
    looking is indistinguishable from a detector that works.

    Four separate per-function tests would each have passed on the day they
    were written and none of them would notice a FIFTH reader added later
    without archive support. So this enumerates the module's public document
    readers instead and holds every one of them to the same rule. Adding a new
    reader that takes a `roadmap=` or `ledger=` path and forgets `archives=`
    turns this red without anyone remembering to write a test for it.
    """

    #: The only place `OPS-70` and `OPS-71` exist in the fixture tree. `OPS-70`
    #: is deliberately a COLLISION - two open headings - so that
    #: `over_allocated` has something to find here too, rather than answering
    #: an empty dict both with and without the archive and looking correct.
    ARCHIVE = (
        "# archive\n"
        "\n"
        "## OPS-70. one archived thing - OPEN\n"
        "\n"
        "## OPS-70. a different archived thing - OPEN\n"
        "\n"
        "### LL-0001 - 2026-01-01 - OPS-71 closed - an archived closure\n"
    )

    #: Named so the enumeration itself has a positive control. A discovery rule
    #: that silently matches nothing would pass every loop below vacuously.
    EXPECTED_READERS: ClassVar[set[str]] = {
        "spent_ids",
        "next_free_id",
        "roadmap_items",
        "ledger_closures",
        "over_allocated",
    }

    def _document_readers(self):
        """Return every public function in the module that takes a document.

        Discovered by signature rather than listed by hand, which is the whole
        point: a hand-maintained list is a filed count, and this repository's
        recorded failure mode is a filed count that reads as authoritative and
        has gone stale.
        """
        readers = {}
        for name, value in vars(ops_ids).items():
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            if value.__module__ != ops_ids.__name__:
                continue
            params = inspect.signature(value).parameters
            if "roadmap" in params or "ledger" in params:
                readers[name] = value
        return readers

    def test_the_enumeration_itself_finds_the_known_readers(self):
        found = set(self._document_readers())
        assert found >= self.EXPECTED_READERS, (
            "the discovery rule missed a reader that is known to exist, so "
            "every check that loops over it proves nothing.\n"
            f"  expected at least: {sorted(self.EXPECTED_READERS)}\n"
            f"  found:             {sorted(found)}"
        )

    def test_every_document_reader_accepts_an_archives_argument(self):
        for name, reader in self._document_readers().items():
            assert "archives" in inspect.signature(reader).parameters, (
                f"ops_ids.{name} reads a document path but has no archives "
                "argument, so it is blind to everything OPS-57 moved out"
            )

    def test_every_document_reader_answers_differently_once_an_archive_is_added(
        self, tmp_path
    ):
        """Signature is not behaviour. An `archives` argument can be ignored.

        Each reader is asked the same question twice against the same tree,
        once with the archive and once without. A reader that answers
        identically is not reading it, whatever its signature says.
        """
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        archive = tmp_path / "ARCHIVE.md"
        roadmap.write_text("# roadmap\n", encoding="ascii")
        ledger.write_text("# ledger\n", encoding="ascii")
        archive.write_text(self.ARCHIVE, encoding="ascii")

        for name, reader in self._document_readers().items():
            params = inspect.signature(reader).parameters
            base = {}
            if "roadmap" in params:
                base["roadmap"] = roadmap
            if "ledger" in params:
                base["ledger"] = ledger
            without = reader(**base, archives=[])
            with_archive = reader(**base, archives=[archive])
            assert with_archive != without, (
                f"ops_ids.{name} gave the same answer with and without an "
                "archive that is the only place OPS-70 and OPS-71 exist, so it "
                "is ignoring the archives argument it accepts"
            )

    def test_roadmap_items_finds_a_heading_that_lives_only_in_the_archive(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        archive = tmp_path / "ARCHIVE.md"
        roadmap.write_text("# roadmap\n", encoding="ascii")
        archive.write_text(self.ARCHIVE, encoding="ascii")
        ids = {
            item.item_id
            for item in ops_ids.roadmap_items(roadmap=roadmap, archives=[archive])
        }
        assert ids == {70}, ids

    def test_ledger_closures_finds_a_closure_that_lives_only_in_the_archive(self, tmp_path):
        ledger = tmp_path / "LEDGER.md"
        archive = tmp_path / "ARCHIVE.md"
        ledger.write_text("# ledger\n", encoding="ascii")
        archive.write_text(self.ARCHIVE, encoding="ascii")
        closures = ops_ids.ledger_closures(ledger=ledger, archives=[archive])
        assert closures == {71: ["LL-0001"]}, closures

    def test_over_allocated_finds_a_collision_that_lives_only_in_the_archive(self, tmp_path):
        """The symptom that started this: a clean report over a dirty tree."""
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        archive = tmp_path / "ARCHIVE.md"
        roadmap.write_text("# roadmap\n", encoding="ascii")
        ledger.write_text("# ledger\n", encoding="ascii")
        archive.write_text(self.ARCHIVE, encoding="ascii")
        report = ops_ids.over_allocated(roadmap=roadmap, ledger=ledger, archives=[archive])
        assert set(report) == {70}, report
        assert report[70].allocations == 2, report[70]


class TestArchivesAreScopedToTheTreeTheCallerNamed:
    """The API footgun, closed by design rather than by documentation.

    `archives=None` used to mean "the real repository's archives", whatever the
    caller had said about the other two documents. So a test that handed the
    module a `tmp_path` roadmap and ledger and omitted `archives` silently
    measured a THIRD tree: two fixture files plus the live archives. It is the
    worst kind of default, because the wrong answer looks like a correct one -
    the module was asked about a fixture and answered about the repository.

    The rule now: `archives=None` follows the documents. Name a roadmap or a
    ledger explicitly and the archives default to NONE, because a caller who
    scoped the scan to their own tree meant their own tree. Pass an explicit
    `archives=` and it is honoured exactly. Pass nothing at all - what every
    real caller does - and all four repository documents are read, unchanged.
    """

    def test_an_explicit_document_pair_does_not_drag_in_the_real_archives(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        roadmap.write_text("# roadmap\n", encoding="ascii")
        ledger.write_text("# ledger\n", encoding="ascii")
        assert ops_ids.spent_ids(roadmap=roadmap, ledger=ledger) == set()
        assert ops_ids.next_free_id(roadmap=roadmap, ledger=ledger) == 1
        assert ops_ids.over_allocated(roadmap=roadmap, ledger=ledger) == {}

    def test_naming_only_one_of_the_two_documents_is_enough_to_scope_it(self, tmp_path):
        """Half a fixture tree is still a fixture tree.

        A caller who names only the roadmap still gets the real ledger, which
        is the documented behaviour of that argument. What they must not get is
        the real ARCHIVES, because the roadmap they named is the one they meant
        to measure.
        """
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text("# roadmap\n", encoding="ascii")
        assert ops_ids.roadmap_items(roadmap=roadmap) == []
        assert ops_ids.spent_ids(roadmap=roadmap) == ops_ids.spent_ids(
            roadmap=roadmap, archives=[]
        )

    def test_an_explicit_archive_list_is_honoured_beside_default_documents(self, tmp_path):
        """The other half of the rule: naming archives does not scope anything.

        An explicit `archives=` REPLACES the default archive list and is used
        verbatim, while `roadmap` and `ledger` keep their own defaults. Naming
        archives says nothing about which documents to read.

        Deliberately proved with an id no document carries rather than by
        subtracting the real archives. The obvious version of this test -
        assert `spent_ids(archives=[])` is strictly smaller than `spent_ids()`
        - was written first and measured FALSE today: 63 ids either way,
        because the ledger entry recording the split mentions the very ids the
        split moved. That is a fact about what the documents currently say, not
        about the code, and pinning it here would make this test go red the
        next time an old id stops being discussed live.
        """
        extra = tmp_path / "EXTRA_ARCHIVE.md"
        extra.write_text("### LL-0000 - 2026-01-01 - OPS-99998 was here\n", encoding="ascii")
        assert 99998 not in ops_ids.spent_ids(), "pick an id the repository does not use"
        assert 99998 in ops_ids.spent_ids(archives=[extra])


class TestACitationNamesTheFileTheEvidenceIsIn:
    """A site that names the wrong file is worse than no site at all.

    "A rendered field is not evidence of a producer": a report reading
    `ROADMAP.md: ## OPS-7. ...` for a heading that now lives in
    `docs/ROADMAP_ARCHIVE.md` sends the reader to a file that does not contain
    the line, and the reader concludes the detector is broken rather than that
    the citation is.
    """

    def test_an_archived_allocation_is_cited_to_the_archive(self, tmp_path):
        roadmap = tmp_path / "ROADMAP.md"
        ledger = tmp_path / "LEDGER.md"
        archive = tmp_path / "ARCHIVE.md"
        roadmap.write_text("## OPS-70. the live one - OPEN\n", encoding="ascii")
        ledger.write_text("# ledger\n", encoding="ascii")
        archive.write_text(
            "### LL-0001 - 2026-01-01 - OPS-70 closed - the archived one\n",
            encoding="ascii",
        )
        sites = ops_ids.over_allocated(
            roadmap=roadmap, ledger=ledger, archives=[archive]
        )[70].sites
        archived = [site for site in sites if site.startswith("ARCHIVE.md:")]
        live = [site for site in sites if site.startswith("ROADMAP.md:")]
        assert len(archived) == 1, sites
        assert "LL-0001" in archived[0], archived
        assert len(live) == 1, sites
        assert "## OPS-70." in live[0], live

    def test_the_two_known_collisions_cite_the_archives_they_moved_into(self):
        report = ops_ids.over_allocated()
        for item_id in KNOWN_COLLISIONS:
            sites = report[item_id].sites
            assert any("ARCHIVE" in site for site in sites), (
                f"OPS-{item_id}'s evidence moved into an archive under OPS-57 "
                f"and nothing in the report says so: {sites}"
            )

    def test_every_real_site_names_a_file_that_actually_carries_it(self):
        """Open each cited file and look for the line it was credited with."""
        report = ops_ids.over_allocated()
        assert report, "no collisions to check, so this proves nothing"
        for item_id, collision in report.items():
            for site in collision.sites:
                label, separator, detail = site.partition(": ")
                assert separator and detail, f"unparseable site: {site}"
                path = REPO_ROOT / label
                assert path.is_file(), f"cited file does not exist: {site}"
                text = path.read_text(encoding="utf-8", errors="replace")
                if detail.startswith("## OPS-"):
                    anchor = f"## OPS-{item_id}."
                else:
                    anchor = f"### {detail.split()[0]}"
                assert anchor in text, (
                    f"cited file {label} does not contain {anchor!r}, so the "
                    f"citation names the wrong file: {site}"
                )
