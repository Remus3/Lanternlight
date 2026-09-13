"""What one refute-fix-refute cycle has cost this repository so far.

``OPS-87`` criterion 4 - "Record how many full-suite runs and how much wall
clock a cycle takes today, and the same numbers after. Both measured, neither
estimated." This module is the BEFORE half. It derives every figure it prints
from git history and the ledger AT RUN TIME. Nothing here is a constant checked
into a file, because a count checked into a file goes stale and becomes a
confident lie - this repository's own rule, and the reason ``ops/preflight.py``
had to stop printing its caveat from string literals (``LL-0241``).

WHAT A CYCLE IS, pinned here so nothing downstream has to re-invent it.
A cycle is ONE complete refute-fix-refute round on ONE roadmap item: the commit
that claims the item done, plus every later commit that exists because an
adversarial pass found something in it. It is deliberately not "a session" and
not "a day" - the unit ``OPS-87`` is complaining about is the round trip.

WHICH GIT DATE, AND WHY. COMMITTER date, ``%ct``. Author date is preserved
across a rebase or a cherry-pick and therefore answers "when was this work first
written", which is a different question from the one being asked. Committer date
answers "when did this commit enter this history", and the cost being measured is
elapsed real time spent on the round trip in this tree. The two are identical for
every commit in the current window, so the choice costs nothing today and stops
meaning drifting the first time a branch is replayed.

WHAT IS DERIVABLE AND WHAT IS NOT, established by measurement before this module
was designed, because the answer changed the design:

* WALL CLOCK is derivable exactly. Commit timestamps are in the object.
* SUITE-RUN COUNT IS NOT IN GIT and is not recorded anywhere else today. What
  the artifact does carry is that commit messages, ledger entries and the
  hand-off routinely QUOTE a full-suite result - "3274 passed", "3275 collected
  across 67 files". Each DISTINCT quoted result is evidence of at least one real
  full-suite run. So what this module reports is a FLOOR and it is printed as
  ``>=`` everywhere it appears. A floor stated as a count is a lie, and
  ``docs/REFUTATION_CENSUS.md`` words its own bounds the same way.
* COLLECT-ONLY FIGURES ARE NOT RUNS. ``3275 collected`` is evidence that
  ``--collect-only`` was run, which costs a second rather than six minutes, so
  those figures are reported beside the floor and never inside it.

* AN ADDED LINE IS NOT ALWAYS THE COMMIT'S OWN WORK. A document
  reorganisation re-adds history: the ``OPS-57`` split created
  ``docs/LEDGER_ARCHIVE.md`` and so "added" every historical entry in one
  commit, which read naively gave a two-commit cycle a floor of 70 suite runs
  and invented three cycles out of archived headings. See
  :func:`attributable_lines` - this was found by RUNNING the instrument, not by
  reasoning about it beforehand.

THE ANCHOR, AND HOW LITTLE OF IT THERE IS. ``docs/LEDGER.md`` contains exactly
two sentences that link a fix commit to the commit it refuted by sha - the
phrase "refutation pass over <sha>" in ``LL-0245`` and in ``LL-0241``. Two is
not a corpus. A parser built on that phrase alone would reach almost nothing, so
the anchored links are used as the HIGH-CONFIDENCE SEED and the rest of each
cycle is assembled by grouping commits that name the same ``OPS-nn`` id. That
grouping is weaker on purpose and the report says so in its own output.

WHERE THE GROUPING IDS ARE ALLOWED TO COME FROM. The commit SUBJECT, and the
heading line of any ledger entry the commit adds. NOT the commit body and not
the body of a ledger entry, because an entry routinely cites a neighbouring item
- ``LL-0245`` names ``OPS-73`` while being about ``OPS-77`` - and grouping on a
citation would weld unrelated cycles together and inflate every span. The cost
of that choice is that a commit which names its item only in prose is missed,
which makes the cycle count itself a floor as well.

THE LIVE HALF - the AFTER number, added for the same criterion once
``ops/suite_recorder.py`` began recording every pytest session in this tree.
Its numbers are RECORDED rather than reconstructed, and the two halves are
printed together but are NOT a ratio: the historical run count is a floor from
quoted prose and the live one is a count of records.

THE BOUNDARY RULE, because a cycle has to have edges before it can have a cost.
The only boundary available on disk is TIME. A record is inside the cycle when
its ``started_utc`` is at or after a start point and there is no upper bound,
because the cycle being measured is the one still running. The start point is
the COMMITTER timestamp of the tip commit by default - the offer is "the cycle
in progress" - and a caller may pass an explicit one with ``--since``.

WHAT THAT BOUNDARY CANNOT DISTINGUISH, stated here and again in the report
itself, because a caveat a reader of the number never sees is not a caveat:

* Nothing on disk says which CYCLE a run belonged to. A record proves that SOME
  session on this machine ran a suite between two points, not that this cycle
  did. The record directory is shared between concurrent sessions, and the lane
  that built the recorder measured exactly that: a concurrent mutation sweep
  contributed most of the records present on its first measured run.
* The tip commit is a PROXY for "when this cycle started". If the cycle already
  landed a commit, the window starts too late and the count is too low; if two
  items were worked in one span, the count is too high.
* ``duration_s`` starts at ``pytest_configure``, so the summed suite clock is a
  floor on real elapsed time in the suite and never an over-count.

Run it with ``python -m ops.cycle_cost``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path

from ops import suite_recorder

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The files whose ADDED lines are read as evidence, beside the commit message
#: itself. All three are places this project has been observed quoting a suite
#: result. A path that is absent from a commit simply contributes nothing.
EVIDENCE_PATHS: tuple[str, ...] = (
    "docs/LEDGER.md",
    "docs/LEDGER_ARCHIVE.md",
    "LL-NEXT-SESSION.txt",
)

#: How many commits back to look, by default. A parameter rather than a fixed
#: horizon: the anchored phrase only exists in the newest entries, so a wider
#: window adds grouped cycles and no anchored ones.
DEFAULT_WINDOW = 40

#: The parser threshold that separates a full-suite figure from a module-sized
#: one. It is a PARSER PARAMETER, not a measurement, and the report prints the
#: margin either side of it from the live rows so a reader can see whether it
#: separated anything cleanly. A cycle from before this suite passed 1000 tests
#: would be undercounted to zero by it, which is stated rather than hidden.
FULL_SUITE_MIN = 1000

#: How many days an added ledger entry's own date may trail the commit that
#: adds it before the entry is read as MOVED rather than written. One, because
#: a session here routinely crosses local midnight - ``LL-0242`` is dated
#: 2026-09-12 and cites a delivery timestamped 2026-09-13.
MOVE_TOLERANCE_DAYS = 1

_ANCHOR_RE = re.compile(r"refutation pass over ([0-9a-f]{7,40})", re.IGNORECASE)
_DATED_HEADING_RE = re.compile(r"^\+#{2,3} +\S+ +- +(\d{4}-\d{2}-\d{2}) +- ")
_ANY_HEADING_RE = re.compile(r"^\+#{2,3} ")
_OPS_RE = re.compile(r"\bOPS-[0-9]+\b")
_FIGURE_RE = re.compile(r"(?<![\d.])(\d{3,})\s+(passed|collected)\b")

_RECORD = "\x1e"
_FIELD = "\x1f"


@dataclass(frozen=True)
class Commit:
    """One commit, with the text this module is allowed to read as evidence."""

    sha: str
    committed_at: int
    subject: str = ""
    body: str = ""
    #: ``YYYY-MM-DD`` committer date. Used to tell a ledger entry this commit
    #: WROTE from one it merely MOVED; empty when a caller did not supply it.
    committed_on: str = ""
    #: The added lines of :data:`EVIDENCE_PATHS` in this commit, "+" prefixes
    #: intact. Empty when the commit touched none of them.
    evidence: str = ""

    @property
    def short(self) -> str:
        return self.sha[:7]

    @property
    def text(self) -> str:
        """Everything this commit offers as evidence, joined."""
        return "\n".join((self.subject, self.body, self.evidence))


@dataclass(frozen=True)
class AnchorLink:
    """One "refutation pass over <sha>" sentence, resolved if it can be."""

    fix_sha: str
    refuted_sha: str
    resolved: bool


@dataclass(frozen=True)
class Cycle:
    """One refute-fix-refute round, as far as the artifact can show it."""

    item_id: str
    #: ``anchored`` when a verbatim refutation sentence links two of its
    #: commits, ``grouped`` when the only evidence is a shared ``OPS-nn`` id.
    kind: str
    commits: tuple[Commit, ...]
    #: ``(refuted_short, fix_short)`` for every anchored link inside it.
    pairs: tuple[tuple[str, str], ...]
    pass_quotes: tuple[str, ...]
    collect_quotes: tuple[str, ...]

    @property
    def commit_count(self) -> int:
        return len(self.commits)

    @property
    def started_at(self) -> int:
        return min(c.committed_at for c in self.commits)

    @property
    def ended_at(self) -> int:
        return max(c.committed_at for c in self.commits)

    @property
    def span_seconds(self) -> int:
        return self.ended_at - self.started_at

    @property
    def human_span(self) -> str:
        return human_span(self.span_seconds)

    @property
    def longest_gap(self) -> int:
        """The largest interval between two consecutive commits in the cycle.

        A span is elapsed time, not effort. This repository's cycles routinely
        straddle a night, so the gap is printed beside the span and a reader can
        see how much of it nobody was working. A one-commit cycle has no gap and
        answers 0 - which is a measured zero here rather than a missing one,
        since there is no interval to be ignorant about.
        """
        stamps = sorted(c.committed_at for c in self.commits)
        if len(stamps) < 2:
            return 0
        return max(b - a for a, b in pairwise(stamps))

    @property
    def suite_run_floor(self) -> int:
        """Distinct quoted full-suite pass figures. A FLOOR, never a count."""
        return len(self.pass_quotes)

    @property
    def shas(self) -> tuple[str, ...]:
        """Short shas, oldest first."""
        return tuple(
            c.short for c in sorted(self.commits, key=lambda c: c.committed_at)
        )


def human_span(seconds: int) -> str:
    """``90061`` -> ``1d 1h 1m 1s``. Leading zero units are dropped."""
    if seconds < 0:
        return f"-{human_span(-seconds)}"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [(days, "d"), (hours, "h"), (minutes, "m"), (secs, "s")]
    started = False
    out: list[str] = []
    for value, unit in parts:
        if value or started or unit == "s":
            started = started or bool(value)
            out.append(f"{value}{unit}")
    return " ".join(out)


def full_suite_quotes(
    text: str, keyword: str, minimum: int = FULL_SUITE_MIN
) -> tuple[str, ...]:
    """Distinct ``<n> <keyword>`` figures at or above ``minimum``, sorted.

    Distinct is the whole point and it is also the whole weakness: two suite
    runs that produced the same number collapse into one quote, so the answer
    can only ever be a lower bound on how many times the suite was run.
    """
    seen: set[int] = set()
    for raw, word in _FIGURE_RE.findall(text):
        if word != keyword:
            continue
        value = int(raw)
        if value >= minimum:
            seen.add(value)
    return tuple(f"{value} {keyword}" for value in sorted(seen))


def figure_margin(
    commits: tuple[Commit, ...], keyword: str = "passed", minimum: int = FULL_SUITE_MIN
) -> tuple[int | None, int | None]:
    """Largest figure BELOW the threshold and smallest AT or above it.

    Printed in the report so the threshold is not taken on trust. If the two
    numbers sit close together the separation is luck rather than design, and a
    reader can see that without re-deriving anything.
    """
    below: list[int] = []
    above: list[int] = []
    for commit in commits:
        for raw, word in _FIGURE_RE.findall(commit.text):
            if word != keyword:
                continue
            value = int(raw)
            (above if value >= minimum else below).append(value)
    return (max(below) if below else None, min(above) if above else None)


def attributable_lines(added: list[str], commit_day: str) -> list[str]:
    """Added diff lines that belong to the commit's OWN session.

    THE DEFECT THIS EXISTS TO FIX, found by this module's first real run rather
    than reasoned about in advance. ``02a40ed`` applied the ``OPS-57`` split and
    CREATED ``docs/LEDGER_ARCHIVE.md``, so every line of every historical entry
    arrived as an addition in that single commit. Read naively it quoted 70
    distinct full-suite results, and a two-commit cycle claimed 70 suite runs.
    A document reorganisation is not a session's work.

    The discriminator is the entry's OWN date. This ledger is append-only and an
    entry is written the day the work landed, so an entry dated more than
    :data:`MOVE_TOLERANCE_DAYS` before the commit that adds it is being moved
    rather than written. An undated heading is refused rather than guessed at,
    and lines arriving before any heading are kept because those are preamble
    edits the commit really did make.

    A commit day that cannot be parsed disables the filter rather than emptying
    the evidence, because losing every figure is a worse failure than keeping a
    moved one, and the report says the floor understates in either direction.
    """
    try:
        commit_date = date.fromisoformat(commit_day)
    except ValueError:
        return list(added)
    kept: list[str] = []
    keeping = True
    for line in added:
        dated = _DATED_HEADING_RE.match(line)
        if dated is not None:
            try:
                entry_date = date.fromisoformat(dated.group(1))
            except ValueError:
                keeping = False
                continue
            keeping = (commit_date - entry_date).days <= MOVE_TOLERANCE_DAYS
        elif _ANY_HEADING_RE.match(line):
            keeping = False
        if keeping:
            kept.append(line)
    return kept


def grouping_ids(commit: Commit) -> frozenset[str]:
    """The ``OPS-nn`` ids a commit may join a cycle on.

    Subject plus added ledger HEADINGS only - see the module docstring for why
    a body citation is refused.
    """
    text = [commit.subject]
    for line in commit.evidence.splitlines():
        if line.startswith("+### "):
            text.append(line)
    return frozenset(_OPS_RE.findall("\n".join(text)))


def anchor_links(commits: tuple[Commit, ...]) -> tuple[AnchorLink, ...]:
    """Every "refutation pass over <sha>" sentence found in ``commits``.

    An unresolvable sha is RETURNED as unresolved rather than dropped, because
    an anchor pointing outside the window is a fact about the window and
    silently discarding it would make a narrow window look like a quiet repo.
    """
    by_prefix = {c.sha: c for c in commits}
    links: list[AnchorLink] = []
    seen: set[tuple[str, str]] = set()
    for commit in commits:
        for raw in _ANCHOR_RE.findall(commit.text):
            target = raw.lower()
            match = by_prefix.get(target)
            if match is None:
                candidates = [c for c in commits if c.sha.startswith(target)]
                match = candidates[0] if len(candidates) == 1 else None
            if match is not None and match.sha == commit.sha:
                continue
            key = (commit.sha, match.sha if match else target)
            if key in seen:
                continue
            seen.add(key)
            links.append(
                AnchorLink(
                    fix_sha=commit.sha,
                    refuted_sha=match.sha if match else target,
                    resolved=match is not None,
                )
            )
    return tuple(links)


def _git(args: list[str], root: Path, git_exe: str) -> str:
    completed = subprocess.run(
        [git_exe, *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def load_commits(
    root: Path = REPO_ROOT,
    window: int = DEFAULT_WINDOW,
    git_exe: str = "git",
) -> tuple[Commit, ...]:
    """The newest ``window`` commits, each carrying its evidence text.

    Two git invocations rather than one per commit: the metadata pass has no
    pathspec so it sees every commit, and the diff pass is restricted to
    :data:`EVIDENCE_PATHS` and joined back by sha. A commit that touched none of
    those files simply arrives with empty evidence.
    """
    meta = _git(
        [
            "log",
            f"-n{window}",
            f"--format={_RECORD}%H{_FIELD}%ct{_FIELD}%cs{_FIELD}%s{_FIELD}%b",
        ],
        root,
        git_exe,
    )
    order: list[tuple[str, int, str, str, str]] = []
    for chunk in meta.split(_RECORD):
        if not chunk.strip():
            continue
        fields = chunk.split(_FIELD)
        if len(fields) < 5:
            continue
        sha, when, day = fields[0].strip(), fields[1], fields[2].strip()
        subject, body = fields[3], fields[4]
        try:
            stamp = int(when.strip())
        except ValueError:
            continue
        order.append((sha, stamp, day, subject, body))

    diffs = _git(
        [
            "log",
            f"-n{window}",
            "-U0",
            f"--format={_RECORD}%H",
            "--",
            *EVIDENCE_PATHS,
        ],
        root,
        git_exe,
    )
    day_of = {sha: day for sha, _stamp, day, _subject, _body in order}
    added: dict[str, str] = {}
    for chunk in diffs.split(_RECORD):
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        sha = lines[0].strip()
        kept = [
            ln
            for ln in lines[1:]
            if ln.startswith("+") and not ln.startswith("+++")
        ]
        added[sha] = "\n".join(attributable_lines(kept, day_of.get(sha, "")))

    return tuple(
        Commit(
            sha=sha,
            committed_at=stamp,
            committed_on=day,
            subject=subject,
            body=body,
            evidence=added.get(sha, ""),
        )
        for sha, stamp, day, subject, body in order
    )


def _make_cycle(
    item_id: str,
    members: list[Commit],
    links: tuple[AnchorLink, ...],
    minimum: int,
) -> Cycle:
    member_shas = {c.sha for c in members}
    by_sha = {c.sha: c for c in members}
    pairs = tuple(
        sorted(
            (by_sha[ln.refuted_sha].short, by_sha[ln.fix_sha].short)
            for ln in links
            if ln.resolved
            and ln.fix_sha in member_shas
            and ln.refuted_sha in member_shas
        )
    )
    text = "\n".join(c.text for c in members)
    return Cycle(
        item_id=item_id,
        kind="anchored" if pairs else "grouped",
        commits=tuple(sorted(members, key=lambda c: c.committed_at)),
        pairs=pairs,
        pass_quotes=full_suite_quotes(text, "passed", minimum),
        collect_quotes=full_suite_quotes(text, "collected", minimum),
    )


def build_cycles(
    commits: tuple[Commit, ...], minimum: int = FULL_SUITE_MIN
) -> tuple[Cycle, ...]:
    """Assemble cycles from the anchored seeds and the id grouping.

    Order of operations matters. Groups are formed first from the ids, then an
    anchored link EXTENDS the group holding the refuted commit to include the
    fix commit - that is the definition doing its work, since the fix commit
    exists only because of the refuted one and frequently carries a different
    item id in its own subject. Any link still not inside a group becomes a
    two-commit cycle of its own, so an anchored pair is never lost.
    """
    by_sha = {c.sha: c for c in commits}
    links = anchor_links(commits)

    groups: dict[str, set[str]] = {}
    for commit in commits:
        for item in grouping_ids(commit):
            groups.setdefault(item, set()).add(commit.sha)

    changed = True
    while changed:
        changed = False
        for shas in groups.values():
            for link in links:
                if not link.resolved:
                    continue
                if link.refuted_sha in shas and link.fix_sha not in shas:
                    shas.add(link.fix_sha)
                    changed = True

    cycles: list[Cycle] = []
    covered: set[tuple[str, str]] = set()
    for item, shas in groups.items():
        if len(shas) < 2:
            continue
        members = [by_sha[s] for s in shas]
        cycle = _make_cycle(item, members, links, minimum)
        cycles.append(cycle)
        for link in links:
            if link.resolved and link.fix_sha in shas and link.refuted_sha in shas:
                covered.add((link.refuted_sha, link.fix_sha))

    for link in links:
        if not link.resolved:
            continue
        if (link.refuted_sha, link.fix_sha) in covered:
            continue
        members = [by_sha[link.refuted_sha], by_sha[link.fix_sha]]
        ids = sorted(grouping_ids(by_sha[link.refuted_sha]))
        cycles.append(
            _make_cycle(ids[0] if ids else "unattributed", members, links, minimum)
        )

    return tuple(sorted(cycles, key=lambda c: (-c.ended_at, c.item_id)))


def _bounds(cycles: tuple[Cycle, ...], commits: tuple[Commit, ...]) -> list[str]:
    """The lines saying what this instrument cannot see, with LIVE numbers.

    Every figure below is computed from the rows on every call. The session
    before this one shipped a caveat printed from string literals and watched a
    refuter rewrite the numbers with the suite staying green (``LL-0241``), so
    the guard beside this function rewrites a row and requires the printed
    total to move.
    """
    total = len(cycles)
    blind = sum(1 for c in cycles if not c.pass_quotes)
    anchored = sum(1 for c in cycles if c.kind == "anchored")
    # DISTINCT, not summed. One anchored pair can sit inside four cycles when a
    # single commit closed four items, and summing it made the first real run
    # claim five refutation sentences where the ledger holds two.
    pairs = len({pair for c in cycles for pair in c.pairs})
    in_cycle = len({c.sha for cycle in cycles for c in cycle.commits})
    below, above = figure_margin(commits)
    slots = sum(c.commit_count for c in cycles)
    widest = max((c.longest_gap for c in cycles), default=0)
    lines = [
        f"  The suite-run figure is a FLOOR. {blind} of the {total} cycles quote"
        " no full-suite",
        "  result at all, and a floor of 0 there means NO EVIDENCE rather than no"
        " runs.",
        "  Two runs that produced the same pass count collapse into one quote, so"
        " even a",
        "  nonzero floor understates.",
        f"  Only {pairs} verbatim refutation sentences exist in the whole window,"
        f" seeding",
        f"  {anchored} of the {total} cycles. The rest are grouped by a shared"
        " OPS- id, and a",
        "  group may hold a commit that FILED an item rather than repaired it.",
        "  Every span starts at a cycle's FIRST COMMIT, so the work done before"
        " that",
        f"  commit is outside git and all {total} spans are lower bounds.",
        f"  {in_cycle} of the {len(commits)} commits in the window are inside a"
        " cycle at all;",
        "  a commit naming its item only in prose is invisible to the grouping.",
        f"  CYCLES OVERLAP. The {slots} commit slots across {total} cycles"
        f" resolve to {in_cycle}",
        "  distinct commits, because one commit can close three items at once, so"
        " the",
        "  summed wall clock above double-counts every shared commit.",
        "  A SPAN IS ELAPSED TIME, NOT EFFORT. The widest gap between two"
        " consecutive",
        f"  commits inside a cycle is {human_span(widest)}, and nobody was"
        " working for most",
        "  of it, so a span is a lower bound on elapsed time and an upper bound"
        " on effort.",
    ]
    if below is not None and above is not None:
        lines.append(
            f"  The full-suite threshold is {FULL_SUITE_MIN} passed. In this"
            f" window the largest"
        )
        lines.append(
            f"  figure below it is {below} and the smallest at or above it is"
            f" {above}."
        )
    return lines


def format_report(
    cycles: tuple[Cycle, ...],
    window: int,
    commits: tuple[Commit, ...] = (),
) -> str:
    """The report, with every number summed from ``cycles``."""
    if not cycles:
        return (
            f"CYCLE COST, HISTORICAL - no cycle could be built from the {window}"
            " most recent commits.\n"
            "  Wall clock would be committer time; the suite-run figure would be"
            " a floor.\n"
            "  Nothing is reported rather than a zero dressed as a result."
        )

    total_span = sum(c.span_seconds for c in cycles)
    total_floor = sum(c.suite_run_floor for c in cycles)
    in_cycle = len({c.sha for cycle in cycles for c in cycle.commits})
    anchored = sum(1 for c in cycles if c.kind == "anchored")
    longest = max(cycles, key=lambda c: c.span_seconds)
    shortest = min(cycles, key=lambda c: c.span_seconds)

    lines = [
        f"CYCLE COST, HISTORICAL (the BEFORE number) - {len(cycles)} cycles over"
        f" {in_cycle} commits",
        f"  window: the {window} most recent commits",
        "  wall clock: committer date, because it answers when a commit entered"
        " THIS history",
        "  suite runs: a FLOOR derived from quoted results, never a count",
        "",
    ]
    for cycle in cycles:
        lines.append(
            f"  {cycle.item_id} [{cycle.kind.upper()}] - {cycle.commit_count}"
            f" commits, {cycle.human_span} ({cycle.span_seconds}s)"
        )
        lines.append("    " + " -> ".join(cycle.shas))
        lines.append(
            f"    widest gap between two of its commits: {human_span(cycle.longest_gap)}"
        )
        for refuted, fix in cycle.pairs:
            lines.append(
                f"    anchored: {fix} exists because a refutation pass over"
                f" {refuted} found something"
            )
        lines.append(f"    full-suite runs >= {cycle.suite_run_floor}")
        for quote in cycle.pass_quotes:
            lines.append(f'      "{quote}"')
        if cycle.collect_quotes:
            joined = ", ".join(f'"{q}"' for q in cycle.collect_quotes)
            lines.append(f"    collect-only figures, NOT counted as runs: {joined}")
        lines.append("")

    lines += [
        "TOTALS, every one of them summed from the rows above",
        f"  cycles: {len(cycles)} ({anchored} anchored,"
        f" {len(cycles) - anchored} grouped)",
        f"  wall clock summed over cycles: {human_span(total_span)}"
        f" ({total_span}s)",
        f"  mean cycle span: {human_span(total_span // len(cycles))}"
        f" ({total_span // len(cycles)}s)",
        f"  longest: {longest.item_id} at {longest.human_span}"
        f" ({longest.span_seconds}s)",
        f"  shortest: {shortest.item_id} at {shortest.human_span}"
        f" ({shortest.span_seconds}s)",
        f"  full-suite runs summed over cycles: >= {total_floor}",
        "",
        "WHAT THIS CANNOT SEE:",
        *_bounds(cycles, commits or tuple(c for cy in cycles for c in cy.commits)),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# THE LIVE HALF - the AFTER number. Everything above this line reconstructs the
# past from git and the ledger; everything below reads what the suite recorder
# actually wrote while this cycle was running.
# ---------------------------------------------------------------------------

#: The label a nested run is tallied under. Nesting is not a filter pytest
#: applied - it is this project's own judgement that a fixture's subprocess is
#: not a cycle's suite run - so it is named here rather than read off a record.
NESTED_REASON = "nested inside another pytest rooted at this tree"

#: Digits inside a filtered reason are generalised before the reason is tallied.
#: "14 of 69 test modules on disk did not run" and "3 of 69 ..." are the same
#: reason, and leaving them distinct turns a tally into a list.
_REASON_DIGITS_RE = re.compile(r"\d+")


def epoch_of(stamp) -> float | None:
    """An ISO-8601 timestamp as POSIX seconds, or ``None`` when unreadable.

    A naive timestamp is read as UTC. The recorder always writes an explicit
    ``+00:00`` offset, so anything arriving without one did not come from it and
    UTC is the only reading consistent with the rest of this project.
    """
    try:
        parsed = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def reason_label(reason: str) -> str:
    """The tally label for one recorded ``filtered_reasons`` string.

    Two normalisations, both of them lossy on purpose and both stated in the
    report that prints the result. The text after a colon is dropped, because
    "target arguments narrowed collection: <fourteen paths>" is one reason
    wearing fourteen disguises. Runs of digits become ``N``, because
    "14 of 69 test modules on disk did not run" and "3 of 69 test modules on
    disk did not run" are the same reason counted twice.
    """
    head = str(reason).split(":", 1)[0].strip()
    return _REASON_DIGITS_RE.sub("N", head)


@dataclass(frozen=True)
class LiveRun:
    """One record from ``ops/runtime/suite_runs/``, flattened.

    Flattened away from the raw dict so that a reader of this module can see
    the fields it depends on. The schema itself is the docstring of
    ``ops/suite_recorder.py`` - this is a reader of that contract and adds
    nothing to it.
    """

    started_utc: str
    started_epoch: float
    duration_s: float
    collected: int
    passed: int
    full: bool
    nested: bool
    pid: int
    reasons: tuple[str, ...]

    @property
    def ended_epoch(self) -> float:
        return self.started_epoch + self.duration_s

    @property
    def counted(self) -> bool:
        """Whether this run is one of the cycle's full-suite runs."""
        return self.full and not self.nested

    @property
    def exclusion_labels(self) -> tuple[str, ...]:
        """Why this run is not counted. Empty is impossible by construction.

        A record that is neither full nor carries a reason would be a defect in
        the recorder rather than in this reader, so it is reported as exactly
        that instead of silently tallying as nothing.
        """
        labels = [reason_label(reason) for reason in self.reasons]
        if self.nested:
            labels.append(NESTED_REASON)
        if labels:
            return tuple(labels)
        return ("filtered, but the record states no reason",)


