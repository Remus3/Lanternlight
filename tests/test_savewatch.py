"""Tests for lanternlight.savewatch - the save-file generation snapshotter.

lanternlight.savewatch exists because one save file the game writes,
StandaloneSlot_<roleId>.sav, is TRANSIENT. Measured on 2026-08-09 by a
stopgap poller (see arm_save_snapshot.py in the session scratchpad, now
superseded by this module): the file appeared at 2,190 bytes and grew
through 33,610 / 35,062 / 36,514 / 41,133 / 43,801 / 44,517 bytes over
roughly 70 seconds, and the game deletes the file entirely about 13 minutes
after it first appears. A watcher that copies only on first sight would
capture a truncated file, so SaveWatcher must capture every observed
generation - identity is (name, size, mtime_ns) - and must never touch the
source directory, and must refuse to write its copies inside a git working
directory, because the saves carry the operator's roleId in the filename and
platform identifiers in the bytes (see the PII HAZARD block in .gitignore).

Every test here runs entirely against tmp_path and hand-built files. None of
it needs the game, the live save directory, or a specific machine, except the
one test in TestAgainstTheRealWorktree, which grounds the guard against the
actual repository this file lives in and skips cleanly if that precondition
does not hold.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import savewatch  # noqa: E402  (path bootstrap must run first)


def _touch(path: Path, data: bytes, mtime_ns: int) -> None:
    """Write ``data`` to ``path`` and pin its mtime explicitly.

    Two quick writes to the same path can land in the same filesystem mtime
    tick, which would make identity-change tests flaky depending on how fast
    the test happens to run. Pinning mtime_ns removes real clock timing from
    the test entirely.
    """
    path.write_bytes(data)
    os.utime(path, ns=(mtime_ns, mtime_ns))


def _safe_dest(tmp_path: Path) -> Path:
    """A destination that is definitely not inside any git working directory."""
    return tmp_path / "captures"


class TestDestinationMustNotBeInsideARepo:
    """The single most important guard in this module.

    Save files carry the operator's roleId in their filename and platform
    identifiers in their bytes. .gitignore's PII HAZARD block states the rule
    in prose; this class proves the module enforces it mechanically rather
    than relying on a human remembering the rule.
    """

    def test_refuses_a_dest_dir_that_is_a_repo_root(self, tmp_path):
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / ".git").mkdir(parents=True)
        with pytest.raises(savewatch.DestinationInsideRepoError):
            savewatch.SaveWatcher(source_dir=tmp_path / "src", dest_dir=fake_repo)

    def test_refuses_a_dest_dir_nested_under_a_repo_root(self, tmp_path):
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / ".git").mkdir(parents=True)
        # Deliberately does not exist yet - the guard must not need to stat it.
        nested = fake_repo / "some" / "deep" / "captures"
        with pytest.raises(savewatch.DestinationInsideRepoError):
            savewatch.SaveWatcher(source_dir=tmp_path / "src", dest_dir=nested)

    def test_refuses_when_the_git_marker_is_a_file_not_a_directory(self, tmp_path):
        # A linked worktree's .git is a FILE containing "gitdir: ...", not a
        # directory - the primary checkout's .git is a directory. This repo
        # itself is running as a worktree, so this is the shape that matters
        # most in practice.
        fake_worktree = tmp_path / "fake_worktree"
        fake_worktree.mkdir()
        (fake_worktree / ".git").write_text("gitdir: /somewhere/else\n", encoding="ascii")
        with pytest.raises(savewatch.DestinationInsideRepoError):
            savewatch.SaveWatcher(
                source_dir=tmp_path / "src", dest_dir=fake_worktree / "captures"
            )

    def test_refusal_message_names_the_offending_path(self, tmp_path):
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / ".git").mkdir(parents=True)
        dest = fake_repo / "captures"
        with pytest.raises(savewatch.DestinationInsideRepoError, match="captures"):
            savewatch.SaveWatcher(source_dir=tmp_path / "src", dest_dir=dest)

    def test_allows_a_destination_with_no_repo_in_its_ancestry(self, tmp_path):
        dest = _safe_dest(tmp_path)
        watcher = savewatch.SaveWatcher(source_dir=tmp_path / "src", dest_dir=dest)
        assert watcher.dest_dir == dest.resolve()

    def test_a_sibling_directory_sharing_a_name_prefix_is_not_refused(self, tmp_path):
        # Guards against a naive string-prefix check: "fake_repository" must
        # not be treated as inside "fake_repo".
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / ".git").mkdir(parents=True)
        sibling = tmp_path / "fake_repository" / "captures"
        watcher = savewatch.SaveWatcher(source_dir=tmp_path / "src", dest_dir=sibling)
        assert watcher.dest_dir == sibling.resolve()

    def test_the_predicate_function_is_directly_callable(self, tmp_path):
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / ".git").mkdir(parents=True)
        assert savewatch.is_inside_repo_working_directory(fake_repo / "x") is True
        assert savewatch.is_inside_repo_working_directory(tmp_path / "elsewhere") is False


class TestAgainstTheRealWorktree:
    def test_refuses_a_destination_inside_this_actual_checkout(self, tmp_path):
        if not (REPO_ROOT / ".git").exists():
            pytest.skip("this checkout has no .git - cannot exercise the real guard")
        with pytest.raises(savewatch.DestinationInsideRepoError):
            savewatch.SaveWatcher(
                source_dir=tmp_path / "src",
                dest_dir=REPO_ROOT / "would_be_pii_if_this_worked",
            )


class TestNewFileAppearing:
    def test_a_new_file_produces_one_snapshot_with_matching_bytes(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        _touch(src_dir / "StandaloneSlot_1.sav", b"A" * 2190, mtime_ns=1_000_000_000)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert len(snaps) == 1
        assert snaps[0].size == 2190
        assert snaps[0].destination.exists()
        assert snaps[0].destination.read_bytes() == b"A" * 2190

    def test_two_new_files_in_one_pass_are_both_captured(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        _touch(src_dir / "a.sav", b"aaaa", mtime_ns=1_000_000_000)
        _touch(src_dir / "b.sav", b"bbbbbb", mtime_ns=1_000_000_000)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert {s.source.name for s in snaps} == {"a.sav", "b.sav"}

    def test_a_subdirectory_in_source_is_not_treated_as_a_file(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "SomeSubdir").mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert snaps == []


class TestChangedFileGrowsThroughGenerations:
    def test_growth_produces_a_new_snapshot_per_observed_size(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        target = src_dir / "StandaloneSlot_7.sav"

        # The exact sequence measured 2026-08-09.
        sizes = [2190, 33610, 35062, 36514, 41133, 43801, 44517]
        all_snaps = []
        for i, size in enumerate(sizes):
            _touch(target, b"S" * size, mtime_ns=1_000_000_000 + i * 10_000_000_000)
            all_snaps.extend(watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, i)))

        assert [s.size for s in all_snaps] == sizes
        # Every generation actually landed on disk with the right byte count,
        # and none of them overwrote an earlier one.
        assert len({s.destination for s in all_snaps}) == len(sizes)
        for snap, size in zip(all_snaps, sizes, strict=True):
            assert snap.destination.stat().st_size == size

    def test_identity_includes_mtime_so_a_same_size_rewrite_is_still_captured(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        target = src_dir / "flaps.sav"

        _touch(target, b"Q" * 100, mtime_ns=1_000_000_000)
        first = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))

        _touch(target, b"R" * 100, mtime_ns=2_000_000_000)  # same size, new content+mtime
        second = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 5))

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].destination != second[0].destination
        assert second[0].destination.read_bytes() == b"R" * 100


class TestUnchangedFileIsNotRecopied:
    def test_polling_twice_without_a_change_yields_nothing_the_second_time(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = _safe_dest(tmp_path)
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=dest_dir)
        _touch(src_dir / "steady.sav", b"X" * 100, mtime_ns=5_000_000_000)

        first = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        second = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 5))
        third = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 10))

        assert len(first) == 1
        assert second == []
        assert third == []
        assert len(list(dest_dir.iterdir())) == 1, "no duplicate copy may land in dest"


class TestSourceDirectoryIsNeverTouched:
    def test_source_bytes_and_stat_are_unchanged_after_a_snapshot_pass(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        f1 = src_dir / "one.sav"
        f2 = src_dir / "two.sav"
        _touch(f1, b"hello world", mtime_ns=2_000_000_000)
        _touch(f2, b"another file entirely, and longer", mtime_ns=3_000_000_000)

        def _fingerprint():
            return {
                p.name: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
                for p in src_dir.iterdir()
            }

        before = _fingerprint()
        before_names = {p.name for p in src_dir.iterdir()}

        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert len(snaps) == 2, "sanity check: the pass must actually have done something"

        after = _fingerprint()
        after_names = {p.name for p in src_dir.iterdir()}

        assert after == before, "source directory must be byte-identical after a snapshot pass"
        assert after_names == before_names, "no file may appear or disappear in the source"


class TestMissingOrUnreadableSourceSurvives:
    def test_a_source_dir_that_does_not_exist_yields_no_snapshots_and_does_not_raise(
        self, tmp_path
    ):
        missing = tmp_path / "does_not_exist"
        watcher = savewatch.SaveWatcher(source_dir=missing, dest_dir=_safe_dest(tmp_path))
        assert watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0)) == []

    def test_a_source_that_is_a_file_not_a_directory_yields_no_snapshots(self, tmp_path):
        # iterdir() on a non-directory raises OSError (NotADirectoryError) -
        # the same failure shape as a permissions refusal, and portable across
        # platforms without needing real ACL manipulation (which an
        # administrator account routinely bypasses anyway).
        not_a_dir = tmp_path / "not_a_dir"
        not_a_dir.write_text("i am a file", encoding="ascii")
        watcher = savewatch.SaveWatcher(source_dir=not_a_dir, dest_dir=_safe_dest(tmp_path))
        assert watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0)) == []

    def test_a_permission_error_from_iterdir_is_swallowed_too(self, tmp_path, monkeypatch):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        def _raise(self):
            raise PermissionError("simulated: access denied")

        monkeypatch.setattr(Path, "iterdir", _raise)
        assert watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0)) == []


class TestFileVanishingBetweenListingAndCopying:
    def test_vanishing_at_copy_time_does_not_crash_and_other_files_still_land(
        self, tmp_path, monkeypatch
    ):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        vanishing = src_dir / "StandaloneSlot_9.sav"
        surviving = src_dir / "steady.sav"
        _touch(vanishing, b"V" * 500, mtime_ns=9_000_000_000)
        _touch(surviving, b"S" * 10, mtime_ns=9_000_000_000)

        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        real_copy2 = savewatch.shutil.copy2

        def _flaky_copy2(src, dst, *a, **kw):
            if Path(src).name == vanishing.name:
                raise FileNotFoundError(f"simulated vanish mid-copy: {src}")
            return real_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(savewatch.shutil, "copy2", _flaky_copy2)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))

        assert {s.source.name for s in snaps} == {"steady.sav"}
        leftovers = [p.name for p in watcher.dest_dir.iterdir() if ".part" in p.name]
        assert leftovers == [], "a failed copy must not leave a temp file behind"

    def test_vanishing_between_listing_and_stat_does_not_crash(self, tmp_path, monkeypatch):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        vanishing = src_dir / "gone.sav"
        surviving = src_dir / "steady.sav"
        _touch(vanishing, b"G" * 50, mtime_ns=9_000_000_000)
        _touch(surviving, b"S" * 10, mtime_ns=9_000_000_000)

        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        real_stat = Path.stat

        def _flaky_stat(self, *a, **kw):
            if self.name == vanishing.name:
                raise FileNotFoundError(f"simulated vanish before stat: {self}")
            return real_stat(self, *a, **kw)

        monkeypatch.setattr(Path, "stat", _flaky_stat)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert {s.source.name for s in snaps} == {"steady.sav"}

    def test_a_failed_copy_is_RETRIED_on_the_next_pass(self, tmp_path, monkeypatch):
        """The half of the fail-soft contract the tests above do not reach.

        ``_copy_one``'s docstring promises a failed identity is deliberately
        NOT recorded as seen, "so a transient failure gets retried on the next
        pass rather than being silently given up on forever". Every other test
        in this class calls ``poll_once`` exactly ONCE, so they prove the
        failure is TOLERATED and prove nothing about the retry - the promise
        was carried by prose alone until this test. Found by the cycle 47
        refutation, which caught `OPS-26` citing these tests as cover for a
        claim they do not support.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        target = src_dir / "StandaloneSlot_4.sav"
        _touch(target, b"R" * 777, mtime_ns=9_000_000_000)

        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        real_copy2 = savewatch.shutil.copy2
        attempts = []

        def _fails_once(src, dst, *a, **kw):
            attempts.append(Path(src).name)
            if len(attempts) == 1:
                raise PermissionError(f"simulated transient failure: {src}")
            return real_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(savewatch.shutil, "copy2", _fails_once)

        first = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert first == [], "the failing copy must produce no snapshot on the first pass"
        assert attempts == ["StandaloneSlot_4.sav"], "sanity check: the copy was attempted"

        # Nothing about the source changed, so identity is unchanged. A watcher
        # that had recorded the failed identity as seen would skip it forever.
        second = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 10))
        assert len(second) == 1, "the failed identity must be retried, not given up on"
        assert second[0].destination.read_bytes() == b"R" * 777


