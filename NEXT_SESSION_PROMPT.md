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

**Cycle 34 worked item 12 and closed its backward half as IMPOSSIBLE.** The
item asked for the 10.35-per-hit floor to be re-measured on client `1.0.15`.
That can never be done - 10.35 was measured at character **level 3**, the
character has been level 5 since 2026-08-25, and levelling does not reverse.
**Do not re-attempt it.** The data it needed was never missing either: a
`1.0.15` training capture had been on disk since 2026-08-30 and was read. Item
12 stays OPEN under a REPLACED, forward acceptance that needs the client.
**Items 7, 11 and 12 are all open and uncredited.** Full detail in `LL-0110`
and `docs/FINDINGS.md` section 16.

**Suite 1390 passed / 1390 collected, ruff clean**, measured on a clean tree -
that is your merge-gate baseline, and **re-measure it yourself before
dispatching work** rather than trusting this line. **Use
`python -m pytest --collect-only` WITHOUT `-q`**: `pytest.ini` addopts already
carries `-q`, so the form printed in `CLAUDE.md` becomes `-qq` and gives
per-file counts with no total - sum them.

The ledger runs to **`LL-0111`**, 111 entries. **The line above said `LL-0104`
until 2026-09-01c and was five entries stale** - the exact defect `LL-0103`
recorded against these same two hand-off documents. Check the tail of
`docs/LEDGER.md` yourself rather than trusting this number.

Read, in this order:

- **`LL-0110`** - 2026-09-01c, item `12`. The item asked for a re-measurement
  that **cannot ever be performed**: its baseline was character level 3 and the
  character is level 5. The data it needed was on disk the whole time. Its
  acceptance has been REPLACED with a forward one.
- **`LL-0111`** - the correction to `LL-0110`, and read it immediately after.
  A wrong durability shipped in FOUR documents **by the very mistake `LL-0110`
  advertises as caught**, one paragraph away from the block quote explaining
  it, and three of that entry's evidence numbers were measured on an
  intermediate tree and do not reproduce against what shipped. Its rule:
  **re-measure every figure in an acceptance record immediately before writing
  it**, because a wrap edits the tree after the count was taken. And: three
  adversarial passes ran that cycle, but only the third was pointed at the
  COMMITTED tree - **a refutation of a tree that no longer exists certifies
  nothing.**

- **`LL-0100`** - it WITHDRAWS a correction that was itself wrong, about affix
  ids `101` and `209`. Its rule is the most reusable thing on file: **before
  overturning a recorded claim, establish what it was MEASURING.** A measurement
  can be exact and still answer a different question. Two refutation passes
  CONFIRMED the wrong claim because each inherited the framing of the brief it
  was handed.
- **`LL-0104`** - 2026-09-01, item `4d`. Two refutation passes caught a suite
  that had gone RED on the session's own doc prose while the entry already
  claimed it green, a withdrawn headline overclaim, and a cost figure that was
  wrong twice in opposite directions. **A green result expires the moment you
  edit anything, including prose.**
- **`LL-0103`** - the wrap refutation of 2026-08-31. It found that the session
  correcting stale records had itself left both hand-off documents two sessions
  stale, a fifth stale corpus count next to the four it had just fixed, and an
  acceptance criterion parked inside an item the loop had already marked
  completed, where nothing would ever read it.
- **`LL-0101`** and **`LL-0102`** - the 2026-08-31 session. `LL-0101` lists five
  of its own claims that a refutation killed before it landed; `LL-0102` records
  that the watcher armed in `LL-0101` was deliberately stopped.
- **`LL-0097`** through **`LL-0099`** - the 2026-08-30 session, which has no
  wrap entry in `WAKEUP_NOTES.md`. `LL-0097` is the REDISCOVERY failure: a
  roadmap item was opened asking for what had been on disk for three weeks.

**The client is CLOSED.** It was launched at 21:11 on 2026-08-30 and quit 21
seconds later. Nothing has run it since.

**A WATCHER MAY ALREADY BE RUNNING - check, do not assume, and never start a
second.** As of 2026-09-01 07:50:14 local one was armed as pid 17568. Item `4d`
made arming part of starting a session, so the right move is simply:

```
python -c "from ops.loop import watch; print(watch.ensure_armed('C:/ll-captures'))"
```

It reads `ops/runtime/armwatch.json`, checks whether the recorded pid is still
alive, and **refuses on its own** if one is live - two pollers on the same four
sources double the snapshot traffic while `OPS-14` is open. A result reporting
`armed=False` is a refusal, not an error. **Never stop the watcher you find**;
nothing in this project terminates a process it did not start.

