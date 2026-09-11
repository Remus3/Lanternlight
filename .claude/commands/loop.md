---
description: Start the unattended Lanternlight loop - self-continuing cycles, guarded against a second instance.
---

# /loop - run unattended

Start the self-continuing loop. The operator is playing Mistfall Hunter and is
not available. Run until the roadmap is empty, a stop is requested, or a stop
condition is hit.

Read [`docs/HEADLESS.md`](../../docs/HEADLESS.md) first. It is the contract this
command executes, and section 6 is not optional.

## Session shape (default, not an escalation)

Every cycle is **orchestrated, multi-agent, parallel, self-adjudicating and
self-adversarial**:

- **Orchestrated** - one merger holds the plan and performs the merge. Work is
  decomposed into disjoint slices before any of it starts.
- **Multi-agent and parallel** - slices run concurrently on non-overlapping
  file sets, worktree-isolated wherever they write.
- **Self-adjudicating** - when two slices produce competing outputs, a
  **distinct** agent decides between them against stated criteria. The agent
  that produced a thing never grades it.
- **Self-adversarial** - an independent agent tries to **REFUTE** every "done"
  claim and defaults to refuted when uncertain. Two agents agreeing is not
  evidence; they can be wrong in the same direction.

**Every feature and every fix starts with a failing test.** Unattended is
exactly when that discipline matters most, because nobody is watching the
output to notice that it was never really exercised.

## Before the first cycle

Take the single-instance lock, arm the session watcher AND take a lane slot, in
one step. Two loops would interleave commits and race each other's ledger
appends; a cycle that runs without a watcher armed is how the log of 2026-08-09
was lost and how 2026-08-30 launched the client with nothing watching; and a
session that takes no lane slot rations the machine's concurrency with nobody,
which is the state this project was in until the lane was wired.

```python
from ops.loop import guard, lane, state, watch

with (
    guard.released() as lock,
    watch.session_armed("C:/ll-captures") as armed,
    lane.session_lane() as slot,
):
    print(armed)
    print(slot.status_line())
    ...  # every cycle runs inside here
```

- `LockBusy` means another loop is live: **print why and exit.** Do not retry in
  a spin, and do not remove the lock. The guard never terminates the holder,
  and neither do you.
- A lock left by a dead pid is reclaimed automatically. That is the crash-
  recovery path, not an error.
- **Arming is written into this block deliberately** (`4d`), because every
  version of "remember to arm it separately" has been forgotten at least once.
  Note the honest limit: `guard.released()` does NOT itself arm, so a cycle
  that writes only the lock line runs unwatched. Keep both. `armed.armed` is
  False when a watcher was already running - that is a refusal, not an error,
  and the cycle proceeds.
- **Never start a second watcher and never stop the one you find.**
  `ensure_armed` refuses on its own, and nothing in this project terminates a
  process it did not start.
- **The lane slot is the third governor, and it is held for the whole session**
  rather than per cycle. The budget it rations is the machine's and the
  account's concurrency, which this project consumes continuously for as long
  as a loop is alive, not in bursts that line up with cycle boundaries. Print
  `slot.status_line()` so the cycle's output says which bucket was contended
  for, which slot was taken, and whether the reserved-floor widening has landed
  there. The line deliberately carries no repository path.

Five caveats about the lane, written out because each one is a real cost the
operator is now paying and none of them is visible from a green suite:

- **This project DELETES stale locks it did not write.** Every acquire runs
  `ops.lane_slot.reap_for_acquire` before it claims anything, so a STALE lock
  in the first-come SURPLUS namespace is reclaimed whoever wrote it. That is
  [ADR-008](../../docs/adr/ADR-008-join-the-shared-bucket.md)'s scheme working
  as designed, not a unilateral deletion - but it does mean this project now
  removes files from `%PROGRAMDATA%\lw-loop\slots`, a directory other projects'
  live loops depend on, and that bucket held exactly one such lock when this was
  measured on 2026-09-11. Three limits: another participant's
  `reserved-<key>.lock` is never reclaimed on this path however stale it looks
  (so a sibling's leaked floor is our accepted blind spot, cleared only by
  running `ops.lane_slot.reap` by hand); a lock that is not stale is never
  removed, whoever owns it; and "stale" is not an age check - it needs an
  unreadable or timestamp-less payload, or a timestamp older than four and a
  half hours, or a recorded pid that is not alive. `docs/HEADLESS.md` section 4c
  carries the full statement.
