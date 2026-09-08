"""Tests for the shared-worktree object-store drift detector - ``OPS-54``.

The item this covers was found by an object-count DISAGREEMENT: an audit
reported one histogram and an independent re-derivation minutes later reported
another, because a concurrently running slice was writing objects into the
shared repository between the two readings. Neither number was wrong. The
movement was the finding.

Two properties are load-bearing here and each has its own tests.

**The check names the commit, it does not merely count.** A count that rose is
exactly what the original audit saw, and it told nobody anything: the whole
failure mode is a number moving for an unexplained reason. So the report has to
carry the sha and the subject of any stash-shaped commit that appeared.

**The check never raises.** It runs at merge time in a repository that other
agents are writing to, on a machine where ``git`` may be absent, the directory
may not be a repository at all, and a command may time out. A guard that
explodes at merge time is a guard somebody deletes.

The end-to-end test in :class:`TestARealStashInAThrowawayRepository` is the one
that makes this real - criterion 3. It creates an actual stash with an actual
``git stash``, watches the detector name the pair of commits git writes, drops
the stash, and watches the detector go quiet once the objects are pruned. A
detector that has only ever been shown hand-built snapshots has not been tested.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import store_drift  # noqa: E402

#: A synthetic identity for every throwaway repository built here. Never the
#: operator's - a test repository that inherits the machine's git identity
#: writes an operator identifier into commit objects that this module then
#: reads back, which is the exposure ``ADR-004`` exists to prevent.
TEST_IDENTITY = ("Drift Fixture", "drift@example.invalid")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run one git command in ``repo``, raising if it fails.

    Raising is correct HERE and wrong in the module under test: a broken
    fixture must fail loudly, while a broken probe at merge time must report.
    """
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )


