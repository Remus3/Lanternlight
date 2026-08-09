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

**What is still unmeasured, and why this item is not closed:** everything above
is the **Prologue**, which runs at `matchId=0`. No matchmade raid, and only one
escape type (`GroveSprite`) has ever been seen.

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

## 1b. Specialist lane build-out - NEXT, machinery landed and proven

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

## 2. GVAS `.sav` reader - REOPENED, a new property type appeared

Ledger `LL-0011`. `lanternlight/gvas.py` parses every `.sav` file. There were five when the reader was written and there are now **six** - `Deck.sav` appeared mid-session and parses cleanly, but no fixture pins it. Published
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

**Captured 2026-08-09, and three filed claims about it are now corrected.** A
snapshotter armed at 17:27 local took 170 generations of it. Measured:

- **It is not 46 KB.** It appeared at 2,190 bytes and reached **126,078** bytes
  in twelve minutes - about 44 times the next largest save, not twenty. The
  earlier "46 KB" was a reading of a file mid-write, not its size.
- **It is not append-only.** At 17:40:02 it measured 125,765 bytes, *smaller*
  than the 126,078-byte peak twelve minutes in. It is rewritten in place with a
  varying size, so a reader must not assume a prefix stays put between polls.
- **The "deletes itself after about 13 minutes" timer did not fire.** It was
  still present 13 minutes after appearing. Whatever removes it is not a simple
  elapsed-time rule from creation; the previous session's disappearance is more
  likely tied to leaving the mode. This is a correction to a claim carried in
  the session hand-off, and it is why the item stayed open.

None of that was reachable by re-reading a document. It came from arming a
watcher before the file existed, which is the whole lesson of this item.

**Acceptance:** `StructProperty` decoded far enough to parse this save with
`undecoded_trailing == 0`, a sanitised fixture pinning it, and every newly
observed property type recorded. If a nested struct cannot be decoded, it is
handed back verbatim and named as undecoded - never guessed.

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

---

## Ordering note

Item 1b is next because it is the only item that makes every other item cheaper:
lanes are how work gets parallelised here, and two of them have now been run end
to end. Items 3 and 4's watcher are independent of everything and of each other.

Item 1's remainder, and items 5 and 6, all need the client open. None of them
needs a *deliberate* capture session any more - the 2026-08-09 pass showed the
log alone was sufficient - so fold them into whichever session next has the game
running rather than scheduling them.

## Deliberately not on this list

- Anything touching the game process. Permanently out of scope
  ([ADR-001](docs/adr/ADR-001-no-game-process-interaction.md)).
- Anything requiring decrypted paks
  ([ADR-002](docs/adr/ADR-002-no-asset-extraction.md)).
- Emberforge formula work. The engine cannot be filled before there are measured
  numbers to fill it with, and as of 2026-08-09 **no cooldown values, damage
  coefficients or stealth durations are published anywhere**
  (`docs/CLASS_RESEARCH.md`). Item 1 is the unblocker.
