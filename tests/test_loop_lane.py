"""Guards for :mod:`ops.loop.lane` - the session-scoped lane governor.

``ops/lane_slot.py`` implements the cross-project lane protocol; this module
tests the WIRING that makes a Lanternlight session actually take a lane. Until
that wiring existed, nothing in this tree called ``acquire_lane`` or
``hold_lane`` at all, so the protocol was implemented and unarmed.

THE SAFETY RULE THIS MODULE OBEYS, stated here because it is the one thing that
cannot be recovered by re-running the suite
--------------------------------------------------------------------------

**No test in this file may write into the real shared bucket at**
``%PROGRAMDATA%\\lw-loop\\slots``. That directory is rationed by sibling
projects on this machine. A stray lock left there by a test is a slot taken
away from somebody else's loop until a stale arm fires hours later, and a test
run is exactly the kind of process that creates and abandons one.

Two independent defences, because one of them can be forgotten in a single
careless edit:

1. The autouse :func:`isolate_the_bucket` fixture repoints ``PROGRAMDATA`` at
   ``tmp_path`` and clears every lane-slot environment override, so even a test
   that forgets to pass ``root=`` cannot resolve the real bucket.
2. Every test that acquires anything passes ``root=`` explicitly as well.

:func:`test_the_isolation_fixture_actually_moves_the_default_root` proves
defence 1 is not decoration, by asking :func:`ops.lane_slot.default_root` where
it would go and requiring the answer to be under ``tmp_path``.

Why the tests never assert a literal repository path
----------------------------------------------------

The payload's ``repo`` field carries this checkout's filesystem path, because
the observed sibling lock carries its own and matching the wire is the point.
That string is not committed and not sent anywhere, but it is still a path on
the operator's machine, so the assertions below check its SHAPE - present, a
string, non-empty - and never its value. The status line is checked in the
opposite direction: it must not contain the repository root at all.
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
from ops.loop import lane  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_the_bucket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point every root-resolving path in this module at ``tmp_path``.

    Autouse on purpose. An opt-in fixture protects only the tests that remember
    to ask for it, and the failure it guards against is silent.
    """
    monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(tmp_path / "programdata"))
    monkeypatch.delenv(lane_slot.ROOT_ENV_VAR, raising=False)
    monkeypatch.delenv(lane_slot.SURPLUS_ENV_VAR, raising=False)


@pytest.fixture
def bucket(tmp_path: Path) -> Path:
    """An empty bucket that no sibling project shares."""
    root = tmp_path / "slots"
    root.mkdir()
    return root


def _fresh_foreign_lock(path: Path, *, name: str) -> None:
    """Write a lock that looks held by a living process and is not ours.

    ``pid`` is this interpreter's, so the liveness arm of
    :func:`ops.lane_slot.is_stale` answers "alive" and the lock is not reaped
    out from under the test. ``run_id`` marks it as somebody else's.
    """
    body = lane_slot.encode_payload(
        pid=os.getpid(),
        repo="a-sibling-checkout",
        run_id=f"not-ours-{name}",
        cycle=1,
        ts=time.time(),
    )
    path.write_text(body, encoding="utf-8")


def _listing(root: Path) -> dict[str, int]:
    """Filename to size, for proving a directory was left alone."""
    return {entry.name: entry.stat().st_size for entry in sorted(root.iterdir())}


# ---------------------------------------------------------------------------
# The safety rule itself
# ---------------------------------------------------------------------------


def test_the_isolation_fixture_actually_moves_the_default_root(tmp_path: Path) -> None:
    """Defence 1 is load-bearing, so it is asserted rather than assumed."""
    resolved = lane_slot.default_root()
    assert str(resolved).startswith(str(tmp_path)), (
        "the autouse isolation fixture did not move the default bucket, so a "
        "test in this module could reach the real shared bucket"
    )


# ---------------------------------------------------------------------------
# Nothing at import time
# ---------------------------------------------------------------------------


