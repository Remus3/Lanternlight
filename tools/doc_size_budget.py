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

THE ARCHIVES ARE NOT BUDGETED INDIVIDUALLY, AND THAT IS A DECISION. ROADMAP
``OPS-62``, decided 2026-09-08. If you came here looking for a budget on
``docs/ROADMAP_ARCHIVE.md`` or ``docs/LEDGER_ARCHIVE.md``, there is none by
choice, the reason is recorded in :data:`UNBUDGETED_BY_DECISION` keyed by those
exact paths, and the real bound on them is :data:`PAIR_BUDGETS`.

Why not a per-archive budget. ``OPS-57`` split both continuity documents, and a
budget is only meaningful next to a growth rate. An archive does not grow the
way a live document does: it gains nothing at all between splits, then takes
one large step when a split runs. So its rate would have to be measured in
bytes per SPLIT, and there has been exactly one split - a slope through one
point is not a measurement, and this repository omits rather than guesses.

What is budgeted instead: THE PAIR. :data:`PAIR_BUDGETS` bounds the live
document and its archive TOGETHER, as one total. Three things recommend it over
any per-archive number:

- **A split cannot game it.** Splitting moves bytes from the live half to the
  archive half and leaves the pair total almost untouched, so the pair budget
  measures the thing that actually grows - total continuity prose in the
  repository - rather than the thing a split rearranges. This is the exact hole
  ``OPS-62`` was filed about: with only live budgets, the documented response
  to a firing (re-run the split) moves bytes into a file nothing watches, and
  the guard then reports OK forever.
- **Its rate is already measured, over six sessions, not one split.** Before
  the split the live document WAS the whole pair - the archive did not exist -
  so the six-session per-session append rates in
  :data:`SESSION_GROWTH_RATES` are pair rates as they stand. The pair model
  reuses them rather than declaring a second copy.
- **It keeps both halves visible.** :attr:`Report.components` carries each
  half's own byte count beside the total, so a reader can still see which half
  the bytes are in even though only the sum is bounded.

THE ONE PROVISIONAL TERM, STATED HERE AND IN THE REPORT ITSELF. ``OPS-62``
criterion 2 requires two splits or a written admission of one. There has been
one, so :class:`PairGrowthModel` carries ``splits_measured`` (1 today), reports
``provisional`` while that is under two, and :meth:`Report.format` prints the
caveat next to every sessions figure it qualifies. The provisional term is
``split_overhead_bytes``: a split is not perfectly byte-conserving, because it
leaves a stub per archived section in the live document and writes a header
into the archive, so the pair total steps UP slightly each time one runs. That
overhead is amortized over the sessions between splits and ADDED to the append
rate, which shortens the reported headroom - the conservative direction, and the
same reasoning that made :data:`SESSION_GROWTH_RATES` use the high median.

THE COST OF THIS DECISION, which is real and is not hidden by it. First, no
individual archive is bounded, so an archive growing on its own - somebody
appending directly to it rather than through a split - consumes pair headroom
indistinguishably from ordinary growth in the live half. The components in the
report are the only mitigation; nothing guards it. Second, and more important:
a pair budget firing has NO mechanical remedy. A live budget firing is answered
by re-running ``tools/doc_archive.py``; a pair budget firing cannot be, because
the split is what the pair total ignores. The only answers are a real reduction
in content (which this repository's own rules forbid for the ledger, since an
entry is written in full for a cold session) or an operator ruling - move the
archives out of this repository, or accept a higher bound. So a pair firing is
a DECISION GATE for the operator, not a chore, which is why
:data:`PAIR_LOW_HEADROOM_SESSIONS` warns further out than the per-document
threshold does.