- **A `held` of False is not an error.** It means every lane slot this
  repository may take is already held, and the status's `reason` says BUSY in
  words.
  The cycle proceeds. Do not spin waiting for a slot, do not raise, and do not
  reach into the bucket by hand - the locks a BUSY answer leaves behind are the
  ones the reaper just judged LIVE, so deleting one manually overrides that
  judgement rather than completing it. If BUSY persists across a whole session,
  that is worth a ledger note, not a workaround.
- **UNUSABLE is a THIRD answer and is not a busy bucket.** A status whose
  `usable` is False means the bucket could not be created, listed or written at
  all - its parent is a file, the volume is read-only, or this account may not
  write the directory. The loop PROCEEDS UNGOVERNED: the block still runs, this
  session rations with nobody, and the status line says UNUSABLE in those words
  every cycle so the condition cannot be mistaken for contention. Refusing to
  start would turn a misconfigured directory into an outage while the operator
  is playing and cannot fix it, which is the worse trade - but running quietly
  ungoverned would be worse still, so it is loud. **What to do when you see it:
  it does not clear on its own.** A busy bucket clears when a sibling finishes;
  this one waits for a person. Check that the bucket's parent is a directory
  this account may write, then ledger it. Do not retry it in a loop, and do not
  silence it by pointing the lane at a private directory without saying so in
  the ledger - that is a withdrawal from the shared budget, not a fix.
- **We are now consuming a slot the sibling projects were rationing between
  themselves.** Joining the shared bucket was an operator ruling
  ([ADR-008](../../docs/adr/ADR-008-join-the-shared-bucket.md)), and its honest
  consequence is that a lane Lanternlight holds is a lane another project on
  this machine cannot have. That is the intended behaviour, not a side effect.
- **A lock we leak lands in a directory other projects share.** The release
  runs in a `finally`, so an exception in the body still frees the slot, but a
  hard kill or a power loss leaves the lock behind and it is reclaimed only
  when the stale arm fires - four and a half hours. Until the reserved-floor
  widening lands in that bucket we contend for surplus slots only, so a leak of
  ours is a name every participant's reaper already understands.

## Each cycle

1. **Orient from disk** - `CLAUDE.md`, `README.md`, `ROADMAP.md`, the top of
   `docs/LEDGER.md`, recent `git log`, and `state.load()` for the active
   directive and in-flight item. Re-probe live state rather than trusting a
   document's claim about it.
2. **Pick** the next `ROADMAP.md` item that has an acceptance criterion.
3. **Plan**, and verify every claim in the plan against ground truth before
   writing code.
4. **Execute in parallel slices** on disjoint files, one merger. **Record the
   dispatch before the agents start** - `state.dispatch(*items, lane=...,
   paths=[...])` - and `state.retire(...)` each slice as it lands. Nothing else
   in this tree records that work is running: `item` is singular, lane state
   carries no in-flight field, and a clean `git status` says nothing about
   agents that have not written yet. `OPS-27`.
5. **Verify** with an independent refutation pass. Re-run the suite fresh and
   quote the counts you observed this run.
6. **Ledger** it via `ops.loop.ledger.append_entry(...)` - item id, date,
   one-line summary, acceptance evidence. Into `docs/LEDGER.md`, never
   `CLAUDE.md`.
7. **Commit and push.**
8. **Advance** - `state.advance_cycle(next_directive, next_item)`. Carrying the
   same item forward credits nothing, because that is a retry (`OPS-7`).

Then start the next cycle by reading disk again. Inherit nothing from the last
cycle except what it wrote down. If context is running short, that is not a
problem to work around - it is the design working: clear, and resume with
`/continue`.

## Never block on the operator

Do not ask a question and wait. Do not idle on a prompt. At a genuine decision
gate - a real fork where either branch is defensible and picking wrong is
expensive - write the question into `docs/LEDGER.md` with the options and their
costs, mark the roadmap item blocked on that named question, and **move to the
next item**.

A decision gate is not "I am unsure this is the nicest API". Decide those,
implement, and note the choice in the ledger entry.

## Stop conditions

Full list in [`docs/HEADLESS.md`](../../docs/HEADLESS.md) section 6. If a task
needs any of these, skip the task, record why in the ledger, and continue:

- anything touching the game or the game process (kernel anti-cheat; ADR-001)
- anything that could get the operator banned
- force-pushing
- rewriting history, including editing existing ledger entries
- deleting operator data
- publishing anything containing unredacted log content

## Stopping

- `ops/runtime/stop_requested` exists - finish the current cycle cleanly,
  commit, ledger, release the lock, exit.
- The roadmap has no eligible item left - say so plainly and exit. Do not
  invent work to stay busy.
- Session ends or the process dies - the lock is left with a dead pid and the
  next run reclaims it.

Run `/done` on the final cycle before exiting.
