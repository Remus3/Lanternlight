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

import json
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

import _toolguard  # noqa: E402

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
        [_toolguard.require("git"), *args],
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
        # OPS-83. This next line IS the wire: from here the throwaway
        # repository runs this repository's REAL `.githooks/pre-commit`, whose
        # shebang is `#!/bin/sh` and whose body calls grep, head, tr and wc.
        # Without that POSIX userland on PATH git cannot spawn the hook at all
        # and the end-to-end cases go red for a reason nothing names. The
        # unhooked branch below reaches no hook and is deliberately NOT guarded
        # - skipping tests that never needed the tool is a coverage loss.
        _toolguard.require_posix_userland()
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


# ---------------------------------------------------------------------------
# Filenames carrying git pathspec metacharacters.
# ---------------------------------------------------------------------------


def _bracket_repo(root: Path) -> tuple[Path, str]:
    """A repo holding BOTH ``a[b].py`` and the name its glob expands to.

    ``a[b].py`` read as a wildmatch pattern is a bracket expression matching
    the single character ``b``, so it also names ``ab.py``. Seeding both is
    the whole point: one file alone cannot tell a literal match from a glob
    match, because either reading finds it.
    """
    repo = _make_repo(root, hooked=False)
    seed = "import os\nVALUE = 1\n"
    _seed(repo, "ab.py", seed)
    _seed(repo, BRACKET_NAME, seed)
    return repo, seed


BRACKET_NAME = "a[b].py"


