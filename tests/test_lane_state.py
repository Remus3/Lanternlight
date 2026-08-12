"""Per-lane on-disk state, and the reason lanes never share one ledger file.

Two separate guarantees are tested here, and they are the two halves of
ROADMAP item 1b.

**Persistence.** A lane is described as a "persistent specialist", but agent
context does not survive a session, so without something on disk every lane
silently resets to zero each time it starts. ``ops/lane_state.py`` gives each
lane a state file it alone owns.

**Non-collision.** Eight lanes on eight branches cannot all append to
``docs/LEDGER.md``. The interesting part is that this is not fixed by a lock,
and the test class at the bottom of this file demonstrates why by measuring
both shapes against real git merges: two branches appending at the same anchor
in one shared file CONFLICT, and two branches appending to their own fragment
files DO NOT. A lock serialises writes in time; git merges content. Those are
different axes, so serialising the writes leaves the conflict exactly where it
was.

That differential is the point. A test that only showed fragments merging
cleanly would prove the change happened without proving it mattered.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lane_state, lanes  # noqa: E402
from ops.loop import ledger  # noqa: E402


def _entry(item_id: str, summary: str = "did a thing") -> ledger.LedgerEntry:
    return ledger.LedgerEntry(
        item_id=item_id,
        summary=summary,
        evidence=["a test that proves it"],
        date="2026-08-09",
    )


class TestPaths:
    def test_each_lane_gets_its_own_directory(self):
        seen = {lane_state.lane_prefix(lane.lane_id) for lane in lanes.LANES}
        assert len(seen) == len(lanes.LANES)

    def test_both_files_live_flat_in_the_lanes_directory(self):
        assert lane_state.state_path("ingest").parent == lane_state.lanes_dir()
        assert lane_state.fragment_path("ingest").parent == lane_state.lanes_dir()

    def test_no_lane_file_sits_in_a_subdirectory(self):
        # Measured 2026-08-09: a directory per lane put `lanes/capture/` in
        # front of two independent PII guards - .gitignore's bare `capture/`
        # rule and the pre-commit hook's `*/capture/*` rule - both of which
        # were behaving correctly. `logs`, `frames`, `private` and `tmp` are
        # blocked the same way, so any lane named after one would have failed
        # identically. Flat files remove the collision class, not one instance.
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            for chooser in (lane_state.state_path, lane_state.fragment_path):
                rel = chooser(lane.lane_id).relative_to(lane_state.REPO_ROOT)
                assert len(rel.parts) == 2, (
                    f"{rel} is nested - a lane id that collides with a blocked "
                    "directory name would be silently unstageable"
                )

    def test_the_state_and_the_fragment_are_different_files(self):
        assert lane_state.state_path("ops") != lane_state.fragment_path("ops")

    def test_lane_directories_sit_outside_ops_so_ownership_stays_disjoint(self):
        # ops/** belongs to the ops lane. A per-lane state file under ops/ would
        # therefore have two owners and turn tests/test_lanes.py red.
        rel = lane_state.lanes_dir().relative_to(lane_state.REPO_ROOT)
        assert rel.parts[0] != "ops"
        assert rel.parts[0] != "docs"


class TestStateRoundTrip:
    def test_save_then_load_returns_what_was_saved(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.LaneState(lane_id="ingest", sessions=3, resume_note="mid-parse")
        lane_state.save(state, target)
        again = lane_state.load("ingest", target)
        assert again.lane_id == "ingest"
        assert again.sessions == 3
        assert again.resume_note == "mid-parse"

    def test_saving_stamps_the_update_time(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.LaneState(lane_id="ingest")
        assert state.updated == ""
        lane_state.save(state, target)
        assert state.updated

    def test_the_write_goes_through_a_temporary_file(self, tmp_path):
        # Same reasoning as ops/loop/state.py - a reader may poll this file, and
        # open(path, "w") truncates the target before writing a byte.
        target = tmp_path / "STATE.json"
        lane_state.save(lane_state.LaneState(lane_id="ingest"), target)
        assert target.exists()
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".")]
        assert leftovers == [], f"temporary debris left behind: {leftovers}"

    def test_the_file_is_ascii_and_newline_terminated(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.save(lane_state.LaneState(lane_id="ingest"), target)
        raw = target.read_bytes()
        assert raw.decode("ascii")
        assert raw.endswith(b"\n")


class TestLoadNeverRaises:
    """A lane that crashes on a damaged state file is a lane that needs a human."""

    def test_a_missing_file_yields_a_usable_default(self, tmp_path):
        state = lane_state.load("ingest", tmp_path / "nope.json")
        assert state.lane_id == "ingest"
        assert state.sessions == 0
        assert state.recovery_note
        assert not state.recovered

    def test_invalid_json_is_recovered_and_reported(self, tmp_path):
        target = tmp_path / "STATE.json"
        target.write_text("{not json", encoding="utf-8")
        state = lane_state.load("ingest", target)
        assert state.recovered
        assert "json" in state.recovery_note.lower()

    def test_an_unknown_schema_is_treated_as_unreadable(self, tmp_path):
        target = tmp_path / "STATE.json"
        target.write_text(json.dumps({"schema": 999, "lane_id": "ingest"}), encoding="utf-8")
        state = lane_state.load("ingest", target)
        assert state.recovered
        assert "schema" in state.recovery_note.lower()

    def test_a_wrong_shape_is_recovered_rather_than_crashing(self, tmp_path):
        target = tmp_path / "STATE.json"
        target.write_text(json.dumps({"schema": 1, "sessions": "many"}), encoding="utf-8")
        state = lane_state.load("ingest", target)
        assert state.recovered

    def test_a_state_file_for_the_wrong_lane_is_refused(self, tmp_path):
        # Loading ingest's state out of ops's file would silently graft one
        # lane's open items onto another.
        target = tmp_path / "STATE.json"
        lane_state.save(lane_state.LaneState(lane_id="ops"), target)
        state = lane_state.load("ingest", target)
        assert state.recovered
        assert "ops" in state.recovery_note

    def test_recovery_flags_are_not_persisted(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.load("ingest", tmp_path / "nope.json")
        lane_state.save(state, target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert "recovered" not in payload
        assert "recovery_note" not in payload


class TestUnknownLaneIsRefused:
    def test_an_unknown_lane_id_raises(self):
        with pytest.raises(KeyError):
            lane_state.state_path("no-such-lane")

    def test_the_read_only_lane_gets_no_state_file(self):
        # verify writes nothing, ever. Handing it somewhere to write would be
        # the first crack in that.
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.state_path("verify")

    def test_the_read_only_lane_gets_no_ledger_fragment_either(self):
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.fragment_path("verify")


class TestSessionsAndOpenItems:
    def test_starting_a_session_bumps_the_counter(self, tmp_path):
        target = tmp_path / "STATE.json"
        first = lane_state.start_session("ingest", "reading the save", target)
        second = lane_state.start_session("ingest", "still reading", target)
        assert first.sessions == 1
        assert second.sessions == 2

    def test_starting_a_session_records_where_to_resume(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.start_session("ingest", "decoding StructProperty", target)
        assert state.resume_note == "decoding StructProperty"
        assert lane_state.load("ingest", target).resume_note == "decoding StructProperty"

    def test_an_open_item_survives_a_reload(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.add_open_item("ingest", "OI-1", "decode the nested struct", path=target)
        state = lane_state.load("ingest", target)
        assert [item.item_id for item in state.open_items] == ["OI-1"]
        assert state.open_items[0].text == "decode the nested struct"

    def test_an_open_item_can_record_what_it_is_blocked_on(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.add_open_item(
            "ingest", "OI-2", "pin a fixture", blocked_on="safety review", path=target
        )
        assert lane_state.load("ingest", target).open_items[0].blocked_on == "safety review"

    def test_closing_an_open_item_removes_it(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.add_open_item("ingest", "OI-1", "a", path=target)
        lane_state.add_open_item("ingest", "OI-2", "b", path=target)
        lane_state.close_open_item("ingest", "OI-1", path=target)
        assert [i.item_id for i in lane_state.load("ingest", target).open_items] == ["OI-2"]

    def test_closing_an_unknown_item_raises_rather_than_passing_quietly(self, tmp_path):
        target = tmp_path / "STATE.json"
        with pytest.raises(KeyError):
            lane_state.close_open_item("ingest", "OI-9", path=target)

    def test_adding_a_duplicate_open_item_id_raises(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.add_open_item("ingest", "OI-1", "a", path=target)
        with pytest.raises(ValueError):
            lane_state.add_open_item("ingest", "OI-1", "different text", path=target)


class TestAsciiIsEnforcedAtTheWrite:
    """Catch it where the field is named, not later where only the file is.

    The offending characters are written as escapes rather than as literals.
    That is not squeamishness - ``tests/test_ascii_hygiene.py`` scans this file
    too, so a literal em-dash here would fail the repository hygiene guard
    while trying to test the lane-level one. Measured this session: it did.
    """

    EM_DASH = chr(0x2014)
    LEFT_QUOTE = chr(0x201C)
    RIGHT_QUOTE = chr(0x201D)

    def test_a_non_ascii_resume_note_raises(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.LaneState(lane_id="ingest", resume_note=f"em{self.EM_DASH}dash")
        with pytest.raises(ValueError):
            lane_state.save(state, target)

    def test_a_non_ascii_open_item_raises(self, tmp_path):
        target = tmp_path / "STATE.json"
        text = f"smart {self.LEFT_QUOTE}quotes{self.RIGHT_QUOTE}"
        with pytest.raises(ValueError):
            lane_state.add_open_item("ingest", "OI-1", text, path=target)

    def test_the_error_names_the_offending_codepoint(self, tmp_path):
        target = tmp_path / "STATE.json"
        state = lane_state.LaneState(lane_id="ingest", resume_note=f"a{self.EM_DASH}b")
        with pytest.raises(ValueError, match="U\\+2014"):
            lane_state.save(state, target)


class TestRenderIsReadableCold:
    def test_the_render_names_the_lane_and_its_open_items(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.start_session("ingest", "mid-parse", target)
        lane_state.add_open_item("ingest", "OI-1", "decode the struct", path=target)
        text = lane_state.render(lane_state.load("ingest", target))
        assert "ingest" in text
        assert "OI-1" in text
        assert "decode the struct" in text
        assert "mid-parse" in text

    def test_the_render_is_ascii(self, tmp_path):
        target = tmp_path / "STATE.json"
        lane_state.add_open_item("ingest", "OI-1", "a thing", path=target)
        assert lane_state.render(lane_state.load("ingest", target)).isascii()

    def test_no_open_items_says_so_rather_than_rendering_an_empty_list(self, tmp_path):
        text = lane_state.render(lane_state.load("ingest", tmp_path / "nope.json"))
        assert "none" in text.lower()


class TestLedgerFragment:
    def test_appending_creates_the_fragment_with_its_marker(self, tmp_path):
        target = tmp_path / "LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=target)
        assert lane_state.FRAGMENT_MARKER in target.read_text(encoding="utf-8")

    def test_a_second_entry_preserves_the_first_byte_for_byte(self, tmp_path):
        target = tmp_path / "LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0100", "first"), path=target)
        after_first = target.read_text(encoding="utf-8")
        first_block = after_first.split(lane_state.FRAGMENT_MARKER, 1)[1]
        lane_state.append_fragment("ingest", _entry("LL-0101", "second"), path=target)
        assert first_block.strip() in target.read_text(encoding="utf-8")

    def test_entries_are_newest_first(self, tmp_path):
        target = tmp_path / "LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=target)
        lane_state.append_fragment("ingest", _entry("LL-0101"), path=target)
        text = target.read_text(encoding="utf-8")
        assert text.index("LL-0101") < text.index("LL-0100")

    def test_reading_back_returns_the_entry_ids_newest_first(self, tmp_path):
        target = tmp_path / "LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=target)
        lane_state.append_fragment("ingest", _entry("LL-0101"), path=target)
        assert lane_state.fragment_entry_ids(target) == ["LL-0101", "LL-0100"]

    def test_an_entry_with_no_evidence_is_refused(self, tmp_path):
        target = tmp_path / "LEDGER.md"
        bad = ledger.LedgerEntry(item_id="LL-0100", summary="s", evidence=[])
        with pytest.raises(ValueError):
            lane_state.append_fragment("ingest", bad, path=target)

    def test_a_missing_fragment_reads_as_empty_rather_than_raising(self, tmp_path):
        assert lane_state.fragment_entry_ids(tmp_path / "nope.md") == []


def _seed_ledger(tmp_path: Path) -> Path:
    """Write a miniature repository ledger, template trap and all."""
    target = tmp_path / "LEDGER.md"
    target.write_text(
        "# Ledger\n\nPreamble with a template:\n\n"
        "```\n### LL-0000 - YYYY-MM-DD - one-line summary\n```\n\n"
        f"{ledger.ENTRIES_MARKER}\n\n"
        "### LL-0099 - 2026-08-08 - something older\n\n"
        "**Evidence:**\n- it happened\n",
        encoding="utf-8",
    )
    return target


class TestIntegrateIntoTheRepositoryLedger:
    def _seeded_ledger(self, tmp_path: Path) -> Path:
        return _seed_ledger(tmp_path)

    def test_a_fragment_entry_lands_in_the_repository_ledger(self, tmp_path):
        book = self._seeded_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0100", "from the lane"), path=frag)
        moved = lane_state.integrate(frag, book)
        assert moved == ["LL-0100"]
        assert "from the lane" in book.read_text(encoding="utf-8")

    def test_integration_preserves_the_existing_entries(self, tmp_path):
        book = self._seeded_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=frag)
        lane_state.integrate(frag, book)
        assert "LL-0099 - 2026-08-08 - something older" in book.read_text(encoding="utf-8")

    def test_integration_is_idempotent(self, tmp_path):
        book = self._seeded_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=frag)
        lane_state.integrate(frag, book)
        again = lane_state.integrate(frag, book)
        assert again == []
        assert book.read_text(encoding="utf-8").count("### LL-0100") == 1

    def test_the_template_in_the_preamble_does_not_count_as_an_entry(self, tmp_path):
        # Measured trap, ledger LL-0014: a naive count of '### LL-' headers in
        # docs/LEDGER.md is one too high, because the Format section contains a
        # LL-0000 template inside a code fence. An idempotence check that
        # searched the whole file would refuse to integrate a real LL-0000.
        book = self._seeded_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0000", "a real entry"), path=frag)
        assert lane_state.integrate(frag, book) == ["LL-0000"]
        assert "a real entry" in book.read_text(encoding="utf-8")

    def test_a_ledger_without_the_marker_is_refused(self, tmp_path):
        book = tmp_path / "LEDGER.md"
        book.write_text("# Ledger\n\nno marker here\n", encoding="utf-8")
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=frag)
        with pytest.raises(ledger.MarkerMissingError):
            lane_state.integrate(frag, book)

    def test_integrating_several_fragments_keeps_every_entry(self, tmp_path):
        book = self._seeded_ledger(tmp_path)
        one = tmp_path / "a.md"
        two = tmp_path / "b.md"
        lane_state.append_fragment("ingest", _entry("LL-0100"), path=one)
        lane_state.append_fragment("ops", _entry("LL-0101"), path=two)
        lane_state.integrate(one, book)
        lane_state.integrate(two, book)
        text = book.read_text(encoding="utf-8")
        assert "### LL-0100" in text
        assert "### LL-0101" in text
        assert "### LL-0099" in text


class TestTwoLanesClaimingOneId:
    """The id-allocation race, ROADMAP item 2c.

    ``LL-0018`` gave every lane its own fragment, which removed the TEXT race:
    two lanes appending can no longer conflict, because they write to different
    files. **The ID race survived, and the fragment design is what hides it.**
    Two lanes branching from a common base both ask "what is the next free id?",
    both get the same answer, and git merges both fragments cleanly because
    nothing textually conflicts.

    ``integrate`` then turned that into silent data loss. Skipping ids already
    present is what makes it idempotent - right for a re-run, catastrophic for a
    collision - and the two cases were indistinguishable, so the second lane's
    entry vanished with no exception, no warning and no diff.

    Reproduced by the integrator on 2026-08-11 against a throwaway copy of the
    real ledger::

        integrate(ingest)   -> ['LL-0024', 'LL-0023']
        integrate(research) -> []          # the entire entry, gone
        research heading present in ledger: False
    """

    def _collision(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Seed a ledger and two fragments that both claim ``LL-0023``."""
        book = _seed_ledger(tmp_path)
        ingest = tmp_path / "ingest.LEDGER.md"
        research = tmp_path / "research.LEDGER.md"
        lane_state.append_fragment(
            "ingest", _entry("LL-0023", "a GVAS serialiser"), path=ingest
        )
        lane_state.append_fragment(
            "research", _entry("LL-0023", "the transient-save decode"), path=research
        )
        return book, ingest, research

    def test_the_second_lanes_entry_is_never_lost_without_a_word(self, tmp_path):
        # The defect itself, asserted in the only form that survives the fix:
        # integrating a colliding fragment must either RAISE or record the
        # entry. What it must never do is return quietly having dropped it.
        book, ingest, research = self._collision(tmp_path)
        assert lane_state.integrate(ingest, book) == ["LL-0023"]

        raised: BaseException | None = None
        moved: list[str] | None = None
        try:
            moved = lane_state.integrate(research, book)
        except Exception as exc:  # broad on purpose - "did it say ANYTHING?"
            raised = exc

        after = book.read_text(encoding="utf-8")
        assert raised is not None or "the transient-save decode" in after, (
            "SILENT DATA LOSS: the research lane's LL-0023 entry is gone. "
            f"integrate returned {moved!r}, raised nothing, and the heading "
            "'the transient-save decode' is absent from the ledger. A whole "
            "session record disappeared and the only symptom was an empty list."
        )

    def test_a_collision_raises_and_says_what_to_do_about_it(self, tmp_path):
        book, ingest, research = self._collision(tmp_path)
        lane_state.integrate(ingest, book)

        with pytest.raises(lane_state.LedgerIdCollision) as caught:
            lane_state.integrate(research, book)

        message = str(caught.value)
        assert "LL-0023" in message, "the message must name the colliding id"
        assert "research.LEDGER.md" in message, "the message must name the fragment"
        assert "renumber" in message.lower(), (
            "the message must say what to do - the integrator is a human "
            "decision here, and an error with no remedy gets a force flag "
            "bolted onto it instead"
        )

    def test_a_refused_collision_writes_nothing(self, tmp_path):
        # A half-applied integration is worse than a refused one: the next
        # re-run would see some ids present and some absent.
        book, ingest, research = self._collision(tmp_path)
        lane_state.integrate(ingest, book)
        before = book.read_text(encoding="utf-8")
        lane_state.append_fragment(
            "research", _entry("LL-0024", "an innocent bystander"), path=research
        )

        with pytest.raises(lane_state.LedgerIdCollision):
            lane_state.integrate(research, book)

        assert book.read_text(encoding="utf-8") == before
        assert "LL-0024" not in book.read_text(encoding="utf-8")

    def test_one_fragment_claiming_one_id_twice_is_a_collision_too(self, tmp_path):
        # Same defect, one file. Both blocks are absent from the ledger, so
        # both would be inserted and the ledger would hold a duplicate id.
        book = _seed_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "first work"), path=frag)
        lane_state.append_fragment("ingest", _entry("LL-0023", "other work"), path=frag)
        with pytest.raises(lane_state.LedgerIdCollision):
            lane_state.integrate(frag, book)

    def test_the_same_entry_twice_is_still_a_skip_not_a_collision(self, tmp_path):
        # Idempotence is load-bearing: integrate must stay safe to re-run after
        # a partial merge. Byte-identical content is a re-run, never a clash.
        book = _seed_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "one thing"), path=frag)
        assert lane_state.integrate(frag, book) == ["LL-0023"]
        assert lane_state.integrate(frag, book) == []
        assert book.read_text(encoding="utf-8").count("### LL-0023") == 1

    def test_line_endings_and_trailing_blanks_do_not_fake_a_collision(self, tmp_path):
        # The hazard this repository has already paid for: Windows write_text
        # turns LF into CRLF and read_text hides it. A byte-exact comparison
        # would call a re-run a collision, and a false collision is WORSE than
        # the bug - it is what makes someone add a force flag.
        book = _seed_ledger(tmp_path)
        frag = tmp_path / "frag.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "one thing"), path=frag)
        assert lane_state.integrate(frag, book) == ["LL-0023"]

        roughed = frag.read_text(encoding="utf-8").replace("\n", "\r\n")
        roughed = roughed.replace("**Evidence:**", "**Evidence:**   ") + "\r\n\r\n"
        assert "\r\n" in roughed, "the CRLF mutation must have applied"
        frag.write_bytes(roughed.encode("utf-8"))

        assert lane_state.integrate(frag, book) == []
        assert book.read_text(encoding="utf-8").count("### LL-0023") == 1


