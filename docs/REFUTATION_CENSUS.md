# The refutation census - what the refute / fix / refute-the-fix cycle costs here

`OPS-87` criterion 1. This document reports a MEASUREMENT. It is the thing that
had to exist before anything was optimised, because a proposal that names no
bucket is a guess about where the time went.

Nothing here is a stored count. Every number below is printed by
`python -m ops.refutation_census`, which recomputes all of them from the
per-event rows in [`refutation_census.tsv`](refutation_census.tsv) each time it
runs. Re-derive them rather than quoting this document:

```bash
python -m ops.refutation_census
```

## The corpus, and where the line was drawn

64 ledger entries dated `2026-09-08` or later and numbered up to `LL-0236` -
five days ending on the day `OPS-87` was filed, a corpus CLOSED AT BOTH ENDS
so that filing another entry cannot move a published percentage - read in five
disjoint line ranges by five extraction
slices. Every one of the 64 was examined, and the data file declares which,
derived from the line ranges the slices were given rather than from the date
window, so the coverage check compares two independent derivations.

That declaration exists because the first pass did not have it. Four slices
covered 53 of the 64 entries and nothing in the data said so: eleven entries
were never opened, and every percentage was quietly computed over a corpus 17
per cent smaller than the report named. An entry with zero refutation events
and an entry nobody read are identical in a file of events.

## The answer, and the fact that grading it changed it

**135 refutation events** across the 64 entries.

| Bucket | As the extraction slices filed it | After adjudication |
|---|---|---|
| (a) a real defect in the deliverable | 50 | **60** |
| (b) a missing registration or plumbing step | 13 | 9 |
| (c) a stale recital in a document | **54** | 53 |
| (d) an artifact of the mutation harness | 12 | 7 |
| (e) an over-report by the check under test | 6 | 6 |

**LARGEST BUCKET: (a), a real defect in the deliverable, with 60 of 135
events.**

The two columns are both reported because the difference between them is a
result. Three adjudicators, none of whom produced the rows they graded, read the
ledger entry behind every event and moved 12 of 135. Every move but one ran the
same way - from a cheap bucket to (a) - under two rules the adjudicators
converged on independently:

* a mismeasuring instrument that is TRACKED SHIPPED CODE is a real defect, not a
  harness artifact; only an ad-hoc scratch harness stays in (d);
* a surviving mutant exposing a coverage gap is a real defect, not a missing
  registration.

Before grading, the answer was "the largest bucket is stale prose". After
grading it is "the largest bucket is real defects". A census that graded itself
would have reported the first.

## The number that decides what to build, and it is not the bucket

A bucket says what KIND of thing was wrong. It does not say whether a program
could have found it. So every event was also judged for GATE-REACHABILITY:
could a program reading the tree have caught this before an adversarial agent
was dispatched, with no human judgement and no knowledge of what the session
intended? Defaulting to NO-GATE when unsure, and NO-GATE for any check that
would fire on hundreds of innocent lines.

**42 of 135 events (31.1 pct) are gate-reachable. 93 are not.**

By bucket as originally filed: (b) 10 of 13 reachable, (c) 15 of 54, (a) 14 of
50, (e) 3 of 6, (d) 0 of 12.

### This refutes a premise of the item that commissioned it

`OPS-87` criterion 2 states that everything in classes (b) and (c) "is
answerable by a program". Measured, that is true of (b) and false of (c). Of 54
stale-recital events, 15 were judged reachable and 39 were not, because the
dominant failure in that class is not a wrong NUMBER but a wrong MECHANISM,
CAUSE, SCOPE or PREDICTION - "joining is one environment variable", "dropping a
stash removes its commits", "the lookup is cached at import time". None of those
names a derivable quantity. Each was refuted only by an experiment nobody had
thought to run.

And the one mechanical family inside (c), a number in prose, carries a trap this
repository built for itself. Our own convention is that a dated measurement
stays correct after it stops reproducing. A dispatch-time re-derivation would
therefore have reported `LL-0199` WRONG at the exact moment it was right: the
check that catches class (c) also manufactures class (c). That check is
deliberately absent from `ops/preflight.py`, and its absence is a finding rather
than an omission.

## The two axes, counted independently of the buckets

* **45 of 135 events (33.3 pct) refuted a claim INHERITED from a durable
  record** - a document, a roadmap item, an earlier ledger entry, a hand-off -
  which was true when written. No write-time gate can fail on those by
  construction, because nothing was being written when they went stale.
* **11 of 135 (8.1 pct) were a fix of a fix.** That is the compounding cost the
  operator's instruction named, and it is smaller than it feels from inside a
  session.
* 27 of 135 were classified with declared uncertainty. That figure is published
  rather than smoothed away.

## What this census cannot tell you

* **It is a LOWER BOUND on events.** The ledger is written by the party being
  measured. A mechanical catch is legible and gets written up; an unnoticed
  wrong-object probe leaves no trace at all.
* **It cannot say a bucket letter is the RIGHT letter**, only that a human
  assigned one against a ledger sentence that still exists. That anchor is
  checked on every run - see `tests/test_refutation_census.py` - so a
  classification cannot outlive its evidence, but nothing checks the judgement
  itself beyond the adjudication recorded above.
* **The extraction slices were not independent of each other in method.** They
  read the same spec and the same house style. Agreement between them is a
  hypothesis, not corroboration, which is why the adjudication is a separate
  pass by different agents and why its 12 moves are reported rather than merged
  away.

## What was built on it

* `ops/preflight.py` - the mechanical subset, measured at 19.3 seconds against a
  full suite measured at 396.2 seconds the same day. It targets (b) in full and
  the reachable slice of (c), and it says in its own report what it does not
  cover.
* `tools/preflight_backtest.py` - criterion 3. It stands the tree up as it was
  when a finding was filed and runs the pre-flight there, reporting CAUGHT,
  MISSED, NO-GUARD or UNBUILDABLE. See
  [`PREFLIGHT_BACKTEST.md`](PREFLIGHT_BACKTEST.md) for the result.
* [`ORCHESTRATION_TIERS.md`](ORCHESTRATION_TIERS.md) - criterion 5, which slice
  kinds need the strongest model, with this session's own evidence for why.