THE COMMAND LINE REFUSES WHAT IT DOES NOT UNDERSTAND, AND ITS ONE OPTION IS
REAL. ROADMAP ``OPS-67``, and this module is the one of that item's four that
actually mattered. Measured 2026-09-08:
``python tools/doc_size_budget.py --lanternlight-bogus-flag`` exited 0 and
printed an ordinary green report about the live documents, because :func:`main`
took no parameters and never read ``sys.argv`` at all - the flag was not
rejected, it was never seen. That is worse here than in a script whose output
nobody reads, because THESE NUMBERS GET QUOTED: this repository's own hand-off
tells the next session to ask this module for headroom in sessions rather than
repeat a byte figure. A caller who believed they had scoped the tool at a
scratch document, and got a confident verdict about ROADMAP.md and
docs/LEDGER.md, is the ``OPS-64`` failure exactly - a true verdict answering a
different question than the one asked.

Two changes answer it and both are needed. Unknown argv is now a usage error
with its own exit code (:data:`USAGE_EXIT_CODE`), and ``--repo-root`` is a REAL
option in the sense ``OPS-67`` criterion 2 demands: passing it changes which
documents are measured, not merely which string is printed. Every run also
prints the root it read, so a verdict cannot be mistaken for an answer about a
different tree.

``--repo-root`` SCOPES BOTH CHANNELS AT ONCE, AND THERE IS DELIBERATELY NO
FLAG THAT SCOPES ONLY ONE. This module has two channels since ``OPS-62`` - the
per-document budgets in :data:`BUDGETS` and the pair budgets in
:data:`PAIR_BUDGETS` - and :func:`main` prints both on every run because an
archive that only appears in the output when it fails is an archive nobody
watches. A ``--documents-only`` or ``--pairs-only`` switch would reintroduce
the very defect this item is about one level up: a run that measured one
channel, printed one confident OK line, and left a reader to assume the other
channel had been checked too. So the option names a TREE, both channels resolve
their watched paths under it, and the scope line names it once for both.

WHAT ``--repo-root`` DOES NOT CHANGE, WHICH MATTERS BECAUSE THIS MODULE
WRITES GIT OBJECTS. :func:`git_blob_size` shells out to ``git hash-object -w``,
and that ``-w`` writes a loose object. ``--repo-root`` moves only where WATCHED
PATHS are resolved from; it does NOT move the git working directory, which
stays this repository's own root (:data:`REPO_ROOT`) exactly as
:func:`git_blob_size`'s default already documents. The consequences, stated
plainly rather than left to be discovered:

- Pointing ``--repo-root`` at a directory that is not a git repository WORKS,
  and is the intended way to check a scratch pair. The scratch files are read
  off disk by absolute path and hashed into THIS repository's object database.
- Every such run therefore leaves loose objects under this repository's
  ``.git/objects`` - one per file measured. They are unreferenced and ordinary
  ``git gc`` reclaims them, but a test suite that counts loose objects will see
  them, so this module is not a good neighbour to run in a tight loop.
- If git itself fails - no repository to write into, an unreadable path - the
  ``subprocess.CalledProcessError`` propagates and the run dies loudly. It is
  never caught and turned into a zero, because "git failed" and "the document
  is small" are different facts and this whole module exists to keep facts like
  those apart.
- A watched path that does not exist under ``--repo-root`` is still a Finding
  and still exits 1. Scoping the tool at an empty directory must not turn a
  missing document into a green run; that would be building the textbook
  vacuous guard on purpose, with a flag.

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

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "BUDGETS",
    "LOW_HEADROOM_SESSIONS",
    "PAIRS",
    "PAIR_BUDGETS",
    "PAIR_GROWTH",
    "PAIR_LOW_HEADROOM_SESSIONS",
    "REPO_ROOT",
    "SESSION_GROWTH_RATES",
    "UNBUDGETED_BY_DECISION",
    "USAGE_EXIT_CODE",
    "DocumentPair",
    "Finding",
    "GrowthRate",
    "PairGrowthModel",
    "Report",
    "build_parser",
    "check_budgets",
    "check_pair_budgets",
    "git_blob_size",
    "headroom_sessions",
    "main",
    "pair_headroom_sessions",
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
class DocumentPair:
    """A live continuity document and the archive its closed content moves to.

    Both halves are repo-relative paths, keyed exactly like :data:`BUDGETS`.
    The pair exists because a split moves bytes between the two and the sum is
    what actually grows - see the module docstring's section on why the archives
    are not budgeted individually.
    """

    live: str
    archive: str