class TestAMalformedHeadingIsRefusedNotSkipped:
    """The LL-0031 defect through a different door, found by a refutation pass.

    `_HEADING_RE` requires exactly `### `, then a non-space id, then ` - `. An
    entry whose heading misses that by one character does not merely fail to
    parse - it becomes INVISIBLE. `fragment_entry_ids` omits it,
    `duplicate_claims` cannot see the id it claims, and `integrate` returns
    `[]` and writes nothing.

    That is precisely the failure LL-0031 was written to end: an entry
    disappears, no exception, and the only symptom is an empty list the
    integrator reads as "already done". Detection was the whole point, so a
    block that looks like an entry and does not parse must be refused loudly
    rather than dropped quietly.

    Measured before choosing the rule: across `docs/LEDGER.md` and all lane
    fragments there are 46 lines starting with `#` below the marker, and all 46
    parse. So refusing an unparseable one costs nothing today.
    """

    MALFORMED = (
        "###  LL-0044 - 2026-08-12 - two spaces after the hashes",
        "###LL-0044 - 2026-08-12 - no space at all",
        "## LL-0044 - 2026-08-12 - one hash short",
        "#### LL-0044 - 2026-08-12 - one hash too many",
        "### LL-0044: 2026-08-12 - a colon instead of the dash",
    )

    def _fragment(self, tmp_path, heading):
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n"
            f"{heading}\n\n**Evidence:**\n- something that must not vanish\n",
            encoding="utf-8",
        )
        return path

    @pytest.mark.parametrize("heading", MALFORMED)
    def test_it_raises_rather_than_returning_nothing(self, tmp_path, heading):
        path = self._fragment(tmp_path, heading)
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)

    @pytest.mark.parametrize("heading", MALFORMED)
    def test_integrate_refuses_instead_of_silently_dropping_it(self, tmp_path, heading):
        book = _seed_ledger(tmp_path)
        path = self._fragment(tmp_path, heading)
        before = book.read_text(encoding="utf-8")
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.integrate(path, ledger_path=book)
        assert book.read_text(encoding="utf-8") == before

    def test_the_error_names_the_file_and_the_offending_line(self, tmp_path):
        path = self._fragment(tmp_path, self.MALFORMED[0])
        with pytest.raises(lane_state.MalformedLedgerHeading) as caught:
            lane_state.fragment_entry_ids(path)
        message = str(caught.value)
        assert "ops.LEDGER.md" in message
        assert "LL-0044" in message

    def test_a_well_formed_heading_is_still_accepted(self, tmp_path):
        path = self._fragment(tmp_path, "### LL-0044 - 2026-08-12 - perfectly ordinary")
        assert lane_state.fragment_entry_ids(path) == ["LL-0044"]

    def test_a_hash_line_carrying_no_id_is_left_alone(self, tmp_path):
        # Scoped to lines that look like an ENTRY. A prose sub-heading is not
        # this rule's business, and a rule that fires on one would be a false
        # positive that gets the whole guard disabled.
        path = self._fragment(tmp_path, "### LL-0044 - 2026-08-12 - fine")
        path.write_text(
            path.read_text(encoding="utf-8") + "\n#### some prose sub-heading\n",
            encoding="utf-8",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0044"]

    def test_an_id_inside_a_fenced_code_block_is_not_a_heading(self, tmp_path):
        # An entry may quote a command or a snippet. A `#` comment naming an id
        # inside a fence is not a malformed heading.
        path = self._fragment(tmp_path, "### LL-0044 - 2026-08-12 - fine")
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\n```\n# see LL-0044 for why\n```\n",
            encoding="utf-8",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0044"]

    def test_the_live_repository_has_no_malformed_heading(self):
        # Runs over the real files on every suite run, like its collision
        # sibling - a guard that only ever sees fixtures cannot protect a wrap.
        lane_state.duplicate_claims()


class TestAnUnclosedFenceCannotSuppressTheGuard:
    """Found by the refutation pass on LL-0034, and WORSE than the bug it fixed.

    The heading guard skips fenced code, because an entry may quote a snippet
    that contains a `#` comment. The fence state was a bare toggle, so an entry
    that opens a fence and forgets to close it left every following line marked
    as code - and the guard silently stood down for the rest of the file.

    Reproduced before this test existed: two entries, one forgotten backtick,
    `integrate()` returned `['LL-0900']` - **non-empty, which reads as
    success** - while the second entry never landed and its body was glued into
    the first one's block. No exception anywhere.

    That is worse than the defect LL-0034 closed, which at least returned an
    empty list. A wrong answer that looks like a right answer is the failure
    this whole module exists to prevent, so an unbalanced fence is now itself a
    refusal.
    """

    def _fragment(self, tmp_path, body):
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n{body}",
            encoding="utf-8",
        )
        return path

    UNCLOSED = (
        "### LL-0900 - 2026-08-12 - forgets to close its fence\n\n"
        "**Evidence:**\n- a command\n```\npython -m pytest\n\n"
        "###  LL-0901 - 2026-08-12 - MALFORMED, and it must not vanish\n\n"
        "**Evidence:**\n- an entire session record\n"
    )

    def test_an_unbalanced_fence_is_refused(self, tmp_path):
        path = self._fragment(tmp_path, self.UNCLOSED)
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)

    def test_integrate_refuses_and_writes_nothing(self, tmp_path):
        book = _seed_ledger(tmp_path)
        path = self._fragment(tmp_path, self.UNCLOSED)
        before = book.read_text(encoding="utf-8")
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.integrate(path, ledger_path=book)
        assert book.read_text(encoding="utf-8") == before

    def test_the_hidden_entry_is_never_absorbed_into_its_neighbour(self, tmp_path):
        # The specific harm: not merely dropped, but glued into the block above.
        book = _seed_ledger(tmp_path)
        path = self._fragment(tmp_path, self.UNCLOSED)
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.integrate(path, ledger_path=book)
        assert "must not vanish" not in book.read_text(encoding="utf-8")

    def test_a_balanced_fence_is_still_fine(self, tmp_path):
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - closes its fence properly\n\n"
            "**Evidence:**\n- a command\n```\n# see LL-0031 for why\n```\n",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0900"]

    def test_a_tilde_fence_suppresses_the_guard_exactly_like_a_backtick_one(self, tmp_path):
        # Pinned because it was UNPINNED: the refutation pass showed that
        # widening the delimiter set changed nothing any test observed, so the
        # behaviour was accidental rather than chosen. `~~~` is valid Markdown,
        # so it is supported deliberately - and now it is asserted.
        # NOTE what a fence does and does not do, because writing this test
        # wrongly is what revealed it: a fence suppresses the malformed-heading
        # GUARD, not the heading PARSER. `_HEADING_RE.finditer` runs over the
        # whole body and knows nothing about fences, so a WELL-FORMED heading
        # inside a code block is still parsed as a real entry. Recorded as
        # OPS-9; the two halves disagreeing is a latent trap, not a fix to make
        # quietly during a wrap.
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - quotes a snippet with a tilde fence\n\n"
            "**Evidence:**\n- a command\n~~~\n###  LL-0901 - malformed, but it is code\n~~~\n",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0900"]

    def test_an_unclosed_tilde_fence_is_refused_too(self, tmp_path):
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - forgets to close a tilde fence\n\n"
            "**Evidence:**\n- a command\n~~~\npython -m pytest\n",
        )
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)

    def test_a_fence_is_closed_only_by_the_delimiter_that_opened_it(self, tmp_path):
        # Mismatched delimiters leave the fence OPEN, which is what Markdown
        # does - and it means the unbalanced check still catches it rather than
        # the guard quietly standing down for the rest of the file.
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - opens with backticks, closes with tildes\n\n"
            "**Evidence:**\n- a command\n```\npython -m pytest\n~~~\n",
        )
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)

    def test_an_unbalanced_fence_with_nothing_after_it_is_still_refused(self, tmp_path):
        # It suppresses nothing today, but it is the same malformation and the
        # next entry appended below it would be swallowed.
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - trailing open fence\n\n"
            "**Evidence:**\n- a command\n```\npython -m pytest\n",
        )
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)


