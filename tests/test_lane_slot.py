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

import hashlib
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


class TestLockRootIsTheSharedBucket:
    """Where our bucket lives is a DECISION, pinned here.

    IT CHANGED. ADR-007 put the root inside this repository, and the two tests
    below asserted exactly that. The operator ruled in chat on 2026-09-10 -
    "yes, join the shared bucket" - and ADR-008 supersedes ADR-007, so the two
    assertions are INVERTED here rather than deleted: the default root is now
    the shared machine-wide bucket, and a regression back to the private one
    would be a silent withdrawal from the scheme that presents as everything
    working.

    The shared bucket is resolved through the all-users environment variable
    rather than written into the module as a drive-rooted literal, so the third
    test below is unchanged and still holds.
    """

    def test_the_default_root_is_the_shared_machine_wide_bucket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # The real all-users root is never touched by this suite. Pointing
        # PROGRAMDATA at tmp_path proves the resolution without going near a
        # directory another project's live loop is rationing.
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(tmp_path))
        root = lane_slot.default_root()
        assert root == tmp_path / lane_slot.SHARED_BUCKET_RELATIVE
        assert root != lane_slot.repo_local_root()
        assert REPO_ROOT not in root.parents

    def test_the_in_repository_bucket_is_the_fallback_when_there_is_no_shared_root(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.delenv(lane_slot.PROGRAMDATA_ENV_VAR, raising=False)
        assert lane_slot.shared_root() is None
        root = lane_slot.default_root()
        assert root == lane_slot.repo_local_root()
        assert REPO_ROOT in root.parents

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


class TestSharedBucketShape:
    """Detection answers THREE things, not two, and looks rather than believes.

    The operator ruled on 2026-09-10 that this repository joins the shared
    machine-wide bucket. A naive join - point the root at it and keep the
    reserved-first order - would create ``reserved-ll.lock`` on essentially
    every acquire, in a bucket whose participants today run a first-come
    surplus scheme with no reserved names in it at all. That file is one no
    sibling's reaper recognises, and it also means we would never contend for
    surplus, so we would not ration with anybody. See ADR-008.

    The order is therefore decided by looking at the bucket, and the look has
    three outcomes: reserved names present, reserved names absent, and COULD
    NOT LOOK. The last one is not the second one.
    """

    def test_the_three_answers_are_three_distinct_values(self):
        answers = {
            lane_slot.RESERVED_PRESENT,
            lane_slot.RESERVED_ABSENT,
            lane_slot.RESERVED_UNKNOWN,
        }
        assert len(answers) == 3

    def test_a_bucket_with_no_reserved_name_answers_absent(self, bucket: Path):
        (bucket / "0.lock").write_text(
            lane_slot.encode_payload(pid=1, repo="C:\\x", run_id="r", cycle=1),
            encoding="utf-8",
        )
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_ABSENT

    def test_a_siblings_reserved_name_answers_present(self, bucket: Path):
        (bucket / "reserved-rc.lock").write_text(
            lane_slot.encode_payload(pid=1, repo="C:\\x", run_id="r", cycle=1),
            encoding="utf-8",
        )
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_PRESENT

    def test_our_own_reserved_lock_is_not_evidence_the_widening_landed(
        self, bucket: Path
    ):
        # Evidence produced by the observer is not evidence about the world. If
        # our own floor counted, one write would latch the detector at PRESENT
        # for good and the check would be measuring our own footprint.
        (bucket / lane_slot.reserved_name("ll")).write_text(
            lane_slot.encode_payload(pid=1, repo="C:\\x", run_id="r", cycle=1),
            encoding="utf-8",
        )
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_ABSENT

    def test_a_missing_bucket_answers_could_not_look_not_absent(self, tmp_path: Path):
        missing = tmp_path / "no-such-bucket"
        state = lane_slot.reserved_scheme_state(missing)
        assert state == lane_slot.RESERVED_UNKNOWN
        assert state != lane_slot.RESERVED_ABSENT

    def test_a_bucket_we_may_not_read_answers_could_not_look(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def _denied(self):  # pragma: no cover - the raise is the point
            raise PermissionError(5, "access is denied")

        monkeypatch.setattr(Path, "iterdir", _denied)
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_UNKNOWN

    def test_garbage_in_a_lock_does_not_crash_detection(self, bucket: Path):
        # Detection reads NAMES and never opens a lock, so an unreadable or
        # half-written payload cannot take it down. The name is the signal.
        (bucket / "reserved-rc.lock").write_text("{not json", encoding="utf-8")
        (bucket / "0.lock").write_bytes(b"\x00\xff\xfe not text at all")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_PRESENT

    def test_detection_creates_nothing(self, tmp_path: Path):
        missing = tmp_path / "never-created"
        lane_slot.reserved_scheme_state(missing)
        assert not missing.exists()

    def test_a_stray_file_that_is_not_a_lock_is_not_a_reserved_name(self, bucket: Path):
        (bucket / "reserved-rc.lock.bak").write_text("x", encoding="utf-8")
        (bucket / "reserved-nope.lock").write_text("x", encoding="utf-8")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_ABSENT


class TestSharedBucketOrder:
    """Surplus-only until the widening lands, then our floor first."""

    def test_surplus_only_when_no_reserved_name_is_present(self, bucket: Path):
        order = lane_slot.bucket_slot_order(bucket, "ll", surplus=3)
        assert order == ("0.lock", "1.lock", "2.lock")
        assert lane_slot.reserved_name("ll") not in order

    def test_our_floor_is_tried_first_once_a_reserved_name_is_present(
        self, bucket: Path
    ):
        (bucket / "reserved-cs.lock").write_text("{}", encoding="utf-8")
        order = lane_slot.bucket_slot_order(bucket, "ll", surplus=3)
        assert order == ("reserved-ll.lock", "0.lock", "1.lock", "2.lock")

    def test_could_not_look_never_orders_a_reserved_name(self, tmp_path: Path):
        # The conservative direction: a look that failed must not be the reason
        # an unrecognised file appears in a directory other projects share.
        order = lane_slot.bucket_slot_order(tmp_path / "missing", "ll", surplus=3)
        assert order == ("0.lock", "1.lock", "2.lock")

    def test_no_other_repos_floor_is_ever_ordered(self, bucket: Path):
        (bucket / "reserved-rc.lock").write_text("{}", encoding="utf-8")
        order = lane_slot.bucket_slot_order(bucket, "ll", surplus=3)
        for key in lane_slot.REPO_KEYS:
            if key != "ll":
                assert lane_slot.reserved_name(key) not in order

    def test_an_unknown_key_is_refused_rather_than_ordered(self, bucket: Path):
        with pytest.raises(lane_slot.UnknownRepoKey):
            lane_slot.bucket_slot_order(bucket, "riot-commander")


class TestSharedSurplusWidth:
    """The width we contend for is note-sourced, and says so."""

    def test_the_default_shared_surplus_width_is_three(self):
        assert lane_slot.SHARED_SURPLUS_WIDTH == 3

    def test_the_provenance_of_the_width_is_written_down_beside_it(self):
        source = (REPO_ROOT / "ops" / "lane_slot.py").read_text(encoding="utf-8")
        marker = "SHARED_SURPLUS_WIDTH = "
        assert marker in source
        preamble = source[: source.index(marker)][-1200:].lower()
        # A number with no provenance becomes a measurement by attrition. The
        # width was never measured here - one lock in a bucket cannot reveal a
        # width - so the comment beside it must say where it came from.
        assert "note" in preamble
        assert "not measured" in preamble or "never measured" in preamble

    def test_the_width_is_configurable_without_a_code_change(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "5")
        assert lane_slot.shared_surplus_width() == 5

    def test_an_unusable_width_override_falls_back_rather_than_crashing(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "three")
        assert lane_slot.shared_surplus_width() == lane_slot.SHARED_SURPLUS_WIDTH
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "-4")
        assert lane_slot.shared_surplus_width() == lane_slot.SHARED_SURPLUS_WIDTH


class TestAcquireLane:
    """The operational entry point - the one that actually joins.

    Every test here passes an explicit ``root`` under ``tmp_path``. Nothing in
    this file writes into the real machine-wide bucket: a test that did would
    take a lane away from another project's live loop, which is the precise
    harm ADR-008 is careful about.
    """

    def test_no_reserved_name_is_ever_written_into_a_bucket_without_one(
        self, bucket: Path
    ):
        held = [
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\x", run_id="r", cycle=n, surplus=3
            )
            for n in range(3)
        ]
        assert all(h is not None for h in held)
        assert {h.name for h in held} == {"0.lock", "1.lock", "2.lock"}
        assert all(h.reserved is False for h in held)
        names = {entry.name for entry in bucket.iterdir()}
        assert not any(name.startswith(lane_slot.RESERVED_PREFIX) for name in names)

    def test_the_bucket_is_exhausted_at_the_shared_width_not_beyond_it(
        self, bucket: Path
    ):
        for cycle in range(3):
            assert (
                lane_slot.acquire_lane(
                    root=bucket, repo="C:\\x", run_id="r", cycle=cycle, surplus=3
                )
                is not None
            )
        assert (
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\x", run_id="r", cycle=9, surplus=3
            )
            is None
        )

    def test_our_floor_is_taken_once_the_widening_lands(self, bucket: Path):
        (bucket / "reserved-lw.lock").write_text("{}", encoding="utf-8")
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\x", run_id="r", cycle=1, surplus=3
        )
        assert held is not None
        assert held.reserved is True
        assert held.name == "reserved-ll.lock"

    def test_the_payload_written_is_the_shared_five_field_shape(self, bucket: Path):
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r5", cycle=2, surplus=3
        )
        assert held is not None
        body = json.loads(held.path.read_text(encoding="utf-8"))
        assert sorted(body) == ["cycle", "pid", "repo", "run_id", "ts"]
        assert isinstance(body["ts"], float)

    def test_hold_lane_releases_on_the_way_out(self, bucket: Path):
        with lane_slot.hold_lane(
            root=bucket, repo="C:\\x", run_id="r", cycle=0, surplus=3
        ) as held:
            assert held is not None
            path = held.path
            assert path.exists()
        assert not path.exists()

    def test_an_order_naming_another_repos_floor_is_refused(self, bucket: Path):
        with pytest.raises(lane_slot.LaneSlotError):
            lane_slot.try_acquire(
                bucket,
                "ll",
                repo="C:\\x",
                run_id="r",
                cycle=0,
                order=("reserved-rc.lock",),
            )
        assert list(bucket.iterdir()) == []

    def test_an_order_naming_a_file_outside_the_scheme_is_refused(self, bucket: Path):
        with pytest.raises(lane_slot.LaneSlotError):
            lane_slot.try_acquire(
                bucket,
                "ll",
                repo="C:\\x",
                run_id="r",
                cycle=0,
                order=("notes.txt",),
            )
        assert list(bucket.iterdir()) == []


