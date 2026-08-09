# Observed engine ids

First-party observations read out of `%LOCALAPPDATA%\MistfallHunter\Saved\Logs\
MistfallHunter.log`. Nothing here is from a wiki. Each row says how it was
established, because the log emits NUMBERS and never a class name string - every
id-to-name binding therefore rests on an operator observation made at the same
moment, not on the log alone.

Game build: Steam buildid `24619162`. Observed 2026-08-09.

## Class ids

Log line: `TS.Dungeon: [basedatacomponent] setClassGender inclassid ==NN, inGender ==N`

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
captured the TALENTS screen every 2s from 16:01:06 to 16:09:16 local while the
operator hovered each node in turn; the operator then named which frame showed
which node, and every name and description below was **read off the rendered
tooltip in that frame**. No wiki, no inference from the icon.

Frames are at `~/.lanternlight/frames/` and are **not** committed - a capture of
a running game shows the account panel.

**12 clusters over 2 pages.** Only **Battle Hardened** is unlocked at level 2;
every other cluster displays `Unlocks at Lv. N`.

**Nodes within a cluster are linked, and the links are prerequisites.**
Operator-attested: at level 2 only **Measured Pace** and **Battle-fed** are
selectable, and they are **mutually exclusive** - one or the other, not both.
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
| Way of the Gylden Hunt | Lv. 12 | 2 |

### Battle Hardened - the six nodes, with tooltip text

| Node | Effect, verbatim from the tooltip |
|---|---|
| Measured Pace | When carrying at least 2 Archer's Arrows, fully drawing and immediately firing Normal Arrows recovers Energy. |
| Battle-fed | When carrying at least 2 Hunter's Arrows, hitting an enemy with a shot reduces the remaining cooldown of all skills. |
| Lasting Pain | After hitting an enemy with a shot, increases the duration of all active debuffs on that enemy. |
| Marksman | Fully-drawn arrows will home in on enemies near the crosshairs. |
| Dodge Rapid Shot | Changes roll into dodge and unlocks Dodge Rapid Shot: shoot immediately after dodging, consuming additional Energy to quickly fire both the currently loaded arrow and a normal arrow toward enemies near the crosshairs. This skill has a cooldown. |
| Dodge Power Shot | Changes roll into dodge and unlocks Dodge Power Shot: shoot immediately after dodging, consuming additional Energy to quickly fire the currently loaded quick-charge arrow. Quick-charge arrows can activate all special effects of fully drawn arrows but have a lower Damage Multiplier. This skill has a cooldown. |

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

Owned: **Steel Arrow** and **Concussive Arrow**.

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

**Still no numbers.** "Physical Damage", "stagger", "knock back", "within range"
- no magnitude, no duration, no radius. Consistent with every other tooltip
captured today.

### Node names in the remaining clusters

Names and icons operator-attested per frame; tooltip text captured only where
noted, so these are **names, not effects**.

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
| Way of the Gylden Hunt | Death Sense, Greed is Good, Gyldenmist Tolerance, Monster Hunter |

`*` tooltip text also captured:

- **Full Draw** - Increases the Damage Multiplier of fully drawn arrows.
- **Blood Infection** - Upon hitting an enemy, Bloodfly Arrow deals reduced DoT
  but inflicts bonus Swarm stacks. Hitting an enemy that has Swarm stacks with
  any fully drawn arrow other than Bloodfly Arrow will detonate the Swarm,
  dealing bonus damage. The more Swarm stacks, the higher the damage. The swarm
  detonation deals Critical Damage, with a portion converted to True Damage.
- **Crippling Pain** - Enemies damaged by Impact Grenade have reduced Movement
  Speed for a period of time.
- **Swift Exit** - Allows you to learn the spawn location of the Smuggler
  Woodling and Soul Ferry in advance.

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

**No numbers appear anywhere in these tooltips.** Every effect is qualitative -
"recovers Energy", "reduces the remaining cooldown", "lower Damage Multiplier" -
with not one magnitude given. That is consistent with the project's founding
measurement: this game publishes no coefficients, and any source quoting one is
fabricating it.

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

## Rule

Every future id binding gets recorded here at the moment it is observed, with
the observation method named. An id learned six weeks later from a wiki is not
the same fact as an id watched being emitted.
