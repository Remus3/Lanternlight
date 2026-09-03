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
## Where the last session left it - CYCLE 37

`main` is at the cycle 37 wrap commit; run `git log --oneline -5` to see it.
Suite **1430 passed**, ruff clean, **29** test files. Measure the count
yourself with `python -m pytest` run BARE - never with `-q`, which prints no
summary line at all and still exits 0.

**Four ledger entries landed:** `LL-0118`, `LL-0119`, `LL-0120`, `LL-0121`.

1. **`LL-0118` - ROADMAP `7c`'s registration search is DONE, as CONSENSUS.**
   `lanternlight.vision_meter` gained `read_frame`, which crops a full 2560x1440
   frame at every row in `FRAME_CONSENSUS_ROWS` (388-392, x FIXED at 2058) and
   requires the readings to AGREE. A conflict REFUSES rather than being broken
   in favour of the best-scoring row, so it is a NEW guard rather than a relaxed
   one. **118 read at the single row, 120 by consensus**, recovering exactly the
   `f0469`/`f0470` the item named, with 0 lost, 0 misread, 0 disagreements.

2. **`LL-0119` - ROADMAP `7d` CLOSED.** `_read_field` never checked that ink
   stopped before `x_hi`, so a glyph pushed entirely outside a field window was
   dropped in silence and the survivors formed a valid number - a WRONG NUMBER,
   not a refusal. `EDGE_LOOKAHEAD` (8) now scans outside the window on both
   sides and refuses, naming the pushed side.

3. **`LL-0120` - the ASCII pre-commit hook could be DEFEATED by piping the
   commit.** `git commit ... 2>&1 | head -1` killed the hook with SIGPIPE; git
   exited 141 and **the banned commit LANDED** while the word BLOCKED still
   printed. Fixed with `trap '' PIPE`, pinned by an end-to-end test.

4. **`LL-0121` - the wrap, which CORRECTED eleven claims** including one of
   `LL-0119`'s own numbers.

---

## The five rules cycle 37 paid for - these are the live ones

1. **A correction that is not SWEPT FOR is a correction in one place.**
   `LL-0119` declared the tidy-guard count of 78 wrong and corrected it to 8 -
   and the same commit left "78 real frames" standing in a third file. Two of
   three sites were fixed because only two were looked at. After correcting a
   number, grep the whole tree for the literal old value.

2. **A withdrawal that is not ADJACENT to the claim does not reach the reader
   who finds the claim.** The module docstring was corrected to say the x band
   "2056-2061" was wrong at both ends, while `FRAME_PANEL_X`'s own comment
   **610 lines below in the same file** still advertised that band as fact. The
   same stale band was live in the test file and in ROADMAP too.

3. **The BEFORE figure and the AFTER figure must be measured over the same
   population.** `LL-0119` published "30 wrong readings" from three crop
   offsets and paired it with an after-figure of zero swept over the whole
   2046-2070 range. Over that range the pre-guard total is **108**, and the
   omitted offsets include **2046, the worst at 69** - more than twice the
   published figure. This is `LL-0116`'s shape, in the session whose own ledger
   claims to have learned it.

4. **A claim can be true when written and false one commit later.** ROADMAP's
   `7c` closure said every function in `read_panel`'s call graph compiles to
   identical bytecode. That was exact for `LL-0118`; `LL-0119` then changed
   `_read_field` itself, an hour later in the same session, and nothing
   re-checked the earlier item.

5. **LIVENESS IS NOT FUNCTION.** `LL-0117` closed "the recorded watcher pid is
   dead". The next gap: at this wrap pid 23628 was alive AND identity-confirmed
   and had archived **nothing** in 24 hours. That is correct with the client
   closed and **indistinguishable from a wedged process** - no heartbeat is
   written, `armwatch.json` is never touched after arming, and the instance
   armed through `ensure_armed` produced no `armwatch.log` where a direct
   invocation does. Recorded as extra acceptance on ROADMAP `4e`.

---

## FIRST ACTIONS, in this order

**1. Is the client running?** Filter on the process NAME, never a command-line
pattern - a command-line filter matches your own probe (`LL-0105`). Include a
positive control so a zero is a measurement rather than a broken query:

```
powershell -NoProfile -Command "$p=@(Get-Process | Where-Object { $_.ProcessName -like 'Mistfall*' }); \"MATCH=$($p.Count)\""
```

**2. Arm the session watcher.** Pass the BASE, never a dated path:

```
python -c "from ops.loop import watch; print(watch.ensure_armed('C:/ll-captures'))"
```

**3. VERIFY THE PID IS ALIVE AND IS ACTUALLY THE WATCHER.** A refusal to re-arm
is only as good as the process it deferred to (`LL-0117`), and a pid can be
recycled. Check liveness, the command line (it must name
`lanternlight.armwatch`), and the start time against `ops/runtime/armwatch.json`.
Then read rule 5 above: none of that proves it is still polling.

---

## NEXT - it depends on whether the client is open

**IF THE CLIENT IS OPEN**, item **10** supersedes everything, then item `12`'s
FORWARD baseline, then `11` and `4b`. **Do NOT re-attempt item 12's backward
comparison: CLOSED as impossible** (`LL-0110`). For affix `101`: equip `1430301`
at PANTS and open Affix Details while worn - grep the log for
`WBP_EquipSkill_DetailPrompt` first.

