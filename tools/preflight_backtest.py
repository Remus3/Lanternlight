"""Run today's pre-flight against the tree as it stood when a finding was filed.

``OPS-87`` criterion 3, in its own words: "A gate that cannot show it would have
caught a finding that really happened is a hypothesis wearing a result's
clothes."

HOW A FINDING IS ADDRESSED IN HISTORY, and why this is exact rather than
approximate. Every classified event names a ledger entry, and a ledger entry's
heading is a string that enters this repository in exactly one commit, so
``git log -S'### LL-0236'`` names the commit that FILED the finding. Its PARENT
is the tree as it stood immediately before, which is the tree a pre-flight would
have run against. Nothing here guesses a date or matches a message.

FOUR OUTCOMES, not two, because a two-outcome harness lies. A guard that did not
exist in that tree is NO-GUARD and is never counted as a catch - a check that
postdates a finding cannot have caught it. A tree that will not stand up is
UNBUILDABLE and is reported apart from a clean run, because "the experiment did
not happen" and "the experiment says no" are different facts and this repository
has been burned before by a silence that read as a result.

WHAT A CATCH HERE DOES AND DOES NOT MEAN. It means a module in the pre-flight
set went red in that tree. It does NOT by itself mean red for the reason the
finding names: the failing test names are carried out of the run precisely so a
human can check relatedness rather than trust the exit code. A catch whose
failing test has nothing to do with the event is a coincidence, and the report
prints the names so it can be seen as one.

Run it with ``python -m tools.preflight_backtest --entries LL-0236,LL-0207``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

NEWLINE = chr(10)

VERDICTS = ("CAUGHT", "MISSED", "NO-GUARD", "UNBUILDABLE")

_FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


@dataclass(frozen=True)
class Outcome:
    """One historical tree, run once."""

    entry_id: str
    commit: str
    verdict: str
    failures: tuple[str, ...]
    summary: str


def failing_tests(output: str) -> tuple[str, ...]:
    """Every node id pytest reported as FAILED, in order."""
    return tuple(_FAILED.findall(output))


def summary_line(output: str) -> str:
    """Pytest's own last summary line, or the empty string."""
    for line in reversed([ln.strip() for ln in output.splitlines() if ln.strip()]):
        if " in " in line and ("passed" in line or "failed" in line or "error" in line):
            return line.strip("= ").strip()
    return ""


def classify(
    returncode: int, present: tuple[str, ...], failures: tuple[str, ...]
) -> str:
    """One of :data:`VERDICTS`, defaulting away from a catch when unsure."""
    if not present:
        return "NO-GUARD"
    if failures:
        return "CAUGHT"
    if returncode != 0:
        return "UNBUILDABLE"
    return "MISSED"


def present_modules(tree: Path, modules: tuple[str, ...]) -> tuple[str, ...]:
    """The pre-flight modules that exist in ``tree``."""
    return tuple(m for m in modules if (tree / m).exists())


