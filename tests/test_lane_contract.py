"""The generated lane contracts, and the drift guard that keeps them honest.

A contract file restates facts that already live in `ops/lanes.py` - which
paths a lane owns, which branch it commits to, whether it holds a veto. This
repository has repeatedly been bitten by a fact restated in a second place: the
copy goes stale, and a stale contract is worse than none because a lane will
believe it and write outside its slice.

So the contracts are generated, and the test that matters here is the last one:
what is on disk must equal what the roster renders right now. Widen a glob in
`ops/lanes.py` without regenerating and the build goes red.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lane_contract, lanes  # noqa: E402


class TestRenderedContent:
    def test_every_lane_renders_something_substantial(self):
        for lane in lanes.LANES:
            assert len(lane_contract.render(lane)) > 1500, lane.lane_id

    def test_the_mandate_appears_verbatim(self):
        for lane in lanes.LANES:
            assert lane.mandate in lane_contract.render(lane)

    def test_every_owned_pattern_is_listed(self):
        for lane in lanes.LANES:
            text = lane_contract.render(lane)
            for pattern in lane.owns:
                assert pattern in text, f"{lane.lane_id} omits {pattern}"

    def test_the_branch_and_worktree_are_named(self):
        # The worktree is named by DIRECTORY, not by absolute path - see
        # TestTheContractIsCheckoutIndependent for why an absolute path here
        # made the whole suite green only in place. Asserting the directory
        # name is the stronger check anyway: it catches a lane pointed at a
        # sibling's worktree, which comparing a full path also did, while
        # surviving a clone at any location.
        for lane in lanes.LANES:
            text = lane_contract.render(lane)
            assert lane.branch_name() in text
            if not lane.read_only:
                assert lane.worktree_path().name in text
                others = [
                    other.worktree_path().name
                    for other in lanes.LANES
                    if other.lane_id != lane.lane_id and not other.read_only
                ]
                assert not [name for name in others if name in text], lane.lane_id

    def test_never_merge_to_main_is_stated(self):
        for lane in lanes.LANES:
            assert "Never merge to" in lane_contract.render(lane)

    def test_the_anti_cheat_boundary_is_restated_in_every_contract(self):
        # A lane must not have to go looking for this one.
        for lane in lanes.LANES:
            text = lane_contract.render(lane)
            assert "Never touch the game process" in text
            assert "anti-cheat" in text.lower()

    def test_the_stop_conditions_are_pointed_at(self):
        for lane in lanes.LANES:
            assert "docs/HEADLESS.md" in lane_contract.render(lane)

    def test_the_no_suggestion_rule_is_stated(self):
        for lane in lanes.LANES:
            assert "Never file a suggestion" in lane_contract.render(lane)

    def test_a_veto_lane_says_so(self):
        text = lane_contract.render(lanes.by_id("safety"))
        assert "holds a veto" in text

    def test_a_read_only_lane_says_it_writes_nothing(self):
        text = lane_contract.render(lanes.by_id("verify"))
        assert "read-only" in text
        assert "owns no files" in text

    def test_a_read_only_lane_is_not_given_a_worktree(self):
        text = lane_contract.render(lanes.by_id("verify"))
        assert "no worktree" in text

    def test_a_writing_lane_is_told_to_assert_its_worktree(self):
        text = lane_contract.render(lanes.by_id("ingest"))
        assert "assert_in_lane_worktree" in text

    def test_the_merge_gate_is_referenced(self):
        for lane in lanes.LANES:
            assert "merge_gate" in lane_contract.render(lane)

    def test_no_contract_tells_a_lane_to_add_a_coauthor_trailer(self):
        for lane in lanes.LANES:
            text = lane_contract.render(lane)
            assert "Never add a `Co-Authored-By` trailer" in text


class TestTheContractIsCheckoutIndependent:
    """A committed generated file must not embed the generating machine's paths.

    `render()` used to interpolate `lanes.primary_checkout()`, an absolute path,
    into text that is then committed. The drift guard below compares the file on
    disk against a fresh render, so the two agreed only at `C:\\Lanternlight` and
    a fresh clone measured one failure - which is what `README.md` tells a new
    contributor to run. Every "N passed" this project has recorded was therefore
    an in-place number.

    The guard is behavioural rather than a substring check: move the checkout and
    the bytes must not move. That goes red for any path re-embedded later,
    including one nobody has thought of yet.
    """

    def test_rendering_does_not_change_when_the_checkout_moves(self, monkeypatch):
        before = {lane.lane_id: lane_contract.render(lane) for lane in lanes.LANES}
        monkeypatch.setattr(
            lanes, "primary_checkout", lambda *a, **k: Path("/elsewhere/Lanternlight")
        )
        for lane in lanes.LANES:
            assert lane_contract.render(lane) == before[lane.lane_id], lane.lane_id

    def test_rendering_does_not_change_when_the_worktree_root_moves(self, monkeypatch):
        before = {lane.lane_id: lane_contract.render(lane) for lane in lanes.LANES}
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", Path("/elsewhere/worktrees"))
        for lane in lanes.LANES:
            assert lane_contract.render(lane) == before[lane.lane_id], lane.lane_id

    def test_no_contract_names_the_checkout_directory(self):
        root = str(lanes.primary_checkout())
        for lane in lanes.LANES:
            assert root not in lane_contract.render(lane), lane.lane_id

    def test_no_contract_names_the_worktree_root(self):
        root = str(lanes.WORKTREE_ROOT)
        for lane in lanes.LANES:
            assert root not in lane_contract.render(lane), lane.lane_id

    def test_no_contract_contains_ANY_absolute_path(self):
        """Close the CLASS, not the two instances that happened to bite.

        A refutation pass showed the two tests above are not enough: they pin
        `primary_checkout()` and `WORKTREE_ROOT` specifically, so embedding some
        OTHER machine-specific path - `Path.home()` was the demonstration - left
        the suite green here while a checkout under a different user measured
        the 2d symptom again. Guarding the two known sources is not the same
        property as "no machine-specific path is ever committed", and only the
        second is what makes a clone-green claim durable.
        """
        absolute = re.compile(r"[A-Za-z]:[\\/]|(?<![\w.])/(?:home|Users|root|mnt|opt)/")
        for lane in lanes.LANES:
            found = absolute.findall(lane_contract.render(lane))
            assert not found, f"{lane.lane_id} embeds an absolute path: {found[:3]}"

    def test_that_absolute_path_guard_actually_matches_something(self):
        # An empty finding is a claim about the pattern, not about the file.
        absolute = re.compile(r"[A-Za-z]:[\\/]|(?<![\w.])/(?:home|Users|root|mnt|opt)/")
        for probe in (r"C:\Lanternlight", "C:/ll-worktrees", "/home/someone", "/Users/someone"):
            assert absolute.search(probe), probe


class TestAuthoringRules:
    def test_every_rendered_contract_is_pure_ascii(self):
        for lane in lanes.LANES:
            text = lane_contract.render(lane)
            bad = [(i, ch) for i, ch in enumerate(text) if ord(ch) > 127]
            assert not bad, f"{lane.lane_id}: non-ascii at {bad[:3]}"

    def test_rendering_is_deterministic(self):
        for lane in lanes.LANES:
            assert lane_contract.render(lane) == lane_contract.render(lane)


class TestOnDiskMatchesTheRoster:
    """The drift guard. This is why the contracts are generated at all."""

    def test_every_lane_has_a_contract_file(self):
        missing = [
            lane.lane_id
            for lane in lanes.LANES
            if not lane_contract.contract_path(lane).is_file()
        ]
        assert not missing, (
            f"lanes with no contract on disk: {missing} - run "
            "`python scripts/write_lane_contracts.py`"
        )

    def test_the_files_on_disk_equal_what_the_roster_renders(self):
        stale = []
        for lane in lanes.LANES:
            path = lane_contract.contract_path(lane)
            if not path.is_file():
                continue
            if path.read_text(encoding="utf-8") != lane_contract.render(lane):
                stale.append(lane.lane_id)
        assert not stale, (
            f"contracts out of sync with ops/lanes.py: {stale} - the roster "
            "changed without regenerating. Run "
            "`python scripts/write_lane_contracts.py`"
        )

    def test_write_all_is_idempotent(self, tmp_path):
        first = lane_contract.write_all(tmp_path)
        before = {p: p.read_bytes() for p in first}
        lane_contract.write_all(tmp_path)
        for path, data in before.items():
            assert path.read_bytes() == data

    def test_write_all_leaves_no_temp_files(self, tmp_path):
        lane_contract.write_all(tmp_path)
        assert not list(tmp_path.glob("*.tmp"))

    def test_contracts_are_written_with_lf_endings(self, tmp_path):
        for path in lane_contract.write_all(tmp_path):
            assert b"\r\n" not in path.read_bytes(), path
