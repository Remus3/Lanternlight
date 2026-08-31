# Observed engine ids

First-party observations read out of `%LOCALAPPDATA%\MistfallHunter\Saved\Logs\
MistfallHunter.log`. Nothing here is from a wiki. Each row says how it was
established, because the log emits NUMBERS and never a class name string - every
id-to-name binding therefore rests on an operator observation made at the same
moment, not on the log alone.

Game build: Steam buildid `24813185`, observed 2026-08-25.

**The game was patched between observations.** Every id below was read on
buildid `24619162` (2026-08-09) unless its row says otherwise, and the patch
landed 2026-08-19T08:06:36Z. None of them has been re-confirmed on the current
build. Treat an id whose row predates 2026-08-19 as a measurement on a build
that no longer exists - it is probably still true, and nothing here has
checked.

## Class ids

Log line, **transcribed exactly** - note the DOUBLE space before `==`:

    TS.Dungeon: [basedatacomponent] setClassGender inclassid  ==NN, inGender ==N

**This line was quoted wrongly here until 2026-08-30**, with a single space. The
wrong form matches **0** lines in every log on this machine and the corrected
form matches 156 in the 2026-08-30 log alone. The `grep for setClassGender
inclassid` instruction further down was never affected - it stops before the
double space - so one of the two patterns in this section worked and the other
silently returned nothing.

Recorded rather than quietly fixed because a quoted log line is load-bearing: it
is what the next session pastes into a grep, and a transcription that is one
space wrong fails closed and looks exactly like "the game stopped emitting it".

| classId | Class | How established |
|---|---|---|
| 10 | **Mercenary** | pixel-joined, 2026-08-09 |
| 11 | **Sorcerer** | pixel-joined, 2026-08-09 |
| 12 | **Blackarrow** | pixel-joined AND operator-attested - the committed character logged `classId 12` |
| 13 | **Shadowstrix** | pixel-joined, 2026-08-09 |
| 14 | **Seer** | pixel-joined, 2026-08-09 |
| 15 | **Withered Knight** | by elimination plus sidebar order; the ROLE panel for it was not captured |

**Complete. 10-15, ascending, matching the in-game sidebar order top to bottom.**

### Method - how "pixel-joined" was established

The log emits `setClassGender inclassid ==NN` with a UTC timestamp. A passive
desktop poller captured the screen every 3s with local-time filenames. Local is
UTC-5, so the two streams join on wall clock. Reading the class NAME off the
ROLE panel in the frame that closes each dwell window gives name-to-id directly.
No process access, no OCR guesswork - the name is rendered text read from a
screenshot.

One wrinkle worth recording: **the ROLE description panel lags the selection by
about one frame, while the left sidebar highlight leads it.** So in the frame at
the instant class 13 is set, the panel still reads "Blackarrow" (class 12) and
the sidebar has already moved to Shadowstrix. Both halves agree with the log,
which is what makes the join trustworthy rather than a coincidence. Read the
panel for the OUTGOING class and the sidebar for the INCOMING one.

Reproduce with [`tools/frame_poller.py`](../tools/frame_poller.py) plus the log
grep for `setClassGender inclassid`.

## Gender ids

| genderId | Meaning | How established |
|---|---|---|
| 1 | Body type 1 | inferred from pairing with 2 |
| 2 | **Body type 2 (Female)** | **operator-attested** - operator selected body type 2, character logged `gender 2` |

## Weapon config ids seen in character creation

Log line: `TS.Avatar: [AvatarComponent] server_refreshKnightFeature: <actor> class-NN holding-NNNNN`

Two preview actors exist and the log labels them by gender
(`BP_Preview_C_...781` = gender-1, `BP_Preview_C_...772` = gender-2).

| classId | Class | holding ids seen | count |
|---|---|---|---|
| 10 | Mercenary | 30401, 30402 | 2 |
| 11 | Sorcerer | 30503 | 1 |
| 12 | Blackarrow | 30504 | 1 |
| 13 | Shadowstrix | 30505, 30506 | 2 |
| 14 | Seer | 30507, 30508 | 2 |
| 15 | Withered Knight | 30409, 30410 | 2 |

Four classes carry two weapon ids, two carry one. The pair count lines up with
the published weapon kits - Mercenary is Hammer plus Sword and Shield,
Shadowstrix is Dagger plus Dual Blades - so **pairs are the two weapon stances,
not gender mesh variants.** The gender-variant hypothesis is refuted: gender
variants would apply uniformly across all six classes, and they do not.

Blackarrow showing a single id **independently corroborates the official
statement that its second weapon ships in a future season.** That corroboration
is worth more than the statement alone, because it was measured here rather than
read from a patch note.

**Still open:** Sorcerer also shows a single id, which the official line does not
account for. Either Sorcerer is genuinely single-weapon too, or its second
weapon was not surfaced during this walk. Do not write "Blackarrow is the only
single-weapon class" anywhere until this is settled.

Note the id space is NOT class-ordered: Withered Knight sits at 304xx alongside
Mercenary, while the middle four sit at 305xx. Do not infer class from an id
range.

### The archived logs hold NO creation walk - a measured negative for ROADMAP 5

Probed 2026-08-30 to see whether `ROADMAP` item 5 (the Sorcerer single-weapon
question) could be closed from bytes already on disk. **It cannot**, and the
negative is recorded here so nobody runs this probe twice.

Across every archived log, measured on the **three distinct sessions** (see the
corpus trap below):

| Probe | Result |
|---|---|
| `class-11` (Sorcerer) occurrences | **0** |
| 5-digit `holding-` ids, the creation-preview space | **0** |
| `BP_Preview_C_` creation-preview actors | **0** |
| `holding-` events in total | 757 |

The 5-digit creation-preview ids in the table above were captured on 2026-08-09,
and **the game truncates its log on launch** (item 4c), so that log is gone. No
surviving log contains a character-creation walk at all.

**The SAVE route is exhausted too**, so both surfaces are closed. Decoding every
persistent save type with `lanternlight/gvas.py` shows none of them carries a
class id at all:

| Save | Top-level keys |
|---|---|
| `CampData_<roleId>` | `LevelModeMap` |
| `Deck` | `DeckDefaultOpenPage` |
| `EnhancedInputUserSettings` | `CurrentProfileIdentifierString` |
| `LoginOptions` | `AccountName`, `SDKType`, `SelectedServer` |
| `Notice` | `readedActivityBulletinId`, `readedGameBulletinId` |
| `Scav` | `bIsMaskReward` |
| `UserSettings_v1` | 16 graphics and audio settings |

Character creation is previewed, not persisted, so nothing about a class the
operator did not commit to reaches a save. Item 5 needs the deliberate re-walk
its acceptance criterion already describes; there is no shortcut through the
archive.

**Already known, restated only so the next reader does not re-derive it:**
`LoginOptions` carries `AccountName` and is a PII surface. It is covered by
`ADR-004`, by `docs/FINDINGS.md`, and by the redactor's `ACCOUNT_NAME` rule,
which keys on four spellings of that field. No `.sav` is tracked in this
repository.

### `server_refreshKnightFeature` is emitted by NINE actor types, not two

This section previously named two - `BP_Preview_C_` for creation and
`BP_Adventurer_C_` for the live character. Seven more emit the same line, and
knowing which actor produced a row is what makes the row interpretable.

| Actor | classes seen | count | Reading |
|---|---|---|---|
| `BP_UIPreview_C_` | 12 | 195 | operator's own character, generic UI preview |
| `BP_Adventure_Bot_C_` | 10, 12, 14, 15 | 196 | **bots** - the log names them as such |
| `BP_RecomPreview_C_` | 12 | 125 | operator's own, recommendation surface |
| `BP_CampAdventurer_C_` | 12 | 53 | operator's own, in camp |
| `BP_PremiumShopPreview_C_` | 12 | 53 | operator's own, shop preview |
| `BP_AppearancePreview_C_` | 12 | 51 | operator's own, appearance surface |
| `BP_Adventurer_C_` | 12, 13, 15 | 51 | live adventurers in a run |
| `BP_EquipPackPreview_C_` | 12 | 31 | operator's own, equip-pack preview |
| `BP_RankPreview_C_` | 12 | 2 | operator's own, rank surface |

