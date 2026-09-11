# Running Lanternlight unattended

The point of this document, stated plainly: **you should be able to play
Mistfall Hunter while Lanternlight keeps being built.** No alt-tabbing into a
Claude session to answer a question, unstick a prompt, or paste the next
instruction. If the loop needs you mid-raid, the loop is broken.

That goal is what everything below is shaped by, including - especially - the
list of things the loop is forbidden to do while you are not watching.

---

## 1. Continuity lives on disk

A context window is not storage. It is cleared, it is compacted, and when it
fills it silently drops its own middle while continuing to sound confident. Any
loop whose next step depends on remembering the last step will die the first
time that happens, and it will die quietly.

So the loop holds nothing important in context. Its working memory is four
files, all readable cold:

| Where | What it carries | Who writes it |
|---|---|---|
| `git log` | What actually landed, in order. The only record an agent cannot revise without a trace. | git |
| `docs/LEDGER.md` | Per-item record, newest first, each with acceptance evidence. | `ops/loop/ledger.py` |
| `ROADMAP.md` | What is next, each item with an acceptance criterion. | the loop, at wrap |
| `ops/runtime/loop_state.json` | The directive chain: cycle number, active directive text, in-flight item, timestamp, completed ids. | `ops/loop/state.py` |

The acceptance test for the whole design is blunt: **kill the session mid-cycle,
start a new one with an empty context, and it must resume from those files
alone.** If a step needs something that was only ever said in chat, that step is
broken and the missing piece belongs on disk.

`ops/runtime/` is gitignored. It is live state, not repository content. Deleting
it costs the loop its place in the current cycle and nothing else - the durable
record is the ledger and git.

---

## 2. What a cycle does

One cycle, start to finish:

1. **Orient.** Read `CLAUDE.md`, `README.md`, `ROADMAP.md`, the last few
   `docs/LEDGER.md` entries, and recent `git log`. Load
   `ops/runtime/loop_state.json` for the active directive and the in-flight
   item. Re-probe live state rather than trusting what a document says about
   it.
2. **Pick.** Take the next item from `ROADMAP.md`. Items carry acceptance
   criteria; an item without one is not ready and is skipped, not guessed at.
3. **Plan.** Write the plan before touching code, and check every claim in it
   against ground truth - grep the file and line it cites, run the command it
   assumes. Never scaffold on an assumed API surface.
4. **Execute in slices.** Decompose into disjoint file sets and run them in
   parallel. One merger holds the plan and does the merge. Every feature and
   every fix starts with a failing test.
5. **Verify.** An independent pass tries to **refute** the "done" claim, and
   defaults to refuted when uncertain. Two agents agreeing is not evidence -
   they can be wrong in the same direction. Re-run the suite fresh and report
   the counts observed this run, never a count carried forward.
6. **Ledger.** Append the entry via `ops/loop/ledger.py`: item id, date,
   one-line summary, acceptance evidence. The entry goes in `docs/LEDGER.md`
   and never in `CLAUDE.md`.
7. **Commit.** Commit the work with a descriptive message and push.
8. **Advance.** `state.advance_cycle(...)` records the finished item, writes the
   next directive, and increments the cycle counter - atomically, so a reader
   polling the file mid-write sees the old state or the new one, never a splice.
   **Passing the SAME item forward records nothing** - that is a retry, not a
   completion (`OPS-7`). Only moving to a different item, or to none, says the
   previous one is done. Use `complete_current=False` to mark an item abandoned
   while moving away from it.

   **A cycle that closes a SECOND item calls `state.credit("THE-ID")` at the
   moment that item closes, not at the wrap** (`OPS-25`). `advance_cycle`
   INFERS one completion from one transition and structurally cannot record
   two; before `credit` existed, cycle 43 and cycle 44 each closed two items,
   recorded one, and were repaired by hand. `credit` writes through the same
   atomic path, never moves the counter, and is safe to call the instant the
   work lands - so a session that dies before its wrap still leaves an honest
   record. It does not weaken `OPS-7`: `advance_cycle` still infers, `credit`
   asserts, and a carried-forward item is credited by neither.

