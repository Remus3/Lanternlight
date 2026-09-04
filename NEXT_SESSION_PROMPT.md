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

## Where the last session left it - CYCLE 41

`main` is at the cycle 41 wrap commit. Suite **1637 passed** in 107.04s, run
BARE at the wrap; ruff clean. Merge gate OK at 1637 collected against a **1634**
baseline measured with `--collect-only` BEFORE any slice was dispatched. Ledger
`LL-0126`. Client **closed** all session.

### ROADMAP `OPS-17` is CLOSED

`_dead_pid()` in **both** `tests/test_loop_watch.py` and
`tests/test_loop_guard.py` now appends the reaped `Popen` to a module-level list
and never drops it. A reaped child whose handle is still open is dead AND
unreissuable at the same time, which is the pair of properties the liveness
callers need. **No production code changed.**

## THE FOUR THINGS CYCLE 41 PAID FOR

1. **THE ITEM'S OWN MECHANISM WAS FALSE, and a fix aimed at it would have
   changed NOTHING.** `OPS-17` blamed the `with` block for closing the process
   handle. It does not: `Popen.__exit__` closes the standard streams and calls
   `wait()`, and neither it nor `_wait()` touches the handle. With the block
   exited and the name still bound, the pid was still openable 275 of 275
   times. What frees it is the REFCOUNT drop - and the refcount alone, with no
   collection anywhere, 60 of 60. Withdrawn in `ROADMAP.md` adjacent to the
   claim. **A filed MECHANISM is a hypothesis, exactly like a filed count.**

2. **THE ITEM'S INVENTORY WAS ONE FILE SHORT.** `tests/test_loop_guard.py`
   carried the same helper with the same defect, character for character, and
   the item named only the other file. Found by SWEEPING for the pattern, not
   by reading the item. Same shape as `OPS-16`'s enumerated blind spots: an
   enumerated inventory is a filed count.

3. **A READING IS A CLAIM ABOUT THE INSTRUMENT - INCLUDING THE MERGER'S OWN.**
   The merger's first probe bound `proc._handle` into a local before dropping
   the `Popen`. That kept the OS handle open, so every post-release reading
   said the pid was still reserved, and the opposite conclusion was nearly
   filed. Second cycle running that the merger's own instrument was the broken
   thing.

4. **"pid 16264 reused" WAS AN INFERENCE, NOT A MEASUREMENT.** The assertion
   that reddened was `is None`, which keeps no creation time, so it cannot
   separate a REISSUED pid from a LINGERING process object whose handle a third
   party still held - both make `OpenProcess` succeed. A 300-trial sweep
   measured **7 lingers and 0 reuses**. Withdrawn to "openable". The fix closes
   both, so the item stood; the evidence for its headline did not.

### ONE PID CANNOT SERVE BOTH NEEDS - provable, not awkward

On Windows the single condition "a process object is still referenced" is what
BOTH reserves the pid and keeps `OpenProcess` succeeding, so "cannot be
reissued" and "cannot be opened" are two faces of one thing. The liveness
callers need the first;
`test_process_creation_time_is_none_rather_than_a_guess_when_it_cannot_tell`
needs the second. That test therefore stopped asking for a dead process and
asks for `UNALLOCATABLE_PID = 999_999` - a number NT can never issue - with the
four-byte client-id premise ASSERTED at the point of use, so a machine that
breaks it reddens and names the reason instead of flaking.

**NOT PROVEN, and written down rather than implied:** the pin is a Windows
guarantee and the mechanism test skips elsewhere, and no test asserts that an
UNPINNED pid reads free. That assertion IS the race the item opened for, so
shipping it would be a flake dressed as a guard. It was watched by hand.

## Where the session before that left it - CYCLE 40

`main` was at the cycle 40 wrap. Suite **1634 passed**; merge gate OK against a
**1594** baseline; ledger `LL-0125`.

**`OPS-16` is CLOSED.** `tests/test_process_capability.py` is a capability
ALLOWLIST over the only two modules that can acquire a process handle,
`ops/loop/guard.py` and `ops/loop/watch.py`. It builds a symbol table of what
each bound NAME refers to and routes every access through the same checks -
attribute, literal `getattr`, or bare name from a from-import. No production
code changed.

**THE WORST DEFECT IN IT WAS ITS OWN DOCSTRING.** The first implementation
shipped with 11 undeclared holes and ASSERTED coverage it did not have. A guard
that MIS-states its coverage is worse than one with a hole: a hole honestly
declared is a known limit, a docstring claiming a laundered path is caught is
an active lie a later session will rely on. Every "this is caught" sentence
needs a test behind it.