@dataclass(frozen=True)
class PairGrowthModel:
    """Per-session growth of one live-plus-archive PAIR, in git-blob bytes.

    Two terms, with very different evidence behind them, kept separate on
    purpose so a reader can see which one is solid:

    ``append_median`` is the live document's measured per-session append rate
    from :data:`SESSION_GROWTH_RATES` - six sessions, and before the ``OPS-57``
    split the live document was the entire pair, so that figure is already a
    pair rate rather than an analogy to one.

    ``split_overhead_bytes`` is how much the pair TOTAL rose across the one
    split that has happened. A split is not byte-conserving: it leaves an
    archive-index stub per moved section in the live half and writes a header
    into the archive. This term rests on a SINGLE split and is therefore
    provisional - :attr:`provisional` says so, and the report prints it beside
    the number it qualifies.

    ``split_interval_sessions`` is derived, not declared: the sessions a live
    document takes to travel from its post-split size to its own budget, which
    is when the next split runs. :attr:`effective_rate` amortizes the split
    overhead across that interval and adds it to the append rate, so the
    reported headroom accounts for the splits that will happen inside it. The
    direction is deliberate - adding the term shortens reported headroom, and
    underestimating growth is the failure this whole check exists to stop.
    """

    append_median: int
    live_budget: int
    live_size_at_split: int
    split_overhead_bytes: int
    splits_measured: int = 1

    @property
    def provisional(self) -> bool:
        """True while the split-overhead term rests on fewer than two splits.

        One point is not a slope. ``OPS-57`` refused a re-measurement on that
        ground and ``OPS-62`` explicitly declined an exemption from it, so this
        stays true until a second split has been measured.
        """
        return self.splits_measured < 2

    @property
    def split_interval_sessions(self) -> float:
        """Sessions from one split to the next, derived from the live budget.

        Returns ``0.0`` when the live document is already at or past its budget
        at the moment it was measured, which would mean a split is due
        immediately; callers must not divide by this without checking.
        """
        if self.append_median <= 0:
            return 0.0
        remaining = self.live_budget - self.live_size_at_split
        if remaining <= 0:
            return 0.0
        return remaining / self.append_median

    @property
    def per_session_split_overhead(self) -> float:
        """The one-off split overhead spread across one split interval."""
        interval = self.split_interval_sessions
        if interval <= 0 or self.split_overhead_bytes <= 0:
            return 0.0
        return self.split_overhead_bytes / interval

    @property
    def effective_rate(self) -> float:
        """Bytes a pair gains per session, appending plus amortized overhead."""
        return self.append_median + self.per_session_split_overhead


#: The live-plus-archive pairs this module bounds as totals, keyed by a short
#: pair name. Created by the ``OPS-57`` split; bounded as pairs by ``OPS-62``.
PAIRS: dict[str, DocumentPair] = {
    "ROADMAP": DocumentPair(live="ROADMAP.md", archive="docs/ROADMAP_ARCHIVE.md"),
    "LEDGER": DocumentPair(live="docs/LEDGER.md", archive="docs/LEDGER_ARCHIVE.md"),
}

