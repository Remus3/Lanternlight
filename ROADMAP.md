# Lanternlight roadmap

What is actually next, in priority order. Every item carries an acceptance
criterion, because "worked on it" is not a state this project recognises.

Aspirational ideas that nobody has committed to live in [`BACKLOG.md`](BACKLOG.md).
Nothing is moved from there to here without an acceptance criterion attached.

Status vocabulary: **NEXT** (the current item), **READY** (specified, unblocked),
**BLOCKED** (waiting on something named), **OPEN** (a question, not a task).

---

## 0. Redactor persona leak - P0, IN FLIGHT

Found 2026-08-09 while preparing the item 1 fixture. Running the current
redactor over the real log leaves **684 of 686 occurrences of the operator's
Steam persona in place**, and `assert_clean()` returns cleanly on a line that
still contains it - so the guard is vacuous for this shape. Two root causes:
keyed rules stop their value match at whitespace so a two-token display name is
half-masked, and the persona also appears with no key at all, as a positional
comma-separated field and after verbs such as `PlayerOpenTreasureBox`.

This **blocks item 1's acceptance outright**, because that criterion requires
committing a redacted log excerpt and the excerpt carries the persona.

**Acceptance:** zero surviving persona occurrences when the new redactor is run
over the full live log, measured and reported as a count; `assert_clean` fails
on a persona-carrying line, proven by breaking the check and watching a test go
red; `tests/test_no_pii.py` still passes; no existing test weakened.

Related, not yet done: `CampData_<userId>.sav` embeds the operator's numeric
userId **in its filename**, so any `.sav` fixture must have its name rewritten,
not just its contents.

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

## 2. GVAS `.sav` reader - READY

Four `.sav` files under `%LOCALAPPDATA%\MistfallHunter\Saved\SaveGames\`, 2-2.7
KB each, plain UE GVAS with magic `47 56 41 53` and no encryption. Measured, not
hoped for. `LoginOptions.sav` yields `SelectedServer` and `AccountName`;
`UserSettings_v1.sav` yields the settings block including `bWarehouseAutomation`.

Write the reader in-repo rather than taking a dependency - GVAS is a small
format and a vendored parser would need a license review for no real gain.

**Acceptance:** `lanternlight` parses all four files into plain dicts; a test
runs against a **redacted** committed fixture (`AccountName` is PII, so this
file cannot be committed raw); an unknown property type raises rather than
silently returning a partial parse.

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

Items 2, 3 and 4 are independent of each other and could run in any order or in
parallel. Item 1 is first because it is the only one that can invalidate the
design of the others. Items 5 and 6 are cheap, and both are best folded into
whichever session next has the game open rather than scheduled on their own.

## Deliberately not on this list

- Anything touching the game process. Permanently out of scope
  ([ADR-001](docs/adr/ADR-001-no-game-process-interaction.md)).
- Anything requiring decrypted paks
  ([ADR-002](docs/adr/ADR-002-no-asset-extraction.md)).
- Emberforge formula work. The engine cannot be filled before there are measured
  numbers to fill it with, and as of 2026-08-09 **no cooldown values, damage
  coefficients or stealth durations are published anywhere**
  (`docs/CLASS_RESEARCH.md`). Item 1 is the unblocker.
