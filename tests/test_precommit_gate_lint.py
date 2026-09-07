"""The commit-time lint gate must fire on ADDED lines and on nothing else.

ROADMAP ``OPS-37`` criterion 2.

WHY IT IS SCOPED. This repository lints manually and tree-wide, with zero
commit-time enforcement. A tree-wide gate is not the fix: the moment one
pre-existing finding exists anywhere in the tree, every commit is refused for a
line nobody touched, and a guard that refuses everything gets switched off
within the hour. So the gate blocks on a finding only when the finding's line
number falls inside a line range that THIS COMMIT ADDS.

THE SUBTLE HALF, and the reason half of this file exists. The added ranges come
from the INDEX (``git diff --cached``). If the linter is then pointed at the
WORKING TREE, an unstaged edit shifts every line number and the two halves stop
describing the same file - the gate blocks on a line the commit did not add, or
waves through the line it did. Both directions are pinned below
(:func:`test_a_working_tree_edit_does_not_move_the_lines_the_gate_judges` and
:func:`test_a_working_tree_violation_on_an_added_line_does_not_block`), because
a gate that is wrong in only one direction still passes a test that checks only
the other.

WHAT THE END-TO-END TEST IS FOR. ``CLAUDE.md`` is explicit that a hook's
presence is not proof it fires, and that the only valid test is end to end. So
:func:`test_a_real_commit_of_a_violating_added_line_is_refused` wires the real
``.githooks/pre-commit`` into a throwaway repository, stages a real violation,
runs a real ``git commit`` and asserts HEAD did not move. Asserting that a
Python function returned a blocking verdict would prove the function, not the
gate.

WHAT A RENAME COSTS. git reports a renamed file as status ``R``, which the
gate's original ``--diff-filter=ACM`` listing excluded outright - so a file
that was renamed AND rewritten in one commit was invisible and every line it
added was permitted. Worse, widening the filter is only half a fix: a
``git diff --cached -- <new path>`` cannot see the deletion of the old path,
so git falls back to reporting the whole file as newly added and the gate then
blames every pre-existing line in it. ``TestRenamedFilesAreSeen`` pins both
halves, and ``TestTheRawListingDecidesPerStatus`` pins the decision made for
each git status letter.

Every git repository here is a throwaway under ``tmp_path``. Nothing in this
module touches this repository's own index.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import precommit_gate  # noqa: E402

HOOKS_DIR = REPO_ROOT / ".githooks"
GATE_SOURCE = REPO_ROOT / "tools" / "precommit_gate.py"
RUFF_CONFIG = REPO_ROOT / "ruff.toml"

#: git exports these to a hook, and a hook that runs this suite would otherwise
#: hand them to every ``git`` below - which would then operate on the
#: repository being committed instead of the throwaway one. The pre-commit hook
#: scrubs them before running pytest; this is the belt to that pair of braces.
GIT_HOOK_ENV = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_PARAMETERS",
    "GIT_AUTHOR_DATE",
    "GIT_EDITOR",
)


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in GIT_HOOK_ENV:
        env.pop(name, None)
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=300,
        env=_clean_env(),
        check=False,
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write(repo: Path, relpath: str, text: str) -> None:
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="ascii", newline="\n")


def _make_repo(root: Path, *, hooked: bool) -> Path:
    """A throwaway repository, optionally wired to the REAL pre-commit hook."""
    root.mkdir(parents=True, exist_ok=True)
    assert _git(root, "init", "-q").returncode == 0, "git init failed"
    settings = [
        ("user.email", "probe@example.invalid"),
        ("user.name", "probe"),
        ("commit.gpgsign", "false"),
    ]
    if hooked:
        settings.append(("core.hooksPath", HOOKS_DIR.as_posix()))
    else:
        # An empty but existing directory, rather than an unset key: this
        # machine's global config is not this test's business, and a repo that
        # silently inherited a hooksPath would make the unhooked cases lie.
        (root / ".nohooks").mkdir(exist_ok=True)
        settings.append(("core.hooksPath", (root / ".nohooks").as_posix()))
    for key, value in settings:
        assert _git(root, "config", key, value).returncode == 0, key
    shutil.copy2(RUFF_CONFIG, root / "ruff.toml")
    return root


def _seed(repo: Path, relpath: str, text: str) -> str:
    """Commit ``text`` at ``relpath`` WITHOUT running hooks; return the HEAD.

    Hooks are off for the seed on purpose. The seed's job is to establish
    "already in history, not added by the commit under test", and several seeds
    here are deliberately dirty - a seed that had to satisfy the gate could not
    express the pre-existing finding these tests are about.
    """
    _write(repo, relpath, text)
    assert _git(repo, "add", "--", relpath).returncode == 0
    result = _git(repo, "-c", "core.hooksPath=", "commit", "-q", "-m", "seed")
    assert result.returncode == 0, f"seed commit failed: {result.stderr}"
    return _head(repo)


def _stage(repo: Path, relpath: str, text: str) -> None:
    _write(repo, relpath, text)
    assert _git(repo, "add", "--", relpath).returncode == 0


@pytest.fixture(autouse=True)
def _require_ruff():
    """Skip honestly when ruff is absent rather than pass vacuously.

    ruff is not a declared dependency of this project, so a fresh clone can
    legitimately be without it. A test that quietly reported success in that
    state would be indistinguishable from one that had stopped exercising the
    gate at all.
    """
    if precommit_gate.ruff_command() is None:
        pytest.skip("ruff is not installed, so the lint gate cannot be exercised")


# ---------------------------------------------------------------------------
# Hunk-header parsing. Pure, no git required.
# ---------------------------------------------------------------------------


class TestAddedRangeParsing:
    def test_an_omitted_count_means_exactly_one_line(self):
        # `@@ -3 +7 @@` is git's spelling for a single added line, and it is
        # the COMMON case. Reading the missing count as zero would silently
        # give every one-line addition an empty range, and the gate would look
        # like it worked while never firing on the commits it most needs to.
        assert precommit_gate.parse_added_ranges("@@ -3 +7 @@\n") == [(7, 7)]

    def test_an_explicit_count_spans_that_many_lines(self):
        assert precommit_gate.parse_added_ranges("@@ -1,0 +2,3 @@\n") == [(2, 4)]

    def test_a_pure_deletion_hunk_contributes_no_range(self):
        # `+3,0` adds nothing. A range of (3, 3) here would blame the commit
        # for whatever line 3 happens to be after the deletion.
        assert precommit_gate.parse_added_ranges("@@ -4,3 +3,0 @@\n") == []

    def test_every_hunk_in_the_diff_is_collected(self):
        diff = "@@ -1 +1 @@\n-old\n+new\n@@ -9,0 +10,2 @@\n+a\n+b\n"
        assert precommit_gate.parse_added_ranges(diff) == [(1, 1), (10, 11)]

    def test_trailing_section_headings_do_not_confuse_the_parser(self):
        # git appends the enclosing function to the hunk header. It must not
        # be mistaken for part of the line numbers.
        diff = "@@ -12 +12 @@ def enclosing(self):\n-a\n+b\n"
        assert precommit_gate.parse_added_ranges(diff) == [(12, 12)]

    def test_added_lines_are_inside_and_neighbours_are_outside(self):
        ranges = [(2, 4)]
        assert not precommit_gate.line_is_added(1, ranges)
        assert precommit_gate.line_is_added(2, ranges)
        assert precommit_gate.line_is_added(4, ranges)
        assert not precommit_gate.line_is_added(5, ranges)

    def test_git_really_emits_the_omitted_count_form(self, tmp_path):
        # The omitted-count branch above is written against a fixture string.
        # This asserts the fixture is not fiction: real git, real index, one
        # added line, and the header carries no count.
        repo = _make_repo(tmp_path / "omitted", hooked=False)
        _seed(repo, "mod.py", "VALUE = 1\n")
        _stage(repo, "mod.py", "VALUE = 1\nOTHER = 2\n")
        diff = precommit_gate.staged_diff(repo, "mod.py")
        assert "+2 @@" in diff, f"git did not emit a bare count here:\n{diff}"
        assert precommit_gate.parse_added_ranges(diff) == [(2, 2)]


# ---------------------------------------------------------------------------
# Scoping. Real index, real ruff.
# ---------------------------------------------------------------------------


class TestTheGateIsScopedToAddedLines:
    def test_a_violation_on_an_added_line_blocks(self, tmp_path):
        repo = _make_repo(tmp_path / "inside", hooked=False)
        _seed(repo, "mod.py", "import os\nVALUE = 1\n")
        _stage(repo, "mod.py", "import os\nVALUE = 1\nimport sys\n")

        findings = precommit_gate.lint_staged(repo)

        assert findings, "the added `import sys` is unused and must be caught"
        assert {f.line for f in findings} == {3}, findings
        assert {f.path for f in findings} == {"mod.py"}, findings
        assert any(f.code == "F401" for f in findings), findings

    def test_a_pre_existing_violation_outside_the_added_range_does_not_block(
        self, tmp_path
    ):
        # The seed's line 1 is an unused import and ruff still reports it on
        # every run. The commit does not touch it, so the gate must not care.
        repo = _make_repo(tmp_path / "outside", hooked=False)
        _seed(repo, "mod.py", "import os\nVALUE = 1\n")
        _stage(repo, "mod.py", "import os\nVALUE = 1\nOTHER = 2\n")

        assert precommit_gate.lint_staged(repo) == []

    def test_the_pre_existing_finding_is_really_still_there(self, tmp_path):
        # Guards the test above against passing for the wrong reason. If ruff
        # stopped reporting the seed's unused import, "no findings" would prove
        # nothing about scoping.
        repo = _make_repo(tmp_path / "control", hooked=False)
        _seed(repo, "mod.py", "import os\nVALUE = 1\n")
        _stage(repo, "mod.py", "import os\nVALUE = 1\nOTHER = 2\n")
        raw = precommit_gate.ruff_findings(repo, "mod.py", "import os\nVALUE = 1\nOTHER = 2\n")
        assert any(f.line == 1 and f.code == "F401" for f in raw), raw

    def test_a_commit_with_no_staged_python_passes(self, tmp_path):
        repo = _make_repo(tmp_path / "nopy", hooked=False)
        _seed(repo, "notes.txt", "seed\n")
        _stage(repo, "notes.txt", "seed\nmore\n")
        _stage(repo, "data.json", '{"a": 1}\n')

        assert precommit_gate.lint_staged(repo) == []

    def test_a_deleted_python_file_contributes_nothing(self, tmp_path):
        repo = _make_repo(tmp_path / "deleted", hooked=False)
        _seed(repo, "mod.py", "import os\nVALUE = 1\n")
        assert _git(repo, "rm", "-q", "--", "mod.py").returncode == 0

        assert precommit_gate.lint_staged(repo) == []


class TestTheGateJudgesTheStagedContent:
    """The index supplies the line numbers, so the index must supply the text.

    Two directions, because getting one right by accident is easy.
    """

    def test_a_working_tree_edit_does_not_move_the_lines_the_gate_judges(
        self, tmp_path
    ):
        # STAGED: the violation is on line 2, which is the line the commit
        # adds. WORKING TREE: two blank lines pad it down to line 4, which the
        # commit did not add. A gate that lints the working tree finds line 4,
        # decides it is out of range, and lets a real violation through.
        repo = _make_repo(tmp_path / "shifted", hooked=False)
        _seed(repo, "mod.py", "VALUE = 1\n")
        _stage(repo, "mod.py", "VALUE = 1\nimport os\n")
        _write(repo, "mod.py", "VALUE = 1\n\n\nimport os\n")

        findings = precommit_gate.lint_staged(repo)

        assert findings, (
            "the staged violation on line 2 was missed - the gate is reading "
            "the working tree, where the same violation sits on line 4"
        )
        assert {f.line for f in findings} == {2}, findings

    def test_a_working_tree_violation_on_an_added_line_does_not_block(self, tmp_path):
        # The mirror. STAGED content is clean; the operator's unstaged edit
        # introduces a violation on the very line the commit adds. A gate
        # reading the working tree refuses a commit that carries nothing wrong.
        repo = _make_repo(tmp_path / "unstaged", hooked=False)
        _seed(repo, "mod.py", "VALUE = 1\n")
        _stage(repo, "mod.py", "VALUE = 1\nOTHER = 2\n")
        _write(repo, "mod.py", "VALUE = 1\nimport os\n")

        assert precommit_gate.lint_staged(repo) == [], (
            "the gate refused a clean staged change because of an UNSTAGED "
            "edit - it is linting the working tree"
        )


# ---------------------------------------------------------------------------
# End to end. A real hook, a real commit, a real HEAD.
# ---------------------------------------------------------------------------


def _hooked_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo on the real hook, seeded THROUGH the hook, plus its HEAD."""
    repo = _make_repo(tmp_path / "e2e", hooked=True)
    (repo / "tools").mkdir(exist_ok=True)
    shutil.copy2(GATE_SOURCE, repo / "tools" / "precommit_gate.py")
    _write(repo, "seed.txt", "seed\n")
    assert _git(repo, "add", "seed.txt", "ruff.toml", "tools/precommit_gate.py").returncode == 0
    first = _git(repo, "commit", "-m", "probe: initial")
    assert first.returncode == 0, (
        "the hook refused an innocent commit, so a refusal below would prove "
        f"only that it refuses everything.\n{first.stdout}\n{first.stderr}"
    )
    return repo, _head(repo)


