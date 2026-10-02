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

import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "COLLECTION_ENV_VARS",
    "Finding",
    "GateReport",
    "MEASUREMENT_HEADER",
    "RunResult",
    "SummaryResult",
    "check_baseline_floor",
    "check_claimed_paths",
    "check_skip_count",
    "describe_store_drift",
    "read_store_drift",
    "check_per_file_counts",
    "check_run_completed",
    "check_test_count",
    "child_env",
    "collect_output",
    "collect_result",
    "describe_env_sanitisation",
    "find_summary_line",
    "parse_collect_counts",
    "parse_summary",
    "selection_flags_in",
    "suite_output",
    "suite_result",
    "take_per_file_baseline",
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
_SKIPPED_RE = re.compile(r"(?<!\w)(\d+) skipped(?!\w)")
_DESELECTED_RE = re.compile(r"(?<!\w)(\d+) deselected(?!\w)")

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


#: Environment variables that change WHAT pytest collects or runs, stripped from
#: every child this module spawns.
#:
#: THE DEFECT THIS CLOSES, measured in the primary working tree. ``_run`` used to
#: inherit the parent environment wholesale, so an ambient ``PYTEST_ADDOPTS``
#: narrowed the gate's own measurement with exit code 0 and no warning at all:
#: 86 files and 4065 tests with nothing set, 1 file and 5 tests under
#: ``PYTEST_ADDOPTS="-k test_ascii_hygiene"``. The count comparison is then
#: satisfied over a suite that never ran, because the baseline and the re-run are
#: narrowed EQUALLY and the per-file floor self-adjusts to the narrowed
#: selection. ``CLAUDE.md``'s whole description of this gate is that it "fails if
#: the collected test count dropped below the baseline" - there the baseline
#: itself was being set by the environment.
#:
#: It is the same class as the ``-q``-in-``addopts`` trap ``CLAUDE.md`` already
#: records, on a different axis: an environment variable instead of an ini file.
#: A sibling project reported the same class and theirs went RED; this one went
#: silently GREEN, which is strictly worse.
#:
#: ``-k``, ``-m``, ``-p``, ``-x``, ``--deselect`` and ``--ignore`` all arrive
#: through ``PYTEST_ADDOPTS``, so removing the variable removes every one of them
#: and there is no flag denylist to keep in step with pytest.
PYTEST_ENV_VARS: frozenset[str] = frozenset(
    {
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_DEBUG",
    }
)

#: Variables that change what a child PRINTS rather than what it runs, which
#: matters here because every verdict in this module is parsed out of text.
#: ``FORCE_COLOR`` wraps a summary line in ANSI escapes and
#: ``RUFF_OUTPUT_FORMAT`` replaces the lint summary wholesale, and a parser that
#: finds neither reports "no summary line" - a finding about the environment
#: wearing the costume of a finding about the work.
OUTPUT_ENV_VARS: frozenset[str] = frozenset(
    {"FORCE_COLOR", "CLICOLOR_FORCE", "RUFF_OUTPUT_FORMAT"}
)

#: The whole stripped set. One definition, consulted by ``ops/preflight.py``,
#: ``ops/stop_audit.py`` and ``tools/preflight_backtest.py`` as well, because a
#: fix closed in one call site is not closed - all four spawn a child and all
#: four inherited the environment.
COLLECTION_ENV_VARS: frozenset[str] = PYTEST_ENV_VARS | OUTPUT_ENV_VARS

#: Flags that narrow a run, named so a report can say HOW an inherited value was
#: dangerous. Only the flag is ever echoed and never its argument: a value can
#: carry an absolute path, which on this machine carries the account name, and
#: ``ADR-004`` scopes redaction to a CLASS OF DATA and a DIRECTION rather than to
#: the game log.
SELECTION_FLAGS: tuple[str, ...] = (
    "--deselect",
    "--ignore",
    "--last-failed",
    "--lf",
    "-k",
    "-m",
    "-p",
    "-x",
)


