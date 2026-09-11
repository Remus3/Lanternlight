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

## Amendment, 2026-09-11 - `OPS-73`, two silent failures in the join

**This section AMENDS the record. Nothing above it was rewritten**, because
this repository's convention is that a record is amended or superseded and never
edited into a different decision. The Decision and Consequences above stand as
written; what follows narrows two of their mechanisms.

Both holes were found by the refutation pass of the same wrap that shipped the
join, filed as `OPS-73`, and neither is a reason to revert it. Both are cases
where the wrong answer is SILENT, which is this repository's standing definition
of the dangerous kind.

### Hole 1: detection could not see two of the machine's seven projects

Decision section 2 says the transition to reserved-first "needs no code change"
and fires the first time another participant's `reserved-<key>.lock` is in the
bucket when we look. That was true only for a key in `REPO_KEYS`, which holds
the five short codes the channel agreed. `CLAUDE.md`'s own machine-wide ports
table lists SEVEN projects: Red Moon and Daemon Slayer are in that table and
were in neither the key set nor, therefore, the detector. A bucket whose only
reserved name was `reserved-ds.lock` read as `RESERVED_ABSENT`. The widening
could have landed and we would have gone on taking surplus slots while every
other participant moved to floors, and the miss would have looked exactly like
correct pre-widening behaviour.

**The ruling: DETECTION uses a wider alphabet than CLAIMING does, and the two
sets are separate, separately named and separately documented.**

- **Claiming is unchanged.** `REPO_KEYS` is still the agreed five, and a key
  outside it is still refused with `UnknownRepoKey` rather than quietly given a
  surplus slot. Acquiring with `ds` or `rm` raises, and that is tested.
- **Detection gets `DETECTION_REPO_KEYS`**, a strict superset of `REPO_KEYS`
  adding `rm` and `ds`. **The provenance of that addition is stated in the
  constant's own comment and pinned by a test that reads the module's source**,
  exactly as `SHARED_SURPLUS_WIDTH`'s note-sourced three already was. The two
  codes are READ OFF THE PORTS TABLE IN `CLAUDE.md` - the same document that
  assigned this repository `ll` - and they are **NOT confirmed lock keys agreed
  by those two projects**. Nobody from either has told us what short code their
  governor would write. That satisfies `OPS-73` acceptance criterion 2 in the
  only way open to us: the codes are recorded WITH their provenance, and the
  limit of that provenance is recorded beside them rather than rounded off. A
  guess presented as an agreement would have been the unilateral act this ADR
  was careful to avoid.
- **Detection does NOT accept an arbitrary token.** A wide-open pattern would
  let stray litter whose name merely begins `reserved-` flip us to
  `RESERVED_PRESENT`, and the asymmetry runs one way: a false ABSENT costs us
  our floor for one acquire and self-corrects the moment a recognised reserved
  name is visible, while a false PRESENT makes us write `reserved-ll.lock` into
  a shared directory where, as this record already says, nobody else's reaper
  recognises it. The expensive direction is the one a loose pattern makes
  easier, and that asymmetry is written down where the set is defined.
- **The reaper's alphabet is NOT widened.** `is_slot_name` still answers False
  for `reserved-ds.lock`, so `reap` and `holders` still leave it alone.
  Noticing a file is a cheaper act than deleting one, so the set that decides
  what we may DELETE stays narrower than the set that decides what we may
  NOTICE. A reaper that removes what it does not understand is how a reaper
  eventually eats somebody's notes, and section 6's "unchanged" list depends on
  that narrowness. Both halves are tested, including that a stale
  `reserved-ds.lock` survives a reap.
- **Our own floor is still not evidence.** Unchanged, and its test is kept, with
  a second one asserting the property survives the wider alphabet.

### Hole 2: an unusable bucket was reported as a busy one

Decision section 1 says that if the all-users root cannot be resolved at all,
`shared_root()` answers `None` and the in-repository bucket is used. It did not
cover a `PROGRAMDATA` that resolves fine and names a FILE. The shared bucket
then resolved to a path underneath that file, `mkdir` failed on every attempt,
and `acquire_lane` answered `None` forever. `None` is this module's word for
"busy", so a permanent misconfiguration presented as contention and would have
been debugged as contention - precisely the shape `UnknownRepoKey`'s own
docstring condemns, reappearing one level down in root resolution rather than in
the key.

