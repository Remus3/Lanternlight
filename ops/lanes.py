"""The specialist lane roster - who owns what, and who may never touch what.

A lane is a persistent specialist. It owns a fixed set of files, runs its own
orchestrated sub-agents inside its own git worktree, verifies their claims with
:mod:`ops.merge_gate`, and commits to its own branch. It never merges to
``main``; a human does that after an out-of-domain check.

**Ownership is by file path, never by topic.** Topic ownership reads well in a
design document and collides the first time two lanes both consider a file
"theirs". Every lane therefore declares explicit path patterns, and the
disjointness of that map is enforced by ``tests/test_lanes.py`` rather than by
review - widen a glob carelessly and the build goes red.

Three properties are load-bearing, and each one exists because violating it
removes a safety guarantee silently rather than breaking anything visible:

**Worktree isolation.** Every lane works in its own directory on its own branch
and may never write into the primary checkout. Two writers in one working
directory corrupt the git index, and that is not recoverable by retrying. The
lane's own worktree is the only place it is allowed to touch.

**Cross-cutting files have no owner.** ``CLAUDE.md``, ``pytest.ini``, the
licence files and the project README are edited by the operator or by a merger
holding the whole picture - never by one of eight concurrent specialists. The
file that records the rules cannot itself be subject to a merge race.

**Some lanes hold a veto.** ``safety`` owns redaction and repository hygiene,
and ``verify`` is read-only. Neither is a peer slice: if either says no, nothing
log-derived gets committed. That is a different thing from a lane that merely
has an opinion, so it is a field on the lane rather than a convention.

The roster deliberately includes lanes with almost nothing to do yet
(``emberforge`` computes nothing; ``surface`` is one small package). A lane that
exists and is idle is honest about a domain that has an owner. A domain with no
owner is the one that silently accumulates orphaned work.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

__all__ = [
    "CROSS_CUTTING",
    "LANES",
    "Lane",
    "MAY_BE_EMPTY",
    "WORKTREE_ROOT",
    "by_id",
    "is_cross_cutting",
    "owner_of",
    "tracked_files",
]

#: Repository root, resolved from this file's location: ops/lanes.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where lane worktrees live. Deliberately a SIBLING of the checkout, never a
#: subdirectory of it - a worktree nested inside the main tree would be walked
#: by the hygiene guards and staged by a careless ``git add`` in either place.
WORKTREE_ROOT = Path(os.environ.get("LL_WORKTREE_ROOT", r"C:\ll-worktrees"))

#: Files no lane may own. Edited by the operator or by a merger holding the
#: whole picture. Everything here either states the rules, configures the
#: tooling, or makes a public legal claim.
CROSS_CUTTING: frozenset[str] = frozenset(
    {
        "CLAUDE.md",
        "README.md",
        "BACKLOG.md",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "pytest.ini",
        "ruff.toml",
        ".gitignore",
        ".gitattributes",
    }
)

#: Lanes permitted to own patterns that currently match no file. These are real
#: domains whose code has not been written yet, not mistakes.
MAY_BE_EMPTY: frozenset[str] = frozenset({"emberforge", "surface"})


@dataclass(frozen=True)
class Lane:
    """One persistent specialist.

    Attributes:
        lane_id: Stable slug. Appears in the branch name, the worktree path and
            every ledger entry the lane writes.
        title: Human-readable name.
        mandate: What this lane is for, in one sentence. This is the text that
            goes into the lane's dispatch prompt, so it has to be specific
            enough to exclude work that belongs to a sibling.
        owns: Path patterns, matched with ``PurePath.full_match`` so ``*`` does
            not cross a directory separator and ``**`` does.
        veto: True when a red result from this lane blocks every other lane.
        read_only: True when the lane may not write at all. A read-only lane
            must own nothing - otherwise it could be asked to grade its own
            work, which this project forbids.
    """

    lane_id: str
    title: str
    mandate: str
    owns: tuple[str, ...] = ()
    veto: bool = False
    read_only: bool = False
    forbidden_note: str = field(default="")

    def branch_name(self) -> str:
        """Return the lane's branch, namespaced so it can never be ``main``."""
        return f"lane/{self.lane_id}"

    def worktree_path(self) -> Path:
        """Return the lane's own working directory, outside the main checkout."""
        return WORKTREE_ROOT / f"ll-lane-{self.lane_id}"

    def owns_path(self, path: str | Path) -> bool:
        """True when ``path`` falls inside this lane's declared ownership.

        Accepts Windows or POSIX separators, absolute or repo-relative, because
        callers will pass all of those and a separator bug here would silently
        hand a file to nobody.
        """
        rel = _normalise(path)
        if rel is None:
            return False
        if is_cross_cutting(rel):
            return False
        return any(rel.full_match(pattern) for pattern in self.owns)


def _normalise(path: str | Path) -> PurePosixPath | None:
    """Return ``path`` as a repo-relative POSIX path, or None if outside."""
    text = str(path).replace("\\", "/")
    candidate = Path(text)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(REPO_ROOT)
        except ValueError:
            return None
        text = candidate.as_posix()
    return PurePosixPath(text.lstrip("./"))


def is_cross_cutting(path: str | Path) -> bool:
    """True when ``path`` is a governing file that no lane may own."""
    rel = _normalise(path)
    return rel is not None and rel.as_posix() in CROSS_CUTTING