class TestALaneCanClaimAPathItIsAdding:
    """`OPS-2`. A lane adding a NEW file could not go green on its own.

    The orphan guard walks the real tree, including untracked files, and fails
    any path no lane owns. Ownership is declared in `ops/lanes.py`, which the
    **ops** lane owns - so any other lane that creates a file is red for its
    whole session and cannot fix it without writing outside its slice.

    Reproduced before this existed: a clone plus one new `lanternlight/` module
    gives `1 failed, 34 passed`.

    **Neither option the item offered removes that.** "ops declares ownership
    first" needs the filename known before the work starts, which is often
    false. "The integrator declares it at merge" is what shipped `LL-0035`, and
    it works - but only for an integrator spanning both lanes; a lane running
    alone still sits red. A lane sitting red all session is precisely the
    pressure that makes somebody weaken a guard to go green, which `CLAUDE.md`
    forbids in as many words.

    So a lane may CLAIM a path in its own `STATE.json` - a file it owns - and
    the orphan guard honours exactly one claimant. The roster stays the single
    source of truth: a claim is a promissory note the integrator redeems, and
    the guards below make sure it cannot quietly become a second ownership map.
    """

    def test_a_claimed_path_has_a_claimant(self, tmp_path):
        state = lane_state.claim_path(
            "ingest", "lanternlight/newthing.py", path=tmp_path / "s.json"
        )
        assert "lanternlight/newthing.py" in state.claimed_paths
        assert lane_state.claimants_of(
            "lanternlight/newthing.py", states={"ingest": state}
        ) == ["ingest"]

    def test_an_unclaimed_path_has_none(self, tmp_path):
        state = lane_state.claim_path("ingest", "lanternlight/a.py", path=tmp_path / "s.json")
        assert lane_state.claimants_of("lanternlight/b.py", states={"ingest": state}) == []

    def test_a_claim_matches_by_pattern_not_by_string(self, tmp_path):
        state = lane_state.claim_path("ingest", "lanternlight/new*.py", path=tmp_path / "s.json")
        assert lane_state.claimants_of("lanternlight/newthing.py", states={"ingest": state})
        assert not lane_state.claimants_of("lanternlight/other.py", states={"ingest": state})

    def test_a_claim_can_be_released(self, tmp_path):
        target = tmp_path / "s.json"
        lane_state.claim_path("ingest", "lanternlight/x.py", path=target)
        state = lane_state.release_path("ingest", "lanternlight/x.py", path=target)
        assert state.claimed_paths == ()

    def test_claiming_twice_does_not_duplicate(self, tmp_path):
        target = tmp_path / "s.json"
        lane_state.claim_path("ingest", "lanternlight/x.py", path=target)
        state = lane_state.claim_path("ingest", "lanternlight/x.py", path=target)
        assert list(state.claimed_paths) == ["lanternlight/x.py"]

    def test_a_read_only_lane_may_not_claim_anything(self, tmp_path):
        # verify owns nothing on purpose. A claim is a write.
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.claim_path("verify", "anything.py", path=tmp_path / "s.json")

    def test_a_claim_survives_a_round_trip(self, tmp_path):
        target = tmp_path / "s.json"
        lane_state.claim_path("ingest", "lanternlight/x.py", path=target)
        assert lane_state.load("ingest", target).claimed_paths == ("lanternlight/x.py",)

    def test_a_state_file_written_before_claims_existed_still_loads(self, tmp_path):
        # Every committed STATE.json predates this field. A loader that treated
        # the missing key as corruption would wipe seven lanes' open items.
        target = tmp_path / "s.json"
        target.write_text(
            json.dumps({"schema": 1, "lane_id": "ingest", "sessions": 2, "open_items": []}),
            encoding="utf-8",
        )
        state = lane_state.load("ingest", target)
        assert state.claimed_paths == ()
        assert state.recovered is False, state.recovery_note

    def test_a_claim_must_be_ascii(self, tmp_path):
        # Built with an escape, not typed: this repository is 7-bit ASCII in
        # every authored file, and writing the character here would fail
        # tests/test_ascii_hygiene.py. It did, on the first attempt.
        non_ascii = "lanternlight/na" + chr(0xEF) + "ve.py"
        with pytest.raises(ValueError):
            lane_state.claim_path("ingest", non_ascii, path=tmp_path / "s.json")

    def test_a_stale_claim_is_reported(self, tmp_path):
        # The whole point. Once the integrator folds a claim into ops/lanes.py,
        # the claim MUST be removed - otherwise it becomes a permanent second
        # ownership map, which is the thing the roster exists to prevent.
        state = lane_state.claim_path(
            "ingest", "lanternlight/gvas.py", path=tmp_path / "s.json"
        )
        stale = lane_state.stale_claims(states={"ingest": state})
        assert stale == [("ingest", "lanternlight/gvas.py")]

    def test_a_fresh_claim_is_not_stale(self, tmp_path):
        state = lane_state.claim_path(
            "ingest", "lanternlight/not_in_the_roster_yet.py", path=tmp_path / "s.json"
        )
        assert lane_state.stale_claims(states={"ingest": state}) == []

    def test_the_live_repository_has_no_stale_claim(self):
        # Runs over the real state files every suite run, like its collision
        # sibling. A claim left behind after a merge is invisible otherwise.
        assert lane_state.stale_claims() == []


