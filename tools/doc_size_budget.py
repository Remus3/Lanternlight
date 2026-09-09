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

HEADROOM IS STATED IN SESSIONS, NOT IN BYTES OR PERCENTAGES. ROADMAP
``OPS-57`` criterion 5, added 2026-09-08 after the ROADMAP budget fired. The
budget that fired had "175,981 bytes of headroom (~41% above the measured
size)" recorded beside it, and it was consumed in about a day. Neither figure
was false; both were simply unreadable as a planning number, because a reader
cannot convert bytes into remaining time without carrying the growth rate in
their head. So this module measures a PER-SESSION GROWTH RATE for every
budgeted document (:data:`SESSION_GROWTH_RATES`) and
:func:`headroom_sessions` divides the remaining bytes by it, which produces a
figure nobody can misread as generous: below 1.0 means the budget fires NEXT
session. A document under :data:`LOW_HEADROOM_SESSIONS` sessions is flagged in
the report even while it is still comfortably under budget in bytes.

That warning is deliberately NOT a failure. ``.githooks/pre-commit`` selects
this module's test file whenever a budgeted document is staged, so making low
headroom fail would start refusing ordinary commits for a condition that is
information rather than a defect - and a guard that refuses routine work is a
guard someone disables. :attr:`Report.ok` therefore still depends only on
:attr:`Report.findings`, exactly as before; :attr:`Report.low_headroom` is a
separate, additive channel.

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
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "BUDGETS",
    "LOW_HEADROOM_SESSIONS",
    "REPO_ROOT",
    "SESSION_GROWTH_RATES",
    "Finding",
    "GrowthRate",
    "Report",
    "check_budgets",
    "git_blob_size",
    "headroom_sessions",
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
    # RE-DERIVED 2026-09-08 AFTER THE OPS-57 SPLIT, and LOWERED, not raised.
    # Measured 175,390 blob bytes immediately after the split moved 65 closed
    # and refuted sections to docs/ROADMAP_ARCHIVE.md. Against the old 700,000
    # that was 16.2 sessions of headroom, which is exactly the rubber stamp
    # OPS-57 warned about, so the budget comes DOWN to 340,000: 164,610 bytes,
    # or 5.1 sessions at the median rate below - AT THE SPLIT. By the commit
    # that closed OPS-57 this file was 194,174 bytes and 4.5 sessions, because
    # the session then wrote its own closure, an archive index and three new
    # items into it. Both are correct for their instant; neither is the live
    # answer. Run this module rather than reading either number.
    #
    # WHEN THIS FIRES, RE-RUN THE SPLIT - do not raise the number again. The
    # split is re-runnable (tools/doc_archive.py) and it is the thing that
    # buys headroom; a raise only defers, which is what the 700,000 above did
    # and was labelled as at the time.
    "ROADMAP.md": 340_000,
    # Measured 678,833 bytes (git blob) on 2026-09-07, still climbing during
    # that session. Measured again 2026-09-08 at 842,387, which leaves 57,613
    # bytes of headroom - under two sessions at the observed rate. NOT raised:
    # it has not fired, and moving a budget before it fires is how a guard
    # stops meaning anything.
    # RE-DERIVED 2026-09-08 AFTER THE OPS-57 SPLIT, and LOWERED. Measured
    # 281,778 blob bytes after the oldest 135 entries moved to
    # docs/LEDGER_ARCHIVE.md, keeping the 60 newest. Against the old 900,000
    # that was 22.4 sessions; the budget comes DOWN to 420,000, which is
    # 138,222 bytes or 5.0 sessions at the median rate below - AT THE SPLIT;
    # 295,174 bytes and 4.5 sessions by the closing commit, for the same
    # reason as above. Same instruction when it fires: re-run the split, do
    # not move the number.
    "docs/LEDGER.md": 420_000,
}
# THE SPLIT RESET THE LEVEL, NOT THE SLOPE - so the rates below are NOT
# re-measured, and that is a decision rather than an omission. The merger slot
# formerly here asked for a post-split re-measurement; there is exactly ONE
# post-split session, and a slope through one point is not a measurement. The
# rates below are rates of APPENDING - new sections and new entries land on the
# live documents at the same pace whatever their current size - so archiving
# changes where the line starts and not how steeply it climbs. Re-measure them
# once several post-split sessions exist, and expect them to be close.