**The actor type partitions the population, and that is the useful part.**
**MEASURED:** all seven newly recorded types carry **class-12 only**, and only
`BP_Adventure_Bot_C_` and `BP_Adventurer_C_` ever carry another class.
**INFERRED, and it is only an inference:** that those seven are therefore UI
renderings of the operator's own character. The type names support it, but
class-12 is Blackarrow and *another* Blackarrow player is also class-12, so the
class alone cannot separate "the operator" from "some Blackarrow". What is safe
to rely on is the measured half - do not count these rows as sightings of
another CLASS.

`BP_CampAdventurer_C_` is new to `docs/`, but not to this repository: it is
already referenced in `tests/test_logparse.py`. The novelty claim here is scoped
to the documentation, and the codebase knew about it first.

**A class seen ONLY on a bot is not evidence a player of that class was
present.** On `server_refreshKnightFeature` lines, class 10 appears 130 times
and class 14 appears 47 times, and every one of both is a bot. Widening to the
whole corpus, class 10 appears 358 times - the extra 228 are on
`refreshGelJarPart`, `refreshBellPart` and `refreshArmorParts`, and those are
bots too, so the reading survives the widening. **State which line family a
count covers**: the 130 is scoped to one line type and reads as a corpus total
if that scope is dropped. Any future count of "classes observed in play" has to
read the actor prefix or it will be wrong.

**`holding-0` is a real state, seen 77 times** - an empty or unset weapon slot.
It is a measured empty, distinguishable from an unmeasured one, and a parser
that treats `holding-` as always naming an item will mis-handle it.

### THE CORPUS TRAP - a `*.log` glob triple-counts

`C:/ll-captures/2026-08-30/logs/` looks like twelve logs. It is not.

- Two of its files are byte-identical **copies** of the two 2026-08-25 backups.
- The other ten are **incremental five-minute snapshots of ONE growing live
  log**, so each is a strict PREFIX of the next. Proven, not assumed: all ten
  are byte prefixes of the live log and of each other, with zero divergence.

**As of 2026-08-30 21:00 the machine held 18 MistfallHunter logs, 13 distinct
hashes, and THREE distinct sessions** - and that count is a MOVING TARGET, which
is the more durable half of this finding. The client was launched again at
`21:11` the same evening; the game truncated its log, rotated the old one to a
backup, and created a fourth session. **Date any corpus count and re-derive it
rather than citing this one.** The three are the 2026-08-25 backup at `01.27.09`, the
2026-08-25 backup at `04.45.02`, and the current live log; the first appears in
**four** places and the second in **three**. A naive glob-and-count inflated
`holding-` events from 757 to 2,438 - a factor of 3.22 - by counting the same
bytes repeatedly.

**This paragraph shipped its own wrong count and an adversarial pass caught
it.** It first said "fifteen `.log` files", because the walk that produced it
missed `C:/ll-captures/2026-08-25/logs/` entirely and both backups sitting in
`%LOCALAPPDATA%/MistfallHunter/Saved/Logs/`. A section arguing that filed counts
inflate, filing an inflated count, is the anti-pattern demonstrating itself.
**Count by walking, then deduplicate by content hash** - and walk every log
location, not the two you happen to remember.

**Any corpus statistic in this repo must name which logs it counted.** The three
distinct sessions are the 2026-08-25 backup, the 2026-08-25 live log, and the
current live log. Deduplicate by content hash before counting anything.


## Weapon-stance toggle probe - NOT YET RUN

Step 4 of the capture plan (hold on one class, cycle the stance toggle, watch
whether `holding-` changes) did not produce a distinguishable event in this
session. The pair-versus-singleton evidence above arrives from the carousel
instead, which is weaker for the stance question specifically. Re-run
deliberately when convenient.

## Post-creation

The committed character emits `BP_Adventurer_C_<id> class-12 holding-3010401`.
Note the id width: creation previews use 5-digit weapon ids (`30504`), the live
character uses a 7-digit id (`3010401`). These are different id spaces - most
likely a weapon config id versus an item instance or item config id. Do not join
them without evidence.

## Dungeon session ids - 2026-08-09, second pass

Everything below was established by **log inspection alone** over the 3h44m
session log (13:18:57Z to 17:03:01Z), with no screen capture required. Where a
binding needed a pixel join it is not claimed. Method is named per row.

### The live holding id space IS the item cfgId space

This **resolves the "do not join them without evidence" caution** in the
Post-creation section above. The evidence now exists.

Three ids appear both as a live `holding-` value on `server_refreshKnightFeature`
and as an item `cfgId` in the loot stream and in `AvgPrice_937566.ini`:

| id | Seen as `holding-` | Priced in AvgPrice | Reading |
|---|---|---|---|
| 3020401 | 23 times, `class-12` | yes, 31 | the equipped weapon, and it is tradeable |
| 901205 | 1 time, `class-12` | yes, 29 | held briefly - consistent with a consumable |
| 901207 | 1 time, `class-12` | yes, 33 | held briefly - consistent with a consumable |

Method: exact-value intersection of three independently produced id sets, then
each hit re-read on its original `TS.Avatar: [AvatarComponent]
server_refreshKnightFeature` line to confirm it was not a parser artefact.

**The caution still stands for the 5-digit ids.** Creation-preview ids (30401
through 30508) show **no** overlap with any item cfgId. So there are two spaces,
not one: a creation-preview weapon-config space, and a live item space shared by
equipment, consumables and market prices. `3010401` and `3010501` are live-space
ids that are **not** priced, so not every live id is tradeable.

### Item cfgIds observed in the loot and inventory stream

35 distinct on `TS.Inventory` lines, which write `cfgId:` with no space. Allowing
a space widens this to 45 by picking up the `TS.FTE` stream - see
`docs/FINDINGS.md` section 9.6 for the ten extra ids and why the narrow pattern
was misleading. All numeric; **no item names appear anywhere in the log**:

```
101      901101   901201   901205   901206   901207   901208   901301
903201   903202   903203   903205   903302   903303   903306   903307
903308   903401   903402   903405   903501   904202   904203   904204
904205   904206   904302   904303   904307   904403   999998   1110301
1310301  1720201  3020401
```

30 of these carry a price in `AvgPrice_937566.ini`. The 5 that do not are `101`,
`901101`, `999998`, `1110301`, `1310301`. **No id-to-item-name binding is
recorded, because none was observed** - a name would need a screen capture
joined on wall clock, exactly as the class ids were.

Scope matters and is easy to get wrong: only **31** of the 35 appear on an
actual `RequestPickupLoot` line (89 such lines). The others arrive through other
inventory operations. Of the 30 priced ids, **28 were picked up**; `1720201` and
`3020401` never were - `3020401` being the id the character was observed
*holding*, so an equipped weapon carries a market price without ever having been
looted.

### Loot source contexts

Log field: `context:` on `TS.Inventory: [DungeonInventoryComponent]` lines.

| context | on `RequestPickupLoot` only | on all `[DungeonInventoryComponent]` |
|---|---|---|
| `Bot` | 17 | 18 |
| `EnemyCorpse` | 15 | 17 |
| `TreasureBox` | 13 | 14 |
| `Pickup` | 1 | 1 |
| **total** | **46** | **50** |

Both columns are log-observed. The first version of this table printed the
right-hand numbers under the left-hand label; the four-line difference is
`RequestLootAndEquip`, a different operation. Same class of scope error as the
`cfgId:` one in `docs/FINDINGS.md` section 9.6 - the counts were real, the scope
sentence beside them was not.

### Gameplay state tags

Not numeric ids, but the same rule applies - recorded when observed.

| Tag | count |
|---|---|
| `Game.PlayState.Gaming` | 13 |
| `Game.PlayState.Spiritual` | 12 |
| `Game.Net.Online` | 6 |
| `Game.PlayState.WaitSpiritual` | 6 |
| `Game.PlayState.Escape` | 5 |
| `Game.PlayState.Death` | 1 |
| `Game.EscapeType.GroveSprite` | 1 |

`Spiritual` and `WaitSpiritual` are **unexplained**. They are not recorded as a
downed state, because nothing observed establishes that.

### Dungeon URL parameters

`TS.Utils: [LevelSwitch] openLevelDirect ... options=levelId=1&roomModeId=9&matchId=0`

| Parameter | Value seen | count |
|---|---|---|
| `levelId` | 1 | 14 |
| `roomModeId` | 9 | 14 |
| `matchId` | 0 | 14 |

