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

## Where the last session left it - CYCLE 46

`main` is at the cycle 46 wrap commit. Suite **1757 passed** in 106.36s, run
BARE; ruff clean. Merge gate OK at 1757 against a **1757** baseline - this cycle
changed a docstring and no behaviour, so the count is deliberately flat. Ledger
`LL-0131`. Client **closed**. **`OPS-24` DECLINED.**

**`OPS-24` was declined on a MEASUREMENT, not a shrug.** The only safe
narrowing must treat eleven characters as disqualifying, and the commit MESSAGE
is part of the command string: **39 of this repo's last 40 commit messages
contain at least one of them**, so the narrowing would refuse to apply 97
percent of the time. The reopen condition is written into the item.

## READ THIS BEFORE PICKING AN ITEM

**The ops backlog is now empty apart from `OPS-14`** (disk hit 100 percent
mid-session, recovered with nothing deleted, unexplained). **Nine** ops items
were resolved across cycles 41 to 46: `OPS-17` through `OPS-25`. `OPS-16` closed
in cycle 40 (`LL-0125`) and is NOT part of that run.

**THE HIGHEST-VALUE WORK NEEDS THE CLIENT AND CANNOT BE DONE FROM DISK.** If
the client is closed and `OPS-14` does not appeal, **say so plainly and stop** -
do not invent work to stay busy. That is the loop's own stopping rule.

## Where the last session left it - CYCLE 45

`main` is at the cycle 45 wrap commit. Suite **1757 passed** in 109.39s, run
BARE; ruff clean. Merge gate OK at 1757 against a **1727** baseline measured
BEFORE dispatch. Ledger `LL-0130`. Client **closed**. **`OPS-20` and `OPS-25`
CLOSED.**

## THE FOUR THINGS CYCLE 45 PAID FOR

1. **ASSERT THE ANCHOR ON THE WAY BACK, NOT ONLY ON THE WAY IN.** A restore
   anchor stopped being unique because the mutation had made it ambiguous. The
   `count == 1` assertion caught it; without it a broken `state.py` would have
   been committed under a green suite.

2. **`OPS-25` WAS FILED ONLY AFTER FIRING TWICE.** Cycles 43 and 44 each closed
   two items and recorded one. `state.credit(*items)` is now callable the
   INSTANT an item closes - an argument on the wrap would need the fact carried
   from closure to wrap, which is the gap both losses fell through.
   **Use it: a second closure in one cycle no longer needs a hand repair.**

3. **ONE NON-STRING ID WOULD DESTROY THE WHOLE COMPLETION RECORD.** `load`
   rejects an invalid `completed` wholesale and returns a fresh default -
   measured, `completed=[]` and `cycle=0`. Now type-checked before any read or
   write. Not silent: `load` sets `recovered=True`.

4. **`PROCESS_TERMINATE` IS NOW CAUGHT.** `guard.py`'s access mask was tested
   by nothing while a docstring claimed otherwise. Planting `| 0x0001` used to
   change zero test outcomes; it now reddens.

## Where the last session left it - CYCLE 44

`main` is at the cycle 44 wrap commit. Suite **1727 passed** in 108.09s, run
BARE; ruff clean. Merge gate OK at 1727 against a **1683** baseline measured
BEFORE dispatch. Ledger `LL-0129`. Client **closed**. **`OPS-21` and `OPS-23`
CLOSED.**

## THE FOUR THINGS CYCLE 44 PAID FOR

1. **`OPS-23`'S OWN HYPOTHESIS WAS REFUTED BY MEASUREMENT - the THIRD item in
   four cycles filed with a mechanism that did not hold.** "Alive but creation
   time unreadable means not ours" is FALSE: `process_creation_time` returns
   `None` on every non-Windows platform, for a handle that will not answer, and
   for an unparseable `started` stamp. **The literal fix would have called
   every healthy POSIX watcher an `IMPOSTOR` and started a second poller.** The
   item warned its premise was reasoning, not measurement - **that warning is
   what saved it, so keep writing it into items.**

2. **A FIX FOUND A CRASH PATH IN THE LOOP'S FRONT DOOR.**
   `UnicodeDecodeError` is a `ValueError`, not an `OSError`, so a lock file
   with one stray non-UTF-8 byte RAISED straight out through `read_owner`,
   `is_locked` and `acquire`.

