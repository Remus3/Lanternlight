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

**INFERENCE, WITHDRAWN 2026-08-30d - see the tooltip section below.** It read:
the item-borne affix looks like a property of the item TYPE rather than a
per-instance random roll, on three independent grounds - the strict one-to-one
item-to-affix mapping, its stability across four days, and the field being
literally named `fixed` and `true` on all 68 observations.

**Two instances of one item name were later found carrying DIFFERENT affixes**,
which is exactly the test the paragraph below this one named as missing. The
MEASUREMENTS in this section all stand; only the inference drawn from them is
withdrawn. One character owning one instance of each type produces this pattern
whether the affix is fixed or rolled, so the log cannot discriminate.

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

Union of the Auction House catalogue, the `f1290` loadout panel, the affixes
named inside gem tooltips, and one read off a weapon tooltip later the same day:
**23 distinct affix names.**

`Blessing`, `Brotherhood`, `Burst`, `Curse`, `Distant Ward`, `Eloquence`,
`Elusive`, `Fervid`, `Fervor`, `Focused`, `Ranged`, `Resilience`, `Seamless`,
`Seeker`, `Skypiercing`, `Smiting`, `Spirit Shield`, `Strife`, `Unyielding`,
`Valor`, `Vitality`, `Wealth`, `Wrath`.

**The count was 22 for part of 2026-08-30 and is corrected here rather than
overwritten silently.** `Blessing` was read off a `Fang-Piercer Dagger` in the
tooltip pass below, after this section was written.

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

## THREE AFFIX IDS ARE BOUND TO NAMES - 2026-08-30

**This is the first time this project has bound a numeric affix id to the name
the game shows a player.** It needed no new capture: the log and the frames were
both already on disk, joined on wall clock.

    201 = Valor        208 = Fervid        211 = Ranged

### Why a join was needed at all

**The logs contain no affix names.** Every name in the Auction House catalogue
above was searched for, case-sensitively, in all three logs: `Brotherhood`,
`Burst`, `Distant Ward`, `Eloquence`, `Fervid`, `Fervor`, `Resilience`,
`Seeker`, `Skypiercing`, `Smiting`, `Spirit Shield`, `Strife`, `Unyielding`,
`Valor`, `Wrath` - **zero occurrences each**. `Ranged` returns 4 hits and all
four are the UI module `RangedAttackIndicator`, nothing to do with the affix.

So the numeric namespace and the player-facing namespace never meet in text, and
no amount of further log reading will bind them. The wall-clock join - log in
UTC, capture filenames in local time, UTC-5 here - is the only sanctioned route,
and it is the same method that bound the class ids in 2026-08-09.

### The mechanism

The client emits `TS.Default: [TradeCtrl] request Trade Goods {...}` when the
Auction House filter changes. 18 such requests exist in the live log and 6 carry
`affixIds`. They form a clean progressive narrowing, each adding one filter:

| UTC | filter added |
|---|---|
| 06.04.16 | `itemType: AFFIX_GEM` |
| 06.09.04 | `affixGemTypes:[4]` |
| 06.09.10 | `affixGemLevels:[2]` |
| 06.09.22 | `affixIds:[208,211]` |
| 06.09.25 | `affixIds:[211]` |
| 06.09.36 | `affixIds:[208]` |
| 06.09.40 | `affixIds:[201]` |

**Two rendered channels report the applied filter**, and both were used:

1. **The `Affix Effects` header** renders the icon of each applied affix. Icon
   count equals array length in every observed case, including zero.
2. **The dropdown rows** show selection as an amber fill PLUS a checkmark. A
   white outline with no fill is HOVER, not selection - `f1816_01.09.42`
   separates them in one frame, with `Valor` amber-and-checked while `Wrath`
   carries only the outline.

### `201 = Valor`

`f1816_01.09.42`, two seconds after the `[201]` request. **Two independent
channels agree inside a single frame:** the `Affix Effects` header carries one
icon, a maroon tile with a diagonal sword, and `Valor` is the sole amber-filled
checked row - carrying that same maroon diagonal sword as its row glyph.

**Caveat, and it is required.** Glyph shape alone does NOT identify `Valor` - the
diagonal-sword form is shared with other entries, and an icon-only argument
would be a three-way tie broken by the maroon tile colour. This binding does not
rest on the glyph: it rests on the CHECKED ROW, read from its text label, with
the header icon as corroboration.

### `211 = Ranged`

`f1932_01.11.56`, with `[211]` applied and the dropdown closed. The header
carries one icon, a maroon feather. **All eleven result cards carry that same
maroon feather as one of their badges.** The `Ranged` row's glyph in the open
dropdown is the same maroon feather.

**A tempting and WRONG argument is recorded here so nobody re-derives it.** The
results under `[211]` are almost all named `Ranged something Peridot`, and
reading that as proof is invalid twice over. `Tenacious - Ranged Peridot` does
not begin with the word. More seriously, **gem names map to affixes by SYNONYM**
- this document establishes that `Ranged Ward` is the gem-name form of the affix
`Distant Ward`, not of `Ranged`. `Ranged Ward - Ranged Peridot` proves it on
screen: it carries a BLUE defensive badge and a separate maroon feather. A
`Ranged`-prefixed name does not imply the `Ranged` affix. The binding rests on
the badge and header ICON, never on the name.

### `208 = Fervid`

By set difference, with no appeal to array ordering.

- `f1799_01.09.21`: `Fervid` is the sole amber-filled checked row; `Ranged`
  carries only a white hover outline.
- The next request, 06.09.22, is `affixIds:[208,211]` - so between those two
  instants `Ranged` was also ticked, and the checked SET became
  `{Fervid, Ranged}` = `{208, 211}`.
- `211 = Ranged` is established independently above.
- Therefore `208 = Fervid`.

`208` also appears as a **singleton** request at 06.09.36, so the pair is not
load-bearing either way.

**An earlier version of this reasoning said "array order is selection order".
That is withdrawn as unsupported.** `Fervid` sits directly above `Ranged` in the
left column, so display order and selection order predict `[208,211]`
identically and the array cannot distinguish them. The backup log's
`[212,211,214]` shows only that the array is not sorted ascending. The set
argument above needs none of it.

### What is NOT bound

Four of the seven known numeric affix ids remain unbound: **101, 209, 212,
214**. Nothing here guesses them.

**`GA_Affix_RangeEnhanced_1_C` is still NOT bound to `211`**, even though `211`
is now known to be `Ranged`. The gameplay-ability class names and the numeric
ids never co-occur on any line in any log, so the pairing would rest on a shared
English root and nothing else - which is the precise shape of the reasoning this
document has already withdrawn twice.

### The recipe, for the remaining ids

Recorded so a future session does not re-derive the method. Capture at 1 Hz.
Auction House -> `Purchase` -> `Affix Gem` -> `Affix Effects`. Tick exactly ONE
box, apply, pause, then untick and repeat. **One affix per cycle** - a pair
yields a set, not an assignment, and only decomposes if one member is already
known. Read the binding off the ROW LABEL, never off the icon: several glyphs
are confusable at capture resolution, and `Wrath` and `Fervid` in particular
render similarly.

### A disagreement left open

An independent refutation pass on these three bindings confirmed all three
conclusions while correctly refuting two of the arguments originally offered -
both rewritten above. That pass also reported the dropdown holding **22 affixes
across 11 rows** and referred to a row named `Ethereal`.

**Neither could be reproduced.** `f1797_01.09.19` shows row 1 flush against the
top of the panel and `f1810_01.09.34` shows row 8 flush against the `Reset` and
`Confirm` buttons, which bounds the list at 8 rows and 16 entries, and no frame
examined here contains the name `Ethereal`. The count of 16 is what this
document states, with the two bounding frames named so it is checkable. The
disagreement is recorded rather than silently resolved in the count's favour.

## Binding the remaining four - `101`, `209`, `212`, `214`

