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
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

__all__ = [
    "CROSS_CUTTING",
    "LANES",
    "Lane",
    "MAY_BE_EMPTY",
    "WORKTREE_ROOT",
    "by_id",
    "git_would_take",
    "is_cross_cutting",
    "owner_of",
    "path_matches",
    "primary_checkout",
    "tracked_files",
]

#: The checkout this code is running FROM. Inside a lane worktree this is that
#: worktree, which is usually what a local operation wants - reading the local
#: contract files, walking the local tree. It is emphatically NOT "the main
#: checkout"; for that, use :func:`primary_checkout`.
REPO_ROOT = Path(__file__).resolve().parents[1]


def primary_checkout(start: Path | None = None) -> Path:
    """Return the MAIN checkout, identically from every worktree.

    ``REPO_ROOT`` is derived from ``__file__``, so a lane running in its own
    worktree sees ``REPO_ROOT`` as that worktree - and every check of the form
    "a lane worktree is not the primary checkout" silently inverts, because for
    the lane you are inside, the two are the same directory. That bug was found
    by actually running a lane end to end, not by reading the code.

    ``git rev-parse --git-common-dir`` answers with the same absolute path from
    the main checkout and from every linked worktree, so it is a fact about the
    repository rather than about where this process happens to be.

    Falls back to ``REPO_ROOT`` when git cannot answer - a source tarball has no
    ``.git``, and returning something usable beats raising.
    """
    root = REPO_ROOT if start is None else Path(start)
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return root
    if proc.returncode != 0 or not proc.stdout.strip():
        return root
    return Path(proc.stdout.strip()).parent

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
        # Governs the harness for every session - which hooks fire, on which
        # tool, with which permissions. It was unowned by OMISSION rather than
        # by design, which is how its PreToolUse matcher sat at "Bash" alone on
        # a PowerShell-primary machine without anyone owning the question.
        ".claude/settings.json",
        # The package marker is re-exported from by several lanes' modules and
        # belongs to none of them.
        "lanternlight/__init__.py",
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
    # removeprefix, NOT lstrip. `str.lstrip("./")` strips CHARACTERS, so it
    # ate the leading dot of every dotted path - `.gitignore` became
    # `gitignore`, `.githooks/pre-commit` became `githooks/pre-commit` - and the
    # ownership map then silently matched nothing for any dotfile. Measured
    # 2026-08-09; the safety lane did not own the git hooks, and every existing
    # test passed because zero owners satisfies "not more than one owner".
    return PurePosixPath(text.removeprefix("./"))


def path_matches(path: str | Path, patterns: Iterable[str]) -> bool:
    """True when ``path`` matches any of ``patterns``, by the roster's rules.

    Exposed so a pending claim (`OPS-2`) is matched by exactly the same
    normalisation the roster uses. Re-implementing it beside the roster is how
    the two would drift, and this repository has already paid once for a
    separator bug here - ``lstrip("./")`` strips CHARACTERS, so it ate the
    leading dot of every dotfile and the ownership map silently matched nothing
    for them.
    """
    rel = _normalise(path)
    if rel is None or is_cross_cutting(rel):
        return False
    return any(rel.full_match(pattern) for pattern in patterns)


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
            "lanes/safety.*",
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
            "lanternlight/savewatch.py",
            "lanternlight/armwatch.py",
            "lanternlight/damage.py",
            "tests/test_logparse.py",
            "tests/test_damage*.py",
            "tests/test_avgprice.py",
            "tests/test_paths*.py",
            "tests/test_gvas*.py",
            "tests/test_tail*.py",
            "tests/test_savewatch*.py",
            "tests/test_armwatch*.py",
            "tests/fixtures/**",
            "lanes/ingest.*",
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
            ".claude/commands/*.md",
            ".claude/agents/*.md",
            "docs/ARCHITECTURE.md",
            "tests/test_lane_*.py",
            "scripts/write_lane_contracts.py",
            "lanes/ops.*",
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
            "lanes/research.*",
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
        owns=("emberforge/**", "tests/test_emberforge*.py", "lanes/emberforge.*"),
    ),
    Lane(
        lane_id="surface",
        title="Operator-facing surface",
        mandate=(
            "Own the always-on-top window, any dashboard, and every rendered "
            "surface. An ordinary window of our own - never an overlay hooked "
            "into the game."
        ),
        owns=(
            "overlay/**",
            "tests/test_overlay_*.py",
            "dashboard/**",
            "docs/OVERLAY.md",
            "lanes/surface.*",
        ),
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
            "lanes/capture.*",
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


def git_would_take(path: str | Path, root: Path = REPO_ROOT) -> bool | None:
    """True when git would accept ``path``, EVEN IF IT DOES NOT EXIST YET.

    `OPS-3` and `OPS-5`. The visibility guard used to answer this by listing
    what git already sees, which silently skipped every path not yet on disk -
    lane fragments are created lazily, so it was checking four of seven and
    reporting green. It also could not notice an ignore rule added AFTER a file
    was tracked, because a tracked file keeps being listed.

    Asking about the RULE rather than the listing fixes both, but the obvious
    probe is a trap this repository has already documented and which was
    re-measured before writing this: ``git check-ignore`` exits **0** when any
    pattern matches **including a negation**, so a correctly re-included file
    reports exactly like an excluded one. Measured here:
    ``tests/fixtures/gvas/standalone_slot.gvas.b64`` is re-included by
    ``!tests/fixtures/**/*.gvas.b64`` and still exits 0.

    So the exit code is not the answer - the matched PATTERN is. With ``-v``
    git prints ``<file>:<line>:<pattern>\\t<path>``, and a pattern starting with
    ``!`` is a carve-out, meaning git would take the file after all.

    Returns None when git cannot answer, so a caller can skip rather than
    passing vacuously.
    """
    rel = _normalise(path)
    if rel is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-v", "--no-index", "--", rel.as_posix()],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode == 1:
        return True  # nothing matched, so nothing excludes it
    if proc.returncode != 0:
        return None  # git declined to answer at all
    first = proc.stdout.splitlines()[0] if proc.stdout.splitlines() else ""
    source = first.split("\t")[0]
    parts = source.split(":", 2)
    if len(parts) != 3:
        return None
    return parts[2].startswith("!")


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
