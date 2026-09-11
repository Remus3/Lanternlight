# ADR-008: Lanternlight joins the shared lane-slot bucket, surplus-only until the reserved widening lands

Supersedes [ADR-007](ADR-007-lane-slot-root-is-ours.md). ADR-007 is not edited
into a different decision; its reasoning stands as the reasoning that was
correct on the day it was written, and this record replaces its outcome.

## Context

### The operator's ruling

**The operator ruled in chat on 2026-09-10: "yes, join the shared bucket".**

That is the ruling ADR-007 left a gate open for. ADR-007 said the root location
was revisable by a later ADR, that joining a shared bucket "still needs an
operator ruling, because it changes another project's available concurrency",
and that on the day such a ruling arrived "this ADR is superseded by a new
record, never edited into a different decision". This is that record.

Two things the ruling did NOT lift, and this record does not act against
either: `OPS-48` - no soliciting RC or RSC - and `OPS-68` - the responder runner
and the propagation of any of this to siblings are on standby. **No note was
sent to any sibling for this change, and nothing was written into any sibling's
directory.** Joining the bucket is an act performed entirely inside this tree.

### What was measured on disk, 2026-09-10

This is the first FIRST-PARTY evidence this project has for the shared bucket,
and it is worth separating from the note-sourced picture that preceded it.

The bucket exists at `%PROGRAMDATA%\lw-loop\slots` and held exactly one file:
`0.lock`, 104 bytes, last written 2026-09-09T15:55:23 local. Its body parses as
JSON with exactly five fields: `cycle`, `pid`, `repo`, `run_id` and `ts`.

- **The payload reconstruction is CONFIRMED.** ADR-007's protocol section said
  that only `pid` and `repo` had been seen quoted verbatim, and that `ts`,
  `run_id` and `cycle` were reconstructed from a call signature a sibling
  quoted from its own tree. All five are now observed on disk, in a live lock
  this project did not write, and the set is exactly five with nothing else in
  it. `ops/lane_slot.py` encodes those five and no others, so our writer and
  the observed wire agree.
- **The `ts` unit is now measured rather than assumed.** It is UNIX EPOCH
  SECONDS as a float. That was an open gap in ADR-007, which described the
  stale arm in seconds without having seen the field. The observed value made
  the lock about 30.5 hours old at the time of reading, far past our
  `STALE_SECONDS` of 16200.0, so what is in that bucket today is a LEAKED lock
  rather than a held one.
- **No reserved name of any kind is in that bucket.** There is no
  `reserved-*.lock` for any key, four days after the channel notes that
  proposed the reserved-floor widening. So the widening has not landed.
- The `repo` field of that lock carries a sibling's checkout path. It is not
  quoted here, and no lock body from that bucket is ever committed.

One thing that was NOT measured and must not be read as though it were: the
bucket's WIDTH. A directory holding one lock cannot reveal how many slots its
participants ration. The channel notes describe three first-come slots. That
figure is note-sourced and is treated as such below.

### Why a bare environment-variable join is refuted by measurement

ADR-007 says joining is "a CONFIGURATION act - one environment variable - and
not a code change". **That is wrong, and the measurement above is what refutes
it.**

`slot_order("ll")` returns `("reserved-ll.lock", "0.lock", "1.lock")`. Our own
reserved floor is tried FIRST, which is correct for the protocol as agreed and
wrong for the bucket as deployed. Point that order at the shared bucket today
and both halves of the intended behaviour invert:

1. We would create `reserved-ll.lock` on essentially every acquire, because it
   is the first candidate and nobody else ever takes it. That is a file no
   other participant's reaper recognises. A lock we leak there is reclaimed by
   our stale arm or by nothing.
2. We would almost never reach a surplus slot, so we would not contend with the
   siblings at all. The whole point of joining - rationing one concurrency
   budget on the same terms as everyone else - would not happen, while the
   configuration said it had.

A join that writes a private file into a shared directory and rations with
nobody is not a join. So the decision below is a code change, not a setting.

## Decision

**Lanternlight's lane-slot bucket defaults to the shared machine-wide bucket,
and the order it tries slots in is decided by LOOKING at that bucket rather
than by believing anything about what the siblings deployed.**

### 1. The default root is the shared bucket

`ops.lane_slot.default_root()` resolves, in order: the `LL_LANE_SLOT_ROOT`
override; then the shared bucket; then the in-repository bucket at
`ops/runtime/lane_slots/` as a fallback.

