# Wakeup notes

Session hand-off. Newest session first. Keep the last two or three at full
fidelity and archive older ones rather than deleting them.

---

# Session 2026-08-27b - OPS-7 closed, the loop stops crediting work nobody did

Client **closed**. Suite **1282 passed / 1282 collected**, ruff clean, clean
tree with `__pycache__` purged. Baseline 1277. Ledger `LL-0070`.

## What shipped

`advance_cycle` no longer credits an item that was merely carried forward.
**Carrying an item forward is a retry**: `X -> X` credits nothing, whatever
`complete_current` says. Only `X -> Y` or `X -> None` says `X` is finished, and
`complete_current=False` stays as the hatch for "abandoned while moving away".

It had been hit three times - `LL-0048`, then twice more while wrapping the two
sessions before this one, both worked around by hand. A workaround that only
works because the operator knows about it is how a defect becomes permanent,
and this one silently tells a cold session to skip an item. There is no
operation that un-completes anything.

`docs/HEADLESS.md` step 8 and `.claude/commands/loop.md` step 8 now state the
rule at the point a session actually calls the function.

## Two habits worth keeping

**The negative controls did the real work.** Three of the five new tests pin the
ordinary cases, and they are what stops the cheap wrong fix - a change that
simply stopped crediting anything satisfies the acceptance and destroys the
record instead.

**A clause of my own fix was inert.** The first version read
`item is not None and item == current.item`; mutating that guard away killed no
test, because `None -> None` is already blocked by `current.item` being falsy.
Deleted rather than kept with a confident comment on it. Verify your own
defensive code with the same mutation discipline as the thing it guards.

## A limit of the OPS-12 guard, observed live

Flipping OPS-7's heading from OPEN to CLOSED briefly made `over_allocated()`
read `[8]` alone, because a CLOSED heading nets against its single closure. The
collision is not resolved - OPS-7 still names two items - and the count is right
again now `LL-0070` announces the second closure. **The reading is transiently
wrong DURING an edit**, between closing a heading and writing the entry that
closes it. Harmless at commit time; do not be alarmed mid-edit.

---

# Session 2026-08-27 - OPS-12 closed, the OPS- namespace has an allocator

Client **closed** again, so this is the fallback item worked end to end. No
capture, no game data touched.

**Suite 1277 passed / 1277 collected**, ruff clean, clean tree with
`__pycache__` purged. Baseline was 1253. Ledger `LL-0068` and `LL-0069`.

## What shipped

`ops/ops_ids.py`. The `OPS-` namespace had no allocator - unlike `LL-` ids,
which `ops/loop/ledger.py` hands out and collision-checks. Now:

```
python -c "from ops import ops_ids; print(ops_ids.next_free_id())"
```

It walks `ROADMAP.md` and `docs/LEDGER.md` at run time and **nothing is checked
in** - a stored list of spent ids was explicitly ruled out by the acceptance,
because it goes stale the first time an item is added without touching it.

**Allocation is counted at two sites only**, since an id appears in prose
constantly and prose is not allocation: a `## OPS-<n>.` roadmap heading, and a
ledger entry heading announcing a closure. A CLOSED heading is read as the same
item as its closure, so the normal lifecycle does not read as a collision:

```
allocations = closures + open_headings + max(0, closed_headings - closures)
```

## The half that matters most

The known-collision set fails **in both directions**. Planting a reuse of
`OPS-9` in the real roadmap went red (`found: [7, 8, 9]`); renumbering the open
`OPS-7` to simulate a repair went red too (`found: [8]`). An exemption that
silently outlives the defect it excuses is how a guard rots.

**The count deliberately under-reports rather than over-reports.** `OPS-4` was
closed by an entry whose heading avoids the word "closed", so it scores 0 and a
second `OPS-4` would slip through. That is the chosen trade: over-reporting
makes the guard red on correct items, and a guard that cries wolf gets
overridden - the same argument OPS-8 made about the merge gate.

## The refutation found a repeat offence

`ops/ops_ids.py` shipped fence-blind: it did its own line matching, so a worked
example inside a code block reads as a live heading. **This repository had
already closed that exact bug** - `OPS-9` / `LL-0038`, whose conclusion was that
there must be one fence scan every reader shares. The new module was a third
private reader, written the day after that ledger entry was read.

Fixed by extracting `ops/mdscan.py` and pointing both `lane_state` and
`ops_ids` at it, deleting `lane_state`'s duplicate copy rather than leaving it.
`test_lane_state.py`'s 29 existing fence assertions pass unchanged, which is
what makes it a refactor rather than a rewrite.

**Then dogfooding found two more that no refuter did.** This session's own
ledger heading says "the same bug OPS-9 closed, rebuilt" - a sentence, not a
closure - and the guard counted it, reporting `[7, 8, 9]`. The closure pattern
is now anchored to the convention every real closure follows. And writing a
worked example with a real number in it **spends that number**: documenting the
fence fix burned an id and pushed `next_free_id` past it. Write examples with a
placeholder. That correction had to be made twice, because the first draft
documented the problem by quoting the offending number.

## Two things that cost time

- **The roster is not the only copy of itself.** Adding `tests/test_ops_ids.py`
  to `ops/lanes.py` made `.claude/commands/lane-ops.md` stale and
  `tests/test_lane_contract.py` went red. Fix is
  `python scripts/write_lane_contracts.py`.
- **A document that describes a pattern can match it.** The OPS-12 closure text
  quotes the `## OPS-<n>.` heading form the scanner looks for. Re-derived after
  writing it - still exactly `{7, 8}`, because the mentions sit mid-line. Check
  this, do not assume it; `LL-0038` is the entry about a parser that ignored its
  own document's structure.

---

# Session 2026-08-26b - OPS-8 closed, and the filed mechanism was wrong

Client was **closed** all session, so this is the fallback item from the
hand-off, worked end to end. No capture, no game data touched.

**Suite 1253 passed / 1253 collected**, ruff clean, measured on a clean tree
with `__pycache__` purged. Baseline was 1244. Ledger entries `LL-0066` and
`LL-0067` - **read `LL-0067`**, it records a PII hole the OPS-8 fix itself
opened and an independent refuter caught.

## What shipped - OPS-8 is CLOSED

The suite is now safe to run concurrently: **24 consecutive green runs at 6-way
concurrency of the full suite**, against a **measured 9-of-10-red baseline**.
That matters because `ops/merge_gate.py` re-runs pytest and CLAUDE.md mandates
a parallel multi-agent workflow, so the gate could redden for reasons unrelated
to the work it gates.

Guard probes are now `_guard_probe_<pid>_<stem>`, still planted at the real
repository root. `.gitignore` ignores the prefix, which is **one lever for all
three** git-based walkers in this repo, and `tests/_tracked.py` adds this
process's own probes back so a probe is still scanned by the guard that planted
it.

## Read this before trusting the next filed mechanism

**The mechanism OPS-8 recorded was wrong about the dominant case**, and
re-measuring before fixing is the only reason that surfaced. Neither of the two
tests it named as casualties failed even once in the baseline. The real failure
is a **shared probe PATH** - two suites planting the same file, the first to
reach its `finally` unlinking the other's evidence mid-scan.

**The fix set the same trap for itself.** The first regression tests named their
foreign probe `_guard_probe_0_...`, a fixed path, reasoning that pid 0 is never
a live process. Six concurrent suites fought over that one file and it died on
`WinError 32`: 17 of 18 green, red for exactly the bug under test, inside the
test for it. Nothing sequential could have seen it.

**The fix opened a PII hole, and only an out-of-domain pass saw it.**
`_is_foreign_probe()` filtered by NAME across the whole candidate list -
**tracked files included** - so a file committed as `docs/_guard_probe_notes.md`
carrying a SteamID64 went GREEN through the repository-wide guard.
`.githooks/pre-commit` does no content scan either. OPS-8 was a guard going red
for the wrong reason; its fix made a guard go **green** for the wrong reason,
which is strictly worse. Three self-run mutations missed it because every one
asked "does this still catch what it caught" and none asked "does this now MISS
something it used to catch". Fixed: the filter applies only on the non-git
fallback walk.

**A mutation that survived is the other thing worth carrying.**
`_is_foreign_probe()` returning `False` left the whole suite green - the
fallback filter was decoration, because every test ran on the git path where
`.gitignore` had already removed the file. Green tests said nothing about it.
Only mutating found it, and a test was written for it.

**And the CRLF trap was re-paid.** Python `write_text` turned all five edited
files fully CRLF against a `.gitattributes` that mandates LF. `git diff --stat`
hid it, because `text=auto` normalises the blob. Only `grep -c` for CR showed
it. CLAUDE.md names this trap and it still landed.

**A scripted edit wrote prose into `.gitignore` as ignore PATTERNS.** A
variable named `new` was reused across blocks, so when the first anchor matched,
a ROADMAP paragraph replaced a comment - with no leading `#`, so git would have
read each line as a pattern. Nothing in the suite could catch it: valid ASCII,
no identifier, all green. Only the verifying grep coming back empty exposed it.
Verify a scripted edit by reading the file, not by trusting the assert.

## New open item - OPS-12, two ops ids each name two items

`OPS-7` and `OPS-8` were **each allocated twice**. Both were spent on items
closed 2026-08-12 (`LL-0039`, `LL-0040`) and both reallocated later. Numbering
resumed from the highest OPEN id rather than the highest ever allocated.
Renumbering is refused on `LL-0040`'s own reasoning, so all four references are
signposted and `OPS-12` carries the acceptance: allocating a spent `OPS-` id
must fail a test, with the spent set derived by walking the documents at run
time rather than from a checked-in list.

## Still open, unchanged

**ROADMAP 10 - the stack buff, measured AT THE CEILING - is still the
highest-value item and still needs the client.** Nothing this session touched
it. Everything the previous hand-off says about it stands.

---

# Session 2026-08-25/26 - the operator played all session, and found the mechanic himself

The first session where the operator was in the client the whole time, and the
best result of the night came from him rather than from the analysis.

**Suite 1244 passed / 1244 collected, ruff clean**, measured on a clean tree
with `__pycache__` purged. Baseline was 1225; the +19 is `tests/test_armwatch.py`.
Ledger entries start at `LL-0056`. **Read `LL-0064` FIRST** - it is the
independent refutation pass and it overturns things the entries before it claim.

## What shipped

