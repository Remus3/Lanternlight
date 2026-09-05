"""Tests for lanternlight.armwatch - the one entry point that arms a session.

ROADMAP item 4c. The failure this module exists to prevent is not a missing
capability - ``lanternlight.savewatch`` already does every byte of the
copying - it is that arming the watchers was something a session had to
REMEMBER. Two things were lost to exactly that: the 6.1 MB log of 2026-08-09,
and the ``AvgPrice_<id>.ini`` market cache, which emptied itself back to its
37-byte state with nothing watching.

So the unit under test here is the PLAN, not the copying. A plan names the
four surfaces the game writes, points each at a destination outside every
checkout, and carries the poll interval together with the measured trigger
that interval was chosen against. Every interval in this module is defensible
by a number somebody observed; a test below asserts each one says which.

Everything here runs against tmp_path and hand-built directories. Nothing
needs the game installed, running, or on this machine, except the one test
that grounds the destination guard against the actual repository this file
lives in, which skips cleanly if that precondition does not hold.

ROADMAP item 4d adds the second half. A destination named for a day has to BE
that day: a watcher armed on 2026-08-31 against a literal
``--dest-root .../2026-08-31`` keeps writing into that directory after
midnight, so the directory claims to cover a day it does not. A mislabelled
archive is worse than an absent one, because it gets believed. The rollover
tests below drive an injected clock across midnight, so the whole crossing
costs no wall-clock time and the assertions are about directory NAMES, which
is the thing that was wrong.

The rollover keeps the watcher INSTANCE and only retargets it, so its seen-set
survives midnight. That is asserted below rather than left to the reader,
because forgetting it re-copies every unchanged file every day: MEASURED
2026-09-01, the live ``Saved/Logs/`` holds 3 files totalling 10,316,212 bytes,
so a forgetful rollover would duplicate 9.84 MB per day - about 3.51 GB per
year, against a total watcher output to date of 80.12 MB across 115 files.

ROADMAP item 4e adds the third half - the heartbeat. MEASURED at the cycle 37
wrap: pid 23628 was alive for over 24 hours and had archived nothing. With
the game client shut that is the CORRECT result, and it is indistinguishable
from a wedged process: ``armwatch.json`` is written once at arming and never
touched again, and a dated destination root only appears when something is
archived, so its absence is equally consistent with both states. The tests
below drive the heartbeat with injected clocks - a frozen monotonic for the
flush throttle and a ticking UTC clock for the stamps - so a 30-second
throttle and a wedged 300-second surface are both asserted in no wall-clock
time at all.
"""

import ast
import json
import os
import sys
import threading
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import armwatch, savewatch  # noqa: E402  (path bootstrap first)


def _saved_tree(root: Path) -> Path:
    """Build the shape of the game's ``Saved/`` directory under ``root``."""
    saved = root / "Saved"
    (saved / "Logs").mkdir(parents=True)
    (saved / "SaveGames").mkdir(parents=True)
    (saved / "StandaloneLevel").mkdir(parents=True)
    (saved / "AvgPrice_937566.ini").write_bytes(b"[AvgPrice]\n")
    (saved / "Logs" / "MistfallHunter.log").write_bytes(b"Log file open\n")
    return saved