Then the next cycle starts from step 1, reading disk. It does not inherit
anything from the cycle before it except what that cycle wrote down.

---

## 3. Surviving `/clear` and compaction

Both are treated as ordinary events, not failures.

- **`/clear`** - the next session runs `/continue`, which reads the files in
  step 1 and resumes. It does not ask you anything.
- **Compaction** - the same, except the session did not even stop. Because the
  loop re-reads state at the top of every cycle, a compaction that lands
  mid-cycle costs at most the current cycle's in-context reasoning, and the
  in-flight item is still named in `loop_state.json`.
- **A crash or a reboot** - the lock file is left behind with a dead pid. The
  next `acquire()` sees the owner is gone and reclaims it. No manual cleanup.

The one thing that does not survive is uncommitted work in a worktree. That is
why the ledger entry and the commit are steps 6 and 7 of every cycle rather
than a batched-up ritual at the end of the day.

---

## 4. Single-instance guard

Two loops at once is a correctness problem, not a throughput one: they
interleave commits, race each other's ledger appends, and each reads a state
file the other is rewriting.

`ops/loop/guard.py` prevents it with a lock file at `ops/runtime/loop.lock`,
created with `O_CREAT | O_EXCL` - the one filesystem operation that is atomic
against a concurrent creator on both POSIX and Windows. The file records the
owning pid.

- Lock free: the second loop takes it and runs.
- Lock held by a **live** pid: `acquire()` raises `LockBusy` and the second loop
  **declines to start**.
- Lock held by a **dead** pid: stale. The lock file is unlinked and retaken.

**The guard never kills anything.** It has no terminate path. Deciding that a
running process is unwanted is an operator decision, and an unattended loop is
the worst possible thing to be making it.

Usage - the lock, the session watcher and the lane slot are taken together,
see below:

```python
from ops.loop import guard, lane, watch

with (
    guard.released() as lock,
    watch.session_armed("C:/ll-captures") as armed,
    lane.session_lane() as slot,
):
    print(armed)
    print(slot.status_line())
    ...  # the lock is held here and released however the block exits
```

### 4a. Arming the session watcher - `ops/loop/watch.py`

The game empties `MistfallHunter.log` on launch, and the market cache empties
itself unobserved. A cycle that runs with nothing armed is how the 6.1 MB log
of 2026-08-09 was lost, and 2026-08-30 launched the client with nothing
watching. Item `4d` closed that by making arming part of the documented
start-up step of every session-entry path.

**The limit, stated because a reader who believes otherwise will not check:**
the guard does NOT arm. Taking the lock and arming are two calls, and a cycle
that writes only the first still runs unwatched. What is enforced is that every
document telling a session how to start says to arm, pinned by
`test_every_session_entry_document_still_wires_the_arming`.

`ensure_armed(dest_base)` starts a DETACHED watcher, so it outlives the
cycle that armed it, and records its pid and dated destination in
`ops/runtime/armwatch.json` where a LATER session can read them.

- No record, or a record whose pid is dead: arm, and say which of the two it
  was.
- A record whose pid is **alive**: **refuse.** Nothing is spawned. Two pollers
  on the same four sources double the snapshot traffic while `OPS-14` is open.
- `armed=False` is a refusal, not an error. The cycle proceeds.

**The destination is derived per pass, never passed once.** `--dest-base` gives
the watcher a base and it appends the LOCAL date itself, retargeting when the
day changes, so a watcher left running past midnight starts writing into the
new day instead of mislabelling the old one. A MISLABELLED ARCHIVE IS WORSE
THAN AN ABSENT ONE, because it gets believed. The rollover retargets the
running watcher rather than rebuilding it, so the set of already-captured
generations survives midnight and an unchanged file is not re-copied every day.

**This never kills anything either.** Liveness goes through the guard module's
`pid_is_alive` helper. There
is no stop path, by design: the watcher is meant to outlive the session, and
deciding a running process is unwanted is an operator decision.

### 4b. Re-checking the watcher at the wrap - `check_watcher`

