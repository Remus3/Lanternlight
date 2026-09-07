"""Guards for :mod:`ops.lane_slot` - the reserved-floor lane governor.

The module re-implements a cross-project concurrency protocol that sibling
repositories on this machine describe on the ``moon_sync_inbox/`` channel. The
protocol is a wire format, not a dependency: nothing is vendored, nothing is
imported from a sibling tree, and the only thing deliberately held in common is
the lock namespace shape, the key strings and the payload shape.

Every test here exists because the corresponding behaviour has a way of failing
SILENTLY. A governor that hands two callers the same slot, a floor that a busy
sibling can starve, a reap that cannot see reserved locks, and a default root
that quietly enrols this repository in a bucket other trees are rationing all
present as "busy" or as "fine" rather than as an error.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lane_slot  # noqa: E402


@pytest.fixture
def bucket(tmp_path: Path) -> Path:
    """An empty slot bucket that no sibling shares."""
    root = tmp_path / "slots"
    root.mkdir()
    return root


def _acquire(bucket: Path, key: str, **kw):
    kw.setdefault("repo", f"C:\\{key}-tree")
    kw.setdefault("run_id", "run-1")
    kw.setdefault("cycle", 1)
    return lane_slot.try_acquire(bucket, key, **kw)


class TestProtocolConstants:
    """The wire format is the whole point of interoperating, so pin it.

    These are the strings a sibling's governor also computes. A typo here does
    not fail loudly - it produces a private bucket that looks healthy and
    bounds nothing, which is the exact failure the channel keeps re-learning.
    """

    def test_this_repository_key_is_ll(self):
        assert lane_slot.REPO_KEY == "ll"

    def test_the_key_set_is_the_five_agreed_short_codes(self):
        assert lane_slot.REPO_KEYS == ("rc", "lw", "rsc", "cs", "ll")

    def test_every_key_is_lowercase_with_no_space_and_no_path_separator(self):
        for key in lane_slot.REPO_KEYS:
            assert key == key.lower()
            assert " " not in key
            assert "\\" not in key and "/" not in key

    def test_reserved_names_carry_the_key_not_an_index(self):
        assert lane_slot.reserved_name("ll") == "reserved-ll.lock"
        assert lane_slot.reserved_name("rc") == "reserved-rc.lock"

    def test_surplus_names_are_zero_based_indices(self):
        assert lane_slot.surplus_names(2) == ("0.lock", "1.lock")

    def test_the_stale_arm_is_four_and_a_half_hours(self):
        assert lane_slot.STALE_SECONDS == 16200.0


class TestSlotOrder:
    """Own floor first, surplus second. The order IS the guarantee."""

    def test_own_reserved_slot_is_tried_before_any_surplus(self):
        order = lane_slot.slot_order("ll", surplus=2)
        assert order[0] == "reserved-ll.lock"
        assert order[1:] == ("0.lock", "1.lock")

    def test_no_other_repos_reserved_slot_is_ever_tried(self):
        order = lane_slot.slot_order("ll", surplus=2)
        for key in lane_slot.REPO_KEYS:
            if key != "ll":
                assert lane_slot.reserved_name(key) not in order


class TestPayload:
    """The payload shape is shared; the reader must survive a partial one."""

    def test_payload_carries_the_five_observed_fields(self, bucket: Path):
        held = _acquire(bucket, "ll", repo="C:\\Lanternlight", run_id="r7", cycle=3)
        assert held is not None
        body = json.loads(held.path.read_text(encoding="utf-8"))
        assert body["pid"] == os.getpid()
        assert body["repo"] == "C:\\Lanternlight"
        assert body["run_id"] == "r7"
        assert body["cycle"] == 3
        assert isinstance(body["ts"], (int, float))

    def test_a_payload_missing_ts_is_treated_as_stale_not_as_fresh(self):
        # Omit rather than guess: an absent timestamp is not "now".
        assert lane_slot.is_stale({"pid": os.getpid()}, now=time.time()) is True

    def test_an_unparseable_payload_is_treated_as_stale(self, bucket: Path):
        orphan = bucket / "0.lock"
        orphan.write_text("{not json", encoding="utf-8")
        assert lane_slot.reap(bucket) == ["0.lock"]
        assert not orphan.exists()

    def test_a_recent_payload_from_a_live_pid_is_not_stale(self):
        payload = {"pid": os.getpid(), "ts": time.time()}
        assert lane_slot.is_stale(payload, now=time.time()) is False


class TestMutualExclusion:
    """The one property with no fallback - two holders of one slot."""

    def test_a_second_acquirer_never_receives_a_slot_already_held(self, bucket: Path):
        first = _acquire(bucket, "ll")
        second = _acquire(bucket, "ll")
        assert first is not None
        assert second is not None
        assert first.name != second.name

    def test_the_bucket_hands_out_at_most_width_slots(self, bucket: Path):
        held = [_acquire(bucket, "ll", surplus=2) for _ in range(3)]
        assert all(h is not None for h in held)
        assert len({h.name for h in held}) == 3
        # Own floor (1) plus surplus (2) is the whole bucket for this key.
        assert _acquire(bucket, "ll", surplus=2) is None

    def test_a_held_slot_is_not_reissued_after_a_failed_second_attempt(
        self, bucket: Path
    ):
        first = _acquire(bucket, "ll", surplus=0)
        assert first is not None
        assert _acquire(bucket, "ll", surplus=0) is None
        body = json.loads(first.path.read_text(encoding="utf-8"))
        assert body["run_id"] == "run-1"


class TestReservedFloor:
    """The guarantee: a repo starved of surplus still gets its own lane."""

    def test_a_repo_gets_its_floor_with_every_surplus_slot_taken(self, bucket: Path):
        for name in lane_slot.surplus_names(2):
            (bucket / name).write_text(
                lane_slot.encode_payload(
                    pid=os.getpid(), repo="C:\\other", run_id="x", cycle=0
                ),
                encoding="utf-8",
            )
        held = _acquire(bucket, "ll", surplus=2)
        assert held is not None
        assert held.reserved is True
        assert held.name == "reserved-ll.lock"

    def test_a_repo_can_never_hold_two_reserved_slots(self, bucket: Path):
        first = _acquire(bucket, "ll", surplus=2)
        second = _acquire(bucket, "ll", surplus=2)
        assert first is not None and second is not None
        assert first.reserved is True
        assert second.reserved is False

    def test_another_repos_floor_is_untouched_when_surplus_is_exhausted(
        self, bucket: Path
    ):
        for _ in range(3):
            _acquire(bucket, "ll", surplus=2)
        assert not (bucket / "reserved-rc.lock").exists()


class TestUnknownKeyRefuses:
    """A silent fallback to surplus presents exactly as "busy"."""

    def test_an_unknown_key_raises_rather_than_taking_surplus(self, bucket: Path):
        with pytest.raises(lane_slot.UnknownRepoKey):
            _acquire(bucket, "riot-commander")
        assert list(bucket.iterdir()) == []

    def test_the_refusal_names_the_key_and_the_set_it_was_checked_against(
        self, bucket: Path
    ):
        with pytest.raises(lane_slot.UnknownRepoKey) as excinfo:
            _acquire(bucket, "C:\\Lanternlight")
        message = str(excinfo.value)
        # The key is quoted with repr so a stray space or newline in it is
        # visible rather than invisible, so the raw spelling is escaped.
        assert repr("C:\\Lanternlight") in message
        assert "Lanternlight" in message
        for key in lane_slot.REPO_KEYS:
            assert key in message

    def test_a_full_path_spelling_of_our_own_repo_is_rejected(self, bucket: Path):
        # The near-miss the siblings measured: three spellings of one repo
        # become three reservations.
        with pytest.raises(lane_slot.UnknownRepoKey):
            _acquire(bucket, "C:\\Lanternlight")


class TestIdentityNotPath:
    """A repository rename must not move the reservation."""

    def test_the_slot_name_does_not_depend_on_the_repository_path(self):
        assert lane_slot.slot_order("ll", surplus=2) == lane_slot.slot_order(
            "ll", surplus=2
        )
        assert "Lanternlight" not in "".join(lane_slot.slot_order("ll", surplus=2))

    def test_a_renamed_root_still_holds_the_same_reservation(self, bucket: Path):
        held = _acquire(bucket, "ll", repo="C:\\Lanternlight", surplus=2)
        assert held is not None and held.name == "reserved-ll.lock"

        # The repository is renamed on disk mid-run. Identity is unchanged, so
        # the same reservation is still the one this repo holds, and a second
        # acquire under the new path must NOT be granted a second floor.
        after = _acquire(bucket, "ll", repo="C:\\Lanternlight-renamed", surplus=2)
        assert after is not None
        assert after.reserved is False
        assert (bucket / "reserved-ll.lock").exists()
        body = json.loads((bucket / "reserved-ll.lock").read_text(encoding="utf-8"))
        assert body["repo"] == "C:\\Lanternlight"

    def test_default_root_does_not_change_when_the_working_directory_moves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        before = lane_slot.default_root()
        monkeypatch.chdir(tmp_path)
        assert lane_slot.default_root() == before


class TestReap:
    """Both naming schemes, or a repo loses its floor for four and a half hours."""

    def _plant(self, bucket: Path, name: str, *, age: float, pid: int) -> Path:
        path = bucket / name
        body = json.loads(
            lane_slot.encode_payload(pid=pid, repo="C:\\x", run_id="x", cycle=0)
        )
        body["ts"] = time.time() - age
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def test_a_stale_reserved_lock_is_reclaimed(self, bucket: Path):
        planted = self._plant(
            bucket, "reserved-ll.lock", age=lane_slot.STALE_SECONDS + 60, pid=os.getpid()
        )
        assert lane_slot.reap(bucket) == ["reserved-ll.lock"]
        assert not planted.exists()

    def test_the_floor_is_acquirable_again_after_reaping_a_stale_reserved_lock(
        self, bucket: Path
    ):
        self._plant(
            bucket, "reserved-ll.lock", age=lane_slot.STALE_SECONDS + 60, pid=os.getpid()
        )
        assert _acquire(bucket, "ll", surplus=0) is None
        lane_slot.reap(bucket)
        held = _acquire(bucket, "ll", surplus=0)
        assert held is not None and held.name == "reserved-ll.lock"

    def test_a_stale_surplus_lock_is_reclaimed(self, bucket: Path):
        self._plant(bucket, "0.lock", age=lane_slot.STALE_SECONDS + 60, pid=os.getpid())
        assert lane_slot.reap(bucket) == ["0.lock"]

    def test_a_fresh_lock_is_never_reaped(self, bucket: Path):
        planted = self._plant(bucket, "reserved-ll.lock", age=1.0, pid=os.getpid())
        assert lane_slot.reap(bucket) == []
        assert planted.exists()

    def test_reap_ignores_files_that_are_not_slot_locks(self, bucket: Path):
        stray = bucket / "notes.txt"
        stray.write_text("hello", encoding="utf-8")
        assert lane_slot.reap(bucket) == []
        assert stray.exists()

    def test_reap_on_an_absent_bucket_is_not_an_error(self, tmp_path: Path):
        assert lane_slot.reap(tmp_path / "never-created") == []


class TestRelease:
    """A release that only LOOKS like it happened is the leak the siblings hit."""

    def test_release_removes_the_lock_and_reports_true(self, bucket: Path):
        held = _acquire(bucket, "ll")
        assert held is not None
        assert lane_slot.release(held) is True
        assert not held.path.exists()

    def test_release_reports_false_when_the_lock_cannot_be_removed(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        held = _acquire(bucket, "ll")
        assert held is not None

        def _refuse(self):  # pragma: no cover - the raise is the point
            raise PermissionError(32, "in use by another process")

        monkeypatch.setattr(Path, "unlink", _refuse)
        assert lane_slot.release(held, retries=2, backoff=0.0) is False

    def test_an_undeletable_lock_is_neutralised_so_the_stale_arm_fires_now(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        held = _acquire(bucket, "ll")
        assert held is not None

        def _refuse(self):  # pragma: no cover - the raise is the point
            raise PermissionError(32, "in use by another process")

        monkeypatch.setattr(Path, "unlink", _refuse)
        lane_slot.release(held, retries=1, backoff=0.0)
        monkeypatch.undo()

        body = json.loads(held.path.read_text(encoding="utf-8"))
        assert lane_slot.is_stale(body, now=time.time()) is True
        assert lane_slot.reap(bucket) == [held.name]

    def test_hold_releases_on_the_way_out(self, bucket: Path):
        with lane_slot.hold(bucket, "ll", repo="C:\\x", run_id="r", cycle=0) as held:
            assert held is not None
            assert held.path.exists()
        assert not held.path.exists()

    def test_hold_releases_even_when_the_body_raises(self, bucket: Path):
        with pytest.raises(RuntimeError), lane_slot.hold(
            bucket, "ll", repo="C:\\x", run_id="r", cycle=0
        ) as held:
            path = held.path
            raise RuntimeError("boom")
        assert not path.exists()

    def test_hold_yields_none_rather_than_blocking_when_the_bucket_is_full(
        self, bucket: Path
    ):
        keep = [_acquire(bucket, "ll", surplus=1) for _ in range(2)]
        assert all(k is not None for k in keep)
        with lane_slot.hold(
            bucket, "ll", repo="C:\\x", run_id="r", cycle=0, surplus=1
        ) as held:
            assert held is None


class TestLockRootIsOurs:
    """Where our bucket lives is a DECISION, pinned here.

    A sibling reports that the shared module defaults its root to a machine-wide
    ``ProgramData`` bucket that several trees ration between themselves. Taking
    that default unilaterally would consume a slot those trees are sharing -
    a change to another tree, made without asking. Our default root is inside
    this repository. See ADR-007.
    """

    def test_the_default_root_is_inside_this_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        root = lane_slot.default_root()
        assert REPO_ROOT in root.parents or root == REPO_ROOT

    def test_the_default_root_is_not_under_programdata(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        parts = [part.lower() for part in lane_slot.default_root().parts]
        assert "programdata" not in parts

    def test_no_shared_bucket_path_is_written_into_the_module(self):
        source = (REPO_ROOT / "ops" / "lane_slot.py").read_text(encoding="utf-8")
        lowered = source.lower()
        # Naming a sibling's live coordination root in code is how a default
        # quietly becomes a dependency. The concept may be discussed in prose;
        # the path may not appear as a value.
        assert "c:\\programdata" not in lowered
        assert "c:/programdata" not in lowered

    def test_the_root_is_overridable_by_environment_for_a_future_shared_bucket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(lane_slot.ROOT_ENV_VAR, str(tmp_path / "elsewhere"))
        assert lane_slot.default_root() == tmp_path / "elsewhere"

    def test_resolving_the_default_root_creates_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        target = tmp_path / "not-created"
        monkeypatch.setenv(lane_slot.ROOT_ENV_VAR, str(target))
        lane_slot.default_root()
        assert not target.exists()


class TestNothingHappensAtImportTime:
    """A governor that acquires on import governs every session, invited or not."""

    def test_importing_the_module_creates_no_bucket_and_takes_no_slot(
        self, tmp_path: Path
    ):
        target = tmp_path / "import-probe"
        env = dict(os.environ)
        env[lane_slot.ROOT_ENV_VAR] = str(target)
        env["PYTHONPATH"] = str(REPO_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", "import ops.lane_slot as m; print(m.REPO_KEY)"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == "ll"
        assert not target.exists()

    def test_a_session_that_acquires_nothing_runs_with_the_namespace_absent(
        self, tmp_path: Path
    ):
        absent = tmp_path / "no-such-bucket"
        assert lane_slot.reap(absent) == []
        assert lane_slot.holders(absent) == {}
        assert not absent.exists()


class TestHolders:
    """Reading the bucket must not disturb it - the reader is how locks leak."""

    def test_holders_reports_each_live_lock_by_name(self, bucket: Path):
        held = _acquire(bucket, "ll", repo="C:\\Lanternlight", run_id="r9", cycle=4)
        assert held is not None
        report = lane_slot.holders(bucket)
        assert set(report) == {held.name}
        assert report[held.name]["run_id"] == "r9"

    def test_holders_leaves_the_lock_deletable(self, bucket: Path):
        held = _acquire(bucket, "ll")
        assert held is not None
        lane_slot.holders(bucket)
        assert lane_slot.release(held, retries=1, backoff=0.0) is True
