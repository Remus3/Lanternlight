"""Re-probe an agent's claims instead of believing its report.

This module exists because of one specific, repeated failure: a subagent
reports that it wrote a file, added a test and left the suite green, the
merger relays that, and none of it is true - or it is true in a way that hides
a regression. ``CLAUDE.md`` already states the rule ("never trust a subagent's
claim"), but a rule that lives only in prose is a rule that gets skipped at
exactly the moment it matters. This is the mechanical version.

Five probes, each aimed at a distinct way a "done" claim goes wrong.

**The file was never delivered.** :func:`check_claimed_paths` asks the
filesystem, not the agent. It separates *missing* from *empty* from *not a
file*, because an agent that created a zero-byte module and an agent that
created nothing have both failed, but they failed differently and the fix
differs too.

**A test was deleted or weakened to make the suite green.** This is the one
that matters most and the one an exit code cannot see. ``pytest`` exits 0 just
as happily on 181 passing tests as on 182, so a green run proves nothing about
coverage staying put. :func:`check_test_count` compares the collected total
against a baseline measured *before* the work started and treats any decrease
as a finding. Deleting a test to fix a build is an explicit stop condition in
``docs/HEADLESS.md``; this is what notices.

**A test was deleted from one file while a different file grew.** The total is
safe for one worker and unsafe for several: once lanes commit concurrently, a
lane deleting 15 tests from its own file is completely hidden by a sibling lane
adding 20 elsewhere, because the total RISES.
:func:`check_per_file_counts` attributes a drop to the file it happened in
rather than netting it off against unrelated work. Wired into :func:`verify` on
2026-09-06, which is later than it should have been - the function had been
exported in ``__all__``, cited by all eight generated lane contracts and
covered by six of its own tests since the day it was written, and **never once
called.** ``ROADMAP`` item ``OPS-31`` records it: a check that has never run is
decoration with a good name, and its own passing tests are no evidence
otherwise.

**The numbers were taken on a tree that was moving.** ``OPS-58``. Every probe
above measures the repository as it is at merge time and none of them notices
that a parallel slice ran ``git stash`` in the middle - which takes the whole
working tree and index, including the files that slice was told not to touch.
:func:`read_store_drift` loads the reading :func:`ops.loop.state.dispatch`
took before the work and compares it with one taken here.

Two things about it are deliberate and easy to get wrong. It is reported in
``GateReport.measurement`` rather than as a finding, because drift changes
what a merger checks next rather than whether the merge proceeds - this
repository has had real stashes taken in it during a session in which nothing
was lost. And when no dispatch-time reading exists it says the check DID NOT RUN;
it never says there was no drift, which would be an answer its record cannot
support. The detector itself was built and proved under ``OPS-54`` and then
left with no caller at all for a week, which is the ``OPS-31`` shape again.

**The suite did not actually run.** :func:`parse_summary` distinguishes "no
summary line was printed" from "zero tests passed". Those are different facts,
and a gate that conflates them will approve a run that crashed during
collection.

**The suite ran, aborted, and lied about it.** This is the subtlest of the
four and it was measured on 2026-09-06 while answering ``ROADMAP`` item
``OPS-30``. A ``pytest`` run that dies part-way - the measured cause was
``MemoryError`` inside ``_pytest/_code/source.py`` ``getstatementrange_ast`` -
can still print a perfectly well-formed stats line, because that line counts
what the run GOT THROUGH rather than what it was asked to do. A four-test
project with two failing tests aborted with ``MemoryError``, exited 3, and
printed ``2 passed in 0.08s``. The old gate read that and reported
``merge gate: OK``. Two independent defects made that possible and both are
fixed here:

- :func:`parse_summary` used to search the whole blob for ``N passed``. This
  very repository's ``tests/test_merge_gate.py`` carries ``182 passed in
  0.78s`` as sample data, so any run that renders a failure in that file
  echoes a summary-shaped string into its own output. The parser now anchors
  on a real summary LINE, scanning upward from the end.
- ``_run`` threw away the process exit code, which was the one witness that
  could not be faked by text. :class:`RunResult` keeps it and
  :func:`check_run_completed` refuses any run whose exit code contradicts its
  own summary.

A third defect was found by the cycle 49 REFUTATION pass, after the two above
were called fixed, and it is recorded here because the sequence is the lesson.
The anchored parser stripped leading whitespace and then anchored, which threw
away the only thing separating pytest's own stats line - always written at
column 0 - from one quoted inside a traceback. An indented
``182 passed in 12.00s`` was read as a real summary, and with returncode 0 it
drew ZERO findings, so the gate signed off exactly as before. **Anchoring that
strips first is not anchoring.** :func:`find_summary_line` now skips any
indented line before the strip.

The residual hole is named rather than hidden, and the previous wording of
this paragraph OVERCLAIMED how it was covered - corrected here rather than
edited away. A test that prints a summary-shaped line AT COLUMN 0, in a run
that then aborts after that print, is still read as a summary. The exit-code
check covers that only when the aborted run exits non-zero; **a run that
prints such a line and exits 0 is covered by neither check.** No such case has
been measured, and it is not claimed to be impossible.

The baseline is deliberately a **parameter, not a stored constant.** A count
checked into the repo goes stale and becomes a confident lie - ``CLAUDE.md``
forbids restating suite counts for exactly that reason. The caller measures
the count before dispatching work and passes what it measured. The same is
true of the per-file baseline: one collect run before dispatch yields both,
since ``sum(parse_collect_counts(text).values()) == total_collected(text)``.

**A default that checks nothing is the same defect wearing a signature.** This
was the second structural hole recorded under ``OPS-31``, and it is why
:func:`verify` no longer accepts silence from itself. ``baseline=None`` at
least raised ``no-baseline``; an empty ``claimed_paths`` raised nothing at all,
so a caller could get ``ok=True`` out of a file probe that had examined ZERO
files. It is now a ``no-claims`` finding. An absent per-file baseline is
recorded in ``GateReport.notes`` and printed by ``GateReport.format`` even on
an OK report, rather than being made a finding - see :func:`verify` for why
that asymmetry is deliberate and what it costs.

**And the limit none of this closes:** every baseline is handed in by the very
caller whose work is under test. The gate can refuse a missing baseline. It
cannot refuse a baseline that was quietly lowered, and it cannot tell a
claimed path that was written from one that merely already existed.

Every output shape parsed here was measured on this machine on 2026-08-09.
Two of them break naive parsing and are the reason this module does not simply
call ``str.splitlines()`` and index:

- pytest's lines are **CR-terminated** here, and the final summary line has no
  trailing newline at all
- ``--collect-only -q`` prints a per-file ``path: count`` list and **no grand
  total**, so the total must be summed

A third shape was measured on 2026-09-06 and matters to the anchored parser:
once a run passes a minute, pytest appends a wall-clock suffix, so this
repository's own green line reads ``1781 passed in 111.56s (0:01:51)`` rather
than the ``<n> passed in <x>s`` a parser would naively assume.

Nothing here shells out unless you ask it to: the parsers are pure functions
over text, so they are testable without running a suite inside a suite.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Finding",
    "GateReport",
    "MEASUREMENT_HEADER",
    "RunResult",
    "SummaryResult",
    "check_claimed_paths",
    "describe_store_drift",
    "read_store_drift",
    "check_per_file_counts",
    "check_run_completed",
    "check_test_count",
    "collect_output",
    "collect_result",
    "find_summary_line",
    "parse_collect_counts",
    "parse_summary",
    "suite_output",
    "suite_result",
    "total_collected",
    "verify",
]

#: Repository root, resolved from this file's location: ops/merge_gate.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

# "tests/test_redact.py: 23" - the count is the last thing on the line, which
# is what keeps this from matching "ERROR tests/x.py - ImportError: boom".
_COLLECT_RE = re.compile(r"^(?P<path>\S.*?):[ \t]*(?P<count>\d+)[ \t]*$")

_PASSED_RE = re.compile(r"(?<!\w)(\d+) passed(?!\w)")
_FAILED_RE = re.compile(r"(?<!\w)(\d+) failed(?!\w)")
_ERROR_RE = re.compile(r"(?<!\w)(\d+) errors?(?!\w)")

# pytest's final stats line, and nothing that merely resembles one. Measured
# shapes this must accept, all on this machine:
#
#   "182 passed in 0.78s"                      -q, short run
#   "1781 passed in 111.56s (0:01:51)"         -q, run long enough for a clock
#   "= 1 failed, 3 passed in 0.05s ="          default verbosity, banner
#   "no tests ran in 0.01s"                    empty selection
#
# and must REJECT, because it is echoed test data rather than a summary:
#
#   "E     + 182 passed in 0.78s"
#
# The load-bearing parts are the anchors. ``^`` and ``$`` mean the line has to
# BE the stats line rather than contain one, and the ``in <duration>s`` tail is
# what a quoted fragment of sample data does not carry on its own.
_SUMMARY_LINE_RE = re.compile(
    r"^(?P<stats>(?:no tests ran|\d+ [a-z]+)(?:,\s*\d+ [a-z]+)*)"
    r"\s+in\s+\d+(?:\.\d+)?s"
    r"(?:\s*\(\d+:\d{2}:\d{2}\))?$"
)

#: Marker pytest prints when it aborts inside its own machinery.
_INTERNAL_ERROR_MARKER = "INTERNALERROR"

# pytest's documented exit codes. Only 0 (everything passed) and 1 (tests
# failed) describe a run that reached the end; the rest mean it did not.
_EXIT_MEANING = {
    0: "all tests passed",
    1: "tests failed",
    2: "interrupted",
    3: "internal error",
    4: "usage error",
    5: "no tests collected",
}


@dataclass(frozen=True)
class Finding:
    """One thing the gate refuses to sign off on.

    ``kind`` is a stable slug so callers can branch on it; ``detail`` is the
    human-readable sentence that names the actual numbers or paths involved.
    """

    kind: str
    detail: str


@dataclass(frozen=True)
class SummaryResult:
    """What pytest's final summary line said, if it printed one at all.

    ``found`` is the field that matters. When it is ``False`` the three counts
    are ``None`` rather than ``0``, because "the suite printed no summary" and
    "the suite ran and nothing passed" are different facts and only one of
    them means the run happened.
    """

    found: bool
    passed: int | None
    failed: int | None
    errors: int | None


@dataclass(frozen=True)
class RunResult:
    """The two things a pytest invocation tells you, kept together.

    Text alone is not enough. A run that aborts can still print a plausible
    stats line, so the exit code is carried alongside it rather than discarded
    - it is the only witness the output cannot contradict.
    """

    text: str
    returncode: int


#: Printed above the measurement block, and only when there is one -
#: ``OPS-58`` criterion 3. A finding says the WORK may be wrong. A measurement
#: line says nothing whatever about the work: it says the numbers above it were
#: taken while the object store was moving. A merger who reads the two as one
#: list either ignores both or blocks on both, and blocking on drift is the
#: worse mistake - real stashes have been taken in this repository during a
#: session in which nothing was lost. No count is given here on purpose: a
#: stash writes two commits, or three when untracked files are included, and a
#: repeat taken from an unchanged index adds only one because its index commit
#: hashes to the object the first one already wrote. See ``OPS-60``.
MEASUREMENT_HEADER = (
    "  --- measurement conditions - NOT a verdict on the claimed work ---",
    "  a finding above says the work may be wrong; a line below says the "
    "numbers above were taken on a moving tree, which changes what you check "
    "next rather than whether you merge",
)


@dataclass(frozen=True)
class GateReport:
    """The composed verdict. ``ok`` is true only when nothing was found.

    ``notes`` is the part that keeps ``ok`` honest. A probe that could not run
    - because the caller supplied nothing for it to compare against - has not
    passed, and an OK report that says nothing about it is indistinguishable
    from an OK report that checked everything. Each note names a check that
    did NOT run, and :meth:`format` renders them even when ``ok`` is true.

    ``measurement`` is the third channel and it is neither of the other two.
    It carries what was true of the REPOSITORY while the numbers above were
    being taken - ``OPS-58``. It never touches ``ok``: drift changes what a
    merger checks next, not whether the merge proceeds.
    """

    ok: bool
    findings: tuple[Finding, ...]
    collected: int | None
    summary: SummaryResult | None
    notes: tuple[str, ...] = ()
    measurement: tuple[str, ...] = ()

    def format(self) -> str:
        """Render the report for a human, one finding per line.

        The unchecked notes are appended in BOTH branches. Printing them only
        on failure would hide them in exactly the case they exist for: a
        report that says OK.

        The measurement block is fenced by :data:`MEASUREMENT_HEADER` and is
        printed only when there is something in it, so the separator never
        becomes furniture a reader stops seeing.
        """
        if self.ok:
            lines = [f"merge gate: OK ({self.collected} tests collected)"]
        else:
            lines = [f"merge gate: {len(self.findings)} finding(s)"]
            lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        lines.extend(f"  [unchecked] {note}" for note in self.notes)
        if self.measurement:
            lines.extend(MEASUREMENT_HEADER)
            lines.extend(f"  {one}" for one in self.measurement)
        return "\n".join(lines)


def _clean_lines(text: str) -> list[str]:
    """Split on newlines and strip the CRs pytest leaves on every line here."""
    if not text:
        return []
    return [line.rstrip("\r") for line in text.split("\n")]


def parse_collect_counts(text: str) -> dict[str, int]:
    """Map each test file to its collected count from ``--collect-only -q``.

    Lines that are not a ``path: count`` pair - collection errors, blank
    trailing lines, warnings - are ignored rather than raising, because this
    runs on output that may already be reporting a problem.
    """
    counts: dict[str, int] = {}
    for line in _clean_lines(text):
        match = _COLLECT_RE.match(line)
        if match is None:
            continue
        counts[match["path"].strip()] = int(match["count"])
    return counts


def total_collected(text: str) -> int:
    """Total tests collected. Summed, because pytest prints no grand total."""
    return sum(parse_collect_counts(text).values())


def find_summary_line(text: str) -> str | None:
    """Return pytest's stats line, or ``None`` if the run never printed one.

    Scans upward from the end, because the stats line is the last thing a
    completed run writes and because anything summary-shaped further up is by
    definition not it.

    This used to be a search over the whole blob, and that was a real defect
    rather than a theoretical one: ``tests/test_merge_gate.py`` carries
    ``182 passed in 0.78s`` as measured sample data, so a run that renders a
    failure in that file prints a summary-shaped string of its own. On
    2026-09-06 a run aborted by ``MemoryError`` in the terminal-summary phase
    printed no stats line at all and the old parser answered ``182 passed``,
    read out of the FAILURES section.
    """
    for line in reversed(_clean_lines(text or "")):
        # An INDENTED line is quoted output - a source line inside a
        # traceback, or captured logging - never pytest's own stats line,
        # which it writes at column 0. Skipping it BEFORE the strip below is
        # the whole of the anchor: the first cut stripped leading whitespace
        # and then anchored, which threw away the one signal that separates a
        # real summary from one quoted inside a failure body. Found by the
        # cycle 49 refutation pass, which showed an indented decoy plus
        # returncode 0 drawing zero findings - the gate signing off again, one
        # layer in from the whole-blob grep this function was written to fix.
        if line[:1].isspace():
            continue
        candidate = line.strip().strip("=").strip()
        match = _SUMMARY_LINE_RE.match(candidate)
        if match is not None:
            return match["stats"]
    return None


def parse_summary(text: str) -> SummaryResult:
    """Read pytest's final summary line.

    Handles the measured local shape - CR-terminated, no trailing newline -
    and returns ``found=False`` with ``None`` counts when no summary was
    printed at all.

    The counts are read out of the stats line only, never out of the
    surrounding output. See :func:`find_summary_line` for why that distinction
    is load-bearing.
    """
    stats = find_summary_line(text)
    if stats is None:
        return SummaryResult(found=False, passed=None, failed=None, errors=None)
    passed = _PASSED_RE.search(stats)
    failed = _FAILED_RE.search(stats)
    errors = _ERROR_RE.search(stats)
    return SummaryResult(
        found=True,
        passed=int(passed[1]) if passed else 0,
        failed=int(failed[1]) if failed else 0,
        errors=int(errors[1]) if errors else 0,
    )


def check_run_completed(
    run: RunResult, summary: SummaryResult | None = None
) -> list[Finding]:
    """Refuse to sign off on a run that did not finish the way it claims to.

    ``ROADMAP`` item ``OPS-30`` criterion 4 in mechanical form. Three distinct
    ways a run fails to be trustworthy, each with its own slug:

    ``no-summary``
        No stats line at all. The run did not complete; that is not the same
        fact as completing with zero passes.
    ``internal-error``
        pytest printed ``INTERNALERROR``, so it aborted inside its own
        machinery. It may still have printed a stats line afterwards; that
        line is a partial count, not a verdict.
    ``exit-mismatch``
        The exit code and the summary disagree. pytest exits 0 only when
        everything passed and 1 only when tests failed; any other code means
        the run did not reach the end, and a summary claiming a clean sweep
        under a non-zero code is the exact shape of the measured near miss.

    ``failed`` and ``errors`` are reported here too, so one function answers
    "is this run's own account of itself believable, and what did it say".
    """
    resolved = parse_summary(run.text) if summary is None else summary
    findings: list[Finding] = []

    if _INTERNAL_ERROR_MARKER in (run.text or ""):
        findings.append(
            Finding(
                kind="internal-error",
                detail=(
                    "pytest printed INTERNALERROR - it aborted inside its own "
                    "machinery, so any count it printed afterwards is a partial "
                    "tally rather than a result"
                ),
            )
        )

    if not resolved.found:
        findings.append(
            Finding(
                kind="no-summary",
                detail=(
                    "pytest printed no summary line - the suite did not complete, "
                    "which is not the same as completing with zero passes"
                ),
            )
        )
        return findings

    failed = resolved.failed or 0
    errors = resolved.errors or 0
    clean_exit = run.returncode == 0 and not failed and not errors
    failing_exit = run.returncode == 1 and (failed or errors)
    if not (clean_exit or failing_exit):
        findings.append(
            Finding(
                kind="exit-mismatch",
                detail=(
                    f"pytest exited {run.returncode} "
                    f"({_EXIT_MEANING.get(run.returncode, 'unknown code')}) but its "
                    f"summary reports {failed} failed and {errors} error(s) - the "
                    "run did not end the way its own summary says it did"
                ),
            )
        )

    if failed:
        findings.append(Finding(kind="failed", detail=f"{failed} test(s) failed"))
    if errors:
        findings.append(Finding(kind="errors", detail=f"{errors} test error(s)"))
    return findings


def check_test_count(current: int, baseline: int | None) -> list[Finding]:
    """Fail when the collected count dropped below ``baseline``.

    A missing baseline is itself a finding. A check that silently no-ops when
    it has nothing to compare against is worse than no check, because it
    reports success either way.
    """
    if baseline is None:
        return [
            Finding(
                kind="no-baseline",
                detail=(
                    f"collected {current} tests but no baseline was supplied, so "
                    "the count-regression check could not run - measure the "
                    "count before dispatching work and pass it in"
                ),
            )
        ]
    if current < baseline:
        return [
            Finding(
                kind="count-regression",
                detail=(
                    f"collected {current} tests, down from a baseline of "
                    f"{baseline} - {baseline - current} test(s) went missing; a "
                    "suite can go green by losing coverage"
                ),
            )
        ]
    return []


def check_per_file_counts(
    current: dict[str, int], baseline: dict[str, int] | None
) -> list[Finding]:
    """Fail when any individual test file lost tests.

    :func:`check_test_count` compares repository totals, which is safe for one
    worker and unsafe for several. Once lanes commit concurrently, a lane that
    deletes 15 tests from its own file is completely hidden by a sibling lane
    adding 20 elsewhere: the total rises and a total-only guard reports
    success while coverage actually fell.

    Comparing per file sees that, because a drop is attributed to the file it
    happened in rather than netted off against unrelated work. A file that
    disappeared entirely is reported separately from one that merely shrank -
    they are different accidents with different fixes.

    New files are never a finding. Lanes are expected to add tests.
    """
    if baseline is None:
        return [
            Finding(
                kind="no-baseline",
                detail=(
                    f"{len(current)} test file(s) collected but no per-file baseline "
                    "was supplied, so the regression check could not run"
                ),
            )
        ]
    findings: list[Finding] = []
    for path, was in sorted(baseline.items()):
        now = current.get(path)
        if now is None:
            findings.append(
                Finding(
                    kind="file-vanished",
                    detail=(
                        f"{path} collected {was} test(s) at baseline and is no longer "
                        "collected at all"
                    ),
                )
            )
        elif now < was:
            findings.append(
                Finding(
                    kind="count-regression",
                    detail=(
                        f"{path} collected {now} test(s), down from {was} - "
                        f"{was - now} lost in this file even if the repository "
                        "total rose"
                    ),
                )
            )
    return findings


def _claim_parts(claim: object) -> tuple[str, tuple[str, ...]]:
    """Split a claim into (path, required fragments).

    Accepts a plain path or a mapping such as
    ``{"path": "a.py", "must_contain": ["def parse"]}``. A bare string keeps
    working unchanged, because ``verify(claimed_paths=[...])`` is quoted
    verbatim in ``CLAUDE.md`` and in all eight generated lane contracts - this
    feature is additive or it is a breaking change to nine documents.
    """
    if isinstance(claim, dict):
        path = str(claim.get("path", ""))
        required = claim.get("must_contain") or ()
        if isinstance(required, str):
            required = (required,)
        return path, tuple(str(r) for r in required)
    return str(claim), ()


def check_claimed_paths(
    paths: Iterable[object], root: Path = REPO_ROOT
) -> list[Finding]:
    """Confirm every claimed path is a non-empty file, and optionally that it
    actually contains what was claimed.

    Existence is a weak signal on its own. An agent that wrote a stub, edited
    the wrong file, or created the right filename with the wrong content passes
    an exists-and-is-non-empty check cleanly - which is precisely the shape of
    "the subagent said it did this and it did not". ``must_contain`` re-reads
    the file and asserts the claimed content is present, turning the claim into
    something the gate can actually refute.

    Fragments are matched as plain substrings, not regexes. A caller quoting a
    function signature should not have to escape it, and a regex typo would
    fail open.
    """
    findings: list[Finding] = []
    for claim in paths:
        raw, required = _claim_parts(claim)
        target = Path(raw)
        resolved = target if target.is_absolute() else root / target
        if not resolved.exists():
            findings.append(
                Finding(kind="missing", detail=f"{raw} was claimed but does not exist")
            )
            continue
        if not resolved.is_file():
            findings.append(
                Finding(kind="not-a-file", detail=f"{raw} exists but is not a file")
            )
            continue
        if resolved.stat().st_size == 0:
            findings.append(
                Finding(kind="empty", detail=f"{raw} exists but is zero bytes")
            )
            continue
        if not required:
            continue
        try:
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(
                Finding(kind="unreadable", detail=f"{raw} could not be read ({exc})")
            )
            continue
        findings.extend(
            Finding(
                kind="missing-content",
                detail=(
                    f"{raw} exists but does not contain {fragment!r} - the file "
                    "was delivered, the claimed work was not"
                ),
            )
            for fragment in required
            if fragment not in text
        )
    return findings


def _run(args: Sequence[str], root: Path, timeout: int) -> RunResult:
    """Run a command and return its output AND exit code, never raising.

    The exit code is not incidental. A pytest run that aborts can still print
    a plausible stats line, so the code is the only part of the answer the
    text cannot contradict.
    """
    proc = subprocess.run(
        list(args),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return RunResult(
        text=(proc.stdout or "") + (proc.stderr or ""),
        returncode=proc.returncode,
    )


def collect_result(root: Path = REPO_ROOT, timeout: int = 300) -> RunResult:
    """Run ``pytest --collect-only -q`` and return its output and exit code."""
    return _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], root, timeout)


def suite_result(root: Path = REPO_ROOT, timeout: int = 900) -> RunResult:
    """Run the full suite and return its output and exit code."""
    return _run([sys.executable, "-m", "pytest"], root, timeout)


def collect_output(root: Path = REPO_ROOT, timeout: int = 300) -> str:
    """Run ``pytest --collect-only -q`` and return its raw output."""
    return collect_result(root=root, timeout=timeout).text


def suite_output(root: Path = REPO_ROOT, timeout: int = 900) -> str:
    """Run the full suite and return its raw output."""
    return suite_result(root=root, timeout=timeout).text


#: Said in the report when the caller supplied no per-file baseline. Named as
#: a constant so the note and the docstring cannot drift apart.
_NO_PER_FILE_BASELINE_NOTE = (
    "the per-file regression check did not run - no per_file_baseline was "
    "supplied, so a file that lost tests stays invisible whenever another "
    "file gained more"
)


#: Said when there is no dispatch-time reading to compare against - ``OPS-58``
#: criterion 2. It never says the store held still, and that is the whole
#: point: an unqualified clean bill drawn from an empty record is the
#: ``OPS-53`` defect, an answer to a question the record cannot answer. The
#: wording also names the ritual, because "take a snapshot" is useless advice
#: without the call that takes it.
_NO_DRIFT_BASELINE_NOTE = (
    "the store-drift check (OPS-54) did not run - no dispatch-time reading of "
    "the object store was found at {where}, so whether the store shifted while "
    "these numbers were taken is UNKNOWN rather than settled; that reading is "
    "written by ops.loop.state.dispatch, and a session which skips the dispatch "
    "ritual leaves no baseline here at all"
)

#: Said when the detector could not even be consulted. Same shape as the note
#: above on purpose: from a reader's position "there was no reading" and "the
#: reader broke" are the same fact - the check did not run.
_DRIFT_UNAVAILABLE_NOTE = (
    "the store-drift check (OPS-54) did not run - it could not be consulted "
    "({why}), so whether the object store shifted while these numbers were "
    "taken is UNKNOWN rather than settled"
)

#: Default for the ``where`` wording. Deliberately NOT an absolute path: a
#: rendered report is pasted into notes and logs, and an absolute path on this
#: machine carries the account name.
_DEFAULT_DRIFT_WHERE = "the loop runtime directory"


def describe_store_drift(
    before: object | None,
    after: object | None,
    *,
    where: str = _DEFAULT_DRIFT_WHERE,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Turn a pair of store readings into ``(measurement lines, notes)``.

    Pure - it reads no repository and spawns no process, so the whole wiring
    is testable without a git tree. ``OPS-58`` criteria 2 and 3 live here:

    - ``before is None`` yields NO measurement and one ``[unchecked]`` note.
      It must never yield "the store did not move", because with one reading
      there is nothing that could have moved between two of them.
    - Otherwise the detector's own rendering is returned as measurement lines,
      which :meth:`GateReport.format` prints under
      :data:`MEASUREMENT_HEADER` rather than among the findings.

    A comparison built on a failed probe renders its own ``COULD NOT ANSWER``
    banner and stays in the measurement channel: it is still a statement about
    the measurement rather than about the work.
    """
    if before is None:
        return (), (_NO_DRIFT_BASELINE_NOTE.format(where=where),)
    try:
        from ops import store_drift
    except Exception as exc:  # pragma: no cover - covered by read_store_drift
        return (), (_DRIFT_UNAVAILABLE_NOTE.format(why=f"{type(exc).__name__}: {exc}"),)
    report = store_drift.compare(before, after)
    lines = [f"readings: dispatch {before.at} -> merge {after.at}"]
    lines.extend(report.format().splitlines())
    return tuple(lines), ()