Only the Prologue was entered, so all three are single-valued. `matchId=0` is
expected to distinguish the non-matchmade Prologue from a real raid - that is a
**prediction to test**, not an observation.

### classId 13 is now live, not just previewed

`"classId":12` appears 16 times and `"classId":13` twice in the `roleInfo` JSON
that `TS.Dungeon` emits on adventurer init. Method: log-observed. So a second
character exists on the account beyond the class-12 main.

Recorded because it was nearly misread: the id sits inside a long JSON payload,
and reading a truncated copy of that line makes `"classId":12` look like
`classId 1`. The value was re-extracted with an anchored pattern over the whole
file before being written here.

## Input action bindings - 2026-08-09, from the save AND the log

The first bindings established from **two independent first-party surfaces at
once**, which is stronger than either alone.

`EnhancedInputUserSettings.sav` persists a
`/Script/EnhancedInput.EnhancedPlayerMappableKeyProfile` object holding three
mapping rows. The game log independently emits `decode key mapping <action>
<key>` lines. They agree:

| Action id | Key | Method |
|---|---|---|
| `KB_Blackarrow_Major_Action` | `RightMouseButton` | save bytes AND log line |
| `KB_Blackarrow_Minor_Action` | `LeftMouseButton` | save bytes AND log line |
| `KB_EmptyHands_Minor_Action` | unbound (`None`) | save bytes AND log line |

**The save persists 3 rows; the log carries 81 pairs.** That asymmetry is the
finding: the save appears to store only **overrides**, not the full keymap. It
is a strong reading rather than a proven one - a deliberate rebind followed by
a re-read of the save would settle it, and nobody has done that.

Each mapping row also carries two further key slots (`None` in every observed
row) and 6 bytes that are **not decoded**. They are handed back verbatim rather
than named.

## Blackarrow talent tree - 2026-08-09, complete for a level-2 character

**Method: pixel capture joined to operator attestation.** `tools/frame_poller.py`
captured the TALENTS screen every 2s from 16:01:15 to 16:09:16 local while the
operator hovered each node in turn; the operator then named which frame showed
which node, and every name and description below was **read off the rendered
tooltip in that frame**. No wiki, no inference from the icon.

Frames are at `~/.lanternlight/frames/` and are **not** committed - a capture of
a running game shows the account panel.

**12 clusters over 2 pages.** Only **Battle Hardened** is unlocked at level 2;
every other cluster displays `Unlocks at Lv. N`.

**Nodes within a cluster are linked, and the links are prerequisites.**
At level 2 only **Measured Pace** and **Battle-fed** are selectable, and this
half IS frame-supported: those two render a grey `Activate` footer bar and the
other four render none.

**Mutual exclusivity is operator-attested and NOT visible in any frame.** The
ring shows a common entry marker feeding two disjoint chains - a branch
structure. A branch from a shared root is not the same fact as "one or the
other, forever"; with more points both branches might be reachable. Only one
talent point existed at capture time, so no frame can separate the readings.
The remaining four Battle Hardened nodes are visible and readable but not yet
takeable. The connecting lines drawn between nodes are that structure; an
earlier reading of this screen treated them as decoration and wrongly presented
all six as available choices.

| Cluster | Unlocks | Page |
|---|---|---|
| **Battle Hardened** | **already unlocked** | 1 |
| Archer's Arrow Enhancement 1 | Lv. 3 | 1 |
| Mighty Archer | Lv. 5 | 1 |
| Nimble Evade | Lv. 7 | 1 |
| Swift Shot | Lv. 8 | 1 |
| Archer's Arrow Enhancement 2 | Lv. 11 | 1 |
| Hunter's Arrow Enhancement 1 | Lv. 6 | 2 |
| Bomb Engineering | Lv. 9 | 2 |
| Predator's Stealth | Lv. 10 | 2 |
| Woodling Expert | Lv. 10 | 2 |
| Hunter's Arrow Enhancement 2 | Lv. 12 | 2 |
| Way of Gylden Hunt | Lv. 12 | 2 |

### Battle Hardened - the six nodes, with tooltip text

| Node | Effect, verbatim from the tooltip |
|---|---|
| Measured Pace | When carrying at least 2 Archer's Arrows, fully drawing and immediately firing Normal Arrows recovers Energy. |
| Battle-fed | When carrying at least 2 Hunter's Arrows, hitting an enemy with a shot reduces the remaining cooldown of all skills. |
| Lasting Pain | After hitting an enemy with a shot, increases the duration of all active debuffs on that enemy. |
| Marksman | Fully-drawn arrows will home in on enemies near the crosshairs. |
| Dodge Rapid Shot | Changes roll into dodge and unlocks Dodge Rapid Shot.<br>Dodge Rapid Shot: Shoot immediately after dodging, consuming additional Energy to quickly fire both the currently loaded arrow and a normal arrow toward enemies near the crosshairs. This skill has a cooldown. |
| Dodge Power Shot | Changes roll into dodge and unlocks Dodge Power Shot.<br>Dodge Power Shot: Shoot immediately after dodging, consuming additional Energy to quickly fire the currently loaded quick-charge arrow toward enemies near the crosshairs. Quick-charge arrows can activate all special effects of fully drawn arrows but have a lower Damage Multiplier. This skill has a cooldown. |

### The level-2 choice is inert, and that is the finding

Operator-attested at level 2: **the character has no arrows of either family,
only skills.** Both selectable nodes gate on *carrying* ammo - Measured Pace on
2 Archer's Arrows, Battle-fed on 2 Hunter's Arrows - so **neither talent does
anything at the moment it becomes available.**

Two things follow that are worth more than the choice itself:

- **Neither talent consumes the ammo it requires.** Measured Pace pays out on
  firing *Normal* Arrows while merely holding 2 Archer's; Battle-fed pays out on
  any hit while holding 2 Hunter's. The special arrows act as a key, not a cost.
  So the entire question is which family you own, not which you spend.
- **The tree front-loads the Archer family by three levels** - Archer's Arrow
  Enhancement 1 at Lv. 3 against Hunter's Arrow Enhancement 1 at Lv. 6. That is
  the game's own ordering, read off the screen, and it is the only measured
  signal available about which ammo a player is expected to hold first.

**Unmeasured:** how arrows are acquired at all - loot, craft or vendor. The
unlock ordering is a proxy for which family arrives first, not proof of it.

### Outcome - the first talent point was spent on Measured Pace

Operator-attested 2026-08-09. Recorded because the character's state is now a
fact a later session has to know, and because the reasoning shows how a decision
was made from measured data rather than from a guide.

The choice was forced by the loadout, not by a judgement about which effect is
stronger: **Battle-fed requires carrying Hunter's Arrows and the entire
Hunter's row is locked at level 2**, so it could not fire at all. Measured Pace's
condition - carrying at least 2 Archer's Arrows - was met by Steel Arrow and
Concussive Arrow.

Worth keeping as a process note: the first two recommendations this project made
on this question were both wrong, and both for the same reason. The first
suggested Dodge Rapid Shot, which is not selectable - the connecting lines
between nodes are prerequisites and had been read as decoration. The second
argued from the tree's unlock ordering while assuming no arrows were held. Only
the operator describing their actual loadout settled it. **A screenshot shows
what is on screen; it does not show what the player has.**

### Skills screen - 2026-08-09, level 2

Same method: passive capture, tooltip text read off the rendered frame.

**Loadout structure.** A single `Basic Skill` slot, then `Weapon Skill` split
into two columns:

| Column | Slots | Bound to |
|---|---|---|
| Arrow | 3 | `Z`, `X`, `C` - `C` locked until **Lv. 3** |
| Skills | 3 | one locked until **Lv. 5**, then `Q`, `E` |

**Arrow pools.** `Archer's Arrow` and `Hunter's Arrow` are shown as two separate
five-slot rows - which is the ammo-family split made visible as UI, not
inferred. At level 2: **2 of 5 Archer's Arrows owned, 3 locked; 0 of 5 Hunter's
Arrows, all locked.**

Owned: **Steel Arrow** and **Concussive Arrow**. Only the Concussive Arrow
tooltip was displayed in the 2026-08-09 capture, so **"Steel Arrow" was
operator-attested, not read off a frame** - flagged at the time because that name
also appears in an established-outlet list in `docs/CLASSES.md`, and a T3 name
presented as a frame reading is the restating-one-source trap this repo warns
about.

