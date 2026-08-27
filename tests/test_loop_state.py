"""Tests for the on-disk loop state.

The properties that matter are the two the loop actually depends on: a write is
atomic, and a load never raises. Everything else here is round-trip cover.

Nothing in this module writes to ``ops/runtime/``. Every test is given an
explicit ``tmp_path``, because a test that scribbles on live runtime state is a
test that can break a running loop.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.loop import state as state_mod  # noqa: E402
from ops.loop.state import LoopState  # noqa: E402


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    """A state file path inside tmp_path. The file does not exist yet."""
    return tmp_path / "loop_state.json"


def test_load_missing_file_returns_default(state_path: Path) -> None:
    loaded = state_mod.load(state_path)

    assert loaded.cycle == 0
    assert loaded.directive == ""
    assert loaded.item is None
    assert loaded.completed == []
    # A first run is not a recovery, but it is still explained.
    assert loaded.recovered is False
    assert "no state file" in loaded.recovery_note
    assert not state_path.exists(), "load() must not create the file it reads"


def test_round_trip(state_path: Path) -> None:
    original = LoopState(
        cycle=7,
        directive="Land the GVAS reader, then ledger it.",
        item="LL-0004",
        completed=["LL-0001", "LL-0002", "LL-0003"],
    )

    written = state_mod.save(original, state_path)
    assert written == state_path

    loaded = state_mod.load(state_path)
    assert loaded.cycle == 7
    assert loaded.directive == "Land the GVAS reader, then ledger it."
    assert loaded.item == "LL-0004"
    assert loaded.completed == ["LL-0001", "LL-0002", "LL-0003"]
    assert loaded.recovered is False
    assert loaded.recovery_note == ""
    # save() stamps the timestamp so callers cannot forget to.
    assert loaded.updated.startswith("2"), loaded.updated

    # The diagnostics are load-time only and must not be persisted, or a
    # one-off recovery would look permanent on every later read.
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert "recovered" not in payload
    assert "recovery_note" not in payload


def test_round_trip_preserves_none_item(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=1, item=None), state_path)
    assert state_mod.load(state_path).item is None


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("truncated mid-write", '{"schema": 1, "cycle": 3, "direc'),
        ("empty file", ""),
        ("not json at all", "cycle=3\n"),
        ("json but not an object", "[1, 2, 3]"),
        ("object with wrong field types", '{"schema": 1, "cycle": "three"}'),
        ("negative cycle", '{"schema": 1, "cycle": -1}'),
        ("completed is not a list of strings", '{"schema": 1, "completed": [1, 2]}'),
        ("unknown schema", '{"schema": 99, "cycle": 3}'),
    ],
)
def test_corrupt_file_recovers_without_raising(state_path: Path, label: str, body: str) -> None:
    state_path.write_text(body, encoding="utf-8")

    loaded = state_mod.load(state_path)

    assert loaded.cycle == 0, label
    assert loaded.completed == [], label
    assert loaded.recovered is True, label
    assert loaded.recovery_note, f"{label}: a recovery must say what happened"
    assert str(state_path) in loaded.recovery_note, label


def test_corrupt_file_is_left_on_disk_for_inspection(state_path: Path) -> None:
    state_path.write_text("{broken", encoding="utf-8")
    state_mod.load(state_path)
    # load() diagnoses; it does not destroy the evidence.
    assert state_path.read_text(encoding="utf-8") == "{broken"


def test_save_goes_through_a_temp_file_and_never_truncates_the_target(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The target must never be observable in a partial state.

    A plain ``open(path, "w")`` truncates first, so a reader polling during the
    write sees an empty or half-written file. This asserts the temp-then-replace
    path instead: the source of the replace is a distinct temp file in the same
    directory, and at the instant of the replace the target still holds the
    complete previous document.
    """
    first = LoopState(cycle=1, directive="first", item="LL-0001")
    state_mod.save(first, state_path)
    before = state_path.read_text(encoding="utf-8")
    assert json.loads(before)["cycle"] == 1

    observed: list[dict] = []
    real_replace = Path.replace

    def spy_replace(self: Path, target: Path) -> Path:
        target_path = Path(target)
        observed.append(
            {
                "source": self,
                "target": target_path,
                # The temp file must already hold the complete new document.
                "source_contents": self.read_text(encoding="utf-8"),
                # What a concurrent reader would see at this instant.
                "target_contents": (
                    target_path.read_text(encoding="utf-8") if target_path.exists() else None
                ),
            }
        )
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", spy_replace)

    second = LoopState(cycle=2, directive="second", item="LL-0002")
    state_mod.save(second, state_path)

    assert len(observed) == 1, "exactly one atomic move per save"
    move = observed[0]

    # The write did not go to the target directly.
    assert move["target"] == state_path
    assert move["source"] != state_path
    assert move["source"].name.startswith(state_mod.temp_prefix_for(state_path))
    # Same directory, or the move would not be a rename and would not be atomic.
    assert move["source"].parent == state_path.parent
    # And the temp file already held the complete new document before the move.
    assert json.loads(move["source_contents"])["cycle"] == 2

    # The critical assertion: mid-write, the target was still the whole old
    # document - not empty, not truncated, not a prefix of the new one.
    assert move["target_contents"] == before
    assert json.loads(move["target_contents"])["cycle"] == 1

    assert json.loads(state_path.read_text(encoding="utf-8"))["cycle"] == 2