def live_run_from_record(record: dict) -> LiveRun | None:
    """Read one record. ``None`` when its timestamp or duration is unreadable.

    Unreadable rather than raising, for the reason ``load_records`` gives: this
    directory is written concurrently, and one bad file must not make the whole
    measurement unavailable. The count of unreadable records is carried on the
    cycle and printed, because a silently dropped record is a missing suite run.
    """
    epoch = epoch_of(record.get("started_utc", ""))
    if epoch is None:
        return None
    try:
        duration = float(record.get("duration_s", 0.0))
    except (TypeError, ValueError):
        return None
    return LiveRun(
        started_utc=str(record.get("started_utc", "")),
        started_epoch=epoch,
        duration_s=duration,
        collected=int(record.get("collected", 0) or 0),
        passed=int(record.get("passed", 0) or 0),
        full=record.get("full") is True,
        nested=record.get("nested") is True,
        pid=int(record.get("pid", 0) or 0),
        reasons=tuple(str(r) for r in (record.get("filtered_reasons") or ())),
    )


@dataclass(frozen=True)
class LiveCycle:
    """The recorded suite runs that fall inside one cycle's boundary."""

    boundary: str
    start_epoch: float | None
    #: The full, non-nested runs inside the boundary, oldest first.
    runs: tuple[LiveRun, ...]
    #: Every other record inside the boundary, oldest first.
    excluded: tuple[LiveRun, ...]
    #: Records whose timestamp or duration could not be read at all. Counted
    #: BEFORE the boundary filter, because a record with no readable timestamp
    #: cannot be placed inside or outside a window.
    unreadable: int = 0

    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)

    @property
    def record_count(self) -> int:
        return len(self.runs) + len(self.excluded)

    @property
    def suite_seconds(self) -> float:
        """Summed ``duration_s`` of the counted runs. A FLOOR on real time.

        ``duration_s`` runs from ``pytest_configure`` to
        ``pytest_sessionfinish``, so interpreter startup and the collection that
        happens before ``pytest_configure`` are outside it. The recorder's own
        docstring says it reads a little under what a shell stopwatch reports,
        which makes this sum a lower bound and never an over-count.
        """
        return sum(run.duration_s for run in self.runs)

    @property
    def all_records(self) -> tuple[LiveRun, ...]:
        return tuple(
            sorted(self.runs + self.excluded, key=lambda r: r.started_epoch)
        )

    @property
    def span_seconds(self) -> float:
        """Boundary start to the END of the newest record inside it.

        Measured against the boundary rather than against the first record,
        because the cycle begins when the boundary says it does and the time
        before the first suite run is part of what the cycle cost. With no
        boundary start it falls back to first record to last record end.
        """
        records = self.all_records
        if not records:
            return 0.0
        end = max(run.ended_epoch for run in records)
        if self.start_epoch is not None:
            return end - self.start_epoch
        return end - min(run.started_epoch for run in records)

    @property
    def distinct_pids(self) -> int:
        return len({run.pid for run in self.all_records})

    @property
    def exclusion_reasons(self) -> tuple[tuple[str, int], ...]:
        """``(label, count)`` for every excluded record, commonest first."""
        tally: dict[str, int] = {}
        for run in self.excluded:
            for label in run.exclusion_labels:
                tally[label] = tally.get(label, 0) + 1
        return tuple(sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])))


