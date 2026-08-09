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
