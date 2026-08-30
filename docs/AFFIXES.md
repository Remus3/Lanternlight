# Affixes, gems and item stats - read off the game's own UI

**This document holds GAME-STATED data, not measured data, and the distinction
is the whole point of the file.** Everything here was read from an item tooltip
rendered by Mistfall Hunter itself. Nothing here was inferred from a damage
curve, and nothing here came from a wiki.

Keep that separation. `docs/FINDINGS.md` holds what this project MEASURED and
carries intervals and error bars; this file holds what the game SAYS and carries
none, because a tooltip is a claim by the developer rather than an observation
of behaviour. A game that states `+1.6%` and applies `+1.4%` is a thing that
happens, so a number here is a hypothesis about behaviour and a starting point
for measurement - never a substitute for it.

## Why this file exists at all

Opened 2026-08-30, at the operator's prompting, and the prompting is the
finding. This project had been treating affix ladders, gem slotting and item
stat tables as **unpublished** - things to be reverse-engineered from damage
data or sourced from launch-window wikis that cross-copy each other.

They are not unpublished. **The game states them, in full, in the item
tooltip.** Nobody had looked there.

That is a sourcing error of the same family as the ones in `LL-0079` and
`LL-0081`: the answer was not hard to get, it was being sought in the wrong
place, and a confident "no source publishes this" was a claim about where we
had looked.

**Trust position.** For item mechanics the game's own UI outranks everything in
the `docs/ECOSYSTEM.md` source register, including T1. Bellring's patch notes
are qualitative by policy and never carry a magnitude; the tooltip carries the
magnitude. Record the reading, name the frame it came from, and treat it as the
best available statement of intent.

**Method, so it is reproducible.** Read off a passive screen capture of the
operator's own display - the sanctioned surface, ADR-001 untouched. Frames live
outside the repository and are never committed: a full frame carries the
operator's persona and on-screen position. What is committed is the READING.

## The `Ranged` affix - read 2026-08-30 from a Legendary bow

Read from frames **`f0636_00.45.07`** (the item tooltip) and
**`f0749_00.47.32`** (the affix detail panel). A first version of this section
named NEITHER, while carrying the entire ladder and every item stat - a
violation of this document's own method paragraph above, which says to name the
frame a reading came from. Recorded rather than quietly fixed, because the
sections that cite no source are exactly the ones that go unchecked.

Observed on `Deathclaw Hunter`, `Legendary Bow and Arrow`, at affix level 1.
The tooltip renders the bare token `Blackarrow` above the price block with no
label; reading that as a class restriction is an INFERENCE, not a reading.

Quoted from the panel (its own headers are underlined and unpunctuated; the
bold-with-period styling below is this document's, not the game's):

> **Effect.** If the distance between you and the target is greater than
> 5 meters when hit, temporarily increase Physical Damage and Magic Damage.
> Upon reaching a certain level, increase ranged damage's effective range.
>
> **Effective Range.** Different ranged attacks have different Effective
> Ranges. Beyond the Effective Range, both DMG and Impact will diminish.

**Level Distribution** - a row of nine equipment-slot icons with a value under
each. On this reading (frame `f0749`) the weapon slot carried `1` and the other
eight read `-`.

**A first version of this document read that as "this affix appears on weapons
only". That was WRONG and is withdrawn.** The row is not an eligibility table,
it is a **per-character breakdown of where your CURRENT levels come from**. At
`f0749` the character had `Ranged Lv.1`, all of it from the bow, so the row read
`1` and eight dashes. The refutation below proves the same affix sits on helm,
bracers, pendant and ring.

Reading a breakdown as an eligibility table is the error, and it inverted the
meaning: the row says where levels ARE, not where they CAN BE.

**Affix Level ladder, stated:**

| Level | Physical Damage | Magic Damage | Effective Range |
|---|---|---|---|
| Lv. 1 | +1.6% | +1.6% | - |
| Lv. 2 | +3.2% | +3.2% | - |
| Lv. 3 | +4.8% | +4.8% | - |
| Lv. 4 | +6.4% | +6.4% | - |
| Lv. 5 | +8% | +8% | +12% |
| Lv. 6 | +9.6% | +9.6% | +12% |
| Lv. 7 | +11.2% | +11.2% | +12% |

The damage figures are exactly `1.6% * level`. Effective Range appears at Lv. 5
and is flat `+12%` through Lv. 7, which is what "upon reaching a certain level"
in the effect text refers to.

### Why this matters far beyond one affix

**It is a distance-gated, TEMPORARY damage buff, stated by the developer.**
That collides with two things this project already believes:

- `ROADMAP` item 10 chases a buff icon that climbs to 5 while the operator
  keeps hitting one target. This affix grants a *temporary* damage increase on
  a *distance* condition. It is now a live candidate for that buff, and it is a
  candidate item 10 never considered - that item weighs `Focus Fire` (a talent)
  against "a base mechanic that was always there", and a WEAPON AFFIX is
  neither.
- `docs/FINDINGS.md` 11.7 reports that a constant per-hit value fits every
  FLOOR run and no off-floor run, and reads that constancy as a property of the
  clamp. **Here is an explicit distance term at 5 meters, from the game**, on
  the weapon that produced those runs. A distance-gated buff reproduces a
  floor/off-floor split without any clamp.

**Neither of those is resolved here, and neither should be written up as
resolved.** What changed is that a third explanation now exists and is
first-party. Deciding between them needs the item 10 measurement, and it now
needs the weapon's affix set recorded alongside every run - which no previous
run recorded, so no previous run can be re-attributed with confidence.

## Affixes and gems COEXIST - `docs/CLASSES.md` needs correcting

`docs/CLASSES.md` records two positions that this reading contradicts.

