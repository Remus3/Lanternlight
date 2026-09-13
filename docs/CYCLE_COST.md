# Cycle cost - what one refute-fix-refute cycle costs this repository

`ROADMAP.md` `OPS-87` criterion 4 asks for two numbers: how many full-suite runs
and how much wall clock one complete refute-fix-refute cycle takes today, and
the same two numbers afterwards, **both measured and neither estimated**. This
document is where those numbers live. It is read by a cold session that has no
other context and by the sibling projects that were told this repository would
publish what its own adversarial review costs, so it is written in full prose
rather than in the terse dialect this project uses in chat.

Two halves are reported and they are kept apart on purpose. The BEFORE half is
**reconstructed** from git history and from full-suite results that this
project's own prose happened to quote; its run count can only ever be a lower
bound. The AFTER half is **counted** from records that `ops/suite_recorder.py`
now writes for every pytest session in this tree; its run count is a fact. A
floor and a count are different kinds of number, and the single most important
sentence in this document is the one further down saying that they must not be
divided by one another.

**Nothing here is a constant.** Every figure below was printed by the
instrument at the moment named beside it, and every one of them moves. Re-derive
them yourself from the repository root:

```
python -m ops.cycle_cost
```

That prints both halves in one report. `--window N` widens or narrows the
historical window; `--since <ISO-8601 timestamp>` replaces the live half's
default boundary with an explicit one.

## What a cycle is, pinned

A cycle is ONE complete refute-fix-refute round on ONE roadmap item: the commit
that claims the item done, plus every later commit that exists because an
adversarial pass found something in it.

It is deliberately **not** "a session" and **not** "a day". The unit `OPS-87`
is complaining about is the round trip - the claim, the refutation, and the
repair - because that is the unit whose cost decides whether an adversarial
pass is affordable on every slice or only on some. A session may contain
several cycles and a cycle may straddle several sessions.

## The BEFORE half - reconstructed, and its run count is a FLOOR

### Where each number comes from

The instrument is `ops/cycle_cost.py`, and it derives everything at run time
rather than reading a filed figure.

* **Wall clock** comes from git, using the **committer** date (`%ct`) rather
  than the author date. Author date survives a rebase or a cherry-pick and so
  answers "when was this work first written", which is a different question
  from the one being asked; committer date answers "when did this commit enter
  this history", and the cost being measured is elapsed real time spent on the
  round trip in this tree.
* **Cycle membership** comes from two sources of different strength. The
  high-confidence seed is the literal sentence "refutation pass over `<sha>`"
  where the ledger names the commit a fix commit exists because of. There are
  exactly two such sentences in `docs/LEDGER.md`, which is not a corpus, so the
  rest of each cycle is assembled by grouping commits that name the same
  `OPS-nn` identifier in their subject line or in the heading of a ledger entry
  they add. The grouping is weaker than the anchor and the report labels every
  cycle as `ANCHORED` or `GROUPED` so a reader can tell which is which.
* **The suite-run figure** comes from full-suite results QUOTED in commit
  messages, ledger entries and the hand-off file - phrases such as
  "3274 passed". Each DISTINCT quoted result is evidence that at least one real
  full-suite run happened. Nothing in the artifact records a run directly,
  which is precisely the gap `ops/suite_recorder.py` was written to close.

### The numbers, observed 2026-09-13 with `HEAD` at `93294fa` and a 40-commit window

| Figure | Value | Kind |
|---|---|---|
| Cycles found | 14 (4 anchored, 10 grouped) | exact for this window and this parser |
| Distinct commits inside a cycle | 25 of the 40 in the window | exact |
| Wall clock summed over cycles | 8d 19h 2m 45s (759765s) | double-counts shared commits, see below |
| Mean cycle span | 15h 4m 28s (54268s) | derived from the two figures above |
| Longest cycle | `OPS-57`, 2d 15h 42m 20s | exact span, elapsed not effort |
| Shortest cycle | `OPS-61`, 14m 40s | exact span, elapsed not effort |
| **Full-suite runs summed over cycles** | **>= 37** | **a FLOOR, never a count** |

