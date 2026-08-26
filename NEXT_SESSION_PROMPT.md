# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`
(section 11 especially), `docs/OBSERVED_IDS.md`, `ROADMAP.md`,
`docs/HEADLESS.md`, `WAKEUP_NOTES.md` (top entry only), then
`git log --oneline -15`.

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

**2026-08-25. Suite 1225 passed / 1225 collected, ruff clean**, measured on a
clean tree with `__pycache__` purged - that is your merge-gate baseline, and
re-measure it yourself before dispatching work rather than trusting this line.
The session's ledger entries start at `LL-0049` and run to the end of the file's
newest block - `grep -n '^### LL-00' docs/LEDGER.md | head` lists them, and no
end-point is filed here because that literal went stale three times in one
session. **Read the corrections first.** Several entries correct the ones before
them; the correcting entries are the ones that explain why the measurements are
trustworthy, and they are more useful than the entries they correct.

**No code changed all session.** It was measurement and documentation, so the
test count is unchanged by design.

### Check the world before anything else

Three things had moved since the previous session and all three mattered:

- **The game was patched** to Steam buildid `24813185` on 2026-08-19. Every id
  in `docs/OBSERVED_IDS.md` was read on a build that no longer exists and none
  has been re-confirmed.
- **The 6.1 MB log from 2026-08-09 no longer exists.** The game truncates its
  log on launch and keeps no backup. A log is evidence only until the next
  launch.
- The market cache had emptied itself back to 37 bytes and nobody saw it
  happen.

The command that settles whether the client is open - do this first, it decides
what you work on. It **says which**, rather than printing nothing and leaving
you to guess whether the check failed or the game is shut:

```
tasklist | grep -qi mistfall && echo "CLIENT OPEN" || echo "client closed"; stat -c '%y %s' "$LOCALAPPDATA/MistfallHunter/Saved/Logs/MistfallHunter.log"
```

That is Bash, not PowerShell - this repo's shell is PowerShell by default and
`grep` and `stat` do not exist there. Run it through the Bash tool.

**Whatever the answer, archive the log first.** It is truncated on the next
launch with no backup kept, and it took one deleted 6.1 MB log to learn that.
Pointing `lanternlight.savewatch.SaveWatcher` at the `Logs/` directory with a
long poll interval is the whole job - the 2026-08-25 session's final 5,080,313
byte log sits under `C:/ll-captures/2026-08-25/logs/`, verified byte-identical
to the live file by sha256 (`1c44235c...`), and therefore survives the next
launch's truncation.

## ROADMAP 7b is ANSWERED - what that bought

The **training ground exists** and is **not a match**: no
`StandaloneSlot_<roleId>.sav` appeared in 36 minutes across ~200 shots, no
`EnterBattle`, and the whole log carries seven occurrences of the substring
`damage` with **not one number** among them. So `DamageCollectonDataSet` is not
written there and `lanternlight/damage.py` has nothing to read in that room.

It is a **pixel rig**. The room renders a cumulative **Total Damage** meter and
writes it nowhere; differencing that meter across captured frames is the
measurement. `Progress Record` beneath it holds the **previous run's** pair.

**Per-hit body damage on the damage floor is exactly 10.35**, solved interval
`[10.3500, 10.3571]`. First value in this project to clear the independent-run
bar. No coefficient is published from it and none may be.

The falloff curve, ten distances in paces:

| paces | 10 | 9 | 8 | 7 | 6 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| total | 104 | 104 | 104 | 231 | 309 | 546 | 687 | 687 | 689 | 691 |

Clamped floor, about 1.3x per pace over four paces, clamped ceiling. Ceiling is
6.64x the floor. **Headshots never give a constant per-hit value**, not even on
the floor where body shots do.

### Start here

1. **If the client is open**, work ROADMAP **7b's open threads** - why the floor
   is a step rather than a tangent, what separates a headshot from a crit, and
   whether ~1.3x per pace is real. All cheap, all need the client. Fold in items
   1, 4b, 5 and 6, which also need it. **Arm the wide-shot poller before the
   first run.**