def test_importing_the_module_creates_no_directory(tmp_path: Path) -> None:
    """Importing must not materialise a bucket, a lock, or a runtime dir.

    Run in a SUBPROCESS with a fresh interpreter. Importing in-process proves
    nothing here - the module is already imported by the time this file runs,
    so any import-time side effect happened before the assertion could look.
    """
    programdata = tmp_path / "import-probe"
    env = dict(os.environ)
    env[lane_slot.PROGRAMDATA_ENV_VAR] = str(programdata)
    env.pop(lane_slot.ROOT_ENV_VAR, None)
    env["PYTHONPATH"] = str(REPO_ROOT)

    proc = subprocess.run(
        [sys.executable, "-c", "from ops.loop import lane; print(lane.__name__)"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ops.loop.lane" in proc.stdout
    assert not programdata.exists(), (
        "importing ops.loop.lane created the all-users bucket tree, which is "
        "an import-time side effect in a directory other projects share"
    )


# ---------------------------------------------------------------------------
# Holding a lane
# ---------------------------------------------------------------------------


def test_a_held_lane_carries_our_payload_and_is_gone_afterwards(bucket: Path) -> None:
    """The whole point: a lock with OUR payload while held, nothing after."""
    with lane.session_lane(root=bucket, cycle=7) as status:
        assert status.held is True
        assert status.slot is not None
        held_path = bucket / status.slot
        assert held_path.exists()

        payload = json.loads(held_path.read_text(encoding="utf-8"))
        # The wire is exactly five fields. More or fewer is a protocol drift.
        assert set(payload) == {"pid", "ts", "repo", "run_id", "cycle"}
        assert payload["pid"] == os.getpid()
        assert payload["cycle"] == 7
        assert payload["run_id"] == lane.session_run_id()
        # SHAPE ONLY. The repo field is this checkout's path and its value is
        # never asserted, printed or committed.
        assert isinstance(payload["repo"], str)
        assert payload["repo"]
        assert isinstance(payload["ts"], float)

    assert not held_path.exists(), "the lane was not released on the way out"
    assert _listing(bucket) == {}, "the bucket was not left clean"


def test_the_run_id_is_stable_within_a_session(bucket: Path) -> None:
    """Two lanes in one session must report one run id, not two.

    A run id that changes per acquire makes an operator reading the bucket
    unable to tell one session holding two lanes from two sessions holding one
    each, which is the question the field exists to answer.
    """
    with lane.session_lane(root=bucket, cycle=1) as first:
        first_id = first.run_id
    with lane.session_lane(root=bucket, cycle=2) as second:
        second_id = second.run_id
    assert first_id == second_id == lane.session_run_id()
    assert first_id


def test_the_body_raising_still_releases(bucket: Path) -> None:
    """An exception in the body must not leak a slot into a shared directory."""

    class Boom(RuntimeError):
        pass

    taken: list[str] = []
    with pytest.raises(Boom), lane.session_lane(root=bucket, cycle=3) as status:
        assert status.held is True
        assert status.slot is not None
        taken.append(status.slot)
        raise Boom("the session failed mid-cycle")

    assert taken, "the body never ran, so this test proved nothing"
    assert not (bucket / taken[0]).exists()
    assert _listing(bucket) == {}


# ---------------------------------------------------------------------------
# BUSY is an answer, not an exception
# ---------------------------------------------------------------------------


def test_a_full_bucket_is_busy_in_words_and_writes_nothing(bucket: Path) -> None:
    """Busy must be reportable, non-exceptional, and leave the bucket alone."""
    _fresh_foreign_lock(bucket / "0.lock", name="zero")
    before = _listing(bucket)

    with lane.session_lane(root=bucket, cycle=4, surplus=1) as status:
        assert status.held is False
        assert status.slot is None
        assert status.reserved is False
        assert "BUSY" in status.reason
        assert "BUSY" in status.status_line()
        inside = _listing(bucket)

    assert inside == before, "a busy acquire wrote into the bucket"
    assert _listing(bucket) == before, "a busy release removed somebody's lock"


def test_busy_says_which_bucket_and_which_scheme(bucket: Path) -> None:
    """A cold operator must be able to read the answer without the code."""
    _fresh_foreign_lock(bucket / "0.lock", name="zero")
    with lane.session_lane(root=bucket, cycle=4, surplus=1) as status:
        line = status.status_line()
        assert "BUSY" in line
        # It says WHICH bucket, but never by naming a path outside this
        # checkout - see the elision section at the foot of this file. A
        # tmp_path bucket is outside it, so the fingerprint is what a reader
        # gets, and two different buckets still read differently.
        assert "<elided bucket #" in line
        assert str(bucket) not in line
        assert lane_slot.RESERVED_ABSENT in line


# ---------------------------------------------------------------------------
# The reserved-scheme state is reported, all three of it
# ---------------------------------------------------------------------------


def test_surplus_only_while_no_reserved_name_is_in_the_bucket(bucket: Path) -> None:
    """An empty shared bucket means surplus-only, and our floor is not written."""
    with lane.session_lane(root=bucket, cycle=5) as status:
        assert status.scheme == lane_slot.RESERVED_ABSENT
        assert status.reserved is False
        assert status.slot == "0.lock"
        assert lane_slot.reserved_name(lane_slot.REPO_KEY) not in status.order
        assert not (bucket / lane_slot.reserved_name(lane_slot.REPO_KEY)).exists()


def test_our_floor_is_taken_first_once_the_widening_has_landed(bucket: Path) -> None:
    """Another participant's reserved name is the signal, and it flips the order."""
    _fresh_foreign_lock(bucket / lane_slot.reserved_name("rc"), name="rc-floor")
    with lane.session_lane(root=bucket, cycle=6) as status:
        assert status.scheme == lane_slot.RESERVED_PRESENT
        assert status.reserved is True
        assert status.slot == lane_slot.reserved_name(lane_slot.REPO_KEY)
        assert status.order[0] == lane_slot.reserved_name(lane_slot.REPO_KEY)


def test_a_bucket_that_cannot_be_read_is_unknown_and_not_absent(tmp_path: Path) -> None:
    """Unknown is a third answer. Collapsing it into absent loses a fact."""
    missing = tmp_path / "never-created"
    with lane.session_lane(root=missing, cycle=8) as status:
        assert status.scheme == lane_slot.RESERVED_UNKNOWN
        assert status.scheme != lane_slot.RESERVED_ABSENT
        # Surplus-only, the conservative branch: a failed look must never be
        # the reason an unrecognised reserved name appears in a shared bucket.
        assert status.reserved is False
        assert status.slot == "0.lock"


# ---------------------------------------------------------------------------
# The status line is safe to print
# ---------------------------------------------------------------------------


def test_the_status_line_never_carries_the_repository_root(bucket: Path) -> None:
    """It is printed into chat and into a loop's output. It must stay clean."""
    root_text = str(lane.repo_root())
    with lane.session_lane(root=bucket, cycle=9) as status:
        line = status.status_line()
    assert root_text not in line
    assert root_text.replace("\\", "/") not in line


def test_the_status_line_is_clean_even_for_the_in_repository_fallback() -> None:
    """The fallback bucket LIVES under the repository root, so this is the case.

    Built directly rather than acquired, because acquiring here would write a
    lock into the real ``ops/runtime/lane_slots`` directory - a side effect on
    the operator's tree that a test has no business having.
    """
    status = lane.LaneStatus(
        held=True,
        slot="0.lock",
        reserved=False,
        bucket=lane_slot.repo_local_root(),
        scheme=lane_slot.RESERVED_ABSENT,
        order=("0.lock",),
        key=lane_slot.REPO_KEY,
        run_id="probe",
        cycle=0,
        reason="held surplus slot 0.lock",
    )
    root_text = str(lane.repo_root())
    line = status.status_line()
    assert root_text not in line
    assert root_text.replace("\\", "/") not in line
    # It still has to SAY something about where the bucket is, or the line is
    # clean by being useless.
    assert "lane_slots" in line


def test_the_status_line_names_the_slot_and_the_scheme(bucket: Path) -> None:
    with lane.session_lane(root=bucket, cycle=10) as status:
        line = status.status_line()
        assert status.slot is not None
        assert status.slot in line
        assert status.scheme in line
        # The bucket is named, but never as a path from outside this checkout.
        assert "<elided bucket #" in line
        assert str(bucket) not in line


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_the_cycle_defaults_to_the_loop_state(bucket: Path, monkeypatch) -> None:
    """``cycle`` comes from ``ops.loop.state`` when the caller does not say."""
    monkeypatch.setattr(lane, "current_cycle", lambda: 4242)
    with lane.session_lane(root=bucket) as status:
        assert status.cycle == 4242
        assert status.slot is not None
        payload = json.loads((bucket / status.slot).read_text(encoding="utf-8"))
        assert payload["cycle"] == 4242


def test_current_cycle_reads_the_real_loop_state() -> None:
    """The default is wired to the real reader, not to a constant."""
    observed = lane.current_cycle()
    assert isinstance(observed, int)
    assert observed >= 0


# ---------------------------------------------------------------------------
# UNUSABLE is a THIRD answer, and never a flavour of BUSY
# ---------------------------------------------------------------------------
#
# ``ops/lane_slot.py`` raises :class:`ops.lane_slot.BucketUnusable` rather than
# answering ``None`` when the bucket cannot be created, listed or written -
# ``OPS-73`` hole 2. ``None`` therefore means exactly one thing, every candidate
# slot is taken, and a misconfigured root is a separate fact with a separate
# name. The tests below pin that the wiring in :mod:`ops.loop.lane` preserves
# the distinction instead of flattening it back into BUSY one layer up.
#
# The unusable condition is CONSTRUCTED THE WAY THE LAYER BELOW ACTUALLY
# PRODUCES IT - a root whose parent is a file - rather than by monkeypatching a
# raise. A patched raise proves the except clause is spelled correctly and
# proves nothing about whether the real fault reaches it.


@pytest.fixture
def unusable_bucket(tmp_path: Path) -> Path:
    """A bucket root that cannot be created, listed or written.

    Its PARENT is an ordinary file, so ``mkdir(parents=True)`` fails, which is
    the measured cause recorded in ``OPS-73``: a ``PROGRAMDATA`` naming a file
    resolved the shared root underneath that file and every acquire answered
    ``None`` forever.
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text(
        "an ordinary file, so no directory can be created underneath it",
        encoding="utf-8",
    )
    return blocker / "slots"


def test_the_layer_below_really_does_raise_on_this_root(unusable_bucket: Path) -> None:
    """The anchor. Without it, every test below could be passing vacuously.

    If this fixture stopped producing an unusable root - a future Windows build
    that tolerates the shape, a change in ``lane_slot`` - the tests that follow
    would quietly be measuring a BUSY bucket, or a held one, and would still be
    green. So the condition is asserted to be the real one FIRST.
    """
    with pytest.raises(lane_slot.BucketUnusable):
        lane_slot.acquire_lane(
            repo="probe", run_id="probe", cycle=0, root=unusable_bucket
        )


def test_an_unusable_bucket_is_answered_in_words_and_never_raises(
    unusable_bucket: Path,
) -> None:
    """The governor must not take the loop down with it.

    An unattended loop that refuses to start because a lock directory is
    misconfigured has converted a coordination problem into an outage, and the
    operator is playing the game and cannot fix it. So the answer is a status,
    the body runs, and the words say UNUSABLE every cycle.
    """
    seen: list[lane.LaneStatus] = []
    with lane.session_lane(root=unusable_bucket, cycle=11) as status:
        seen.append(status)
        assert status.held is False
        assert status.slot is None
        assert status.reserved is False
        assert status.usable is False
        assert "UNUSABLE" in status.reason
        assert "UNUSABLE" in status.status_line()

    assert seen, "the body never ran, so this test proved nothing"
    assert not unusable_bucket.exists(), (
        "the unusable root was created after all, so the fixture is no longer "
        "producing the condition this test is about"
    )


def test_unusable_and_busy_are_textually_unmistakable(
    bucket: Path, unusable_bucket: Path
) -> None:
    """Two different facts must not be readable as one.

    Asserted as a DIFFERENCE and not merely as two separate presence checks,
    because two statuses can each contain their own word and still be the same
    sentence with a substitution, which is not what "unmistakable" means to an
    operator skim-reading a cycle's output.
    """
    _fresh_foreign_lock(bucket / "0.lock", name="zero")
    with lane.session_lane(root=bucket, cycle=12, surplus=1) as busy:
        busy_reason = busy.reason
        busy_line = busy.status_line()
        busy_usable = busy.usable
        busy_held = busy.held

    with lane.session_lane(root=unusable_bucket, cycle=12) as unusable:
        unusable_reason = unusable.reason
        unusable_line = unusable.status_line()
        unusable_usable = unusable.usable
        unusable_held = unusable.held

    assert busy_held is False and unusable_held is False
    assert busy_usable is True, "a full bucket is a usable bucket"
    assert unusable_usable is False

    assert busy_reason != unusable_reason
    assert busy_line != unusable_line

    assert "BUSY" in busy_reason and "BUSY" in busy_line
    assert "UNUSABLE" in unusable_reason and "UNUSABLE" in unusable_line
    assert "BUSY" not in unusable_reason, "UNUSABLE must not wear the BUSY wording"
    assert "BUSY" not in unusable_line, "UNUSABLE must not wear the BUSY wording"
    assert "UNUSABLE" not in busy_reason
    assert "UNUSABLE" not in busy_line


def test_the_unusable_answer_carries_no_repository_path() -> None:
    """The in-repository fallback bucket is the case this has to survive.

    That bucket lives UNDER the repository root, so the obvious rendering would
    put the root into a status line every time the all-users root could not be
    resolved - the safe case common, the leaking case the fallback. Built
    directly rather than acquired, because acquiring here would write into the
    operator's real tree.
    """
    inside = lane_slot.repo_local_root() / "never-created"
    reason = lane._unusable_reason(inside, "FileExistsError")
    status = lane.LaneStatus(
        held=False,
        slot=None,
        reserved=False,
        bucket=inside,
        scheme=lane_slot.RESERVED_UNKNOWN,
        order=(),
        key=lane_slot.REPO_KEY,
        run_id="probe",
        cycle=0,
        reason=reason,
        usable=False,
    )
    line = status.status_line()
    root_text = str(lane.repo_root())
    for text in (line, reason):
        assert root_text not in text
        assert root_text.replace("\\", "/") not in text
    assert "UNUSABLE" in line
    assert "lane_slots" in line, (
        "the line is clean by being useless - it still has to say where the "
        "bucket was"
    )


def test_the_body_raising_under_unusable_still_exits_cleanly(
    unusable_bucket: Path,
) -> None:
    """The context manager has to unwind the same way in all three states."""

    class Boom(RuntimeError):
        pass

    observed: list[bool] = []
    with pytest.raises(Boom), lane.session_lane(root=unusable_bucket, cycle=13) as status:
        observed.append(status.usable)
        raise Boom("the session failed mid-cycle with no bucket to release")

    assert observed == [False], "the body never ran under an unusable bucket"
    assert not unusable_bucket.exists()


def test_an_unusable_bucket_reports_the_scheme_as_unknown(
    unusable_bucket: Path,
) -> None:
    """A root we cannot list is a root we did not look at. Say so, both ways.

    ``scheme`` and ``usable`` answer two different questions - "what shape is
    this bucket" and "can this bucket be operated at all" - and a root whose
    parent is a file is the case where the honest answers are UNKNOWN and False
    together. Pinning both keeps a future change from silently making the
    scheme read ABSENT, which would claim a look that never happened.
    """
    with lane.session_lane(root=unusable_bucket, cycle=14) as status:
        assert status.scheme == lane_slot.RESERVED_UNKNOWN
        assert status.scheme != lane_slot.RESERVED_ABSENT
        assert status.usable is False


# ---------------------------------------------------------------------------
# No absolute path from outside this checkout reaches any printed text
# ---------------------------------------------------------------------------
#
# ``_display_bucket`` used to rewrite ONLY a bucket lying under the repository
# root and returned the absolute path unchanged for every other one. That is
# backwards for the two buckets this project actually uses. The shared machine
# bucket is outside the checkout, and ``LL_LANE_SLOT_ROOT`` - which
# ``docs/HEADLESS.md`` recommends as the way to withdraw from the shared budget
# - can point anywhere at all, including under the operator's profile, where a
# path segment IS the operator's account name. ``CLAUDE.md`` names an account
# name an operator identifier, and the status line is printed every cycle.
#
# The segment asserted against below is a synthetic one chosen by this file.
# The operator's real account name is never written here as a literal: it is
# reached instead by asserting that ``tmp_path``, which lives under the
# operator's profile on this machine, does not appear either. A guard that
# hardcodes the value it protects is scoped to one value.

#: A path segment shaped like a Windows account name, invented for these tests.
_ACCOUNT_SHAPED = "probe-account-name"


def _outside_bucket(tmp_path: Path) -> Path:
    """A bucket outside the checkout whose path carries an account-shaped name."""
    root = tmp_path / "Users" / _ACCOUNT_SHAPED / "lw-loop" / "slots"
    root.mkdir(parents=True)
    return root


def _assert_carries_no_outside_path(text: str, bucket: Path, tmp_path: Path) -> None:
    """No absolute path from outside this checkout, in any spelling."""
    for raw in (str(bucket), str(bucket.parent), str(tmp_path)):
        assert raw not in text, f"an absolute path reached printed text: {text!r}"
        assert raw.replace("\\", "/") not in text
    assert _ACCOUNT_SHAPED not in text, (
        "an account-name-shaped path segment reached printed text, which is an "
        f"operator identifier by CLAUDE.md's definition: {text!r}"
    )


def test_a_held_answer_outside_the_repository_carries_no_absolute_path(
    tmp_path: Path,
) -> None:
    """The HELD branch. This is the common case and prints every cycle."""
    bucket = _outside_bucket(tmp_path)
    with lane.session_lane(root=bucket, cycle=20) as status:
        assert status.held is True, "the anchor: this bucket was empty, so a lane was taken"
        line = status.status_line()
        reason = status.reason
    _assert_carries_no_outside_path(line, bucket, tmp_path)
    _assert_carries_no_outside_path(reason, bucket, tmp_path)


def test_a_busy_answer_outside_the_repository_carries_no_absolute_path(
    tmp_path: Path,
) -> None:
    """The BUSY branch names the bucket too, so it leaks by the same route."""
    bucket = _outside_bucket(tmp_path)
    for index in range(lane_slot.shared_surplus_width()):
        _fresh_foreign_lock(bucket / f"{index}.lock", name=str(index))
    with lane.session_lane(root=bucket, cycle=21) as status:
        assert status.held is False and status.usable is True, (
            "the anchor: every surplus slot was held by a live foreign lock"
        )
        line = status.status_line()
        reason = status.reason
    assert "BUSY" in reason
    _assert_carries_no_outside_path(line, bucket, tmp_path)
    _assert_carries_no_outside_path(reason, bucket, tmp_path)


def test_the_unusable_text_outside_the_repository_carries_no_absolute_path(
    tmp_path: Path,
) -> None:
    """The UNUSABLE branch, which ``docs/HEADLESS.md`` promises omits the path.

    Constructed the way the layer below actually produces the fault - a parent
    that is an ordinary file - rather than by patching a raise.
    """
    holder = tmp_path / "Users" / _ACCOUNT_SHAPED
    holder.mkdir(parents=True)
    blocker = holder / "not-a-directory"
    blocker.write_text("an ordinary file", encoding="utf-8")
    bucket = blocker / "slots"
    with lane.session_lane(root=bucket, cycle=22) as status:
        assert status.usable is False, "the anchor: the bucket really was unusable"
        line = status.status_line()
        reason = status.reason
    assert "UNUSABLE" in line and "UNUSABLE" in reason
    _assert_carries_no_outside_path(line, bucket, tmp_path)
    _assert_carries_no_outside_path(reason, bucket, tmp_path)
    assert not bucket.exists()


def test_the_shared_machine_bucket_is_still_named_in_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eliding must not make the production line useless.

    The shared bucket is the one this project contends in every session, and
    its namespace - ``lw-loop/slots`` - is a WIRE fact held in this tree's own
    source, not a path read off the operator's machine. So it is named, while
    the all-users root it hangs under never is.
    """
    programdata = tmp_path / "Users" / _ACCOUNT_SHAPED / "ProgramData"
    monkeypatch.setenv(lane_slot.PROGRAMDATA_ENV_VAR, str(programdata))
    shared = lane_slot.shared_root()
    assert shared is not None, "the anchor: the all-users root resolved"
    rendered = lane._display_bucket(shared)
    assert lane_slot.SHARED_BUCKET_RELATIVE.as_posix() in rendered, (
        "the shared bucket's own namespace is a wire fact and stays legible"
    )
    _assert_carries_no_outside_path(rendered, shared, tmp_path)


# ---------------------------------------------------------------------------
# Reclaiming is wired into the acquire, and the documents have to say so
# ---------------------------------------------------------------------------
#
# ``OPS-76`` wired ``ops.lane_slot.reap_for_acquire`` into
# ``ops.lane_slot.acquire_lane``, which ``session_lane`` reaches through
# ``hold_lane``. Every acquire this project makes now reclaims a STALE lock in
# the surplus namespace whoever wrote it. Three shipped documents went on
# saying the opposite - that this project never removes a lock it did not
# create - and a green suite did not notice, because none of them was pinned to
# anything.
#
# The two behavioural tests below pin the code fact from both sides, and the
# prose test pins the documents to it. A prose guard alone would be decoration:
# it would stay green if the reaping were ripped out tomorrow.


def _stale_foreign_lock(path: Path, *, name: str) -> None:
    """A lock stale by BOTH arms: pid 0 is never alive, ts is long past.

    Stale by both arms on purpose. A lock stale by only one would leave the
    test dependent on which arm ``ops.lane_slot.is_stale`` consults first, and
    the live shared bucket's real leak, measured 2026-09-11, was stale by both.
    """
    body = lane_slot.encode_payload(
        pid=0,
        repo="a-sibling-checkout",
        run_id=f"not-ours-{name}",
        cycle=1,
        ts=time.time() - (lane_slot.STALE_SECONDS * 2),
    )
    path.write_text(body, encoding="utf-8")


def test_a_session_acquire_reclaims_a_stale_surplus_lock_it_did_not_write(
    bucket: Path,
) -> None:
    """The headline behaviour change, asserted rather than described.

    The lock is somebody else's by ``run_id`` and by ``repo``, and it is in the
    first-come surplus namespace, which every participant's reaper understands.
    A stale one is reclaimed, and the slot is then taken.
    """
    leaked = bucket / "0.lock"
    _stale_foreign_lock(leaked, name="zero")
    before = _listing(bucket)
    assert "0.lock" in before, "the anchor: the foreign stale lock really is there"

    with lane.session_lane(root=bucket, cycle=30, surplus=1) as status:
        assert status.held is True, (
            "the stale foreign lock was not reclaimed, so the only surplus slot "
            "read as held and the answer came back BUSY"
        )
        assert status.slot == "0.lock"
        payload = json.loads(leaked.read_text(encoding="utf-8"))

    assert payload["run_id"] != "not-ours-zero", (
        "the lock file survived byte for byte, so it was never reclaimed - it "
        "was merely reported over"
    )
    assert payload["pid"] == os.getpid()


def test_a_session_acquire_never_reclaims_another_participants_stale_floor(
    bucket: Path,
) -> None:
    """The disclosed blind spot, pinned so it cannot be widened by accident.

    A sibling's ``reserved-<key>.lock`` is left alone however stale it looks.
    Removing one in the window between an exclusive create and its payload
    write would cost its owner the single guarantee the reserved scheme sells.
    """
    foreign_floor = bucket / lane_slot.reserved_name("rc")
    _stale_foreign_lock(foreign_floor, name="rc-floor")
    before = _listing(bucket)
    assert foreign_floor.name in before, "the anchor: a foreign stale floor is there"

    with lane.session_lane(root=bucket, cycle=31, surplus=1) as status:
        assert status.held is True
        assert foreign_floor.exists(), (
            "another participant's reserved floor was reclaimed on the "
            "automatic path, which ADR-008's 2026-09-11b amendment forbids"
        )

    assert _listing(bucket)[foreign_floor.name] == before[foreign_floor.name]


def _collapsed(path: Path) -> str:
    """A document's text with all whitespace collapsed, lowercased.

    Prose in this repository is hard-wrapped near 80 columns, so a quoted
    sentence routinely spans two lines and a single-line pattern misses it.
    That has produced two false clean bills here already, so the search is done
    on a collapsed copy rather than line by line.
    """
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


#: Documents that describe what the lane governor deletes. Each is checked in
#: full, collapsed, because each carried a refuted claim on 2026-09-11.
_LANE_DOCUMENTS = (
    Path("ops") / "loop" / "lane.py",
    Path("docs") / "HEADLESS.md",
    Path(".claude") / "commands" / "loop.md",
)

#: Claims the code refutes. Each was in a shipped document until 2026-09-11.
_REFUTED_CLAIMS = (
    "never removes a lock it did not create",
    "only ever removes the lock this session created",
    "do not delete anybody's lock",
    "reaps stale locks deliberately or not at all",
    "reaping stale locks is a separate, deliberate act and is not done here",
)


@pytest.mark.parametrize("relative", _LANE_DOCUMENTS, ids=lambda p: p.as_posix())
def test_no_lane_document_still_claims_we_never_remove_a_foreign_lock(
    relative: Path,
) -> None:
    """The prose is pinned to the code, in the one direction a suite can pin it.

    This cannot prove a document is TRUE. It can prove that the specific
    sentences the code refuted on 2026-09-11 have not come back, and that each
    document still names the function that does the reclaiming - so the
    correction cannot be satisfied by deleting the subject instead of fixing it.
    """
    document = REPO_ROOT / relative
    assert document.is_file(), f"{relative.as_posix()} is missing"
    text = _collapsed(document)
    for claim in _REFUTED_CLAIMS:
        assert claim not in text, (
            f"{relative.as_posix()} still carries a claim the code refutes: "
            f"{claim!r}. Every acquire reclaims a stale surplus lock whoever "
            "wrote it - see ops.lane_slot.reap_for_acquire."
        )
    assert "reap_for_acquire" in text, (
        f"{relative.as_posix()} no longer names the reaper the acquire path "
        "runs, so a reader cannot find out what is actually deleted"
    )