**The ruling has two halves, and both are implemented.**

**(a) `shared_root()` answers `None` when the resolved all-users root exists and
is not a directory**, exactly as it already answers `None` when the root cannot
be resolved at all. The in-repository bucket is then the fallback, so the loop
is still GOVERNED rather than permanently busy. No drive letter is invented, an
absent root is still created on first use as it always was, and the stat is
taken in a way that answers `None` on `OSError` rather than propagating from a
malformed path.

**(b) The general fix, which also covers a permission error and a read-only
volume: AN UNUSABLE BUCKET IS DISTINGUISHABLE FROM A FULL ONE.** `try_acquire`,
and therefore `acquire_lane` and `hold_lane`, raise `BucketUnusable` - a new,
exported, specifically-named subclass of `LaneSlotError` - when the bucket
cannot be created, cannot be listed, or refuses the lock create for any reason
other than the exclusive create losing a race. `None` now means exactly one
thing: every candidate slot is taken. The distinction is documented in the
module docstring and in the new exception's own docstring, and it is tested as a
difference of KIND rather than of value, because "a wrong answer is quiet" is
the whole point of the item.

`OPS-73` acceptance criterion 3 asked that an unusable root be reported as
unusable rather than as busy; that is what `BucketUnusable` is. Criterion 4
asked that the override branch and `shared_root()` agree about whitespace: they
now do, and a `LL_LANE_SLOT_ROOT` of three spaces is ignored rather than
producing a bucket named three spaces.

### The loop is now WIRED to the bucket, and unusable is surfaced

Recorded here because the amendment above would otherwise be a change to a
protocol nobody called. Until 2026-09-11 this record described a lane that was
implemented and UNARMED: nothing in this tree called `acquire_lane` or
`hold_lane`, so the operator's ruling of 2026-09-10 was true in code and not yet
true in behaviour, and a protocol nobody calls rations nothing.

`ops/loop/lane.py` closes that. It holds one lane for a SESSION - not for a
cycle - and is taken in the same `with` statement as the single-instance lock
and the session watcher, making it the exact peer of the two governors this
project already had. Session scope is the scope the rationed budget actually
has: this project consumes the machine's concurrency continuously for as long
as a loop is alive, and session entry is the only moment when "somebody else is
using the machine, so this session does not start" is an answer a caller can act
on. The three entry documents were updated in the same change.

**And the third state reaches a reader.** `BucketUnusable` exists so that an
unusable bucket cannot be mistaken for a full one, and a wiring layer that
caught it and reported BUSY would have undone hole 2 one level up. It does not.
`session_lane` catches the exception, does not propagate it, and yields a status
whose `usable` is False and whose words say UNUSABLE - sharing no wording with
the BUSY answer, so the two are unmistakable in the one line a cycle prints.

The loop then PROCEEDS UNGOVERNED, loudly. That is a deliberate trade and it is
recorded rather than left implicit: an unattended loop that refused to start
because a lock directory is misconfigured converts a coordination problem into
an outage, and the operator is playing the game and cannot fix a directory
permission right now. A session rationing with nobody is a smaller harm than a
session doing nothing. The price is that it must say so in its own status line
every cycle, so the condition cannot rot unnoticed and cannot be read as the
self-clearing contention it is not.

### What this amendment does not change

The decision to join, the surplus-only default, the three-way detection and its
conservative direction on could-not-look, the note-sourced width, the refusal of
an order we do not own, the identity-not-path keying, the stale arm, and the
rule that nothing happens at import time. Nothing is vendored: no file was
copied in from `moon_sync_inbox/` and no module is imported from a sibling tree.
No port is allocated. No note was sent to any sibling, and nothing was written
into any sibling's directory, so `OPS-48` and `OPS-68` are still respected.

**The testing claim above still holds for the new tests.** No test added by this
amendment writes into the real machine-wide bucket: the `PROGRAMDATA`-is-a-file
cases point the all-users variable at a file under `tmp_path` AND redirect the
in-repository fallback under `tmp_path` as well, so the fallback acquire creates
nothing inside the checkout either. The real bucket was snapshotted - names,
sizes and mtimes - before and after the targeted run and was unchanged.

## Amendment, 2026-09-11b - `OPS-76`, the stale arm had no caller