def entry_commit(entry_id: str, root: Path = REPO_ROOT) -> str | None:
    """The commit that introduced ``### <entry_id> `` into the ledger."""
    for ledger in ("docs/LEDGER.md", "docs/LEDGER_ARCHIVE.md"):
        completed = subprocess.run(
            ["git", "log", "--format=%H", "-S", f"### {entry_id} - ", "--", ledger],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        shas = [ln.strip() for ln in completed.stdout.splitlines() if ln.strip()]
        if shas:
            return shas[-1]
    return None


def _work_root() -> Path:
    """Where historical worktrees are stood up.

    OUTSIDE the repository, deliberately. A worktree under the repo root shows
    up in ``git ls-files --others``, so the pre-flight's own untracked-file
    warning listed the back-test's scaffolding as a finding the first time this
    ran, and every tracked-file walker in the suite would have had to learn to
    ignore it.
    """
    return Path(tempfile.gettempdir()) / "ll_preflight_backtest"


def _run(args: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def back_test_entry(
    entry_id: str,
    modules: tuple[str, ...],
    root: Path = REPO_ROOT,
    work: Path | None = None,
) -> Outcome:
    """Stand up the parent tree of ``entry_id``'s commit and run the subset."""
    sha = entry_commit(entry_id, root)
    if sha is None:
        return Outcome(entry_id, "", "UNBUILDABLE", (), "no commit filed this entry")
    parent = _run(["git", "rev-parse", f"{sha}^"], root)
    if parent.returncode != 0:
        return Outcome(entry_id, sha, "UNBUILDABLE", (), "no parent commit")
    base = parent.stdout.strip()
    work = work or _work_root()
    tree = work / f"bt_{entry_id}"
    if tree.exists():
        _run(["git", "worktree", "remove", "--force", str(tree)], root)
        shutil.rmtree(tree, ignore_errors=True)
    added = _run(["git", "worktree", "add", "--detach", str(tree), base], root)
    if added.returncode != 0:
        return Outcome(entry_id, base, "UNBUILDABLE", (), added.stderr.strip()[:120])
    try:
        here = present_modules(tree, modules)
        if not here:
            return Outcome(entry_id, base, "NO-GUARD", (), "no pre-flight module existed")
        run = _run([sys.executable, "-m", "pytest", "-rf", *here], tree)
        failures = failing_tests(run.stdout)
        return Outcome(
            entry_id,
            base,
            classify(run.returncode, here, failures),
            failures,
            summary_line(run.stdout),
        )
    finally:
        _run(["git", "worktree", "remove", "--force", str(tree)], root)
        shutil.rmtree(tree, ignore_errors=True)


#: The files a new tracked test module must be registered in. Derived from the
#: three reds this repository produced on 2026-09-12 the moment a new module
#: appeared, and from the same three that closed ``OPS-75`` the day before. The
#: lane contracts under ``.claude/commands/`` are GENERATED from ``ops/lanes.py``
#: and are not listed: removing the owner is what makes the contract stale, and
#: stripping both would be reconstructing the same fact twice.
_REGISTRATION_FILES = ("docs/INVENTORY.md", "ops/lanes.py")


def registration_files() -> tuple[str, ...]:
    """The files the reconstruction strips a module's registration from."""
    return _REGISTRATION_FILES


def strip_mentions(text: str, module: str) -> str:
    """Drop every line naming ``module``, by path or by bare basename.

    The basename half matters: ``ops/lanes.py`` names a module with its
    directory and a generated contract may not, and a reconstruction that
    removed only one of the two would leave the tree half-registered and the
    guard green for a reason the experiment did not intend.
    """
    basename = module.rsplit("/", 1)[-1]
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if module not in line and basename not in line
    ]
    return "".join(kept)


def reconstruct_missing_registration(
    tree: Path, module: str
) -> tuple[str, ...]:
    """Undo a module's registration in ``tree``. Returns the files changed."""
    changed: list[str] = []
    for rel in _REGISTRATION_FILES:
        path = tree / rel
        if not path.exists():
            continue
        before = path.read_text(encoding="utf-8")
        after = strip_mentions(before, module)
        if after != before:
            path.write_text(after, encoding="utf-8", newline=NEWLINE)
            changed.append(rel)
    return tuple(changed)


def added_test_modules(sha: str, root: Path = REPO_ROOT) -> tuple[str, ...]:
    """The ``tests/test_*.py`` files a commit ADDED."""
    completed = _run(
        ["git", "show", "--name-only", "--format=", "--diff-filter=A", sha], root
    )
    return tuple(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith("tests/test_") and line.strip().endswith(".py")
    )


def back_test_reconstructed(
    entry_id: str,
    modules: tuple[str, ...],
    root: Path = REPO_ROOT,
    work: Path | None = None,
) -> Outcome:
    """Rebuild the mid-session state the commit graph cannot address.

    Stand up the tree AS THE FIX LEFT IT, then remove the registration lines
    that same commit added for the new test module. That is the state the
    session was actually in for the twenty minutes before somebody noticed, and
    it is derived entirely from what the commit is on record as having added -
    nothing about it is invented.
    """
    sha = entry_commit(entry_id, root)
    if sha is None:
        return Outcome(entry_id, "", "UNBUILDABLE", (), "no commit filed this entry")
    added = added_test_modules(sha, root)
    if not added:
        return Outcome(entry_id, sha, "UNBUILDABLE", (), "that commit added no test module")
    work = work or _work_root()
    tree = work / f"rc_{entry_id}"
    if tree.exists():
        _run(["git", "worktree", "remove", "--force", str(tree)], root)
        shutil.rmtree(tree, ignore_errors=True)
    built = _run(["git", "worktree", "add", "--detach", str(tree), sha], root)
    if built.returncode != 0:
        return Outcome(entry_id, sha, "UNBUILDABLE", (), built.stderr.strip()[:120])
    try:
        changed: list[str] = []
        for module in added:
            changed.extend(reconstruct_missing_registration(tree, module))
        if not changed:
            return Outcome(
                entry_id, sha, "UNBUILDABLE", (), "nothing to un-register in that tree"
            )
        here = present_modules(tree, modules)
        if not here:
            return Outcome(entry_id, sha, "NO-GUARD", (), "no pre-flight module existed")
        run = _run([sys.executable, "-m", "pytest", "-rf", *here], tree)
        failures = failing_tests(run.stdout)
        return Outcome(
            entry_id,
            sha,
            classify(run.returncode, here, failures),
            failures,
            summary_line(run.stdout) + f" [un-registered {', '.join(added)}]",
        )
    finally:
        _run(["git", "worktree", "remove", "--force", str(tree)], root)
        shutil.rmtree(tree, ignore_errors=True)


def tally(rows: list[Outcome]) -> dict[str, int]:
    """Verdict counts, recomputed from the rows."""
    counts = dict.fromkeys(VERDICTS, 0)
    for row in rows:
        counts[row.verdict] += 1
    return counts


def format_report(rows: list[Outcome]) -> str:
    counts = tally(rows)
    lines = [
        "PRE-FLIGHT BACK-TEST - OPS-87 criterion 3",
        f"  trees run: {len(rows)}",
        f"  CAUGHT: {counts['CAUGHT']}",
        f"  MISSED: {counts['MISSED']}",
        f"  NO-GUARD (the check postdates the finding): {counts['NO-GUARD']}",
        f"  UNBUILDABLE (the experiment did not happen): {counts['UNBUILDABLE']}",
        "",
        "PER TREE - the failing test names are printed so a catch can be checked",
        "for relatedness rather than believed on its exit code:",
    ]
    for row in rows:
        lines.append(f"  {row.entry_id} {row.commit[:8]} {row.verdict:12s} {row.summary}")
        for failure in row.failures:
            lines.append(f"      {failure}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from ops import preflight

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entries", required=True, help="comma separated LL ids")
    parser.add_argument("--out", default="", help="write the report here as well")
    parser.add_argument(
        "--reconstruct",
        action="store_true",
        help="rebuild the mid-session state instead of the parent commit",
    )
    args = parser.parse_args(argv)
    entries = [e.strip() for e in args.entries.split(",") if e.strip()]
    runner = back_test_reconstructed if args.reconstruct else back_test_entry
    rows = [runner(e, preflight.MODULES) for e in entries]
    report = format_report(rows)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