# WHY EACH ARCHIVE HAS NO BUDGET OF ITS OWN, keyed by the archive path itself so
# that a reader who greps this file for the archive they were looking for lands
# on the decision instead of on silence. ``OPS-62`` criterion 4 asks for exactly
# that: the decision recorded WITH ITS COST, where it will be looked for.
UNBUDGETED_BY_DECISION: dict[str, str] = {
    "docs/ROADMAP_ARCHIVE.md": (
        "No individual budget, by decision (ROADMAP OPS-62, 2026-09-08). An "
        "archive gains nothing between splits and then takes one large step "
        "when a split runs, so its rate would be bytes per SPLIT and only one "
        "split has happened - a slope through one point is not a measurement. "
        "The bound lives in PAIR_BUDGETS['ROADMAP'], on ROADMAP.md and this "
        "file TOGETHER, which is the figure a split cannot game. COST: this "
        "file growing on its own is indistinguishable from the live half "
        "growing, and a pair budget firing has no mechanical remedy - re-"
        "running the split will not relieve it, so it is an operator decision "
        "gate. See the module docstring for the full statement."
    ),
    "docs/LEDGER_ARCHIVE.md": (
        "No individual budget, by decision (ROADMAP OPS-62, 2026-09-08). Same "
        "reasoning as docs/ROADMAP_ARCHIVE.md: step-wise growth measured across "
        "exactly one split is not a rate, and this repository omits rather than "
        "guesses. The bound lives in PAIR_BUDGETS['LEDGER'], on docs/LEDGER.md "
        "and this file TOGETHER. COST: no attribution between the halves, and a "
        "pair firing is an operator decision gate rather than a chore, because "
        "the ledger's own rules forbid compressing an entry to save bytes."
    ),
}

#: A PAIR with fewer than this many sessions of headroom is flagged. Four, not
#: the two used per document, and the difference is the remedy rather than the
#: risk: a live budget firing is answered mechanically by re-running the split,
#: while a pair budget firing needs an operator ruling (see the module
#: docstring's cost statement). Four sessions is about one split interval at the
#: measured rates, so the warning arrives with a full cycle in hand rather than
#: with one session. Like :data:`LOW_HEADROOM_SESSIONS` this is a WARNING
#: threshold and never a failure threshold.
PAIR_LOW_HEADROOM_SESSIONS = 4.0

# Per-pair growth models. MEASURED 2026-09-08 for ``OPS-62``.
#
# METHOD, so it is repeatable rather than trusted. Every figure below is a git
# blob size read straight out of history, which means anybody can reproduce it
# without re-running a session:
#
#   git cat-file -s $(git rev-parse <rev>:<path>)
#
# at rev ``0eb6217`` (the commit that closed ``OPS-57`` and performed the split)
# and at its parent ``0eb6217^`` (the last commit before any archive existed):
#
#   ROADMAP.md              0eb6217^  633,871      0eb6217  193,854
#   docs/ROADMAP_ARCHIVE.md 0eb6217^  ABSENT       0eb6217  475,473
#   docs/LEDGER.md          0eb6217^  867,833      0eb6217  295,174
#   docs/LEDGER_ARCHIVE.md  0eb6217^  ABSENT       0eb6217  586,771
#
# So the ROADMAP pair went from 633,871 to 669,327 across the split (+35,456)
# and the LEDGER pair from 867,833 to 881,945 (+14,112). Those deltas are the
# ``split_overhead_bytes`` below.
#
# TWO CAVEATS ON THAT NUMBER, both of which a reader deserves rather than a
# clean-looking figure. It rests on ONE split, so it is provisional and says so
# in code (:attr:`PairGrowthModel.provisional`). And the split commit also
# carried that session's own prose - a closure, an archive index and three new
# items - which cannot be separated from the split's structural overhead in a
# commit-level measurement, so each delta is an UPPER BOUND on the overhead
# rather than the overhead exactly. An upper bound here raises the effective
# rate and shortens the reported headroom, which is the safe direction and the
# same choice the high median made in SESSION_GROWTH_RATES above.
PAIR_GROWTH: dict[str, PairGrowthModel] = {
    "ROADMAP": PairGrowthModel(
        append_median=SESSION_GROWTH_RATES["ROADMAP.md"].median,
        live_budget=340_000,
        live_size_at_split=193_854,
        split_overhead_bytes=35_456,
        splits_measured=1,
    ),
    "LEDGER": PairGrowthModel(
        append_median=SESSION_GROWTH_RATES["docs/LEDGER.md"].median,
        live_budget=420_000,
        live_size_at_split=295_174,
        split_overhead_bytes=14_112,
        splits_measured=1,
    ),
}

