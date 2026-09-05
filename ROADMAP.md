# Lanternlight roadmap

What is actually next, in priority order. Every item carries an acceptance
criterion, because "worked on it" is not a state this project recognises.

Aspirational ideas that nobody has committed to live in [`BACKLOG.md`](BACKLOG.md).
Nothing is moved from there to here without an acceptance criterion attached.

Status vocabulary: **NEXT** (the current item), **READY** (specified, unblocked),
**BLOCKED** (waiting on something named), **OPEN** (a question, not a task).

**Allocating an `OPS-` id: ask, do not count.** Numbering by eye from the OPEN
items is what produced `OPS-12`, because a spent id may have been closed long
ago and be invisible among them.

```
python -c "from ops import ops_ids; print(ops_ids.next_free_id())"
```

It walks this file and `docs/LEDGER.md` at run time, so it cannot go stale.
`tests/test_ops_ids.py` fails if an already-spent id is allocated anyway.

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
  **That is the FIRST `OPS-8`.** The id was later reallocated to an unrelated
  item, the concurrent-suite failure closed 2026-08-26b. Two items, one id -
  see `OPS-12`.

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

## 4. `AvgPrice` market cache - CLOSED 2026-08-25

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

**Remaining acceptance was:** a watcher that snapshots the file on change with
a timestamp and never writes to it. Given the measured trigger, it should
expect a burst at camp re-entry and silence otherwise, and a poll interval
chosen against that rather than against a guess.

**CLOSED 2026-08-25, by code that had already shipped.**
`lanternlight/savewatch.py` is a generic "copy every changed generation, never
write to the source, refuse a destination inside a git working directory"
watcher, and pointing it at `Saved/` does exactly what this item asked for -
verified functionally during the session wrap, not by reading: it snapshots on
change and not otherwise, embeds the timestamp and size in the filename, leaves
the source's mtime and size untouched across repeated polls, and its
`DestinationInsideRepoError` guard fires live.

**Do not build a second watcher.** What is genuinely left is item **4c** -
arming it without a session having to remember to.

**2026-08-25b, and it puts a question mark on the trigger.** 4c's armed watcher
caught the file crossing 37 -> 157 bytes, the first time anything has watched
it change rather than finding it already changed. It happened **2 s after a
dungeon finished loading**, with the operator leaving camp - the opposite
direction to the escape-then-camp switch this item measured. Neither
observation is amended; the reading that fits both is a **level transition** in
either direction, and it is n=1 on each side. `docs/FINDINGS.md` 12.2.

## 7c. Read the training ground meter without a human reading it - ORANGE PAIR DONE 2026-09-01d, white row still open

Opened 2026-08-25, straight out of the session that measured 10.35. The meter
is the only damage surface the training ground has, and every number in
`docs/FINDINGS.md` section 11 was read by a human looking at tiled screenshots.
That worked and it does not scale: a five-distance sweep cost more attention
than the measurement did, and attention is the thing this project runs out of.

**Tesseract is not installed and is not to be installed for this.** Downloading
a binary to read eight glyphs off a fixed HUD is the wrong trade. The digits
are a fixed font at fixed positions in a fixed rectangle, which is the easiest
possible template-matching problem.

**Acceptance:**

- A reader that takes a captured panel image and returns the total, the hit
  count, and the Progress Record pair, or **refuses**. Refusing is a required
  behaviour, not a fallback - a misread digit is indistinguishable from a
  measurement, which is exactly the failure mode this project's doctrine
  exists to prevent.
- Ground truth for the test comes from this session's capture: the frames under
  `C:/ll-captures/2026-08-25/panel` include series already read by hand and
  written into section 11, so a test can assert the reader reproduces
  `10 21 31 41 52 62 72 83 93 103` and `55 109 164 219 275 330 386 441 496 552`
  from the real frames rather than from synthesised ones.
- **Prove the guard is not vacuous**: feed it a frame where the panel is down
  and assert it refuses, and corrupt one glyph and assert it refuses rather
  than guessing a neighbour.

**Two traps already measured while doing this by hand.** The panel plate is
semi-transparent, so hashing its pixels keys on the scene behind it and reports
a new state on every frame - a coarse column-occupancy signature is what
actually dedupes. And a full-screen poller writes 4.8 MB a frame, 34 GB an
hour; cropping the HUD rectangle at capture time costs about 150 KB a frame and
loses nothing.

### Groundwork MEASURED 2026-08-25b - the naive approach is refuted

A reader was built far enough to find out what does not work, then **removed
from the repository rather than left half-working**, because a reader that
refuses every real frame is worse than no reader. The draft, its templates and
the calibration scripts are kept at
`C:/ll-captures/2026-08-25/meterread-wip/`. What follows is the part worth
having: nobody should pay for these measurements twice.

**The panel geometry, measured off the 6,439 captured crops** (500x310 RGB,
`C:/ll-captures/2026-08-25/panel`):

- Orange **Total Damage** digits occupy rows **y 98-118**; white **Progress
  Record** digits occupy **y 255-273**.
- The value is left-aligned near **x=51**; the hit count near **x=197**
  (orange) or **x=200** (white), so **x=190** separates the two fields.
  **It is NOT empty space** - an earlier draft claimed it was "empty in every
  frame examined" and an independent pass refuted that: **109 of 6,439 frames
  carry ink at x=190**, and 45 orange plus 61 white column runs straddle the
  split. A splitter must therefore tolerate a glyph crossing the boundary
  rather than assume none does.
- Glyphs are **10-12 px wide and 17-21 px tall**, advancing about **12-13 px**.
- **The colours separate the two rows for free:** Total Damage digits are
  orange, Progress Record digits white. The word `Hit` is white in BOTH rows,
  so it never pollutes the orange mask and always pollutes the white one.

**A panel-down frame is not a dark frame.** The last frame of the capture has
**zero** orange pixels while being *brighter* overall than a panel-up frame -
bright fraction 0.0668 against 0.0153. So presence must be decided on the
digits or the headers, never on brightness. The upside: zero orange pixels is
itself a clean, correct refusal trigger.

**Exact template matching is dead on arrival**, and now there is a number for
it: ten digits produced **430 distinct exact bitmaps** across the capture,
because the plate is semi-transparent and the scene behind it moves. Only a
tolerant scorer has any chance.

**The digit shapes ARE cleanly separable, and the templates exist.** Clustering
normalised patches from the orange hit-count field gives **exactly 10**
clusters, and they were labelled two independent ways that agreed on all ten:
by reading the rendered ASCII art, and by the counter itself - seven clusters
first appear at consecutive scan positions and read 1,2,3,4,5,6,7 under the
shape labelling. Those templates are in the wip directory.

**THE DEFECT THAT KILLED THE SIMPLE VERSION: one template set cannot serve
four fields.** Scored against the orange-hit-field templates, the share of
glyphs matching within distance 0.12 was:

| field | n | matched |
|---|---|---|
| orange hit count (where the templates came from) | 367 | **100%** |
| orange total | 599 | **40%** (39.2% unrounded) |
| white progress total | 494 | **9%** |
| white hit count | 432 | **0%** |

The white hit-count row was omitted from an earlier draft of this table. It is
the worst of the four and leaving it out flattered the result.

Two attempts to close that gap, both measured, both insufficient:

- **Normalised cross-correlation made it worse** - orange total fell to 17%.
  So the difference is not a linear intensity scaling.
- **Fixed-row normalisation, a 3x3 blur and a +/-3 row shift search helped and
  did not finish the job** - orange total reached 28% within 0.06, and the
  white fields sat at a stubbornly *consistent* 0.11-0.12. A consistent
  distance is the signature of a systematic rendering difference, not noise.

**The root cause, seen by dumping the art side by side:** in the value field a
glyph's top stroke is rendered fainter, so a hard colour threshold erodes it,
and normalising to the glyph's own ink extent then rescales the whole glyph
against a template built from an uneroded one. The same digit in two fields is
the same shape at a different weight and offset.

**So the next attempt should build one template set PER FIELD.** Each field
sits at a fixed position over a fixed background, which is exactly why the
orange hit field matches its own templates at distance 0.00-0.02. A first pass
at per-field harvesting is also recorded, because it shows the remaining
problem: at a fixed clustering distance of 0.05 the fields gave **11, 13 and 7**
clusters rather than 10, 10 and 10, so **the clustering threshold cannot be a
constant across fields either**. Labelling the extra sets is the tractable part
- map each field's clusters onto the labelled orange set by nearest neighbour
and **require the assignment to be a bijection onto 0-9**, which a wrong
mapping would almost certainly fail.

**None of this changes the acceptance**, and in particular the refusal
requirement now has measured teeth: the two-threshold design (accept below,
reject above, **refuse in between**) is what stops a damaged glyph from
silently truncating a number into a shorter one that would look perfectly
valid.

### PARTLY DONE 2026-08-27b - the ORANGE pair is read; the white pair is refused

`lanternlight/vision_meter.py` reads the Total Damage value and its hit count
off a captured panel crop, and **reproduces the hand-read series exactly**:
`10 21 31 41 52 62 72 83 93 103`, from ten named frames in
`C:/ll-captures/2026-08-25/panel`. Five other floor runs in the same capture
read the same series ending `104` rather than `103` - the rounding tie 10.35
predicts, so that is corroboration rather than disagreement.

**The per-field plan works, and the labelling method in this item did not.**
Clustering per field reproduced the counts recorded above (orange hits exactly
10, orange value 13, white value 7). Labelling those clusters is where two
attempts went wrong:

- The wip's label list is by cluster CREATION ORDER, which is **not portable**
  across harvest runs. Reusing it produced a confident, entirely wrong reading.
- Reading the shapes off rendered ASCII art by eye produced a second wrong set.

What worked is the counter itself. Walking the capture in time order and
recording which cluster follows which gives an unambiguous successor chain, and
the cluster preceding every two-glyph reading is `9`. Walking that chain back
labels all ten, and the assignment is checked as a bijection. A lone cluster
whose successor is `1` turns out to be the meter's `0 Hit` reset state, which
independently confirms the zero. **Derive labels from behaviour, never from
shape.**

**REFUTED - the white row is not the same glyphs at a different weight.** This
item's stated root cause says "the same digit in two fields is the same shape at
a different weight and offset". That holds WITHIN the orange row, where value
clusters label onto the hit-count set with margins of 0.032 to 0.101. It is
false across the colours: the white Progress Record digits carry **wide
bracketed base serifs the orange digits do not have**. Nearest-neighbour
labelling of white clusters onto the orange set returns margins as low as
**0.002**, and the bijection check correctly refuses the mapping.

**The reference capture also cannot supply white templates.** Its white hit
count reads a constant `11` for almost the whole 6,439 frames, so only one digit
shape is available to harvest there - 3 clusters, one of them the letter `t`
from the `Hit` label.

So `read_panel` returns the orange pair and reports `progress=None`. That is the
refusal requirement applied to a whole field rather than a glyph.

**A claim made here on 2026-08-27b was WRONG and is withdrawn.** It said the
second cited series, `55 109 164 219 275 330 386 441 496 552`, was "not in
`panel/`". It is there, at `p01185` to `p01224`, and the reader reproduces it
exactly - 55, 109, 164, 219, 275, 330, 386, 496, 552, with hit 8 simply not
captured at that cadence. Both cited series are now pinned by tests.

**AND THE "hit 8 not captured" HALF OF THAT IS ITSELF NOW WITHDRAWN, measured
2026-09-01d.** 441 IS in the capture, at `p01216_19.02.51.472.png` and
`p01217_19.02.52.028.png`, both reading `441 / 8 Hit` and sitting exactly
between `386 / 7` at `p01211` and `496 / 9` at `p01219`. It was never absent - the
reader of the day REFUSED those frames, because 441's `4` and `1` merge into one
24px column run. Widening the value window and splitting merged runs made 121
previously-refused frames of this capture readable and 441 is one of them, so
the second series is now pinned COMPLETE at all ten values.

**What that claim was measuring, before overturning it (`LL-0100`):** that the
reader of 2026-08-27b could not produce 441 from any frame. That was TRUE of
that reader. The error was generalising from "the reader cannot read it" to "it
is not in the capture" - a claim about the INSTRUMENT written down as a claim
about the DATA. This repo's own rule arriving from a new direction: an empty
search is a claim about the search, and a refusal is a claim about the reader.

The error is worth keeping: the scratch scan sampled every THIRD frame, found a
different run that also starts at 55 (`55 110 166 221 ...`, about 55.6 per hit),
and generalised from that one run to the whole directory. A partial search
produced a false negative, and it was written down as a positive claim about the
capture. An independent refuter found the real run immediately. **An empty
search is a claim about the search.**

**Guards proven non-vacuous - FOUR mutations, each red in a different place:**
closing the accept/reject gap kills 2 tests; disabling the bleed ceiling kills
the bleed test; accepting any glyph width kills the fragment test; swapping two
VALUE template labels kills BOTH ground-truth tests. (Filed as "five" in three
places at first, including the append-only ledger, while enumerating four. The
count is four.)

And one test here was found vacuous while checking: the corrupted-glyph test
refuses with "matched no digit", i.e. it scores ABOVE the reject threshold, so
it would still pass if the two thresholds were equal. The gap now has its own
test that erodes a prototype until it lands inside the band.

**What is left**, and it is the white pair only:

- **Acceptance:** a labelled template set for the white Progress Record digits,
  and `read_panel` returning the pair instead of None. **BLOCKED on a new
  capture** - but read the two sections below in order before acting, because
  the REASON was refuted once and then re-established differently.

### White-row groundwork MEASURED 2026-08-27d - not blocked on data after all

**The "blocked on a capture where the record changes" claim above is REFUTED,
and it was mine.** It generalised from the white HIT COUNT, which really does
read a constant `11` throughout, to the whole row. The white VALUE field varies
freely: **26 distinct values** appear in the reference capture - 104, 123, 158,
231, 264, 265, 309, 350, 438, 531, 546, 552, 556, 559, 651, 684, 687, 689, 690,
692, 705, 799, 817, 818, 896, 980 - and a labelled harvest covers **all ten
digits**. The data was there the whole time.

**Segmentation must be FIXED-PITCH SLOTS, not column runs.** The white glyphs
are 1px-stroke outlines, so a `1` splits into two column runs and the run-based
segmentation that works for the thicker orange digits returns 0, 1, 2, 3, 4, 5
or 7 glyphs for a 3-digit number. Measured slot geometry, from a column
occupancy histogram over the capture:

| field | slots | pitch |
|---|---|---|
| white value | x52, x65, x78 | 13 |
| white hit count | x200, x213 | 13 |

The white `Hit` label starts at **x233** and must never be read as a digit.

**The Progress Record shows the PREVIOUS COMPLETED RUN**, not the best ever, and
that is what makes labelling possible: the orange reader already knows what that
run totalled, so every white patch has a known label and **no clustering is
needed**. Measured - grouping frames by the previous completed run's total gives
a single dominant white pattern in **22 of 26 epochs**, most at 100%. The
best-so-far model was tried first and is refuted by its own output: it makes the
"record" DECREASE, and within one supposed epoch the first slot goes empty, then
a 7-shape, then a 1-shape.

That independently corroborates `LL-0064`, which reached the same conclusion
from a single frame reading `42, 3 Hit` beside `0, 0 Hit`. This is the pixel
evidence for it, and it was in the ledger before this work started.

**Clustering was the wrong tool and is abandoned.** Pooled and per-slot, one
cluster absorbs several digits - cluster 0 alone took 1, 0, 6, 5, 4 and 9 - and
44 clusters emerged for what should be 10 shapes. The strokes are 1px and the
plate is semi-transparent, so the scene behind moves under them.

**What is left is a REPRESENTATION problem, and it is measured.** With templates
averaged per (slot, digit) from the record labels, held-out accuracy is:

| representation | held-out | median margin |
|---|---|---|
| 20x12, 3x3 blur | 58.8% | 0.022 |
| 20x12, no blur | **65.5%** | 0.040 |
| 25x10, no blur | 65.5% | 0.040 |
| 25x10, blur | 59.2% | 0.030 |

Blur HURTS here, the opposite of the orange row, because it destroys 1px
strokes. Grid size is irrelevant, which says the loss is not resolution. The
worst confusions are `1`->`9` (89), `5`->`4` (50) and `6`->`7` (30).

**Nothing shipped from this pass**, deliberately: 65.5% is not a reader, it is a
guesser, and this project would rather have no white row than a wrong one.

### Alignment search done 2026-08-27e - REFUTED, and the real cause is the LABEL

**The alignment hypothesis above is refuted.** Six variants were measured on one
cached mask set and one train/held-out split, so only the alignment varied:

| variant | held-out glyph |
|---|---|
| fixed slot crop (baseline) | 65.5% |
| crop to ink bounding box | 65.4% |
| crop x to ink, fixed rows | 65.5% |
| fixed + dx/dy search when scoring | 63.9% |
| bbox + dx/dy search | 64.2% |
| bbox-x + dx/dy search | 63.9% |

Nothing moves. Neither does the white threshold (61.1% to 63.9% across five
settings from `>165` to `>105`), nor grid size, nor dropping outliers from each
class before averaging.

**The cause is the LABEL, not the pixels, and there are two independent proofs.**

First, two classes are identical: the mean grids for `(slot 0, '1')` and
`(slot 0, '9')` differ by **0.0000**, with 149 and 15 members. Fifteen patches
labelled `9` are averaging to the same thing as 149 labelled `1`, which can only
mean those fifteen frames display a `1`.

Second, excluding frames near a label change fixes it, monotonically:

| frames excluded within N of a label change | glyph | frame-exact | digits covered |
|---|---|---|---|
| 0 | 65.5% | 39.4% | 10 |
| 8 | 76.1% | 51.0% | 10 |
| 12 | 89.2% | 78.3% | 9 |
| 16 | 93.7% | 86.5% | 9 |
| 20 | 94.4% | 89.2% | 9 |
| **25** | **96.8%** | **92.3%** | 9 |
| 30 | 96.5% | 91.7% | 9 |

So the templates and the labelling METHOD are sound. **The measured ceiling is
96.8% per glyph and 92.3% per frame, at a median margin of 0.052** - comfortably
above `AMBIGUITY_MARGIN`. Only the timing of the label is wrong.

**And the timing error is JITTER, not a constant lag.** Shifting the whole label
sequence to model a fixed display lag makes it monotonically worse - 65.5% at
shift 0 down to 46.2% at shift 12 - so the record does not simply appear N
frames late. Detecting the change from the white pixels directly is worse again
(68.2%): it finds **51 segments where there are about 26 records**, because
scene bleed through the semi-transparent plate creates spurious change points.

**Nothing shipped from this pass either.** 92.3% per frame is not a reader.

### Boundary fix done 2026-08-27f - also refuted, and the real limit is the CAPTURE

**The run-boundary hypothesis is refuted too.** Three rules were derived offline
from one cache of raw orange readings, so they were compared on identical
pixels:

| boundary rule | held-out glyph, no guard |
|---|---|
| hit count decreases (the old rule) | 65.5% |
| meter reads 0 hits - an actual reset, seen in 313 frames | 55.7% |
| reset OR a new run starting at 1 hit | 64.9% |

The reset signal is unambiguous and makes things **worse**. Shifting the label
sequence in BOTH directions was then tested - the earlier pass only tried one -
and shift 0 is the peak: -4 gives 53.2%, +4 gives 57.3%. There is no timing
offset, in either direction, that recovers the accuracy.

**What IS true: clean frames are essentially perfect.** Measuring each patch
against its own class mean by distance from a label change:

| distance from a label change | median | p90 | white ink |
|---|---|---|---|
| <= 2 | 0.0123 | 0.189 | 77.0 |
| 3 to 6 | 0.0712 | 0.189 | 77.0 |
| 7 to 12 | 0.0068 | 0.186 | 77.5 |
| **> 12** | **0.0045** | **0.0123** | 89.5 |

Far from a transition the classification is near-perfect and the row carries
**14% more ink**. So the pixels and the method are both fine; frames near a
transition are genuinely mid-render and are not labellable by any rule.

**And that is exactly what a refusal is for**, so the reader was re-scored the
way it would actually run - train on clean frames, then REFUSE any glyph over an
accept distance or under a margin. The result is a tradeoff with no good point on
it, because a long epoch gives clean frames but they all spell the SAME number:

| train guard | train frames | digits covered | frames accepted | accuracy on accepted |
|---|---|---|---|---|
| 0 | 374 | 10 | 0% | - |
| 6 | 216 | 10 | 2.2% | 0% |
| 8 | 162 | 10 | 43.9% | 72.4% |
| 12 | 116 | 9 | 59.8% | 74.3% |
| 16 | 93 | 6 | 50.9% | 76.2% |
| 20 | 78 | **5** | 39.4% | **89.7%** |

Ten digits costs accuracy; accuracy costs coverage. Nothing here is shippable and
nothing shipped.

**So it IS a capture limitation - but not the one first filed.** `LL-0071` said
the field never changes, which is false. The real constraint is that the field
changes *often*: only a handful of record epochs last long enough to yield clean
training frames, and those few epochs repeat the same digits.

**What would unblock it, stated as a capture request:** a capture with LONGER
stable stretches per record value - the operator pausing between runs rather
than starting the next immediately - across at least ten distinct records. The
existing capture has about 26 records but only about five long epochs. Nothing
else about the method needs to change: slot geometry, the previous-run labelling
and the refusal gate are all measured and working.
- **CLOSED 2026-08-30 (ledger `LL-0083`). A fresh clone CAN now verify a
  successful read.** The gap was real: every real-frame test needed 1.1 GB of
  the operator's screen and skipped without it, and the clone-safe tests are
  built from the same templates the reader scores against, so they could never
  prove the templates match anything the game rendered. A clone tested
  segmentation and refusals and never saw the reader get a real number right.

  `tests/fixtures/panel_total_103_hits_10.png` closes it. `read_panel` reads
  only `TOTAL_BAND` inside two column windows, so the fixture keeps exactly
  those pixels - **2,025 of 155,000, 1.31%** - and blacks out the other 98.69%:
  the whole scene behind the semi-transparent plate, the white row, both
  headers. The kept pixels are REAL capture, which is what a synthesised frame
  cannot supply. 3.5 KB, reads `103` with `10` hits.

  **Proven by taking the capture away**, not by assertion: the directory was
  renamed and the suite re-run - the three fixture tests passed, the five
  real-capture tests skipped, capture restored at 6,439 frames.

  The safety-lane call this item deferred was taken and recorded: source frame
  reviewed before selection, no PNG text or time chunks, filename renamed so it
  carries no capture wall-clock (the `SAF-1` precedent), and committed only on
  the operator's explicit approval since it enters a public repository
  permanently. **Two of the three guards protect the REDACTION itself**, so it
  cannot erode when the fixture is next regenerated.

### The reader was pointed at a NEW capture 2026-09-01c - two measured results

Found while working item 12, on the `1.0.15` training frames. Ledger `LL-0110`.

**It fits a full-screen frame unmodified.** `read_panel` needs no change to read
a 2560x1440 full-scene PNG - take the 500x310 crop at origin **`(2058, 390)`**.
The `x` origin was measured tolerant across `2056-2061` at the time of this
item. **That is superseded**: it was already wrong at both ends, and after
`ROADMAP` 7d the band reading all 118 frames is `2058-2064`.

**Row `390` is the BEST row, not the only workable one**, and a draft of this
line said "the only row that works at all" on a single agent's report rather
than on a measurement. Re-run over all 124 panel-up frames at five origins:

| crop origin `y` | correct | disagreements | refused |
|---|---|---|---|
| 388 | 2 | **0** | 122 |
| 389 | 33 | **0** | 91 |
| **390** | **61** | **0** | 63 |
| 391 | 37 | **0** | 87 |
| 392 | 2 | **0** | 122 |

**Zero disagreements at every offset**, which is the reassuring half: vertical
misalignment costs READINGS and never produces a wrong one. It degrades to
refusal, exactly as designed. Over 124 panel-up frames it returned **61 agreeing readings and 0
disagreeing ones**, re-run by the merger over all 124 against readings taken by
eye first. That removes the assumption that this reader only ever works on a
purpose-built crop.

**SUPERSEDED 2026-09-01d - it is now 118 of 124.** The 61 below is the state
BEFORE the window was widened and merged runs were split. See the CLOSED section
at the end of this item; the zero-disagreement property is unchanged.

**"124 panel-up" carries a CRITERION and the criterion is the whole
disagreement.** It means *a human could read the live row*. An automated
detector - orange ink in the module's own row band, or header NCC - finds
**123**, and an adversarial pass reported that as an error in this section. It
is not. The single frame between them is `f0661_00.45.40`: motion-blurred, zero
ink in the band, and legible as `9 / 1 Hit` at 8x magnification. **Both counts
are right about different questions**, which is why the number is now published
with the question attached. The same frame is why that pass also read the
single-digit tally as "2 of 19" rather than 3 of 20.

**It goes blind at 1000, and that is the gap worth closing.** Above 999 the
meter renders a thousands comma - `1,257` and `1,913` are both on screen in that
capture. Inside the module's row band the comma is a **3 px** column run, and
`MIN_GLYPH_WIDTH` is 6, so `_read_field` raises *"a fragment, not a digit"*.
**All 55 four-digit frames refused; none misread.** The two-threshold refusal
machinery does exactly what its docstring promises and never truncates `1,257`
into a plausible `157`.