- **ROADMAP 4c is CLOSED.** `lanternlight/armwatch.py` arms all four capture
  surfaces from one entry point: `python -m lanternlight.armwatch --dest-root
  C:/ll-captures/<day>`. It reimplements no copying. Intervals carry their
  rationale as a FIELD, and a test asserts each cites a digit.
- **`FINDINGS` 11.8's "keeps no backup" is REFUTED.** A launch was watched
  directly and it left a byte-identical `MistfallHunter-backup-<UTC>.log`. It is
  NOT guaranteed - an entire earlier session had none - so archive regardless.
  **Watch the `Logs/` DIRECTORY, never the log file**; that is what catches it.

## What was learned, and it is mostly negative

- **A full dungeon run wrote NO transient save.** `StandaloneLevel` occurs zero
  times in its log. So a dungeon run is NOT a guarantee of damage data and item
  7's source is mode-dependent. **Whether a patch or the mode causes it is
  CONFOUNDED** - every prior sighting was on buildid 24619162, this run on
  24813185.
- **Equipment is SERVER-SIDE.** `Deck.sav` and `CampData` are byte-identical
  across an item change. A loadout can only be baselined in pixels.
- **The stack buff (ROADMAP 10) is the biggest thread.** It may make 11.7's
  "constancy tracks the clamp" an artifact. Measure it at the CEILING; the floor
  is insensitive because the increment rounds away.

## Capture was pruned at the operator's request - 4.5 GB to 3.0 GB

Recorded here because this project's expensive lesson is deleted evidence, and
the precedent set when `frames/` was removed is **downsample, keep a record,
then delete, and write down what was lost.** Same method here.

**Provably lossless, 220 MB.** 76 superseded log generations. The game APPENDS
within a session, and every deleted generation was verified a strict **byte
prefix** of the one that supersedes it, re-checked at the moment of deletion.
One of two byte-identical backup copies also went. **A `MANIFEST.txt` stays in
each `logs/` directory** listing every original name, size, sha256 and mtime -
because `LL-0056`'s measured negative is "N generations at these timestamps and
not one a `*-backup-*.log`", and that claim lives in the LISTING, not the bytes.

**`2026-08-25/panel2/` overlap, 278 MB.** `panel/` and `panel2/` were two
simultaneous pollers on the same HUD rectangle. `panel/` runs to 19:51:31 and
`panel2/` starts 19:34:50, so 1,775 frames were duplicated. Near-simultaneous
pairs were compared first and showed identical meter content. **`panel/` was
the copy kept, because ROADMAP 7c names that exact path as its ground truth.**
`panel2/`'s unique window after 19:51:31 is untouched.

**`2026-08-25b/reanchor/` downsampled, 1,084 MB.** 320 full-screen 2560x1440
PNGs at ~3.1 MB became `reanchor_small/panel` (meter crops) plus
`reanchor_small/wide` (half-scale JPEGs) - **all 320 frames, both streams**.
Spot-checked afterwards: `143`/`10 Hit`, `129`/`9`, `42`/`3` and `28`/`2` are
all still legible in the crops, which are the four readings FINDINGS 13 rests
on.

**24 frames were kept at FULL resolution** - every visually distinct equipment
view: the inventory grid, several item tooltips with their stat text, the Affix
Details screen and the character panel. They were kept because **equipment is
server-side** (13.1), so those frames are the only record anywhere of the
loadout that produced that run. A near-duplicate filter chose them; the
threshold erred toward keeping.

**What a future session can no longer do:** re-crop the reanchor capture at a
different rectangle, or read equipment text from a frame that was not among the
24. Everything published from that capture is preserved. The old capture-tree
listing further down this file describes the pre-prune shape.

## The lesson worth carrying

Four independent refuters found **zero arithmetic errors** and **eight bad
readings**. Every defect was a misread frame, an invented explanation for a gap
that did not exist, a circular citation, or a binding read off an error line.
**Verification effort had been pointed at the arithmetic, which was already
sound.** Point it at the readings.

And `LL-0058` claimed to have fixed an over-claim in two places; it fixed two
and missed a third in the same commit. A self-run refutation cannot see that.

---

# Session 2026-08-25 - the client was open, and 7b turned into a measurement rig

The first session in four with the game actually running, so ROADMAP 7b was the
work exactly as the hand-off said it should be. **1225 tests at the start and
1225 at the end**, ruff clean, measured on a clean tree with `__pycache__`
purged. No code changed - this session was measurement and documentation, so
the count is unchanged by design and a merge gate baseline of 1225 is correct.

The session's ledger entries start at `LL-0049`; `grep -n '^### LL-00'
docs/LEDGER.md | head` lists them, and no end-point is filed here because that
literal went stale twice in one session, and a third occasion was avoided only
because the same commit that would have staled it removed it instead. The
session's commits run from
`9ac4b1b`
to the wrap - `git log --oneline 9ac4b1b~1..HEAD` lists them, and no count is
filed here on purpose: the first draft of this line said "six", the second said
"fifteen", and both were wrong. Count it if you need it.

## Check the world before anything else - it had moved three ways

1. **The game was patched.** buildid `24619162` -> `24813185`, 2026-08-19.
   Every id in `docs/OBSERVED_IDS.md` was read on a build that no longer
   exists, and the file now says so at the top.
2. **The 6.1 MB log from 2026-08-09 is gone.** The game truncates its log on
   launch. **"and keeps no backup" was refuted the next session** - a launch
   watched directly left a byte-identical `MistfallHunter-backup-<UTC>.log`,
   though no backup existed at any point during this one, so it is a windfall
   and not a mechanism. `docs/FINDINGS.md` 11.8 and 11.12, ROADMAP 4c.
   `lanternlight/savewatch.py` already solves this - point it at `Logs/` and at
   `Saved/` and the log plus the market cache archive themselves. That is also
   item 4's remaining acceptance, met by shipped code.
3. **`AvgPrice_937566.ini` is back to 37 bytes**, its empty state. It had
   filled to 343. Nothing watched it empty.

## ROADMAP 7b is ANSWERED, and two of its three answers are negatives

- **(a) The training ground exists.** `/Game/Project/Maps/TrainingGround/
  Training`, `DA_DungeonSettings_Training`, `BP_Adventure_Bot_C`.
- **(b) `DamageCollectonDataSet` is NOT written there.** No
  `StandaloneSlot_<roleId>.sav` for the whole 36-minute session across roughly
  200 shots, against 17 seconds to appear in a real dungeon. Empty
  `StandaloneLevel/`, no `EnterBattle`, and seven occurrences of "damage" in
  the entire log, **none carrying a number**. `lanternlight/damage.py` has
  nothing to read in that room. **The rig is a PIXEL rig.**
- **(c) Body yes, head no.** See below.

## The measurement method, which is the reusable part

The room renders a cumulative **Total Damage** meter - a running total and a
hit count - and writes it nowhere. Differencing it across frames gives per-hit
damage. `Progress Record` beneath it holds the **previous run's** pair, not a
best; the meter resets per run, which makes a run a self-delimiting window.

**Solve, do not eyeball.** A constant per-hit value ALWAYS makes the displayed
deltas wobble by one, because the meter rounds a real-valued cumulative sum. So
a wobbling delta is not evidence of variance. Solving `round(n*v) == total_n`
across a ten-hit run either yields an interval or is contradictory, and only
the contradiction is evidence.

**The body value is 10.35 and it is exact.** Three runs at the long range gave
the same series, and the one hit that ever disagreed - 104 against 103 on the
tenth - is the ONLY cumulative in the series that lands on an exact .5 tie.
Searching every two- and three-decimal value that fits all three runs with ties
free returns exactly one candidate. First number in this project to clear the
independent-run bar. Corroborated as a PROPERTY by the transient save, whose
`damageValue` is a float.

**Headshots never yield a constant**, not even at the range where body shots
are perfectly constant. Head totals reproduce (123 twice, 817 against 818,
122/123/123 earlier) while individual hits do not. A headshot is not a body
shot times a number.

## The live mistake, and it is the most useful thing here

Both sweeps produced **seven** completed runs. Distances were assigned to the
body runs **by clock order** and committed. The operator then labelled the head
runs and listed **six**, starting `123 = 10 paces` - implying an uncounted run
first. If the body sweep also opened with one, every run shifts by one and the
**damage floor disappears**.

`docs/FINDINGS.md` 11.10 lays out both mappings and the evidence on both sides.
**RESOLVED before hand-off, by re-running rather than arguing.** A wide-shot
poller was armed and the operator redid only the ambiguous pair - ten body hits
at 10 paces, reset, ten at 8. **Both read 104.** The floor is real and the
committed mapping was right. 11.11 records how, including a measurement that
failed twice and is written up as failed.

**Every total in both sweeps is exact. What broke was the LABEL**, and it broke
silently because clock order looked like an obvious ordering and nobody had
said that it was. A measurement whose independent variable was inferred rather
than recorded is not a measurement of that variable, and it reads exactly like
one.

## Capture economics, measured

- Full-screen PNG at 2 fps: **4.8 MB a frame, 34 GB an hour**, on a disk with
  52 GB free. Do not leave that running.
- Cropping the HUD rectangle at capture time: ~150 KB a frame, 20x less, and it
  lost nothing this measurement used.
- Half-scale JPEG wide shot at 1 fps: ~140 KB a frame, and it is what records
  where the operator was standing.
- Deduping panel frames by pixel hash **fails** - the plate is semi-transparent
  so the scene behind it changes the hash while the number stands still. A
  coarse column-occupancy signature is what works.
- Tesseract is not installed. ROADMAP 7c is the template-matching reader, and
  its acceptance insists it REFUSE rather than guess.

**Where this session's evidence actually is**, since none of it is in the repo
and nothing in the repo said so:

```
C:/ll-captures/2026-08-25/
  panel/  panel2/     HUD crops at 2 fps - every number came from these
  scene/              half-scale wide shots at 1 fps - where the operator stood
  scene_early/        half-scale sample of 18:40:30-18:55:30, every 42nd frame
  logs/               MistfallHunter.log snapshotted every 5 minutes
  savegames/  saved-root/   every changed generation of every save
  sheets/             the contact sheets the numbers were read off