def read_store_drift(
    root: Path = REPO_ROOT, snapshot_path: Path | None = None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Load the dispatch-time reading, take a second one, and describe the gap.

    **This never raises, for any reason at all** - ``OPS-58`` criterion 6. The
    gate is consulted at merge time and a merger who cannot run the gate stops
    running it, at which point the claim goes unchecked AND the drift goes
    unwatched. Every failure below becomes a note saying the check did not run:

    - the detector or the loop state module cannot be imported at all
    - the stored reading is absent, truncated or of the wrong shape
    - git is missing, the directory is not a repository, a probe times out

    The second reading is taken by the CALLER as late as it can be - see
    :func:`verify`, which takes it after the suite has run, so the window it
    covers is the whole measurement rather than a slice of the front of it.
    """
    try:
        from ops import store_drift
        from ops.loop import state as loop_state
    except Exception as exc:
        return (), (_DRIFT_UNAVAILABLE_NOTE.format(why=f"{type(exc).__name__}: {exc}"),)

    try:
        base = Path(root)
        if snapshot_path is None:
            # The runtime directory's position is derived from the loop state
            # module rather than spelled again here, so "ops/runtime" has one
            # definition and cannot drift into two.
            relative = loop_state.runtime_dir().relative_to(loop_state.REPO_ROOT)
            target = loop_state.store_snapshot_path(
                base / relative / loop_state.STATE_FILENAME
            )
        else:
            target = Path(snapshot_path)
        try:
            where = target.relative_to(base).as_posix()
        except ValueError:
            where = target.name

        before = loop_state.load_store_snapshot(target)
        if before is None:
            return describe_store_drift(None, None, where=where)
        return describe_store_drift(before, store_drift.snapshot(base), where=where)
    except Exception as exc:
        return (), (_DRIFT_UNAVAILABLE_NOTE.format(why=f"{type(exc).__name__}: {exc}"),)


def verify(
    claimed_paths: Iterable[str | Path] = (),
    baseline: int | None = None,
    root: Path = REPO_ROOT,
    per_file_baseline: Mapping[str, int] | None = None,
    snapshot_path: Path | None = None,
) -> GateReport:
    """Run every probe and compose the verdict.

    This actually executes the suite. It is the slow, honest path - the point
    of the module is that the merger measures rather than relays.

    Measure both baselines from ONE collect run before dispatching work, and
    pass what you measured::

        before = merge_gate.parse_collect_counts(merge_gate.collect_output())
        # ... dispatch the work, then ...
        report = merge_gate.verify(
            claimed_paths=["the/file/it/said/it/wrote.py"],
            baseline=sum(before.values()),
            per_file_baseline=before,
        )

    Both are parameters and neither may become a stored constant: a count
    checked into the repository goes stale and becomes a confident lie.

    **A gate that reports OK after checking nothing is the exact failure this
    module exists to prevent**, so the two weak defaults are loud rather than
    silent. Both were recorded as structural holes under ``ROADMAP`` item
    ``OPS-31`` and neither was reachable by re-running anything:

    ``claimed_paths`` empty
        Draws a ``no-claims`` finding. The file probe examined zero files,
        which proves nothing about delivery, and it used to say so nowhere -
        the caller got ``ok=True`` from a probe that had looked at nothing.
    ``per_file_baseline`` absent
        Leaves :func:`check_per_file_counts` unrun, which is recorded in
        ``GateReport.notes`` and rendered by :meth:`GateReport.format` even on
        an OK report. That function was exported, documented and NEVER CALLED
        until this wiring landed. It is a NOTE rather than a finding on
        purpose: the invocation quoted in ``CLAUDE.md`` and in all eight
        generated lane contracts passes only ``claimed_paths`` and
        ``baseline``, so making it a finding would turn the documented call
        permanently red, and a gate that always says no is a gate nobody
        reads.

    **Store drift is reported, never blocked on** - ``OPS-58``. The readings
    above are only worth what the tree they were taken on is worth, and a
    parallel slice running ``git stash`` moves that tree wholesale. The gap
    between the dispatch-time reading and one taken here goes into
    ``GateReport.measurement``, printed under :data:`MEASUREMENT_HEADER` and
    kept out of ``findings``: it says the numbers were taken on a moving
    target, not that the work is wrong.

    ``snapshot_path`` overrides where the dispatch-time reading is looked for;
    by default it is the one :func:`ops.loop.state.dispatch` writes under
    ``root``. **When there is none, the report says the check did not run.** It
    does not say there was no drift - the dispatch ritual is a ritual, nothing
    calls it for anyone, and a gate that answered "no drift" from an empty
    record would be asserting something its record cannot support.

    **The limit this cannot fix, named rather than hidden.** Every baseline is
    supplied by the very caller whose work is under test. Nothing here holds
    an independent record of the count before the work started, and
    re-deriving one now would compare the tree against itself, which is
    vacuous. The gate can refuse a MISSING baseline; it cannot refuse one that
    was quietly lowered. ``no-claims`` is satisfiable the same way - by
    claiming a path that already existed and was never touched.
    """
    claims = list(claimed_paths)
    findings: list[Finding] = []
    notes: list[str] = []

    if not claims:
        findings.append(
            Finding(
                kind="no-claims",
                detail=(
                    "no claimed paths were supplied, so the file probe examined 0 "
                    "files and proved nothing about delivery - name the files the "
                    "agent said it wrote"
                ),
            )
        )
    findings.extend(check_claimed_paths(claims, root=root))

    # One collect run feeds both count checks. The total is the SUM of the
    # per-file lines - pytest prints no grand total - so re-running collect for
    # the second check could only introduce a disagreement.
    #
    # A collect pass that dies returns no per-file lines, so the total comes
    # back as 0 and check_test_count reports the drop. That is why there is no
    # separate exit-code probe here: the count guard already refuses it, and
    # with no baseline the no-baseline finding refuses it instead.
    per_file = parse_collect_counts(collect_output(root=root))
    collected = sum(per_file.values())
    findings.extend(check_test_count(collected, baseline))

    if per_file_baseline is None:
        notes.append(_NO_PER_FILE_BASELINE_NOTE)
    else:
        findings.extend(check_per_file_counts(per_file, dict(per_file_baseline)))

    run = suite_result(root=root)
    summary = parse_summary(run.text)
    findings.extend(check_run_completed(run, summary))

    # LAST, deliberately. The second store reading is taken after the suite has
    # run, so the interval it covers is the whole measurement rather than the
    # front of it - the collect pass and the suite are exactly the long window
    # in which a sibling slice has time to stash. ``OPS-58``.
    measurement, drift_notes = read_store_drift(root=root, snapshot_path=snapshot_path)
    notes.extend(drift_notes)

    return GateReport(
        ok=not findings,
        findings=tuple(findings),
        collected=collected,
        summary=summary,
        notes=tuple(notes),
        measurement=tuple(measurement),
    )