So this is a coverage gap, not a correctness bug - but it bites precisely where
it hurts, because **a long run is the run that crosses 1000**, and a long run is
what a distance sweep produces.

### The obvious fix is INSUFFICIENT and produces the exact truncation it forbids

**Read this before touching the module.** A first draft of this section
prescribed "teach the reader a separator glyph, and do NOT lower
`MIN_GLYPH_WIDTH`". That prescription is **incomplete in a way that is worse
than doing nothing**, and an adversarial pass implemented it to find out.

`VALUE_WINDOW` is `(48, 92)`. Measured on `f0600_00.44.21`, whose true value is
`2,000`, the glyph runs inside the module's own row band are:

    (54,63)=2   (68,70)=comma   (73,83)=0   (86,96)=0   (99,109)=0

**Only the first three fall inside `VALUE_WINDOW`.** The window was sized for
three digits and it CLIPS THE LAST TWO. So teaching the reader to skip the 3 px
comma while leaving the window alone makes it read a confident, plausible,
WRONG number - the adversarial implementation returned `2,06` for a true `2,000`
and `1,0` plus a fragment for `f0549`. Widening to `(40, 120)` read every
four-digit frame correctly.

**The 3 px refusal is currently the ONLY thing standing between this module and
silent truncation.** Do not remove it before the window is widened. The fix is
all three together: **widen `VALUE_WINDOW`, teach the separator, re-harvest the
templates** - and re-run the whole 124-frame set expecting **zero
disagreements**, which is the property that must survive.

This is the session's own warning arriving through its own prescription. Writing
"do not lower `MIN_GLYPH_WIDTH`" felt like the careful move and was not
sufficient care, because the danger was never that one constant - it was that
the value field has a fixed width nobody had checked against a four-digit value.

The full tally over the 124, re-derived by the merger by running the module
against every one of them:

| digits in total | frames | read | refused |
|---|---|---|---|
| 1 | 20 | 17 | 3 |
| 2 | 7 | 7 | 0 |
| 3 | 42 | 37 | 5 |
| 4 | 55 | 0 | **55** |
| **all** | **124** | **61** | **63** |

61 read, 61 agreeing with the human transcription, **zero disagreements**. The
non-four-digit refusals are all glyph-distance refusals in the `0.135-0.165`
band against an `ACCEPT_DISTANCE` of `0.115`.

**SUPERSEDED 2026-09-01d, and the sentence that followed here is WITHDRAWN.** It
read that the band is "the signature of templates harvested from a different
capture" and that the answer is re-harvesting. The distances are right and the
inference is wrong - the templates' OWN source capture produces refusals in the
same band, and the typeface is identical across both captures. The real cause is
segmentation: merged runs and two misregistered frames. Full refutation with its
positive control is in the CLOSED section at the end of this item. This table is
the BEFORE state; it is now 118 read and 6 refused.

**A detector warning, measured twice by two independent agents.** Do not build
panel presence out of an ink count. A grey sky scored 2,835 neutral pixels in
the header band of a frame with no panel on it, and a gold-title pixel count
ranked four panel-free frames above a frame that genuinely held the panel.
Normalised cross-correlation on the header rectangle separates cleanly. **The
control, not the ranking, is what makes such a scan mean anything.**

### CLOSED for the orange pair 2026-09-01d - 118 of 124, ZERO disagreements

Ledger `LL-0112`. The blind-at-1000 gap above is closed, and the fix was three
things together as this item demanded - but **the third one is not the third one
this item prescribed**, and that prescription is withdrawn below.

**What shipped**, all in `lanternlight/vision_meter.py`:

1. **`VALUE_WINDOW` (48, 92) -> (40, 120).** Mandatory, not merely enabling. A
   four-digit value spans x54-115, so the old window dropped the last digit and
   clipped the third. Measured bounds: the full value extent across all 124
   panel-up frames is x53-115, no value run ever reaches x>=193, and the hit
   count starts at x199. **A first draft called that "84 columns of
   guaranteed-empty gap, so widening cannot collide" and that is over-stated:**
   the gap belongs to the 1.0.15 capture, not to the HUD, and on the 2026-08-25
   capture the leftmost lit column inside `HITS_WINDOW` is x193, the window's
   own first column. The fields cannot collide because they are read through
   SEPARATE windows and the value window ends at 120 - not because the region
   between them is empty.
2. **A thousands separator rule**, keyed on the run's FIRST INKED ROW.
3. **A merged-run splitter**, gated on a new `MAX_GLYPH_WIDTH` of 18.

Plus a **grouping check**: digits are regrouped around any separator and a
malformed grouping REFUSES. That catches the `2,06` truncation shape directly
rather than relying on the window being right.

**RE-HARVESTING WAS THE WRONG PRESCRIPTION AND IS WITHDRAWN.** This item said
the sub-1000 refusals were "the signature of templates harvested from a
different capture" and that the answer was re-harvesting. The DISTANCES it cited
reproduce exactly - 0.1352 to 0.1644. Every inference from them fails:

- **Positive control:** the ORIGINAL 2026-08-25 capture, the templates' own
  source, produces accept-band refusals in the SAME 0.122-0.165 band on the
  same 12px and 24-27px runs. A band that appears in the templates' own source
  capture cannot be a signature of staleness.
- **The typeface is identical across both captures** - value width 8/10/12,
  height 17/18/19, pitch 11/13/15, baseline rows y100-101 and y117-118; hits
  height exactly 18 in all 332 runs in both.
- The new capture is if anything SAFER: max distance 0.0871 against 0.0925, and
  tightest margin 0.0638 against 0.0318.

Re-harvesting would also have risked poisoning the set with dithered transition
frames. **The real third part was segmentation, not templates.**

**The merge mechanism, measured.** `_column_runs` breaks on a gap of 3 or more
because the widest intra-glyph gap is 1px. Two digits separated by exactly ONE
blank column give `column - previous == 2`, which does not break, so the pair
merges - **19 such runs**, 18 of them with a `4` on the left whose crossbar
spills a column right. The design margin is exactly one column.

**The width gate is the safety property, not the valley.** Measured over the
1.0.15 capture:

| population | width |
|---|---|
| definitely ONE glyph, value field | 8-13 |
| definitely ONE glyph, hit count | 10-12 |
| definitely TWO glyphs | 24-27 |

Nothing at all lands in 14-23 **on the 1.0.15 capture**.

**A first draft of that sentence dropped the scope and is corrected here.** On
the 6,439-frame 2026-08-25 capture, 18 runs in the value window and 309 in the
hit window DO land in 14-23. The gate is still sound, and the number that
carries it is a different one: **the widest run that ever CLASSIFIES as a digit
anywhere in that capture is 13px**, a `4` at x51-63 of `p04331`, so a gate at 18
sits 5px above the widest real glyph. 277 runs there exceed 18 and go to the
splitter, and the consumer diff below shows none of them produced a wrong
number. State the criterion beside the number: 8-13 is the width of a run that
IS a digit, not the width of every run that exists.

Splitting on an interior gap ALONE would be unsafe: **12 definitely-single
glyphs carry an interior blank column of their own, 11 of them the digit `0`**,
whose hollow centre looks exactly like a join.
`MAX_GLYPH_WIDTH` of 18 is the middle of the measured gap, and both directions
of a mis-set gate fail safe - too low splits a real glyph into halves that score
as nothing, too high leaves a pair merged, and both end in a refusal.

**The result over the 124 panel-up frames at crop origin `(2058, 390)`:**

| digits | frames | read | refused |
|---|---|---|---|
| 1 | 20 | 17 | 3 |
| 2 | 7 | 7 | 0 |
| 3 | 42 | 40 | 2 |
| 4 | 55 | **54** | 1 |
| **all** | **124** | **118** | **6** |

**ZERO disagreements**, which is the property that had to survive. Up from 61
read at the start of the cycle.

### The acceptance said "all 124" and that is NOT met - here is every frame

Six refuse, each pinned BY NAME in `tests/test_vision_meter.py` so that a
seventh refusal fails the suite and so does one of the six starting to read.
None is a segmentation failure:

| frame | true | why it refuses |
|---|---|---|
| `f0661` | 9 / 1 | **ZERO orange pixels anywhere in the band** |
| `f0469` | 0 / 0 | ~~panel sliding IN, misregistered by 2px~~ **panel SCALING in - reads at y=389 only, so 1px, and the ink band is one row TALLER (2,21) vs (5,23)**; see `LL-0118` |
| `f0470` | 0 / 0 | same |
| `f0527` | 261 / 6 | dithered, leading glyph at x54-66, 0.122 |
| `f0537` | 618 / 13 | dithered, MIDDLE digit at x69-78, 0.164 |
| `f0581` | 1834 / 38 | smeared, leading glyph at x55-64, 0.165 |

**"All 124" was never achievable.** `f0661` carries no ink at all in the row
band - the transcription itself flags it not legible and a human read it at 8x
magnification. No window, template or threshold can extract a digit from zero
pixels, and the refusal it raises is the required "panel is not up" behaviour.

**THE OTHER FIVE ARE THE MODULE WORKING, AND THAT IS MEASURED RATHER THAN
ASSERTED.** It would be easy to read them as a timid threshold and widen a
constant until 124 of 124 came back. Disabling the accept band and the ambiguity
margin does exactly that - the reader returns **123 of 124** - and **THREE are
WRONG**:

| frame | true | read with the guards off |
|---|---|---|
| `f0527` | 261 | 262 |
| `f0537` | 618 | 633 |
| `f0581` | 1834 | **3334** |

The last is wrong in its LEADING digit, a 1500-unit error that would sit
unremarked in a damage series. On `f0581` the two candidates tie at 0.165 to
three decimals and the true digit is neither of them. **So the count that
matters is not how many frames read - it is that none is misread**, and a test
now fails if a future pass widens a constant to chase the remainder.

### Regression: the consumer's output was diffed, not just the edited line

Both module versions were run over all **6,439** frames of the 2026-08-25
reference capture:

| outcome | frames |
|---|---|
| identical reading | 3,122 |
| both refused | 3,196 |
| NEW reads where old refused | **121** |
| OLD read where new refuses | **0** |
| disagreeing readings | **0** |

Monotone improvement - no reading changed value and no coverage was lost. The
121 newly-readable frames have no transcription, so they were checked for
TEMPORAL CONSISTENCY instead, the meter being monotonic within a run: **zero**
are inconsistent with their nearest read neighbours. One of them is 441, which
is how the withdrawal recorded earlier in this item was found.

**Guards proven non-vacuous - seven mutations, and one found a defect in the new
tests themselves.** Deleting the separator's row rule left the suite GREEN: the
high-fragment test painted a run 19 rows tall, so the HEIGHT check refused it
and the row rule was never exercised. A 7-row test - a comma's exact height,
differing only in sitting high in the band - now goes red for that mutation. The
other six kill the height rule, the grouping rule, the split gap-count rule, the
width gate (8 tests, including the committed fixture), the window revert, and
swapping two VALUE template labels (**77 disagreements**, which is what proves
the zero-disagreement test is loud rather than decorative). The module was
restored byte-exact by sha256 after every one.

### What is left on this item

- **The white Progress Record row**, unchanged and still blocked exactly as
  described above - it needs a capture with longer stable stretches per record
  value across at least ten distinct records.
- ~~**A registration search, OPTIONAL and NOT done.**~~ **DONE 2026-09-02 as
  CONSENSUS, not as a search** (ledger `LL-0118`). `lanternlight.vision_meter`
  gained `read_frame`, which crops a full frame at every row in
  `FRAME_CONSENSUS_ROWS` (388-392, x fixed at 2058) and requires the readings to
  AGREE - a conflict REFUSES rather than being broken in favour of the
  best-scoring offset. **It is therefore a NEW guard, not a relaxed one**, which
  is what makes it a different thing from the search this bullet declined: it
  never picks a winner, so it cannot hunt for an alignment that makes a glyph
  match, and two rows returning different numbers is a refusal trigger that did
  not exist before.

  **Measured 2026-09-02:** 118 of 124 at the single shipped row, **120 of 124**
  by consensus, and the two recovered frames are exactly the `f0469` and `f0470`
  this bullet named. 0 lost, 0 misread against the human transcription, 0
  disagreements across the five rows, 0 of 231 panel-down frames read, and 0 of
  all 1,817 out-of-window frames read. `read_panel` is untouched - the
  6,439-frame consumer diff is 0 changed / 0 lost / 0 gained, and every function
  in its call graph compiled to identical bytecode **as of `LL-0118`**. That
  bytecode claim is deliberately past-tense: `LL-0119` then changed
  `_read_field` itself to add the truncation guard, so it no longer holds and
  must not be re-quoted as current.

  **The four that still refuse are NOT registration failures**, so no shift
  recovers them: `f0527`, `f0537` and `f0581` are dithered or smeared, and
  `f0661` is a FADE - its brightest value-window pixel is rgb(106, 65, 24)
  against rgb(234, 128, 21) in both neighbouring frames, so its ink never passes
  the orange predicate at any offset. The transcription labels it `up` and
  records 9/1; a human can read a dimmed glyph that a hard colour threshold
  cannot. Refusing it is correct behaviour.

  *The original wording is kept for the measurement it carries:* ~~A +2px shift
  scores the glyph 0.0601 at margin 0.0910, so a search would recover both. It
  was not done because searching for an alignment that makes a glyph match is a
  different fix with a different risk profile - it multiplies scoring attempts
  and so erodes the margin guarantee.~~ That reasoning still stands and is
  precisely why the fix that shipped requires agreement instead of searching.

  **The x axis was measured and deliberately NOT swept.** A 2-D sweep over x
  2056-2061 crossed with y 388-392 recovers ZERO additional frames over the y
  sweep alone, so x consensus is pure cost - and horizontal misalignment is not
  even safe: see `7d`.
- ~~**Two DEFENCE-IN-DEPTH gaps, found by the final adversarial pass, recorded
  rather than hot-fixed because neither has ever fired.**~~ **BOTH CLOSED
  2026-09-01e** (ledger `LL-0115`). Neither was a bug: over 6,439 frames the
  change is 0 changed readings, 0 lost and 0 gained, and only 10 frames shifted
  which guard refuses them. The second gap's TIDY bound turned out to be a trap
  - tightening the separator predicate to the comma population refuses a real
  comma at crop origin y=391 and all 54 at y=392, because the comma's geometry
  MOVES with the crop, so `SEPARATOR_MIN_ROW` and `SEPARATOR_MAX_HEIGHT` buy
  crop tolerance rather than discrimination and were left alone. What was
  actually missing was a height FLOOR (`SEPARATOR_MIN_HEIGHT` = 4 - it
  shipped at 5 and was corrected the same day, see `LL-0116`), the one
  property the rule never tested. The original wording is kept below for the
  measurements it carries.

  1. ~~**A split piece is not re-checked against the width gate, and never
     recursively split.**~~ CLOSED - and its "all nine were caught by the
     DISTANCE threshold alone" is WITHDRAWN: three of the nine never reach the
     classifier and a fourth refuses at the reject bound, so six were relying
     on the distance threshold, not nine. On the 2026-08-25 capture, **9** pieces come back from
     `_split_merged` still wider than `MAX_GLYPH_WIDTH`. Nothing catches that;
     only the distance thresholds stand behind it, and they do hold - the
     closest template distance among those 9 is **0.1489** against an
     `ACCEPT_DISTANCE` of 0.115, so all 9 refuse. **Acceptance:** either the
     splitter re-checks its pieces and refuses a still-over-wide one by name, or
     a test pins that those 9 refuse for the reason claimed - and the
     6,439-frame consumer diff still shows zero changed readings.
  2. ~~**`_is_separator` is looser than the comma population it documents.**~~
     CLOSED - and this sub-item's "**None ever reached a number**" is FALSE and
     withdrawn: 30 of those 384 firings are the genuine comma in a frame that
     reads a four-digit value, which only became possible when the value window
     was widened. Only 3 frames in 6,439 ever had `_regroup` as their sole
     guard, and in all three the field held separators and no digits at all.

     *The original wording followed, kept for the measurements it carries. It
     is written in the PRESENT TENSE about a predicate that has since changed,
     so read it as the BEFORE state:* ~~The docstring describes a comma at
     width 3-4 and first inked row 19-20. The predicate accepts ANY sub-6px run
     with first row >= 12 and height <= 10, and on the 2026-08-25 capture it
     fires **384** times - at widths 1, 2, 3, 4 and 5, and at first rows spread
     across 12-26. None ever reached a number, and the only reason is that
     `_regroup` rejects every malformed grouping, which is one guard rather
     than two. **Acceptance:** tighten the predicate to the measured
     population, or state the looser bounds in the docstring as deliberate -
     and either way keep the 124-frame set at ZERO disagreements and the
     6,439-frame diff at zero changed readings.~~

     Both halves of that are now false: the predicate additionally requires
     `height >= SEPARATOR_MIN_HEIGHT` (4), and 30 of the 384 firings ARE a
     genuine comma in a frame that reads a four-digit value.

- **A four-digit committed fixture, BLOCKED on operator approval.** The
  `LL-0083` precedent is that capture-derived pixels enter this public repo only
  on the operator's explicit approval. A clone can currently verify a successful
  three-digit read but not a four-digit one, so the separator and splitter paths
  are clone-tested only against synthesised masks. Recorded as a decision gate
  rather than committed unasked.

## 7d. A digit pushed OUTSIDE a field window is SILENTLY DROPPED - CLOSED 2026-09-02

Opened 2026-09-02, cycle 37. Found by the x-offset slice while measuring
something else, then DEMONSTRATED ON REAL INK rather than left as geometry.

**The defect, in the past tense because it is CLOSED - everything from here to
the closure block below describes the BEFORE state.** `_read_field` did not
assert that ink stopped before `x_hi`. It collected the column runs inside the
window and assembled whatever it found, so when a glyph fell ENTIRELY outside,
the survivors formed a valid number and were returned as a measurement. That is
the failure class the whole module exists to prevent: not a refusal, a WRONG
NUMBER.

**Demonstrated, on real captured ink, 2026-09-02.** Frame
`f0539_00.42.52.png`, true `live_hits` 14:

| window passed to `_read_field` | result |
|---|---|
| `(193, 224)` - the shipped one | `14`, correct |
| `(193, 218)` | REFUSED - the partial glyph scores 0.132, in the ambiguity band |
| `(193, 212)` | **`1`** - a wrong number for a true 14 |
| `(193, 210)` | **`1`** - a wrong number for a true 14 |

**A PARTIAL cut fails safe and a CLEAN cut fails dangerous.** That is why this
has no detector: the harmless case is the one that trips a guard.

**Why it is live, not theoretical.** Both fields are LEFT-ALIGNED - the left ink
extent is constant regardless of digit count - so values grow RIGHTWARD into the
window's right margin. Measured over all 124 panel-up frames of the 1.0.15
capture:

| field | window | usable | left margin | right margin at the widest observed value |
|---|---|---|---|---|
| value | `(40, 120)` | 40-119 | 13-15 | **4** columns, at 4 digits (55 frames) |
| hits | `(193, 224)` | 193-223 | 6 | **0** columns, at 2 digits (78 frames) |

The glyph advance is about 13px, so a third digit lands entirely outside the
window. **That 100 would read as exactly 10 is a PREDICTION from the measured
geometry, not an observation** - no capture here holds a 3-digit hit count. The
MECHANISM is measured on real ink, below. Stated as prediction rather than fact -
the third digit starts near column 225 and the window ends at 223, a CLEAN cut.
`value` has one digit of headroom left: 10000 would need about 20 more columns
against 4 available.

**Never fired, and no recorded measurement is corrupt.** The capture's maximum
`live_hits` is 50 and its digit lengths are 1 and 2 only. This is a latent
defect, recorded before it bites, not an incident.

**Same family as the value field's "blind at 1000", with the polarity
REVERSED.** That one refused (the separator made runs too narrow) and was fixed
by widening `VALUE_WINDOW`. That fix bought exactly one digit of headroom and
stopped, and it left the *hits* field untouched at zero.

### Do not fix it by widening the window

Choosing a right bound without a capture that actually contains a 3-digit hit
count is guessing at a boundary, which is `LL-0116`'s exact failure - a constant
justified by a sweep that never covered the case it was chosen for.

**A naive "refuse if ink touches the last column" is also WRONG and must not be
shipped.** The rightmost lit column IS 223 in real 2-digit frames, so that guard
would refuse 8 measured frames. NEVER REFUSE MEASURED DATA. (This item first
said 78, which conflated "frames with a two-digit hits value" with "frames whose
ink reaches column 223". The rightmost-column histogram over the 124 is
{209: 43, 210: 2, 222: 70, 223: 8}. Refusing 8 measured frames is still fatal -
the count was wrong, the verdict was not.)

**Proposed instead: a LOOKAHEAD guard.** Refuse when there is orange ink in the
columns immediately RIGHT of the window (and, for symmetry, LEFT of it), because
that is the signature of a glyph pushed out. Measured 2026-09-02 over all 124
panel-up frames: the 12 columns outside each window, on each side, contain ZERO
lit pixels in every frame. So the guard refuses NONE of the measured population
and fires exactly when a digit has been displaced.

**Acceptance:**

- A test reading real captured ink through a truncating window asserts it now
  REFUSES rather than returning the truncated number. The `(193, 212)` case
  above is the ready-made fixture.
- The guard WATCHED GOING RED - delete it, see the test fail, restore.
- The 6,439-frame consumer diff still shows 0 changed, 0 lost, 0 gained.
- The 124-frame set still reads 120 with ZERO disagreements.
- The question is asked and answered for ALL FOUR edges, not just the hits right
  edge. The defect is a property of `_read_field`, not of one window, and this
  item's own table exists so that no future pass has to rediscover the other
  three.

### CLOSED 2026-09-02 - `EDGE_LOOKAHEAD`, ledger `LL-0119`

`_read_field` now scans `EDGE_LOOKAHEAD` (8) columns immediately outside its
window on BOTH sides and refuses when it finds orange ink there, naming the side
the digit was pushed. Every acceptance criterion above was met:

| criterion | result |
|---|---|
| real ink through a truncating window refuses | `f0539` through `(193, 212)` REFUSES; it returned `1` for a true `14` before |
| the guard watched going RED | 5 mutations, all RED, module restored byte-exact by sha256 |
| 6,439-frame consumer diff | **0 changed, 0 lost, 0 gained**; 62 frames changed only WHICH guard refuses them |
| the 124-frame set | still 118 single / **120 by consensus**, 0 misreads, 0 disagreements, 0 of 231 panel-down |
| all four edges answered | the guard is symmetric, and the margin table above is the answer |

**It fixes a real wrong-number bug, not just a theoretical one.** At crop origins
x 2046-2070 the reader previously returned **108 confidently wrong
numbers** across the 124 panel-up frames - `1913/40` read as `1913/4`, `347/6` as
`347/5`. All 30 are now refusals. That is the x-axis analogue of the property the
y axis already had, and `7c`'s "misalignment costs readings and never produces a
wrong one" is now true of BOTH axes rather than only the vertical.

**The constant is pinned from both sides by measurement, and both captures were
asked** - `LL-0116`'s lesson applied on the way in rather than a cycle later:

- **Floor 6.** The largest gap between two runs that BOTH classify as real digits
  is 5 columns (value; 3 in hits), so a displaced glyph begins within 6.
- **Ceiling 19, measured by sweeping the constant itself.** The binding question
  is not "where is there ink" but "where is there ink on a frame that READS".
  Over ALL 6,439 frames the nearest outside ink is 1 column, in 111 of them - and
  NONE of those 111 reads. Over the 3,243 that do, sweeping this constant costs
  zero readings up to 19 and loses 3 at 20. An earlier draft of this block said
  18, from a proxy measurement of "nearest ink" rather than from sweeping; the
  proxy was off by one.
- Mutating to 3 or to 25 both go RED, so it cannot drift either way.

**Two honest limits, recorded rather than smoothed over.**

1. **The 6,439-frame capture contains no positive example of the defect.** Zero
   out-of-window runs there classify as a digit, so that capture BOUNDS the
   constant but cannot demonstrate the guard catching anything. The catching is
   demonstrated elsewhere: on the 30 misaligned-crop wrong readings, on the real
   `f0539` truncation, and on a synthesised 3-digit `hits` value.

   **That last one carried a false claim and it is withdrawn.** An earlier draft
   said the synthesised value "previously read as 10". It did not - against the
   pre-guard module it refused with "run x199-204 matched no digit". The test
   pins WHICH guard refuses it, not a rescue from a wrong number that was never
   measured on that input. A synthesised glyph is not evidence about the HUD;
   the wrong number is real and is demonstrated on REAL ink by the other two.
2. **The ceiling is priced entirely by value-left**, which has 11 columns of
   slack at `EDGE_LOOKAHEAD` 8, while `hits` - the field with zero right margin
   and therefore the likeliest place for a pushed glyph - is nowhere near the
   bound. A per-edge lookahead would decouple them. It is NOT done, because a
   single symmetric bound is safe on both captures today and per-edge constants
   are four things to drift instead of one. **Acceptance if a future session
   takes it up:** the 6,439-frame diff still shows 0 changed / 0 lost / 0 gained,
   the 124-frame set still reads 120 with zero disagreements, and each per-edge
   value is pinned from both sides by a test watched going red.