class TestAnEditedEntryIsNotACollision:
    """`OPS-8`. Two different faults gave one diagnosis, and it was the wrong one.

    Edit an entry AFTER it has been integrated and it no longer matches its
    fragment, so `integrate()` reports a `LedgerIdCollision` and the live guard
    stays red. Reproduced before any fix: integrate, edit one number in the
    ledger copy, re-integrate -> raised, and the message said the id was
    "claimed twice by DIFFERENT entries" and told the reader to **renumber the
    fragment's entry by hand**.

    That remedy is actively wrong here. Renumbering would record one piece of
    work twice under two ids - the opposite of what the reader wants, and it
    corrupts the record while appearing to fix it.

    **The decision OPS-8 asked for, taken and stated.** The item offered two
    options: policy (an integrated entry is never edited) or code (reconcile the
    fragment automatically). *Policy stands.* Auto-reconciliation would write to
    a lane fragment, which this module documents as append-only and never
    edited, so a fix for a reporting defect would have broken a core invariant.
    What is fixed is the **diagnosis**: the two causes are now told apart where
    that is possible, and where it is not, both are named rather than one being
    guessed.
    """

    def _integrated(self, tmp_path):
        book = _seed_ledger(tmp_path)
        frag = tmp_path / "ops.LEDGER.md"
        lane_state.append_fragment("ops", _entry("LL-0500", "the original"), path=frag)
        assert lane_state.integrate(frag, book) == ["LL-0500"]
        return book, frag

    def _edit_the_ledger_copy(self, book):
        text = book.read_text(encoding="utf-8")
        edited = text.replace("the original", "the original, with a typo fixed")
        assert edited != text, "the edit must apply or this probe is vacuous"
        book.write_text(edited, encoding="utf-8")

    def test_duplicate_claims_calls_it_an_edit_not_a_collision(self, tmp_path):
        book, frag = self._integrated(tmp_path)
        self._edit_the_ledger_copy(book)
        found = lane_state.duplicate_claims(ledger_path=book, fragments=[frag])
        assert list(found) == ["LL-0500"]
        assert lane_state.classify_claim(found["LL-0500"]) == lane_state.EDITED_AFTER_INTEGRATION

    def test_two_lanes_are_still_called_a_collision(self, tmp_path):
        # The other half. A guard that renamed every collision an "edit" would
        # be just as wrong in the opposite direction.
        book = _seed_ledger(tmp_path)
        ingest = tmp_path / "ingest.LEDGER.md"
        research = tmp_path / "research.LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "serialiser"), path=ingest)
        lane_state.append_fragment("research", _entry("LL-0023", "decode"), path=research)
        found = lane_state.duplicate_claims(ledger_path=book, fragments=[ingest, research])
        assert lane_state.classify_claim(found["LL-0023"]) == lane_state.TWO_LANES_COLLIDED

    def test_the_rendered_report_gives_the_right_remedy_for_an_edit(self, tmp_path):
        book, frag = self._integrated(tmp_path)
        self._edit_the_ledger_copy(book)
        rendered = lane_state.format_duplicate_claims(
            lane_state.duplicate_claims(ledger_path=book, fragments=[frag])
        )
        assert "edited" in rendered.lower()
        # Not "the word renumber is absent" - the message legitimately contains
        # it while FORBIDDING it. The property is that renumbering is refused,
        # because doing it here records one piece of work under two ids.
        assert "do not renumber" in rendered.lower()
        assert "append a new entry" in rendered.lower()

    def test_the_rendered_report_still_says_renumber_for_a_real_collision(self, tmp_path):
        book = _seed_ledger(tmp_path)
        ingest = tmp_path / "ingest.LEDGER.md"
        research = tmp_path / "research.LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "serialiser"), path=ingest)
        lane_state.append_fragment("research", _entry("LL-0023", "decode"), path=research)
        rendered = lane_state.format_duplicate_claims(
            lane_state.duplicate_claims(ledger_path=book, fragments=[ingest, research])
        )
        assert "renumber" in rendered.lower()

    def test_integrate_no_longer_asserts_renumbering_as_the_only_remedy(self, tmp_path):
        # integrate() sees ONE fragment and the ledger, so it genuinely cannot
        # tell an edit from another lane's prior claim. Omit rather than guess:
        # it must name both causes instead of confidently giving one remedy.
        book, frag = self._integrated(tmp_path)
        self._edit_the_ledger_copy(book)
        with pytest.raises(lane_state.LedgerIdCollision) as caught:
            lane_state.integrate(frag, book)
        message = str(caught.value).lower()
        assert "edited" in message
        assert "LL-0500".lower() in message

    def test_integrate_still_writes_nothing_when_it_refuses(self, tmp_path):
        book, frag = self._integrated(tmp_path)
        self._edit_the_ledger_copy(book)
        before = book.read_text(encoding="utf-8")
        with pytest.raises(lane_state.LedgerIdCollision):
            lane_state.integrate(frag, book)
        assert book.read_text(encoding="utf-8") == before

    def test_an_untouched_integration_is_still_a_silent_no_op(self, tmp_path):
        # The behaviour none of this may disturb.
        book, frag = self._integrated(tmp_path)
        assert lane_state.integrate(frag, book) == []
        assert lane_state.duplicate_claims(ledger_path=book, fragments=[frag]) == {}


