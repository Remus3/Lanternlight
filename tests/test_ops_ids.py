"""`OPS-` ids must name one item each, and the next free one must be askable.

`OPS-12`. The `OPS-` namespace had no allocator. An id was chosen by a human
reading `ROADMAP.md`, and on 2026-08-26 that produced two collisions at once:
`OPS-7` and `OPS-8` each name two unrelated items, because numbering resumed
from the highest id visible among the OPEN items rather than the highest ever
allocated. `docs/LEDGER.md` already knew about `LL-0039` and `LL-0040`; nothing
asked it.

Two things are pinned here.

**The spent set is derived by walking both documents at run time.** A
checked-in list of spent ids is exactly the filed count this repository has
been burned by - it would go stale the first time an item was added without
touching it. `ops/ops_ids.py` reads `ROADMAP.md` and `docs/LEDGER.md` and
counts what it finds.

**The known collisions are asserted as an exact set.** That is a record of a
measured state, not a list of spent ids: it fails if a THIRD collision appears,
and it fails just as loudly if `OPS-7` or `OPS-8` is ever resolved, so the
exemption cannot outlive the thing it excuses. It is the same shape as
`lane_state.stale_claims()`.
"""

import sys
from pathlib import Path

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

    def test_both_states_actually_occur_in_the_real_roadmap(self):
        # Keeps the real-document path exercised without pinning any single
        # item's status. If every heading ever reads the same way, the
        # discrimination above is not being used on real input.
        items = ops_ids.roadmap_items()
        assert any(item.closed for item in items), "no CLOSED heading was recognised"
        assert any(not item.closed for item in items), "no OPEN heading was recognised"

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
