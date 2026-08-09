"""One shared file walker for the repo-wide hygiene guards.

Why this module exists. The ASCII guard and the PII guard each used to carry
their own copy of an extension allowlist, and both copies had the same hole:
`LICENSE`, `NOTICE`, `.gitignore`, `.gitattributes`, `.claude/settings.json` and
the `.githooks` scripts have no recognised suffix, so neither guard ever looked
at them. They were clean at the time, which is exactly why nobody noticed - a
coverage hole in a green guard is invisible until the day it matters.

Two copies of a rule is also two chances to drift, so the rule now lives here
once and both guards import it.

The walker asks **git** what is tracked rather than guessing from extensions.
Git already knows the answer, and "what will be published" is precisely the set
these guards care about. When git is unavailable - a source tarball, a fresh
copy before `git init` - it falls back to a filesystem walk so the suite still
runs, and the fallback is deliberately wider than the old allowlist.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Suffixes that are not authored text. Everything else tracked is in scope.
BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".bmp",
        ".mp4",
        ".zip",
        ".gz",
        ".pyc",
        ".pyd",
        ".so",
        ".dll",
        ".exe",
        ".pak",
        ".sav",
        ".ucas",
        ".utoc",
    }
)

#: Directories never walked, in the non-git fallback path.
SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "scratchpad",
        "_scratch",
        "frames",
        "logs",
        "runtime",
    }
)

#: A walk that silently finds almost nothing passes forever. This floor is set
#: near the real tracked count on purpose - the old value of 5 would have been
#: satisfied by a walker that had collapsed to a single directory.
MIN_EXPECTED_FILES = 40


def _git_listing(root: Path, extra_args: list[str]) -> list[str] | None:
    """Run one ``git ls-files`` variant, returning names or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", *extra_args],
            cwd=root,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]


def _git_tracked(root: Path) -> list[Path] | None:
    """Return tracked AND untracked-but-not-ignored paths, or None.

    **Untracked files are included deliberately, and it is the whole point.**
    A plain ``git ls-files`` lists only what is already committed, so a
    brand-new file was invisible to both hygiene guards until after it had
    landed in history - which is the exact moment they stop being able to help.
    Measured on 2026-08-09: two separate agents wrote new files containing
    18-digit identifiers, ran the guards, and got green solely because nothing
    looked at those files.

    ``--exclude-standard`` keeps ``.gitignore`` authoritative, so ``ops/runtime``
    and the caches stay out. The guards therefore scan what is about to be
    published, not merely what already was.
    """
    tracked = _git_listing(root, [])
    if tracked is None:
        return None
    untracked = _git_listing(root, ["--others", "--exclude-standard"]) or []
    names = list(dict.fromkeys([*tracked, *untracked]))
    if not names:
        return None
    return [root / n for n in names]


def _walked(root: Path) -> list[Path]:
    """Filesystem fallback for a tree that is not a git checkout."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        found.extend(Path(dirpath) / name for name in sorted(filenames))
    return found


def iter_authored_files(root: Path = REPO_ROOT) -> Iterator[Path]:
    """Yield every authored text file that would be published from ``root``."""
    candidates = _git_tracked(root)
    if candidates is None:
        candidates = _walked(root)
    for path in sorted(candidates):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if not path.is_file():
            continue
        yield path
