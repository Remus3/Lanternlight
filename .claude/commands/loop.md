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

Take the single-instance lock. Two loops would interleave commits and race each
other's ledger appends.

```python
from ops.loop import guard, state

with guard.released() as lock:
    ...  # every cycle runs inside here
```

- `LockBusy` means another loop is live: **print why and exit.** Do not retry in
  a spin, and do not remove the lock. The guard never terminates the holder,
  and neither do you.
- A lock left by a dead pid is reclaimed automatically. That is the crash-
  recovery path, not an error.

## Each cycle

1. **Orient from disk** - `CLAUDE.md`, `README.md`, `ROADMAP.md`, the top of
   `docs/LEDGER.md`, recent `git log`, and `state.load()` for the active
   directive and in-flight item. Re-probe live state rather than trusting a
   document's claim about it.
2. **Pick** the next `ROADMAP.md` item that has an acceptance criterion.
3. **Plan**, and verify every claim in the plan against ground truth before
   writing code.
4. **Execute in parallel slices** on disjoint files, one merger.
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
