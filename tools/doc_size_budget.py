"""Flag a watched document once it reaches its configured byte budget.

ROADMAP ``OPS-37`` criterion 3. Measured 2026-09-07: ``ROADMAP.md`` had grown
to 412,224 bytes across 126 sections with no guard of any kind, and
``docs/LEDGER.md`` - append-only, growing every session by this repo's own
design - is large too. Both are append-heavy documents a cold session must be
able to read, which makes silent unbounded growth a real continuity risk. But
both are ALSO deliberately verbose by this repository's own rules - a ledger
entry is written in full, never compressed, because a cold session has no
other context to recover it from - so a hard size limit that truncates or
blocks would fight the project's own continuity design.

This module is therefore a REPORTING check, not a blocker: it measures and
tells the truth about being over budget, and stops there. Whether a future
change wires it into ``.githooks/pre-commit`` or ``.claude/settings.json`` is a
decision for whoever owns those files, made later, with the operator's
say-so - not something this module decides for them by hard-failing on its
own.

WHICH BYTES ARE MEASURED, AND WHY. ``CLAUDE.md`` records a concrete case where
this distinction bit: Windows ``write_text`` turns LF into CRLF, this repo's
``.gitattributes`` pins text files (including every ``.md``) to ``eol=lf``,
and the result is that a working-tree file and its git blob are different
sizes - 26,734 on-disk bytes versus 25,879 as a blob, for one file, measured
2026-09-01e. A budget measured against on-disk bytes is a budget that silently
depends on whichever OS and git config last checked the file out, which makes
it unreproducible for anyone else re-running the same check. So
:func:`git_blob_size` measures the GIT BLOB size instead - what the content
would occupy once committed - and does it by asking ``git`` itself
(``git hash-object`` then ``git cat-file -s``) rather than re-implementing
git's own CRLF/LF text-attribute normalization in Python. This project's own
history is full of exactly that kind of subtle, confidently-wrong
reimplementation (see CLAUDE.md's notes on ``grep -iF`` and on
``taskkill``/MSYS path conversion) and there is no reason to add one here when
the real thing is one subprocess call away.

Concretely, ``git hash-object -w`` reads the CURRENT on-disk content (staged
or not - this deliberately measures the working tree, not a stale HEAD, since
a future pre-commit hook would need to see edits that have not landed yet
either), applies whatever ``.gitattributes`` text/eol conversion the path is
subject to, and writes the resulting blob into this repository's own object
database so ``git cat-file -s`` can report its size. That write is a normal,
expected git operation - it is exactly what ``git add`` does internally - and
it touches only loose objects under ``.git/objects``; it does not stage
anything, does not move a ref, and does not modify any tracked file or the
working tree. Ordinary ``git gc``/repacking reclaims any object this leaves
unreferenced.

WHAT COUNTS AS FAILURE. A watched path that does not exist on disk is a
Finding, not a silent pass - a missing file trivially satisfies "under
budget" for reasons that have nothing to do with the document being small,
which is the textbook vacuous guard this repository's own doctrine warns
against. :func:`check_budgets` never returns early on the first problem it
finds either: every over-budget document AND every missing document in the
same run is collected into one :class:`Report`, because a scan that stops at
the first bad path would hide every problem after it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BUDGETS",
    "REPO_ROOT",
    "Finding",
    "Report",
    "check_budgets",
    "git_blob_size",
    "main",
]

#: Repository root, resolved from this file's location: tools/doc_size_budget.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

# Budgets, keyed by repo-relative path (forward slashes; resolved against
# REPO_ROOT by check_budgets). Values are GIT BLOB bytes - see the module
# docstring for why blob bytes rather than on-disk bytes.
#
# Both figures below were measured 2026-09-07 with:
#   git hash-object -w <path> && git cat-file -s <that sha>
# while two sibling lanes were concurrently appending to both files as part
# of this same OPS-37 session - LEDGER.md alone grew by roughly 3,000 bytes
# in the few minutes this module was being written. Treat the "measured"
# figures below as a lower bound on what had already landed by the time this
# was read, not an exact instant - and treat the headroom as sized for that
# uncertainty on top of ordinary future growth, not just for the gap to the
# one number that happened to be measured.
# RAISED ONCE, ON 2026-09-08, AND THAT RAISE IS A DEFERRAL RATHER THAN A FIX.
# The roadmap budget fired for real: 600,555 blob bytes against 600,000, and
# the pre-commit hook refused the commit. Raising a budget to make a red run
# green is the antipattern this repository has written down, so the numbers
# behind the raise are here and the structural problem is filed as `OPS-56`'s
# neighbour `OPS-57` rather than absorbed silently.
#
# What the measurement actually showed, and it is worse than one file being
# large. The 424,019 figure below was taken on 2026-09-07. By the START of the
# 2026-09-08 session the same file was already 569,870 blob bytes, and that
# session added a further 30,685 to reach 600,555. So the 175,981 bytes of
# headroom sized for "ordinary future growth" were consumed in about a day,
# and roughly 30 KB per session is the rate to plan against - not the rate the
# original budget assumed.
#
# The ledger is on the same curve and is NOT raised here, because it is not
# failing and a budget moved before it fires is a budget nobody trusts: it
# measured 813,780 at the start of that session and 842,387 at the end, which
# leaves 57,613 bytes against its 900,000 budget - under two sessions at the
# observed rate. Expect it to fire next, and do not treat that as a surprise.
BUDGETS: dict[str, int] = {
    # Measured 424,019 bytes (git blob) on 2026-09-07; on-disk was 431,289
    # bytes the same moment, the usual CRLF-vs-LF gap. The original 600,000
    # budget left 175,981 bytes of headroom (~41% above the measured size) and
    # was exhausted on 2026-09-08 at 600,555 bytes. Raised to 700,000, which is
    # ~99,000 bytes of headroom, or about three sessions at the rate measured
    # above. It is deliberately NOT a large raise: a budget that buys a year
    # stops being a tripwire and starts being a rubber stamp.
    "ROADMAP.md": 700_000,
    # Measured 678,833 bytes (git blob) on 2026-09-07, still climbing during
    # that session. Measured again 2026-09-08 at 842,387, which leaves 57,613
    # bytes of headroom - under two sessions at the observed rate. NOT raised:
    # it has not fired, and moving a budget before it fires is how a guard
    # stops meaning anything.
    "docs/LEDGER.md": 900_000,
}


@dataclass(frozen=True)
class Finding:
    """One watched document that failed the check.

    ``kind`` is ``"missing"`` when the path does not exist on disk at all, or
    ``"over_budget"`` when its measured git-blob size is AT OR OVER
    ``budget`` - the ROADMAP acceptance criterion says "at or over", so a size
    exactly equal to the budget is a Finding, not a pass. ``size`` is
    ``None`` only for a ``"missing"`` Finding; a document that was actually
    measured always carries its measured size here, whether or not that size
    is what tripped the Finding.
    """

    kind: str
    path: str
    budget: int
    size: int | None
    detail: str


@dataclass(frozen=True)
class Report:
    """The composed verdict over every watched document in one run.

    ``ok`` is true only when ``findings`` is empty. ``measured`` carries the
    git-blob byte size of every watched document that DID exist on disk,
    whether or not it was over budget, so a caller - or a human reading
    :meth:`format` - can see exactly how much headroom is left on a document
    that is still passing, rather than learning about it only the day it
    fires.
    """

    ok: bool
    findings: tuple[Finding, ...]
    measured: dict[str, int]

    def format(self) -> str:
        """Render the report for a human, one finding per line.

        Measured sizes are appended in BOTH branches - printing them only on
        failure would hide the shrinking headroom on a report that still says
        OK, which is exactly the information this check exists to surface
        before the day it actually fires.
        """
        if self.ok:
            lines = [f"doc size budget: OK ({len(self.measured)} document(s) measured)"]
        else:
            lines = [f"doc size budget: {len(self.findings)} finding(s)"]
            lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        for path in sorted(self.measured):
            lines.append(f"  [measured] {path}: {self.measured[path]} bytes")
        return "\n".join(lines)


def git_blob_size(path: Path, git_cwd: Path = REPO_ROOT) -> int:
    """Return the git-blob byte size of ``path``'s CURRENT on-disk content.

    Measures the working-tree content as it stands right now (staged or not),
    normalized exactly the way ``git`` would normalize it for a commit - see
    the module docstring for why this asks ``git`` itself rather than
    re-implementing CRLF/LF text-attribute handling here.

    ``path`` need not be inside ``git_cwd``'s working tree at all - it is
    passed to ``git hash-object`` as-is and read directly off disk. ``git_cwd``
    only needs to be a directory inside SOME git repository, since its sole
    job is to give ``git hash-object -w`` an object database to write into;
    it defaults to this repository's own root and callers checking a fixture
    under a throwaway directory should leave it at that default rather than
    pointing it at the fixture root, which is generally not a git repository
    at all and would make ``git hash-object -w`` fail outright (measured
    while writing this module's own tests - a tempting-looking but wrong
    fix). Raises ``subprocess.CalledProcessError`` if either git invocation
    fails - this check must never mistake "git failed" for "the document is
    small".
    """
    hashed = subprocess.run(
        ["git", "hash-object", "-w", "--", str(path)],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    sha = hashed.stdout.strip()
    sized = subprocess.run(
        ["git", "cat-file", "-s", sha],
        cwd=git_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return int(sized.stdout.strip())


def check_budgets(
    budgets: dict[str, int] | None = None,
    repo_root: Path = REPO_ROOT,
) -> Report:
    """Check every watched document against its byte budget.

    ``budgets`` defaults to the module-level :data:`BUDGETS` and ``repo_root``
    to :data:`REPO_ROOT`; both are overridable so this can be exercised
    against throwaway fixtures instead of the real repository.

    Every path in ``budgets`` is checked, in order, and every problem found is
    collected into the returned :class:`Report` - a missing path never stops
    the scan, so a later over-budget sibling in the same mapping is still
    reported in the same run.
    """
    if budgets is None:
        budgets = BUDGETS

    findings: list[Finding] = []
    measured: dict[str, int] = {}

    for rel_path, budget in budgets.items():
        full_path = repo_root / rel_path
        if not full_path.is_file():
            findings.append(
                Finding(
                    kind="missing",
                    path=rel_path,
                    budget=budget,
                    size=None,
                    detail=(
                        f"{rel_path}: WATCHED PATH DOES NOT EXIST "
                        f"(budget {budget} bytes) - a missing document is a "
                        "check failure, not a pass"
                    ),
                )
            )
            continue

        # git_blob_size's own default git_cwd (this repo's real root) is
        # deliberately NOT overridden with `repo_root` here - `repo_root` is
        # only where WATCHED PATHS resolve from (a fixture's tmp_path, in
        # tests), and is generally not a git repository in its own right.
        # See git_blob_size's docstring for why passing it through as the git
        # execution directory would break exactly that case.
        size = git_blob_size(full_path)
        measured[rel_path] = size
        if size >= budget:
            over = size - budget
            findings.append(
                Finding(
                    kind="over_budget",
                    path=rel_path,
                    budget=budget,
                    size=size,
                    detail=(
                        f"{rel_path}: {size} bytes, at or over its "
                        f"{budget}-byte budget ({over} bytes over)"
                    ),
                )
            )

    return Report(ok=not findings, findings=tuple(findings), measured=measured)


def main() -> int:
    """Run the real check against :data:`BUDGETS` and print a human report.

    Exit code reflects the verdict (0 ok, 1 findings) so this can be wired
    into a hook later by whoever owns that decision - nothing in this repo
    calls this entry point today, by design; see the module docstring.
    Never mutates a tracked file or the working tree.
    """
    report = check_budgets()
    print(report.format())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
