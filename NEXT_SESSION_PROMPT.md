# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`
(sections 11 to 15), `docs/OBSERVED_IDS.md`, `ROADMAP.md`, `docs/HEADLESS.md`,
`WAKEUP_NOTES.md` (top entry only), then `git log --oneline -15`.

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

**Suite 1295 passed / 1295 collected, ruff clean**, measured on a clean tree
with `__pycache__` purged - that is your merge-gate baseline, and re-measure it
yourself before dispatching work rather than trusting this line.

The ledger runs to **`LL-0074`**. Read **`LL-0064`** and **`LL-0074`** first,
then `LL-0066` and `LL-0067`.

- **`LL-0064`** is an independent four-agent refutation pass that **overturns
  claims earlier entries make** - reading LL-0056 through LL-0063 without it
  leaves you believing things that were withdrawn.
- **`LL-0074`** is the end of the 7c white-row chain and supersedes the
  intermediate conclusions in `LL-0071`, `LL-0072` and `LL-0073`. Those three
  contradict each other on purpose, each correcting the last; only the last one
  is current.
- **`LL-0066`** closes OPS-8 and records that **the mechanism OPS-8 itself had
  on file was wrong about the dominant case**, found only by re-measuring before
  fixing. **`LL-0067`** is its refutation: it could not overturn the claim, but
  found the fix had **opened a PII hole**, hiding git-TRACKED files from the
  guard.

## Check the world before anything else

```
tasklist | grep -qi mistfall && echo "CLIENT OPEN" || echo "client closed"; stat -c '%y %s' "$LOCALAPPDATA/MistfallHunter/Saved/Logs/MistfallHunter.log"
```

That is Bash, not PowerShell - `grep` and `stat` do not exist in this repo's
default shell. Run it through the Bash tool.

**Then arm capture, whatever the answer. It is one command now:**

```
python -m lanternlight.armwatch --dest-root C:/ll-captures/<today>
```

That is ROADMAP 4c, closed last session. It arms all four surfaces at intervals
argued from measured triggers, and it **refuses a destination inside a git
working directory** rather than trusting you to remember. It watches the
`Logs/` DIRECTORY, not the log file, which is what catches a launch's
`MistfallHunter-backup-<UTC>.log` - so arming at session start recovers the
PREVIOUS session as well as preserving the current one. Whether a launch leaves
a backup at all is **unmeasured**: one did, an entire earlier session had none.

## NEXT: ROADMAP item 10 - the stack buff, measured AT THE CEILING

**This is the highest-value open question, because an existing headline finding
may be an artifact.**

The operator found a buff icon that climbs to **5** while he keeps hitting the
same target inside a time limit, centre screen above the energy bar. It is
readable in a half-scale wide shot at `x 600-690, y 600-665`, and joining that
crop to the meter crop on wall clock puts stack count and cumulative damage on
one row.

`FINDINGS` 11.7 says a constant per-hit value fits every FLOOR run and no
off-floor run, and reads that as constancy being a property of the clamp. **A
buff of ~1% per stack reproduces that split with no distance term at all** -
invisible at 10.35 per hit, visible at 55 to 69. The ten-point curve is
untouched; the inference is contested.

**Measure at the CEILING. The floor is insensitive** - at ~13.5 per hit the
whole five-stack bonus rounds away, which is why nine floor runs gave only a
4-count spread. At ~90 per hit it is several display units.

Acceptance is in ROADMAP 10, including the target-switch test that separates
`Focus Fire` from a base mechanic. **Do not attribute the buff to Focus Fire
without it**: the tooltip scopes that talent to `Rapid Arrows`, and 2.27-2.87 s
inter-hit intervals prove drawn shots, not Volley.

**If the client is shut, there is no code item ready to start.** Everything
specified is closed: OPS-7 and OPS-12 on 2026-08-27, OPS-8 on 2026-08-26b, 4c on
2026-08-25b, and 7c is as far as its data allows.

**7c is PARTLY DONE.** The orange pair reads and reproduces the hand-read series
exactly. The white Progress Record pair is **blocked on a new capture** - and the
reason changed twice, so read it carefully rather than skimming:

- `LL-0071` said the white field never changes. **That was wrong** and `LL-0072`
  refuted it: the field varies plenty and the existing capture does cover all ten
  digits.
- `LL-0074` re-blocks it on data for the OPPOSITE reason. The field changes
  *often*, so only about five record epochs last long enough to give clean
  training frames, and those few repeat the same digits.

Slot geometry, the previous-run labelling method and the refusal gate are all
measured and working; alignment, thresholds, grid size and three run-boundary
rules were tried and refuted. Clean frames classify near-perfectly (p90 distance
0.012); near-transition frames are mid-render and unlabellable by any rule. The
live limit is a tradeoff with no good point on it: ten digits costs accuracy
(72.4% on accepted frames), accuracy costs coverage (89.7% on five digits).

**Capture request, and it costs the operator almost nothing:** longer stable
stretches per record value - pausing between runs rather than starting the next
immediately - across at least ten distinct records. The same session can serve
ROADMAP 10.

**`advance_cycle` is safe to call normally again.** Carrying an item forward is
a retry and credits nothing, so you no longer need `complete_current=False` by
hand when ROADMAP 10 stays parked.

**OPS-12 is CLOSED as of 2026-08-27.** Before you add a roadmap item, ask for
its id rather than counting by eye - counting from the OPEN items is what
produced two collisions:

```
python -c "from ops import ops_ids; print(ops_ids.next_free_id())"
```

