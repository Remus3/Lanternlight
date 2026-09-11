# ADR-007: Lanternlight takes a lane slot, and its lock root lives in this repository

## Context

Several projects share this one machine and one Anthropic account. Their
headless loops therefore contend for one concurrency budget, and the sibling
projects coordinate that contention through a directory of lock files that they
describe to each other on the `moon_sync_inbox/` channel.

**The operator ruled in chat on 2026-09-07 that Lanternlight takes a lane slot
in that scheme.** The decision is settled and is not a session's to re-litigate.
Recorded in `ROADMAP.md` under `OPS-42` question 1, alongside the earlier
rulings that adopted the cross-project lock (`OPS-35`) and the convergence
charter (`OPS-36`) and assigned this repository the key `ll`.

What was NOT settled by that ruling, and is settled here, is **where our bucket
of lock files lives**.

### The protocol, reconstructed in our own words

Written down here so a cold session can re-implement it without opening a
sibling's file, per `OPS-35` acceptance criterion 2.

A bucket is a directory holding lock files under two naming schemes at once,
because a reservation cannot be expressed by an index alone:

```
<bucket>/reserved-<key>.lock   one per participating repository; ours is `ll`
<bucket>/<n>.lock              surplus, first-come, zero-based
```

so a five-repository bucket with two surplus slots holds seven files: one
reserved lock for each of the five keys below, plus surplus zero and one.

- **Key strings.** `rc`, `lw`, `rsc`, `cs`, `ll`. Lowercase, no spaces, no
  paths. The set is closed; a key outside it is refused rather than given
  surplus, because a silent fallback presents exactly as a busy bucket and gets
  debugged as contention rather than as a misconfiguration.
- **Claim.** One atomic `O_CREAT | O_EXCL` create per candidate slot, tried in
  order: the caller's own reserved lock first, then the surplus locks in
  ascending index order. The first create that succeeds is the lane. Nothing
  blocks and nothing waits; an exhausted bucket answers "busy" and the caller
  decides what that means.
- **Payload.** A JSON object written into the lock at claim time, carrying
  `pid`, `ts`, `repo`, `run_id` and `cycle`. `repo` is a human-facing label for
  somebody reading the bucket - it is explicitly NOT what the reservation keys
  on.
- **Release.** Unlink the lock. On Windows a concurrent reader's open handle can
  refuse the unlink, so the release retries with a short bounded backoff, and if
  the file still cannot be removed it rewrites the payload so the stale arm
  fires immediately instead of hours later.
- **Reserved floor.** Every participating repository has one lock nobody else
  may take. That is the guarantee: a repository starved of surplus by a busy
  neighbour can still always start one lane, and a busy repository can burst
  into the surplus.
- **Stale arm.** 4.5 hours (16200 seconds). A lock older than that is
  reclaimable regardless of what its `pid` says. Reaping must understand BOTH
  naming schemes; a reaper blind to the reserved scheme costs that repository
  its floor for the whole window, which is the orphan bug at a new address and
  harder to see there, because a missing reservation reads as a policy decision
  rather than as a leak.

Two fields of that payload were seen quoted verbatim in a sibling's report of
its own live bucket (`pid`, and `repo` carrying a full checkout path). The other
three are reconstructed from the acquirer call signature a sibling quoted from
its own tree and from prose describing the staleness arms. Our reader therefore
treats every field as optional and treats a missing one as absent rather than as
a default - a lock with no readable `ts` is stale, never fresh.

### Identity, not path

A sibling measured the near-miss that makes this correctness rather than
cosmetics: its live locks carried the full checkout path as the repository
label, and its checkout root was renamed this week. Under a reservation keyed on
that spelling, the rename would have abandoned the held reservation and claimed
a second one while the first sat orphaned until the stale arm fired. Two
repositories would then have been one reservation short between them.

We adopt the fix, not the defect: the reservation keys on the short repository
key, which is a constant.

### The root question

A sibling reports that the shared module it declined to vendor defaults its lock
root to a machine-wide bucket under `ProgramData` named for one particular
sibling project, and that several trees ration slots between themselves in that
bucket. That sibling declined to adopt the default and pinned its own root
inside its own repository with a test, on the grounds that taking the shared
default unilaterally would consume a slot those trees are sharing - a change to
another tree's behaviour, made without asking anyone.

That reasoning is a note's reasoning and it is not authority here, but the
underlying fact is checkable and the consequence is ours either way. Two things
decide it for this repository:

1. **The widening has not landed.** The reserved-floor design is a proposal at
   width 7 (five reserved plus two surplus). What is deployed today is a shared
   bucket of three first-come slots with no reserved names in it at all. A
   reserved lock written into that bucket today is a file nobody's reaper
   recognises, and a surplus lock written into it today is a slot taken away
   from the trees already rationing three of them. Neither is interoperation;
   both are a unilateral change to somebody else's concurrency.
2. **The standalone rule still binds.** The operator's exception adopts the
   PROTOCOL - the namespace shape, the key strings and the payload shape. A
   shared writable directory that other projects depend on is a shared runtime
   resource, which is the same class of thing as a shared port, and the ports
   table in `CLAUDE.md` exists precisely so that knowing a neighbour's block is
   not treated as permission to use it.

## Decision

**Lanternlight takes the lane slot `ll` and implements the reserved-floor
protocol in `ops/lane_slot.py`, re-implemented from the protocol above. Our lock
root defaults to a bucket INSIDE this repository, at `ops/runtime/lane_slots/`,
and is overridable by the environment variable `LL_LANE_SLOT_ROOT`.**

Specifically:

- Nothing is vendored. No file was copied in from `moon_sync_inbox/` and no
  module is imported from a sibling tree. Techniques and protocol facts are not
  copyrightable; source is, the drop carried no license statement, and this
  repository is public under Apache-2.0.
- The default root is inside the repository, is under a gitignored directory, is
  pinned by `tests/test_lane_slot.py::TestLockRootIsOurs`, and no shared bucket
  path appears anywhere in the module as a value.
- Joining a shared bucket later is a CONFIGURATION act - one environment
  variable - and not a code change. It still needs an operator ruling, because
  it changes another project's available concurrency.
- Nothing is acquired at import time, and a session that acquires nothing runs
  to completion with the bucket absent entirely.
- No port is allocated. This project's block is 8810-8819 and this work uses
  none of it.

## Consequences

**What this buys.** The protocol is implemented and tested, the repository key
is pinned, the identity-not-path fix is adopted with a test that renames the
root under a held reservation, and the reap understands both naming schemes with
a test that plants a stale reserved lock specifically. Flipping to a shared
bucket the day the operator rules for one is an environment variable.

**What this costs, stated plainly rather than hedged out.** With the root inside
this repository, our governor bounds only Lanternlight's own concurrency. It
does NOT contend with the siblings today, so it delivers none of the
cross-project rationing the scheme exists for, and `OPS-35` acceptance criterion
5 - interoperation proven against a real sibling holder rather than a mock - is
NOT met by this ADR and stays open. A mock proving we agree with ourselves is
the two-agents-agreeing failure in a new costume, and this decision does not
pretend otherwise.

**A second cost.** A repository-local bucket means a sibling's reaper will never
reclaim a lock we leak, and ours will never reclaim theirs. That is the correct
consequence of separate buckets rather than a defect, but it means our stale arm
is the only thing that reclaims our leaks, so it is tested directly.

**What would change this.** An operator ruling that Lanternlight joins the
shared machine-wide bucket, taken in a round with the other carriers so that the
width and the reserved names land in the same window. On that day this ADR is
superseded by a new record, never edited into a different decision.

## Status

**SUPERSEDED on 2026-09-10 by
[ADR-008](ADR-008-join-the-shared-bucket.md).** The operator ruled in chat that
day - "yes, join the shared bucket" - which is the ruling the "What would
change this" section above asked for. Per that section, this record is
superseded by a new one rather than edited into a different decision: everything
above stands as the reasoning that was correct while it held, and ADR-008
carries the decision now in force.

Two parts of this record are specifically corrected there rather than merely
replaced. Its claim that joining is "a CONFIGURATION act - one environment
variable - and not a code change" was REFUTED by measurement on 2026-09-10:
the reserved-first order would have written `reserved-ll.lock` into a bucket
with no reserved names in it and would never have reached a surplus slot, so a
bare environment-variable join would have rationed with nobody. And its note
that three of the five payload fields were reconstructed rather than observed
is now closed - all five were read off a live lock, and the `ts` unit was
measured.

The original status, kept for the record: Accepted. The lane-slot decision
itself was ruled by the operator on 2026-09-07; the root location was this
record's own decision and was revisable by a later ADR, which is what happened.