**This section AMENDS the record. Nothing above it was rewritten**, including
the Consequences paragraph it corrects. The convention this repository keeps is
that a record is amended or superseded and never edited into a different
decision, and that applies with more force, not less, when the thing being
corrected is a sentence that turned out to be false.

### The correction: a Consequences claim the code did not support

The Consequences section above says, as its second paragraph heading:

> **Our leaks now land in a shared directory, and our own stale arm is still the
> only thing that reclaims them.**

**The first half was true and the second half was false.** Nothing reclaimed
them. As deployed on the day that sentence was written, `ops.lane_slot.reap` had
NO CALLER anywhere in this tree: the name appeared in its own definition, in
`tests/test_lane_slot.py` and in prose, and in no operational path. `STALE_SECONDS`,
the two-scheme reaper and every test covering them were correct and unreachable
from `acquire_lane`, `hold_lane` and `try_acquire` alike.

The corrected sentence, which the code now supports: **our leaks land in a
shared directory, and our own stale arm - reached from `acquire_lane` on every
acquire - is the only thing we have measured reclaiming them.** Whether any
other participant's reaper also reclaims our surplus locks is still not a fact
we have measured, and the original paragraph's caution about that stands
unchanged.

### What was measured, 2026-09-11

Both halves independently, before any code was written.

- **Against the real shared bucket.** The bucket held one lock, `0.lock`, stale
  by both arms - holder pid dead, timestamp about 33 hours old. A real acquire
  by this project took `1.lock` and left `0.lock` byte for byte as it found it:
  same size of 104, same modification time to the nanosecond, same SHA-256. It
  was not reclaimed, and under the code as it then stood it never would have
  been.
- **Against the tree.** A grep across `ops/`, `tools/`, `lanternlight/`,
  `scripts/` and `tests/` for a call to `reap` returned its own definition and
  eleven call sites, every one of them inside `tests/test_lane_slot.py`. Reading
  `try_acquire` confirms the mechanism: it creates the bucket, lists it once to
  prove it is readable, and then walks its candidate names calling `_claim` on
  each. No reaping happens on that path.

**Why this is worse than an unused function.** Every lock this project leaks
into a directory other projects share stays there permanently, and each one
silently lowers our real concurrency by one while presenting as an ordinary
"busy" answer - the self-clearing condition it is precisely not. That is the
same silent shape `OPS-73` hole 2 removed one layer down, reappearing one layer
up. And it is this repository's standing lesson in a new costume: a green suite
proves a behaviour is IMPLEMENTED, never that it is WIRED. Seventy-odd tests
covered a reaper no production path could reach while this record, the module
docstring and a session hand-off all described its live behaviour in the present
tense.

### The ruling: reaping is wired into `acquire_lane`, before the candidates

`acquire_lane` calls `reap_for_acquire(bucket, key)` as its first act on the
bucket - before the try order is computed and before any candidate is claimed -
so an acquire can take a slot whose previous holder leaked it, and so a stale
lock cannot influence the order decision either.

**Why there and not in `try_acquire`.** `acquire_lane` is the operational entry
point: it is the function that resolves the bucket and decides the try order by
looking at it, so it is the one place that knows the acquire is an automatic,
unattended act rather than a caller stating its own terms. `try_acquire` keeps
the contract section 5 of this record gives it - it does what its `order` says
and nothing more - because a caller passing an explicit order is asserting
knowledge about the bucket, and a primitive that silently deletes files
underneath such a caller is a worse surprise than one that does not. Every
production path in this tree reaches the bucket through `acquire_lane`:
`ops/loop/lane.py` uses `hold_lane`, which is `acquire_lane` plus a release.

**The disclosed cost of that placement.** `hold` and a direct `try_acquire`
caller do NOT reap. Nothing operational uses either today, but a future caller
that reaches for the primitive instead of the entry point would reintroduce this
hole for itself, and no test can catch a caller that does not exist yet.

### The `OPS-76` criterion 3 decision: another participant's stale floor is NOT removed

**The decision, made explicitly rather than by omission: the automatic acquire
path may reclaim a stale SURPLUS lock whoever wrote it, and may reclaim our own
stale `reserved-ll.lock`, and may NEVER remove another participant's
`reserved-<key>.lock`, however stale it looks.** `is_ours_to_reclaim` is that
rule, `reap_for_acquire` applies it, and it is tested in that direction - for
every key in the agreed set other than ours, not merely for one of them.

