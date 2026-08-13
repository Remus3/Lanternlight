# Lanternlight roadmap

What is actually next, in priority order. Every item carries an acceptance
criterion, because "worked on it" is not a state this project recognises.

Aspirational ideas that nobody has committed to live in [`BACKLOG.md`](BACKLOG.md).
Nothing is moved from there to here without an acceptance criterion attached.

Status vocabulary: **NEXT** (the current item), **READY** (specified, unblocked),
**BLOCKED** (waiting on something named), **OPEN** (a question, not a task).

---

## 0. Redactor persona leak - CLOSED 2026-08-09

Ledger `LL-0004` and `LL-0013`. Left here as a closed item rather than deleted,
because the shape of the bug is the useful part.

The redactor left **684 of 686** occurrences of the operator's persona in the
live log, and `assert_clean()` returned cleanly on a leaking line - so the guard
was vacuous for that shape. Three separate root causes, found one at a time:
keyed rules stopped their value match at whitespace so a two-token display name
was half masked; the persona also appears with **no key at all**; and discovery
was **scope-dependent**, returning empty on an isolated excerpt - which is
exactly what a test fixture is.

Now 0 of 686, raw UTF-16 included, and `assert_clean` has a **cannot-certify**
state so it refuses to approve text it has no basis to approve.

## 1. Raid recon pass - PARTLY DONE, remainder is BLOCKED on a real raid

Reframed 2026-08-09 after the data turned out to be on disk already. No capture
session was needed: the operator had played 3h44m and the log had grown from
567 KB to 6.1 MB. Section 7's "unmeasured" was a statement about the world at
08:28, not about the game.

**What is now measured** and written up in `docs/FINDINGS.md` section 9 and
`docs/OBSERVED_IDS.md`: the dungeon lifecycle across two runs, both outcomes
(one disconnect, one successful escape), the escape-portal mechanic, the
`Game.PlayState.*` tag namespace including `Death` and `Escape`, six inventory
opcodes, four loot source contexts, 35 item cfgIds, and the join proving the
live `holding-` id space and the item cfgId space are the same space.

Also corrected here: the game's own nouns are **dungeon** and **escape**. The
words `raid` and `extract` appear **zero** times in the log. A grep for the
wrong word returns a clean negative that means nothing.

**PARTLY REFUTED 2026-08-09c, by an operator attestation plus a log join.** The
operator named the mode - "Hallowgrove, Normal, Solo explore" - and the log was
checked against it immediately. What that overturned:

- **Non-zero `matchId` values EXIST**: `11111` and `11112`. This item's
  acceptance treated "non-zero `matchId`" as a proxy for "a real matchmade
  raid". **That proxy is refuted.** Both belong to *solo explores*. `matchId=0`
  is the Prologue; a solo explore gets a low sequential id. Whatever
  distinguishes a matchmade run, it is not simply a non-zero `matchId`.
- **A better discriminator is available**, straight from the map URL:
  `?levelId=119&roomModeId=0&matchType=1&matchId=11112`. Four axes, not one.
- **A second escape type exists.** `FixEscapeBell` / `WindChime` appears
  alongside `GroveSprite` in one run, so "only one escape type has ever been
  seen" is no longer true.
- **The player-facing and internal names differ.** "Hallowgrove" is the name
  the operator sees; the map loaded is `/Game/Project/Maps/Map_2/Whitewoods_Day`
  with sublevel `WhiteWoods_Level_Easy2`. A grep for the player-facing name
  finds only cosmetics.
- **Match state machine**, observed in order: `onRequestMatch`, `InMatch`,
  `MatchSuccessful`, `EnterBattle`, `NotMatch`.
- **A loot pity system exists** - `OnHandleFirstLoot` carries `dropValue`,
  `dropPity` and `addPityDropValue exceed threshold`. Unmeasured beyond its
  existence; no coefficient is claimed here.

**What is still unmeasured:** a run with another player in it. Everything above
is solo. PvP mechanics remain a clean null.

**And the transient save's trigger is now known.** `StandaloneSlot_<roleId>.sav`
is created at match start and destroyed when the run ends - it is not on a
timer at all. Measured on two independent runs: `matchId=11112` entered battle
at 22:27:00 UTC and the file appeared 17 seconds later at 22:27:17; the run
ended around 22:46 and the file was gone by 22:48:48. The previous session's
file, which appeared at 20:39 UTC, fits `matchId=11111` starting at 20:38:19.
The "about 13 minutes" lifetime was never a timer - it was simply how long that
run lasted. Its producer is named too: `StandaloneLevelCtrl.battleSnapUpdate`
emits battle snapshots throughout, and the controller name matches the file.

**The operator has never been observed dying.** The log's single
`Game.PlayState.Death` belongs to a second player, not to them
(`docs/FINDINGS.md` 9.3). So the original "one run to an extraction, one to a
death" pairing is still half open, and no amount of re-reading this log will
close it.

A second player and PvP analytics events **were** present, so PvP is no longer a
clean null - it is "contact observed, mechanics unmeasured" (`docs/FINDINGS.md`
9.10). That also means captures can contain a third party's identity, which the
safety item above now has to cover.

**Acceptance for the remainder:** a redacted log excerpt from a run with a
**non-zero `matchId`**, committed as a fixture, covering entry, at least one
loot event, and an outcome; plus new `docs/OBSERVED_IDS.md` rows for every id
observed, each with its method named. Confirming or refuting that `matchId=0`
is what distinguishes the Prologue from a real raid is itself a result worth
recording. Blocked only on the operator entering one - nothing here needs a
deliberate capture session any more, because the log is sufficient on its own.

## 1b. Specialist lane build-out - CLOSED 2026-08-09

Decided with the operator 2026-08-09. Eight persistent specialist lanes, each
owning a disjoint file set, each running its own orchestrated sub-agents and
verifying their claims with `ops/merge_gate.py`, each in **its own git worktree
on its own branch**, and **none of them ever merging to `main`** - a human
merges after an out-of-domain check.

**Landed:** `ops/lanes.py` declares the roster and `tests/test_lanes.py` enforces
the invariants that actually matter - no repo file has two owners (walked over
the real tree, not compared as pattern strings), cross-cutting files such as
`CLAUDE.md` and `pytest.ini` are owned by nobody, every lane has a unique
worktree outside the main checkout, `safety` holds a veto, and `verify` owns
nothing and is read-only.

**Also landed:** `ops/lane_launcher.py` creates each writing lane's worktree on
`lane/<id>` and `assert_in_lane_worktree` refuses to let a lane write in the
primary checkout; an integration test proves a lane commit leaves the primary
checkout with an empty `git status`. `ops/lane_contract.py` renders all eight
contracts **from the roster**, so ownership cannot drift out of sync with the
prose describing it, and the drift guard is proven non-vacuous. The contracts
live in `.claude/commands/`, so each lane is also a slash command.

**Both remaining pieces landed 2026-08-09.** Ledger `LL-0018`.

1. **Per-lane on-disk state - DONE.** `ops/lane_state.py` gives every writing
   lane `lanes/<lane_id>.STATE.json`, holding a session counter, a one-line
   resume note and its open items. Each file has exactly one owner, so it
   cannot race. All seven writing lanes are seeded from this roadmap, so a lane
   starting cold reads its own queue instead of the whole document. `verify` is
   read-only and is refused a state file rather than given one it must remember
   not to use.
2. **Commit serialisation - DONE, and the lock option is refuted.** A lock does
   **not** fix this, and that is worth keeping so nobody re-proposes it: a lock
   serialises writes *in time*, but the lanes are on different branches and git
   merges *content*. Two lanes can append perfectly serialised, an hour apart,
   and still conflict, because both inserted text below the same anchor of the
   same file. So the shared mutable file is removed instead - each lane appends
   only to `lanes/<lane_id>.LEDGER.md`, and `docs/LEDGER.md` keeps exactly one
   writer forever: the integrator on `main`, calling `lane_state.integrate`,
   which is idempotent.
3. **Nobody has actually run a lane yet - THIS WAS ALREADY STALE when written.**
   Two lanes had run end to end before this line was committed: `ingest` built
   the GVAS reader and `safety` closed the base64 hole, both in their own
   worktrees on their own branches, both merged (`Merge branch 'lane/ingest'`,
   `Merge branch 'lane/safety'`). Running them is what found the
   `primary_checkout()` bug that reading the code never would.

**Acceptance - MET.** A lane launched into its own worktree, doing real work,
committing to its branch, primary checkout untouched: demonstrated by the two
lanes above, and again this session by `lane/ingest`.

The differential that justifies the fragment design is measured rather than
argued: `tests/test_lane_state.py` runs **real git merges** and asserts that two
branches appending to one shared ledger **conflict**, and that two branches
appending to their own fragments **do not**. Proving only the second would have
shown the change happened without showing it mattered.

## 2. GVAS `.sav` reader - DECODED 2026-08-09, fixture split out to 2b

Ledger `LL-0011`. `lanternlight/gvas.py` parses every `.sav` file. The save set
keeps growing and any count written here goes stale within the day: four at
first probe, then five, six, seven, and as of 2026-08-09 **eight distinct
names** - `Scav.sav` appeared at 17:51 local mid-session and parses cleanly
with one property, `bIsMaskReward`. A reader must enumerate the directory,
never assume a list. Published
GVAS parsers do not work on this build: UE 5.4+ replaced `FPropertyTag`'s
`FName Type; int32 Size; int32 ArrayIndex` with a recursive type name plus a
flags byte. All 627 trailing bytes of `EnhancedInputUserSettings.sav` decode,
and the result cross-corroborates the log - save and log independently agree
that `KB_Blackarrow_Major_Action` is bound to `RightMouseButton`.