def selection_flags_in(value: str) -> tuple[str, ...]:
    """Selection-narrowing flags present in an addopts-shaped string.

    Used for the WORDING of the report, never for the decision - the decision is
    to remove the variable whatever it holds, so a flag this list has never heard
    of cannot slip through. Returns flag names only; the argument beside a flag is
    never echoed anywhere.
    """
    found = [
        flag
        for flag in SELECTION_FLAGS
        if re.search(rf"(?:^|\s){re.escape(flag)}(?:[=\s]|$)", value or "")
    ]
    return tuple(found)


def child_env(
    base: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tuple[str, ...]]:
    """A copy of ``base`` with :data:`COLLECTION_ENV_VARS` removed.

    Returns ``(environment, stripped names)``. The second half is the whole
    reason this is not a one-line ``dict`` comprehension at each call site: a
    sanitisation nobody can see is a measurement condition nobody recorded, and
    this repository's rule is that a caveat dropped from the artifact is a lie in
    the artifact.

    **SANITISE AND REPORT, rather than refuse.** Both were available and the
    choice is argued from this repository's own rules. Refusing to run would make
    the gate unavailable at exactly the moment it is needed - the same reasoning
    that makes :func:`read_store_drift` never raise, because a merger who cannot
    run the gate stops running it and then the claim goes unchecked too - and an
    ambient ``PYTEST_ADDOPTS`` is a legitimate thing for an operator's shell to
    carry, so refusing on it is a guard that cries wolf and gets overridden.
    Sanitising silently is the other failure: a guard that goes green while the
    conditions changed under it is decoration. So the hazard is REMOVED and the
    removal is STATED, in :attr:`GateReport.measurement`, where a reader can tell
    a 4065 from a 5.

    ``base`` defaults to the real environment. Tests pass an explicit mapping,
    because a test that reads the ambient shell is measuring the shell.

    The copy keeps everything else - ``PATH``, ``SYSTEMROOT``, ``TEMP``. Handing
    a child an environment stripped to just the safe names breaks process
    creation on Windows, which is a cure worse than the disease.
    """
    source = dict(os.environ if base is None else base)
    stripped = tuple(sorted(name for name in COLLECTION_ENV_VARS if name in source))
    for name in stripped:
        del source[name]
    return source, stripped


#: One rendered line per stripped variable. The NAME is given, the VALUE never
#: is - see :data:`SELECTION_FLAGS`.
_ENV_STRIPPED_LINE = (
    "environment: {name} was set and was REMOVED before the child ran{how} - "
    "an inherited value here narrows the measurement silently, with exit code 0"
)