class TestSurplusIndexWeDoNotUse:
    """A shared bucket is wider than our own contention window.

    Another participant may hold an index above the width we contend for, and
    ours is the only reaper that reclaims what WE leak. Both halves must
    tolerate an index we never ask for, or a shared bucket slowly fills with
    locks nobody recognises.
    """

    def test_is_slot_name_accepts_an_index_above_our_width(self):
        assert lane_slot.is_slot_name("2.lock") is True
        assert lane_slot.is_slot_name("7.lock") is True
        assert lane_slot.is_slot_name("12.lock") is True

    def test_reap_reclaims_a_stale_index_above_our_width(self, bucket: Path):
        body = json.loads(
            lane_slot.encode_payload(pid=os.getpid(), repo="C:\\x", run_id="x", cycle=0)
        )
        body["ts"] = time.time() - (lane_slot.STALE_SECONDS + 60)
        (bucket / "7.lock").write_text(json.dumps(body), encoding="utf-8")
        assert lane_slot.reap(bucket) == ["7.lock"]

    def test_holders_reports_an_index_above_our_width(self, bucket: Path):
        (bucket / "7.lock").write_text(
            lane_slot.encode_payload(pid=1, repo="C:\\x", run_id="r7", cycle=0),
            encoding="utf-8",
        )
        assert lane_slot.holders(bucket)["7.lock"]["run_id"] == "r7"