def _new_repo(root: Path) -> Path:
    """Create a throwaway repository with one commit and a synthetic identity."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.name", TEST_IDENTITY[0])
    _git(root, "config", "user.email", TEST_IDENTITY[1])
    _git(root, "config", "commit.gpgsign", "false")
    (root / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "first subject")
    return root


def _snap(sha_to_type: dict[str, str], subjects: dict[str, str] | None = None,
          unreachable: tuple[str, ...] = ()) -> store_drift.StoreSnapshot:
    """Build a snapshot by hand, for the pure tests of :func:`compare`."""
    return store_drift.StoreSnapshot(
        root="fixture",
        at="2026-09-08T00:00:00+00:00",
        objects=dict(sha_to_type),
        subjects=dict(subjects or {}),
        unreachable=frozenset(unreachable),
        errors=(),
    )


class TestTheStashSubjectPredicate:
    """``WIP on `` and ``index on `` are the pair ``git stash`` writes."""

    def test_a_wip_subject_is_stash_shaped(self) -> None:
        assert store_drift.is_stash_subject("WIP on main: 6acc6b7 Wrap the session")

    def test_an_index_subject_is_stash_shaped(self) -> None:
        assert store_drift.is_stash_subject("index on main: 6acc6b7 Wrap the session")

    def test_an_ordinary_commit_subject_is_not(self) -> None:
        assert not store_drift.is_stash_subject("Close OPS-27: write the interlock at DISPATCH")

    def test_the_prefix_keeps_its_trailing_space(self) -> None:
        """``WIP onboarding`` is not a stash, and it is the only test that says so.

        The first version of this test used ``WIPocalypse`` and ``reindex on``,
        which FEEL like the counterexamples and are not: neither starts with
        ``WIP on`` or ``index on`` even once the trailing space is deleted, so
        the mutation that deletes it survived them both. A counterexample has
        to differ from the real thing in exactly the way the code does.
        """
        assert not store_drift.is_stash_subject("WIP onboarding notes for the new lane")
        assert not store_drift.is_stash_subject("index onboarding docs rebuilt")

    def test_a_word_that_merely_starts_the_same_is_not_a_stash(self) -> None:
        assert not store_drift.is_stash_subject("WIPocalypse now")
        assert not store_drift.is_stash_subject("reindex on main: rebuild the cache")

    def test_the_match_is_anchored_at_the_start(self) -> None:
        assert not store_drift.is_stash_subject("Document what WIP on main: means")

    def test_a_non_string_subject_is_not_stash_shaped_and_does_not_raise(self) -> None:
        assert not store_drift.is_stash_subject(None)


class TestParsingGitsOwnOutput:
    """Pure parsers, so the shapes can be pinned without spawning git."""

    def test_batch_check_lines_become_a_sha_to_type_map(self) -> None:
        text = (
            "20e50a07feffafe7699bf38ff4027a606f406eaa tree 33\n"
            "5626abf0f72e58d7a153368ba57db4c673c0e171 blob 4\n"
            "6946058cfa780c74de968c1679a3cbc182f2eae0 commit 124\n"
        )
        assert store_drift.parse_batch_check(text) == {
            "20e50a07feffafe7699bf38ff4027a606f406eaa": "tree",
            "5626abf0f72e58d7a153368ba57db4c673c0e171": "blob",
            "6946058cfa780c74de968c1679a3cbc182f2eae0": "commit",
        }

    def test_blank_and_malformed_batch_check_lines_are_skipped_not_fatal(self) -> None:
        text = (
            "\n"
            "not a record\n"
            "warning: three words\n"
            "gggggggggggggggggggggggggggggggggggggggg commit 12\n"
            "6946058cfa780c74de968c1679a3cbc182f2eae0 commit 124\n"
            "  \n"
        )
        assert store_drift.parse_batch_check(text) == {
            "6946058cfa780c74de968c1679a3cbc182f2eae0": "commit"
        }

    def test_unreachable_lines_become_a_set_of_shas(self) -> None:
        text = (
            "unreachable blob 814f4a422927b82f5f8a43f8fab6d3839e3983f2\n"
            "unreachable tree 6218aaa5fc1a58f5b32cbee55bc0cb0954022787\n"
            "unreachable commit 92bbb41d7f96f98be38c8a8c59d0957233a7cf02\n"
        )
        assert store_drift.parse_unreachable(text) == frozenset(
            {
                "814f4a422927b82f5f8a43f8fab6d3839e3983f2",
                "6218aaa5fc1a58f5b32cbee55bc0cb0954022787",
                "92bbb41d7f96f98be38c8a8c59d0957233a7cf02",
            }
        )

    def test_dangling_and_progress_lines_are_not_unreachable(self) -> None:
        """``git fsck`` also prints ``dangling`` and progress chatter.

        Counting a dangling object as unreachable would report drift on a
        repository nobody touched, and a check that cries wolf is a check that
        gets removed.
        """
        text = (
            "Checking object directories: 100% (256/256), done.\n"
            "dangling commit 92bbb41d7f96f98be38c8a8c59d0957233a7cf02\n"
            "unreachable commit 6f9d703c245d60d2472d7e5f872eeae499109778\n"
        )
        assert store_drift.parse_unreachable(text) == frozenset(
            {"6f9d703c245d60d2472d7e5f872eeae499109778"}
        )

    def test_a_commit_subject_is_the_first_line_after_the_header_block(self) -> None:
        body = (
            "tree 20e50a07feffafe7699bf38ff4027a606f406eaa\n"
            "parent 5b1cb54106316ff64b1f29218fe3eabdd5b286b4\n"
            "author A <a@example.invalid> 1788897562 -0500\n"
            "committer A <a@example.invalid> 1788897562 -0500\n"
            "\n"
            "WIP on master: 5b1cb54 first subject\n"
        )
        assert store_drift.parse_commit_subject(body) == "WIP on master: 5b1cb54 first subject"

    def test_a_commit_with_no_message_yields_an_empty_subject(self) -> None:
        assert store_drift.parse_commit_subject("tree abc\nauthor A\n") == ""


class TestComparingTwoSnapshots:
    """What ``compare`` says, on snapshots built by hand."""

    def test_an_unmoved_store_reports_no_drift(self) -> None:
        snap = _snap({"aa": "commit", "bb": "tree"}, {"aa": "Close OPS-1"})
        report = store_drift.compare(snap, snap)
        assert report.moved is False
        assert report.stash_commits == ()
        assert "did not move" in report.format()

    def test_an_ordinary_new_commit_is_drift_but_is_not_named_as_a_stash(self) -> None:
        """The distinction the original audit could not make.

        A sibling slice committing legitimately also moves the store. That is
        still drift worth reporting - the audit's numbers were still taken
        against a moving target - but it is not the stash hazard, and reporting
        it as one would be a false alarm.
        """
        before = _snap({"aa": "commit"}, {"aa": "Close OPS-1"})
        after = _snap({"aa": "commit", "cc": "commit"}, {"aa": "Close OPS-1", "cc": "Close OPS-2"})
        report = store_drift.compare(before, after)
        assert report.moved is True
        assert report.appeared == {"commit": 1}
        assert report.stash_commits == ()

    def test_a_stash_shaped_commit_is_named_with_its_sha_and_subject(self) -> None:
        before = _snap({"aa": "commit"}, {"aa": "Close OPS-1"})
        after = _snap(
            {"aa": "commit", "dd": "commit"},
            {"aa": "Close OPS-1", "dd": "WIP on main: aa Close OPS-1"},
        )
        report = store_drift.compare(before, after)
        named = [fact.sha for fact in report.stash_commits]
        assert named == ["dd"]
        rendered = report.format()
        assert "dd" in rendered
        assert "WIP on main: aa Close OPS-1" in rendered

    def test_a_dropped_stash_is_named_and_flagged_unreachable(self) -> None:
        """The real-world signature: present in the store, reachable from nothing."""
        before = _snap({"aa": "commit"}, {"aa": "Close OPS-1"})
        after = _snap(
            {"aa": "commit", "dd": "commit"},
            {"aa": "Close OPS-1", "dd": "index on main: aa Close OPS-1"},
            unreachable=("dd",),
        )
        report = store_drift.compare(before, after)
        assert [fact.unreachable for fact in report.stash_commits] == [True]
        assert "unreachable" in report.format()

    def test_objects_that_vanished_are_reported_too(self) -> None:
        """A ``gc`` under a slice is drift in the other direction.

        It also destroys the evidence this detector reads, so it is the one
        movement worth reporting even though nothing appeared.
        """
        before = _snap({"aa": "commit", "dd": "commit"}, {"aa": "x", "dd": "WIP on main: aa x"})
        after = _snap({"aa": "commit"}, {"aa": "x"})
        report = store_drift.compare(before, after)
        assert report.moved is True
        assert report.vanished == {"commit": 1}
        assert "vanished" in report.format()

    def test_a_snapshot_that_failed_produces_a_report_that_says_so(self) -> None:
        broken = store_drift.StoreSnapshot(
            root="fixture",
            at="2026-09-08T00:00:00+00:00",
            objects={},
            subjects={},
            unreachable=frozenset(),
            errors=("git cat-file failed (rc=128): not a git repository",),
        )
        report = store_drift.compare(broken, _snap({"aa": "commit"}))
        assert report.answered is False
        assert report.errors
        assert "COULD NOT ANSWER" in report.format()

    def test_comparing_a_failed_snapshot_never_raises(self) -> None:
        broken = store_drift.StoreSnapshot(
            root="fixture",
            at="",
            objects={},
            subjects={},
            unreachable=frozenset(),
            errors=("boom",),
        )
        store_drift.compare(broken, broken).format()


class TestTheProbeNeverRaises:
    """A guard that explodes at merge time is a guard that gets removed."""

    def test_a_directory_that_is_not_a_repository_reports_rather_than_raises(
        self, tmp_path: Path
    ) -> None:
        report = store_drift.snapshot(tmp_path)
        assert report.errors
        assert report.usable is False
        assert report.objects == {}

    def test_a_missing_git_binary_reports_rather_than_raises(self, tmp_path: Path) -> None:
        """And it says WHY in words, not as an errno.

        Asserting only that ``errors`` is non-empty left the ``FileNotFoundError``
        clause untested: that exception is an ``OSError``, so deleting the clause
        entirely still produced an error string and the mutation survived. The
        message is the only thing the clause actually decides, so the message is
        what has to be asserted.
        """
        report = store_drift.snapshot(tmp_path, git="git-that-is-not-installed-anywhere")
        assert report.errors
        assert report.usable is False
        assert any("git program was not found" in one for one in report.errors), report.errors

    def test_a_timeout_reports_rather_than_raises(self, tmp_path: Path) -> None:
        """Zero timeout, so the real subprocess call really does time out."""
        report = store_drift.snapshot(tmp_path, timeout=0)
        assert report.errors
        assert report.usable is False

    def test_this_repository_snapshots_cleanly(self) -> None:
        snap = store_drift.snapshot(REPO_ROOT)
        assert snap.usable, snap.errors
        histogram = snap.histogram()
        assert histogram.get("commit", 0) > 0
        assert histogram.get("tree", 0) > 0
        assert histogram.get("blob", 0) > 0


class TestARealStashInAThrowawayRepository:
    """Criterion 3. An actual ``git stash``, watched from both sides.

    Everything above builds its snapshots by hand, which proves the arithmetic
    and proves nothing about whether the shapes match what git emits. This
    class runs the real commands in a repository under ``tmp_path`` - never in
    the shared worktree, which is the very hazard being detected.
    """

    def test_a_real_stash_is_named_and_a_pruned_one_goes_quiet(self, tmp_path: Path) -> None:
        repo = _new_repo(tmp_path / "throwaway")
        before = store_drift.snapshot(repo)
        assert before.usable, before.errors
        assert store_drift.compare(before, before).stash_commits == ()

        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "-q")

        during = store_drift.snapshot(repo)
        loud = store_drift.compare(before, during)
        subjects = sorted(fact.subject.split(":")[0] for fact in loud.stash_commits)
        assert subjects == ["WIP on master", "index on master"], loud.format()
        assert loud.moved is True

        _git(repo, "stash", "drop", "-q")
        after_drop = store_drift.compare(before, store_drift.snapshot(repo))
        assert [fact.unreachable for fact in after_drop.stash_commits] == [True, True], (
            "dropping a stash unlinks the ref but leaves the commits in the store - "
            "that is exactly the signature this detector was built to read"
        )

        _git(repo, "reflog", "expire", "--expire-unreachable=now", "--all")
        _git(repo, "gc", "--prune=now", "-q")
        quiet = store_drift.compare(before, store_drift.snapshot(repo))
        assert quiet.stash_commits == (), quiet.format()
        assert "did not move" in quiet.format()

    def test_a_repository_nobody_touched_stays_quiet(self, tmp_path: Path) -> None:
        """The negative control. Without it, a detector that always fires passes."""
        repo = _new_repo(tmp_path / "untouched")
        before = store_drift.snapshot(repo)
        after = store_drift.snapshot(repo)
        report = store_drift.compare(before, after)
        assert report.moved is False
        assert report.stash_commits == ()


def _stash_subjects(report: store_drift.DriftReport) -> list[str]:
    """The prefix-and-branch half of every named stash subject, sorted.

    The tail of a stash subject carries a commit sha that changes every run, so
    the assertions below pin the half git's own format decides.
    """
    return sorted(fact.subject.split(":")[0] for fact in report.stash_commits)


class TestEveryFormOfStashGitCanWrite:
    """``OPS-60`` criterion 2. Every subject form, measured rather than assumed.

    ``OPS-54`` shipped a prefix set holding ``WIP on `` and ``index on `` and
    called them "the two subjects git stash writes". They are two of five, and
    the missing ones are not exotic: a MESSAGED stash - the form a careful agent
    is most likely to use, because it labels its own work - writes neither of
    them for its first commit.

    Enumerated by running each form in a throwaway repository, git
    2.53.0.windows.3, 2026-09-08, and reading back the subject git wrote:

    ===================================  =====================================
    command                              subjects, in git's parent order
    ===================================  =====================================
    ``git stash``                        ``WIP on <branch>: <sha> <subject>``
                                         ``index on <branch>: <sha> <subject>``
    ``git stash push -m "msg"``          ``On <branch>: msg``
                                         ``index on <branch>: <sha> <subject>``
    ``git stash push --keep-index``      the unmessaged pair, unchanged
    ``git stash push --staged``          the unmessaged pair, unchanged
    ``git stash push -u``                the unmessaged pair, plus a THIRD
                                         ``untracked files on <branch>: ...``
    ``git stash push -u -m "msg"``       the messaged pair, plus that third
    on a detached HEAD                   every form above with the branch field
                                         the literal ``(no branch)``
    ``git stash create "msg"``           the messaged pair, on no ref at all
    ===================================  =====================================

    Each test below builds the stash with a real ``git stash`` in a repository
    under ``tmp_path`` and reads the subject back. A test that types the subject
    string by hand and asserts the prefix matches asserts on a coincidence
    between two literals in the same repository, which is a defect this project
    has already shipped once.
    """

    def test_a_messaged_stash_names_BOTH_of_its_commits(self, tmp_path: Path) -> None:
        """Criterion 1. The defect: only the ``index on `` half used to match."""
        repo = _new_repo(tmp_path / "messaged")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "-m", "my message")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == ["On master", "index on master"], report.format()

    def test_an_include_untracked_stash_names_all_THREE_of_its_commits(
        self, tmp_path: Path
    ) -> None:
        repo = _new_repo(tmp_path / "untracked")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        (repo / "b.txt").write_text("new\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "--include-untracked")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == [
            "WIP on master",
            "index on master",
            "untracked files on master",
        ], report.format()

    def test_a_messaged_include_untracked_stash_names_all_three(self, tmp_path: Path) -> None:
        """The two defective forms at once - the messaged head and the third commit."""
        repo = _new_repo(tmp_path / "untracked-messaged")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        (repo / "b.txt").write_text("new\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "-u", "-m", "with untracked")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == [
            "On master",
            "index on master",
            "untracked files on master",
        ], report.format()

    def test_keep_index_writes_the_ordinary_unmessaged_pair(self, tmp_path: Path) -> None:
        """Measured, not assumed: ``--keep-index`` changes the tree, not the subject."""
        repo = _new_repo(tmp_path / "keep-index")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "add", "a.txt")
        (repo / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "--keep-index")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == ["WIP on master", "index on master"], report.format()

    def test_a_stash_on_a_detached_head_is_named_with_no_branch(self, tmp_path: Path) -> None:
        """There is no branch name, so git writes the literal ``(no branch)``."""
        repo = _new_repo(tmp_path / "detached")
        _git(repo, "checkout", "-q", "--detach", "HEAD")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "-q")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == [
            "WIP on (no branch)",
            "index on (no branch)",
        ], report.format()

    def test_a_messaged_stash_on_a_detached_head_is_named_too(self, tmp_path: Path) -> None:
        repo = _new_repo(tmp_path / "detached-messaged")
        _git(repo, "checkout", "-q", "--detach", "HEAD")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "-m", "on a detached head")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert _stash_subjects(report) == [
            "On (no branch)",
            "index on (no branch)",
        ], report.format()

    def test_a_branch_name_cannot_contain_a_space(self, tmp_path: Path) -> None:
        """The assumption the messaged form's shape check rests on, measured.

        ``On <branch>: <message>`` is only distinguishable from an ordinary
        English subject beginning "On " because the field before the colon is a
        branch name and git refuses a branch name with a space in it. If that
        were not true the check would have to be a bare ``On `` prefix, which
        would name every commit subject starting with that word.
        """
        repo = _new_repo(tmp_path / "branch-names")
        refused = subprocess.run(
            ["git", "branch", "a name with spaces"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert refused.returncode != 0, refused.stdout + refused.stderr

    def test_an_ordinary_commit_that_starts_with_On_is_not_named_as_a_stash(
        self, tmp_path: Path
    ) -> None:
        """The false-positive control for the widened match.

        A real commit, written by a real ``git commit``, whose subject opens
        with the same word a messaged stash does. Widening the match to a bare
        ``On `` prefix names this one, and a report full of false alarms is a
        report the reader learns to skip.
        """
        repo = _new_repo(tmp_path / "prose")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-q", "-m", "On the third pass: rewrite the parser")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert report.moved is True, report.format()
        assert report.stash_commits == (), report.format()


class TestTheArithmeticThatWasWrong:
    """``OPS-60`` criteria 3 and 4. A commit count is not a stash count.

    ``OPS-54``'s closure and ``LL-0188`` both stated that one stash writes two
    commits, and inferred that six unreachable commits were three stashes. The
    first half is right about one stash in isolation and the inference is wrong
    in both directions - the counterexample is below, so the next person to
    reason about it meets it rather than the intuition.
    """

    def test_two_stashes_from_an_unchanged_index_leave_THREE_commits_not_four(
        self, tmp_path: Path
    ) -> None:
        """The deduplication counterexample, built by running the real commands.

        The second stash's ``index on `` commit has the same tree, the same
        parent and the same subject as the first one, so it hashes to the same
        object and git stores one commit rather than two. N stashes taken from
        an unchanged index leave N+1 commits, not 2N.
        """
        repo = _new_repo(tmp_path / "dedup")
        before = store_drift.snapshot(repo)

        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "-m", "first stash")
        _git(repo, "stash", "drop", "-q")

        (repo / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "-q")
        _git(repo, "stash", "drop", "-q")

        report = store_drift.compare(before, store_drift.snapshot(repo))
        assert len(report.stash_commits) == 3, report.format()
        assert _stash_subjects(report) == [
            "On master",
            "WIP on master",
            "index on master",
        ], report.format()
        assert all(fact.unreachable for fact in report.stash_commits), report.format()

    def test_the_report_refuses_to_convert_its_commit_count_into_a_stash_count(
        self, tmp_path: Path
    ) -> None:
        """The rendered report has to carry the caveat, not just this test.

        A caveat stated in a test and dropped from the artifact is a lie in the
        artifact: the merger reads ``format()``, not this file.
        """
        repo = _new_repo(tmp_path / "caveat")
        before = store_drift.snapshot(repo)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8", newline="\n")
        _git(repo, "stash", "push", "-q", "-m", "my message")

        rendered = store_drift.compare(before, store_drift.snapshot(repo)).format()
        assert "STASH-SHAPED COMMITS: 2" in rendered
        assert "not a count of stashes" in rendered
        assert "git stash list" in rendered


class TestTheWrittenBan:
    """Criterion 1. The list is prose, so the test pins that it stays complete."""

    @pytest.mark.parametrize(
        "command",
        [
            "git stash",
            "git stash pop",
            "git reset",
            "git reset --hard",
            "git checkout -- .",
            "git clean",
            "git add -A",
            "git rebase",
            "git gc --prune=now",
        ],
    )
    def test_every_banned_command_is_named(self, command: str) -> None:
        assert command in store_drift.SHARED_WORKTREE_BAN

    def test_each_entry_says_how_it_destroys_a_siblings_work(self) -> None:
        """A bare list of forbidden commands is a rule nobody believes.

        The reason is the part that makes a dispatching session stop, so the
        prose has to carry one per entry rather than a single blanket warning.
        """
        body = store_drift.SHARED_WORKTREE_BAN
        for phrase in ("working tree", "index", "untracked", "unrecoverable"):
            assert phrase in body, phrase
        assert body.count("\n") > 20, "the ban collapsed to a one-liner"