class TestAFragmentPathThatIsNotAFragment:
    """`OPS-7`. A missing fragment is ordinary; a nonsense one is not.

    `integrate()` and friends treat a fragment that does not exist as empty,
    which is correct - fragments are created lazily on a lane's first entry, so
    six of seven lanes have none. But that tolerance used to swallow a genuine
    caller mistake too: `integrate("ops")`, passing a LANE ID where a fragment
    PATH belongs, hit a directory and surfaced a bare
    ``PermissionError: [Errno 13] Permission denied: 'ops'`` on Windows.

    An errno is not a diagnosis. Worse, the two cases are a hair apart: get the
    name slightly wrong and you get a silent `[]`, get it wrong in a different
    way and you get an unrelated OS error. Neither says "that is not a
    fragment", which is the one thing the caller needs to hear.
    """

    def test_a_bare_lane_id_is_refused_with_the_path_it_should_have_been(self, tmp_path):
        book = _seed_ledger(tmp_path)
        with pytest.raises(lane_state.NotAFragment) as caught:
            lane_state.integrate("ops", ledger_path=book)
        message = str(caught.value)
        assert "ops" in message
        assert "ops.LEDGER.md" in message, "the error must name the path meant"

    def test_a_directory_is_refused_rather_than_raising_an_errno(self, tmp_path):
        book = _seed_ledger(tmp_path)
        somewhere = tmp_path / "a_directory"
        somewhere.mkdir()
        with pytest.raises(lane_state.NotAFragment) as caught:
            lane_state.integrate(somewhere, ledger_path=book)
        assert "directory" in str(caught.value).lower()

    def test_refusing_writes_nothing(self, tmp_path):
        book = _seed_ledger(tmp_path)
        before = book.read_text(encoding="utf-8")
        somewhere = tmp_path / "a_directory"
        somewhere.mkdir()
        with pytest.raises(lane_state.NotAFragment):
            lane_state.integrate(somewhere, ledger_path=book)
        assert book.read_text(encoding="utf-8") == before

    def test_fragment_entry_ids_refuses_a_directory_too(self, tmp_path):
        somewhere = tmp_path / "a_directory"
        somewhere.mkdir()
        with pytest.raises(lane_state.NotAFragment):
            lane_state.fragment_entry_ids(somewhere)

    def test_duplicate_claims_refuses_a_directory_too(self, tmp_path):
        book = _seed_ledger(tmp_path)
        somewhere = tmp_path / "a_directory"
        somewhere.mkdir()
        with pytest.raises(lane_state.NotAFragment):
            lane_state.duplicate_claims(ledger_path=book, fragments=[somewhere])

    def test_a_MISSING_fragment_is_still_ordinary_and_still_reads_as_empty(self, tmp_path):
        # The behaviour this fix must not break. Fragments are created lazily,
        # so absence is the normal state for most lanes and must stay silent.
        book = _seed_ledger(tmp_path)
        assert lane_state.fragment_entry_ids(tmp_path / "nope.LEDGER.md") == []
        assert lane_state.integrate(tmp_path / "nope.LEDGER.md", ledger_path=book) == []
        assert lane_state.duplicate_claims(
            ledger_path=book, fragments=[tmp_path / "nope.LEDGER.md"]
        ) == {}

    def test_an_unreadable_but_EXISTING_fragment_is_not_reported_as_absent(
        self, tmp_path, monkeypatch
    ):
        """A file that is there and cannot be read is not an empty lane.

        Added because a mutation survived: widening the catch back to a bare
        `except OSError` left the whole suite green, which means nothing pinned
        what happens when a fragment exists but the read fails. Swallowing that
        into `None` reports a lane with entries as a lane with none - the same
        silent-loss shape as every other bug in this module.
        """
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n"
            "### LL-0500 - 2026-08-12 - a real entry that must not vanish\n\n"
            "**Evidence:**\n- x\n",
            encoding="utf-8",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0500"]

        def refuse(*args, **kwargs):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "read_text", refuse)
        with pytest.raises(OSError):
            lane_state.fragment_entry_ids(path)

    def test_every_real_lane_id_is_refused_not_just_ops(self, tmp_path):
        book = _seed_ledger(tmp_path)
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            with pytest.raises(lane_state.NotAFragment):
                lane_state.integrate(lane.lane_id, ledger_path=book)