```

About **2.5 GB** in total, outside every checkout on purpose - these contain
the operator's account name and third-party player ids and must never be
committed.

**A `frames/` directory was deleted at the operator's request** - 1026
full-resolution PNGs at 4.8 GB, covering 18:40:30 to 18:55:30. Everything the
measurements used had already been extracted from it into `sheets/`, and the
disk was at 96%. Before deleting, every 42nd frame was kept as a half-scale
JPEG in `scene_early/` - 25 frames, 4 MB - because that window is the **only**
wide-scene record of the runs that first produced 10.35, fired before a pace
was defined and before the wide-shot poller existed. Nothing published depends
on it; the floor value was independently confirmed later by the labelled 10, 9
and 8-pace runs. But if anyone ever wants to know where the operator was
standing for those early runs, `scene_early/` is now the only place to look,
and it is a sample rather than a record.

## The finished curve

Ten distances, ten body hits each. Ledger `LL-0051`, **and every entry after it
corrects something - read the whole block, newest first, rather than any one
entry.**

**How each label was actually established, since two earlier drafts of this
paragraph got it wrong:**

- **Two** distances, the 10 and 8-pace pair, had their label fixed by protocol
  **before** firing - that is the deliberate re-run in `docs/FINDINGS.md` 11.11.
- **Eight** labels were assigned by clock order from the order the operator
  named the runs. The 9, 7, 3 and 1-pace ones are forced by monotonicity and
  that check is written out in 11.6; the 6, 4, 2 and 0-pace ones come from the
  original sweep, whose mapping 11.11 settled.
- **Six** runs - 10, 9, 8, 7, 3 and 1 paces - were fired while the wide-shot
  poller was running, so the operator's position is on film for them. The other
  four predate the poller, which started at 19:32:34; those runs were fired
  between 19:14 and 19:16.
- **No distance was ever read off the wide shot.** The attempt to turn apparent
  size into a number saturated twice and is written up as failed in 11.11.
  Having the position on film is not a recorded label; it is a re-checkable
  record that a human can settle a dispute against, which is what it was used
  for.

| paces | 10 | 9 | 8 | 7 | 6 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| total | 104 | 104 | 104 | 231 | 309 | 546 | 687 | 687 | 689 | 691 |

Three regimes: a clamped floor at 104 - per hit exactly **10.35**, the solved
interval being `[10.3500, 10.3571]` at all three floor distances - a slope of
about **1.3x per pace** across four consecutive paces, and a clamped ceiling
spanning 3 through 0 paces at 0.6% spread. **Ceiling is 6.64x the floor.** The floor boundary is between 8 and
7 paces and it is a **step** - extrapolating the slope outward predicts ~174 at
8 paces and it reads 104.

**Constancy belongs to the clamp, not to flatness.** Every floor run admits a
constant per-hit value; no other run does, including all four ceiling runs
whose totals agree to 0.6% while their hits do not.

## Next

Read ROADMAP 7b's open threads first - both breakpoints are now located, so
what remains there is the step-versus-tangent question, the headshot mechanism,
and whether the ~1.3x per pace is real. If the client is open,
those are all cheap. If it is not, ROADMAP 4c and 7c are both unblocked and
need nothing but work.

---

# Session 2026-08-13a - a correct conclusion resting on a false reason

Small session, one item, no new feature. Ledger `LL-0048`. **1223 tests at the
start, 1225 at the end**, ruff clean, both measured on a clean tree with
`__pycache__` purged; `ops.merge_gate.verify` OK against baseline 1223.

**What was wrong.** `LL-0047` published an enumeration to justify its claim that
CDKEY idempotence is over-determined: "`<PRODUCTUSERID>` at 15 characters is the
only placeholder clearing the floor". **Four clear it** - `<USER_UNIQUE_ID>`
(16), `<PRODUCTUSERID>` (15), `<ACCOUNT_NAME>` (14), `<OWNER_ROLEID>` (14). The
sentence was copied into **four** artifacts and was false in every one, and it
was false the day it was written.

**Why it survived three sessions.** All four are digit-free, so the minimum
blocker count really is 2 and the safety conclusion really does hold. **A true
conclusion resting on a false reason is indistinguishable from a sound one by
reading.** Nothing could have caught this, because prose has no failure mode.

**The fix.** The recital is replaced by a derivation -
`test_no_placeholder_rests_on_a_single_cdkey_condition` takes `_CDKEY_VALUE`
apart by surgery on the live pattern string and counts independent blockers for
every placeholder any rule collection can emit. It kills the class-widening
mutation the older test survives.

**Three things this session got wrong before getting right,** all caught by
mutation or by the wrap refutation, none by review:

1. The first draft of the fix **hard-coded the assumption it was testing**
   ("the class excludes `<`") instead of reading the pattern - so the
   class-widening mutation survived the fix too. Isolating each condition with
   the other two relaxed is what fixed it.
2. Two mutation counts were filed from a **`-k` filtered run** into a document
   whose convention is full-suite. Re-measured: 1 -> 4 and 2 -> 6. **A count
   without its scope is a wrong count.**
3. The derivation read `RULES` alone; `redact()` also applies `LOG_TEXT_RULES`.
   No live gap today, but a future log-text-only placeholder would have escaped
   the guard. It now scans all three collections.

**The habit to carry, sharpened:** `LL-0047` said to run the mutation before
committing a sentence of the form "X is what prevents Y". That is necessary and
not sufficient - this defect was **a list of identifiers**, not a causal claim.
If you type an enumeration into a comment, derive it in a test instead.

---

# Session 2026-08-12h - the cdkey hole shut, and a guard that was never pinned

Three slices on disjoint files plus two independent refutation passes, merged
to `main` and **pushed** - `main` is `e956942`. Ledger `LL-0046` and `LL-0047`.
**1196 tests at the start, 1223 at the end**, ruff clean, both measured by the
integrator on a clean tree with `__pycache__` purged. `ops.merge_gate.verify`:
OK.

**The wrap refutation confirmed all six claims and then found three defects**,
closed in `LL-0047`: dead regex in `_CDKEY_VALUE`, a comment crediting the
wrong condition, and an anchor test with no unique kill. See the section at the
end of this entry - the way the second one was fixed is the most useful thing
here.

**Process failure, on the record:** `LL-0046` was merged and pushed **before**
that refutation returned a verdict, on the operator's explicit instruction. It
came back CONFIRMED so nothing unsafe landed, but the merge was unreviewed at
the moment it happened. The pass also noted that at `43693b3` the roadmap still
read `READY` and no ledger entry existed - **"item 9 CLOSED" was never a
property of the commit that was merged**; the docs landed separately.

**Checked first, as the hand-off said to:** the game was NOT running - log mtime
2026-08-09 18:03:53, 74 hours stale, no process. So item 7b was not startable
and **ROADMAP item 9** was the work.

## Item 9 is CLOSED, and three of its four surfaces were already closed

The real hole was one surface, not four. Measured first-party before touching
anything:

| surface | filed as | measured |
|---|---|---|
| `cdkey` | 9 tokens, 0 masked | **5** tokens, 0 masked - a real hole |
| `device_id` / `user_unique_id` | needs a token-level check | 19-digit runs, **0 of 202** and **0 of 198** survive |
| `OnRep_PlayStateTag` player name | open hazard, third-party names | **0 of 20** survive, non-ASCII one included |
| `/Game/` anchor test | to be written | already existed - and did **not** pin the anchor |

After the fix: **0 of 5** survive, `assert_clean` refuses all five
token-bearing raw lines, **0 firings across 118 tracked files**, idempotent on
the whole 12.8 MB log.

## The sharpest finding: an existing test that looked exactly right

`test_a_non_game_url_with_a_query_is_not_a_map_url` shipped in `LL-0045` and
reads like the test item 9 asked for. Mutation-probed, it **survived three of
five** weakenings - dropping the trailing slash, truncating to `/G`, and
widening the character class - because the committed stand-in used a
**lowercase** path, so the only things pinned were case and a leading `/G`. Not
a leak on today's log (all three still match the same 36 lines), but the
comment beside it claimed more than the test delivered. Four cases added, each
with a **positive twin** one character or one word away. All five now killed.

**The mechanism was also misdescribed.** `MapUrl.target` stops dead at the
`?`, so no `MapUrl` field would ever hold the key or the token - they ride in
the embedded `LogLine.raw` and `.message`. The hazard is a whole extra event on
a secrets-bearing line, not a poisoned field. A test now pins that.

## Three corrections that are worth more than the feature

1. **A slice's own mutation refuted its own reasoning.** It wrote that the
   digit requirement kept the CDKEY rule off prose. Dropping the digit left the
   tree scan **green** - the length floor is what stops today's words. But
   "configuration", "documentation" and "implementation" all clear the floor,
   so the digit is load-bearing for a case the corpus does not happen to
   contain. Those words are now in the tests. **A guard that is green only
   because the corpus is kind is not proven.**
2. **A slice inferred a live game from a size reading - second session
   running.** It reported the log had grown and the game was up. **12,899,997
   raw BYTES decode to 12,867,803 CHARACTERS**; the 32,194 difference is the
   multi-byte UTF-8 `SAF-4` already documents. Byte counts and character counts
   are different quantities on this log because it is not ASCII. Believed, it
   would have started 7b against a game that is not running.
3. **The integrator measured a moving tree and got two answers** - 1222 passed,
   then 5 failed minutes later, because a slice was mid-mutation with
   `re.IGNORECASE` spliced into the anchor. Last session's rule about freezing a
   ref before a refutation **applies to the integrator's own measurements too**.
   The filed numbers were taken against a clean tree matching the commit.

Also: I handed a slice a number I had not checked - the URL credential is
**304** characters, not the 122 I said. It was already masked, so the point
survived, but an unverified number given to an agent as ground truth is worse
than none.

## The 9-versus-5 reconciliation

The filed 9 came from a probe reading the ordinary word after a **CamelCase**
mention of the key as a value: 5 real tokens plus 4 innocent neighbouring
words. There are **4 positions and 5 occurrences**, so the acceptance's own
wording "all 9 observed positions" was wrong on its face. One of the 7 matching
lines is a false positive - a three-letter fragment inside binary garbage,
which is why the abbreviation is deliberately not a key.

## A fourth encoding, measured and clean

Percent-encoding is not one of the three the module claims to reach. Measured:
3 runs, **0** hiding a persona, and percent-decoding a **redacted** log brings
back **0 of 12** personas. n=3 - a fact about this capture, not the encoding.
No rule added; a guard built on three runs is decoration.

## Three wrong answers in a row, each refuted by its own mutation

The single most useful thing this session produced, and it is a reasoning
failure rather than a result. Asked what keeps the `CDKEY` rule off a CamelCase
mention of the key:

| claim written | mutation run | outcome |
|---|---|---|
| the `\b` word boundary does | delete both boundaries | suite **green** |
| no - the separator does | make the separator optional | suite **green** |
| then the two together | remove **both** at once | suite **still green** |

The real answer is the **value shape**: the token after such a mention is
`Gift`, four characters with no digit, nowhere near the floor. All three
conditions block it independently.

Every one of those comments would have shipped as confident prose explaining a
mechanism that does not exist. **And the first attempt at fixing this shipped a
decoration comment while fixing a decoration comment** - it claimed widening
the value class would redden the placeholder test; that mutation was run and
**survived**. Writing the claim and then testing it is what caught it.

The same over-determination turned out to hold for idempotence: measured
against every placeholder `RULES` can emit, each is blocked by at least two of
the class, the digit requirement and the floor, so **no single edit exposes any
of them**.

**That paragraph used to end with a false sentence** - "`<PRODUCTUSERID>` at 15
characters is the only one long enough to clear the floor". Four clear it, and
`LL-0048` corrects it in all four places it was written. The conclusion above
survived because all four are digit-free, which is exactly what makes it worth
recording: a true conclusion resting on a false reason reads identically to a
sound one. The enumeration is now DERIVED from `RULES` in
`test_no_placeholder_rests_on_a_single_cdkey_condition` rather than recited, and
that derived test kills the class-widening mutation the older test survived.

**The habit worth carrying:** when you write "X is what prevents Y", run the
mutation that removes X before you commit the sentence. In this module that
sentence has now been wrong five times in three sessions - and the fifth was a
list of facts rather than a causal claim, so the habit has to extend to
enumerations too. If you catch yourself typing a list of identifiers into a
comment, derive it in a test instead.

## Where to start next

**Check whether the game is running first.** If it is, **item 7b**, the
training ground - still the only route to **outgoing** damage in quantity, and
`sourceType: 0` is what to look for. Fold in items 1, 4b, 5 and 6.

If it is not, **item 4's `AvgPrice` watcher**. There is no open safety item any
more; `lanes/safety.STATE.json` is entirely blocked on a candidate fixture.

Do **not** label any damage number dealt or taken beyond the 21 proven TAKEN,
and publish **no** coefficient until a value repeats in an independent run.

One operator decision remains, deliberately unanswered: **OPS-6** - retire the
global `LL-NNNN` id space for per-lane namespacing.

---

# Session 2026-08-12g - the log tail shipped, and the refutation refused the merge

Two parallel slices on disjoint files, one independent refutation pass, merged
to `main` and **pushed** - `main` is `1890c40`. Ledger `LL-0045`. **1108 tests
at the start, 1196 at the end**, ruff clean, both measured by the integrator
with `__pycache__` purged.

ROADMAP **item 3 is CLOSED**. `lanternlight/tail.py` follows the log with 49
tests; `logparse` gained five recognisers. Port 8811 is still reserved and
**unbound** - the acceptance asked for a library and nothing binds a socket.

## The refutation pass returned "not safe to merge as-is", and it was right

Both blocking defects were invisible to a green suite.

- **`iter_events` RAISED `ValueError`** on a digit run over 4300, breaking a
  contract the module docstring and one of the slice's own tests both assert.
  Six sites: three new, one in the header's own `frame` group so the input
  reached `parse_line` before any recogniser, and **one PRE-EXISTING on `main`**
  via `_eqeq_fields`. **`main` had been violating its own never-raise promise
  and nobody had noticed.** `_as_int` is now the only integer conversion in the
  module - never add a bare `int()` there again (`ING-15`).
- **The `/Game/` anchor was decoration.** Relaxing it keeps the suite green
  while admitting a `LogUGiftAgent` redemption URL - carrying a cdkey and an
  access-token parameter - into an event payload. Now pinned.

## The integrator was wrong three times, and each is on the record

1. **"8 distinct shapes" was a method artifact.** Collapsing per digit
   CHARACTER counts id WIDTHS, not shapes. Per-run gives **4**; the slice was
   right and I refuted it twice with the same broken method - which is the
   "two measurements sharing one bug agree" trap, with me on both sides.
2. **"101299 lines refuted" was wrong.** 101198 LF + 101 lone CR = **101299** =
   exactly `readlines()` in text mode. Three methods give 101199, 101299 and
   101893 on the same bytes. The slice's *inference* that the log grows live is
   still wrong - size and mtime were identical all session.
3. **"zero personas in URL query strings" came from too narrow a filter** -
   it required `/Game/` or `http`, missing the producer that logs a query string
   alone. Broader: **72 lines, 26 carrying a persona.** An empty grep is a claim
   about your pattern.

## A merger verification was itself VACUOUS, caught by its own counter

The first probe of the tailer's redaction reported **0 personas surviving while
emitting 0 EVENTS**. Only printing the event count revealed it. Re-run with a
positive control - 4 fed, 4 emitted, 4 personas in the raw text, 0 surviving -
the property holds.

But naive per-line redaction **also** scores 0 on those four, and the tailer
learned **0** personas doing it. So the accumulation design is **correct but
not yet load-bearing on this log**; it is kept because the leaking shape exists
and any new recogniser makes it reachable, and the docstring says exactly that.

## Three mutant survivors exposed WEAK TESTS, not weak code - one of them mine

Writing my own control-character finding into a docstring produced a documented
property with **nothing behind it** until it was pinned. A note in a docstring
is not a guard.

## Measured, and none of it was in any plan

- **`st_ino` is PRESERVED across in-place truncation and CHANGES on
  delete-and-recreate.** So identity alone cannot see a truncation and size
  alone cannot see replacement by a larger file. Both checks are load-bearing.
- **The log carries 594 embedded control characters** (98 VT, 106 FF, 113 FS,
  85 GS, 97 RS, 95 NEL). **`bytes.splitlines()` does NOT split on them; only
  `str.splitlines()` does** - I stated this as a `splitlines()` hazard and was
  corrected by measurement. The hazard is the **decode-then-split ORDER**. The
  first mutant, written against the method name, **survived**. And the event
  COUNT does not catch the real mutation - the first shard keeps a complete
  header and still parses - only the exact text does.
- **`MapTransitionEvent` was pointed at the wrong lines all along.** All
  **4408** `at world` lines are `TS.UI` widgets; it matched **0** of the 44 real
  `[LevelSwitch]` map changes. Not renamed - public API, separate decision - but
  its docstring now says outright that it is not a transition. One user-visible
  map change emits **four** `LevelSwitchEvent`s.

## NEW: ROADMAP item 9, a safety hole the guard approves

**`cdkey` tokens survive `redact()` 9 of 9, and `assert_clean` CERTIFIES the
line.** Same vacuous-guard shape as item 0 and `LL-0029` - the third time in
this project. Also there: a player-name parameter on **20** lines including
**third-party** players (one non-ASCII), and `device_id` / `user_unique_id`
needing a token-level rather than a line-changed check.

**Nothing leaked. No raw excerpt is committed. What is broken is the
protection.** Drafting the item tripped `tests/test_no_pii.py` **twice** on my
own prose - the guard working exactly as designed. The prose was rewritten both
times and the guard was not touched.

## Where to start next

**Check whether the game is running first** - the log's mtime plus a process
check settles it in one command. If it is, **item 7b**, the training ground,
and fold in items 1, 4b, 5 and 6. If it is not, **item 9** (the cdkey hole,
safety lane, holds a veto) or **item 4's watcher**, the cheaper of the two.

Do **not** label any damage number dealt or taken beyond the 21 proven TAKEN,
and publish **no** coefficient until a value repeats in an independent run.

One operator decision remains, deliberately unanswered: **OPS-6** - retire the
global `LL-NNNN` id space for per-lane namespacing.

---

# Session 2026-08-12 - a clone finally runs green, and a P0 in the machinery that guards the record

Branch work on `lane/ops` and `session/2026-08-12-damage-extractor`, both
merged to `main` and **pushed** - `main` is `0d919c0`, and all nine branches are
on the remote. Ledger `LL-0033` through `LL-0035`. **953 tests at the start,
1009 at the end**, ruff clean. The outgoing diff scanned **0** identifiers
through `lanternlight.redact` with a positive control firing 5 on the same text.

## The headline is not a feature, it is that every count before today was a lie

**ROADMAP 2d is closed.** `ops/lane_contract.py` interpolated
`primary_checkout()` and `worktree_path()` - both absolute - into text that is
then **committed**, and the drift guard compares the committed file against a
fresh render. So the two agreed only at `C:\Lanternlight`. A real clone at
`311cef8` measured **1 failed, 952 passed**; at the fix, **957 passed**.

`README.md` told contributors to clone and run pytest, so the documented
first-run experience was a red suite. **1009 is the first number in this
project's history measured from a fresh clone at a foreign path.**

Of the two options the acceptance allowed, the second - "the test compares
modulo the root" - was **refused** with a reason: it goes green while leaving
`C:\Lanternlight` inside eight generated files in a public repo, and weakens
the drift guard into "equal after an arbitrary substitution".

**A second, independent trigger was found and closed too**, and it was in
nobody's plan: `worktree_path()` does not derive from the checkout, so setting
`LL_WORKTREE_ROOT` reddened the suite **in place**, where every other symptom
of this item was invisible. The item was filed as path-dependence on the
checkout; it was path-dependence on **any** absolute path the generator saw.
The new guards are therefore behavioural - render must not change when the
checkout moves, or when the worktree root moves - which catches a path
re-embedded later that nobody has thought of yet.

## The two refutation passes disagreed with each other, which is the point

Both were run against a frozen `814b1ea`, on slices that had shipped with none.

**2b came back CONFIRMED on all eight claims** - the 882/96/21 positive
control reproduced exactly, all 15 detectors fire when injected, no dead
detector, and the LL-0029 P0 fix verified across all 263 generations. Safe as
shipped. Its four new defects are non-blocking; the sharpest is that the
fixture builder's documented provenance is **ambiguous** - four captures are
177,878 bytes and three of them rebuild differently.

**2c came back with a P0.** `_HEADING_RE` wants exactly `###`, one space, a
non-space id, then `" - "`. Miss it by **one character** and the entry does not
fail loudly, it becomes **invisible**: `fragment_entry_ids` `[]`,
`duplicate_claims` `[]`, `integrate` `[]`, ledger unchanged, entry gone.