**A second cost, and it is the real price of this guard: x TOLERANCE.** The
band of crop origins reading all 118 frames narrowed from **2057-2065 to
2058-2064**. Re-measured over x 2046-2070 after the change, there are now ZERO
wrong readings at every offset, but 2057 reads 110 rather than 118, 2065 reads
34, and 2056, 2066 and 2068 read 42, 0 and 0. Offsets that used to return a
confident wrong number now refuse. That is the direction this module is required
to fail in, and it is a trade rather than a free win: **7 usable origins instead
of 9, in exchange for 108 wrong readings becoming refusals.**

**One cost, recorded because shrinking coverage should never be silent.**
`p06217` now refuses at this guard rather than at the splitter's over-wide
postcondition, so that postcondition is exercised by **5** real frames rather
than 6. No reading changed anywhere.

**A fixture artifact was corrected, not worked around.** The synthesiser drew the
hits field at `HITS_WINDOW[0] + 4`, which put a two-digit synthetic value's ink
at x224 - one column OUTSIDE the window, where real two-digit ink stops at
222-223. The prototypes are deliberately fatter than real ink, so this was the
fixture misrepresenting the HUD; it is now `+ 3` and lands where real ink lands.

## 4c. Archive the log and the market cache on every session - CLOSED 2026-08-25b, successor 4d OPEN

Opened 2026-08-25 after measuring that the 6.1 MB log from 2026-08-09 no longer
exists. The game **truncates its log on launch** - after the launch that
emptied it, the live `MistfallHunter.log` still carries its original
2026-08-09 08:18:56 creation time. Every line
not copied out before the next launch is gone, and this project's own findings
now rest on prose whose raw evidence was destroyed.

**"and keeps no backup" was part of this item's premise and it is REFUTED**
(`docs/FINDINGS.md` 11.12). A launch watched directly on 2026-08-25 at 21:28:59
left `MistfallHunter-backup-<UTC>.log` beside the live log, byte-identical to
the previous run's final 5,080,313-byte log. **It does not weaken this item, it
sharpens it:** no backup existed at any point across 23 listings of `Logs/`
during the session before it, so a backup is a windfall of unmeasured
conditions rather than a mechanism to rely on - and the archiving it argues for
is what captures the windfall when it does appear.

`lanternlight/savewatch.py` already solves it. It is a generic "copy every
changed generation, never write to the source, refuse a destination inside a
git working directory" watcher, and pointing it at `Logs/` and at `Saved/` was
enough this session to archive the log every five minutes and to snapshot
`AvgPrice_<id>.ini` on change - which is item 4's remaining acceptance, met by
code that already shipped rather than by a second watcher.

**Acceptance:** one entry point that arms the watchers for a session - log,
`SaveGames/`, `Saved/` root and `StandaloneLevel/` - with the poll intervals
chosen against measured triggers rather than guessed (the transient save needs
seconds, the log does not, and a 3-second cadence on a growing log copies
gigabytes). A test that the destination guard refuses a path inside a checkout,
and a written note of what each interval is for.

**Do not** re-implement the copying. The one thing this item adds is that
arming it is not something a session has to remember.

**IT STILL HAS TO BE ARMED, and on 2026-08-30 it was not.** The client was
launched at `21:11` with no watcher running. The game truncates on launch, so
the 4.45 MB log this session had just mined - the sole source for `LL-0099`'s
ability bindings and the PvP death - was rotated to
`MistfallHunter-backup-2026.08.30-06.24.23.log` and had **zero** archived
copies. The 2026-08-26 `01.27.09` backup that existed earlier in the same
session was already gone from that directory, so the game keeps only a couple.

The evidence was **rescued rather than lost**: the rotated log is now archived
under `C:/ll-captures/2026-08-30/logs/`, verified byte-identical by sha256 with
both digests asserted non-empty first. Nothing in the game's own directory was
moved or deleted.

**The lesson is not "archive harder", it is that a closed item can still fail
open.** This one is MET and tested, and it protected nothing during a session
where nobody invoked it. An unattended loop cannot arm a watcher for a client
launch it does not know about.

**IT WAS STILL UNARMED AT CYCLE 29, and the successor log was single-copy.**
Measured 2026-08-31. The `21:11` launch of 2026-08-30 truncated the live log and
started a **successor**, and nothing was armed for it afterwards. So at the start
of cycle 29 that successor - `235,864` bytes, sha256 `296547c5...` - existed in
exactly ONE place, the live file. Arming `lanternlight.armwatch` archived it
byte-identical to `C:/ll-captures/2026-08-31/logs/`. **Rescuing the log you just
mined is not the same as leaving the watcher armed for the one being written
next.**

**This is the SAME gap persisting, not a second incident** - an earlier draft of
this paragraph called it a second failure and that is withdrawn. No launch
occurred between the 2026-08-30 wrap and cycle 29, so nothing was actually at
risk in that window, and one fix closes both descriptions. What DID work is the
written record: the wrap's directive in `ops/runtime/loop_state.json` says in
terms that `armwatch` "MUST BE ARMED and was not", and cycle 29 armed it because
that sentence was read. **The continuity mechanism fired; only the arming did
not.**

**A backup is a windfall and this item already says so - do not restate it as a
rule.** An earlier draft here said the next launch "destroys" the live file.
`docs/FINDINGS.md` 11.12 forbids exactly that: what decides whether a launch
leaves a backup is unmeasured, so no rule may be written from `n=1` in either
direction. Measured since: the 2026-08-30 `21:11` launch DID leave one -
`MistfallHunter-backup-2026.08.30-06.24.23.log`, created at `21:11:19`, the
launch instant, holding only pre-launch content - which is a second instance of
the 2026-08-25 observation, not a rule. The live file also still carries its
original `2026-08-09 08:18:56` creation time. **Archive anyway**, because the
windfall is unmeasured in both directions.

That successor turned out to be a **21-second launch-and-quit** (UTC `02.11.22`
to `02.11.43`) carrying zero `affix`, `exEquip`, `cfgid` tooltip,
`setClassGender`, `holding-`, `EnterBattle` and `DamageCollection` events, so
nothing of measurement value would have been lost. **Note the spelling** - the
log spells it `DamageCollection` while the SAVE property is
`DamageCollectonDataSet` (`lanternlight/damage.py`), and a first draft of this
line searched the save spelling against a log, where it can never match. A zero
from that token is a claim about the token. Recorded so the next session does
not spend a pass re-mining this log.

**SUPERSEDED 2026-09-01 by `4d` / `LL-0104` - everything in the rest of this
section is the state as of cycle 29 and three of its statements are now FALSE.**
A watcher IS running; arming is no longer owed; and `armwatch.py` now DOES carry
date logic. Do not act on the instructions below - use `4d`. They are kept
because they are the reasoning that produced `4d`, not because they are current.

**As of cycle 29 (2026-08-31): no watcher was running - it was armed and then
deliberately stopped.** Cycle 29
armed `lanternlight.armwatch` at `17:09:06` local as PID 34116, which is what
rescued the successor log, and the operator stopped it the same evening because
**`--dest-root` is a DATE directory that does NOT roll over**. A watcher left
running past midnight keeps archiving into `2026-08-31/` while claiming to cover
the current day, which is a silently mislabelled archive rather than a missing
one - the worse of the two failures. Verified stopped: zero `armwatch` processes
on the machine.

**So arming was owed again at the next session** - and `4d` has since done it,
with a destination derived per pass instead of a literal dated path, so the
instruction that used to stand here ("arm with TODAY's date") is exactly the
shape `4d` removed. **Arm with `--dest-base C:/ll-captures` and let it derive
the day**; never hand it a dated path. Before arming, check whether one is
already running - `ensure_armed` now does that check itself and refuses -
because **a second watcher points two pollers at the
same four sources**, doubling snapshot traffic while `OPS-14` (this machine's
disk reaching 100 percent) is still OPEN. To end one, use `taskkill /F /PID
<pid>`, this repository's only sanctioned way to end a process. **From Git Bash
that command fails**: MSYS rewrites `/F` into `F:/` and `taskkill` rejects it.
Run it from PowerShell, or use `//F //PID`.

**The remaining half - AUTOMATIC arming - became item `4d`, and parking it here
was a mistake.** `4c` sits in the loop's `completed` list, and
`ops/loop/state.py` says in terms that a cold session reads `completed` to learn
what to skip and that nothing un-completes an item. An acceptance criterion
written inside a completed item is unreachable work. The claim that there was
**no date-resolution code in `armwatch.py`** was true when written and was the
right correction at the time; `4d` has since ADDED that code. See `4d`.

**MET 2026-08-25b by `lanternlight/armwatch.py`**, 19 tests in
`tests/test_armwatch.py`, suite 1225 -> 1244. Not one byte of copying was
reimplemented: the module builds a four-surface plan and hands it to
`SaveWatcher`.

- **All four surfaces** are covered and each gets its own destination, because
  the snapshot name is `<stamp>_<size>_<name>` and two sources sharing a
  destination would collide on any same-named file.
- **Each interval carries its own argument, as a field rather than a comment.**
  A test asserts every `rationale` cites at least one digit, so an interval
  cannot quietly become prose. `SaveGames/` and `StandaloneLevel/` poll at 3 s
  (the transient save appears 17 s after `EnterBattle` and grows through 7
  generations in about 70 s); `Saved/` root at 30 s (the market cache changes
  state, it does not grow); `Logs/` at 300 s (5,080,313 bytes in one session,
  23 generations at that cadence).
- **The destination guard is pinned three ways** - against a hand-built `.git`
  fixture, against this actual checkout, and by asserting the refusal happens
  before any destination directory is created.
- **Guards proven non-vacuous.** Four mutations were applied and each went red
  in the right place before being restored: `LOG_POLL_S` 300 -> 3, the logs
  source changed from the directory to the file, a rationale stripped of its
  numbers, and `arm()` made to construct nothing.

**The one design decision worth carrying forward: watch the DIRECTORY, never
the log FILE.** That is what captured the 5,080,313-byte backup at 21:30:40
this session, which means arming at session start now recovers the PREVIOUS
session's log as well as preserving the current one. It also makes the open
question in 11.12 - what decides whether a launch leaves a backup - answer
itself over enough launches, with nobody running an experiment.

## 4d. Arm the session watcher AUTOMATICALLY - CLOSED 2026-09-01

Opened 2026-08-31, ledger `LL-0103`. Closed 2026-09-01, ledger `LL-0104`.
**Split out of `4c` because `4c` is in the loop's `completed` list**, so an
acceptance criterion parked there is work no cold session will ever pick up.
This item existed to give that work an id.

`4c` shipped the entry point and it is genuinely met -
`python -m lanternlight.armwatch --dest-root <path>` arms all four surfaces.
What was never met is `4c`'s own stated aim, that "arming it is not something a
session has to remember". Two sessions running proved it was: 2026-08-30
launched the client with nothing armed, and 2026-08-31 found the successor log
still single-copy.

**The staleness was in the ARGUMENT, not in any resolution code**, correcting
`LL-0102` and an earlier draft of `4c`. `lanternlight/armwatch.py` contained no
date logic at all. It does now, because this item added it - but the correction
stands as the record of why the previous session should not have been sent
hunting for code that did not exist.

### What shipped

- `ops/loop/watch.py`, the arming supervisor. `ensure_armed(dest_base)` is
  idempotent: it starts a DETACHED watcher and records its pid and dated
  destination in `ops/runtime/armwatch.json`, or - when the recorded pid is
  still alive - **refuses and spawns nothing**. A record whose pid is dead is
  stale and is re-armed, and the two cases are reported as different facts
  rather than both as "armed". `session_armed(...)` is the context manager a
  cycle wraps itself in.
- `lanternlight/armwatch.py` gained `--dest-base`, which derives
  `<base>/<local date>` from the clock **on every pass** and retargets the
  running watchers when the day changes. `--dest-root` keeps its literal
  meaning; exactly one of the two is required.

**Nothing here kills anything.** Liveness is `guard.pid_is_alive`, which uses
`OpenProcess` plus the EXIT time out of `GetProcessTimes` on Windows, because
`os.kill(pid, 0)` there maps onto `TerminateProcess` - the conventional POSIX
existence probe would kill the process it is asking about. (It read
`GetExitCodeProcess` until `OPS-18`; that sentence is corrected here rather
than left to mislead.)

### Acceptance, with the evidence observed 2026-09-01

- **Arming without a session choosing to do it - met in the documented
  start-up step, and see the stated limit below.** Every document that tells a
  session how to start - `.claude/commands/loop.md`, `.claude/commands/
  continue.md` and [`docs/HEADLESS.md`](docs/HEADLESS.md) section 4a - now
  arms as part of starting, and
  `test_every_session_entry_document_still_wires_the_arming` pins all three so
  the wiring cannot vanish in a later edit without going red. Verified live: a real
  detached `python -m lanternlight.armwatch --dest-base C:/ll-captures` was
  running as pid 17568 within seconds of the call, and it had archived 13
  files including all three log generations and `AvgPrice_937566.ini`.
- **A session that never invokes the entry point still ends with the live log
  archived.** The test named in that criterion exists and is called
  `test_a_session_that_never_invokes_the_entry_point_still_archives_the_live_log`,
  in `tests/test_loop_watch.py`. It drives a session body that touches
  no watcher of any kind, through the real `SaveWatcher`, and asserts both the
  archived bytes and the record a LATER session reads. **What it does not
  prove**, stated because the test name is stronger than the test: the test
  itself calls `session_armed`, so it shows that a session BODY need not know
  about the watcher - not that an unwired session gets armed by magic. The
  wiring is what the session-entry documents and their pinning test cover, and
  the limit below says where that stops.
- **A refusal to start a second watcher.** Verified live, not only in a test: a
  second `ensure_armed` call returned `armed=False` naming pid 17568, and the
  machine still held exactly one armwatch process.
- **A destination derived per run, not passed once.** Two different tiers of
  evidence, kept apart on purpose. OBSERVED LIVE: the running watcher derived
  `C:/ll-captures/2026-09-01` from the clock, with only a base passed to it.
  DRIVEN IN A HARNESS, not observed in the wild: the midnight rollover, using
  an injected clock against real files on disk - an UNCHANGED source produced
  no duplicate and no day-2 content at all, while a source changed after
  midnight was captured into `2026-09-02/`. **No watcher has yet been observed
  crossing a real midnight**, and that is the one part of this item resting on
  a harness rather than an observation.

### The stated limit - what "cannot skip" does and does not mean

**`guard.released()` does not arm, and nothing in code forces a session to.**
The lock is a lock; taking it and arming are two calls, and a cycle that writes
only the first still runs unwatched. An earlier draft of this item claimed
arming was "bolted to the one step a cycle cannot skip" - that was
**overclaimed and is withdrawn**, found by the pre-push refutation.

What is actually true is weaker and worth stating exactly, because a reader who
believes the stronger version will not check: arming is now the documented
default in every session-entry path rather than a separate thing to remember,
and a test pins those documents. The gain is one of SALIENCE plus a regression
guard, not of mechanism. Making the lock itself arm was considered and
rejected: `ops/loop/guard.py` would then spawn a real watcher from inside every
test that takes a lock, and a lock module that starts background processes is a
worse trade than an honest limit.

### Measured cost, 2026-09-01 - the item asked for a rate, not just a proof

**The size of `C:/ll-captures` does not answer this question**, because that
tree has two producers and the watcher is the small one. Scoping it is the
whole measurement.

**How "watcher output" is defined here, because the first attempt got it
wrong.** Every snapshot `savewatch` writes is named `<stamp>_<size>_<name>`, so
the scope is *files matching that convention*, not files under a directory
whose name I recognised. The first pass filtered on directory names
(`logs`, `savegames`, `savedroot`, `standalonelevel`) and silently missed
`2026-08-25/saved-root` - 7 files, an older hyphenated spelling of the same
surface - which is `AN EMPTY GREP IS A CLAIM ABOUT YOUR PATTERN` in its
positive form: a NON-empty match that was still measuring the pattern rather
than the thing. Found by the pre-push refutation.

Measured after this session armed its own watcher:

| scope | files | size |
|---|---|---|
| `C:/ll-captures` total | 19,175 | 9.884 GB |
| of which watcher snapshots, whole tree | 405 | **122.66 MB** (1.21 percent) |
| of which in the five dated session roots | 133 | 97.23 MB |
| of which frame captures | the remainder | about 9.76 GB |

Per armed session-day, dated roots only: 9.59 MB (`2026-08-25`), 20.28 MB
(`2026-08-25b`), 42.54 MB (`2026-08-30`), 12.42 MB (`2026-08-31`), 12.42 MB
(`2026-09-01`). **Worst observed 42.54 MB.** Those five sum to 97.23 MB, which
is the dated-roots row exactly - a check worth doing, because an earlier
version of this table listed per-day figures that summed to more than the total
printed above them. The remaining 25.43 MB sits in `C:/ll-captures/saves`, an
earlier destination predating the dated layout.

The cost scales with GAME ACTIVITY, not with armed duration, because
`savewatch` only copies a CHANGED generation. An arming pays a one-off startup
cost for whatever is present - today's was 13 files and 13,019,536 bytes,
12.42 MB - and then copies nothing at all while the sources are idle. So the
worst observed day repeated every day for a year is about 15 GB against
159.1 GB free, and a year of idle days is about zero. **The disk pressure
`OPS-14` tracks is the frame poller, not this watcher.**

**A 4.43 GB/yr defect was designed out rather than shipped and documented.**
The first cut rebuilt each watcher at rollover, which forgets the
`(name, size, mtime_ns)` identities it has captured and therefore re-copies
every unchanged file into every new dated directory - one full startup pass per
day. Measured today that is 13,019,536 bytes, so 12.42 MB/day, about **4.43 GB
a year, roughly 37x the entire 122.66 MB the watchers have produced in total to
date**, with `OPS-14` open. The rollover now RETARGETS the running watcher
instead, so the seen-set survives midnight. An unchanged 5 MB log is not a new
fact just because midnight passed.

**That ratio was first published as "9.84 MB/day, 3.51 GB/yr, 45x" and is
corrected twice over**, both times by the pre-push refutation. The original
numerator counted only the 3 files in `Saved/Logs/` against a denominator
covering every surface - asymmetric, and it UNDERSTATED the defect. The
denominator was then itself too small, for the `saved-root` reason above. Both
halves now count the same thing on the same definition.

**The caveat that buys, stated rather than left implied:** a dated directory
now holds what CHANGED that day, not everything that existed that day. A day
whose sources never changed is empty or absent, and reconstructing a surface's
full state on such a day means reading back to the earlier directory that last
captured it.

### Why a loop cycle and not a scheduled task

The acceptance allowed either. A scheduled task was rejected on three counts:
it is machine state living outside the repo, so a fresh clone silently does not
have it and `CLAUDE.md`'s fresh-clone section could not make it true; this
project shares no scheduled-task namespace with its siblings and adding one is
an operator-level change to the machine rather than to Lanternlight; and the
loop already has a mandatory start-up step - taking the single-instance lock -
which is the natural place to hang an unavoidable side effect.

**This paragraph used to end "Arming now rides on the step a cycle cannot skip",
and that sentence is WITHDRAWN** - see the stated limit above, which withdrew it
90 lines earlier in this same item. `released()` in `ops/loop/guard.py` does not
arm. Caught by the wrap refutation, and it is the defect `LL-0104` itself named -
a stale sentence surviving a few hundred lines from the correction - recurring
inside the item that named it.

## 4e. Re-check the watcher's LIVENESS at the WRAP, not only at entry - CLOSED 2026-09-03

**CLOSED by ledger `LL-0122`, cycle 38.** `check_watcher()` and
`ensure_armed_at_wrap()` ship in `ops/loop/watch.py`, the heartbeat ships in
`lanternlight/armwatch.py` behind `--heartbeat PATH`, and the wrap-side check
is written into `docs/HEADLESS.md` 4b and step 8 of `.claude/commands/done.md`.
Suite 1518 passed, ruff clean, measured at the wrap.

**TWO OF THIS ITEM'S OWN PREMISES WERE FALSE and are withdrawn below, adjacent
to where each was written.** Read the strikethrough notes in place; do not cite
this item's original text without them.

**What it does NOT close, now split out as `4f`:** the verdict still rests on
the combined `written` stamp, so one wedged surface out of four reads as
`ARMED`. The per-surface stamps make that visible to a reader and nothing makes
it fail.

Opened 2026-09-02, cycle 37. Deferred here by ledger `LL-0117`, which recorded
it rather than hot-fixing it because changing the documented start-up contract
is a ROADMAP item and not a wrap edit.

**The failure it exists to close.** On 2026-09-01 the session watcher was armed
as pid 17568, correctly REFUSED two re-arm attempts during the session because
it was still alive, and was then found DEAD at the wrap. For an unmeasured
stretch nothing was archiving the log, the saves or the market cache. This is
not "nobody armed it" - `4c` and `4d` closed that. It is the next failure along:
**a refusal to re-arm is only as good as the process it deferred to**, and
nothing re-checks that process between the arming and the next session entry.

Every session-entry path calls `ensure_armed` on the way IN. None checks on the
way OUT - and the way out is precisely when a session hands the machine back to
an operator who is about to launch the client.

**Liveness is not enough, and this is the part a naive fix will miss.** A pid
can be recycled, so "a process with that pid exists" is a weaker statement than
"the watcher is running". Cycle 37 checked both by hand at session entry: pid
23628 was alive AND its command line was
`python -m lanternlight.armwatch --dest-base C:\ll-captures`, and the start
time matched the arming record. A check that stops at the pid would have passed
on any unrelated process that inherited the number.

**Acceptance:**

- The wrap path re-checks the recorded pid before printing the next-session
  prompt, and re-arms when it is dead rather than reporting the stale record.
- The check confirms IDENTITY as well as liveness - a live pid that is not the
  watcher must read as NOT armed. Name the evidence used (command line, start
  time against the arming record, or both).
- A test that has been WATCHED GOING RED: record a pid that is alive but is not
  the watcher - the test's own process will do - and assert the wrap refuses to
  treat it as armed. A test that only ever sees a dead pid does not pin this.
- `docs/HEADLESS.md` states the wrap-side check beside the entry-side one, so a
  cold session reading the headless contract learns both.

### A THIRD failure mode, measured at the cycle 37 wrap - LIVENESS IS NOT FUNCTION

`4e` above closes "the recorded pid is dead". The wrap that opened it found the
next gap along, and it is not covered by anything written here or in `4d`.

At the cycle 37 wrap, pid 23628 was **alive and identity-confirmed** - its
command line named `lanternlight.armwatch --dest-base C:\ll-captures` and its
start time matched `ops/runtime/armwatch.json` to the second. It had been
running for over 24 hours. In that time it archived **nothing**: every file
under `C:/ll-captures/2026-09-01/` carries the arm-time stamp `20260901-202636`
or the earlier `20260901-075014`, and no `2026-09-02` dated root was ever
created.

**That is the expected result** - the client was closed for the whole period, the
source files did not change, and the watcher copies each file exactly once. But
it is indistinguishable from a watcher that hung five minutes after arming.
There is no observation that separates "correctly idle" from "wedged":

- No heartbeat is written. `armwatch.json` records the arming and is never
  touched again.
- The current instance produced **no `armwatch.log` at all** under its dated
  root, while a directly-invoked watcher does write one - the newest on this
  machine is `C:/ll-captures/2026-08-31/armwatch.log`. So the one artifact that
  would show passes happening is absent exactly when the watcher was armed
  through `ensure_armed`.

  **WITHDRAWN 2026-09-03, `LL-0122`: there is no such asymmetry.** NO code path
  in this repository writes `armwatch.log` - it appears only in prose and in
  one test's denylist, and a `FileHandler|basicConfig|getLogger` sweep returns
  nothing with the positive control passing. The 2026-08-31 file is 562 bytes
  containing exactly `run_rolling`'s startup banner, with a 0-byte
  `armwatch.err` beside it: a hand-typed shell redirect, not an artifact of
  either arming path. The real and much smaller difference is that
  `default_spawn` sends a detached child's stdout and stderr to `DEVNULL`
  deliberately, so a long-running child cannot block on a pipe nobody drains.
  The acceptance bullet below that asks for parity is therefore answered by
  documenting the DEVNULL redirect, which `docs/HEADLESS.md` 4b now does, and
  by making the HEARTBEAT the sanctioned liveness artifact instead of a log
  file nobody was writing.
- A dated root only appears when something is archived, so its absence is
  equally consistent with both states.

**This matters because it makes `4e`'s own check weaker than it looks.**
Confirming a live pid with the right command line proves a process exists, not
that it is still polling. The failure `LL-0117` recorded was a dead watcher;
a wedged one would have been invisible to every check this project currently
has, including the one `4e` proposes.

**WITHDRAWN 2026-09-03, `LL-0122`: "There is no observation that separates
correctly idle from wedged" was FALSE.** One exists, it needs no code, and it
is passive: sample `Win32_Process.OtherOperationCount` twice. For pid 23628 it
climbed 508 in 15 s, 971 in 30 s and 266 in 10 s while `ReadOperationCount`,
`WriteOperationCount` and CPU stayed flat, with `Threads=5` - four surface
daemons plus main. That is exactly what `poll_once` predicts, since
`iterdir()` and a stat per entry are both "Other" operations and every entry
was already in `_seen` so nothing was copied. Controls: an idle Python process
gives 0, a scan-only Python process gives 1442, and four `pwsh.exe` gave 0 -
the counter discriminates.