def build_live_cycle(
    records: list[dict],
    start_epoch: float | None,
    boundary: str,
) -> LiveCycle:
    """Split ``records`` into the cycle's suite runs and everything else.

    THE BOUNDARY RULE, in one sentence: a record is inside the cycle when its
    ``started_utc`` is at or after ``start_epoch``, and there is no upper bound
    because the cycle being measured is the one still running. ``None`` for
    ``start_epoch`` means every record on disk.
    """
    runs: list[LiveRun] = []
    excluded: list[LiveRun] = []
    unreadable = 0
    for record in records:
        run = live_run_from_record(record)
        if run is None:
            unreadable += 1
            continue
        if start_epoch is not None and run.started_epoch < start_epoch:
            continue
        (runs if run.counted else excluded).append(run)
    return LiveCycle(
        boundary=boundary,
        start_epoch=start_epoch,
        runs=tuple(sorted(runs, key=lambda r: r.started_epoch)),
        excluded=tuple(sorted(excluded, key=lambda r: r.started_epoch)),
        unreadable=unreadable,
    )


def tip_commit(
    root: Path | str = REPO_ROOT, git_exe: str = "git"
) -> tuple[str, int] | None:
    """``(sha, committer epoch)`` of ``HEAD``, or ``None`` when git says nothing.

    COMMITTER date again, for the reason the module docstring gives about the
    historical half: it answers when the commit entered this history, which is
    when the work after it started.
    """
    out = _git(["log", "-1", "--format=%H %ct"], Path(root), git_exe).strip()
    parts = out.split()
    if len(parts) < 2:
        return None
    try:
        return parts[0], int(parts[1])
    except ValueError:
        return None


