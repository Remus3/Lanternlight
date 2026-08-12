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

**Namespacing was NOT implemented, deliberately** - recorded as `OPS-6`. The
safety lane's accidental `SAF-NNNN` is collision-free by construction and is a
real long-term answer, but retiring the global space changes what 30 existing
entries, and every roadmap item, branch and commit citing an `LL` id, refer to.
That is an operator decision, and detection makes it a considered one rather
than an urgent one.

## 2d. The suite is only green IN PLACE - OPEN, ops lane, confirmed twice

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

**Acceptance:** the contract renders a path relative to the checkout, or the
test compares modulo the root; a fresh `git clone` plus `python -m pytest`
goes green, demonstrated end to end rather than argued; and the guard is shown
to go red when the relativisation is removed.

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

## 3. Live log tail - READY

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

**EXTRACTED 2026-08-11.** All **263** generations parsed, **278** window
readings deduplicated by `(monsterGuid, timeStamp, damageValue)` down to
**21 distinct hits** over a **1020.3-second** span. Damage ranged 9.745483 to
137.517426 against **8 distinct monsterIds** (1005, 1006, 1014, 1029, 2003,
2007, 2017, 2021) across 9 monster instances.

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

- `nameId` is **0 on all 424 readings** in every one of the 263 generations,
  and `Key` is empty on all 424. So the save's window carries no attribution
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

**Remaining acceptance:** the extractor is currently merger analysis in a
scratchpad, not shipped code. It needs a home in a lane, tests, and the
timestamps joined to log wall-clock. Plus: no damage coefficient may be
published until the same value is seen from an **independent run** - one run
cannot separate a coefficient from a lucky repeat, however precise.

**A sampling limit to design against:** 278 window readings over ~20 minutes of
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

---

## Ordering note

**Item 2b is CLOSED 2026-08-11.** The next item is **7** - extract the damage
series into shipped code - because it is the only thing on this list that
unblocks Emberforge, and because the numbers are already on disk. **Item 7b** is
the cheapest thing here and answers item 7's one blocking question, so fold it
into whichever session next has the client open. **Item 2c** is a defect in the
continuity machinery and should be fixed before the next multi-lane session,
not after it silently eats another entry.

One ownership correction, measured this session: `tests/fixtures/**` is owned by
**ingest**, not safety. This document called 2b "safety-lane work" and the
roster in `ops/lanes.py` disagreed. What actually worked was a split - ingest
built the artifact, safety owned the detectors and held the veto. Read the
roster, not this file, for who owns a path.

Items 3 and 4's watcher remain independent of everything and of each other.

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