**So pid 23628 was correctly idle, not wedged.** But the claim must be stated
as "not WHOLLY wedged" and no stronger: the counter is per-PROCESS, not
per-thread. The `logs` surface is about 0.5 percent of that traffic, so a hung
`logs` thread is invisible to it. That per-thread blindness is why the
heartbeat was still worth building, and it is the whole content of `4f`.

**Additional acceptance for `4e`, or for a successor if it is split out:**

- The watcher writes a heartbeat that advances even when nothing is archived -
  a timestamp in `armwatch.json`, or a log line per pass. Nothing else in this
  repo can currently distinguish idle from wedged, so a passive record is the
  minimum.
- The wrap-side check reads that heartbeat and reports the watcher as STALE when
  it has not advanced within a stated multiple of the slowest poll interval,
  which is the 300s `logs` source.
- `ensure_armed` produces the same `armwatch.log` a direct invocation does, or
  the difference is documented as deliberate. An artifact that appears only on
  one of two arming paths is a trap for whoever goes looking for it.
- A test that has been WATCHED GOING RED: freeze the heartbeat and assert the
  check reports STALE. A check that only ever sees a fresh heartbeat does not
  pin this any more than a dead-pid-only test pins the liveness half.

**Not in scope:** killing anything. The loop guard never kills and neither does
this - it refuses, re-arms, and reports.

## 4f. One wedged surface out of four still reads as ARMED - CLOSED 2026-09-03

**CLOSED by ledger `LL-0123`, cycle 39.** `check_watcher()` gained a seventh
state, `SURFACE_STALE`: each surface is judged against its OWN poll interval,
the status NAMES which surfaces stopped, and a surface that never recorded at
all is caught once its grace window closes. The heartbeat is now
self-describing - it carries an `intervals` map - and the set of surfaces that
OUGHT to have reported comes from `session_plan`, never from the heartbeat's
own maps. Suite 1560 passed, ruff clean, measured at the wrap.

**Three defects were found by the refutation pass AFTER the first
implementation reported done, and two of them meant this item's acceptance was
not actually met in production.** They are recorded in `LL-0123` because the
shape recurs: all three were invisible to a green 1547-test suite and to the
merge gate.

Nothing is re-armed and nothing is terminated for a `SURFACE_STALE` watcher.
`REARM_STATES` is still exactly `NO_RECORD`, `DEAD`, `IMPOSTOR`.

Opened 2026-09-03, cycle 38, split out of `4e` by ledger `LL-0122` rather than
left implied inside a closed item.

`check_watcher()` decides `STALE` from the heartbeat's single combined
`written` stamp. The heartbeat also carries a per-surface map, but nothing
compares each surface against its OWN poll interval, so the two 3-second
surfaces keep the combined stamp fresh even when `logs` - the 300-second
surface, and the one guarding the 5 MB log that `4d` exists to protect - has
been hung for an hour. The map makes that visible to a human reading the
evidence line. Nothing makes it fail.

The same blindness defeats the cheaper instrument, which is why this is not
solved by dropping the heartbeat and sampling the OS counter instead:
`Win32_Process.OtherOperationCount` is per-PROCESS, and `logs` is roughly 0.5
percent of that traffic.

**Acceptance:**

- `check_watcher()` reports a surface as stale against that surface's own
  `poll_seconds`, not against the combined stamp, and names WHICH surface.
- The verdict distinguishes "every surface stale" from "one surface stale" -
  they are different failures and collapsing them loses the interesting one.
- The first heartbeat after arming can carry fewer than four `surfaces` keys.
  A missing key must read as "no completed pass yet", never as stale, or every
  wrap in the first 30 seconds of a watcher's life cries wolf.
- A test WATCHED GOING RED: freeze ONE surface's stamp, leave the other three
  and the combined `written` stamp fresh, and assert the check reports that
  surface. A test that freezes all four passes today and pins nothing.

## OPS-16. The termination-path guard has three spellings it cannot see - CLOSED 2026-09-03

**CLOSED by ledger `LL-0125`, cycle 40.** `tests/test_process_capability.py`
is a capability ALLOWLIST over the two modules that can acquire a process
handle, `ops/loop/guard.py` and `ops/loop/watch.py`. It builds a symbol table
of what each bound NAME refers to and routes every access through the same
checks whether spelled as an attribute, a literal `getattr`, or a bare name
from a from-import. Suite 1634 passed, ruff clean, measured at the wrap.

All three spellings this item named are caught, plus `os.system`, `os.killpg`
and `os.abort`, which it did not - **its own list of three was incomplete**,
which is the shape it was filed to warn about.

**The first implementation was REFUTED and had to be fixed.** It shipped with
**11 undeclared holes** - `from os import system`, the `executable=` kwarg,
the whole `getattr` laundering family, handle rebinding through an alias,
`with`, `for` and tuple unpacking - and, worse, its docstring ASSERTED coverage
it did not have. That is precisely the failure this item exists to end, so it
was not close-able until fixed. Recorded in `LL-0125` because the shape recurs.

What it is still blind to is enumerated in the module docstring rather than
implied - propagation through a call, a conditional, a container or a helper
return; a subscripted handle; `getattr` on an unresolvable target; and the
`**kwargs` splat, named there as the sharpest remaining edge.

**No production code changed.** The anti-cheat boundary was re-inventoried and
is clean.

Opened 2026-09-03, cycle 38, by the refutation pass of `LL-0122`. **All three
predate that cycle**; the guard was narrowed in it, and the refutation replayed
both the old and new guard logic over HEAD's module to separate what the change
lost from what was never caught. Exactly one spelling was lost, and it was
fixed in the same cycle - these three are the residue.

`tests/test_loop_watch.py::test_watch_exposes_no_termination_path` collects
call NAMES from the AST and forbids a set of them. It is blind to:

- `subprocess.run(["taskkill", "/F", "/PID", pid])` and the same through
  `Popen`. `taskkill` is banned as a call name, so a string in an argument list
  sails past - and `Popen` cannot simply be banned, because the module's own
  detached spawn needs it and an anchor assertion requires it.
- `getattr(kernel32, "Open" + "Process")`, and any other dynamically assembled
  attribute name. This defeats every name-based AST check by construction.
- `ntdll.NtSuspendProcess` and the other undocumented NT entry points, none of
  which appear in the forbidden set.

**Why this is filed rather than fixed on the spot:** a name-based check cannot
close any of them, and the honest fix is a different KIND of check. Widening
the deny list one string at a time is how the `.gl` bug in `OPS-13` happened -
an enumerated list that reads as exhaustive and is not.

**Acceptance:**

- Either a check that constrains what the module may IMPORT and CALL by
  allowlist rather than denylist, or a written statement in the test's own
  docstring naming these three as known-blind, so the guard stops implying
  coverage it does not have.
- Whichever is chosen, the blindness is stated in the ARTIFACT. A guard that
  reads as exhaustive and is not is worse than one that says what it misses.
- A test WATCHED GOING RED for each spelling the chosen approach claims to
  catch.

**Not in scope:** the anti-cheat boundary. The refutation inventoried every
call in the shipped `ops/loop/watch.py` - kernel32 `OpenProcess`,
`GetProcessTimes` and `CloseHandle`, plus one `Popen` with a fixed argv - and
found no terminate, suspend or memory-write path. This is a guard-strength
item, not a live defect.

## OPS-17. `_dead_pid()` reopens the pid-reuse hole its own docstring warns about - CLOSED 2026-09-04

Opened 2026-09-03, cycle 40, by the refutation pass of `OPS-16`. Found as an
intermittent red that had nothing to do with the item under test, which is the
expensive kind: a session that meets it spends its time on the wrong thing.

**Observed**, not theorised: a full-suite run failed at
`tests/test_loop_watch.py::test_process_creation_time_is_none_rather_than_a_guess_when_it_cannot_tell`,
with **pid 16264 reused** between being reaped and being probed. It passes in
isolation and passed on the next run.

`_dead_pid()` exists specifically to avoid guessing a pid, and its docstring
says so - "a guessed pid can be reused, and this test would then flake in the
one direction that matters". Then it does this:

```python
with subprocess.Popen([sys.executable, "-c", ""]) as proc:
    proc.wait(timeout=60)
    return proc.pid
```

**The `with` block closes the process handle on exit, and on Windows that is
exactly the moment the pid becomes eligible for reuse.** Reaping alone does not
free a pid while a handle to the process is still open; closing the last handle
does. So the helper reintroduces the hole it was written to close, and the
docstring's reasoning is correct while the code under it is not.

**THE BOLD SENTENCE ABOVE IS FALSE AND IS WITHDRAWN, measured 2026-09-04.**
`Popen.__exit__` does NOT close the process handle. It closes the standard
streams and calls `wait()`, and in CPython 3.14.4 neither it nor `_wait()`
touches `self._handle`. With the `with` block exited and the name still bound,
the reaped pid was STILL openable - 275 of 275 trials, against a negative
control that forced the handle shut and flipped every reading. What frees the
pid is the REFCOUNT reaching zero, which in the old helper happened at
`return proc.pid`. The refcount alone is enough, with no collection anywhere
(60 of 60). **So a fix aimed at the `with` block would have changed nothing.**
The rest of the paragraph - that reaping alone does not free a pid while a
handle is open, and that the helper reopens its own hole - stands.

**"pid 16264 reused" OVERSTATES THE OBSERVATION and is withdrawn to
"openable".** The assertion that reddened was `is None`, which keeps no
creation time, so it cannot separate a REISSUED pid from a LINGERING process
object whose handle somebody else still held. Both make `OpenProcess` succeed.
A 300-trial sweep on this machine measured 7 lingers and 0 reuses, so linger is
the likelier reading of the original red. The pin closes both, so the fix is
unaffected - but do not re-cite "reused" as a measured fact.

**Acceptance:**

- `_dead_pid()` returns a pid that CANNOT be reused for the lifetime of the
  test - for example by keeping the `Popen` object (and therefore the handle)
  alive for the duration, rather than closing it at the point of return.
- Whatever is chosen is argued in the docstring against the mechanism above.
  A fix that merely retries, or that sleeps, is not one: it lowers the odds
  without changing the reason.
- The existing reasoning about not GUESSING a pid is preserved. This is a
  narrowing of that helper, not a reversal of it.
- A test WATCHED GOING RED. This one is genuinely awkward to pin - the failure
  is a race - so the honest acceptance is a test on the MECHANISM rather than
  the symptom: assert the handle is still open (or the chosen invariant holds)
  at the moment the pid is handed back. If no such assertion can be written,
  say so in the ledger rather than claiming a proof the test does not give.

**Not in scope:** `OPS-8`, which closed concurrent-pytest safety. This is a
single-process race against the OS pid allocator, a different mechanism.

**CLOSED 2026-09-04, cycle 41, ledger `LL-0126`.** Both helpers now append the
reaped `Popen` to a module-level list and never drop it, so the process object
- and with it the pid - survives the whole run. Watched red by hand in both
files with the pin removed, and again with the `wait()` removed, which is the
plausible WRONG fix: it reserves the pid by leaving the child ALIVE, and turns
every liveness caller red.

**THE ITEM'S INVENTORY WAS INCOMPLETE - there were TWO helpers, not one.**
`tests/test_loop_guard.py` carried the same defect character for character and
this item named only `tests/test_loop_watch.py`. An enumerated inventory is a
filed count, which is the lesson `OPS-16` paid for one cycle earlier.

**ONE PID CANNOT SERVE BOTH NEEDS, and that is provable rather than awkward.**
On Windows the single condition "a process object is still referenced" is what
BOTH reserves the pid and keeps `OpenProcess` succeeding, so "cannot be
reissued" and "cannot be opened" are two faces of it. The liveness callers need
the first; the creation-time test needs the second. So that test stopped asking
for a dead process and asks instead for a number NT can never issue, with the
four-byte client-id premise ASSERTED at the point of use, so a machine that
breaks it reddens and names the reason instead of flaking.

**NOT PROVEN, stated rather than implied.** The pin is a Windows guarantee and
the mechanism test skips elsewhere. No test asserts that an UNPINNED pid reads
free: that assertion IS the race this item opened for, so shipping it would be
a flake dressed as a guard. It was watched by hand instead.

## OPS-18. `pid_is_alive` calls a DEAD process ALIVE when it exited with 259 - CLOSED 2026-09-04

Opened 2026-09-04, cycle 41, by the refutation pass of `OPS-17`, which was not
asked about it and found it anyway.

`ops/loop/guard.py` decides liveness with `GetExitCodeProcess` and compares the
result against `STILL_ACTIVE`, which is 259. **259 is also a perfectly legal
exit code.** A process that exits with 259 is therefore reported ALIVE, and
stays reported alive for as long as anything keeps its process object around.

**Measured twice, independently**, by spawning children that exit with a chosen
code and pinning them open so the probe has something to read:

| exit code | `pid_is_alive` |
|---|---|
| 0, 1, 42, 258, 260 | False - correct |
| **259** | **True - WRONG**, 5 of 5 |

The neighbours either side read correctly, so this is the constant collision
and not a general failure of the probe.

**Why this is not a curiosity.** `ensure_armed` REFUSES to start a watcher when
the recorded pid reads alive - deliberately, because a second poller on the
same four sources is the exact failure it exists to prevent. A watcher that
exits with 259 would be believed alive forever, `ensure_armed` would refuse
every re-arm, and nothing would archive the log, the saves or the market cache.
That is the silent outage `LL-0124` caught in production, with the check that
caught it disarmed.

**"BELIEVED ALIVE FOREVER" IS AN OVERSTATEMENT AND IS WITHDRAWN, measured the
same day it was written.** The false ALIVE needs a live handle to the exited
process object, and the shipped `default_spawn` drops its `Popen` at
`return child.pid`, so in the detached topology NOTHING holds one and the pid
frees within about a second - re-measured directly in `ops/loop/watch.py`.
A third party holding a `PROCESS_QUERY_LIMITED_INFORMATION` handle does sustain
it indefinitely (measured alive at t+2/5/8/11 s, flipping the instant the
holder exits), and **nothing in this repo exits 259**: `armwatch.main()`
returns 0 or 2 only, and `taskkill /F`, `TerminateProcess`, an uncaught
exception and an argparse error give 1, 1, 1 and 2. So the defect is real,
summonable and worth fixing - **but it was NOT firing in production**, and the
item said otherwise. Fixed anyway, on the `LL-0124` principle that a disarmed
check fires the cycle after it ships.

**THE CONSUMER COUNT IN THIS ITEM WAS ALSO WRONG.** It said six; there are
**five** - `guard.is_locked`, `guard.acquire`, `watch.armed_pid`,
`watch.ensure_armed` and `watch.check_watcher`. Two of the six lines cited were
not call sites at all: they are f-strings recording the ANSWER, not asking the
question. And the list omitted `armed_pid` entirely. Third filed count wrong in
two cycles - and the correction was itself loose on a first pass, which the
refutation caught: it called those two lines "branches of one call", which they
are not.

**What a false ALIVE actually does, per consumer, measured against the old
code:** `is_locked` -> True, which is the fail-closed case the docstring
promises, unharmed. `acquire` -> raises `LockBusy`, safe-but-annoying and
genuinely PROTECTED by fail-closed; it never kills, only declines.
`armed_pid` -> returns the dead pid and `is_armed` -> True, unsafe but latent,
since nothing calls it. `ensure_armed` -> refuses with "a watcher is already
running", which is a confident falsehood and NOT fail-closed: the refusal
guards against double-polling while the real risk is ZERO-polling.
`check_watcher` -> worst of the five: the `DEAD` branch is skipped and every
reachable verdict falls OUTSIDE `REARM_STATES`, so the wrap never re-arms.
`IMPOSTOR` is UNREACHABLE, because `process_creation_time` still succeeds on
the exited process - a held handle serves `GetProcessTimes` as happily as
`GetExitCodeProcess` - so `_identity_matches` returns True. Both the `4e`
identity check and the `4f` surface check are defeated by it.

**Acceptance:**

- A test that spawns a child exiting with 259, pins it against pid reuse, and
  asserts `pid_is_alive` reports it DEAD. **Watched going red against today's
  `guard.py` first.** This defect reproduces on demand, so a mechanism-only
  test is not good enough here - unlike `OPS-17`, the symptom is summonable.
- Exit codes 258 and 260 stay correct, and a live process still reads alive.
- The fail-closed promise in `pid_is_alive`'s docstring is PRESERVED: when
  existence genuinely cannot be determined the answer stays True. A fix that
  makes an ambiguous case read dead trades this bug for a worse one, because
  the loop guard would then trample a live loop.
- Whatever call replaces or supplements `GetExitCodeProcess` is added to the
  `OPS-16` capability allowlist in `tests/test_process_capability.py`
  deliberately, with the right it asks for argued. `WaitForSingleObject` on the
  handle with a zero timeout is the obvious candidate - a signalled process
  object means exited, whatever the code - but this item does not prescribe it.
- `ops/loop/watch.py` reaches liveness through this same function, so state
  either way whether `check_watcher`'s `DEAD` branch inherits the bug.

**Not in scope:** `OPS-17`. That was a test-helper race against the pid
allocator; this is a production constant collision in a module no test helper
touches. The two met only because `OPS-17`'s refutation needed children with
chosen exit codes.

**CLOSED 2026-09-04, cycle 42, ledger `LL-0127`.** `_windows_pid_is_alive` now
reads the EXIT time out of `GetProcessTimes` instead of the exit CODE out of
`GetExitCodeProcess`. The exit time is zero until the process exits and a real
timestamp afterwards, it is a different field from the exit code so no exit
code can impersonate it, and it is answerable under
`PROCESS_QUERY_LIMITED_INFORMATION` - the right the module already held.
`ops/loop/watch.py` reads the CREATION time out of the same call under exactly
that right, so this is one idiom, not a second one.

**TWO DESIGNS WERE BUILT AND A DISTINCT AGENT CHOSE BETWEEN THEM.** The
implementing slice built `WaitForSingleObject(handle, 0)`, which has fully
DOCUMENTED semantics and whose defence of `SYNCHRONIZE` as observational was
correct. It lost on REACH, and the deciding number was measured:

> With `SeDebugPrivilege` dropped from the probing token, **77 of the 312 pids
> this machine can open with `PROCESS_QUERY_LIMITED_INFORMATION` DENY
> `PQLI | SYNCHRONIZE` with `ERROR_ACCESS_DENIED`** - 24.7 percent, all service
> processes. Every one lands on that design's fallback, which is the original
> buggy comparison verbatim. Driven through the shipped function with
> `SYNCHRONIZE` denied, it returned True for a child that exited 259.

So that design would have shipped `OPS-18` unfixed on a quarter of the pids it
can be asked about, in a branch its own diff never exercised - and its
correctness would have been **a function of the launching token**, which is
exactly the fresh-clone case this repo writes its rules for.

**THE FIRST SWEEP OF THAT POPULATION READ ZERO, AND IT WAS AN ARTIFACT OF THE
TOKEN.** This session runs with `SeDebugPrivilege` ENABLED, which bypasses the
DACL check in `OpenProcess`, so the residual set could not have been non-empty
no matter what the security descriptors said. A reading is a claim about the
instrument, and here the instrument was the privilege set.

**THE COST ON THE CHOSEN SIDE, written down rather than only known.** Microsoft
documents `lpExitTime` as "If the process has not exited, the content of this
structure is undefined." The zero is MEASURED, not promised: 0 of 312 running
processes reported a non-zero exit `FILETIME`. That hedge is carried in
`_windows_pid_is_alive`'s own docstring, because a guard that mis-states its
coverage is worse than one with a declared hole (`OPS-16`).

**A REJECTED THIRD DESIGN, recorded so it is not re-proposed:** cross-checking
the exit time against `GetExitCodeProcess`, reading the time only when the code
is 259. It sounds like belt and braces and buys nothing - **a live process
ALWAYS reports 259**, so the undefined field is read in exactly the same cases
either way, and the extra call reduces nothing.

**THE SAFETY GUARD CHANGED AND IT WAS RE-PROVED, NOT ASSUMED.** Dropping
`GetExitCodeProcess` made `guard`'s win32 inventory EQUAL to `watch`'s, which
silently retired the discriminator in
`test_the_guard_module_and_the_watch_module_differ_where_expected`. Rather than
delete the assertion, the equality is now asserted, the two surviving
discriminators (`os.kill`, `subprocess.Popen`) are asserted in BOTH directions,
and the docstring states that the win32 namespace no longer discriminates at
all. Re-proved by mutation: `_scope_source` forced to read `guard.py` for every
path still reddens that test. **No allowlist entry was needed** - every call
the new probe makes was already in `ALLOWED_WIN32_FUNCTIONS`.

## OPS-19. `pid_is_alive` calls RUNNING processes DEAD on access-denied - OPEN

Opened 2026-09-04, cycle 42. Found independently by THREE passes during
`OPS-18` - the implementing slice, the blast-radius sweep and the adjudicator -
which is worth noting on its own: it sat under the same twenty lines everyone
was reading and none of them was looking for it.

`_windows_pid_is_alive` returns False when `OpenProcess` yields no handle, and
its comment reads "No such process, or it is gone and unopenable. Either way,
not a holder worth blocking on." **That folds two different facts together.**
`ERROR_INVALID_PARAMETER` (87) means no such process. `ERROR_ACCESS_DENIED` (5)
means the process EXISTS and is running and this token may not ask about it.

Measured: with `SeDebugPrivilege` dropped, **12 running processes read DEAD**
through this path. `pid_is_alive`'s own docstring promises the opposite - "when
existence cannot be determined, the answer is True, so an ambiguous case
refuses to start rather than trampling a live loop". This is a **fail-OPEN in a
function that documents itself as fail-closed**, and it survives `OPS-18`
unchanged in both the shipped design and the rejected one.

**Why it matters:** `guard.acquire` reclaims a lock whose owner reads dead. A
loop running under a different token - a scheduled task, another user, an
elevated session - could therefore have its lock stolen by a second loop, which
is the exact "two loops interleaving commits" failure the module exists to
prevent, and it would happen silently.

**Acceptance:**

- `GetLastError` is consulted after a failed `OpenProcess`, and 5 is separated
  from 87. Access-denied returns True (cannot tell, fail closed); no-such-
  process returns False.
- A test WATCHED GOING RED that pins the distinction. Constructing a genuine
  access-denied case needs care: a protected or other-user process is the
  honest subject, and `SeDebugPrivilege` must be DROPPED from the probing token
  or the denial cannot occur at all. If no such subject can be constructed
  reliably on this machine, say so and pin the branch by injection instead -
  but say which was done.
- The docstring's fail-closed promise and the code agree afterwards. Today they
  do not, and the docstring is the one that is right.

**Not in scope:** `OPS-18`, which was the exit-code collision on the SUCCESS
path. This is the failure path, a different mechanism, and fixing one does
nothing for the other.

## OPS-20. Nothing tests `guard.py`'s access mask, and a docstring says otherwise - OPEN

Opened 2026-09-04, cycle 42, by the `OPS-18` adjudication.

`tests/test_process_capability.py` checks WHICH Win32 entry points the two
in-scope modules reach. Its own docstring says it "says nothing about the RIGHT
an `OpenProcess` asks for", and points the reader at `tests/test_loop_watch.py`
for that check. **That check reads `ops/loop/watch.py` only.** So the access
mask in `ops/loop/guard.py` is tested by nothing at all, while a docstring
tells a later session it is covered.

That is precisely the `OPS-16` failure mode - a guard that MIS-states its
coverage is worse than one with a declared hole, because the mis-statement is
an active lie a later session will rely on. It nearly mattered this cycle: the
rejected `OPS-18` design widened `guard.py`'s mask with `SYNCHRONIZE` and no
test would have noticed.

**Acceptance:**

- The mask assertion is generalised over both files in `SCOPE` rather than
  naming one, so adding a third in-scope module cannot silently escape it.
- Shown RED against `_PROCESS_QUERY_LIMITED_INFORMATION | 0x0001` planted in
  `ops/loop/guard.py` - `PROCESS_TERMINATE` is the right that must never
  appear, so that is the mutation worth proving, not a harmless one.
- Whatever docstring currently claims the coverage is corrected in the same
  change, and states what IS and is NOT checked.

## OPS-21. `guard.read_owner` folds four facts onto `None`, and a corrupt lock is reclaimed - OPEN

Opened 2026-09-04, cycle 42, by the `OPS-18` blast-radius sweep.

`read_owner` returns `None` for a missing file, unreadable JSON, a payload that
is not a dict, and a `pid` that is not an int. `is_locked` then calls
`pid_is_alive(None)`, which is False, so **a corrupt lock file is treated as
unheld and is overwritten.**

`LockBusy.__init__`'s own docstring already says what the intended behaviour
is - `pid` is "None when the file was unreadable but a live owner could not be
ruled out" - so the module has already decided that unreadable means
cannot-tell. `read_owner` does not implement that decision. **This is fail-OPEN
in the same module and the same direction as `OPS-19`**, reached by a different
route.

**Acceptance:**

