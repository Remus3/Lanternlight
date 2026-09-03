---
description: Wrap the session - full suite, commit, push, ledger the item, sync docs, print the next-session prompt.
---

# /done - the wrap ritual

Nothing is finished until it is on disk and pushed. A session that ends with
work in a worktree ends with that work lost, because the next session starts
with an empty context and will never know to look.

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

**Every feature and every fix starts with a failing test.** That rule applies
to anything you fix during the wrap too - a green suite reached by editing the
test rather than the code is not a green suite.

## Steps

1. **Audit what is pending.** `git status` and `git diff`. Read the diff; do
   not commit changes you have not looked at.
2. **Run the full suite, fresh.**
   - `python -m pytest`
   - `python -m ruff check .`
   Report the **exact** summary line you observed **this run**. Never carry a
   count forward from earlier in the session, and never quote a count from a
   document or from a subagent's report - re-run and read it yourself.
3. **Refutation pass.** Hand the "done" claim to an independent agent whose job
   is to break it: confirm every cited file exists, every cited test runs, and
   every claimed behaviour is actually exercised rather than asserted. Default
   to refuted when uncertain.
4. **Commit and push.** A descriptive message - what changed and why, not
   "updates". **Never** add a `Co-Authored-By` trailer. Never force-push, never
   amend a pushed commit, never rebase published history.
5. **Append the ledger entry.** Use `ops.loop.ledger.append_entry(...)`:
   item id, ISO date, one-line summary, and the acceptance evidence - the test
   names, file paths and observed results that justify calling it done.
   **The entry goes in `docs/LEDGER.md`. Never in `CLAUDE.md`.** `CLAUDE.md`
   holds rules; it is auto-loaded every turn and is not a log.
6. **Sync the living docs.** Update `ROADMAP.md` - move the finished item out,
   promote the next one, and record any decision gate you hit as a named
   blocker rather than answering it yourself. Update `README.md`,
   `docs/ARCHITECTURE.md` or `docs/OPERATIONS.md` only where this session made
   them wrong. If you changed a number that a document recites, grep for the
   literal old value; a stale recital is worse than no recital.
7. **Advance the loop state.** `ops.loop.state.advance_cycle(...)` with the
   next directive, so a cold session can pick up from disk alone.
8. **Re-check the watcher.** Call `check_watcher()` from `ops/loop/watch.py`
   (or its `ensure_armed_at_wrap` wrapper) before the next-session prompt is
   printed. Re-arm on `NO_RECORD`, `DEAD` or `IMPOSTOR`; a `STALE` or
   `NO_HEARTBEAT` result is reported, not re-armed, and nothing is ever
   killed - see `docs/HEADLESS.md` 4b.
9. **Print the next-session prompt.** A complete, self-contained prompt: what
   was just finished, what is next, the acceptance criterion, and the files to
   read first. Assume the reader has zero context, because they will.

## Definition of done

- Suite green, counts observed this run and quoted exactly.
- Ruff clean.
- Committed and pushed.
- Ledger entry appended with real evidence.
- `ROADMAP.md` reflects reality.
- Watcher re-checked with `check_watcher()`, and its state reported in the
  next-session prompt rather than assumed.
- Next-session prompt printed.