The shared bucket is resolved THROUGH the `PROGRAMDATA` environment variable
and the relative namespace `lw-loop/slots`, never as a drive-rooted literal.
Two reasons, and the second is the load-bearing one: a literal absolute path is
unportable, and `tests/test_lane_slot.py::` `test_no_shared_bucket_path_is_`
`written_into_the_module` - written under ADR-007 and deliberately kept
unchanged - still asserts that no such literal appears in the module. The
namespace string is a WIRE fact, which the operator's `OPS-35` exception
explicitly permits us to hold in common; an absolute path baked into source is
a dependency, which it does not.

If the all-users root cannot be resolved at all, `shared_root()` answers `None`
rather than inventing a drive letter, and the in-repository bucket is used. A
machine with no shared bucket still has a governor bounding our own loop.

**This is a real join, not a switch nobody turns on.** Any caller that does not
name a root now contends in the shared bucket by default.

### 2. Surplus-only while the bucket has no reserved names

`bucket_slot_order(root, key)` decides the try order from the bucket's observed
shape:

- reserved names present: `("reserved-ll.lock", "0.lock", ... )` - our own
  floor first, exactly as the agreed protocol says;
- otherwise: the surplus names only, and `reserved-ll.lock` is never a
  candidate.

**The transition needs no code change.** It fires the first time any other
participant's `reserved-<key>.lock` is in the bucket when we look - which is
what the widening landing looks like from outside, and it will land in somebody
else's tree on a day nobody tells us about.

### 3. Detection has three answers, and could-not-look is one of them

`reserved_scheme_state(root, key)` returns one of `RESERVED_PRESENT`,
`RESERVED_ABSENT` or `RESERVED_UNKNOWN`. The third is returned when the bucket
is missing, is not a directory, or the listing is refused.

**`RESERVED_ABSENT` and `RESERVED_UNKNOWN` are different facts and are reported
apart**, even though both take the surplus-only branch. This repository keeps
re-learning the same lesson in new costumes - an empty grep is a claim about
your pattern, a crashed `grep -iF` looks exactly like a clean negative, a
`taskkill` that killed nothing looked exactly like one that worked - and every
one of them is a failed look wearing the costume of a measured absence. An
operator reading the state needs to know which of the two they have.

**Could-not-look fails toward surplus-only, and here is the justification.**
The conservative direction is the one that does not write an unrecognised file
into a directory other projects share. Taking our floor on a failed look would
mean a permission error, a mistyped root, or a bucket that is simply not there
becomes the reason a stray `reserved-ll.lock` appears somewhere. The costs are
not symmetric: guessing surplus-only when the widening HAS landed only costs us
our floor for that acquire - we still contend, on the same terms as everyone
else, and we recover the moment any sibling's reserved lock is visible - while
guessing reserved-first when it has NOT landed puts a file in a shared
directory that nobody but us will ever reclaim.

Detection reads NAMES and never opens a lock. A half-written, unreadable or
garbage payload therefore cannot take it down, and reading cannot leave a
handle that blocks its owner's unlink on Windows.

Our OWN reserved lock does not count as evidence. Counting it would latch the
detector at `RESERVED_PRESENT` after a single write of our own, and evidence
the observer produced is not evidence about the world.

### 4. The surplus width is configurable and its default carries its provenance

`SHARED_SURPLUS_WIDTH` is `3`, overridable by `LL_LANE_SLOT_SURPLUS`. **That
three is NOTE-SOURCED and was never measured here**, and the constant's comment
says so in those terms, enforced by a test that reads the module's own source.
The channel describes the deployed bucket as rationing three first-come slots;
the one first-party look this project has taken found a single lock, and one
lock cannot reveal a width.

Getting it wrong is not symmetric either. Too small only costs us lanes we
could have taken. Too large creates a surplus index the deployed scheme may not
hand out - so `is_slot_name` and `reap` accept ANY digit index, including ones
above the width we contend for, and that is tested. An index above anyone's
width is then still reclaimable by any implementation of this scheme rather
than being litter forever.

### 5. `try_acquire` refuses an order it does not own

An explicit order naming a file outside the scheme, or naming another
repository's reserved floor, raises rather than creating it. The check runs
before the bucket is created, so a bad order leaves no trace. Writing litter or
taking a neighbour's guaranteed floor are not things to do by accident in a
shared directory.

### 6. Unchanged

`slot_order`, `try_acquire`'s default order, the reserved-floor guarantees, the
identity-not-path keying, the stale arm at 16200.0 seconds, the refusal of an
unknown repository key, the two-scheme reap, and the rule that nothing happens
at import time. Detection does not run on import and does not materialise the
bucket. No port is allocated; this project's block is 8810-8819 and this work
uses none of it. Nothing is vendored: no file was copied in from
`moon_sync_inbox/` and no module is imported from a sibling tree.