- "No lock file" stays distinguishable from "a lock file this code cannot
  parse". A missing file is genuinely unheld; a corrupt one is not a licence to
  take the lock.
- A test WATCHED GOING RED that writes a corrupt lock file and asserts
  `acquire` REFUSES rather than reclaiming it.
- Consider whether the operator needs a way out - an unparseable lock that can
  never be reclaimed is its own denial of service. Deleting the file is already
  the documented escape hatch in `LockBusy`'s message, so state whether that is
  sufficient rather than adding a flag.

**Not in scope:** changing what `acquire` does with a lock whose owner is
genuinely dead. That path is correct and is the crash-recovery behaviour.

## OPS-22. `precommit_gate` matches a forbidden cmdlet as a bare substring - OPEN

Opened 2026-09-04, cycle 42, by the `OPS-18` blast-radius sweep - which **it
fired on**, blocking a legitimate command because the analysis mentioned the
cmdlet by name.

`tools/precommit_gate.py` decides with `if "<cmdlet>" in command`. A plain
substring test cannot tell a CALL from a MENTION, so the name inside a comment,
a string literal, a grep pattern or a docstring is blocked exactly as hard as
an invocation. This is the same shape as `OPS-18`: **a sentinel that is also a
legal datum.** The repo already knows the class - `lanternlight/gvas.py`'s
`KeyMapping` refuses to fold Unreal's `"None"` string onto Python `None` for
the same reason - and `NEXT_SESSION_PROMPT.md` already carries the symptom as a
trap ("a grep PATTERN can trip a pre-tool hook").

**Acceptance:**

- A mention is distinguished from an invocation. The bar is not perfection: a
  cheap improvement is to require the cmdlet in a command POSITION rather than
  anywhere in the string, and to say plainly in the docstring what the check
  can and cannot see.
- Tests both ways, WATCHED GOING RED: a real invocation is still blocked (the
  guard must not be weakened - this is the whole point), and a mention inside a
  quoted string or a comment is not.
- **The guard must not become weaker overall.** If a form cannot be
  distinguished safely, it stays blocked and the docstring says so. A false
  block is an annoyance; a false pass is the thing this file exists to prevent.

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

**PARTLY ADVANCED 2026-08-25b, and one sub-question now has a clean experiment.**
Captured at level 5; full write-up in `docs/OBSERVED_IDS.md`.

- **The types-versus-charges question is still NOT separated, but it is now
  separable.** At level 5 the operator holds **exactly one** Hunter's Arrow -
  unlocked, not equipped, with four still locked. `Battle-fed` requires
  "carrying at least 2 Hunter's Arrows". **So: equip that single Hunter's arrow,
  take Battle-fed, and watch whether it fires.** One arrow type carrying
  multiple charges is precisely the case that tells the two readings apart, and
  it did not exist at level 2 when the operator had 2 types and 3 charges at
  once. **Do not spend the point on this alone** - it costs a talent point to
  answer, so fold it in only when Battle-fed is worth taking anyway.
- **A slot-state reading rule was established** and it matters for every future
  loadout count: gold border = equipped, dashed border = owned but not equipped,
  padlock = locked. Counting the middle state as owned-and-active would
  overstate a loadout, which is exactly how a talent gate gets mis-evaluated.
- **Still unmeasured:** how arrows are acquired, and how `roll` differs from
  `dodge`. The Dodge nodes remain the only source on the latter and still do not
  say.

## 5. Sorcerer single-weapon question - OPEN, needs the client

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

**THE ARCHIVE ROUTE IS EXHAUSTED - probed 2026-08-30, do not repeat it.** The
whole log corpus was searched for anything that could close this from disk and
it carries nothing: **zero** `class-11` occurrences, **zero** 5-digit
creation-preview `holding-` ids, and **zero** `BP_Preview_C_` creation-preview
actors, measured across the three distinct sessions known then - and RE-DERIVED
2026-08-31 across all FOUR sessions (22 log files, 14 distinct hashes), still
zero, zero and zero. The 2026-08-09 creation
walk that produced the recorded ids is gone, because the game truncates its log
on launch (item 4c). See `docs/OBSERVED_IDS.md`, "The archived logs hold NO
creation walk".

**So this item needs the client and nothing else will do.** It is otherwise
cheap - one pass over the Sorcerer creation screen with the frame poller
running. Worth pairing with item 6, whose acceptance needs the same screen.

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

## 7. Emberforge is NOT blocked - the save records damage - OPEN, both routes BLOCKED on fresh gameplay

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

> **CONSTRAINT ADDED 2026-08-25b, and it changes what this item can promise.**
> A full dungeon run was captured live and wrote **no**
> `StandaloneSlot_<roleId>.sav` at all - the substring `StandaloneLevel` occurs
> **zero** times in its log, against a `requestEnterStandaloneLevel` at the
> start of the runs that did write one. **A dungeon run is therefore not a
> guarantee of damage data.** Any reader must treat the file's absence as a
> normal mode rather than a parse failure, and any plan of the form "play a
> dungeon and collect damage" is underspecified until the mode is named. What
> selects the two behaviours is **unmeasured**. `docs/FINDINGS.md` 12.1.

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

**Acceptance, added 2026-08-30 - this item had none, which made it permanently
ineligible for the unattended loop.** Every cycle skips items with no acceptance
criterion, so an item marked READY and high value was never once picked up. That
is an ops defect in the roadmap, not in the item.

Close it with **either**:

- a `nameId` other than `0` observed inside a save's `DamageCollectonDataSet`,
  which would settle whether that field is ever populated on that surface; **or**
- a second distinct `skillNameId` value seen also as a `nameId`, which is what
  the paragraph above asks for.

**The second route is BLOCKED ON A FRESH LOG, and the reason is measured.**
`skillNameId` occurs **zero** times across every MistfallHunter log on this
machine - 18 when this line was written, re-derived 2026-08-31 across 22 files,
14 distinct hashes and four sessions, and re-derived again **2026-09-01 across
25 log files, still zero** - the 12.7 MB log that carried `6130017` was
truncated away by the game's launch truncation (item 4c). No probe of the
existing corpus can close it. Recorded so nobody runs that search again.

### ROUTE 1 IS EXHAUSTED - measured 2026-09-01 across the COMPLETE save corpus

**Do not run this search again.** It has now been run to completion over every
save on this machine and the answer is a definitive NO.

- **353 `.sav` files** scanned across `C:/ll-captures` and the live `Saved/`
  tree, **zero parse failures**.
- **The damage field is confined to ONE save type.** Only
  `StandaloneSlot_<roleId>.sav` carries `DamageCollectonDataSet`. The seven
  other save types - `CampData_<id>.sav` (26 files), `Deck.sav` (17),
  `Scav.sav` (14), `UserSettings_v1.sav` (9),
  `EnhancedInputUserSettings.sav` (8), `LoginOptions.sav` (8), `Notice.sav`
  (8), **90 files in total** - do not carry it in a single instance. No other
  save surface is worth searching, which is a result rather than an absence of
  one.
- Of the **263** transient generations: **1 ABSENT, 10 present-and-EMPTY, 252
  carrying records.** That empty ten is finer than this item previously
  recorded and it matters - "the game had not written the field yet" and "the
  game wrote an empty window" stay distinguishable, exactly as the measurement
  doctrine requires.
- **424 child hit readings. `nameId` is `0` on all 424 and `Key` is empty on
  all 424.** No non-zero value exists anywhere.

**Two independent instruments, because a broken search and a true negative are
indistinguishable.** The repo's own reader was one. The other was a regex over
the **raw JSON text** of every payload, which bypasses `DamageHit` entirely and
found 424 occurrences of `"nameId"` carrying the single distinct token `0`.

**The instrument was proved non-vacuous BEFORE the negative was believed.** The
same pass re-derived every headline figure this item already carried, and all
of them matched: 262 generations carrying the field, 21 distinct hits,
1020.344 s span, 9 monster instances, the same 8 monsterIds, total damage
1284.835785, range 9.745483 to 137.517426, and **both** the 278 top-level and
424 child counts that this item once confused for each other. A search that
reproduces eight filed numbers is reading the data.

**Three new constants**, each measured over the whole corpus: `sourceType` is
**1 on all 278** entries, `bDeathCauser` is **False on all 278**, and
`bChildDeathCauser` is **False on all 424**. The second and third independently
confirm item 7a's recorded claim that the save's rolling window **drops the
killing blow** - the save has never captured a death-causing record.

### The two surfaces do not overlap - but the claim is narrower than it first looked

Measured the same day over the log corpus, 25 files:

- The **save** corpus is **100 percent `sourceType: 1`** - by item 7a's reading,
  damage the operator TOOK.
- The log's **JSON** payloads are **100 percent `sourceType: 0`**.

**An earlier draft of this line said "the log corpus is 100 percent
`sourceType: 0`" and that was too broad**, caught by the pre-push refutation. It
holds for the twelve JSON payload occurrences only. The verbose per-hit lines
described below carry **no `sourceType` field at all**, so they are neither, and
a claim about "the log corpus" that was measured on one emission shape does not
cover the other.

What survives is narrower and still useful: **no damage value on the log side
matches any damage value in the save corpus**, and the two sets of events are 17
days apart - the save run is 2026-08-09 17:28 to 17:45 UTC, the verbose log
events are 2026-08-26. So no wall-clock join between the surfaces is available
**for the events currently on disk**. A future capture in which both surfaces
cover the same encounter is what would make the join possible.

**What the log corpus actually holds right now, deduplicated.** `nameId` values
`6150251`, `6152203` and `6152206` with Keys `LightAttack`, `SpearFlurry` and
`ShieldImpact` - which is item 7a's 2026-08-30 table, re-derived. They appear 12
times each, but that is **ONE distinct payload duplicated across 12 archived
copies** of a growing log, so it is **n=1**, not n=12. Counting the raw
occurrences would have inflated a single observation twelvefold - the byte-prefix
trap this repo already recorded for session counts, hit again on a different
quantity.

**7a's three original bindings are absent from the LOGS but `6130017` is NOT
absent from disk**, and an earlier draft of this paragraph got that wrong.
`6130017` (`NormalArrow`), `6130007` (`ExplosionArrow`) and `6250000`
(`MonsterDamage`) occur nowhere in the 25 logs, which is consistent with this
item's record that the 12.7 MB log carrying them was truncated away. But
**`6130017` is re-derivable from the SAVES today**: 139 of the 263 generations
carry the token `SkillNameId` and the int32 `6130017` (bytes `61895d00`)
together, nested under the top-level `LeaderRankScoreData` property. Already
filed at `docs/FINDINGS.md`.

That matters for how route 2 is stated. **"No probe of the existing corpus can
close it" is a LOG-scoped claim wearing corpus-scoped clothes.** The corpus does
contain a `SkillNameId`; what it does not contain is a **SECOND DISTINCT** one -
139 generations carry exactly one value. Route 2 is still blocked, and the
correct reason is the missing second value, not a missing field.

The one thing that genuinely **cannot** be re-checked is the conclusion "the log
populates the same attribution the save blanks, for the same event class": the
only `sourceType: 1` log payload was in the truncated log. That remains a
recorded observation rather than a re-measured one, and is flagged rather than
repeated as though it were fresh.

### A THIRD SPELLING, and a per-hit log surface nobody had enumerated

**This section exists because an earlier draft of the one below it said
"nothing further can be extracted from disk". That was FALSE**, and the
pre-push refutation found the counter-example. Route 1's negative is unaffected;
the framing around it was suppressing a real surface.

`[DamageCollectionComponent]` emits a second, **non-JSON** line whose field is
spelled **`nameid`, all lowercase** - a THIRD spelling, neither the save's
`DamageCollecton` nor the log's `DamageCollection`. A search built on the two
known spellings walks straight past it.

Measured 2026-09-01: **44 raw occurrences across 8 archived logs**, which
deduplicate by their own log timestamp to **10 distinct hit events** carrying
**7 distinct damage values** against **8 distinct `insId` values**. The raw 44
would have inflated 10 events fourfold - the byte-prefix trap again, since the
archived logs are prefixes of one another.

Every event carries `nameid: 0`, `instigator: true`, and
`causer: BP_HermitSprites_C`. **So route 1 fails here too** - this surface adds
no non-zero `nameid`. What it adds is `insId`, which distinguishes individual
monster instances, and seven damage numbers that were not previously enumerated.

**THE DIRECTION OF THIS SURFACE IS CONTESTED AND IS NOT SETTLED HERE.** The
refutation pass that found it read these as the operator's outgoing bow hits.
The surrounding lines do not support that confidently, and they do not support
the opposite confidently either:

- **For outgoing:** 2 of 7 in the largest log sit immediately before a
  `HitIndicator` view-cell bind and a bow `GA_Aimingattack End`, with
  ammunition-index updates just before.
- **For incoming:** 2 of 7 sit beside `GameplayCue.Damage.BeDamaged` and an
  Adventurer `Hit.Light` line, with a monster combo ability active.
- **Decisive field absent:** the verbose line carries **no `sourceType`**, which
  is the field item 7a identifies as the direction flag. Neither reading is
  decidable from this surface alone.

Both readings are adjacency arguments, which is the weak method this repo has
already been bitten by. It is recorded as UNSETTLED rather than resolved in
either direction, and what would settle it is a capture where the same value
appears on a surface that does carry `sourceType`.

**A determinism result that does NOT depend on the direction.** The three-value
sequence `16.99298095703125`, `16.0489501953125`, `75.52435302734375` occurs
**twice**, against different monster instances each time:

| occurrence | timestamps (UTC) | gaps | insIds |
|---|---|---|---|
| first | `04.03.27:692`, `04.03.28:771`, `04.03.29:049` | 1.079 s, 0.278 s | 466, then 469 twice |
| second | `04.06.25:024`, `04.06.26:107`, `04.06.26:391` | 1.083 s, 0.284 s | 536, then 541 twice |

Same three values, same order, same structure - one instance then a second
instance hit twice - and gaps agreeing to about 5 ms. This **independently
corroborates item 7's "damage is DETERMINISTIC, not rolled"** on a different
emission surface and a different encounter from the one that produced it. It is
n=2 sequences and should not be called a constant, the same hedge item 7 already
applies to its own 1.5 s interval.

### What this item now needs

Both acceptance routes require **fresh gameplay**. Route 1 is exhausted; route 2
needs a second distinct `SkillNameId`, and the corpus holds exactly one.

When the client is next open, the cheapest thing that would move this item is a
capture in which **both** surfaces cover the **same** event class - concretely, a
run where the operator DEALS damage while `StandaloneSlot_<roleId>.sav` exists,
so the save's window and the log's `DamageCollectionComponent` payload describe
the same hits. That is what would let the two surfaces be joined at all, and it
is a precondition for either acceptance route rather than a third route.

Note the constraint already recorded above: a dungeon run is **not** a guarantee
that the transient save is written at all, and what selects the two behaviours is
unmeasured.

**What the log CAN already do is bind abilities**, and item 7a now carries six
such bindings rather than three. The save's window remains the surface with no
attribution; the log remains the surface that has it.

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

### THREE MORE ABILITY BINDINGS, and a new id range - 2026-08-30, client `1.0.15`

The live log carries a second death payload, and it binds three ids at once.
Read straight out of the death-statistics line (the label is Chinese and is not
reproduced here; match on `damageChildList`, not on the label):

| nameId | `Key` | `iconPath` leaf | damageValue |
|---|---|---|---|
| 6150251 | `LightAttack` | `T_UI_Icon_Skill_914` | 384.573104858 |
| 6152203 | `SpearFlurry` | `T_UI_Icon_Skill_917` | 384.007812500 |
| 6152206 | `ShieldImpact` | `T_UI_Icon_Skill_919` | 61.545669556 |

`sourceType: 0`, `bDeathCauser: true`, `totalDamage: 830.1265869140625`, and
`monsterId` **absent** rather than null.

**Internally consistent, which is a check worth running:** the three children sum
to `totalDamage` **bit-exactly** in IEEE754, not merely to the last displayed
digit. A payload that did not sum would mean the child list is a sample rather
than a decomposition, so this is the cheap check that a death payload is
complete.

**THIRD-PARTY PII LIVES IN THIS PAYLOAD, and the redactor was tested against the
real bytes.** The same object carries the KILLER's 19-digit `roleId`, 16-digit
`onlineUserId`, a short `name` and a 15-character `onlineDisplayName`, plus
`appearanceStr` and `gender`. `CLAUDE.md` puts third-party players in scope, not
only the operator. **Checked, and the guard holds:** `lanternlight/redact.py`
masks all four identity fields plus `appearanceStr` on the real line, and
`assert_clean` then certifies the result. Only `onlineChannel`, a single digit,
survives.

Recorded as **checked and clean rather than filed as a gap**, deliberately -
`LL-0090` withdrew a redaction-gap claim that had been raised against a
FABRICATED input. This one was derived from the measured bytes, which is the
only test that means anything here.

**`iconPath` is a field nothing had recorded**, and it is the first surface
joining an ability id to a rendered ASSET name. `615xxxx` is also a **new range**
beside the recorded `613xxxx` (player ability) and `625xxxx` (monster source).

**THE SOURCE IS IDENTIFIED, and a first draft of this section said it could not
be.** That draft reasoned that the Keys `SpearFlurry` and `ShieldImpact` cannot
belong to the operator's bow class, offered "another player killed the operator"
as an inference, and then declared that **"nothing observed separates"** that
reading from a broader `sourceType`. **The payload separates it, and the field
was in the line the section had already decoded:**

| Field | Value | Reading |
|---|---|---|
| `classId` | **15** | `Withered Knight` - bound in `docs/OBSERVED_IDS.md` |
| `damagePlayerType` | 0 | a second source-kind flag, semantics unmeasured |
| `sourceType` | 0 | player is the source, per the rule above |

The operator is `class-12`, Blackarrow. The killer is `class-15`. **So this is a
PvP death, the project's first recorded, and `615xxxx` is a Withered Knight
ability range** - matching a spear-and-shield kit rather than a bow.

**HOW THE ERROR HAPPENED, because the shape recurs.** The decode script pulled a
hand-picked list of fields, printed them, and the output was then treated as the
whole record. The payload actually carries thirteen top-level keys. **A selective
extractor's output is a claim about the extractor**, exactly as an empty grep is
a claim about the pattern - and this one was used to assert an absence. Dump the
KEYS before trusting a decode.

**Still unmeasured:** what `damagePlayerType` distinguishes, and whether
`615xxxx` is Withered-Knight-specific or a shared player-ability range that the
recorded `613xxxx` also sits in.

**This does NOT close item 7's open thread.** That asks for a second distinct
`skillNameId` seen also as a `nameId`. **`skillNameId` occurs ZERO times in every
log on this machine**, re-derived 2026-08-31 across 22 files and four sessions
(18 when this was written) - the 12.7 MB log that carried `6130017` was truncated
away, so the thread cannot be closed from the current corpus at all. Recorded so
nobody re-runs that probe.

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

## 7b. Training grounds as a controlled measurement rig - ANSWERED 2026-08-25

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

**All three answered, 2026-08-25, operator in the client.** Full write-up in
`docs/FINDINGS.md` section 11; ids in `docs/OBSERVED_IDS.md`.

| acceptance | answer |
|---|---|
| (a) does it exist | **YES** - `/Game/Project/Maps/TrainingGround/Training`, `DA_DungeonSettings_Training`, `BP_Adventure_Bot_C` |
| (b) is `DamageCollectonDataSet` written there | **NO** - a clean negative. It is not a match: no `StandaloneSlot_<roleId>.sav`, empty `StandaloneLevel/`, no `EnterBattle`, no `damageValue` anywhere on disk |
| (c) does a repeated identical attack repeat its value | **YES for body, NO for head** |

The rig is real but it is a **pixel** rig, not a file rig. The room renders a
cumulative **Total Damage** meter and writes nothing, so the measurement path
is frame capture joined to the log on wall clock - the same join that bound
class ids - and `lanternlight/damage.py` has nothing to read here.

Two body runs eight minutes apart are **identical hit for hit** and solve to a
**fractional** per-hit value in `[10.3500, 10.3571)`, no integer in the
interval. Two of three head runs are likewise identical to each other and the
third is not, and no single value fits them under either display model.

**What this opens, and it is now the highest-value thread on this list:**

- **The distance term - SUPERSEDED by the ten-point curve below, kept for
  the record.** The first controlled sweep was six points. Ten body
  hits at 10, 8, 6, 4, 2 and 0 paces gave 104, 104, 309, 546, 687 and 691. The
  curve is **clamped at both ends**: 10 and 8 paces are identical - a floor,
  where the per-hit value is exactly **10.35** - and 2 and 0 are within 0.6%, a
  ceiling. The slope between them is steep and the ceiling is 6.64x the floor.
  A pace is defined: a full stride counted off the run-cycle animation loop
  reset, no crouch, sprint or roll.
- **Constancy tracks the flat parts of the curve.** A constant per-hit value
  fits both floor runs and NO run on the slope, and the only same-distance
  readings that disagree across the session are on the slope - 6 paces read 265
  once and 309 once, 16.6% apart. Nothing observed requires the game to roll
  damage; the uncontrolled variable is the operator's own position, which he
  reported himself. A delta wobbling by one is NOT evidence of variance - a
  constant value produces that wobble too, and the floor runs prove it.
- **The floor is CONFIRMED under a recorded label.** After the mapping was
  challenged, the ambiguous pair was re-run under wide-shot capture: ten body
  hits at 10 paces and ten at 8, both reading **104**. See `docs/FINDINGS.md`
  11.10 and 11.11.
- **The FLOOR breakpoint is LOCATED: between 8 and 7 paces.** Ten-hit runs at
  10, 9 and 8 paces all read **104** and all solve to `[10.3500, 10.3571]`; at
  7 paces the total is **231**, a 2.221x step in one pace against 1.338x for
  the next. An abrupt clamp, not a flattening curve. Constancy changes at the
  same step - every floor run admits a constant per-hit value and no run off
  the floor does.
- **The CEILING breakpoint is LOCATED too: reached by 3 paces.** Runs at 3, 2,
  1 and 0 paces read 687, 687, 689 and 691 - a four-distance plateau spanning
  0.6% - while 4 paces reads 546. Unlike the floor, the ceiling is approached
  gently: 4 -> 3 is 1.258x, slightly less than the slope's own ~1.3x per pace.
- **The curve is now ten measured points** at 10, 9, 8, 7, 6, 4, 3, 2, 1 and 0
  paces: 104, 104, 104, 231, 309, 546, 687, 687, 689, 691. Three regimes - a
  clamped floor, about 1.3x per pace for four consecutive paces, a clamped
  ceiling.
- **Why is the floor a STEP and not a tangent?** Extrapolating the slope
  outward from 7 paces predicts about 174 at 8 paces; it reads 104. The game is
  not running out of curve, something is clamping. **Acceptance:** a mechanism,
  or a written negative saying the gap is real and unexplained. Do not publish
  a falloff formula from four interior points either way.
  **Record the distance in the capture, not in anyone's memory** - the
  wide-shot poller exists for this and the first sweep had to be re-run without
  it.
- **Measure apparent size properly, or not at all.** Turning "the target looks
  closer" into a number was attempted twice and saturated twice, because a dark
  character against a dark cave is the wrong segmentation problem.
  **Acceptance:** a fixed high-contrast marker placed in frame at a known
  position, or a written negative saying apparent size is not recoverable from
  this scene.
- **Is the headshot bonus a constant multiplier? - SWEEP RUN, and it is not
  that simple.** Seven ten-hit head runs across the six distances gave 123,
  123, 350, 651, 799, 817, 818. **Not one admits a constant per-hit value** -
  including the two on the floor, at the ranges where body shots are perfectly
  constant at 10.35. The totals reproduce (123 twice, 817 against 818, and 122
  / 123 / 123 from earlier runs) while the individual hits do not, so a
  headshot is not a body shot times a number.
  **Open, and blocking the ratio table:** seven runs were fired at six
  distances and the mapping of the last three is unconfirmed, so no
  per-distance ratio is recorded. The ratio is roughly 1.18 where both were
  measured at the same nominal range.
  **Acceptance for the mechanism:** something that separates a headshot from a
  crit. The client renders headshots in red crit text, so the eye cannot do it
  and neither can this data.
- **What separates a headshot from a crit.** The client renders headshots in
  red crit text (operator), so the two cannot be told apart by eye and were not
  separated by this data. **Acceptance:** a run where the two are forced apart,
  or a written negative saying they cannot be.
- **What `Progress Record` counts.** Measured: it holds the PREVIOUS run's
  total and hit count, not a best. That is established; what resets a run is
  not.
- **`capabilityId 13003`** is emitted beside `DA_DungeonSettings_Training` and
  its meaning is unknown. Recorded, not interpreted.

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

## 8b. Source register - CLOSED 2026-08-29

Ledger `LL-0078`. The direct successor to item 8: that item fixed the tier and
provenance of two sites, and this one fixed the fact that the answer was
unfindable.

The vetting had already been done and was scattered across four documents -
`docs/ECOSYSTEM.md` by category, item 8 above, the `docs/CLASSES.md` tier ladder
plus its fabrication catalogue, and a ledger entry. A cold session therefore had
no entry point and re-derived source trust from scratch, which is the exact
rediscovery this project's continuity design exists to prevent.

