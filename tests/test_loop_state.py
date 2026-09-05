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

#: The real default-path function, captured before the autouse fixture below
#: replaces it. The one test that asserts on the live location calls this.
_REAL_DEFAULT_STATE_PATH = state_mod.default_state_path


@pytest.fixture(autouse=True)
def never_touch_the_live_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the module default at tmp_path for the duration of every test.

    ``load``, ``save``, ``credit`` and ``advance_cycle`` all fall back to
    :func:`default_state_path` when no ``path`` is given, and that is
    ``ops/runtime/loop_state.json`` - live state for a loop that may be running
    right now, gitignored, so a wrong write is not recoverable from git.

    Every test here passes an explicit path, but "every test remembers" is a
    convention, and a convention is not a guard. This makes an omission land in
    a temporary directory instead of on the running loop.
    """
    decoy = tmp_path / "decoy-runtime" / state_mod.STATE_FILENAME
    monkeypatch.setattr(state_mod, "default_state_path", lambda: decoy)


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
    # The REAL function, not the decoy the autouse fixture installs - this is
    # the one test that is about the live location.
    default = _REAL_DEFAULT_STATE_PATH()
    assert default.name == state_mod.STATE_FILENAME
    assert default.parent == state_mod.runtime_dir()
    assert default.parent.parent.name == "ops"


def test_the_live_state_file_is_never_the_default_during_tests(tmp_path: Path) -> None:
    """Prove the autouse guard is armed rather than assuming it.

    A safety fixture that silently stopped applying would look exactly like a
    safe test suite right up until something wrote on the running loop.
    """
    patched = state_mod.default_state_path()
    assert patched != _REAL_DEFAULT_STATE_PATH()
    assert tmp_path in patched.parents

    # And the fallback really does follow it: a path-less write lands in tmp.
    state_mod.save(LoopState(cycle=1, item="decoy"), None)
    assert patched.exists()
    assert state_mod.load(None).item == "decoy"


def test_saved_payload_is_ascii(state_path: Path) -> None:
    # The repo is 7-bit ASCII by rule; a directive is free text, so the writer
    # escapes rather than emitting raw bytes. The accented character below is
    # built with chr() on purpose - this source file is itself ASCII-only.
    accented = "caf" + chr(0xE9)
    state_mod.save(LoopState(cycle=1, directive=accented), state_path)
    assert state_path.read_bytes().isascii()
    assert state_mod.load(state_path).directive == accented


def test_a_cycle_that_closes_two_items_credits_both(state_path: Path) -> None:
    """`OPS-25`, replayed exactly as it happened in cycle 43.

    The cycle went in with `OPS-19` in flight, closed it, picked up `OPS-22`
    mid-cycle and closed that too. `advance_cycle` knows only about the single
    in-flight item, so it credited `OPS-19` and silently lost `OPS-22`. The
    state file was repaired by hand - twice, because cycle 44 did it again with
    `OPS-21` and `OPS-23`.

    Under-crediting is the REDISCOVERY failure: a cold session reads `completed`
    to learn what is already done, so a lost id means the next session redoes
    closed work and never learns why.
    """
    state_mod.save(LoopState(cycle=43, directive="old", item="OPS-19"), state_path)

    # Mid-cycle, at the moment the second closure is known - not saved up for
    # the wrap, because a fact held in a context window is a fact already lost.
    state_mod.credit("OPS-22", path=state_path)

    advanced = state_mod.advance_cycle("cycle 44", "OPS-20", path=state_path)

    assert advanced.completed == ["OPS-22", "OPS-19"]
    assert advanced.cycle == 44, "the counter moves once for one cycle, not twice"

    reloaded = state_mod.load(state_path)
    assert reloaded.completed == ["OPS-22", "OPS-19"]
    assert reloaded.cycle == 44


def test_credit_does_not_move_the_cycle_counter(state_path: Path) -> None:
    """The acceptance criterion `OPS-25` states first, pinned on its own.

    A second closure must not cost a cycle. If crediting advanced the counter,
    a two-item cycle would read as two cycles and every later count - the
    directive chain, the ledger, the next-session prompt - would drift.
    """
    state_mod.save(LoopState(cycle=43, directive="d", item="OPS-19"), state_path)

    credited = state_mod.credit("OPS-22", path=state_path)

    assert credited.cycle == 43
    assert state_mod.load(state_path).cycle == 43


def test_credit_leaves_the_in_flight_item_and_directive_alone(state_path: Path) -> None:
    """Crediting a second closure says nothing about what is in flight."""
    state_mod.save(LoopState(cycle=43, directive="the live directive", item="OPS-19"), state_path)

    credited = state_mod.credit("OPS-22", path=state_path)

    assert credited.item == "OPS-19"
    assert credited.directive == "the live directive"
    reloaded = state_mod.load(state_path)
    assert reloaded.item == "OPS-19"
    assert reloaded.directive == "the live directive"


def test_credit_records_several_items_in_one_call(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=2, completed=["OPS-1"]), state_path)

    credited = state_mod.credit("OPS-2", "OPS-3", path=state_path)

    assert credited.completed == ["OPS-1", "OPS-2", "OPS-3"]
    assert state_mod.load(state_path).completed == ["OPS-1", "OPS-2", "OPS-3"]


def test_credit_never_records_an_item_twice(state_path: Path) -> None:
    """De-duplication, across calls and within one call.

    `completed` is a set in meaning and a list only so its order carries the
    sequence. A repeat says nothing new and makes the record look like the loop
    did an item twice.
    """
    state_mod.save(LoopState(cycle=2, completed=["OPS-1"]), state_path)

    state_mod.credit("OPS-1", path=state_path)
    state_mod.credit("OPS-2", "OPS-2", path=state_path)
    credited = state_mod.credit("OPS-2", path=state_path)

    assert credited.completed == ["OPS-1", "OPS-2"]


def test_credit_then_advance_does_not_double_credit_the_in_flight_item(
    state_path: Path,
) -> None:
    """Crediting the in-flight item early must not credit it again at the wrap.

    The durable-record argument cuts both ways: a merger that closes the
    in-flight item mid-cycle should be able to write that down immediately
    rather than hold it until the wrap. `advance_cycle`'s existing
    de-duplication is what stops the second credit, so it is pinned here
    against the new path rather than assumed to still cover it.
    """
    state_mod.save(LoopState(cycle=43, item="OPS-19"), state_path)

    state_mod.credit("OPS-19", path=state_path)
    advanced = state_mod.advance_cycle("next", "OPS-20", path=state_path)

    assert advanced.completed == ["OPS-19"]
    assert advanced.cycle == 44


def test_crediting_a_different_item_leaves_the_retry_rule_intact(
    state_path: Path,
) -> None:
    """`OPS-7` under the new path - the guarantee this item must not break.

    A cycle that closed a second item and is CARRYING the first one forward
    must credit only the second. If `credit` had loosened the retry rule, the
    carried item would appear finished and the next cold session would skip it.
    """
    state_mod.save(LoopState(cycle=43, item="OPS-19"), state_path)

    state_mod.credit("OPS-22", path=state_path)
    advanced = state_mod.advance_cycle("carry it forward", "OPS-19", path=state_path)

    assert advanced.completed == ["OPS-22"], "the carried item must not be credited"
    assert advanced.item == "OPS-19"
    assert advanced.cycle == 44
    assert state_mod.load(state_path).completed == ["OPS-22"]


def test_credit_survives_a_session_that_dies_before_its_wrap(state_path: Path) -> None:
    """The whole reason this is a separate call and not a wrap argument.

    The state on disk after `credit` and before `advance_cycle` already carries
    the second closure. A wrap-time argument would have lost it here, which is
    exactly where cycles 43 and 44 lost theirs.
    """
    state_mod.save(LoopState(cycle=43, item="OPS-19"), state_path)

    state_mod.credit("OPS-22", path=state_path)
    # No advance_cycle. Pretend the session ended right here.

    cold = state_mod.load(state_path)
    assert cold.completed == ["OPS-22"]
    assert cold.cycle == 43
    assert cold.item == "OPS-19"


def test_credit_refuses_a_non_string_id_and_writes_nothing(state_path: Path) -> None:
    """A non-string id does not add a bad row - it destroys the whole record.

    Measured, not reasoned: `save` does not validate `completed`, so an int id
    serialises fine, but `LoopState.from_dict` rejects the list wholesale and
    `load` falls back to a fresh default. The completion record comes back
    EMPTY and the cycle counter comes back 0. So the check has to happen before
    anything is written, and a rejected call has to leave the file untouched.
    """
    state_mod.save(LoopState(cycle=43, item="OPS-19", completed=["OPS-1"]), state_path)
    before = state_path.read_bytes()

    with pytest.raises(TypeError, match="must be strings"):
        state_mod.credit("OPS-22", 19, path=state_path)

    assert state_path.read_bytes() == before, "a rejected call must not half-apply"
    reloaded = state_mod.load(state_path)
    assert reloaded.completed == ["OPS-1"], "the good id in the same call is not written either"
    assert reloaded.recovered is False


def test_a_non_string_id_really_would_destroy_the_record(state_path: Path) -> None:
    """The measurement the test above rests on, run rather than asserted.

    Without this, "the type check is load-bearing" is just a confident
    sentence. This writes the state `credit` refuses to write and shows what
    the next cold session would have read.
    """
    poisoned = LoopState(cycle=43, item="OPS-19", completed=["OPS-1", 19])
    state_mod.save(poisoned, state_path)

    assert json.loads(state_path.read_text(encoding="utf-8"))["completed"] == ["OPS-1", 19]

    cold = state_mod.load(state_path)
    assert cold.completed == [], "one bad id empties the entire completion record"
    assert cold.cycle == 0, "and resets the cycle counter"
    assert cold.recovered is True


def test_credit_refuses_an_empty_id(state_path: Path) -> None:
    state_mod.save(LoopState(cycle=1, completed=["OPS-1"]), state_path)
    before = state_path.read_bytes()

    for blank in ("", "   ", "\t"):
        with pytest.raises(ValueError, match="non-empty"):
            state_mod.credit(blank, path=state_path)

    assert state_path.read_bytes() == before


def test_credit_refuses_to_credit_nothing(state_path: Path) -> None:
    """`credit()` with no ids is a bug at the call site, not a no-op.

    Silently doing nothing is how a merger comes away believing it recorded a
    closure it did not record.
    """
    state_mod.save(LoopState(cycle=1), state_path)
    before = state_path.read_bytes()

    with pytest.raises(ValueError, match="at least one item id"):
        state_mod.credit(path=state_path)

    assert state_path.read_bytes() == before


def test_credit_stores_ids_verbatim(state_path: Path) -> None:
    """No stripping or normalising, because `advance_cycle` does not either.

    If the two paths disagreed about the stored form, the de-duplication that
    stops a double credit would stop matching.
    """
    state_mod.save(LoopState(cycle=1), state_path)

    credited = state_mod.credit("OPS-22 (partial)", path=state_path)

    assert credited.completed == ["OPS-22 (partial)"]


def test_credit_keeps_recovery_diagnostics_instead_of_clearing_them(
    state_path: Path,
) -> None:
    """Unlike `advance_cycle`, which clears them because it starts a new cycle.

    If the state file was unusable, this credit just landed on a fresh default
    whose `completed` list is empty. The caller has to be able to see that, and
    the returned state is the only place it shows.
    """
    state_path.write_text("{broken", encoding="utf-8")

    credited = state_mod.credit("OPS-22", path=state_path)

    assert credited.recovered is True
    assert "not valid JSON" in credited.recovery_note
    assert credited.completed == ["OPS-22"]


def test_credit_accepts_an_explicit_state_without_reading_disk(state_path: Path) -> None:
    """Symmetry with `advance_cycle`'s `state=` argument."""
    given = LoopState(cycle=9, directive="d", item="OPS-19", completed=["OPS-1"])

    credited = state_mod.credit("OPS-22", path=state_path, state=given)

    assert credited.completed == ["OPS-1", "OPS-22"]
    assert credited.cycle == 9
    assert state_mod.load(state_path).completed == ["OPS-1", "OPS-22"]


def test_credit_writes_atomically_like_every_other_writer(state_path: Path) -> None:
    """It goes through `save`, so it inherits temp-then-replace. Pinned, not assumed."""
    state_mod.save(LoopState(cycle=1), state_path)
    state_mod.credit("OPS-22", path=state_path)

    debris = list(state_path.parent.glob(state_mod.TEMP_PREFIX + "*"))
    assert debris == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["completed"] == ["OPS-22"]