def load_live_cycle(
    root: Path | str = REPO_ROOT,
    git_exe: str = "git",
    since: str | None = None,
) -> LiveCycle:
    """The live cycle, boundary taken from ``since`` or from the tip commit.

    The default offer is the cycle IN PROGRESS: every full, non-nested run
    started since the tip commit entered this history. That boundary is a
    proxy and it errs in one direction, which is stated in the report - if the
    current cycle already landed a commit or two, the boundary starts too late
    and the count it produces is too low.
    """
    records = suite_recorder.load_records(root)
    if since is not None:
        start = epoch_of(since)
        if start is None:
            try:
                start = float(since)
            except (TypeError, ValueError):
                start = None
        boundary = (
            f"explicit start {since} - full, non-nested runs started at or after it"
        )
        if start is None:
            boundary = (
                f"explicit start {since} could NOT be read, so every record on"
                " disk is in the window"
            )
        return build_live_cycle(records, start, boundary)

    tip = tip_commit(root, git_exe)
    if tip is None:
        return build_live_cycle(
            records,
            None,
            "no tip commit could be read, so every record on disk is in the window",
        )
    sha, stamp = tip
    iso = datetime.fromtimestamp(stamp, UTC).isoformat()
    boundary = (
        f"the cycle IN PROGRESS - full, non-nested runs started at or after the"
        f" tip commit {sha[:7]} at {iso}"
    )
    return build_live_cycle(records, float(stamp), boundary)


