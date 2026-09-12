"""The pre-commit hook must not let the shell rewrite a path - ``OPS-56``.

Two defects, both found by an enumeration sweep and both reproduced here
END TO END through a real ``git commit`` in a throwaway repository wired to the
REAL ``.githooks/pre-commit``. A string assertion against the hook's source
would pass against a hook that carries the fix only in a comment, so the
assertions that matter below are about what the hook DID, and what HEAD did
afterwards. The text assertions at the bottom are carried as well, never
instead.

DEFECT 1 - the doc guard's pathspec. ``git diff --name-only -- "$doc"`` takes a
BARE pathspec, and a bare pathspec is a wildmatch glob. ``$doc`` is a real
staged Markdown filename, so a document named ``docs/N[O]TE.md`` is compared
against every path matching that pattern - which is ``docs/NOTE.md`` and not
itself. Measured 2026-09-08 before the fix: with the bracket document staged
and IDENTICAL to the working tree, and its glob neighbour edited in the working
tree only, the hook printed ``BLOCKED docs/N[O]TE.md ... differs from the
working tree`` and HEAD did not move. An OVER-match, so it is loud - a false
refusal of a document that is perfectly clean, blamed on a file the operator
did not touch.

DEFECT 2 - the subset run's word split, and this is the one that matters.
``exec "$py_bin" -m pytest $selected`` is unquoted on purpose so the selector's
newline-separated module list splits into several arguments. Globbing, however,
is ON at that point: ``set -f`` is set for the staged-path loop and cleared
again before the doc guard runs, and nothing re-set it. So a selected module
named ``tests/test_a[b].py`` is replaced by whatever matches the pattern.
Measured 2026-09-08 before the fix, in the probe below: the selector chose
``tests/test_a[b].py``, the hook announced ``running 1 doc-reading test
module(s)``, pytest ran ``tests/test_ab.py`` - a DIFFERENT module that reads no
document at all - it passed, and THE COMMIT LANDED. A guard that runs the wrong
thing and then reports that it ran is the exact failure this project's
verification discipline exists to prevent, and nothing about it is visible in
an exit code.

WHAT THE FIX CAN AND CANNOT BUY, written down because a caveat dropped from the
artifact is a lie in the artifact. Measured here: pytest REFUSES a path
argument containing brackets - ``ERROR: path cannot contain [] parametrization:
tests/test_a[b].py`` - so with globbing disabled a bracket-named test module
that reads a staged document cannot be run at all, and the commit is REFUSED
rather than passed. That is the right outcome and it is not a clean one: the
fix converts a silent wrong-module success into a loud refusal, it does not
make such a module runnable. Nobody has yet needed one; this suite is the
record that they cannot have one without further work.

Both defects are LATENT in this repository today - ``git ls-files | grep -c
"\\["`` is 0 against a control of 174 for a dot - so every input below is built
inside the test rather than borrowed from the tree.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _toolguard  # noqa: E402

from ops import docguards  # noqa: E402

HOOK = REPO_ROOT / ".githooks" / "pre-commit"

#: A module name whose glob pattern matches a DIFFERENT existing file. The
#: bracket expression ``[b]`` matches the single character ``b``, so this
#: pattern matches ``tests/test_ab.py`` and does not match itself.
BRACKET_MOD = "tests/test_a[b].py"
NEIGHBOUR_MOD = "tests/test_ab.py"
BRACKET_DOC = "docs/N[O]TE.md"
NEIGHBOUR_DOC = "docs/NOTE.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_toolguard.require("git"), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=300,
        check=False,
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _commit_with_the_hook_disarmed(repo: Path, message: str) -> None:
    """Land a SETUP commit with no hook running, and say why in one place.

    Setup here has to plant a document that the guard under test would judge,
    and a fixture that depends on the guard it is about to measure proves
    nothing in either direction. It is also not always possible: pytest refuses
    a path argument containing brackets, so once globbing is disabled a
    bracket-named selected module cannot run at all and a hook-armed setup
    commit would be refused before any test made an assertion. Empty
    ``core.hooksPath`` for this ONE commit is the house pattern -
    ``tests/test_docguards.py`` uses the same idiom for the same reason.
    """
    landed = _git(repo, "-c", "core.hooksPath=", "commit", "-q", "-m", message)
    assert landed.returncode == 0, f"the setup commit failed.\n{_blob(landed)}"


def _blob(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr


def _probe_repo(
    tmp_path: Path,
    *,
    doc: str,
    modules: dict[str, str],
    reading: dict[str, str],
) -> Path:
    """A throwaway repository carrying the real hook and the real selector.

    Args:
        tmp_path: The pytest temporary directory to build under.
        doc: The document the observed map records as read.
        modules: Test module path -> its source text.
        reading: The subset of ``modules`` the observed map names, module path
            -> the document it reads.

    Nothing Markdown is in the seed commit: staging a ``.md`` is what arms the
    doc guard, and the seed must land unconditionally or every refusal measured
    afterwards would be meaningless.
    """
    # OPS-83. This helper copies the REAL hook directory in and points
    # `core.hooksPath` at it below, so every caller runs a `#!/bin/sh` hook
    # whose body calls grep, head, tr and wc. Without that POSIX userland on
    # PATH git cannot spawn the hook and these cases go red naming nothing.
    # Skip here, naming the missing members. The PRESENT direction is pinned by
    # the seed commit at the end of this function, which runs the real hook.
    _toolguard.require_posix_userland()
    repo = tmp_path / "probe"
    (repo / "ops").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    shutil.copytree(HOOK.parent, repo / ".githooks")
    shutil.copy2(REPO_ROOT / "ops" / "docguards.py", repo / "ops" / "docguards.py")
    for name, source in modules.items():
        (repo / name).write_text(source, encoding="ascii")
    (repo / "seed.txt").write_text("seed\n", encoding="ascii")

    assert _git(repo, "init", "-q").returncode == 0
    for key, value in (
        ("user.email", "probe@example.invalid"),
        ("user.name", "hook probe"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", (repo / ".githooks").as_posix()),
    ):
        assert _git(repo, "config", key, value).returncode == 0
    assert _git(repo, "add", "-A").returncode == 0
    seeded = _git(repo, "commit", "-m", "probe: seed")
    assert seeded.returncode == 0, (
        "the hook refused a commit carrying no Markdown, so every refusal "
        f"measured below would prove nothing.\n{_blob(seeded)}"
    )

    docguards.write_observed(
        {
            "complete": True,
            "exitstatus": 0,
            "args": ["tests"],
            "root": str(repo.resolve()),
            "modules": {name: [read] for name, read in reading.items()},
            "modules_run": sorted(reading),
            "test_module_digests": docguards.test_module_digests(repo),
        },
        repo,
    )
    assert doc  # named for the reader; the map above is what the hook consults
    return repo


def _reader_source(doc: str) -> str:
    """A test module that asserts on a document's CONTENT.

    The shape of ``tests/test_source_register.py``, and the shape that reddened
    three commits before ``OPS-31`` existed.
    """
    return (
        "from pathlib import Path\n\n\n"
        "def test_the_note_is_registered():\n"
        f'    text = Path("{doc}").read_text(encoding="ascii")\n'
        '    assert "REGISTERED" in text\n'
    )


PASSING_SOURCE = "def test_it_passes():\n    assert True\n"


class TestABracketNamedDocumentIsComparedToItself:
    """DEFECT 1. The doc guard asks whether the STAGED document differs from
    the working-tree copy. A bare pathspec asks a wider question than that."""

    def _repo(self, tmp_path: Path) -> Path:
        repo = _probe_repo(
            tmp_path,
            doc=BRACKET_DOC,
            modules={"tests/test_probe.py": _reader_source(BRACKET_DOC)},
            reading={"tests/test_probe.py": BRACKET_DOC},
        )
        (repo / BRACKET_DOC).write_text("# bracket REGISTERED\n", encoding="ascii")
        (repo / NEIGHBOUR_DOC).write_text("# neighbour\n", encoding="ascii")
        assert _git(repo, "add", "-A").returncode == 0
        landed = _git(repo, "commit", "-m", "probe: both documents")
        assert landed.returncode == 0, (
            f"the hook refused the setup commit.\n{_blob(landed)}"
        )
        return repo

    def test_a_clean_bracket_doc_is_not_blamed_for_its_glob_neighbour(self, tmp_path):
        """The defect, end to end. The staged document is byte-identical to the
        working tree; only the neighbour differs, and the neighbour is not
        staged at all."""
        repo = self._repo(tmp_path)
        before = _head(repo)
        (repo / BRACKET_DOC).write_text("# bracket REGISTERED, edited\n", encoding="ascii")
        assert _git(repo, "add", BRACKET_DOC).returncode == 0
        (repo / NEIGHBOUR_DOC).write_text(
            "# neighbour, edited in the working tree only\n", encoding="ascii"
        )
        result = _git(repo, "commit", "-m", "probe: bracket document, staged clean")
        after = _head(repo)
        assert "differs from the working tree" not in _blob(result), (
            "the doc guard blamed a clean staged document for a DIFFERENT file "
            "that differs - a bare pathspec is a glob, so the comparison was "
            f"never about this document.\n{_blob(result)}"
        )
        assert result.returncode == 0, (
            f"a clean bracket-named document was refused.\n{_blob(result)}"
        )
        assert after != before, f"HEAD did not move from {before[:8]}"

    def test_a_bracket_doc_that_really_differs_is_still_refused(self, tmp_path):
        """The non-vacuity half. A pathspec fix that matched NOTHING would pass
        the test above and silently switch guard (a) off for every bracket-named
        document. Here the staged copy genuinely differs from the working tree,
        and the refusal must name this document."""
        repo = self._repo(tmp_path)
        before = _head(repo)
        (repo / BRACKET_DOC).write_text("# bracket REGISTERED, staged\n", encoding="ascii")
        assert _git(repo, "add", BRACKET_DOC).returncode == 0
        (repo / BRACKET_DOC).write_text(
            "# bracket REGISTERED, working tree, different\n", encoding="ascii"
        )
        result = _git(repo, "commit", "-m", "probe: bracket document really differs")
        after = _head(repo)
        assert result.returncode != 0, (
            "a staged document differing from the working tree LANDED - the "
            f"guard is off for bracket-named paths.\n{_blob(result)}"
        )
        assert after == before, f"HEAD moved {before[:8]} -> {after[:8]}"
        assert BRACKET_DOC in _blob(result), (
            f"the refusal does not name the document.\n{_blob(result)}"
        )


class TestTheSelectedModuleIsTheOneThatRuns:
    """DEFECT 2, the silent one. The selector's answer must reach pytest
    unrewritten, and it must still split into separate arguments."""

    def _repo(self, tmp_path: Path, *, neighbour: bool) -> Path:
        modules = {BRACKET_MOD: _reader_source(NEIGHBOUR_DOC)}
        if neighbour:
            # Reads no document, so the selector never picks it. If the hook
            # globs, this is what runs in place of the module that does.
            modules[NEIGHBOUR_MOD] = PASSING_SOURCE
        repo = _probe_repo(
            tmp_path,
            doc=NEIGHBOUR_DOC,
            modules=modules,
            reading={BRACKET_MOD: NEIGHBOUR_DOC},
        )
        (repo / NEIGHBOUR_DOC).write_text("# note REGISTERED\n", encoding="ascii")
        assert _git(repo, "add", NEIGHBOUR_DOC).returncode == 0
        _commit_with_the_hook_disarmed(repo, "probe: clean note")
        return repo

    def test_the_glob_neighbour_never_runs_in_place_of_the_selected_module(self, tmp_path):
        """Prose that reddens the SELECTED module is staged. Before the fix the
        hook ran ``tests/test_ab.py`` instead, it passed, and the commit landed
        while the hook printed that it had run a doc-reading module."""
        repo = self._repo(tmp_path, neighbour=True)
        before = _head(repo)
        (repo / NEIGHBOUR_DOC).write_text("# note, token removed\n", encoding="ascii")
        assert _git(repo, "add", NEIGHBOUR_DOC).returncode == 0
        result = _git(repo, "commit", "-m", "probe: prose that reddens the selected module")
        after = _head(repo)
        blob = _blob(result)
        assert NEIGHBOUR_MOD.replace("/", "\\") not in blob and NEIGHBOUR_MOD not in blob, (
            "pytest ran the SELECTED module's glob neighbour - a module that "
            "reads no document - and the hook reported that the doc-reading "
            f"subset had run.\n{blob}"
        )
        assert result.returncode != 0, (
            "prose that reddens the selected doc-reading module LANDED.\n" + blob
        )
        assert after == before, f"HEAD moved {before[:8]} -> {after[:8]}"

    def test_the_same_input_without_a_neighbour_is_refused_too(self, tmp_path):
        """A control, and it discriminates nothing on its own - it is refused
        both before and after the fix, because with no file to match the
        pattern the shell leaves it alone. It is here to pin WHICH input makes
        the defect appear: the neighbour, not the brackets."""
        repo = self._repo(tmp_path, neighbour=False)
        before = _head(repo)
        (repo / NEIGHBOUR_DOC).write_text("# note, token removed\n", encoding="ascii")
        assert _git(repo, "add", NEIGHBOUR_DOC).returncode == 0
        result = _git(repo, "commit", "-m", "probe: no neighbour to match")
        assert result.returncode != 0, (
            f"the commit landed with no doc-reading module run.\n{_blob(result)}"
        )
        assert _head(repo) == before

    def test_several_selected_modules_still_reach_pytest_as_several_arguments(self, tmp_path):
        """The word split is deliberate and must survive the fix.

        Quoting ``"$selected"`` disables the glob and breaks this: pytest is
        handed one argument containing a newline, no such path exists, and the
        commit is refused for a reason that has nothing to do with the prose.
        Two ordinary modules, both reading the document, both passing.
        """
        repo = _probe_repo(
            tmp_path,
            doc=NEIGHBOUR_DOC,
            modules={
                "tests/test_one.py": _reader_source(NEIGHBOUR_DOC),
                "tests/test_two.py": _reader_source(NEIGHBOUR_DOC),
            },
            reading={
                "tests/test_one.py": NEIGHBOUR_DOC,
                "tests/test_two.py": NEIGHBOUR_DOC,
            },
        )
        before = _head(repo)
        (repo / NEIGHBOUR_DOC).write_text("# note REGISTERED\n", encoding="ascii")
        assert _git(repo, "add", NEIGHBOUR_DOC).returncode == 0
        result = _git(repo, "commit", "-m", "probe: two selected modules")
        blob = _blob(result)
        assert result.returncode == 0, (
            f"two selected modules were not run as two arguments.\n{blob}"
        )
        assert _head(repo) != before
        assert "2 passed" in blob, (
            "the hook did not run both selected modules, so the word split no "
            f"longer happens.\n{blob}"
        )


class TestTheHookSourceCarriesTheFix:
    """Text assertions, carried AS WELL AS the behavioural ones above. On their
    own they would pass against a hook that has the strings in a comment, which
    is why they are last and why nothing here is the reason to believe the
    fix."""

    def test_the_doc_guard_uses_a_literal_pathspec(self):
        text = HOOK.read_text(encoding="ascii")
        line = [one for one in text.splitlines() if "git diff --name-only" in one]
        assert len(line) == 1, f"expected exactly one doc-guard diff line, got {line}"
        assert ":(literal)" in line[0], (
            f"the doc guard still takes a bare pathspec, which is a glob: {line[0]}"
        )

    def test_the_subset_run_disables_globbing_around_the_split(self):
        text = HOOK.read_text(encoding="ascii")
        # Anchor on the exec, not on "-m pytest": the prose above it mentions
        # `python -m pytest` and a str.find would land in the comment.
        assert text.count("exec ") == 1, "expected exactly one exec in the hook"
        marker = text.find("exec ")
        window = text[max(0, marker - 400) : marker]
        assert "set -f" in window, (
            "nothing disables globbing before the selector's answer is split, "
            "so a selected path is whatever the working directory matches"
        )

    def test_the_hook_has_no_carriage_returns(self):
        """Git for Windows chokes on a CR in the shebang, and this file was
        edited on Windows."""
        assert b"\r" not in HOOK.read_bytes(), "the pre-commit hook contains a CR"


@pytest.mark.parametrize("path", [BRACKET_MOD, BRACKET_DOC])
def test_the_probe_inputs_do_not_exist_in_this_repository(path):
    """Both defects are latent here. If a bracket-named path is ever tracked,
    this fails and says so, because at that point the defects stop being
    hypothetical and the tests above stop being the only place they appear."""
    assert not (REPO_ROOT / path).exists(), (
        f"{path} now exists in the working tree - re-read OPS-56 before "
        "assuming the hook's glob behaviour is still latent"
    )