class TestTheGuardAndTheParserAgreeAboutFences:
    """`OPS-9`. The two halves used to disagree, which is this module's bug shape.

    `_assert_headings_parse` skipped fenced lines. `_HEADING_RE.finditer` ran
    over the whole entry region and knew nothing about fences. So inside a code
    block a **well-formed** heading was parsed as a real entry while a
    **malformed** one was ignored - the guard protecting a region the parser was
    not reading the same way.

    That is not hypothetical: `docs/LEDGER.md` documents its own entry format
    with a fenced `### LL-0000 - ...` example, and it is safe today only because
    it sits ABOVE the entries marker. Quote an example entry below the marker,
    or in a lane fragment, and it became a phantom entry with a real id.

    Both halves now share one fence scanner, so there is no second opinion to
    disagree with.
    """

    def _fragment(self, tmp_path, body):
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n{body}",
            encoding="utf-8",
        )
        return path

    QUOTES_AN_EXAMPLE = (
        "### LL-0900 - 2026-08-12 - documents the entry format\n\n"
        "**Evidence:**\n- an entry looks like this:\n"
        "```\n"
        "### LL-9999 - 2026-01-01 - EXAMPLE, not a real entry\n"
        "```\n"
    )

    def test_a_well_formed_heading_inside_a_fence_is_not_an_entry(self, tmp_path):
        path = self._fragment(tmp_path, self.QUOTES_AN_EXAMPLE)
        assert lane_state.fragment_entry_ids(path) == ["LL-0900"]

    def test_the_phantom_id_never_becomes_an_entry_in_the_ledger(self, tmp_path):
        book = _seed_ledger(tmp_path)
        path = self._fragment(tmp_path, self.QUOTES_AN_EXAMPLE)
        assert lane_state.integrate(path, ledger_path=book) == ["LL-0900"]

        text = book.read_text(encoding="utf-8")
        # The example TEXT is carried, because it is part of LL-0900's body and
        # an append-only record must not rewrite what its author wrote. What
        # must not happen is LL-9999 becoming an ENTRY - so the assertion is
        # about the parsed ids, not about the bytes.
        assert "EXAMPLE, not a real entry" in text
        blocks = lane_state._blocks_below(text, ledger.ENTRIES_MARKER, book)
        ids = [item_id for item_id, _ in blocks]
        assert "LL-9999" not in ids
        assert "LL-0900" in ids

    def test_the_phantom_id_is_invisible_to_the_collision_check(self, tmp_path):
        book = _seed_ledger(tmp_path)
        path = self._fragment(tmp_path, self.QUOTES_AN_EXAMPLE)
        found = lane_state.duplicate_claims(ledger_path=book, fragments=[path])
        assert "LL-9999" not in found

    def test_a_fenced_example_cannot_collide_with_a_real_entry(self, tmp_path):
        # The sharp end: a quoted example carrying an id that IS already in the
        # ledger must not be reported as a collision, because it is not an
        # entry at all. A false collision blocks a legitimate integration.
        book = _seed_ledger(tmp_path)
        path = self._fragment(
            tmp_path,
            "### LL-0900 - 2026-08-12 - quotes a REAL id as an example\n\n"
            "**Evidence:**\n- like this:\n```\n"
            "### LL-0018 - 2026-08-09 - totally different text\n```\n",
        )
        assert lane_state.duplicate_claims(ledger_path=book, fragments=[path]) == {}
        assert lane_state.integrate(path, ledger_path=book) == ["LL-0900"]

    def test_the_body_of_a_fenced_example_stays_with_its_real_entry(self, tmp_path):
        path = self._fragment(tmp_path, self.QUOTES_AN_EXAMPLE)
        blocks = lane_state._fragment_blocks(path.read_text(encoding="utf-8"), path)
        assert [item_id for item_id, _ in blocks] == ["LL-0900"]
        assert "LL-9999" in blocks[0][1]


class TestTheIdShapeIsNotAssumedToBeLLNNNN:
    """Also from the refutation pass: six id shapes dropped silently.

    The first cut of the guard recognised an entry attempt by matching
    ``[A-Z]{2,6}-\\d{3,}``, which is what today's ids happen to look like. A
    malformed heading carrying any other shape failed BOTH the heading pattern
    and the id pattern, so it fell straight through into silence - the exact
    hole the guard was written to close, reopened by assuming the id format.

    `OPS-7` and `OPS-8` sit outside the original pattern, and `SAF-0001` exists
    in this repository's own history, so this is not hypothetical.
    """

    SHAPES = (
        "###  ll-0044 - 2026-08-12 - lowercase",
        "###  Ll-0044 - 2026-08-12 - mixed case",
        "###  L-0044 - 2026-08-12 - one letter",
        "###  LEDGERX-0044 - 2026-08-12 - seven letters",
        "###  LL-04 - 2026-08-12 - two digits",
        "###  LL0044 - 2026-08-12 - no hyphen",
        "###  OPS-7 - 2026-08-12 - a real id from this repo's own state files",
    )

    @pytest.mark.parametrize("heading", SHAPES)
    def test_a_malformed_heading_of_any_id_shape_is_refused(self, tmp_path, heading):
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n{heading}\n\n**Evidence:**\n- x\n",
            encoding="utf-8",
        )
        with pytest.raises(lane_state.MalformedLedgerHeading):
            lane_state.fragment_entry_ids(path)

    def test_prose_mentioning_an_id_is_NOT_a_false_positive(self, tmp_path):
        # The guard must fire on a heading that is TRYING to be an entry, not on
        # a sub-heading that merely cites one. A rule that cries wolf gets
        # switched off, and then the real collision passes too.
        path = tmp_path / "ops.LEDGER.md"
        path.write_text(
            "# Lane ledger fragment - ops\n\n"
            f"{lane_state.FRAGMENT_MARKER}\n\n"
            "### LL-0044 - 2026-08-12 - ordinary\n\n"
            "**Evidence:**\n- x\n\n"
            "#### Why LL-0031 was not enough\n\n"
            "#### Section 2 of the analysis\n",
            encoding="utf-8",
        )
        assert lane_state.fragment_entry_ids(path) == ["LL-0044"]


class TestDuplicateClaimsSurfacesTheHazardEarly:
    """See a collision BEFORE integrating, not as an exception during it."""

    def test_two_fragments_claiming_one_id_are_reported(self, tmp_path):
        book = _seed_ledger(tmp_path)
        ingest = tmp_path / "ingest.LEDGER.md"
        research = tmp_path / "research.LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "serialiser"), path=ingest)
        lane_state.append_fragment("research", _entry("LL-0023", "decode"), path=research)

        found = lane_state.duplicate_claims(ledger_path=book, fragments=[ingest, research])

        assert list(found) == ["LL-0023"]
        assert {claim.source for claim in found["LL-0023"]} == {ingest, research}
        rendered = lane_state.format_duplicate_claims(found)
        assert "LL-0023" in rendered
        assert "ingest.LEDGER.md" in rendered and "research.LEDGER.md" in rendered

    def test_an_already_integrated_entry_is_not_reported(self, tmp_path):
        # Fragments are not deleted after integration, so every integrated id
        # legitimately appears in two files. Reporting those would bury the one
        # real collision in noise, and a noisy report is one nobody reads.
        book = _seed_ledger(tmp_path)
        frag = tmp_path / "ingest.LEDGER.md"
        lane_state.append_fragment("ingest", _entry("LL-0023", "serialiser"), path=frag)
        lane_state.integrate(frag, book)

        assert lane_state.duplicate_claims(ledger_path=book, fragments=[frag]) == {}
        assert "no id" in lane_state.format_duplicate_claims({}).lower()

    def test_a_missing_fragment_is_not_an_error(self, tmp_path):
        book = _seed_ledger(tmp_path)
        assert lane_state.duplicate_claims(
            ledger_path=book, fragments=[tmp_path / "nope.md"]
        ) == {}

    def test_the_live_repository_has_no_colliding_id(self):
        # The wrap ritual's check, run as a test so a collision cannot reach a
        # merge unnoticed even if the ritual is skipped.
        found = lane_state.duplicate_claims()
        assert found == {}, lane_state.format_duplicate_claims(found)


