"""The lane launcher, and the one guarantee it exists to provide.

Eight persistent lanes sharing one working directory is the unrecoverable
failure: concurrent writers corrupt the git index, and no amount of retrying
fixes it afterwards. So every lane runs in its own worktree on its own branch,
and this module is what puts it there and what refuses to let it run anywhere
else.

The refusal is the important half. Creating a worktree is ordinary plumbing;
the safety property is that a lane which somehow starts in the primary checkout
**stops** rather than writing. That check is cheap, it is the last line of
defence, and it is tested here against the real repository root rather than a
mock, because a path-comparison bug is exactly the kind of thing a mock hides.

Planning is separated from execution on purpose: the argv builders are pure
functions, so the command shape can be asserted without shelling out, and the
integration tests that do shell out build a throwaway git repo in ``tmp_path``
rather than touching this one.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lane_launcher, lanes  # noqa: E402


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with one commit, so worktrees can be added to it."""
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-b", "main", cwd=root)
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "seed", cwd=root)
    return root


class TestRefusalToRunInThePrimaryCheckout:
    """The guarantee. Everything else in this module is plumbing."""

    def test_running_from_the_primary_checkout_raises(self):
        lane = lanes.by_id("ingest")
        with pytest.raises(lane_launcher.WrongWorkingDirectory):
            lane_launcher.assert_in_lane_worktree(lane, cwd=lanes.primary_checkout())

    def test_the_error_names_the_lane_and_both_paths(self):
        lane = lanes.by_id("ingest")
        try:
            lane_launcher.assert_in_lane_worktree(lane, cwd=lanes.primary_checkout())
        except lane_launcher.WrongWorkingDirectory as exc:
            message = str(exc)
        else:
            raise AssertionError("expected a refusal")
        assert "ingest" in message
        assert str(lanes.primary_checkout()) in message

    def test_a_subdirectory_of_the_primary_checkout_also_raises(self):
        lane = lanes.by_id("ingest")
        with pytest.raises(lane_launcher.WrongWorkingDirectory):
            lane_launcher.assert_in_lane_worktree(
                lane, cwd=lanes.primary_checkout() / "lanternlight"
            )

    def test_the_correct_worktree_is_accepted(self):
        lane = lanes.by_id("ingest")
        lane_launcher.assert_in_lane_worktree(lane, cwd=lane.worktree_path())

    def test_a_subdirectory_of_the_lane_worktree_is_accepted(self):
        lane = lanes.by_id("ingest")
        lane_launcher.assert_in_lane_worktree(
            lane, cwd=lane.worktree_path() / "lanternlight"
        )

    def test_another_lanes_worktree_is_refused(self):
        ingest = lanes.by_id("ingest")
        with pytest.raises(lane_launcher.WrongWorkingDirectory):
            lane_launcher.assert_in_lane_worktree(
                ingest, cwd=lanes.by_id("safety").worktree_path()
            )

    def test_a_read_only_lane_is_refused_a_worktree_entirely(self):
        verify = lanes.by_id("verify")
        assert verify.read_only
        with pytest.raises(lane_launcher.ReadOnlyLane):
            lane_launcher.add_worktree_argv(verify)


class TestDefaultRepoRootIsThePrimaryCheckout:
    """Measured accident, 2026-08-09: a lane worktree branched off the wrong thing.

    ``ensure_worktree`` defaulted its ``repo_root`` to ``lanes.REPO_ROOT``,
    which is derived from ``__file__``. Creating a second lane's worktree from
    inside the first lane's worktree therefore ran ``git worktree add`` there,
    and the new branch forked from **that lane's** HEAD rather than from the
    branch the operator was on - silently importing one lane's work into
    another's.

    The default has to be a fact about the repository, not about which
    directory the process happens to have imported from.
    """

    def test_ensure_worktree_defaults_to_the_primary_checkout(self):
        import inspect

        sig = inspect.signature(lane_launcher.ensure_worktree)
        assert sig.parameters["repo_root"].default is None, (
            "the default must be resolved at call time via primary_checkout(), "
            "not bound to REPO_ROOT at import time"
        )

    def test_branch_exists_defaults_to_the_primary_checkout(self):
        import inspect

        sig = inspect.signature(lane_launcher.branch_exists)
        assert sig.parameters["repo_root"].default is None

    def test_resolver_returns_the_primary_checkout_when_given_none(self):
        assert lane_launcher._repo_root(None) == lanes.primary_checkout()

    def test_resolver_honours_an_explicit_root(self, tmp_path):
        assert lane_launcher._repo_root(tmp_path) == tmp_path


class TestCommandPlanning:
    """Pure argv construction - assertable without touching git."""

    def test_add_argv_names_the_branch_and_the_path(self):
        lane = lanes.by_id("ingest")
        argv = lane_launcher.add_worktree_argv(lane)
        assert argv[:3] == ["git", "worktree", "add"]
        assert lane.branch_name() in argv
        assert str(lane.worktree_path()) in argv

    def test_add_argv_creates_the_branch_with_dash_b(self):
        argv = lane_launcher.add_worktree_argv(lanes.by_id("ingest"))
        assert "-b" in argv

    def test_existing_branch_is_checked_out_rather_than_recreated(self):
        argv = lane_launcher.add_worktree_argv(
            lanes.by_id("ingest"), branch_exists=True
        )
        assert "-b" not in argv

    def test_remove_argv_is_scoped_to_the_lane_path(self):
        lane = lanes.by_id("ingest")
        argv = lane_launcher.remove_worktree_argv(lane)
        assert argv[:3] == ["git", "worktree", "remove"]
        assert str(lane.worktree_path()) in argv

    def test_no_planned_command_ever_targets_the_primary_checkout(self):
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            for argv in (
                lane_launcher.add_worktree_argv(lane),
                lane_launcher.remove_worktree_argv(lane),
            ):
                assert str(lanes.primary_checkout()) not in argv


class TestAgainstARealRepo:
    def test_a_worktree_is_created_on_its_own_branch(self, scratch_repo, monkeypatch):
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        created = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        assert created.is_dir()
        assert (created / ".git").exists()
        head = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=created,
            capture_output=True,
            text=True,
            check=True,
        )
        assert head.stdout.strip() == lane.branch_name()

    def test_ensure_is_idempotent(self, scratch_repo, monkeypatch):
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        first = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        second = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        assert first == second
        assert second.is_dir()

    def test_the_primary_checkout_is_untouched_by_a_lane_commit(
        self, scratch_repo, monkeypatch
    ):
        # The whole point: work in the lane must not appear in the main tree.
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        wt = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        (wt / "lane_only.txt").write_text("from the lane\n", encoding="utf-8")
        _git("add", "-A", cwd=wt)
        _git("-c", "user.email=t@e.invalid", "-c", "user.name=T",
             "commit", "-m", "lane work", cwd=wt)
        assert not (scratch_repo / "lane_only.txt").exists()
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=scratch_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert status.stdout.strip() == ""

    def test_two_lanes_get_separate_directories(self, scratch_repo, monkeypatch):
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        a = lane_launcher.ensure_worktree(lanes.by_id("ingest"), repo_root=scratch_repo)
        b = lane_launcher.ensure_worktree(lanes.by_id("safety"), repo_root=scratch_repo)
        assert a != b
        assert a.is_dir() and b.is_dir()
