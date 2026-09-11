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