**Reopened the same day.** A seventh save, `StandaloneSlot_<roleId>.sav`,
appeared at 15:39 and does not parse: it uses
`StructProperty<F_PlayzoneSaveData>`, never measured here. The reader **raises**
rather than guessing, which is the correct behaviour and is why this is an open
item rather than a silent partial parse.

It is the real character and progression store's best candidate, and therefore
the most valuable save surface for Emberforge. Its filename also embeds the
operator's roleId, so any fixture must be renamed, not just redacted.

**CAPTURED 2026-08-09, whole lifetime, and three filed claims are corrected.**
A snapshotter was armed at 17:27:14 local, before the file existed. It took
**263 generations** across **105 distinct sizes**, from first appearance to
deletion. The bytes are held outside the repository at `C:\ll-captures\saves\`
and are **not committed** - the filename embeds the operator's roleId.

Measured, first-party, this session:

- **It is not 46 KB.** It appeared at 17:27:17 at **2,190** bytes and was last
  seen at 17:46:54 at **177,878** bytes - about **62 times** the next largest
  save (`UserSettings_v1.sav`, 2,867 bytes), not twenty. The earlier "46 KB"
  was a reading of a file mid-write, mistaken for its size.
- **It is not append-only.** At 17:40:02 it measured 125,765 bytes, *smaller*
  than the 126,078-byte peak recorded 50 seconds earlier. It is rewritten in
  place with a varying size, so a reader must not assume a prefix stays put
  between two polls, and a single snapshot can be a torn read.
- **It does not live about 13 minutes.** It was still being written **19
  minutes 37 seconds** after appearing, and was gone by 17:48:48 - a lifetime
  of roughly 20 to 21 minutes. Whatever removes it is not a simple elapsed-time
  rule from creation. Leaving the mode remains the more likely trigger, and is
  still unmeasured.

None of this was reachable by re-reading a document, and the previous session
lost the file entirely. It came from arming a watcher **before** the file
existed, which is the whole lesson of this item and the reason
`lanternlight/savewatch.py` now exists rather than a scratch script.

**Acceptance - THREE OF FOUR MET 2026-08-09.** Ledger `LL-0019`, `LL-0020`.

- **Decoded.** All **263** captured generations, 105 distinct sizes up to
  177,878 bytes, parse in strict mode with `undecoded_trailing == 0` and zero
  unknown properties. Re-measured by the merger rather than relayed. All seven
  live saves still parse, so nothing regressed.
- **Types recorded.** A struct value is a nested tagged property list closed by
  `"None"` - no epilogue, no inner length, bounded by the tag's `Size`. New:
  `ByteProperty<Enum>` is an FString of the qualified enumerator and **not** a
  raw byte, plus `ArrayProperty`, generic `MapProperty`, and `StructProperty`.
- **Undecoded is named, not guessed.** Natively serialised structs (tag flag
  `0x08`) - `Vector` (24 bytes), `Rotator` (24), `Quat` (32), `Vector2D` (16) -
  come back verbatim as `UndecodedStruct`. 401 leaves, 10,600 bytes, in the
  largest capture. `Vector` and `Rotator` share a width, so they are separable
  only by name: the concrete case against guessing.
- **NOT met: no fixture.** See item 2b - it is safety-lane work, not ingest's,
  and doing it quietly here would be exactly the wrong move.

The reader **raised twice** on genuinely new things mid-work rather than
misreading them - a `MapProperty` keyed by `DoubleProperty`, and `Rotator`.
That is the raise-on-unknown guard validated in the wild for the second time,
which is better evidence than any test.

## 2c. Ledger fragments have an ID-ALLOCATION race - CLOSED 2026-08-11

Found by the integrator during the 2026-08-11 wrap, and proven rather than
suspected. This is a defect in the continuity machinery itself, which is the one
thing this project's whole design exists to protect.

`LL-0018` removed the shared mutable ledger and gave each lane its own
`lanes/<lane_id>.LEDGER.md` fragment, so two lanes appending could no longer
conflict. **It solved the TEXT race and left the ID race untouched, and the
fragment design is what hides it.** Two lanes on separate branches both
allocated `LL-0023` - `ingest` for the GVAS serialiser, `research` for the
transient-save decode. Because they wrote to different files, git merged both
cleanly and nothing anywhere complained.

**`integrate()` then turns the collision into SILENT DATA LOSS.** It skips ids
already present, which is what makes it idempotent - correct behaviour for a
re-run, catastrophic for a collision. Reproduced against a throwaway copy of the
real ledger:

    integrate(ingest)   -> ['LL-0024', 'LL-0023']
    integrate(research) -> []          # the entire entry, gone
    research heading present in ledger: False

No exception, no warning, no diff. A lane's whole session record disappears and
the only symptom is an empty list nobody reads.

**Worked around, not fixed.** The integrator renumbered by hand before
integrating - research to `LL-0025`, and the safety lane's two entries, which
had been written in a **different namespace entirely** (`SAF-0001`/`SAF-0002`,
against the `LL-NNNN` convention the ledger preamble states), to `LL-0026` and
`LL-0027`. The result was verified: 27 entries, `LL-0001` to `LL-0027`, zero
duplicates, strictly descending. A hand fix is not a fix, and the next session
that runs three lanes hits this again.

**Worth noticing before choosing a design:** the safety lane's accidental
`SAF-NNNN` namespace is **collision-free by construction**, which the global
`LL-NNNN` space is not. The lane that broke the convention may have stumbled
onto the answer.

**Acceptance - MET 2026-08-11.** Ledger `LL-0031`. Option (a), detection.
Prevention by allocation was rejected with a reason: lanes branch from a common
base, so two lanes each asking "what is the next free id?" get the **same**
answer and both take it. That is exactly what happened. What can be guaranteed
is that a collision never passes in silence.

`integrate()` now compares CONTENT per id and distinguishes the two cases it
previously could not tell apart - same id with same content is still skipped
silently, so idempotence survives; same id with **different** content raises
`LedgerIdCollision`, names the id and the fragment, and **writes nothing**.
`duplicate_claims()` and `format_duplicate_claims()` report collisions across
`docs/LEDGER.md` and every lane fragment BEFORE integration, and
`test_the_live_repository_has_no_colliding_id` runs that over the real files on
every suite run - so a collision cannot reach a merge even if a wrap ritual is
skipped.

**Verified independently by the integrator, before and after, on the real
function:** the collision case went from `returned []` with the entry silently
absent, to `RAISED LedgerIdCollision`. Idempotence held at `[]`.

**The guard is two-sided, and proving that took two attempts.** The dangerous
failure here is not the collision - it is over-tightening, because a comparison
that is too strict turns every legitimate re-run into a false collision, blocks
recovery after a partial merge, and gets a force flag bolted on, which disarms
the guard for real collisions too. The integrator's first mutation probe used
CRLF and showed no difference, which looked like a one-sided guard. **It was a
vacuous probe:** `read_text` performs universal-newline translation, so CRLF is
already gone before any comparison runs. Re-run with trailing whitespace - a
difference that survives the read - the real code stays idempotent while a
byte-exact comparison raises. The normaliser is load-bearing.

"Same content" means equal after normalising line endings, per-line trailing
whitespace, and leading and trailing blank lines - the three things that change
without an author touching a character. Interior blank lines and leading
indentation are deliberately NOT normalised, because both carry meaning in
Markdown. Validated against real data: 11 ids currently exist in both the
ledger and a fragment, and all 11 compare equal.

### The independent adversarial pass, run 2026-08-12 - it found a P0

2c shipped with **no** independent refutation, which is a departure from this
project's default, so one was run against a frozen `814b1ea`. The core guard
held. Several of the claims above did not, and one of them was a P0.

**P0 - the same silent data loss, through a different door. FIXED, `LL-0034`.**
`_HEADING_RE` wants exactly `###`, one space, a non-space id, then `" - "`.
Miss that by **one character** and the entry did not fail loudly - it became
**invisible**. Reproduced independently by the integrator before any fix, on a
throwaway copy of the real ledger, with a genuinely colliding `LL-0018`:

| heading | `fragment_entry_ids` | `duplicate_claims` | `integrate` | entry lands |
|---|---|---|---|---|
| `### LL-0018 - ...` | `['LL-0018']` | `['LL-0018']` | **raises** | no, correctly refused |
| `###  LL-0018 - ...` | `[]` | `[]` | **`[]`** | **no - silently gone** |

So a lane writes an entry, `integrate` returns `[]`, the integrator reads that
as "already done", and the entry is gone with no error - **which is the exact
failure LL-0031 was written to end.** Detection was the whole point of 2c, and
2c could be walked around with a space.

Fixed by `_assert_headings_parse`: below the marker, a **non-fenced** line
starting with `#` that carries an **id-shaped token** and does not parse as a
heading now **raises** `MalformedLedgerHeading` naming the file, the line
number and the offending text. Scoped that way on purpose - the dangerous false
positive is a rule that fires on ordinary prose, because a guard that cries
wolf gets switched off and then the real collision passes too. Verified after:
all three entry points now raise where all three previously returned empty.
Three mutants, `__pycache__` purged and every anchor asserted: guard removed
from `_blocks_below` -> 5 failed; from `fragment_entry_ids` -> 6 failed;
id-token test forced false -> 11 failed; restored -> 84 passed.

**THAT FIX WAS INCOMPLETE, AND AN ADVERSARIAL PASS FOUND A WORSE HOLE IN IT.**
See the section below. This item's claim to have closed the silent-entry-loss
*class* did not stand; `LL-0037` is where that is settled.

Also wrong, and it is this file's own anti-pattern for the fourth time: the
sentence above used to cite "**46** lines start with `#` below the marker, and
all 46 parse". Re-measured, it was **47** at the commit that wrote it and **51**
four commits later. The count grows with every entry, so filing it at all was
the mistake - it is no longer quoted anywhere, including in the docstring that
recited it.