# PAIR BUDGETS, and how each number was arrived at - because a budget nobody can
# re-derive is a number that looks measured.
#
# Measured 2026-09-08, working tree, with this module's own git_blob_size:
#   ROADMAP pair  226,565 + 475,473 = 702,038
#   LEDGER pair   314,927 + 586,771 = 901,698
#
# The effective rates the models above produce are roughly 40,286 bytes per
# session for the ROADMAP pair (32,421 appending plus 35,456 of split overhead
# spread over a 4.51-session split interval) and roughly 30,708 for the LEDGER
# pair (27,589 plus 14,112 over 4.52 sessions). Run the module rather than
# trusting either figure; both are derived properties, not constants.
#
# THE HORIZON IS TWELVE SESSIONS, AND THAT PART IS A JUDGEMENT, not a
# measurement. The rate under it is measured; the choice of how much headroom to
# grant is not, and pretending otherwise is how a guessed number starts looking
# derived. Twelve was chosen because a pair firing is an operator decision gate
# with no mechanical remedy: at roughly two and a half split intervals it is far
# enough out that the operator is not asked to rule every fortnight, and at
# ~40 KB a session it is nowhere near the "buys a year" range that turns a
# tripwire into a rubber stamp - which is the failure mode the 700,000 raise on
# 2026-09-08 was labelled with before OPS-57 lowered it again.
#
# Twelve sessions of headroom on the measured totals gives 1,185,434 and
# 1,270,230; both are rounded DOWN to a round number below, since rounding down
# shortens headroom and is the conservative direction.
#
# WHEN ONE OF THESE FIRES, DO NOT RE-RUN THE SPLIT AND DO NOT RAISE THE NUMBER
# ON YOUR OWN. The split does not move this figure (it nudges it up, by the
# overhead above) and raising a budget to make a red run green is the antipattern
# this repository has written down. It is an operator ruling: move the archives
# out of this repository, accept a higher bound, or reduce content for real.
PAIR_BUDGETS: dict[str, int] = {
    "ROADMAP": 1_180_000,
    "LEDGER": 1_270_000,
}


@dataclass(frozen=True)
class Finding:
    """One watched document that failed the check.

    ``kind`` is ``"missing"`` when the path does not exist on disk at all,
    ``"over_budget"`` when its measured git-blob size is AT OR OVER
    ``budget`` - the ROADMAP acceptance criterion says "at or over", so a size
    exactly equal to the budget is a Finding, not a pass - or
    ``"pair_over_budget"`` when a live-plus-archive PAIR total is at or over its
    :data:`PAIR_BUDGETS` entry, in which case ``path`` is the PAIR NAME rather
    than a file path and ``detail`` names both halves and their sizes. ``size``
    is ``None`` only for a ``"missing"`` Finding; anything actually measured
    always carries its measured size here, whether or not that size is what
    tripped the Finding.
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
    ``low_headroom_threshold``; it is a warning channel and deliberately does
    NOT feed ``ok``.

    The remaining fields exist so one report shape can render both channels -
    per-document budgets and the per-PAIR budgets ``OPS-62`` added - without a
    second near-identical class drifting away from this one. ``title`` and
    ``unit`` are wording only. ``low_headroom_threshold`` is carried on the
    report rather than read from the module at render time, because the pair
    channel warns at :data:`PAIR_LOW_HEADROOM_SESSIONS` and a rendered report
    quoting the wrong threshold would be lying about its own rule.
    ``components`` breaks a measured subject into its parts, which is how a pair
    total stays attributable to a half even though only the sum is bounded.
    ``provisional_notes`` carries a caveat to print beside a subject's sessions
    figure - the pair model's split-overhead term rests on one split, and a
    caveat that lives only in a report somebody wrote once is a caveat the next
    reader never sees.
    """

    ok: bool
    findings: tuple[Finding, ...]
    measured: dict[str, int]
    headroom_sessions: dict[str, float] = field(default_factory=dict)
    low_headroom: tuple[str, ...] = ()
    title: str = "doc size budget"
    unit: str = "document"
    low_headroom_threshold: float = LOW_HEADROOM_SESSIONS
    components: dict[str, dict[str, int]] = field(default_factory=dict)
    provisional_notes: dict[str, str] = field(default_factory=dict)

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
            lines = [
                f"{self.title}: OK ({len(self.measured)} {self.unit}(s) measured)"
            ]
        else:
            lines = [f"{self.title}: {len(self.findings)} finding(s)"]
            lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        for path in sorted(self.measured):
            line = f"  [measured] {path}: {self.measured[path]} bytes"
            parts = self.components.get(path)
            if parts:
                joined = " + ".join(f"{name} {size}" for name, size in parts.items())
                line += f" ({joined})"
            left = self.headroom_sessions.get(path)
            if left is None:
                line += ", headroom in sessions unknown - no measured growth rate"
            else:
                line += f", {left:.1f} sessions of headroom"
                if path in self.low_headroom:
                    line += (
                        f" - LOW HEADROOM (under "
                        f"{self.low_headroom_threshold:.1f} sessions; this is a "
                        "warning, not a failure)"
                    )
                note = self.provisional_notes.get(path)
                if note:
                    line += f" [{note}]"
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


