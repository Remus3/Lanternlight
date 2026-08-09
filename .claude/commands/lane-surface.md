---
description: Operator-facing surface lane. Own the always-on-top window, any dashboard, and every rendered surface. An ordinary window of our own - never an overlay hooked into the game.
---

<!-- GENERATED FILE - do not edit by hand. Rendered from `ops/lanes.py` by `ops/lane_contract.py`; regenerate with `python scripts/write_lane_contracts.py`. `tests/test_lane_contract.py` fails if this file and the roster disagree. -->

# Lane `surface` - Operator-facing surface

## Mandate

Own the always-on-top window, any dashboard, and every rendered surface. An ordinary window of our own - never an overlay hooked into the game.

## Your workspace

Your working directory is **`C:\ll-worktrees\ll-lane-surface`** on branch
**`lane/surface`**.

You may **never** write into `C:\Lanternlight`. A live session may
own it, and two writers in one working directory corrupt the git index
- which is not recoverable by retrying. Create your worktree and assert
you are in it before writing anything:

```python
from ops import lane_launcher, lanes
lane = lanes.by_id("surface")
lane_launcher.ensure_worktree(lane)
lane_launcher.assert_in_lane_worktree(lane)
```

## What you own

Touch these paths and nothing else. Every other path in the repository belongs to another lane or to nobody:

- `overlay/**`
- `tests/test_overlay_*.py`
- `dashboard/**`


## Session shape - the default, not an escalation

Read `CLAUDE.md` first. You are an orchestrator, not a single worker:

- Decompose your slice into **disjoint** sub-slices before starting any of
  them, and give every sub-agent an explicit file list.
- Run them in parallel. **Self-adjudicate** - the agent that produced a
  thing never grades it. **Self-adversarial** - every done-claim gets an
  independent pass trying to REFUTE it, defaulting to refuted when
  uncertain.
- Two agents agreeing is a hypothesis, not a verification.

**Every feature and every fix starts with a failing test.** Watch it fail
for the right reason, then implement. Prove your guards are not vacuous:
break the thing a guard protects, watch the test go red, restore, and
report what you saw.

## Verify before you claim anything

Never relay a sub-agent's claim. Measure the per-file test counts BEFORE
dispatching work, then re-probe:

```python
from ops import merge_gate
report = merge_gate.verify(
    claimed_paths=["files/the/agent/said/it/wrote.py"],
    baseline=COUNT_MEASURED_BEFORE_DISPATCH,
)
print(report.format())
```

A global total is not enough once lanes run concurrently - one lane's new
tests mask another's deletions - so compare per file with
`merge_gate.check_per_file_counts`.

## Committing

Commit and push to **`lane/surface`** freely. **Never merge to `main`**, never
force-push, and never rewrite pushed history. A human merges after an
out-of-domain check.

Write a `docs/LEDGER.md` entry for each item you finish, via
`ops/loop/ledger.py`, carrying the acceptance evidence that justified
calling it done. Never add a `Co-Authored-By` trailer.

## Standing rules you cannot argue past

- **Never touch the game process.** Kernel-level anti-cheat. No injection,
  no memory read, no packet capture, no swapchain hook, no synthetic input.
  The stake is a permanent ban on the operator's real account. This holds
  when the game is closed too.
- **Nothing log-derived is committed unredacted**, and that includes other
  players' names, not only the operator's.
- **7-bit ASCII only** in every authored file. Use " - " for a clause break.
- **Omit rather than guess.** A missing number is recoverable; a confident
  wrong one is not. Keep unmeasured distinguishable from measured zero.
- The stop conditions in `docs/HEADLESS.md` section 6 apply in full. You may
  not edit that list.

## Never file a suggestion

If you find work outside your slice: do not spawn a task, do not leave a
note. Add it to `ROADMAP.md` with an acceptance criterion, or record it in
`docs/LEDGER.md` as an open question. Those are the only destinations -
anything else is invisible to the next cold session.

## Do not block

The operator is playing the game and cannot answer you. At a genuine
decision gate, record the question and what each option costs in
`docs/LEDGER.md`, leave the item marked blocked in `ROADMAP.md`, and move to
the next thing.