**FLAG CLEARED 2026-08-30.** `f1650_01.06.27` in the 2026-08-30 capture renders
the tooltip. Verbatim:

> **`Steel Arrow`** (`Bow`) - Fine steel arrows deal `Physical Damage` on hit
> and can `pierce` one unit.

A lore paragraph follows it, naming a smithy, a master smith and an apprentice;
it carries no mechanical content and is not reproduced here.

**`pierce` is a COUNTED mechanic shared across skills.** `Steel Arrow` pierces
**one** unit; `Sky Piercer`, quoted elsewhere in this repo, pierces **5**. Same
verb, same units, different magnitude - so pierce-count is a real engine
quantity Emberforge can carry, not tooltip prose.

**The same frame updates the loadout at Level 5**, against the Level 2 reading
above: all three arrow slots `Z`, `X`, `C` are now unlocked.

**The arrow rows render THREE visual states, not two, and a first draft of this
paragraph said "all 5 Hunter's Arrows are still locked" - which the frame
refutes.** Measured by counting pixels above a luminance sum of 420 in an 80 px
box on each slot:

| Row | s1 | s2 | s3 | s4 | s5 |
|---|---|---|---|---|---|
| Archer's | 184 | 117 | 192 | **0** | 355 |
| Hunter's | **0** | 338 | **0** | **0** | **0** |

A slot showing a padlock has **exactly zero** bright pixels. So **four** of the
five Hunter's slots are locked, not five, and `Hunter's` slot 2 renders a bright
icon with no padlock - the same state as `Archer's` slot 5.

**This project has no word for that third state and does not invent one.** It is
neither the gold-bordered equipped state nor the padlocked state. Whether it
means unlocked-but-unequipped, previewable, or something else is **unmeasured**.
The claim that "the Hunter's family remains entirely unavailable" is withdrawn.

**Worth keeping as method:** the wrong version came from reading the row by eye
off a rendered frame, and the correction came from counting pixels. For a
count of near-identical tiles, measure - do not look.

**Archer's Arrows are charge-based, not consumable stock.** Operator-attested:
they apply a special effect to the next nocked arrow, start at 3 uses, may be
spent successively, and regenerate one at a time on a cooldown. So "carrying at
least 2 Archer's Arrows" in the Measured Pace talent is a condition on the
loadout, not on an inventory count that can run dry.

**Open, and it matters later:** whether "at least 2 Archer's Arrows" counts
distinct arrow TYPES equipped or available CHARGES. At level 2 the operator has
both - 2 types, 3 charges - so this capture cannot separate the readings.

### Concussive Arrow - the game states the class weakness and its counter

Verbatim tooltip:

> Storm-imbued rune arrowheads burst into air waves on hit, dealing Physical
> Damage to enemies within range and inflicting stagger. If fired at full draw,
> they will knock back enemies caught in the air waves.

And the in-game hint beneath it:

> Maintain one shot's distance when using a bow. The arrow loses accuracy when
> it's too far, and drawing the bow may be difficult when too close. Use
> Concussive Arrows to knock back fast-approaching enemies.

**This is first-party corroboration of two findings that `docs/CLASSES.md` could
previously support only from player testimony:**

1. **Blackarrow is hard-countered by melee gap-closers.** The game ships a
   dedicated counter and names the problem in its own words - "fast-approaching
   enemies".
2. **It is not a sniper.** An explicit optimal-band statement - inaccurate when
   too far, hard to draw when too close - matching the reported effective heavy-
   shot range of roughly two dodge-lengths, which was absent from every guide
   site consulted.

Note the corroboration direction: this is the developer's own UI agreeing with
first-party player testimony, against a wiki tier that carried neither claim.

**No magnitudes.** "Physical Damage", "stagger", "knock back", "within range" -
no damage figure, no duration, no radius. Consistent with every other tooltip
captured today. Note the precise claim: unquantified **effects**, not an absence
of all digits - see the Pursuit Mark counterexample above.

### Node names in the remaining clusters

Names and icons operator-attested per frame. **Essentially every one of the 36
tooltips was captured** - the starred entries below are simply the ones
transcribed here, not the only ones on disk. An earlier version said "tooltip
text captured only where noted", which understated the evidence and is how
Pursuit Mark's stack cap went unnoticed long enough to be denied in print.

| Cluster | Nodes |
|---|---|
| Swift Shot | Tactical Adjustments, Full Draw*, Colossal Power |
| Nimble Evade | Pursuer, Rapid Barrage, Pursuit Mark |
| Archer's Arrow Enhancement 1 | Sepsis, Astound, Lightning Spread |
| Archer's Arrow Enhancement 2 | Long Shot, Blood Infection* |
| Mighty Archer | Unstoppable Edge, Powerful Scattershot, Focus Fire |
| Hunter's Arrow Enhancement 1 | Power Infusion, Laceration, Shockwave |
| Hunter's Arrow Enhancement 2 | Neurotoxin, Lingering |
| Predator's Stealth | Steady Stealth, Heightened Senses |
| Bomb Engineering | Crippling Pain*, Cold Infusion |
| Woodling Expert | Woodling Bane, Swift Exit*, Regular |
| Way of Gylden Hunt | Death Sense, Greed is Good, Gyldenmist Tolerance, Monster Hunter |

`*` tooltip text also captured:

- **Pursuit Mark** - Enemies hit by normal arrows have reduced Movement Speed
  for a period of time. This effect can stack up to 3 times.
- **Full Draw** - Increases the Damage Multiplier of fully drawn arrows.
- **Blood Infection** - Upon hitting an enemy, Bloodfly Arrow deals reduced DoT
  but inflicts bonus Swarm stacks. Hitting an enemy that has Swarm stacks with
  any fully drawn arrow other than Bloodfly Arrow will detonate the Swarm,
  dealing bonus damage. The more Swarm stacks the target has, the higher the
  damage dealt. The swarm detonation deals Critical Damage, with a portion
  converted to True Damage.
- **Crippling Pain** - Enemies damaged by Impact Grenade have reduced Movement
  Speed for a period of time. Frame `f0081_16.04.16`.
- **Swift Exit** - Allows you to learn the spawn location of the Smuggler
  Woodling and Soul Ferry in advance. Frame `f0090_16.04.36`.

### Page-two node tooltips - ALL 16, 2026-08-09 capture, read 2026-08-30

**Read this before filing any item that says page two lacks tooltip text.** Two
of these - `Crippling Pain` and `Swift Exit` - have been in the starred list
directly above since 2026-08-09. A `ROADMAP` item nevertheless stated that
"page one has four such texts quoted and page two has none", and that item was
itself the correction to an earlier rediscovery failure about this same screen.
The claim was false when written. The remaining 14 texts below are new.

Every node was hovered in the `2026-08-09` capture at
`C:/Users/Administrator/.lanternlight/frames/`, which is a **2560x1440
full-scene set outside `C:/ll-captures/`** and is therefore invisible to a walk
of that tree. It holds 218 PNGs: 217 in the `f`-series, `f0000_16.01.15` to
`f0216_16.09.16`, plus one `skills_16.54.16` taken 45 minutes later. The character is **Level 2** and every page-two cluster is locked,
which settles a question the level-5 capture could not: **a locked node still
renders its full tooltip on hover.** `LAlt` pins it open (already recorded under
UI facts).