class TestDetectionAlphabetIsWiderThanClaiming:
    """Detection sees more keys than claiming does, and the two sets are apart.

    ``OPS-73`` hole 1. ``REPO_KEYS`` holds the five short codes the channel
    agreed, but this machine carries seven projects in ``CLAUDE.md``'s ports
    table. A bucket whose only reserved name is ``reserved-ds.lock`` therefore
    read as ``RESERVED_ABSENT``: the reserved-floor widening could land and we
    would keep taking surplus slots, and the failure would look exactly like
    correct pre-widening behaviour. A silent wrong answer is the kind this
    repository cares most about.

    The fix is deliberately NOT a wider ``is_slot_name``. That function is
    narrow so a reaper never deletes a file it does not understand, and ADR-008
    leans on the narrowness. DETECTION gets its own wider alphabet; CLAIMING
    keeps the agreed five and still refuses anything else.
    """

    def test_the_detection_alphabet_is_a_strict_superset_of_the_claim_alphabet(self):
        detect = set(lane_slot.DETECTION_REPO_KEYS)
        claim = set(lane_slot.REPO_KEYS)
        assert claim < detect

    def test_the_detection_only_keys_are_exactly_red_moon_and_daemon_slayer(self):
        extra = set(lane_slot.DETECTION_REPO_KEYS) - set(lane_slot.REPO_KEYS)
        assert extra == {"rm", "ds"}

    def test_the_provenance_of_the_detection_only_keys_is_written_down_beside_them(
        self,
    ):
        # Same discipline the note-sourced surplus width carries, and for the
        # same reason: a key with no provenance becomes an agreed key by
        # attrition. These two were read off a ports table, not agreed by the
        # projects they name, and the comment has to say so.
        source = (REPO_ROOT / "ops" / "lane_slot.py").read_text(encoding="utf-8")
        # The DEFINITION, not the export list entry of the same spelling. An
        # anchor that matches the wrong occurrence reads the wrong preamble and
        # passes for the wrong reason.
        marker = "DETECTION_REPO_KEYS: tuple"
        assert marker in source
        preamble = source[: source.index(marker)][-2000:].lower()
        assert "ports table" in preamble
        assert "claude.md" in preamble
        assert "not confirmed" in preamble

    def test_a_daemon_slayer_reserved_name_reads_as_present(self, bucket: Path):
        (bucket / "reserved-ds.lock").write_text("{}", encoding="utf-8")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_PRESENT

    def test_a_red_moon_reserved_name_reads_as_present(self, bucket: Path):
        (bucket / "reserved-rm.lock").write_text("{}", encoding="utf-8")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_PRESENT

    def test_a_detection_only_reserved_name_flips_the_try_order_to_our_floor_first(
        self, bucket: Path
    ):
        (bucket / "reserved-ds.lock").write_text("{}", encoding="utf-8")
        order = lane_slot.bucket_slot_order(bucket, "ll", surplus=3)
        assert order == ("reserved-ll.lock", "0.lock", "1.lock", "2.lock")

    def test_a_reserved_name_outside_the_detection_alphabet_still_reads_absent(
        self, bucket: Path
    ):
        # A false PRESENT is the expensive direction. It makes us write
        # reserved-ll.lock into a shared directory where, per ADR-008, nobody
        # else's reaper recognises it - so stray litter must never flip us.
        (bucket / "reserved-zz.lock").write_text("{}", encoding="utf-8")
        (bucket / "reserved-notakey.lock").write_text("{}", encoding="utf-8")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_ABSENT

    def test_claiming_with_a_detection_only_key_is_still_refused(self, bucket: Path):
        for key in ("ds", "rm"):
            with pytest.raises(lane_slot.UnknownRepoKey):
                lane_slot.slot_order(key)
            with pytest.raises(lane_slot.UnknownRepoKey):
                lane_slot.bucket_slot_order(bucket, key)
            with pytest.raises(lane_slot.UnknownRepoKey):
                lane_slot.try_acquire(bucket, key, repo="C:\\x", run_id="r", cycle=0)
        assert list(bucket.iterdir()) == []

    def test_the_reaper_alphabet_is_not_widened_by_detection(self, bucket: Path):
        # The whole point of keeping the two sets apart. A reaper that deletes
        # what it does not understand eventually eats somebody's notes.
        assert lane_slot.is_slot_name("reserved-ds.lock") is False
        assert lane_slot.is_slot_name("reserved-rm.lock") is False
        assert lane_slot.is_reserved_name("reserved-ds.lock") is False
        body = json.loads(
            lane_slot.encode_payload(pid=os.getpid(), repo="C:\\x", run_id="x", cycle=0)
        )
        body["ts"] = time.time() - (lane_slot.STALE_SECONDS + 60)
        (bucket / "reserved-ds.lock").write_text(json.dumps(body), encoding="utf-8")
        assert lane_slot.reap(bucket) == []
        assert (bucket / "reserved-ds.lock").exists()
        assert lane_slot.holders(bucket) == {}

    def test_our_own_floor_is_still_not_evidence_under_the_wider_alphabet(
        self, bucket: Path
    ):
        (bucket / lane_slot.reserved_name("ll")).write_text("{}", encoding="utf-8")
        assert lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_ABSENT