### Why that run count is a floor, stated as a floor

1. Two runs that produced the same pass count collapse into a single quoted
   figure, because the parser counts DISTINCT figures. A cycle that ran the
   suite four times and got the same number each time contributes one.
2. A cycle that quotes no full-suite result at all contributes zero, and a zero
   there means NO EVIDENCE rather than no runs. In the observation above, zero
   of the fourteen cycles were in that position, but the possibility is real
   and a wider window reaches cycles that are.
3. Collect-only figures ("3275 collected") are reported beside the floor and
   never inside it, because `--collect-only` costs about a second rather than
   about six minutes and counting it as a suite run would flatter the BEFORE
   number.
4. A commit that names its item only in prose is invisible to the grouping, so
   the number of CYCLES is itself a floor, which drags the run total down with
   it.
5. The parser's full-suite threshold is 1000 passed. That is a parser
   parameter, not a measurement. In the window above the largest figure below
   it was 382 and the smallest at or above it was 1264, so it separated the two
   populations cleanly on this data - and a cycle from before this suite passed
   1000 tests would be undercounted to zero by it.

The summed wall clock also carries a defect worth naming rather than burying:
**cycles overlap**. In the observation above, 37 commit slots across 14 cycles
resolve to 25 distinct commits, because one commit here routinely closes three
items at once. The summed figure therefore double-counts every shared commit,
and the mean derived from it inherits that.

## The AFTER half - recorded, and its run count is EXACT

### The boundary rule

A cycle has to have edges before it can have a cost, and **the only boundary
available on disk is time**. Nothing in a suite-run record says which cycle the
run belonged to.

The rule, in one sentence: a record is inside the cycle when its `started_utc`
is at or after a start point, and there is no upper bound because the cycle
being measured is the one still running. By default the start point is the
**committer timestamp of the tip commit**, which makes the default offer "the
cycle in progress"; a caller may pass an explicit start with `--since`.

Only records with `full` true and `nested` false are counted. A filtered run is
not the thing criterion 4 is measuring, and a nested run is one of this suite's
own pytest subprocesses wearing a suite's clothes. Every record that falls
inside the boundary but fails either test is reported as an exclusion, with the
reason the recorder itself gave, so a wrong exclusion can be argued with rather
than merely suspected.

### The numbers, observed 2026-09-13T03:55Z with the boundary at the tip commit `93294fa` (2026-09-13T02:36:55+00:00)

| Figure | Value | Kind |
|---|---|---|
| Full-suite runs inside the boundary | 3 | **EXACT** |
| Summed suite wall clock | >= 1017.1s (16m 57s) | **a FLOOR**, see below |
| Elapsed span, boundary to newest record | 1h 23m 21s (5001.3s) | exact as measured, a lower bound on the finished cycle |
| Records excluded from the count | 37 | exact |
| Records that could not be read at all | 0 | exact |

The three counted runs, oldest first, took 345.2s, 370.1s and 301.8s, each in
its own process. The first two collected 3357 tests and passed 3356; the third
collected 3377 and passed 3376, because the cycle being measured added tests to
the suite while it ran. That is worth saying out loud: the three runs are not
three runs of the same suite, so their durations are not three samples of one
quantity and averaging them would describe a suite that never existed.

**The observation is timestamped because the instrument is inside what it
measures.** Verifying this document means running the suite, and running the
suite writes another record, which moves every figure in the table above. The
numbers are what the instrument printed at the instant named in the heading;
re-running `python -m ops.cycle_cost` will give a larger run count and a longer
span, and that is the instrument working rather than the document rotting.

The thirty-seven exclusions carried eighty-three reasons between them, since one
record can fail several tests at once: thirty-seven runs that did not enter every
test module on disk, twenty-eight narrowed by target arguments, nine collect-only
runs and nine runs nested inside another pytest in this tree.

### Which of those are exact and which are floors

