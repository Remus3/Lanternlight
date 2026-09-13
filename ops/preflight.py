"""Run the mechanical guards at a moment when a slice can still act on them.

``OPS-87`` criterion 2. The recurring cost this repository pays is not the
adversarial pass itself - every refutation in the session that filed the item
was CORRECT and two of them were defects that would have shipped. The cost is
paying the adversarial rate for findings a program could have produced. So the
mechanical classes get a pre-flight, and this is it.

WHAT IT IS. A named subset of guards that already exist, run in one pytest
invocation, plus one git question no guard asks. Measured 2026-09-12 on this
machine: the full suite is 396 seconds and this subset is 19. The subset is not
new logic and does not try to be - the registration guards that caught ``OPS-75``
were already in the suite, six and a half minutes away from the slice that
needed them, and the defect was never that the check did not exist.

WHAT IT IS NOT, stated here because an item about doing less verification is the
easiest place to do less verification. This does not replace an adversarial
pass and does not touch class (a). The census that motivated it found 60 of 135
events to be real defects in the deliverable, and no program in this file would
have found one of them.

THE PART OF THE ITEM'S OWN PREMISE THAT MEASUREMENT REFUTED. ``OPS-87`` states
that everything in classes (b) and (c) "is answerable by a program". The
adjudication of the 54 stale-recital events judged 15 gate-reachable and 39
not, because the dominant failure there is a wrong MECHANISM, CAUSE or SCOPE
rather than a wrong number - "joining is one environment variable", "dropping a
stash removes its commits" - and each was refuted only by an experiment nobody
had thought to run. It also found that the one mechanical family, a number in
prose, is poisoned by this repository's own convention that a dated measurement
stays correct once it no longer reproduces: a dispatch-time re-derivation would
have called ``LL-0199`` wrong at the exact moment it was right. So a
recompute-the-number gate is NOT in the set, and that absence is a finding
rather than an omission.

Run it with ``python -m ops.preflight``.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The subset, with one line each on the finding class it pre-empts. Every entry
#: earned its place from a real event in ``docs/refutation_census.tsv`` - none is
#: here because it sounded relevant. Cost is the other criterion: the two most
#: expensive doc guards in the suite, ``tests/test_no_pii.py`` at 39 seconds and
#: ``tests/test_docguards.py`` at 24, are deliberately LEFT OUT. They are the
#: commit gate's job and they more than double the pre-flight's runtime, which
#: is the difference between a check a slice runs and a check a slice skips.
WHY: dict[str, str] = {
    "tests/test_inventory.py": (
        "class (b). A new tracked test module needs a row in docs/INVENTORY.md "
        "and its absence is invisible to the module's own green - the exact "
        "shape of the OPS-75 cycle, and it fired again in the session that "
        "wrote this file."
    ),
    "tests/test_lanes.py": (
        "class (b). A new tracked file with no owner in ops/lanes.py is an "
        "orphan that nothing arbitrates, and the failure appears in a module "
        "the slice was not editing."
    ),
    "tests/test_lane_contract.py": (
        "class (b). Ownership edited without regenerating the lane contracts "
        "leaves the generated files disagreeing with the registry."
    ),
    "tests/test_source_register.py": (
        "class (c), the reachable slice of it. Prose naming a dotted filename "
        "or a config key reddens the host-shaped pattern, and this is the guard "
        "the hand-off warns about by name."
    ),
    "tests/test_ascii_hygiene.py": (
        "class (c). A non-ASCII glyph in an authored file is refused at commit "
        "time, so finding it at merge time is finding it twice."
    ),
    "tests/test_no_hardcoded_home_path.py": (
        "class (c). An absolute interpreter or home path written into a tracked "
        "file carries the account name and is a privacy failure, not a style one."
    ),
    "tests/test_doc_size_budget.py": (
        "class (c). A fired size budget has a mechanical remedy (OPS-80) and "
        "discovering it at commit time costs the commit."
    ),
    "tests/test_archive_link_guard.py": (
        "class (c). A stub in a split continuity document that points at "
        "nothing is the archive half of the same staleness."
    ),
    "tests/test_ops_ids.py": (
        "class (b). Two lanes taking the same OPS- id merge cleanly with "
        "nothing complaining - the collision is only visible to this guard."
    ),
    "tests/test_repo_surfaces.py": (
        "class (c). A documented command that silences its own summary, which "
        "is the tooling tier OPS-87 is aimed at."
    ),
    "tests/test_refutation_census.py": (
        "class (c). The census itself going stale - a classified event whose "
        "ledger sentence no longer exists."
    ),
    "tests/test_gitignore_shadowing.py": (
        "class (b). An ignore rule shadowing a tracked path, closed as OPS-75 "
        "with a measured zero; the check is what keeps the zero true."
    ),
    "tests/test_no_inbox_in_git.py": (
        "class (b). A file under moon_sync_inbox/ becoming tracked is a "
        "licensing failure a push makes very hard to undo."
    ),
    "tests/test_hook_file_mode.py": (
        "class (b). Hook registration and mode, which is plumbing whose "
        "absence no feature test can see."
    ),
}

MODULES: tuple[str, ...] = tuple(WHY)


@dataclass(frozen=True)
class Result:
    """One pre-flight run. ``seconds`` is measured, never declared."""

    returncode: int
    summary: str
    seconds: float
    modules: int


def check_modules_present(
    modules: tuple[str, ...], root: Path = REPO_ROOT
) -> tuple[str, ...]:
    """Named modules that are not on disk.

    A runner that skipped them would quietly run fewer checks and still print a
    pass, which is the defect ``ops/merge_gate.py`` exists to catch one level up.
    """
    return tuple(m for m in modules if not (root / m).exists())


def untracked_new_files(root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Files that exist, are not ignored, and are not in the git index.

    Measured 2026-09-12: three of this repository's guards subtract its own
    filenames by asking ``git ls-files``, so a file created but not yet staged
    is invisible to that listing and ``tests/test_source_register.py`` reported
    two of the session's own new files as unregistered external hosts. Staging
    them turned the guard green with no edit to any denylist. Reporting this as
    a WARNING rather than a failure is deliberate: a slice mid-flight
    legitimately has new files, and a check that always fires is a check nobody
    reads.

    A directory that is not a repository answers empty rather than raising,
    because a pre-flight whose whole job is to be cheap must not become the
    reason a slice cannot run it.
    """
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(
        line.strip() for line in completed.stdout.splitlines() if line.strip()
    )