**Still owed, one hover each:** the Splatter Arrow tooltip, and ONE of Elusive,
Smiting or Curse. The log carries no player-facing affix, skill or item name -
33 names tested with two positive controls - so only a hover will do.

**IF THE CLIENT IS CLOSED**, the item is **`4e`** - re-check the watcher's
liveness AND identity at the WRAP as well as at entry, plus the heartbeat gap in
rule 5. It is fully doable from disk and it has bitten twice now. Read the whole
of `4e` in `ROADMAP.md`; its acceptance is written there, including that a live
pid which is NOT the watcher must read as NOT armed, and a test watched going
RED.

**Also available with the client closed**, both recorded with acceptance in
`ROADMAP.md`:

- **`7d`'s per-edge lookahead.** The ceiling of 19 is priced entirely by
  value-left, which carries 11 columns of slack at the shipped 8, while `hits` -
  zero right margin, the likeliest place for a pushed glyph - is nowhere near
  the bound. Declined as four constants to drift instead of one; the acceptance
  for taking it up is in `7d`.
- **`7c`'s WHITE Progress Record row**, still blocked on a capture with longer
  stable stretches per record value across at least ten distinct records. That
  is blocked on DATA, not on a session.

**OPERATOR DECISION PENDING:** a four-digit committed fixture needs explicit
approval before capture-derived pixels enter this public repo (`LL-0083`).

---

## DO NOT RE-DO

Item `7` route 1 EXHAUSTED (`LL-0106`). Item `14` CLOSED (`LL-0107`). `4d`
CLOSED (`LL-0109`). Item `12`'s backward half CLOSED as impossible (`LL-0110`).
`7c`'s orange pair DONE (`LL-0112`), its two defence-in-depth gaps CLOSED
(`LL-0115`/`0116`), and its registration search DONE as consensus (`LL-0118`).
`7d` CLOSED (`LL-0119`). **Items 7, 11 and 12 remain OPEN and UNCREDITED - do
not credit any of them.**

---

## Verification traps that produce FALSE GREENS

- **`python -m pytest -q` prints NO summary line and still exits 0**, because
  `pytest.ini` already carries `-q` so a second makes it `-qq`. Run it BARE.
- **A sha256 of a working `.py` is NOT the commit's.** `.gitattributes` pins
  `*.py` to `eol=lf` while the working tree is CRLF. Say WHICH form you measured;
  only the git blob is reproducible from a clone.
- **`grep -iF` CRASHES here** (SIGABRT, exit 134) and looks exactly like a clean
  negative. Use `-i` or `-F`, never both.
- **A line-oriented grep is a claim about line breaks** and a case-sensitive one
  is a claim about capitalisation. Prose here wraps near 80 columns, so search
  whitespace-collapsed AND case-insensitively.
- **NEVER pipe a `git commit` through `head`.** Fixed in the hook this cycle, but
  the general lesson stands: a reader that closes the pipe early can kill the
  process writing to it, and the failure prints a success message.
- **Five instruments reported falsely in cycle 37 alone**, each caught only by a
  second method: `grep -c` seeing 0 carriage returns in a file with 602; `cmp`
  flagging a CRLF-vs-LF artifact as a content change; a `co_consts` comparison
  flagging five unchanged functions because nested code objects compare by
  identity; a hand-rolled PII control whose planted identifier went to
  `C:/Program Files/Git/` because Git Bash maps a leading `/` to the Git root;
  and the commit-pipe above. **An empty or passing result is a claim about the
  INSTRUMENT.**

---

## GROUND TRUTH for the meter work

`C:/ll-captures/2026-08-30/meter_transcription_cycle34.csv`, sha256
`973a3f58...`, 124 panel-up rows, digit-length tally 20/7/42/55, 231 panel-down,
and 1,817 out-of-window frames - the last of which were ALL swept this cycle and
produce zero readings, so 124 is a TOTAL and not a floor.

---

## Item 10 - the stack buff, measured AT THE CEILING

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

**7c's orange pair is DONE** (`LL-0112`); only the WHITE row is left. The white Progress Record pair is **blocked on a new capture** - and the
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

## Traps EARLIER cycles paid for - kept because they are still live

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
- **NEVER `git add -A` while a subagent may be writing to the tree.** One
  commit here swept a refuter's live mutation into itself and pushed a red HEAD
  under the message "Docs only. Suite untouched." Stage named paths, or diff
  what is staged against what you intended.
- **A measured null needs the same evidence as a positive.** "The capture
  cannot supply this" closes an avenue for every later session. Two such claims
  were wrong in the cycle that recorded them - one inferred from a neighbouring field, one from a
  scan that sampled every third frame and missed the run it was looking for.
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
  normalises the blob. Write with `write_bytes`, and check by counting BYTES -
  read the file and count occurrences of the two-byte sequence \r\n.
  **Do NOT use grep with a \r escape as the pattern** - that pattern is
  empty in this shell, matches every line, and reports the file's line count
  while measuring nothing. An earlier version of this very trap recommended it,
  and the edit that fixed it mangled its own escapes and left a stray CR byte in
  this file. Write escape-heavy text with an editor, not a shell heredoc.

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