`docs/ECOSYSTEM.md` now opens with a **Source register**: per source, how it was
built, what tier it sits at, what it is licensed to do, and where that
assessment came from. The provenance column is the load-bearing one, because for
almost every row the method is the only thing being trusted. Item 8's rule is
restated there as the register's governing rule: **"third-party site" is not a
trust tier.**

**Four cross-document conflicts were found and are recorded rather than
smoothed** - the real yield, because each was a place where a cold session would
inherit whichever document it happened to open first:

- `questlog.gg` sits in the `CLASSES.md` T4 copy-farm cluster but was measured
  DATAMINED two days later in item 8. The later measured assessment is carried.
  It stays T4: a datamined source is not more trustworthy, it fails differently.
- `mistfallhunterguide.org` is simultaneously in the T4 cluster and ranked the
  second-best upstream in `ECOSYSTEM.md`. **Left unresolved** - a stated
  editorial policy is a claim about a source, not a measurement of it, and
  nothing here has tested whether it is honoured.
- `lagofast.com` is on the `CLASSES.md` excluded-vendor list AND cited in
  `ECOSYSTEM.md` section 2 as a tier-list site. Excluded wins.
- `captain-carry.com` stays flagged for the excluded list rather than silently
  reclassified.

Also recorded: `gyldforge.com` and `gamerguides.com` appear nowhere in the
`CLASSES.md` tier ladder because that document predates their assessment, **not**
because they were rejected - a distinction that would otherwise read as
rejection.

**Acceptance - MET 2026-08-29, but only after the first claim of it was
REFUTED.** Left in this shape deliberately, because the error is the useful
part.

The first pass claimed **62 of 62, 0 missing**. The independent refutation
overturned it: `th.gl` is cited twice in `docs/ECOSYSTEM.md` (sections 6 and the
safety-gate table) and was **absent from the register**. The cause was not the
register, it was the checker - its bare-domain regex carried a **hardcoded TLD
allowlist** (`com|org|net|gg|io|app|...`) and `.gl` was not in it. So the green
result was a claim about the pattern, not about `docs/` - the exact
"an empty grep is a claim about your pattern" anti-pattern in `CLAUDE.md`, and
the second time this project has shipped a guard that certified what it had no
basis to certify.

Re-derived after the fix with a **TLD-agnostic** extractor: **78 host-shaped
tokens cited across `docs/`, 15 of them non-hosts** (code identifiers such as
`str.splitlines` and `gvas.parse`, filenames, and the GSDK package name
`com.hermes.pstgame`), leaving **63 genuine external sources, 63 of 63 present,
0 missing.** `th.gl` was added to the register as a **measured negative**: it
lists 33 titles and this game is not among them, which is a second independent
confirmation of the companion-tool gap.

Suite **1302 passed, 1302 collected**, identical to the baseline measured before
any edit; ruff clean. Both guards were watched going red: removing
`gyldforge.com` from the register gave exit 1 naming the host; injecting a
U+2014 into the register's own text failed
`tests/test_ascii_hygiene.py::test_repository_is_seven_bit_ascii` inside the
register's own line range. Note what non-vacuity did **not** buy: the checker
went red correctly for the host it was asked about and was still blind to a
whole TLD. **A guard proven non-vacuous on one input is not proven correct.**

**Branch hygiene worth keeping:** `lane/research` was **112 commits behind
main** and 0 ahead when the work started. It was fast-forwarded before any
authoring, because the acceptance criterion walks all of `docs/` and the stale
tree was missing 2372 lines of it - `FINDINGS.md` alone was 1203 lines short.
Authoring on the stale branch would have produced a register that was complete
only against a docs tree that no longer exists. **Check a lane branch's distance
from main before trusting anything derived from its tree.**

**What this item did NOT do:** see `OPS-13`. Nothing guards the register's
completeness, so it can go stale silently the next time a document cites a new
domain.

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
work was **1196**. The follow-up in `LL-0047` added one test and `LL-0048` added
two more, so the suite was **1225** at the latter's close - re-measure rather
than quoting any of these numbers, because every one of them is a snapshot and
this file has been wrong about a count five times already.

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

### The follow-up to the follow-up, `LL-0048` - the evidence for that last sentence was false

The over-determination claim above is TRUE. The enumeration `LL-0047` published
to justify it was not, and it was copied into four artifacts before anyone
re-derived it.

- **The wrong fact.** `redact.py`, `test_redact.py`, the `LL-0047` ledger entry
  and `WAKEUP_NOTES.md` all stated that `<PRODUCTUSERID>` at 15 characters is
  the **only** placeholder clearing `_CDKEY_MIN_CHARS`. **Four clear it** -
  `<USER_UNIQUE_ID>` (16), `<PRODUCTUSERID>` (15), `<ACCOUNT_NAME>` (14) and
  `<OWNER_ROLEID>` (14). `RULES` emits **17** distinct placeholders.
- **Why nobody caught it for three sessions.** All four are digit-free, so the
  minimum blocker count is still 2 and the safety conclusion held anyway. **A
  true conclusion resting on a false reason reads exactly like a sound one**,
  and prose has no failure mode.
- **The fix is a derivation, not a corrected sentence.**
  `test_no_placeholder_rests_on_a_single_cdkey_condition` takes `_CDKEY_VALUE`
  apart by surgery on the live pattern string and counts independent blockers
  for every placeholder `RULES` emits. It reddens if a future placeholder is
  ever both at the floor **and** digit-bearing - the one shape that would rest
  on the character class alone. Note that lowering the floor to 11 puts
  `<STEAMID64>` in exactly that position.
- **It kills a mutation the old test survived.** `LL-0047` recorded that
  widening the value class leaves `test_an_existing_cdkey_placeholder_is_not_
  remasked` green. The derived test goes red.
- **The fix shipped the same defect twice before passing**, both caught by
  mutation or by the wrap refutation rather than by review. Its first draft
  hard-coded "the class excludes `<`" as a Python assumption instead of reading
  the pattern, and the class-widening mutation survived it too. Then the ledger
  entry filed **two mutation counts taken from a `-k` filtered run** into a
  document whose convention is full-suite - re-measured, 1 became 4 and 2
  became 6. **A count without its scope is a wrong count.**
- **A scope gap, also found by the refutation.** The derivation read `RULES`
  alone while `redact()` also applies `LOG_TEXT_RULES` and `DETECT_ONLY_RULES`.
  No live gap - the former emits only `<PERSONA>`, the latter has empty
  replacements - but a future log-text-only placeholder that was long and
  digit-bearing would have escaped the guard. All three are scanned now.

**The habit this adds** to the one below: `LL-0047` said to run the mutation
before committing a sentence of the form "X is what prevents Y". That is not
enough, because this defect was a **list of identifiers**, not a causal claim.
If you catch yourself typing an enumeration into a comment, derive it in a test
instead - a filed count is a hypothesis, and this repository's own anti-pattern
list already said so.

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

## OPS-7. `advance_cycle` silently credits an item that was never started - CLOSED 2026-08-27

**This is the SECOND `OPS-7`.** The id was already spent on a fragment-path
defect closed 2026-08-12 (ledger `LL-0039`). Two items, one id - see `OPS-12`.

Hit for real during the `LL-0048` wrap, and caught only because the return value
was printed and read. `ops.loop.state.advance_cycle(directive, item="7b")`
defaults to `complete_current=True`, which moves the **previous** cycle's
in-flight item into `completed`. The previous in-flight item was also `7b`, so
passing the same item forward - the normal shape of "I did not get to this,
carry it" - **credited `7b` as finished when nothing had been done to it**. The
state was repaired by hand in the same session.

`completed` is meant to be, in the docstring's own words, the honest answer to
what the loop finished. A cold session reading `7b` in that list would skip the
single highest-value item on this roadmap and never know why.

**Acceptance:** a failing test first, asserting that
`advance_cycle(directive, item=X)` where `X == current.item` does **not** append
`X` to `completed` - because carrying the same item forward is a retry, not a
completion. Then the minimum change that makes it pass. The existing
`complete_current=False` escape hatch stays; the point is that the **default**
must not manufacture a completion. Check `tests/test_loop_state.py` for the
current pins before touching the semantics, and verify the guard is not vacuous
by reverting the fix and watching the new test go red.

### CLOSED 2026-08-27

**The rule, one line:** carrying an item forward is a retry, so `X -> X` credits
nothing whatever `complete_current` says. Only `X -> Y` or `X -> None` says `X`
is finished.

All four transitions were run against the real function rather than reasoned
about: `None -> None` credits nothing and still advances the cycle,
`X -> None` credits `X`, `X -> X` credits nothing, `X -> Y` credits `X`.

**Five tests, two of them red first** - `test_carrying_the_same_item_forward_is_a_retry_not_a_completion`
and `test_carrying_forward_twice_never_credits_the_item`. The other three are
negative controls, and they are the ones that stop the cheap wrong fix: a change
that simply stopped crediting anything would satisfy the acceptance and quietly
destroy the record. The multi-hop test exists because an item needing the game
client gets carried across several sessions, and one bad hop loses it for good -
there is no operation that un-completes anything.

**Vacuity proved as the acceptance demanded:** deleting `and not carried_forward`
reddens exactly the two acceptance tests and nothing else. Deleting
`complete_current` from the same condition reddens exactly the escape-hatch test.

**And a clause of the fix turned out to be inert.** The first version read
`item is not None and item == current.item`; mutating the guard away killed **no
test**, because `None -> None` is already blocked by `current.item` being falsy.
It was deleted rather than kept with a confident comment on it. Verifying your
own defensive code with the same mutation discipline as the thing it guards is
the cheap habit here.

**Why this mattered more than its size.** It was hit for real three times -
`LL-0048`, and twice more on 2026-08-26b and 2026-08-27, both worked around by
hand with `complete_current=False`. A workaround that only works because the
operator happens to know about it is how a defect becomes permanent, and this
one silently tells a cold session to skip an item. `docs/HEADLESS.md` and
`.claude/commands/loop.md` now state the retry rule at the step that calls it.

Suite 1282 passed / 1282 collected, ruff clean. Baseline 1277.

## 10. The stack buff - measure it AT THE CEILING - READY, needs the client

**READ [`docs/AFFIXES.md`](docs/AFFIXES.md) BEFORE WORKING THIS ITEM - 2026-08-30
moved the ground under it.** Three things were read off the game's own UI that
this item did not have. (1) `Focus Fire`'s tooltip is now quoted exactly:
"Rapid Arrows increase the Damage Multiplier with each hit on the same enemy" -
so the thing that climbs is a named `Damage Multiplier`. (2) A THIRD candidate
exists that this item never considered: the `Ranged` weapon AFFIX grants a
TEMPORARY damage increase gated on distance greater than 5 metres, which is
neither a talent nor a base mechanic. (3) `Focus Fire` is currently ALLOCATED
while the operator reports the buff no longer appearing at all - so something
here is wrong and the item cannot be worked as written.

**(4) A FOURTH candidate, added 2026-08-30b, and it is the first one carrying
the number 5 from the GAME rather than from a memory of the screen.** The
`SKILLS` screen states that `Rapid Arrows` enters a mode called `Volley`
"allowing you to hold to rapidly fire **up to 5 arrows** for a certain
duration". This item chases an icon that climbs to 5. The icon may simply be the
Volley arrow COUNT and not a stacking buff at all.

**That candidate got WEAKER the same day it was raised, and the reason matters
more than the candidate.** `Sky Piercer` also states 5 - its arrow can "pierce
5 units". **Two unrelated skills in one kit both state 5**, so matching this
item's climbing icon on that number discriminates nothing at all. The candidate
survives only on the Volley MECHANIC, never on its maximum.

**(5) A FIFTH candidate, added 2026-08-30, and it is the first one that is
actually a STACKING BUFF.** The `Fervor` affix ladder, read off
`f0980_00.52.15` and quoted in `docs/AFFIXES.md`, states: after hitting an
enemy, increase `Physical Damage` and `Magic Damage` for 3s, **"stacking up to
5 times"**.

**Why this one is different in kind, not just another 5.** The four candidates
above are an arrow count, a pierce count and a duration-bounded fire mode; none
of them is a buff that stacks. This item describes an ICON THAT CLIMBS TO 5,
which is what a stack counter looks like. `Fervor` is a stack counter with a cap
of 5 and a 3-second window, stated by the game.

**It also makes the number even less discriminating**, which is the honest half:
three separate things in reach of this character now state 5. **The candidate
rests on the stacking MECHANIC and on the 3s window, never on the number.**

**The distinguishing test is cheap and it is the same target-switch run this
item already needs:** `Fervor` is affix-borne, so it should be present only
while an item or gem granting it is equipped, and it decays 3s after the last
hit. `Focus Fire` is talent-borne and per-target. Unequipping the `Fervor`
source and re-running is a clean separation that needs no new measurement rig.

Note also that Volley is bounded by a DURATION while this item reports the icon
climbing per HIT, which is a behavioural difference worth testing - and that
nothing observed ties the on-screen icon to Volley in the first place.

**So the item now needs TWO runs, not one, and they are different tests.**

1. **Target-switch**, which separates `Focus Fire` from the `Ranged` affix.
   `Focus Fire` is scoped to one enemy; the affix is scoped to distance and does
   not care about the target. Ten hits alternating between two enemies.
2. **Fire-and-stop**, which separates a Volley COUNTER from a per-hit STACK.
   Fire `Rapid Arrows`, then stop without dodging, and watch the icon. A
   duration counter decays on its own; a per-hit stack does not.

These are not exclusive candidates - a Volley counter and a per-hit multiplier
could both be on screen at once, which is itself a reason to run both tests
rather than stopping at the first explanation that fits. **Record the weapon's affix set with every run from now on** - no
previous run recorded it, so no previous run can be re-attributed.

Opened 2026-08-26. **The highest-value open question this project has**, because
it may mean an existing headline finding is an artifact.

The operator spotted a buff icon that climbs to **5** while he keeps hitting the
same target inside a time limit, centre screen above the energy bar. It is
readable in the wide shots at `x 600-690, y 600-665` of a 1280x720 frame, and
joining that crop to the meter crop by wall clock gives stack count and
cumulative damage on one row. Nine ten-hit runs at one fixed floor distance came
out monotone non-decreasing in stack count: 1 -> 135, 135; 2 -> 135; 3 -> 136;
4 -> 136; 5 -> 137, 139, 139, 139. See `docs/FINDINGS.md` section 15.

**Why it matters beyond itself.** `FINDINGS` 11.7 reports that a constant
per-hit value fits every FLOOR run and no off-floor run, and reads that as
constancy being a property of the clamp. **A buff of about 1% per stack
reproduces that exact split with no distance term at all** - invisible at 10.35
per hit where it rounds away, visible at 55 to 69 per hit where it does not. The
ten-point curve is untouched; the INFERENCE is contested.

**Measure it at the CEILING, not the floor.** At ~13.5 per hit a 1%-per-stack
effect is ~0.135 and rounds away - which is why the floor runs above give a
4-count spread and no more. At ~90 per hit it is ~0.9 per stack and ~3.6 at
five, several display units clear of rounding.

**Acceptance:**

- Ten hits pinned at ONE stack against ten allowed to reach five, at the near
  end of the curve, without moving between them. Report the solved interval for
  each, not the eyeballed deltas.
- A written statement of whether the buff survives switching targets: ten hits
  alternating between two enemies. "With each hit on the same enemy" implies the
  stack resets per enemy, so if it survives the switch it is not `Focus Fire`.
- Either a per-stack figure with its interval, or a written negative saying the
  effect cannot be separated from run-to-run variation at this precision.

**Do not attribute it to `Focus Fire` without that target-switch test.** The
talent was taken the same session, its tooltip scopes it to `Rapid Arrows`, and
measured inter-hit intervals of 2.27 to 2.87 s prove drawn shots rather than
Volley. Either its scope exceeds its tooltip or the buff is a base mechanic that
was always there. **The logs that could settle it were destroyed before anything
archived them.**

## OPS-8. The suite is not safe to run CONCURRENTLY - CLOSED 2026-08-26b

**This is the SECOND `OPS-8`.** The id was already spent on a ledger-collision
diagnosis closed 2026-08-12 (ledger `LL-0040`). Two items, one id - see
`OPS-12`. A grep for `OPS-8` returns both, so read the date.

Found 2026-08-26 by two independent refuters running the suite while other
agents ran it too. Sequentially the suite was deterministic - five clean runs in
a row **gave `1244 passed`, which was the count at the time and is not the
current one**. Under **concurrent** runs it went intermittently red: one refuter
saw 3 failures in 12 runs, another 2 in 5.

**Mechanism, proven not guessed:** `tests/test_no_pii.py` plants probe files at
the **repository root** (`_pipeline_probe_binary.png`, `_pipeline_probe_utf16.bin`)
to prove its scanner is not vacuous, while `tests/_tracked.py` walks untracked
files at that same root. A second pytest process scanning the root mid-plant
sees a file the first process is about to delete. The observed casualties are
`test_no_pii.py::test_the_repository_carries_no_encoded_identifiers` and
`test_lanes.py::TestNoFileIsOrphaned::test_every_tracked_file_is_owned_or_explicitly_cross_cutting`.

**Why this matters more than a flake:** `ops/merge_gate.py` re-runs pytest, and
CLAUDE.md mandates a **parallel multi-agent** workflow. So the gate that exists
to catch a dropped test can itself go red for a reason that has nothing to do
with the work being gated - and a gate that cries wolf is a gate people learn
to override.

**Acceptance:** the suite passes reliably when several pytest processes run at
once - demonstrate it by running N concurrent suites and observing all green,
having first watched the current code fail that same check. The probe files
must stay at the repository root, because scanning the real root is the point
of the guard; isolate by making the probe name unique per process, or by
teaching the tracked-file walker to ignore the probe pattern, or by serialising
through a lock file. **Do not weaken either guard to make this pass.**

### CLOSED 2026-08-26b - and the filed mechanism was wrong about the dominant case

**Re-measured before any fix was written**, because a filed mechanism is a
hypothesis: five concurrent FULL suites went red in **9 of 10 runs**, across
five different tests - and **neither of the two tests named above as the
casualties failed even once**. What actually breaks:

- **Shared probe PATHS, not shared scanning.** Every guard probe was planted at
  a FIXED name at the repository root, so two suites planted the same file and
  the first to reach its `finally` unlinked the other's evidence mid-scan. The
  two `tests/test_no_pii.py` pipeline probes were the most frequent casualties,
  8 of 10 runs each.
- **A suite that plants nothing was hit too.**
  `test_the_scannable_view_is_a_superset_of_the_authored_view` walks the tree
  twice and subtracts, so a foreign probe appearing between the two walks
  breaks it. That is the direction this item originally described. It is real,
  just far rarer than the collision.
- **Windows adds a third face.** `finally: unlink()` raises
  `PermissionError [WinError 32]` while another process holds the same path
  open, because Python's `open()` does not share delete.

**The fix**, with the probes still planted at the real repository root and
neither guard weakened - only the NAME changed:

- `tests/_tracked.py` gains `probe_path(stem)`, returning
  `_guard_probe_<pid>_<stem>` at the root. Unique per process, so no two suites
  can ever name the same file.
- `.gitignore` ignores `_guard_probe_*`. That is **one lever for all four**
  `--exclude-standard` sites in this repo - `tests/_tracked.py`,
  `ops/lanes.py`, `tests/test_lane_state.py` and `tests/test_tracked_walker.py`
  - because each takes its untracked pass that way. Patching them one at a time
  would have rebuilt the two-copies-of-a-rule trap that `tests/_tracked.py`
  exists to prevent. (Filed as **three** on the first pass and corrected by an
  independent refuter who counted them - a tally re-derived from the artifact
  has now been wrong in this repo often enough to be a rule.)
- `_published()` adds **this process's own** probes back, so a probe is still
  scanned by the guard that planted it, and filters foreign probes on the
  non-git fallback walk, which `.gitignore` cannot reach.

**Acceptance evidence:** 24 consecutive green runs at 6-way concurrency of the
full suite, against the measured 9-of-10-red baseline. Sequential suite 1252
passed / 1252 collected, ruff clean, merge gate OK against a baseline of 1244
measured with `--collect-only` before dispatching.

**Three mutations, each watched going red on a different guard**, because a
green guard proves nothing here until it has been seen failing:

- `_own_probes()` returning `[]` kills 5 tests, including **both** original
  `test_no_pii.py` pipeline probes - so the migrated probes are still genuinely
  scanned and the guards did not become decoration.
- `_is_foreign_probe()` returning `False` initially killed **nothing**. The
  fallback filter was decoration, because every test ran on the git path where
  the ignore rule had already removed the file.
  `test_a_foreign_probe_is_filtered_on_the_non_git_fallback_path` was written
  for it, and the same mutation now dies.
- Deleting the `.gitignore` line kills only the `test_lanes.py` orphan test -
  correctly, because `ops/lanes.py` carries no filter of its own and rests
  entirely on that rule.

**An independent refutation pass then found a hole the fix itself opened, and
it was a hygiene hole.** `_is_foreign_probe()` filtered by NAME across the whole
candidate list, **tracked files included** - so a file committed as
`docs/_guard_probe_notes.md` became invisible to the PII guard, demonstrated
with a real-shaped SteamID64 going GREEN through the repository-wide guard.
`.githooks/pre-commit` does no content scan, so nothing else caught it. A name
test cannot tell a concurrent suite's scratch file from a tracked file under the
same name, and on the git path `.gitignore` already draws that line correctly.
The filter now applies **only on the non-git fallback walk**;
`TestTheProbeFilterCannotHideATrackedFile` pins it, and the inverse mutation -
re-applying the filter to the git listing - reddens exactly that test.

**The trap this item set for its own fix**, recorded because it is the sharpest
thing here. The first version of the regression tests named their foreign probe
`_guard_probe_0_...` - a FIXED path, on the reasoning that pid 0 is never a
live process and so can never be mistaken for a real suite's probe. Six
concurrent suites then fought over that single file and it died on
`WinError 32`: **17 of 18 green, red for exactly the bug under test,
reproduced inside the test for it.** Only the concurrent run could see it. A
foreign probe now carries `<prefix><pid>other_` - foreign to every walker
because it does not match `<prefix><pid>_`, and unique on disk.

## OPS-12. Two ops ids each name two different items - CLOSED 2026-08-27

Found 2026-08-26b while closing the second `OPS-8`. The `OPS-` namespace was
reallocated without checking what was already spent, so **`OPS-7` and `OPS-8`
each name two unrelated items**:

| id | first item | second item |
|---|---|---|
| `OPS-7` | fragment path that is not a fragment - closed 2026-08-12, `LL-0039` | `advance_cycle` credits an unstarted item - OPEN |
| `OPS-8` | entry edited after integration misread as an id collision - closed 2026-08-12, `LL-0040` | suite unsafe under concurrent pytest - closed 2026-08-26b |

`OPS-1` through `OPS-6`, `OPS-9`, `OPS-10` and `OPS-11` are each used once, so
the reuse starts exactly where the 2026-08-12 batch ended - somebody resumed
numbering from the highest id they could see in the OPEN items rather than from
the highest ever allocated.

**Renumbering is the wrong remedy and this repo has already reasoned it out.**
`LL-0040`'s own conclusion is that renumbering an item records one piece of work
under two ids, corrupting the record while appearing to repair it. The ledger is
append-only, and `LL-0064` and the hand-off both already cite `OPS-8` meaning
the concurrency item. So the live meaning stays, and the collision is signposted
at each reference instead - done for all four references above.

**What is NOT done, and is the acceptance:** nothing stops a third collision. An
`OPS-` id is allocated by a human reading this file, with no equivalent of the
ledger's `next free id` check. Acceptance: allocating an already-spent `OPS-`
id fails a test. The id set must be derived by walking `ROADMAP.md` and
`docs/LEDGER.md` at run time - **a checked-in list of spent ids is exactly the
filed count this project has been burned by**, and it would go stale on the
first item added without touching it.

### CLOSED 2026-08-27 - `ops/ops_ids.py` and `tests/test_ops_ids.py`

**Nothing is checked in.** `spent_ids()` recomputes from both documents on every
call, and `next_free_id()` returns `max(spent) + 1` - above the maximum, never
into a gap, because a gap means an id was retired and reissuing it re-creates
the confusion.

**What counts as ALLOCATING an id**, since an id appears in prose constantly and
that is not allocation. Exactly two sites are counted: a top-level
`## OPS-<n>.` heading here, and a ledger ENTRY HEADING announcing a closure.
One item normally produces both over its life, so a heading marked CLOSED is
read as the same item as its closure:

```
allocations = closures + open_headings + max(0, closed_headings - closures)
```

Derived from the real documents: `OPS-9` scores 1 (one closure, no heading),
`OPS-7` scores 2 (`LL-0039` plus an OPEN heading), `OPS-8` scores 2 (`LL-0040`
and `LL-0066` plus a CLOSED heading), and `OPS-12` scores 1 - as a CLOSED
heading plus its one closure `LL-0068`, which is **not** the "heading, no
closure" this document first claimed. Closing the item moved its own row, and
an independent refuter caught the stale derivation in the same commit that
created it. Re-derive, do not cite.

