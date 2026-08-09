# Lanternlight roadmap

What is actually next, in priority order. Every item carries an acceptance
criterion, because "worked on it" is not a state this project recognises.

Aspirational ideas that nobody has committed to live in [`BACKLOG.md`](BACKLOG.md).
Nothing is moved from there to here without an acceptance criterion attached.

Status vocabulary: **NEXT** (the current item), **READY** (specified, unblocked),
**BLOCKED** (waiting on something named), **OPEN** (a question, not a task).

---

## 1. Raid recon pass - NEXT

The single biggest unknown in the project. The 2026-08-09 probe reached camp and
character creation only, so loot names, extraction events, match results, death
and downed states, party composition and any in-raid economy line are
**unmeasured, not absent** (`docs/FINDINGS.md` section 4). Everything downstream
of this - the save reader's schema guesses, the market watcher's assumptions,
Emberforge's first question - is being designed in the dark until it is run.

Do it as a deliberate capture session, not opportunistically: start the frame
poller, note the wall-clock at raid entry, play one full raid to a successful
extraction, then play one to a death. Two runs, two outcomes, because the log
almost certainly distinguishes them and we need both sides to know which field
carries it.

**Acceptance:** a redacted log excerpt covering entry, at least one loot or
inventory event, and both a successful extraction and a death, committed as a
test fixture; plus new rows in `docs/OBSERVED_IDS.md` for every id observed,
each with its method named. If a category yields nothing, that null result is
written down explicitly rather than left silent.

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

## 4. `AvgPrice` market watcher - READY, but low-yield until it fills

`AvgPrice_937566.ini` is a market and trade-price cache the game maintains
itself. At the time of measurement it was **37 bytes and empty** - the operator
had not traded. The file existing at all is the finding; its contents are not
yet a data source.

This is cheap to build and cheap to leave running, so build the watcher now and
let it capture the moment the file first fills. That first non-empty write tells
us the schema, and it is a moment that only happens once.

**Acceptance:** a watcher that snapshots the file on change with a timestamp and
never writes to it; a parser that is written **after** a non-empty sample
exists, not before. If the file is still empty, the acceptance for this item is
the snapshot history, not a parser.

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