**Other cycle 40 lessons still live:** hand an agent the METHOD to re-derive an
inventory, not the inventory. An empty result is a claim about the instrument.
The merge gate is not optional cover for the "run only your own tests"
instruction - both slices reported green and the gate reported `2 failed`. A
NEW tracked file needs a lane owner in `ops/lanes.py`, then
`python scripts/write_lane_contracts.py`.

---

## FIRST ACTIONS, in this order

**1. Is the client running?** Filter on the process NAME, never a command-line
pattern - a command-line filter matches your own probe (`LL-0105`). **Use a
control that cannot fail:**

```
powershell -NoProfile -Command "$self=@(Get-Process | Where-Object { $_.Id -eq $PID }).Count; $p=@(Get-Process | Where-Object { $_.ProcessName -like 'Mistfall*' }); \"CONTROL_self=$self MISTFALL=$($p.Count) TOTAL=$((Get-Process).Count)\""
```

`CONTROL_self` MUST be 1. If it is 0, your query is broken and the Mistfall
count means nothing.

**2. Arm the session watcher.** Pass the BASE, never a dated path:

```
python -c "from ops.loop import watch; print(watch.ensure_armed('C:/ll-captures'))"
```

**3. READ THE WATCHER'S STATE rather than assuming it:**

```
python -c "from ops.loop import watch; s=watch.check_watcher(); print(s.state); print(s.reason)"
```

**The live watcher is pid 21452, armed 2026-09-03 into
`C:\ll-captures\2026-09-03`.** At the cycle 41 wrap it read **`ARMED`** with all
four surfaces fresh and 44106 passes reported. Any document naming **23628** is
stale - that one DIED and was replaced (`LL-0124`), and **why it died is still
UNMEASURED and is a real open question.** Nothing in this repo records a
watcher's exit.

What each state means: `ARMED` is fine. `NO_HEARTBEAT` means a watcher armed
before the heartbeat shipped - correct, and it must NOT be re-armed, because a
second poller on the same four sources is the failure `ensure_armed` refuses
while `OPS-14` (disk) is open. `SURFACE_STALE` NAMES the surface that stopped,
so quote the name and not just the state. Only `NO_RECORD`, `DEAD` and
`IMPOSTOR` re-arm, and nothing is ever killed.

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

**IF THE CLIENT IS CLOSED, the item is `OPS-18`**, opened this cycle by the
`OPS-17` refutation and fully doable from disk:

> `ops/loop/guard.py` decides liveness with `GetExitCodeProcess` compared
> against `STILL_ACTIVE`, which is **259**. **259 is also a legal exit code**,
> so a process that exits with 259 is reported **ALIVE**. Measured twice
> independently: exit codes 0, 1, 42, 258 and 260 all read correctly dead;
> **259 read ALIVE 5 of 5.**

It matters because `ensure_armed` refuses to start a watcher while the recorded
pid reads alive, so a watcher that exited with 259 would be believed alive
forever and nothing would archive the log, the saves or the market cache - the
silent outage `LL-0124` caught in production, with the check that caught it
disarmed.

Full acceptance is in `ROADMAP.md`. The important differences from `OPS-17`:
**the symptom is summonable on demand here, so a mechanism-only test is NOT
good enough** - watch it go red against today's `guard.py` first. And the
fail-closed promise in `pid_is_alive`'s docstring must be PRESERVED: when
existence genuinely cannot be determined the answer stays True, or the loop
guard starts trampling live loops, which is a worse bug than the one being
fixed. Whatever call you add must be declared in the `OPS-16` allowlist in
`tests/test_process_capability.py` with the right it asks for argued.

**Also available with the client closed:**

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
`7d` CLOSED (`LL-0119`). `4e` CLOSED (`LL-0122`). `4f` CLOSED (`LL-0123`).
`OPS-16` CLOSED (`LL-0125`). **`OPS-17` CLOSED (`LL-0126`).**
**Items 7, 11 and 12 remain OPEN and UNCREDITED - do not credit any of them.**

---

## Verification traps that produce FALSE GREENS

- **`python -m pytest -q` prints NO summary line and still exits 0**, because
  `pytest.ini` already carries `-q` so a second one makes it `-qq`. Run it BARE.
- **A filed MECHANISM is a hypothesis, exactly like a filed count.** `OPS-17`
  named the wrong trigger and a fix aimed at it would have changed nothing.
  Re-measure a mechanism before building against it, not just an acceptance.
- **An enumerated inventory is a filed count.** `OPS-17` named one file and
  there were two. Sweep for the pattern; do not trust the item's list.
- **Your own probe can be the broken instrument.** Binding `proc._handle` into
  a local kept the OS handle open and faked every reading. Ask what your
  instrument holds open, keeps alive, or shares with the thing it measures.