3. **FILED COUNTS WRONG IN FOUR CONSECUTIVE CYCLES.** `OPS-21` said four
   `None` cases; there are five, and it mis-identified which.

4. **CHECK A SLICE'S PARTING CLAIM.** One reported `ruff format` emitting a
   syntax error here. **PEP 758** makes unparenthesized exception groups valid
   in 3.14, which is this repo's floor. Refuted by parsing the output.

## Where the last session left it - CYCLE 43

`main` is at the cycle 43 wrap commit. Suite **1683 passed** in 109.80s, run
BARE at the wrap; ruff clean. Merge gate OK at 1683 collected against a **1647**
baseline measured with `--collect-only` BEFORE any slice was dispatched. Ledger
`LL-0128`. Client **closed** all session. **`OPS-19` and `OPS-22` both CLOSED.**

## THE FOUR THINGS CYCLE 43 PAID FOR

1. **AN ERGONOMIC ITEM WAS A SECURITY ITEM.** `OPS-22` was filed because the
   pre-tool gate blocked MENTIONS of the banned cmdlet. Fixing it revealed the
   old case-SENSITIVE substring test let a **lowercase INVOCATION through
   entirely**, plus the uppercase form, the mixed-case form and the `spps`
   alias - **four false passes in a guard nobody doubted.** Verified over 18
   spellings: 0 regressions, 4 strengthened, 14 unchanged.

2. **A FIX CAN INTRODUCE A HAZARD, AND SAYING SO IS THE JOB.** `OPS-19`'s slice
   found its own fix makes an absent watcher read ARMED when the recorded pid
   is recycled onto an unopenable process, could not repair it from its file
   list, and REPORTED it. Filed as `OPS-23` - a narrow regression shipped
   knowingly, with the reasoning written down.

3. **PROVOKE THE CONDITION IF YOU CAN, rather than only injecting it.**
   `SeDebugPrivilege` dropped with `AdjustTokenPrivileges` and ASSERTED gone,
   then 315 pids swept: 13 real ACCESS_DENIED, all still running half a second
   later, HEAD reading False on 13 of 13.

4. **A HOOK'S PRESENCE IS NEVER PROOF IT FIRES.** The gate was driven END-TO-END
   with real payloads, not only unit-tested.

## Where the last session left it - CYCLE 42

`main` is at the cycle 42 wrap commit. Suite **1647 passed** in 105.24s, run
BARE at the wrap; ruff clean. Merge gate OK at 1647 collected against a **1637**
baseline measured with `--collect-only` BEFORE any slice was dispatched. Ledger
`LL-0127`. Client **closed** all session.

### ROADMAP `OPS-18` is CLOSED

`_windows_pid_is_alive` now reads the EXIT time out of `GetProcessTimes`
instead of comparing `GetExitCodeProcess` against `STILL_ACTIVE` (259), which
is also a legal exit code. Zero until the process exits, a timestamp
afterwards, a different field from the exit code, under the right the module
already held. **No new capability and no allowlist entry.**

## THE FIVE THINGS CYCLE 42 PAID FOR

1. **THE REFUTATION REFUSED THE MERGE, and it was right. Third cycle running
   that it caught what the suite could not.** Three FALSE SENTENCES in the
   shipped `guard.py` docstring - the `OPS-16` failure mode reproduced verbatim
   inside the fix that replaced it. One asserted the exact OPPOSITE of
   `OPS-19`, filed in the same commit. **A docstring written the same hour as
   the code is not exempt from needing evidence.**

2. **THE FAIL-CLOSED PROMISE WAS GUARDED BY NOTHING.** Flipping the
   `GetProcessTimes`-failure branch to fail OPEN left the suite green at 221
   passed, rc=0. Three injected tests now pin it. The branch nobody tested was
   the one carrying the promise the whole module rests on.

3. **A DISTINCT ADJUDICATOR CHANGED THE OUTCOME.** The implementing slice built
   `WaitForSingleObject` and argued it well. It lost on REACH: with
   `SeDebugPrivilege` dropped, **77 of 312 openable pids DENY
   `PQLI | SYNCHRONIZE`**, and every one lands on that design's fallback, which
   is the original buggy comparison verbatim. Its correctness would have been a
   function of the LAUNCHING TOKEN.