**Pass the BASE, never a dated path.** `C:/ll-captures`, not
`C:/ll-captures/<today>`. The watcher derives the local date itself and
retargets at midnight; handing it a literal dated path is the exact defect
`LL-0102` stopped a watcher over.

## Two machine-level things that were repaired, not in this repo

**Ports.** This project's block is **8810-8819** and `CLAUDE.md` carries the
machine-wide registry for all six local projects. `tests/test_ports.py` fails if
a constant lands outside the block. Knowing a neighbour's block is not
permission to talk to it - the standalone rule still holds.

**Two MCP servers were dead and are fixed** (`LL-0077`), both outside this
repository in the plugin cache, both backed up as `.bak-2026-08-29`:

- **github** rejected a hardcoded `Authorization` header with 401. The header
  was removed so OAuth fallback can engage - **but it still needs a human to
  complete the sign-in** when the server next prompts.
- **serena** re-installed itself through `uvx` on every launch and lost a race
  extracting a package. It is now installed once via `uv tool install` and the
  config runs `serena.exe` directly.

## Check the world before anything else

```
tasklist | grep -qi mistfall && echo "CLIENT OPEN" || echo "client closed"; stat -c '%y %s' "$LOCALAPPDATA/MistfallHunter/Saved/Logs/MistfallHunter.log"
```

That is Bash, not PowerShell - `grep` and `stat` do not exist in this repo's
default shell. Run it through the Bash tool.

**Then make sure capture is armed, whatever the answer. One command:**

```
python -c "from ops.loop import watch; print(watch.ensure_armed('C:/ll-captures'))"
```

That is ROADMAP `4c` plus `4d`, both closed. It arms all four surfaces at intervals
argued from measured triggers, and it **refuses a destination inside a git
working directory** rather than trusting you to remember. It watches the
`Logs/` DIRECTORY, not the log file, which is what catches a launch's
`MistfallHunter-backup-<UTC>.log` - so arming at session start recovers the
PREVIOUS session as well as preserving the current one. Whether a launch leaves
a backup at all is **unmeasured**: one did, an entire earlier session had none.

## NEXT: it depends on whether the client is open - CHECK THAT FIRST

**Client CLOSED -> items `4d` and `7` are both done as far as disk allows.**

`4d` is CLOSED (`LL-0104`). Do NOT re-do it: arming is wired into `/loop`,
`/continue` and `docs/HEADLESS.md` 4a, and the destination rolls over per pass.

**Item `7` is NOT credited but route 1 is EXHAUSTED - do not re-run that
search** (`LL-0106`). No non-zero `nameId` exists anywhere: 424 JSON readings
across 353 saves plus 10 events on a third, lowercase-`nameid` log surface found
later. Route 2 needs a SECOND distinct `SkillNameId`; the corpus holds exactly
one, `6130017`, in 139 save generations. Both routes now need fresh gameplay.

**Item `14` is CLOSED** (`LL-0107`) - its premise was refuted. The two bows were
two different cfgIds sharing a display NAME, so the type-to-affix mapping
survives and a rendered name must never be used to identify a type.

**Item `11` is down to `101` and `214`, and BOTH are now blocked from disk.**
`209 = Seeker` and `212 = Fervor` are bound (`LL-0107`, `LL-0108`). The best
affix surface is the `Affix Details` panel, but its only two openings in the
corpus are already read. `101`'s item was never equipped during either, and its
tooltip lasted 262 ms against a 1 fps capture; `214` has no record of any kind.
**Item 11 needs the client now.**

**Item `12` is WORKED and its backward half is CLOSED as impossible**
(`LL-0110`). Do not re-attempt it. The `2026-08-30/frames` set WAS a `1.0.15`
training session - two windows, 355 in-window frames, meter legible in 124 - and
it was read. The display model, the bot and the safe-circle radius all cross the
patch boundary unchanged. **What cannot be done is the comparison itself:** 10.35
was measured at character **level 3**, the character is level 5, and levelling
does not reverse. Item 12's acceptance is now a FORWARD one - capture a `1.0.15`
baseline whose configuration is recorded at the same wall clock as its meter
run - and that needs the client.

