---
description: Resume Lanternlight from disk. Read state, pick the next item, start work. Ask nothing.
---

# /continue - resume from disk

Continuity in this project lives on disk, not in a context window. You may have
been cleared, compacted, or started cold on a machine that has never seen this
work. It does not matter. Everything you need is in files.

**Do not ask the operator anything.** They are playing Mistfall Hunter. A
question is a failure of this command, not a use of it.

## Session shape (default, not an escalation)

Every session here is **orchestrated, multi-agent, parallel, self-adjudicating
and self-adversarial**:

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

**Every feature and every fix starts with a failing test.** Write the test,
watch it fail for the right reason, then implement.

Departing from this shape needs a justification. Choosing it does not. The only
exception is genuinely trivial work - a doc typo, a single string.

## Steps

1. **Read the durable record.** In one batch:
   - `CLAUDE.md` - the rules
   - `README.md` - what this project is
   - `ROADMAP.md` - what is next, with acceptance criteria
   - the top few entries of `docs/LEDGER.md` - what just landed
   - `git log --oneline -15` - what actually landed, in order
   - `ops/runtime/loop_state.json` via `ops.loop.state.load()` - the active
     directive, the in-flight item, the cycle number, the completed ids
2. **Re-probe live state.** Do not trust a document's claim about the world.
   If it says a file exists, a port is listening, a test count is N, or a field
   is present in a log - check. Documents go stale; the disk does not lie.
3. **Reconcile.** If `loop_state.json` names an in-flight item, look for its
   work: a branch, a worktree, uncommitted changes, a partial test. Finish it
   before starting anything new. If it landed but was never ledgered, ledger it.
4. **Pick the next item.** Take it from `ROADMAP.md`, in priority order. Skip
   any item with no acceptance criterion and any item blocked on a named
   question - do not answer the question on the operator's behalf.
5. **Plan, then verify the plan.** Emit the plan before writing code, and check
   every claim it makes against ground truth - grep the file and line it cites,
   run the command it assumes. Never scaffold against an assumed API surface.
6. **Work it**, in the session shape above.
7. **Wrap with `/done`.**

## Hard rules that apply to every cycle

- 7-bit ASCII only in all authored text. Use ` - ` for a clause break.
- Never emit a `Co-Authored-By` trailer, and never instruct anyone to add one.
- The stop conditions in [`docs/HEADLESS.md`](../../docs/HEADLESS.md) section 6
  apply in full, whether or not the loop is what invoked you.
