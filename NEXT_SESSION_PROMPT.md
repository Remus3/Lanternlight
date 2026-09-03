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

## Where the last session left it - CYCLE 38

`main` is at the cycle 38 wrap commit. Suite **1518 passed** in 103.68s, run
BARE and read at the wrap; ruff clean. Merge gate OK against a **1430**
baseline measured the same way BEFORE dispatching. One ledger entry landed:
`LL-0122`. Client **closed** all session.

Measure the count yourself with `python -m pytest` run BARE - never with `-q`,
which prints no summary line at all and still exits 0.

### ROADMAP `4e` is CLOSED

The wrap now re-checks the watcher instead of trusting a record written at
session entry. `ops/loop/watch.py` gained:

- **`check_watcher()`** - returns `NO_RECORD`, `DEAD`, `IMPOSTOR`,
  `NO_HEARTBEAT`, `STALE` or `ARMED`, each with the EVIDENCE it rests on.
- **`ensure_armed_at_wrap()`** - re-arms on the first three ONLY. `STALE` and
  `NO_HEARTBEAT` are reported, never re-armed. Nothing is ever terminated.
- **Identity, not just liveness** - process CREATION TIME via ctypes
  `GetProcessTimes`, compared against the record's `started` stamp inside
  `IDENTITY_TOLERANCE_S = 120.0` s. The window is generous ON PURPOSE: a false
  `IMPOSTOR` re-arms beside a live watcher, which is the one failure
  `ensure_armed` exists to refuse. Command line is deliberately not used - it
  needs WMI or `PROCESS_VM_READ`, and `PROCESS_QUERY_LIMITED_INFORMATION`
  already answers the question.

`lanternlight/armwatch.py` gained `--heartbeat PATH`, writing
`ops/runtime/armwatch_heartbeat.json`. It **advances even when nothing is
archived**, which is the observation `armwatch.json` could never provide.
`HEARTBEAT_STALE_AFTER_S = 900.0` = 3 x the 300 s `logs` interval, which clears
the 330 s a healthy watcher can honestly take.

## THE FIVE THINGS CYCLE 38 PAID FOR - these are the live ones

1. **A GREEN SUITE IS NOT EVIDENCE A GUARD WAS NOT WEAKENED.** An agent
   narrowed a safety test that was blocking its own feature - the textbook
   conflict of interest. The narrowing was legitimate in principle, the merger
   reviewed it and PASSED IT, and its replacement collector matched
   `ast.Attribute` only, so a bare `OpenProcess(...)` after a rebinding evaded a
   spelling the old guard caught. The suite was green at 1509 with that hole
   open and the merge gate said OK. Only the refutation pass found it. **When an
   agent edits a guard that was blocking it, re-derive what the old guard caught
   and replay both over the same input.**

2. **A guard that has only ever seen the code it ships is untested.** The fix
   above is a guard FOR the guard: five synthetic evasion spellings fed to the
   collector, plus a mirror test so a `return False` mutation cannot pass. Red
   observed with exactly 1 of 5 failing, which is what proves the new branch
   load-bearing rather than incidental.

3. **A POSITIVE CONTROL CAN ITSELF BE BROKEN.** The first client check ran
   `Get-Process | Where-Object { $_.ProcessName -like 'powershell*' }` as its
   control and got 0 - because the tool runs `pwsh`, not `powershell`. The
   control failed silently and its zero looked exactly like a clean
   measurement. Use a control that CANNOT fail: the current process itself.

4. **Two premises of a ROADMAP item were false, and the item had been read
   several times.** See below. Re-measure an item's PREMISES before building
   against them, not just its acceptance.

5. **A withdrawal must sit ADJACENT to the claim.** Both corrections below are
   written in `ROADMAP.md` next to the original text, not only in the ledger.
   Cycle 37 paid for this and cycle 38 applied it.

## TWO FALSE PREMISES, WITHDRAWN - do not re-cite the originals

