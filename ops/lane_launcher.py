"""Put a lane in its own worktree, and refuse to let it run anywhere else.

Two writers in one working directory corrupt the git index, and that is not a
transient failure you retry past - it is the class of accident that ends with
somebody reconstructing work by hand. Eight persistent lanes make it a
certainty rather than a risk, so every lane gets its own worktree on its own
branch, created here.

**The refusal is the half that matters.** Creating a worktree is ordinary
plumbing that git already does well. The guarantee this module adds is
:func:`assert_in_lane_worktree`, which a lane calls before it writes anything:
if it somehow finds itself in the primary checkout, it stops. Cheap, blunt, and
the last line of defence when a launcher script is edited or a lane is started
by hand.

Command construction is deliberately separated from command execution. The
argv builders are pure functions, so the shape of every command can be asserted
in a test without git being involved - including the property that no planned
command ever names the primary checkout. Only :func:`ensure_worktree` actually
shells out.

Read-only lanes are refused a worktree outright rather than given one they must
remember not to use. A lane that cannot write is better served by having
nowhere to write.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ops import lanes

__all__ = [
    "LaneLaunchError",
    "ReadOnlyLane",
    "WorktreeError",
    "WrongWorkingDirectory",
    "add_worktree_argv",
    "assert_in_lane_worktree",
    "branch_exists",
    "ensure_worktree",
    "remove_worktree_argv",
]

REPO_ROOT = lanes.REPO_ROOT


class LaneLaunchError(RuntimeError):
    """Base class for every refusal this module raises."""


class WrongWorkingDirectory(LaneLaunchError):
    """The lane is not in its own worktree, so it must not write."""


class ReadOnlyLane(LaneLaunchError):
    """A read-only lane asked for somewhere to write."""


class WorktreeError(LaneLaunchError):
    """git declined to create or remove the worktree."""


def _resolved(path: Path | str) -> Path:
    """Resolve without requiring the path to exist."""
    return Path(path).expanduser().resolve()


def _repo_root(repo_root: Path | str | None) -> Path:
    """Resolve the repository to operate on, defaulting to the MAIN checkout.

    Defaulting to :data:`ops.lanes.REPO_ROOT` was a measured accident: that
    value comes from ``__file__``, so creating one lane's worktree from inside
    another lane's worktree ran ``git worktree add`` there, and the new branch
    silently forked from that lane's HEAD instead of the branch the operator
    was on. The new lane then started life carrying another lane's work.

    Resolved at call time rather than bound as a default argument, because a
    default is evaluated once at import and would freeze whichever checkout
    happened to import the module first.
    """
    if repo_root is not None:
        return Path(repo_root)
    return lanes.primary_checkout()


def assert_in_lane_worktree(lane: lanes.Lane, cwd: Path | str | None = None) -> None:
    """Raise unless ``cwd`` is inside ``lane``'s own worktree.

    Call this before a lane writes anything. The failure it prevents - a lane
    editing the primary checkout while another writer is in it - produces a
    corrupt index rather than a clean error, so the check has to happen before
    the first write and not after the first conflict.
    """
    here = _resolved(Path.cwd() if cwd is None else cwd)
    want = _resolved(lane.worktree_path())
    if here == want or want in here.parents:
        return
    raise WrongWorkingDirectory(
        f"lane {lane.lane_id!r} may only write inside its own worktree.\n"
        f"  expected: {want}\n"
        f"  actually: {here}\n"
        "Two writers in one working directory corrupt the git index. Start the "
        "lane with ops.lane_launcher.ensure_worktree() and run it from there."
    )


def add_worktree_argv(lane: lanes.Lane, branch_exists: bool = False) -> list[str]:
    """Build the ``git worktree add`` command for ``lane``.

    Creates the branch with ``-b`` the first time and merely checks it out on
    later runs, so the launcher is idempotent across sessions rather than
    failing the second time a lane starts.
    """
    if lane.read_only:
        raise ReadOnlyLane(
            f"lane {lane.lane_id!r} is read-only and is given no worktree - it "
            "reports a verdict and writes nothing"
        )
    target = str(lane.worktree_path())
    if branch_exists:
        return ["git", "worktree", "add", target, lane.branch_name()]
    return ["git", "worktree", "add", "-b", lane.branch_name(), target]


def remove_worktree_argv(lane: lanes.Lane) -> list[str]:
    """Build the ``git worktree remove`` command for ``lane``.

    Deliberately not forced. A worktree with uncommitted changes should refuse
    to disappear - losing a lane's in-flight work to a cleanup step is exactly
    the outcome the branch-per-lane design exists to avoid.
    """
    return ["git", "worktree", "remove", str(lane.worktree_path())]


def branch_exists(name: str, repo_root: Path | None = None) -> bool:
    """True when ``name`` already resolves to a ref in ``repo_root``."""
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", name],
        cwd=_repo_root(repo_root),
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def ensure_worktree(lane: lanes.Lane, repo_root: Path | None = None) -> Path:
    """Create ``lane``'s worktree if it is missing, and return its path.

    Idempotent: an existing worktree is returned untouched, so a lane can call
    this at the top of every run without special-casing the first one.
    """
    if lane.read_only:
        raise ReadOnlyLane(
            f"lane {lane.lane_id!r} is read-only and is given no worktree"
        )

    target = lane.worktree_path()
    if (target / ".git").exists():
        return target

    root = _repo_root(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    argv = add_worktree_argv(lane, branch_exists=branch_exists(lane.branch_name(), root))
    proc = subprocess.run(
        argv, cwd=root, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise WorktreeError(
            f"could not create the worktree for lane {lane.lane_id!r}\n"
            f"  command: {' '.join(argv)}\n"
            f"  stderr : {proc.stderr.strip()}"
        )
    return target
