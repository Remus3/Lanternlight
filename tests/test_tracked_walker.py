"""The hygiene walker must see files that are not committed yet.

Both repository guards - `tests/test_ascii_hygiene.py` and `tests/test_no_pii.py` -
delegate their file discovery to `tests/_tracked.py`. That walker asked git for
`ls-files`, which lists **tracked** paths only. So a brand-new file was invisible
to both guards until after it had been committed.

That is precisely backwards. A guard against leaking identifiers is needed most
at the moment a new file is written, and it went blind at exactly that moment.
Measured on 2026-08-09: two independent agents each produced a new file
containing 18-digit identifiers, ran the guards, saw green, and were green only
because the walker never looked. One of those files would have been committed.

The fix is to include untracked-but-not-ignored files as well. `.gitignore` is
still respected, so `ops/runtime/`, caches and scratch directories stay out.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "tests"))

import _tracked  # noqa: E402


def _walked() -> set[str]:
    return {p.resolve().as_posix() for p in _tracked.iter_authored_files(REPO_ROOT)}


class TestUntrackedFilesAreScanned:
    def test_a_new_untracked_file_is_visible_to_the_walker(self, tmp_path):
        target = _tracked.probe_path("walker_untracked.md")
        target.write_text("probe\n", encoding="utf-8")
        try:
            assert target.resolve().as_posix() in _walked(), (
                "a newly written, uncommitted file must be scanned - it is the "
                "one most likely to carry a pasted identifier"
            )
        finally:
            target.unlink(missing_ok=True)

    def test_this_very_test_file_is_scanned(self):
        assert Path(__file__).resolve().as_posix() in _walked()

    def test_every_currently_untracked_authored_file_is_scanned(self):
        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            import pytest

            pytest.skip("git unavailable")
        names = [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]
        walked = _walked()
        missed = []
        for name in names:
            path = REPO_ROOT / name
            if path.suffix.lower() in _tracked.BINARY_SUFFIXES or not path.is_file():
                continue
            if path.resolve().as_posix() not in walked:
                missed.append(name)
        assert not missed, "untracked authored files not scanned:\n" + "\n".join(missed)


class TestIgnoredFilesStayOut:
    def test_a_gitignored_file_is_not_scanned(self):
        # ops/runtime/ is gitignored live state. Widening the walker must not
        # drag it in, or every guard run starts tripping over runtime JSON.
        runtime = REPO_ROOT / "ops" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        probe = runtime / f"_walker_probe_ignored_{os.getpid()}.json"
        probe.write_text("{}\n", encoding="utf-8")
        try:
            assert probe.resolve().as_posix() not in _walked()
        finally:
            probe.unlink(missing_ok=True)

    def test_the_scratchpad_is_not_scanned(self):
        assert "scratchpad" in _tracked.SKIP_DIRS


class TestBinariesAreScannedForPii:
    """A binary is where an identifier hides best, so it must not be skipped.

    `iter_authored_files` filters on BINARY_SUFFIXES because the ASCII guard
    cannot do anything sensible with a PNG. The PII guard can: a SteamID64
    written into a save, a screenshot's EXIF, or a base64 blob inside a zip
    entry is an identifier like any other. `.gitignore` blocks `*.sav`, which
    is exactly the pressure that produces an encoded or renamed copy instead.

    So there are two views of the tree, and this pins the difference.
    """

    def test_a_binary_file_is_scannable_even_though_it_is_not_authored_text(self):
        target = _tracked.probe_path("walker_binary.zip")
        target.write_bytes(b"PK\x03\x04\x00\x01binary probe\x00\x02")
        try:
            scannable = {
                p.resolve().as_posix()
                for p in _tracked.iter_scannable_files(REPO_ROOT)
            }
            authored = {
                p.resolve().as_posix()
                for p in _tracked.iter_authored_files(REPO_ROOT)
            }
            key = target.resolve().as_posix()
            assert key in scannable, "a publishable binary must still be scanned for PII"
            assert key not in authored, "the ASCII guard must still skip binaries"
        finally:
            target.unlink(missing_ok=True)

    def test_a_save_file_would_be_scanned_if_it_ever_reached_the_tree(self, tmp_path):
        # `*.sav` is gitignored, so the repository walker never sees one unless
        # somebody force-adds it - and if they do, `git ls-files` lists it and
        # it is scanned. That path cannot be exercised against the real
        # repository without writing to its index, so it is exercised against
        # the filesystem fallback, which applies the same suffix policy.
        if _tracked._git_tracked(tmp_path) is not None:
            import pytest

            pytest.skip("tmp_path is inside a git work tree; fallback not exercised")
        (tmp_path / "role.sav").write_bytes(b"GVAS\x00\x02\x00\x00\x00")
        scannable = {p.name for p in _tracked.iter_scannable_files(tmp_path)}
        authored = {p.name for p in _tracked.iter_authored_files(tmp_path)}
        assert "role.sav" in scannable, (
            "a save that reaches the published tree must be scanned - it is the "
            "single file most likely to carry the operator's account id"
        )
        assert "role.sav" not in authored

    def test_the_scannable_view_is_a_superset_of_the_authored_view(self):
        scannable = {p.resolve().as_posix() for p in _tracked.iter_scannable_files(REPO_ROOT)}
        authored = {p.resolve().as_posix() for p in _tracked.iter_authored_files(REPO_ROOT)}
        assert authored <= scannable

    def test_ignored_files_stay_out_of_the_scannable_view_too(self):
        runtime = REPO_ROOT / "ops" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        probe = runtime / f"_walker_probe_ignored_{os.getpid()}.bin"
        probe.write_bytes(b"\x00\x01")
        try:
            scannable = {
                p.resolve().as_posix()
                for p in _tracked.iter_scannable_files(REPO_ROOT)
            }
            assert probe.resolve().as_posix() not in scannable
        finally:
            probe.unlink(missing_ok=True)


class TestWalkerStillSane:
    def test_tracked_files_are_still_scanned(self):
        walked = _walked()
        assert (REPO_ROOT / "CLAUDE.md").resolve().as_posix() in walked
        assert (REPO_ROOT / "README.md").resolve().as_posix() in walked

    def test_the_walk_is_still_above_the_floor(self):
        assert len(_walked()) >= _tracked.MIN_EXPECTED_FILES

    def test_no_duplicates_are_yielded(self):
        # Tracked and untracked sets must not overlap into double-scanning.
        paths = [p.resolve().as_posix() for p in _tracked.iter_authored_files(REPO_ROOT)]
        assert len(paths) == len(set(paths))


class TestTheProbeFilterCannotHideATrackedFile:
    """The isolation must never blind a guard to something git TRACKS.

    Found by an independent refutation pass on 2026-08-26b, against the first
    version of the OPS-8 fix. ``_is_foreign_probe`` filtered by NAME over the
    whole candidate list - tracked files included - so a file committed as
    ``docs/_guard_probe_notes.md`` became invisible to the PII guard.
    Demonstrated with a real-shaped SteamID64 in a force-added file: the
    repository-wide guard went GREEN, and ``.githooks/pre-commit`` does no
    content scan to catch it either.

    A tracked file that happens to carry a probe name is not a concurrent
    suite's scratch file. It is a PUBLISHED file, which is the entire category
    these guards exist to read. The filter therefore applies only on the
    non-git fallback walk, which is the only path that needs it - on the git
    path ``.gitignore`` has already removed every untracked probe, and
    anything still listed is tracked and must be scanned.
    """

    def test_a_tracked_file_with_a_probe_name_is_still_scanned(self, tmp_path):
        import pytest

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True, check=False
            )

        if git("init", "-q", ".").returncode != 0:
            pytest.skip("git unavailable")
        git("config", "user.email", "probe@example.invalid")
        git("config", "user.name", "probe")

        planted = repo / f"{_tracked.PROBE_PREFIX}notes.md"
        planted.write_text("a note somebody committed", encoding="ascii")
        assert git("add", "-f", planted.name).returncode == 0
        git("commit", "-q", "-m", "probe: track a probe-named file")

        # Prove the premise before believing the conclusion: git really is
        # tracking it. Otherwise this passes for the wrong reason.
        tracked = git("ls-files").stdout.split()
        assert planted.name in tracked, tracked

        names = {p.name for p in _tracked.iter_scannable_files(repo)}
        assert planted.name in names, (
            "a TRACKED file was hidden from the PII guard by the probe-name "
            "filter - the filter is for a concurrent suite's scratch files, "
            "never for anything that would be published"
        )


class TestConcurrentSuitesDoNotCollide:
    """Two pytest processes at once must not destroy each other's evidence.

    Measured 2026-08-26, and the mechanism is not subtle. Every guard probe
    used to be planted at a FIXED path at the repository root, so two suites
    running at once planted the SAME file and the first to reach its
    ``finally`` unlinked the other's evidence mid-scan. Five concurrent full
    suites went red in **9 of 10 runs**, across five different tests.

    A process that plants nothing was hit too: a foreign probe appearing
    between two consecutive walks of the same tree broke
    ``test_the_scannable_view_is_a_superset_of_the_authored_view``, whose two
    walks are supposed to differ only by the binary filter.

    This matters beyond flakiness. ``ops/merge_gate.py`` re-runs pytest and
    ``CLAUDE.md`` mandates a parallel multi-agent workflow, so the gate that
    exists to catch a dropped test could redden for a reason unrelated to the
    work being gated - and a gate that cries wolf is a gate people override.

    The rule these pin: a probe is named for the process that owns it, its
    owner always sees it, and nobody else ever does. **The probes stay at the
    repository root**, because scanning the real root is the point of the
    guards they exercise; only the NAME changed.
    """

    FOREIGN_STEM = "foreign_suite_probe.bin"

    def _foreign(self) -> Path:
        """A probe that is foreign to the WALKER but still unique on DISK.

        Both properties are required, and the first draft of this class only
        had one. It used a fixed ``<prefix>0_`` name - pid 0 is never a live
        process, so it reads as foreign - and six concurrent suites promptly
        fought over that single file: ``PermissionError: [WinError 32]`` on
        ``unlink`` while another suite was still writing it. 17 of 18 runs
        green, red for exactly the bug this class exists to prevent,
        reproduced inside the test for it.

        So the owner tag is this process's pid with a marker appended. It does
        not match ``<prefix><pid>_``, so every walker treats it as somebody
        else's, and no two processes ever name the same path. The marker
        cannot collide with a longer pid either: the character after the
        digits is never the ``_`` the owner check requires.
        """
        return REPO_ROOT / f"{_tracked.PROBE_PREFIX}{os.getpid()}other_{self.FOREIGN_STEM}"

    def test_a_probe_path_is_unique_to_this_process(self):
        path = _tracked.probe_path("binary.png")
        assert str(os.getpid()) in path.name, (
            "a probe named the same in every process is the collision itself"
        )
        assert path.parent == REPO_ROOT, (
            "probes must stay at the repository root - scanning the real root "
            "is what the guards they exercise are for"
        )

    def test_two_processes_would_not_pick_the_same_probe_path(self):
        # The pid is the whole isolation mechanism, so pin that it is what
        # varies. Same stem, different owner, different file.
        ours = _tracked.probe_path(self.FOREIGN_STEM)
        assert ours != self._foreign()

    def test_a_foreign_probe_is_invisible_to_the_authored_walk(self):
        foreign = self._foreign()
        foreign.write_text("another suite is mid-test\n", encoding="ascii")
        try:
            assert foreign.resolve().as_posix() not in _walked(), (
                "another process's probe must not enter this process's walk - "
                "it is about to be unlinked under us"
            )
        finally:
            foreign.unlink(missing_ok=True)

    def test_a_foreign_probe_is_invisible_to_the_scannable_walk(self):
        foreign = self._foreign()
        foreign.write_bytes(b"\x00another suite\x00")
        try:
            scannable = {
                p.resolve().as_posix() for p in _tracked.iter_scannable_files(REPO_ROOT)
            }
            assert foreign.resolve().as_posix() not in scannable
        finally:
            foreign.unlink(missing_ok=True)

    def test_our_own_probe_is_still_visible_to_both_walks(self):
        """The other half. Hiding foreign probes must not hide our own.

        A probe its owner cannot see proves nothing, and a guard proved by
        nothing is decoration - so this is the assertion that stops the
        isolation being implemented by simply blinding the walker.
        """
        own_text = _tracked.probe_path("own_visible.md")
        own_binary = _tracked.probe_path("own_visible.zip")
        own_text.write_text("mine\n", encoding="ascii")
        own_binary.write_bytes(b"PK\x03\x04mine")
        try:
            walked = _walked()
            scannable = {
                p.resolve().as_posix() for p in _tracked.iter_scannable_files(REPO_ROOT)
            }
            assert own_text.resolve().as_posix() in walked
            assert own_text.resolve().as_posix() in scannable
            assert own_binary.resolve().as_posix() in scannable
            assert own_binary.resolve().as_posix() not in walked, (
                "the binary suffix policy still applies to our own probes"
            )
        finally:
            own_text.unlink(missing_ok=True)
            own_binary.unlink(missing_ok=True)

    def test_a_foreign_probe_is_filtered_on_the_non_git_fallback_path(self, tmp_path):
        """The ignore rule cannot reach a tree git is not managing.

        ``_published`` falls back to a filesystem walk for a source tarball or
        a tree before ``git init``, and that walk never reads ``.gitignore``.
        So the explicit foreign-probe filter is the only thing standing between
        that path and the race the ignore rule closes everywhere else.

        This test exists because a mutation proved the filter was decoration:
        replacing its body with ``return False`` left the whole suite green,
        since every other test runs on the git path where the ignore rule has
        already removed the file.
        """
        import pytest

        if _tracked._git_tracked(tmp_path) is not None:
            pytest.skip("tmp_path is inside a git work tree; the fallback is not exercised")

        foreign = tmp_path / f"{_tracked.PROBE_PREFIX}{os.getpid()}other_fallback.bin"
        ours = _tracked.probe_path("fallback.bin", root=tmp_path)
        foreign.write_bytes(b"another suite")
        ours.write_bytes(b"mine")

        names = {p.name for p in _tracked.iter_scannable_files(tmp_path)}
        assert foreign.name not in names, (
            "the fallback walk let another process's probe through - "
            ".gitignore does not apply to a tree git is not managing"
        )
        assert ours.name in names, "our own probe must survive the filter"

    def test_the_two_walks_stay_consistent_while_a_foreign_probe_exists(self):
        """The failure a process that plants nothing still suffered.

        ``test_the_scannable_view_is_a_superset_of_the_authored_view`` walks
        the tree twice and subtracts. A foreign probe that appears between the
        two walks breaks it, so the invariant is pinned here with one present
        for the whole test rather than left to a race to expose.
        """
        foreign = self._foreign()
        foreign.write_text("still here for both walks\n", encoding="ascii")
        try:
            scannable = {
                p.resolve().as_posix() for p in _tracked.iter_scannable_files(REPO_ROOT)
            }
            authored = {
                p.resolve().as_posix() for p in _tracked.iter_authored_files(REPO_ROOT)
            }
            assert authored <= scannable
            assert foreign.resolve().as_posix() not in scannable
        finally:
            foreign.unlink(missing_ok=True)
