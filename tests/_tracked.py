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

#: Prefix for the throwaway files a guard plants at the repository ROOT to
#: prove it is not vacuous - see :func:`probe_path`.
PROBE_PREFIX = "_guard_probe_"


def probe_path(stem: str, root: Path = REPO_ROOT) -> Path:
    """Path for a guard probe owned by THIS process, at the repository root.

    Root placement is deliberate and must not be relaxed: scanning the real
    root is the whole point of the guards these probes exercise. What the pid
    changes is only the NAME.

    Measured 2026-08-26, and the mechanism was not subtle. Every probe used a
    FIXED name, so two suites running at once planted the same path and the
    first to reach its ``finally`` unlinked the other's evidence mid-scan.
    Five concurrent full suites went red in **9 of 10 runs** across five
    different tests, and a suite that planted nothing was hit too - a foreign
    probe appearing between two consecutive walks of one tree is enough.
    """
    return root / f"{PROBE_PREFIX}{os.getpid()}_{stem}"


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


def _own_probe_prefix() -> str:
    return f"{PROBE_PREFIX}{os.getpid()}_"


def _is_foreign_probe(path: Path) -> bool:
    """True for a guard probe belonging to some OTHER process.

    ``.gitignore`` already keeps every probe out of the git listing, so on the
    normal path this filter finds nothing. It is here for the FALLBACK walk,
    which does not consult ``.gitignore`` at all - a source tarball or a tree
    before ``git init`` would otherwise reintroduce the exact race the ignore
    rule closes.
    """
    name = path.name
    return name.startswith(PROBE_PREFIX) and not name.startswith(_own_probe_prefix())


def _own_probes(root: Path) -> list[Path]:
    """Guard probes THIS process planted, which git is ignoring on purpose.

    Ignoring the prefix is what makes a concurrent suite safe, but it also
    hides a probe from its own owner - and a probe its owner cannot see proves
    nothing, which would quietly turn every guard it backs into decoration.

    So the owner's probes, and only the owner's, are added back. The match is
    on the exact ``<prefix><pid>_`` string, so no widening of the ignore rule
    can drag a foreign probe in through here.
    """
    prefix = _own_probe_prefix()
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    return [p for p in entries if p.name.startswith(prefix) and p.is_file()]


def _published(root: Path) -> list[Path]:
    """Every path that would be published from ``root``, in sorted order.

    Plus this process's own guard probes, and minus anyone else's - see
    :func:`probe_path` for why, and ROADMAP ``OPS-8`` for what it cost.
    """
    candidates = _git_tracked(root)
    if candidates is None:
        candidates = _walked(root)
    kept = [path for path in candidates if not _is_foreign_probe(path)]
    return sorted(dict.fromkeys([*kept, *_own_probes(root)]))


def iter_authored_files(root: Path = REPO_ROOT) -> Iterator[Path]:
    """Yield every authored TEXT file that would be published from ``root``.

    Binaries are excluded because the guard this feeds - the 7-bit ASCII rule -
    has nothing to say about them: a PNG is high bytes by definition, and
    flagging that would be noise, not a finding.

    For the PII guard, use :func:`iter_scannable_files` instead.
    """
    for path in _published(root):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if not path.is_file():
            continue
        yield path


def iter_scannable_files(root: Path = REPO_ROOT) -> Iterator[Path]:
    """Yield every published file, binaries included.

    **Why binaries are scanned rather than skipped.** The suffix filter above
    is right for the ASCII rule and wrong for PII: an account id inside a
    ``.sav`` or a ``.png`` is an account id, and a file this walker refuses to
    open is a file the guard cannot testify about. "Nothing found" and "nothing
    looked" are different facts, and only one of them is safe to publish.

    Scanning also beats the two alternatives that were considered:

    - *Refusing* every committed binary needs an allowlist, and an allowlist is
      a list of files nobody scans. It would also block a legitimate diagram
      while doing nothing about a renamed save.
    - *Skipping* is what produced the hole this closes. ``.gitignore`` blocks
      ``*.sav``, so the standing pressure is to commit an encoded or renamed
      copy of exactly the file that carries the operator's identity.

    Refusal by PATH - the game's Saved tree, ``frames/``, ``*.log``, ``*.sav``
    - is a separate mechanism and still lives in ``.githooks/pre-commit``. This
    is the net under it, for the paths nobody anticipated.

    Ignored files stay out: ``.gitignore`` remains authoritative, so
    ``ops/runtime`` and the caches are no more scanned than before.
    """
    for path in _published(root):
        if not path.is_file():
            continue
        yield path