def test_save_leaves_no_temp_debris(state_path: Path) -> None:
    for cycle in range(3):
        state_mod.save(LoopState(cycle=cycle), state_path)

    leftovers = [p.name for p in state_path.parent.iterdir() if p != state_path]
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_save_creates_the_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "runtime" / "deeper" / "loop_state.json"
    state_mod.save(LoopState(cycle=1), nested)
    assert nested.exists()


def test_advance_cycle_increments_and_credits_the_finished_item(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=4, directive="old", item="LL-0009"), state_path)

    advanced = state_mod.advance_cycle("next directive", "LL-0010", path=state_path)

    assert advanced.cycle == 5
    assert advanced.directive == "next directive"
    assert advanced.item == "LL-0010"
    assert advanced.completed == ["LL-0009"]

    # It persisted, which is the entire point - the next session reads disk.
    reloaded = state_mod.load(state_path)
    assert reloaded.cycle == 5
    assert reloaded.item == "LL-0010"
    assert reloaded.completed == ["LL-0009"]


def test_advance_cycle_can_decline_to_credit_an_abandoned_item(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=1, item="LL-0009"), state_path)

    advanced = state_mod.advance_cycle(
        "retry", "LL-0009", complete_current=False, path=state_path
    )

    assert advanced.cycle == 2
    assert advanced.completed == []


def test_advance_cycle_does_not_duplicate_a_completed_item(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=1, item="LL-0009", completed=["LL-0009"]), state_path)
    advanced = state_mod.advance_cycle("onward", None, path=state_path)
    assert advanced.completed == ["LL-0009"]


def test_carrying_the_same_item_forward_is_a_retry_not_a_completion(
    state_path: Path,
) -> None:
    """`OPS-7`. The default must not manufacture a completion.

    Hit for real during the `LL-0048` wrap, and caught only because the return
    value happened to be printed and read. `advance_cycle(directive, item="7b")`
    defaults to `complete_current=True`, which credits the PREVIOUS cycle's
    in-flight item. When the previous item was also `7b` - the ordinary shape of
    "I did not get to this, carry it forward" - `7b` was recorded as finished
    with nothing done to it.

    `completed` is meant to be, in the docstring's own words, the honest answer
    to what the loop finished. A cold session reading `7b` there would skip the
    highest-value item on the roadmap and never learn why. That is a direct hit
    on the continuity design the whole project rests on, because continuity here
    lives on disk and nothing else remembers.

    Carrying an item forward is a retry. Only moving to a DIFFERENT item, or to
    none, says the previous one is done.
    """
    state_mod.save(LoopState(cycle=11, directive="old", item="7b"), state_path)

    advanced = state_mod.advance_cycle("carry it forward", "7b", path=state_path)

    assert advanced.completed == [], (
        "the item was carried forward, not finished - crediting it tells the "
        "next cold session to skip it"
    )
    assert advanced.cycle == 12, "a retry is still a cycle"
    assert advanced.item == "7b"
    assert advanced.directive == "carry it forward"

    # It has to be true on disk, because that is the only thing that survives.
    reloaded = state_mod.load(state_path)
    assert reloaded.completed == []
    assert reloaded.item == "7b"