**That is the LL-0031 silent-data-loss defect verbatim, through a different
door, in the machinery closed to prevent exactly it.** 2c shut the door and
left the window open. Reproduced by the integrator before any fix, on a
throwaway copy of the real ledger with a genuinely colliding `LL-0018`. Fixed
as `LL-0034`.

Three of `LL-0031`'s own claims are corrected rather than edited away: the "11
ids" count was **wrong when written** (13 today), two normaliser branches are
**dead code** because `read_text` translates newlines before any comparison,
and a real false positive exists - editing an entry **after** it is integrated
makes it differ from its fragment forever, so `integrate` raises and the live
test stays red. That last was recorded as `OPS-8`, with the open question being
whether the right answer is a policy that an integrated entry is simply never
edited. It was **closed later the same session** - and the answer was yes; see
the ops-queue sweep below.

## The fix shipped a silent bug first, and the shape is the lesson

A heredoc collapsed the backslashes in the new `_ID_TOKEN_RE`, turning `\b`
into a literal **backspace byte**. The regex compiled without complaint and
matched **nothing**, so the brand-new guard was entirely dead while the module
imported cleanly. Only the still-failing tests caught it.

That is the second heredoc backslash mangling in one session - the first
aborted a mutation probe on its anchor assertion, which is the only reason it
did not read as "the guard is vacuous". **Do not use a heredoc for anything
containing a backslash.** Write the script to a file.