**Three claims above are overstated and are corrected here rather than edited
away:**

- **"11 ids currently exist in both the ledger and a fragment" was wrong when
  written.** Re-derived by the integrator: **13** today, and the pass measured
  **12** at the commit that wrote the sentence. A filed count is a hypothesis -
  for the third time in two sessions. All of them do still compare equal, so
  the conclusion drawn from the number survives; the number did not.
- **"zero survivors" under mutation does not hold.** Two parts of the
  normaliser are **dead code**: flattening CRLF is unreachable because
  `read_text` performs universal-newline translation before any comparison, and
  the final-newline strip is likewise unreachable. Only the per-line `rstrip`
  is load-bearing. This is the same vacuous-CRLF trap the item already
  documents, caught a second time on the other side - the fix was written
  against a difference that cannot survive the read.
- **A real false positive exists and is worth knowing before it bites.** Any
  post-hoc edit to an entry already integrated into `docs/LEDGER.md` makes it
  differ from its fragment forever, so `integrate` raises and the live
  collision test goes red until the two are reconciled by hand. That is the
  over-tightening hazard this item named, arriving through editing rather than
  through re-running. Recorded as `OPS-8`, **now CLOSED** - ledger `LL-0040`.

  **The decision it asked for, taken: POLICY STANDS.** An integrated entry is
  never edited; a correction is a **new** entry. Auto-reconciliation was
  rejected with a reason - it would write to a lane fragment, which this
  project documents as append-only and never edited, so fixing a *reporting*
  defect would have broken a core invariant to do it. This session already
  followed that policy in practice: `LL-0037` corrects `LL-0031`'s claims by
  appending, not by editing.

  **What was actually broken was the diagnosis, and it gave the opposite
  remedy.** The message said the id was "claimed twice by DIFFERENT entries"
  and told the reader to **renumber the fragment's entry** - which for an
  edited entry records one piece of work under two ids, corrupting the record
  while appearing to repair it. The two faults are now told apart: two
  *fragments* differing means two lanes collided (renumber); one fragment
  differing from the *ledger* means the entry was edited after integration
  (restore it, or append a correcting entry, and do **not** renumber).
  `integrate()` sees only one fragment so it cannot tell, and now names both
  causes instead of guessing.

  The guard still goes red on an edited entry, deliberately - a durable record
  disagreeing with a lane's own copy is worth stopping for. The red is now
  self-explaining.

### The P0 fix was itself holed - found by refuting it, closed as `LL-0037`

The wrap ran an independent pass over this session's own three done-claims. It
confirmed 2d and item 7 and returned **`LL-0034` as PARTIAL**, with the verdict
that it "should not be recorded as closing the silent-entry-loss class". It was
right, and the worst finding is worse than the bug `LL-0034` fixed.

**A single forgotten backtick disarmed the whole guard.** The fence state was a
bare toggle, so an entry that opened a code fence and never closed it left every
following line counted as code - and the guard stood down for the rest of the
file. Reproduced by the integrator before any fix:

    integrate() -> ['LL-0900']      # NON-EMPTY. It reads as SUCCESS.
    LL-0901 landed as its own entry: False
    LL-0901 text swallowed into LL-0900's block: True
    exception raised: none

`LL-0034`'s defect at least returned `[]`, which looks anomalous. This returns a
success, and absorbs a whole entry into its neighbour. An unbalanced fence is
now itself a refusal.

**And the id pattern assumed today's ids.** It matched `[A-Z]{2,6}-\d{3,}`, so a
malformed heading carrying any other shape failed the heading pattern *and* the
id pattern and fell straight through into silence - lowercase, mixed case, a
one- or seven-letter prefix, two digits, or no hyphen. **`OPS-7` and `SAF-0001`
both sit outside that pattern and both exist in this repository**, so it was
never hypothetical. The shape is now permissive about all five, while still
firing only on a line whose FIRST token is id-shaped, so a sub-heading citing an
id in passing is not a false positive.

Both weakenings the pass proved were unpinned are now pinned, and all six
mutants go red: id shape narrowed -> 7 failed; fence delimiters narrowed -> 2;
unbalanced-fence refusal deleted -> 6; id matched anywhere rather than
first-token -> 2; `Path.home()` embedded in a contract -> 2; undecodable
property reading as absence -> 2. Restored: **1030 passed**.

**A new latent trap was found while writing one of those tests** - `OPS-9`,
**now CLOSED**, ledger `LL-0038`. The heading **guard** respected code fences;
the heading **parser** did not, so a *well-formed* heading inside a code block
was parsed as a real entry while a malformed one beside it was ignored.

Not hypothetical: `docs/LEDGER.md` documents its own entry format with a fenced
`### LL-0000 - ...` example, safe only because it sits **above** the marker.
Quote an example entry below the marker and it minted a phantom entry with a
real id.

Closed by giving both halves **one** `_scan_entry_region`, so there is no second
opinion left to disagree with. **A third private reader turned up while fixing
the first two** - `fragment_entry_ids` had its own `finditer` as well, and was
not in the filed defect. `_HEADING_RE` is now referenced in exactly one place.

Existing readings are unchanged: the real ledger still parses 37 entries and the
fragments still parse 3, 5, 6 and 1. Three mutants -> 3, 1 and 5 failures;
restored **1035 passed**.

**The pattern is now four for four in this module.** Every defect here has been
**two halves of one parser disagreeing** - the id race, the malformed heading,
the unclosed fence, and the guard-versus-parser split. Each time the fix was to
delete the second opinion, not to teach it the same rules.

**Namespacing was NOT implemented, deliberately** - recorded as `OPS-6`. The
safety lane's accidental `SAF-NNNN` is collision-free by construction and is a
real long-term answer, but retiring the global space changes what 30 existing
entries, and every roadmap item, branch and commit citing an `LL` id, refer to.
That is an operator decision, and detection makes it a considered one rather
than an urgent one.

## 2d. The suite is only green IN PLACE - CLOSED 2026-08-12

`OPS-4` was recorded in `LL-0021` as "path-dependent" and has now been
confirmed by an independent pass with the consequence spelled out.

`ops/lane_contract.py:render()` bakes the **absolute** `REPO_ROOT` into the
contract text, so
`tests/test_lane_contract.py::TestOnDiskMatchesTheRoster::test_the_files_on_disk_equal_what_the_roster_renders`
can only pass at `C:\Lanternlight`. In a fresh clone it FAILS - measured at
`060d48d` **and** at `548e5b6`, so it predates this session and is not a
regression. Substituting the root makes all eight lane contracts byte-equal.

**Why it matters more than it looks:** every "N passed" this project has ever
recorded, including `LL-0028`'s **927**, is true **in place** and not in a
clone. A fresh clone measures one failure. `README.md` tells a new contributor
to clone and run `python -m pytest`, so the documented first-run experience is
a red suite.

**Acceptance - MET 2026-08-12.** Ledger `LL-0033`. Closes `OPS-4`.

Of the two options the acceptance allowed, the **first** was taken and the
second deliberately refused. A test that compares modulo the root would have
gone green while leaving `C:\Lanternlight` sitting inside eight generated files
in a **public** repository, and it would have weakened the drift guard into
"equal after an arbitrary substitution". The contract now names **no absolute
path at all**: it gives the lane its worktree *directory* (`ll-lane-<id>`),
says the root is `LL_WORKTREE_ROOT` or `ops.lanes.WORKTREE_ROOT`, and tells it
to resolve the concrete path with `lane.worktree_path()` - the same function the
launcher itself calls. A path typed into a document is a guess about the
reader's machine.

**Demonstrated end to end, not argued.** A real `git clone` into a scratch
directory at a foreign path, both times:

| ref | command | result |
|---|---|---|
| `311cef8` | `python -m pytest` | **1 failed, 952 passed** - all eight lanes stale |
| `5725c03` | `python -m pytest` | **957 passed** |