* The **run count is exact**. It is a count of records, not an inference from
  prose. It is exact about what was recorded; see the concurrency caveat below
  for what "recorded" does and does not establish.
* The **summed suite wall clock is a floor**. `duration_s` is measured from
  `pytest_configure` to `pytest_sessionfinish`, so interpreter startup and the
  collection that happens before `pytest_configure` fall outside it. It reads a
  little under what a shell stopwatch reports, which means the figure can only
  understate real elapsed time in the suite.
* The **elapsed span is exact as measured between its two points**, and is a
  lower bound on the finished cycle, because the cycle was still open when it
  was taken. It is also elapsed time rather than effort: nobody was necessarily
  working for all of it.
* The **exclusion counts are exact**.

### The concurrency caveat - what a record actually proves

**A record proves that SOME session on this machine ran a suite between the two
points. It does not prove that THIS cycle did.**

`ops/runtime/suite_runs/` is a single directory shared by every session working
in this tree, and this is not a theoretical worry: on the recorder's own first
measured run, most of the records present had been written by a concurrent
mutation sweep belonging to a different slice. The report prints how many
records and how many distinct process ids sit inside the boundary for exactly
this reason, so a reader can see the shape of what they are counting.

The boundary compounds it in both directions. If the cycle being measured had
already landed a commit before the measurement, the tip commit starts the
window too late and the count is too low. If two items were worked in the same
span, the count is too high. The instrument cannot tell those apart, and
neither can a reader without knowing what the session was doing.

## What is NOT comparable between the two halves

**The BEFORE run count and the AFTER run count cannot be compared, and no ratio
between them means anything.**

They are not two measurements of the same quantity taken at different times.
The BEFORE figure counts DISTINCT SUITE RESULTS THAT SOMEONE HAPPENED TO QUOTE
IN PROSE across fourteen reconstructed cycles; the AFTER figure counts RECORDED
PYTEST SESSIONS inside one time window. A quoted result collapses repeats, so
the BEFORE figure is a lower bound of unknown tightness, while the AFTER figure
is exact about records and silent about which cycle wrote them. Dividing one by
the other produces a confident-looking number that neither half supports.

This repository has already had to withdraw exactly that kind of figure once.
`LL-0244` records a number published to another tree that this project could no
longer reproduce, and the ruling that followed it was to withdraw such a figure
in a note rather than quietly correct it here, because a single
reproducible-looking figure is what another tree designs against. The same
discipline applies before the fact: this document declines to state a speed-up,
a multiple, or a percentage.

What CAN be said, and is all that can be said from these two halves:

* Before this work, the number of full-suite runs in a cycle was **not
  recorded anywhere** and could only be reconstructed as a lower bound.
* After this work, it is recorded per run, and the count for a stated time
  window is exact.
* The wall clock of a cycle was derivable from git before and still is; what
  was added is the wall clock of the SUITE RUNS inside it, which git never
  knew.

## What the instrument cannot see

For the historical half:

* Every cycle span starts at the cycle's FIRST COMMIT, so any work done before
  that commit is outside git entirely and every span is a lower bound.
* A span is elapsed time, not effort. This project's cycles routinely straddle
  a night. The report prints the widest gap between two consecutive commits
  inside a cycle beside the span for that reason.
* A grouped cycle may hold a commit that FILED an item rather than repaired it,
  because the grouping evidence is a shared identifier and nothing more.
* A document reorganisation re-adds history. The `OPS-57` split created
  `docs/LEDGER_ARCHIVE.md` and therefore "added" every historical ledger entry
  in a single commit; read naively that gave a two-commit cycle a floor of
  seventy suite runs. The instrument now refuses an added ledger entry whose
  own date trails the commit that added it, which is why this document's
  historical figures are not that. This defect was found by RUNNING the
  instrument, not by reasoning about it beforehand.

For the live half:

* Nothing on disk says which cycle a run belonged to. See the boundary rule and
  the concurrency caveat above.
* Only the newest 200 records survive a write, so a cycle long enough to exceed
  that loses its oldest runs.