class TestUnusableBucketIsNotABusyOne:
    """``OPS-73`` hole 2. ``None`` means full, and nothing else.

    A ``PROGRAMDATA`` naming a FILE resolved the shared root underneath that
    file, ``mkdir`` failed, and ``acquire_lane`` answered ``None`` forever. A
    caller could not tell that from a bucket every participant had filled. It is
    the shape ``UnknownRepoKey``'s own docstring condemns, one level down.
    """

    def test_the_unusable_error_is_exported_and_is_its_own_kind(self):
        assert "BucketUnusable" in lane_slot.__all__
        assert issubclass(lane_slot.BucketUnusable, lane_slot.LaneSlotError)
        assert lane_slot.BucketUnusable is not lane_slot.NoSlotAvailable
        assert lane_slot.BucketUnusable is not lane_slot.UnknownRepoKey

    def test_an_all_users_root_that_is_a_file_answers_none_rather_than_a_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        impostor = tmp_path / "programdata-is-a-file"
        impostor.write_text("not a directory", encoding="utf-8")
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(impostor))
        assert lane_slot.shared_root() is None

    def test_programdata_pointing_at_a_file_falls_back_to_the_repo_local_bucket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        impostor = tmp_path / "programdata-is-a-file"
        impostor.write_text("not a directory", encoding="utf-8")
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(impostor))
        # The in-repository bucket is redirected under tmp_path so this test
        # creates nothing inside the checkout, and nothing anywhere near the
        # real shared bucket.
        monkeypatch.setattr(lane_slot, "_REPO_ROOT", tmp_path / "fake-repo")
        root = lane_slot.default_root()
        assert root == lane_slot.repo_local_root()
        assert tmp_path in root.parents

    def test_a_lane_can_still_be_taken_when_programdata_is_a_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Governed rather than permanently busy. A machine with a broken
        # all-users root still has a governor bounding our own loop.
        impostor = tmp_path / "programdata-is-a-file"
        impostor.write_text("not a directory", encoding="utf-8")
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(impostor))
        monkeypatch.setattr(lane_slot, "_REPO_ROOT", tmp_path / "fake-repo")
        held = lane_slot.acquire_lane(repo="C:\\x", run_id="r", cycle=0, surplus=3)
        assert held is not None
        assert held.path.parent == lane_slot.repo_local_root()
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_a_root_under_a_file_raises_rather_than_returning_none(
        self, tmp_path: Path
    ):
        impostor = tmp_path / "afile"
        impostor.write_text("not a directory", encoding="utf-8")
        with pytest.raises(lane_slot.BucketUnusable):
            lane_slot.try_acquire(
                impostor / "slots", "ll", repo="C:\\x", run_id="r", cycle=0
            )

    def test_acquire_lane_raises_for_an_unusable_root(self, tmp_path: Path):
        impostor = tmp_path / "afile"
        impostor.write_text("not a directory", encoding="utf-8")
        with pytest.raises(lane_slot.BucketUnusable):
            lane_slot.acquire_lane(
                root=impostor / "slots", repo="C:\\x", run_id="r", cycle=0, surplus=3
            )

    def test_a_bucket_no_lock_can_be_created_in_raises(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # The general case behind the file: a read-only volume or a directory
        # we may not write. mkdir succeeds because the directory is there.
        real_open = os.open

        def _refuse(path, *args, **kwargs):
            if str(path).endswith(lane_slot.LOCK_SUFFIX):
                raise PermissionError(5, "access is denied")
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(lane_slot.os, "open", _refuse)
        with pytest.raises(lane_slot.BucketUnusable):
            lane_slot.try_acquire(bucket, "ll", repo="C:\\x", run_id="r", cycle=0)

    def test_a_bucket_that_cannot_be_listed_raises(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def _denied(self):
            raise PermissionError(5, "access is denied")

        monkeypatch.setattr(Path, "iterdir", _denied)
        with pytest.raises(lane_slot.BucketUnusable):
            lane_slot.try_acquire(bucket, "ll", repo="C:\\x", run_id="r", cycle=0)

    def test_a_genuinely_full_bucket_still_returns_none(self, bucket: Path):
        keep = [
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\x", run_id="r", cycle=n, surplus=2
            )
            for n in range(2)
        ]
        assert all(k is not None for k in keep)
        assert (
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\x", run_id="r", cycle=9, surplus=2
            )
            is None
        )

    def test_busy_and_unusable_are_different_outcomes(self, tmp_path: Path):
        # "A wrong answer is quiet" is the whole point of OPS-73, so the two
        # outcomes are asserted to be different KINDS of thing rather than two
        # values a caller has to squint at.
        full = tmp_path / "full"
        full.mkdir()
        for cycle in range(2):
            assert (
                lane_slot.acquire_lane(
                    root=full, repo="C:\\x", run_id="r", cycle=cycle, surplus=2
                )
                is not None
            )
        busy = lane_slot.acquire_lane(
            root=full, repo="C:\\x", run_id="r", cycle=9, surplus=2
        )
        assert busy is None

        impostor = tmp_path / "afile"
        impostor.write_text("x", encoding="utf-8")
        with pytest.raises(lane_slot.BucketUnusable) as caught:
            lane_slot.acquire_lane(
                root=impostor / "slots", repo="C:\\x", run_id="r", cycle=0, surplus=2
            )
        assert caught.value is not busy
        assert isinstance(caught.value, lane_slot.LaneSlotError)

    def test_hold_lane_raises_for_an_unusable_root_rather_than_yielding_none(
        self, tmp_path: Path
    ):
        impostor = tmp_path / "afile"
        impostor.write_text("x", encoding="utf-8")
        with (
            pytest.raises(lane_slot.BucketUnusable),
            lane_slot.hold_lane(
                root=impostor / "slots", repo="C:\\x", run_id="r", cycle=0, surplus=2
            ),
        ):
            pass

    def test_the_override_and_the_shared_root_agree_about_whitespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # shared_root() has always ignored a blank all-users root. The override
        # branch did not, so LL_LANE_SLOT_ROOT="   " produced Path("   ") and a
        # bucket named three spaces. Two readers of the same kind of value must
        # not disagree about what blank means.
        monkeypatch.setenv(lane_slot.ROOT_ENV_VAR, "   ")
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(tmp_path))
        assert lane_slot.default_root() == tmp_path / lane_slot.SHARED_BUCKET_RELATIVE

        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, "   ")
        assert lane_slot.shared_root() is None
        monkeypatch.setattr(lane_slot, "_REPO_ROOT", tmp_path / "fake-repo")
        assert lane_slot.default_root() == lane_slot.repo_local_root()