**Result: none of the four can be bound from data now on disk, and that is a
measured null rather than a failure to look.** Each has a specific, named
reason, recorded per id so nobody re-runs this search. What the pass DID
produce is a second binding method, validated against a known answer, and a
capture recipe that is precise about which method reaches which id.

### The two routes are COMPLEMENTARY, which is the structural finding

An affix id can be reached two ways, and the two sets do not coincide:

| route | what it needs | ids it can reach |
|---|---|---|
| **Trade filter** | an `affixIds` request joined to a frame of the Auction House dropdown | 201, 208, 211, 212, 214 |
| **Item tooltip** | an item carrying the affix, its tooltip opened, joined to a frame | 101, 208, 209, 211, 212 |

- **Filter-only:** `201`, `214` - never observed on any item.
- **Item-only:** `101`, `209` - never observed in any trade filter.
- **Both:** `208`, `211`, `212`.

So the tooltip route is not a fallback, it is the ONLY route to `101` and `209`.
All three ids bound so far were bound through the filter, which is why this was
not visible until now.

### The tooltip route, VALIDATED on a known answer

The client logs a tooltip-open event carrying the item's `cfgId` - `TS.UI:`
followed by a localised label and `cfgid == <id>`. Note the label contains
non-ASCII characters, so match on `cfgid ==` and not on the words around it, and
note the **space after `==`**, which defeated the first pattern tried here.

**Validated, rather than assumed, on a control with a known answer.** The log
records item `3060404` carrying affix `cfgId 211`, with tooltip-open events
through `2026.08.30-05.45.05` UTC (00:45:05 local). Frame `f0636_00.45.07` shows that item's
tooltip - `Deathclaw Hunter`, `Legendary Bow and Arrow` - and its affix reads
**`Ranged` Lv.1**. Independently, `211 = Ranged` was established through the
trade filter. **Two unrelated methods, one answer.**

**The reading rule, now proven rather than assumed.** The same tooltip shows
`Ranged` with no gem icon above the sockets and `Fervor` with a gem icon beside
it. The log's `affixes[].cfgId` for this item is `211` alone. So the item's OWN
affix is the one WITHOUT a gem icon, and gem-granted affixes do not appear in
`affixes[]`. Read only the gem-less row.

### Why each of the four failed - CORRECTED 2026-08-30 after a refutation pass

**The conclusion below survived the refutation. The evidence originally
published for it did not, and three statements in it were false.** They are
replaced here rather than quietly edited, because a false first-party statement
in a public repo is the exact failure this document has now withdrawn three
times.

**WHAT WAS WRONG, and the mistake underneath it.** The first version of this
section said "Only ONE capture on this machine is full-screen". That is FALSE:
there are **eight** full-scene capture sets **within `C:/ll-captures`**, three of
them at 2560x1440 - plus a NINTH outside that tree at `~/.lanternlight/frames`,
which a walk of `C:/ll-captures` cannot see. It also
listed five capture windows when there are **fourteen** capture directories, and
it blamed the `101` and `209` failure on the capture being a 500x310 crop - when
a 1280x720 FULL-SCENE capture covered both timestamps.

The cause of all three errors was one line of code: the inventory loop tested
only the subdirectory names `frames`, `panel` and `panel2`, which happened to be
the ones already known. **It was an empty grep - a claim about my directory
list, not about the disk** - and this repository's anti-patterns list names that
exact error.

**The complete capture inventory, walked rather than assumed:**

| directory | files | frame size | window (local) |
|---|---|---|---|
| `2026-08-25/panel` | 6439 | 500x310 | 18:51:31 - 19:51:31 |
| `2026-08-25/panel2` | 4692 | 500x310 | 19:51:31 - 20:34:50 |
| `2026-08-25/scene` | 2221 | **1280x720** | 19:32:34 - 20:12:34 |
| `2026-08-25/scene_early` | 25 | **1280x720** | 18:40:30 - 18:55:14 |
| `2026-08-25/sheets` | 67 | 1120x1484 | (no timestamps) |
| `2026-08-25b/panel` | 948 | 540x360 | 23:08:11 - 23:17:18 |
| `2026-08-25b/panel2` | 893 | 540x360 | 23:27:02 - 23:35:29 |
| `2026-08-25b/reanchor` | 24 | **2560x1440** | 22:53:29 - 22:55:17 |
| `2026-08-25b/reanchor_small/panel` | 320 | 540x360 | 22:53:14 - 22:57:43 |
| `2026-08-25b/reanchor_small/wide` | 320 | **1280x720** | 22:53:14 - 22:57:43 |
| `2026-08-25b/talents` | 164 | **2560x1440** | 22:23:53 - 22:29:52 |
| `2026-08-25b/wide` | 238 | **1280x720** | 23:08:11 - 23:17:18 |
| `2026-08-25b/wide2` | 224 | **1280x720** | 23:27:02 - 23:35:29 |
| `2026-08-30/frames` | 2172 | **2560x1440** | 00:30:12 - 01:17:06 |

**Re-run against that complete inventory**, the sweep finds **36** tooltip-route
events on items carrying a target affix, of which **four** fall inside a
full-scene capture. All four were opened and read:

| affix | item | local time | capture | what the frame shows |
|---|---|---|---|---|
| 209 | 3030403 | 19:54:03 | `25/scene` 1280x720 | Warehouse open, **no tooltip rendered** |
| 101 | 1430301 | 19:54:35 | `25/scene` 1280x720 | Warehouse, a slot highlighted, **no tooltip** |
| 212 | 1230304 | 22:26:34 | `25b/talents` 2560x1440 | a tooltip IS up - but for `Rover Hood`, a **different item** |
| 209 | 3030403 | 22:26:40 | `25b/talents` 2560x1440 | a context menu and an inventory-full toast, **no tooltip** |

**So the conclusion holds and the reason is different from the one published.**
`101` and `209` are not lost to a cropped capture - at the four tooltip-EVENT
timestamps above, no usable tooltip was on screen.

**THE GENERALISATION OF THAT SENTENCE IS REFUTED, 2026-09-01, and `209` IS NOW
BOUND.** The sentence used to end "at any instant a full-scene capture was
running", and that is false. A usable tooltip for item `3030403` is on screen in
frame `s01223_19.54.36` - **one second after** the 19:54:35 event this table
checked, and 33 seconds after the 19:54:03 event for that same item. The narrow
claim about the four event timestamps survives; the sweep's conclusion about all
instants does not.

**Why the sweep could not have found it by looking harder.** It selected frames
at the timestamps of `cfgid ==` log events. A tooltip is rendered when the
player HOVERS, and the log line fires on its own schedule, so frame-selection by
event time looks in the wrong second. The fix is not a wider window - it is a
different join key, and durability is one. See `209 = Seeker` below.

**`212` and `214` fail for the originally stated reason, which does survive.**
Their four trade-filter requests land at 22:43:54 to 22:44:11 local, between the
`talents` capture (ends 22:29:52) and `reanchor` (starts 22:53:14). That gap is
real against the complete inventory, not just against the partial one.

### A METHOD CAVEAT that the refutation exposed, and it weakens the tooltip route

**The logged `cfgid` and the tooltip actually drawn are NOT reliably the same
item.** At 22:26:34 the log names cfgId `1230304` - a `12xxxxx` cloth-family
item - while the frame at that second renders a tooltip for `Rover Hood`, a
`Rare Head`. The event marks an item the UI touched; it does not promise that
item's tooltip is on screen.

**So a frame at the right second is not sufficient.** A binding needs the
tooltip in the frame to independently identify the item - its name and type must
match the cfgId's known family - before its affix row can be attributed.

The control still passes that stricter test, which is why the three existing
bindings are unaffected: cfgId `3060404` is a `30xxxxx` weapon, and `f0636`
renders `Deathclaw Hunter`, `Legendary Bow and Arrow`. Family and identity both
match. But the rule has to be stated, because reading any frame at any matching
timestamp would have produced a false binding here.

