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
"""

import sys
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