* A run killed before `pytest_sessionfinish` writes no record at all, so a
  crashed or interrupted suite run costs real time and is invisible here.
* A fast run cannot be told from a legitimately faster suite. A warm filesystem
  cache, another process competing for the machine, and a suite that genuinely
  got quicker all look identical in `duration_s`.
* The full-versus-filtered test is biased toward calling a run FILTERED when it
  is unsure - an option it does not recognise has its value misread as a target
  path. That errs against flattering the AFTER number, which is deliberate.

## What the measuring slice deliberately did not say

The slice that took these measurements made **no recommendation** about
whether the pre-flight, the recorder or any other instrument should be wired
into a hook, a ritual or a command. That was deliberate: the decision belongs
to whoever holds the plan, not to the slice that took the measurement, and a
measurement taken by someone with a proposal to defend is worth less than one
taken by someone with none.

## The decision the merger then took, and the evidence it rests on

`OPS-87` still-open item 3 asked where, if anywhere, the pre-flight gets wired.
It was left open on purpose, because wiring it before the cycle-cost numbers
existed would have been optimising without the measurement - the one thing the
item forbids. The numbers now exist, so the decision is taken here.

**A git hook is REFUSED, and the evidence against it is our own.** Back-test
experiment one in [`PREFLIGHT_BACKTEST.md`](PREFLIGHT_BACKTEST.md) ran the
pre-flight at the parent commit of every commit that filed a gate-reachable
finding, and caught **0 of 17**. That is not a weak gate; it is a gate pointed
at the wrong window. A new test module, its registration and its ledger entry
land in ONE commit, so the tree in which the registration was missing existed
for twenty minutes inside a session and was never committed at all. A
pre-commit or pre-push hook guards a boundary this class of defect does not
cross. Experiment two, which rebuilt that mid-session state, caught **9 of 9**.

**The wiring is therefore into the LANE CONTRACT**, the artifact a slice reads
at the moment it is about to claim done, which is the window experiment two
measured. It is generated by `ops/lane_contract.py`, so every lane's contract
carries it and none can drift out of carrying it;
`tests/test_lane_contract.py` fails if the command disappears, if it is moved
after the merge-gate instruction a MERGER runs, or if the sentence saying it
does not replace an adversarial pass is dropped.

### The event that put the linter in the pre-flight set

This is a measured event from the session that closed criterion 4, not a
hypothetical. Three slices landed work. Each ran `python -m ops.preflight`
before claiming done and each got `PRE-FLIGHT PASS`. `ruff check .` then failed
with seven findings on lines those slices had just added, and the repository's
own pre-commit gate refused the commit. The defect was found by the
**adversarial pass** - the most expensive instrument this project owns - and it
was a mechanical, sub-second, program-answerable lint error.

Be precise about what that cost and what it did not. Nothing was going to ship:
the commit gate would have refused it, which is back-test experiment one's
finding over again. What was spent was an adversarial round on a lint error.
That is exactly the substitution `OPS-87` criterion 2 exists to prevent, so
`ops/preflight.py` now runs the linter, borrowing the invocation from
`ruff_command()` in `tools/precommit_gate.py`, so there is one truth about
how ruff is called here.

Back-tested against the real event rather than asserted: reintroducing one of
the seven findings and running the pre-flight end to end gives
`PRE-FLIGHT REFUSE`, `pytest: 382 passed, 1 skipped`, `lint: Found 1 error.
(0.07s)`. The lint step costs **0.07 seconds** against a pre-flight measured
serially on a quiet machine at 17.93, 21.45 and 24.44 seconds.

### What this decision does not claim

It does not claim a saving. No cycle has yet run end to end with the linter in
the pre-flight, so the number that would demonstrate one does not exist, and
this project has already had to withdraw one confident figure it could not
reproduce (`LL-0244`). It also does not reduce adversarial review by one pass:
60 of the 135 events in [`REFUTATION_CENSUS.md`](REFUTATION_CENSUS.md) are real
defects in a deliverable, and no program described here would have found one of
them.