**The guard is blind to 4 of the 12 ids in use, and that is measured.** `OPS-4`,
`OPS-6`, `OPS-10` and `OPS-11` all score 0, because each was opened or closed
only in ledger BODY prose - never in an entry heading and never as a roadmap
item heading. `OPS-6` is called "THE ONLY OPEN OPS ITEM" in `docs/LEDGER.md`
and is invisible here. The first draft of this item admitted only `OPS-4`,
which understated its own blind spot by a factor of four.

That is the deliberate direction of the error: reading entry bodies would catch
those four and flag many correct items besides, because a body mentions ids for
every reason there is. Over-reporting makes the guard red on correct work, and
a guard that cries wolf gets overridden - the argument `OPS-8` made about the
merge gate. The blind spot is also narrower than it sounds, because
`next_free_id()` uses `spent_ids()`, which counts **any mention anywhere**, so
all four invisible ids are still disqualified from being handed out. The
allocator prevents a collision; this detector only catches one that happened
because somebody did not use the allocator.

**The two known collisions are asserted as an exact set**, which is a record of
a measured state rather than a list of spent ids. It fails on a third collision
**and on a resolution**, so the exemption cannot outlive the defect it excuses -
the `lane_state.stale_claims()` shape.

**Acceptance evidence, both directions demonstrated against the REAL documents,
not only fixtures:**

- Planting `## OPS-9.` - an id `LL-0038` closed on 2026-08-12 - into this file
  turned the guard red: `expected: [7, 8]` / `found: [7, 8, 9]`, with a message
  naming `ops_ids.next_free_id()`. Reverted, green.
- Renumbering the OPEN `OPS-7` item to 13, simulating a resolution, ALSO turned
  it red: `expected: [7, 8]` / `found: [8]`. Reverted, green.
- Five mutations, each watched killing a different set, all re-measured against
  the FINAL code rather than an earlier draft of the tests: `over_allocated` ->
  `{}` kills 6; `ledger_closures` -> `{}` kills 7; dropping `open_headings` from
  the formula kills 4; a never-matching heading regex kills 8; making
  `roadmap_items` ignore fences kills 2. No survivors. Two of the mutation
  scripts failed to apply on their first attempt and their anchor asserts caught
  it, rather than letting a non-mutation read as a survivor.
- Suite 1277 passed / 1277 collected, ruff clean. Baseline 1253.

**A refutation pass then found the scanner was fence-blind**, one edit away from
a live false positive: a fenced worked example of an item heading, beside a
genuine heading for the same id, reports that id as over-allocated.
`docs/LEDGER.md` line 16
already carries a fenced entry template that matches the ledger-heading pattern,
inert only because it happens to carry no id and no closure word.

This repository had closed that exact bug before. `OPS-9` / `LL-0038` was the
heading GUARD and the heading PARSER disagreeing because only one tracked
fences, and its conclusion was that there must be **one** fence scan every
reader shares. This module was written as a third private reader in a
repository whose own ledger says why not to.

Fixed by extracting that scan into `ops/mdscan.py` - CommonMark rules, an
unclosed fence reported rather than silently swallowing the file - and pointing
both `ops/lane_state.py` and `ops/ops_ids.py` at it. The duplicate
`_fence_marker` and `_FENCE_MARKS` in `lane_state` were deleted rather than left
beside it, because two copies of a rule is two chances to drift.

**One consequence worth knowing:** adding `tests/test_ops_ids.py` to the ops
lane's roster made `.claude/commands/lane-ops.md` stale and
`tests/test_lane_contract.py` went red until
`python scripts/write_lane_contracts.py` regenerated it. The roster is not the
only copy of itself.

## PORT-1. The port block is guarded by a test - CLOSED 2026-08-29

`LL-0076` recorded, as a deliberate omission, that nothing stopped a port being
allocated outside this project's block. `LL-0077` closes it.

`tests/test_ports.py` (safety lane - it is a repository hygiene guard) fails on
a port constant outside **8810-8819**, and separately on `CLAUDE.md`'s own table
drifting from the block it declares or leaving a port in the block unaccounted
for. The sibling registry is **not** restated in the test: `CLAUDE.md` is the
authority, and a second copy is precisely the defect that left port 8812
contradicted between `CLAUDE.md` and `docs/ARCHITECTURE.md`.