def describe_env_sanitisation(
    stripped: Sequence[str], values: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Measurement lines for what :func:`child_env` removed. Pure.

    Empty when nothing was stripped, which keeps the measurement block from
    becoming furniture a reader stops seeing - the same reason
    :data:`MEASUREMENT_HEADER` is printed only when there is something under it.
    """
    source = dict(os.environ if values is None else values)
    lines: list[str] = []
    for name in stripped:
        flags = selection_flags_in(source.get(name, ""))
        how = f", and it carried {', '.join(flags)}" if flags else ""
        lines.append(_ENV_STRIPPED_LINE.format(name=name, how=how))
    return tuple(lines)


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

    ``found`` is the field that matters. When it is ``False`` every count is
    ``None`` rather than ``0``, because "the suite printed no summary" and "the
    suite ran and nothing passed" are different facts and only one of them means
    the run happened.

    ``skipped`` and ``deselected`` are the two ways the population that RAN is
    smaller than the population that was COLLECTED, and the gate was blind to
    both. ``check_test_count`` floors on the collected count, which neither of
    them changes, so a lane could mark 30 tests skipped and the gate stayed
    green. Measured here before the fix: ``check_run_completed`` on a summary
    reading ``12 passed, 30 skipped in 1.00s`` with returncode 0 returned ``[]``.

    Not hypothetical in this repository. The same tree gives 3896 passed and 22
    skipped under Git Bash, and 3833 passed and 85 skipped under PowerShell,
    because PowerShell's ``PATH`` lacks Git's ``usr/bin`` - 62 tests stop running
    and the run still exits 0.
    """

    found: bool
    passed: int | None
    failed: int | None
    errors: int | None
    skipped: int | None = None
    deselected: int | None = None


@dataclass(frozen=True)
class RunResult:
    """The two things a pytest invocation tells you, kept together.

    Text alone is not enough. A run that aborts can still print a plausible
    stats line, so the exit code is carried alongside it rather than discarded
    - it is the only witness the output cannot contradict.
    """

    text: str
    returncode: int
    stripped_env: tuple[str, ...] = ()


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
    "  a finding above says the work may be wrong; a line below says HOW the "
    "numbers above were taken - on a moving tree, from a sanitised environment, "
    "over which population - which changes what you check next rather than "
    "whether you merge",
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
        return SummaryResult(
            found=False,
            passed=None,
            failed=None,
            errors=None,
            skipped=None,
            deselected=None,
        )
    passed = _PASSED_RE.search(stats)
    failed = _FAILED_RE.search(stats)
    errors = _ERROR_RE.search(stats)
    skipped = _SKIPPED_RE.search(stats)
    deselected = _DESELECTED_RE.search(stats)
    return SummaryResult(
        found=True,
        passed=int(passed[1]) if passed else 0,
        failed=int(failed[1]) if failed else 0,
        errors=int(errors[1]) if errors else 0,
        skipped=int(skipped[1]) if skipped else 0,
        deselected=int(deselected[1]) if deselected else 0,
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
    if resolved.deselected:
        findings.append(
            Finding(
                kind="deselected",
                detail=(
                    f"{resolved.deselected} test(s) were DESELECTED, so the run "
                    "executed a smaller population than it collected - this module "
                    "passes no -k or -m and strips the variables that can inject "
                    "one, and pytest.ini carries neither, so nothing legitimate "
                    "explains a deselection here"
                ),
            )
        )
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


def check_skip_count(current: int | None, baseline: int | None) -> list[Finding]:
    """Fail when more tests SKIPPED than the baseline recorded.

    THE DECISION, because both alternatives were defensible and the middle has to
    be argued rather than assumed. A skip is not a defect: this repository skips
    22 tests legitimately, by design, through ``tests/_toolguard.py``, so making
    any skip a finding would turn every honest run red and a guard that always
    says no is a guard nobody reads. Silence is the other end, and silence is
    what was here: 62 tests stopped running under PowerShell and the gate
    reported success.

    So the skipped count is ALWAYS REPORTED - it reaches
    :attr:`GateReport.measurement` on every run, including an OK one, which is
    what makes it unable to hide again - and a RISE is a finding only against a
    baseline the caller measured and supplied. That keeps the red tied to a
    specific before-and-after a human chose to assert, rather than to an
    environment difference the gate cannot interpret. With no baseline the check
    did not run, which is recorded as a note: a check that did not run has not
    passed, and the absence must not read as a measured zero.

    ``current is None`` means the suite printed no summary at all. That is
    :func:`check_run_completed`'s ``no-summary`` finding, not a skip story, so
    nothing is added here - reporting it twice would make a crashed run and a
    skipped test indistinguishable in one report.
    """
    if baseline is None or current is None:
        return []
    if current > baseline:
        return [
            Finding(
                kind="skip-regression",
                detail=(
                    f"{current} test(s) skipped, up from a baseline of {baseline} - "
                    f"{current - baseline} test(s) collected and then did not run; "
                    "the collected count is unchanged by a skip, so no count guard "
                    "can see this"
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


def check_baseline_floor(
    baseline: Mapping[str, int], tree: Mapping[str, int]
) -> list[Finding]:
    """Refuse a per-file floor that already sits BELOW the working tree.

    ``ROADMAP`` item ``OPS-95`` item 2, measured on 2026-09-16. A per-file
    baseline for this repository was derived in a detached worktree AT HEAD.
    The worktree was sound - a control reproduced HEAD exactly across seventy
    files, and the only two that differed from the primary tree were
    modified-but-uncommitted test files whose deltas summed to the whole gap.
    The defect is the CHOICE OF TREE, and it is not specific to worktrees: any
    route that measures HEAD while uncommitted test work exists has it.

    What it costs is a floor that gives coverage away before the work starts.
    The measured instance would have handed :func:`check_per_file_counts` a
    floor of 46 for a file the working tree already held at 60, so a lane could
    have deleted 13 of the tests it added in the same session and still passed
    the per-file check - the exact failure that check exists to prevent, one
    level down.

    Two accidents, kept apart because their fixes differ:

    ``stale-baseline``
        The floor for a file is lower than what the tree collects. Every test
        between the two numbers is unprotected.
    ``baseline-missing-file``
        The tree collects a file the baseline has no row for at all.
        :func:`check_per_file_counts` treats an unknown file as NEW and
        therefore clean, which is correct when the baseline came from this tree
        and wrong when it did not: there the whole file is unprotected rather
        than part of it.

    A floor ABOVE the tree is not reported here. That is an ordinary
    regression, it is :func:`check_per_file_counts`'s answer at merge time, and
    reporting it in both places would make a deleted test and a mis-taken
    baseline indistinguishable in one report.

    **Call this when the floor is TAKEN, not at merge time.** After the work,
    ``baseline < current`` is the healthy case - it is what a lane that added
    tests looks like - so the same inequality is evidence of nothing then. It
    is evidence of a stale floor only in the window before anything has been
    written, which is why :func:`verify` does not call it and the dispatch
    ritual does.
    """
    findings: list[Finding] = []
    for path, now in sorted(tree.items()):
        was = baseline.get(path)
        if was is None:
            findings.append(
                Finding(
                    kind="baseline-missing-file",
                    detail=(
                        f"{path} collects {now} test(s) in the working tree and has no "
                        "row in the baseline at all - an unknown file is treated as NEW "
                        "and therefore clean, so all "
                        f"{now} are unprotected; this baseline was not measured in this "
                        "tree"
                    ),
                )
            )
        elif was < now:
            findings.append(
                Finding(
                    kind="stale-baseline",
                    detail=(
                        f"{path} has a floor of {was} but the working tree already "
                        f"collects {now} - the floor gives away {now - was} test(s) "
                        "before any work starts; measure the baseline in the PRIMARY "
                        "WORKING TREE immediately before dispatch, never at HEAD"
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

    **The environment is SANITISED and never inherited whole.** See
    :func:`child_env` for the measured defect and for why sanitising-and-
    reporting beat refusing. What was removed travels back on the
    :class:`RunResult`, so the report can say it rather than leave a reader to
    guess whether a count of 5 was the suite or the selection.
    """
    env, stripped = child_env()
    proc = subprocess.run(
        list(args),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    return RunResult(
        text=(proc.stdout or "") + (proc.stderr or ""),
        returncode=proc.returncode,
        stripped_env=stripped,
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


def take_per_file_baseline(root: Path = REPO_ROOT, timeout: int = 300) -> dict[str, int]:
    """Measure the per-file floor in the tree at ``root``, whatever is on disk.

    The sanctioned way to take the baseline, and it exists so the rule has one
    call rather than a ritual. ``root`` defaults to the PRIMARY WORKING TREE -
    the checkout this module lives in - and collection reads the files as they
    are, uncommitted edits included.

    That is the whole point. ``ROADMAP`` item ``OPS-95`` item 2: a floor
    measured at HEAD, in a detached worktree or anywhere else that ignores
    uncommitted test work, is already below the tree it will be compared
    against and hands coverage away before dispatch. Pass this to
    :func:`check_baseline_floor` alongside a baseline of unknown provenance to
    find out whether that happened.

    The total is the sum of these counts, so one call still feeds both count
    checks and there is no second collect to disagree with.

    **The hazard in :func:`child_env` is at its worst here**, which is why this
    function says out loud when it fired. A narrowed collect does not merely
    lower a floor, it leaves the dropped files with NO ROW at all, and
    :func:`check_per_file_counts` treats a file it has no row for as NEW and
    therefore clean - so the whole file is unprotected rather than part of it. A
    one-file floor measured under ``PYTEST_ADDOPTS="-k ..."`` against an 86-file
    tree protects nothing whatever while looking exactly like a floor.

    The child's environment is sanitised, so the returned floor covers the whole
    tree. The notice goes to stderr because this function's contract is a plain
    ``dict`` and has nowhere to put a note - and because an operator whose
    deliberate ``PYTEST_ADDOPTS`` was ignored should be told, not left to
    discover it from a count. It is a notice rather than a refusal for the reason
    argued in :func:`child_env`: the floor it returns is correct, so refusing
    would be crying wolf over a hazard that has already been removed.
    """
    run = collect_result(root=root, timeout=timeout)
    if run.stripped_env:
        for line in describe_env_sanitisation(run.stripped_env):
            print(f"take_per_file_baseline: {line}", file=sys.stderr)
    return parse_collect_counts(run.text)


#: Said when no skip baseline was supplied. A NOTE and not a finding, for the
#: same reason ``_NO_PER_FILE_BASELINE_NOTE`` is one: the invocation quoted in
#: ``CLAUDE.md`` and in all eight generated lane contracts passes neither, so a
#: finding would turn the documented call permanently red and a gate that always
#: says no is a gate nobody reads. The skipped count itself is reported
#: unconditionally in the measurement block, so the number is never silent even
#: when this comparison cannot be made.
_NO_SKIP_BASELINE_NOTE = (
    "the skip-regression check did not run - no skip_baseline was supplied, so "
    "whether MORE tests collected-and-then-skipped than before is UNKNOWN rather "
    "than settled; measure it with parse_summary(suite_result().text).skipped "
    "before dispatching work. The skipped count for THIS run is in the "
    "measurement block below and a skip does not move the collected count, so no "
    "count guard above can see one"
)


def _coverage_lines(
    collected: int,
    files: int,
    summary: SummaryResult,
    per_file_baseline: Mapping[str, int] | None,
) -> tuple[str, ...]:
    """The provenance of the numbers this report compared.

    ``CLAUDE.md``: a filed count is a hypothesis and every count re-derived from
    the artifact has been wrong at least once. A bare ``3918`` and a bare ``93``
    render identically as "N tests collected", and that is exactly the pair of
    numbers the ``PYTEST_ADDOPTS`` defect produced from the same tree. So the
    report states the population it measured - how many tests in how many files -
    how many files the floor it compared against covered, and how the suite
    ACCOUNTED for that population once it ran.

    The accounting line is where a skip stops being invisible. ``collected`` minus
    passed minus failed is the number of collected tests that produced no result
    at all, and it is printed whether or not anybody supplied a skip baseline.
    """
    lines = [
        f"population: collect found {collected} test(s) in {files} file(s)",
    ]
    if per_file_baseline is None:
        lines.append(
            "floor: no per-file baseline was supplied, so nothing was compared "
            "file by file"
        )
    else:
        lines.append(
            f"floor: the baseline covered {len(per_file_baseline)} file(s) "
            f"totalling {sum(per_file_baseline.values())} test(s)"
        )
    if not summary.found:
        lines.append(
            "accounting: the suite printed no summary line, so what became of "
            "those tests is unknown"
        )
        return tuple(lines)
    passed = summary.passed or 0
    failed = summary.failed or 0
    skipped = summary.skipped or 0
    deselected = summary.deselected or 0
    unaccounted = collected - passed - failed
    lines.append(
        f"accounting: the suite reported {passed} passed, {failed} failed, "
        f"{skipped} skipped, {deselected} deselected - "
        f"{unaccounted} of the {collected} collected test(s) produced no pass or "
        "fail, and a skip never moves the collected count the guards above "
        "compare"
    )
    return tuple(lines)


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
    skip_baseline: int | None = None,
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

    **Both baselines are measured in the PRIMARY WORKING TREE immediately
    before dispatch, never at HEAD when uncommitted work exists** - ``OPS-95``
    item 2. The call above does that by default, because ``collect_output``
    reads the files as they are on disk in the checkout this module lives in;
    :func:`take_per_file_baseline` is the same measurement under a name that
    says so. A floor taken at HEAD, in a detached worktree, or from a stored
    reading is already BELOW the tree it will be compared against whenever
    uncommitted test work exists, and the gap is coverage handed away before
    the work starts: the measured instance would have given a file a floor of
    46 that the working tree held at 60, letting a lane delete 13 of its own
    new tests and still pass :func:`check_per_file_counts`. When the floor's
    provenance is not certain, run :func:`check_baseline_floor` against a fresh
    :func:`take_per_file_baseline` BEFORE dispatching. It is not checked here,
    and that is deliberate rather than an omission: after the work
    ``baseline < current`` is what a lane that added tests looks like, so the
    inequality carries no signal at merge time.

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

    **The environment is sanitised before any child runs, and the sanitisation
    is reported.** ``PYTEST_ADDOPTS`` and its relatives narrow collection with
    exit code 0, and because they narrow the baseline measurement and the merge
    re-run EQUALLY, every count comparison above is satisfied over a suite that
    did not run. Measured in this tree: 86 files and 4065 tests clean, 1 file and
    5 tests under ``-k test_ascii_hygiene``, and an OK verdict against the
    baseline of 5 that the same contamination produced. See :func:`child_env`
    for why the answer is sanitise-and-report rather than refuse.

    **The population that RAN is reported too, which is the other half of the
    same hole.** A test that collects and then SKIPS leaves the collected count
    untouched, so ``check_test_count`` and ``check_per_file_counts`` are both
    blind to it - and this is a measured local hazard rather than a theory: the
    same tree gives 22 skips under Git Bash and 85 under PowerShell. The counts
    now reach the measurement block on every run, and a RISE is a finding only
    against ``skip_baseline``, which the caller measures and supplies. See
    :func:`check_skip_count` for that argument.

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
    collect = collect_result(root=root)
    per_file = parse_collect_counts(collect.text)
    collected = sum(per_file.values())
    findings.extend(check_test_count(collected, baseline))

    if per_file_baseline is None:
        notes.append(_NO_PER_FILE_BASELINE_NOTE)
    else:
        findings.extend(check_per_file_counts(per_file, dict(per_file_baseline)))

    run = suite_result(root=root)
    summary = parse_summary(run.text)
    findings.extend(check_run_completed(run, summary))

    if skip_baseline is None:
        notes.append(_NO_SKIP_BASELINE_NOTE)
    else:
        findings.extend(check_skip_count(summary.skipped, skip_baseline))

    # Provenance FIRST in the measurement block, because it is what tells a
    # reader whether the numbers in the verdict line describe the suite or a
    # selection of it. Both children are sanitised, and both are reported: the
    # collect pass and the suite run are separate processes and an environment
    # can change between them.
    conditions: list[str] = list(
        _coverage_lines(collected, len(per_file), summary, per_file_baseline)
    )
    for stage, stripped in (("collect", collect.stripped_env), ("suite", run.stripped_env)):
        conditions.extend(
            f"{stage}: {line}" for line in describe_env_sanitisation(stripped)
        )

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
        measurement=tuple(conditions) + tuple(measurement),
    )