class TestSessionPlanCoversEverySurface:
    """The acceptance names four surfaces. All four, or the item is not done."""

    def test_plan_names_all_four_surfaces(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        plans = armwatch.session_plan(saved, tmp_path / "dest")
        sources = {p.source.name for p in plans}
        assert sources == {"Logs", "SaveGames", "StandaloneLevel", "Saved"}

    def test_saved_root_is_the_saved_dir_itself(self, tmp_path: Path) -> None:
        """The market cache sits at the root of Saved/, not in a subdirectory.

        ``AvgPrice_<id>.ini`` is a top-level file. Watching only the
        subdirectories would miss the exact file whose silent emptying opened
        this item.
        """
        saved = _saved_tree(tmp_path)
        plans = armwatch.session_plan(saved, tmp_path / "dest")
        roots = [p for p in plans if p.source == saved]
        assert len(roots) == 1

    def test_every_plan_gets_its_own_destination(self, tmp_path: Path) -> None:
        """Two watchers sharing a destination would overwrite each other.

        The snapshot filename is ``<stamp>_<size>_<name>``, which collides
        across sources whenever two sources hold a same-named file.
        """
        saved = _saved_tree(tmp_path)
        plans = armwatch.session_plan(saved, tmp_path / "dest")
        dests = [p.dest for p in plans]
        assert len(set(dests)) == len(dests)

    def test_every_destination_is_under_the_given_root(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        dest_root = tmp_path / "dest"
        for plan in armwatch.session_plan(saved, dest_root):
            assert dest_root in plan.dest.parents or plan.dest == dest_root


class TestIntervalsAreArguedNotGuessed:
    """"Chosen against measured triggers rather than guessed" is the wording.

    A number with no argument behind it is the thing this repo calls a
    confident guess, so the rationale is part of the data structure and not a
    comment somebody can drift away from.
    """

    def test_every_plan_carries_a_rationale(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        for plan in armwatch.session_plan(saved, tmp_path / "dest"):
            assert plan.rationale.strip(), f"{plan.name} has no rationale"

    def test_every_rationale_cites_a_number(self, tmp_path: Path) -> None:
        """A rationale with no digit in it is prose, not a measurement."""
        saved = _saved_tree(tmp_path)
        for plan in armwatch.session_plan(saved, tmp_path / "dest"):
            assert any(ch.isdigit() for ch in plan.rationale), (
                f"{plan.name}'s rationale cites no measured number: {plan.rationale!r}"
            )

    def test_match_lifetime_surfaces_poll_in_seconds(self, tmp_path: Path) -> None:
        """StandaloneSlot_<roleId>.sav appears 17 s after EnterBattle.

        It then grows through at least seven generations in roughly 70 s and
        is deleted about 13 minutes later. Anything slower than a few seconds
        samples that file a handful of times and calls it a capture.
        """
        saved = _saved_tree(tmp_path)
        by_name = {p.source.name: p for p in armwatch.session_plan(saved, tmp_path / "dest")}
        assert by_name["SaveGames"].poll_seconds <= 5.0
        assert by_name["StandaloneLevel"].poll_seconds <= 5.0

    def test_the_log_is_not_polled_at_match_cadence(self, tmp_path: Path) -> None:
        """The acceptance says this in so many words.

        A 3-second cadence on a log that reached 5,080,313 bytes copies
        gigabytes across a session. The 2026-08-25 session used a 5-minute
        cadence and took 23 generations, which is a record of the session's
        shape without being a record of every byte twice.
        """
        saved = _saved_tree(tmp_path)
        by_name = {p.source.name: p for p in armwatch.session_plan(saved, tmp_path / "dest")}
        assert by_name["Logs"].poll_seconds >= 60.0


class TestDestinationGuard:
    """The acceptance asks for this one by name."""

    def test_arm_refuses_a_destination_inside_a_checkout(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        plans = armwatch.session_plan(saved, fake_repo / "captures")
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.arm(plans)

    def test_arm_refuses_before_creating_any_destination(self, tmp_path: Path) -> None:
        """Refusing late is refusing after making a mess.

        The guard lives in SaveWatcher.__init__, so a refusal must happen
        before any watcher has had a chance to mkdir its destination.
        """
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        dest_root = fake_repo / "captures"
        plans = armwatch.session_plan(saved, dest_root)
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.arm(plans)
        assert not dest_root.exists()

    def test_arm_accepts_a_destination_outside_every_checkout(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        watchers = armwatch.arm(armwatch.session_plan(saved, tmp_path / "dest"))
        assert len(watchers) == 4
        assert all(isinstance(w, savewatch.SaveWatcher) for w in watchers)

    def test_the_guard_is_not_vacuous_against_this_repo(self) -> None:
        """Ground the guard against the real checkout this file lives in.

        A guard proven only against a hand-built .git directory is proven
        against a fixture, not against the situation it exists for.
        """
        if not savewatch.is_inside_repo_working_directory(REPO_ROOT):
            pytest.skip("this test file is not inside a git working directory")
        saved = REPO_ROOT / "does-not-need-to-exist" / "Saved"
        plans = armwatch.session_plan(saved, REPO_ROOT / "captures")
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.arm(plans)


class TestArmedWatchersActuallyCopy:
    """Arming that does not copy is a plan, not a watcher."""

    def test_one_pass_snapshots_each_surface(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        watchers = armwatch.arm(armwatch.session_plan(saved, tmp_path / "dest"))
        taken = [snap for w in watchers for snap in w.poll_once()]
        names = {s.source.name for s in taken}
        assert "MistfallHunter.log" in names
        assert "AvgPrice_937566.ini" in names

    def test_the_log_backup_is_captured_too(self, tmp_path: Path) -> None:
        """MEASURED 2026-08-25: the launch at 21:28:59 left a backup beside the log.

        ``MistfallHunter-backup-<UTC>.log`` was created at the moment of
        launch, byte-identical to the previous run's final log. Watching the
        Logs/ DIRECTORY rather than the log FILE is what picks it up, and
        that is the difference between recovering the previous session and
        not.
        """
        saved = _saved_tree(tmp_path)
        backup = saved / "Logs" / "MistfallHunter-backup-2026.08.26-01.27.09.log"
        backup.write_bytes(b"the previous run\n")
        watchers = armwatch.arm(armwatch.session_plan(saved, tmp_path / "dest"))
        taken = [snap for w in watchers for snap in w.poll_once()]
        assert backup.name in {s.source.name for s in taken}

    def test_no_watcher_writes_to_the_source(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        before = {p.name: p.read_bytes() for p in sorted(saved.rglob("*")) if p.is_file()}
        watchers = armwatch.arm(armwatch.session_plan(saved, tmp_path / "dest"))
        for w in watchers:
            w.poll_once()
        after = {p.name: p.read_bytes() for p in sorted(saved.rglob("*")) if p.is_file()}
        assert before == after


class TestEntryPoint:
    """One entry point. The acceptance says one."""

    def test_main_arms_and_returns_zero(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-root",
                str(tmp_path / "dest"),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 0

    def test_main_actually_copied_something(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        dest_root = tmp_path / "dest"
        armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-root",
                str(dest_root),
                "--max-passes",
                "1",
            ]
        )
        copied = [p for p in dest_root.rglob("*") if p.is_file()]
        assert copied, "main() reported success without copying anything"

    def test_main_refuses_a_destination_inside_a_checkout(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-root",
                str(fake_repo / "captures"),
                "--max-passes",
                "1",
            ]
        )
        assert rc != 0, "main() accepted a destination inside a git working directory"

    def test_main_survives_an_absent_saved_dir(self, tmp_path: Path) -> None:
        """The game may not be installed, or may never have run.

        SaveWatcher.poll_once tolerates an absent source by design; the entry
        point must not undo that by refusing to start.
        """
        rc = armwatch.main(
            [
                "--saved-dir",
                str(tmp_path / "nope" / "Saved"),
                "--dest-root",
                str(tmp_path / "dest"),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 0


class _SequenceClock:
    """A ``now_fn`` handing out a fixed sequence of readings, in order.

    The last reading repeats forever once the sequence runs out, so a test
    that adds an assertion does not have to re-count internal clock reads.
    ``run_rolling`` reads the clock once while arming the first day, then once
    per pass after that.
    """

    def __init__(self, *readings: datetime) -> None:
        assert readings, "a clock with no readings cannot be read"
        self._readings = list(readings)
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        if len(self._readings) > 1:
            return self._readings.pop(0)
        return self._readings[0]


#: The three clock readings every rollover test below drives: one to arm the
#: first day, one pass still inside it, one pass after midnight.
_ACROSS_MIDNIGHT = (
    datetime(2026, 8, 31, 23, 59, 30),
    datetime(2026, 8, 31, 23, 59, 45),
    datetime(2026, 9, 1, 0, 0, 15),
)


def _snapshot_files(root: Path) -> list[Path]:
    """Every snapshot file under ``root``, ignoring the directories."""
    return sorted(p for p in root.rglob("*") if p.is_file())


class TestDatedDestRoot:
    """The dated root is DERIVED, never a literal a caller typed once.

    ROADMAP item 4d. ``armwatch`` had no date logic at all - ``--dest-root``
    was required and the caller passed a literal path - so the day baked into
    that path was fixed at arm time and never revisited.
    """

    def test_dated_dest_root_appends_the_local_date(self, tmp_path: Path) -> None:
        root = armwatch.dated_dest_root(tmp_path, now=datetime(2026, 8, 31, 23, 59, 30))
        assert root == tmp_path / "2026-08-31"

    def test_the_date_format_is_the_sortable_iso_day(self) -> None:
        """A dated directory is read by a human and sorted by a machine.

        ``%Y-%m-%d`` is the format where lexical order and chronological order
        agree, and it is what the capture tree on this machine already uses.
        """
        assert armwatch.DEST_DATE_FORMAT == "%Y-%m-%d"
        assert datetime(2026, 9, 1, 0, 0, 30).strftime(armwatch.DEST_DATE_FORMAT) == "2026-09-01"

    def test_the_date_is_derived_per_call_not_cached(self, tmp_path: Path) -> None:
        """Two calls either side of midnight must not agree.

        A root computed once and reused IS the defect 4d fixes, so the
        derivation is pinned to every call rather than being allowed to hide
        behind a cache of the first one.
        """
        before = armwatch.dated_dest_root(tmp_path, now=datetime(2026, 8, 31, 23, 59, 59))
        after = armwatch.dated_dest_root(tmp_path, now=datetime(2026, 9, 1, 0, 0, 1))
        assert before.name == "2026-08-31"
        assert after.name == "2026-09-01"
        assert before != after

    def test_dated_dest_root_accepts_a_string_base(self, tmp_path: Path) -> None:
        """argparse hands back a Path; a caller in a script hands a str."""
        root = armwatch.dated_dest_root(str(tmp_path), now=datetime(2026, 9, 1, 12, 0, 0))
        assert root == tmp_path / "2026-09-01"

    def test_the_default_clock_is_the_local_one(self, tmp_path: Path) -> None:
        """``now=None`` reads the LOCAL clock, which is what the tree uses.

        Snapshot filenames are already stamped local by ``savewatch._stamp``
        and the capture tree on this machine is named in local dates. This
        machine sits at UTC-5, so for five hours of every day the UTC date is
        the NEXT day, and picking UTC here would file an evening session under
        tomorrow. Reading the clock either side of the call and accepting
        either answer removes the once-a-day race at midnight without
        weakening what is asserted.
        """
        before = datetime.now()
        root = armwatch.dated_dest_root(tmp_path)
        after = datetime.now()
        assert root.name in {
            before.strftime(armwatch.DEST_DATE_FORMAT),
            after.strftime(armwatch.DEST_DATE_FORMAT),
        }


class TestMidnightRollover:
    """A watcher left running past midnight starts writing into the new day."""

    def test_a_changed_source_lands_in_the_new_day(self, tmp_path: Path) -> None:
        """The game keeps writing across midnight; the archive must follow.

        The log grows between the two passes, so the generation captured after
        midnight is a genuinely new one and belongs under the SECOND day.
        """
        saved = _saved_tree(tmp_path)
        log = saved / "Logs" / "MistfallHunter.log"
        base = tmp_path / "captures"
        readings = list(_ACROSS_MIDNIGHT)

        def clock() -> datetime:
            reading = readings.pop(0) if len(readings) > 1 else readings[0]
            if reading.day == 1:
                log.write_bytes(b"Log file open\nafter midnight\n")
            return reading

        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=clock,
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
        )
        days = sorted(p.name for p in base.iterdir() if p.is_dir())
        assert days == ["2026-08-31", "2026-09-01"]
        second = _snapshot_files(base / "2026-09-01")
        assert [p.name for p in second if p.name.endswith("MistfallHunter.log")], (
            "the post-midnight generation did not land in the new day"
        )
        assert all(p.stat().st_size == len(b"Log file open\nafter midnight\n") for p in second)

    def test_an_unchanged_source_is_not_recopied_after_midnight(self, tmp_path: Path) -> None:
        """The rollover keeps the seen-set. This is the regression that matters.

        MEASURED 2026-09-01: the live ``Saved/Logs/`` holds 3 files totalling
        10,316,212 bytes. A rollover that forgot which generations were
        already captured would re-copy all 9.84 MB into every new dated
        directory - about 3.51 GB a year, roughly 45x the entire 80.12 MB of
        watcher output that exists today, with OPS-14 (disk pressure) open. An
        unchanged 5 MB log is not a new fact just because midnight passed.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=_SequenceClock(*_ACROSS_MIDNIGHT),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
        )
        assert _snapshot_files(base / "2026-08-31"), "nothing was archived before midnight"
        assert _snapshot_files(base / "2026-09-01") == [], (
            "an unchanged source was duplicated into the new day's directory"
        )

    def test_every_snapshot_is_stamped_with_the_day_that_holds_it(self, tmp_path: Path) -> None:
        """The whole point of 4d: the directory name must not be a lie.

        A snapshot is named ``<YYYYmmdd-HHMMSS>_<size>_<name>`` and lives at
        ``<base>/<YYYY-MM-DD>/<surface>/``. If the dated root is stale, a file
        stamped with today sits in a directory named for yesterday, which is
        exactly the mislabelling this item exists to remove.
        """
        saved = _saved_tree(tmp_path)
        log = saved / "Logs" / "MistfallHunter.log"
        base = tmp_path / "captures"
        readings = list(_ACROSS_MIDNIGHT)

        def clock() -> datetime:
            reading = readings.pop(0) if len(readings) > 1 else readings[0]
            if reading.day == 1:
                log.write_bytes(b"Log file open\nafter midnight\n")
            return reading

        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=clock,
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
        )
        seen_days = set()
        for snap in _snapshot_files(base):
            day_dir = snap.parent.parent.name
            stamp_day = snap.name.split("-", 1)[0]
            assert stamp_day == day_dir.replace("-", ""), (
                f"{snap.name} is stamped {stamp_day} but sits in {day_dir}"
            )
            seen_days.add(day_dir)
        assert seen_days == {"2026-08-31", "2026-09-01"}, (
            f"only {sorted(seen_days)} checked - the assertion never saw a rollover"
        )

    def test_a_bounded_run_never_sleeps_and_never_threads(self, tmp_path: Path) -> None:
        """The bounded path is the one tests drive, so it must be synchronous.

        A real sleep or a background thread here would make every rollover
        assertion above a race rather than a measurement.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        sleeps: list[float] = []
        threads_before = threading.active_count()
        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=_SequenceClock(*_ACROSS_MIDNIGHT),
            sleep_fn=sleeps.append,
            log_fn=lambda _m: None,
        )
        assert _snapshot_files(base), "a bounded run that copies nothing proves nothing"
        assert sleeps == []
        assert threading.active_count() == threads_before


class TestRollingDestinationGuard:
    """The refusal must stay at arm time, and must survive the retarget.

    ``TestDestinationGuard.test_arm_refuses_before_creating_any_destination``
    pins all-or-nothing for the literal ``--dest-root`` path. Building the
    dated watchers lazily on the first poll would leave that test green while
    quietly moving the refusal later, so the first two below ask for the
    refusal with ZERO passes: nothing ever polls, and it must still refuse.
    """

    def test_a_dest_base_inside_a_checkout_is_refused_with_no_passes(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.run_rolling(
                saved,
                fake_repo / "captures",
                max_passes=0,
                now_fn=_SequenceClock(datetime(2026, 9, 1, 9, 0, 0)),
                log_fn=lambda _m: None,
            )

    def test_the_refusal_leaves_the_checkout_untouched(self, tmp_path: Path) -> None:
        """All-or-nothing, stated positively: nothing new exists afterwards."""
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        base = fake_repo / "captures"
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.run_rolling(
                saved,
                base,
                max_passes=0,
                now_fn=_SequenceClock(datetime(2026, 9, 1, 9, 0, 0)),
                log_fn=lambda _m: None,
            )
        assert not base.exists()
        assert sorted(p.name for p in fake_repo.iterdir()) == [".git"]

    def test_the_rollover_retarget_still_refuses_a_checkout(self, tmp_path: Path) -> None:
        """Retargeting must re-run the guard, not just assign a new path.

        A checkout created inside the capture base is not hypothetical - the
        base is an ordinary directory on an operator's disk. Here tomorrow's
        dated root already contains a ``.git`` marker while today's does not,
        so the destination only becomes forbidden at the moment of the roll.
        Assigning ``dest_dir`` without re-validating would sail straight past
        it and write roleId-bearing save files into a working directory.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        (base / "2026-09-01" / ".git").mkdir(parents=True)
        with pytest.raises(savewatch.DestinationInsideRepoError):
            armwatch.run_rolling(
                saved,
                base,
                max_passes=2,
                now_fn=_SequenceClock(*_ACROSS_MIDNIGHT),
                sleep_fn=lambda _s: None,
                log_fn=lambda _m: None,
            )
        assert _snapshot_files(base / "2026-08-31"), (
            "the refusal fired before the roll, so it proves nothing about the retarget"
        )

    def test_main_refuses_a_dest_base_inside_a_checkout(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-base",
                str(fake_repo / "captures"),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 2
        assert not (fake_repo / "captures").exists()


class TestDestBaseEntryPoint:
    """``--dest-base`` is the dated door; ``--dest-root`` stays the literal one."""

    def test_main_accepts_dest_base_and_returns_zero(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-base",
                str(tmp_path / "captures"),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 0

    def test_main_with_dest_base_copies_into_a_dated_subdirectory(self, tmp_path: Path) -> None:
        """End to end on the real clock, with the midnight race removed.

        Reading the clock either side of the call and accepting either day
        keeps this from being the one test that fails once a year at 00:00.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        before = datetime.now()
        armwatch.main(["--saved-dir", str(saved), "--dest-base", str(base), "--max-passes", "1"])
        after = datetime.now()
        dated = [p for p in base.iterdir() if p.is_dir()]
        assert len(dated) == 1
        assert dated[0].name in {
            before.strftime(armwatch.DEST_DATE_FORMAT),
            after.strftime(armwatch.DEST_DATE_FORMAT),
        }
        assert _snapshot_files(dated[0]), "main() reported success without copying anything"

    def test_dest_root_still_means_a_literal_directory(self, tmp_path: Path) -> None:
        """4d must not smuggle a date into the path 4c already ships.

        A caller passing ``--dest-root C:/ll-captures/2026-08-31`` gets that
        directory, with nothing appended to it.
        """
        saved = _saved_tree(tmp_path)
        dest = tmp_path / "dest"
        rc = armwatch.main(
            ["--saved-dir", str(saved), "--dest-root", str(dest), "--max-passes", "1"]
        )
        assert rc == 0
        assert (dest / "logs").is_dir()
        assert _snapshot_files(dest / "logs")

    def test_neither_destination_is_rejected(self, tmp_path: Path) -> None:
        """A watcher with no destination has nowhere to archive to."""
        saved = _saved_tree(tmp_path)
        with pytest.raises(SystemExit) as excinfo:
            armwatch.main(["--saved-dir", str(saved), "--max-passes", "1"])
        assert excinfo.value.code == 2

    def test_both_destinations_are_rejected(self, tmp_path: Path) -> None:
        """Two destinations is a question about which one the operator meant."""
        saved = _saved_tree(tmp_path)
        with pytest.raises(SystemExit) as excinfo:
            armwatch.main(
                [
                    "--saved-dir",
                    str(saved),
                    "--dest-root",
                    str(tmp_path / "dest"),
                    "--dest-base",
                    str(tmp_path / "captures"),
                    "--max-passes",
                    "1",
                ]
            )
        assert excinfo.value.code == 2


_HEARTBEAT_EPOCH = datetime(2026, 9, 3, 5, 0, 0, tzinfo=UTC)


class _HeartbeatWasBuilt(Exception):
    """Raised by the detonator below when a Heartbeat is constructed.

    Deliberately NOT an ``AssertionError``. This repo has already paid for a
    raising spy that was swallowed by a fail-soft ``except Exception``, and a
    spy whose exception can be eaten proves nothing. A private class also
    cannot be confused with a real failure from somewhere else.
    """


class _Detonator:
    """Stands in for ``armwatch.Heartbeat`` and explodes on construction."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise _HeartbeatWasBuilt(f"Heartbeat({args!r}, {kwargs!r})")


class _RefusingHeartbeat:
    """A ``_write`` that always fails with a real OSError.

    ``OSError`` specifically, because that is the one class the flush is
    allowed to absorb. Anything wider would be the fail-soft trap.
    """

    def _write(self, payload: str) -> None:
        raise OSError(13, "permission denied")


class _AssertingHeartbeat:
    """A ``_write`` raising the one exception a fail-soft catch must not eat."""

    def _write(self, payload: str) -> None:
        raise AssertionError("the spy fired")


class _RecoveringHeartbeat:
    """A ``_write`` that fails ``fails_left`` times with a real OSError, then works.

    ``OSError`` and nothing wider, for the same reason as
    :class:`_RefusingHeartbeat`: it is the one class the flush is allowed to
    absorb, and a spy raising anything else would be exercising a different
    catch.

    ``write_attempts`` counts every call, which is what separates "the
    throttle declined to retry" from "the retry happened and failed again".
    ``failed_writes`` alone cannot tell those apart, and this repo's rule is
    that a negative assertion has to be paired with something positive.

    Both counters are CLASS attributes used only as defaults; the ``+=`` and
    ``-=`` below bind instance attributes on first use, so two spied
    heartbeats never share a count.
    """

    fails_left = 0
    write_attempts = 0

    def _write(self, payload: str) -> None:
        self.write_attempts += 1
        if self.fails_left > 0:
            self.fails_left -= 1
            raise OSError(28, "no space left on device")
        super()._write(payload)


class _FrozenMonotonic:
    """A monotonic clock a test moves by hand.

    ``armwatch.Heartbeat`` throttles its flush against ``time.monotonic``
    rather than against the wall clock, so crossing the flush interval in a
    test means moving THIS clock. Reading it never advances it: a test that
    wants time to pass has to say so, which keeps a throttle assertion from
    depending on how many times the implementation happens to read the clock.
    """

    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class _TickingUtcClock:
    """A UTC-aware wall clock advancing ``step_seconds`` on every read.

    Not thread-safe on its own, and it does not need to be: ``Heartbeat``
    reads it only while holding its own lock, so every reading is serialised
    by the same lock that serialises the counter.
    """

    def __init__(self, start: datetime = _HEARTBEAT_EPOCH, step_seconds: float = 1.0) -> None:
        assert start.tzinfo is not None, "a naive start cannot test a UTC contract"
        self._next = start
        self._step = timedelta(seconds=step_seconds)
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        reading = self._next
        self._next = reading + self._step
        return reading


def _beat(
    path: Path,
    *,
    step_seconds: float = 1.0,
) -> tuple[armwatch.Heartbeat, _TickingUtcClock, _FrozenMonotonic]:
    """A Heartbeat wired to injected clocks, plus the clocks themselves.

    The monotonic clock starts FROZEN, so nothing flushes after the first
    record until a test moves it. That makes every throttle assertion below a
    statement about the interval rather than about wall-clock luck.
    """
    clock = _TickingUtcClock(step_seconds=step_seconds)
    ticks = _FrozenMonotonic()
    return armwatch.Heartbeat(path, now_fn=clock, monotonic_fn=ticks), clock, ticks


def _read_heartbeat(path: Path) -> dict:
    """Parse the heartbeat file, which must be exactly one JSON object.

    ``json.loads`` raises "Extra data" on a file that was appended to rather
    than replaced, so this helper is also the append check.
    """
    return json.loads(path.read_text(encoding="ascii"))


def _spy_heartbeat(
    spy: type,
    path: Path,
    *,
    monotonic_fn: _FrozenMonotonic | None = None,
) -> armwatch.Heartbeat:
    """Build a Heartbeat subclass whose ``_write`` comes from ``spy``.

    The spy is mixed in AHEAD of ``Heartbeat`` so its ``_write`` wins, which
    puts the raise inside the guarded region rather than around it - a spy
    that replaced the whole guarded call would prove nothing about the catch.

    ``monotonic_fn`` defaults to a fresh frozen clock, so every existing
    caller keeps the shape it had. A test that has to MOVE the throttle
    window passes its own handle rather than reaching into a private
    attribute, which would pin the implementation's field name instead of its
    behaviour.
    """
    ticks = _FrozenMonotonic() if monotonic_fn is None else monotonic_fn
    subclass = type(f"Spied{spy.__name__}", (spy, armwatch.Heartbeat), {})
    return subclass(path, now_fn=_TickingUtcClock(), monotonic_fn=ticks)


class TestHeartbeatShape:
    """The file is a fixed set of flat keys, parsed by a reader, not a human.

    ROADMAP item 4e. MEASURED at the cycle 37 wrap: pid 23628 was alive for
    over 24 hours having archived nothing, which is the CORRECT result with
    the game client shut - and byte for byte indistinguishable from a wedged
    process. ``armwatch.json`` is written once at arming and never touched
    again, and a dated destination root only appears when something is
    archived, so its absence says "idle" and "hung" in exactly the same voice.
    """

    def test_the_top_level_keys_are_exactly_the_contract(self, tmp_path: Path) -> None:
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        assert set(_read_heartbeat(path)) == {"pid", "written", "passes", "surfaces"}

    def test_the_surface_keys_are_the_plan_names(self, tmp_path: Path) -> None:
        """Cross-checked against session_plan, so a renamed surface breaks here.

        A hard-coded literal set would keep agreeing with itself after
        somebody renamed a ``WatchPlan``, and the heartbeat would then report
        a surface the reader has never heard of while the reader waited
        forever for one that no longer exists.
        """
        saved = _saved_tree(tmp_path)
        names = {plan.name for plan in armwatch.session_plan(saved, tmp_path / "dest")}
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        for name in sorted(names):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record(name)
        assert set(_read_heartbeat(path)["surfaces"]) == names
        assert names == {"savegames", "standalonelevel", "savedroot", "logs"}

    def test_pid_is_this_process(self, tmp_path: Path) -> None:
        """The pid is what lets a reader join this file to an identity check.

        ``ops.loop.watch`` already confirms a watcher's identity from a pid;
        the heartbeat has to name the same process or the two records are
        describing different things.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        assert _read_heartbeat(path)["pid"] == os.getpid()

    def test_written_is_utc_at_second_resolution(self, tmp_path: Path) -> None:
        """A staleness check is arithmetic, so the stamp must be unambiguous.

        Second resolution keeps the file a fixed width; the explicit offset
        keeps a reader from having to guess which clock produced it.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        written = datetime.fromisoformat(_read_heartbeat(path)["written"])
        assert written.utcoffset() == timedelta(0)
        assert written.microsecond == 0

    def test_every_surface_stamp_is_truncated_to_the_second(self, tmp_path: Path) -> None:
        """The truncation happens here, not in whatever clock was handed in."""
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path, step_seconds=0.5)
        for _ in range(3):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record("logs")
        stamp = datetime.fromisoformat(_read_heartbeat(path)["surfaces"]["logs"])
        assert stamp.microsecond == 0
        assert stamp.utcoffset() == timedelta(0)

    def test_a_naive_clock_is_refused_rather_than_guessed_at(self, tmp_path: Path) -> None:
        """A stamp with no offset is a guess wearing a confident tone.

        Assuming local would be wrong for five hours of every day on this
        machine and doubly wrong inside a DST fold, where one naive reading
        names two different instants. This is a wiring error, not an
        environmental one, so it sits deliberately outside what the flush
        absorbs.
        """
        beat = armwatch.Heartbeat(
            tmp_path / "beat.json",
            now_fn=lambda: datetime(2026, 9, 3, 5, 0, 0),
            monotonic_fn=_FrozenMonotonic(),
        )
        with pytest.raises(ValueError):
            beat.record("logs")

    def test_an_aware_non_utc_clock_is_normalised_to_utc(self, tmp_path: Path) -> None:
        """The contract says UTC, so a local-but-aware clock is converted."""
        path = tmp_path / "beat.json"
        beat = armwatch.Heartbeat(
            path,
            now_fn=lambda: datetime(2026, 9, 3, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5))),
            monotonic_fn=_FrozenMonotonic(),
        )
        beat.record("logs")
        assert _read_heartbeat(path)["surfaces"]["logs"] == "2026-09-03T05:00:00+00:00"

    def test_the_default_clock_is_aware_and_utc(self, tmp_path: Path) -> None:
        """Every other test here injects a clock, so the DEFAULT needs its own.

        A production watcher injects nothing. A default that had drifted to a
        naive local reading would be caught by nothing else in this file,
        because nothing else ever calls it - which is exactly the shape of a
        guard that is green because it is looking somewhere else. Found by
        mutating ``_utc_now`` to ``datetime.now()`` and watching every test
        below stay green.
        """
        path = tmp_path / "beat.json"
        before = datetime.now(UTC).replace(microsecond=0)
        beat = armwatch.Heartbeat(path, monotonic_fn=_FrozenMonotonic())
        beat.record("logs")
        after = datetime.now(UTC).replace(microsecond=0)
        stamp = datetime.fromisoformat(_read_heartbeat(path)["surfaces"]["logs"])
        assert stamp.utcoffset() == timedelta(0)
        assert before <= stamp <= after

    def test_the_payload_is_seven_bit_ascii(self, tmp_path: Path) -> None:
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        assert max(path.read_bytes()) < 0x80, "the heartbeat file carries a non-ASCII byte"

    def test_the_file_is_rewritten_never_appended(self, tmp_path: Path) -> None:
        """An appended file grows without bound and stops being one JSON object.

        OPS-14 (disk pressure) is open and a watcher left running for days is
        the normal case, so the one shape this file must never take is a
        growing one.
        """
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        sizes = []
        for _ in range(5):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record("logs")
            sizes.append(path.stat().st_size)
        assert _read_heartbeat(path)["passes"] == 5
        assert len(set(sizes)) == 1, f"the heartbeat changed size across flushes: {sizes}"


class TestHeartbeatAdvancesWithNothingArchived:
    """THE point of 4e: an idle watcher and a wedged one must not look alike."""

    def test_passes_advance_when_no_source_ever_changes(self, tmp_path: Path) -> None:
        """Twelve completed passes, two archived files - ten passes copied nothing.

        The source tree is built once and never touched again, so after the
        first pass the seen-set inside every ``SaveWatcher`` makes each later
        pass a no-op. That IS the cycle 37 state - alive, correct, archiving
        nothing - and the heartbeat has to move through it.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        armwatch.run_rolling(
            saved,
            base,
            max_passes=3,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        assert len(_snapshot_files(base)) == 2, "the fixture stopped being a two-file tree"
        assert _read_heartbeat(path)["passes"] == 12

    def test_a_surface_that_archives_nothing_at_all_still_reports(self, tmp_path: Path) -> None:
        """StandaloneLevel was measured EMPTY for a whole 36-minute session.

        A heartbeat that only moved when a file was copied would leave that
        surface permanently silent and unfalsifiable, which is the exact
        defect this item exists to remove.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        dated = [p for p in base.iterdir() if p.is_dir()]
        assert len(dated) == 1
        assert sorted(p.name for p in dated[0].iterdir()) == ["logs", "savedroot"]
        assert "standalonelevel" in _read_heartbeat(path)["surfaces"]

    def test_the_stamp_advances_between_passes(self, tmp_path: Path) -> None:
        """Two readings either side of one pass, with nothing else able to move them."""
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        beat.record("logs")
        first = _read_heartbeat(path)["surfaces"]["logs"]
        ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
        beat.record("logs")
        second = _read_heartbeat(path)["surfaces"]["logs"]
        assert datetime.fromisoformat(second) > datetime.fromisoformat(first)
        assert _read_heartbeat(path)["passes"] == 2


class TestAWedgedSurfaceIsVisible:
    """Four surfaces poll at 3 s, 3 s, 30 s and 300 s.

    One aggregate stamp would let the two 3-second threads keep the file
    looking fresh while the 300-second ``logs`` thread - the slowest, and the
    one carrying the 5,080,313-byte log - sat wedged. Per-surface stamps are
    the entire reason the ``surfaces`` object exists.
    """

    def _wedged(self, tmp_path: Path) -> dict:
        """Drive one surface hard while ``logs`` records once and then stops."""
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path, step_seconds=60.0)
        beat.record("logs")
        for _ in range(20):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record("savegames")
        return _read_heartbeat(path)

    def test_a_stalled_surface_falls_behind_the_others(self, tmp_path: Path) -> None:
        data = self._wedged(tmp_path)
        logs = datetime.fromisoformat(data["surfaces"]["logs"])
        fast = datetime.fromisoformat(data["surfaces"]["savegames"])
        assert (fast - logs).total_seconds() > armwatch.LOG_POLL_S

    def test_the_aggregate_stamp_alone_would_call_the_wedge_healthy(self, tmp_path: Path) -> None:
        """State positively the failure the per-surface stamps prevent.

        ``written`` tracks the last FLUSH, and a flush happens whenever ANY
        surface completes a pass. So with one surface healthy and one wedged,
        ``written`` stays fresh: a reader holding only that number would
        report a healthy watcher while the log surface had been dead for
        twenty minutes.
        """
        data = self._wedged(tmp_path)
        written = datetime.fromisoformat(data["written"])
        logs = datetime.fromisoformat(data["surfaces"]["logs"])
        fast = datetime.fromisoformat(data["surfaces"]["savegames"])
        assert written >= fast
        assert (written - logs).total_seconds() > armwatch.LOG_POLL_S


#: How long a test waits for a surface thread to report or to exit. Generous
#: on purpose: it is not a timing assertion, it is the difference between a
#: test that FAILS and a test that HANGS the suite forever on a thread that
#: never arrived.
_THREAD_JOIN_TIMEOUT_S = 10.0


class _DayFlipClock:
    """A thread-safe ``now_fn`` naming one day until a test flips it.

    ``_SequenceClock`` pops from a list, which is correct for the synchronous
    shape and wrong here: four threads read this clock concurrently and the
    order they happen to arrive in is not a fact about anything. This one
    hands the same reading to every caller until :meth:`flip`, so the day a
    surface sees is decided by the TEST rather than by the scheduler.
    """

    def __init__(self, before: datetime, after: datetime) -> None:
        self._before = before
        self._after = after
        self._flipped = threading.Event()

    def flip(self) -> None:
        self._flipped.set()

    def __call__(self) -> datetime:
        return self._after if self._flipped.is_set() else self._before


class _OnePassPerSurface:
    """A ``sleep_fn`` that walks the THREADED shape through one pass per surface.

    ``run_rolling``'s production shape blocks forever, so the only way into
    its second heartbeat call site is to own the sleeps. Every surface thread
    reports its completed pass and then parks; the main loop's own wait
    collects all four reports and raises the ``KeyboardInterrupt`` the
    function already handles. Nothing here waits on wall-clock time, so the
    run costs no real seconds and has no timing flake in it.

    The surface threads are told apart from the main loop by THREAD NAME
    rather than by the sleep duration, because 60.0 is a literal that could
    drift; a renamed thread instead makes this raise in the wrong thread, the
    main loop's collection times out, and the test fails loudly rather than
    passing while looking somewhere else.

    :meth:`release` must be run or the parked threads outlive the test.
    """

    def __init__(self, surfaces: int) -> None:
        self.surfaces = surfaces
        #: (thread name, seconds) for every surface sleep, so a test can assert
        #: the threaded shape really ran all four rather than one four times.
        self.surface_sleeps: list[tuple[str, float]] = []
        self._reported = threading.Semaphore(0)
        self._parked = threading.Semaphore(0)

    def __call__(self, seconds: float) -> None:
        name = threading.current_thread().name
        if name.startswith("armwatch-"):
            self.surface_sleeps.append((name, seconds))
            self._reported.release()
            self._parked.acquire()
            return
        for _ in range(self.surfaces):
            assert self._reported.acquire(timeout=_THREAD_JOIN_TIMEOUT_S), (
                "a surface thread never reported a completed pass"
            )
        raise KeyboardInterrupt

    def release(self) -> None:
        for _ in range(self.surfaces):
            self._parked.release()


def _armwatch_threads() -> list[threading.Thread]:
    """Every live surface thread, by the name ``run_rolling`` gives them."""
    return [t for t in threading.enumerate() if t.name.startswith("armwatch-")]


class TestTheHeartbeatDescribesItsOwnCadence:
    """ROADMAP item 4f. The interval TRAVELS with the stamp it judges.

    ``TestAWedgedSurfaceIsVisible`` above proves a wedged ``logs`` surface
    falls behind in the file. Visible is not the same as failing, and to
    judge a surface against its OWN cadence a reader needs that cadence.
    There are exactly two places it can come from: this file, or a literal
    re-typed in the reader.

    THAT IS NOT A STYLE PREFERENCE, it is a defect this repo has already
    filed. Cycle 38's reader re-typed ``300.0`` as its own
    ``SLOWEST_POLL_INTERVAL_S`` and the refutation pass flagged the drift
    risk; it is now pinned by a test naming the interval armwatch actually
    uses. Four surfaces means four more chances to re-type a number, so the
    number ships beside the stamp instead.

    STATED COST: the payload grows by one map of at most four numbers, and
    ``surfaces`` and ``intervals`` can disagree for one pass while a surface
    that has never completed one is missing from both. A reader that keys off
    ``intervals`` and looks up ``surfaces`` sees a surface with a cadence and
    no stamp, which is the honest reading of "armed, no completed pass yet"
    and is precisely what the 4f acceptance forbids reading as stale.
    """

    def test_a_bounded_run_records_every_surfaces_own_interval(self, tmp_path: Path) -> None:
        """The synchronous call site, driven through ``run_rolling`` itself.

        A hand-built Heartbeat would prove the map works and nothing at all
        about whether production fills it.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        armwatch.run_rolling(
            saved,
            base,
            max_passes=1,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        data = _read_heartbeat(path)
        assert data["intervals"] == {
            "savegames": 3.0,
            "standalonelevel": 3.0,
            "savedroot": 30.0,
            "logs": 300.0,
        }
        plans = armwatch.session_plan(saved, base / "2026-09-03")
        assert data["intervals"] == {plan.name: plan.poll_seconds for plan in plans}

    def test_the_threaded_shape_records_the_interval_too(self, tmp_path: Path) -> None:
        """The OTHER call site. One updated and one missed is three surfaces of four.

        ``max_passes=None`` is the production shape and the only one an
        operator ever runs, so a test that exercised the bounded loop alone
        would stay green while the threaded path recorded bare names. The
        threads exit through the module's own documented door: tomorrow's
        dated root already holds a ``.git`` marker, so the retarget after the
        clock flips refuses and each thread stops rather than leaking.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        (base / "2026-09-04" / ".git").mkdir(parents=True)
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        clock = _DayFlipClock(datetime(2026, 9, 3, 9, 0, 0), datetime(2026, 9, 4, 9, 0, 0))
        sleeper = _OnePassPerSurface(4)
        said: list[str] = []
        assert not _armwatch_threads(), "a surface thread leaked out of an earlier test"
        try:
            armwatch.run_rolling(
                saved,
                base,
                now_fn=clock,
                sleep_fn=sleeper,
                log_fn=said.append,
                heartbeat=beat,
            )
            data = _read_heartbeat(path)
        finally:
            clock.flip()
            sleeper.release()
            for thread in _armwatch_threads():
                thread.join(timeout=_THREAD_JOIN_TIMEOUT_S)
        assert not _armwatch_threads(), "a surface thread outlived the run"
        assert sum(1 for line in said if line.startswith("stopping ")) == 4
        assert dict(sleeper.surface_sleeps) == {
            "armwatch-savegames": 3.0,
            "armwatch-standalonelevel": 3.0,
            "armwatch-savedroot": 30.0,
            "armwatch-logs": 300.0,
        }, "the threaded shape did not run all four surfaces once each"
        assert data["intervals"] == {
            "savegames": 3.0,
            "standalonelevel": 3.0,
            "savedroot": 30.0,
            "logs": 300.0,
        }

    def test_the_number_comes_from_the_plan_not_from_a_literal(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Re-tune one interval and the payload must follow it.

        A test asserting only ``300.0`` is satisfied by a heartbeat that
        hard-codes ``300.0``, which is the very drift this item exists to
        prevent - the same defect, moved one file to the left.
        """
        monkeypatch.setattr(armwatch, "LOG_POLL_S", 111.0)
        saved = _saved_tree(tmp_path)
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        armwatch.run_rolling(
            saved,
            tmp_path / "captures",
            max_passes=1,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        data = _read_heartbeat(path)
        assert data["intervals"]["logs"] == 111.0
        assert data["intervals"]["savedroot"] == armwatch.SAVED_ROOT_POLL_S

    def test_the_surfaces_map_keeps_its_existing_shape(self, tmp_path: Path) -> None:
        """The ops-layer reader already parses ``surfaces``. It must not move.

        ``intervals`` is a SIBLING map, never a value nested inside the
        stamps, because folding the two together would turn every existing
        reader's ``fromisoformat`` into a ``TypeError`` on the first pass
        after an upgrade.
        """
        saved = _saved_tree(tmp_path)
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        armwatch.run_rolling(
            saved,
            tmp_path / "captures",
            max_passes=1,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        data = _read_heartbeat(path)
        assert set(data) == {"pid", "written", "passes", "surfaces", "intervals"}
        assert set(data["surfaces"]) == set(data["intervals"])
        for name, stamp in data["surfaces"].items():
            assert isinstance(stamp, str), f"{name} stopped being a plain ISO stamp"
            assert datetime.fromisoformat(stamp).utcoffset() == timedelta(0)

    def test_a_surface_recorded_without_an_interval_contributes_no_key(
        self, tmp_path: Path
    ) -> None:
        """Absent, not null. A missing field is a different fact from a null one.

        The positive half matters as much as the negative: the surface is
        still STAMPED, so what is missing is its cadence and nothing else. An
        assertion that only ruled the key out would be satisfied by a
        heartbeat that dropped the surface entirely.
        """
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        beat.record("logs", armwatch.LOG_POLL_S)
        ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
        beat.record("savegames")
        data = _read_heartbeat(path)
        assert data["intervals"] == {"logs": armwatch.LOG_POLL_S}
        assert set(data["surfaces"]) == {"logs", "savegames"}
        assert data["passes"] == 2

    def test_an_unsupplied_interval_never_appears_as_a_null(self, tmp_path: Path) -> None:
        """Read as TEXT, because ``json.loads`` makes both readings look alike.

        ``{"savegames": null}`` and an absent key are one keystroke apart in
        the writer and a different fact to the reader, so this one asks the
        file rather than the parsed object.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("savegames")
        beat.flush()
        text = path.read_text(encoding="ascii")
        assert "null" not in text, f"the heartbeat wrote a null: {text}"
        assert datetime.fromisoformat(_read_heartbeat(path)["surfaces"]["savegames"])

    def test_no_interval_at_all_omits_the_key_rather_than_writing_an_empty_map(
        self, tmp_path: Path
    ) -> None:
        """An empty map is a claim that four surfaces have no cadence. Omit it.

        Pinned positively as well: the rest of the payload is exactly what it
        was before 4f, so nothing here is green merely because the file
        failed to be written.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        data = _read_heartbeat(path)
        assert set(data) == {"pid", "written", "passes", "surfaces"}
        assert "{}" not in path.read_text(encoding="ascii")
        assert data["passes"] == 1
        assert datetime.fromisoformat(data["surfaces"]["logs"])

    def test_an_interval_that_changes_is_updated(self, tmp_path: Path) -> None:
        """First reported wins would freeze a re-tuned cadence into the file."""
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        beat.record("logs", 300.0)
        ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
        beat.record("logs", 30.0)
        data = _read_heartbeat(path)
        assert data["intervals"] == {"logs": 30.0}
        assert data["passes"] == 2

    def test_an_integer_interval_is_written_as_a_float(self, tmp_path: Path) -> None:
        """``3`` and ``3.0`` are the same number and different JSON tokens.

        The reader divides by this value and compares it to a difference of
        timestamps. Normalising here means the type in the file depends on
        the contract rather than on how a caller happened to spell a literal.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("savegames", 3)
        assert isinstance(_read_heartbeat(path)["intervals"]["savegames"], float)

    def test_the_intervals_map_is_sorted_like_the_surfaces_map(self, tmp_path: Path) -> None:
        """Two heartbeats must differ only where the facts differ.

        Insertion order would follow whichever thread finished first, which
        is a fact about the scheduler and about nothing else.
        """
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        for name in ("standalonelevel", "savegames", "savedroot", "logs"):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record(name, 3.0)
        data = _read_heartbeat(path)
        assert list(data["intervals"]) == sorted(data["intervals"])
        assert list(data["surfaces"]) == sorted(data["surfaces"])

    def test_the_interval_lands_under_the_production_default_wiring(self, tmp_path: Path) -> None:
        """No injected clock, no injected monotonic - the real defaults.

        Every other test in this class hands the Heartbeat a clock it can
        move, and this repo has already watched a ``naive_clock`` mutation
        SURVIVE for exactly that reason: a suite where every test injects a
        dependency says nothing about the production default. A watcher armed
        by ``main`` injects nothing at all, so one test has to run that way.
        """
        path = tmp_path / "beat.json"
        before = datetime.now(UTC).replace(microsecond=0)
        beat = armwatch.Heartbeat(path)
        beat.record("logs", armwatch.LOG_POLL_S)
        after = datetime.now(UTC).replace(microsecond=0)
        data = _read_heartbeat(path)
        assert data["intervals"] == {"logs": 300.0}
        assert before <= datetime.fromisoformat(data["surfaces"]["logs"]) <= after


class TestHeartbeatThrottle:
    """The flush RATE is capped; the counting behind it never is.

    Unthrottled, the production shape rewrites this file 28,800 + 28,800 +
    2,880 + 288 = 60,768 times a day for four surfaces polling at 3 s, 3 s,
    30 s and 300 s. OPS-14 (disk pressure) is open.
    """

    def test_the_flush_interval_is_thirty_seconds(self) -> None:
        assert armwatch.HEARTBEAT_FLUSH_INTERVAL_S == 30.0

    def test_the_interval_sits_between_the_fastest_and_slowest_surface(self) -> None:
        """Coarser than the fastest surface, or the reduction is given back.

        Finer than the slowest, or the throttle itself becomes the reason a
        ``logs`` stamp looks stale.
        """
        assert armwatch.HEARTBEAT_FLUSH_INTERVAL_S >= armwatch.MATCH_LIFETIME_POLL_S
        assert armwatch.HEARTBEAT_FLUSH_INTERVAL_S < armwatch.LOG_POLL_S

    def test_records_inside_the_interval_are_counted_but_not_written(self, tmp_path: Path) -> None:
        """The throttle caps WRITES. Losing a pass from the count would be a bug."""
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        for _ in range(100):
            beat.record("savegames")
        assert _read_heartbeat(path)["passes"] == 1
        beat.flush()
        assert _read_heartbeat(path)["passes"] == 100

    def test_a_record_after_the_interval_flushes(self, tmp_path: Path) -> None:
        path = tmp_path / "beat.json"
        beat, _clock, ticks = _beat(path)
        beat.record("savegames")
        beat.record("savegames")
        assert _read_heartbeat(path)["passes"] == 1
        ticks.value = armwatch.HEARTBEAT_FLUSH_INTERVAL_S
        beat.record("savegames")
        assert _read_heartbeat(path)["passes"] == 3

    def test_the_first_record_writes_immediately(self, tmp_path: Path) -> None:
        """An absent file is ambiguous with being armed without --heartbeat.

        Waiting a full interval before the first write would leave a reader
        that polls straight after arming unable to tell those apart, which is
        the same ambiguity 4e exists to close.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        assert not path.exists()
        beat.record("savegames")
        assert path.is_file()


class TestHeartbeatWriteIsAtomic:
    """A reader polls this file, so it must never observe a half-written one."""

    def test_no_temporary_file_survives_a_flush(self, tmp_path: Path) -> None:
        path = tmp_path / "runtime" / "beat.json"
        beat, _clock, ticks = _beat(path)
        for _ in range(3):
            ticks.value += armwatch.HEARTBEAT_FLUSH_INTERVAL_S
            beat.record("logs")
        assert [p.name for p in sorted(path.parent.iterdir())] == ["beat.json"]

    def test_the_payload_never_goes_straight_into_the_polled_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """``tmp.write_text(...)`` then ``tmp.replace(target)``, stated positively.

        Asserting only that no ``.tmp`` file survives is a NEGATIVE: it is
        satisfied just as well by an implementation that never made one and
        wrote straight over the live file, which is precisely the shape that
        lets a reader observe a half-written object. Found by mutating the
        write to ``target.write_text(...)`` and watching all 69 tests stay
        green. So this one records where the bytes actually went.
        """
        path = tmp_path / "beat.json"
        written: list[Path] = []
        replaced: list[tuple[Path, Path]] = []
        real_write = Path.write_text
        real_replace = Path.replace

        def spy_write(self, *args, **kwargs):
            written.append(Path(self))
            return real_write(self, *args, **kwargs)

        def spy_replace(self, target):
            replaced.append((Path(self), Path(target)))
            return real_replace(self, target)

        monkeypatch.setattr(Path, "write_text", spy_write)
        monkeypatch.setattr(Path, "replace", spy_replace)
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        monkeypatch.undo()

        assert written, "nothing was written at all - the spy never fired"
        assert path not in written, "the payload went straight into the file a reader polls"
        landed = [source for source, target in replaced if target == path]
        assert landed, "no atomic replace ever landed the payload on the target path"
        assert all(source.name.endswith(".tmp") for source in landed)
        assert all(source.parent == path.parent for source in landed), (
            "the temp file must sit in the target's own directory, or the "
            "replace is a cross-volume copy and stops being atomic"
        )
        assert _read_heartbeat(path)["passes"] == 1, (
            "the replace happened but published nothing readable"
        )

    def test_the_parent_directory_is_created(self, tmp_path: Path) -> None:
        """``ops/runtime/`` is gitignored and may not exist on a fresh clone."""
        path = tmp_path / "runtime" / "deeper" / "beat.json"
        beat, _clock, _ticks = _beat(path)
        beat.record("logs")
        assert path.is_file()


class TestHeartbeatFailureNeverStopsTheWatcher:
    """A watcher that dies for want of its own heartbeat is worse than one without."""

    def test_a_failing_write_is_absorbed_and_polling_continues(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        path = tmp_path / "beat.json"
        beat = _spy_heartbeat(_RefusingHeartbeat, path)
        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
            heartbeat=beat,
        )
        assert beat.failed_writes >= 1, "the write never failed - this guard proves nothing"
        assert _snapshot_files(base), "archiving stopped when the heartbeat failed"
        assert not path.exists()

    def test_a_real_unwritable_path_does_not_stop_the_run(self, tmp_path: Path) -> None:
        """No spy: the parent of the heartbeat path IS an ordinary file.

        A guard proven only against a monkeypatched raise is proven against
        the monkeypatch. Here the OSError comes from the filesystem.
        """
        blocker = tmp_path / "blocker"
        blocker.write_bytes(b"not a directory\n")
        beat, _clock, _ticks = _beat(blocker / "beat.json")
        beat.record("logs")
        assert beat.failed_writes >= 1
        assert blocker.read_bytes() == b"not a directory\n"

    def test_a_non_oserror_from_the_write_is_not_swallowed(self, tmp_path: Path) -> None:
        """``except Exception`` would eat an AssertionError and make spies vacuous.

        This repo has paid for that once already. The catch around the flush
        names ``OSError`` and nothing wider, and this is the test that says so.
        """
        beat = _spy_heartbeat(_AssertingHeartbeat, tmp_path / "beat.json")
        with pytest.raises(AssertionError):
            beat.record("logs")

    def test_the_run_does_not_swallow_it_either(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        beat = _spy_heartbeat(_AssertingHeartbeat, tmp_path / "beat.json")
        with pytest.raises(AssertionError):
            armwatch.run_rolling(
                saved,
                tmp_path / "captures",
                max_passes=1,
                now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
                sleep_fn=lambda _s: None,
                log_fn=lambda _m: None,
                heartbeat=beat,
            )


class TestAFailedFlushDoesNotConsumeTheThrottleWindow:
    """A write that did not happen consumed none of the rate the throttle caps.

    FOUND BY AN ADVERSARIAL REFUTATION PASS, with a reproduction. The flush
    used to stamp ``_last_flush`` BEFORE attempting the write and then absorb
    the ``OSError``, so a flush that failed still spent the full 30-second
    window: the file was not written, and the next 30 seconds of passes
    declined to try again.

    THE MEASURED CONSEQUENCE, with every surface polling exactly on cadence:

        t=70  failed_writes=2  ->  SURFACE_STALE  stale=('savegames',)

    That is a HEALTHY watcher reported as having a wedged surface. The 4f
    reader's per-surface threshold is ``k * poll + 2 * flush``, which for a
    3-second surface is ``3 * 3 + 2 * 30`` = 69 s - and 60 s of that 69 is
    the flush slack, so two failed flushes eat the entire allowance the
    throttle was granted and leave about 6 s of honest headroom. A check that
    cries wolf on a healthy watcher is worse than no check at all, because it
    trains its reader to ignore it.

    The throttle itself is not the defect and is not relaxed here: the
    control below asserts that a SUCCESSFUL flush still holds off the next
    one, so "retry always" is not a passing answer.
    """

    def test_a_failed_flush_is_retried_by_the_next_record(self, tmp_path: Path) -> None:
        """The reproduction. The clock does not move, and the retry happens anyway.

        Positive as well as negative: the recovered file is parsed and its
        contents asserted, so this cannot pass on a heartbeat that merely
        stopped raising.
        """
        path = tmp_path / "beat.json"
        beat = _spy_heartbeat(_RecoveringHeartbeat, path)
        beat.fails_left = 1

        beat.record("savegames", armwatch.MATCH_LIFETIME_POLL_S)
        assert beat.write_attempts == 1
        assert beat.failed_writes == 1, "the write never failed - this guard proves nothing"
        assert not path.exists()

        beat.record("savegames", armwatch.MATCH_LIFETIME_POLL_S)
        assert beat.write_attempts == 2, "the throttle ate the retry after a failed write"
        assert beat.failed_writes == 1
        data = _read_heartbeat(path)
        assert data["passes"] == 2
        assert data["intervals"] == {"savegames": armwatch.MATCH_LIFETIME_POLL_S}
        assert data["surfaces"]["savegames"].endswith("+00:00")

    def test_a_real_failing_destination_is_retried_and_recovers(self, tmp_path: Path) -> None:
        """No spy anywhere: a real OSError from the filesystem, and a real recovery.

        A guard proven only against a monkeypatched raise is proven against
        the monkeypatch, and this module has its own precedent for an
        injected dependency leaving the production path unexercised - the
        naive clock. Here the parent of the heartbeat path IS an ordinary
        file, so ``mkdir`` raises ``FileExistsError``; deleting it lets the
        real :meth:`Heartbeat._write` succeed.
        """
        blocker = tmp_path / "runtime"
        blocker.write_bytes(b"not a directory\n")
        path = blocker / "beat.json"
        beat, _clock, ticks = _beat(path)

        beat.record("savedroot", armwatch.SAVED_ROOT_POLL_S)
        assert beat.failed_writes == 1
        beat.record("savedroot", armwatch.SAVED_ROOT_POLL_S)
        assert beat.failed_writes == 2, "the retry never happened - the throttle ate it"
        assert ticks.value == 0.0, "the retry must not need the clock to have moved"
        assert blocker.read_bytes() == b"not a directory\n"

        blocker.unlink()
        beat.record("savedroot", armwatch.SAVED_ROOT_POLL_S)
        assert beat.failed_writes == 2
        data = _read_heartbeat(path)
        assert data["passes"] == 3
        assert data["intervals"] == {"savedroot": armwatch.SAVED_ROOT_POLL_S}

    def test_a_successful_flush_still_consumes_the_window(self, tmp_path: Path) -> None:
        """The control. Same spy, same frozen clock, nothing failing.

        Without this, "retry on every record" passes the reproduction above
        while handing back the entire 60,768-writes-a-day reduction the
        throttle exists to buy, and a mutation replacing the throttle check
        with ``return False`` would survive.
        """
        path = tmp_path / "beat.json"
        beat = _spy_heartbeat(_RecoveringHeartbeat, path)

        beat.record("savegames", armwatch.MATCH_LIFETIME_POLL_S)
        assert beat.write_attempts == 1
        assert beat.failed_writes == 0

        for _ in range(50):
            beat.record("savegames", armwatch.MATCH_LIFETIME_POLL_S)
        assert beat.write_attempts == 1, "a successful flush stopped throttling the next one"
        assert _read_heartbeat(path)["passes"] == 1

    def test_the_throttle_resumes_from_the_write_that_actually_landed(
        self, tmp_path: Path
    ) -> None:
        """After a recovery the window is measured from the SUCCESS, not the failure.

        The third shape, and the one that says ``_last_flush`` is neither
        stamped on a failure nor abandoned once a write lands: a failure at
        t=0, a retry that succeeds at t=5, and then a full interval of
        silence measured from 5 rather than from 0.
        """
        path = tmp_path / "beat.json"
        ticks = _FrozenMonotonic()
        beat = _spy_heartbeat(_RecoveringHeartbeat, path, monotonic_fn=ticks)
        beat.fails_left = 1

        beat.record("logs", armwatch.LOG_POLL_S)
        assert beat.failed_writes == 1
        ticks.value = 5.0
        beat.record("logs", armwatch.LOG_POLL_S)
        assert beat.write_attempts == 2
        assert _read_heartbeat(path)["passes"] == 2

        ticks.value = 5.0 + armwatch.HEARTBEAT_FLUSH_INTERVAL_S - 1.0
        beat.record("logs", armwatch.LOG_POLL_S)
        assert beat.write_attempts == 2, "the window is measured from the successful write"
        assert _read_heartbeat(path)["passes"] == 2

        ticks.value = 5.0 + armwatch.HEARTBEAT_FLUSH_INTERVAL_S
        beat.record("logs", armwatch.LOG_POLL_S)
        assert beat.write_attempts == 3
        assert _read_heartbeat(path)["passes"] == 4


class TestHeartbeatUnderThreads:
    """The production shape is four daemon threads sharing one Heartbeat."""

    def test_concurrent_records_lose_no_passes(self, tmp_path: Path) -> None:
        """``passes += 1`` is a read-modify-write and four threads share it.

        The monotonic clock stays frozen, so exactly one write happens during
        the hammering and the final forced flush reports what the counter
        actually holds.
        """
        path = tmp_path / "beat.json"
        beat, _clock, _ticks = _beat(path)
        names = ["savegames", "standalonelevel", "savedroot", "logs"]

        def hammer(name: str) -> None:
            for _ in range(500):
                beat.record(name)

        threads = [threading.Thread(target=hammer, args=(name,)) for name in names]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        beat.flush()
        data = _read_heartbeat(path)
        assert data["passes"] == 4 * 500
        assert set(data["surfaces"]) == set(names)


class TestHeartbeatCommandLine:
    """``--heartbeat`` is optional, and refuses the one pairing it cannot honour."""

    def test_dest_root_with_heartbeat_is_refused(self, tmp_path: Path, capsys) -> None:
        """A silently ignored flag is a trap.

        ``--dest-root`` runs the literal-destination path, which is not
        ``run_rolling`` and writes no heartbeat. Accepting the flag there
        would leave a reader polling a file nothing ever writes, and reporting
        a healthy watcher dead.
        """
        saved = _saved_tree(tmp_path)
        path = tmp_path / "beat.json"
        dest = tmp_path / "dest"
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-root",
                str(dest),
                "--heartbeat",
                str(path),
                "--max-passes",
                "1",
            ]
        )
        assert rc != 0
        assert not path.exists()
        assert not dest.exists(), "the run went ahead anyway and archived into dest-root"
        err = capsys.readouterr().err
        assert "--heartbeat" in err
        assert "--dest-root" in err
        assert "--dest-base" in err

    def test_dest_base_with_heartbeat_is_accepted(self, tmp_path: Path) -> None:
        saved = _saved_tree(tmp_path)
        path = tmp_path / "beat.json"
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-base",
                str(tmp_path / "captures"),
                "--heartbeat",
                str(path),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 0
        data = _read_heartbeat(path)
        assert data["pid"] == os.getpid()
        assert data["passes"] == 4
        assert set(data["surfaces"]) == {"savegames", "standalonelevel", "savedroot", "logs"}

    def test_a_refused_dest_base_writes_no_heartbeat(self, tmp_path: Path) -> None:
        """Building a Heartbeat touches no filesystem, so a refusal leaves none."""
        saved = _saved_tree(tmp_path)
        fake_repo = tmp_path / "checkout"
        (fake_repo / ".git").mkdir(parents=True)
        path = tmp_path / "beat.json"
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-base",
                str(fake_repo / "captures"),
                "--heartbeat",
                str(path),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 2
        assert not path.exists()

    def test_without_the_flag_no_heartbeat_is_built_at_all(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Absent means absent: no object, no file, no syscall.

        A watcher armed by an older session passes no such flag, so this path
        has to behave exactly as it did before 4e.
        """
        saved = _saved_tree(tmp_path)
        monkeypatch.setattr(armwatch, "Heartbeat", _Detonator)
        rc = armwatch.main(
            [
                "--saved-dir",
                str(saved),
                "--dest-base",
                str(tmp_path / "captures"),
                "--max-passes",
                "1",
            ]
        )
        assert rc == 0

    def test_the_detonator_fires_when_the_flag_is_present(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Proves the test above is not passing because the patch missed.

        A mutation that fails to apply looks exactly like a passing test, so
        the spy has to be shown firing before its silence means anything.
        """
        saved = _saved_tree(tmp_path)
        monkeypatch.setattr(armwatch, "Heartbeat", _Detonator)
        with pytest.raises(_HeartbeatWasBuilt):
            armwatch.main(
                [
                    "--saved-dir",
                    str(saved),
                    "--dest-base",
                    str(tmp_path / "captures"),
                    "--heartbeat",
                    str(tmp_path / "beat.json"),
                    "--max-passes",
                    "1",
                ]
            )

    def test_run_rolling_without_a_heartbeat_writes_nothing_new(self, tmp_path: Path) -> None:
        """The default is None and that path stays exactly as it was."""
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        armwatch.run_rolling(
            saved,
            base,
            max_passes=2,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=lambda _m: None,
        )
        assert sorted(p.name for p in tmp_path.iterdir()) == ["Saved", "captures"]


class TestARefusedDestinationFreezesItsSurface:
    """`OPS-26`. A watcher archiving NOTHING must stop looking healthy.

    PROVOKED 2026-09-05 before a line of this was written. Against a
    destination that refused every copy - once by a real filesystem
    ``PermissionError``, once by ``OSError(28)``, the ``ENOSPC`` this machine
    actually hit - ``run_rolling`` completed 12 passes, advanced the heartbeat,
    kept all four surfaces inside their thresholds, archived ZERO files, and
    ``check_watcher`` reported ``ARMED`` / ``VERIFIED``.

    The fix reuses the machinery a reader ALREADY consults instead of adding a
    channel it does not: a refused surface stops recording, so ``4f``'s
    per-surface staleness names it. **This class proves only that the surface
    stops recording.** That a stopped surface is then reported as
    ``SURFACE_STALE`` and NAMED is ``4f``'s property and is covered in
    ``tests/test_loop_watch.py``; duplicating it here would be a second copy of
    a roster. An earlier draft of this docstring put a NUMBER on that coverage
    and the number was the token's occurrence count, not the assertion count -
    a filed count, in a docstring, in the cycle that had just paid for one.

    The composition was watched end to end on the FIXED code anyway - threaded,
    every copy refused with ENOSPC: ``ARMED`` at 5 s and 40 s, then
    ``SURFACE_STALE`` naming ``savegames`` at 78 s and 88 s, zero files archived
    throughout.

    It must not fire on a transient. A save file vanishing mid-copy is exactly
    the transience this watcher exists for, and the game does NOT hold its log
    exclusively - measured on the real archive, ten consecutive log snapshots
    at the 300 s cadence straight through play session S3 on 2026-08-30,
    ``20260830-003030`` to ``20260830-011530``, inside a session running local
    00:20:37 to 01:24:23.
    """

    class _Spy:
        """Counts records per surface. The heartbeat FILE cannot answer this.

        Freezing means a surface's stamp stops ADVANCING, not that its key
        disappears - the heartbeat keeps the last stamp it ever wrote. An
        earlier draft of these tests asserted the key was absent and failed
        against correct code.
        """

        def __init__(self) -> None:
            self.calls: list[str] = []

        def record(self, surface: str, poll_seconds: float | None = None) -> None:
            self.calls.append(surface)

        def flush(self) -> None:
            pass

        def count(self, surface: str) -> int:
            return self.calls.count(surface)

    def _run(self, saved, base, spy, passes, messages=None):
        armwatch.run_rolling(
            saved,
            base,
            max_passes=passes,
            now_fn=_SequenceClock(datetime(2026, 9, 3, 9, 0, 0)),
            sleep_fn=lambda _s: None,
            log_fn=(lambda m: messages.append(m)) if messages is not None else (lambda _m: None),
            heartbeat=spy,
        )

    def test_a_refused_surface_stops_recording_at_the_threshold(self, tmp_path, monkeypatch):
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        spy = self._Spy()

        def _refuse(src, dst, *a, **kw):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(savewatch.shutil, "copy2", _refuse)
        passes = armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES + 2
        self._run(saved, base, spy, passes)

        assert _snapshot_files(base) == [], "the fixture must archive nothing"
        threshold = armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES
        for refused in ("logs", "savedroot"):
            assert spy.count(refused) == threshold - 1, (
                f"{refused} has a file it is refused every pass, so it must record "
                f"until its count REACHES the threshold and then stop"
            )

    def test_an_empty_surface_is_idle_not_refused_and_keeps_reporting(
        self, tmp_path, monkeypatch
    ):
        """StandaloneLevel was measured EMPTY for a whole 36-minute session.

        It attempts no copy, so it can never be refused. Freezing it would cry
        wolf on the normal case and would undo
        TestHeartbeatAdvancesWithNothingArchived.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        spy = self._Spy()

        def _refuse(src, dst, *a, **kw):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(savewatch.shutil, "copy2", _refuse)
        passes = armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES + 2
        self._run(saved, base, spy, passes)

        for idle in ("standalonelevel", "savegames"):
            assert spy.count(idle) == passes, (
                f"{idle} is empty, attempts nothing, and must report every pass"
            )

    def test_a_single_transient_failure_does_not_freeze_anything(self, tmp_path, monkeypatch):
        """One failure is the NORMAL vanish and must be invisible to a reader."""
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        spy = self._Spy()

        real_copy2 = savewatch.shutil.copy2
        calls = {"n": 0}

        def _fails_once(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FileNotFoundError("simulated vanish mid-copy")
            return real_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(savewatch.shutil, "copy2", _fails_once)
        passes = armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES + 2
        self._run(saved, base, spy, passes)

        assert calls["n"] > 1, "sanity check: the fixture must have retried after failing"
        for name in ("logs", "savedroot", "savegames", "standalonelevel"):
            assert spy.count(name) == passes, (
                f"{name} must report every pass - one transient failure is not a "
                f"refused destination"
            )

    def test_a_surface_resumes_when_the_destination_comes_back(self, tmp_path, monkeypatch):
        """Frozen is not dead - the old mkdir path killed the thread outright.

        This has to happen inside ONE ``run_rolling`` call. A second call builds
        fresh watchers with a fresh count, so a two-call version would pass just
        as happily if freezing were permanent: it would be measuring the new
        watcher rather than the recovery.
        """
        saved = _saved_tree(tmp_path)
        base = tmp_path / "captures"
        spy = self._Spy()
        messages: list[str] = []

        real_copy2 = savewatch.shutil.copy2
        # Two files are offered per pass (logs and savedroot), so this refuses
        # exactly the first `threshold` passes and then lets the copies land.
        budget = {"n": armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES * 2}

        def _recovers(src, dst, *a, **kw):
            if budget["n"] > 0:
                budget["n"] -= 1
                raise OSError(28, "No space left on device")
            return real_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(savewatch.shutil, "copy2", _recovers)
        passes = armwatch.FAILING_PASSES_BEFORE_SURFACE_FREEZES + 3
        self._run(saved, base, spy, passes, messages=messages)

        froze = [m for m in messages if "freezing its heartbeat" in m and m.startswith("logs")]
        resumed = [m for m in messages if "archiving again" in m and m.startswith("logs")]
        assert froze, f"logs must announce the freeze; saw {messages}"
        assert resumed, f"logs must announce the recovery; saw {messages}"
        assert spy.count("logs") == passes - 1, (
            "exactly one pass - the one that crossed the threshold - may be skipped"
        )
        assert _snapshot_files(base), "the recovered destination must actually archive"


class TestBOTHCallSitesRouteThroughTheFreeze:
    """`OPS-26`. The production loop is the one no behavioural test reaches.

    ``run_rolling`` has TWO places that record a pass: a synchronous branch
    driven by ``max_passes``, and ``poll_forever``, the threaded loop that
    ``default_spawn`` actually runs. Every behavioural test in this file drives
    the synchronous branch, because a surface's poll interval is fixed by
    ``session_plan`` and is not injectable, so a threaded test would have to
    spend 9 real seconds to see one freeze.

    The cycle 47 refutation measured what that leaves uncovered: reverting the
    THREADED call site alone to ``heartbeat.record(...)`` left the whole suite
    at **1769 passed**. The guard existed and production did not have it.
    ``docs/LEDGER.md`` records this repo hitting the identical two-call-site
    defect once already, on the ``4e`` heartbeat.

    This is a STRUCTURAL guard, and that is a deliberate second-best. It cannot
    prove the threaded loop behaves correctly; it proves the two call sites
    cannot DIVERGE, which is the failure that actually happened.
    """

    def _run_rolling_ast(self) -> ast.FunctionDef:
        source = Path(armwatch.__file__).read_text(encoding="ascii")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_rolling":
                return node
        raise AssertionError("run_rolling not found - this test is measuring the wrong file")

    def _nested(self, parent: ast.FunctionDef, name: str) -> ast.FunctionDef:
        for node in ast.walk(parent):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError(f"{name} not found inside run_rolling")

    def test_every_heartbeat_record_call_sits_inside_record_pass(self) -> None:
        run_rolling = self._run_rolling_ast()
        recorder = self._nested(run_rolling, "record_pass")
        lo, hi = recorder.lineno, recorder.end_lineno

        direct = [
            node.lineno
            for node in ast.walk(run_rolling)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "heartbeat"
        ]
        assert direct, "no heartbeat.record call found at all - the pattern is wrong"
        outside = [line for line in direct if not lo <= line <= hi]
        assert outside == [], (
            f"heartbeat.record is called directly at line(s) {outside}, outside "
            f"record_pass (lines {lo}-{hi}). Both call sites must route through the "
            f"freeze, or one of them keeps reporting a surface that archives nothing."
        )

    def test_the_threaded_loop_records_through_record_pass(self) -> None:
        run_rolling = self._run_rolling_ast()
        forever = self._nested(run_rolling, "poll_forever")
        called = {
            node.func.id
            for node in ast.walk(forever)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "record_pass" in called, (
            "poll_forever is the loop default_spawn runs in production - it must "
            "record through record_pass, not around it"
        )