class TestOwnershipMatchesTheRoster:
    def test_every_writing_lane_owns_its_own_lane_directory(self):
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            rel = lane_state.state_path(lane.lane_id).relative_to(lane_state.REPO_ROOT)
            assert lanes.owner_of(rel) == lane.lane_id, (
                f"{rel} must be owned by {lane.lane_id} alone - a lane state "
                "file with another owner reintroduces the shared-file race"
            )

    def test_one_lane_never_owns_another_lanes_state(self):
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            rel = lane_state.state_path(lane.lane_id).relative_to(lane_state.REPO_ROOT)
            others = [
                other.lane_id
                for other in lanes.LANES
                if other.lane_id != lane.lane_id and other.owns_path(rel)
            ]
            assert others == [], f"{rel} is also claimed by {others}"

    def test_the_fragment_is_owned_by_the_same_lane(self):
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            rel = lane_state.fragment_path(lane.lane_id).relative_to(lane_state.REPO_ROOT)
            assert lanes.owner_of(rel) == lane.lane_id

    def test_the_repository_ledger_is_still_owned_by_exactly_one_lane(self):
        # docs/LEDGER.md keeps a single writer - the integrator. Fragments exist
        # so that the other seven lanes never need to touch it.
        assert lanes.owner_of("docs/LEDGER.md") == "ops"


class TestReadOnlyRefusalCannotBeBypassedWithAPath:
    """Found by the refutation pass, and it was a real door left open.

    The refusal lived only in :func:`state_path` and :func:`fragment_path`, so
    every default route raised - and every route that took an explicit ``path``
    sailed straight past it. ``save(LaneState(lane_id="verify"), somewhere)``
    and ``append_fragment("verify", entry, path=somewhere)`` both wrote files,
    and ``load`` read one back. Eight entry points raising is not the same
    property as "verify writes nothing, ever", and only the second one is the
    guarantee that lets a read-only lane grade other lanes' work.
    """

    def test_save_refuses_a_read_only_lane_even_with_an_explicit_path(self, tmp_path):
        target = tmp_path / "verify.STATE.json"
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.save(lane_state.LaneState(lane_id="verify"), target)
        assert not target.exists(), "the refusal must happen BEFORE anything is written"

    def test_append_fragment_refuses_a_read_only_lane_even_with_an_explicit_path(self, tmp_path):
        target = tmp_path / "verify.LEDGER.md"
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.append_fragment("verify", _entry("LL-0100"), path=target)
        assert not target.exists()

    def test_load_refuses_a_read_only_lane_even_with_an_explicit_path(self, tmp_path):
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.load("verify", tmp_path / "anything.json")

    def test_the_open_item_helpers_refuse_a_read_only_lane_too(self, tmp_path):
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.add_open_item("verify", "X-1", "nope", path=tmp_path / "s.json")
        with pytest.raises(lane_state.ReadOnlyLane):
            lane_state.start_session("verify", "nope", tmp_path / "s.json")

    def test_a_writing_lane_is_still_allowed_a_path(self, tmp_path):
        # The refusal must be about read-only, not about passing a path at all.
        target = tmp_path / "ingest.STATE.json"
        lane_state.save(lane_state.LaneState(lane_id="ingest"), target)
        assert target.exists()


class TestIntegrationOrderIsActuallyChecked:
    """Also from the refutation pass: ``reversed()`` had ZERO coverage.

    ``integrate`` inserts oldest-first so the newest entry ends up on top, and
    every existing test used a single-entry fragment - so removing
    ``reversed()`` left the entire suite green. A docstring promise with no
    test behind it is decoration, which is exactly what this repository means
    by a vacuous guard.
    """

    def _seeded(self, tmp_path: Path) -> Path:
        book = tmp_path / "LEDGER.md"
        body = [
            "# Ledger",
            "",
            ledger.ENTRIES_MARKER,
            "",
            "### LL-0001 - 2026-08-01 - oldest",
            "",
            "**Evidence:**",
            "- seeded",
            "",
        ]
        book.write_text("\n".join(body), encoding="utf-8", newline="\n")
        return book

    def test_a_multi_entry_fragment_lands_newest_first(self, tmp_path):
        book = self._seeded(tmp_path)
        frag = tmp_path / "frag.md"
        for item in ("LL-0100", "LL-0101", "LL-0102"):
            lane_state.append_fragment("ingest", _entry(item), path=frag)
        assert lane_state.fragment_entry_ids(frag) == ["LL-0102", "LL-0101", "LL-0100"]

        assert lane_state.integrate(frag, book) == ["LL-0102", "LL-0101", "LL-0100"]
        text = book.read_text(encoding="utf-8")
        positions = [text.index(f"### {i}") for i in ("LL-0102", "LL-0101", "LL-0100", "LL-0001")]
        assert positions == sorted(positions), (
            "the repository ledger promises newest first - integrating a "
            f"multi-entry fragment broke that ordering: {positions}"
        )


def _skip_unless_git_is_installed() -> None:
    """Skip only when git is genuinely absent from the machine.

    Deliberately NOT "skip when the probe returns None". Those are different
    facts, and conflating them turns a broken probe into a green run - measured,
    by mutation, on the first version of this file.
    """
    try:
        proc = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=False
        )
    except OSError:  # pragma: no cover - git is present on this machine
        pytest.skip("git is not installed")
    if proc.returncode != 0:  # pragma: no cover - same
        pytest.skip("git is not installed")


class TestLaneStateIsVisibleToGit:
    """A state file git cannot see is a lane that silently resets to zero.

    Measured 2026-08-09, and it was live: ``.gitignore`` carries a bare
    ``capture/`` rule for directories of captured frames, and a bare pattern
    matches a directory of that name at ANY depth - so it swallowed
    ``lanes/capture/``, the capture lane's own state directory. The file was
    written, the seeding script reported success, and git never saw it.

    Nothing existing could have caught this. The orphan guard in
    ``tests/test_lanes.py`` walks ``git ls-files``, so a path git is ignoring
    is invisible to the exact check meant to notice an unowned file - the
    blind spot and the bug were the same shape. This class asks git directly
    instead.

    The bug had a second layer worth recording, because it is the reason the
    first fix looked applied and was not: the negation lines were written with
    CRLF endings while the rest of the file was LF, so each pattern carried a
    trailing carriage return and matched nothing at all. ``.gitignore`` read
    back as correct. Only the byte count showed it.

    Do not probe this with ``git check-ignore``. Measured while writing this
    class: ``check-ignore -q`` exits 0 when ANY pattern matches the path,
    **including a negation**, so a correctly re-included file reports exactly
    like an excluded one and the test passes or fails for the wrong reason.
    The question that matters is not "did a pattern match" but "will git take
    this file", so that is what is asked - a path is acceptable when git lists
    it as tracked, or as untracked-and-not-excluded.
    """

    def _git_lines(self, *args: str) -> list[str] | None:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            return None
        return [line.replace("\\", "/") for line in proc.stdout.splitlines() if line]

    def _acceptable(self) -> set[str] | None:
        tracked = self._git_lines("ls-files")
        untracked = self._git_lines("ls-files", "--others", "--exclude-standard")
        if tracked is None or untracked is None:
            return None
        return set(tracked) | set(untracked)

    def test_the_probe_itself_can_tell_an_ignored_path_from_a_kept_one(self):
        # Without this, both tests below would pass vacuously on any machine
        # where git declines to answer.
        acceptable = self._acceptable()
        if acceptable is None:
            pytest.skip("git unavailable")
        assert "ops/lanes.py" in acceptable, "git is not listing a file it tracks"
        assert not any(p.endswith(".pyc") for p in acceptable), (
            "compiled bytecode is excluded, so this probe should never see it - "
            "if it does, the probe is not measuring exclusion at all"
        )

    def _assert_git_would_take(self, chooser) -> None:
        # Asks lanes.git_would_take rather than keeping a second notion of
        # visibility. The `and Path(...).exists()` this replaced is `OPS-3` and
        # `OPS-5`: it skipped every lane whose file was not yet on disk, so the
        # fragment half was checking four of seven and reporting green.
        _skip_unless_git_is_installed()
        missing = []
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            rel = (
                chooser(lane.lane_id)
                .relative_to(lane_state.REPO_ROOT)
                .as_posix()
            )
            if lanes.git_would_take(rel) is False:
                missing.append(rel)
        assert not missing, (
            "git will not take these files, so the lanes owning them silently "
            "reset to zero every session and nothing warns:\n  "
            + "\n  ".join(missing)
        )

    def test_git_would_take_every_writing_lanes_state_file(self):
        self._assert_git_would_take(lane_state.state_path)

    def test_git_would_take_every_writing_lanes_ledger_fragment(self):
        self._assert_git_would_take(lane_state.fragment_path)