**OPS-8 is CLOSED as of 2026-08-26b.** The suite now survives 6-way concurrent
pytest - 24 consecutive green full-suite runs against a measured 9-of-10-red
baseline - so the merge gate no longer reddens for reasons unrelated to the
work it gates.

## Traps this session paid for

- **Point verification at the READINGS, not the arithmetic.** Four independent
  refuters found **zero** arithmetic errors and **eight** bad readings: a
  misread frame, an invented explanation for a sampling gap that did not exist,
  a circular citation, a binding read off a `Puerts: Error` line, a delta
  transposition that summed correctly either way.
- **A sum is not a check on an ordering.** A transposed delta list summed to the
  same total, so every total-based check passed it.
- **A self-run refutation cannot find a fix you applied in only one place.**
  LL-0058 corrected an over-claim in two files and missed a third in the same
  commit. An independent pass found it immediately.
- **"Which conclusion feels less exciting" is not evidence.** The mode-versus-
  patch call was made that way and was refuted; build and mode are perfectly
  confounded.
- **Quote the DELIVERED capture rate, not the requested one.** A poller asked
  for 2 fps delivered 1.19.
- **A full-screen PNG is ~3.1 MB; the panel crop is ~235 KB.** Crop at capture
  time. Disk sat at 95% all session.
- **`taskkill /F /PID` needs `//F //PID` from Git Bash**, or MSYS mangles the
  flags into paths. `Stop-Process` is forbidden.
- **An over-constrained grep gives a false negative.** One here did, and was
  caught only by re-checking with a positive control. Always prove the pattern
  on a file that DOES contain the string.
- **A FILED MECHANISM IS A HYPOTHESIS, exactly like a filed count.** OPS-8's
  write-up named two casualty tests. Re-measured before any fix, **neither
  failed even once** and the real mode was a different one. Re-run the
  measurement; do not fix what the write-up says is broken.
- **Ask whether a change makes a guard MISS something, not only whether it
  still catches what it caught.** Three mutations of the OPS-8 fix all asked
  the first question. The hole was in the second: a name filter that hid
  tracked files from the PII guard, green all the way through.
- **Measure the metric the DESIGN promises, not the one that is easy.** Three
  sessions optimised the white reader's accuracy over every frame; the design
  promises accuracy over frames it ACCEPTS. Scoring it correctly located the
  real limit immediately.
- **Prefer the cheap sweep that isolates a variable to the plausible story
  about a mechanism.** Two specified next-steps in a row were wrong because both
  were inferred from the shape of a symptom. A guard sweep and a class-mean
  collision found the real cause in minutes.
- **A measured null needs the same evidence as a positive.** "The capture
  cannot supply this" closes an avenue for every later session; one such claim
  was inferred from a neighbouring field and was wrong.
- **Derive an id or a label from BEHAVIOUR, never from shape or from a stored
  order.** Two wrong meter label sets came from a creation-order list that is
  not portable and from reading glyphs by eye. The hit counter settled it.
- **The lane roster is not the only copy of itself.** Editing `ops/lanes.py`
  makes `.claude/commands/lane-*.md` stale and reddens
  `tests/test_lane_contract.py`. Run `python scripts/write_lane_contracts.py`.
- **A document that describes a pattern can match it**, and prose about an id
  ALLOCATES it. Both bit within a minute of each other: a ledger heading saying
  "the bug OPS-9 closed" was counted as a closure, and a worked example with a
  real number in it spent that number. Run the scanner after writing prose
  about the scanner.
- **A new module can violate a rule the repo already closed.** `ops/ops_ids.py`
  was written fence-blind the day after `LL-0038` - the entry about exactly
  that - was read. Grepping the ledger for an id is not reading what it says.
- **Verify a scripted edit by READING the file.** A reused `new` variable wrote
  a ROADMAP paragraph into `.gitignore`, where unprefixed lines are ignore
  PATTERNS. Valid ASCII, no identifier, suite green - uncatchable by any test.
- **A green suite says nothing about a branch no test reaches.** Mutating
  `_is_foreign_probe()` to `return False` left everything green - it was
  decoration. Mutate the thing you just wrote, not only the thing you changed.
- **The fix can set the bug's own trap.** The OPS-8 regression tests used a
  fixed probe path and died on `WinError 32` under concurrency - the bug under
  test, inside the test for it. Nothing sequential could see it.
- **`write_text` on Windows turns a whole file CRLF**, against a
  `.gitattributes` mandating LF. `git diff --stat` hides it because `text=auto`
  normalises the blob. Write with `write_bytes`, and check by counting BYTES:
  `python -c "import pathlib;print(pathlib.Path(F).read_bytes().count(b'
'))"`.
  **Do NOT use `grep -c $''`** - that pattern is empty in this shell and
  matches every line, so it reports the file's line count and measures nothing.
  An earlier version of this very trap recommended it.

## Operator context worth having

Plays **Blackarrow** (classId 12), now **level 5**, second character at classId
13. Right-click is the primary attack (binds swapped). Counts distance in
**paces** - a full stride off the run-cycle animation loop reset, no crouch,
sprint or roll.

**He is the reason the best result of the session exists.** He spotted the stack
icon, then designed and ran the capped-stack experiment himself without being
asked. When he reports a mechanic, capture it and check it - do not explain it
away.

**He cannot read chat while playing.** Use text-to-speech for anything he needs
mid-game, keep it short, and never block waiting for an answer.

Capture evidence from the session is under `C:/ll-captures/2026-08-25b/` and
contains his account name and third-party player ids. **It must never be
committed.**