def test_a_clean_added_line_still_commits(tmp_path):
    """The control. Without it, the refusal test cannot mean anything."""
    repo, before = _hooked_repo(tmp_path)
    _stage(repo, "clean.py", "VALUE = 1\n")
    result = _git(repo, "commit", "-m", "probe: clean")
    assert result.returncode == 0, (
        f"the gate refused a clean file.\n{result.stdout}\n{result.stderr}"
    )
    assert _head(repo) != before, "the clean commit did not land"


def test_a_real_commit_of_a_violating_added_line_is_refused(tmp_path):
    """Stage a real violation, run a real ``git commit``, assert HEAD is fixed.

    This is the assertion the item turns on. Everything above tests functions;
    only this tests THE GATE - that ``.githooks/pre-commit`` reaches the lint
    check at all, that it reads its exit code, and that git therefore writes no
    commit object.
    """
    repo, before = _hooked_repo(tmp_path)
    _stage(repo, "violating.py", "import os\nVALUE = 1\n")

    result = _git(repo, "commit", "-m", "probe: must be refused")
    after = _head(repo)

    assert after == before, (
        "THE VIOLATING COMMIT LANDED. "
        f"HEAD moved {before[:8]} -> {after[:8]}; git exit {result.returncode}"
    )
    assert result.returncode != 0, "git reported success on a refused commit"
    combined = result.stdout + result.stderr
    assert "F401" in combined, (
        "the commit was refused, but not by the lint gate - no lint code in "
        f"the output, so some other hook rule fired.\n{combined}"
    )