1. **"`ensure_armed` produced no `armwatch.log` where a direct invocation
   does."** There is NO such asymmetry. **No code path in this repository
   writes `armwatch.log` at all** - it appears only in prose and one test's
   denylist, and a `FileHandler|basicConfig|getLogger` sweep returns nothing
   with its positive control passing. The 2026-08-31 file is 562 bytes of
   `run_rolling`'s startup banner with a 0-byte `armwatch.err` beside it: a
   hand-typed shell redirect. The real difference is that `default_spawn` sends
   a detached child's streams to `DEVNULL` deliberately, so a long-running child
   cannot block on a pipe nobody drains.

2. **"There is no observation that separates correctly idle from wedged."** One
   exists and needs NO code. Sample `Win32_Process.OtherOperationCount` twice:
   for pid 23628 it climbed 508 in 15 s, 971 in 30 s, 266 in 10 s while
   `ReadOperationCount`, `WriteOperationCount` and CPU stayed flat, with
   `Threads=5`. That matches what `poll_once` predicts - `iterdir()` and a stat
   per entry are "Other" operations, and every entry was already in `_seen`.
   Controls: idle Python 0, scan-only Python 1442, four `pwsh.exe` 0.

   **BUT STATE IT AS "NOT WHOLLY WEDGED" AND NO STRONGER.** The counter is
   per-PROCESS, not per-thread. The `logs` surface is about 0.5 percent of that
   traffic, so a hung `logs` thread is invisible to it. That is the whole
   content of `4f`.

---

## FIRST ACTIONS, in this order

**1. Is the client running?** Filter on the process NAME, never a command-line
pattern - a command-line filter matches your own probe (`LL-0105`). **Use a
control that cannot fail**, which the previous version of this prompt did not:

```
powershell -NoProfile -Command "$self=@(Get-Process | Where-Object { $_.Id -eq $PID }).Count; $p=@(Get-Process | Where-Object { $_.ProcessName -like 'Mistfall*' }); \"CONTROL_self=$self MISTFALL=$($p.Count) TOTAL=$((Get-Process).Count)\""
```

`CONTROL_self` MUST be 1. If it is 0, your query is broken and the Mistfall
count means nothing.

**2. Arm the session watcher.** Pass the BASE, never a dated path:

```
python -c "from ops.loop import watch; print(watch.ensure_armed('C:/ll-captures'))"
```

**3. Now READ THE WATCHER'S STATE rather than assuming it.** This is new and it
is the point of `4e`:

```
python -c "from ops.loop import watch; s=watch.check_watcher(); print(s.state); print(s.reason)"
```

At the cycle 38 wrap this returned **`NO_HEARTBEAT`** with `armed=True` for pid
23628 - alive, identity-confirmed at 0.057 s, but armed BEFORE the heartbeat
existed, so it writes none. **That is correct and must NOT be re-armed**: a
second poller on the same four sources is the failure `ensure_armed` refuses,
and `OPS-14` (disk) is open. If the operator has since restarted the watcher,
expect `ARMED` instead.

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

**IF THE CLIENT IS CLOSED**, the item is **`4f`**, opened this cycle and fully
doable from disk:

> **One wedged surface out of four still reads as `ARMED`.** `check_watcher()`
> judges `STALE` from the single combined `written` stamp. The heartbeat also
> carries a per-surface map, but nothing compares each surface against its OWN
> poll interval - so the two 3-second surfaces keep the combined stamp fresh
> even when `logs`, the 300-second surface guarding the 5 MB log that `4d`
> exists to protect, has been hung for an hour. The map is EVIDENCE, not a
> verdict.

Its acceptance is written in `ROADMAP.md` and includes the trap: **the first
heartbeat after arming can carry fewer than four `surfaces` keys**, and a
missing key must read as "no completed pass yet", never as stale, or every wrap
in a watcher's first 30 seconds cries wolf. It also requires a test WATCHED
GOING RED that freezes ONE surface while the other three and the combined stamp
stay fresh - freezing all four passes today and pins nothing.