`grep` for `C:\`, `/Lanternlight` and `ll-worktrees` over the **cloned**
`.claude/commands/` returns nothing.

**The guard goes red when the relativisation is removed - both halves.**
`__pycache__` purged before each run, and the anchor asserted before believing
any survivor: re-embedding the checkout path fails 3 tests, re-embedding the
worktree path fails 3, restored is 957.

Worth keeping, because it is this file's own anti-pattern caught live: **the
first mutation probe aborted on its own anchor assertion.** A heredoc mangled
the backslashes so the anchor never matched. Without that assertion the probe
would have reported a clean GREEN and been read as proof the guard was vacuous
- the exact shape of "a mutation that fails to apply looks exactly like a
passing test", hit while specifically watching for it.

**A SECOND, INDEPENDENT TRIGGER of the same defect was found and is also
closed**, and it was in nobody's plan. `lane.worktree_path()` was baked in too,
and it does **not** derive from the checkout - so setting
`LL_WORKTREE_ROOT` reddened the suite **in place**, at `C:\Lanternlight`,
where every other symptom of this item was invisible. Measured at `311cef8`:
`1 failed, 20 passed`. At `5725c03`: `957 passed`. The item was filed as
path-dependence on the *checkout*; it was path-dependence on **any** absolute
path the generator happened to see.

The new guards are **behavioural rather than substring checks** - rendering must
not change when the checkout moves, and must not change when the worktree root
moves.

**One sentence here was an OVER-CLAIM and a refutation pass refuted it.** It
said those guards catch "a path re-embedded later that nobody has thought of
yet". They do not: they pin `primary_checkout()` and `WORKTREE_ROOT`
*specifically*. The pass demonstrated it by embedding `Path.home()` and
regenerating - **1009 passed** on this machine with `C:\Users\Administrator`
committed into a contract, while a checkout under a different `USERPROFILE`
measured `1 failed, 1008 passed`. The 2d symptom exactly, invisible here.

Guarding two known sources is not the property "no machine-specific path is
ever committed", and only the second makes a clone-green claim durable. Closed
by `test_no_contract_contains_ANY_absolute_path`, which matches any drive-letter
or `/home`-style path in a rendered contract and carries its own positive
control so an empty finding is not mistaken for a clean one. Ledger `LL-0037`.

**One existing test changed shape, stated rather than quietly edited.**
`test_the_branch_and_worktree_are_named` asserted `str(lane.worktree_path())`
appeared in the text, which cannot survive a relocated checkout. It was made
**stronger** rather than relaxed: it now asserts the lane's own worktree
directory is named **and** that no other lane's directory appears, which
catches a lane pointed at a sibling's worktree. A test weakened to go green is
invisible to an exit code, so this is on the record.

**And the consequence for every earlier count.** `LL-0028`'s **927**, and 943,
and 953, and every "N passed" this project has ever written down, were true
**in place** and not in a clone. **957 is the first number in this project's
history measured from a fresh clone at a foreign path.**

## 2b. Sanitised fixture for the transient save - CLOSED 2026-08-11

Split out of item 2 rather than left implied, because it is a different lane's
work and a different risk.

The captured bytes are held **outside** the repository and are not committed.
A fixture cannot be a copy: the filename embeds the operator's roleId, so it
needs a **rename**, not merely redaction. Inside, it carries `BattleId`, the
`AutoSaveTempSlot` / `FinalSlot` names, an `IdGeneratorData.NumIdToUUID` map,
and `ownerRoleId` inside the `ItemCell` JSON - and **several of those fire no
existing `lanternlight.redact` detector**. It is also ~177 KB raw, so it needs
size reduction as well.

**Three statements in the paragraph above were WRONG and are corrected here
rather than quietly edited, because each one would have produced a leaking
fixture:**

1. **"The filename embeds the roleId" implies the bytes do not. They do.** The
   roleId appears **verbatim inside the file**, twice, as `AutoSaveFinalSlot`
   and `AutoSaveTempSlot`. A rename alone ships it. Found by the research lane.
2. **The map has 91 entries, not 23.** 23 is true of exactly 5 of the 263
   generations; the map grows monotonically from 16 to 91. A filed count is a
   hypothesis - this file's own anti-pattern, hit twice more this session.
3. **The `LONG_ID` floor makes same-length substitution useless.** The rule is
   `\d{15,}` - length only - so an authored 19-digit id fires exactly like a
   real one. Every identifier has to get SHORTER, which changes FString
   lengths, which is why the serialiser in `LL-0023` had to exist first.

**And a fourth hazard that was in nobody's plan.** The save carries a **third
party's display name** in plaintext - `KillPlayerHistoryDatas.PlayerName`, plus
`MsgSubChannelString` and `MsgAppearanceString`. Measured: **no content rule
can reach it.** Keyed rules are structurally blind because GVAS writes the key
and the value as separate length-prefixed strings with no separator, persona
discovery returns zero candidates, and a display name has no shape to match. The
safety lane's answer is a **structural** rule, `NAME_FIELD`, which recognises
the property and demands an authored-value marker beside it.

**The trap inside that hazard, and it is the sharpest thing this item found.**
Those bytes are refused today - but **only** because a Blueprint GUID beside
them trips `PRODUCTUSERID`, which is a **false positive**. The false positive
was accidentally load-bearing. Authoring the GUIDs, which this item **requires**
in order to clear that same false positive, removes the only thing standing
between a stranger's name and a public repository. A remediation that opens a
hole is worth more written down than any number here.

Related and newly measured (`SAF-3`): inventory instance ids share a
**12-digit prefix** with the operator's roleId, so masking the roleId alone
does not mask them and each one leaks that prefix.

**Acceptance - MET 2026-08-11.** Ledger `LL-0023` through `LL-0027`. Every
criterion below was re-measured by the integrator rather than relayed.

`tests/fixtures/gvas/standalone_slot.gvas.b64`, **19,867 raw bytes** from a
177,878-byte source, built by the committed
`tests/fixtures/build_standalone_slot_fixture.py` and reproducible byte for
byte on a second run.

- parses with `undecoded_trailing == b""`, `is_complete`, zero unknown
  properties, 17 top-level properties
- `serialise(parse(fixture)) == fixture`
- sha256 collides with none of the 7 live saves and none of the 273 captures
- `iter_sensitive` returns **empty** under `FILE_SCAN_LABELS` **and** under the
  stricter `ALL_LABELS`; `iter_encoded_sensitive` over the committed base64
  returns **empty**
- **POSITIVE CONTROL, which is what makes those zeroes mean anything.** The
  same scans over the pre-sanitised source: **882 plain findings**
  (PRODUCTUSERID 772, LONG_ID 100, OWNER_ROLEID 3, NAME_FIELD 3, SAVE_SLOT 2,
  ACTOR 2), **96 through the encoded pass**, **21 on the base64 text itself**.
  Fixture: 0, 0, 0. A clean result and a dead scanner are otherwise identical.

**Three things the build discovered that no plan anticipated:**

1. **The authored decoration width is load-bearing, not cosmetic.**
   `iter_encoded_sensitive` decodes each base64 **run** separately, so a
   76-column fixture is scanned as 57-byte windows. `NAME_FIELD` needs
   `len(name)+17` bytes present and goes quiet only if the marker follows
   within 64, and no 57-byte window holds both unless the decoration is at
   least 27 characters. An 11-character first attempt was refused by the
   builder's own gate.
2. **24 zero bytes encode to 32 `A` characters, and `A` is a hex digit.** So an
   all-zero native `Vector` payload makes the committed TEXT trip
   `PRODUCTUSERID` while the save it encodes is clean. Three payloads hit this
   and no choice of entries avoids it. The builder authors those payloads and a
   new test guards the whole fixture directory.
3. **It is 19,867 bytes, not the under-10 KB the spec asked for, and the reason
   is measured rather than conceded.** 12,972 bytes are tag overhead - 5,046
   property names, **7,311 recursive type names**, 615 size and flag fields
   across 123 tagged properties. Those type names are the game's own struct
   identities and package paths; authoring them down would be lying about what
   the game writes. The JSON the spec expected to dominate is 2,964 bytes.
   Reaching 10 KB means dropping a container the brief required, so the brief
   won. Recorded as `ING-12` for whoever decides otherwise.

**Kept verbatim, stated rather than hidden:** game config ids and counts in the
item JSON, the non-zero native struct payloads, the in-run damage numbers and
timestamps, and the `LevelDetail` / `BotSpawnerData` values. None is an
identifier under any detector.

**A P0 WAS FOUND IN THE GUARD AFTER THIS ITEM WAS CLOSED.** Ledger `LL-0029`
and `LL-0030`. The fixture was, and remains, clean - verified by direct scan
and by an independent scan of all 113 blobs on the pushed remote. **Nothing
leaked.** What was broken was the protection: `redact()` rewrites the Blueprint
decoration to `<PRODUCTUSERID>`, `NAME_FIELD`'s anchor required
`[0-9A-Za-z]`, and angle brackets are not alphanumeric - so **redacting a file
disarmed the rule**, and `assert_clean(redact(raw))` approved bytes still
carrying a third party's display name verbatim.

That is the second time in one session that a **remediation opened the hole it
was cleaning** - the first being that authoring the GUIDs removes the false
positive which was accidentally the only thing refusing the same record. Two
instances is a pattern, not a coincidence, and the pattern is: **check what
your fix removes, not only what it adds.**

Fixed by matching the decoration as a run of units where a unit is either one
alphanumeric character or a whole placeholder taken from the module's own
constants, so a placeholder added later cannot silently disarm it again.

### The original acceptance, for the record

**Still unidentified:** the 4 zero bytes after every tagged property list. An
`int32` zero, an empty FString and four zero flag bytes all fit and nothing
observed separates them, so they are handed back as `GvasSave.epilogue` rather
than named.

## 3. Live log tail - CLOSED 2026-08-12

`MistfallHunter.log` appends while the game runs - 567 KB in the first ten
minutes. A tail that follows it and emits structured events is the spine of
every live feature that could ever exist here.

Port **8811** is reserved for this. The tail must handle the file being
truncated or replaced on game restart, and must never hold a lock that could
affect the writing process.

**Acceptance:** the tailer follows an appending file, survives truncation and
rotation without dropping into a spin, emits parsed events for the line shapes
already known (`setClassGender inclassid`, `OnRep_WeaponCfgId`,
`server_refreshKnightFeature`, `match state changed to`, `match id`, map and
sublevel transitions), and passes every event through the redactor before it
reaches any sink. Tested against a synthetic appending file, so the suite does
not need the game.

**Acceptance - MET 2026-08-12.** Ledger `LL-0045`. `lanternlight/tail.py` with
49 tests, plus five new recognisers in `lanternlight/logparse.py`. Suite **1196
passed, 1196 collected, ruff clean**, measured by the integrator with
`__pycache__` purged; the baseline before the work was **1108**. Port 8811
stays reserved and **unbound** - the acceptance asked for a library and nothing
binds a socket.

**Three things were measured that no plan anticipated, and each changed the
design rather than decorating it:**

1. **`st_ino` is preserved across in-place truncation and changes on
   delete-and-recreate.** So file identity alone cannot see a truncation, and
   size alone cannot see replacement by a larger file. Both checks are kept for
   that reason, and the size-only degradation when the inode reads zero is
   written into the docstring and pinned by a test rather than left as prose.
2. **The log carries 594 embedded control characters** - 98 VT, 106 FF, 113 FS,
   85 GS, 97 RS, 95 NEL. `str.splitlines()` treats every one as a line break
   and the file does not, so a reader that decodes before splitting fragments
   lines at all 594. **The integrator first stated this as a hazard of
   `splitlines()` and was corrected by measurement:** `bytes.splitlines()` does
   **not** split on them, only `str.splitlines()` does. On
   `b"A\x0bB\x0cC\x1cD\x85E\nF"` the counts are bytes **2**, str **6**,
   `split("\n")` **2**. The hazard is the decode-then-split **order**, not the
   method name - established because the first mutant, written against the
   method name, **survived**. Worth keeping: the event **count** does not catch
   that mutation, because the first shard keeps a complete header and still
   parses. Only the exact emitted text does.
3. **`MapTransitionEvent` was pointed at the wrong lines all along.** It fires
   on `at world`, and **all 4408** of those are `TS.UI` widget lines, while it
   recognised **0** of the 44 real `[LevelSwitch]` map changes. It is **not**
   renamed or weakened - that is public API and a separate decision - but its
   docstring now says outright that it is not a transition, and
   `LevelSwitchEvent` is the type that answers "did the map just change".
   Note one user-visible map change emits **four** `LevelSwitchEvent`s (11
   switches, 4 verbs, 44 lines), so a consumer that counts events counts four
   times too many.

**A documented never-raise contract was already broken on `main`, and the
independent refutation pass is what found it.** `parse_line` and `iter_events`
are documented never to raise; an unbounded digit run made them raise
`ValueError`. Six conversion sites were involved - three added this session,
one in the **header's own `frame` group** so the input reached `parse_line`
before any recogniser could see it, and **one pre-existing on `main`** via
`_eqeq_fields`. `_as_int` is now the module's only integer conversion: an
unreadable **required** field drops the event, an unreadable **optional** axis
is omitted and the event survives.

**The refutation pass returned "not safe to merge as-is" and was right.** It is
recorded because a green suite could see neither defect, and because it
corrected the integrator three times - see `LL-0045` for all three, the sharpest
being that a shape count collapsed per digit **character** counts id **widths**
rather than shapes.

**And one integrator verification was itself vacuous.** The first probe of the
tailer's redaction reported zero personas surviving while emitting **zero
events**. Re-run with a positive control - 4 lines fed, 4 events emitted, 4
personas in the raw text, 0 surviving - the property holds. But naive per-line
redaction also scores 0 on those same four lines and the tailer learned 0
personas doing it, so **the persona-accumulation design is correct but not yet
load-bearing on this log**. It is kept because the leaking shape exists and any
new recogniser makes it reachable, and the docstring says exactly that rather
than claiming credit it has not earned.

## 4. `AvgPrice` market cache - PARSER DONE, watcher still to build

**The file filled.** Measured 2026-08-09: 37 bytes to 343 bytes, carrying
`[PriceTime]` plus 30 `cfgId=price` rows. The moment that only happens once has
happened, and the schema is now known rather than awaited.

Landed this cycle: `lanternlight/avgprice.py`, tests, and a committed fixture
byte-identical to the real file. Also fixed `lanternlight/paths.py`, which
pointed at `<Saved>/Config/WindowsClient/AvgPrice.ini` - wrong parent directory,
wrong platform subdirectory (the real one is `Windows`) and wrong filename - so
`find_avg_price_ini()` returned `None` on a machine where the file plainly
existed.

Two findings worth keeping. The old "37 bytes and empty" state was **not** an
empty file: `[PriceTime]` + a 10-digit stamp + `[TradePrices]` is exactly 37
bytes under LF, so it always had both headers and a stamp with zero rows.
And the write is triggered by **returning to camp**, not by trading and not
continuously - the file was written **0.975s** after the camp level-switch that
followed a successful escape (14:53:35.681 to 14:53:36.656), with
`CampData_<userId>.sav` 1.010s after that. An earlier draft said 1.7s, which
came from subtracting a truncated whole second from a fractional one.

**Remaining acceptance:** a watcher that snapshots the file on change with a
timestamp and never writes to it. Given the measured trigger, it should expect a
burst at camp re-entry and silence otherwise, and a poll interval chosen against
that rather than against a guess.

## 4b. Ammo-family and talent measurement - READY, cheap, needs the client

Opened 2026-08-09 after the talent and skills screens were captured. The class's
whole kit is gated on ammo families, and the following are **unmeasured**:

- Whether "carrying at least 2 Archer's Arrows" counts equipped **types** or
  available **charges**. At level 2 the operator has both, so the capture cannot
  separate the readings.
- How arrows are acquired at all - loot, craft or vendor. Everything about which
  family a player holds first currently rests on the tree's unlock ordering
  (Archer's Lv. 3, Hunter's Lv. 6) as a proxy.
- How `roll` differs from `dodge`. Both Dodge nodes say they convert one to the
  other and neither says how they differ, and the class's effective range is
  counted in dodge-lengths.
- The three locked Archer's Arrows and all five Hunter's Arrows.

**Acceptance:** each answered by observation and recorded in
`docs/OBSERVED_IDS.md` with its method, or written up as a measured negative
naming what was tried. A guide site does not close any of these.

## 5. Sorcerer single-weapon question - OPEN

Four classes surfaced two weapon config ids in character creation, two surfaced
one (`docs/OBSERVED_IDS.md`). Blackarrow's single id independently corroborates
the official statement that its second weapon ships in a future season.
**Sorcerer's single id has no such explanation.** Either Sorcerer is genuinely
single-weapon, or its second weapon simply was not surfaced during that walk.

Until this is settled, nothing in this repo may state that Blackarrow is the
only single-weapon class.

**Acceptance:** either a second Sorcerer `holding-` id observed and recorded, or
a deliberate re-walk of the Sorcerer creation screen that surfaces none, written
up as a measured negative with the walk described. A wiki claim does not close
this.

## 6. Weapon-stance toggle probe - OPEN, did not produce a result

Step 4 of the original capture plan - hold on one class, cycle the stance
toggle, watch whether the `holding-` id changes - **ran and produced no
distinguishable event.** That is a failed probe, not evidence either way.

The pair-versus-singleton reading currently rests on the class carousel instead,
which is indirect for the stance question specifically. It is consistent with
the published weapon kits (Mercenary hammer plus sword-and-shield, Shadowstrix
dagger plus dual blades) and it refutes the gender-variant hypothesis, but it
does not directly show a stance toggle changing an id.

**Acceptance:** a re-run where the toggle is exercised slowly and repeatedly on
a single class with the frame poller running, yielding either a `holding-` id
change joined to the toggle input, or a documented negative stating what was
tried and over how many attempts. Note item 1 may answer this incidentally - the
toggle may be more legible in a raid than on the creation screen.

## 7. Emberforge is NOT blocked - the save records damage - READY, high value

Opened 2026-08-11. This item exists because the "deliberately not on this list"
section at the bottom of this file was **wrong**, and it was wrong in the
direction that cost the most: it said Emberforge cannot be filled until numbers
exist, and named item 1 as the only unblocker.

**Measured this session, first-party, from bytes already on disk.** The
transient save carries `DamageCollectonDataSet`, a JSON array of per-source
damage records. Each entry has `sourceType`, `monsterId`, `monsterGuid`,
`bDeathCauser`, `totalDamage`, and a `damageChildList` of individual hits. Each
hit carries `damageValue` (a float), `timeStamp` (a Unix epoch float with
sub-millisecond resolution), `nameId`, `Key` and `bChildDeathCauser`.

Two consecutive hits on one target in the captured run measured 17.356201171875
and 92.13079833984375, 0.256 seconds apart. Those are the first damage numbers
this project has ever held, and nobody published them - the game wrote them.

**263 generations of that file are already captured** at `C:\ll-captures\saves\`,
so a damage timeline for a whole 20-minute run exists right now without the
operator doing anything.

Two properties of the field are measured and constrain any reader:

- It is a **rolling window, not a cumulative log.** Summed `totalDamage` across
  generations went 74.66, 251.20, 137.52, 89.09, 89.09, 227.94 - it falls as
  well as rises, so entries age out. A reader must accumulate across
  generations and must not treat one snapshot as a run total.
- `nameId` was **0** on every hit observed. If `nameId` binds to the ability
  that dealt the damage, that is damage-per-ability and it is the single most
  valuable binding available to Emberforge. It is **unmeasured** - 0 may mean
  basic attack, or unset. Do not assume.

**EXTRACTED 2026-08-11.** All **263** generations parsed, **424** window
readings deduplicated by `(monsterGuid, timeStamp, damageValue)` down to
**21 distinct hits** over a **1020.344-second** span. Damage ranged 9.745483 to
137.517426 against **8 distinct monsterIds** (1005, 1006, 1014, 1029, 2003,
2007, 2017, 2021) across 9 monster instances.

**RE-DERIVED INDEPENDENTLY 2026-08-12 by the integrator, and it corrected two
filed counts.** Every headline above held on re-measurement - 263 parsed with
zero failures, 21 distinct hits, 1020.344 s, the same 8 monsterIds, 9
instances, total 1284.835785, and all three repeat groups with their gaps. Two
things did not:

1. **The deduped-from count was 278 and is 424.** This document said "**278**
   window readings deduplicated by `(monsterGuid, timeStamp, damageValue)`",
   and then said "`nameId` is 0 on all **424** readings" a few paragraphs
   later - two numbers for one quantity, in one item. Both are real and they
   count **different things**: summed across generations there are **278
   top-level entries** (one per monster instance per generation) and **424
   child hit readings**. The dedup key is a **child-level** key, so the number
   being deduped is 424. The sentence paired the right operation with the
   wrong count. A filed count is a hypothesis - this file's own anti-pattern,
   and the correction matters because an extractor test encoding "278 deduped
   to 21" would freeze a wrong intermediate.
2. **It is 262 generations carrying the field, not 263.** The **first**
   generation - 2,190 bytes, the smallest, written at match start before any
   combat - does not carry `DamageCollectonDataSet` **at all**. The property is
   **absent**, not present-and-empty. That is a fact worth keeping rather than
   smoothing over: the field is created when the first damage lands, so
   "unmeasured" and "measured zero" stay distinguishable on this surface
   exactly as the measurement doctrine requires, and a reader must treat a
   missing property as normal rather than as a parse failure.

**The load-bearing result: damage is DETERMINISTIC, not rolled.** Three values
repeat exactly, and every repeat has a distinct timestamp, so none is a
deduplication artifact:

| value | hits | detail |
|---|---|---|
| `9.745483398` | 5 | one monster instance, gaps 1.712, **1.501, 1.499, 1.499** |
| `83.740417480` | 3 | monsterId 2003, across **two different instances** |
| `30.472595215` | 2 | gap 1.709 |

**Both halves of that were overstated, and an adversarial pass corrected them.**
Kept visible rather than edited away, because the overstatement is instructive:

- **"a float to nine places" is wrong.** Every value is exactly `float32`; the
  ULP at 83.74 is 7.6e-6, so a repeat pins about **7 significant digits**, not
  9. Still far too tight for a per-hit roll, but say the true number.
- **The five repeats of `9.745483398` are ONE computation, not five.** They are
  the 1.5-second tick itself, so counting them as independent evidence
  double-counts. The genuinely independent evidence is a single fact:
  `83.740417480` landing identically on **two different instances of the same
  monster type**.
- **"the first timing constant this project has measured" is too strong.** It
  is n=3 intervals, from one monster instance in one encounter, at a 1 ms
  quantisation floor. It is a strong lead, not a constant.

**Three negatives, each worth as much as the positives:**

- `nameId` is **0 on all 424 readings** in every one of the **262** generations
  that carry the field, and `Key` is empty on all 424. So the save's window
  carries no attribution
  at all, and the ~1.5 s interval cannot be attributed from the save alone.

  **PROBABLY the same id space as `SkillNameId` - a strong hypothesis, NOT
  proven.** The value `6130017` appears as `skillNameId` in the log's
  kill-history payload and as `nameId` inside a `damageChildList` in the same
  log. An earlier draft of this item called that "proven" and "not inferred".
  **Both were over-claims and an adversarial pass refuted them:**

  - **n = 1.** `skillNameId` has exactly **one** distinct value in the entire
    12.7 MB log. One shared value between two fields is a strong lead, not a
    demonstration that the spaces coincide.
  - **`6130007` never appears as a `skillNameId` at all**, so the overlap is
    not reciprocal on the sample available.
  - **"from the same component family" was simply WRONG.** `skillNameId` is
    emitted by `leaderRankScoreComponent`, `battleSnapUpdate` and
    `battleSettlement` - **not** by `DamageCollectionComponent`. That sentence
    asserted a shared provenance that does not exist, which is exactly the kind
    of detail that makes a weak claim read as a strong one.

  `nameId: 0` still most likely means **unset**. Closing this needs a second
  distinct `skillNameId` seen also as a `nameId`.

## 7a. The log carries what the save's window does not - MEASURED 2026-08-11

The log's `[DamageCollectionComponent]: jsonString:` emits the **same structure**
the save stores in `DamageCollectonDataSet`, but with `Key` **populated** where
all 424 save readings had it empty. That makes the log the attribution surface
and the save the sampling surface.

**Three id-to-name bindings, first-party, read off the game's own emission:**

| id | Key | range |
|---|---|---|
| 6130017 | `NormalArrow` | `613xxxx` - player ability |
| 6130007 | `ExplosionArrow` | `613xxxx` - player ability |
| 6250000 | `MonsterDamage` | `625xxxx` - monster as source |

No Key maps to two ids and no id maps to two Keys across the sample. These are
the first ability bindings the project holds, and they are **distinct from the
`1205xx` ammoId space** already recorded, so ability and ammo are not one space.

**`sourceType` is the direction flag, and it is now read rather than guessed:**

- `sourceType: 0` - `monsterId` is **null** and the Key is a player ability.
  The **player** is the source.
- `sourceType: 1` - `monsterId` is **populated** and the Key is `MonsterDamage`.
  The **monster** is the source.

**CONSEQUENCE, and it inverts the natural reading of item 7's series.** All 21
extracted hits carry `sourceType: 1` with a populated `monsterId`, so they are
**damage the operator TOOK**. This was written as a strong inference from a
single log payload; it has since been **CONFIRMED independently** by the
`PlayerData.Hp` join in item 7 above, which is first-party and does not depend
on the log at all.

**One caveat on generalising the log half.** The only `sourceType: 1` payload
in the log carries `monsterId` **99021**, which appears **once** in the whole
log against 105 mentions of the `1xxx`/`2xxx` space. It looks like a synthetic
death-source bucket rather than a real monster, so its semantics should not be
stretched. The direction conclusion does not rest on it any more - the Hp join
carries it.

**Also measured here:** the log emits **one payload per death event** with
`bDeathCauser: true`, so the log holds the killing blow that the save's rolling
window drops. A reader that wants complete combat needs both surfaces. And a
new monsterId, **99021**, appears only as the source that killed the operator -
a range no other observation has touched.

**SAFETY, routed to the safety lane:** the log line adjacent to these payloads
carries the operator's persona in a bare `name:` field, and the kill-history
line carries a third party's `playerName` **in CJK**, confirming `SAF-4` on a
second surface. No excerpt of this region may be committed, and the
`DamageCollectionComponent` region is now a named redaction target.
- `bDeathCauser` and `bChildDeathCauser` are **False on all 21**, yet the run
  recorded kills. So `DamageCollectonDataSet` is **not a complete combat log** -
  it drops or rotates out the killing blow.
- `sourceType` is **1** on all 21 and `Key` is empty on all 21. One source type,
  no key. Whatever those fields discriminate was never exercised here.

**DIRECTION - SETTLED 2026-08-11. These are damage the operator TOOK.**

Not an inference and not from the log. The answer was in the captured bytes the
whole time, in a **second field of the same file**: `PlayerData.Hp`, sampled
262 times across the run.

- **13 HP drops, totalling 1286.**
- **21 damage hits, totalling 1284.84.**
- The 1.16 gap is integer rounding across 13 drops, and the drops pair to hits
  **individually**: 108.53 + 83.74 = 192.27 against a 192 drop, 17.36 + 92.13 =
  109.49 against a 110 drop, 137.52 against 138, 89.09 against 89.
- **No HP drop is unaccounted for.**

Found by the adversarial pass and re-measured independently by the integrator.
An earlier draft of this item left direction open and called it the blocking
question; it was answerable from data already on disk, and the reason it stayed
open is that nobody joined the two fields.

**AND THIS IS THE DEFLATING PART, which matters more than the result.** The 21
hits are **incoming** damage. Emberforge needs **outgoing** damage - what the
player's build does - and the save's rolling window does not carry it. So:

- Everything above describes what monsters do to the player. It constrains
  survivability, not build math.
- **Outgoing damage exists, but only in the log**, in the four
  `DamageCollectionComponent` payloads at `sourceType: 0` - `NormalArrow` at
  409.03, 278.26 and 378.79, `ExplosionArrow` at 273.22. Four samples, emitted
  at kill events, WITH ability attribution.
- So item 7's headline holds but shrinks: Emberforge is unblocked by the
  **log**, at four samples, not by the save at twenty-one.

Item 7b is now more important, not less: the training ground is the only route
to outgoing damage in quantity, and `sourceType: 0` is what to look for.

**Remaining acceptance - MET 2026-08-12 for the shipped-code half.** Ledger
`LL-0035`. `lanternlight/damage.py`, owned by **ingest**, with 37 tests.

- **A home in a lane.** Ownership declared in `ops/lanes.py` and the contracts
  regenerated. This was `OPS-2`'s second option - the integrator declares it at
  merge - taken deliberately, because the orphan guard goes red the moment the
  file exists, so the file and its ownership cannot land separately. **`OPS-2`
  is now CLOSED** (`LL-0041`) with a third option that neither of its two
  offered: a lane may **claim** a path in its own `STATE.json`, the orphan
  guard honours exactly one claimant, and the claim goes **stale** - failing
  the suite - once the roster absorbs it. That works for a lane running alone,
  which is what the two filed options did not.
- **Tests.** The JSON shape is characterised against the **committed fixture**,
  which does carry `DamageCollectonDataSet` (one record, one hit), so no
  out-of-repo data is needed to ship or to test. Cross-generation dedup is our
  logic rather than the game's, so it is tested on authored generations.
- **Timestamps joined to wall-clock - and the join found a trap.** See below.
- **Verified end to end** against all 263 captures, the shipped module
  reproducing the scratch analysis exactly: 262 generations with payload, 424
  readings, 21 distinct hits, 1020.344 s, total 1284.835785, the same 8 ids, 9
  instances, direction `monster` only, `nameId` 0 only.

**`timeStamp` IS NOT A UNIX EPOCH. It encodes LOCAL wall clock as though it
were UTC.** This was in nobody's plan and it silently breaks every join between
this surface and the log.

Measured on two independent surfaces:

- The capture files' own **mtimes** put the run at **22:27:00 to 22:46:54 UTC**
  (17:27 to 17:46 local, machine at UTC-5). Reading the hit timestamps as an
  epoch renders them **17:28:10 to 17:45:11 "UTC"** - five hours *before* the
  run began, which is impossible, and numerically equal to the run's **local**
  clock.
- The **log**, which timestamps in real UTC and emits the same payload:
  across 5 readings at **three separate times of day**, log-UTC minus
  timestamp-read-as-epoch is **18009 to 18015 seconds**, i.e. 5.0025 to 5.0041
  hours. Exactly the operator's offset, plus a few seconds of event-to-emission
  lag - and the lag is positive, which is the physically correct direction.

So `as_local_naive()` returns a **naive** datetime, and `to_utc()` **refuses**
without an explicit offset rather than inventing one. The offset is a property
of the machine that played, is absent from the save, and moves with daylight
saving. With the offset supplied, the first and last hits land at 22:28:10 and
22:45:11 UTC - both inside the mtime-measured window, which is the join working.

**Still open on this item:** no damage coefficient may be published until the
same value is seen from an **independent run** - one run cannot separate a
coefficient from a lucky repeat, however precise. Nothing here computes one.

**A sampling limit to design against:** 424 window readings over ~20 minutes of
play yielded only 21 hits, because the window holds roughly two monster entries
at a time and combat rotates them out fast. Most of the run's combat was never
observed. Polling faster will not fix a window that small - this is a ceiling
on what this surface can ever give, and it is an argument for the controlled
environment in item 7b rather than for a faster poller.

## 7b. Training grounds as a controlled measurement rig - READY, needs the client

Opened 2026-08-11 from third-party player testimony (see item 8), and it is the
cheapest unblocker on this list.

The game ships a **training ground** where the host can spawn bots of chosen
class, difficulty and gear quality, freeze them, and restore their own health
and consumables. If that is accurate, it is a repeatable, zero-stake
environment with a controlled input - which is exactly what item 7 needs to
turn a damage number into a coefficient. Every previous plan for measuring
combat math assumed a real run, with its gear loss, its variance and its
single-attempt sampling.

**This claim is UNVERIFIED.** It comes from one creator's video and no
first-party observation here has seen the training ground at all.

**Acceptance:** enter the training ground with the log tailing and a frame
poller running, and record whether (a) it exists, (b) `DamageCollectonDataSet`
is written there at all - it lives in `StandaloneSlot_<roleId>.sav`, which is
created at match start, and a training ground may not be a "match", so this may
be a clean negative - and (c) whether a repeated identical attack yields an
identical `damageValue`. A written negative on any of the three is a result.

## 8. Third-party data sources - reviewed 2026-08-11, tier and provenance fixed

Reviewed at the operator's request. Recorded here so the assessment is not
re-done, and so nothing absorbs these as facts by accident.

**`questlog.gg` is DATAMINED, not hand-mapped.** Measured, not inferred: its
monster database is addressed by numeric id at `/db/monster/<id>` in the same
id space this project observed in the save's `Id2cnt` maps, and its listing
carries developer-internal rows no player can ever see - a
`[Debug]OrdinaryMonsterTemplate`, a `Test Dummy Monster` and a `[Discarded]`
entry. A wiki built from play cannot contain a discarded placeholder. Its
category slugs are internal too: the UI says "Greater Elite" while the URL says
`BigElite`.

The consequence is **not** that we use it more, and **not** that we relax
[ADR-002](docs/adr/ADR-002-no-asset-extraction.md). Someone else decrypted the
paks; this project still does not, and nothing about that changes. What it
means is that the site is a **hypothesis and cross-check source**, tier 4, and
that an id learned there is **never** written into
[`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) as an observation. A
**contradiction** between their table and our measurement is a real result and
is worth chasing; an agreement is not corroboration.