# ---------------------------------------------------------------------------
# OPS-76: the stale arm has to be REACHABLE from the operational entry point
# ---------------------------------------------------------------------------


def _fingerprint(path: Path) -> tuple[int, int, str]:
    """Size, modification time to the nanosecond, and content digest.

    Three independent facts rather than one. A same-size rewrite, a touch that
    changes nothing else, and a silent content swap each move a different member
    of this tuple, and "the file was left alone" is a claim all three have to
    agree on. This is the same instrument the 2026-09-11 measurement used
    against the real shared bucket, kept here so a regression is caught in
    ``tmp_path`` instead.
    """
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (stat.st_size, stat.st_mtime_ns, digest)


def _plant_lock(
    bucket: Path, name: str, *, age: float, pid: int, run_id: str = "planted"
) -> Path:
    """Write one lock with an exact age and an exact holder pid.

    ``age`` is subtracted from the current wall clock, so a value above
    :data:`ops.lane_slot.STALE_SECONDS` fires the timestamp arm and a small one
    does not. ``pid`` of ``0`` is deterministically dead - ``_pid_alive``
    refuses any non-positive pid without probing the operating system - which
    lets the liveness arm be exercised without spawning and reaping a process.
    """
    path = bucket / name
    body = json.loads(
        lane_slot.encode_payload(pid=pid, repo="C:\\some-tree", run_id=run_id, cycle=0)
    )
    body["ts"] = time.time() - age
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


class TestTheAcquirePathReclaimsStaleLocks:
    """``OPS-76``. A behaviour that is implemented and UNWIRED is not a behaviour.

    Measured on 2026-09-11 against the real shared bucket: it held one lock,
    ``0.lock``, stale by both arms - holder pid dead and timestamp about 33
    hours old. A real acquire took ``1.lock`` and left ``0.lock`` byte for byte
    as it found it. The cause was that ``reap`` had no caller anywhere in this
    tree, so :data:`ops.lane_slot.STALE_SECONDS`, the two naming schemes and
    seventy-odd green tests were all correct and all unreachable from
    :func:`ops.lane_slot.acquire_lane`.

    The consequence is worse than an unused function. Every lock this project
    leaks into a directory other projects share stays there permanently, and
    each one silently lowers our real concurrency by one while presenting as an
    ordinary "busy" answer.
    """

    def test_an_acquire_reclaims_a_stale_lock_in_an_earlier_candidate_position(
        self, bucket: Path
    ):
        # Criterion 1, and the exact shape of the measured defect: the stale
        # lock sits in the FIRST candidate position and the acquire used to
        # step over it.
        planted = _plant_lock(
            bucket, "0.lock", age=lane_slot.STALE_SECONDS + 3600, pid=0
        )
        assert planted.exists()
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert held.name == "0.lock", (
            "the acquire stepped past a stale lock instead of reclaiming it, "
            "which is the OPS-76 defect measured against the real bucket"
        )
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_a_bucket_full_of_stale_locks_is_not_reported_as_busy(self, bucket: Path):
        # The cost of the defect stated as a test. Permanently leaked locks
        # lower real concurrency to zero while every acquire answers "busy",
        # which is the self-clearing condition this one is not.
        for index in range(3):
            _plant_lock(
                bucket, f"{index}.lock", age=lane_slot.STALE_SECONDS + 60, pid=0
            )
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=3
        )
        assert held is not None, (
            "every slot was leaked rather than held, so the bucket was "
            "reclaimable and answering None was a lie about contention"
        )
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_hold_lane_reclaims_on_the_way_in_as_well(self, bucket: Path):
        # The wiring has to be on the path ops/loop/lane.py actually uses, and
        # that path is hold_lane rather than acquire_lane directly.
        _plant_lock(bucket, "0.lock", age=lane_slot.STALE_SECONDS + 60, pid=0)
        with lane_slot.hold_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        ) as held:
            assert held is not None
            assert held.name == "0.lock"
        assert not (bucket / "0.lock").exists()

    def test_the_timestamp_arm_alone_is_enough_to_reclaim(self, bucket: Path):
        # Arm one, isolated: the holder pid is THIS interpreter and is very much
        # alive, so only the age of the lock can be what reclaims it. This is
        # also the arm that catches the real orphan, because a long-lived
        # controller keeps its pid alive across a leak.
        _plant_lock(
            bucket, "0.lock", age=lane_slot.STALE_SECONDS + 60, pid=os.getpid()
        )
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None and held.name == "0.lock"
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_the_liveness_arm_alone_is_enough_to_reclaim(self, bucket: Path):
        # Arm two, isolated: the timestamp is seconds old, so the age arm
        # cannot fire, and only the dead holder can be what reclaims it.
        _plant_lock(bucket, "0.lock", age=5.0, pid=0)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None and held.name == "0.lock"
        assert lane_slot.release(held, retries=1, backoff=0.0) is True


