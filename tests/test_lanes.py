"""The lane roster's invariants, enforced mechanically rather than by review.

A lane architecture fails in exactly one way: two lanes believe they own the
same file. Everything after that - the merge conflict, the lost edit, the
corrupted index - is downstream of that single mistake. So the disjointness of
the ownership map is not a convention here, it is a test, and it fails the
build the moment someone widens a glob carelessly.

The other invariants tested here exist because each one, if violated, silently
removes a safety property rather than breaking anything visibly:

- cross-cutting files (``CLAUDE.md``, ``pytest.ini``, the license files) must be
  owned by NO lane, because the file that records the rules cannot be edited by
  eight concurrent writers
- every lane needs a unique worktree path and branch, or two lanes share a
  working directory and the corruption class returns
- the verification lane must own nothing, because a verifier that owns files is
  a verifier that can be asked to grade its own work
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import lanes  # noqa: E402


class TestRosterShape:
    def test_the_roster_is_not_empty(self):
        assert lanes.LANES

    def test_every_lane_id_is_unique(self):
        ids = [lane.lane_id for lane in lanes.LANES]
        assert len(ids) == len(set(ids))

    def test_lane_ids_are_safe_for_a_branch_and_a_path(self):
        for lane in lanes.LANES:
            assert re.fullmatch(r"[a-z][a-z0-9_-]*", lane.lane_id), lane.lane_id

    def test_every_lane_has_a_title_and_a_mandate(self):
        for lane in lanes.LANES:
            assert lane.title.strip()
            assert lane.mandate.strip()

    def test_lookup_by_id_works_and_unknown_raises(self):
        first = lanes.LANES[0]
        assert lanes.by_id(first.lane_id) is first
        try:
            lanes.by_id("no-such-lane")
        except KeyError:
            pass
        else:
            raise AssertionError("unknown lane id must raise, not return None")


class TestOwnershipIsDisjoint:
    """The invariant the whole architecture rests on."""

    def test_no_two_lanes_declare_the_same_owned_pattern(self):
        seen: dict[str, str] = {}
        clashes = []
        for lane in lanes.LANES:
            for pattern in lane.owns:
                if pattern in seen:
                    clashes.append(f"{pattern!r} claimed by {seen[pattern]} and {lane.lane_id}")
                seen[pattern] = lane.lane_id
        assert not clashes, "overlapping ownership:\n" + "\n".join(clashes)

    def test_no_real_repo_file_is_owned_by_more_than_one_lane(self):
        # Patterns can differ textually and still both match a real file, which
        # a string-equality check would miss entirely. This walks the actual
        # tree, which is the only check that catches that.
        conflicts = []
        for path in lanes.tracked_files(REPO_ROOT):
            owners = [lane.lane_id for lane in lanes.LANES if lane.owns_path(path)]
            if len(owners) > 1:
                conflicts.append(f"{path} owned by {owners}")
        assert not conflicts, "files with multiple owners:\n" + "\n".join(conflicts)

    def test_owner_of_returns_exactly_one_lane_or_none(self):
        for path in lanes.tracked_files(REPO_ROOT):
            owner = lanes.owner_of(path)
            assert owner is None or owner in {lane.lane_id for lane in lanes.LANES}


class TestCrossCuttingFilesAreUnowned:
    def test_the_governing_files_belong_to_no_lane(self):
        for name in lanes.CROSS_CUTTING:
            assert lanes.owner_of(name) is None, (
                f"{name} is cross-cutting and must not be owned by a lane - "
                "the file that records the rules cannot have eight writers"
            )

    def test_claude_md_specifically_is_unowned(self):
        assert "CLAUDE.md" in lanes.CROSS_CUTTING
        assert lanes.owner_of("CLAUDE.md") is None

    def test_a_cross_cutting_file_is_reported_as_such(self):
        assert lanes.is_cross_cutting("pytest.ini")
        assert not lanes.is_cross_cutting("lanternlight/redact.py")


class TestPrimaryCheckoutIsStableFromEveryWorktree:
    """Found by actually running a lane, which is why the run was worth doing.

    ``REPO_ROOT`` is derived from ``__file__``, so inside a lane worktree it
    resolves to *that worktree* - and every assertion of the form "a lane
    worktree is not the primary checkout" silently inverts, because for the
    lane whose worktree you are in, they are the same directory.

    ``primary_checkout()`` asks git instead. ``--git-common-dir`` returns the
    same absolute path from the main checkout and from every linked worktree,
    so it is a fact about the repository rather than about where the code
    happens to be executing.
    """

    def test_primary_checkout_matches_gits_own_answer(self):
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            pytest.skip("git unavailable")
        expected = Path(proc.stdout.strip()).parent.resolve()
        assert lanes.primary_checkout().resolve() == expected

    def test_the_primary_checkout_is_never_a_lane_worktree(self):
        primary = lanes.primary_checkout().resolve()
        for lane in lanes.LANES:
            assert primary != lane.worktree_path().resolve(), (
                f"primary checkout resolved to lane {lane.lane_id}'s worktree - "
                "this is the worktree-relative bug"
            )

    def test_it_falls_back_rather_than_raising_without_git(self, tmp_path):
        # A source tarball has no .git. Returning something sane beats raising.
        assert lanes.primary_checkout(start=tmp_path) is not None


class TestIsolation:
    def test_every_lane_has_a_unique_worktree_path(self):
        paths = [lane.worktree_path() for lane in lanes.LANES]
        assert len(paths) == len(set(paths))

    def test_every_lane_has_a_unique_branch(self):
        branches = [lane.branch_name() for lane in lanes.LANES]
        assert len(branches) == len(set(branches))

    def test_no_lane_worktree_is_inside_the_main_checkout(self):
        # Two writers in one working directory is the unrecoverable class.
        # Compared against primary_checkout(), NOT REPO_ROOT - inside a lane
        # worktree the latter is that worktree and this assertion inverts.
        primary = lanes.primary_checkout().resolve()
        for lane in lanes.LANES:
            assert primary not in lane.worktree_path().resolve().parents
            assert lane.worktree_path().resolve() != primary

    def test_branches_are_namespaced_so_they_never_collide_with_main(self):
        for lane in lanes.LANES:
            assert lane.branch_name().startswith("lane/")
            assert lane.branch_name() != "main"


class TestVetoAndReadOnly:
    def test_at_least_one_lane_holds_a_veto(self):
        assert any(lane.veto for lane in lanes.LANES)

    def test_the_safety_lane_holds_a_veto(self):
        assert lanes.by_id("safety").veto, (
            "redaction is a safety boundary, not a peer slice - if it is red, "
            "nothing log-derived may be committed"
        )

    def test_the_verification_lane_owns_nothing(self):
        verify = lanes.by_id("verify")
        assert verify.owns == ()
        assert verify.read_only

    def test_a_read_only_lane_owns_nothing_by_construction(self):
        for lane in lanes.LANES:
            if lane.read_only:
                assert lane.owns == (), f"{lane.lane_id} is read-only but claims files"


class TestOwnsPath:
    def test_a_lane_owns_a_file_matching_its_glob(self):
        assert lanes.by_id("safety").owns_path("lanternlight/redact.py")

    def test_a_lane_does_not_own_a_file_outside_its_globs(self):
        assert not lanes.by_id("safety").owns_path("emberforge/__init__.py")

    def test_windows_style_separators_are_normalised(self):
        # The repo is Windows-first; a caller will pass backslashes eventually.
        assert lanes.by_id("safety").owns_path("lanternlight\\redact.py")

    def test_every_lane_that_owns_anything_owns_at_least_one_real_file(self):
        # A lane whose globs match nothing is a lane that will silently never
        # do any work - and it would look identical to a lane that is simply
        # idle. Emberforge and surface are allowed to be empty for now.
        tracked = list(lanes.tracked_files(REPO_ROOT))
        for lane in lanes.LANES:
            if not lane.owns or lane.lane_id in lanes.MAY_BE_EMPTY:
                continue
            assert any(lane.owns_path(p) for p in tracked), (
                f"lane {lane.lane_id} owns no file that exists - its globs are "
                "probably wrong, and an empty lane looks exactly like an idle one"
            )