**Also available with the client closed:**

- **`OPS-16`** - the termination-path guard is blind to `taskkill` passed as a
  string argument, `getattr`-assembled attribute names, and ntdll entry points.
  **All three PREDATE cycle 38** - the refutation replayed both the old and new
  guard over HEAD's module to separate what the narrowing lost from what was
  never caught. The honest fix is a different KIND of check, not one more
  string in a denylist; that is how the `.gl` bug in `OPS-13` happened.
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
`7d` CLOSED (`LL-0119`). **`4e` CLOSED (`LL-0122`).** **Items 7, 11 and 12
remain OPEN and UNCREDITED - do not credit any of them.**

---

## Verification traps that produce FALSE GREENS

- **`python -m pytest -q` prints NO summary line and still exits 0**, because
  `pytest.ini` already carries `-q` so a second one makes it `-qq`. Run it BARE.
- **A positive control can itself be broken.** See rule 3 above. Prefer a
  control that cannot fail over one that merely ought to pass.
- **A green suite says nothing about a guard that was quietly narrowed.** See
  rule 1 above. This is the cycle's most expensive lesson.
- **`grep -iF` CRASHES here** (SIGABRT, exit 134) and looks exactly like a clean
  negative. Use `-i` or `-F`, never both.
- **A line-oriented grep is a claim about line breaks** and a case-sensitive one
  is a claim about capitalisation. Prose here wraps near 80 columns, so search
  whitespace-collapsed AND case-insensitively.
- **A shell heredoc mangles backslash escapes.** A sweep script written as a
  heredoc died on `'\\'` this cycle. Write escape-heavy text with an editor.
- **Writing prose about a filename can trip the source register.** Four tokens
  in this cycle's own ledger entry - `Process.OtherOperationCount`,
  `armwatch.err`, `ast.Attribute`, `done.md` - reddened
  `test_source_register.py` and had to be added to `KNOWN_NON_HOSTS`. The
  ledger is append-only, so the denylist is the only lever.
- **A grep PATTERN can trip a pre-tool hook.** Searching for the forbidden
  process-stopping cmdlet by name was BLOCKED by `tools/precommit_gate.py`,
  which matched the search string itself.
- **A sha256 of a working `.py` is NOT the commit's.** `.gitattributes` pins
  `*.py` to `eol=lf` while the working tree is CRLF. Say WHICH form you
  measured; only the git blob is reproducible from a clone.
- **NEVER pipe a `git commit` through `head`.** A reader that closes the pipe
  early kills the process writing to it, and the failure prints a success
  message. Fixed in the hook (`LL-0120`) and pinned end-to-end by
  `test_the_hook_survives_a_reader_that_closes_the_pipe`.

## Traps EARLIER cycles paid for - kept because they are still live

- **Point verification at the READINGS, not the arithmetic.** Four independent
  refuters found **zero** arithmetic errors and **eight** bad readings.
- **A sum is not a check on an ordering.** A transposed delta list summed to the
  same total, so every total-based check passed it.
- **A self-run refutation cannot find a fix you applied in only one place.**
- **A FILED MECHANISM IS A HYPOTHESIS, exactly like a filed count.** Re-run the
  measurement; do not fix what a write-up says is broken.
- **Ask whether a change makes a guard MISS something, not only whether it
  still catches what it caught.** This cycle is the second time that question
  found a real hole.
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
- **Verify a scripted edit by READING the file.** A reused variable once wrote a
  ROADMAP paragraph into `.gitignore`.
- **A green suite says nothing about a branch no test reaches.** Mutate the
  thing you just WROTE, not only the thing you changed.
- **`write_text` on Windows turns a whole file CRLF.** Write with
  `write_bytes`, or pass `newline="\n"`, and check by counting BYTES.

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