class TestVisibilityIsCheckedForPathsThatDoNotExistYET:
    """`OPS-3` and `OPS-5`. The guard above skips what is not on disk.

    Fragments are created lazily on a lane's first entry, so most lanes have
    none - measured at the time of this fix, **four of seven** existed. The
    guard's `and Path(...).exists()` therefore skipped three lanes entirely and
    still reported green. A guard that silently checks half its subjects is the
    shape this repository keeps paying for.

    The same blindness covers `OPS-5`'s second half: a rule added to
    `.gitignore` AFTER a file is tracked leaves the file listed, so a
    listing-based probe cannot see it either.

    Both are answered by asking git about the RULE rather than about the
    listing - see `ops.lanes.git_would_take`, and note that its exit code is
    deliberately not the answer, because `check-ignore` exits 0 on a negation
    too.
    """

    def _skip_without_git(self):
        """Skip ONLY when git itself is missing - never when the probe breaks.

        Caught by mutation: the first version skipped whenever
        `git_would_take` returned None, so breaking the probe turned every test
        in this class from a failure into a SKIP. `1094 passed, 7 skipped` reads
        green. A guard that stands down when the thing it guards breaks is not
        a guard, and this repository has been bitten by that shape before.

        So availability is measured independently, and a None from the probe on
        a machine that HAS git is a real failure below.
        """
        _skip_unless_git_is_installed()

    def test_the_probe_tells_a_kept_path_from_an_excluded_one(self):
        # Non-vacuity first: a probe that answered True to everything, or None
        # to everything, would make every assertion below meaningless.
        self._skip_without_git()
        assert lanes.git_would_take("ops/lanes.py") is True
        assert lanes.git_would_take("ops/never_written.pyc") is False

    def test_the_probe_reads_a_NEGATION_as_kept(self):
        # The documented trap, pinned. This path is re-included by an explicit
        # `!` rule and `check-ignore` still exits 0 for it.
        self._skip_without_git()
        assert lanes.git_would_take("tests/fixtures/gvas/standalone_slot.gvas.b64") is True

    def test_the_probe_answers_for_a_path_that_does_not_exist(self):
        self._skip_without_git()
        absent = Path(lane_state.REPO_ROOT) / "lanes" / "nosuchlane.LEDGER.md"
        assert not absent.exists(), "this probe needs a path that is really absent"
        assert lanes.git_would_take("lanes/nosuchlane.LEDGER.md") is True

    def test_every_writing_lane_is_checked_not_only_the_ones_with_files(self):
        """The fix, stated as a count rather than as a hope."""
        self._skip_without_git()
        writing = [lane for lane in lanes.LANES if not lane.read_only]
        refused = []
        for lane in writing:
            for chooser in (lane_state.state_path, lane_state.fragment_path):
                rel = chooser(lane.lane_id).relative_to(lane_state.REPO_ROOT).as_posix()
                if lanes.git_would_take(rel) is False:
                    refused.append(rel)
        assert not refused, (
            "git would REFUSE these lane files, so the lane silently resets to "
            "zero every session and nothing warns:\n  " + "\n  ".join(refused)
        )
        assert len(writing) == 7, "roster changed - re-read this test's premise"

    def test_a_lane_fragment_that_does_not_exist_is_still_checked(self):
        # The specific regression. Pick a writing lane with no fragment on disk
        # and assert the probe still has an opinion about it.
        self._skip_without_git()
        absent = [
            lane
            for lane in lanes.LANES
            if not lane.read_only and not lane_state.fragment_path(lane.lane_id).exists()
        ]
        if not absent:
            pytest.skip("every lane has a fragment now - the gap closed itself")
        for lane in absent:
            rel = lane_state.fragment_path(lane.lane_id).relative_to(
                lane_state.REPO_ROOT
            ).as_posix()
            assert lanes.git_would_take(rel) is True, rel


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _new_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "lane@example.invalid")
    _git(root, "config", "user.name", "Lane Test")
    # core.hooksPath is local config and is not inherited, so no repository hook
    # fires in here. That is deliberate: this test is about merge behaviour.
    return root


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


@pytest.mark.slow
class TestSharedLedgerRacesAndFragmentsDoNot:
    """The differential that justifies the whole fragment design.

    Both halves run real git merges. The first half is the status quo and is
    expected to CONFLICT - if it ever stops conflicting, the second half is no
    longer proving anything and this file should be revisited rather than
    trusted.
    """

    def _seed(self, repo: Path) -> None:
        book = repo / "LEDGER.md"
        book.write_text(
            f"# Ledger\n\n{ledger.ENTRIES_MARKER}\n\n"
            "### LL-0001 - 2026-08-01 - the entry that was already there\n\n"
            "**Evidence:**\n- seeded\n",
            encoding="utf-8",
        )
        _commit_all(repo, "seed")

    def test_two_branches_appending_to_one_shared_ledger_conflict(self, tmp_path):
        repo = _new_repo(tmp_path / "shared")
        self._seed(repo)
        book = repo / "LEDGER.md"

        for branch, item in (("lane/a", "LL-0100"), ("lane/b", "LL-0101")):
            _git(repo, "checkout", "-b", branch, "main")
            ledger.append_entry(_entry(item, f"work from {branch}"), book)
            _commit_all(repo, f"{branch} ledgers {item}")

        _git(repo, "checkout", "main")
        assert _git(repo, "merge", "--no-edit", "lane/a").returncode == 0
        second = _git(repo, "merge", "--no-edit", "lane/b")

        assert second.returncode != 0, (
            "two lanes appending at the same anchor in one shared ledger were "
            "expected to conflict - if git now merges this cleanly, the "
            "fragment design's justification has changed and needs re-measuring"
        )
        # Match git's own marker line, not the bare word: git's advice text
        # says "fix conflicts", which an uppercased substring check also
        # matches, so the loose form could pass on a non-conflict message.
        assert "CONFLICT (" in (second.stdout + second.stderr), (
            "expected git to report a real content conflict, got: "
            + second.stdout
            + second.stderr
        )
        _git(repo, "merge", "--abort")

    def test_two_branches_appending_to_their_own_fragments_merge_cleanly(self, tmp_path):
        repo = _new_repo(tmp_path / "fragments")
        self._seed(repo)
        (repo / "lanes").mkdir()
        _commit_all(repo, "add lanes dir")

        for branch, lane_id, item in (("lane/a", "a", "LL-0100"), ("lane/b", "b", "LL-0101")):
            _git(repo, "checkout", "-b", branch, "main")
            frag = repo / "lanes" / f"{lane_id}.LEDGER.md"
            frag.parent.mkdir(parents=True, exist_ok=True)
            lane_state.append_fragment("ingest", _entry(item, f"work from {branch}"), path=frag)
            _commit_all(repo, f"{branch} ledgers {item}")

        _git(repo, "checkout", "main")
        first = _git(repo, "merge", "--no-edit", "lane/a")
        second = _git(repo, "merge", "--no-edit", "lane/b")

        assert first.returncode == 0, first.stdout + first.stderr
        assert second.returncode == 0, (
            "per-lane fragments are disjoint files and must merge without a "
            "conflict:\n" + second.stdout + second.stderr
        )
        assert (repo / "lanes" / "a.LEDGER.md").exists()
        assert (repo / "lanes" / "b.LEDGER.md").exists()

    def test_the_integrator_then_folds_both_fragments_into_one_ledger(self, tmp_path):
        # The fragments merged cleanly; a single writer on main composes them.
        repo = _new_repo(tmp_path / "integrate")
        self._seed(repo)
        book = repo / "LEDGER.md"
        moved = []
        for lane_id, item in (("a", "LL-0100"), ("b", "LL-0101")):
            frag = repo / "lanes" / f"{lane_id}.LEDGER.md"
            frag.parent.mkdir(parents=True, exist_ok=True)
            lane_state.append_fragment("ingest", _entry(item), path=frag)
            moved.extend(lane_state.integrate(frag, book))

        assert moved == ["LL-0100", "LL-0101"]
        text = book.read_text(encoding="utf-8")
        for item in ("LL-0001", "LL-0100", "LL-0101"):
            assert f"### {item}" in text