- **A positive control can itself be broken.** Prefer a control that CANNOT
  fail over one that merely ought to pass.
- **A green suite says nothing about a guard that was quietly narrowed.**
- **`grep -iF` CRASHES here** (SIGABRT, exit 134) and looks exactly like a clean
  negative. Use `-i` or `-F`, never both.
- **A line-oriented grep is a claim about line breaks** and a case-sensitive one
  is a claim about capitalisation. Prose here wraps near 80 columns, so search
  whitespace-collapsed AND case-insensitively.
- **Line endings differ per file in the working tree.** `ROADMAP.md` and
  `WAKEUP_NOTES.md` are CRLF on disk while `NEXT_SESSION_PROMPT.md` and most
  `.py` are LF, and `.gitattributes` normalises everything to LF in the blob. A
  scripted edit whose anchors are LF will silently fail to match a CRLF file -
  **assert the anchor matched before believing a survivor.**
- **A shell heredoc mangles backslash escapes.** Write escape-heavy text - any
  Windows path included - with an editor, not a heredoc.
- **Writing prose about a filename can trip the source register.** The ledger is
  append-only, so `KNOWN_NON_HOSTS` in `test_source_register.py` is the only
  lever.
- **A grep PATTERN can trip a pre-tool hook.** Searching for the forbidden
  process-stopping cmdlet by name was BLOCKED by `tools/precommit_gate.py`,
  which matched the search string itself.
- **A sha256 of a working `.py` is NOT the commit's.** `.gitattributes` pins
  `*.py` to `eol=lf` while some working files are CRLF. Say WHICH form you
  measured; only the git blob is reproducible from a clone.
- **NEVER pipe a `git commit` through `head`.** A reader that closes the pipe
  early kills the process writing to it, and the failure prints a success
  message. Fixed in the hook (`LL-0120`).

## Traps EARLIER cycles paid for - kept because they are still live

- **Point verification at the READINGS, not the arithmetic.** Four independent
  refuters found **zero** arithmetic errors and **eight** bad readings.
- **A sum is not a check on an ordering.**
- **A self-run refutation cannot find a fix you applied in only one place.**
- **Ask whether a change makes a guard MISS something**, not only whether it
  still catches what it caught.
- **Measure the metric the DESIGN promises, not the one that is easy.**
- **NEVER `git add -A` while a subagent may be writing to the tree.** Stage
  named paths.
- **A measured null needs the same evidence as a positive.**
- **Derive an id or a label from BEHAVIOUR, never from shape or a stored order.**
- **The lane roster is not the only copy of itself.** Editing `ops/lanes.py`
  makes `.claude/commands/lane-*.md` stale. Run
  `python scripts/write_lane_contracts.py`.
- **Prose about an id ALLOCATES it.** Ask for an id rather than counting by eye:
  `python -c "from ops import ops_ids; print(ops_ids.next_free_id())"`.
- **Verify a scripted edit by READING the file.**
- **A green suite says nothing about a branch no test reaches.** Mutate the
  thing you just WROTE, not only the thing you changed.
- **`write_text` on Windows turns a whole file CRLF.** Write with
  `write_bytes`, or pass an explicit `newline=`, and check by counting BYTES.

## Operator context worth having

Plays **Blackarrow** (classId 12), now **level 5**, second character at classId
13. Right-click is the primary attack (binds swapped). Counts distance in
**paces** - a full stride off the run-cycle animation loop reset.

**He is the reason the best result of cycle 37 exists.** He spotted the stack
icon, then designed and ran the capped-stack experiment himself without being
asked. When he reports a mechanic, capture it and check it - do not explain it
away.

**He cannot read chat while playing.** Use text-to-speech for anything he needs
mid-game, keep it short, and never block waiting for an answer.

Capture evidence from earlier sessions is under `C:/ll-captures/2026-08-25b/`
and contains his account name and third-party player ids. **It must never be
committed.**

## Item 10 - the stack buff, measured AT THE CEILING - STILL THE HIGHEST-VALUE OPEN QUESTION

**An existing headline finding may be an artifact.** The operator found a buff
icon that climbs to **5** while he keeps hitting the same target inside a time
limit, centre screen above the energy bar, readable in a half-scale wide shot at
`x 600-690, y 600-665`. Joining that crop to the meter crop on wall clock puts
stack count and cumulative damage on one row.

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

## GROUND TRUTH for the meter work

`C:/ll-captures/2026-08-30/meter_transcription_cycle34.csv`, sha256
`973a3f58...`, 124 panel-up rows, digit-length tally 20/7/42/55, 231 panel-down,
and 1,817 out-of-window frames - all swept, producing zero readings, so 124 is a
TOTAL and not a floor.