### The recipe, per id

Capture **full-screen** at 1 Hz or better - a cropped poller cannot show a
tooltip at all. But full-screen is necessary and NOT sufficient, which is the
lesson of `101` and `209`: a 1280x720 full-scene capture covered both their
timestamps and neither frame had a usable tooltip on screen. **The operator has
to actually open the tooltip and leave it up for a beat**, and the frame must
show a tooltip whose item identity matches the cfgId's family - see the method
caveat above.

**`212` is the cheapest and needs no shopping.** Item `1230304` is still in the
live log still carrying affix `212`, so the operator still holds it. Open that
item's tooltip with a full-screen capture running and read the gem-less affix
row. Alternatively use the filter route - `212` is filterable, since it has been
requested four times.

**`214` needs the Auction House.** Its only route is the filter: tick it alone
in `Affix Effects`, apply, and read the checked ROW LABEL against the request
emitted at that wall clock. One affix per cycle - a pair yields a set, not an
assignment.

**`101` and `209` need an item that carries them, and the operator may no longer
have one.** Items `1430301` and `3030403` appear in both rotated logs and are
**absent from the 2026-08-30 log entirely**, so they are likely sold or
otherwise gone. Either re-acquire an item carrying the affix, or try the filter
route - but note that `101` and `209` have never appeared in any filter request,
so **it is unknown whether they are filterable at all.** The `Affix Effects`
list is 16 entries under one gem type and is demonstrably not the whole affix
set, so an affix that only ever appears on items may have no filter row. That is
a question this recipe cannot answer in advance.

**Read the ROW LABEL, never the icon**, on either route. Several glyphs are
confusable at capture resolution and `Wrath` and `Fervid` in particular render
similarly.

### What was NOT done

No arithmetic was attempted on the id space. `Valor`, `Fervid` and `Ranged` sit
at catalogue positions 6, 9 and 11 with ids 201, 208 and 211, and those gaps fit
no simple rule in either row-major or column-major order. Guessing a fourth id
from three points would be exactly the reasoning this document has already
withdrawn twice.

## The `Affix Details` panel STATES the aggregation rule - 2026-08-25, read 2026-08-30

Read from frame `f0119_22.28.15` in `C:\ll-captures\2026-08-25b\talents\`, a
2560x1440 capture that **no session had ever opened**. It was found by walking
the capture tree rather than by looking where the frames were expected to be -
the same omission that produced the false "only one capture is full-screen"
claim withdrawn in `LL-0088`.

The game has a screen called **`Affix Details`**. It renders a `Type` header of
**nine equipment-slot icons** and, under a heading `Active`, one row per affix
carrying that affix's level and a per-slot count.

**Transcribed, with the counts exactly as rendered:**

| affix | level | slots carrying a count | row sums to |
|---|---|---|---|
| `Fervid` | Lv.2 | two adjacent slots in the lower-body group | 2 |
| `Fervor` | Lv.2 | two adjacent slots in the upper-body group | 2 |
| `Seeker` | Lv.1 | the leftmost slot, the weapon column | 1 |
| `Wealth` | Lv.1 | one slot in the accessory group | 1 |

**Every affix's stated level equals the sum of its own row.** 1+1=2, 1+1=2,
1=1, 1=1. Four independent matches on one screen.

### Why this matters more than another reading

`docs/AFFIXES.md` derived "one icon is one level, summed across equipped gear"
by COUNTING ICONS across a loadout on frame `f1290`, captured 2026-08-30. That
derivation replaced a withdrawn claim which had read the same row as an
eligibility table.

**This frame states the rule directly, in a table, from a different capture
session four days earlier and on a different loadout.** It is not the same
evidence re-examined - it is an independent surface, and the icon-counting
derivation predicted exactly what it shows.

It also settles the withdrawn claim's replacement beyond argument: a row here is
plainly a per-character BREAKDOWN, because the counts sum to the level the same
screen reports. Nothing about it reads as a permission list.

### Two affixes confirmed on a real loadout for the first time

`Seeker` had been seen only in the Auction House catalogue, and `Wealth` only
inside a gem tooltip. Both appear here as `Active` affixes on the operator's own
gear, which is a stronger class of observation than either.

### The slot count agrees with the log

The `Type` header carries NINE slot icons. `docs/OBSERVED_IDS.md` binds nine
equipment slots from the log alone - 0 through 6 plus 10 and 11 - by joining
`generateBotPlayerStateData` against equipment payloads on item cfgId. Two
unrelated surfaces, one number.

**The per-slot attributions above are deliberately described by GROUP rather
than named.** Several of the nine header glyphs are small and two pairs are
confusable at this resolution, and this document has already withdrawn one
claim that rested on reading an icon instead of a label. The SUM rule needs no
icon identification and is stated without hedging; the individual slot
assignments would need a frame where the header is legible or a hover that
labels a column.

### What this does NOT establish

The panel shows one character's active affixes, so it is not a catalogue - the
same caveat this document applies to `f1290` and to the Auction House list. No
level above 2 appears here, so nothing about the upper end of the ladder is
observed on this screen.


## The TALENTS screen at level 5 - 2026-08-25, from an unread capture

Read from `f0000_22.23.53` in `C:\ll-captures\2026-08-25b\talents\`, 164 frames
at 2560x1440 that no session had opened before 2026-08-30.

### The screen has TWO pages - RECORDED SINCE 2026-08-09, and this section claimed otherwise

**WITHDRAWN. The heading here read "which was not recorded anywhere" and the body
said "every prior reading of it covered page one only" and that page two was
uncaptured. All of that is FALSE**, and it is the rediscovery failure this
project's whole continuity design exists to prevent.

`docs/OBSERVED_IDS.md` has carried a talent-cluster table with an explicit
**`Page` column** since **2026-08-09** - commit `bfda016` - listing all six
page-two clusters with their unlock levels, and a further table of the NODE
NAMES inside them. `Mighty Archer`, which this document also called unrecorded,
is in that same table.

The frame `f0160_22.29.45` in this very capture shows page two, and every
cluster and gate on it matches that table exactly: `Hunter's Arrow
Enhancement 1` (Lv. 6), `Bomb Engineering` (Lv. 9), `Predator's Stealth`
(Lv. 10), `Woodling Expert` (Lv. 10), `Hunter's Arrow Enhancement 2` (Lv. 12),
`Way of Gylden Hunt` (Lv. 12).

**What this frame actually contributes is corroboration, not discovery** - a
three-week-old table re-measured on a later capture and found correct. That is
worth having and it is a much smaller claim.

**How it happened, recorded because the mechanism is the useful part.** The
author read the TALENTS screen, saw two page dots, and wrote "not recorded
anywhere" without opening `docs/OBSERVED_IDS.md` - the file this same lane owns
and had read the section headings of earlier in the same session. An absence was
asserted from memory rather than checked, which is the third instance of that
exact failure in one day.

### Six clusters on page one, with their gates

TRANSCRIPTION:

| cluster | state |
|---|---|
| `Swift Shot` | locked - `Unlocks at Lv. 8.` |
| `Nimble Evade` | locked - `Unlocks at Lv. 7.` |
| `Battle Hardened` | unlocked, nodes lit |
| `Archer's Arrow Enhancement 1` | unlocked |
| `Mighty Archer` | unlocked |
| one lower-centre cluster | name occluded by the open tooltip |

`Swift Shot` at Lv. 8 and `Nimble Evade` at Lv. 7 match what
`docs/AFFIXES.md` records from the 2026-08-30 `TALENTS` frame, four days later
and one level higher. Two captures, same gates.

`Mighty Archer` was ALREADY RECORDED - `docs/OBSERVED_IDS.md` has it with a
Lv. 5 gate. An earlier version of this line called it new; that is withdrawn.

### A talent tooltip, quoted

The frame has a node tooltip open. Verbatim:

> **`Unstoppable Edge`**, frame `f0000_22.23.53`. `Sky Piercer`'s `Physical Damage` is partially
> converted to `True Damage`.

