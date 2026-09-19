"""No EMPTY untracked, unignored directory may sit in this tree - ``OPS-96``.

WHY THIS FILE EXISTS, AND WHY IT IS NOT REDUNDANT WITH THE OTHER GUARDS
----------------------------------------------------------------------
The machine-wide stray-work sweep on 2026-09-19 found two of these, and the
finding was not that they were harmful - both were 0 files and 0 bytes - but
that FOUR of the five commands a sweep runs cannot see them at all:

* ``git status --ignored --porcelain`` does not list them.
* ``git status --porcelain --untracked-files=all <path>`` returns nothing.
* ``git check-ignore -v <path>`` exits 1 saying only that no rule matches, which
  is a statement about ``.gitignore`` and not about the tree.
* a plain ``os.walk`` looking for files finds nothing, because there are none.

Only ``git ls-files --others --directory`` reports them, because **git does not
report empty directories** anywhere else. That is a reporting rule, not a fact
about the repository, and this repository already has a name for the mistake: an
empty grep is a claim about your pattern. A clean ``git status --ignored`` is a
claim about git's output policy.

AND THE COMMAND USUALLY RECOMMENDED FOR THIS MISSES ONE OF THE TWO. Measured on
2026-09-19 with both orphans present:

* ``git ls-files --others --exclude-standard --directory`` reported
  ``.backtest/`` and NOT ``.claude/worktrees/``.
* the same command WITHOUT ``--exclude-standard`` reported both.
* the same command scoped with ``-- .claude`` reported NOTHING, while
  ``pathlib`` confirmed the directory existed and was empty.

So the enumeration used here is ``--others --directory`` with ``.gitignore``
applied afterwards by :func:`_is_ignored`, rather than ``--exclude-standard``
applied during the walk. The reason for not reverse-engineering git's collapse
rule and relying on it: the FIX for one of these orphans is a ``.gitignore``
rule, so the guard has to answer "is this ignored" with a question about the
specific path and not with a flag whose behaviour differs between a top-level
and a nested empty directory. This paragraph is the measurement, not a theory
about ``dir.c``.

WHAT WAS ACTUALLY AT RISK, which is why this is a guard and not a tidy-up
------------------------------------------------------------------------
``.claude/worktrees/`` was the dangerous one. ``.claude/`` is DELIBERATELY
TRACKED in this repository, unlike in the sibling projects on this machine,
because the governance in it is the point of the repo being reproducible. That
directory matched no ``.gitignore`` rule, so the first file a session wrote into
it would have been an untracked orphan with no owning lane - the exact condition
``tests/test_lanes.py`` fails on - and it would have been a worktree's entire
contents sitting one ``git add -A`` from publication in a PUBLIC repo. It is now
ignored by name, with the reason written at the rule.

``.backtest/`` was the leftover staging root of this project's own back-test of
whether a git hook could replace the in-session pre-flight, recorded in
``docs/CYCLE_COST.md``. It is deliberately NOT ignored: if it comes back, that
means the back-test was re-run and left its staging behind again, and this guard
is the thing that says so.

WHY THE CHECK IS SCOPED TO *EMPTY* DIRECTORIES
----------------------------------------------
``git ls-files --others --directory`` also reports a
directory full of brand-new unstaged work, and failing on that would make this
guard a false red every time anybody creates a module before staging it - which
is the one failure mode that gets a guard deleted rather than fixed. This
repository's pre-flight already warns about unstaged new files at a moment a
slice can act on them. An EMPTY untracked directory, by contrast, is never
work-in-progress: there is nothing in it to stage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _untracked_directory_entries(root: Path = REPO_ROOT) -> list[str]:
    """Every untracked, unignored entry git collapses to a directory.

    ``--directory`` is what makes an empty one visible at all.
    ``--exclude-standard`` is deliberately NOT passed - see the module
    docstring for the measurement that rules it out - so every ignored cache
    comes back here and is filtered by :func:`_is_ignored` afterwards.
    """
    completed = subprocess.run(
        ["git", "ls-files", "--others", "--directory"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line.endswith("/")]


def _is_ignored(relative: str, root: Path = REPO_ROOT) -> bool:
    """True when ``.gitignore`` covers ``relative``.

    Asked per path, and asked AFTER the walk, for the reason in the module
    docstring: ``--exclude-standard`` did not report a nested empty orphan that
    the same command without it did report.
    """
    completed = subprocess.run(
        ["git", "check-ignore", "-q", relative],
        cwd=root,
        capture_output=True,
    )
    return completed.returncode == 0


def _is_empty(relative: str, root: Path = REPO_ROOT) -> bool:
    """True when nothing at all lives under ``relative``.

    Directories are counted as well as files. A chain of empty directories is
    still empty of content and is still the orphan class this guards.
    """
    target = root / relative
    if not target.is_dir():
        return False
    return not any(target.rglob("*"))


def empty_orphans(root: Path = REPO_ROOT) -> list[str]:
    """The whole detection, as ONE named function a test can point elsewhere.

    This exists because an adversarial pass refuted the first version of this
    file. The helpers hardcoded ``cwd=REPO_ROOT``, so the non-vacuity test could
    not call them and re-implemented the subprocess call inline instead. Two
    mutants proved the consequence: ``_is_empty`` returning ``False``
    unconditionally, and ``_untracked_directory_entries`` returning ``[]``, each
    left the file at 7 passed. The detection logic could be deleted outright and
    the guard stayed green while its own docstring claimed otherwise.
    """
    return sorted(
        entry
        for entry in _untracked_directory_entries(root)
        if _is_empty(entry, root) and not _is_ignored(entry, root)
    )


def test_no_empty_untracked_unignored_directory_exists() -> None:
    offenders = empty_orphans()
    assert offenders == [], (
        "empty untracked directories found: "
        + ", ".join(offenders)
        + ". These are invisible to `git status --ignored` because git does not "
        "report empty directories. Either delete them, or add a .gitignore rule "
        "with a comment naming what writes them - see OPS-96."
    )


def test_the_two_known_orphans_are_gone_or_ignored() -> None:
    """Pin the two by name, because the general check above cannot say WHICH.

    A future session that deletes ``.backtest/`` and re-introduces
    ``.claude/worktrees/`` leaves the general assertion green and undoes half
    the fix. Naming them is what makes the regression specific.
    """
    for relative in (".backtest", ".claude/worktrees"):
        target = REPO_ROOT / relative
        if not target.exists():
            continue
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert ignored.returncode == 0, (
            f"{relative} exists and is not ignored. It was an empty orphan when "
            "the 2026-09-19 sweep found it; see OPS-96."
        )


def test_the_claude_worktrees_rule_is_present_and_explained() -> None:
    """``.claude/`` is tracked here, so its one exception must say why.

    An unexplained rule in a file full of explained rules is the one a later
    session deletes while tidying, which restores the publication hazard.
    """
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".claude/worktrees/" in text
    index = text.index(".claude/worktrees/")
    preamble = text[:index]
    assert "OPS-96" in preamble.rsplit("# ---", 1)[-1], (
        ".claude/worktrees/ must be ignored with the OPS-96 reason beside it"
    )


def test_the_guard_can_actually_fail(tmp_path: Path) -> None:
    """Point the SHIPPED detection at a scratch repo that has an orphan.

    An adversarial pass refuted the earlier version of this test, which
    re-implemented the enumeration inline and therefore proved only that git
    behaves as documented - not that :func:`empty_orphans` detects anything. It
    now calls that function, so deleting the body of either helper turns this
    red.

    The scratch repository is in ``tmp_path``. Nothing is planted in the real
    tree: a probe file at this repository's root is visible to every other
    guard's walker and to a concurrently running suite.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tracked.txt").write_text("x\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)

    assert empty_orphans(tmp_path) == [], "the fixture starts with no orphan"

    (tmp_path / "orphan").mkdir()
    assert empty_orphans(tmp_path) == ["orphan/"], (
        "the shipped detection no longer finds an empty untracked directory, so "
        "the assertions above it are vacuous"
    )

    # And an orphan with CONTENT is deliberately not one, because failing on
    # unstaged new work is the false red that gets a guard deleted.
    (tmp_path / "orphan" / "work.py").write_text("x\n", encoding="utf-8", newline="\n")
    assert empty_orphans(tmp_path) == [], (
        "a directory holding brand-new unstaged work must not be reported"
    )

    # An ignored empty directory is not one either - that is the FIX applied to
    # `.claude/worktrees/` in this repository, so it has to be exercised.
    (tmp_path / "orphan" / "work.py").unlink()
    (tmp_path / ".gitignore").write_text("orphan/\n", encoding="utf-8", newline="\n")
    assert empty_orphans(tmp_path) == [], (
        "an ignored empty directory must not be reported, or the .claude/"
        "worktrees fix would read as a permanent failure"
    )