Three mutations, each red on a different test: pointing
`overlay.window.CONTROL_PORT` at 8888 (Amberstone's block) kills two including
the positive control; deleting the `8815-8819` row kills the coverage test;
changing the declared block kills the drift test.

Nothing binds a port yet, so this guards an allocation rather than a service.
That is the point - the moment a service is built is the moment a stray constant
becomes expensive, and a guard added then arrives after the mistake.

## OPS-13. Source register completeness - REFUTED, then RE-CLOSED 2026-08-29c

Opened 2026-08-29 by item 8b, as its own item rather than a note inside that
item, because a caveat buried in a closed item is invisible to the next session.

Closed by ledger `LL-0080`. The guard is `tests/test_source_register.py`,
owned by the **safety** lane - see `ops/lanes.py`, which answers the
ownership question this item deliberately left open.

**THE FIRST CLOSURE WAS REFUTED. A three-lens adversarial pass on `af70a73`
found a LIVE false negative**, and `LL-0081` records the repair. The guard
asked `host in section`, a bare substring test, so `grandwiki.com` - cited
standalone in `docs/ECOSYSTEM.md` section 8 and carrying no register row -
passed on the strength of the neighbouring `mistfallhunter.grandwiki.com`
row. Under the same defect `x.com` passed inside `gamingpromax.com` and
`t.co` inside `grindnstrat.com`, which are the two most plausible
first-party sources a future session would reach for. Presence now requires
a host BOUNDARY, and `grandwiki.com` has a row of its own.

**The counts, re-derived after the repair. Every earlier figure in this item
was wrong at least once, so re-measure rather than cite:** 309 host-shaped
tokens in `docs/`, 238 denylisted, 71 surviving tokens, and **63 DISTINCT
external sources** once 8 case/`www.` duplicates collapse. Only that last
number is stable - the first three move every time a ledger entry names a
new file, which is precisely how the previous closure's figures went stale
inside a single commit. The item
originally filed 78/15/63 and the first closure filed 303/227/76; the 76 was
an overcount that counted duplicates and five of this repository's OWN
documents as external sources. The extractor is deliberately broad - it
matches any dotted token whose final label is 2-24 letters - because a
broader net has fewer blind spots at the cost of a bigger denylist, and
blindness is the failure this item exists to prevent.

**The denylist was adversarially probed, and THE PROBE ITSELF WAS WRONG THE
FIRST TIME - which is the most reusable lesson in this item.** The denylist
is the trusted surface, so a real source hidden in it would be `LL-0079`
wearing the other hat. The first probe screened members by whether their
final label was a 'real public TLD' - using a HAND-WRITTEN list of TLDs. That
list omitted `.md` (Moldova) and `.py` (Paraguay), so it reported 3
candidates when the true figure is 60-plus. **A hardcoded TLD allowlist, in
the audit written to guard against a hardcoded TLD allowlist.**

What survives re-derivation: 0 of the 232 members are uncited dead weight,
which is evidence the list came from measurement rather than guesswork, and
every `.md`/`.py` member resolves to a repository filename or module path
cited by other documents. No member is an external source. **Do not re-run
the filed probe as if its number were a baseline** - screen by reading the
members, not by matching a TLD list you wrote yourself.

The register in `docs/ECOSYSTEM.md` was proven complete by a checker that lived
in a session scratchpad and is now gone. The research lane wrote it there
because that lane writes no code and `tests/` belongs to other lanes. So the
completeness claim is true as of 2026-08-29 and has **no mechanism to stay
true**: the next document that cites a new domain silently makes the register
wrong, and the failure is invisible - a register that omits a source reads
exactly like a register that covers everything.

Same shape as items 0 and 9: the thing being protected is fine, the protection
is what is missing.

**The checker's logic, so it does not have to be re-derived - and the one way
it has already been got wrong.** Extract every `https?://host` and every bare
domain from every `*.md` under `docs/`, and assert each surviving host appears
between the `## Source register` heading and the `## 1. Item / loot databases`
heading in `docs/ECOSYSTEM.md`.

**Do NOT filter bare domains through a TLD allowlist.** The first version of
this checker did exactly that and was blind to `th.gl` for the whole of item 8b,
reporting a confident 62 of 62 while a cited source was missing. Match
`(label.)+label` with the last label as 2-24 letters, TLD-agnostic, and subtract
a **denylist** of the things that shape legitimately matches: file extensions,
dotted code identifiers (`str.splitlines`, `gvas.parse`, `payload.rows`), and
the GSDK package name `com.hermes.pstgame`. The ratio matters - a checker that
reports zero non-host noise is misconfigured rather than clean. (This
paragraph originally filed 15 denylist members and 78 tokens down to 63
hosts. Those were measured against the wrap's narrower extractor and do
NOT describe the shipped one; see the closure block above for the real
figures. Left here because the reasoning is still correct.)

**Acceptance:** a test under `tests/` that fails when a domain cited anywhere in
`docs/` is absent from the register, **proven non-vacuous** by citing a new
domain in some document and watching the test go red, then removing it and
watching it go green. The failure message must **name the missing host and the
file that cites it** - a failure that does not name the host is not actionable,
and this repo has already shipped one guard whose red state told nobody what
was wrong.

**Ownership question, deliberately not answered here.** The test guards a
research-lane document but must live in `tests/`, which research does not own.
`safety` owns the repository hygiene guards (`tests/test_ascii_hygiene.py`,
`tests/test_no_pii.py`) and this is one of those in shape - but it is a
doc-completeness check, not a redaction check, and nobody has decided whether
that stretches the mandate. Read `ops/lanes.py` for who owns a path, not this
paragraph.

## OPS-15. `precommit_gate._block` fails OPEN when stderr is unusable - CLOSED 2026-08-30

Closed by ledger `LL-0082`, on branch `lane/safety` and merged. Found
2026-08-29c by the adversarial pass on `af70a73`, filed rather than fixed
because it is not what that pass was reviewing and it predates the change
under review.

**REPRODUCING IT FIRST CORRECTED THIS ITEM TWICE, which is the reusable
part.** The text below predicts exit 1. The measured code was **120**, from
a SECOND path this item did not describe: CPython flushes the standard
streams at interpreter shutdown and exits 120 when that flush raises,
overriding whatever the script exited with. A fix built only to this item's
text would have caught the write failure, looked correct, and still failed
open. And a THIRD defect went unmentioned entirely - with stderr dead a
benign `ls -la` also exited 120, because the success path never writes to
stderr and so never got the chance to recover from it.

The fix is therefore two parts, not one: `_say` writes best-effort and
detaches a stderr it could not write, and `_exit` flushes both streams
before exiting and detaches whichever fails, so the exit code survives on
every path including the ones that never report.

**The gate had NO test before this** - `grep -rln precommit_gate tests/`
returned nothing. A guard whose whole job is refusing commits, with zero
coverage, whose one measured behaviour under stress was to permit.
`tests/test_precommit_gate.py` now carries 5, and both halves were proven
non-vacuous by one mutation each - each killing exactly one test, so the
two guard independent failure modes rather than overlapping. **It is not caused by the `pythonw.exe` switch** - both
interpreters behave identically here, which was measured across 14 cases.

`tools/precommit_gate.py` writes the reason to `sys.stderr` and only THEN
calls `sys.exit(2)`. If that write raises - a closed, null or non-writable
stderr - the outer `except Exception` handler writes to stderr again, raises
again, and the process exits 1 or 120. **A PreToolUse exit that is not 2 does
not block**, so a gate that cannot report its reason silently permits the
commit it was trying to stop. Measured in two constructed shapes; not
observed in the live runner, which does capture output.

The fix is ordering, not logic: decide, exit non-zero, and treat the message
as best-effort. A guard whose failure mode is fail-open is the one shape this
repository's safety lane exists to refuse.

**Acceptance:** a test that runs the gate on a blocking payload with stderr
made unwritable and asserts the exit code is still 2, proven non-vacuous by
restoring the current ordering and watching it go red.

## OPS-14. C: hit 100% mid-session, then recovered with nothing deleted - OPEN

Observed 2026-08-29 during item 8b. Recorded because it will hit the loop, and
because a session that has never seen it will misdiagnose it and start deleting
evidence. **This is a question, not a task** - nobody has measured the cause of
either half.

What was observed, in order:

- `Get-PSDrive C` and git-bash `df -h` **independently** reported **0.71 GB free
  of 954 GB**, so it was not one tool's mount view being wrong.
- Two unrelated commands died with `head: write error: No space left on device`.
- The first attempt to append ledger entry `LL-0078` failed with
  `OSError: [Errno 28] No space left on device` inside `append_entry`. **The
  ledger survived intact**, because that writer is atomic - tmp then replace -
  so the target was never opened for writing. This is the first time the atomic
  rule in `CLAUDE.md` has demonstrably saved a file rather than merely being
  good practice.
- Minutes later, with **nothing deleted by the session**, `Get-PSDrive C`
  reported **120 GB free**.

**What was ruled out, so nobody repeats it - RE-MEASURED 2026-08-31 because the
filed figure had gone stale by 3.3x.** `C:/ll-captures` is now **9.87 GB across
19,162 files**; it was **2.96 GB across 16,941** when this item was filed. `C:`
is 83.0 percent used with 161.6 GB free. The captures still cannot explain a
953 GB drive reaching 100 percent, so the ruling-out survives - but it now rests
on a number measured today rather than one recited from a fortnight ago, and the
**growth rate is itself a reason to measure `4d` before arming a watcher
permanently**. The capture evidence **must not be pruned in response** - the `LL-0016`
neighbourhood records that those directories are the only record behind several
published claims. A full-drive scan to find the real consumer **timed out at 10
minutes and was abandoned** rather than left half-finished.

**WHICH PRODUCER, measured 2026-09-01 while closing `4d`.** The tree has two
and they are nothing like each other in size. Counting watcher output by the
snapshot naming convention `<stamp>_<size>_<name>` rather than by directory
name - the distinction matters, see `4d` - the whole tree is 19,175 files and
9.884 GB, of which **405 files and 122.66 MB, 1.21 percent, are watcher
snapshots**. Essentially all the rest is frame captures: `2026-08-30` alone
holds 2,172 frames totalling 7,025 MB against 42.54 MB of watcher output the
same day. **So an always-armed watcher is not what threatens this disk, and
pruning to reclaim space would mean pruning FRAMES**, which is exactly what the
`LL-0016` neighbourhood says must not happen.

**Every figure above is post-arming.** Immediately BEFORE this session armed
its own watcher the tree was 19,162 files, byte-identical to the 2026-08-31
measurement - which was itself the evidence that no watcher had been running in
between, as `LL-0102` recorded. The session then added exactly 13 files and
13,019,536 bytes, so any capture-tree count quoted without an as-of moment is
stale the moment it is written, and this item has now been bitten by that
twice.

`C:` on 2026-09-01 is **83.3 percent used with 159.1 GB free**, against 83.0
percent and 161.6 GB the day before. That 2.5 GB went somewhere OTHER than
`C:/ll-captures`, which did not grow at all - a small data point for the open
question below, and not an answer to it.

**Why it matters beyond tidiness:** the STOP CONDITIONS in
[`docs/HEADLESS.md`](docs/HEADLESS.md) assume a writable disk. An unattended
loop that hits this mid-write gets a partially applied session, and only the
atomic-write rule stands between that and a corrupted durable record.

**The question for the operator, not answered here:** is something on this
machine - a sibling project, a build cache, a VM disk, a shadow copy - expanding
and contracting by roughly 119 GB, or was this a one-off? Answering it needs a
directory-level scan that survives longer than a 10-minute tool timeout, which
is an operator action rather than a session action.

## 11. Bind the remaining affix ids - TWO LEFT (101, 214), both now need the client

Opened 2026-08-30. Ledger `LL-0085` and `LL-0086`.

**Five are already bound** - `201 = Valor`, `208 = Fervid`, `211 = Ranged` by
the wall-clock join, **`209 = Seeker`** and **`212 = Fervor`** added 2026-09-01
by two different methods described below. **Two remain: `101` and `214`**, and
each is now blocked for a MEASURED reason rather than an assumed one.

### `212 = Fervor`, by SLOT ATTRIBUTION on the `Affix Details` panel

**The strongest binding this item has produced, because it is confirmed twice on
two different loadouts.** The `Affix Details` screen prints one row per active
affix with a per-slot count, and for ARMOUR the second cfgId digit gives the slot (see
`docs/OBSERVED_IDS.md`), so a row can be attributed to a specific equipped item.

**There are exactly TWO openings of that screen in the entire corpus and both
have full-scene frame coverage.** The first, `f0119_22.28.15`, was already
transcribed. **The second, `f0124_22.54.52` in `reanchor`, had never been
opened by any session** - found by listing the window-open events rather than by
looking where frames were expected.

| panel | rows and the slots carrying them |
|---|---|
| `f0119_22.28.15` | `Fervid` Lv.2 pants+boots, `Fervor` Lv.2 **helm+chest**, `Seeker` Lv.1 weapon, `Wealth` Lv.1 necklace |
| `f0124_22.54.52` | `Fervid` Lv.2 pants+boots, `Ranged` Lv.2 weapon+gloves, `Fervor` Lv.2 **weapon+chest**, `Wealth` Lv.1 necklace |

**In both, the CHEST slot contributes a `Fervor`, and in both the chest item is
`1230304`, which carries item-borne affix `212` and has NO gem.** Every other
row on both panels is independently accounted for, so nothing else can be
supplying it.

**Every row reconciles, which is what makes this more than a set difference:**
`Fervid` is affix 208 on `1430303` (pants) and `1530303` (boots); `Ranged` is
affix 211 on the weapon `3060404` and on `1360303` at gloves; `Seeker` is affix
`209` on the weapon `3030403`, **confirming that binding a third independent
way**; `Wealth` is the necklace `1630103`, which has no item-borne affix and
carries gem `224110`; and the second `Fervor` source is gem `223106`, rendered
in the gem row of two separate item tooltips.

**A BARE SET DIFFERENCE WOULD HAVE GOT THIS WRONG, and nearly did.** Counting
only affix instances leaves `{212, gem 223106, gem 224110}` mapping onto
`{Fervor, Fervor, Wealth}` with two consistent assignments, and the first draft
of this section picked the wrong one - `212 = Wealth`. **The per-slot counts are
what disambiguate it**, and they are the reason this panel is worth more than
any tooltip.

### `101` and `214` - why each is blocked, measured rather than assumed

- **`101`** sits on item `1430301`, the PANTS slot. It was never equipped during
  either panel opening - `1430303` held that slot both times - so the panel
  route cannot reach it. Its tooltip route fails for a sharper reason than
  "no tooltip was on screen": at its only frame-covered event, `19:54:35`, the
  hover lasted **262 ms** before the next item was hovered, against a capture
  running at about **1 frame per second**. `s01222_19.54.35` shows the warehouse
  with a slot highlighted and no tooltip, exactly as recorded. **The capture
  cadence, not the capture resolution, is what loses it.**
- **`214`** has no `exEquip` record, no durability record and appears on neither
  panel. It is known only from trade-filter requests. **Nothing on disk can
  reach it**, and that is now a measured statement rather than an inference.

### THE DURABILITY JOIN - added 2026-09-01, ledger `LL-0107`

**A frame can be joined to the log by DURABILITY instead of by wall clock**, and
that removes this item's hardest constraint. Item records carry
`"durability":<int>`; the tooltip renders it as a percentage of a per-tier
maximum, and **that maximum is `900 + (third cfgId digit) * 100`** - measured at
every tier 1 to 6 as 1000, 1100, 1200, 1300, 1400 and 1500, with every tier's
largest observed value landing exactly on it.

So an on-screen `97%` on a tier-3 item means a logged durability of 1164 to
1175, which picks one record out of the corpus without needing the frame and the
log line to coincide in time.

**`209 = Seeker` was bound this way, and the argument does not even need the
durability** - that only corroborates it:

- The frame `s01223_19.54.36` (`25/scene`, 1280x720) shows an **Equipped**
  `Oil-soaked Wooden Bow`, `Rare Bow and Arrow`, carrying **`Seeker` Lv.1** at
  **97%** durability, in the item-borne affix position with no gem slot.
- The log's affixed WEAPONS are `3030403` (affix 209), `3030404` (affix 211) and
  `3060404` (affix 211). **`211 = Ranged` is confirmed three independent ways**
  and the frame does not show `Ranged`, so the item is neither of those two.
- `3030403` is the only affixed weapon left, so its affix `209` is `Seeker`.
- **Corroboration:** `3030403` is logged at 1166/1200 = 97.17%, which is what
  renders as `97%`, and it is the ONLY weapon-range record that would.

**The limit, stated:** this assumes the bow on screen is one of the eight
affixed `cfgId`s the log records. A ninth affixed weapon never logged would
break it. The durability record is also 77 minutes older than the frame, so it
holds only if the bow was not used in between - which the `97%` reading is
itself evidence for, and which is why the elimination argument is the primary
one and durability the corroboration.

**The recipe for the two ids this could still reach**, from the same table:
`101` sits on item `1430301` at 98% and 100%, and `212` on `1230304` at 94%,
98% and 100%. **Prefer a distinctive percentage** - 97% picked out one weapon,
whereas 100% is shared by many items and 98% is shared by `1430301` and
`1230304` both. `214` has no durability record at all and is unreachable this
way.

### Why the wall-clock sweep missed this, and it is NOT the sweep being careless

The recorded conclusion was that `101` and `209` "are lost because **no usable
tooltip was on screen** at any instant a full-scene capture was running". **The
narrow half of that survives and the generalisation does not.** The sweep
selected frames at the four tooltip-EVENT timestamps and correctly found no
usable tooltip at any of them. But the tooltip for `3030403` was on screen at
`19:54:36` - **one second after** the 19:54:35 event the sweep checked, and 33
seconds after the 19:54:03 event for that same item.

**A tooltip is rendered when the player hovers, and the `cfgid ==` line fires on
its own schedule.** Selecting frames by the log event's timestamp therefore
looks in the wrong second. That is `LL-0100`'s rule turned on the sweep itself:
the measurement was exact and answered a different question from the one that
mattered.

**They are not blocked on the game. They are blocked on the CAPTURE**, and that
distinction is the whole item. Every one of the four failed for a reason that a
different capture would have prevented:

- `212` has FOUR trade-filter requests, two of them singletons - ideal join
  material - at 22:43:54 to 22:44:11 local on 2026-08-25. That falls between the
  `talents` capture (ends 22:29:52) and `reanchor` (starts 22:53:14). The frames
  were never taken. Checked against the COMPLETE 14-directory capture inventory,
  not a partial one - an earlier version of this item cited a five-window list
  that omitted nine directories.
- `214` occurs once in the whole corpus, inside `[212,211,214]`, in that same
  uncaptured window, and has never been seen on an item.
- `101` and `209` ARE covered by a **1280x720 full-scene** capture at their
  tooltip timestamps, and are still unrecoverable because **no usable tooltip
  was on screen** in any covering frame. This is the ORIGINAL diagnosis and it
  is correct. See `docs/AFFIXES.md` for the per-id table.

  **A "correction" to this line on 2026-08-30 was ITSELF WRONG and is
  withdrawn.** It claimed the two ids are "not covered by any capture at all"
  and cited three wall clocks - `18:37:02`, `18:38:16`, `21:29:30` - none of
  which any capture covers. Those three are real, but they are **`exEquip`
  inventory-snapshot events**, the wrong event family. The events that matter
  are the tooltip opens, `TS.UI: cfgid ==`, and they land at local `19:54:03`
  for item `3030403` (affix `209`) and `19:54:35` for item `1430301` (affix
  `101`) - both **inside** the `25/scene` window of `19:32:34` to `20:12:34`.
  Re-derived by walking every line mentioning either item id across the three
  distinct log sessions and bucketing by event kind.

  **HOW THE WRONG CORRECTION HAPPENED, because it is a NEW failure mode.** The
  two earlier versions of this line asserted coverage without deriving any
  timestamps. The third derived timestamps carefully - **for the wrong event
  type** - and never checked which event family the claim it was overturning
  referred to. A measurement can be exact and still answer a different question
  than the one asked. **Before overturning a recorded claim, establish what it
  was measuring**; re-deriving from a pattern of your own choosing measures your
  pattern, which is the same defect as an empty grep wearing better clothes.

There are EIGHT full-scene capture sets **within `C:/ll-captures`**, three at
2560x1440 - the claim that only one exists was false and is withdrawn. **A
NINTH sits outside that tree**, at `~/.lanternlight/frames` (2026-08-09,
2560x1440, 218 PNGs), invisible to a walk of `C:/ll-captures`; it is the only
set holding talent page-two hovers. No game video exists on the machine.
The binding constraint is not resolution alone: a tooltip has to be open, held
long enough to land in a frame, and identifiable as the right item.

**Two routes exist and they are COMPLEMENTARY** - neither reaches the whole id
space. Filter-only: `201`, `214`. Item-only: `101`, `209`. Both: `208`, `211`,
`212`. The item-tooltip route is validated against a known answer (item
`3060404` -> affix `211` -> `Ranged Lv.1` on frame `f0636`), so it is a proven
method and not a hopeful one.

**Cheapest first:** `212` needs no shopping. The operator still holds item
`1230304` carrying it, so it is one tooltip hover with a full-screen capture
running.

**A THIRD ROUTE was found 2026-08-30c and it is cheaper than either, because it
needs no deliberate action at all.** Equip an item whose affix cfgId the log
carries, with the **`Affixes` panel OPEN** across the equip, and the affix that
appears NAMES that id. It has never fired for a precise reason: of 23
single-slot equip events across three logs, exactly one involves a known-affix
item during a full-screen capture, and the panel is closed on both sides of it.
**The recipe is one sentence - keep the `Affixes` panel open while equipping** -
and it turns ordinary gear changes into id bindings. Recorded as `RES-26`.

**A fourth surface exists and is unexplored: WINE.** The log carries
`wines[{id:1, affixes:[208,211]}]`, so wine carries affixes too, and `Victory
Wine` is brewed from `Malt`. A wine screen showing an affix beside a wine id
would bind ids the same way.

**Acceptance:** for each id bound, a new row in `docs/OBSERVED_IDS.md` naming
the id, the name, and the method, plus the frame filename and the UTC log
timestamp it was joined to. A binding read off an ICON rather than a ROW LABEL
does not count - several glyphs are confusable at capture resolution. Recording
that `101` or `209` has no filter row at all is itself a result worth writing
down, since it is currently unknown whether they are filterable.

**Run a full-screen poller during ordinary menu use.** This item needs no
deliberate experiment; it needs the frames to exist when the operator happens to
open a tooltip or a filter.

### `101`'s blocker is now EXACT, measured 2026-09-01c - NOT a credit

Found while auditing configuration for item 12, and recorded here so the recipe
stops being approximate. **Nothing below binds `101`; this item stays open.**

The `Affix Details` screen opens as
`TS.UI: Verbose: [WindowHandle] open WBP_EquipSkill_DetailPrompt`, view class
`AffixDetailPromptView_C`. Counted over all four maximal logs, `LL-0108`'s
"exactly two openings in the whole corpus" is **re-measured and stands**: two,
both on 2026-08-25b, local `22:28:10` and `22:54:52`, and zero in every other
session including both `1.0.15` logs.

**And `1430301` - the item carrying `101` - is at the PANTS slot for the whole
of the 2026-08-25 session**, measured against `server_EquipArmors` rather than
against a single record: the array
`[1120301, 1230304, 1320301, 1430301, 1520301, 1630102, 1720201]` appears in
**46 payload lines from local 18:37:18 to 20:24:31**, and the only variant,
at `19:54:04`, differs solely by the helm coming off. That session has **zero**
`Affix Details` openings.

**It is worn in session B too, and saying otherwise was this paragraph's second
error.** `1430301` sits at pants on 2026-08-25b from `21:29:32` to `21:35:58`,
and is replaced by `1430303` from `21:36:22` onward. Both `Affix Details`
openings - `22:28:10` and `22:54:52` - fall **52 minutes or more after that
swap**, and the pants slot at each is pinned independently: the payload at
`22:26:39`, 91 seconds before the first opening, and the one at `22:28:56`, 46
seconds after it, both read `1430303`.

So the two facts never overlap: **the item was on the character for about six
minutes in a session whose screen openings came nearly an hour later, and for
two hours in a session that never opened the screen at all.** That is a
measured miss, not an assumed one - and it is tighter than the first draft,
which claimed the item was worn in only one session and rested the other half on
a `roleInfo` record 21 minutes after the opening it was supposed to describe.

**A payload-shape trap, found in that same sweep and worth one line:** the
unequip-all state serialises as `cfgIds-[0,0,0,0,0,0]` - **SIX** elements, where
every other payload in the session carries **seven**. A reader that assumes a
fixed seven-slot array will mis-index or crash on it. It occurs 3 times, at
local 19:51:09 through 19:51:36.

So the two facts are disjoint in time: **the one session where the item was on
the character never opened the screen, and every session that opened the screen
had a different item at pants.** No resolution, cadence or window-width change
could have bridged that, which retires the last hope that `101` is recoverable
from existing frames by looking harder.

**The recipe is therefore checkable BEFORE any frame is read.** Equip `1430301`
at pants, open the `Affix Details` screen while it is worn, and confirm success
by grepping the session log for `WBP_EquipSkill_DetailPrompt` - if the token is
absent the attempt failed and no capture needs opening at all.

## 12. The client was PATCHED - the backward comparison is IMPOSSIBLE, a forward baseline is OPEN

Opened 2026-08-30. The log's own marker `TS.Default: [Startup] Version:` reads
`1.0.14` / Build Date `20260818232428` in both rotated backups and **`1.0.15` /
`20260826170036`** in the 2026-08-30 log. The client changed between
2026-08-26 and 2026-08-30.

By `docs/OBSERVED_IDS.md`'s own standing rule, **every row in it dated
2026-08-25 is now provisional** - including the training-ground damage series
that `docs/FINDINGS.md` section 11 rests on.

Also recorded here so nobody re-derives it: the literal string `buildid` occurs
**zero** times in all three logs, so the Steam buildid `24813185` recorded in
`OBSERVED_IDS.md` is a depot value the log can neither confirm nor refute.
Anchor future passes on `Version` plus `Build Date`, which is first-party and
in-log.

**Acceptance, AS ORIGINALLY WRITTEN and now known to be unachievable - kept
here because the reason it fails is the result:** re-measure the 10.35-per-hit
floor value on `1.0.15` and record whether it moved. If it did not, say so
explicitly - a re-measurement that confirms is worth as much as one that
overturns, and this project has no record of any value being checked across a
patch boundary.

**That last clause was FALSE when it was written.** `LL-0098`, filed the same
day, recorded the safe-circle radius as checked across this very boundary and
found unmoved. Re-measured here rather than cited: `Radius 25597.265625` is
byte-identical in both `1.0.14` maximal logs and in the `1.0.15` maximal log,
and absent from the short `1.0.15` log which never loads a dungeon. The
defensible narrowing is that no measured **combat** quantity had been checked
across a patch boundary.

### WORKED 2026-09-01c - the data existed all along, and the acceptance cannot be met

Ledger `LL-0110`. The item said this needed the client. **It did not need the
client to get an answer, and the answer is that the question as posed can never
be answered.**

**A `1.0.15` training-ground capture has been on disk since 2026-08-30.** That
session entered `LoadMap(/Game/Project/Maps/TrainingGround/Training)` **twice**,
local `00:40:23-00:44:31` and `00:45:16-00:49:10`, and 355 full-screen
2560x1440 frames cover both windows with the `Total Damage` meter legible in
124 of them. **No session had read it - though the previous session's
hand-off had already NAMED that set as the one to check**, so this is a
follow-through on a live pointer rather than a discovery, and calling it
"nobody had looked" would take credit that belongs to whoever wrote the
pointer.

**What crossed the patch boundary intact.** One run of ten hits solves to a
constant per-hit value under the round-to-nearest model - `v` in
`[579/10, 695/12]` = `[57.9000, 57.9167]`, width `1/60`, with truncation empty
and no integer fitting. So **section 11's display model - a real-valued running
sum rounded for display - is reproduced on `1.0.15`.** The standard training bot
is also unchanged: `classId` 10, nine items, zero affixes, zero gems, **7 items
at durability 1400 and 2 at 0**, in every session on both clients - 20 spawns in
the 2026-08-25 session, 16 on 2026-08-25b, 4 on `1.0.15`.

**That "unchanged" is about the STANDARD bot and the 10.35 session had a second
kind.** A single `classId` **12** bot spawned at local 18:38:27 with 8 items -
**6 at durability 1100 and 2 at 0**, the necklace and ring, exactly as on every
other actor. It is the only non-class-10 bot in the corpus, and the room's own
`Weapon Archetype: Blackarrow` setting predicts exactly that. So section 11's
runs had at least two candidate targets on the floor and the log does not say
which was shot. It does not overturn 10.35; it means that measurement's TARGET
is one hypothesis short of pinned.

**Why it is nevertheless NOT a re-measurement of 10.35.** The configuration
differs on nearly every axis, and this is now measured rather than assumed,
from an `OnCustomInfoReady roleInfo` record the log emits within a second of
every training load. Against the session that produced 10.35: character level
**3 against 5**, **nine items equipped against four**, four affix instances
against none, and the held weapon `3030403` carrying affix `209` against a bare
tier-1 `3010401`. **All NINE of the nine equipment slots differ**, in both
1.0.15 windows - re-counted slot by slot at merge time after a first draft of
this line filed "eight of nine", which was the merger's own arithmetic and not
any agent's. A filed count is a hypothesis.

**THE ACCEPTANCE IS UNACHIEVABLE, AND NOT FOR WANT OF THE CLIENT.** 10.35 was
measured at character **level 3**. The character has been level 5 since
2026-08-25 and levelling does not reverse. Section 11's conditions cannot be
reconstructed on this character at all - not today, not with the client open,
not ever. The item asked for a comparison whose baseline was destroyed before
the item was written.

**The exact scope of "unachievable", because the word is doing real work here.**
It is unachievable ON THIS CHARACTER. A *new* character is not excluded in
principle - but it would have to be held at level 3 AND carry all nine of the
2026-08-25 items, `3030403` included, and this document does not claim to know
whether those items can be moved between characters. That is a materially
different and larger task than "re-measure a number", which is why the item is
being re-pointed forward rather than left open against a criterion nobody can
meet. If a future session establishes that item transfer works, this paragraph
is the one to revisit.

**Acceptance, REPLACED.** Since the backward comparison is closed, close the
item forward instead: **record a `1.0.15` combat baseline complete enough that
the NEXT patch boundary is testable.** That means one meter run whose full
configuration is captured at the same wall clock - the `roleInfo` equipped set,
the character level, and the `Training Room Settings` panel photographed open -
plus the run's own `(hit count, total)` pairs. The reason the current boundary
is untestable is precisely that this was never recorded; recording it once
costs one training session and permanently fixes the defect.

**A caution for whoever does it.** Constancy is NOT sufficient evidence that a
run sits on the floor. This session found two segments of one `1.0.15` visit
each admitting a constant, at about 57.9 and about 8.65, and they cannot both
be a minimum. See `docs/FINDINGS.md` section 16 - the likely reconciliation is
that constancy indicates a stationary shooter rather than a clamp, which
narrows the diagnostic `11.7` offers.

**Also delivered, and it is the reusable half:** the `Training Room Settings`
panel has three `Bot Settings` fields - `Weapon Archetype`, `Difficulty` and
`Equipment Rarity` - that configure the TARGET and so parameterise every damage
number the room has ever produced. This repo had recorded the panel's engine
names since 2026-08-25 and never once read its contents.

### DECISION GATE FOR THE OPERATOR - `CLAUDE.md` carries a claim the client refutes

Not answered here, because `CLAUDE.md` is cross-cutting and reserved for the
operator or a merger holding the whole picture - a lane may not edit it.

Its **Measurement doctrine** section says "Nobody has published cooldowns,
damage coefficients or stealth durations for this game. Any site quoting a
second value is fabricating one."

**The first sentence is now false as written.** The game publishes affix
cooldowns exactly, in seconds, in item tooltips - `10s` and `60s`, quoted in
`docs/AFFIXES.md` - along with full affix ladders carrying exact percentages.
`docs/CLASSES.md` had the same blanket in two places and both were narrowed on
2026-08-30 to say **class ability**, which is the form that survives contact
with the client.

The second sentence still stands and is the load-bearing half: a site quoting a
number it did not read off the client is still fabricating one.

**The decision:** whether to narrow `CLAUDE.md`'s wording the same way. The risk
of leaving it is that the doctrine reads as a licence to skip the client, which
is precisely the sourcing error that `LL-0079`, `LL-0081` and `CLASSES.md` C14
all record - the answer was not hard to get, it was being sought in the wrong
place.

## 13. Page-2 talent NODE TEXT - CLOSED 2026-08-30e, and its OWN premise was false

Opened 2026-08-30d, rewritten the same day, **closed and corrected 2026-08-30e.**
Ledger `LL-0093`, `LL-0097`, `LL-0098`.

**Delivered: all 16 page-two node tooltips**, verbatim with a frame named for
each, in `docs/OBSERVED_IDS.md` under "Page-two node tooltips". The acceptance
criterion asked for one. `Gyldenmist Tolerance`, named here as the highest-value
single node, reads off `f0101_16.05.00`:

> Increases resistance to the `Gyldenmist`, slowing the rate of `Gyldening`.

It did **not** settle the `PlayzoneData` question - see `docs/FINDINGS.md`
10.9.1. The talent text is purely temporal, the zone fields are purely spatial,
and no log joins them. The binding stays refused, which is the outcome this item
said it would accept.

### THIS ITEM'S OWN PREMISE WAS FALSE, and that is the part worth keeping

This item said: "`OBSERVED_IDS` records node NAMES - `Steady Stealth`,
`Cold Infusion`, `Gyldenmist Tolerance` and the rest - **but not what any of
them does**."

**It records what two of them do**, and has since 2026-08-09.

Note which sentence is quoted, because the item's next line - "page one has four
such texts quoted in `docs/AFFIXES.md`; page two has none" - is TRUE as scoped:
`AFFIXES.md` really does carry four page-one texts and zero page-two ones. The
false claim is the one about `OBSERVED_IDS`, the file the item told its reader to
open first. **Quoting the defensible sentence instead of the false one would have
made this correction look like a quibble**, and a first draft of this rewrite did
exactly that. `Crippling Pain` (Bomb Engineering, Lv. 9) and
`Swift Exit` (Woodling Expert, Lv. 10) have been quoted in
`docs/OBSERVED_IDS.md` since **2026-08-09**, in the starred list two tables
below the cluster table this item cites as its evidence.

**This item WAS the correction to a rediscovery failure about this same screen**
and it shipped a rediscovery failure of the same shape, one table lower in the
same file. The previous version asked a future session to capture page two,
which was three weeks on disk. This version asked for tooltip text that was
partly on disk too. The refutation pass that caught the first one checked the
cluster table and the node-name table and stopped one table short.

**The transferable rule, which is now narrower and harder than "open the file":**
grep for the CLAIM, not for the section you remember. Both failures were by
authors who had the right file open. Reading a file's headings is not reading
the file, and neither is checking the one table that your claim happens to cite.

**Also corrected here:** the two 2026-08-09 quotes carried NO FRAME. Both are
now attributed - `f0081_16.04.16` and `f0090_16.04.36` - by locating them in the
capture, which makes every talent tooltip in the repo frame-cited.

**A capture fact that was never written down and cost a slice:** the 2026-08-09
frames live at `~/.lanternlight/frames/`, **outside `C:/ll-captures/`**. It is a
2560x1440 full-scene set of 218 PNGs - 217 in the `f`-series plus one
`skills_` frame - and it is the ONLY set holding page-two
hovers. A sweep that walks `C:/ll-captures` alone will never see it, and one
did not.

**Settled in passing:** a LOCKED node still renders its full tooltip on hover.
The 2026-08-09 character is Level 2 with every page-two cluster gated at Lv. 6
or above, and all 16 tooltips render anyway. The level-5 capture yields no
page-two text not because locked nodes are mute but because nobody hovered them.

## 14. CLOSED 2026-09-01 - the premise is REFUTED, the two bows are two TYPES

Opened 2026-08-30d. Ledger `LL-0096`, which withdraws the claim that it does.

The log shows 8 affixed item cfgIds each mapping to exactly ONE affix triple,
stable across three logs and a client patch, with the field literally named
`fixed` set `true`. That looked like "the affix is a property of the item TYPE".

**Two instances of an `Oil-soaked Wooden Bow` carry DIFFERENT affixes** -
`Seeker` in one frame and `Ranged` in another, same base stats, different
durability. One character owning one instance of each type produces the log's
pattern whether the affix is fixed or rolled, so the log cannot distinguish the
two models and the UI says they differ.

**The honest limit:** the two bows are matched by display NAME and base stats,
not by `cfgId`, and two cfgIds could share a name. The log carries no `exEquip`
for either, so this cannot be closed from disk.

**Acceptance, as written:** two instances of one item type, both with their
`cfgId` visible in the log AND their affix visible on screen at the same wall
clock. If their affixes differ, the roll is per-instance and `fixed:true` means
something else.

### CLOSED 2026-09-01 - and not by meeting that acceptance, but by refuting the premise

**The two bows were never two instances of one type. They are two different
`cfgId`s that share a display name and base stats**, held simultaneously in
adjacent slots with distinct 19-digit instance ids:

| cfgId | slot | affix triple | durability seen | on-screen affix |
|---|---|---|---|---|
| `3030403` | 10 | `(209, 1, true)` | 1166/1200 = 97.17%, 1027 = 85.58% | `Seeker` |
| `3030404` | 11 | `(211, 1, true)` | 1137/1200 = 94.75%, 1200 = 100% | `Ranged` |

Both render as `Oil-soaked Wooden Bow`, `Rare Bow and Arrow`, `23 Attack`,
`+2.00% Physical Damage`. **`LL-0096`'s own "honest limit" turns out to be
exactly what happened** - it warned that "two different cfgIds could share a
name", and they do.

**So the withdrawal in `LL-0096` is itself withdrawn, and the type-to-affix
mapping SURVIVES.** Every one of the eight affixed cfgIds still maps to exactly
one affix triple, and no observation contradicts it. Emberforge may treat an
item's affix as derivable from its `cfgId` - though NOT from its display name,
which is the trap this item existed to find.

**What is still NOT established, stated so nobody reads more into this than it
carries:** nothing here shows that two items sharing a `cfgId` must share an
affix. No such pair exists on disk. What is refuted is the specific evidence
that was offered against the type-level model, not the general possibility.

**How it was resolved, and the method is the reusable part - see item 11.** Not
by the wall-clock join the acceptance asks for. The item records in the log
carry `"durability":<int>`, and the tooltip renders that as a percentage of a
per-tier maximum, so **durability is a join key that needs no wall-clock
coincidence at all**.

## Ordering note

**Items 2b, 2c, 2d, item 7's shipped-code half and item 3 are CLOSED as of
2026-08-12.** `lanternlight/damage.py` reads the damage series and
`lanternlight/tail.py` follows the log, so both the extractor and the live spine
are shipped code rather than scratchpad analysis.

**Item 7b is ANSWERED as of 2026-08-25** (ledger `LL-0049`, `LL-0050` and
`LL-0051`, all corrected by `LL-0052`). The training ground exists, it is **not a match** so it
writes no `DamageCollectonDataSet`, and its damage surface is the on-screen
**Total Damage** meter - a pixel rig, not a file rig. Outgoing damage is
measured: **10.35 per hit** on the damage floor, plus a ten-point falloff curve.
What remains open under 7b is listed in that item: the step-versus-tangent
question, the headshot mechanism, and whether the ~1.3x per pace is real.

**10.35 CARRIES A SCOPE AND IT IS NOT OPTIONAL** - stated here because this
paragraph is where the number gets recited without one. It is a `Blackarrow`
right-click standard-arrow **body** shot, at floor distance, on client `1.0.14`,
**at character level 3 with the nine-item loadout of 2026-08-25 including weapon
`3030403`** - and against a target that is **not fully pinned**, because that
session spawned both the standard `classId` 10 bot and a single `classId` 12
one, and nothing recorded says which was shot. Writing "against the training
bot" here, as a first draft of this very paragraph did, commits the exact defect
the paragraph exists to prevent. That loadout is gone and the level does
not reverse, so 10.35 is now a HISTORICAL reading that cannot be reproduced -
see item 12. It remains correct as measured; it is simply no longer a value any
future session can check.

**The next item depends on whether the client is open.**

- **Client open:** 7b's remaining threads are all cheap and all need it. Fold
  in items 1, 4b, 5, 6, **11** and **13**, which also need the client and none
  of which deserves its own session. **Item 11's cheapest route needs no
  deliberate action at all**, only that the `Affixes` panel be left OPEN while
  equipping anything. **Item 13 is CLOSED** - all 16 page-two node tooltips are
  recorded in `docs/OBSERVED_IDS.md`, each frame-cited, so do not fold it into a
  client session. **Arm the wide-shot poller before the first run** -
  the first sweep of 2026-08-25 had to be re-run because its distances were
  inferred from clock order rather than recorded (`docs/FINDINGS.md` 11.10).
  **Make that poller FULL-SCREEN, not a crop** - though note the reason is NOT
  the one this paragraph used to give. It blamed a 500x310 HUD crop, and that
  cause was refuted: `101` and `209` sat inside a 1280x720 FULL-SCENE capture
  and are lost anyway, because no usable tooltip was on screen at the covering
  frames. Full-screen is necessary and NOT sufficient - the tooltip has to be
  open and held. A full-screen poller still costs disk and nothing else, and it
  turns ordinary menu use into evidence.

**Item 12 is BOTH a caveat and, since 2026-09-01c, a task.** The client moved
from `1.0.14` to `1.0.15` between 2026-08-26 and 2026-08-30, so any measurement
dated 2026-08-25 that a session leans on should be re-checked before being built
on rather than assumed to still hold. What changed is that the backward check is
now known to be **impossible** - 10.35's baseline was level 3 and the character
is level 5 - so item 12's replacement acceptance is a FORWARD one: capture a
`1.0.15` baseline whose configuration is recorded at the same wall clock as its
meter run. That needs the client and belongs in the client-open list.
- **Client closed:** item **7c** (read the meter without a human reading it) is
  now the only specified fallback. Item 4c closed 2026-08-25b, **OPS-8** closed
  2026-08-26b, and **OPS-12** and **OPS-7** both closed 2026-08-27, so none of
  them is the fallback any more. **`OPS-10`, `OPS-11` and `OPS-13` all closed
  2026-08-29b** (ledger `LL-0080`), so none of those three is the fallback
  either. `OPS-6` remains open and is an operator decision, not a task.
  `OPS-14` is likewise an operator question about this machine's disk.
  **`OPS-15` closed 2026-08-30** (ledger `LL-0082`), and item **7c's**
  fresh-clone gap closed the same day (`LL-0083`), leaving only 7c's WHITE
  row - which is blocked on a capture, not on a session. **So there is no
  fully specified client-closed task left.** **That ceased to be true on
  2026-08-31:** item **`4d`** - arm the session watcher automatically - is fully
  specified, is pure code and tests, and needs no client at all. It was split out
  of `4c` precisely because `4c` is in the loop's `completed` list and work
  parked there is invisible. ~~**`4d` is the client-closed task to pick up.**~~
  **`4d` CLOSED 2026-09-01** (ledger `LL-0109`), so it is not the fallback any
  more either. ~~**The client-closed task is now item `7c`'s reader**, with two jobs: teach
  it the thousands separator, and record that it fits a full-screen frame at
  crop origin `(2058, 390)`.~~ **BOTH DONE 2026-09-01d** (ledger `LL-0112`,
  corrected by `LL-0113`). `MIN_GLYPH_WIDTH` was not lowered; the reader now
  returns **118 of 124** panel-up frames with **ZERO disagreements**, up from
  61, and the crop origin is recorded in the module's own docstring.

  **So there is again no fully specified client-closed task.** What remains on
  `7c` is the WHITE row, still blocked on a capture rather than on a session,
  plus three items recorded in `7c` with acceptance criteria that are
  defence-in-depth rather than capability: a registration search for two
  misregistered frames, a re-check of split pieces against the width gate, and
  tightening `_is_separator` to the comma population it documents. **A
  four-digit committed fixture is BLOCKED on an operator decision**, not on
  work - capture-derived pixels enter this public repo only on explicit
  approval (`LL-0083` precedent). The other client-closed work is
  now reading more first-party data off the game's own menus into
  [`docs/AFFIXES.md`](docs/AFFIXES.md), which needs the operator in a menu
  but not in combat - and item 10 still supersedes everything the moment the
  client is open.

**Item 9 is CLOSED as of 2026-08-12** (ledger `LL-0046`). The `cdkey` hole is
shut, the `/Game/` anchor is genuinely pinned, and two of that item's four
surfaces turned out to have been closed already.

**Item 4's remaining acceptance is met by shipped code**, measured 2026-08-25:
`lanternlight/savewatch.py` pointed at `Saved/` snapshots `AvgPrice_<id>.ini` on
change with a timestamp and never writes to it, which is exactly what that item
asked for. Item **4c** is the part that is genuinely left - arming it without a
session having to remember. There is no longer an open safety item; the safety
lane's queue in `lanes/safety.STATE.json` is all blocked on a candidate fixture
existing.

Item 3 is closed, so it is no longer the fallback. The tailer exists; what does
not exist yet is anything consuming it, and nothing on this list currently asks
for that - do not invent a consumer without an acceptance criterion.

Item 7 itself stays **open**, but its blocker has been cleared once: no
coefficient may be published until the same value is seen in an **independent
run**, and **10.35 has now cleared that bar** - three runs at the damage floor,
whose only disagreement is a rounding tie that 10.35 itself predicts. It is a
floor value with its conditions attached, not a coefficient, and nothing has
entered Emberforge.

One ownership correction, measured this session: `tests/fixtures/**` is owned by
**ingest**, not safety. This document called 2b "safety-lane work" and the
roster in `ops/lanes.py` disagreed. What actually worked was a split - ingest
built the artifact, safety owned the detectors and held the veto. Read the
roster, not this file, for who owns a path.

Item 4 is closed. `4c`'s entry point is closed; arming it AUTOMATICALLY is now
item `4d`, which is OPEN and needs no client. Item 3 is closed.

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
