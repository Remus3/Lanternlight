"""Guard the live suite-run recorder - ``ops/suite_recorder.py``, ``OPS-87``.

WHY THIS FILE EXISTS. Criterion 4 of ``OPS-87`` wants the cost of a
refute-fix-refute cycle recorded as a MEASUREMENT rather than a recollection,
before and after. The recorder is the instrument that makes the AFTER number
obtainable at all: every pytest session in this repository writes one record of
itself, so a later session counts full-suite runs instead of remembering them.

An instrument is only worth its wall clock if it cannot quietly lie, and this
one has exactly two ways to do that. The first is counting a three-second
single-module run as a full suite, which would make any AFTER number look
wonderful for a reason that is false; every test under
``TestClassification`` exists for that. The second is the fail-soft wrapper in
``tests/conftest.py``: a recorder that must never redden a green suite is a
recorder whose failures are invisible, and ``CLAUDE.md`` records that a raising
spy is VACUOUS under a bare ``except Exception`` because ``AssertionError`` is
an ``Exception``. So nothing here drives the recorder THROUGH the swallowing
hook. The recorder is tested directly and is required to RAISE; the wrapper is
tested separately with a spy that raises a private exception type and records
that it was called, which pins both halves - the swallow is real, and it is not
swallowing a call that never happened.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import suite_recorder  # noqa: E402

STAMP = datetime(2026, 9, 12, 18, 30, 5, 123456, tzinfo=UTC)


def _invocation(**kwargs) -> suite_recorder.Invocation:
    return suite_recorder.Invocation(**kwargs)


def _recorder(
    root: Path, *, env: dict | None = None, pid: int = 4242, ppid: int = 1
):
    return suite_recorder.SessionRecorder(
        root=root,
        env={} if env is None else env,
        pid=pid,
        ppid=ppid,
        utcnow=lambda: STAMP,
        clock=iter([100.0, 496.5]).__next__,
    )


def _stand_up_tree(root: Path, module_names: tuple[str, ...]) -> None:
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    for name in module_names:
        (tests_dir / name).write_text("# placeholder\n", encoding="ascii")


class TestClassification:
    """Full versus filtered. The load-bearing field, so it gets the most tests."""

    def test_a_bare_unfiltered_run_of_every_module_on_disk_is_full(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py", "test_b.py"))
        result = suite_recorder.classify(
            _invocation(),
            modules_run={"tests/test_a.py", "tests/test_b.py"},
            modules_on_disk=suite_recorder.test_modules_on_disk(tmp_path),
        )
        assert result.full is True, result.reasons
        assert result.reasons == ()

    @pytest.mark.parametrize(
        "kwargs, fragment",
        [
            ({"keyword": "recorder"}, "-k"),
            ({"markexpr": "slow"}, "-m"),
            ({"collect_only": True}, "collect-only"),
            ({"last_failed": True}, "--lf"),
            ({"failed_first": True}, "--ff"),
            ({"stepwise": True}, "--sw"),
            ({"args": ("tests/test_a.py",)}, "target"),
            ({"deselected": 3}, "deselect"),
        ],
    )
    def test_every_narrowing_switch_makes_the_run_filtered(
        self, tmp_path, kwargs, fragment
    ):
        _stand_up_tree(tmp_path, ("test_a.py", "test_b.py"))
        result = suite_recorder.classify(
            _invocation(**kwargs),
            modules_run={"tests/test_a.py", "tests/test_b.py"},
            modules_on_disk=suite_recorder.test_modules_on_disk(tmp_path),
        )
        assert result.full is False, f"{kwargs} was called a full suite run"
        assert any(fragment in reason for reason in result.reasons), result.reasons

    def test_a_module_on_disk_that_did_not_run_makes_the_run_filtered(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py", "test_b.py"))
        result = suite_recorder.classify(
            _invocation(),
            modules_run={"tests/test_a.py"},
            modules_on_disk=suite_recorder.test_modules_on_disk(tmp_path),
        )
        assert result.full is False
        assert any("did not run" in reason for reason in result.reasons), result.reasons

    def test_a_tree_with_no_test_modules_is_never_full(self, tmp_path):
        """A subprocess pytest over a throwaway directory must not read as a suite."""
        (tmp_path / "tests").mkdir()
        result = suite_recorder.classify(
            _invocation(),
            modules_run=set(),
            modules_on_disk=suite_recorder.test_modules_on_disk(tmp_path),
        )
        assert result.full is False
        assert result.reasons, "an empty tree produced no reason at all"

    def test_an_option_value_is_not_mistaken_for_a_target_path(self):
        assert suite_recorder.target_arguments(("-p", "no:cacheprovider")) == ()
        assert suite_recorder.target_arguments(("-k", "recorder")) == ()
        assert suite_recorder.target_arguments(("--tb=long",)) == ()
        assert suite_recorder.target_arguments(("tests/test_a.py",)) == (
            "tests/test_a.py",
        )

    def test_the_module_set_on_disk_is_read_from_the_tree_not_from_a_constant(
        self, tmp_path
    ):
        _stand_up_tree(tmp_path, ("test_a.py",))
        first = suite_recorder.test_modules_on_disk(tmp_path)
        _stand_up_tree(tmp_path, ("test_b.py",))
        second = suite_recorder.test_modules_on_disk(tmp_path)
        assert first == {"tests/test_a.py"}
        assert second == {"tests/test_a.py", "tests/test_b.py"}


class TestNesting:
    """A pytest spawned from inside a pytest must be distinguishable."""

    def test_the_first_session_is_not_nested_and_marks_the_environment(self, tmp_path):
        env: dict[str, str] = {}
        recorder = _recorder(tmp_path, env=env)
        recorder.begin()
        assert recorder.nested is False
        assert env.get(suite_recorder.NEST_ENV) == "1", (
            "a child pytest inherits the environment, so an unmarked parent "
            "leaves every subprocess run indistinguishable from a real suite"
        )

    def test_a_session_started_inside_a_marked_environment_is_nested(self, tmp_path):
        recorder = _recorder(tmp_path, env={suite_recorder.NEST_ENV: "1"})
        recorder.begin()
        assert recorder.nested is True

    def test_the_nested_flag_reaches_the_record(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py",))
        recorder = _recorder(tmp_path, env={suite_recorder.NEST_ENV: "1"})
        recorder.begin()
        recorder.note_module("tests/test_a.py")
        record = recorder.build_record(_invocation(), collected=1, exitstatus=0)
        assert record["nested"] is True


class TestNestingSurvivesAScrubbedEnvironment:
    """MEASURED, not assumed - the environment mark alone was not enough.

    On the first full-suite run after this recorder landed, three pytest runs
    that the suite itself had spawned still read as top-level, so an inherited
    environment variable does not reach every child. A constructed environment
    is one way that happens - ``tools/false_red_probe.py`` spawns pytest with
    ``env=dict(env)`` - but those three were not that case and the cause is not
    identified, which is exactly why the fix is a signal that does not travel
    through the environment at all: the parent stamps a marker file named by
    its own process id, and a child asks whether a marker exists for ITS
    parent. The next measured full run had none undetected.
    """

    def test_a_child_with_a_scrubbed_environment_is_still_nested(self, tmp_path):
        parent = _recorder(tmp_path, env={}, pid=1000, ppid=1)
        parent.begin()
        child = _recorder(tmp_path, env={}, pid=1001, ppid=1000)
        child.begin()
        assert child.nested is True, (
            "the parent's marker was not consulted, so every subprocess run "
            "launched with a constructed environment reads as top-level"
        )

    def test_a_run_whose_parent_is_not_a_pytest_is_not_nested(self, tmp_path):
        recorder = _recorder(tmp_path, env={}, pid=1000, ppid=999)
        recorder.begin()
        assert recorder.nested is False

    def test_begin_stamps_a_marker_and_finish_removes_it(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py",))
        recorder = _recorder(tmp_path, env={}, pid=1000, ppid=1)
        recorder.begin()
        marker = suite_recorder.marker_path(tmp_path, 1000)
        assert marker.is_file(), "no marker, so no child can ever see this run"
        recorder.note_module("tests/test_a.py")
        recorder.finish(_invocation(), collected=1, exitstatus=0)
        assert not marker.exists(), (
            "a marker left behind outlives its process and makes a later "
            "unrelated run with the same parent id read as nested"
        )

    def test_a_stale_marker_is_ignored_and_cleared(self, tmp_path):
        stale = suite_recorder.marker_path(tmp_path, 2000)
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale marker" + chr(10), encoding="ascii")
        import os as _os

        long_ago = stale.stat().st_mtime - (suite_recorder.MARKER_TTL_S + 60)
        _os.utime(stale, (long_ago, long_ago))
        recorder = _recorder(tmp_path, env={}, pid=2001, ppid=2000)
        recorder.begin()
        assert recorder.nested is False, (
            "a marker from a process that died hours ago was treated as a "
            "live parent"
        )
        assert not stale.exists(), "the stale marker was not cleared"

    def test_the_age_check_is_in_the_lookup_and_not_only_in_the_sweep(
        self, tmp_path
    ):
        """Found by mutation: the sweep hid the lookup's own age check.

        Disabling the age test inside the lookup SURVIVED, because
        ``begin`` sweeps stale markers away before it ever asks. That made the
        lookup's own check untested rather than unnecessary - it is the thing
        that answers correctly for a marker written between the sweep and the
        question - so it is pinned here directly.
        """
        import os as _os

        marker = suite_recorder.marker_path(tmp_path, 3000)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("marker" + chr(10), encoding="ascii")
        assert suite_recorder._parent_is_a_recorded_session(tmp_path, 3000) is True
        long_ago = marker.stat().st_mtime - (suite_recorder.MARKER_TTL_S + 60)
        _os.utime(marker, (long_ago, long_ago))
        assert suite_recorder._parent_is_a_recorded_session(tmp_path, 3000) is False

    def test_a_marker_is_cleared_at_process_exit_as_well_as_at_finish(
        self, tmp_path, monkeypatch
    ):
        """Observed, not theorised: one marker outlived a full suite run.

        A run that never reaches ``pytest_sessionfinish`` leaves its marker on
        disk for the whole time-to-live, and a later unrelated run whose parent
        id matches then reads as nested and drops out of the count. Registering
        the same cleanup at process exit closes the class without needing to
        know which process it was.
        """
        registered: list[tuple] = []
        monkeypatch.setattr(
            suite_recorder.atexit,
            "register",
            lambda fn, *args: registered.append((fn, args)),
        )
        recorder = _recorder(tmp_path, env={}, pid=1000, ppid=1)
        recorder.begin()
        assert (suite_recorder._cleanup_marker, (tmp_path, 1000)) in registered, (
            "no exit-time cleanup was registered, so a run that dies before "
            "sessionfinish leaves its marker behind"
        )

    def test_cleanup_removes_a_marker_and_tolerates_its_absence(self, tmp_path):
        marker = suite_recorder.marker_path(tmp_path, 4000)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("marker" + chr(10), encoding="ascii")
        suite_recorder._cleanup_marker(tmp_path, 4000)
        assert not marker.exists()
        suite_recorder._cleanup_marker(tmp_path, 4000)

    def test_the_markers_live_under_the_record_directory(self, tmp_path):
        assert suite_recorder.marker_path(tmp_path, 7).parent == (
            suite_recorder.record_dir(tmp_path) / "active"
        )

    def test_a_marker_that_cannot_be_written_does_not_lose_the_record(
        self, tmp_path, monkeypatch
    ):
        """The marker is an auxiliary signal, never a reason to drop a run."""
        _stand_up_tree(tmp_path, ("test_a.py",))

        def explode(*args, **kwargs):
            raise OSError("no room for a marker")

        monkeypatch.setattr(suite_recorder, "_stamp_marker", explode)
        recorder = _recorder(tmp_path, env={}, pid=1000, ppid=1)
        recorder.begin()
        recorder.note_module("tests/test_a.py")
        written = recorder.finish(_invocation(), collected=1, exitstatus=0)
        assert written.is_file()


class TestTally:
    def test_outcomes_are_counted_by_phase_and_not_only_by_name(self):
        tally = suite_recorder.Tally()
        tally.note("call", "passed")
        tally.note("call", "failed")
        tally.note("setup", "skipped")
        tally.note("teardown", "failed")
        tally.note("call", "skipped", wasxfail=True)
        tally.note("call", "passed", wasxfail=True)
        assert tally.passed == 1
        assert tally.failed == 1
        assert tally.skipped == 1
        assert tally.errors == 1, (
            "a teardown failure is an ERROR, and folding it into failed loses "
            "the distinction the summary line makes"
        )
        assert tally.xfailed == 1
        assert tally.xpassed == 1

    def test_a_passing_setup_and_teardown_are_not_counted_as_tests(self):
        tally = suite_recorder.Tally()
        tally.note("setup", "passed")
        tally.note("call", "passed")
        tally.note("teardown", "passed")
        assert tally.passed == 1, "each test would be counted three times"


class TestRecordShape:
    def test_the_record_carries_every_field_the_contract_names(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py",))
        recorder = _recorder(tmp_path)
        recorder.begin()
        recorder.note_module("tests/test_a.py")
        recorder.note_report("call", "passed")
        record = recorder.build_record(_invocation(), collected=1, exitstatus=0)
        for field in suite_recorder.RECORD_FIELDS:
            assert field in record, f"{field} is named in the contract and absent"
        assert record["full"] is True
        assert record["collected"] == 1
        assert record["passed"] == 1
        assert record["exitstatus"] == 0
        assert record["duration_s"] == pytest.approx(396.5)
        assert record["started_utc"].startswith("2026-09-12T18:30:05")

    def test_the_record_is_json_serialisable_as_ascii(self, tmp_path):
        _stand_up_tree(tmp_path, ("test_a.py",))
        recorder = _recorder(tmp_path)
        recorder.begin()
        record = recorder.build_record(_invocation(), collected=0, exitstatus=1)
        json.dumps(record, ensure_ascii=True)


class TestWriting:
    def test_the_record_lands_under_the_gitignored_runtime_directory(self, tmp_path):
        assert suite_recorder.record_dir(tmp_path) == (
            tmp_path / "ops" / "runtime" / "suite_runs"
        ), "a record outside ops/runtime/ would be a tracked file"

    def test_two_runs_in_the_same_microsecond_do_not_collide(self):
        first = suite_recorder.record_name(STAMP, 111)
        second = suite_recorder.record_name(STAMP, 222)
        assert first != second
        assert first.endswith(".json") and second.endswith(".json")

    def test_the_write_goes_to_a_temporary_name_and_is_then_replaced(
        self, tmp_path, monkeypatch
    ):
        """Atomic, because a reader may poll this directory mid-run."""
        target = suite_recorder.record_dir(tmp_path) / suite_recorder.record_name(
            STAMP, 4242
        )
        written: list[Path] = []
        real_write_text = Path.write_text

        def spy(self, *args, **kwargs):
            written.append(Path(self))
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", spy)
        result = suite_recorder.write_record(
            {"started_utc": STAMP.isoformat(), "pid": 4242}, tmp_path
        )
        assert result == target
        assert written, "nothing was written at all"
        assert written[0] != target, (
            "the payload was written straight onto the target, so a reader "
            "polling this directory can catch a half-written record"
        )
        assert written[0].parent == target.parent, (
            "the temporary must share the directory or replace is not atomic"
        )
        assert sorted(p.name for p in target.parent.iterdir()) == [target.name], (
            "a stray temporary was left behind"
        )

    def test_pruning_keeps_the_newest_and_removes_the_oldest(self, tmp_path):
        directory = suite_recorder.record_dir(tmp_path)
        directory.mkdir(parents=True)
        for index in range(6):
            (directory / f"2026091{index}T000000000000Z-000001.json").write_text(
                "{}\n", encoding="ascii"
            )
        removed = suite_recorder.prune(tmp_path, keep=3)
        remaining = sorted(p.name for p in directory.iterdir())
        assert removed == 3
        assert remaining == [
            "20260913T000000000000Z-000001.json",
            "20260914T000000000000Z-000001.json",
            "20260915T000000000000Z-000001.json",
        ]


class TestReading:
    def _write(self, root: Path, name: str, record: dict) -> None:
        directory = suite_recorder.record_dir(root)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )

    def test_records_come_back_newest_first(self, tmp_path):
        self._write(
            tmp_path,
            "20260910T000000000000Z-000001.json",
            {"started_utc": "2026-09-10T00:00:00+00:00", "full": True},
        )
        self._write(
            tmp_path,
            "20260912T000000000000Z-000002.json",
            {"started_utc": "2026-09-12T00:00:00+00:00", "full": False},
        )
        records = suite_recorder.load_records(tmp_path)
        assert [r["started_utc"] for r in records] == [
            "2026-09-12T00:00:00+00:00",
            "2026-09-10T00:00:00+00:00",
        ]

    def test_the_full_and_nested_distinction_survives_the_round_trip(self, tmp_path):
        self._write(
            tmp_path,
            "20260912T000000000000Z-000003.json",
            {"started_utc": "2026-09-12T00:00:00+00:00", "full": True, "nested": False},
        )
        self._write(
            tmp_path,
            "20260912T000000000001Z-000004.json",
            {"started_utc": "2026-09-12T00:00:01+00:00", "full": True, "nested": True},
        )
        self._write(
            tmp_path,
            "20260912T000000000002Z-000005.json",
            {"started_utc": "2026-09-12T00:00:02+00:00", "full": False, "nested": False},
        )
        assert len(suite_recorder.load_records(tmp_path)) == 3
        top = suite_recorder.full_runs(tmp_path)
        assert len(top) == 1, (
            "full_runs must exclude both filtered runs and nested ones, or the "
            "AFTER number counts a fixture's subprocess as a suite run"
        )
        assert top[0]["nested"] is False and top[0]["full"] is True

    def test_an_absent_directory_reads_as_no_records_rather_than_an_error(
        self, tmp_path
    ):
        assert suite_recorder.load_records(tmp_path) == []

    def test_an_unreadable_record_is_skipped_rather_than_poisoning_the_read(
        self, tmp_path
    ):
        self._write(
            tmp_path,
            "20260912T000000000000Z-000006.json",
            {"started_utc": "2026-09-12T00:00:00+00:00", "full": True},
        )
        directory = suite_recorder.record_dir(tmp_path)
        (directory / "20260912T000000000001Z-000007.json").write_text(
            "{not json", encoding="ascii"
        )
        records = suite_recorder.load_records(tmp_path)
        assert len(records) == 1


class TestTheRecorderRaisesAndTheWrapperSwallows:
    """The two halves of fail-soft, pinned separately on purpose."""

    def test_finish_raises_rather_than_returning_a_quiet_failure(self, tmp_path):
        blocker = tmp_path / "ops"
        blocker.write_text("this is a file, so mkdir under it cannot work\n")
        recorder = _recorder(tmp_path)
        recorder.begin()
        with pytest.raises(OSError):
            recorder.finish(_invocation(), collected=0, exitstatus=0)

    def test_the_conftest_wrapper_swallows_but_really_calls_the_recorder(
        self, monkeypatch
    ):
        """A spy raising a PRIVATE type, because AssertionError is swallowed too."""
        import conftest

        class RecorderExploded(Exception):
            pass

        calls: list[dict] = []

        class Spy:
            def finish(self, *args, **kwargs):
                calls.append(dict(kwargs))
                raise RecorderExploded("the recorder failed for real")

        class FakeConfig:
            def __init__(self):
                self.option = _FakeOption()
                self.invocation_params = _FakeParams()

        class _FakeOption:
            keyword = ""
            markexpr = ""
            collectonly = False

        class _FakeParams:
            args = ()

        class FakeSession:
            def __init__(self):
                self.config = FakeConfig()
                self.testscollected = 7

        monkeypatch.setattr(conftest, "_SUITE_RECORDER", Spy())
        conftest._record_suite_run(FakeSession(), 0)
        # Put the real recorder back BEFORE this test returns. Measured: with
        # the spy still installed at teardown, the live hook that tallies this
        # test's own call-phase report hits the spy instead, the tally silently
        # loses one pass, and the record for the run disagrees with pytest's
        # summary line by exactly one. An instrument must not be perturbed by
        # the test that checks it.
        monkeypatch.undo()
        assert calls, (
            "the wrapper swallowed without ever reaching the recorder, so this "
            "guard would pass with the call deleted"
        )

    def test_the_wrapper_is_not_the_thing_under_test_anywhere_else(self):
        """Every other test here drives the recorder directly - pin that."""
        source = Path(__file__).read_text(encoding="utf-8")
        # Assembled rather than written whole, so this line does not count
        # itself - the first version of this test failed on its own assertion
        # text, which is the same shape of defect it exists to catch.
        needle = "_record_suite_run" + "("
        assert source.count(needle) == 1, (
            "a second test driving the recorder through the swallowing wrapper "
            "is vacuous; call the recorder directly instead"
        )


class TestLiveWiring:
    """The recorder is wired into the real conftest, not merely importable."""

    def test_the_conftest_installs_the_recorder_and_the_hooks(self):
        import conftest

        assert isinstance(conftest._SUITE_RECORDER, suite_recorder.SessionRecorder)
        assert hasattr(conftest, "pytest_runtest_logreport")
        assert hasattr(conftest, "_record_suite_run")

    def test_this_very_session_is_marked_in_the_environment(self):
        import os

        assert os.environ.get(suite_recorder.NEST_ENV) == "1", (
            "the live session did not mark the environment, so a pytest "
            "spawned by a test would record itself as a top-level run"
        )

    def test_the_live_recorder_has_seen_this_module_run(self):
        import conftest

        assert "tests/test_suite_recorder.py" in conftest._SUITE_RECORDER.modules_run