def test_a_repository_without_the_gate_is_skipped_not_refused(tmp_path):
    """A repository that does not carry the gate is SKIPPED, not refused.

    ``tests/test_no_pii.py`` and ``tests/test_ascii_hygiene.py`` point throwaway
    repositories at this same hook and commit ordinary ``.py`` files into them.
    Those trees are not Lanternlight, carry no ``tools/precommit_gate.py`` and
    have no lint config, so the block must stand down there exactly as the
    doc-guard block does.
    """
    repo = _make_repo(tmp_path / "nogate", hooked=True)
    (repo / "ruff.toml").unlink()
    _write(repo, "seed.txt", "seed\n")
    assert _git(repo, "add", "seed.txt").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "seed").returncode == 0
    before = _head(repo)

    _stage(repo, "ordinary.py", "import os\nVALUE = 1\n")
    result = _git(repo, "commit", "-m", "probe: no gate present")

    assert result.returncode == 0, (
        "the hook refused a commit in a repository that carries no lint gate "
        f"and no lint config.\n{result.stdout}\n{result.stderr}"
    )
    assert _head(repo) != before


# ---------------------------------------------------------------------------
# Renames. Real index, real ruff.
# ---------------------------------------------------------------------------


def _bulk(prefix: str, count: int) -> str:
    """``count`` boring, lint-clean assignment lines.

    Bulk exists to push the rename similarity index well above git's default
    50 percent threshold, so these fixtures exercise the RENAME path and not
    the delete-plus-add path a small file would fall back to.
    """
    return "".join(f"{prefix}_{index} = {index}\n" for index in range(1, count + 1))