class TestAnAcquireNeverRemovesALockThatIsNotStale:
    """``OPS-76`` criterion 2, the direction that can do real harm.

    A reaper wired into the hot path is the single most dangerous thing this
    repository does to a directory other projects depend on. One-directional
    evidence - only that reclaiming works - is exactly what this criterion
    forbids, so every arm of :func:`ops.lane_slot.is_stale` is also tested from
    the other side, and survival is asserted on three independent facts about
    the file rather than on its mere existence.
    """

    def test_a_live_pid_holders_lock_survives_an_acquire_untouched(
        self, bucket: Path
    ):
        # The liveness arm from the safe side. Fresh timestamp, and the holder
        # pid is this running interpreter.
        planted = _plant_lock(bucket, "0.lock", age=5.0, pid=os.getpid())
        before = _fingerprint(planted)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert held.name == "1.lock", "the acquire took a lock it did not own"
        assert planted.exists()
        assert _fingerprint(planted) == before
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_a_fresh_timestamp_holders_lock_survives_an_acquire_untouched(
        self, bucket: Path
    ):
        # The timestamp arm from the safe side, at the boundary rather than in
        # the comfortable middle: the lock is only just inside the window, so a
        # reaper that widened its arm by a whisker still fails this.
        planted = _plant_lock(
            bucket, "0.lock", age=lane_slot.STALE_SECONDS - 60, pid=os.getpid()
        )
        before = _fingerprint(planted)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None and held.name == "1.lock"
        assert planted.exists()
        assert _fingerprint(planted) == before
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_a_busy_bucket_of_fresh_locks_answers_none_rather_than_stealing_one(
        self, bucket: Path
    ):
        # The strongest statement of the safety direction. When the only way to
        # get a lane is to take somebody else's live lock, the answer is BUSY.
        planted = {}
        for index in range(2):
            path = _plant_lock(bucket, f"{index}.lock", age=5.0, pid=os.getpid())
            planted[path] = _fingerprint(path)
        assert (
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
            )
            is None
        )
        for path, before in planted.items():
            assert path.exists()
            assert _fingerprint(path) == before

    def test_a_file_the_scheme_does_not_own_survives_an_acquire(self, bucket: Path):
        # is_slot_name stays narrow, so a reaper on the hot path still leaves
        # anything it does not understand alone. A reaper that deletes what it
        # cannot name eventually eats somebody's notes.
        stray = bucket / "notes.txt"
        stray.write_text("a sibling operator scratch file", encoding="utf-8")
        foreign = bucket / "reserved-ds.lock"
        foreign.write_text("{}", encoding="utf-8")
        before = {stray: _fingerprint(stray), foreign: _fingerprint(foreign)}
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        for path, fingerprint in before.items():
            assert path.exists()
            assert _fingerprint(path) == fingerprint
        assert lane_slot.release(held, retries=1, backoff=0.0) is True


class TestAnotherParticipantsReservedFloorIsNeverReapedOnTheAcquirePath:
    """``OPS-76`` criterion 3, decided explicitly and tested in that direction.

    THE DECISION, recorded in ``docs/adr/ADR-008-join-the-shared-bucket.md``:
    the acquire path may reclaim a stale SURPLUS lock whoever wrote it, and may
    reclaim OUR OWN stale ``reserved-ll.lock``, and may never remove another
    participant's ``reserved-<key>.lock`` however stale it looks.

    The asymmetry is in who pays for an error. A surplus name is first-come,
    every participant's reaper understands it, and a wrongly reclaimed one
    costs its owner a lane it will take again on its next cycle. A floor is the
    single guarantee the reserved scheme sells, and a reaper that is wrong
    about staleness there costs its owner that guarantee - in a bucket where no
    reserved name has ever been observed, so we would be exercising judgement
    about a protocol we have never seen anybody else run.

    :func:`ops.lane_slot.reap` itself is UNCHANGED and still understands both
    schemes. The narrowing is on the automatic path only, which is the path
    nobody asked for.
    """

    def test_another_repositorys_stale_reserved_floor_survives_an_acquire(
        self, bucket: Path
    ):
        planted = _plant_lock(
            bucket,
            "reserved-rc.lock",
            age=lane_slot.STALE_SECONDS * 10,
            pid=0,
        )
        before = _fingerprint(planted)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert planted.exists(), (
            "the acquire path removed another repository's guaranteed floor, "
            "which ADR-008's OPS-76 amendment rules it may never do"
        )
        assert _fingerprint(planted) == before
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_every_other_repositorys_floor_is_protected_not_just_one(
        self, bucket: Path
    ):
        others = [k for k in lane_slot.REPO_KEYS if k != lane_slot.REPO_KEY]
        assert others, "the key set collapsed to our own key, so this proves nothing"
        before = {}
        for key in others:
            path = _plant_lock(
                bucket,
                lane_slot.reserved_name(key),
                age=lane_slot.STALE_SECONDS * 10,
                pid=0,
            )
            before[path] = _fingerprint(path)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        for path, fingerprint in before.items():
            assert path.exists()
            assert _fingerprint(path) == fingerprint
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_our_own_stale_floor_is_reclaimed_because_it_is_ours(self, bucket: Path):
        # A fresh foreign reserved lock is what flips the try order to
        # reserved-first, and it also has to survive, so this test carries both
        # halves of the decision at once.
        witness = _plant_lock(
            bucket, "reserved-rc.lock", age=5.0, pid=os.getpid(), run_id="a-sibling"
        )
        witness_before = _fingerprint(witness)
        _plant_lock(
            bucket,
            lane_slot.reserved_name(lane_slot.REPO_KEY),
            age=lane_slot.STALE_SECONDS + 60,
            pid=0,
        )
        assert (
            lane_slot.reserved_scheme_state(bucket) == lane_slot.RESERVED_PRESENT
        ), "the try order was not reserved-first, so this test proves nothing"
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert held.name == lane_slot.reserved_name(lane_slot.REPO_KEY)
        assert held.reserved is True
        assert witness.exists()
        assert _fingerprint(witness) == witness_before
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_the_explicit_reaper_still_understands_both_naming_schemes(
        self, bucket: Path
    ):
        # The narrowing above is scoped to the AUTOMATIC path. reap() called by
        # hand is the operator's deliberate act and keeps the contract ADR-008
        # section 6 lists as unchanged.
        _plant_lock(
            bucket, "reserved-rc.lock", age=lane_slot.STALE_SECONDS + 60, pid=0
        )
        _plant_lock(bucket, "0.lock", age=lane_slot.STALE_SECONDS + 60, pid=0)
        assert lane_slot.reap(bucket) == ["0.lock", "reserved-rc.lock"]

    def test_the_acquire_path_predicate_says_exactly_which_names_it_will_remove(
        self,
    ):
        assert lane_slot.is_ours_to_reclaim("0.lock") is True
        assert lane_slot.is_ours_to_reclaim("7.lock") is True
        assert lane_slot.is_ours_to_reclaim("reserved-ll.lock") is True
        for key in lane_slot.REPO_KEYS:
            if key == lane_slot.REPO_KEY:
                continue
            assert lane_slot.is_ours_to_reclaim(lane_slot.reserved_name(key)) is False
        assert lane_slot.is_ours_to_reclaim("reserved-ds.lock") is False
        assert lane_slot.is_ours_to_reclaim("notes.txt") is False