def test_git_status_really_cannot_see_an_empty_untracked_directory(
    tmp_path: Path,
) -> None:
    """The premise of the whole file, asserted rather than assumed.

    If a future git DOES report an empty untracked directory in ``git status``,
    this guard can be simplified and its module docstring is wrong. Better to
    be told than to keep the complexity on the strength of a measurement nobody
    re-ran.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tracked.txt").write_text("x\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    (tmp_path / "orphan").mkdir()

    status = subprocess.run(
        ["git", "status", "--ignored", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "orphan" not in status.stdout, (
        "`git status` can now see an empty untracked directory - simplify this "
        "guard and correct its module docstring"
    )


@pytest.mark.parametrize("relative", [".backtest", ".claude/worktrees"])
def test_neither_orphan_is_tracked(relative: str) -> None:
    """Neither may be resurrected as a TRACKED empty-ish directory either.

    git cannot track an empty directory, so the only way one of these names
    comes back tracked is with a placeholder file in it - which would put a
    worktree path or a back-test staging root into a public repository's
    history under cover of looking like housekeeping.
    """
    completed = subprocess.run(
        ["git", "ls-files", "--", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "", (
        f"{relative} has tracked contents; see OPS-96"
    )


def test_operations_doc_carries_the_probe_from_root_rule() -> None:
    """``OPS-96`` item 4 is a PRACTICE, so the only guard available is the doc.

    No test in this suite can observe ``~/.claude/projects/``, which is exactly
    why the practice had to be written down: the artifact a chdir-ing probe
    leaves behind is outside the tree, so a cold session cannot find it and a
    later sweep has to rediscover it from the machine side. Asserting the rule
    is present is the weakest kind of guard and it is the only honest one here -
    it catches a tidy-up that deletes the paragraph, and nothing else.

    Searched on a whitespace-collapsed copy on purpose. Prose in this repository
    is hard-wrapped near 80 columns, so a quoted sentence routinely spans two
    lines and a single-line pattern misses it - a trap this repository has hit
    twice, both times producing a false clean bill.
    """
    raw = (REPO_ROOT / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
    collapsed = " ".join(raw.split())
    assert "never `cd` into it" in collapsed
    assert "Do not change the session's working directory into the probe." in collapsed
    assert "OPS-96" in collapsed