class TestAFilenameCarryingPathspecMetacharacters:
    """``staged_diff`` must name its path LITERALLY, not as a glob.

    git treats a pathspec as a wildmatch pattern unless told otherwise, and
    ``git diff --cached -- <path>`` therefore answers about every path the
    pattern happens to reach. FOR THE BRACKET CASE it is not an under-match:
    git compares the pathspec to the name literally FIRST and only falls back
    to wildmatch, so a real file named ``a[b].py`` IS found. The damage is the
    other direction - the reply carries a SECOND file's hunks as well, and
    :func:`parse_added_ranges` reads every hunk header it is given because
    ``staged_diff`` promises one change per call. The added ranges for
    ``a[b].py`` then include line numbers that belong to ``ab.py``, and the
    gate attributes another file's edits to this one.

    DO NOT READ THAT AS "THERE IS NO UNDER-MATCH". It is a statement about
    bracket expressions, and a refutation pass measured a case where it is
    false: a leading ``:`` is pathspec MAGIC and is parsed before matching
    runs at all, so a bare ``:colon.py`` misses the real file entirely. That
    is the silent direction, and it is why the fix is a magic prefix rather
    than an escape.

    WHICH CASES ARE REAL ON THIS MACHINE. ``*``, ``?`` and ``:`` are illegal
    in NTFS filenames, so ``[`` and ``]`` are the only metacharacters a real
    Windows file can carry - those get a real repository below. The colon case
    above was measured only with ``core.protectNTFS`` forced off, because Git
    for Windows will not put such a name in the index otherwise. The rename
    branch and the argument shape are pinned at ARGUMENT level instead, by
    capturing what is handed to git: a bare origin cannot be made to misfire
    with real files here, because the origin is already named alongside the
    destination.
    """

    def test_the_diff_for_a_bracketed_name_carries_only_that_file(self, tmp_path):
        repo, seed = _bracket_repo(tmp_path / "brackets")
        _stage(repo, "ab.py", seed + "import sys\n")
        _stage(repo, BRACKET_NAME, seed + "import json\n")

        diff = precommit_gate.staged_diff(repo, BRACKET_NAME)

        assert diff, f"no staged diff at all for {BRACKET_NAME!r}"
        assert "import json" in diff, (
            f"the diff does not carry {BRACKET_NAME!r}'s own added line:\n{diff}"
        )
        assert "b/ab.py" not in diff, (
            "the bare pathspec was glob-expanded and dragged in ab.py, whose "
            f"hunks are not this change's:\n{diff}"
        )

    def test_the_glob_neighbour_does_not_inflate_the_added_ranges(self, tmp_path):
        # ab.py adds at line 3 and so does a[b].py, so a union is invisible
        # here unless the neighbour's added line sits somewhere else. Push
        # ab.py's addition to line 5 and the pollution becomes a range that
        # cannot come from the bracketed file at all.
        repo, seed = _bracket_repo(tmp_path / "ranges")
        _stage(repo, "ab.py", seed + "A = 1\nB = 2\nimport sys\n")
        _stage(repo, BRACKET_NAME, seed + "import json\n")

        ranges = precommit_gate.parse_added_ranges(
            precommit_gate.staged_diff(repo, BRACKET_NAME)
        )

        assert ranges == [(3, 3)], (
            "the added ranges are not this file's alone - a foreign hunk "
            f"header was parsed as if it belonged here: {ranges}"
        )

    def test_the_gate_does_not_blame_a_bracketed_file_for_a_neighbours_line(
        self, tmp_path
    ):
        """The consumer's answer, not just the helper's.

        ``a[b].py`` carries a PRE-EXISTING unused ``os`` on line 1 that this
        commit does not touch, and ``ab.py`` adds a line at that same number.
        Union the two range sets and the gate blocks ``a[b].py`` for a finding
        it did not add.

        THE ASSERTION IS ON THE MESSAGE, NOT THE PATH, and deliberately so.
        ruff glob-expands its own ``--stdin-filename`` when a matching file
        exists on disk, so it reports this file's findings under the name
        ``ab.py``; a path assertion here would be satisfied by that mangling
        rather than by the fix, which is exactly a test passing for the wrong
        reason. ``os`` and ``sys`` are unique to one file each, so the message
        says which file a finding really came from.
        """
        repo = _make_repo(tmp_path / "consumer", hooked=False)
        _seed(repo, "ab.py", "VALUE = 1\n")
        _seed(repo, BRACKET_NAME, "import os\nVALUE = 1\n")
        _stage(repo, "ab.py", "import sys\nVALUE = 1\n")
        _stage(repo, BRACKET_NAME, "import os\nVALUE = 1\nOTHER = 2\n")

        findings = precommit_gate.lint_staged(repo)

        assert any("sys" in f.message for f in findings), (
            "the control is gone - ab.py really does add an unused `sys` on "
            f"an added line and the gate must still catch it: {findings}"
        )
        assert not any("os" in f.message for f in findings), (
            "a[b].py was blamed for its pre-existing line 1, which only ab.py "
            f"added: {findings}"
        )

    def test_both_pathspecs_of_a_rename_are_passed_literally(self, monkeypatch):
        """Argument level, because the origin cannot misfire with real files.

        Covers the metacharacters NTFS forbids as well - the pathspec is a
        string handed to git, so a name this filesystem cannot hold is still
        worth pinning at the boundary where the string is built.
        """
        seen: list[tuple[str, ...]] = []

        def _capture(repo, *args: str) -> str:
            seen.append(args)
            return ""

        monkeypatch.setattr(precommit_gate, "_git_stdout", _capture)
        precommit_gate.staged_diff(Path(), "new[1].py", "old*.py")

        assert len(seen) == 1, seen
        args = seen[0]
        assert "--" in args, args
        pathspecs = list(args[args.index("--") + 1 :])
        assert pathspecs == [":(literal)old*.py", ":(literal)new[1].py"], pathspecs

    def test_the_single_path_branch_is_passed_literally(self, monkeypatch):
        seen: list[tuple[str, ...]] = []

        def _capture(repo, *args: str) -> str:
            seen.append(args)
            return ""

        monkeypatch.setattr(precommit_gate, "_git_stdout", _capture)
        precommit_gate.staged_diff(Path(), "solo[0-9].py")

        assert len(seen) == 1, seen
        args = seen[0]
        pathspecs = list(args[args.index("--") + 1 :])
        assert pathspecs == [":(literal)solo[0-9].py"], pathspecs