@dataclass(frozen=True)
class GrowthRate:
    """Measured per-session growth of one document, in git-blob bytes.

    ``median`` is the planning rate :func:`headroom_sessions` divides by,
    ``mean`` sits beside it so a reader can see the spread rather than one
    confident number, and ``samples`` keeps the evidence in the module so both
    summaries stay re-derivable from it - a rate is a hypothesis like any other
    count in this repository, and a summary detached from its samples is how a
    hypothesis quietly becomes folklore.
    """

    median: int
    mean: int
    samples: tuple[int, ...]


#: A document with fewer than this many sessions of headroom is flagged in the
#: report. Two, because one is already too late: a document flagged with one
#: session left fires during the very next session, which gives whoever reads
#: the flag no session in which to act on it. This is a WARNING threshold and
#: never a failure threshold - see the module docstring.
LOW_HEADROOM_SESSIONS = 2.0

# Per-session growth rates, keyed exactly like BUDGETS.
#
# MEASURED 2026-09-08, and this is a HYPOTHESIS, not a constant of nature.
# Method, so it can be repeated rather than trusted: the git blob size of each
# document was taken at each of the 18 commits whose subject begins "Wrap " or
# "Hand off" - this repository's session boundaries - and the last six
# consecutive deltas between those boundaries were kept. Six sessions is a
# short window on purpose: this repository's writing habits have changed over
# its life, and a rate averaged over its whole history would describe a project
# that no longer exists.
#
# THE SUMMARY FIGURE IS THE HIGH MEDIAN, NOT THE PLAIN MEDIAN, and the
# difference is worth naming rather than glossing. With six samples the plain
# median averages the two middle values (27,984 for ROADMAP.md and 26,138 for
# docs/LEDGER.md); the figures below take the HIGHER of the two middle samples
# instead - statistics.median_high - which is the more conservative planning
# number, since overestimating the rate shortens the reported headroom and
# underestimating it is exactly the failure this whole criterion exists to
# stop. The median of either kind is preferred to the mean because a single
# ~95 KB session drags the mean up by roughly a quarter; the mean is recorded
# beside it so that spread stays visible instead of being averaged away.
#
# These rates are pre-split measurements. See the MERGER SLOT above.
SESSION_GROWTH_RATES: dict[str, GrowthRate] = {
    "ROADMAP.md": GrowthRate(
        median=32_421,
        mean=40_628,
        samples=(95_785, 8_129, 19_885, 23_548, 32_421, 64_001),
    ),
    "docs/LEDGER.md": GrowthRate(
        median=27_589,
        mean=37_290,
        samples=(81_272, 14_235, 24_688, 27_589, 21_907, 54_053),
    ),
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

    ``headroom_sessions`` carries the remaining sessions for every measured
    document a growth rate was known for - a document with no measured rate is
    ABSENT from it rather than present with a placeholder, because unmeasured
    and "zero sessions left" are different facts and conflating them is how
    this check would start lying. ``low_headroom`` names the documents under
    :data:`LOW_HEADROOM_SESSIONS`; it is a warning channel and deliberately
    does NOT feed ``ok``.
    """

    ok: bool
    findings: tuple[Finding, ...]
    measured: dict[str, int]
    headroom_sessions: dict[str, float] = field(default_factory=dict)
    low_headroom: tuple[str, ...] = ()

    def format(self) -> str:
        """Render the report for a human, one finding per line.

        Measured sizes are appended in BOTH branches - printing them only on
        failure would hide the shrinking headroom on a report that still says
        OK, which is exactly the information this check exists to surface
        before the day it actually fires.

        Each measured line states its headroom in SESSIONS as well as in
        bytes, and marks the document ``LOW HEADROOM`` when it is under
        :data:`LOW_HEADROOM_SESSIONS`. Both figures are printed rather than
        just the sessions one: the byte count is what a reader re-measures to
        check the claim, and the sessions count is what tells them whether to
        act this week. A document with no measured growth rate says so in
        words instead of showing a number nobody measured.
        """
        if self.ok:
            lines = [f"doc size budget: OK ({len(self.measured)} document(s) measured)"]
        else:
            lines = [f"doc size budget: {len(self.findings)} finding(s)"]
            lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        for path in sorted(self.measured):
            line = f"  [measured] {path}: {self.measured[path]} bytes"
            left = self.headroom_sessions.get(path)
            if left is None:
                line += ", headroom in sessions unknown - no measured growth rate"
            else:
                line += f", {left:.1f} sessions of headroom"
                if path in self.low_headroom:
                    line += (
                        f" - LOW HEADROOM (under {LOW_HEADROOM_SESSIONS:.1f} "
                        "sessions; this is a warning, not a failure)"
                    )
            lines.append(line)
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


def headroom_sessions(
    path: str,
    size: int,
    budgets: dict[str, int] | None = None,
    rates: dict[str, GrowthRate] | None = None,
) -> float | None:
    """Return how many more sessions ``path`` can grow before it hits budget.

    ``(budget - size) / rate``, where ``rate`` is the measured per-session
    median growth from :data:`SESSION_GROWTH_RATES`. ``size`` is passed in
    rather than measured here so this stays pure arithmetic that a test can
    exercise at an exact boundary without shelling out to ``git`` - the
    measurement itself already happened in :func:`check_budgets`.

    Returns ``None``, never a number, when ``path`` has no budget, no measured
    growth rate, or a non-positive one. That is this repository's "omit rather
    than guess" rule applied where it matters most: a fallback of ``0.0`` would
    read as "fires next session" and a fallback of ``inf`` would read as
    "nothing to worry about", and both are claims nobody measured.

    The result is NOT clamped at zero. A document already past its budget
    reports negative sessions, so "just fired" and "far past" stay
    distinguishable; exactly ``0.0`` means the document is sitting on its
    budget right now, and any value under ``1.0`` means the budget fires during
    the next session.
    """
    if budgets is None:
        budgets = BUDGETS
    if rates is None:
        rates = SESSION_GROWTH_RATES

    budget = budgets.get(path)
    rate = rates.get(path)
    if budget is None or rate is None or rate.median <= 0:
        return None
    return (budget - size) / rate.median


def check_budgets(
    budgets: dict[str, int] | None = None,
    repo_root: Path = REPO_ROOT,
    rates: dict[str, GrowthRate] | None = None,
) -> Report:
    """Check every watched document against its byte budget.

    ``budgets`` defaults to the module-level :data:`BUDGETS`, ``repo_root`` to
    :data:`REPO_ROOT` and ``rates`` to :data:`SESSION_GROWTH_RATES`; all three
    are overridable so this can be exercised against throwaway fixtures
    instead of the real repository.

    Every path in ``budgets`` is checked, in order, and every problem found is
    collected into the returned :class:`Report` - a missing path never stops
    the scan, so a later over-budget sibling in the same mapping is still
    reported in the same run.

    Remaining headroom in sessions is computed for every document that was
    actually measured AND has a measured growth rate. It never affects
    ``Report.ok``: the failure condition is unchanged from before OPS-57,
    because ``.githooks/pre-commit`` depends on it.
    """
    if budgets is None:
        budgets = BUDGETS
    if rates is None:
        rates = SESSION_GROWTH_RATES

    findings: list[Finding] = []
    measured: dict[str, int] = {}
    sessions_left: dict[str, float] = {}
    low_headroom: list[str] = []

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

        left = headroom_sessions(rel_path, size, budgets=budgets, rates=rates)
        if left is not None:
            sessions_left[rel_path] = left
            if left < LOW_HEADROOM_SESSIONS:
                low_headroom.append(rel_path)

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

    return Report(
        ok=not findings,
        findings=tuple(findings),
        measured=measured,
        headroom_sessions=sessions_left,
        low_headroom=tuple(low_headroom),
    )


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