class TestTheReapingPathHasACaller:
    """``OPS-76`` criterion 5. An implemented-but-unwired behaviour must FAIL.

    The item exists because seventy-odd green tests covered a reaper no
    production path could reach, and three documents described its live
    behaviour in the present tense. The primary guard here is behavioural - the
    tests above observe a real reclaim through the real entry point - and these
    add the structural half, so that deleting the call rather than breaking it
    is caught too.
    """

    def test_acquire_lane_reaps_the_bucket_it_actually_resolves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # root=None is the production shape: ops/loop/lane.py lets the module
        # resolve the bucket. PROGRAMDATA is repointed under tmp_path so this
        # test cannot reach the real machine-wide bucket.
        monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
        monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(tmp_path / "programdata"))
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "2")
        resolved = lane_slot.default_root()
        assert str(resolved).startswith(str(tmp_path)), (
            "the bucket was not redirected under tmp_path, so this test must "
            "not be allowed to run"
        )
        resolved.mkdir(parents=True, exist_ok=True)
        _plant_lock(resolved, "0.lock", age=lane_slot.STALE_SECONDS + 60, pid=0)
        held = lane_slot.acquire_lane(repo="C:\\Lanternlight", run_id="r", cycle=0)
        assert held is not None
        assert held.name == "0.lock"
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_the_reaping_call_is_reachable_from_acquire_lane(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        seen: list[Path] = []
        real = lane_slot.reap_for_acquire

        def _spy(root, key=lane_slot.REPO_KEY, **kwargs):
            seen.append(Path(root))
            return real(root, key, **kwargs)

        monkeypatch.setattr(lane_slot, "reap_for_acquire", _spy)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert seen == [bucket], (
            "acquire_lane did not call the acquire-path reaper, so the stale "
            "arm is unreachable from production again - the OPS-76 defect"
        )
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_the_acquire_path_reaper_is_exported(self):
        assert "reap_for_acquire" in lane_slot.__all__
        assert "is_ours_to_reclaim" in lane_slot.__all__

    def test_an_unusable_bucket_still_raises_rather_than_being_swallowed(
        self, tmp_path: Path
    ):
        # The reap runs before the candidates are walked, and reap() answers []
        # on a bucket it cannot list. That must not turn OPS-73's BucketUnusable
        # into a silent success or a silent busy.
        impostor = tmp_path / "afile"
        impostor.write_text("not a directory", encoding="utf-8")
        with pytest.raises(lane_slot.BucketUnusable):
            lane_slot.acquire_lane(
                root=impostor / "slots",
                repo="C:\\Lanternlight",
                run_id="r",
                cycle=0,
                surplus=2,
            )


class TestAZeroSurplusWidthIsAnOptOutAndNeverABusyBucket:
    """``OPS-77``. A width of zero used to answer ``None`` against a healthy bucket.

    The measured defect: ``acquire_lane`` with ``surplus=0``, or with
    ``LL_LANE_SLOT_SURPLUS`` set to ``0``, produced an EMPTY candidate order in
    every bucket where the reserved-floor widening has not landed. The loop over
    candidates then had nothing to walk and the return was ``None`` - which by
    the contract ``OPS-73`` hole 2 established means exactly one thing, that
    every candidate slot is taken. Against an empty, writable, perfectly healthy
    bucket that reported ``BUSY - no slot free``, forever.

    The decision, and it is a DECISION rather than a refusal: a width of zero is
    a documented OPT-OUT from lane contention. :func:`shared_surplus_width`
    deliberately accepts ``0`` while rejecting a negative and a non-numeric
    width, so zero is a value an operator may legitimately set; what it may not
    do is wear the BUSY wording, because BUSY is the one condition a caller is
    expected to shrug off and retry past, and a zero width is a permanent
    configuration state that clears only when somebody changes it.

    Every test here uses an EMPTY, WRITABLE bucket wherever it can, because that
    is the case the old behaviour lied about.
    """

    def test_a_zero_width_parameter_does_not_answer_none_on_an_empty_bucket(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        assert list(bucket.iterdir()) == [], "the bucket under test is not empty"
        with pytest.raises(lane_slot.LaneContentionOptedOut):
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=0
            )

    def test_the_same_bucket_hands_out_a_slot_at_an_ordinary_width(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # The control for the test above. Without it, "it did not answer None"
        # could be a claim about a broken bucket rather than about the width,
        # and the whole point of OPS-77 is that the bucket is healthy.
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        held = lane_slot.acquire_lane(
            root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
        )
        assert held is not None
        assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_the_environment_override_opts_out_exactly_as_the_parameter_does(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "0")
        with pytest.raises(lane_slot.LaneContentionOptedOut):
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0
            )

    def test_the_two_entry_points_cannot_disagree_about_zero(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # OPS-77 acceptance criterion 2, and the reason OPS-73 criterion 4
        # already gave about the two whitespace branches: two readers of the
        # same kind of value must not mean different things by it. The
        # parameter wins over the environment when it is given - that is the
        # precedence the module already had - but ZERO means opt out whichever
        # of the two supplied it, and a non-zero parameter is never overridden
        # into an opt-out by the environment.
        cases = [
            ({"surplus": 0}, None, True),
            ({"surplus": 0}, "5", True),
            ({}, "0", True),
            ({"surplus": 2}, "0", False),
            ({}, "2", False),
        ]
        for kwargs, env, opted_out in cases:
            if env is None:
                monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
            else:
                monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, env)
            if opted_out:
                with pytest.raises(lane_slot.LaneContentionOptedOut):
                    lane_slot.acquire_lane(
                        root=bucket,
                        repo="C:\\Lanternlight",
                        run_id="r",
                        cycle=0,
                        **kwargs,
                    )
            else:
                held = lane_slot.acquire_lane(
                    root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, **kwargs
                )
                assert held is not None, (kwargs, env)
                assert lane_slot.release(held, retries=1, backoff=0.0) is True

    def test_one_predicate_decides_for_both_entry_points(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Structural half of the criterion above: the two entry points agree
        # because there is one resolver, not two agreeing implementations.
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "0")
        assert lane_slot.is_contention_opt_out(None) is True
        assert lane_slot.is_contention_opt_out(2) is False
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        assert lane_slot.is_contention_opt_out(None) is False
        assert lane_slot.is_contention_opt_out(0) is True

    def test_the_opt_out_status_words_name_the_opt_out_and_never_say_busy(self):
        phrase = lane_slot.OPT_OUT_STATUS
        assert "opt" in phrase.lower(), (
            "an undisclosed opt-out is the blind spot OPS-70 closed wearing a "
            "configuration hat - the status words have to name it"
        )
        assert "busy" not in phrase.lower(), (
            "BUSY is the one condition a caller is expected to shrug off and "
            "retry past, and a zero width is permanent"
        )
        assert phrase == phrase.strip()
        assert len(phrase.splitlines()) == 1

    def test_the_reason_names_the_variable_that_produced_it(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(lane_slot.SURPLUS_ENV_VAR, "0")
        with pytest.raises(lane_slot.LaneContentionOptedOut) as env_error:
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0
            )
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        with pytest.raises(lane_slot.LaneContentionOptedOut) as param_error:
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=0
            )
        env_text = str(env_error.value)
        param_text = str(param_error.value)
        for text in (env_text, param_text):
            assert lane_slot.OPT_OUT_STATUS in text
            assert "busy" not in text.lower()
        assert lane_slot.SURPLUS_ENV_VAR in env_text
        assert "surplus" in param_text.lower()
        assert env_text != param_text, (
            "the two entry points agree on the ANSWER and still say which one "
            "was set, because an operator has to know where to go and change it"
        )

    def test_an_opt_out_is_not_an_unusable_bucket(self):
        # Two conditions sharing one class is the collapse OPS-73 removed. A
        # bucket that is perfectly fine must never be reported as one that
        # cannot be created, listed or written.
        assert issubclass(lane_slot.LaneContentionOptedOut, lane_slot.LaneSlotError)
        assert not issubclass(
            lane_slot.LaneContentionOptedOut, lane_slot.BucketUnusable
        )
        assert not issubclass(
            lane_slot.BucketUnusable, lane_slot.LaneContentionOptedOut
        )

    def test_a_full_bucket_still_answers_none_and_is_not_an_opt_out(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # The other side of the distinction: BUSY still exists and still means
        # what it meant. Fill every surplus slot at width 2 and ask again.
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        for name in lane_slot.surplus_names(2):
            _plant_lock(bucket, name, age=1.0, pid=os.getpid())
        assert (
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=2
            )
            is None
        )

    def test_opting_out_touches_nothing_in_the_bucket(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Opting out of contention means not operating the shared bucket at
        # all, so the acquire-path reaper must not run either: a session that
        # is not participating has no business deleting another project's
        # stale surplus lock.
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        planted = _plant_lock(bucket, "0.lock", age=lane_slot.STALE_SECONDS * 10, pid=0)
        before = _fingerprint(planted)
        with pytest.raises(lane_slot.LaneContentionOptedOut):
            lane_slot.acquire_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=0
            )
        assert planted.exists()
        assert _fingerprint(planted) == before

    def test_the_opt_out_is_decided_before_the_bucket_is_even_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # An unusable root plus a zero width answers OPTED OUT, not UNUSABLE.
        # Nothing was asked of the bucket, so nothing can be said about it, and
        # the honest answer is the one about the configuration we did read.
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        impostor = tmp_path / "afile"
        impostor.write_text("not a directory", encoding="utf-8")
        with pytest.raises(lane_slot.LaneContentionOptedOut):
            lane_slot.acquire_lane(
                root=impostor / "slots",
                repo="C:\\Lanternlight",
                run_id="r",
                cycle=0,
                surplus=0,
            )
        assert not (impostor / "slots").exists()

    def test_hold_lane_opts_out_before_the_block_runs(
        self, bucket: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)
        ran = []
        with (
            pytest.raises(lane_slot.LaneContentionOptedOut),
            lane_slot.hold_lane(
                root=bucket, repo="C:\\Lanternlight", run_id="r", cycle=0, surplus=0
            ),
        ):
            ran.append("body")
        assert ran == [], "the block ran under an opt-out"

    def test_try_acquire_with_an_explicit_order_is_deliberately_unchanged(
        self, bucket: Path
    ):
        # The boundary, stated as a test rather than only in prose. A width of
        # zero at try_acquire still yields the floor-only order, so None there
        # still means the floor is taken - a caller that states its own order is
        # asserting knowledge about the bucket, and this primitive keeps its
        # documented contract of doing exactly what the order says.
        first = _acquire(bucket, "ll", surplus=0)
        assert first is not None and first.name == lane_slot.reserved_name("ll")
        assert _acquire(bucket, "ll", surplus=0) is None

    def test_the_opt_out_is_exported(self):
        for name in (
            "LaneContentionOptedOut",
            "OPT_OUT_STATUS",
            "is_contention_opt_out",
        ):
            assert name in lane_slot.__all__