## Item 7 shipped, and the wall-clock join found the real result

`lanternlight/damage.py`, owned by ingest, 37 tests, `LL-0035`.

**The save's `timeStamp` is NOT a Unix epoch. It encodes LOCAL wall clock as
though it were UTC.** Confirmed on two independent surfaces:

- capture file **mtimes** put the run at 22:27:00-22:46:54 UTC, while the hits
  read as an epoch render 17:28:10-17:45:11 "UTC" - five hours *before* the run
  began, and numerically equal to its **local** clock
- the **log**, which timestamps in real UTC and emits the same payload: across
  5 readings at **three separate times of day**, the delta is 18009-18015 s =
  5.0025-5.0041 h, the operator's offset plus event-to-emission lag

So `as_local_naive()` returns a **naive** datetime and `to_utc()` **raises**
without an explicit offset. The offset belongs to the machine that played, is
absent from the save, and moves with DST - guessing it shifts every hit by
hours. A test pins the *wrong* reading too, so "it lands in the window" is not
vacuous.

Verified end to end: the shipped module over all 263 captures reproduces the
scratch analysis exactly, and the joined first and last hits land inside the
mtime-measured window.

**Two filed counts in ROADMAP 7 were wrong and are corrected.** It carried
*both* "278 window readings" and "0 on all 424 readings" for one quantity -
278 is top-level entries, 424 is child hits, and the dedup key is child-level,
so the deduped-from number is **424**. A test encoding "278 deduped to 21"
would have frozen a wrong intermediate. Also: **262** generations carry the
field, not 263 - the first, 2,190 bytes and pre-combat, does not carry it at
all, so absence stays distinguishable from zero on this surface.

## The wrap's own refutation pass holed the P0 fix, and that is the best result of the day

A third pass ran at wrap time over this session's own three done-claims. It
**confirmed 2d and item 7** - re-deriving the damage figures with its own reader
and proving the log prefix is really UTC non-circularly, by comparing the last
log stamp against its own file mtime. It returned **`LL-0034` as PARTIAL**:
"it should not be recorded as closing the silent-entry-loss class."

It was right, and the hole it found is **worse than the bug `LL-0034` fixed**.

**One forgotten backtick disarmed the entire guard.** The fence state was a bare
toggle, so an entry that opened a code fence and never closed it left every line
below it counted as code, and the guard stood down for the rest of the file:

    integrate() -> ['LL-0900']   NON-EMPTY, so it reads as SUCCESS
    LL-0901 landed as its own entry: False
    LL-0901 text swallowed into LL-0900's block: True
    exception: none

The original defect at least returned `[]`, which looks anomalous. This returns
**success** while absorbing a whole entry into its neighbour.

Three more, all the same mistake - **guarding the instance instead of the
class**:

- the id pattern was `[A-Z]{2,6}-\d{3,}`, i.e. *today's* ids, so a malformed
  heading in any other shape fell through into silence. **`OPS-7` and
  `SAF-0001` both sit outside it and both exist here.**
- 2d's guards pinned `primary_checkout()` and `WORKTREE_ROOT` specifically, so
  embedding `Path.home()` gave **1009 passed** on this machine with
  `C:\Users\Administrator` committed into a contract - and `1 failed` under a
  different `USERPROFILE`. The 2d symptom, invisible here.
- an undecodable property read as **absence**, because `gvas.parse` omits it
  from `.properties` and records it in `.unknown_properties`.

All four closed, 12 failing tests first, six mutants all red, **1030 passed**.

**A filed count was wrong for the fourth time in two sessions** - "46 lines
below the marker" was 47 then 51. It grows with every entry, so *filing it* was
the error. It is now quoted nowhere.

**`OPS-9`** - the heading **guard** respected code fences, the heading **parser**
did not, so a well-formed heading inside a code block was parsed as a real entry
while a malformed one beside it was ignored. Found because a test failed for a
reason its author had not predicted. **Closed later the same session** - see the
ops-queue sweep below.

## The ops queue was swept to empty, and every fix found a bigger hole beside it

Seven open `OPS-*` items went to **one**. Ledger `LL-0038` through `LL-0042`.
The pattern held in every single one: **the filed item undersold the defect,
and mutation testing - not reading - found the rest.**

- **`OPS-9`** - guard and parser disagreed about fences. Fixing the two readers
  in the item exposed a **third** (`fragment_entry_ids` had its own
  `finditer`). `_HEADING_RE` is now referenced in exactly one place.
- **`OPS-7`** - filed as "the error message should name the mistake". A
  surviving mutant showed an **existing but unreadable** fragment read as
  *absent*, which was not in the item at all.
- **`OPS-8`** - the decision it asked for is **taken: policy stands.** An
  integrated entry is never edited; a correction is a NEW entry.
  Auto-reconciliation was refused because it would write to an append-only
  fragment. What was actually broken was the **diagnosis** - it told the reader
  to *renumber*, which for an edited entry records one piece of work under two
  ids.
- **`OPS-2`** - neither option the item offered removed the friction, so a
  third was built: a lane **claims** a path in its own `STATE.json`, the orphan
  guard honours exactly one claimant, and the claim goes **stale** once the
  roster absorbs it. The guard's claim branch was itself unpinned at first -
  the real repo has no claimed path, so deleting the branch left the suite
  green.
- **`OPS-1`, `OPS-3`, `OPS-5`** - the visibility guard was checking **4 of 7**
  writing lanes and reporting green, because it skipped any path not yet on
  disk. Now it asks git about the **rule** (`lanes.git_would_take`). The
  documented `check-ignore` trap was re-measured rather than trusted: it exits
  **0 on a negation**, so the exit code is not the answer - the pattern's
  leading `!` is. And `ops/loop/ledger.py`, the only sanctioned writer of the
  ledger, finally has its own 27 tests.

**The sharpest single lesson of the sweep, and it was in my own tests.** The
first version of the visibility tests **skipped** whenever the probe returned
None - so breaking the probe turned every test in the class from a failure into
a SKIP. The mutation run read `1094 passed, 7 skipped`, which looks green. A
guard that stands down when the thing it guards breaks is not a guard.
Availability is now measured independently with `git --version`.

**Only `OPS-6` is left, and it is yours:** retire the global `LL-NNNN` id space
for per-lane namespacing. It changes what 42 entries and every citing commit
refer to, so it is not a call to make unattended.

## Where to start next

**Item 7b, the training ground** - the cheapest unblocker on the list and the
only route to **outgoing** damage in quantity. `sourceType: 0` is what to look
for. Needs the client open, so fold it into whichever session has it running,
along with items 1, 4b, 5 and 6.

Otherwise **item 3, the live log tail** - fully specified, needs nothing but
work, and it is the spine of every live feature.

Do **not** label any damage number dealt or taken beyond the 21 already proven
TAKEN, and publish **no** coefficient until the same value appears in an
independent run.

One operator decision remains, deliberately unanswered: **OPS-6** - retire
the global `LL-NNNN` id space for per-lane namespacing. **OPS-8 was closed**
later in the same session; see the ops-queue sweep above.

---

# Session 2026-08-11 - the fixture landed, and the roadmap was wrong about Emberforge

Orchestrated and multi-agent throughout: three lanes in parallel worktrees, an
adversarial pass, and a P0 fix. Branch `session/2026-08-11-standalone-fixture`,
**merged to `main` at the operator's instruction** - `main` is `ea01e95`.
Ledger `LL-0023` through `LL-0030`. 807 tests at the start, **943** at the end,
green in place, ruff clean. Public `main` scans zero identifiers across all 113
blobs.

## The thing that mattered most was not the item being worked on

ROADMAP 2b closed - the sanitised fixture exists and scans **0** findings where
its source scans **882**. But the session's real result came from an aside: the
operator handed over a YouTube transcript and two map sites to review, and
chasing one claim into the save turned up `DamageCollectonDataSet`.

**The game has been writing per-hit damage all along.** Float `damageValue`,
Unix timestamps to sub-millisecond, attributed to a monster. 263 generations
were already captured on disk from 2026-08-09. This file's own "deliberately
not on this list" section said Emberforge could not be filled because no
numbers existed. It was wrong for two days, and nobody had read the field.

## And then the adversarial pass took half of it back

Dispatched against a frozen ref, which is the lesson from last session. It
returned five corrections to claims made **earlier the same session**:

- **Direction settled, and it deflates the headline.** `PlayerData.Hp` is
  sampled 262 times; its 13 drops total 1286 against the damage set's 1284.84,
  pairing individually. Those 21 hits are damage **TAKEN**. So they constrain
  survivability, **not build math** - Emberforge is unblocked by the log's four
  `sourceType: 0` payloads, not the save's twenty-one. A quarter the size of
  what was claimed.