**One cross-check already ran and held.** Their `1029` is "Hallowgrove
Woodling". This project independently measured `1029` in the save's
`TeamKillMonsterData` on a run the operator attested was Hallowgrove, whose
internal map is `Whitewoods_Day` with the save's own zone key
`WhiteWoodsOutskirts`. Their player-facing name and our internal name agree
from opposite directions, which is worth something precisely because neither
was derived from the other.

**A second map name is now known and unmeasured here: `Brandrgarde`.** Their
Brandrgarde (South) layer counts 316 treasure chests, 63 extraction points, 327
enemies (2 Boss, 4 Greater Elite, 22 Elite, 68 Mini-Elite, 231 Normal), 13
merchants and 9 quest interactables. **None of that is recorded as fact here.**
It is a set of expectations to test the first time the operator loads that map,
and the useful form of the test is the count, because a count that disagrees is
immediately informative.

**A live example of why the word matters.** That site says "Extraction Point".
The game says **escape**, and `extract` appears zero times in the log - already
recorded under item 1. Anyone grepping the log for a term learned from a map
site gets a clean negative that means nothing.

**`gamerguides.com` is HAND-MAPPED, and it is a DIFFERENT provenance from the
site above.** Its maintainer states it plainly in the announcement thread: a
small team "filling them out as we play", with a "Suggest Markers" function for
readers to add their own findings. So it is **first-party player observation,
crowd-sourced** - a higher trust tier than a datamined dump for anything about
where a thing actually is, and a **lower** one for completeness, because
whatever nobody has walked past yet is simply absent.

