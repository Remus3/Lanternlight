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

Usage - the lock and the session watcher are taken together, see below:

```python
from ops.loop import guard, watch

with guard.released() as lock, watch.session_armed("C:/ll-captures") as armed:
    print(armed)
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
| `IMPOSTOR` | The pid is alive, but its process creation time does not match the arming record's `started` stamp - an unrelated process inherited a recycled pid. | Yes |
| `NO_HEARTBEAT` | Identity is confirmed but no heartbeat file exists. Counted ARMED. | No |
| `STALE` | Identity is confirmed and a heartbeat file exists, but it has not advanced within `HEARTBEAT_STALE_AFTER_S` = **900 s**, which is 3 x the slowest poll interval (300 s, the `logs` surface). One missed pass is noise - a slow disk, a machine that slept - three consecutive ones are a pattern. | No |
| `SURFACE_STALE` | The combined stamp is inside its threshold, but at least one INDIVIDUAL surface has stopped advancing against its own poll interval - or never recorded a pass at all. The status names which. | No |
| `ARMED` | Identity is confirmed and the heartbeat is fresh. | No |

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