def pair_headroom_sessions(
    name: str,
    total: int,
    budgets: dict[str, int] | None = None,
    models: dict[str, PairGrowthModel] | None = None,
) -> float | None:
    """Return how many more sessions a PAIR can grow before it hits budget.

    ``(budget - total) / model.effective_rate``, the pair counterpart of
    :func:`headroom_sessions`, and it follows the same three rules for the same
    reasons: ``total`` is passed in rather than measured so the arithmetic can be
    exercised at an exact boundary without shelling out to ``git``; the answer is
    ``None`` rather than a number when the pair has no budget, no model or a
    non-positive rate, because ``0.0`` would read as "fires next session" and
    ``inf`` as "nothing to worry about" and nobody measured either; and the
    result is NOT clamped at zero, so a pair already past its budget reports
    negative sessions and "just fired" stays distinguishable from "far past".

    The rate used is :attr:`PairGrowthModel.effective_rate`, which includes the
    amortized split overhead. That term rests on one split and is provisional -
    see the module docstring.
    """
    if budgets is None:
        budgets = PAIR_BUDGETS
    if models is None:
        models = PAIR_GROWTH

    budget = budgets.get(name)
    model = models.get(name)
    if budget is None or model is None:
        return None
    rate = model.effective_rate
    if rate <= 0:
        return None
    return (budget - total) / rate