| Cluster | Node | Effect, verbatim from the tooltip | Frame |
|---|---|---|---|
| Hunter's Arrow Enhancement 1 | Power Infusion | Increases the effective range of Featherlight Arrows. | `f0064_16.03.38` |
| Hunter's Arrow Enhancement 1 | Laceration | Enemies hit by Barbed Arrow are Stunned for a period of time if they reach the maximum number of dodge uses before the Barbed Arrow effect ends. | `f0067_16.03.44` |
| Hunter's Arrow Enhancement 1 | Shockwave | After Sonic Arrow hits terrain, it emits sound waves multiple times over a period of time. This effect will not trigger if it hits players or monsters. | `f0069_16.03.49` |
| Hunter's Arrow Enhancement 2 | Neurotoxin | After Paralysis Arrow expires, it leaves an aftereffect that reduces the enemy's Skill Cooldown Speed for a period of time. | `f0071_16.03.53` |
| Hunter's Arrow Enhancement 2 | Lingering | Increases the poison duration and total Damage Multiplier of Spore Arrow, but reduces the Damage Multiplier per second. | `f0073_16.03.58` |
| Predator's Stealth | Steady Stealth | Attacks received during Shadow Step's Stealth no longer remove Stealth. | `f0076_16.04.04` |
| Predator's Stealth | Heightened Senses | Increases the number of uses for Predator's Senses and reduces its base cooldown. | `f0080_16.04.13` |
| Bomb Engineering | Crippling Pain | Enemies damaged by Impact Grenade have reduced Movement Speed for a period of time. | `f0081_16.04.16` |
| Bomb Engineering | Cold Infusion | Frostblight Bomb reduces the Movement Speed of enemies entering the blast area during the delayed explosion phase for a period of time. | `f0084_16.04.22` |
| Woodling Expert | Woodling Bane | Greatly increases damage dealt to Returner Woodlings. | `f0088_16.04.31` |
| Woodling Expert | Swift Exit | Allows you to learn the spawn location of the Smuggler Woodling and Soul Ferry in advance. | `f0090_16.04.36` |
| Woodling Expert | Regular | Woodling merchants will offer you a discount during matches. | `f0093_16.04.42` |
| Way of Gylden Hunt | Death Sense | Allows you to sense the corpses of other Gyldhunters. | `f0095_16.04.47` |
| Way of Gylden Hunt | Greed is Good | Increases Gyldenblod gained. | `f0099_16.04.56` |
| Way of Gylden Hunt | Gyldenmist Tolerance | Increases resistance to the Gyldenmist, slowing the rate of Gyldening. | `f0101_16.05.00` |
| Way of Gylden Hunt | Monster Hunter | Increases damage dealt to monsters but reduces damage dealt to Gyldhunters. | `f0105_16.05.09` |

**The census is complete and the completeness is checked, not assumed.** The
node-name table above lists 3+2+2+2+3+4 = 16 nodes across the six page-two
clusters, and frame `f0160_22.29.45` from the separate level-5 capture renders
exactly 16 node icons on page two, counted per cluster in the same 3/2/2/2/3/4
shape. Two independent surfaces, same count.

**`Gyldening` and `Woodling merchants` and `Spore Arrow` are new game nouns.**
Every other noun in the table was already recorded elsewhere in `docs/`. The
game's own spelling is `Gyldhunters`, not `Gyldenhunters`, agreeing with
`docs/AFFIXES.md`.

**No magnitude appears anywhere in these 16 texts.** Not one duration, radius,
percentage or stack cap - only "a period of time", "greatly", "reduces". That
extends the pattern every other talent tooltip in this file already shows, and
it is the reason Emberforge cannot derive talent effects from tooltip text.


### What this corroborates, and what it opens

**Corroborates:** the class research finding that **Archer and Hunter are ammo
families**, not weapon stances. Measured Pace gates on Archer's Arrows and
Battle-fed on Hunter's Arrows, and both cluster names use the same split. That
was previously a claim adjudicated from published sources; it is now visible in
the game's own UI.

**Opens:** the tooltips say both Dodge nodes change `roll` into `dodge` and
never say how the two differ. Whether dodge is shorter, faster, or has different
invulnerability is **unmeasured**, and it matters - the class's effective
heavy-shot range was reported at roughly two dodge-lengths, so the dodge is the
unit its spacing is counted in.

**Numbers are rare but they DO appear - an earlier version of this section
claimed otherwise and was wrong three ways.** It read: "No numbers appear
anywhere in these tooltips." Counterexamples, all from captured frames:

- **Pursuit Mark** - "This effect can stack up to 3 times." A stack cap.
- **Measured Pace** - "When carrying **at least 2** Archer's Arrows..."
- **Battle-fed** - "When carrying **at least 2** Hunter's Arrows..."

The last two are quoted verbatim in the table above this one, so the document
denied the existence of numbers it had itself transcribed 155 lines earlier.

**The surviving, narrower and still useful claim:** no tooltip gives a
**magnitude of an effect** - no damage figure, no percentage, no duration in
seconds, no radius. "Recovers Energy", "reduces the remaining cooldown",
"reduced Movement Speed for a period of time", "lower Damage Multiplier" are all
unquantified. The numbers that do appear are **thresholds and caps** - how many
arrows you must carry, how many times a debuff stacks - never the size of what
happens.

That narrower claim still supports the project's founding measurement: the
quantities Emberforge needs are not published, and a source quoting one is
fabricating it. It just is not the sweeping negative first written, and a
sweeping negative is exactly the shape that turns out to have a counterexample.

### UI facts observed in passing

Top-level hotkeys: `Warehouse` Tab, `Prepare` E, `Skills` K, `Talents` P, `Camp`
U, `Task` H, `Mall` Z. `LAlt` pins a tooltip open ("Lock and view"). Page turn
is `A` and `D`.

**The account panel shows a RANDOMISED display name**, not the Steam persona.
Operator-attested: this is a **privacy setting in the game's own menu**, which
the operator had enabled. An earlier version of this section called it "a
separate in-game identifier" that the redactor must learn - that was wrong and
is retracted. It is a game-supplied pseudonym, so a capture of this screen is
safer than assumed rather than more dangerous.

Worth keeping for a different reason: the setting exists, so **a capture's
safety depends on a game option that can be toggled off**. A screenshot is only
as redacted as the operator's current privacy setting, and nothing in this
repository can detect which way it is set.

## Ids from the transient dungeon save - 2026-08-09 capture, read 2026-08-11