Two caveats the maintainer volunteers, and both matter more than the maps:

- **Its database's first iteration was built on the DEMO.** A demo-derived
  table is stale by construction against a shipped build, and this is
  self-declared rather than inferred. Nothing from that database may be treated
  as current without a first-party check.
- **They are "being mindful of randomization"**, which implies spawn or loot
  randomization exists. That is a game-mechanic claim from a credible source
  and it is **UNMEASURED here**. It also means a hand-placed marker for
  randomised content is a probability, not a location - so a marker that fails
  to match observation refutes nothing on its own.

Also from that thread, unmeasured here: **Brandrgarde has North and South
layers**, and **Chaos Mode gets its own map layers**, which implies difficulty
changes map content rather than only scaling it. If true, `roomModeId` or
`matchType` in the map URL is the axis that selects it - see item 1, which
already established that four axes exist and that `matchId` is not the
discriminator.

**The general rule this item exists to fix:** "third-party site" is not a trust
tier. Two sites for the same game, reviewed on the same day, turned out to have
opposite provenances - one datamined from encrypted assets, one walked by hand.
They fail in opposite directions and must be cited differently. Check how a
source was built before quoting it, every time.

## 9. `cdkey` was invisible to the redactor - CLOSED 2026-08-12

Opened 2026-08-12 by the integrator, closed the same day. Ledger `LL-0046`.
Nothing leaked and nothing raw is committed. **What was broken was the
protection** - the same shape as item 0 and `LL-0029`, and the third time in
this project that a guard has certified text it had no basis to certify.