**The client-free item is now `7c`**, and it has two concrete measured jobs
waiting in its ROADMAP section: teach `vision_meter` the thousands separator,
because as shipped it **refuses every value at or above 1000** and a long run is
exactly the run that crosses 1000; and record that it fits a full-screen
2560x1440 frame unmodified at crop origin `(2058, 390)`. **Do NOT lower
`MIN_GLYPH_WIDTH`** - that converts a safe refusal into a silent truncation.

**Before ANY configuration question, use the log, not pixels.**
`TS.Dungeon: [DungeonPlayerState]OnCustomInfoReady roleInfo` fires within a
second of every `TrainingGround` `LoadMap` and carries the full equipped set
with affixes, gems and durability, plus talents, class, level and exp. Two
extractor traps, both hit this session: the gem key is **`gem`** singular, and a
**missing `slot` key means slot 0**, the helm.

Historic, kept because the method is reusable: `209` was bound by a DURABILITY
join. Use the **durability join**: item records
carry a durability integer, the tooltip renders it as a percentage of
`900 + (third cfgId digit) * 100`, so a frame matches a log record with NO
wall-clock coincidence. `101` sits on `1430301` at 98% and 100%; `212` on
`1230304` at 94%, 98%, 100%. Prefer a DISTINCTIVE percentage - 100 is shared by
many items and 98 by those two. `214` has no durability record and is
unreachable this way.

**Index every frame-naming convention before filtering.** Enumerated from the
filesystem 2026-09-01c: **18,965 images machine-wide across 28 distinct filename
shapes, of which SIX are timestamped** - `fNNNN_HH.MM.SS` in both `.png` and
`.jpg`, `pNNNNN_HH.MM.SS.mmm`, `sNNNNN_HH.MM.SS` in `.jpg` with and without
milliseconds, and a single `skills_HH.MM.SS.png`. Missing one hid a deciding
frame for a whole pass and produced a figure wrong by 4x.

**`LL-0109`'s "FIVE conventions, 18,680 of 18,747" is correct and SCOPED to
`C:/ll-captures`.** Machine-wide it is 18,898 of 18,965; the 218-frame
difference is `~/.lanternlight/frames`, the 2026-08-09 set, and the sixth
convention lives inside it. Recite that figure with its scope or it reads as a
machine-wide count.

**One surface is left unexplored and its direction is UNSETTLED** - the 10
verbose `nameid` events in `7`. Do not resolve the direction by adjacency; both
readings already have partial support and the line carries no `sourceType`.

Two things `4d` disclosed and did NOT fix, if you want them: the real
detached-spawn helper has no test, and the no-termination guard matches call
NAMES only. Neither is a defect on its own; both are written down in `LL-0104`
because the surrounding prose reads stronger than the guards are.

**Client OPEN -> item 10 below, then 11, 5 and 6.** Item **11** is IN FLIGHT and
uncredited: **TWO affix ids remain, `101` and `214`** - `209 = Seeker` and
`212 = Fervor` were bound 2026-09-01 (`LL-0107`, `LL-0108`).

**The best surface is the `Affix Details` screen, not a tooltip.** It prints a
per-slot count per active affix, and for ARMOUR (`1xxxxxx`) the second cfgId
digit is the equipment slot, so a row attributes to a specific equipped item. **Open it after every
gear change.** For `101`, item `1430301` must be EQUIPPED at the pants slot when
you do - it never was during either panel already on disk. **Capture FASTER as
well as full-screen**: `101`'s tooltip route died to a 262 ms hover against a
1 fps capture, which is a cadence problem, not a resolution one. `214` needs the
Auction House filter with one affix ticked alone.

Still worth doing while equipping: **keep the `Affixes` panel OPEN**. **One
affix per cycle** - a pair yields a set, not an assignment. Items **5 and 6**
pair on one pass over the Sorcerer creation screen; 5's archive route is proven
exhausted.

Also owed the moment the client is open, both one hover each: the **Splatter
Arrow** tooltip (the camp skill grid renders ICONS ONLY, so no capture yields it
unless the operator hovers), and **one** of `Elusive`, `Smiting` or `Curse` to
settle the standing prediction that each has a FIVE-level ladder. **Record the
result either way** - a refutation is worth as much as a confirmation.

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
- **NEVER `git add -A` while a subagent may be writing to the tree.** One
  commit here swept a refuter's live mutation into itself and pushed a red HEAD
  under the message "Docs only. Suite untouched." Stage named paths, or diff
  what is staged against what you intended.
- **A measured null needs the same evidence as a positive.** "The capture
  cannot supply this" closes an avenue for every later session. Two such claims
  were wrong this session - one inferred from a neighbouring field, one from a
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