4. **A READING IS A CLAIM ABOUT THE INSTRUMENT - this time a PRIVILEGE SET.**
   The first sweep read ZERO denials because this session holds
   `SeDebugPrivilege`, which bypasses the DACL check in `OpenProcess`. Second
   cycle running; last time it was a held handle.

5. **THE PII BACKSTOP FIRED ON THE FIX'S OWN FIXTURE, correctly.** An 18-digit
   `FILETIME` used as test data matched the long-identifier rule. The value was
   arbitrary, so the CONSTANT changed and the rule did not. **Narrowing a
   redaction guard to make a test pass is never available.**

### The defect was real and summonable but was NOT firing

The item claimed otherwise and the claim is withdrawn adjacent to it. A false
ALIVE needs a live handle to the exited process object, and `default_spawn`
drops its `Popen` at `return child.pid`. Nothing here exits 259 either:
`armwatch.main()` returns 0 or 2. Fixed anyway, on the `LL-0124` principle that
a disarmed check fires the cycle after it ships. **The item's consumer count
was also wrong - six claimed, five real - and the first correction of it was
itself loose.**

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

**IF THE CLIENT IS CLOSED**, the only ops item left is `OPS-14`. **If it does
not appeal, the honest answer is that the ops backlog is EMPTY and the
highest-value work needs the client** - say so and stop.

- **`OPS-14`** - this machine's disk hit 100 percent mid-session and recovered
  with nothing deleted. Still open, still unexplained. **It is a QUESTION, not
  a task**, and has no acceptance meetable from disk. Re-measured at the cycle
  46 wrap: `C:/ll-captures` is **9.91 GB across 19,202 files**, up just 0.04 GB
  in five days, while `C:` free fell **161.6 to 134.9 GB**. The captures took
  **0.15 percent** of what the drive lost, so the ruling-out is now a measured
  five-day statement rather than an inference. The slowdown probably tracks the
  client being shut - **hypothesis, not finding**: a silently-stopped watcher
  would look identical, and nobody has joined capture growth to play sessions.


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
`OPS-16` CLOSED (`LL-0125`). `OPS-17` CLOSED (`LL-0126`).
`OPS-18` CLOSED (`LL-0127`).
`OPS-19` and `OPS-22` CLOSED (`LL-0128`).
`OPS-21` and `OPS-23` CLOSED (`LL-0129`).
`OPS-20` and `OPS-25` CLOSED (`LL-0130`).
**`OPS-24` DECLINED and CLOSED (`LL-0131`).**
**Items 7, 11 and 12 remain OPEN and UNCREDITED - do not credit any of them.**

---

## Verification traps that produce FALSE GREENS

- **`python -m pytest -q` prints NO summary line and still exits 0**, because
  `pytest.ini` already carries `-q` so a second one makes it `-qq`. Run it BARE.
- **A filed MECHANISM is a hypothesis, exactly like a filed count.** `OPS-17`
  named the wrong trigger and a fix aimed at it would have changed nothing.
  Re-measure a mechanism before building against it, not just an acceptance.
- **A DOCSTRING WRITTEN THE SAME HOUR AS THE CODE STILL NEEDS EVIDENCE.**
  Cycle 42 shipped three false sentences in a brand-new docstring, one of them
  asserting the opposite of an item filed in the same commit. This is `OPS-16`'s
  lesson and it recurs because a fresh docstring feels verified and is not.
- **A CAVEAT DROPPED FROM THE ARTIFACT IS A LIE IN THE ARTIFACT.** A measured
  "77 of 312" was true only with `SeDebugPrivilege` DROPPED. The roadmap carried
  the condition; the shipped docstring did not.
- **YOUR TOKEN IS PART OF YOUR INSTRUMENT.** A session holding
  `SeDebugPrivilege` bypasses the DACL check in `OpenProcess` and measures ZERO
  access denials, so any process-rights sweep run from here is an artifact
  unless the privilege is explicitly dropped first.
- **The branch carrying a module's central promise is often the one no test
  reaches.** Mutate the FAIL path, not only the success path.
- **`test_no_pii.py` fires on long digit runs, including innocent ones** - an
  18-digit `FILETIME` fixture tripped it. Change the CONSTANT, never the rule.
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