The state before, re-measured by the integrator rather than relayed:

    lines matching the key or its abbreviation : 7
    VALUE-BEARING tokens                       : 5
    tokens SURVIVING redact()                  : 5 of 5
    assert_clean() certified                   : 7 of 7 lines

That last line needs the qualifier it was first written without: **7 of 7 is
true of REDACTED lines**, which is what was measured. On RAW lines the guard
already refused 4 of the 5 token-bearing lines for unrelated labels. The
vacuous-guard finding stands - the code itself survived the sanctioned path
untouched - but the number was imprecise. Corrected in `LL-0047`.

**Acceptance - MET 2026-08-12.** Suite **1222 passed, 1222 collected** at the
moment of closure, ruff clean, `__pycache__` purged; the baseline before the
work was **1196**. The follow-up in `LL-0047` added one test, so the suite is
**1223** today - re-measure rather than quoting either number, because both are
snapshots and this file has been wrong about a count five times already.

- **The `CDKEY` rule masks all four measured positions** - the bare word plus a
  space, `key=value` in a comma list, a query parameter in the redemption URL,
  and JSON. After: **0 of 5** survive, `assert_clean` **refuses** all five
  token-bearing raw lines, redaction stays idempotent on the whole 12.8 MB log,
  and the rule fires on **0 of 118** tracked files.
- **A positive control** proves the detector fires when injected in each of the
  four positions, so a zero finding cannot be confused with a dead scanner.
- **The `/Game/` anchor is pinned** - see below, because it was not.
- **The `device_id` / `user_unique_id` decision is taken**, with the
  token-level check the acceptance demanded.

### The filed count of 9 was wrong, and the reconciliation is the useful part

This item said "candidate tokens found: 9". It is **5**, confirmed by two
independent probes and reconciled by a third. The 9 came from a probe that read
the ordinary word after a **CamelCase mention** of the key as though it were a
value: 5 real tokens plus 4 innocent neighbouring words. No value-based method
yields 9 on this log.

So the acceptance's own wording, "masks the token in all 9 observed positions",
was **wrong on its face** - there are **4 positions and 5 occurrences**. A
detector built against that wording would have been hunting four tokens that do
not exist. A filed count is a hypothesis, for the fifth time in this file.

Also corrected: this item recorded `assert_clean` certifying "6 of 6". Both are
true and they count different things - 6 is the lines matching the full
spelling, 7 is the lines matching the abbreviation as well. One of those 7 is a
**false positive**: a three-letter fragment inside a run of binary garbage.

### Why the value is shaped, and the measurement that corrected the reason

`RULES` runs over every tracked file, and the key is an ordinary noun in this
repository's own prose - the roadmap, the ledger, the wakeup notes and
`logparse.py` all discuss it in sentences. A rule taking the next word masks
"parameter", "and" and "tokens" and reddens the tree scan on every commit. The
abbreviation is deliberately **not** a key for the same reason: this file
writes it followed by spaces and a colon inside a code block, which a keyed
rule reads as a key and a value.

The slice first wrote that **the digit requirement** was what kept the rule off
prose. A mutation **refuted** it: dropping the digit left the tree scan green,
because the words following the key today are 3 to 9 characters and the
**length floor** stops them. But "configuration", "documentation" and
"implementation" all clear the floor on their own, so the digit is what
separates a code from a long word - it is load-bearing for a case the tree does
not currently contain. Such words are now in the tests, so removing the digit
goes red. A guard that is green only because the corpus happens to be kind is
not proven.