2. **If the client is closed**, work item **4c** (arm the archiving watchers -
   no new code, `lanternlight/savewatch.py` already does the copying) or item
   **7c** (read the meter without a human reading it).

## How to measure the meter, so you do not rediscover this

- **Solve, do not eyeball.** A constant per-hit value ALWAYS makes the displayed
  deltas wobble by one, because the meter rounds a real-valued cumulative sum.
  A wobbling delta is not evidence of variance. Solve `round(n*v) == total_n`
  across a run: you get an interval, or a contradiction, and only the
  contradiction is evidence.
- The observed cumulative states for all ten runs are published in
  `docs/FINDINGS.md` 11.7, so the whole solve is re-runnable from the artifact.
- **Capture economics, measured.** Full-screen PNG at 2 fps is **4.8 MB a
  frame, 34 GB an hour** - do not leave it running. Cropping the HUD rectangle
  at capture time is ~150 KB. A half-scale JPEG wide shot at 1 fps is ~140 KB
  and is what records where the operator stood.
- **Deduping panel frames by pixel hash FAILS.** The plate is semi-transparent,
  so the scene behind it changes the hash while the number stands still. A
  coarse column-occupancy signature over the digit colour is what works.
- Tesseract is **not installed** and is not to be installed for this. Item 7c
  is the template-matching reader, and its acceptance insists it **refuse**
  rather than guess.
- This session's evidence is at `C:/ll-captures/2026-08-25/`. It contains the
  operator's account name and third-party player ids and **must never be
  committed**.

## Traps that will bite you, all measured

- **A measurement whose independent variable was INFERRED rather than RECORDED
  is not a measurement of that variable** - and it reads exactly like one. The
  first distance sweep had to be re-run because its distances came from clock
  order. Record the independent variable in the same stream as the dependent
  one.
- **The wrap refutation was run three times and found 13, then 5, then 2.** It
  is not a step you complete, it is a step you repeat until it comes back
  empty. Round one found that BOTH arguments made for the WRONG distance
  mapping were arithmetically invalid - each mixed two mappings - and that one
  run had been solved using points belonging to its neighbour. Round two found
  the fix had been applied in one of the two places the defect lived. Round
  three found it applied in both places with a number nobody re-derived, which
  is worse because it reads as corrected. **When you act on a refutation,
  re-derive the arithmetic of your correction, not just its presence.**
- **A Windows path in a non-raw Python string** turns `\2026` into an octal
  escape and writes byte `0x82`. It happened twice in one session. Use forward
  slashes.
- **An empty grep is a claim about your pattern**, not about the codebase.
- **Do not pass `-q` to pytest.** `pytest.ini` already sets it; `-qq`
  suppresses the summary line entirely.
- **Clear `__pycache__` before any mutation test.**
- **`ops/merge_gate.py` exists so you never relay an agent's claim.** Measure
  the baseline before dispatching and pass it in.

## Open questions nobody has answered

- Why is the damage floor a **step** rather than a tangent? Extrapolating the
  slope predicts ~174 at 8 paces and it reads 104.
- What separates a headshot from a crit? The client renders headshots in red
  crit text, so the eye cannot do it and neither could this data.
- Is `matchId` what distinguishes the Prologue from a real raid? Predicted,
  never observed.
- What are the 4 zero bytes after every GVAS tagged property list?
- Sorcerer's single weapon config id is still unexplained. **Nothing in this
  repo may say Blackarrow is the only single-weapon class.**
- Where do server-side settings live? `InvertCameraYAxis` is in the log and in
  no save file.

## Operator context worth having

Plays **Blackarrow** (classId 12), second character at classId 13. Right-click
is the primary attack (binds swapped), standard arrow. Counts distance in
**paces** - a full stride, counted off the run-cycle animation loop reset, no
crouch, sprint or roll. Reliable, engaged, and volunteers control failures
unprompted - when he says he was "a little off the mark", believe it and treat
that run accordingly.

**He cannot read chat while playing.** Use text-to-speech for anything he needs
mid-game, keep it short, and never block waiting for an answer.
