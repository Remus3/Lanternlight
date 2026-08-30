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

Observed on `Deathclaw Hunter`, Legendary Bow and Arrow, Blackarrow-restricted,
at affix level 1. Verbatim from the tooltip:

> **Effect.** If the distance between you and the target is greater than
> 5 meters when hit, temporarily increase Physical Damage and Magic Damage.
> Upon reaching a certain level, increase ranged damage's effective range.
>
> **Effective Range.** Different ranged attacks have different Effective
> Ranges. Beyond the Effective Range, both DMG and Impact will diminish.

**Level Distribution** - the tooltip shows a row of nine equipment-slot icons
with a value under each. Only the weapon slot carries `1`; the other eight read
`-`. So this affix appears on weapons only.

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

**Not yet established, and deliberately left open:** whether `Ranged` is
strictly intrinsic, or whether the visual difference is only "socketed versus
not". One item at one level cannot settle it. The check is cheap - compare two
items whose gem sets differ - and it needs doing before Emberforge encodes
either shape.

## Other item facts read from the same tooltip

Recorded because they are cheap to capture and were never written down:

- Item identity: `Deathclaw Hunter`, rarity `Legendary`, type
  `Bow and Arrow`, class restriction `Blackarrow`.
- Base stats: `40 Attack`, `+7.20% Physical Damage`. Note the base line is a
  flat percentage on the item, separate from the affix ladder.
- `Durability 100%`, with its own info tooltip.
- `Average Transaction Price 2,467` against `Value 345` - two different numbers
  the UI shows side by side. The first is market-derived, the second is not, and
  `lanternlight/avgprice.py` already watches the market cache that feeds one of
  them.
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