def check_pair_budgets(
    pairs: dict[str, DocumentPair] | None = None,
    budgets: dict[str, int] | None = None,
    models: dict[str, PairGrowthModel] | None = None,
    repo_root: Path = REPO_ROOT,
) -> Report:
    """Check each live-plus-archive PAIR total against its pair budget.

    This is the ``OPS-62`` channel: the archives created by the ``OPS-57`` split
    carry no budget of their own (see :data:`UNBUDGETED_BY_DECISION` and the
    module docstring), and the bound on them is the sum of each archive and its
    live half. A split moves bytes between the halves without changing that sum,
    which is precisely why the sum is what gets bounded - it is the one figure
    the documented response to a firing cannot quietly relieve.

    Every argument is overridable so this can be exercised against throwaway
    fixtures. Failure semantics match :func:`check_budgets` exactly: a half that
    does not exist on disk is a ``"missing"`` Finding rather than a cheap pass, a
    total AT OR OVER budget is a ``"pair_over_budget"`` Finding, the scan never
    returns early so every problem in one run is reported together, and low
    headroom is a warning that never touches ``Report.ok``.

    A pair with a missing half is absent from ``Report.measured`` rather than
    present with a total that silently omits the missing half - "unmeasurable"
    and "small" are different facts, and conflating them is how this check would
    start lying.
    """
    if pairs is None:
        pairs = PAIRS
    if budgets is None:
        budgets = PAIR_BUDGETS
    if models is None:
        models = PAIR_GROWTH

    findings: list[Finding] = []
    measured: dict[str, int] = {}
    components: dict[str, dict[str, int]] = {}
    sessions_left: dict[str, float] = {}
    low_headroom: list[str] = []
    provisional_notes: dict[str, str] = {}

    for name, pair in pairs.items():
        budget = budgets.get(name, 0)
        halves: dict[str, int] = {}
        complete = True
        for rel_path in (pair.live, pair.archive):
            full_path = repo_root / rel_path
            if not full_path.is_file():
                complete = False
                findings.append(
                    Finding(
                        kind="missing",
                        path=rel_path,
                        budget=budget,
                        size=None,
                        detail=(
                            f"{rel_path}: WATCHED PATH DOES NOT EXIST, so pair "
                            f"{name} cannot be measured at all (pair budget "
                            f"{budget} bytes) - a missing half is a check "
                            "failure, not a small pair"
                        ),
                    )
                )
                continue
            # git_blob_size keeps its own default git_cwd for the reason given
            # in check_budgets: repo_root is only where watched paths resolve
            # from and is generally not a git repository in a fixture.
            halves[rel_path] = git_blob_size(full_path)

        if not complete:
            continue

        total = sum(halves.values())
        measured[name] = total
        components[name] = halves

        model = models.get(name)
        if model is not None and model.provisional:
            provisional_notes[name] = (
                "model provisional: its split-overhead term rests on "
                f"{model.splits_measured} split"
            )

        left = pair_headroom_sessions(name, total, budgets=budgets, models=models)
        if left is not None:
            sessions_left[name] = left
            if left < PAIR_LOW_HEADROOM_SESSIONS:
                low_headroom.append(name)

        if total >= budget:
            over = total - budget
            breakdown = " + ".join(f"{p} {n}" for p, n in halves.items())
            findings.append(
                Finding(
                    kind="pair_over_budget",
                    path=name,
                    budget=budget,
                    size=total,
                    detail=(
                        f"pair {name}: {total} bytes ({breakdown}), at or over "
                        f"its {budget}-byte pair budget ({over} bytes over) - "
                        "re-running the split will NOT relieve this; it is an "
                        "operator ruling, see PAIR_BUDGETS"
                    ),
                )
            )

    return Report(
        ok=not findings,
        findings=tuple(findings),
        measured=measured,
        headroom_sessions=sessions_left,
        low_headroom=tuple(low_headroom),
        title="doc pair size budget",
        unit="pair",
        low_headroom_threshold=PAIR_LOW_HEADROOM_SESSIONS,
        components=components,
        provisional_notes=provisional_notes,
    )