**Position 1, that the game "publishes no affix list, roll ranges, weights,
tiers or socket" data.** Refuted for at least this affix: the tooltip publishes
a named affix, its full seven-level ladder with exact percentages, and its
per-slot distribution. It is published, in the client.

**Position 2, that community affix names are "almost certainly gem effects
wearing legacy ARPG vocabulary", on the basis of DevNote #6 and Dev Team FAQ #2
saying gems replaced random gear affix rolls.** Partly right and partly wrong,
and the item shows both halves at once. The same `Deathclaw Hunter` tooltip
carries, in order:

- `Ranged  Lv.1` - in its own section, with an affix icon and **no gem icon**.
- `Tier II Peridot Slot - Empty` - an empty gem socket.
- `[gem icon] Fervor  Lv.1` - a **filled** socket, the gem shown beside it.

So `Fervor` is arriving through a gem, which is what DevNote #6 describes, while
`Ranged` sits above the sockets with no gem attached. **Gems did not replace
affixes; the two coexist on one item, and the tooltip renders them differently.**
The community vocabulary was not simply legacy ARPG noise - `Ranged` and
`Fervor` are both names the game itself uses.

**That open question is now SETTLED** - see the gem section below. Gems are
called `Affix Gem` by the game and they GRANT affixes. The character's `Affixes`
panel lists `Ranged` and `Fervor` side by side with no marker distinguishing
them, so an affix is an affix regardless of how it arrived. `Ranged` sits on the
item; `Fervor` is delivered by a socketed gem. One system, two delivery routes.

## Gems - the socketing rules, read 2026-08-30

### The gem that was in the bow

The socketing screen (`PREPARE`, frame `f1697`) shows the `Deathclaw Hunter`
with an `Equipped` gem named **`Warspirit Moonstone`**, and the item's
`Fervor Lv.1` row carries that gem's icon. So:

    Warspirit Moonstone  ->  grants  ->  Fervor Lv.1

The right-hand `Attributes | Affixes` tab then lists `Ranged Lv.1` and
`Fervor Lv.1` together - identical icon frames, identical seven-segment pip bars
with one segment filled, identical level labels, nothing distinguishing them.

**That is corroboration, not proof, and an earlier version of this document
called it proof.** An undifferentiated list is CONSISTENT with one system; it
does not establish one. The actual evidence is elsewhere and this document has
it: the game names the category `Affix Gem`, the gem tooltip grants named
affixes each with a level, and `Warspirit Moonstone` binds to `Fervor Lv.1`.

### The rule, stated verbatim by the game

From an `Affix Gem` tooltip in the Auction House (frame `f1829`):

> Can be inlaid into equipment sockets of the matching type. **The level of an
> Affix Gem cannot exceed the level of the target equipment socket.**

Two constraints, both first-party, and together they answer the question this
document opened with about whether tier gates level:

1. **Type must match.** A gem goes only into a socket of its own type. The bow
   carried a `Tier II Peridot Slot - Empty` alongside its Moonstone, so one item
   can hold sockets of different types.
2. **Socket LEVEL caps gem LEVEL.** A gem cannot exceed its socket.

**TIER AND LEVEL ARE DIFFERENT QUANTITIES, and an earlier version of this
document conflated them.** The inlay rule says *level*, twice, and never says
tier. On the very tooltip that states it, a `Tier 2` gem grants two `Lv.1`
affixes - so tier is not level. **No socket LEVEL appears anywhere in the
evidence gathered so far**: the bow's socket shows a TIER (`Tier II`). So the
rule's ceiling is real and stated, and the quantity it names has not yet been
observed on any socket. Finding where a socket's level is displayed is the next
cheap reading, and until then nothing here says what caps what in practice.

### Gem structure

Read from the same tooltip - `Flawless Fortune Peridot`, described by the game
as a **`Tier 2 Affix Gem`**:

> **`Seamless` Lv.1** - Increases `Skill Cooldown Speed`. Upon reaching a
> certain level, knocking down a `Gyldhunter` reduces skill `cooldowns`
> currently in progress.
>
> **`Wealth` Lv.1** - Increase the amount of `Gyldenblod` from PvE in dungeons.

**One gem carries MORE THAN ONE affix.** This gem grants two, each with its own
level. Of the listing rows legible in `f1829` - the left column is largely
occluded by the open tooltip - every one shows two small icons, which is
consistent with two-affix gems being the norm. "Every row in the browser" would
be a generalisation from a partial view, and is not claimed.

**Gem types and tiers are both filterable**, so both are real taxonomies: the
browser offers a `Gem Type` filter with four icons and a `Gem Tier` filter with
two. Two type names are confirmed - `Peridot` (green) and `Moonstone` (teal) -
and the other two types are unnamed so far. `Tier 2` is confirmed by name and
the bow's socket read `Tier II`, so tier IS shared vocabulary between gem and
socket. That is a matching taxonomy and nothing more - it does not satisfy the
inlay rule, which is about level. An earlier version claimed it did.

**Gem names DO map to their affixes, by SYNONYM, and an earlier version of this
document said they do not.** That was wrong and the reasoning is corrected here
because the wrong reason is more dangerous than the wrong advice.

`Flawless Fortune Peridot` grants `Seamless` and `Wealth`. Flawless/Seamless and
Fortune/Wealth are synonym pairs, in the same word order. The listing icons
confirm it positionally: `Brutal Blessed Peridot` and `Brutal Fortune Peridot`
share their first icon; `Tenacious - Blessed Peridot` and `Brutal Blessed
Peridot` share the flask; `Ranged Ward - Fortune Peridot` carries the same star
that the tooltip labels `Wealth`.

**The advice stands, the reason changes.** Do not parse gem names - not because
they carry no information, but because the mapping runs through an unenumerated
synonym table, and a guess that lands on the wrong synonym is indistinguishable
from a correct read. Use the tooltip. Recording the synonym structure anyway,
because it is a real property of the naming scheme and it says the affix set is
larger than the affix WORDS seen so far.