# ---------------------------------------------------------------------------
# ROADMAP OPS-55 - ruff glob-expands the filenames it is handed.
# ---------------------------------------------------------------------------

#: The ruff release the behaviour below was measured against, recorded rather
#: than asserted so a future ruff that CHANGES it is reported with the version
#: that was true when the fix was written. The measurement itself is re-derived
#: at run time by :class:`TestRuffGlobExpandsTheFilenamesItIsHanded`; this
#: string only makes the failure message useful.
RUFF_VERSION_MEASURED = "ruff 0.15.12"

#: The stdin payload used by the direct-ruff probes: exactly one F401.
ONE_UNUSED_IMPORT = "import os\n"

#: What the staged commits below ADD at the top of an existing file: one
#: unused import plus the blank line isort insists on, so the only finding is
#: the F401 these tests are actually about and not an incidental I001.
STAGED_ADDITION = "import os\n\nVALUE = 1\n"


def _ruff_version() -> str:
    command = precommit_gate.ruff_command()
    assert command is not None, "the autouse fixture should have skipped"
    probe = subprocess.run(
        [*command, "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return probe.stdout.strip()


def _ruff_reported_filename(cwd: Path, stdin_filename: str) -> str:
    """Ask ruff about ``stdin_filename`` from ``cwd``; return the name it says.

    ``--isolated`` and an explicit ``--select`` so the answer depends on the
    working directory's FILES and on nothing that a stray ``ruff.toml`` above
    ``tmp_path`` could contribute.
    """
    command = precommit_gate.ruff_command()
    assert command is not None
    result = subprocess.run(
        [
            *command,
            "check",
            "--no-cache",
            "--isolated",
            "--select",
            "F401",
            "--output-format",
            "json",
            "--stdin-filename",
            stdin_filename,
            "-",
        ],
        cwd=cwd,
        input=ONE_UNUSED_IMPORT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    payload = json.loads(result.stdout or "[]")
    assert len(payload) == 1, (
        "the probe payload no longer produces exactly one finding, so nothing "
        f"below is measuring what it claims: {result.stdout}\n{result.stderr}"
    )
    return Path(payload[0]["filename"]).name


class TestRuffGlobExpandsTheFilenamesItIsHanded:
    """The third-party behaviour, re-derived here instead of trusted.

    ``ruff check --stdin-filename <name>`` treats ``<name>`` as a GLOB. The
    payload on stdin is unchanged between the two probes below and only the
    contents of the working directory differ, so a difference in the reported
    name can come from nothing else.

    THIS TEST IS A TRIPWIRE IN BOTH DIRECTIONS, which is the point. If ruff
    stops mangling the name, this fails and says so - a fix that has silently
    stopped being needed is as much a problem as one that has stopped working,
    because the next reader cannot tell the two apart from a green suite.
    """

    def test_a_bracket_name_is_reported_as_its_glob_neighbour(self, tmp_path):
        near = tmp_path / "with_neighbour"
        near.mkdir()
        (near / "ab.py").write_text("VALUE = 1\n", encoding="ascii", newline="\n")

        reported = _ruff_reported_filename(near, BRACKET_NAME)

        assert reported == "ab.py", (
            f"{_ruff_version()} no longer glob-expands --stdin-filename "
            f"(measured against {RUFF_VERSION_MEASURED}, where it reported "
            f"'ab.py' here). It reported {reported!r}. Re-read ROADMAP OPS-55 "
            "and decide whether the fix in ruff_findings is still earning its "
            "place before deleting this test."
        )

    def test_the_same_name_is_reported_intact_with_no_neighbour_on_disk(
        self, tmp_path
    ):
        """The control that makes the probe above mean something.

        Nothing about the stdin payload or the argument changes between these
        two cases. Without this one, a reported ``ab.py`` could just as well be
        ruff ignoring the argument altogether.
        """
        far = tmp_path / "no_neighbour"
        far.mkdir()

        reported = _ruff_reported_filename(far, BRACKET_NAME)

        assert reported == BRACKET_NAME, (
            f"{_ruff_version()} did not report the name it was handed even "
            f"with no file for it to expand onto: {reported!r}"
        )


class TestABracketedFilesFindingIsAttributedToThatFile:
    """``ruff_findings`` must not label a finding with ruff's reported name.

    The whole trigger is the glob NEIGHBOUR being on disk, so every case here
    is paired with the same case without it. ``ab.py`` is seeded but never
    STAGED, which makes the defect loud rather than merely wrong: the gate
    blocks on a path the commit does not touch at all.
    """

    def test_the_gate_blocks_on_the_bracketed_path_and_not_its_neighbour(
        self, tmp_path
    ):
        repo = _make_repo(tmp_path / "attribution", hooked=False)
        _seed(repo, "ab.py", "VALUE = 1\n")
        _seed(repo, BRACKET_NAME, "VALUE = 1\n")
        _stage(repo, BRACKET_NAME, STAGED_ADDITION)

        findings = precommit_gate.lint_staged(repo)

        assert [f.code for f in findings] == ["F401"], (
            "the control is gone - the staged added line really does carry one "
            f"unused import and nothing else: {findings}"
        )
        assert any("os" in f.message for f in findings), (
            f"the finding is not the one this test staged: {findings}"
        )
        assert {f.path for f in findings} == {BRACKET_NAME}, (
            "the finding was attributed to a file this commit never staged. "
            "ruff glob-expanded the --stdin-filename it was handed and the "
            f"gate believed the name it got back: {findings}"
        )

    def test_the_answer_is_the_same_with_no_glob_neighbour_present(self, tmp_path):
        """The input mutant. Identical staging, no ``ab.py`` anywhere.

        This case is green with or without the fix, and that is what it is for:
        it pins the neighbour's PRESENCE as the trigger, so the case above
        cannot be explained by anything else the repository does.
        """
        repo = _make_repo(tmp_path / "attribution_alone", hooked=False)
        _seed(repo, BRACKET_NAME, "VALUE = 1\n")
        _stage(repo, BRACKET_NAME, STAGED_ADDITION)

        findings = precommit_gate.lint_staged(repo)

        assert [f.code for f in findings] == ["F401"], findings
        assert {f.path for f in findings} == {BRACKET_NAME}, findings

    def test_a_real_refusal_names_the_bracketed_file_and_not_its_neighbour(
        self, tmp_path
    ):
        """End to end, because the reported name is what the operator READS.

        ``CLAUDE.md`` is explicit that only an end-to-end attempt proves a hook
        fired, and the mis-attribution's whole damage is in the text a person
        is shown when the commit is refused. ``ab.py`` is committed clean
        through the hook first, so it exists on disk for ruff to expand onto
        while being nothing this commit touches.
        """
        repo, before = _hooked_repo(tmp_path)
        _stage(repo, "ab.py", "VALUE = 1\n")
        clean = _git(repo, "commit", "-m", "probe: the glob neighbour")
        assert clean.returncode == 0, (
            f"the neighbour itself was refused.\n{clean.stdout}\n{clean.stderr}"
        )
        before = _head(repo)
        _stage(repo, BRACKET_NAME, STAGED_ADDITION)

        result = _git(repo, "commit", "-m", "probe: must be refused")

        assert _head(repo) == before, "the violating commit landed"
        combined = result.stdout + result.stderr
        assert "F401" in combined, f"refused by something other than lint:\n{combined}"
        assert BRACKET_NAME in combined, (
            "the refusal does not name the file that actually violates - the "
            f"operator is told to look somewhere else:\n{combined}"
        )
        assert "ab.py" not in combined.replace(BRACKET_NAME, ""), (
            "the refusal names a file this commit never staged, because ruff "
            f"glob-expanded the name it was handed:\n{combined}"
        )

    def test_ruff_findings_labels_with_the_path_it_was_asked_about(self, tmp_path):
        """The unit-level statement, one layer under the consumer above."""
        repo = _make_repo(tmp_path / "unit", hooked=False)
        _write(repo, "ab.py", "VALUE = 1\n")

        findings = precommit_gate.ruff_findings(repo, BRACKET_NAME, ONE_UNUSED_IMPORT)

        assert [f.path for f in findings] == [BRACKET_NAME], (
            f"ruff_findings returned ruff's reported name, not the asked path: "
            f"{findings}"
        )


class TestEveryFilenameHandedToAnExternalTool:
    """ROADMAP OPS-55 criterion 5 - the sweep, pinned rather than described.

    ``tools/precommit_gate.py`` starts four external processes. Two of them
    (``git diff --cached --name-only`` and ``ruff --version``) are handed no
    filename at all. The remaining argument-carrying sites are covered here
    and by ``TestAFilenameCarryingPathspecMetacharacters`` above:

    * ``staged_diff`` pathspecs - FIXED under ``OPS-39`` with ``:(literal)``.
    * ``staged_source``'s ``git show :<path>`` - CONFIRMED glob-safe below.
    * ``ruff --stdin-filename`` - FIXED, see the class above.
    * ``ruff --config`` - FIXED below, and this one was not label-only.
    """

    def test_git_show_reads_a_bracketed_index_path_literally(self, tmp_path):
        """``:<path>`` is an object name, not a pathspec. Characterization.

        Recorded because "git took a filename" was the whole of ``OPS-39`` and
        an unmeasured assumption that this second git site behaves differently
        is exactly the kind of thing this project gets wrong. It does behave
        differently, and here is the evidence rather than the assertion.
        """
        repo = _make_repo(tmp_path / "show", hooked=False)
        _seed(repo, "ab.py", "NEIGHBOUR = 1\n")
        _seed(repo, BRACKET_NAME, "BRACKET = 2\n")

        bracket = precommit_gate.staged_source(repo, BRACKET_NAME)
        neighbour = precommit_gate.staged_source(repo, "ab.py")

        assert bracket is not None and neighbour is not None
        assert "BRACKET = 2" in bracket and "NEIGHBOUR" not in bracket, bracket
        assert "NEIGHBOUR = 1" in neighbour and "BRACKET" not in neighbour, neighbour

    def test_a_bracketed_repository_root_does_not_swap_the_ruff_config(
        self, tmp_path
    ):
        """The loud one: ``--config`` glob expansion changes the RULESET.

        Unlike ``--stdin-filename``, this is not a mislabelled finding. The
        neighbour directory ``rx`` holds a ruff.toml selecting NOTHING, so a
        gate that hands ruff an absolute ``<root>/ruff.toml`` from a root named
        ``r[x]`` lints the staged file against the wrong configuration and
        reports it clean. That is a guard that did not run, reporting a pass.
        """
        neighbour = tmp_path / "rx"
        neighbour.mkdir(parents=True)
        (neighbour / "ruff.toml").write_text(
            "[lint]\nselect = []\n", encoding="ascii", newline="\n"
        )
        repo = _make_repo(tmp_path / "r[x]", hooked=False)
        (repo / "ruff.toml").write_text(
            '[lint]\nselect = ["F401"]\n', encoding="ascii", newline="\n"
        )
        _seed(repo, "mod.py", "VALUE = 1\n")
        _stage(repo, "mod.py", STAGED_ADDITION)

        findings = precommit_gate.lint_staged(repo)

        assert [f.code for f in findings] == ["F401"], (
            "the gate linted against the neighbour directory's permissive "
            "ruff.toml, so a real violation on an added line was reported "
            f"clean: {findings}"
        )

    def test_the_ruff_arguments_carry_no_glob_metacharacter(
        self, tmp_path, monkeypatch
    ):
        """Argument level, because a behavioural test cannot see the shape.

        The repository root here carries brackets on purpose: an absolute
        ``--config`` would drag them into the argument, and asserting on a
        root without them would pass whatever the code did.
        """
        repo = _make_repo(tmp_path / "a[r]gs", hooked=False)
        seen: dict[str, object] = {}

        class _Result:
            returncode = 0
            stdout = "[]"
            stderr = ""

        def _capture(args, **kwargs):
            seen["args"] = list(args)
            seen["cwd"] = kwargs.get("cwd")
            return _Result()

        monkeypatch.setattr(precommit_gate.subprocess, "run", _capture)
        precommit_gate.ruff_findings(repo, BRACKET_NAME, ONE_UNUSED_IMPORT)

        args = seen["args"]
        assert args[args.index("--stdin-filename") + 1] == BRACKET_NAME, args
        config = args[args.index("--config") + 1]
        assert not set("[]*?") & set(config), (
            "the --config argument carries a glob metacharacter from the "
            f"repository root, and ruff expands it: {config!r}"
        )
        assert seen["cwd"] == repo, (
            "a relative --config is only meaningful with the working "
            f"directory pinned to the repository: {seen['cwd']!r}"
        )


# ---------------------------------------------------------------------------
# argv - OPS-66. An argument this entry point does not understand must REFUSE
# ---------------------------------------------------------------------------


class TestUnrecognisedArgvIsRefused:
    """A typo in the invocation must not read as a pass.

    FOUND BY `OPS-64`'S SWEEP, 2026-09-08, and measured before it was fixed:
    ``python tools/precommit_gate.py --lintstaged`` exited 0 and printed
    nothing. The real invocation, ``lint-staged``, also exits 0 on a clean
    repository, so the two were indistinguishable by the only thing a git hook
    reads - the exit code.

    ``.githooks/pre-commit`` invokes this module as
    ``precommit_gate.py lint-staged``. A one-character slip in that line
    therefore turned the lint gate off and reported success, and nothing
    anywhere would have said so. That is the same shape as the pre-commit hook
    that ran the WRONG test module while reporting the guard had run, and as
    the archive link guard that answered a question nobody asked - a true
    verdict about something other than what was requested.

    Why this is a refusal and not a soft pass: every other path in this module
    exists to refuse. A gate that cannot tell "I checked and it is clean" from
    "I did not understand you" has no verdict to give, and the failure direction
    for an unreadable request is REFUSE.
    """

    def test_an_unknown_flag_is_refused_in_process(self) -> None:
        assert precommit_gate.dispatch(["--lintstaged"]) != 0

    def test_the_refusal_names_the_argument_it_did_not_understand(self, capsys) -> None:
        precommit_gate.dispatch(["--lintstaged"])
        assert "--lintstaged" in capsys.readouterr().err

    def test_a_trailing_extra_argument_is_refused_too(self) -> None:
        """``lint-staged`` plus junk is a request nobody meant to make."""
        assert precommit_gate.dispatch(["lint-staged", "--nope"]) != 0

    def test_both_spellings_of_the_real_entry_point_still_dispatch(self, tmp_path) -> None:
        """The positive control. Without it, refusing EVERYTHING would pass."""
        _toolguard.require("git")
        for spelling in sorted(precommit_gate._LINT_ARGV):
            result = subprocess.run(
                [sys.executable, str(GATE_SOURCE), spelling],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
            )
            assert result.returncode == 0, (spelling, result.stderr)

    def test_no_argv_still_reaches_the_pretooluse_stdin_path(self) -> None:
        """The hook passes NO argument, and that path must be untouched.

        Run as a subprocess with empty stdin, which is the shape a PreToolUse
        hook sees when the payload is unreadable: the gate permits, exit 0.
        """
        result = subprocess.run(
            [sys.executable, str(GATE_SOURCE)],
            cwd=str(REPO_ROOT),
            input="",
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr

    def test_an_unknown_flag_is_refused_end_to_end(self) -> None:
        """The exit code is the whole verdict, so measure the real process."""
        result = subprocess.run(
            [sys.executable, str(GATE_SOURCE), "--lintstaged"],
            cwd=str(REPO_ROOT),
            input="",
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode != 0, (
            "an unrecognised argument exited 0, which a git hook reads as a pass "
            f"and a PreToolUse hook reads as permission: {result.stdout!r}"
        )
        assert "--lintstaged" in result.stderr, result.stderr