class TestAPersistentlyRefusedDestinationIsCounted:
    """`OPS-26`. Tolerating a failed copy is right; hiding it forever is not.

    PROVOKED 2026-09-05 before any of this was written. A watcher whose every
    copy was refused - once by a real filesystem ``PermissionError`` and once by
    ``OSError(28)``, the ``ENOSPC`` this machine actually hit - completed 12
    passes, advanced its heartbeat, kept all four surfaces inside their
    thresholds, archived ZERO files, and read ``ARMED`` / ``VERIFIED``.

    ``consecutive_failed_passes`` is what lets the layer above tell a REFUSED
    destination from an idle one. The distinction it has to preserve, and the
    reason this is a counter rather than a flag:

    * a save file vanishing mid-copy is NORMAL - it is the transience this
      module exists for - and produces exactly ONE failing pass, because once
      the file is gone ``_entry_identity`` returns ``None`` and no copy is
      attempted again;
    * a refused destination fails EVERY pass, forever.

    A pass that attempted nothing leaves the count alone rather than resetting
    it. Quiescent sources are the normal state - measured 2026-09-05, no watched
    file changed for five days - so resetting there would mean a destination
    that broke while nothing was changing could never accumulate evidence.
    """

    def _watcher(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        return src_dir, savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

    def test_a_fresh_watcher_has_not_failed(self, tmp_path):
        _src, watcher = self._watcher(tmp_path)
        assert watcher.consecutive_failed_passes == 0

    def test_every_refused_pass_increments_the_count(self, tmp_path, monkeypatch):
        src_dir, watcher = self._watcher(tmp_path)
        _touch(src_dir / "a.sav", b"A" * 64, mtime_ns=1_000_000_000)

        def _refuse(src, dst, *a, **kw):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(savewatch.shutil, "copy2", _refuse)

        for expected in (1, 2, 3):
            assert watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, expected)) == []
            assert watcher.consecutive_failed_passes == expected

    def test_an_idle_pass_CLEARS_the_count_so_the_freeze_is_not_sticky(
        self, tmp_path, monkeypatch
    ):
        """The first version of this test asserted the OPPOSITE, and was wrong.

        It required an idle pass to leave the count alone, reasoning that a
        destination breaking while nothing changed should still accumulate
        evidence. The cycle 47 refutation measured what that produces: three
        transient failures, then the source goes quiet - which is the transient
        save's actual life cycle - and the count stays pinned through recovery
        and 200 idle passes. On sources measured quiescent for five days
        straight, a recovered destination would never be forgiven.

        Resetting costs only a few passes of delay: while nothing is changing
        there is nothing to archive and so nothing is being lost, and the count
        climbs again as soon as content reappears.
        """
        src_dir, watcher = self._watcher(tmp_path)
        target = src_dir / "a.sav"
        _touch(target, b"A" * 64, mtime_ns=1_000_000_000)

        def _refuse(src, dst, *a, **kw):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(savewatch.shutil, "copy2", _refuse)
        watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert watcher.consecutive_failed_passes == 1

        target.unlink()  # nothing left to attempt at all
        watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 1))
        assert watcher.consecutive_failed_passes == 0, (
            "an idle pass must clear, or a surface frozen by a transient stays "
            "frozen forever once its source goes quiet"
        )

    def test_a_refused_RENAME_does_not_escape_poll_once_either(self, tmp_path):
        """The second raising call, found only because the first fix was checked.

        `_copy_one` moves its temporary into place with ``Path.replace``. That
        sat outside the ``try`` even after the mkdir was moved inside it, so an
        ordinary Windows read-only attribute on the target - no mocks, no
        exotic ACL - raised ``PermissionError [WinError 5]`` straight out
        through ``poll_once``, killed the polling thread, and leaked the
        ``.part`` behind it.
        """
        import stat as _stat

        src_dir, watcher = self._watcher(tmp_path)
        target = src_dir / "a.sav"
        _touch(target, b"A" * 64, mtime_ns=1_000_000_000)

        when = datetime(2026, 8, 9, 12, 0, 0)
        landed = watcher.poll_once(now=when)[0].destination
        landed.chmod(_stat.S_IREAD)
        try:
            # A second watcher with the same stamp and size aims at the very
            # same target path, which is now read-only.
            again = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
            assert again.poll_once(now=when) == [], "the refused rename yields no snapshot"
            assert again.consecutive_failed_passes == 1
            leftovers = [p.name for p in landed.parent.iterdir() if p.name.endswith(".part")]
            assert leftovers == [], "a refused rename must not leak its temporary"
        finally:
            landed.chmod(_stat.S_IWRITE)

    def test_one_success_clears_the_count(self, tmp_path, monkeypatch):
        src_dir, watcher = self._watcher(tmp_path)
        _touch(src_dir / "a.sav", b"A" * 64, mtime_ns=1_000_000_000)
        real_copy2 = savewatch.shutil.copy2
        refusing = {"on": True}

        def _sometimes(src, dst, *a, **kw):
            if refusing["on"]:
                raise OSError(28, "No space left on device")
            return real_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(savewatch.shutil, "copy2", _sometimes)
        watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 1))
        assert watcher.consecutive_failed_passes == 2

        refusing["on"] = False
        assert len(watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 2))) == 1
        assert watcher.consecutive_failed_passes == 0, (
            "a destination that started working again must clear, or the surface "
            "stays frozen after it recovers"
        )

    def test_a_refused_MKDIR_does_not_escape_poll_once(self, tmp_path):
        """The docstring promised "never raises" and it was false. `OPS-26` D.

        ``dest_dir.mkdir()`` sat outside ``_copy_one``'s ``try``, so a
        destination that refuses the mkdir raised ``FileExistsError`` straight
        out through ``poll_once`` and killed the polling thread. Provoked in the
        real threaded shape: the surface stopped advancing and was correctly
        named by ``SURFACE_STALE`` after its 69 s grace window - so the FACT was
        visible, but via a dead thread that can never recover, and the REASON
        went to the null device with the traceback.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        _touch(src_dir / "a.sav", b"A" * 64, mtime_ns=1_000_000_000)
        dest = _safe_dest(tmp_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"not a directory")

        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=dest)

        assert watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0)) == []
        assert watcher.consecutive_failed_passes == 1, (
            "a destination that refuses mkdir is a refused destination like any "
            "other, and must reach the same counter"
        )


class TestSnapshotFilenamesPreserveSizeAndTimestamp:
    def test_filename_contains_the_observed_size(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        _touch(src_dir / "StandaloneSlot_3.sav", b"Z" * 12345, mtime_ns=1_000_000_000)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 13, 45, 30))
        assert len(snaps) == 1
        assert "12345" in snaps[0].destination.name

    def test_filename_contains_a_local_timestamp_and_the_original_name(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        _touch(src_dir / "StandaloneSlot_3.sav", b"Z" * 10, mtime_ns=1_000_000_000)

        snaps = watcher.poll_once(now=datetime(2026, 8, 9, 13, 45, 30))
        name = snaps[0].destination.name
        assert "20260809" in name
        assert "134530" in name
        assert "StandaloneSlot_3.sav" in name

    def test_generations_sort_lexicographically_in_capture_order(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        target = src_dir / "StandaloneSlot_3.sav"

        stamps = [
            datetime(2026, 8, 9, 12, 0, 0),
            datetime(2026, 8, 9, 12, 0, 10),
            datetime(2026, 8, 9, 12, 0, 20),
        ]
        names = []
        for i, (when, size) in enumerate(zip(stamps, [100, 200, 300], strict=True)):
            _touch(target, b"Q" * size, mtime_ns=1_000_000_000 + i * 5_000_000_000)
            snaps = watcher.poll_once(now=when)
            names.append(snaps[0].destination.name)

        assert names == sorted(names), "lexicographic filename order must match capture order"

    def test_a_truncated_capture_is_identifiable_by_its_own_filename(self, tmp_path):
        # If the watcher is killed after capturing a partial generation, the
        # size in that snapshot's filename must show the partial number, not
        # the eventual final size - that is what "identifiable" means here.
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        target = src_dir / "StandaloneSlot_9.sav"

        _touch(target, b"P" * 2190, mtime_ns=1_000_000_000)
        partial = watcher.poll_once(now=datetime(2026, 8, 9, 12, 0, 0))
        assert "2190" in partial[0].destination.name
        assert "44517" not in partial[0].destination.name


class TestTheArchiveMomentIsNotTheMtime:
    """A snapshot's mtime is the SOURCE's mtime, NOT when it was archived.

    ``_copy_one`` copies with ``shutil.copy2``, which carries the source's
    mtime across, and then ``Path.replace`` - which preserves the temporary
    file's mtime rather than restamping it. So a snapshot lands in the
    capture tree wearing the modification time of the game file it copied,
    which can be days older than the copy.

    That makes ``mtime`` the WRONG instrument for asking when a file entered
    the capture tree. Measured on the real tree 2026-09-05: every one of the
    13 files archived at local 2026-09-03 18:53:54 carries an mtime of
    2026-08-30 or earlier, so a ``find -newermt 2026-08-31`` over the whole of
    C:/ll-captures returns three files and NONE of the thirteen. Tree-wide
    over all 431 watcher snapshots the worst single misdating is 25.44 days.
    A session dating capture growth by mtime therefore misdates the watcher's
    entire output by days, which is exactly the join ``OPS-14`` asks a future
    session to perform.

    **The stamp is not the ONLY right instrument, and an earlier draft of this
    docstring said it was.** The file's CREATION time also records the archive
    moment - ``copy2`` does not carry that across - and it agrees with the
    stamp on 431 of 431 snapshots within 5 seconds, sub-second on the 13 above.
    Prefer the stamp anyway, because creation time is not durable: copying the
    capture tree resets it while the stamp travels in the name. Measured the
    same day - a ``copy2`` of a snapshot kept the 2026-08-09 mtime and took a
    fresh 2026-09-05 creation time.

    **Why the trap is worse than a plain wrong answer: mtime is right MOST of
    the time.** 260 of the 431 snapshots, 60.3 percent, have an mtime within 2
    seconds of their stamp - the live log and the transient save are rewritten
    by the game moments before being archived, so for those the two clocks do
    coincide. The full error shows up only on quiescent sources, which are
    exactly the files a growth timeline is made of. Spot-checking a few
    snapshots is therefore likely to CONFIRM the wrong instrument.

    Nothing tested this. Every existing test here pins the SOURCE's stat (see
    TestSourceDirectoryIsNeverTouched) or the destination's NAME (see
    TestSnapshotFilenamesPreserveSizeAndTimestamp); none of them looks at the
    destination's mtime.

    Swapping ``copy2`` for ``copy`` was watched going red before this class
    was believed: 3 failed, 25 passed, and the destination's mtime became the
    archive moment. **One of those three was pre-existing, and it does not
    count as cover.** An earlier draft of this docstring claimed the swap left
    every other test green; it does not.
    ``TestFileVanishingBetweenListingAndCopying`` reddens because it
    monkeypatches ``shutil.copy2`` and the mutated code stops calling its spy -
    it fails on the spy going unused, not on the clock. Re-pointing that spy at
    ``copy``, which is what fixing it looks like, restores green with the
    property silently changed. So the swap is loud in a way that names the
    wrong cause, which is worse than silence.
    """

    def test_snapshot_mtime_is_the_sources_and_not_the_archive_moment(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        # An mtime five days before the archive moment, mirroring the real
        # tree: sources last written 2026-08-30, archived 2026-09-03.
        source_mtime_ns = 1_000_000_000_000_000_000
        target = src_dir / "StandaloneSlot_7.sav"
        _touch(target, b"D" * 4096, mtime_ns=source_mtime_ns)

        snaps = watcher.poll_once(now=datetime(2026, 9, 3, 18, 53, 54))
        assert len(snaps) == 1, "sanity check: the pass must actually have copied something"
        destination = snaps[0].destination

        assert destination.stat().st_mtime_ns == source_mtime_ns, (
            "the snapshot must carry the SOURCE's mtime - if this fails, mtime has "
            "become the archive time and every capture-tree dating method that reads "
            "the filename stamp needs revisiting"
        )

    def test_the_two_clocks_disagree_so_mtime_cannot_stand_in_for_the_stamp(self, tmp_path):
        """The negative half: the two instruments must be distinguishable.

        The test above would still pass if a source happened to be modified at
        the instant it was archived. This one pins that they are separate
        clocks by making them disagree on purpose, which is the property a
        dating method actually relies on.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        source_mtime = datetime(2026, 8, 30, 21, 11, 46)
        archived_at = datetime(2026, 9, 3, 18, 53, 54)
        _touch(
            src_dir / "StandaloneSlot_7.sav",
            b"D" * 4096,
            mtime_ns=int(source_mtime.timestamp() * 1_000_000_000),
        )

        destination = watcher.poll_once(now=archived_at)[0].destination

        assert "20260903-185354" in destination.name, "the stamp records the ARCHIVE moment"
        landed_mtime = datetime.fromtimestamp(destination.stat().st_mtime)
        assert landed_mtime.date() == source_mtime.date(), "the mtime records the SOURCE moment"
        assert (archived_at - landed_mtime).days == 3, (
            "the two clocks must be able to disagree by days - a dating method that "
            "reads mtime instead of the filename stamp is wrong by exactly this much"
        )


class TestOnePassIsSeparableFromLooping:
    """poll_once() is the deterministic unit; run() is a thin loop around it
    with an injectable sleep function, precisely so a test never has to sleep
    through a real poll interval to prove the loop calls poll_once correctly.
    """

    def test_run_calls_poll_once_max_passes_times_without_real_sleep(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))
        _touch(src_dir / "a.sav", b"A" * 10, mtime_ns=1_000_000_000)

        sleep_calls = []
        total = watcher.run(poll_seconds=3.0, max_passes=3, sleep_fn=sleep_calls.append)

        assert total == 1, "only the first of three passes should see anything new"
        assert sleep_calls == [3.0, 3.0], "must sleep between passes, not after the last one"

    def test_run_with_zero_max_passes_does_nothing_and_never_sleeps(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        watcher = savewatch.SaveWatcher(source_dir=src_dir, dest_dir=_safe_dest(tmp_path))

        def _must_not_sleep(seconds):
            pytest.fail(f"run() must not sleep when max_passes=0, tried to sleep {seconds}")

        total = watcher.run(max_passes=0, sleep_fn=_must_not_sleep)
        assert total == 0