- "a float to nine places" - they are `float32`, so about **7** significant
  digits.
- The five repeats of `9.745483398` **are** the 1.5 s tick, so counting them as
  independent evidence double-counts one computation.
- "first timing constant this project has measured" - n=3 intervals, one
  encounter, at the 1 ms quantisation floor.
- "`nameId` and `SkillNameId` are the same id space, **proven**" - n=1 shared
  value, and "from the same component family" was **flatly wrong**.

The merger's own probe had also mis-measured a prefix, reporting matching
positions **anywhere** as a leading prefix. Every one of these was caught by
somebody other than the author. That is the whole argument for the shape.

## A remediation opened the hole it was cleaning. Twice.

Worth carrying forward as a pattern, not two anecdotes.

1. The third party's display name in the save was refused **only** because a
   Blueprint GUID beside it tripped `PRODUCTUSERID` - a **false positive** that
   was accidentally load-bearing. Authoring those GUIDs, which item 2b
   **required**, removes the one thing standing between a stranger's name and a
   public repository.
2. Then `redact()` itself - the only sanctioned redaction path - **disarmed**
   the `NAME_FIELD` guard written to close that hazard. It rewrites the
   decoration to `<PRODUCTUSERID>`, the anchor required `[0-9A-Za-z]`, angle
   brackets are not alphanumeric. `assert_clean(redact(raw))` approved bytes
   still carrying the name verbatim. **Redacting the file broke the guard.**

Nothing leaked - the fixture was clean throughout and the pushed tree scans
zero. What was broken was the protection. **Check what your fix removes, not
only what it adds.**

And the guard's own test passed for the wrong reason: it used a 32-character
**alphanumeric** stand-in, which satisfies the anchor. The tested case was not
the case the module's own redactor produces.

## A proven defect in the continuity machinery

`LL-0018` removed the shared ledger so lanes could not conflict. It solved the
**text** race and left the **id** race untouched - and the fragment design is
what hides it. Two lanes on separate branches both allocated `LL-0023`; git
merged both cleanly; `integrate()` then **silently dropped one**, returning
`[]` with no error, because it skips ids already present.

Reproduced against a throwaway copy of the real ledger. Renumbered by hand and
verified. **`ROADMAP.md` item 2c, and it should be fixed before the next
multi-lane session** - the safety lane's accidental per-lane `SAF-NNNN`
namespace may already be the answer.

## Third-party sources, tiered so it is not re-done

`questlog.gg` is **datamined** - it addresses monsters by numeric id in the
same space the save uses, and lists `[Debug]` and `[Discarded]` developer rows
no player can see. `gamerguides` is **hand-mapped** and says so, with a
database whose first iteration was built on the **demo**. Opposite
provenances, opposite failure modes, and neither may write an id into
`docs/OBSERVED_IDS.md`. "Third-party site" is not a trust tier.

## Item 2c was fixed in the same session - and the probe for it was vacuous

`LL-0031`. `integrate()` now compares content per id: same id and same content
is still skipped, so idempotence survives, while same id with **different**
content raises and writes nothing. `duplicate_claims()` reports collisions
across the ledger and every fragment, and a test runs it over the real files on
every suite run.

**The instructive part is the verification, not the fix.** The dangerous
failure was never the collision - it was **over-tightening**, because a
comparison that is too strict turns every legitimate re-run into a false
collision, which gets a force flag bolted on, which disarms the guard for real
collisions too.

The integrator mutated the normaliser and tested it with **CRLF**. Nothing
changed, which looked like proof the guard was one-sided. **The probe was
vacuous:** `read_text` performs universal-newline translation, so CRLF is gone
before any comparison runs. Re-run with **trailing whitespace** - a difference
that survives the read - the real code stays idempotent while a byte-exact
comparison raises.

So this repo's own "a mutation that fails to apply looks exactly like a passing
test" was hit **while specifically watching for it**. The rule that saved it is
the other one: assert the mutation applied before believing the result.

**Namespacing was deliberately not implemented** - `OPS-6`. `SAF-NNNN` is
collision-free by construction and is probably the right long-term answer, but
retiring the global space changes what 31 existing entries and every citing
commit refer to. Operator decision.

## Where to start next

**Item 2d first** - it is small, and it is what a new contributor hits before
anything else. A fresh clone runs **one failing test**:
`tests/test_lane_contract.py` bakes the absolute `REPO_ROOT` into a rendered
contract, so the suite is only green in place. Measured at `548e5b6` too, so it
predates all of this. `README.md` tells people to clone and run `pytest`, so
the documented first-run experience is currently a red suite. **Every count in
this repository, including the 953 above, is an in-place number.**

Then **item 7** - extract the damage series into shipped code - with **item 7b**
folded into whichever session next has the client open. The training ground is
the only route to **outgoing** damage in quantity, and `sourceType: 0` is what
to look for.

Do **not** label any damage number dealt or taken beyond what is already
measured.

---

# Session 2026-08-09c - the lane machinery finished, and a save caught mid-flight

Orchestrated and multi-agent throughout. Branch
`session/2026-08-09c-lane-state-and-capture`, **merged to `main` at the
operator's instruction** and pushed - `main` is `58ff2e7`. Ledger `LL-0018`
through `LL-0022`. 685 tests at the start, **807** at the end, all green from
purged caches on `main` after the merge, ruff clean.

## The thing that mattered most, and it was luck plus ten minutes

The hand-off said `StandaloneSlot_<roleId>.sav` was PERISHABLE and that the
previous session had lost it. Ten minutes into this session, before touching
the roadmap, a crude poller was armed against the save directory. **Seventeen
seconds later the file appeared.**

It was caught whole: **263 generations, 105 distinct sizes, 2,190 bytes at
17:27:17 to 177,878 at 17:46:54**, and then it deleted itself. Every one of
those 263 generations now parses with zero undecoded bytes.

Three filed claims about that file were wrong, and only capturing it showed
that:

- **not 46 KB** - it ends near 178 KB, about 62x the next largest save. The old
  figure was a file read mid-write and mistaken for its size.
- **not append-only** - it measured *smaller* fifty seconds after a peak. It is
  rewritten in place, so one snapshot can be a torn read.
- **not a 13-minute life** - it was still being written 19m37s in.

The lesson is not about this file. It is that arming a watcher **before** the
event costs ten minutes and re-reading a document costs the whole observation.

## ROADMAP 1b is closed - and a lock was the wrong answer

Per-lane state is `lanes/<lane_id>.STATE.json`; the ledger race is solved by
`lanes/<lane_id>.LEDGER.md` fragments that only the integrator folds into
`docs/LEDGER.md`.

**The roadmap offered a lock as one of two options. A lock does not work**, and
that is now written down so nobody re-proposes it: a lock serialises writes in
*time*, but lanes are on different *branches*, and git merges *content*. Two
perfectly serialised appends still conflict. `tests/test_lane_state.py` proves
the point with real git merges - the shared-file shape is asserted to CONFLICT
and the fragment shape to merge clean. Proving only the second would have shown
the change happened without showing it mattered.

## The layout is flat because two safety guards said so

The first cut used `lanes/<id>/STATE.json`. `lanes/capture/` was then rejected
by **two independent PII guards** - `.gitignore`'s bare `capture/` rule and the
pre-commit hook's `*/capture/*` rule - both behaving exactly as designed. The
lane directory was a false positive against a correct rule.

Weakening a veto-holding lane's guard for a naming convenience was the wrong
trade. Flat files (`lanes/capture.STATE.json`) remove the whole collision class
rather than one instance: `logs`, `frames`, `private` and `tmp` are blocked the
same way, so a future lane named after any of them would have failed
identically and nobody would have connected symptom to cause.

## Three traps, all of them this repo's own documented anti-patterns

Hit anyway, which is the point of writing them down again:

1. **CRLF.** The first `.gitignore` carve-out looked applied and was not - the
   negation lines were written with CRLF while the file was LF, so each pattern
   carried a trailing CR and matched nothing. The file read back as correct.
   Only the byte count showed it.
2. **`git check-ignore` is the wrong probe.** It exits 0 when *any* pattern
   matches, **including a negation**, so a correctly re-included file reports
   exactly like an excluded one.
3. **The orphan guard could not have caught the hole it exists to catch.** It
   walks `git ls-files`, so a path git is *ignoring* is invisible to it. The
   blind spot and the bug were the same shape.

## Live operator attestation, and what the log said back

Mid-session the operator reported: at level 3, **Marksman** was the **only**
talent choice at that tier, and **Lightning Arrow** went into the **C** skill
slot. The log was checked immediately and yielded a previously unrecorded
shape:

    [SkillSlotView::OnRequestEquipAmmo]  Equip ammo: ammoId: <id>, destSlot: <n>

**Exactly two equip events exist in the entire log and both target
`destSlot: 2`, at level 3** - which independently corroborates from the log
what `LL-0016` read off the screen: the C arrow slot unlocks at Lv. 3 and is
the first slot a player must fill. Four ammoIds appear overall - 120501,
120502, 120508, 120510 - a 1205xx space distinct from item cfgIds.

**Which id is Lightning Arrow is deliberately NOT recorded.** Two were equipped
to that slot five seconds apart and the log names neither. That binding needs
the operator or a frame, and inventing it would poison exactly the file whose
value is that it does not invent things.

**Measured negative, worth as much as a positive:** the equipped loadout is in
**no local save**. All seven saves plus the largest capture were searched for
those ids as ASCII, int32, int64 and float64 - zero hits. The log is the only
local surface carrying a loadout, so Emberforge cannot read one from disk.

## Two safety findings, routed to the lane holding the veto

- **`SAF-3`** - inventory instance ids share a **12-digit prefix** with the
  operator's roleId. Masking the roleId alone does not mask them, and each one
  leaks that prefix.
- **`SAF-4`** - some `TS.UI` lines carry **CJK text**, so a raw log excerpt is
  neither ASCII nor single-byte.

## The refutation pass earned its keep, twice over

An independent verifier was told to REFUTE this session's own claims and to
default to refuted when uncertain. It refuted nothing - but it found **two
guarantees that were narrower than the words describing them**, and both were
in code this session had already mutation-tested and called proven:

1. **The read-only refusal was bypassable.** It lived only in `state_path()`
   and `fragment_path()`, so every default route raised and every route taking
   an explicit `path=` walked straight past it. `save(LaneState(lane_id=
   "verify"), p)` wrote a file. "Eight entry points raise" is not the same
   property as "verify writes nothing, ever" - and only the second is what
   lets a read-only lane grade other lanes' work.
2. **`integrate()`'s `reversed()` had zero coverage.** Removing it left the
   whole suite green, because every test used a single-entry fragment. The
   docstring promise that newest lands on top was decoration.

**The lesson is about the method, not the bugs.** An author's own mutation
testing aims at the code that exists; it does not aim at the route around it,
and it cannot notice a promise nothing ever exercised. That is precisely why
the adversarial pass is a separate agent with a separate brief, and why
"agreement is not evidence" is written the way it is.

It also caught two stale things worth knowing: the merge test was still
building fragments at the **nested** `lanes/<id>/LEDGER.md` layout abandoned
earlier the same session, so it had stopped exercising what ships; and the
conflict assertion matched the bare word `CONFLICT`, which also matches git's
own advice text "fix conflicts".

One process note for next time: the verifier ran while the branch was moving
under it, and it handled that correctly by re-anchoring to pinned clones. But
a refutation pass is cheaper and sharper against a frozen ref - dispatch it
after the last commit of a slice, not during.

## Where to start next

**Item 2b** - the sanitised fixture for the transient save. It is safety-lane
work and it is specified. Read `lanes/safety.STATE.json` first; every lane now
carries its own queue, so read the state file of the lane that owns the files
rather than re-reading the whole roadmap.