The tooltip offers an `Activate` action, and the character has **1 Talent
Point** unspent at Level 5.

**Three game nouns bound for the first time by this reading:**
`Unstoppable Edge` a talent node, `Sky Piercer` a skill it modifies, and
`True Damage` a damage type distinct from `Physical Damage`.

**`True Damage` is the one worth flagging to Emberforge.** A damage type that
`Physical Damage` can be "partially converted" into is a mechanic the engine
has no representation for, and the conversion FRACTION is not stated - the
tooltip says "partially" and gives no number. Recorded as a named mechanic with
an unmeasured coefficient, which is the state this project keeps distinct from
a measured zero.

### The numeric talent ids remain UNBOUND

The log carries `TS.Ability: talent data response: [30008,30009]` on 2026-08-25
and `[32000,30008,30009]` on 2026-08-30, plus three gameplay tags -
`Talent.Scout.Bow.ContinuouseShoot` (the game's spelling),
`Talent.Scout.Bow.DrawEnhanced` and `Talent.Scout.Bow.HomingTarget`.

**None of the three tags is bound to any of the three ids, and no id is bound to
any name on this screen.** The 2026-08-25 response falls inside the `25/scene`
capture, so a join is available in principle - but a two-element array yields a
SET, not an assignment, exactly as with the affix ids, and the allocated set at
that moment is not otherwise known. Pairing `HomingTarget` with a node called
`Unstoppable Edge` on a shared intuition would be the reasoning this project has
withdrawn three times.

**What would bind them:** allocate ONE talent with a full-screen capture
running, then read the node name off the frame against the `talent data
response` emitted at that wall clock. One talent per cycle. The same recipe the
affix ids need, and the same reason.

## The SKILLS screen - 2026-08-25, and it carries a `5` that ROADMAP item 10 needs

Read from `f0059_22.26.04` in `C:\ll-captures\2026-08-25b\talents\`, part of the
2560x1440 capture no session had opened. Level 5 Blackarrow.

**Scope note.** This document opened as a record of affix and item readings and
has drifted into being the home for anything read off the client. That drift is
recorded rather than resisted - the alternative is scattering first-party
readings across three files - but a reader looking for CLASS facts should also
check `docs/CLASSES.md`.

### `Rapid Arrows`, quoted in full

The skill tooltip, verbatim:

> **`Rapid Arrows`** - `Bow`
>
> After using the skill, Blackarrow enters `Volley` mode, allowing you to hold
> to rapidly fire **up to 5 arrows** for a certain duration, dealing
> `Physical Damage`. During Volley, shooting does not reduce `Movement Speed`.
> Dodging removes Volley.

### Why this matters to ROADMAP item 10, and what it does NOT settle

Item 10 chases a buff icon **that climbs to 5** while the operator keeps hitting
one target. `docs/AFFIXES.md` already quotes the `Focus Fire` talent as scoping
to `Rapid Arrows`. Here the game states that `Rapid Arrows` fires **up to 5
arrows** in a mode it names `Volley`.

**A fourth candidate for the climbing icon now exists, and it is the first one
carrying the number 5 from the game itself:** the icon may be the Volley arrow
COUNT rather than any stacking damage buff.

**This is a candidate, not a resolution, and the coincidence of the number is
exactly the kind of evidence this project has been burned by.** Three things
stop it being an answer:

1. Nothing observed ties the on-screen icon to Volley. The match is between a
   remembered maximum of 5 and a stated maximum of 5.
2. Volley is described as lasting "a certain duration" - a TIME bound - whereas
   item 10 reports the icon climbing with hits on one target. A count that
   ticks down over time and a count that climbs per hit behave differently, and
   nobody has watched which one the icon does.
3. `Focus Fire` still exists and is still scoped to this same skill, so the two
   candidates are not mutually exclusive - a Volley counter and a per-hit
   multiplier could both be on screen.

**What separates them is cheap and already specified.** Item 10's target-switch
test discriminates `Focus Fire` from the `Ranged` affix. Volley needs a
different one: fire Rapid Arrows and then STOP, without dodging. A duration
counter decays on its own; a per-hit stack does not.

### The skill screen's structure, recorded because nothing had it

TRANSCRIPTION. Two sections:

- **`Basic Skill`** - one slot.
- **`Weapon Skill`** - split into two columns, `Arrow` and `Skills`.

The `Arrow` column has three equipped slots keyed, left to right, **`Z`, `X`,
`C`**. Below them sit two named rows of five icons each:

| row | slots |
|---|---|
| `Archer's Arrow` | 5, of which 3 render unlocked and 2 locked |
| `Hunter's Arrow` | 5, all rendering locked except one |

The `Skills` column has three equipped slots keyed **hold**, **`Q`**, **`E`**,
over a pool of seven icons of which three render locked.

### This narrows RES-8, which was blocked on exactly this

`docs/OBSERVED_IDS.md` records that `destSlot 2` is the only arrow slot ever
equipped in the log, and the open question was the mapping of `Z`/`X`/`C` to
`0`/`1`/`2`. **The screen shows the three arrow slots keyed `Z`, `X`, `C` in
that left-to-right order.**

That does not finish the binding, and the remaining gap should be stated
precisely rather than waved through: `destSlot` is an integer and nothing
observed says it indexes this row left-to-right from zero. What was a
two-part question - what the slots are, and how they are numbered - is now a
one-part question. A single capture of an arrow being equipped to the `Z` slot,
joined to the `destSlot` value emitted at that wall clock, closes it.

### Two arrow FAMILIES, which ROADMAP 4b needs

`Archer's Arrow` and `Hunter's Arrow` are named rows of five. `OBSERVED_IDS`
records four ammoIds in a `1205xx` space observed being equipped. Ten arrow
types are visible here against four ids observed.

**No id is bound to any arrow name by this frame** - the screen shows icons and
row names, the log shows ids, and nothing on this frame carries both. Recorded
as a count that constrains the id space, not as a binding.

### New game nouns

`Volley`, a mode entered after using `Rapid Arrows`, removed by dodging.
`Brandrgarde`, a faction or place named in the skill's flavour text, which also
names `Deathclaw Hunter Eric` as "the last Blackarrow to shoot 10 arrows in
succession". The bow this project has been reading affixes off is called
`Deathclaw Hunter`, so the weapon is named for that figure - recorded as a
naming link, with no mechanical claim attached.


## Sweeping the unread captures - 2026-08-30c

**Method, stated because the coverage claim depends on it.** The two unread
captures hold 188 frames. Rather than read them one by one, every frame was
reduced to a 16x16 average hash and consecutive frames grouped where the Hamming
distance was 12 or less. That collapses **188 frames to 75 distinct states** -
53 in `talents`, 22 in `reanchor`. States were then read in descending order of
expected information, and every distinct SCREEN TYPE below was opened directly.

**What that does and does not cover.** Every distinct screen type in the
captures has been read. Individual item-tooltip hovers - the long tail of
single-frame states in the warehouse - were sampled, not exhausted, so an item
name or a Source list may remain unread. No screen type is unaccounted for.

### THREE COMPLETE AFFIX LADDERS, and the third refutes the pattern

This document previously had ONE published ladder, for `Ranged`. Two more were
read off `f0092_22.27.16` and `f0104_22.27.42`.

**`Fervid`**, quoted:

> **Effect.** When `Health` is above 70%, increase `Physical Damage` and
> `Magic Damage`. Upon reaching a certain level, when `Health` is above 70%,
> reduce `Skill Energy Cost`.

| Level | Physical Damage | Magic Damage | Skill Energy Cost Reduction |
|---|---|---|---|
| Lv. 1 | +1.8% | +1.8% | - |
| Lv. 2 | +3.6% | +3.6% | - |
| Lv. 3 | +5.4% | +5.4% | - |
| Lv. 4 | +7.2% | +7.2% | - |
| Lv. 5 | +9% | +9% | +6% |
| Lv. 6 | +10.8% | +10.8% | +6% |
| Lv. 7 | +12.6% | +12.6% | +6% |

**`Seeker`**, quoted:

> **Effect.** Hitting an enemy increases `Movement Speed` for 3s. Upon reaching
> a certain level, the `Speed Boost` can stack.

| Level | Movement Speed |
|---|---|
| Lv. 1 | +1.5% |
| Lv. 2 | +3% |
| Lv. 3 | +4.5% |
| Lv. 4 | +4.5%, stacking up to 2 times |
| Lv. 5 | +6%, stacking up to 2 times |

### A TEMPLATE WAS ALMOST PUBLISHED FROM TWO LADDERS, AND THE THIRD BREAKS IT

With `Ranged` and `Fervid` in hand the pattern looks firm: a primary that is
exactly `rate * level`, a secondary that unlocks at **Lv. 5** and stays flat,
and a ladder **7 levels** long. `Ranged` is 1.6% per level with Effective Range
appearing at Lv. 5 and flat at +12%; `Fervid` is 1.8% per level with Skill
Energy Cost Reduction appearing at Lv. 5 and flat at +6%.

**`Seeker` breaks all three properties at once.** Its ladder is **5 levels, not
7**. Its secondary unlocks at **Lv. 4, not Lv. 5**. And its primary is **not
linear** - Lv. 3 and Lv. 4 both read +4.5%, with the level-4 step spent on
gaining the stack instead of on the number.

**Recorded as a near miss rather than quietly dropped.** Two ladders agreeing
was a hypothesis, and it was one edit away from being written down as a law that
Emberforge could have encoded. What survives is weaker and true: an affix has a
primary that scales with level and MAY gain a secondary clause at some level,
and neither the ladder length nor the unlock level nor the linearity is shared
across affixes.

### The conditional gate is a real family

Each ladder's effect is gated on a condition, and the conditions differ in kind:

| affix | gate |
|---|---|
| `Ranged` | distance to target greater than 5 meters |
| `Distant Ward` | distance to attacker greater than 5 meters |
| `Fervid` | `Health` above 70% |
| `Seeker` | on hitting an enemy, for 3s |

**More published durations and thresholds:** `3s` for `Seeker`, `70%` for
`Fervid`, `10s` and `60s` from the gem tooltip recorded earlier. The claim that
this game publishes no durations is false for affixes by a widening margin.

### The `Affix Details` slot attributions can now be NAMED

An earlier reading of the `Affix Details` table described the per-slot counts by
GROUP rather than by name, because the header glyphs are small. **Two
independent surfaces now agree**, so the hedge can be lifted for the two that
are cross-checked: each affix's own `Level Distribution` row names the same
slots the table does.

| affix | level | slots, agreed by BOTH surfaces |
|---|---|---|
| `Fervid` | Lv.2 | pants 1, boots 1 |
| `Seeker` | Lv.1 | weapon 1 |

`Fervor` Lv.2 and `Wealth` Lv.1 are read from the table only - helm and chest
for the first, an accessory column for the second - and stay unconfirmed by a
second surface.

**The sum rule now has SIX independent confirmations** - four rows on the
`Affix Details` table plus two per-affix `Level Distribution` rows - and holds
on every row
of every surface examined.

### An affix appearing LIVE on an equip

Between `f0128_22.28.34` and `f0141_22.29.02` the `Affixes` panel goes from four
entries to five, and the new entry is **`Elusive` Lv.1**. The four existing
affixes are unchanged. The log names the cause exactly:

    22:28:56 local - server_EquipArmor: ... slot-2 cfg-1330304

Slot 2 is `glove`. So **item `1330304` grants `Elusive` Lv.1**, and the previous
occupant of that slot granted nothing.

**Whether `Elusive` is the item's OWN affix or comes from a gem socketed in it is
NOT determined.** The `Affixes` panel lists both kinds undifferentiated - this
document establishes that elsewhere - and the log never carries this item's
`exEquip`, so its affix cfgId is unknown. An item-to-affix-NAME binding, not an
id binding.

### A THIRD binding route exists, and its two halves have never co-occurred

The equip above is the template for a route this document had not identified:
**equip an item whose affix cfgId the log carries, with the `Affixes` panel OPEN
across the equip, and the affix that appears names that id.**

It has never fired, and the reason is precise. There are 23 single-slot equip
events across the three logs. Only ONE involves an item with a known affix
cfgId while a full-screen capture was running - item `1360303`, affix `211`, at
01:15:35 on 2026-08-30. **The `Affixes` panel is CLOSED in the frames on both
sides of it**, showing only the `F2 Attributes & Affixes` prompt, so no delta
can be read.

The one equip with the panel open is the `Elusive` case, whose item has no
recorded affix cfgId.

**So the recipe is one sentence: keep the `Affixes` panel open while equipping.**
That costs nothing and converts ordinary gear changes into id bindings.

### `211 = Ranged` re-confirmed by a third method

`f0134_22.55.00` in the `reanchor` capture shows a side-by-side comparison:
`Deathclaw Hunter`, a `Legendary Bow and Arrow`, against `Oil-soaked Wooden
Bow`, a `Rare Bow and Arrow`. **Both carry `Ranged` Lv.1**, in the gem-less
position.

`Deathclaw Hunter` is item `3060404`, whose affix cfgId the log gives as `211`.
So the item route agrees with the trade-filter route that `211` is `Ranged` -
now three independent confirmations of that binding.

**Two different bows, different rarities, same item-borne affix.** This was
offered as UI evidence that the affix travels with the item TYPE rather than
being rolled per instance.

**THAT READING IS WITHDRAWN - see the tooltip section below.** A second
`Oil-soaked Wooden Bow` carries `Seeker` where this one carries `Ranged`, so
two instances of one item name disagree. The OBSERVATION here stands - these two
bows do share an affix - but it is no longer evidence for the type-level model,
because a per-instance roll produces coincidences too.

### The character ATTRIBUTE sheet, which nothing had recorded

From `f0079_22.26.47`, the `Attributes` tab. `docs/CLASSES.md` lists the
attribute system under what nobody knows; this is a partial answer.

| Basic | | Energy | |
|---|---|---|---|
| `Attack` | 140 | `Maximum Energy` | 100 |
| `Defense` | 198 | `Energy Recovery Speed` | 10 |
| `Maximum Health` | 844 | `Skill Energy Cost Reduction` | +0.00% |
| | | `Max Dodge` | 250 |
| | | `Dodge Recovery Speed` | 20 |
| | | `Dodge Energy Cost Reduction` | +0.00% |
| | | `Max Stagger` | 100 |
| | | `Stagger Recovery Speed` | 5 |

A `Damage` section sits below and was scrolled off in every frame examined.

**`Dodge` is a numeric resource with a cap of 250 and its own recovery speed**,
separate from `Energy`, and `Stagger` is a third such resource. That bears on
`RES-3`, which asks how roll differs from dodge - dodge is at least a metered
resource here, which a roll may or may not share.

**A guide claim gains a mechanism, and only that.** `docs/CLASSES.md` reports
from T4 guides that `Elusive` "reduces dodge energy cost". A stat literally
named `Dodge Energy Cost Reduction` exists. That makes the guide claim
mechanically POSSIBLE; it does not confirm it, and no reading here connects
`Elusive` to that stat.

### Items state their SOURCE

From `f0128_22.28.34`, the tooltip for `Mithril Ingot`, an
`Epic Forging Material`, carries a `Source` block listing where to obtain it:

- `Auction`
- `Brandrgarde Exploration`
- `Explore the Hallowgrove`

plus a `Value` of 192.

**This is an acquisition taxonomy stated by the game**, and it is the surface
`RES-2` needs - that item asks how arrows are acquired at all, loot or craft or
vendor, and the answer is written on the tooltip of any item worth asking about.
`Hallowgrove` is the player-facing name this project has already bound to the
`Whitewoods` map, so one Source entry names a dungeon and another names
`Brandrgarde`, which the skill flavour text also names.

No arrow's tooltip was captured, so no arrow's Source is read here.


## The tooltip tail - 2026-08-30d, and it REFUTES a claim published hours earlier

Continuing the sweep of the unread captures into the item and talent tooltips
that the first pass sampled rather than exhausted.

### FIRST, A WITHDRAWAL

The previous pass wrote, from `f0134_22.55.00`, that a `Legendary` and a `Rare`
bow "both carry `Ranged` Lv.1" and offered it as UI evidence that the
item-borne affix travels with the item TYPE.

**`f0130_22.28.38` shows an `Oil-soaked Wooden Bow` carrying `Seeker` Lv.1.**
Same item name, same base stats - `23 Attack`, `+2.00% Physical Damage` - and a
different affix. The two differ in durability, 63% against 94%.

**That durability gap is NOT proof of two instances, and an earlier version of
this line said it was.** Durability rose between the two readings, which a
REPAIR explains as readily as a second item. Either way the conclusion holds -
if it is one item, its affix CHANGED, which refutes the type-level model just as
firmly as two instances disagreeing would. The reason is corrected; the finding
is not.

**So two instances of the same-named item carry DIFFERENT affixes, and the
"affix travels with the item type" reading is refuted as stated.** This is
precisely the test the log-derived section named as missing - it says in terms
that every observed item was a distinct type, so "nothing here compares two
instances of the SAME type". Two instances now exist and they disagree.

**What survives, stated carefully.** The log's `"fixed":true` flag and the
one-to-one item-to-affix mapping across three logs are still measured facts.
What they cannot support is the INFERENCE that the mapping is a property of the
item type - one character owning one instance of each type produces exactly that
pattern whether the affix is fixed or rolled.

**The honest limit of the refutation:** the two bows are matched by display NAME
and base stats, not by `cfgId`, and two different cfgIds could share a name.

**THAT LIMIT WAS THE ANSWER, AND THIS REFUTATION IS ITSELF WITHDRAWN,
2026-09-01.** They ARE two different cfgIds sharing a name. The log records both
held at once, in adjacent slots, with distinct 19-digit instance ids:
`3030403` carries affix `(209, 1, true)` and rendered `Seeker`; `3030404`
carries `(211, 1, true)` and rendered `Ranged`. Both display as `Oil-soaked
Wooden Bow`, `Rare Bow and Arrow`, `23 Attack`, `+2.00% Physical Damage`.

**So the type-to-affix mapping SURVIVES** and the "two instances of one type
disagree" evidence never existed. What the episode does establish is narrower
and still useful: **an item's display NAME does not identify its type.** Two
cfgIds share this one, so any binding matched on a rendered name rather than a
`cfgId` is unsafe.

The sentence "the log carries no `exEquip` for either" was also simply wrong -
the log carries `exEquip` for both, and it is the reason the two are now
separable.

### The affix delivery routes are THREE, not two

`f0136_22.28.51` shows `Malt`, a `Common Materials` item, described as an
"Ingredient for `Victory Wine`". The log carries `WineAffixPoolView` and a
payload `{"wines":[{"id":1,"affixes":[208,211]}]}`.

**Wine carries affixes.** With `208 = Fervid` and `211 = Ranged` already bound,
wine id 1 grants those two. So an affix reaches a character by at least three
routes - borne by the item, delivered by a socketed gem, or carried by a wine -
and the `Affixes` panel lists all of them undifferentiated.

### Items state their SOURCE, and the taxonomy has two kinds of entry

| item | rarity band | Source entries |
|---|---|---|
| `Mithril Ingot` | `Epic Forging Material` | `Auction`, `Brandrgarde Exploration`, `Explore the Hallowgrove` |
| `Malt` | `Common Materials` | `Shop`, `Auction`, `Brandrgarde Exploration`, `Explore the Hallowgrove` |

`Shop` and `Auction` render with a navigation arrow; the two `Explore` entries
do not. **INFERENCE:** the arrow marks a source the UI can take you to, which
separates vendor sources from activity sources. This is the surface `RES-2`
needs, which asks how arrows are acquired - no arrow tooltip was captured, so no
arrow's Source is read here.

### THREE SKILL TOOLTIPS, quoted - with their frames named

**An earlier version of this section cited NO frame for any of these**, which
breaks the method paragraph at the top of this document - the same omission it
was written to shame, and one already recorded as a method defect earlier today.
The frames are named here.

> **`Rapid Arrows`**, frame `f0059_22.26.04` - enters `Volley` mode, hold to
> rapidly fire **up to 5 arrows** for a certain duration. Dodging removes
> Volley.

> **`Sky Piercer`**, frame `f0050_22.25.45` - fully draw the bow and fire a powerful arrow in a straight
> line toward the crosshairs. The arrow can `pierce` **5 units**.

> **`Scattershot`**, frame `f0056_22.25.58` - fire **7 arrows** forward simultaneously, `knocking them
> back`. **Scattershot has a shorter `base cooldown` in trio mode.**

**THE NUMBER 5 IS NOT DISTINCTIVE, and that weakens a candidate this document
raised.** The previous pass offered Volley's "up to 5 arrows" as a fourth
candidate for `ROADMAP` item 10's icon that climbs to 5, while flagging the
numeric coincidence as suspect. `Sky Piercer` also states 5. **Two unrelated
skills in one kit both state 5**, so matching on that number discriminates
nothing. The candidate survives only on the Volley mechanic itself, not on its
maximum.

**`trio mode` changes a `base cooldown`.** That is the game stating a
party-size mechanic, and `docs/CLASSES.md` calls its solo-versus-group section
the least settled for this class. **No magnitude is given** - only that the
cooldown is shorter - so the narrowed claim that no class-ability cooldown
VALUES are published survives intact.

### FOUR TALENT TOOLTIPS, quoted, and one answers a blocked item

> **`Unstoppable Edge`**, frame `f0000_22.23.53`. `Sky Piercer`'s `Physical Damage` is partially
> converted to `True Damage`.

> **`Powerful Scattershot`**, frame `f0023_22.24.44`. After `Scattershot` knocks back enemies, if they
> stop due to obstruction, they will be `Stunned`. The greater the impact force
> when enemies hit obstacles, the longer the `Stun` duration.

> **`Lightning Spread`**, frame `f0039_22.25.20`. Increases the chaining range of the lightning
> generated by a fully drawn `Lightning Arrow`.

> **`Dodge Power Shot`**, frame `f0044_22.25.32`. **Changes `roll` into `dodge`** and unlocks Dodge
> Power Shot: shoot immediately after `dodging`, consuming additional `Energy`
> to quickly fire the currently loaded quick-charge arrow. Quick-charge arrows
> can activate all special effects of fully drawn arrows but have a lower
> `Damage Multiplier`. This skill has a `cooldown`.

**`Dodge Power Shot` answers `RES-3` on its first half.** That item asks how
roll differs from dodge. **They are different actions, and a TALENT converts one
into the other** - so dodge is the upgraded form, gated behind a talent, and any
measurement taken before that talent was allocated was measuring roll. The
second half of `RES-3`, whether the class effective range is counted in
dodge-lengths, is untouched by this.

**`Damage Multiplier` is a shared named quantity.** `Focus Fire` increases it
per hit on the same enemy; quick-charge arrows have a lower one. It is the same
term in both, which makes it a real engine quantity rather than tooltip prose.

**Two draw states exist** - `fully drawn` and `quick-charge` - and they differ in
`Damage Multiplier` while sharing special effects.

### Page one of the talent tree is now completely named

The cluster occluded in the first reading is `Archer's Arrow Enhancement 2`,
`Unlocks at Lv. 11.` So page one is: `Swift Shot` (Lv. 8), `Nimble Evade`
(Lv. 7), `Battle Hardened`, `Archer's Arrow Enhancement 1`,
`Archer's Arrow Enhancement 2` (Lv. 11), and `Mighty Archer`.

**Page two is NOT uncaptured** - an earlier version of this line said it was.
`f0160_22.29.45` shows it, and `docs/OBSERVED_IDS.md` has held its clusters and
node names since 2026-08-09.

### The COMBAT BAG preset system, which nothing had recorded

`f0146_22.29.13` shows a `Combat Bag` tab beside `Storage Box`, holding tiered
bags and named loadout presets:

| bag tier | owned |
|---|---|
| `Novice Combat Bag` | 7/10 |
| `Advanced Combat Bag` | 1/5 |
| `Pro Combat Bag` | 1/5 |
| `Elite Combat Bag` | 0/5 |

Presets under the first, named to a scheme:

    Common - Blackarrow (Bow Hunter) [PvE]
    Common - Blackarrow (Bow Hunter) [Balanced]
    Common - Blackarrow (Bow Archer) [PvE]

So the scheme is `<rarity> - <class> (<build>) [<mode>]`, with `Bow Hunter` and
`Bow Archer` as build names and `PvE` and `Balanced` as modes. A
`Total Expense` and a `Confirm Equip` complete the screen.

**This confirms a reconstruction this document made and flagged as
reconstructed.** The `f1290` preset label was truncated on screen to
`ndary - Blackarrow (Bow)` and `Legendary` was inferred from the rarity list
above it. The scheme here has rarity in exactly that position, so the
reconstruction was right - and it was right for the stated reason rather than
by luck.

**INFERENCE, offered as a candidate only:** `docs/OBSERVED_IDS.md` records an
unexplained second equipment slot range, 33 to 38, carrying the same item
families as slots 0 to 6. A preset loadout system is a natural producer of a
second slot range. Nothing observed connects them and no binding is claimed.

### The in-dungeon HUD confirms the arrow slots in combat

`f0151_22.55.13` in the `reanchor` capture is gameplay, not menus. The HUD shows
three arrow slots with live ammo counts keyed **`Z`, `X`, `C`**, and three skill
slots keyed hold, **`Q`**, **`E`** - the same layout the `SKILLS` screen shows,
now confirmed in combat. Also visible: an `Item Wheel` on `~`, `Inspect` on `Y`,
a compass with bearings, and two resource bars beneath the crosshair.

### Other first-party facts worth having

- **Class restriction renders in RED when the item is unusable.** A
  `Fang-Piercer Dagger` shows `Shadowstrix` in red on a Blackarrow character,
  where usable items show the class in plain text.
- **`Blessing` is a new affix name**, carried by that dagger - taking the known
  affix vocabulary to 23.
- Rarity bands seen on materials: `Common Materials`, `Epic Forging Material`.
- New nouns: `Victory Wine`, `Corroded Soldiers`, `Dmitrheim`, `Master Vronn`,
  `Scattershot`, `Stun`, `Lightning Arrow`, `Volley`, `True Damage`.

## The unread captures, finished - 2026-08-30e

`LL-0097` recorded two frames as still unread and named what each should hold.
One delivered and one did not, and the miss is recorded first because an
expectation that failed is the more useful half.

### WITHDRAWN - `talents/f0083` does NOT hold a Splatter Arrow tooltip

`LL-0097` said a fourth skill tooltip for `Splatter Arrow` sat unread in
`2026-08-25b/talents/f0083`. **It does not.** `f0083_22.26.56` is the
`WAREHOUSE` screen, and so are its neighbours `f0082` and `f0084`. There is no
skill tooltip of any kind on any of the three, cut off or otherwise. Opened
directly and confirmed by two independent readers.

**`Splatter Arrow` remains unquoted**, and the "fourth skill tooltip" is still
owed. Note the shape: the ledger entry naming this frame was written by the same
pass that swept the capture, so the miss is not a stale record going bad - it
was wrong when filed. A frame number remembered from a sweep is a hypothesis.

### The FOURTH complete affix ladder - `Wealth`, and it has NO secondary

Read off `f0115_22.54.46` in `2026-08-25b/reanchor/`, the frame `LL-0097` named.
This one delivered.

> **Effect.** Increase the amount of `Gyldenblod` from PvE in dungeons.

| Level | Effect |
|---|---|
| Lv. 1 | Amount of Gyldenblod dropped +10%. |
| Lv. 2 | Amount of Gyldenblod dropped +20%. |
| Lv. 3 | Amount of Gyldenblod dropped +30%. |
| Lv. 4 | Amount of Gyldenblod dropped +40%. |
| Lv. 5 | Amount of Gyldenblod dropped +50%. |

**It breaks the surviving pattern in a fourth new way.** `Seeker` already
refuted shared ladder length, shared unlock level and linearity. `Wealth` refutes
something those three left standing: that a ladder HAS a secondary clause at
all. It has none - the tooltip renders `Effect`, `Level Distribution` and
`Affix Level` and **no unlock line whatsoever**. That is a measured absence on a
complete, uncut panel, not a field that scrolled off.

**Its gate is a different KIND of gate.** `Fervid` gates on a combat state
(`Health` above 70%) and `Seeker` on a combat event (hitting an enemy).
`Wealth` gates on CONTENT - "from PvE in dungeons" - inside the Effect sentence
rather than in the ladder. An affix condition is not always a combat condition,
which matters to Emberforge because a content gate cannot be evaluated from a
combat state at all.

**A rendering detail worth not normalising:** the ladder rows read `Lv. 1` with
a space while the side panel reads `Lv.1` without one, both on this one frame.

### The affix BAR encodes ladder length and current level - read it without a tooltip

Counted directly off the `Affixes` panel on `f0115_22.54.46`, then re-counted
from an upscaled crop:

| Affix | Bar segments | Gold segments | Panel level | Ladder length |
|---|---|---|---|---|
| `Fervid` | 7 | 2 | Lv.2 | 7, recorded independently |
| `Ranged` | 7 | 2 | Lv.2 | 7, recorded independently |
| `Fervor` | 7 | 2 | Lv.2 | **7, READ 2026-08-30 - see below** |
| `Wealth` | 5 | 1 | Lv.1 | 5, read off the same frame |

**Two readings, each confirmed on the frame that also carries its check.** Total
segments equal the ladder length in all three cases where the length is known by
other means. Gold segments equal the affix level in all four rows.

**The obvious objection is refuted on the same frame.** Three affixes at Lv.2 all
showing 7 could mean the bar is a fixed 7-wide widget rather than a ladder
length - `Wealth` showing 5 on the same panel rules that out.

**This is worth having because it is free.** Ladder length and current level can
be read off the panel without opening a single tooltip, which turns one
screenshot of the `Affixes` list into a length for every affix on it. It
PREDICTS `Fervor` at 7 levels; that is a prediction, not a reading, and one
tooltip settles it.

**THE PREDICTION WAS THEN TESTED AND HELD.** `Fervor`'s ladder was read off
`f0980_00.52.15` and is **seven levels**, panel border visible below `Lv. 7`.
See "Mining the 2026-08-30 capture" below. A prediction recorded before its
reading is worth more than a pattern fitted after one, which is why the wording
above is left standing rather than edited to sound confident in hindsight.

### The attribute sheet's lower half, which was scrolled off in every earlier frame

The section above records `Basic` and `Energy` from `f0079_22.26.47` and says a
`Damage` section "sits below and was scrolled off in every frame examined".
`f0084_22.26.58` is scrolled one notch further and carries the rest, completing
the sheet at **five sections**:

| Damage | | Survival | | Speed | |
|---|---|---|---|---|---|
| `Physical Damage` | +6.60% | `Physical Resistance` | +2.50% | `Movement Speed` | +0.00% |
| `Magic Damage` | +3.60% | `Magic Resistance` | +2.00% | `Skill Cooldown Speed` | +0.00% |
| `Critical Damage` | +25.00% | `Critical Damage Resistance` | +2.00% | | |
| `Defense Penetration` | +0.00% | `Healing Done` | +0.00% | | |

`Physical Damage` and `Magic Damage` render green with an up-chevron; the rest
render plain. On this loadout those two are the only attributes the gear has
moved, which is consistent with the affixes equipped and is the panel marking
a delta rather than a total.

**Note the unit split, because it is a parsing trap.** This panel uses
two-decimal percentages (`+0.00%`) while the affix ladders use whole numbers
(`+10%`), so a reader normalising one to the other will silently corrupt the
other.

**A marquee trap, found by reading two adjacent frames.** The `Pip's Pouch`
label is a SCROLLING marquee: `f0083` renders `limit per slot:1500` and `f0084`
renders `alue limit per 1500` - the same label, mid-scroll, at 2-second spacing.
A single frame of it can look like a complete string and be a fragment. Any
label read off one frame should be confirmed on a neighbour.

**Not a new finding, and recorded so nobody files it as one:** the `Basic` and
`Energy` values on these frames are identical to those already in this document
from `f0079`. Only the three lower sections are new.

## Mining the 2026-08-30 capture - 2026-08-30 pass

2172 frames at `C:/ll-captures/2026-08-30/frames/`, largely unopened. 186 were
read. The screen map is in the session scratch; what follows is what it settled.

### `Fervor`'s ladder - the SEVEN-LEVEL prediction was made, then CONFIRMED

The bar rule above predicted 7 levels from a 7-segment bar. Read off
`f0980_00.52.15`, and the panel's bottom border sits below `Lv. 7`, so the list
is complete rather than clipped:

> **Effect.** After hitting an enemy, increase `Physical Damage` and
> `Magic Damage` for 3s, **stacking up to 5 times**. Upon reaching the required
> level, when the number of stacks is greater than or equal to 3, increase
> `Defense Penetration`.

| Level | Physical Damage | Magic Damage | Defense Penetration |
|---|---|---|---|
| Lv. 1 | +0.4% | +0.4% | - |
| Lv. 2 | +0.8% | +0.8% | - |
| Lv. 3 | +1.2% | +1.2% | - |
| Lv. 4 | +1.6% | +1.6% | - |
| Lv. 5 | +2% | +2% | +2.5% |
| Lv. 6 | +2.4% | +2.4% | +2.5% |
| Lv. 7 | +2.8% | +2.8% | +2.5% |

**This is a prediction that was recorded BEFORE the reading and then held**,
which is a different and stronger kind of evidence than a pattern fitted after
the fact. It also restores the shape `Seeker` broke, without restoring the
template: `Fervor` matches `Ranged` and `Fervid` in ladder length (7), in linear
primary scaling (0.4% per level) and in a secondary that unlocks at Lv. 5 and
stays flat (+2.5%). Four ladders now: three of one shape, one of another. **The
shape is a family, not a law** - `Seeker` at 5 levels and `Wealth` at 5 with no
secondary are still counterexamples.

**`Fervor` and `Fervid` are DIFFERENT affixes** with different icons and
different ladders. They appear adjacent in the panel and the names differ by two
letters. Do not merge them.

### The bar's segment count VARIES BY AFFIX - the rule is not a constant width

`f1300_00.58.54` renders nine affixes at once and the bars are not all the same:

| Bar | Segments | Affixes |
|---|---|---|
| 187 px | 7 | `Fervid`, `Ranged`, `Focused`, `Skypiercing`, `Valor`, `Wrath` |
| 134 px | 5 | `Elusive`, `Smiting`, `Curse` |

Same 26.7-26.8 px pitch in both, so the difference is segment COUNT, not scale.

**Those three numbers were published wrong first and an adversarial pass
corrected them** - 193, 140 and 27.6-28.0. All three came from measuring to the
bar's left edge from the ICON's right edge rather than from the bar's own start,
a six-pixel offset that inflates every width and the pitch derived from them.
The bar is a crisp rectangle with no antialiasing to argue about. **The segment
counts and the affix assignment were right**, so the conclusion never moved -
but a derived number that nobody re-measures is how a wrong constant enters a
build engine.
That rules out the obvious objection to the rule - a fixed-width widget - on a
single frame, and it means the 7 that predicted `Fervor` carried real
information.

**A standing prediction, recorded before the reading as the `Fervor` one was:**
`Elusive`, `Smiting` and `Curse` each have a **5-level** ladder. One hover on
any of them confirms or refutes it, and a refutation is worth as much here.

### `Splatter Arrow` is NOT in this capture - a measured negative

Ledger `LL-0097` claimed it sat in `talents/f0083`; that was refuted earlier
today. It is not in the 2026-08-30 capture either. The `SKILLS` screen appears
in exactly **8** frames (`f0510`, `f0516`, `f0517`, `f0518`, `f1187`, `f1188`,
`f1278`, `f1650`) and all eight were read. No skill of that name renders.

**Why the capture cannot answer it:** the 7-tab camp skill grid renders **icons
only** - names appear solely in the right-hand detail panel - and in all four
7-tab frames the operator was tabbing through, so the panel never left its
default selection. The in-field panel names only the six EQUIPPED weapon skills:
`Steel Arrow`, `Concussive Arrow`, `Lightning Arrow`, `Scattershot`,
`Rapid Arrows`, `Sky Piercer`. **`Splatter Arrow` remains unquoted** and needs a
capture where the operator hovers it.

### A socket TIER is rendered; a socket LEVEL still is not

`f1733_01.08.04` shows `Tier II Peridot Slot - Empty` and `Tier I Moonstone Slot
- Empty` - Roman numerals, which misread as `Tier 0` and `Tier 1` at contact-sheet
resolution. `Moonstone Slot` is new; `Peridot Slot` and `Tier II` were already
recorded.

The gem rule quoted elsewhere in this document - a gem's level cannot exceed the
level of the target equipment socket - therefore names a socket LEVEL that
**still appears on no frame in this capture**. Tier is not level. That
observation stays open exactly as recorded.


## What to capture next, in priority order

Each is one hover in a menu and yields a whole ladder, so the ratio of effort to
recorded fact is better than any measurement this project runs.

**Rewritten 2026-08-30 after the binding pass.** Items 3 and 5 of the previous
list are wholly or partly answered and are marked so rather than deleted.

1. **The four unbound affix ids**, per the recipe in the section above. `212` is
   the cheapest - the operator still holds item `1230304`, so it is one tooltip
   hover with a FULL-SCREEN capture running. `214` needs the Auction House
   filter, one affix ticked alone. `101` and `209` need an item carrying them
   and may need one re-acquired.
   **The binding constraint is the capture, not the game.** Every failure in
   that section is a frame that was never taken or was cropped - so a
   full-screen poller running during ordinary menu use is worth more here than
   any deliberate experiment.
2. **A gem slotting screen** - socket tiers, what a Peridot is, and whether tier
   gates level. Still open: the inlay rule names a socket LEVEL and no socket
   level has been observed on any frame.
3. **`Fervor`'s ladder** - ANSWERED 2026-08-30 and quoted above. Seven levels,
   as the segment rule predicted. Replaced by: read `Elusive`, `Smiting` or
   `Curse`, each predicted at **5 levels** by the same rule.
4. **The `Focus Fire` talent tooltip** - ANSWERED 2026-08-30 and quoted above.
   Left here because the remaining half - whether the climbing buff icon is
   `Focus Fire` or the `Ranged` affix - needs the target-switch test, not
   another tooltip.
5. **The remaining named affixes from guide consensus** - ANSWERED. All seven
   are confirmed real game vocabulary, and `Valor` and `Fervid` are now bound to
   ids. See `CLASSES.md` C14.
6. **Whether the `Affix Effects` list is scoped by gem type** - one capture:
   change the `Gem Type` selection and re-read the dropdown. If the 16 entries
   change, the list is type-scoped, which would also explain why `Focused`,
   `Elusive` and `Curse` are missing from it.
