# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`,
`docs/OBSERVED_IDS.md`, `ROADMAP.md`, `docs/HEADLESS.md`, `WAKEUP_NOTES.md`
(top entry only), then `git log --oneline -15`.

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
   includes other players' names, not only the operator's.

---

## Where the last session left it

Branch `session/2026-08-09-recon-redaction-lanes`, pushed, **not merged to
`main`**. Ledger entries `LL-0002` through `LL-0012`. Two lane branches exist
and are also pushed: `lane/ingest` and `lane/safety`.

**Re-probe live state before trusting any number below.** The single
highest-value move of the last session was re-probing and finding three
documented facts had gone stale inside one session - the log had grown 567 KB to
6.1 MB, the market cache had filled, and a fifth save file had appeared. The
operator plays between sessions. Assume the world moved.

### Start here

1. **ROADMAP item 1b, the lane build-out**, is the biggest ready piece. The
   roster, launcher and generated contracts all landed and a lane has been run
   end to end. What is missing: **per-lane on-disk state** (agent context does
   not survive a session, so "persistent specialist" is fiction without it) and
   **commit serialisation** (eight lanes and one `docs/LEDGER.md` will race).
2. **Item 1's remainder needs the operator to enter a real raid.** Everything
   measured is the Prologue at `matchId=0`. Do not schedule a capture session -
   the log alone was sufficient last time. Just check for a run with a non-zero
   `matchId`.
3. **Items 3 (live log tail) and 4's watcher** are unblocked and independent.

### How to run a lane

```python
from ops import lane_launcher, lanes
lane = lanes.by_id("ingest")
lane_launcher.ensure_worktree(lane)          # C:\ll-worktrees\ll-lane-<id>
lane_launcher.assert_in_lane_worktree(lane)  # refuses outside its own worktree
```
Each lane's contract is `.claude/commands/lane-<id>.md`, generated from
`ops/lanes.py`. **Edit the roster, then run `python scripts/write_lane_contracts.py`** -
a drift test fails otherwise. Lanes commit to `lane/<id>` and never merge to
`main`.

### Traps that will bite you, all measured

- **An empty grep is a claim about your pattern.** `cfgId:(\d+)` silently
  dropped an entire subsystem because `TS.FTE` writes `cfgId: 123` with a space.
  It cost a wrong number in a published document.
- **Clear `__pycache__` before any mutation test.** A same-length mutation inside
  one mtime tick leaves a stale `.pyc`, which can fake a GREEN under mutation and
  therefore fake a non-vacuity proof outright.
- **Do not pass `-q` to pytest.** `pytest.ini` already sets it; `-qq` suppresses
  the summary line entirely.
- **`git check-ignore -v` prints the pattern even for a negation.** Test the exit
  code, not whether there was output.
- **A path from `__file__` is not a fact about the repository.** Inside a
  worktree it is that worktree. Use `lanes.primary_checkout()`.
- **`ops/merge_gate.py` exists so you never relay an agent's claim.** Measure
  per-file counts BEFORE dispatching and pass them as the baseline; a global
  total lets one agent's additions mask another's deletions.
- **Agreement is not verification.** An adversarial pass returned **nine**
  defects in findings that had already been written up confidently. Dispatch the
  refuter every time.

### Open questions nobody has answered

- Is `matchId` what distinguishes the Prologue from a real raid? Predicted, not
  observed.
- Does the camp-return option byte (`GAA=` vs `GAU=`) carry the run outcome? Two
  samples cannot establish an encoding.
- What are the 4 zero bytes after every GVAS tagged property list? An `int32`
  zero, an empty FString and four flag bytes all fit; nothing separates them.
- Sorcerer's single weapon config id is still unexplained. **Nothing in this repo
  may say Blackarrow is the only single-weapon class.**
- Where do server-side settings live? `InvertCameraYAxis` is in the log and in no
  save file, so a settings reader built on `.sav` alone is incomplete.
- Raw UTF-16 in a file still defeats the PII guard; UTF-16 inside base64 does not.

### Operator context worth having

Plays Blackarrow (classId 12), has a second character at classId 13
(Shadowstrix). Deluxe edition, three Twitch drops claimed, Discord linked - no
entitlement id observed anywhere yet. Has swapped primary/secondary attack binds
(right click primary) and turned off invert-look. Died once, in the tutorial.
Cannot read chat while playing; use text-to-speech for anything urgent, and
never block waiting for an answer.
