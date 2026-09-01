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
"""

import sys
import threading
from datetime import datetime
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