## Consequences

Stated plainly rather than hedged out, because a caveat dropped from the
artifact is a lie in the artifact.

**We now consume a slot the siblings were rationing.** That is the whole point
and it is still a cost. Before this record our governor bounded only our own
loop; from now on, a Lanternlight lane occupies one of the shared first-come
slots and some sibling's loop will wait where it previously would not have.
ADR-007 declined to do this unilaterally and was right to; the operator has now
ruled, so it is no longer unilateral.

**Our leaks now land in a shared directory, and our own stale arm is still the
only thing that reclaims them.** The reserved widening has not landed, so we
write only surplus names, which other participants' reapers do recognise - but
whether any of them actually reclaims our lock is not a fact we have measured,
and we should not assume it. What IS measured is that a leaked lock can sit in
that bucket for 30 hours: one was sitting there when this record was written.
Our stale arm fires at 4.5 hours on anything we can see, in both naming
schemes, and that is tested directly.

**Detection is opportunistic and can flap.** Reserved locks exist only while
they are held, so a bucket whose participants have all released looks exactly
like a bucket where the widening never landed. We would then contend
surplus-only for that acquire and lose our floor. The failure is in the safe
direction and self-corrects the moment any sibling's reserved lock is visible,
but it means "the widening has landed" is not a fact we latch - it is a fact we
re-measure on every acquire. There is no marker we could write to settle it
without putting an unrecognised file in a shared directory, which is the thing
this record exists to avoid.

**A sibling writing reserved names does not prove its reaper reads them.** The
transition condition detects that somebody's ACQUIRE understands reserved
names. It does not detect that their REAP does. If they diverge, our floor is
taken in a bucket where only we would reclaim it.

**`OPS-35` acceptance criterion 5** - interoperation proven against a real
sibling holder rather than a mock - is advanced by this record but is not
closed by it on our say-so. What is now first-party rather than note-sourced:
the bucket's location, its payload's five fields, the `ts` unit, and the
absence of reserved names. What is still note-sourced: the width, and every
claim about what any sibling's code does with what it finds. The merger owns
whether that clears the criterion.

**Testing.** No test in `tests/test_lane_slot.py` writes into the real shared
bucket, in a fixture or otherwise. A test that took a real slot would take it
from another project's live loop, which is the precise harm this record is
careful about.

That claim was verified rather than asserted, and by a method worth naming: the
wrap's refutation pass wrapped every file-creating, file-writing and
file-removing entry point the standard library offers - the low-level ones in
the os module, the builtin opener, and the create, write and delete methods on
pathlib paths - filtered them to the shared prefix, and ran the suite under it.
(The individual names are deliberately not enumerated here. Each dotted name
parses as host-shaped to the source-register guard, and eleven of them would
have gone into the denylist that module's own docstring calls the one place a
real source can hide. The instrumentation is described; the vocabulary is not
load-bearing.) **The guard's positive control fired**, so the instrument was
proved capable of seeing a write before the negative result was believed. Zero
hits across 676 tests, and zero across `tests/test_lane_slot.py` alone. Before
and after snapshots of the bucket - names, sizes, mtimes, SHA-256, and the
directory's own mtime - were identical.

**One sentence here originally overclaimed and is narrowed.** It said every test
points `PROGRAMDATA` at `tmp_path` rather than reading the real one. That is
false for exactly one test,
`test_default_root_does_not_change_when_the_working_directory_moves`, which
READS the real `PROGRAMDATA`. It only reads, so the no-writes claim above is
unaffected - but "every test" was wrong, and a document that overstates its own
test isolation is the same defect this project removed from
`tools/hook_command_guard.py` earlier the same day, where a guard printed
"Measured" for something nobody had measured.

**Two ADR-007 tests were INVERTED, not deleted.** `test_the_default_root_is_`
`inside_this_repository` and `test_the_default_root_is_not_under_programdata`
pinned the decision this record supersedes. They are replaced by assertions of
equal strength in the new direction - that the default root IS the shared
bucket, and that the in-repository bucket is the FALLBACK - so a regression
back to a private bucket is still caught. A silent withdrawal from the scheme
would otherwise present as everything working.

## Status

Accepted, 2026-09-10, superseding ADR-007. The decision to join was the
operator's; the surplus-only mechanism, the three-way detection and the
direction could-not-look fails in are this record's own and are revisable by a
later ADR.
