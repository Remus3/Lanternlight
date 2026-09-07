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

Every git repository here is a throwaway under ``tmp_path``. Nothing in this
module touches this repository's own index.
"""

from __future__ import annotations

import os
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