def test_moving_to_a_different_item_still_credits_the_finished_one(
    state_path: Path,
) -> None:
    """The negative control for `OPS-7`.

    A fix that simply stopped crediting anything would pass the test above and
    destroy the record, so the ordinary case is pinned right beside it.
    """
    state_mod.save(LoopState(cycle=11, item="7b"), state_path)

    advanced = state_mod.advance_cycle("on to the next", "10", path=state_path)

    assert advanced.completed == ["7b"]
    assert advanced.item == "10"


def test_moving_to_no_item_still_credits_the_finished_one(state_path: Path) -> None:
    """Finishing an item and starting nothing is still finishing it."""
    state_mod.save(LoopState(cycle=3, item="4c"), state_path)

    advanced = state_mod.advance_cycle("nothing queued", None, path=state_path)

    assert advanced.completed == ["4c"]
    assert advanced.item is None


def test_carrying_forward_twice_never_credits_the_item(state_path: Path) -> None:
    """The real shape of the bug: an item carried across several cycles.

    One session carrying an item forward is the common case; three in a row is
    what actually happens when an item needs the game client and the client
    stays shut. If any single hop credits it, the item is lost for good - and
    the loop has no way to un-complete something.
    """
    state_mod.save(LoopState(cycle=1, item="10"), state_path)

    for cycle in (2, 3, 4):
        advanced = state_mod.advance_cycle(f"cycle {cycle}", "10", path=state_path)
        assert advanced.cycle == cycle
        assert advanced.completed == [], f"credited at cycle {cycle}"


def test_declining_to_credit_still_works_when_the_item_changes(
    state_path: Path,
) -> None:
    """`complete_current=False` stays the explicit escape hatch.

    `OPS-7` narrows the DEFAULT. It must not remove the caller's ability to say
    "this was abandoned" about an item they are also moving away from, which is
    the one case the new default cannot infer.
    """
    state_mod.save(LoopState(cycle=1, item="7b"), state_path)

    advanced = state_mod.advance_cycle(
        "abandoned, moving on", "10", complete_current=False, path=state_path
    )

    assert advanced.completed == []
    assert advanced.item == "10"


def test_advance_cycle_from_no_file_starts_at_one(state_path: Path) -> None:
    advanced = state_mod.advance_cycle("first directive", "LL-0001", path=state_path)
    assert advanced.cycle == 1
    assert advanced.completed == []
    assert advanced.recovered is False


def test_advance_cycle_clears_stale_recovery_diagnostics(state_path: Path) -> None:
    state_path.write_text("{broken", encoding="utf-8")
    advanced = state_mod.advance_cycle("recovered directive", "LL-0001", path=state_path)
    assert advanced.recovered is False
    assert advanced.recovery_note == ""


def test_default_paths_point_into_the_gitignored_runtime_dir() -> None:
    default = state_mod.default_state_path()
    assert default.name == state_mod.STATE_FILENAME
    assert default.parent == state_mod.runtime_dir()
    assert default.parent.parent.name == "ops"


def test_saved_payload_is_ascii(state_path: Path) -> None:
    # The repo is 7-bit ASCII by rule; a directive is free text, so the writer
    # escapes rather than emitting raw bytes. The accented character below is
    # built with chr() on purpose - this source file is itself ASCII-only.
    accented = "caf" + chr(0xE9)
    state_mod.save(LoopState(cycle=1, directive=accented), state_path)
    assert state_path.read_bytes().isascii()
    assert state_mod.load(state_path).directive == accented