**Affixes confirmed from gems, adding to the roster above:** `Seamless`
(Skill Cooldown Speed) and `Wealth` (Gyldenblod from PvE in dungeons).

**Two new game nouns worth binding:** `Gyldhunter`, an enemy or enemy class that
can be knocked down; and `Gyldenblod`, of which the tooltip says only "the amount
of Gyldenblod from PvE in dungeons". Whether it is a currency, a material or a
score is UNSTATED - an earlier version of this document called it a currency,
which the evidence does not say.
Note `gyldforge.com` already sits in the `docs/ECOSYSTEM.md` source register -
the shared `Gyld` root is worth a look, but nothing here establishes a link and
none should be asserted.

**Gems are auction-house tradeable** with an `Average Transaction Price` and a
`Value` shown side by side, the same two-number pattern the weapon carried
(116 against 100 here). `lanternlight/avgprice.py` already watches the cache
behind one of them.

## The affix ROSTER, read 2026-08-30 from `PREPARE` -> `Affixes`

The `PREPARE` screen carries an `Attributes | Affixes` tab that lists affixes
with a level and a pip bar. Read from frame `f1290`:

| Affix | Level |
|---|---|
| `Fervid` | Lv. 7 |
| `Ranged` | Lv. 7 |
| `Focused` | Lv. 6 |
| `Skypiercing` | Lv. 4 |
| `Valor` | Lv. 3 |
| `Elusive` | Lv. 2 |
| `Wrath` | Lv. 1 |
| `Smiting` | Lv. 1 |
| `Curse` | Lv. 1 |

**READ THE CAVEAT BEFORE USING THIS TABLE.** The panel had the `Recommended`
preset selected - rendered left-truncated as `ndary - Blackarrow (Bow)`, so
`Legendary` is RECONSTRUCTED from the Rare/Excellent/Epic entries above it and
not read - with `Quick Buy & Equip` and a
`Total Expense` of 16,559 showing. So these are the affixes that preset WOULD
grant, not a reading of currently equipped gear. It is a statement about a
loadout the game itself recommends - useful, and not the same fact as "what the
operator is wearing". Re-read it against `Current Loadout` before treating any
level here as the operator's.

**ONE ICON IS ONE LEVEL, SUMMED ACROSS EQUIPPED GEAR. This is proven, not
inferred**, and a first version of this document under-claimed it as "not yet
proven" while simultaneously over-claiming the weapons-only line above. Both are
corrected.

Every item tile in `f1290` carries a strip of four affix icons - eight FILLED
pieces, the ninth tile being an empty secondary-weapon slot. Counting the
`Ranged` feather glyph across the preset's **eight filled pieces**: bow 2,
helm 2, bracers 1, pendant 1, ring 1 = **7**, against a panel reading of
`Ranged Lv.7`. The same count reproduces every other affix:

| Affix | icons counted across the loadout | panel |
|---|---|---|
| `Ranged` | bow 2, helm 2, bracers 1, pendant 1, ring 1 | Lv. 7 |
| `Fervid` | bow 1, bracers 1, pants 2, boots 1, pendant 1, ring 1 | Lv. 7 |
| `Focused` | bow 1, helm 1, armor 1, bracers 1, boots 1, ring 1 | Lv. 6 |
| `Skypiercing` | armor 1, pants 1, boots 1, pendant 1 | Lv. 4 |
| `Valor` | helm 1, bracers 1, boots 1 | Lv. 3 |
| `Elusive` | pendant 1, ring 1 | Lv. 2 |
| `Wrath` / `Smiting` / `Curse` | 1 each | Lv. 1 each |

Eight pieces times four icon slots is **32 icons**, and the panel levels sum to
7+7+6+4+3+2+1+1+1 = **32**. Nine independent per-affix matches and an exact
total. That is what makes `Level Distribution` a breakdown rather than a
permission list, and it is why the weapons-only reading above was withdrawn.

### This resolves the `CLASSES.md` affix-versus-gem confusion

`CLASSES.md` lists, from T4 guide consensus, "Ranged, Focused, Elusive, Fervid,
Curse, Valor, Fervor" and doubts all of them. Measured against the client:

- **Six are confirmed present on a loadout** - `Ranged`, `Focused`, `Elusive`,
  `Fervid`, `Curse`, `Valor`. Note the weaker wording: `f1290` is one loadout's
  affix summary, NOT a catalogue of every affix in the game. Confirming a name
  appears is enough to refute "this is legacy ARPG vocabulary"; it is not enough
  to enumerate the game's affix set, and no frame here does that.
- **Three the guides did not have** - `Skypiercing`, `Wrath`, `Smiting`.
- **`Fervor` is absent from THIS PRESET's list** - and an earlier version of
  this document turned that into "`Fervor` is NOT in the affix list", which is
  **FALSE and is withdrawn**. It contradicted this document's own statement,
  three sections above, that the character's `Affixes` panel lists `Ranged` and
  `Fervor` side by side with nothing distinguishing them. Both `f0749` and
  `f1697` show exactly that. `Fervor` is missing from `f1290` only because that
  Recommended preset has no Moonstone socketed. **An argument from absence, in a
  panel that shows one loadout rather than a catalogue.**

That is a clean resolution rather than a flat contradiction. The guides were
mostly right about the names and wrong to file `Fervor` among them; DevNote #6
was right that gems grant effects of this kind; and the inference that ALL of
these names were "gem effects wearing legacy ARPG vocabulary" was wrong. Both
systems exist, the tooltip renders them differently, and the affix list names
only one of them.

## `Focus Fire`, the talent - read 2026-08-30 from `TALENTS`

`ROADMAP` item 10 turns on this talent's exact scope, and the talent screen
states it. Verbatim from frame `f1200`, tooltip open:

> **Focus Fire.** Rapid Arrows increase the `Damage Multiplier` with each hit
> on the same enemy.

Recorded with it: the node is **currently allocated** - it renders lit with a
`Revert` action offered - and the character has **0 Talent Point** unspent at
**Level 5**. Neighbouring nodes are gated: `Swift Shot` at Lv. 8, `Nimble
Evade` at Lv. 7, a second `Archer's Arrow Enhancement` at Lv. 11. Other named
nodes visible: `Battle Hardened`, `Archer's Arrow Enhancement 1`.

**What this settles for item 10.** That item recorded the tooltip as scoping
the effect to `Rapid Arrows` and could not quote it. Now it is quoted, and it
adds a term the item did not have: the thing that increases is a named
`Damage Multiplier`, not a flat damage add. "With each hit on the same enemy"
matches the observed icon climbing to 5 while hitting one target.

**What it does NOT settle, and the contradiction now on the table.** The
operator reports the buff is not appearing at all in this session - while
`Focus Fire` is allocated. Both cannot be casually true. The candidates, none
eliminated:

1. `Rapid Arrows` is not the skill being used now, so the talent never fires.
   The tooltip scopes it to that skill and previous runs measured inter-hit
   intervals of 2.27 to 2.87 s, which item 10 reads as drawn shots.
2. The climbing icon was never `Focus Fire` at all, and was the `Ranged` affix's
   temporary distance buff - a candidate that did not exist when item 10 was
   written.
3. The effect is present but invisible at this character's level and gear.

**The target-switch test item 10 already specifies now discriminates cleanly**,
which it could not before: `Focus Fire` is scoped to ONE ENEMY, and the `Ranged`
affix is scoped to DISTANCE and indifferent to the target. Ten hits alternating
between two enemies separates them in one run.

## Other item facts read from the same tooltip

Recorded because they are cheap to capture and were never written down:

- Item identity: `Deathclaw Hunter`, rarity `Legendary`, type
  `Bow and Arrow`, class restriction `Blackarrow`.
- Base stats: `40 Attack`, `+7.20% Physical Damage`. Note the base line is a
  flat percentage on the item, separate from the affix ladder.
- `Durability 100%`, with its own info tooltip.
- `Average Transaction Price 2,467` against `Value 345` - two different numbers
  the UI shows side by side, and the same pairing appears on gems (116 against
  100). Which is market-derived and which is intrinsic is NOT stated on screen;
  an earlier version of this document asserted it. The naming is suggestive and
  `lanternlight/avgprice.py` already watches an `AvgPrice` cache, so the link is
  worth measuring rather than assuming.
- Gem slots are TIERED and typed: `Tier II Peridot Slot`.

## The AFFIX SURFACE IN THE LOG - read 2026-08-30, and nobody had looked

**Everything above this line was read off PIXELS. This section is read off
TEXT**, out of the game's own log, and it is a different evidence class that
this document did not previously have.

The difference is not cosmetic. A tooltip has to be transcribed by eye, and this
document has already withdrawn two conclusions drawn from correctly transcribed
tooltips. A log string cannot be misread - it can only be mis-INFERRED.
`CLAUDE.md` states the preference directly: prefer text over pixels whenever a
text path exists. For affixes a text path exists, and the whole tooltip
workstream ran without it.

**Corpus, named because a count is meaningless without one.** Three logs on this
machine: the live `MistfallHunter.log` (session 2026-08-30 00:20 to 01:24 local,
37,651 lines) and two rotated backups from 2026-08-26.

