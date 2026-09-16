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

import _toolguard  # noqa: E402

from ops import lane_launcher, lanes  # noqa: E402


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_toolguard.require("git"), *args], cwd=cwd, capture_output=True, text=True, check=True
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
            [_toolguard.require("git"), "rev-parse", "--abbrev-ref", "HEAD"],
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
            [_toolguard.require("git"), "status", "--short"],
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


def _names_force(argv: list[str]) -> bool:
    """True when ``argv`` carries git's force flag in any spelling.

    Written as a scan rather than a membership test because ``--force`` is not
    the only spelling: git also accepts ``-f``, ``--force=...``, and short
    option clusters such as ``-fv``. A guard that looked only for the long form
    would be defeated by the shortest edit that defeats the invariant.
    """
    for token in argv:
        if token.startswith("--"):
            if token == "--force" or token.startswith("--force="):
                return True
        elif token.startswith("-") and len(token) > 1 and "f" in token[1:]:
            return True
    return False


class TestTheWorktreeOrderingInvariant:
    """CONVERGENCE CHARTER v4, the worktree ordering invariant.

    Stated by the charter as: no worktree is removed until the work it holds
    exists somewhere durable that survives the removal. The test that decides
    it is "if this directory vanished right now, what would be lost?" - if the
    answer is anything, it is not removable yet.

    This project's implementation of that invariant is a single mechanism:
    :func:`ops.lane_launcher.remove_worktree_argv` plans an UNFORCED removal,
    and git itself then refuses to delete a worktree holding uncommitted or
    untracked work. Nothing else enforces it.

    That mechanism is switched off by four characters. An adversarial pass
    showed that ``['git', 'worktree', 'remove', '--force', path]`` satisfied
    every assertion the planning tests made, so the one guard the invariant
    leaned on could be disabled without a single test noticing. These tests
    close that: the first pins the flag's absence for every writable lane, and
    the rest pin the BEHAVIOUR the flag's absence buys, against a real git
    repository, so a future refactor that reaches the same outcome differently
    is not punished while one that loses the refusal is.
    """

    def test_no_writable_lane_plans_a_forced_removal(self):
        for lane in lanes.LANES:
            if lane.read_only:
                continue
            argv = lane_launcher.remove_worktree_argv(lane)
            assert not _names_force(argv), (
                f"lane {lane.lane_id!r} plans a FORCED worktree removal: {argv}. "
                "Forcing defeats git's refusal to delete a worktree holding "
                "uncommitted work, which is the only mechanism enforcing the "
                "CONVERGENCE CHARTER v4 worktree ordering invariant here."
            )

    def test_the_force_detector_itself_sees_every_spelling(self):
        # Guards the guard: a detector blind to -f would pass a forced argv.
        base = ["git", "worktree", "remove", "C:/somewhere"]
        assert not _names_force(base)
        for flag in ("--force", "--force=true", "-f", "-fv", "-vf"):
            assert _names_force([*base[:3], flag, base[3]]), flag

    def test_removal_is_refused_while_tracked_work_is_uncommitted(
        self, scratch_repo, monkeypatch
    ):
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        wt = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        (wt / "seed.txt").write_text("in-flight lane work\n", encoding="utf-8")

        proc = subprocess.run(
            [_toolguard.require("git"), *lane_launcher.remove_worktree_argv(lane)[1:]],
            cwd=scratch_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, (
            "git removed a worktree holding uncommitted changes - the planned "
            f"command must not be forced. stdout={proc.stdout!r}"
        )
        assert wt.is_dir()
        assert (wt / "seed.txt").read_text(encoding="utf-8") == "in-flight lane work\n"

    def test_removal_is_refused_while_untracked_work_is_present(
        self, scratch_repo, monkeypatch
    ):
        # Untracked is the likelier shape here: a lane's new module exists on
        # disk and in no commit, so the directory vanishing loses all of it.
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        wt = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        (wt / "brand_new_module.py").write_text("# not in any commit\n", encoding="utf-8")

        proc = subprocess.run(
            [_toolguard.require("git"), *lane_launcher.remove_worktree_argv(lane)[1:]],
            cwd=scratch_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, (
            "git removed a worktree holding untracked work - the planned "
            f"command must not be forced. stdout={proc.stdout!r}"
        )
        assert wt.is_dir()
        assert (wt / "brand_new_module.py").exists()

    def test_removal_succeeds_once_the_work_is_durable(
        self, scratch_repo, monkeypatch
    ):
        # The other half of the pair. Without this, the two refusal tests above
        # would also pass against a command that could never remove anything,
        # and a removal step that never works is not the invariant either.
        monkeypatch.setattr(lanes, "WORKTREE_ROOT", scratch_repo.parent / "wt")
        lane = lanes.by_id("ingest")
        wt = lane_launcher.ensure_worktree(lane, repo_root=scratch_repo)
        (wt / "brand_new_module.py").write_text("# soon durable\n", encoding="utf-8")
        _git("add", "-A", cwd=wt)
        _git("-c", "user.email=t@e.invalid", "-c", "user.name=T",
             "commit", "-m", "lane work", cwd=wt)

        proc = subprocess.run(
            [_toolguard.require("git"), *lane_launcher.remove_worktree_argv(lane)[1:]],
            cwd=scratch_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, (
            "committed lane work is durable and the worktree must then be "
            f"removable. stderr={proc.stderr!r}"
        )
        assert not wt.exists()
        # The work survived the removal, which is what "durable" means here.
        show = subprocess.run(
            [_toolguard.require("git"), "show", f"{lane.branch_name()}:brand_new_module.py"],
            cwd=scratch_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert show.stdout.strip() == "# soon durable"

    def test_the_docstring_still_states_why_it_is_unforced(self):
        # The reason is the thing that decays. A future editor who adds --force
        # to silence a cleanup failure should have to delete this sentence.
        doc = lane_launcher.remove_worktree_argv.__doc__ or ""
        assert "not forced" in doc.lower()