The reasoning, and the asymmetry that decides it:

- **Removing a stale surplus lock is the scheme working as this record
  describes it.** The surplus namespace is first-come, every participant's
  reaper understands those names, and this record's section 4 already says an
  index above anyone's width must stay reclaimable rather than becoming litter
  forever.
- **A floor is a different kind of object.** It exists to guarantee that a
  starved repository can always start one lane. That guarantee is the entire
  product the reserved scheme sells, and a reaper that is wrong about staleness
  there takes it away from its owner.
- **`is_stale` requires its evidence, which helps but does not settle it.** It
  never guesses: an absent or unusable timestamp is treated as stale rather than
  as "now", the pid arm is consulted last and fails toward ALIVE, and a missing
  field fires the arms rather than suppressing them. But it treats an
  UNREADABLE payload as stale, and a lock is briefly unreadable in the window
  between an exclusive create and the payload write - a window our own `_claim`
  has, so a sibling's implementation very likely has one too. In that window a
  reaper sees a freshly taken lock as reclaimable.
- **So the error case is real, and the cost of it is not symmetric.** A surplus
  lock wrongly reclaimed costs its owner one lane it takes again on its next
  cycle. A floor wrongly reclaimed costs its owner the one guarantee it was
  promised, at the moment it was exercising it.
- **And we would be ruling on a protocol we have never watched anybody run.**
  No reserved name of any key has ever been observed in that bucket, by this
  project or in any note. Deleting one would be acting with confidence on a
  scheme whose only first-party evidence is its absence.

**The blind spot this accepts, stated plainly.** Another participant's genuinely
leaked floor now sits in the shared bucket forever as far as we are concerned.
That costs nobody a surplus slot - a floor is not a slot we could have taken -
and it costs its owner only the floor its own reaper is responsible for. The
explicit `reap` still removes it when an operator asks for it by hand, and that
two-scheme contract from section 6 is unchanged and still tested; the narrowing
is on the automatic path only, which is the path nobody asked for.

### An unwired behaviour must now FAIL a test, not a reading

`OPS-76` criterion 5. The primary guard is behavioural: tests drive the real
`acquire_lane` and `hold_lane` against a bucket holding a planted stale lock and
observe the reclaim and the slot actually taken, including with `root=None` so
the bucket is the one the module resolves for itself rather than one the test
handed it. A structural guard sits behind it - a spy that asserts
`reap_for_acquire` was called with the resolved bucket - so that deleting the
call rather than breaking it is caught too. Deleting the call from
`acquire_lane` was mutated in and turned eight tests red.

### What this amendment does not change

The decision to join, the surplus-only default, the three-way detection and its
conservative direction on could-not-look, the note-sourced width, the narrow
`is_slot_name` alphabet, the refusal of an order we do not own, the
identity-not-path keying, the stale arm at 16200.0 seconds, and the rule that
nothing happens at import time. `reap` itself is unchanged apart from an
optional predicate that can only NARROW what it will delete and never widen it.
Nothing is vendored: no file was copied in from `moon_sync_inbox/` and no module
is imported from a sibling tree. No port is allocated. No note was sent to any
sibling and nothing was written into any sibling's directory, so `OPS-48` and
`OPS-68` are still respected.

**The testing claim still holds.** No test added by this amendment writes into
the real machine-wide bucket: every one points its root at `tmp_path`, and the
single test that lets the module resolve the root for itself repoints
`PROGRAMDATA` under `tmp_path` first and asserts the redirection took effect
before it does anything else. The real bucket was snapshotted - names, sizes,
modification times to the nanosecond and SHA-256 - before the work started and
after every run including the five mutation runs, and was identical each time:
one file, `0.lock`, 104 bytes, unchanged.

## Status

Accepted, 2026-09-10, superseding ADR-007. The decision to join was the
operator's; the surplus-only mechanism, the three-way detection and the
direction could-not-look fails in are this record's own and are revisable by a
later ADR.

Amended 2026-09-11 by the section above, closing `OPS-73`. The amendment
narrows two mechanisms and reverses no part of the 2026-09-10 decision.

Amended again 2026-09-11b, closing `OPS-76`. That amendment corrects a
Consequences claim this record made about reclaiming, wires the stale arm into
`acquire_lane`, and rules explicitly that another participant's reserved floor
is never removed on the automatic path. It reverses no part of the 2026-09-10
decision either.
