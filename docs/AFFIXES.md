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
