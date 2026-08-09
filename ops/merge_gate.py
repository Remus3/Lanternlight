"""Re-probe an agent's claims instead of believing its report.

This module exists because of one specific, repeated failure: a subagent
reports that it wrote a file, added a test and left the suite green, the
merger relays that, and none of it is true - or it is true in a way that hides
a regression. ``CLAUDE.md`` already states the rule ("never trust a subagent's
claim"), but a rule that lives only in prose is a rule that gets skipped at
exactly the moment it matters. This is the mechanical version.

Three probes, each aimed at a distinct way a "done" claim goes wrong.

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

**The suite did not actually run.** :func:`parse_summary` distinguishes "no
summary line was printed" from "zero tests passed". Those are different facts,
and a gate that conflates them will approve a run that crashed during
collection.

The baseline is deliberately a **parameter, not a stored constant.** A count
checked into the repo goes stale and becomes a confident lie - ``CLAUDE.md``
forbids restating suite counts for exactly that reason. The caller measures
the count before dispatching work and passes what it measured.

Every output shape parsed here was measured on this machine on 2026-08-09.
Two of them break naive parsing and are the reason this module does not simply
call ``str.splitlines()`` and index:

- pytest's lines are **CR-terminated** here, and the final summary line has no
  trailing newline at all
- ``--collect-only -q`` prints a per-file ``path: count`` list and **no grand
  total**, so the total must be summed

Nothing here shells out unless you ask it to: the parsers are pure functions
over text, so they are testable without running a suite inside a suite.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Finding",
    "GateReport",
    "SummaryResult",
    "check_claimed_paths",
    "check_per_file_counts",
    "check_test_count",
    "collect_output",
    "parse_collect_counts",
    "parse_summary",
    "suite_output",
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
class GateReport:
    """The composed verdict. ``ok`` is true only when nothing was found."""

    ok: bool
    findings: tuple[Finding, ...]
    collected: int | None
    summary: SummaryResult | None

    def format(self) -> str:
        """Render the report for a human, one finding per line."""
        if self.ok:
            return f"merge gate: OK ({self.collected} tests collected)"
        lines = [f"merge gate: {len(self.findings)} finding(s)"]
        lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
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


def parse_summary(text: str) -> SummaryResult:
    """Read pytest's final summary line.

    Handles the measured local shape - CR-terminated, no trailing newline -
    and returns ``found=False`` with ``None`` counts when no summary was
    printed at all.
    """
    blob = text or ""
    passed = _PASSED_RE.search(blob)
    failed = _FAILED_RE.search(blob)
    errors = _ERROR_RE.search(blob)
    if passed is None and failed is None and errors is None:
        return SummaryResult(found=False, passed=None, failed=None, errors=None)
    return SummaryResult(
        found=True,
        passed=int(passed[1]) if passed else 0,
        failed=int(failed[1]) if failed else 0,
        errors=int(errors[1]) if errors else 0,
    )


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


def check_claimed_paths(
    paths: Iterable[str | Path], root: Path = REPO_ROOT
) -> list[Finding]:
    """Confirm every path an agent claimed to deliver is a non-empty file."""
    findings: list[Finding] = []
    for raw in paths:
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
    return findings


def _run(args: Sequence[str], root: Path, timeout: int) -> str:
    """Run a command and return stdout+stderr, never raising on exit code."""
    proc = subprocess.run(
        list(args),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def collect_output(root: Path = REPO_ROOT, timeout: int = 300) -> str:
    """Run ``pytest --collect-only -q`` and return its raw output."""
    return _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], root, timeout)


def suite_output(root: Path = REPO_ROOT, timeout: int = 900) -> str:
    """Run the full suite and return its raw output."""
    return _run([sys.executable, "-m", "pytest"], root, timeout)


def verify(
    claimed_paths: Iterable[str | Path] = (),
    baseline: int | None = None,
    root: Path = REPO_ROOT,
) -> GateReport:
    """Run every probe and compose the verdict.

    This actually executes the suite. It is the slow, honest path - the point
    of the module is that the merger measures rather than relays.
    """
    findings: list[Finding] = list(check_claimed_paths(claimed_paths, root=root))

    collected = total_collected(collect_output(root=root))
    findings.extend(check_test_count(collected, baseline))

    summary = parse_summary(suite_output(root=root))
    if not summary.found:
        findings.append(
            Finding(
                kind="no-summary",
                detail=(
                    "pytest printed no summary line - the suite did not complete, "
                    "which is not the same as completing with zero passes"
                ),
            )
        )
    else:
        if summary.failed:
            findings.append(
                Finding(kind="failed", detail=f"{summary.failed} test(s) failed")
            )
        if summary.errors:
            findings.append(
                Finding(kind="errors", detail=f"{summary.errors} test error(s)")
            )

    return GateReport(
        ok=not findings,
        findings=tuple(findings),
        collected=collected,
        summary=summary,
    )
