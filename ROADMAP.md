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

**Not built yet, and this is the whole remaining item:**

1. **Per-lane on-disk state.** Agent context does not survive a session, so
   "persistent specialist" has to mean a charter plus a work log plus open items
   on disk, or every lane silently resets to zero each time it starts. This is
   the piece that makes the lanes actually persistent rather than merely
   well-described.
2. **A commit-serialisation answer.** Eight lanes and one `docs/LEDGER.md` will
   race. `ops/loop/ledger.py` is atomic per write, which prevents a torn read
   but does nothing about two lanes appending in separate worktrees and
   conflicting at merge. Options worth weighing: a per-lane ledger fragment
   merged on integration, or a lock modelled on `ops/loop/guard.py`.
3. **Nobody has actually run a lane yet.** Everything above is tested, and
   none of it has been exercised by a real slice of work.

**Acceptance:** a lane launched into its own worktree, doing a slice of real
work, passing its own merge gate, committing to its branch and pushing, with the
primary checkout untouched throughout - demonstrated end to end for one lane,
not described.

## 2. GVAS `.sav` reader - CLOSED 2026-08-09

Ledger `LL-0011`. `lanternlight/gvas.py` parses all five `.sav` files. Published
GVAS parsers do not work on this build: UE 5.4+ replaced `FPropertyTag`'s
`FName Type; int32 Size; int32 ArrayIndex` with a recursive type name plus a
flags byte. All 627 trailing bytes of `EnhancedInputUserSettings.sav` decode,
and the result cross-corroborates the log - save and log independently agree
that `KB_Blackarrow_Major_Action` is bound to `RightMouseButton`.

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