def _live_bounds(cycle: LiveCycle) -> list[str]:
    """What the live instrument cannot see, with numbers taken from the rows.

    Same discipline as :func:`_bounds`. Every figure below is computed from the
    records on every call, and ``tests/test_cycle_cost.py`` rewrites a row and
    requires the printed figure to move - a literal cannot do that, which is
    the defect ``LL-0241`` recorded.
    """
    plural = "" if cycle.distinct_pids == 1 else "s"
    return [
        "  The record directory is SHARED between concurrent sessions in this"
        " tree. The",
        f"  {cycle.record_count} records written by {cycle.distinct_pids} distinct"
        f" process id{plural} inside this boundary prove",
        "  that SOME session on this machine ran a suite, not that THIS cycle did."
        " The",
        "  recorder lane measured exactly that happening: a concurrent mutation"
        " sweep",
        "  contributed most of the records present on its own first measured run.",
        "  THE BOUNDARY IS TIME, NOT A CYCLE MARKER. Nothing on disk says which"
        " cycle a",
        "  run belonged to. If the cycle being measured already landed a commit,"
        " the tip",
        "  commit starts the window too late and the count is too low; if another"
        " item was",
        "  worked in the same span, the count is too high.",
        "  The summed suite clock EXCLUDES interpreter startup and the collection"
        " that",
        "  happens before pytest_configure, so it is a floor on real elapsed time"
        " in the",
        "  suite and never an over-count.",
        f"  {cycle.unreadable} records could not be read at all and are outside"
        " every number above.",
        f"  Only the newest {suite_recorder.KEEP_RECORDS} records survive a write,"
        " so a long enough cycle",
        "  loses its oldest runs, and a run killed before pytest_sessionfinish"
        " writes nothing.",
        "  THE TWO HALVES OF THIS REPORT ARE NOT A RATIO. The historical suite-run"
        " figure",
        "  is a floor reconstructed from quoted prose and the live one is a"
        " recorded count;",
        "  dividing one by the other would manufacture a number neither half"
        " supports.",
    ]