#: The roster. Ordered by how load-bearing the lane is, not alphabetically.
LANES: tuple[Lane, ...] = (
    Lane(
        lane_id="safety",
        title="Safety and hygiene",
        mandate=(
            "Own redaction and every repository hygiene guard. Nothing derived "
            "from a game log reaches a commit without this lane's approval. "
            "Treat third-party player names as in scope, not only the "
            "operator's, and never weaken a guard to make a build pass."
        ),
        owns=(
            "lanternlight/redact.py",
            "tests/test_redact.py",
            "tests/test_no_pii.py",
            "tests/test_ascii_hygiene.py",
            "tests/test_tracked_walker.py",
            "tests/_tracked.py",
            "tools/ascii_check.py",
            "tools/precommit_gate.py",
            ".githooks/**",
            "scripts/install_hooks.py",
        ),
        veto=True,
        forbidden_note="May not edit application logic to make a guard pass.",
    ),
    Lane(
        lane_id="verify",
        title="Out-of-domain verification",
        mandate=(
            "Independently REFUTE other lanes' done-claims, defaulting to "
            "refuted when uncertain. Re-derive every number from ground truth "
            "rather than accepting a reported one. Owns no files on purpose."
        ),
        owns=(),
        veto=True,
        read_only=True,
        forbidden_note="Writes nothing, ever. It reports a verdict.",
    ),
    Lane(
        lane_id="ingest",
        title="Data ingest",
        mandate=(
            "Own every reader of a surface the game writes - the log parser and "
            "tail, the GVAS save reader, the market cache, and path resolution. "
            "Never emits a value it did not measure."
        ),
        owns=(
            "lanternlight/logparse.py",
            "lanternlight/avgprice.py",
            "lanternlight/paths.py",
            "lanternlight/gvas.py",
            "lanternlight/tail.py",
            "tests/test_logparse.py",
            "tests/test_avgprice.py",
            "tests/test_paths*.py",
            "tests/test_gvas*.py",
            "tests/test_tail*.py",
            "tests/fixtures/**",
        ),
    ),
    Lane(
        lane_id="ops",
        title="Continuity and orchestration",
        mandate=(
            "Own the loop, the lane machinery, the merge gate, and the durable "
            "record that lets a cold session resume - roadmap, ledger, wakeup "
            "notes and the headless contract."
        ),
        owns=(
            "ops/**",
            "tests/test_loop_*.py",
            "tests/test_merge_gate.py",
            "tests/test_lanes.py",
            "ROADMAP.md",
            "docs/LEDGER.md",
            "docs/HEADLESS.md",
            "docs/OPERATIONS.md",
            "WAKEUP_NOTES.md",
            "NEXT_SESSION_PROMPT.md",
            ".claude/commands/lane-*.md",
            "scripts/write_lane_contracts.py",
        ),
    ),
    Lane(
        lane_id="research",
        title="Research and provenance",
        mandate=(
            "Own the measured record and the class reference. Writes no code. "
            "Every claim carries its source and its trust tier, and a measured "
            "null is a result worth writing down."
        ),
        owns=(
            "docs/FINDINGS.md",
            "docs/OBSERVED_IDS.md",
            "docs/CLASSES.md",
            "docs/CLASS_RESEARCH.md",
            "docs/ECOSYSTEM.md",
            "docs/adr/**",
        ),
        forbidden_note="Writes no code. Findings only.",
    ),
    Lane(
        lane_id="emberforge",
        title="Emberforge math engine",
        mandate=(
            "Own the build and combat math. May not encode a number that has no "
            "measured source - omit the field instead, and keep unmeasured "
            "distinguishable from measured zero."
        ),
        owns=("emberforge/**", "tests/test_emberforge*.py"),
    ),
    Lane(
        lane_id="surface",
        title="Operator-facing surface",
        mandate=(
            "Own the always-on-top window, any dashboard, and every rendered "
            "surface. An ordinary window of our own - never an overlay hooked "
            "into the game."
        ),
        owns=("overlay/**", "tests/test_overlay_*.py", "dashboard/**"),
    ),
    Lane(
        lane_id="capture",
        title="Capture and vision",
        mandate=(
            "Own passive screen capture and the frame-to-log wall-clock join "
            "that binds rendered text to numeric ids. Passive reading only - "
            "never synthesises input."
        ),
        owns=(
            "tools/frame_poller.py",
            "tools/probe_paks.py",
            "lanternlight/vision*.py",
            "tests/test_vision*.py",
            "tests/test_capture*.py",
        ),
    ),
)


def by_id(lane_id: str) -> Lane:
    """Return the lane with ``lane_id``. Raises ``KeyError`` when unknown."""
    for lane in LANES:
        if lane.lane_id == lane_id:
            return lane
    raise KeyError(f"unknown lane id: {lane_id!r}")


def owner_of(path: str | Path) -> str | None:
    """Return the id of the lane owning ``path``, or None when unowned.

    Unowned is a legitimate answer: cross-cutting files have no owner by
    design, and a genuinely new area may not have one yet. It is never an
    invitation to guess.
    """
    for lane in LANES:
        if lane.owns_path(path):
            return lane.lane_id
    return None


def tracked_files(root: Path = REPO_ROOT) -> Iterator[Path]:
    """Yield repo-relative POSIX paths of tracked and new files, for auditing.

    Used by the ownership tests to walk the real tree, because two patterns can
    differ textually and still both match the same file - a check that compares
    only pattern strings would never see that.
    """
    args = [["git", "ls-files", "-z"], ["git", "ls-files", "-z", "--others", "--exclude-standard"]]
    seen: set[str] = set()
    for argv in args:
        try:
            proc = subprocess.run(
                argv, cwd=root, capture_output=True, timeout=30, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        for name in proc.stdout.decode("utf-8", "replace").split("\0"):
            if name and name not in seen:
                seen.add(name)
                yield Path(name)