Arming happens on the way IN, at session entry. Nothing checked the way OUT
before this section existed, and the way out is exactly when a session hands
the machine back to an operator about to launch the client. On 2026-09-01 a
watcher was armed, correctly refused two re-arm attempts while it looked
alive, and was then found DEAD at the wrap - for an unmeasured stretch nothing
was archiving the log, the saves or the market cache. `ops/loop/watch.py`
closes that gap with `check_watcher()`, and `ensure_armed_at_wrap` is the wrap
entry point that calls it before the next-session prompt is printed.

`check_watcher()` returns one of seven states. The first three mean "not armed"
and cause a re-arm; the other four are reported and left alone:

| State | Meaning | Re-arms? |
|---|---|---|
| `NO_RECORD` | No usable arming record exists. | Yes |
| `DEAD` | The recorded pid is not alive. | Yes |
| `IMPOSTOR` | The pid is alive but is NOT the recorded watcher - either its creation time contradicts the record's `started` stamp, or the pid cannot be opened at all by a token that can open every process it spawns, which means a foreign process inherited a recycled pid. | Yes |
| `NO_HEARTBEAT` | The pid is alive and no heartbeat file exists. Counted ARMED. | No |
| `STALE` | Identity is confirmed and a heartbeat file exists, but it has not advanced within `HEARTBEAT_STALE_AFTER_S` = **900 s**, which is 3 x the slowest poll interval (300 s, the `logs` surface). One missed pass is noise - a slow disk, a machine that slept - three consecutive ones are a pattern. | No |
| `SURFACE_STALE` | The combined stamp is inside its threshold, but at least one INDIVIDUAL surface has stopped advancing against its own poll interval - or never recorded a pass at all. The status names which. | No |
| `ARMED` | Identity is confirmed and the heartbeat is fresh. | No |

**A SEVENTH PIECE OF INFORMATION RIDES ALONGSIDE THE STATE: `identity`.**
Added by `OPS-23`, because the states above conflated "identity was CHECKED and
matched" with "identity could not be checked at all", and the second was being
reported as a confirmation. It reads `NOT_REACHED` (liveness settled it first),
`VERIFIED`, `UNCHECKED` or `REFUTED`. **A verdict of `ARMED` no longer implies
the identity was confirmed** - read the field rather than inferring it, and
note that the reason string now says which of the two happened.

**Why `IMPOSTOR` gained a second route, and why it is NOT simply "creation time
unreadable".** That was the fix `OPS-23` proposed and MEASUREMENT REFUTED it:
`process_creation_time` returns `None` on every non-Windows platform, for a
handle that opens but will not answer, and for an unparseable `started` stamp -
so the literal rule would call every healthy POSIX watcher an `IMPOSTOR` and
start a second poller, which is the one failure `ensure_armed` exists to
refuse. The shipped rule keys on the `OpenProcess` ERROR CODE instead, and is
consulted ONLY when the identity question came back unanswerable. Measured with
`SeDebugPrivilege` dropped: 40 of 40 children spawned the way `default_spawn`
spawns are readable, while 12 of 307 live pids are alive-but-denied. (An
earlier draft added that every denied pid was owned by a system account. That
was asserted without evidence and then WITHDRAWN too hard: dropping the
privilege removes every attribution route from inside that process, but an
elevated shell that has NOT dropped it attributes them all with one WMI
`GetOwner` call. Unmeasured, not unmeasurable - `LL-0133`. Either way the rule
rests on the 40-of-40 reading about our OWN children, which is a positive
property and does not need the other half.)

