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
        target = REPO_ROOT / "_walker_probe_untracked.md"
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
        probe = runtime / "_walker_probe_ignored.json"
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
        target = REPO_ROOT / "_walker_probe_binary.zip"
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
        probe = runtime / "_walker_probe_ignored.bin"
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