**Method for every row below: direct decode of `StandaloneSlot_<roleId>.sav`
with `lanternlight/gvas.py` in strict mode.** The bytes are the 263-generation
capture at `C:\ll-captures\saves\`, held outside this repository and not
committed. Unless a row says otherwise the value is from the largest
generation. No wiki was consulted for any of it, and no name below was imported
from one.

This is the first id set this project has taken from a **save** rather than
from the log or the screen, so the surface itself is worth naming: these ids
were watched being **written to disk by the game**, which is a different and
slightly stronger observation than reading them out of a log line.

The full structural analysis is `docs/FINDINGS.md` section 10.

### Monster config ids - `MonsterData.<key>.MonsterID`

19 distinct ids over 61 monster records. The number after each id is how many
records carried it in that single generation, so it is a population count for
one dungeon run and not a property of the id.

| MonsterID | Records | MonsterID | Records |
|---|---|---|---|
| 1003 | 1 | 1400 | 6 |
| 1004 | 7 | 1410 | 4 |
| 1005 | 13 | 2001 | 1 |
| 1006 | 2 | 2002 | 1 |
| 1007 | 6 | 2003 | 4 |
| 1010 | 2 | 2007 | 1 |
| 1013 | 1 | 2012 | 1 |
| 1014 | 5 | 2017 | 3 |
| 1029 | 1 | 2021 | 1 |
| | | 3003 | 1 |

**No monster id is bound to a name.** Nothing in the save carries a monster
name string, and none was observed on screen at a time that could be joined to
these bytes. Binding them needs the same wall-clock pixel join that bound the
class ids. Recorded now, unbound, because the ids exist and that is a fact worth
keeping.

The same id space is used by the kill-count maps below, which is a
within-file cross-check rather than a separate observation.

### Zone names - `LeaderRankScoreData`

Three zone-name strings appear as map keys, emitted by the game into its own
save:

| Zone key | Appears under |
|---|---|
| `WhiteWoodsOutskirts` | `TeamKillMonsterData`, `TeamOpenTreasuresData` |
| `GiantHighland` | `TeamKillMonsterData`, `TeamOpenTreasuresData` |
| `Default` | `TeamKillMonsterData` only |

`WhiteWoodsOutskirts` is consistent with the log's `WhiteWoods_Level_Easy2`
sublevel and with the operator's player-facing name **Hallowgrove**, already
recorded as an open item in `lanes/research.STATE.json`. **Consistent is not
bound** - nothing observed here proves these name the same place, and no
binding is claimed. `GiantHighland` and `Default` have no player-facing name
attached to them by anything measured.

`TeamKillMonsterData` nests one level deeper than the zone: the outer key is a
**category**, and the only value seen is `Normal`. Whether that is a difficulty,
a monster class or something else is unmeasured.

### Monster kill counts by zone - `TeamKillMonsterData.Normal.<zone>.Id2cnt`

Monster id to kill count, one solo run:

| Zone | Id2cnt |
|---|---|
| `WhiteWoodsOutskirts` | 1004:3, 1005:6, 1006:1, 1007:2, 1014:2, 1400:2, 2003:2, 2007:1, 2021:1 |
| `GiantHighland` | 2017:1 |
| `Default` | 1029:1 |

Total 22, which equals the file's own `KillMonsterNum` of 22 and the 22
`MonsterData` records flagged `Dead`. Three independent counts in one file
agreeing is a consistency check, not three observations.

### Container config ids - `TeamOpenTreasuresData.<zone>.Id2cnt`

Container id to open count. **A different id space from the monster ids** -
`1204` and `1211` appear in both zones here, and neither is a `MonsterID`:

| Zone | Id2cnt |
|---|---|
| `WhiteWoodsOutskirts` | 1002:1, 1203:1, 1204:1, 1205:1, 1206:2, 1211:2 |
| `GiantHighland` | 1204:1, 1211:1, 1219:1 |

Note these keys arrive as JSON **strings** while the monster `Id2cnt` keys
arrive as ints. Same shape, two encodings, in one file.

**No container id is bound to a name.**

### Assist source ids - `AssistMonsterCount`

Five 8-digit ids, each mapping to an `Id2cnt` of monster id to count:

| Id | Monsters assisted |
|---|---|
| 30101001 | 1004:1, 1005:2, 1400:2, 2007:1 |
| 30101003 | 1004:2, 1005:2, 1014:1, 2003:1, 2021:1 |
| 30101004 | 1005:2, 1006:1, 1007:2, 1014:1, 2003:1 |
| 30108004 | 2017:1 |
| 30298031 | 1029:1 |

**These are unbound.** An 8-digit id in a field called `AssistMonsterCount`
could be a skill, an ability, a damage source or an equipment slot. The field
name is not evidence of what the id names - this document's own standing rule -
and nothing observed distinguishes the readings.

Related and also unbound: `SkillNameId 6130017` on the kill-history record
(below) is a **7**-digit id in a differently named field, so it is a different
id space from the 8-digit ones here unless something later joins them.

### Bot attribute id - `BotData.<key>.AttributeId`

One value observed: **`11120007`**. Unbound. It is 8 digits like the assist ids
and shares no observed value with them.

### Class id 15 confirmed live, from a save

`LeaderRankScoreData.KillPlayerHistoryDatas[0].ClassId` reads **15**, with
`Level` 2 and `BotGender` 1. That is the **Withered Knight** row of the class
table above - the one row established "by elimination plus sidebar order",
because its ROLE panel was never captured.

This does **not** promote that binding. It confirms the id **exists in live
play** and is emitted by a second surface, which is what was previously thin
about it; it says nothing about the name. The name still rests on elimination.

Recorded also because the record carries `IsPlayer: true` **and** `IsBot: true`
at once, and `KillPlayerCount` counts it - see `docs/FINDINGS.md` section 10.10.
Any id read out of this structure is a **bot's** id unless `IsBot` says
otherwise.

### Loot context is numeric in the save and a string in the log

The log emits `context:` as a word - `Bot`, `EnemyCorpse`, `TreasureBox`,
`Pickup`, recorded earlier in this document. The save emits `LootContext` as an
**integer** on the same kind of item record:

| `LootContext` | Observed on | Occurrences |
|---|---|---|
| 2 | items inside `TreasureBoxMap` entries | 19 |
| 5 | items inside `BotData.TreasurableItems` | 22 |

**The mapping to the log's words is a hypothesis, not a binding.** The
containers make `2 -> TreasureBox` and `5 -> Bot` the obvious readings, but no
observation puts a number and a word together, and this document does not
record obvious readings as bindings. Two values out of at least four is also not
a decoding.

`IvtrContext` is a separate numeric field on the same records: `0` on all 19
treasure-box items, and `0`:13, `1`:1, `2`:7, `5`:1 across the bot's 22. Values
observed, meanings unmeasured.

### `LevelDetail` keys

Five integer keys, each with a float value, in every generation that has the
map: **1, 2, 3, 100, 101**. Unbound - nothing observed says what a level-detail
key selects or what its float means.

### `MatchID`

**`11112`**, constant across all 263 generations. `docs/LEDGER.md` LL-0022
already records 11111 and 11112 as ids belonging to **solo explores**, observed
from the log. The save agreeing is a second surface for the same id, not a new
binding: what the number selects is still unmeasured.

### Item config ids seen in this save

All in the 7-digit live-item space already established above, which is itself
the finding - **the save and the log share one item id space**, checked by
value.

Dropped on the ground, `DropItemMap.<key>.ItemCell.cfgId`, 12 entries:

```
901210   903202   903205   904203 (x2)   905201
1110301  1210301  1320301  1510301  1620201  1720101
```

In treasure boxes, `TreasureBoxMap.<key>.TreasureData[].CfgId`, 19 items across
11 boxes:

```
901201   903201   903202   903205   903208   903301 (x2)  903306
903308   903411   904203 (x4)  904207 (x2)  904304
1310301  1620201
```

Carried by the single bot, `BotData.<key>.TreasurableItems[].CfgId`, 22 items:

```
101      901101 (x2)  901202  901210  903206  903302  903304  903306  903310
904205   1120101  1120301  1220101  1320101  1420101  1520101  1520301
1630102  1720101   3020401  3020901
```

Equipped by that bot, `BotData.<key>.Inventory.equipments[].cfgId`, 8 items:

```
1120101  1220101  1320101  1420101  1520101  1630102  1720101  3020901
```

**39 distinct ids** appear in this save. **16** were already recorded in this
document from the log; **23 are new to this project**:

```
901202   901210   903206   903208   903301   903304   903310   903411
904207   904304   905201   1120101  1120301  1220101  1320101  1320301
1420101  1520101  1520301  1620201  1630102  1720101  3020901
```

That list was derived twice. The first version wrongly included `903201`, which
was already recorded, and wrongly omitted `903301`, which was not - two errors
in opposite directions from reading a 35-id block by eye. The version above was
computed by set difference against the recorded block. **A hand-checked id list
is a hypothesis for the same reason a hand-checked count is.**

**None of the 39 is bound to a name.** No item name appears anywhere in this save,
exactly as none appears anywhere in the log.

One structural note worth more than the list: the bot's 8 equipped ids follow
the `1120101 / 1220101 / 1320101 / 1420101 / 1520101` pattern, which mirrors the
operator's own equipped `1110301 / 1210301 / 1310301 / 1410301 / 1510301` from
section 9.9.2 of `docs/FINDINGS.md` - same slot positions in the second digit
pair, different trailing group. That is **suggestive of an armour-set encoding
where the middle digits select the slot**, and it is written down as suggestive.
Two sets is not an encoding, and the last time this document inferred a scheme
from an id range it had to be retracted.

## Training ground - 2026-08-25, on buildid 24813185

The first ids in this file read on the CURRENT build. Method: operator entered
the training ground while the log was read directly and a 2 fps frame poller
ran; log timestamps are UTC, frame filenames local (UTC-5), joined on wall
clock. See `docs/FINDINGS.md` section 11.

| id or name | What it is | How established |
|---|---|---|
| `/Game/Project/Maps/TrainingGround/Training` | the training ground map | `LoadMap(...)`, 23:38:16 UTC |
| `DA_DungeonSettings_Training` | its settings data asset | `TS.Dungeon: [WeaponComponent]` line, same second |
| `13003` | `capabilityId` carried on that line | log, 23:38:17 UTC - meaning UNKNOWN, recorded because it was emitted |
| `WBP_Level_Room_Setting` | the room configuration panel | `TS.UI` window open, 23:38:24 UTC |
| `PracticeRoomSettingView_C` | its view class | `TS.UI` createWidget, same second |
| `BP_Adventure_Bot_C` | the spawned practice dummy | log instance names, plus rendered on frame |
| `WBP_HUD_Predicator_AssistAim` | aim predictor widget, one per shot | `TS.UI` open/createWidget, repeated |
| `GC_Damage_BeDamaged_C` | gameplay cue notify, damage taken | `LogAbilitySystem` async load |
| `GC_NumberPops_DamageCrits_C` | gameplay cue notify, crit number pop | `LogAbilitySystem` async load |
| `/Game/Project/Maps/CampMap/CampMap` | camp | `LoadMap(...)`, 23:37:03 UTC |
| `/Game/Project/Startup` | startup map | `LoadMap(...)`, 23:34:56 UTC |

**Two cue classes above are NOT hit counters.** `LogAbilitySystem` logs them
when the class is first async-loaded, once per session, not once per
occurrence. Counting those lines as crits would produce a wrong number.

**`AmmunitionComponent` id is always 0 so far.** `SpawnDefaultAmmunition spawn
id=0` appears once per arrow (63 times), and
`[AmmunitionComponent]: UsingCustomizedAmmunition: id=0` appears once. No other
value of that id has been observed, so nothing here binds an ammo family - it
is the first sight of the distinction ROADMAP 4b is about, and no more.

## Dungeon run - 2026-08-25b, on buildid 24813185

Read live off the log while the operator played, and the run is the one written
up in `docs/FINDINGS.md` section 12 - a complete dungeon that wrote **no**
transient save at all.

| id or name | What it is | How established |
|---|---|---|
| `DA_DungeonSettings_Classic` | a settings data asset name the log MENTIONS - **not bound to this run**, see the note below | log, 02:29:05 and 02:29:31 UTC |
| `113` | `levelId` on the map URL | `LoadMap(...)` and the connect URL |
| `11114` | `matchId` on the same URL | same lines |
| `BP_Dungeon_GameMode_C` | the game mode | `?game=` on the LoadMap URL |
| `/Game/Project/Maps/Map_2/Whitewoods_Day` | the map | `LogNet: Welcomed by server`, 02:56:19 UTC |
| `WhiteWoods_Enemy_Day_Solo01` | a **solo** enemy spawner sublevel | sublevel load line |
| `WhiteWoods_Enemy_Easy` | easy enemy spawner sublevel | sublevel load line |
| `WhiteWoods_Treasure_Easy` | easy treasure spawner sublevel | sublevel load line |
| `WhiteWoods_Easy_Traps` | easy trap sublevel | sublevel load line |
| `WhiteWoods_Easy_EscapePoint` | easy escape point sublevel | sublevel load line |
| `WhiteWoods_Easy_Gameplay` / `WhiteWoods_Easy_MapConfig` | easy gameplay and map config sublevels | sublevel load lines |
| `Whitewoods_TaskInteractable` | task interactable sublevel | sublevel load line |
| `onPartEscape` / `getPartEscape` | a third escape noun | `TS.UI` and `TS.Dungeon`, uninterpreted |

**`DA_DungeonSettings_Classic` is NOT this run's settings asset, and an earlier
draft of this file said it was.** Refuted by an independent pass and verified
directly: the string occurs **exactly twice** in the whole log, at 02:29:05 and
02:29:31 UTC - **27 minutes BEFORE** this run's `EnterBattle` at 02:56:01 - and
both occurrences are inside
`Puerts: Error: call TsConstruct of DA_DungeonSettings_Classic(...)`. They are
**construction-failure lines**, not evidence that the run loaded that asset.
The name is real and worth recording as a name; the binding was invented. The
section heading named a mode off it and has been changed too.

**So this run's settings asset is UNKNOWN**, and the "sharpest discriminator
candidate" that `docs/FINDINGS.md` 12.1 built on it is withdrawn with it.

**`WhiteWoods_Enemy_Day_Solo01` is first-party corroboration of a solo run.**
The operator attested "solo" and the game loaded a spawner set whose own name
says `Solo01`. Two independent sources, one of them the game's own asset path.

**The difficulty here is `Easy`, from the sublevel names**, and it is worth
saying that the word `difficulty` occurs **zero** times in the log - the
difficulty is legible only through which `Spawners_<tier>` sublevels load.
`Normal` appears 20 times and **none of them is a difficulty**: they are Wwise
audio events, an arrow blueprint (`Arrow_Normal`) and a config-path helper.
Grepping for the player-facing difficulty word finds nothing, exactly as
grepping for `raid` and `extract` did.

## Blackarrow talents at level 5 - 2026-08-25b, on buildid 24813185

**Method: passive capture joined to operator attestation**, the same join as the
2026-08-09 pass. `tools/frame_poller.py` at a 2 s interval while the operator
hovered nodes; every name and every effect line below was **read off the
rendered tooltip**, not from a wiki and not from an icon. Frames are at
`C:/ll-captures/2026-08-25b/talents/` and are **not committed** - they are
full-screen and show the account panel.

Level confirmed on screen: **Lv. 5**. Three arrow slots bound (`Z`, `X`, `C`),
three skills equipped.

### The slot iconography, which is a reading rule worth having

Three states are distinguishable in the arrow and skill rows, and conflating the
last two would miscount a loadout:

| Rendering | Meaning |
|---|---|
| **Solid tan-gold border, no glow** | owned AND equipped |
| **Gold border WITH a halo/glow** | **hovered** - says nothing about equipped |
| **Dashed border, no padlock** | owned/unlocked but NOT equipped |
| **Padlock glyph** | locked |
| **Solid white border** | a fourth state, seen on Skills slot 4 - **meaning unknown** |

**An earlier draft collapsed the first two rows into "gold border = equipped",
and that is REFUTED by its own frames.** Hunter's slot 2 - `Barbed Arrow`,
never equipped - renders dashed in one frame and a bright glowing gold in
another, under the cursor. Hover paints a gold halo. Reading any gold border as
"equipped" would have counted a hovered slot as an owned-and-equipped one.

**The loadout counts below were re-verified against seven frames after this was
found, and they hold.**

### Loadout at level 5

| Row | State |
|---|---|
| Archer's Arrow | **3 equipped**, 1 unlocked-not-equipped, 1 locked |
| Hunter's Arrow | **0 equipped**, **1 unlocked-not-equipped**, 4 locked |
| Skills | 3 equipped, 1 unlocked-not-equipped, 3 locked |

At level 2 this was 2 of 5 Archer's and **0 of 5 Hunter's, all locked**. So one
Hunter's arrow has since unlocked, and it is still not equipped.

### New talent nodes, effect text verbatim

**Archer's Arrow Enhancement 1** (unlocks Lv. 3) - every node buffs a specific
ARROW:

| Node | Effect, verbatim | Selectable |
|---|---|---|
| Astound | Increases the `knockback` distance of fully drawn Concussive Arrows. | Activate |
| Sepsis | Increases the `Damage Multiplier` of fully charged Splatter Arrow's splash. | Activate |
| Lightning Spread | Increases the chaining range of the lightning generated by a fully drawn Lightning Arrow. | Activate |

**Mighty Archer** (unlocks Lv. 5) - every node buffs a specific SKILL:

| Node | Effect, verbatim | Selectable |
|---|---|---|
| Unstoppable Edge | Sky Piercer's `Physical Damage` is partially converted to `True Damage`. | Activate |
| Focus Fire | Rapid Arrows increase the `Damage Multiplier` with each hit on the same enemy. | Activate |
| Powerful Scattershot | After Scattershot `knocks back` enemies, if they `stop` due to obstruction, they will be `Stunned`. The greater the impact force when enemies hit obstacles, the longer the `Stun` duration. | Activate |

**That split is the structural finding**: Archer's Arrow Enhancement buffs
arrows, Mighty Archer buffs skills. It also means a node's value depends
entirely on whether the named arrow or skill is owned, which is the same
loadout-gating that made the level-2 choice inert.

**Battle Hardened**: `Dodge Power Shot` now renders an `Activate` bar. At level
2 it rendered none, so it has become selectable in the interim.

**`Rapid Arrows`, verbatim** - the only skill whose name is confirmed by its own
tooltip rendering:

> After using the skill, Blackarrow enters Volley mode, allowing you to hold to
> rapidly fire up to 5 arrows for a certain duration, dealing Physical Damage.
> During Volley, shooting does not reduce Movement Speed. Dodging removes
> Volley.

**Three skill names are now first-party**: `Rapid Arrows`, `Sky Piercer` and
`Scattershot` - the latter two because the Mighty Archer tooltips name them.
**That the operator OWNS Sky Piercer and Scattershot is NOT established**: it is
an inference from two equipped icons, and this document does not bind a name to
an icon. Only `Rapid Arrows` is confirmed both named and owned.

**No magnitude appears on any node.** "Increases the Damage Multiplier" and
"Increases the knockback distance" carry no number, so nothing here supports a
coefficient and none is recorded.

## 2026-08-30 session - client `1.0.15`, and the ids it bound

Read from the live `MistfallHunter.log` covering 2026-08-30 00:20 to 01:24
local, plus the two rotated backups from 2026-08-26 where a comparison is
stated. Log stamps are UTC; local is UTC-5.

### The client build marker - use THIS, not the Steam buildid

TRANSCRIPTION, one hit per log:

    TS.Default: [Startup] Version: <version>, Build Date: <stamp>

| log | Version | Build Date |
|---|---|---|
| backup 2026.08.26-01.27.09 | `1.0.14` | `20260818232428` |
| backup 2026.08.26-04.45.02 | `1.0.14` | `20260818232428` |
| live 2026-08-30 | `1.0.15` | `20260826170036` |

**The client was patched between 2026-08-26 and 2026-08-30.** By this file's own
standing rule, every row dated 2026-08-25 was measured on `1.0.14` and is now
provisional.

**The string `buildid` occurs ZERO times in all three logs.** The Steam buildid
`24813185` recorded at the top of this file is a depot value; the log is not its
source and can neither confirm nor refute it. Anchor future passes on `Version`
plus `Build Date`, which is first-party and in-log.

### Equipment slots are BOUND - slot number to slot NAME, from the log alone

**Method: a two-surface join on item cfgId, no pixels involved.** The log emits
one line per slot naming it:

    TS.AI: generateBotPlayerStateData <slotName>: <itemCfgId>

and equipment payloads elsewhere carry the same items as
`{"cfgId":<id>,"slot":<n>}`. Joining on the cfgId gives the binding. **Every one
of the eight bot equipment cfgIds resolves to exactly ONE slot number** across
the whole log - checked for ambiguity rather than assumed.

| slot | name | joined via cfgId | uniqueness |
|---|---|---|---|
| 0 | `helmet` | 1150108 | unique |
| 1 | `cloth` | 1250108 | unique |
| 2 | `glove` | 1350108 | unique |
| 3 | `pants` | 1450108 | unique |
| 4 | `shoe` | 1550108 | unique |
| 5 | `necklace` | 1650103 | unique |
| 6 | `ring` | 1750201 | unique |
| 11 | `weapon2` | 3050208 | unique |

**`weapon1` is NOT bound.** The log emits the name but never with a cfgId in
this capture, so slot 10 holding weapon-family cfgIds and being the only
unclaimed weapon slot is an INFERENCE by elimination, not a join. It is left
unbound here deliberately.

The game's own slot nouns differ from the words this project's UI notes use.
Recorded as the game states them: `cloth` not "armor", `glove` not "bracers",
`shoe` not "boots", `necklace` not "pendant".

### Item cfgIds are partitioned by equipment family

TRANSCRIPTION. Grouping every `{"cfgId":<id>,"slot":<n>}` by the id's leading
two digits:

| cfgId family | slots it appears at |
|---|---|
| `11xxxxx` | 0 |
| `12xxxxx` | 1, 37 |
| `13xxxxx` | 2, 35 |
| `14xxxxx` | 3, 36 |
| `15xxxxx` | 4, 38 |
| `16xxxxx` | 5 |
| `17xxxxx` | 6 |
| `30xxxxx` | 1, 10, 11, 33, 34 |
| `90xxxxx` | 1, 2, 17, 38 |

The leading two digits track the equipment family exactly for `11` through `17`,
matching the slot names above. **INFERENCE:** item cfgIds are allocated in
per-slot blocks. Useful, and not a licence to guess an unobserved id.

**Slots 33 to 38 are a SECOND range carrying the same item families**, and this
file does not explain them. They are not a fixed offset of 0 to 6 - `13xxxxx`
sits at 2 and 35 while `12xxxxx` sits at 1 and 37 - so a simple "+33 preset"
reading is refuted by the data. A second loadout or preset is the obvious guess
and is NOT asserted. Slots 17 and 53 are likewise unexplained.

**`slot` is NOT one namespace.** The same key carries equipment slots, inventory
positions and at least one ammo id (`120508` appears as a `slot` value). Read
`slot` only in the context of the payload it sits in.

### Seven wearable non-weapon slots, and what that does NOT settle

Slots 0 to 6 are exactly seven wearable non-weapon slots. The Auction House
trade filter's `ARMOR` category takes `itemSubType` values 1 to 7, also exactly
seven - see `docs/AFFIXES.md`.

**The correspondence is suggestive and the mapping is NOT established.** Slot
numbers start at 0 and subtypes start at 1, so any binding needs an offset that
nothing has observed, and the ORDER of the subtype numbering is unobserved too.
Recorded as a testable hypothesis, not a binding.

### Class and gender ids, re-observed on client `1.0.15`

Corrected log shape - note the DOUBLE space before `==`:

    TS.Dungeon: [basedatacomponent] setClassGender inclassid  ==NN, inGender ==N

156 matches in the live log. Distinct pairs, with counts:

| classId | class (from the table above) | inGender | count |
|---|---|---|---|
| 10 | Mercenary | 1 | 8 |
| 12 | Blackarrow | 1 | 3 |
| 12 | Blackarrow | 2 | 139 |
| 13 | Shadowstrix | 1 | 5 |
| 15 | Withered Knight | 2 | 1 |

**RE-OBSERVATION, not a new binding.** These four class ids were already bound
by the 2026-08-09 pixel join. What is new is that they still hold on client
`1.0.15`, four days after the previous capture and across a patch. Classes 11
(Sorcerer) and 14 (Seer) were not emitted in this session - an absence of
observation, nothing more.

### The numeric affix namespace

Seven ids observed across two surfaces and three logs. Full derivation, counts
and per-log breakdown are in [`AFFIXES.md`](AFFIXES.md); recorded here because
this file is the authority for engine ids.

| affix id | name | key paths it appears at | how established |
|---|---|---|---|
| 101 | UNBOUND | `affixes[].cfgId` | - |
| 201 | **`Valor`** | `affixIds[]` | pixel-joined, 2026-08-30 |
| 208 | **`Fervid`** | `affixIds[]`, `affixes[].cfgId` | pixel-joined by set difference, 2026-08-30 |
| 209 | UNBOUND | `affixes[].cfgId` | - |
| 211 | **`Ranged`** | `affixIds[]`, `affixes[].cfgId` | pixel-joined, 2026-08-30 |
| 212 | UNBOUND | `affixIds[]`, `affixes[].cfgId` | - |
| 214 | UNBOUND | `affixIds[]` | - |

**Method for the three bound rows**, same wall-clock join that bound the class
ids: the client emits `[TradeCtrl] request Trade Goods {...,"affixIds":[N],...}`
when the Auction House affix filter changes, and a frame captured at the same
wall clock shows which row is checked and which icon the filter header carries.
`201` and `211` are read directly; `208` follows by set difference from a
two-element request whose other member is `211`. Full derivation, the frames
cited, and the two arguments that were tried and REFUTED are in
[`AFFIXES.md`](AFFIXES.md).

**The logs contain no affix names at all** - every catalogue name returns zero
occurrences across all three logs - so this binding is not recoverable from text
and the join is the only route.

**`cfgId` is a PER-TABLE key, not a global id, and this matters more than the
list does.** The same field name carries item ids of six and seven digits, affix
ids of three, and gem ids in a `22xxxx` family. `101` is an affix id here and a
currency id elsewhere in the same corpus. **The namespace is decided by the KEY
PATH, never by the value** - which is why every row above names its path. A
lookup that takes the bare integer without its path returns the wrong row.

**The `101` collision, verified rather than asserted.** The live log carries both
`"affixes":[{"cfgId":101,...}]` (in the backups) and `"currencyId":101` with a
matching `TS.Default: [Currency] Request currency info 101 169`. Two different
tables, same integer. The value `169` in that line also equals the coin balance
rendered in the Auction House header at the same wall clock, so currency `101`
is the currency the Auction House spends - **which this project has NOT bound to
a name.** `docs/AFFIXES.md` records `Gyldenblod` as a game noun of unstated
kind; nothing here connects the two and no connection is asserted.


## Rule

Every future id binding gets recorded here at the moment it is observed, with
the observation method named. An id learned six weeks later from a wiki is not
the same fact as an id watched being emitted.