**A CLIENT PATCH RUNS THROUGH THIS CORPUS, and every cross-log statement below
inherits the caveat.** The client's own startup line - `TS.Default: [Startup]
Version: <v>, Build Date: <stamp>`, one hit per log and the only in-log build
identifier found - reads `1.0.14` / `20260818232428` in BOTH 2026-08-26 backups
and `1.0.15` / `20260826170036` in the live 2026-08-30 log. The two backups are
one client build; the live log is a different, later one. **A union taken across
all three is a union across two game versions, not a snapshot of one.** Where
that changes a reading below, it is said explicitly.

Note also that `docs/OBSERVED_IDS.md` records the game build as Steam buildid
`24813185`. The literal string `buildid` occurs **zero** times in all three
logs, so that value is a Steam depot number and the log neither confirms nor
refutes it. `Version` plus `Build Date` is the log's own identifier and is the
one to anchor future passes on.

**"37,651 lines" needs its method stated, because the number is
definition-dependent.** That is the count of newline bytes. The log also embeds
83 other C0 and C1 control characters - `0x0b`, `0x0c`, `0x1c`, `0x1d`, `0x1e`
and `0x85` - which Python's `splitlines` treats as line breaks and `wc -l` does
not, so the same file reads as 37,748 lines under one definition and 37,651
under the other. Neither is wrong. A tool that reports a line count for this log
without saying which rule it used is reporting an ambiguous number, and any
per-line parser has to decide what those 83 bytes mean. Log timestamps are UTC
and local is UTC-5. Counts below say which log they came from and are never
blended silently.

### The trade filter payload - a machine-readable grammar

The client emits a JSON search filter. Transcribed shape, one real example from
the live log:

    {"itemType":"AFFIX_GEM","itemSubType":16,"affixIds":[208,211],
     "currentClass":false,"primaryAttr":"PRIMARY_ANY",
     "secondaryAttr":"SECONDARY_ANY","page":0,
     "affixGemTypes":[4],"affixGemLevels":[2]}

TRANSCRIPTION. Six fields are always present - `itemType`, `itemSubType`,
`currentClass`, `primaryAttr`, `secondaryAttr`, `page`. Three more appear only on
`AFFIX_GEM` payloads and are independently optional: in the live log 12
`AFFIX_GEM` payloads carry `affixGemTypes` 9 times, `affixGemLevels` 8 times and
`affixIds` 6 times. The `WEAPON` and `OTHER` payloads carry none of the three.

**This is the strongest corroboration in this document, and it is independent.**
`AFFIX_GEM` is a first-class item category in the client's own wire vocabulary.
The gem sections above concluded that gems are `Affix Gems` from a rendered
tooltip; the log says the same thing in a machine-readable field, from a
completely separate surface. Two evidence classes, one conclusion, and neither
derived from the other.

`primaryAttr` and `secondaryAttr` read `PRIMARY_ANY` and `SECONDARY_ANY` in all
18 live-log payloads and never anything else. That is a measured constant over 18
observations, not evidence that other values do not exist - the operator simply
never narrowed those filters.

### `itemType` and `itemSubType`, and an inference this document nearly shipped

Union across all three logs. TRANSCRIPTION:

| `itemType` | `itemSubType` values observed |
|---|---|
| `AFFIX_GEM` | 16 |
| `ARMOR` | 1, 2, 3, 4, 5, 6, 7 |
| `OTHER` | 0, 2, 7, 100, 200, 300 |
| `WEAPON` | 1, 3 |

**A false inference was caught here and is recorded rather than quietly
dropped.** In the live log alone the pairing is `AFFIX_GEM`/16 twelve times,
`WEAPON`/1 five times and `OTHER`/2 once - eighteen payloads, three types, a
perfect one-to-one match. That reads as "`itemSubType` is determined by
`itemType`". **It is false.** The 04.45 backup shows `ARMOR` taking seven
different subtypes and `OTHER` taking six. The live log contained exactly one
subtype per type by accident of what the operator browsed, and a clean pattern in
a small sample is not a rule.

What survives: `itemSubType` is a **per-`itemType` sub-taxonomy**, so the same
integer means different things under different types - `WEAPON` 1 and `ARMOR` 1
are not the same category. INFERENCE, but a weak and safe one: no observed
payload contradicts it.

**`ARMOR` runs 1 to 7 with no gaps, and the affix-icon count above independently
found SEVEN non-weapon equipment pieces** in a full loadout - helm, armor,
bracers, pants, boots, pendant, ring. The correspondence is striking and it is
**NOT a binding**. Whether accessories are filed under `ARMOR` or under `OTHER`
is unobserved, the direction of the numbering is unobserved, and no subtype
integer has been tied to a named slot. Recorded as suggestive and unresolved.

### The numeric affix id space

TRANSCRIPTION. Distinct `affixIds` values, union of all three logs:

| id | seen in |
|---|---|
| 201 | live log |
| 208 | live log |
| 211 | live log, 04.45 backup |
| 212 | 04.45 backup |
| 214 | 04.45 backup |

**Five ids, and the sample is tiny.** 41 payloads carry `affixIds` across all
three logs - 6 in the live log, 0 in the 01.27 backup and 35 in the 04.45
backup. `211` dominates: it occurs 37 times of the 41 payloads' ids, 33 of those
in the 04.45 backup, where it is the sole id in 31 arrays. `214` appears exactly
once in the entire corpus, inside `[212,211,214]`. Nothing here enumerates the id
space; it reports the five values that happen to have been searched for, by one
operator, in three sessions.

**No id is bound to a name.** Nothing in any of the three logs ties `201`, `208`,
`211`, `212` or `214` to `Ranged`, `Fervor` or any other affix word this document
reads off the UI. The two vocabularies - numeric on the wire, player-facing on
screen - do not meet anywhere in the corpus. **Every id here is UNBOUND, and
guessing a binding from the order the ids appear in would be exactly the
reasoning error this document withdrew twice.**

### `affixGemTypes` and `affixGemLevels` - and a naming discrepancy worth keeping

TRANSCRIPTION, live log: `"affixGemTypes":[4]` 9 times and
`"affixGemLevels":[2]` 8 times, no other value of either. The 04.45 backup has 2
`AFFIX_GEM` payloads and carries neither field.

Both are ARRAYS, and `affixIds` is an array that demonstrably holds more than one
id - `[208,211]`, `[212,211,214]`. INFERENCE, well supported by that parallel:
these are **lists of selected filter values**, so `[4]` reads as "gem type 4
selected" rather than "there are 4 gem types". Only one value of each has ever
been observed, so the type and level spaces are otherwise unmeasured.

**The wire calls this axis LEVEL. The UI was read as TIER.** The gem section
above records the browser offering a `Gem Tier` filter, and this document spends
a paragraph on tier and level being different quantities that an earlier version
conflated. The wire field is `affixGemLevels`. Either the client labels the same
filter `Tier` on screen and `Level` on the wire, or the on-screen filter was read
as `Tier` when it says something else. **This does not resolve the tier versus
level question - it sharpens it**, and it is now cheap to settle: open that
filter and read its label against a log line emitted at the same wall clock.

### `affixLvUp` is a MEASURED ZERO, not an unmeasured field

TRANSCRIPTION: `affixLvUp` appears 1,107 times in the live log and every single
occurrence reads `affixLvUp 0`. Not one non-zero value.

Recorded because this project keeps "unmeasured" and "measured zero" strictly
apart. This is the second kind: the field was emitted 1,107 times and held zero
every time. What it MEANS is unmeasured - whether it is a counter that never
incremented, a flag for an action the operator never took, or a field that is
always zero - and nothing here says which.

### Gameplay-ability names, and the rotation trap

TRANSCRIPTION. Union of `GA_Affix_*` class names across the three logs:

| name | live log | 01.27 backup | 04.45 backup |
|---|---|---|---|
| `GA_Affix_HitSwiftness_1_C` | absent | present | present |
| `GA_Affix_NoDamage_1_C` | present | absent | present |
| `GA_Affix_RangeEnhanced_1_C` | present | present | present |
| `GA_Affix_SwiftAttack_1_C` | present | present | present |

These are Unreal `GameplayAbility` Blueprint class names, so the game implements
at least four affixes as gameplay abilities. The `_1_C` suffix is Unreal's
generated-class decoration; reading the `1` as an affix LEVEL would be a guess
and is not made here.

**`RangeEnhanced` is not asserted to be `Ranged`.** It is the obvious candidate
and it is an INFERENCE with nothing behind it but a shared English root. This
document withdrew a claim built on exactly that much support.

**Two competing explanations for `HitSwiftness`, and this document does not
choose between them.** The name is present in both 2026-08-26 backups and absent
from the 2026-08-30 live log.

1. **Rotation and coverage.** A sweep of the live log alone reports three ability
   names and three affix ids where the three-log corpus holds four and five. On
   this reading the absence is simply a coverage gap.
2. **The patch.** The backups are client `1.0.14` and the live log is `1.0.15`.
   `HitSwiftness` may have been renamed or removed in that update, in which case
   it is not a coverage gap at all and carrying it forward as a current affix
   would be wrong.

**Nothing in the corpus separates these**, and the difference matters: one says
"read more logs", the other says "this name is stale". A single post-2026-08-26
observation of `HitSwiftness` settles it.

The coverage lesson survives either way and is worth stating alone: one log is
not the corpus.
`FINDINGS.md` 11.8 already records that the log is perishable and that one was
lost; this is the same hazard from the other end - the rotated logs are still
here and were simply not read.

**Method note for anyone extending this section.** Every count above came from
`grep -o ... | sort | uniq -c` against a named log, counting OCCURRENCES. An
early pass of this work used `grep -c`, which counts matching LINES, and reported
3,756 affix hits by adding two line counts together. The real figures for the
live log are **2,651 matching lines and 3,819 occurrences**. A line can match
twice and two patterns can match the same line, so line counts neither add nor
equal occurrence counts.

## The EQUIPMENT affix model, from the log - 2026-08-30

The trade filter above is what the client ASKS FOR. This is what the client is
TOLD it owns, and it is a different and richer surface.

### The affix object

TRANSCRIPTION. Every affix carried on an item is a three-key object inside the
item's `exEquip`:

    "exEquip":{"affixes":[{"cfgId":208,"level":1,"fixed":true}]}

**Both an escaped and an unescaped form occur**, because some payloads are
nested inside an outer JSON string. In the live log the unescaped form appears
31 times and the escaped form 17 times. A pattern written for one silently
misses the other, and this project's own first pass at this section did exactly
that and reported zero.

### `level` is always 1 and `fixed` is always `true`

TRANSCRIPTION, across all three logs: **68 affix objects, every one
`"level":1`, every one `"fixed":true`.** No other value of either field appears
anywhere in the corpus.

Two facts, and they must not be merged. `level:1` is a **measured constant over
68 observations** on one character's gear, not a statement that level 2 cannot
exist - the affix ladder read off the UI runs to Lv. 7, so higher levels
demonstrably exist somewhere. What is measured is that the ITEM-BORNE component
was 1 every time it was observed here.

### Item type determines the affix - the strongest structural result

TRANSCRIPTION. Grouping every `"cfgId":<6-7 digits> ... "exEquip":{"affixes":[...]}`
across all three logs:

| item cfgId | affix triple | logs it appears in |
|---|---|---|
| 1230304 | `(212, 1, true)` | BK1, BK2, LIVE |
| 1360303 | `(211, 1, true)` | BK2, LIVE |
| 1430301 | `(101, 1, true)` | BK1, BK2 |
| 1430303 | `(208, 1, true)` | BK2, LIVE |
| 1530303 | `(208, 1, true)` | BK2, LIVE |
| 3030403 | `(209, 1, true)` | BK1, BK2 |
| 3030404 | `(211, 1, true)` | BK1, BK2, LIVE |
| 3060404 | `(211, 1, true)` | BK2, LIVE |

Eight distinct affixed item cfgIds. **Not one of them ever carries a different
affix triple**, and **all eight** appear in two or more logs - across four days
and two sessions - with the identical triple.

**And those four days span the `1.0.14` to `1.0.15` client patch.** That makes
the stability finding stronger rather than weaker: six of the eight are observed
on both sides of a client update carrying the identical affix triple. A
per-instance random roll has no reason to survive a patch unchanged.

**INFERENCE, and it is the one this document most wants to be careful about:
the item-borne affix looks like a property of the item TYPE rather than a
per-instance random roll.** Three independent things point the same way - the
strict one-to-one item-to-affix mapping, its stability across four days, and the
field being literally named `fixed` and being `true` on all 68 observations.

**This is the first-party evidence for what DevNote #6 and Dev Team FAQ #2 said**
and what `docs/CLASSES.md` C14 had to correct itself about. Those notes say gems
replaced random affix ROLLS. Here is an item-borne affix flagged `fixed`, stable
across sessions, with no roll in sight - and a separate gem system delivering the
variable part. The dev notes were describing this, accurately.

**Where it could still be wrong.** Eight item types from ONE character's
inventory is a small sample, every observed item is a distinct type so nothing
here compares two instances of the SAME type, and a roll that happens to be
sticky per item id would look identical. Two instances of one item type, side by
side, would settle it and no capture has them.

### Affixes and gems coexist - proven a second time, from the log

TRANSCRIPTION. Seven `exEquip` objects in the live log carry both arrays at
once. The same item - affix `211` - appears in FOUR different socket states:

    "exEquip":{"affixes":[{"cfgId":211,"level":1,"fixed":true}],"gem":[{},{}]}
    "exEquip":{"affixes":[{"cfgId":211,...}],"gem":[{},{"cfgId":223106}]}
    "exEquip":{"affixes":[{"cfgId":211,...}],"gem":[{"cfgId":224210},{"cfgId":223106}]}
    "exEquip":{"affixes":[{"cfgId":211,...}],"gem":[{"cfgId":224210},{"cfgId":221109}]}

**The item's own affix is identical in all four while the sockets go from empty
to one gem to two, and the gems themselves change.** That is a stronger
statement than coexistence: the item-borne affix is INDEPENDENT of what is
socketed, observed directly rather than argued.

The tooltip sections above concluded coexistence from PIXELS - `Ranged` above
the sockets with no gem icon, `Fervor` in a filled socket. **The log states the
same structure in a machine-readable field, from a completely independent
surface.** That is corroboration in the strict sense this repository uses it:
two evidence classes, neither derived from the other.

Two further facts fall out. This item has **exactly two sockets**, because the
`gem` array is length 2 in every one of the four states. And an EMPTY socket is
the empty object `{}` while an absent socket is simply not in the array, so a
parser must not treat a missing entry and an empty entry as the same state.

### The complete numeric affix namespace observed so far

TRANSCRIPTION. Union of both surfaces across all three logs:

| id | trade filter `affixIds` | equipment `affixes[].cfgId` |
|---|---|---|
| 101 | - | BK1, BK2 |
| 201 | LIVE | - |
| 208 | LIVE | BK2, LIVE |
| 209 | - | BK1, BK2 |
| 211 | LIVE, BK2 | BK1, BK2, LIVE |
| 212 | BK2 | BK1, BK2, LIVE |
| 214 | BK2 | - |

**Seven ids.** The two surfaces overlap on 208, 211 and 212 but neither
contains the other, so **either surface read alone undercounts the namespace**.
Nothing here says the space is contiguous, bounded, or that 101 and the 2xx
block are the same table.

**`cfgId` is a per-table key, not a global id.** The same field name carries
item ids of six and seven digits, affix ids of three, and gem ids in a 22xxxx
family. The namespace is determined by the KEY PATH the value sits at, never by
the value. A lookup that takes the bare integer without its path will return the
wrong row, and `docs/OBSERVED_IDS.md` records the path with each id for exactly
this reason.

## The Auction House is an affix CATALOGUE - read 2026-08-30

This document said, correctly, that `f1290` is "one loadout's affix summary, NOT
a catalogue of every affix in the game", and that no frame gathered so far
enumerated the affix set. **A frame in the same capture does enumerate one.**

The Auction House `Purchase` screen carries an `Affix Effects` dropdown that
lists affixes with their icons. Read off frames `f1797_01.09.19` (list scrolled
to the top) and `f1810_01.09.34` / `f1813_01.09.38` / `f1814_01.09.39` (scrolled
down one row), which together cover every row.

### The 16 entries, in the order the game lists them

TRANSCRIPTION, two columns, read left then right per row:

| # | left column | right column |
|---|---|---|
| 1 | `Brotherhood` | `Spirit Shield` |
| 2 | `Unyielding` | `Distant Ward` |
| 3 | `Resilience` | `Valor` |
| 4 | `Wrath` | `Skypiercing` |
| 5 | `Fervid` | `Seeker` |
| 6 | `Ranged` | `Fervor` |
| 7 | `Smiting` | `Burst` |
| 8 | `Strife` | `Eloquence` |

Eight rows, sixteen entries. The scroll range is exactly one row - `f1797` shows
row 1 flush at the top and `f1810` shows row 8 flush against the `Reset` and
`Confirm` buttons - so nothing is hidden above or below.

### It is a catalogue, but NOT the game's whole affix set

**This is the caveat that keeps the table honest, and it is not a small one.**
The `PREPARE` -> `Affixes` panel at `f1290`, transcribed earlier in this
document, lists nine affixes. Only **six** of them appear in the sixteen:
`Fervid`, `Ranged`, `Skypiercing`, `Smiting`, `Valor`, `Wrath`. The other
three - **`Focused`, `Elusive` and `Curse`** - are absent from the Auction House
list entirely, while demonstrably existing on the character.

So neither list is complete, and **an affix missing from this table is not
evidence that it does not exist.** This document has already withdrawn one
argument from absence built on a partial panel; the same error is available here
and is refused in advance.

**INFERENCE, untested, and the obvious explanation:** the `Gem Type` filter had
type 4 (the green `Peridot`) selected in every frame cited above, so this list is
plausibly scoped to affixes obtainable on THAT gem type rather than being a
global catalogue. **One cheap capture settles it** - change the `Gem Type`
selection and re-read the dropdown. If the sixteen change, the list is
type-scoped; if they do not, the three missing names are missing for some other
reason.

### The affix vocabulary now known, from all sources

Union of the Auction House catalogue, the `f1290` loadout panel, and the affixes
named inside gem tooltips: **22 distinct affix names.**

`Brotherhood`, `Burst`, `Curse`, `Distant Ward`, `Eloquence`, `Elusive`,
`Fervid`, `Fervor`, `Focused`, `Ranged`, `Resilience`, `Seamless`, `Seeker`,
`Skypiercing`, `Smiting`, `Spirit Shield`, `Strife`, `Unyielding`, `Valor`,
`Vitality`, `Wealth`, `Wrath`.

Ten of these were unknown to this document before 2026-08-30, and none of them
appears anywhere in the launch-window wiki cluster's affix lists.

## `Gem Tier` on screen is `affixGemLevels` on the wire - the naming question resolved

The log section above flagged a discrepancy: the wire field is `affixGemLevels`
while this document had recorded the browser offering a `Gem Tier` filter, and
this document also spends a paragraph on tier and level being distinct
quantities that an earlier version wrongly conflated.

**Resolved by reading the frame the request came from.** In `f1811_01.09.36` the
filter row is labelled **`Gem Tier`** on screen and offers exactly two icons,
with the second selected - and the request emitted at that same wall clock
carries `"affixGemLevels":[2]`.

**So the client itself uses both words for one filter: `Tier` in the UI, `Level`
on the wire.** That does NOT license treating tier and level as one quantity
elsewhere. The inlay rule quoted earlier says LEVEL twice and is about a gem
against a socket; this is a search filter with two options. What it does mean is
that **an inconsistency in the game's own vocabulary caused part of the earlier
confusion** - the conflation was not purely a reading error, the client speaks
both ways.

The `Gem Type` row resolves the same way: four icons on screen, and the request
carries `"affixGemTypes":[4]` with the fourth icon selected. That confirms the
log section's inference that these arrays are **lists of selected filter values**
rather than counts.

## Single-affix gems exist - a claim above is corrected

This document says of the Auction House listing rows that "every one shows two
small icons, which is consistent with two-affix gems being the norm", and
carefully declined to generalise from a partially occluded view. **The
unoccluded view is in this capture, and two-affix gems are not the norm.**

`f1789_01.09.10` shows the gem listing with no tooltip covering it, sorted by
price ascending. The cheapest eight rows carry **one** affix icon each:

| gem | price |
|---|---|
| `Deft Peridot` | 46 |
| `Farguard Peridot` | 56 |
| `Fortune Peridot` | 57 |
| `Blessed Peridot` | 59 |
| `Crushing Peridot` | 84 |
| `Brawling Peridot` | 87 |
| `Tenacious Peridot` | 90 |
| `Flawless Peridot` | 100 |

Every row from 115 upward carries **two** icons - `Blessing Fortune Peridot`,
`Ranged Ward - Crush Peridot`, `Ranged Ward - Vitality Peridot` and so on.

**Two things follow, one measured and one inferred.** MEASURED: single-affix
gems exist, so "two-affix gems being the norm" is withdrawn - the earlier view
was occluded and price-sorted such that only the expensive end was legible.
INFERENCE, strong but not proven: affix count tracks gem TIER, since the
one-icon gems render in a plain frame and carry one-word names while the
two-icon gems render in an ornate gold frame with two-part names, and the gem
tooltip earlier in this document describes a `Tier 2 Affix Gem` granting exactly
two affixes. No frame here states the tier of a one-icon gem, so the binding
"Tier 1 grants one affix" is NOT claimed.

Note also the price structure, recorded without interpretation: one-affix gems
span 46 to 100 and two-affix gems start at 115. Whether that is a floor, a
coincidence of this snapshot, or a consequence of the affixes involved is
unmeasured.

## `Distant Ward` - a second full affix reading, and the game publishes COOLDOWNS

Read from the gem tooltip in `f1793_01.09.14`, on `Ranged Ward - Vitality
Peridot`, described by the game as a `Tier 2 Affix Gem`. Quoted:

> **`Distant Ward` Lv.1.** If the distance between you and the attacker is
> greater than 5 meters when hit, temporarily increases your Physical Resistance
> and Magic Resistance. Upon reaching a certain level, you also resist minor
> impacts from distances greater than 5 meters; once triggered, this effect has
> a cooldown of 10s.
>
> **`Vitality` Lv.1.** Increases Maximum Energy. Upon reaching a certain level,
> when entering a state of Energy Overdraft, you become immune to that specific
> instance of Energy Overdraft. Cooldown: 60s.

**`Distant Ward` is the defensive mirror of `Ranged`.** Same 5 meter distance
gate, same "temporarily increases", same "upon reaching a certain level"
escalation clause - Resistance where `Ranged` gives Damage. Affixes are built
from a shared template, which is a structural fact worth more than either
reading alone.

**THE GAME PUBLISHES COOLDOWNS IN SECONDS.** `10s` and `60s`, first-party, in a
tooltip. `CLAUDE.md` and `docs/CLASSES.md` both state that no cooldowns are
published for this game and that any site quoting a second value is fabricating
one. **That remains true for CLASS ABILITY cooldowns** - nothing here touches
those - **but it is now false as a blanket statement.** Affix cooldowns are
published, exactly, in the client. The measurement doctrine is unchanged: these
are still statements of intent to be checked against behaviour, not measurements.

Two new game nouns, recorded unbound: `Energy Overdraft`, a state a character can
enter; and `Maximum Energy`, the quantity `Vitality` increases. `Energy` is also
what `docs/CLASSES.md` reports `Elusive` reducing the dodge cost of, so the three
plausibly name one resource - not asserted here.

**The gem name synonym rule gains a case, and a wrinkle.** `Ranged Ward -
Vitality Peridot` grants `Distant Ward` and `Vitality`. So the first name-part
`Ranged Ward` maps to the affix `Distant Ward` by synonym in word order, exactly
as this document records - but the second part, `Vitality`, is the affix name
EXACTLY. **A gem name part can be a synonym or an identity**, which makes
name-parsing worse than the earlier advice implied, not better: a parser cannot
even tell from the shape whether it is looking at a synonym or a literal.

## What to capture next, in priority order

Each is one hover in a menu and yields a whole ladder, so the ratio of effort to
recorded fact is better than any measurement this project runs.

1. **`Fervor`** - the other affix on this weapon, and the one arriving via a
   gem. Its ladder plus its gem tier settles part of the affix-versus-gem
   question above.
2. **A gem slotting screen** - socket tiers, what a Peridot is, and whether tier
   gates level.
3. **The remaining named affixes** `CLASSES.md` lists from guide consensus -
   `Focused`, `Elusive`, `Fervid`, `Curse`, `Valor`. Each one found in-game
   converts a T4 guide claim into a first-party fact, or refutes it.
4. **The `Focus Fire` talent tooltip** - item 10 turns on its exact scope, and
   the talent screen states it. The log records the loadout as ids
   (`TS.Ability: talent data response`), so a tooltip reading binds an id to a
   name the way `docs/OBSERVED_IDS.md` requires.