def _rename(repo: Path, old: str, new: str) -> None:
    """``git mv``, which stages the rename on both sides."""
    result = _git(repo, "mv", "--", old, new)
    assert result.returncode == 0, f"git mv {old} {new} failed: {result.stderr}"


class TestRenamedFilesAreSeen:
    """A renamed-and-modified file must be judged on the lines it ADDS.

    The defect these pin: ``git`` reports a rename as status ``R``, the gate
    listed staged paths with ``--diff-filter=ACM``, and ``ACM`` excludes ``R``.
    The staged listing came back EMPTY for a commit that renamed a file and
    added an unused import to it, so the gate reported no findings and
    permitted a violation ruff reports on the same staged bytes.
    """

    def test_a_rename_that_adds_a_violation_blocks(self, tmp_path):
        repo = _make_repo(tmp_path / "rename_dirty", hooked=False)
        body = _bulk("VALUE", 17)
        _seed(repo, "big.py", body)
        _rename(repo, "big.py", "renamed.py")
        _stage(repo, "renamed.py", body + "import json\n")

        findings = precommit_gate.lint_staged(repo)

        assert findings, (
            "the renamed file was invisible to the gate - git reports a rename "
            "as R and the staged listing excluded it, so a net-new unused "
            "import was permitted"
        )
        assert {f.line for f in findings} == {18}, findings
        assert {f.path for f in findings} == {"renamed.py"}, findings
        assert any(f.code == "F401" for f in findings), findings

    def test_a_pure_rename_contributes_nothing(self, tmp_path):
        # No content change at all, so no line in the new file was written by
        # this commit. Exactly like a deletion: nothing to blame.
        repo = _make_repo(tmp_path / "rename_pure", hooked=False)
        _seed(repo, "clean.py", _bulk("VALUE", 17))
        _rename(repo, "clean.py", "moved.py")

        assert precommit_gate.lint_staged(repo) == []

    def test_a_rename_carrying_a_pre_existing_violation_does_not_block(self, tmp_path):
        repo = _make_repo(tmp_path / "rename_carry", hooked=False)
        _seed(repo, "dirty.py", "import os\n" + _bulk("VALUE", 17))
        _rename(repo, "dirty.py", "moved.py")

        assert precommit_gate.lint_staged(repo) == [], (
            "moving a file is not writing its lines - the gate blamed the "
            "commit for a finding that was already in history"
        )

    def test_the_carried_violation_is_really_still_in_the_staged_blob(self, tmp_path):
        # Control for the test above. Without it, "no findings" could just as
        # easily mean the gate stopped looking at the file at all.
        repo = _make_repo(tmp_path / "rename_carry_ctl", hooked=False)
        _seed(repo, "dirty.py", "import os\n" + _bulk("VALUE", 17))
        _rename(repo, "dirty.py", "moved.py")

        staged = precommit_gate.staged_source(repo, "moved.py")
        assert staged is not None and staged.startswith("import os\n"), staged
        raw = precommit_gate.ruff_findings(repo, "moved.py", staged)
        assert any(f.line == 1 and f.code == "F401" for f in raw), raw

    def test_a_rename_that_only_moves_a_violation_does_not_block(self, tmp_path):
        # The added line is line 1. The pre-existing unused import slides from
        # line 1 to line 2 - it is inside the file the commit writes, but it is
        # not on a line the commit added.
        repo = _make_repo(tmp_path / "rename_shift", hooked=False)
        body = "import os\n" + _bulk("VALUE", 17)
        _seed(repo, "dirty.py", body)
        _rename(repo, "dirty.py", "moved.py")
        _stage(repo, "moved.py", "OTHER = 2\n" + body)

        assert precommit_gate.lint_staged(repo) == [], (
            "the gate blamed this commit for an import it only pushed down "
            "one line"
        )

    def test_that_shifted_violation_is_really_reported_on_line_two(self, tmp_path):
        # Control for the test above, in both halves: ruff still reports the
        # import, and the added range really is line 1 and nothing else.
        repo = _make_repo(tmp_path / "rename_shift_ctl", hooked=False)
        body = "import os\n" + _bulk("VALUE", 17)
        _seed(repo, "dirty.py", body)
        _rename(repo, "dirty.py", "moved.py")
        _stage(repo, "moved.py", "OTHER = 2\n" + body)

        staged = precommit_gate.staged_source(repo, "moved.py")
        raw = precommit_gate.ruff_findings(repo, "moved.py", staged)
        assert any(f.line == 2 and f.code == "F401" for f in raw), raw
        diff = precommit_gate.staged_diff(repo, "moved.py", "dirty.py")
        assert precommit_gate.parse_added_ranges(diff) == [(1, 1)], diff

    def test_the_origin_path_is_what_pairs_the_rename(self, tmp_path):
        """Widening the status filter alone is NOT the fix.

        ``git diff --cached -- <new path>`` filters the old path's deletion out
        of the diff, so rename detection has nothing to pair with and git falls
        back to reporting the destination as a brand-new file - every line of
        it "added". A gate built that way swaps a false PASS for a false BLOCK
        on every pre-existing finding in a moved file. Both shapes are measured
        here rather than asserted, because this is the exact half-fix the test
        exists to refuse.
        """
        repo = _make_repo(tmp_path / "rename_pairing", hooked=False)
        body = _bulk("VALUE", 17)
        _seed(repo, "big.py", body)
        _rename(repo, "big.py", "renamed.py")
        _stage(repo, "renamed.py", body + "import json\n")

        unpaired = precommit_gate.staged_diff(repo, "renamed.py")
        assert "new file mode" in unpaired, unpaired
        assert precommit_gate.parse_added_ranges(unpaired) == [(1, 18)], unpaired

        paired = precommit_gate.staged_diff(repo, "renamed.py", "big.py")
        assert "rename from big.py" in paired, paired
        assert precommit_gate.parse_added_ranges(paired) == [(18, 18)], paired

    def test_the_staged_listing_names_both_sides_of_the_rename(self, tmp_path):
        repo = _make_repo(tmp_path / "rename_entries", hooked=False)
        body = _bulk("VALUE", 17)
        _seed(repo, "big.py", body)
        _rename(repo, "big.py", "renamed.py")
        _stage(repo, "renamed.py", body + "import json\n")

        entries = precommit_gate.staged_python_entries(repo)

        assert [(e.origin, e.path, e.status) for e in entries] == [
            ("big.py", "renamed.py", "R")
        ], entries

    def test_a_rename_out_of_python_is_not_listed(self, tmp_path):
        # The destination decides. `mod.py` -> `notes.txt` leaves no Python
        # file behind to lint.
        repo = _make_repo(tmp_path / "rename_out", hooked=False)
        _seed(repo, "mod.py", _bulk("VALUE", 17))
        _rename(repo, "mod.py", "notes.txt")

        assert precommit_gate.staged_python_entries(repo) == []

    def test_a_rename_into_python_is_listed(self, tmp_path):
        # The mirror. A text file renamed to `.py` becomes Python and the
        # lines the rename rewrites are this commit's.
        repo = _make_repo(tmp_path / "rename_in", hooked=False)
        body = _bulk("VALUE", 17)
        _seed(repo, "notes.txt", body)
        _rename(repo, "notes.txt", "mod.py")
        _stage(repo, "mod.py", body + "import json\n")

        entries = precommit_gate.staged_python_entries(repo)
        assert [(e.origin, e.path) for e in entries] == [("notes.txt", "mod.py")]
        findings = precommit_gate.lint_staged(repo)
        # Line 18 and nothing else, which is the added line. ruff reports more
        # than one code there (E402 as well as F401), so the codes are checked
        # by membership while the path and line are pinned exactly.
        assert {(f.path, f.line) for f in findings} == {("mod.py", 18)}, findings
        assert any(f.code == "F401" for f in findings), findings

    def test_git_really_emits_the_two_path_rename_record(self, tmp_path):
        # The synthetic records in TestTheRawListingDecidesPerStatus are
        # written against strings. This asserts the strings are not fiction.
        repo = _make_repo(tmp_path / "rename_raw", hooked=False)
        body = _bulk("VALUE", 17)
        _seed(repo, "big.py", body)
        _rename(repo, "big.py", "renamed.py")
        _stage(repo, "renamed.py", body + "import json\n")

        raw = precommit_gate.staged_raw_listing(repo)

        assert re.fullmatch(
            r":100644 100644 [0-9a-f]+ [0-9a-f]+ R\d+\x00big\.py\x00renamed\.py\x00",
            raw,
        ), repr(raw)


