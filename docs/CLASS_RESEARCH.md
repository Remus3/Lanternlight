# Class research - Blackarrow vs Shadowstrix

Two independent research agents, one per class, 2026-08-09. Adjudicated here by
the merger. Neither agent graded its own output; this file records where they
agreed, where they conflicted, and what was thrown out.

Player profile weighted against: League mains Tristana and Vayne - ranged
sustained auto-attack DPS, spacing and kiting, target selection, high mechanical
ceiling, historically vulnerable to being collapsed on. New to extraction games.

## Cross-agent conflict, resolved

The Shadowstrix agent reported "every class carries two stances" from the Steam
store page. The Blackarrow agent found an official launch announcement stating
"the Blackarrow's new weapon will launch in a future season". **The store copy
is generic marketing; Blackarrow is the exception.** Blackarrow is bow-only at
launch. Its "Archer" and "Hunter" are ammo/playstyle families on one weapon, not
two stances. Resolved in favour of the specific official statement.

## Blackarrow

- Bow only. Archer = charged burst; Hunter = fast hits plus debuffs. The
  developer is deliberately widening the gap between them (DevNote #7 gated the
  Splatter Arrow Sepsis bonus behind a full charge, removed the charge
  requirement from Featherlight Arrow).
- **Nerfed 2026-08-06**: impact effect removed from uncharged shots, impact of
  fully charged shots slightly reduced. Official. Any tier list stamped only
  "August 2026" cannot be placed relative to this, so treat S-tier claims as
  probably pre-nerf.
- Officially acknowledged as **overperforming in solo** before that patch.
- Top affixes agreed by two independent outlets: Ranged, then Focused. Its speed
  stat is **Charging Speed**, not attack speed.
- Effective heavy-shot range is roughly **two dodge-lengths** - player
  testimony, absent from every guide site. It is not a sniper.
- Dies to gap-closers in tight terrain and to baited mobility cooldowns. Thin
  escape kit: Shadow Step, dodge charges, Scattershot knockback, traps.
- **Gear-hungry.** Officially tied to "high-tier gear matches".

## Shadowstrix

- Two real stances: Dagger (stealth-enabled, single-target) and Dual Blades
  (combo/dash/Wound stacking). **Stealth is Dagger-only.**
- Stealth is entered by holding both mouse buttons, is duration-limited, has a
  long cooldown, works on players, and is stripped by reveal consumables and by
  proximity. Blackarrow is named as its worst enemy.
- Element of Surprise makes a dagger backstab out of Stealth an **automatic
  crit**, which is why crit stats are de-emphasised in favour of raw physical
  and penetration.
- Squishiest class in the game. Loses a straight fight to Mercenary and Withered
  Knight; Withered Knight parries most of its kit.
- **Untouched by every patch since launch.** Its only nerf (Crow Storm stacking
  on stunned players) shipped in the launch build. Blackout plus Crow Storm
  stun-lock is a live, loud complaint and is the likeliest next nerf target.
- Sits at or near the top of every tier list, and unlike Blackarrow those lists
  are all post-nerf and therefore current.

## Agreed by both agents

- **No cooldown numbers, damage coefficients or stealth durations are published
  anywhere as of 2026-08-09.** Any site quoting a second value is fabricating.
  This is load-bearing for Emberforge: the engine's first job is to measure what
  nobody has published, which is exactly the gap RedMoon was built to fill.
- Gems replaced random gear affix rolls (DevNote #6, Dev Team FAQ #2). Mid-game
  power comes from sockets, not drops.
- Mercenary is the consensus first class for learning the genre. Both agents
  independently advised against starting on their own assigned class.
- The launch-window wiki farms (mistfallhunters.wiki, mistfallhunter.app,
  mistfall-hunter.wiki, metamist.io, mistfalldb.com and roughly ten siblings)
  cross-copy each other verbatim. **Agreement among them is not corroboration.**
  One invented an "SS tier" that no other list uses; one invented an August 5
  Blackarrow nerf that does not exist. Boost and gold vendors (skycoach,
  mmoexp) were excluded as evidence.

## Unresolved

- Shadowstrix solo vs trio: FandomWire and KeenGamer say best solo; Mobalytics
  ranks Withered Knight and Mercenary above it solo and puts its strength in
  trios. Not resolvable from published sources.
- Whether incoming damage breaks Shadowstrix stealth. Not published.
- Whether the Blackarrow Archer/Hunter split is a hard talent lock or just a
  power gradient. Official language says "playstyles", never "branches".
- Attribute system (Strength / Dexterity semantics) is unpublished at any
  trustworthy tier.

## Verdict

**Blackarrow as the main.** It is the direct transfer of the player's existing
skillset, it is strong in solo, and its failure mode is one they already
understand from the other side of it. The Aug 6 nerf was modest and it remains
top-half.

**Shadowstrix as the second character**, taken around hour 20 once map knowledge
and extract timings are internalised. The log shows `roleLimit:3`, so slots are
not scarce. Taking it first would put the squishiest body in the game, with a
one-opener-one-escape kit, into an unfamiliar extraction loop where a lost fight
also loses the kit.

Note the timing asymmetry honestly: Shadowstrix is the stronger class *right
now* precisely because it has not been touched, and that is also the reason to
expect it to be nerfed next. Building a main around an untouched outlier eleven
days after launch is building on sand.

## Operator decision, 2026-08-09

**Blackarrow now, Shadowstrix committed for slot 2 at approximately hour 20.**
Slot 3 left free. Purpose is "both" - it is the real main account, and
Lanternlight harvests whatever the log yields rather than the class being chosen
as an instrument.

Consequence for Emberforge: two-class coverage is scheduled rather than
accidental, so the data model must not hard-code a single class shape. Class
identity appears in the log as a numeric `inclassid`, so the first mapping job
is `inclassid -> class name`, established by observation at each character
creation. Record the id the moment each character is made; it is cheap then and
expensive to recover later.
