# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`,
`docs/OBSERVED_IDS.md`, `ROADMAP.md`, `docs/HEADLESS.md`, then `git log`.

**Before touching anything:**

```
python scripts/install_hooks.py
python -m pytest
```

A fresh clone runs zero git hooks until that first command runs. The tracked
`.githooks/` directory does nothing on its own.

## The three rules that are not negotiable

1. **Never touch the game process.** Kernel-level anti-cheat. No injection, no
   memory read, no packet capture, no swapchain hook, no synthetic input. The
   stake is a permanent ban on the operator's real account. Passive screen
   capture and reading files the game writes are fine. See ADR-001.
2. **7-bit ASCII everywhere**, and never add a `Co-Authored-By` trailer.
3. **Nothing log-derived is committed without passing the redactor**, and that
   now includes **other players' names**, not only the operator's.

---

## Where the last session left it (2026-08-09)

Work is on branch `session/2026-08-09-recon-redaction-lanes`, pushed, **not
merged to `main`**. Six ledger entries, `LL-0002` through `LL-0007`.

**Re-probe before trusting any number below.** The last session's single most
useful move was re-probing live state and discovering three documented facts had
gone stale inside one session - the log had grown 567 KB to 6.1 MB, the market
cache had filled, and a fifth save file had appeared. The game may well have
been played again since.

### Start here, in this order

1. **ROADMAP item 0 is closed** (the redactor P0). Item **1b**, the specialist
   lane build-out, is the biggest ready piece: the roster and its invariants
   landed, but the launcher, the per-lane contract files, the per-lane on-disk
   state and the commit-serialisation answer do not exist. Acceptance is one
   lane demonstrated end to end, not described.
2. **Item 1's remainder needs the operator to enter a real raid.** Everything
   measured so far is the Prologue at `matchId=0`. Do not schedule a capture
   session for it - the log alone was sufficient last time. Just check whether a
   run with a non-zero `matchId` has appeared.
3. **Items 2, 3 and 4's watcher** are all unblocked and independent.

### Things that will bite you if you do not know them

- **An empty grep is a claim about your pattern.** `cfgId:(\d+)` silently
  dropped every `TS.FTE` line because that subsystem writes `cfgId: 123` with a
  space. It cost a wrong number in a published doc.
- **The hygiene guards now scan uncommitted files too.** They used to walk
  `git ls-files` and were blind to exactly the new files most likely to carry a
  pasted identifier.
- **`ops/merge_gate.py` exists so you do not relay an agent's claim.** Measure
  the per-file test counts BEFORE dispatching work and pass them as the
  baseline; a global total lets one agent's new tests mask another's deletions.
- **Agreement is not verification.** Last session an adversarial pass returned
  **nine** defects in findings that had already been written up confidently,
  including a death attributed to the operator that belonged to another player.
  Dispatch the refuter every time.
- **The redactor is scope-dependent by nature.** It discovers personas from
  keyed shapes and then masks literals, so redact the FULL log and excerpt from
  the redacted text - or pass `personas=` explicitly. `assert_clean` will now
  refuse to certify rather than pass vacuously, but do not lean on that.

### Open questions nobody has answered

- Is `matchId` what distinguishes the Prologue from a real raid? Predicted, not
  observed.
- What are `Game.PlayState.Spiritual` and `WaitSpiritual`? Suspected downed or
  ghost state; unestablished.
- Does the camp-return option byte (`GAA=` vs `GAU=`) carry the run outcome? Two
  samples cannot establish an encoding.
- Sorcerer's single weapon config id is still unexplained. **Nothing in this
  repo may say Blackarrow is the only single-weapon class.**
- `OnlinePlayerCount: 0` appears alongside a second player's `PlayerName`. Those
  cannot both mean what they appear to mean.