def _summary_line(text: str) -> str:
    for line in reversed([ln.strip() for ln in text.splitlines() if ln.strip()]):
        if " in " in line and ("passed" in line or "failed" in line or "error" in line):
            return line.strip("= ").strip()
    return ""


def run(root: Path = REPO_ROOT, modules: tuple[str, ...] = MODULES) -> Result:
    """Run the subset in ONE pytest invocation and time it."""
    missing = check_modules_present(modules, root)
    if missing:
        return Result(
            returncode=2,
            summary=f"module(s) named in the pre-flight set are absent: {missing}",
            seconds=0.0,
            modules=len(modules),
        )
    start = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *modules],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=900,
    )
    seconds = time.monotonic() - start
    return Result(
        returncode=completed.returncode,
        summary=_summary_line(completed.stdout),
        seconds=seconds,
        modules=len(modules),
    )


def format_report(result: Result, untracked: tuple[str, ...]) -> str:
    """The report a slice reads before it claims done."""
    verdict = "PRE-FLIGHT PASS" if result.returncode == 0 else "PRE-FLIGHT REFUSE"
    lines = [
        f"{verdict} - {result.modules} guard modules in {result.seconds:.2f}s",
        f"  pytest: {result.summary}",
    ]
    if untracked:
        lines.append("")
        lines.append(
            "  WARNING - these files exist but are not in the git index, so every"
        )
        lines.append(
            "  guard that subtracts this repository's own filenames is blind to"
        )
        lines.append("  them and may report a false red. Stage them and re-run:")
        for path in untracked:
            lines.append(f"    {path}")
    lines += [
        "",
        "WHAT THIS DOES NOT COVER:",
        "  Class (a), a real defect in the deliverable - 60 of the 135 events in",
        "  docs/refutation_census.tsv - and the 39 of 54 stale-recital events an",
        "  adjudication judged unreachable by any program. Those still need an",
        "  adversarial pass, and this report is not a substitute for one.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--modules-only" in args:
        for module in MODULES:
            print(f"{module}\n    {WHY[module]}")
        return 0
    result = run()
    print(format_report(result, untracked_new_files()))
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