def format_live_report(cycle: LiveCycle) -> str:
    """The live report, with every number taken from ``cycle``'s records."""
    lines = [
        "CYCLE COST, LIVE (the AFTER number) - measured from"
        " ops/runtime/suite_runs/",
        f"  boundary: {cycle.boundary}",
        f"  full-suite runs: {cycle.run_count} (EXACT - every full, non-nested"
        " record inside the boundary)",
        f"  summed suite wall clock (a FLOOR): >= {cycle.suite_seconds:.1f}s"
        f" ({human_span(int(cycle.suite_seconds))})",
    ]
    if cycle.run_count == 0:
        lines.append(
            "  no full-suite run has been recorded inside this boundary, which is"
            " NO EVIDENCE"
        )
        lines.append(
            "  rather than a measured zero - the suite may have run before the"
            " recorder existed."
        )
    if cycle.record_count:
        lines.append(
            f"  elapsed span from the boundary to the newest record:"
            f" {human_span(int(cycle.span_seconds))} ({cycle.span_seconds:.1f}s)"
        )
        lines.append(
            "  that span is a LOWER BOUND on the finished cycle, because the cycle"
            " is still open"
        )
    else:
        lines.append(
            "  elapsed span: not measurable - no record falls inside this boundary"
        )
    lines.append(
        f"  {cycle.excluded_count} records excluded from the count, by reason:"
    )
    for label, count in cycle.exclusion_reasons:
        lines.append(f"      {count} x {label}")
    if not cycle.exclusion_reasons:
        lines.append("      (none)")
    label_total = sum(count for _label, count in cycle.exclusion_reasons)
    if label_total > cycle.excluded_count:
        lines.append(
            f"      the {cycle.excluded_count} records carry {label_total} reasons"
            " between them, so the counts above do not sum to the record count"
        )
    lines.append("")
    lines.append("  every counted run, oldest first:")
    for run in cycle.runs:
        lines.append(
            f"      {run.started_utc}  {run.duration_s:.1f}s "
            f" {run.collected} collected  {run.passed} passed  pid {run.pid}"
        )
    if not cycle.runs:
        lines.append("      (none)")
    lines += ["", "WHAT THE LIVE HALF CANNOT SEE:", *_live_bounds(cycle)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    window = DEFAULT_WINDOW
    git_exe = "git"
    if "--window" in args:
        window = int(args[args.index("--window") + 1])
    if "--git" in args:
        git_exe = args[args.index("--git") + 1]
    since: str | None = None
    if "--since" in args:
        since = args[args.index("--since") + 1]
    commits = load_commits(window=window, git_exe=git_exe)
    cycles = build_cycles(commits)
    print(format_report(cycles, window=window, commits=commits))
    print()
    print(format_live_report(load_live_cycle(git_exe=git_exe, since=since)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