The capture bytes are at `C:\ll-captures\saves\`, **outside the repo, not
committed**, and the filename embeds the operator's roleId.

One caveat worth keeping: a lane that adds a **new** file cannot go green
alone, because ownership is declared in `ops/lanes.py`, which the ops lane
owns. Measured on `lane/ingest`. Open as `OPS-2`.

# Session 2026-08-09b - recon, redaction P0, and the lane architecture

The second session, and much longer than the first. It ran orchestrated and
multi-agent throughout: roughly a dozen parallel agents, two persistent lanes in
their own git worktrees, and an adversarial verifier that returned nine defects
in this session's own findings.

Work is on branch `session/2026-08-09-recon-redaction-lanes`, pushed, **not
merged to `main`**. Ledger entries LL-0002 through LL-0012.

## The thing that mattered most

**The redactor was leaking.** Running it over the live log left **684 of 686**
occurrences of the operator's persona in place, and `assert_clean()` returned
cleanly on a leaking line - so the guard was vacuous for that shape. Two root
causes: keyed rules stopped their value match at whitespace, half-masking a
two-token display name; and the persona also appears with **no key at all**, as
a positional comma-separated field and after verbs like `PlayerOpenTreasureBox`.

Then a second, subtler defect surfaced on review: persona discovery returned
empty on an **isolated excerpt** - which is exactly what a test fixture is - so
the keyless shapes passed through and `assert_clean` approved them. Fixed, and
`assert_clean` gained a **cannot-certify** state so it refuses to approve text it
has no basis to approve. That distinction - "I could not determine this is safe"
is not "this is safe" - is the omit-rather-than-guess doctrine applied to a
guard, and it is worth keeping.

This blocked the raid-recon acceptance criterion outright, because that criterion
requires committing a redacted log excerpt.

## The recon nobody needed to capture

ROADMAP item 1 was written as "do a deliberate capture session". It was not
needed. The operator had played 3h44m and the log had grown 567 KB to 6.1 MB -
the data was already on disk. Re-probing live state instead of trusting the
document is the single highest-value habit this project has.

Measured: the dungeon lifecycle across two runs, the escape-portal mechanic, the
`Game.PlayState.*` namespace, six inventory opcodes, four loot contexts, 35
item cfgIds, and the join proving **the live `holding-` id space and the item
cfgId space are one space** (`3020401` is both the equipped weapon and a
tradeable item priced at 31).

Also: the game's nouns are **dungeon** and **escape**. `raid` and `extract`
appear **zero** times.

## Nine defects, in our own findings, from one adversarial pass

An independent verifier was dispatched to REFUTE the recon and returned nine.
The instructive ones:

- A death was attributed to the operator that belonged to somebody else.
- A scope label said "`cfgId:` anywhere in the log" and measured a pattern that
  silently dropped an entire subsystem, because `TS.FTE` writes `cfgId: 123`
  **with a space** and the pattern required none. 35 versus 45 ids.
- "SEscapePortalSpawner places a portal" - it placed nothing; all six of its
  lines are failures to find a config. A producer inferred from a name.

Then the **operator's own attestation** ("I had one death, in the tutorial")
corrected the correction. The log had been read wrong twice: `WaitSpiritual` is
the death state and `Spiritual` the resurrection state, the operator's death is
recorded by `OnPlayerDead` and **not** by a `Game.PlayState.Death` tag, and the
"second player" is a **bot** the operator killed. PvP is a clean null after all.

Lesson worth carrying: three passes, three different wrong answers, settled by
one sentence from the person who was there.

## The lane architecture

Eight persistent specialist lanes, each owning a disjoint file set, each in its
own git worktree on its own branch, none merging to `main`. Operator-chosen
shape. `ops/lanes.py` declares the roster and `tests/test_lanes.py` enforces the
invariants **mechanically** - no repo file has two owners (walked over the real
tree, not compared as pattern strings), cross-cutting files like `CLAUDE.md` are
owned by nobody, `safety` holds a veto, `verify` owns nothing and is read-only.

Contracts in `.claude/commands/lane-*.md` are **generated** from the roster, so
ownership and prose cannot drift; the drift guard is proven by mutation.

**Running a lane end to end found two defects that reading the code never would**,
both in the same family: a path derived from `__file__` is not a fact about the
repository. `lanes.REPO_ROOT` resolves to the *worktree* inside a worktree, so
every "this is not the primary checkout" assertion inverted; and
`ensure_worktree` defaulted to it, so creating one lane's worktree from inside
another's forked the new branch off the wrong HEAD, silently importing another
lane's work. Both fixed via `primary_checkout()`, which asks
`git rev-parse --git-common-dir`.

## Two lanes actually ran

`ingest` built the GVAS `.sav` reader (ROADMAP item 2) and then finished it -
all 627 trailing bytes of `EnhancedInputUserSettings.sav` decode, and the result
**cross-corroborates the log**: save and log independently agree that
`KB_Blackarrow_Major_Action` is bound to `RightMouseButton`. Published GVAS
parsers do not work on this build; UE 5.4+ replaced the property tag with a
recursive type name plus a flags byte.

`safety` closed a hole the ingest lane's own fixtures had exposed: base64
defeated the PII guard completely. It also stopped the guards skipping binaries
by suffix. Merging the two was the real test - each was green alone and only the
merge could show whether the new scanner could see into the fixtures. It can,
and they are clean.

## Traps found the expensive way, all now written down

- **The hygiene guards were blind to every uncommitted file.** They walked
  `git ls-files`, which lists tracked paths only, so a new file was unscanned
  until after it was committed - the exact moment the guard stops mattering. Two
  separate agents hit this in one day.
- **A same-length mutation inside one mtime tick leaves a stale `.pyc`.** Python
  reuses the old bytecode, which can fake a GREEN under mutation and therefore
  fake a non-vacuity proof outright. Clear `__pycache__` before every mutation
  run. This one undermines the technique the whole project relies on.
- **`pytest -q` on top of `pytest.ini`'s own `-q` becomes `-qq`**, which
  suppresses the summary line. A wait-loop grepping for "N passed" could never
  match and spun to its timeout.
- **`git check-ignore -v` prints the matching pattern even for a NEGATION.**
  Treating "any output" as "blocked" reads a carve-out as a refusal.
- **Some settings never touch local storage.** `InvertCameraYAxis` exists in the
  log and in no save file at all, so a settings reader built on `.sav` alone is
  silently incomplete.

## Where it stands

Suite green. The primary checkout was byte-identical throughout both lane runs.
ROADMAP item 0 (redactor P0) closed, item 2 (GVAS) closed, item 4's parser
closed. Item 1's remainder needs a real matchmade raid, which needs the operator
to enter one - everything measured so far is the Prologue at `matchId=0`.

---

# Session 2026-08-09 - project inception

The first session. Lanternlight went from "does a companion tool for this game
even make sense" to a scaffolded public repo with a measured foundation, in one
sitting. Nothing was built on an assumption that was not probed first, and two
of the session's conclusions reversed earlier conclusions from the same session.

## Starting point

Precedent was `C:\RedMoon` (Red Moon, V Rising) - an established architecture
with a live-state half and a static-extraction half. The question was whether
that architecture transfers to Mistfall Hunter (Steam appid 3282300, UE5, 41.6
GB, buildid `24619162`, client version string `0.2.0.0` on the title screen).

The answer is no, in both halves, and the reason had to be measured before
anything could be designed. That measurement is `docs/FINDINGS.md`.

## The feasibility probe and its negative results

Three findings, all of them blockers, all of them permanent.

**Kernel anti-cheat.** The Steam store page discloses "Uses Kernel Level
Anti-Cheat", named Bellring Anti-Cheat, behind a third-party EULA gate. The
shipped binary set corroborates it heavily - `gpHackerProc.dll` at 5.7 MB,
`gpShell.dll`, `sscronet.dll`, plus a full publisher SDK stack under
`GSDK_US\Steam\` (`gsdk.dll`, `parfait.dll`, `bmf_hydra.dll`), GSDK version
string `3.23.0.0`, package `com.hermes.pstgame`, app_id `937566`, and an
embedded CEF browser.

This kills the entire RedMoon live-state half permanently: no injected plugin,
no process memory read, no packet capture, no swapchain-hooked overlay, no
synthetic input into the game window. The stake is a ban on the operator's real
account, and several of those are plainly outside the EULA. This became
ADR-001 and it is the defining constraint of the whole project.

**All paks encrypted.** `MistfallHunter\Content\Paks` holds `global.utoc` /
`global.ucas` plus 15 chunks. Headers were read directly - 144 bytes per file,
read-only, no process touched, script now at `scratchpad/probe_paks.py`. Every
content chunk carries `flags=Compressed|Encrypted|Indexed`; 101,500 entries
across all TOCs; every legacy `.pak` sidecar reports `pakver=12
encrypted_index=True`. `keyguid=ZERO` means one global AES key, not per-chunk
named keys, and that key is not on disk in plaintext. Recovering it means either
dumping it from the running process (forbidden by the above) or statically
reverse-engineering a binary shipping with kernel anti-cheat. Neither is
acceptable. This became ADR-002.

**No loose game data.** A sweep of the whole 41.6 GB install for `*.ini *.json
*.csv *.uasset *.cfg` returned exactly three files: a zero-byte
`StagedBuild_MistfallHunter.ini`, and two GSDK config files next to the
anti-cheat binaries. None of them game data. RedMoon's extractor half is dead
too.

At this point the honest read was that there might be no project here at all.

## The post-launch sweep that reversed them

The pre-launch sweep of `%LOCALAPPDATA%` found nothing, and that negative was
nearly recorded as final. It was wrong for a boring reason: **the game had never
been run on this machine, so it had not yet written its Saved tree.**

The operator launched the game at 08:18. A second read-only sweep found
`%LOCALAPPDATA%\MistfallHunter\Saved\` created 08:18:56, containing:

| Artifact | Size | Value |
|---|---|---|
| `Logs\MistfallHunter.log` | 567 KB after 10 min, live-appending | the primary surface |
| `SaveGames\*.sav` (4) | 2-2.7 KB each | plain UE GVAS, magic `47 56 41 53`, NOT encrypted |
| `Config\Windows\GameUserSettings.ini` | 1398 B | settings only |
| `Config\Windows\Engine.ini` | 7228 B | plugin roster only |
| `AvgPrice_937566.ini` | 37 B | market / trade-price cache, currently empty |

The log turned out to be rich: map and sublevel transitions with ms timestamps,
`match state changed to <state>`, a `match id` field, `setClassGender inclassid
==NN`, weapon config ids via `OnRep_WeaponCfgId`, equipment asset paths,
`seasonId`, server region, gateway hostname, `roleLimit:3`. Categories are
namespaced (`LogStk`, `TS.Avatar`, `TS.Dungeon`, `TS.Camp`, `TS.Inventory`,
`TS.Network`, `Puerts`). The GVAS saves parse with any GVAS reader.

**Process lesson worth keeping: the negative was a measurement of the wrong
world state, not of the game.** The sweep was correct and its conclusion was
false. Anything probed before the game had ever run needs re-probing after.

Two boundaries were set at the same time and both hold. `GSDKCache\
accountList.json`, `user.json`, `user_infos.json` and `gsdk_app_log.db` sit
under the install dir beside the anti-cheat binaries - they were **listed, never
opened**, and are treated as out of bounds. And the registry sweep was capped at
depth 2 and found nothing, which is recorded as non-exhaustive rather than as a
clean negative.

The log also carries the operator's SteamID64, Steam persona, GSDK openID and
userId, an EOS ProductUserId, and an IP-resolved city, state and country. On a
public repo that is not a style concern. It became ADR-004: a tested redactor
gates every fixture, and it sits between any capture and any committable
artifact - not at review time, and not as a habit.

## Class research and the Blackarrow decision

Two independent research agents ran, one per class, and were adjudicated by a
merger that graded neither its own output nor allowed either agent to grade its
own. Written up in `docs/CLASS_RESEARCH.md`.

The player profile weighted against: League mains Tristana and Vayne - ranged
sustained auto-attack DPS, spacing and kiting, target selection, high mechanical
ceiling, historically vulnerable to being collapsed on. New to extraction games.

**One cross-agent conflict, resolved on specificity.** The Shadowstrix agent
reported from Steam store copy that every class carries two stances. The
Blackarrow agent found an official launch announcement saying the Blackarrow's
new weapon launches in a future season. The store copy is generic marketing; the
specific official statement wins. Blackarrow is bow-only at launch, and its
"Archer" and "Hunter" are ammo and playstyle families on one weapon, not two
stances.

Substance on each: Blackarrow was nerfed 2026-08-06 (impact effect removed from
uncharged shots, fully charged impact slightly reduced) after being officially
acknowledged as overperforming in solo - so any tier list stamped only "August
2026" is probably pre-nerf and cannot be placed. Its speed stat is Charging
Speed, not attack speed. Effective heavy-shot range is roughly two dodge-lengths
per player testimony, absent from every guide site - it is not a sniper. It is
gear-hungry and dies to gap-closers in tight terrain. Shadowstrix has two real
stances, stealth is Dagger-only, Element of Surprise makes a backstab out of
stealth an automatic crit, it is the squishiest class in the game, and it is
**untouched by every patch since launch** - which is why it tops the post-nerf
tier lists and also why it is the likeliest next nerf target.

**Operator decision: Blackarrow now, Shadowstrix committed for slot 2 at
approximately hour 20, slot 3 left free.** The log shows `roleLimit:3` so slots
are not scarce. Blackarrow is the direct transfer of the existing skillset, and
its failure mode is one the player already understands from the other side of
it. Taking Shadowstrix first would put the squishiest body in the game, with a
one-opener-one-escape kit, into an unfamiliar extraction loop where a lost fight
also loses the kit. The timing asymmetry was recorded honestly: building a main
around an untouched outlier eleven days after launch is building on sand.

Purpose is "both" - this is the real main account, and Lanternlight harvests
whatever the log yields rather than the class being picked as an instrument.

Consequence for Emberforge, and it is a design constraint not a note:
**two-class coverage is scheduled rather than accidental, so the data model must
not hard-code a single class shape.**

The most load-bearing thing both agents agreed on: **no cooldown numbers, damage
coefficients or stealth durations are published anywhere as of 2026-08-09**, and
any site quoting one is fabricating. That is exactly the gap the engine exists to
fill. Also agreed: gems replaced random gear affix rolls, so mid-game power comes
from sockets; and the launch-window wiki farms cross-copy each other verbatim, so
**agreement among them is not corroboration** - one invented an SS tier nobody
else uses, another invented an August 5 nerf that does not exist.

## The pixel-to-log id join

The best piece of method from the session, and the reason `docs/OBSERVED_IDS.md`
is a first-party table rather than a wiki transcription.

The log emits `setClassGender inclassid ==NN` with a UTC timestamp and **never a
class name string**. So the ids alone are meaningless. A passive desktop poller
captured the screen every 3 seconds with local-time filenames; local is UTC-5,
so the two streams join on wall clock. Reading the class name off the ROLE panel
in the frame closing each dwell window gives name-to-id directly. No process
access, no OCR guesswork - the name is rendered text read off a screenshot.

Result, complete and ascending, matching the in-game sidebar order top to
bottom: **10 Mercenary, 11 Sorcerer, 12 Blackarrow, 13 Shadowstrix, 14 Seer, 15
Withered Knight.** Class 12 is doubly established - pixel-joined and
operator-attested, because the committed character logged `classId 12`. Class 15
is the weakest row: established by elimination plus sidebar order, because its
ROLE panel was never captured.

**The wrinkle that made the join trustworthy rather than lucky:** the ROLE
description panel lags the selection by about one frame while the left sidebar
highlight leads it. In the frame at the instant class 13 is set, the panel still
reads Blackarrow (12) and the sidebar has already moved to Shadowstrix. Both
halves agree with the log from opposite directions. Read the panel for the
outgoing class and the sidebar for the incoming one.

The same method yielded weapon config ids from `server_refreshKnightFeature:
<actor> class-NN holding-NNNNN`. Four classes show two ids, two show one.
Because the pair counts line up with the published weapon kits (Mercenary hammer
plus sword-and-shield, Shadowstrix dagger plus dual blades), **pairs are the two
weapon stances, and the gender-variant hypothesis is refuted** - gender variants
would apply uniformly across all six classes, and they do not. Blackarrow's
single id independently corroborates the official future-season statement, which
is worth more than the statement alone because it was measured here.

Three things left open on purpose:

- **Sorcerer also shows a single id and the official line does not account for
  it.** Nothing anywhere may say "Blackarrow is the only single-weapon class"
  until this is settled.
- **The stance-toggle probe produced no distinguishable event.** Step 4 of the
  capture plan - hold on one class, cycle the toggle, watch `holding-` - simply
  did not fire. The pair evidence comes from the carousel instead, which is
  weaker for the stance question specifically. Re-run deliberately.
- The id space is **not** class-ordered (Withered Knight sits at 304xx with
  Mercenary while the middle four sit at 305xx), and creation previews use
  5-digit ids (`30504`) while the live character uses 7-digit (`3010401`).
  Different id spaces. Do not join them without evidence, and do not infer class
  from an id range.

## Also settled this session

Licensing and posture: Apache-2.0, public from the first commit, copyright
Moonbeam 2026, with a Bellring Games / Skystone Games non-affiliation notice and
a no-redistributed-assets statement that is trivially true because nothing is
extractable anyway. That became ADR-006.

Names: the project is **Lanternlight**, the math engine is **Emberforge**. Repo
at `github.com/Remus3/Lanternlight`. Reserved local ports, none built: dashboard
8810, log-tail service 8811, Emberforge 8813.

The overall shape is the inverse of RedMoon: Emberforge plus a build planner is
roughly 90 percent of the project and live state is close to zero. The hard
problem is not extraction, it is **provenance** - proving where every number came
from and refusing to emit one that has no source.

---

## Next session starts here

1. **Read `docs/FINDINGS.md` and `docs/OBSERVED_IDS.md` first.** They are the
   source of truth. Nothing else in the repo outranks them, and where a
   recollection disagrees with them, they win.
2. **Do the raid recon pass (ROADMAP item 1).** It is the top item and the only
   one that can invalidate the design of the others. Loot, extraction events,
   match results and death states are unmeasured, not absent. Run one raid to a
   successful extraction and one to a death, with the frame poller running and
   the wall-clock of entry noted.
3. **Fold in the two cheap open questions while the game is open** - the Sorcerer
   second-weapon check (ROADMAP 5) and a deliberate stance-toggle re-run (ROADMAP
   6). Both need the client and neither deserves its own session.
4. **Every id observed gets written into `docs/OBSERVED_IDS.md` at the moment it
   is observed, with the method named.** An id learned from a wiki six weeks
   later is not the same fact.
5. **Nothing gets committed until it has been through the redactor**, including
   anything captured in step 2. The log carries a SteamID64, a persona, SDK and
   EOS ids, and an IP-resolved location.
6. Do not open anything under `GSDKCache\`. Listed, never opened, stays that way.
