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

Usage:

```python
from ops.loop import guard

with guard.released() as lock:
    ...  # the lock is held here and released however the block exits
```

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