# ---------------------------------------------------------------------------
# One decision per git status letter, each one written down.
# ---------------------------------------------------------------------------


def _record(src_mode: str, dst_mode: str, status: str, *paths: str) -> str:
    return f":{src_mode} {dst_mode} 1111111 2222222 {status}\0" + "".join(
        f"{path}\0" for path in paths
    )


class TestTheRawListingDecidesPerStatus:
    """``A M R C T`` are lintable when the destination is a regular file blob.

    ``D`` and ``U`` are not, and neither is a ``T`` whose destination is a
    symlink or a gitlink: there is no Python text at the far end of one, and
    ``git show :<path>`` on an unmerged path fails outright because there is no
    stage-0 blob to show.

    ``C`` is understood but cannot arrive through :func:`staged_raw_listing`,
    which passes an explicit ``-M``; see
    :func:`test_explicit_rename_detection_suppresses_copy_records`. It is
    parsed anyway because a two-path record read as a one-path record would
    desynchronise every record after it in the NUL-separated stream.
    """

    def test_a_modification_is_lintable_and_is_its_own_origin(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "100644", "M", "mod.py")
        )
        assert (entry.origin, entry.path, entry.status) == ("mod.py", "mod.py", "M")
        assert entry.lintable

    def test_an_addition_is_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("000000", "100644", "A", "new.py")
        )
        assert (entry.origin, entry.path, entry.status) == ("new.py", "new.py", "A")
        assert entry.lintable

    def test_a_rename_record_carries_two_paths(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "100644", "R094", "old.py", "new.py")
        )
        assert (entry.origin, entry.path, entry.status) == ("old.py", "new.py", "R")
        assert entry.lintable

    def test_a_copy_record_carries_two_paths(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "100644", "C095", "src.py", "dup.py")
        )
        assert (entry.origin, entry.path, entry.status) == ("src.py", "dup.py", "C")
        assert entry.lintable

    def test_an_executable_blob_is_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "100755", "M", "mod.py")
        )
        assert entry.lintable

    def test_a_deletion_is_not_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "000000", "D", "gone.py")
        )
        assert entry.status == "D"
        assert not entry.lintable

    def test_an_unmerged_record_is_not_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "000000", "U", "conflict.py")
        )
        assert entry.status == "U"
        assert not entry.lintable

    def test_a_typechange_into_a_symlink_is_not_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("100644", "120000", "T", "mod.py")
        )
        assert entry.status == "T"
        assert not entry.lintable

    def test_a_typechange_out_of_a_symlink_is_lintable(self):
        # Real Python text is arriving where a link used to be. That IS a
        # staged blob and the commit wrote all of it.
        (entry,) = precommit_gate.parse_raw_records(
            _record("120000", "100644", "T", "mod.py")
        )
        assert entry.lintable

    def test_a_gitlink_destination_is_not_lintable(self):
        (entry,) = precommit_gate.parse_raw_records(
            _record("000000", "160000", "A", "sub")
        )
        assert not entry.lintable

    def test_two_path_records_do_not_desynchronise_the_stream(self):
        raw = (
            _record("100644", "100644", "R094", "old.py", "new.py")
            + _record("100644", "100644", "M", "other.py")
            + _record("100644", "000000", "D", "gone.py")
        )
        records = precommit_gate.parse_raw_records(raw)
        assert [(r.origin, r.path, r.status) for r in records] == [
            ("old.py", "new.py", "R"),
            ("other.py", "other.py", "M"),
            ("gone.py", "gone.py", "D"),
        ]

    def test_a_path_beginning_with_a_colon_is_not_read_as_a_header(self):
        # Record boundaries come from the status letter's arity, never from a
        # leading colon. A path may legitimately start with one.
        raw = _record("100644", "100644", "M", ":odd.py") + _record(
            "100644", "100644", "M", "plain.py"
        )
        records = precommit_gate.parse_raw_records(raw)
        assert [r.path for r in records] == [":odd.py", "plain.py"]

    def test_a_malformed_record_refuses_rather_than_dropping_files(self):
        with pytest.raises(precommit_gate.StagedListingFailed):
            precommit_gate.parse_raw_records("not a raw record\0mod.py\0")


