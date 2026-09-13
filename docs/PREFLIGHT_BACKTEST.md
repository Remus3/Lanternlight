# Back-testing the pre-flight - what it would have caught, and what it could not see

`OPS-87` criterion 3: "Run the new pre-flight against the tree as it stood when
each historical finding was filed, and report how many it would have CAUGHT and
how many it would have MISSED. A gate that cannot show it would have caught a
finding that really happened is a hypothesis wearing a result's clothes."

Two experiments were run. The first returned zero catches, and reporting that
figure on its own would have been reporting an instrument defect as a result.

## Experiment one: the parent of the commit that filed the finding

For each of the 17 ledger entries carrying at least one gate-reachable event,
`git log -S'### LL-NNNN - '` names the single commit that filed it. Its parent
is the tree immediately before. Today's 14 pre-flight modules were run in a
detached worktree at each of those 17 trees.

**CAUGHT 0. MISSED 17. NO-GUARD 0. UNBUILDABLE 0.**

Every tree ran clean - 180 to 314 tests passing, no failures.

### Why, and it is not that the guards are weak

The tree those findings lived in was never committed. Measured on `83a4f86`,
the commit that filed `LL-0236`:

```
 .claude/commands/lane-safety.md   |   1 +
 docs/INVENTORY.md                 |   1 +
 docs/LEDGER.md                    |  16 +
 ops/lanes.py                      |   1 +
 tests/test_gitignore_shadowing.py | 908 +
```

The new test module, its inventory row, its lane owner, its regenerated contract
and the ledger entry recording the whole thing all arrive in ONE commit. The
state where the module existed and the registration did not lasted about twenty
minutes inside a session and never reached the object store. The parent tree
contains neither the module nor the gap, so the guards were green for a correct
reason and the MISS is a fact about the addressing scheme, not about the guard.

**This is a result in its own right.** These mechanical defects do not ship.
They are caught before a commit - by the merger, or by a full suite run - which
means the pre-flight's value is not measured in defects prevented from reaching
`main`. It is measured in the time between the defect existing and somebody
finding out, and in whether that somebody is a nineteen-second program or an
adversarial agent.

## Experiment two: the mid-session state, reconstructed

The addressable state is rebuilt from the fix commit itself: check out the tree
AS THE FIX LEFT IT, then remove the registration lines that same commit added
for the new test module. Nothing is invented - every removed line is one the
commit is on record as adding - and the removal is mechanical
(`tools.preflight_backtest.strip_mentions`).

Nine entries in the window were filed by a commit that added a
`tests/test_*.py`, which is the shape class (b) takes here.

**CAUGHT 9. MISSED 0. NO-GUARD 0. UNBUILDABLE 0.**

| Entry | Fix commit | Un-registered module | Pre-flight result |
|---|---|---|---|
| `LL-0178` | `d6de485e` | `tests/test_stop_audit.py` | 3 failed |
| `LL-0187` | `b3fbba83` | `tests/test_store_drift.py` | 3 failed |
| `LL-0191` | `6bb55788` | `tests/test_precommit_hook_globbing.py` | 3 failed |
| `LL-0192` | `6bb55788` | `tests/test_precommit_hook_globbing.py` | 3 failed |
| `LL-0196` | `0eb6217a` | `tests/test_archive_link_guard.py`, `tests/test_doc_archive.py` | 3 failed |
| `LL-0197` | `0eb6217a` | same pair | 3 failed |
| `LL-0220` | `02a40edd` | `tests/test_apply_doc_split.py` | 5 failed |
| `LL-0230` | `4095e27d` | `tests/test_vendored_write_tracer.py` | 5 failed |
| `LL-0236` | `83a4f86c` | `tests/test_gitignore_shadowing.py` | 5 failed |

The failing test names are printed by the harness rather than summarised, so a
catch can be checked for relatedness instead of believed on its exit code. Every
catch here fails on `tests/test_lanes.py::TestNoFileIsOrphaned` and
`tests/test_lane_contract.py::TestOnDiskMatchesTheRoster` - the orphan and the
stale contract - which is the defect the reconstruction introduced.

**Three of the nine catch it with three tests and six with five, and the
difference is a date.** The two `tests/test_inventory.py` arms only appear from
`LL-0220` onward, because the inventory completeness property landed with
`OPS-69` on 2026-09-10. In the four oldest trees the pre-flight still catches
the registration gap, but through the lane roster alone. A guard that postdates
a finding cannot have caught it, and the harness reports NO-GUARD rather than
crediting itself; here the older trees are catches on the strength of the
guards they actually had.

## What these two numbers do and do not license

* They show the pre-flight fires on the class (b) shape in a REAL tree, nine
  times out of nine, using only guards that existed in that tree.
* They do NOT show it prevents anything from shipping. Experiment one says the
  opposite: this class does not reach a commit.
* They say nothing at all about class (a). 60 of the 135 events in
  [`REFUTATION_CENSUS.md`](REFUTATION_CENSUS.md) are real defects in the
  deliverable, and no run in either experiment would have found one of them.
* The reconstruction is our own construction. It is derived mechanically from a
  real commit, but it is a rebuilt state rather than an observed one, and it is
  labelled that way everywhere it is reported.

Reproduce either experiment:

```bash
python -m tools.preflight_backtest --entries LL-0236,LL-0230
python -m tools.preflight_backtest --reconstruct --entries LL-0236,LL-0230
```