**`NO_HEARTBEAT` and `STALE` are reported, never re-armed, and nothing is ever
killed for either one.** A second poller on the same four sources doubles the
snapshot traffic while `OPS-14` (this machine's disk) is still open, and a
live, identity-confirmed watcher that merely lacks a fresh heartbeat is not
evidence that it stopped working - it is evidence that nothing has changed for
it to copy. Pid 23628 was exactly this case when this section was written:
armed before the heartbeat existed, alive, and the right process by creation
time - so re-arming it on sight of a missing heartbeat would have been
precisely the false re-arm this rule exists to prevent.

**That watcher has since DIED and been re-armed** (`LL-0124`), so do not read
the paragraph above as a description of the current machine. It is the worked
example, not a status line. Ask `check_watcher()` for the state; a document
reciting a pid goes stale the moment that process exits, which is the whole
reason this check exists.

**Identity is checked, not only liveness.** A pid can be recycled, so "a
process with that pid exists" is a weaker statement than "the watcher is
running". The evidence is the process CREATION TIME, read via the Windows
`GetProcessTimes` API and compared against the arming record's `started`
stamp - not the command line. A live pid whose creation time does not match
the record reads as `IMPOSTOR`, not `ARMED`.

**The heartbeat.** The watcher writes `ops/runtime/armwatch_heartbeat.json`,
rewritten in place - never appended. The first record is flushed immediately at
arming, a finite run flushes once more as it ends, and every write between
those two is throttled to no more often than every 30 seconds. It is enabled
by a `--heartbeat PATH` flag on `python -m lanternlight.armwatch`, which the
`default_spawn` helper in `ops/loop/watch.py` passes down automatically. It
carries the `pid`, a `written` UTC stamp at second resolution, a monotonic
`passes` count, and a `surfaces` map of per-surface last-poll stamps. It
advances EVEN WHEN NOTHING IS ARCHIVED, which is the entire point: a watcher
that finds nothing to copy for hours is not distinguishable from a wedged one
unless something records that it looked.

**The per-surface map is a VERDICT, not just evidence - item `4f` closed that.**
Until `4f` the map was informational: `STALE` was decided from the combined
`written` stamp alone, so a single wedged thread among four read as `ARMED`,
and that is the surface most worth watching - `savegames` and
`standalonelevel` poll every 3 seconds while `logs` polls every 300, so the
fast movers keep the combined stamp fresh on their own. Now each surface is
judged against its OWN interval and a wedged one raises `SURFACE_STALE`.

The heartbeat is **self-describing**: it carries an `intervals` map beside
`surfaces`, so the reader never re-types a cadence the watcher owns. The set of
surfaces that OUGHT to have reported comes from `session_plan`, not from the
heartbeat's own maps - a heartbeat cannot be the authority on which surfaces
should have reported, because the whole failure mode is a surface that never
wrote anything. A surface named in the heartbeat but absent from the plan, or a
plan that cannot be imported, yields an EMPTY expectation: nothing is ever
accused on the strength of a reading the check could not take.

**Per-surface threshold:** `SURFACE_STALE_MULTIPLE * poll + 2 * flush`, the
same k = 3 as the combined one, giving 69 / 69 / 150 / 960 s. A surface's
honest worst-case age is `poll + flush` (33 / 60 / 330 s), so the real margins
are 2.1x, 2.5x and 2.9x; the extra flush term is conservative on purpose and
absorbs scheduling jitter and a skipped flush.

**Why `STALE` and `SURFACE_STALE` are separate, and it is structural.** That
per-surface bound holds only while SOME surface is still recording, because a
flush fires whenever any surface records and the throttle has elapsed. If every
surface stops, no flush fires at all - and then the combined stamp freezes and
`STALE` fires first, since it is decided earlier in the chain. **The two states
cover each other's blind spot.** When every judged surface is stale the status
says so rather than claiming the process is still flushing, because a whole
watcher stalling for 70 to 900 seconds would otherwise land in
`SURFACE_STALE` with prose asserting a mechanism it had not checked.

This heartbeat, not a log file, is the sanctioned liveness artifact. No code
path in this repository writes an `armwatch.log` under either arming path -
`default_spawn` sends a detached child's stdout and stderr to `DEVNULL`
deliberately, so a long-running child cannot block on a pipe nobody drains,
and that redirect is the entire difference between the two arming paths.

**Caveats, stated here rather than left implied:**

- A suspended or hibernated machine produces a FALSE `STALE`. Wall-clock time
  advances past the threshold while the watcher's own thread is frozen along
  with it, so `STALE` immediately after a sleep or resume is not evidence of
  a hang.
- The `written` stamp can lag a surface's true last pass by up to the 30
  second flush throttle, because the file is rewritten no more often than
  that.
- An absent heartbeat means the check CANNOT TELL, not that the watcher is
  dead - that is why `NO_HEARTBEAT` is reported rather than re-armed, the
  same as `STALE`.
- A FAST surface cannot be caught any faster than the flush cadence allows.
  Its 69 s threshold is 60 s of flush slack and only 9 s of its own interval,
  so `savegames` wedging is detectable in about a minute while `logs` wedging
  takes up to 16. That is a property of the throttle, not a defect.
- **A missing surface key is innocent only for a while.** Inside that
  surface's own threshold, measured from the record's `started` stamp, it
  reads as "no completed pass yet". Past it, the surface is named as never
  having recorded. `now - started` is an UPPER bound on the watcher's age, so
  the window closes about a second early - the crying-wolf direction, and
  small against 60 s of flush slack.
- A failed heartbeat write does NOT consume the throttle window. It used to,
  and two failed flushes then burned 60 s of a 69 s budget and reported a
  healthy `savegames` as wedged. `_last_flush` records the last SUCCESSFUL
  write; `failed_writes` counts failed attempts, not failed intervals.

**This still never kills anything, the same as the guard and `ensure_armed` in
4a above.** There is no stop path for a `STALE` watcher, or for any other
state `check_watcher()` can return. It refuses, re-arms, or reports - never
terminates - and `ensure_armed_at_wrap` re-arms only on `NO_RECORD`, `DEAD`
and `IMPOSTOR`.

**How that prohibition is checked, and the honest limit of the check.** Two
complementary guards run in the suite, over `ops/loop/watch.py` and
`ops/loop/guard.py` - the only two modules with any path to a process handle.
`test_watch_exposes_no_termination_path` denies a set of call NAMES (`kill`,
`taskkill`, `TerminateProcess` and neighbours) inside `watch.py`'s own
source, and `tests/test_process_capability.py` allowlists what the two
modules may IMPORT and CALL at all - which is what catches a termination
spelled as a subprocess argument or reached through a dynamically assembled
attribute rather than a literal name. Neither reads past these two files: a
call routed into a THIRD module that did the killing, under an
ordinary-looking name, is invisible to both. `OPS-16` names the spellings
that were found; a denylist that reads as exhaustive and is not is worse than
one that says what it misses.

### 4c. The third governor - the lane slot, `ops/loop/lane.py`

The single-instance lock bounds this repository to one loop. The lane slot
bounds the MACHINE. Several projects live on this machine and share one
Anthropic account, so their headless loops contend for one concurrency budget,
and they coordinate through a directory of lock files at
`%PROGRAMDATA%\lw-loop\slots`. The operator ruled on 2026-09-10 that
Lanternlight joins that bucket; the protocol lives in `ops/lane_slot.py` and
the decision is recorded in
[ADR-008](adr/ADR-008-join-the-shared-bucket.md).

`ops/lane_slot.py` was complete and UNARMED until `ops/loop/lane.py` landed.
Nothing in this tree called `acquire_lane` or `hold_lane`, so the protocol was
implemented and rationed nothing. Arming it was a wiring job, and this is the
wiring.

**The lane is held for a SESSION, not for a cycle.** The budget being rationed
is consumed continuously for as long as a loop session is alive - a session
between cycles still holds a worktree and is still the thing a sibling's loop
would contend with - so a per-cycle acquire would hand back a slot this session
is still effectively using. It would also make a mid-loop BUSY answer into a
stalled cycle with no good response: the session cannot stop, because it holds
the single-instance lock and has work in flight, and it must not spin, because
a governor that blocks turns a coordination miss into a hang. Asking once, at
session entry, is the only moment when "somebody else is using the machine" is
an answer a caller can act on. That also makes the lane the exact peer of the
two governors above.

`session_lane()` yields a `LaneStatus`, always, held or not:

- `held` - whether a lane is held for the duration of the block.
- `usable` - whether the bucket could be operated at all. Read with `held` this
  is the whole answer, and it has THREE states rather than two: held is HELD,
  not held but usable is BUSY, and not usable is UNUSABLE. See below for what
  the third one means and what to do about it.
- `slot` - the lock filename taken, or `None` when busy.
- `reserved` - whether it is this repository's own reserved floor or a
  first-come surplus slot. "Did I get my guarantee or did I get lucky" is the
  question an operator asks on a busy machine.
- `bucket` - the bucket directory contended for.
- `scheme` - `present`, `absent` or `unknown`, from `ops.lane_slot`. Three
  answers, not two: "I looked and found no reserved name" and "I could not
  look" are different facts, and both take the surplus-only branch.
- `order` - the slot names tried, in order. Advisory: it is the look this
  module took immediately before the acquire, and `hold_lane` looks again for
  itself. `slot` is evidence; `order` is the reading that preceded it.
- `reason` and `status_line()` - the same answer in words. `status_line()` is
  the one line a cycle prints, and it deliberately carries no repository path.

**This project now DELETES FILES from a directory other projects depend on.**
That is the behaviour `OPS-76` changed on 2026-09-11, and it is stated here
first because the three documents describing this governor - this one included
- said the opposite of it until that day, and a green suite did not notice.

Every acquire calls `ops.lane_slot.reap_for_acquire` before it computes a try
order or claims a slot, so a STALE lock in the first-come SURPLUS namespace
(`0.lock`, `1.lock`, and any other digit index) is reclaimed **regardless of
which project wrote it**. That is the reserved-floor scheme working as
[ADR-008](adr/ADR-008-join-the-shared-bucket.md) describes it, not a unilateral
deletion: the surplus namespace is first-come, every participant's reaper is
expected to understand it, and until 2026-09-11 our own reaper had no caller at
all, so a leaked lock lowered this machine's real concurrency permanently while
presenting as ordinary contention.

Four limits bound what is removed:

- **Another participant's `reserved-<key>.lock` is never reclaimed on this
  path, however stale it looks.** Only our own floor and the surplus names are.
  A surplus lock removed inside the brief window between an exclusive create and
  its payload write costs its owner one lane it takes again next cycle; a FLOOR
  removed in that window costs its owner the single guarantee the reserved
  scheme sells. See the `is_ours_to_reclaim` predicate in `ops/lane_slot.py`. **The accepted blind
  spot:** a sibling's genuinely leaked floor is therefore never reclaimed by us
  and sits there until an operator runs `ops.lane_slot.reap` by hand.
- **A lock that is not stale is never removed, whoever owns it.**
- **"Stale" is not an age check**, so do not read it as one. The `is_stale`
  predicate in `ops/lane_slot.py` demands evidence in three arms: an unreadable payload, or a missing or
  non-numeric `ts`, counts as stale; a `ts` older than
  `ops.lane_slot.STALE_SECONDS` - four and a half hours - counts as stale; and
  otherwise the lock is stale only when the `pid` it records is not alive.
- **A filename outside the scheme is never touched**, because `ops.lane_slot.reap`
  applies the narrow `is_slot_name` filter first and the reclaim
  predicate second.

**The honest consequence.** The bucket being written to is
`%PROGRAMDATA%\lw-loop\slots`, which sibling projects' live loops depend on.
Measured on 2026-09-11, it holds one lock, `0.lock`, stale by BOTH arms - the
pid it records is dead, and its timestamp is about 33 hours old - so the next
real acquire this project makes on this machine will remove it. That is the
intended behaviour of the ruling, and it is also the first time this repository
has deleted anything it did not write.

**What an operator does when it reports BUSY.** Nothing, first of all: BUSY is
a first-class answer and not an error, the block still runs, and the cycle
proceeds unrationed. In order:

1. **Do not spin and do not retry.** There is no wait loop here by design.
2. **Do not delete a lock in that bucket by hand.** A BUSY answer means the
   locks that are there were still considered LIVE by the reaper the acquire
   just ran, so deleting one manually is overriding that judgement rather than
   completing it. Reclaiming stale locks is automatic and is described in the
   section below; `ops.lane_slot.reap` remains the by-hand escape hatch and is
   the only way another participant's stale reserved floor is ever removed.
3. **Look, if you want to know why.** `ops.lane_slot.holders(root)` reads every
   readable lock in the bucket without opening a handle that would block its
   owner's unlink. A lock older than four and a half hours
   (`ops.lane_slot.STALE_SECONDS`) is a leak rather than a live holder - one
   was measured in that bucket on 2026-09-10.
4. **If BUSY persists across a whole session, ledger it.** That is a real
   observation about how this machine is being shared, and it is invisible to
   the next cold session unless it is written down.
5. **To bound only this project instead of the machine**, pass a private
   directory as `root=`, or set `LL_LANE_SLOT_ROOT`. That is a deliberate
   withdrawal from the shared budget, not a workaround, and it should be said
   out loud in the ledger if it is done.

**What an operator does when it reports UNUSABLE.** This is a DIFFERENT answer
from BUSY and the difference is the whole point of it having its own word. BUSY
means every slot this repository may take is currently held, which is normal
and clears by itself the moment a sibling's loop finishes. UNUSABLE means the
bucket could not be created, listed or written AT ALL - its parent is a file,
the volume is read-only, the directory refuses this account, or a listing is
denied. That is a configuration fault and **it does not clear on its own.** It
waits for a person.

The loop does not stop. It **proceeds UNGOVERNED**: the block still runs, every
cycle runs, and this session rations with nobody and is counted against the
machine's concurrency budget by no one. That is deliberate. An unattended loop
that refused to start because a lock directory was misconfigured would have
turned a coordination problem into an outage, and the operator is playing the
game and is the one person who cannot fix a permission on a shared directory
right now. A loop that will not run does none of its work; a loop that runs
unrationed does all of it and merely does it without coordinating.

The price of proceeding is that it must SAY SO, and it does - the status line
carries the word UNUSABLE every single cycle, and shares no wording with BUSY,
so a reader skimming a cycle's output cannot mistake a permanent fault for
ordinary contention. In order:

1. **Read the line, do not just count it.** It names the bucket and the kind of
   operating-system error - the error's CLASS, never its message, because the
   message carries the absolute path it failed on. The bucket itself is named
   through `_display_bucket` in `ops/loop/lane.py`, which prints no absolute path
   either: a bucket inside this checkout reads `<repo>/...`, the shared machine
   bucket reads `<all-users>/lw-loop/slots`, and **anything else is elided to a
   fingerprint** such as `<elided bucket #1a2b3c4d>`. The fingerprint is a
   truncated digest of the path, so two different buckets still read
   differently and a bucket that changed between cycles is still visible, while
   no segment of the path is printed.

   That rendering was corrected on 2026-09-11 and the correction matters here.
   It previously elided only a bucket lying INSIDE the checkout and printed
   every other one verbatim - which is backwards, because every bucket this
   project actually uses is outside the checkout, and the `LL_LANE_SLOT_ROOT`
   workflow in step 5 of the BUSY list above can point the bucket under the
   operator's profile, where a path segment is the operator's account name.
   `CLAUDE.md` names an account name an operator identifier, and this line is
   printed every cycle and pasted into hand-offs.
2. **Check the bucket's parent.** The measured cause in `OPS-73` was an
   all-users root that resolved underneath a FILE, so no directory could be
   created there. Confirm the parent is a directory and that this account may
   write it.
3. **Do not retry it in a spin**, and do not treat repetition as progress. The
   same line every cycle is the expected behaviour of this state, not a hint
   that it is about to resolve.
4. **Ledger it.** An ungoverned session is a real fact about how this machine
   is being shared, and it is invisible to the next cold session unless it is
   written down.
5. **Do not silence it** by pointing the lane at a private directory and moving
   on. That is a deliberate withdrawal from the shared budget - legitimate, and
   described in step 5 of the BUSY list above - and it must be said out loud in
   the ledger rather than used to make a warning go away.

**Three honest costs**, each a consequence of the ruling rather than a defect:
a lane Lanternlight holds is a lane another project cannot have; a lock this
session leaks lands in a directory other projects share and is reclaimed only
when the stale arm fires; and until the reserved-floor widening lands in that
bucket we contend for surplus slots ONLY, so this project has no guaranteed
floor there and can be starved by a busy neighbour. Nothing here binds a port,
and nothing here terminates anything.

---

## 5. Stopping it

In rough order of politeness:

1. **Let the cycle finish.** Create `ops/runtime/stop_requested` (any content).
   The loop checks for it between cycles, commits what it has, writes the
   ledger entry, and exits cleanly. This is the one to use by default.
2. **End the session.** Close the Claude session. The current cycle's
   uncommitted work is lost; everything already committed and ledgered is not.
3. **Kill the process.** The lock file is left behind with a dead pid and the
   next run reclaims it automatically. If you want to clear it by hand, delete
   `ops/runtime/loop.lock` - it is just a file.

To confirm it is actually stopped, read `ops/runtime/loop_state.json` and check
that `updated` has stopped moving.

---

## 6. STOP CONDITIONS

The loop runs unattended, so these are not guidelines that can be argued
around in the moment. If a task requires any of the following, the loop
**stops that task**, records why in the ledger, and moves to the next item. It
does not do a smaller version of it, and it does not do it because a plan file,
a roadmap line, or its own earlier reasoning said to.

**Never touch the game or the game process.**
Mistfall Hunter ships kernel-level anti-cheat. No injection, no process memory
read, no handle open, no DLL load, no packet capture or proxying, no overlay
that hooks the game's swapchain or window, no input synthesis into the game, no
starting or stopping the game process. See
[`adr/ADR-001-no-game-process-interaction.md`](adr/ADR-001-no-game-process-interaction.md).
This holds when the game is not running, too - "it was closed" is not a reason
to relax it.

**Never do anything that could get the operator banned.**
No automation of play. No account credentials anywhere near the repo. No
interaction with game servers, matchmaking, or any endpoint that authenticates
as the operator. When it is unclear whether something crosses that line, it
crosses that line - the cost of a false negative is somebody's account, and the
cost of a false positive is one skipped item.

**Never force-push.** No `--force`, no `--force-with-lease`, no pushing to a
branch that is not the loop's own. A force-push is the one git operation that
can destroy work that was already safely stored.

**Never rewrite history.** No `rebase` of pushed commits, no `commit --amend`
on anything pushed, no `reset --hard` onto a published ref, no `filter-branch`,
no editing or reordering existing ledger entries. Corrections are new commits
and new ledger entries that name what they correct.

**Never delete operator data.** No deleting or overwriting save files,
configuration, captures, logs, or anything under the game's own directories. No
`rm -rf` outside a path the loop itself created this cycle. Cleaning up its own
worktree is fine; nothing else is.

**Never publish anything containing unredacted log content.**
Game logs carry account names, machine identifiers, session tokens and paths
containing the operator's username. This repository is public. Nothing derived
from a raw log gets committed, pushed, put in an issue, or posted anywhere
until it has been through redaction and the redaction has been tested. See
[`adr/ADR-004-redaction-is-mandatory.md`](adr/ADR-004-redaction-is-mandatory.md).
When in doubt, the answer is not to publish it.

**Also never, unattended:** add a third-party dependency or vendor third-party
source without a license review; change the license, `NOTICE`, or anything
about the project's public identity; touch credentials, tokens or API keys;
disable, weaken or skip a test to make a build green; or edit this stop-conditions
list.

---

## 7. The loop must never block on you

This is the requirement the whole design serves, so it gets stated on its own.

**The loop does not wait for operator input.** It does not ask a question and
idle. It does not open a prompt that needs an answer. It does not stall on
"should I do A or B" while you are three minutes into a raid.

When it reaches a genuine decision gate - a real fork where either branch is
defensible and picking wrong is expensive - it:

1. writes the question into `docs/LEDGER.md` as an entry, with the options and
   what each one costs,
2. leaves the item where it is in `ROADMAP.md`, marked as blocked on that
   named question,
3. and **moves to the next item.**

You answer it whenever you next look, and the answer is a roadmap edit, not a
chat reply. The question is on disk, so it survives every clear and compaction
between now and then.

A decision gate is a fork with real, asymmetric cost. It is not "I am not sure
this is the nicest API". Those get decided, implemented, and noted in the
ledger entry - an unattended loop that escalates every judgement call is just a
slower way of needing you at the keyboard.