class TestTheStatusDecisionsAgainstRealGit:
    """The decisions above, re-measured against git rather than a fixture."""

    def test_an_unmerged_path_is_not_listed(self, tmp_path):
        repo = _make_repo(tmp_path / "unmerged", hooked=False)
        _seed(repo, "mod.py", "VALUE = 1\n")
        base = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        assert _git(repo, "checkout", "-q", "-b", "other").returncode == 0
        _stage(repo, "mod.py", "VALUE = 2\nimport os\n")
        commit = _git(repo, "-c", "core.hooksPath=", "commit", "-q", "-m", "other")
        assert commit.returncode == 0, commit.stderr
        assert _git(repo, "checkout", "-q", base).returncode == 0
        _stage(repo, "mod.py", "VALUE = 3\nimport sys\n")
        commit = _git(repo, "-c", "core.hooksPath=", "commit", "-q", "-m", "mine")
        assert commit.returncode == 0, commit.stderr
        assert _git(repo, "merge", "other").returncode != 0, "expected a conflict"

        raw = precommit_gate.staged_raw_listing(repo)
        assert " U\0mod.py\0" in raw, repr(raw)
        assert precommit_gate.staged_python_entries(repo) == []
        assert precommit_gate.lint_staged(repo) == []

    def test_a_typechange_into_a_symlink_is_not_linted(self, tmp_path):
        repo = _make_repo(tmp_path / "typechange", hooked=False)
        _seed(repo, "mod.py", "VALUE = 1\n")
        _write(repo, "linkbody", "target.py")
        blob = _git(repo, "hash-object", "-w", "--", "linkbody").stdout.strip()
        assert blob, "hash-object wrote nothing"
        cached = _git(repo, "update-index", "--cacheinfo", f"120000,{blob},mod.py")
        assert cached.returncode == 0, cached.stderr

        raw = precommit_gate.staged_raw_listing(repo)
        assert " T\0mod.py\0" in raw, repr(raw)
        assert precommit_gate.staged_python_entries(repo) == []
        assert precommit_gate.lint_staged(repo) == []

        # Control: the link body really does lint dirty, so the empty verdict
        # above is the mode guard working rather than ruff having nothing to
        # say about the bytes at the far end of a symlink.
        body = precommit_gate.staged_source(repo, "mod.py")
        assert body == "target.py", repr(body)
        assert precommit_gate.ruff_findings(repo, "mod.py", body), (
            "the control is vacuous - ruff found nothing in the link body"
        )

    def test_explicit_rename_detection_suppresses_copy_records(self, tmp_path):
        """``diff.renames=copies`` must not weaken the gate.

        Copy detection excuses the lines a new file shares with an existing
        one. That is the wrong default for a guard: a genuinely new file that
        happens to resemble an old one would arrive pre-forgiven. So the
        listing passes an explicit ``-M``, the copy is reported as a plain
        ``A``, and every line of the new file counts as added.
        """
        repo = _make_repo(tmp_path / "copies", hooked=False)
        assert _git(repo, "config", "diff.renames", "copies").returncode == 0
        body = _bulk("VALUE", 20)
        _seed(repo, "src.py", body)
        _stage(repo, "src.py", body + "EXTRA = 1\n")
        _stage(repo, "dup.py", body + "import json\n")

        # Control: git really would report a copy here if asked its own way.
        honoured = _git(repo, "diff", "--cached", "--raw", "-z").stdout
        assert "\0src.py\0dup.py\0" in honoured, repr(honoured)

        entries = precommit_gate.staged_python_entries(repo)
        assert sorted((e.origin, e.path, e.status) for e in entries) == [
            ("dup.py", "dup.py", "A"),
            ("src.py", "src.py", "M"),
        ], entries

    def test_rename_detection_does_not_depend_on_local_config(self, tmp_path):
        """``diff.renames=false`` must not put the hole back.

        Rename detection is a configurable default, and a repository that
        turned it off would report the rename as a delete plus an add - which
        blames the commit for every pre-existing line in the moved file. The
        listing therefore asks for ``-M`` explicitly instead of inheriting it.
        """
        repo = _make_repo(tmp_path / "norenames", hooked=False)
        assert _git(repo, "config", "diff.renames", "false").returncode == 0
        body = "import os\n" + _bulk("VALUE", 17)
        _seed(repo, "dirty.py", body)
        _rename(repo, "dirty.py", "moved.py")

        # Control: with the repository's own setting honoured, git splits it.
        honoured = _git(repo, "diff", "--cached", "--raw", "-z").stdout
        assert " D\0dirty.py\0" in honoured, repr(honoured)

        entries = precommit_gate.staged_python_entries(repo)
        assert [(e.origin, e.path, e.status) for e in entries] == [
            ("dirty.py", "moved.py", "R")
        ], entries
        assert precommit_gate.lint_staged(repo) == []