#: Exit code for a usage error - a flag this module does not understand, or a
#: positional argument it takes none of. Deliberately NOT 1: 1 means the checks
#: ran and a document or a pair is at or over budget, and a caller that cannot
#: tell "you typed something I do not understand" from "the roadmap is too big"
#: learns nothing from either. Matches ``argparse``'s own choice and the value
#: ``tools/archive_link_guard.py`` settled on for the same reason under
#: ``OPS-64``.
USAGE_EXIT_CODE = 2


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for :func:`main`.

    ONE OPTION, AND IT IS REAL. ``--repo-root`` is handed straight to both
    :func:`check_budgets` and :func:`check_pair_budgets` as their ``repo_root``,
    so it changes which files are opened and which byte counts are printed -
    ``OPS-67`` criterion 2's test is that pointing it at a scratch pair makes
    the numbers change, and it does. An option that were accepted and ignored
    would be worse than one refused, because the resulting verdict is true about
    a corpus the caller did not ask about.

    IT SCOPES BOTH CHANNELS, ON PURPOSE, and there is no flag to scope one. See
    the module docstring: a run that measured only the per-document channel and
    printed one OK line would be this item's own defect one level up.

    ABBREVIATION IS DISABLED ON PURPOSE. ``argparse`` accepts any unambiguous
    prefix by default, so ``--repo-roo`` would silently mean ``--repo-root``.
    That is again the same class of defect - a caller getting an answer about
    something other than what they typed - so only the exact spelling is
    accepted.

    THERE ARE NO BUDGET-OVERRIDE OPTIONS, WHICH IS ALSO A DECISION. The budgets
    in :data:`BUDGETS` and :data:`PAIR_BUDGETS` each carry a paragraph of
    measurement beside them saying how the number was derived and what to do
    when it fires. A ``--budget`` flag would let a caller print a green verdict
    against a number nobody measured, which is the "raise the budget to make a
    red run green" antipattern this repository has already written down, handed
    a command-line spelling. Scoping the TREE answers the question this item
    asked; loosening the THRESHOLD answers a different one nobody asked.
    """
    parser = argparse.ArgumentParser(
        prog="doc_size_budget",
        description=(
            "Report each watched continuity document against its byte budget, "
            "and each live-plus-archive pair against its pair budget. Reads "
            "documents and writes no tracked file; see --repo-root."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        metavar="PATH",
        help=(
            "tree the watched documents are resolved from, for BOTH the "
            "per-document and the per-pair channel (default: this repository). "
            "It does not move where git runs: blobs are always hashed into this "
            "repository's own object database, so a non-git PATH is fine"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run both real checks and print a human report for each.

    ``argv`` is the argument list WITHOUT the program name; ``None`` means read
    ``sys.argv[1:]``, which is what this module's ``__main__`` block relies on.
    An in-process caller - a test, most often - should pass an explicit list,
    because a test runner's ``sys.argv`` is not this module's and is now refused
    rather than ignored.

    Two channels, printed in order: the per-document budgets in :data:`BUDGETS`
    and the per-pair budgets in :data:`PAIR_BUDGETS`. Both are printed on every
    run, because the pair channel exists to make the two archives visible and an
    archive that only appears in the output when it fails is an archive nobody
    watches.

    EXIT CODES, KEPT DISTINCT BECAUSE THEY ARE DIFFERENT FACTS:

    ``0``
        Both checks ran and found nothing, OR ``--help`` was asked for.
    ``1``
        A check ran and found a Finding - a document or pair at or over budget,
        or a watched path missing. Low headroom is a warning and never reaches
        this code; see :data:`LOW_HEADROOM_SESSIONS`.
    ``2``
        A usage error: an unknown flag, an abbreviation, or a positional
        argument. See :data:`USAGE_EXIT_CODE`.

    WHY ``argparse``'S ``SystemExit`` IS CAUGHT AND TURNED BACK INTO A RETURN
    VALUE. ``parse_args`` exits the process on a usage error, which would make
    every in-process caller wrap this function in ``pytest.raises`` and would
    make the return type a lie. Catching it keeps the contract "``main`` returns
    an int, always" - and the code is taken FROM the exception rather than
    replaced, so ``--help``'s 0 stays 0 while an error's 2 stays 2. ``argparse``
    has already written its own message, naming the offending argument, to
    stderr by then; the ``str`` branch below exists only for the documented case
    where ``SystemExit`` carries a message instead of a code.

    NOTHING IS PRINTED ON A USAGE ERROR EXCEPT ARGPARSE'S OWN MESSAGE. A refused
    run that still printed a green report about the live documents would leave
    the exact artifact this item was filed against sitting in the caller's
    terminal, one exit code away from being believed.

    Still never mutates a tracked file or the working tree. It does write loose
    git objects - see the module docstring - which is what ``git add`` does too.
    """
    args_list = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return USAGE_EXIT_CODE

    repo_root = Path(args.repo_root)
    print(f"doc size budget: scope both channels under {repo_root}")
    report = check_budgets(repo_root=repo_root)
    print(report.format())
    pair_report = check_pair_budgets(repo_root=repo_root)
    print(pair_report.format())
    return 0 if report.ok and pair_report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