**The accepted blind spots are in the module docstring and pinned by tests:** a
purely alphabetic code, and a code shorter than the floor, are **not caught**.
Stated rather than hidden, because a caveat dropped from the artifact is a lie
in the artifact.

### The `/Game/` anchor test existed and did NOT pin the anchor

This is the sharpest finding of the item, and it came from refusing to accept
that an existing test met the clause. `test_a_non_game_url_with_a_query_is_not_a_map_url`
shipped in `LL-0045` and looks exactly like the test the acceptance asked for.
Mutation-probed, each run with `__pycache__` purged and the mutation asserted
present on disk before any survivor was believed:

| mutation of `_MAP_URL_TARGET_RE` | before |
|---|---|
| relax to a bare `/<path>?` | KILLED |
| add `re.IGNORECASE` | KILLED |
| drop the trailing slash, `/Game` | **SURVIVED** |
| truncate to `/G` | **SURVIVED** |
| widen the class to admit `-` | **SURVIVED** |

The committed stand-in used a **lowercase** path, so the only properties
actually pinned were case-sensitivity and a leading `/G`. Three plausible
weakenings were invisible. On today's log none of them is a leak - `/Game/`,
`/Game` and `/G` all match the same 36 lines - so the guard was real while its
own comment overstated what it pinned, which is the kind of comment a future
maintainer relies on.

Four cases added, each paired with a **positive twin** one character or one
word away whose exact `target` is asserted, so no rejection rests on a bare
negative. All five mutations are now KILLED.

**One of those four does not earn independent coverage, and says so.** The wrap
refutation found that `test_a_path_starting_with_g_but_not_game_is_not_a_map_url`
has **no unique kill** - under every natural truncation the trailing-slash test
fails too. It is kept, because it asserts a distinct property and a contrived
anchor such as `/G[a-z]*/` would separate them, but the test now states outright
that it is not independent mutation coverage rather than reading as though it
were. `LL-0047`.

### The follow-up, `LL-0047` - what the wrap refutation found after this closed

The refutation returned **CONFIRMED on all six** claims above and then found
three defects, all now closed. Two are worth carrying:

- **Dead regex.** A placeholder lookahead in `_CDKEY_VALUE` could never fire,
  because `[A-Za-z0-9]` cannot match `<`. Deleting it left the suite green,
  which is what proved it dead. Removed rather than pinned.
- **A comment crediting the wrong condition - and it took THREE wrong answers
  to fix.** Asked what keeps the rule off a CamelCase mention of the key, the
  integrator wrote that the `\b` boundary does it (refuted - deleting both
  boundaries left the suite green), then that the separator does it (refuted -
  making it optional left the suite green), then that the two together do it
  (refuted - removing **both** still left the suite green). The real answer is
  the **value shape**: the token after such a mention is four characters with no
  digit. **The first attempt at fixing that comment was itself decoration**,
  claiming a mutation would go red when it survived.

The general shape, now measured twice in this module: **protections here are
over-determined**, so a surviving mutant usually means redundancy rather than a
dead guard. Idempotence is the other instance - every placeholder `RULES` can
emit is blocked by at least two of the character class, the digit requirement
and the length floor, so no single edit exposes any of them.

**And a process failure, recorded rather than smoothed over.** This item was
merged and pushed **before** that refutation returned its verdict, on the
operator's explicit instruction. It came back clean, so nothing unsafe landed,
but the merge was unreviewed at the moment it happened. The pass also noted that
at the commit which was merged, this file still read `READY` and no ledger entry
existed - **"item 9 CLOSED" was never a property of that commit**.

### Two comment claims were measured wrong and are corrected, not edited away

- **The leak is a whole extra event on a secrets-bearing line, not a poisoned
  field.** `MapUrl.target` stops dead at the `?`, so on that line it would hold
  the 26-character path alone and **no `MapUrl` field would ever carry the key
  or the token**. They would reach a consumer through the embedded
  `LogLine.raw` and `.message`. The hazard is real; the mechanism was
  misdescribed, and a test now pins the mechanism.
- **The comment asserted what `lanternlight.redact` does not mask.** That
  sentence is **removed rather than updated**: the anchor's job does not depend
  on another module's state, and a comment asserting it goes stale the moment
  that module changes - which it did, this session, three files away.

### Two of the item's own surfaces were already closed

Recorded rather than dropped, because the item widened its own scope onto
hazards that did not exist:

- **`OnRep_PlayStateTag` needs no new rule.** Measured at token level: **0 of
  20** `PlayerName` values survive, including all three distinct third-party
  names and the one non-ASCII value. `PlayerName` is already a distinctive
  persona key. `TagName` and `lastState` survive and **should** - they are
  `Game.PlayState.*` tags, not PII.
- **`device_id` and `user_unique_id` were already masked.** 202 and 198 tokens,
  one distinct value each, every one a **19-digit** run, **0 surviving** at
  token level before any rule was added - caught by `LONG_ID`'s 15-digit floor.

  **Decision taken: name them anyway.** `DEVICE_ID` and `USER_UNIQUE_ID` are
  `_keyed_id` rules following the `BATTLEID` / `OWNER_ROLEID` / `ROLEID`
  precedent. This is a **renaming, not a widening** - each takes a digit run at
  `LONG_ID`'s own floor, so every value they decline `LONG_ID` declines too. It
  adds a label and no coverage. The limit is `_ID_VALUE`'s existing one: a value
  under either key written as fewer than 15 digits, or as a UUID or hex blob, is
  named by neither rule and caught by neither.

### A fourth encoding, measured and clean

The module names three encodings it reaches - base64, hex, wide characters -
and states anything else is out of reach. **Percent-encoding is a fourth**, it
is plainly present in this log, and it was worth measuring rather than assuming:

    lines containing a percent-escape             : 3
    runs hiding a persona behind the encoding     : 0
    labels reachable ONLY after percent-decoding  : NONE
    redact the log, THEN percent-decode it        : 0 of 12 personas reappear

**No rule is added.** It is n=3, which makes this a fact about this capture and
not about the encoding, and a guard built for three runs is decoration. Recorded
as a measured negative with its limit attached so nobody re-derives it.

---

## Ordering note

**Items 2b, 2c, 2d, item 7's shipped-code half and item 3 are CLOSED as of
2026-08-12.** `lanternlight/damage.py` reads the damage series and
`lanternlight/tail.py` follows the log, so both the extractor and the live spine
are shipped code rather than scratchpad analysis.

**The next item is 7b, the training ground**, and it needs the client open. It
is the cheapest thing on this list and the **only** route to **outgoing**
damage in quantity - which is the half Emberforge actually needs, because the
21 hits measured so far are damage **taken**. `sourceType: 0` is what to look
for. If the game is running, do 7b first and fold items 1, 4b, 5 and 6 into the
same session, since all of them need the client and none deserves its own.

**Item 9 is CLOSED as of 2026-08-12** (ledger `LL-0046`). The `cdkey` hole is
shut, the `/Game/` anchor is genuinely pinned, and two of that item's four
surfaces turned out to have been closed already.

**If the client is not open, the next item is 4's `AvgPrice` watcher** - it is
fully specified, independent of everything else, and needs nothing but work.
There is no longer an open safety item; the safety lane's queue in
`lanes/safety.STATE.json` is all blocked on a candidate fixture existing.

Item 3 is closed, so it is no longer the fallback. The tailer exists; what does
not exist yet is anything consuming it, and nothing on this list currently asks
for that - do not invent a consumer without an acceptance criterion.

Item 7 itself stays **open** on one thing only: no coefficient may be published
until the same value is seen in an **independent run**.

One ownership correction, measured this session: `tests/fixtures/**` is owned by
**ingest**, not safety. This document called 2b "safety-lane work" and the
roster in `ops/lanes.py` disagreed. What actually worked was a split - ingest
built the artifact, safety owned the detectors and held the veto. Read the
roster, not this file, for who owns a path.

Item 4's watcher remains independent of everything else. Item 3 is closed.

Each lane now carries its own queue in `lanes/<lane_id>.STATE.json`, so the
right way to pick work is to read the state file of the lane that owns the
files, not to re-read this whole document. This list stays the single place an
item's acceptance criterion is defined; the lane files say who holds it and
what is blocked.

Item 1's remainder, and items 5 and 6, all need the client open. None of them
needs a *deliberate* capture session any more - the 2026-08-09 pass showed the
log alone was sufficient - so fold them into whichever session next has the game
running rather than scheduling them. **Item 4b and items 5 and 6 are held as
open items on the `research` and `capture` lanes**, each naming what it is
blocked on, so they are no longer only a paragraph in a document nobody reads
mid-session.

## Deliberately not on this list

- Anything touching the game process. Permanently out of scope
  ([ADR-001](docs/adr/ADR-001-no-game-process-interaction.md)).
- Anything requiring decrypted paks
  ([ADR-002](docs/adr/ADR-002-no-asset-extraction.md)).
- ~~Emberforge formula work.~~ **REFUTED 2026-08-11 - see item 7.** This line
  said the engine could not be filled before measured numbers existed, and named
  item 1 as the unblocker. It is still true that **no cooldown values, damage
  coefficients or stealth durations are published anywhere**
  (`docs/CLASS_RESEARCH.md`). It is **false** that no numbers exist: the
  transient save writes per-hit `damageValue` with sub-millisecond timestamps,
  and 263 generations of it were captured on 2026-08-09. The blocker was never
  the game - it was that nobody had read the field. Left here struck through
  rather than deleted, because "we checked and there is nothing" was wrong for
  two days and the shape of that error is the useful part.