# ---------------------------------------------------------------------------
# End to end, for renames. A real hook, a real commit, a real HEAD.
# ---------------------------------------------------------------------------
#
# WHY THESE STAGE AN UNRELATED COMPANION .py FILE. `.githooks/pre-commit`
# computes its own staged set with `git diff --cached --name-only
# --diff-filter=ACM` and exits 0 immediately when that is empty. A commit that
# ONLY renames a file therefore never reaches the hook's lint section at all,
# whatever this module does - the same `ACM` defect, one layer up, in a file
# this lane does not own. Staging one ordinary .py alongside the rename gets
# the hook past its own filter so the gate below it is genuinely exercised.
# Written down here rather than left in a chat message: the caveat is part of
# what these two tests do and do not prove.


def _rename_e2e_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A hooked repo holding a committed 17-line Python file, plus its body."""
    repo, _ = _hooked_repo(tmp_path)
    body = _bulk("VALUE", 17)
    _stage(repo, "big.py", body)
    result = _git(repo, "commit", "-m", "probe: seed big.py")
    assert result.returncode == 0, (
        f"the hook refused a clean seed.\n{result.stdout}\n{result.stderr}"
    )
    return repo, _head(repo), body


def test_a_real_commit_of_a_rename_with_a_violating_added_line_is_refused(tmp_path):
    repo, before, body = _rename_e2e_repo(tmp_path)
    _rename(repo, "big.py", "renamed.py")
    _stage(repo, "renamed.py", body + "import json\n")
    _stage(repo, "companion.py", "COMPANION = 1\n")

    result = _git(repo, "commit", "-m", "probe: rename must be refused")
    after = _head(repo)

    assert after == before, (
        "THE RENAMED VIOLATION LANDED. "
        f"HEAD moved {before[:8]} -> {after[:8]}; git exit {result.returncode}"
    )
    assert result.returncode != 0, "git reported success on a refused commit"
    combined = result.stdout + result.stderr
    assert "F401" in combined, (
        "the commit was refused, but not by the lint gate - no lint code in "
        f"the output, so some other hook rule fired.\n{combined}"
    )
    assert "renamed.py" in combined, (
        f"the refusal did not name the renamed file.\n{combined}"
    )


def test_a_real_pure_rename_still_commits(tmp_path):
    """The control. A rename that adds nothing must not be refused.

    The companion file is staged here for the same reason as above, so this
    really does run the gate rather than coasting on the hook's early exit.
    """
    repo, before, _ = _rename_e2e_repo(tmp_path)
    _rename(repo, "big.py", "renamed.py")
    _stage(repo, "companion.py", "COMPANION = 1\n")

    result = _git(repo, "commit", "-m", "probe: pure rename")

    assert result.returncode == 0, (
        f"the gate refused a pure rename.\n{result.stdout}\n{result.stderr}"
    )
    assert _head(repo) != before, "the pure rename did not land"
