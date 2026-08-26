# Mistfall Hunter classes

The single source of truth for class knowledge in this repo. It merges six
independent per-class research passes (2026-08-09, one agent per class, none of
them grading its own output) with this repo's own first-party measurements and
with the earlier adjudicated Blackarrow-vs-Shadowstrix pass.

**What this document deliberately does not contain: numbers.** No cooldowns, no
damage coefficients, no stealth or buff durations, no heal amounts, no energy
costs, no crowd-control durations. All six research passes went looking, and all
six independently reached the same result: **none of those values are published
anywhere, at any trust tier, as of 2026-08-09.** Any site quoting a second value
or a percentage is manufacturing it. Where a specific number was found
circulating, it is named in [Fabrications identified](#fabrications-identified)
so the next reader recognises it rather than re-adopting it. Emberforge exists to
measure this gap, not to fill it with guesses.

Scope and relationship to the other docs:

- [`docs/OBSERVED_IDS.md`](OBSERVED_IDS.md) is the authority for every engine id.
  Ids appear here only as a convenience and never as a correction to that file.
- [`docs/CLASS_RESEARCH.md`](CLASS_RESEARCH.md) remains the record of the
  2026-08-09 operator main-and-alt decision and its reasoning. For class facts,
  this file supersedes it, and the three places where it needed correcting are
  itemised in [Contradictions](#contradictions-and-how-they-were-resolved)
  rather than silently edited.
- Nothing here is a balance recommendation. It is a record of what is known,
  what is disputed, and how strongly each line is held.

Everything below is stated as of **2026-08-09**. The last official patch of any
kind was 2026-08-07.

## How to read this

### Trust tiers

Ordered strongest first. This is the ordering in `CLAUDE.md`, and note that
**first-party player evidence outranks established outlets here** - that ordering
decides at least one live dispute below.

| Tier | What it is | Notes |
|---|---|---|
| T0 | In-repo first-party measurement | Read off the game's own log on this machine, method recorded. Outranks every web source, because it was measured here rather than reported. |
| T1 | Official Steam news, dev posts, patch notes, store page | Specific official statements beat generic official marketing copy. The store page's "two unique weapon stances" line is known-generic and has at least one real exception. |
| T2 | First-party player evidence | Steam Community threads, creator video. Real texture, small sample, often about feel rather than fact. |
| T3 | Established outlets | KeenGamer, Destructoid, GameRant, Mobalytics, FandomWire, GameSpot, GamingBolt. Dated, bylined, but frequently uncited on mechanics. |
| T4 | Launch-window wiki sites | See the cross-copy rule below. Counts as one source in total, not one per site. |
| Excluded | Cheat, boosting and currency vendors | skycoach.gg, mmoexp.com, iggm.com, playerauctions.com, lagofast.com, u4gm.com, gladiatorboost.com. Never cited as evidence for anything, named only to record what was thrown out. |

### The cross-copy rule

The launch-window wiki farms for this game copy each other close to verbatim.
**Agreement among them is one source, not corroboration.** Two of the
fabrications catalogued below were caught precisely because a specific,
false-precision claim appeared word-for-word on unrelated domains with zero
citation on either. When a claim below rests only on that cluster, it says so.

The same caution applies to search-engine synthesis. Three separate passes
caught a search layer manufacturing a confident, specific, sourced-sounding
claim that dissolved when the cited primary source was fetched and read. Where a
claim could not be traced past a search summary, it is marked as such.

### Reading the class sections

Every class section has the same eleven subsections in the same order, so they
can be read side by side. Within them:

- A claim with no tier marker inherits the tier of the paragraph it sits in.
- "Officially" always means a T1 source, and the post is named.
- A blank is a blank. Nothing here is filled with a plausible value; per the
  repo's measurement doctrine an absent fact is recoverable and a confident
  wrong one is not.

## At a glance

**Table A - identity and kit.** The weapon-id column is T0, measured on this
machine at character creation (build `24619162`, superseded by `24813185` on
2026-08-19 and not re-confirmed since); see
[`docs/OBSERVED_IDS.md`](OBSERVED_IDS.md) for the method.

| id | Class | Weapon ids measured here | Weapons and stances | Role |
|---|---|---|---|---|
| 10 | Mercenary | 2 (`30401`, `30402`) | Hammer; Sword and Shield | Melee frontline bruiser. No official source uses the word "tank". |
| 11 | Sorcerer | 1 (`30503`) | Staff, with two spell branches, Elemental and Stardust, both named officially in DevNote #7. Second-weapon question **open**, see C2. | Ranged caster, burst and area control |
| 12 | Blackarrow | 1 (`30504`) | Bow only at launch. Officially: its "new weapon will launch in a future season". Archer and Hunter are ammo and playstyle families on the one bow, not stances. | Ranged bow damage, traps, manual aim |
| 13 | Shadowstrix | 2 (`30505`, `30506`) | Dagger; Dual Blades. Stealth is Dagger-only. | Stealth assassin, single-target burst |
| 14 | Seer | 2 (`30507`, `30508`) | Catalyst (Reverent); Mace (Blasphemer). Both named officially in DevNote #7. Which id is which is **not** established. | Support and battlefield control (Reverent); curse-melee duelist (Blasphemer) |
| 15 | Withered Knight | 2 (`30409`, `30410`) | Greatsword; Polearm and Shield. Both live at launch. | Melee bruiser and chaser, with tank-adjacent utility on Polearm and Shield |

The pair-versus-singleton pattern in that column is **real corroboration**, not
wiki agreement: it was measured here, and it independently matches the published
kits for Mercenary, Shadowstrix, Seer and Withered Knight, and independently
matches the official "future season" statement for Blackarrow. Sorcerer is the
one class where the measurement and the official record do not line up, and that
is exactly why C2 stays open.

**Caveat on the id column itself:** Withered Knight's binding to class id 15 is
the weakest in this repo. It was established by elimination plus in-game sidebar
order; its ROLE panel was never captured and pixel-joined to the log the way the
other five were. Treat "Withered Knight is 15" as strong but not equal to the
other five, and do not strengthen it from a wiki.

**Table B - current standing.** "Patched since launch" counts anything after the
2026-07-30 01:00 UTC launch. Difficulty claims are T3 or T4 guide consensus
unless marked official.

| id | Class | Solo lean | Group (trio) lean | Patched since launch | Difficulty |
|---|---|---|---|---|---|
| 10 | Mercenary | Strong (T3 consensus) | Strong opener and frontline (T3) | Yes - bug fix only, 2026-08-06. No post-launch balance change. | Lowest skill floor of the six, near-universal agreement. Ceiling claims are guide-tier only, see C13. |
| 11 | Sorcerer | **Disputed**, see C7 | Strong; Stardust specifically wants peel (T3) | Yes - bug fix only, 2026-08-06. Balance untouched since launch. | High floor and high ceiling (T3, T4). Stardust harder than Elemental. |
| 12 | Blackarrow | Officially called overperforming in solo pre-nerf (T1); guides call solo play difficult (T3). Both, see C14. | Viable (T3) | **Yes - balance nerf, 2026-08-06** | High floor and high ceiling (T3) |
| 13 | Shadowstrix | **Disputed**, see C1 | **Disputed**, see C1 | **No.** Its only change shipped inside the launch build. Verified item by item against the official feed through 2026-08-07. | Highest or among the highest execution demand in the roster (T3, T4) |
| 14 | Seer | Reverent: worst or near-worst (T3). Blasphemer: the solo option, magnitude disputed (T3). | Reverent: top tier, reportedly the only healing playstyle in the game (T3) | **No.** Its only balance changes shipped inside the launch build. | Officially acknowledged "steep learning curve" for the Support playstyle (T1, DevNote #7) |
| 15 | Withered Knight | Greatsword leans solo (T3), contested | Polearm and Shield leans group (T3) | **Yes - buffs on 2026-07-30 and 2026-08-06.** No nerf found in any source. The most actively buffed class in this research. | High, with a punishing floor (T3). Player testimony disputes whether the tools work at all, see C5. |

**One caveat governs every cell in Table B's last two columns: no tier list
verifiably dated after the 2026-08-06 patch was found for any of the six
classes.** Every statement of current standing in this document is an inference
from what that patch contained, not a citation to a source that saw it.

## Contradictions and how they were resolved

Thirteen genuine conflicts. Four resolved, nine open. A conflict is recorded
here rather than silently decided, because a silent pick destroys the
information that there was ever a disagreement.

### C1. Shadowstrix solo versus trio, and what Mobalytics actually says - OPEN

- **Prior art claims:** [`docs/CLASS_RESEARCH.md`](CLASS_RESEARCH.md) records
  "Mobalytics ranks Withered Knight and Mercenary above it solo and puts its
  strength in trios." That file does not say how the Mobalytics content was
  obtained.
- **New Shadowstrix pass claims the reverse:** Mobalytics' solo list places
  Shadowstrix in S-tier *above* Mercenary and Withered Knight, and Shadowstrix
  drops one tier *below* its own solo rank in trios. It reports every other
  source agreeing on solo-strong and trio-weaker, and says it could not locate
  the "strong in trios" framing anywhere.
- **Tier of each side:** both are T3 by origin (Mobalytics). Neither side is a
  first-hand read. The new pass states plainly that mobalytics.gg returned
  **HTTP 403 on three separate attempts** and that its correction rests on
  search-engine synthesis of indexed Mobalytics content, not on a page it
  loaded. The prior file offers no provenance at all.
- **Adjudication: unresolved. The newer pass does not win by default.** It is
  better-argued and it is internally honest about its own weakness, but "a
  search index summarised a page I could not open" is not evidence strong enough
  to overturn a recorded finding, and this project has already caught a search
  layer inventing a specific sourced-sounding claim three separate times in
  these same six passes. Two accounts of an unread page are not one account plus
  corroboration.
- **A complication worth recording, because it changes the next step.** Four of
  the six passes (Sorcerer, Shadowstrix, Mercenary, Withered Knight) report
  HTTP 403 from mobalytics.gg. The Seer pass claims it fetched two Mobalytics
  pages in full and cites publish dates for both (Seer guide 2026-08-01, tier
  list 2026-08-06), and it reports that Mobalytics splits its rankings into
  separate solo and trio lists. If that fetch was real, the block is not
  absolute and a retry along the Seer pass's path can settle C1 outright. The
  Mobalytics split-list structure it describes is also the exact shape that
  makes the prior file's version a plausible misread of a two-list source.
- **Next action:** re-fetch the Mobalytics tier list by the path the Seer pass
  used, read the solo and trio lists separately, and record which list each
  claim came from. Until then, cite neither version.

### C2. Is there an official statement about a second Sorcerer weapon? - OPEN

This is the most consequential conflict in the merge, because it touches a
standing repo rule.

- **The Sorcerer pass concludes NOT ESTABLISHED**, after checking DevNote #7,
  the Official Launch FAQ, the 2026-07-14 Community AMA (fetched and read line
  by line), the Wave 3 roadmap and all Steam news through 2026-08-07. Its
  finding is an absence-of-statement pattern: the developers used that channel
  to pre-announce Blackarrow's future weapon and to preview Withered Knight's
  Polearm and Shield, and did not use it for Sorcerer.
- **The Seer pass states the opposite in passing**, attributing to Dev Team
  FAQ #2 (T1, official) that the Sorcerer's second weapon is "closer in gameplay
  to the 'Blasphemer'". **Dev Team FAQ #2 does not appear in the Sorcerer pass's
  source list at all** - it is a venue that pass never checked.
- **Two further versions of the same claim are already known to be bad.** A T4
  site (dtgre.com) asserts "second weapon in development" citing nothing. And
  the Sorcerer pass caught a search summary asserting the second weapon was
  "confirmed to be in development" while citing the AMA - a post the pass then
  fetched and found contains no such content. So the same claim is circulating
  with three different citations, which is itself evidence that it is
  propagating without a stable source.
- **Adjudication: open, and it cuts both ways.** The Seer pass cites a specific
  official post with a URL, which is a materially stronger citation than either
  bad version, and it read that post for unrelated reasons, which is a point in
  its favour. But it is a single parenthetical in a document about another
  class, it was not the pass's subject, and it has the exact shape of the
  fabrication already caught twice.
- **This does not close the single-weapon question either way.** The repo rule
  stands unchanged: **nothing may state "Blackarrow is the only single-weapon
  class"** until a second Sorcerer `holding-` id is observed in game, or a
  deliberate documented re-walk of character creation surfaces none. Note that
  if the Seer pass's citation is real, it would make the Sorcerer's second
  weapon a planned future addition rather than a capture gap, which still leaves
  the measured single id correct for the launch build.
- **Next action, in order:** re-read Dev Team FAQ #2 directly and quote it
  verbatim or record that the sentence is absent; then run the deliberate
  character-creation re-walk, which is the only thing that closes the measured
  half regardless of what any post says.

### C3. Which class does "Shadow Veil" belong to? - OPEN

- **Sorcerer pass:** lists Shadow Veil as a Sorcerer skill, in the Stardust
  branch, described as defensive and evasion utility. T3 and T4 guides.
- **Shadowstrix pass:** describes Shadow Veil as a Shadowstrix dagger mechanic -
  a semi-stealth state entered by exiting Stealth while attacking with a dagger,
  and the state that the Element of Surprise talent's own wording references.
  T3 and T4 guides. That pass independently flagged the risk, noting one wiki
  serves its Shadow Veil page under a `skills/sorcerer-shadow-veil` URL slug and
  warning of a possible naming collision or cataloguing error.
- **Adjudication: unresolved, and neither researcher could have caught this
  alone** - each held only one half. The Shadowstrix pass predicted the
  collision from a URL slug, and the Sorcerer pass independently supplies the
  other half of it. Equal tiers on both sides, so tier does not break the tie.
- **Reading it forward:** the two descriptions are not obviously the same
  mechanic wearing one name, so the likeliest explanations are a genuine shared
  name across two classes, or a wiki-cluster mis-attribution that then
  cross-copied. Do not attribute Shadow Veil to either class in Emberforge until
  it is observed.

### C4. Which class is the squishiest? - OPEN

Sorcerer is described as having the lowest or among the lowest health and
survivability in the game (T3, T4). Shadowstrix is described as "the squishiest
class in the game", well corroborated across every source its pass checked, and
recorded that way in prior art. Seer is separately described as fragile and
escape-less, that last part officially. **Both superlatives cannot be true.** No
source found in any of the six passes compares any two classes' health directly.
The Sorcerer pass flagged this itself rather than asserting its own side.
Adjudication: treat every "squishiest" claim as relative and approximate. This is
cheaply measurable in game later and should not be settled from the web.

### C5. Withered Knight's Parry: defining strength or "a disaster"? - OPEN

- **T3 guides** call Parry a defining strength, and GameRant specifically says it
  nullifies Shadowstrix burst strategies. That last point is independently
  consistent with what the Shadowstrix side reported from its own direction.
- **T2 player testimony** (a detailed Steam Community thread) calls Parry "a
  disaster", saying its window is too long to be practically useful and that
  attacks interrupt it before it activates. The same thread says Breakthrough
  Charge has excessive displacement without Super Armor to justify committing to
  it.
- **Adjudication: unresolved, and the tier ordering matters here.** This repo
  ranks first-party player evidence *above* established outlets, so by doctrine
  the T2 thread outranks the T3 guides. That is not enough to close it: it is a
  single thread, it is contested inside its own thread, and the two sides may
  not even be making the same kind of claim - a guide describing what a tool is
  designed to do and a player describing how it currently feels can both be
  accurate. Record both. Do not report "Parry is strong" as settled.

### C6. Withered Knight's standing: A-tier or 5th of 6? - OPEN

KeenGamer (T3, published 2026-07-30) places it A-tier. FandomWire (T3, published
2026-08-02) ranks it 5th of 6. Three days apart, both after the same 2026-07-30
buff patch and both before 2026-08-06, so the patch state is identical and the
gap cannot be explained by tuning. Two named, dated, non-wiki-farm outlets in
direct disagreement. A wiki-tier source separately claims the July 30 patch
pushed the class to "S-tier frontline status", which widens the spread further
but adds no weight. First-party player sentiment in the clearest thread found is
more negative than any of them. Adjudication: unresolved, and the honest summary
is that nobody knows whether this class is currently strong.

### C7. Sorcerer's solo strength - OPEN

- The **Mercenary pass** reports Sorcerer as one of the two strongest solo
  classes, paired with Mercenary itself, across several rankings.
- The **Sorcerer pass** reports Destructoid (T3, published 2026-08-03, updated
  2026-08-04) saying the opposite for solo specifically: better suited to Trio
  mode, and at a disadvantage solo against the Mercenary and Withered Knight
  meta because closing to melee range is fatal for it. The T4 cluster says
  strong or best solo, which counts once.
- **Adjudication: unresolved.** Both passes are quoting real T3 outlets that
  disagree. Neither pass found an official or first-party statement that
  resolves it. Note the structural similarity to C1: the trio-versus-solo
  question is disputed for three of the six classes, and no source has published
  anything that would settle any of them.

### C8. Seer's tier placement - RESOLVED, by identifying the axis

FandomWire ranks Seer 6th of 6. GameRant rates it A-tier in two separate
articles. Mobalytics splits: Reverent S-tier in trios, Seer B-tier and "the
worst Solo class" in solo. These look irreconcilable and are not. **The
disagreement is a methodology split, not a factual one:** a single blended score
for a class this context-dependent lands near the bottom if the scorer weights
solo, and near the top if the scorer weights trio, and Mobalytics simply
declines to blend. GameRant's flat A-tier is the hardest of the three to
reconcile, because its own tier-list article acknowledges the solo weakness
without letting it pull the grade down. **Standing rule that falls out of this:
never quote a Seer tier without saying whether it is a solo, trio or blended
number.** For this class that distinction moves the answer between "worst in the
game" and "top tier", and both are defensible.

### C9. Mercenary's Shockwave Strike: Hammer or Shield? - RESOLVED, for the official source

A wiki-tier source lists Shockwave Strike among core Hammer skills. Official
DevNote #7 tags "Shockwave Strike Talent" explicitly as "(Shield Playstyle)".
Cross-checks: KeenGamer lists it separately from both of its own weapon lists
(ambiguous, not contradicting); Destructoid's Hammer list omits it entirely.
**Resolved for the official tag: it is Shield, that is, Sword and Shield.** Worth
keeping as the cleanest example in this document of the cross-copy problem
producing a specific, checkable, false claim - the kind that is invisible until
someone reads the primary source.

### C10. DevNote #7's publication date - RESOLVED, by recomputing at merge time

The Blackarrow pass dates DevNote #7 to 2026-07-21. Five other passes date it to
2026-07-24, and all of them cite the same announcement URL. The Sorcerer pass
records a raw Unix timestamp of `1784886600` for it. **Converted during this
merge, that timestamp is `2026-07-24T09:50:00Z`**, which independently matches
the "2026-07-24 09:50 UTC" the Shadowstrix pass reports from the news feed.
**Resolved to 2026-07-24.** The Blackarrow pass's date is wrong; its quotations
from that post are unaffected and are corroborated elsewhere. Recorded because
the 2026-07-21 date would otherwise place the pre-launch balance pass a further
three days from launch than it was.

### C11. Dev Team FAQ #2's publication date - OPEN

The Seer pass dates it 2026-03-04 and gives a URL. The Blackarrow pass's patch
table dates it 2026-07-02 and gives no URL. Leaning 2026-03-04 on the strength
of the citation, but not closed. This matters more than a date normally would,
because C2 hinges on what that specific post says.

### C12. Launch date, 2026-07-29 versus 2026-07-30 - RESOLVED

Not a real conflict. Launch was **2026-07-30 at 01:00 UTC**, per the Official
Launch FAQ, simultaneously on Steam, PS5 and Xbox Series X and S. DevNote #7's
own text says "July 29", which is the developers' CDT-local framing of the same
instant. Recorded so nobody re-derives it. One knock-on: the "Launch Rewards and
July 30 Update" post went up at 17:04 UTC on 2026-07-30, which is *after* the
01:00 UTC launch, so its Withered Knight buffs are post-launch by the clock -
even though one T3 outlet describes that same window as "the final pre-launch
balance update". A labelling ambiguity, not a factual one.

### C13. Mercenary's skill ceiling - OPEN, and note the asymmetric sourcing

Guide-tier sources describe a deceptively high ceiling located in Perfect Block
and Perfect Parry timing, counter-timing and Sword Tip management. First-party
player testimony on Steam leans the other way, describing the class as
low-effort - one thread's complaint is that wins come from swinging until the
opponent dies. A low floor and a high ceiling are not logically contradictory,
so this may be no conflict at all. It is recorded because of *who says what*:
the high-ceiling framing came exclusively from build-guide sites, which have an
incentive to make every class sound deep, and never from an official source or
from player testimony independent of a guide.

### Corrections to prior art - not conflicts

Three items in [`docs/CLASS_RESEARCH.md`](CLASS_RESEARCH.md) needed correcting.
That file is left as written; the corrections live here.

1. **Drop the anonymous S-tier data point.** That file cites "one tier list"
   rating Shadowstrix and Blackarrow as the two S-tier classes, without naming
   it. The Blackarrow pass traced it to SkyCoach, a boosting vendor already on
   this project's exclusion list. It should be dropped entirely rather than
   carried forward as an unattributed data point.
2. **"Withered Knight parries most of its kit" overstates the sourcing.** The
   sources say "many". The direction is right, the degree is inflated.
3. **"Overperforming in solo" is a damage-ceiling statement, not a
   survivability statement.** The official pre-launch language is about burst
   output in high-tier gear matches. It is entirely compatible with the separate
   T3 and T2 finding that Blackarrow is fragile and hard to play solo. The prior
   file's phrasing reads as though the official line settled the whole solo
   question; it settled half of it.

### Resolved by cross-reading, not by new evidence

Two open questions in the six passes were closed by putting the documents side
by side. Neither researcher could have done it alone.

1. **"Zeal" is identified.** The Withered Knight pass quotes a player calling
   Execute "extremely weak compared to others like Zeal" and notes it could not
   identify the ability, guessing another class's finisher. It is Seer's: the
   Blasphemer self-buff **Unleash Zeal**, with "Zeal" appearing officially in
   DevNote #7's "Super Armor effect from Zeal". The player was comparing across
   classes.
2. **The weapon-id counts are corroborated in both directions.** Four classes
   measured two ids here and independently have two officially or
   press-documented weapons; Blackarrow measured one id and independently has an
   official statement that its second weapon ships later. This is genuine
   corroboration - a measurement here agreeing with a T1 statement made
   elsewhere - and it is a different and stronger thing than several wiki sites
   agreeing with each other. Sorcerer is the sole class where the two do not
   line up, which is C2.

## Mercenary (id 10)

Archetypal melee frontline built on durability and fundamentals rather than
combos. Playable as damage, hybrid or tank depending on build and weapon. No
official source uses the word "tank" for it.

### Weapons and stances

Two, and this is the most solidly corroborated fact about the class: **Hammer**
and **Sword and Shield**. Every source at every tier agrees, and the repo's own
measurement of two weapon config ids (`30401`, `30402`) agrees independently. The
official Mercenary Class Reveal Trailer, as covered by GamingBolt (T3 covering
T1 material), describes swapping between a reliable sword and shield and a
hammer with heavy hyper armor.

- **Sword and Shield** leans defensive: blocking, counterattacks, sustained
  trades. Favoured for solo, PvP control and beginners.
- **Hammer** leans offensive and area: crowd control and heavy melee damage,
  with a Super Armor property while charging heavy attacks. Favoured for large
  PvE pulls and team-fight engage.

Guide consensus holds that skills attach to the weapon in hand rather than to a
fixed class bar, so swapping stance swaps roughly half the active kit. **Whether
Mercenary can swap stance mid-combat is not confirmed** - it is inferred by
omission from a general claim that every class except Seer can, and no source
names Mercenary in that context.

### Skills

Officially named in DevNote #7 (T1): **Perfect Parry** (trigger window extended),
**Skullcrusher** (Hammer; mid-air steering after a Level 2 charged smash
improved, PvE damage increased), **Warhammer Sling** (Hammer; Level 1 charge
hitbox detection accelerated), **Shockwave Strike Talent** (tagged Shield
Playstyle; PvE damage increased) and **Block Damage Boost Talent** (tagged Shield
Playstyle; enabled in PvE).

Guide-tier names beyond those, T3 and T4 consensus, no official confirmation:

- Sword and Shield: Stacked Slash, Whirling Cut, Shield Dash, Stonebreaker Slash,
  Impalement, Shield Slam, Perfect Block.
- Hammer: Earthshaker, Hammer Dash, Hammer Spin.

Warhammer Sling is repeatedly characterised as the class's answer to being
kited - a low-energy ranged option most players do not expect a melee class to
have. Destructoid additionally lists "Assault Hammer", "Power Hammer" and
"Punishing Hammer"; those three names appear in no other source checked and
their status is unresolved, so do not treat them as confirmed base-skill names.

**Sword Tip**, the class resource, has two incompatible descriptions in the
wild - see [Fabrications identified](#fabrications-identified), unpublished
numbers. Guides also describe Shield Block and all active skills drawing from
one shared energy bar, with running it dry mid-fight a common way Mercenary
players lose. No official source confirms that mechanic by name.

### How it plays

Fundamentals over combos: block or parry to open a safe window, build Sword Tip
on Sword and Shield or land charged hits on Hammer, spend the payoff when it
opens. Guides describe it as rewarding patience more than any other class.

### Strengths

- Survivability. Perfect Block and Perfect Parry plus Super Armor on Hammer
  charges. Repeatedly called the most durable or joint-most-durable class.
- Genuine versatility - two different weapons rather than one weapon with two
  modes, in contrast to Blackarrow.
- Rated among the strongest solo classes for both PvE and PvP (T3).
- In trios: holds corridors, absorbs first contact, peels for squishier allies,
  protects objective channels.
- Universally rated the best class for a first-time player in the genre. This
  was reached independently by the Mercenary pass and by both agents in the
  earlier Blackarrow and Shadowstrix pass.

### Weaknesses

- **Kited by ranged classes in open terrain**, with Blackarrow and Sorcerer named
  specifically. The most consistent weakness claim found at every tier, including
  a first-party concession from a frustrated ranged player who conceded that
  Mercenary wins if it closes.
- Team-fight liability once a fight extends past the opening trade - a pure
  damage identity with little utility to fall back on.
- Slow by design, not by bug, per developer commentary relayed at wiki tier and
  not independently confirmed at T1 in this pass.
- Loses to a well-geared Withered Knight in high-level duelling, per a single T3
  source, not cross-verified.
- Energy management: blocking and attacking share a resource, so overcommitting
  to blocks leaves nothing to punish with.

### Gearing and gems

Gems replaced random gear affix rolls game-wide (DevNote #6 and Dev Team FAQ #2),
so mid-game power comes from sockets, not drops. Guide-tier direction, offered
as stat families rather than values: stagger resistance and energy recovery on
Shield; stagger contribution and pressure on Hammer; generally Attack, Maximum
Health, Physical Damage, Defense Penetration; for solo, bias to survival and
mobility over raw damage, since living to extract funds more gems than dying
with a perfect damage roll. Whether the two weapons' gem sockets are independent
pools is only gestured at, not confirmed. The August 6 update confirms gem
affixes exist but publishes no affix list, roll ranges, weights, tiers or socket
rules.

### Solo vs group

Strong in both. The real split is duel length rather than mode: strong in short
decisive fights (solo duels, PvE bursts, the opening trade), weaker in fights
that extend, whether that extension happens solo by being kited or in a group by
a team fight lingering. Commonly built into a balanced trio with Sorcerer and
Seer, or with Shadowstrix and Seer.

### Patch history

- **2026-07-24, DevNote #7** (T1, pre-launch): all buffs. Perfect Parry window
  extended; Skullcrusher air-steering and PvE damage; Warhammer Sling hitbox;
  PvE damage and enablement on two Shield-playstyle talents.
- **2026-07-30 01:00 UTC:** launch.
- **2026-08-06, August 6 Live Update** (T1): the only Mercenary content is a bug
  fix - Sword and Shield triggering auto-blocks under specific circumstances.
  Not a balance change.

**Net: no post-launch balance patch as of 2026-08-09.**

### Tier placement

Best-verified placement is GameRant, published 2026-08-02 21:53 EDT, **A-tier**,
with an explicit breakdown: strong in solo duels, a liability in extended team
fights, superior in PvE against stationary targets. That date is after DevNote #7
and before the August 6 patch. Other placements, dates not individually
confirmed: Destructoid and GamerBlurb S-tier, KeenGamer and Mobalytics A-tier,
GAMES.GG B-tier. Spread is A to S among attributable outlets, never below B
anywhere. A beta-era list self-labelled "Open Beta 3, updated Jun 17 2026" is
excluded on its own stated date. Because the August 6 patch contained only a bug
fix for this class, the A-tier placement plausibly still holds - that is an
inference from patch content, not a citation.

### Difficulty

Lowest skill floor of the six, agreed independently by Destructoid, Deltia's
Gaming, Mobalytics, KeenGamer and the general tenor of Steam discussions. The
ceiling claim is disputed, see C13.

### Open for this class

- Sword Tip's exact structure - one six-stack threshold, or a two-tier
  progression. Sources disagree, neither is official.
- Whether it can swap stance mid-combat.
- Whether Hammer and Sword and Shield gem sockets are independent pools.
- No authoritative full skill list exists anywhere; every one found is a
  reconstruction and they disagree with each other.
- The in-combat resource bar's official name. "Energy" is guide convention.

## Sorcerer (id 11)

Ranged elemental and arcane caster. Highest or among the highest ranged damage at
launch, with real area control and two answers to pressure that are not simply
running away.

A sourcing note on its own identity blurb: the widely repeated description of
Sorcerers wielding complex spells through arcane chants, gestures and magical
tools appears near word-for-word across many independent-looking guide sites,
which by this project's doctrine makes it one source being copied. It reads like
press-kit or trailer copy and an official Sorcerer Class Reveal Trailer does
exist, but no pass could fetch that video's own description to confirm the
wording originates there. Treat the blurb as probably official-derived, not
confirmed official.

### Weapons and stances

**Staff, with two spell branches: Elemental and Stardust.** DevNote #7 (T1)
discusses the entire pre-launch Sorcerer pass under a single "Staff" framing
split into those two named playstyles. It never describes them as two weapons or
two stances the way it describes Mercenary's Hammer and Sword and Shield or
Shadowstrix's Dagger and Dual Blades.

Guides converge on Staff-only, with Elemental as fire, ice and thunder - faster
casts, lower per-hit damage, stacking effects - and Stardust as gravity, meteor
and zone control - slower casts, higher raw damage. The commitment is per
loadout, not per fight (T3 and T4).

A minority of guides use "staff versus focus" language implying a second item
called Focus. Investigated specifically: the term is used inconsistently,
sometimes as a build or affix category, never clearly as a named second weapon,
and no official source uses the word for Sorcerer at all. It looks like informal
guide-writer shorthand. Flagged so it is not mistaken for a lead.

**The single-weapon question is NOT ESTABLISHED and is not closed here.** The
repo measured exactly one weapon config id (`30503`), matching Blackarrow's
pattern. No official source confirms or denies a second Sorcerer weapon; whether
one exists in an official post is itself disputed (C2). The better-supported
reading is that Sorcerer is genuinely single-weapon at launch, but
better-supported is not settled, and nothing found proves the character-creation
walk did not simply miss a second id. **Do not write "Blackarrow is the only
single-weapon class" anywhere.**

### Skills

Elemental branch. Officially named in DevNote #7 (T1): **Fire Bolt** (can
fast-cast with no channel even when Energy is depleted), **Crystal Icebolt**
(cooldown now starts when the projectile fires rather than on cast; base cooldown
reduced, no value published), **Thunderstrike** with talents **Thunder Pierce**
and **Furious Thunder** (hitbox enlarged, same fast-cast treatment),
**Deep Freeze** (activation sped up), **Windcraft** (area coverage and cast speed
improved), **Arcane Armor** (channel time shortened). **Flameblade** appears in
the official Known Issues post for a visual effect not matching its damage area.

Guide-tier only (T3, T4): Cryptic Ward - stops enemy telegraphed heavy attacks
outright and functions as a perfect block against melee, stunning and knocking
back the attacker; Forbidden Gate - a directional barrier blocking incoming
projectiles while allies fire through it from the Sorcerer's side; Phantom Step -
mobility and repositioning.

Stardust branch. Officially named: **Meteor Charm** (same fast-cast treatment;
a bug preventing use of the fully charged version was fixed 2026-08-06),
**Stardust Tempest** (cooldown reduced and damage increased, called out as making
it far more threatening). Guide-tier only: Gravitational Vortex, Meteor Impact
(relationship to Meteor Charm unresolved), Shadow Veil (**disputed ownership,
see C3**).

**Chant Guard**, a talent, reportedly had an in-game description corrected to
clarify it increases Chanting Speed specifically for Stardust spells. The pass
that found this could not pin the exact thread and relied on an aggregate search
result. Weakly sourced, carried forward rather than dropped.

System-level, official: the pre-launch kit's chain crowd control from Ice-branch
skills was called unhealthily oppressive in extreme scenarios and received the
single biggest reduction in that balance pass. Qualitative, no value given for
either the old or new behaviour.

### How it plays

Commit to one spell school per loadout and play the range. Elemental is faster
and safer and more forgiving; Stardust is slower and higher-commitment with
bigger single hits and area denial, and is repeatedly described as needing
teammates to cover the long wind-ups. Unlike Blackarrow it carries its own peel
tools rather than relying purely on kiting distance.

### Strengths

- Highest or among the highest ranged damage at launch. Developers themselves
  reportedly called it the most OP class at the moment in balance discussion
  relayed via Steam Community content (T2 or T3, consistent across sources).
- Strong area control - several named area and zone tools plus hard crowd
  control even after the pre-launch ice nerf.
- Two real answers to being approached: Cryptic Ward's perfect block and stun,
  and Forbidden Gate's projectile wall.
- Rated S-tier by non-wiki outlets, and particularly strong in confined PvP
  spaces per direct player testimony - a Steam thread from 2026-07-30 calls for
  a nerf centred on area burst being very hard to escape in tight spaces,
  especially with multiple Sorcerers stacked on one team.

### Weaknesses

- Very low health pool. See C4 - the superlative is disputed against Shadowstrix.
- Hard-countered by melee gap-closers. Destructoid names Shadowstrix flanking
  from stealth and a charging Mercenary specifically.
- Stardust is high-risk: long cast and chant times, dangerous solo, much safer
  with peel.
- High floor for its defensive kit. Cryptic Ward and positioning discipline are
  explicitly the difference between a Sorcerer that survives being approached
  and one that does not.

### Gearing and gems

Guide consensus (T4 cluster, counts once): commonly recommended affixes are
Eloquence, Ranged, Elusive, Valor and Stoic, described as broadly strong picks
rather than Sorcerer-exclusive. Priority is survivability and cast consistency
first, raw damage second - the framing is that a Sorcerer dies to interrupted
chants, not to missing damage, so gems protecting cast stability, energy
recovery, control duration and movement between casts come before damage
sockets, with damage added once a build has peel support. No gem drop rates,
socket counts or stat values are published.

### Solo vs group

Disputed - see C7. Trio reasoning is consistent regardless: Stardust's slow,
high-commitment casts become much safer with teammates peeling, and a commonly
cited balanced trio pairs Sorcerer's ranged damage and control with a Mercenary
frontline and a Seer healer.

### Patch history

- **2026-07-14, Community AMA** (T1): no Sorcerer-specific weapon or balance
  content beyond a blanket statement that balance will be tuned on live data.
- **2026-07-24, DevNote #7** (T1): the substantive pre-launch pass, listed under
  Skills. Net framing across sources is that it buffed Sorcerer overall despite
  the one crowd-control nerf.
- **2026-07-30, Known Issues** (T1): a Sorcerer casting-tutorial key-prompt bug
  in some languages, plus the Flameblade visual mismatch.
- **2026-08-06, Live Update** (T1): the only Sorcerer line is a bug fix, the
  charged Meteor Charm being unusable under certain conditions.

**Net: Sorcerer's balance has been untouched since the launch build.** Recorded
with a methodology note the researcher volunteered: a first pass at the August 6
notes mis-attributed an energy-cost reduction and two bug fixes to Sorcerer that
actually belong to Withered Knight, and a second section-preserving re-fetch
corrected it. That is the misattribution failure mode this repo warns about, and
it was caught only by re-reading the primary source.

### Tier placement

KeenGamer (T3, 2026-07-30): **S-tier, the best overall class**, on ranged damage,
area control and escape tools; the article states it reflects the launch build
including the final pre-launch balance update. Destructoid (T3, 2026-08-03,
updated 2026-08-04): no letter grade, frames it as strong overall with immense
DPS potential while marking it worse than Mercenary and Withered Knight solo.
GameSpot: a headline strongly implying Sorcerer, body inaccessible (HTTP 403),
date unconfirmed - headline-only, low confidence. T4 cluster: S-tier, counts
once. Nothing dated after 2026-08-06 was found, though since that patch did not
touch Sorcerer's balance there is no mechanical reason for opinion to have
moved. Community sentiment was calling for a nerf as of 2026-07-30 that has not
been delivered.

### Difficulty

High floor and high ceiling for a ranged class, not a point-and-click caster.
Requires disciplined positioning, elemental sequencing and cooldown management;
low health makes positioning mistakes immediately fatal; the whole plan collapses
if melee closes. Stardust is consistently the harder school, with Elemental
recommended as the more forgiving start. All difficulty claims are T3 and T4;
no official source quantifies difficulty.

### Open for this class

- **The single-weapon question** - design choice or capture gap. The core open
  item, and the re-walk is what closes it, not more press coverage.
- Whether an official statement about a second weapon exists at all (C2).
- Which class Shadow Veil belongs to (C3).
- The relationship between Meteor Charm and Meteor Impact.
- Whether "Focus" is a real second item or guide shorthand.
- Interrupt rules for chants beyond the qualitative framing.
- Whether the Chant Guard description fix is accurately captured here.

## Blackarrow (id 12)

The dedicated ranged archer: bow, third-person manual aiming, traps and
specialised arrow types. Class id 12 is the strongest binding in the repo -
pixel-joined **and** operator-attested.

A naming trap worth knowing: "Archer" is used two ways in the wild, informally
as a nickname for the whole class, and formally as one of the two in-kit ammo and
playstyle families. At least one build guide title conflates them.

### Weapons and stances

**Bow only at launch.** Verified verbatim from the primary source, DevNote #7
(T1, 2026-07-24): "Due to development timelines, the Blackarrow's new weapon will
launch in a future season - thanks for your patience on that one!" The Steam
store page's generic "each mastering two unique weapon stances" line carries no
per-class carve-out; Blackarrow is its unstated exception. The repo's own single
measured weapon id (`30504`) corroborates the official statement independently,
which is worth more than the statement alone because it was measured here.

**Archer and Hunter are ammo and playstyle families on the one bow, not
stances.** Destructoid's build guide buckets the arrows into Archer's Arrows and
Hunter's Arrows with a separate Weapon Skills bucket outside both. Structural
support beyond the naming: both Splatter Arrow and Featherlight Arrow are
described as having no cooldown and no energy cost, consistent with arrows being
basic-attack ammo modifiers while the separately bucketed Weapon Skills carry the
real cooldowns. GamerRant sorts the same skill pool into its own PvP and PvE
split, which is that guide's build-advice organisation and not a second official
axis.

The second weapon's **name is not officially confirmed**. See
[Fabrications identified](#fabrications-identified) for the "Javelin" claim.

### Skills

By name only, qualitative. Compiled from Destructoid, GamerRant and KeenGamer
(all T3).

**Archer's Arrows**, charged-burst family: Steel Arrow (pierces one additional
unit behind the target); Concussive Arrow (staggers and knocks back at full
draw); Lightning Arrow (chains between enemies, reduced damage per jump);
Bloodfly Arrow (continuous damage, with part reportedly landing as True Damage
against defensive targets); Splatter Arrow (no cooldown, no energy, area splash
on impact; draw time increases splash radius, splash hits softer than a direct
hit; carries the Sepsis talent bonus).

**Hunter's Arrows**, status and trap family: Soundwave Arrow (also called Sonic
Arrow by one source, same ability, no official name confirmed either way) reveals
enemies in the area; Barbed Arrow (extra damage against dodging enemies, plants a
ground trap); Paralysis Arrow (mist causing exhaustion and skill lockout); Spore
Arrow (mushroom construct, contact damage, detonatable); Featherlight Arrow (no
cooldown, no energy, unaffected by gravity, high travel speed).

**Weapon Skills**, the true cooldown-gated kit: Scattershot (seven-arrow spread
with knockback, repeatedly named as the answer to melee closing); Rapid Arrows;
Sky Piercer (heavy charged piercing shot); Frostblight Bomb (area freeze opening
a charged follow-up); Shadow Step (short reposition and escape); Impact Grenade
(sticks to units or terrain, knockback scaling with proximity to the blast);
Predator's Senses (named once, no description found anywhere - thin).

### How it plays

Establish distance, make the opponent spend resources approaching, punish the
approach, reposition before being locked into a bad trade. Its speed stat is
**Charging Speed, not attack speed** - no source in any pass used the term attack
speed for this class.

**Range is a real tension in the evidence.** Marketing-toned guide copy claims
the highest or longest effective range of any class. Player testimony says the
range that matters in a fight is short: to deal good damage with a heavy shot you
cannot be further than about two dodges' distance, and about one for uncharged
shots. That testimony was independently re-derived in the deep-dive pass rather
than inherited, but **the exact thread could not be re-opened - it surfaced
through search synthesis, so it is T2 by origin with a citation gap that is still
open.** The reconciliation offered, not asserted: nominal arrow travel and
scouting utility are plausibly long while effective damage range is short, and
conflating the two is exactly the error the wiki tier makes elsewhere. **It is
not a sniper in the damage-range sense.**

One low-confidence mobility note: a T4 source excluded a dash-evade interaction
bug from its rankings pending a developer-confirmed fix, plausibly the same bug
the August 6 patch fixed. If so, part of pre-patch Blackarrow's perceived
strength may have been a mobility bug on top of intended power. Texture only.

### Strengths

- High single-target and burst damage when shots land clean.
- Scattershot as the specific tool that punishes melee for closing.
- Strong in open space against melee. The counter-read runs the other way in
  tight space.
- Named as Shadowstrix's hardest counter, reconfirmed from the Shadowstrix side
  ("can counter Stealth and attack from difficult positions"). Note the axis
  distinction so it is not misread as conflicting evidence: a melee-side player
  separately claims a high escape rate *with* Shadowstrix *from* Blackarrow.
  Winning the fight and being unable to disengage are different claims.
- The most emphatic testimony comes unprompted from the melee side: one player
  calls it the only class they have no chance against if the enemy is any good,
  and advises fighting it only in tight spaces.

### Weaknesses

- Low survivability, confirmed by multiple independent guides including one
  published the day before the nerf - so the perception predates and is separate
  from the August 6 damage change.
- Mostly weak at close range, called completely ineffective once melee closes.
- The full-draw charge mechanic punishes panicked shots under pressure.
- Stamina and resource management is a named failure point from the melee side
  too: forcing a Blackarrow to keep moving to recover is cited as how to beat it.
- **Gear-hungry**, and this has an unusually strong source: the official
  pre-launch language describes its arrows as having become overbearing in
  high-tier gear matches. That is the developers' own stated reason for touching
  the class before launch, which is stronger corroboration than a general claim.
- Thin escape kit: Shadow Step, dodge charges, Scattershot knockback, traps.

### Gearing and gems

**Terminology flag for Emberforge's data model.** Guide sites uniformly say
"affix" for Blackarrow's gearing stats - Ranged, Focused, Elusive, Fervid, Curse,
Valor, Fervor - but gems replaced random affix rolls per DevNote #6 and Dev Team
FAQ #2. These community "affixes" are almost certainly gem effects wearing legacy
ARPG vocabulary. Not one guide was found using "gem" and "affix" consistently
side by side for the same mechanic, so the community's language has not caught up
to the official change. **Keep "affix" and "gem" distinct in Emberforge's schema
rather than assuming guide vocabulary maps onto dev-note vocabulary.**

Top picks, reconfirmed with more detail than prior art had: **Ranged** (damage at
distance), then **Focused** (raises charging speed and, past a threshold,
movement speed while charging). Then Elusive (reduces dodge energy cost, named as
important alongside Fervid), Curse (extends debuff duration, called essential for
debuff builds using Splatter, Bloodfly and Lightning arrows), with Valor and
Fervor as secondary picks with no detail found. Socket priority per guide
consensus, not official: movement, stagger resistance and resource recovery on
shots before raw damage, on the reasoning that archers lose runs when caught
during swap animations.

### Solo vs group

The least settled section for this class, and it stayed unsettled after
independent digging.

**For solo strength:** the official pre-nerf acknowledgment that it was
overperforming in solo, specifically in high-tier gear matches - the strongest
single data point and the only official one. KeenGamer's build guide, published
2026-08-08 and therefore *after* the nerf, still lists solo PvPvE, boss fights
and trio play as its best modes without qualification - though it never mentions
the nerf, so the silence cannot be read either way.

**Against solo strength:** Destructoid (2026-08-02, pre-nerf) calls survivability
very low and solo play explicitly difficult. The original Steam complaint thread
(2026-08-01, pre-nerf) reports weak damage, poor survivability and an
insufficient escape kit, though the same thread contains pushback and notes
Blackarrow players are common on leaderboards. One T3 synthesis (direct fetch
blocked) says it leans on a squad more than it carries solo.

**Adjudicated read:** the official acknowledgment settles the damage-ceiling half
of the question, not the survivability half. The class can be both a glass cannon
that was hitting too hard solo and subjectively unforgiving to play solo, because
peak output and floor are different claims. Prior art conflated them; see the
prior-art corrections above.

### Patch history

| Date | Post | Blackarrow content |
|---|---|---|
| 2026-04-12 or 2026-04-14 | DevNote #5 | Combat overhaul, dodge decoupled from Energy. Not class-specific. Date disputed between passes. |
| 2026-06-09 | DevNote #6 | Gems replace affix rolls. Not class-specific. |
| 2026-07-24 | **DevNote #7** | Pre-launch pass: solo performance described as slightly overturned; special arrows overbearing in high-tier gear matches; Sepsis talent on Splatter Arrow gated behind a full charge; no-cost arrow talents rebalanced toward their intended playstyle with a small power buff; second weapon confirmed for a future season. |
| 2026-08-05 | Roadmap and Launch Rewards: Wave 3 | 1 million players, Solo Mode announced for September. **No weapon name**, despite being the likeliest place for one. |
| **2026-08-06** | **August 6 Live Update** | **The nerf**, verbatim from the primary source: "Removed the impact effect from uncharged shots, and slightly reduced the impact of fully charged shots." Same patch: fixed abnormal displacement when jumping after a side dodge, and fixed a collision prompt appearing abnormally when aiming at Stealthed units. |
| 2026-08-07 | August 7 Server Online Update Notice | Server-side. No Blackarrow change, but it touches the Focused affix that Blackarrow relies on, via a Withered Knight weapon bug. |

Nothing dated 2026-08-08 or 2026-08-09 exists in the official feed. **August 6
remains the last Blackarrow balance change; August 7 is the last patch of any
kind.** The August 6 nerf had a pre-launch predecessor: DevNote #7 already
described its solo performance as overturned before the game shipped, so August 6
was the second touch, not the first.

Two data-quality notes carried forward from the pass. First, the news feed also
returned an item dated November 10, 2026 sorted ahead of items from earlier in
August; it postdates today so it cannot be a published patch note, and it was
relied on for nothing - flagged so a future session does not trip on it. Second,
**the full verbatim text of DevNote #7's class-balance section was never read end
to end** - four fetch attempts truncated on a roughly 8500-word document. Those
quotations are corroborated by two independently-run searches landing on
consistent wording, and are T1 by origin, but they are held at slightly lower
confidence than the August 6 quotation, which was read directly.

### Tier placement

**Pre-nerf, and therefore unable to reflect the patch:** a beta-era list
self-labelled "Open Beta 3, updated Jun 17 2026"; Destructoid's tier list, which
is self-labelled "(Launch)"; GamerRant 2026-08-01 and Destructoid's build guide
2026-08-02.

**Post-nerf:** KeenGamer's build guide, 2026-08-08, rates it across solo, trio
and boss content without caveat but never engages with the patch. One tier-list
source states community consensus places it in A-tier alongside Mercenary and
Withered Knight post-patch, contrasted explicitly against pre-nerf S-tier claims.

**The S-tier claim is now traceable and excludable by name** - it is SkyCoach, a
boosting vendor on this project's exclusion list. Drop it rather than carrying it
forward. Independent non-excluded outlets place it at A-tier, though GameSpot and
Mobalytics fetches were both blocked (HTTP 403), so those two attributions rest
on search snippets.

**Bottom line: "top-half post-nerf" is defensible; "S-tier" is not.**

### Difficulty

High floor and high ceiling. Body shots do minimal damage and headshots are hard
to land on moving targets; the full-draw mechanic punishes panic shots
specifically under pressure; it requires strong positioning and map knowledge and
is described as less forgiving for beginners than Mercenary or Sorcerer. A claim
that it has the highest damage ceiling of any class traces to the same excluded
vendor as the S-tier claim and is treated as unconfirmed for the same reason.

### Open for this class

- The second weapon's real name and date. "Future season" is all that is
  official.
- Whether Archer and Hunter is a hard talent lock or a power gradient. Official
  language says "playstyles", never "branches" or "locked".
- Predator's Senses - named once, never described.
- The exact source thread for the dodge-length range testimony.
- The full verbatim text of DevNote #7's class-balance section.
- Whether the dash-evade bug one T4 source flagged is the one August 6 fixed.

## Shadowstrix (id 13)

The stealth-assassin archetype: a highly mobile melee class built to choose when
a fight starts, kill a vulnerable target before the rest of the enemy team can
react, and disappear. Crow and shadow imagery throughout. Class id 13 is
pixel-joined, and `"classId":13` has since been observed live in the roleInfo
payload the game emits on adventurer init, so a second character exists on the
account beyond the class-12 main.

### Weapons and stances

**Two real stances**, confirmed both first-party (two weapon config ids,
`30505` and `30506`) and by every community source checked.

- **Dagger** - stealth entry and single-target assassination. Grants the innate
  Sneak skill, plus Shadow Strike and Flash Stride for repositioning, and Shadow
  Wheel Slash. Described consistently as the PvE-meta stance.
- **Dual Blades** - sustained combo damage, Wound stacking, and mobility
  including a teleport. Described as the PvP-meta stance for fast burst.

**Stealth is Dagger-only.** No stealth skill appears in any Dual Blades skill
list in any source checked, and this is genuine corroboration rather than one
copied claim: KeenGamer's skill-by-skill breakdown and multiple wiki class pages
agree on the same split. Held at T3 and T4 - no official source states it.

### Stealth mechanics

- **Entry:** hold both mouse buttons, which crushes crow feather dust and places
  the Shadowstrix in Stealth. Consistent across multiple guides; no T1
  confirmation.
- **Shadow Veil:** a second, related state, described as entered by exiting
  Stealth while attacking with a dagger, granting a semi-stealth that confuses
  PvE enemies and makes player detection difficult. **Its class ownership is
  disputed - see C3.**
- **Breaking and detection:** sources consistently say stealth can be broken by
  "certain skills" and by proximity, never with a number. No detection radius is
  published anywhere. Prior art says "reveal consumables"; this pass's sources
  say "certain skills". These may be the same fact described two ways or a real
  discrepancy - **unresolved, newly identified.**
- **No stealth duration in seconds exists anywhere**, official or otherwise.
  Every source uses vague phrasing. Worth stating positively: the pass went
  looking specifically for a fabricated number here and did not find one in the
  sources it fetched. That is not a certification that none exists on any of the
  roughly fifteen wiki-farm sites, only that none surfaced.
- Whether incoming damage breaks stealth is **still unpublished**, and this pass
  did not resolve it either.

### Skills

**Dagger:** Sneak (enters Stealth); Shadow Strike (leaves an afterimage and
dashes through the enemy, the shadow returning after a delay); Flash Stride
(forward dash-attack damaging along its path); Shadow Wheel Slash (three-stage
attack with branching follow-ups, restoring Energy on branch hits);
**Element of Surprise** (talent - a dagger backstab landed while in the Stealth
or Shadow Veil state is always a critical hit); **Lurking Blow** (talent -
Physical damage increase and Energy regen on exiting Stealth with a Dagger,
reduced slightly in DevNote #7).

**Dual Blades:** Inspiring Impale (thrust, restores Energy on connection);
Spinning Slash (burst dash, activates a damage bonus); Bloody Blade Dance
(channeled multi-hit, deflects projectiles); Fang Rush (post-dodge dash,
consumes or stops Dodge Energy recovery while active; hitbox optimised in
DevNote #7); Flurry Strike (moves back then dashes forward, chargeable); Phantom
Shift (teleport with a temporary movement speed boost); **Wound** (a stacking
effect applied by Dual Blades attacks that detonates into True Damage at a
threshold - the threshold count is guide-tier only, see unpublished numbers).

**Class-wide:** Crow Storm (area attack with a stun component, the ability at the
centre of the chain-crowd-control complaint); Blackout (talent, interacts with
Crow Storm to create group stun-lock opportunities in trios).

"Ambush Momentum" appeared exactly once, in a low-confidence auto-summarised
search pass, and could not be corroborated in any direct fetch or any other
search. **Treat as unverified and possibly spurious.**

### How it plays

Pick an isolated, low-defense target - guides name Seer, Blackarrow and Sorcerer
as priority prey - open from Stealth for a guaranteed crit via Element of
Surprise, burst with a Dual Blades combo and Wound or Dagger follow-ups, then
disengage before the enemy party can respond. Rewards patient target selection
over aggression. A botched combo or a failed disengage generally cannot be walked
back given the health pool.

### Strengths

- Chooses its fights. Stealth plus mobility means opting into favourable
  engagements and declining unfavourable ones, unlike classes that must react to
  being found.
- Guaranteed-crit opener rewards a clean approach with a large single burst.
- Best-in-class solo kill pressure on squishy targets.
- High mobility kit doubling as escape tooling.

### Weaknesses

- Among the lowest health pools and lowest survivability. See C4 for the
  superlative dispute.
- Loses a straight fight to heavy melee. Mercenary and Withered Knight are named
  repeatedly, because they force close-range trading, its weakest exchange.
  Withered Knight specifically can parry **many** of its abilities and punish
  failed combinations - note "many", not "most", is what sources actually say.
- Blackarrow is a strong counter. The relationship is corroborated in both
  directions; the "worst enemy" superlative in prior art is not independently
  found in any fetched source.
- **Weak in hard PvE boss fights**, because the kit is built around choosing
  engagements rather than surviving forced ones. New detail beyond prior art.
- Highest execution demand in the roster, which is a real weakness in the sense
  that mistakes cost more for this class than for others.
- Crow Storm's chain-crowd-control and stun-lock potential remains a live
  community complaint, and the complaints postdate the pre-launch nerf, so they
  are about the class as it stands now.

### Gearing and gems

KeenGamer (2026-08-04) is the most detailed source found. **Crit stats are
explicitly de-emphasised**, ranked roughly tenth, behind Physical Damage, Attack,
Defense Penetration, Maximum Energy and Movement Speed in that order. The
reasoning: the guaranteed crit from Element of Surprise already covers the
opener, so further crit investment has a lower marginal payoff than raw physical
and penetration. This confirms prior art and adds Max Energy and Movement Speed
as also outranking crit, which prior art did not record.

Named gems, qualitative: Fervor (repeated hits stack physical and magic damage,
higher levels add Defense), Valor (Attack, plus Defense Penetration at a higher
breakpoint), Vitality (Maximum Energy, prevents one Energy Overdraft), Elusive
(reduces Dodge Energy cost), Seeker (Movement Speed after landing a hit), Fervid
(damage while Health is above a threshold), Smiting (Critical Hits restore Energy
and reduce cooldowns).

A wiki claims Bellring shared an official beginner Dagger loadout in Discord.
**Treat as wiki-attributed-to-official, not confirmed official** - the Discord
post could not be reached. This is the same shape as the Mercenary fabrication
catalogued below, though with no invented numbers attached.

### Solo vs group

**Disputed - see C1**, which is the single largest cross-document conflict in
this merge. Do not cite either version until Mobalytics is read first-hand.

### Patch history

Verified item by item against the official Steam news feed through 2026-08-07.

- **2026-07-24, DevNote #7** (T1, pre-launch): named Shadowstrix specifically for
  overwhelming crowd-control chains and excessive mobility on certain skills.
  Crow Storm can no longer stack on players who are already stunned, and its
  damage was slightly reduced; Fang Rush hitbox optimised; Pursuit Strike and
  Jumping Pursuit Strike mobility toned down. It reportedly received the
  strongest language of any class in that pass.
- **2026-07-30 17:04 UTC, Launch Rewards and July 30 Update:** no Shadowstrix
  content. This is the live-build patch that shipped DevNote #7's changes.
- **2026-08-06, August 6 Live Update:** **no Shadowstrix content.** Verified by
  two independent targeted fetches. That patch touched Blackarrow, Withered
  Knight, Mercenary and Sorcerer only.
- **2026-08-07, Server Online Update Notice:** no Shadowstrix content.

**"Untouched by every patch since launch" is CONFIRMED**, now backed by an
item-by-item reading rather than a general impression.

A methodology flag the pass volunteered, recorded so nobody re-derives the error:
an early search-summarised pass briefly mis-attributed the Crow Storm and Pursuit
Strike changes to the August 6 patch rather than to DevNote #7. Two more targeted
fetches corrected it. Left uncorrected it would have produced a false
"patch landed" finding that directly contradicted the untouched-since-launch
result.

First-party player evidence (T2) confirms the live complaint: a 2026-08-01 thread
argues Crow Storm still delivers a long stun plus heavy damage on a short,
spammable cooldown with little counterplay and can combo into a full-health kill.
A second thread makes the same complaint about area attacks that stun. Both
postdate the pre-launch nerf.

### Tier placement

Because the class received no changes on 2026-08-06, its position relative to
itself is unchanged across that boundary by construction. Its position relative
to the field could still have moved, since one direct solo rival, Blackarrow, was
nerfed that same day - **that is inference, not a sourced claim.**

- **Pre-August-6:** KeenGamer's launch tier list places it S-tier, the most
  common PvP number one for stealth and burst.
- **Post-August-6:** no tier list explicitly dated after the patch was found.

Prior art's claim that Shadowstrix's tier lists are "all post-nerf and therefore
current" is true **in the specific sense that nothing has changed for the class
since DevNote #7**, not because a fresh post-August-6 ranking was found. One
search synthesis describing it as by far the strongest class in current guides
could not be pinned to a dated source and is treated as unverified colour.

### Difficulty

Consistently described as the highest or among the highest in the roster. Widely
called the hardest class to master; punishes positioning mistakes harshly; no
health buffer to cover a misplay. Specific high-execution mechanics named: Shadow
Strike's delayed afterimage return, and Wound stack timing on Dual Blades. The
gap between a new and an experienced Shadowstrix is described as larger than for
other classes - which is the basis for the operator's recorded decision to take
it as a second character rather than a first.

### Open for this class

- Solo versus trio, and what Mobalytics actually says (C1).
- Whether incoming damage breaks stealth.
- The exact detection mechanism and radius for proximity.
- Reveal consumables versus "certain skills" - newly identified discrepancy.
- Whether Shadow Veil is Shadowstrix-exclusive (C3).
- Whether "Ambush Momentum" is real.
- Whether any tier list has been re-dated after 2026-08-06.

## Seer (id 14)

Support and battlefield control - **not** a pure healer, **not** a summoner, and
not a damage class, though one of its two weapons is a melee debuff duelist. The
official class-intro post frames its two specialities as protective utility
(shielding allies, concealing them, preventing fatal blows) and a more aggressive
approach (binding enemies to the ground and blinding them). Both are control
functions, one ally-facing and one enemy-facing. Healing is one tool among
several, not the headline.

On "summoner" specifically: Dev Team FAQ #2 (T1) answers a player question about
a dedicated summoning class with "There are currently no plans for this", citing
battlefield chaos from stacked summons. Seer's Rune Pillar is a stationary,
destructible Construct that can auto-attack, which gives it summon-adjacent
flavour, but the developers rule out summoner as any class's core identity.

A terminology caution: the 2025-03-23 class-intro post describes Seers consuming
"energy charges", while the launch kit's named resources are Psionic Energy
(Reverent) and Curse Mana (Blasphemer), and Dev Team FAQ #2 separately confirms
the general Energy system was reworked before launch to remove an Exhaustion
penalty. **Whether the 2025 language maps onto the launch resources is not
established.** Treat the shape as durable (a resource gates skills, bigger
effects cost more); do not assume the naming carried through a year-plus gap.

### Weapons and stances

Two, officially named in DevNote #7: **"Seer - Catalyst"** and **"Seer - Mace"**,
matching the two weapon config ids measured here (`30507`, `30508`). No
contradiction. The official terms for the two paths are also used directly in
that post: a **Reverent** Seer (Catalyst, the support stance) and a
**Blasphemer** Seer (Mace, the curse-melee duelist stance). GameRant frames the
in-fiction hook as renouncing the oath, which switches the catalyst to a mace.

- **Hard lock, not a mid-fight swap.** Mobalytics states plainly that a Seer
  cannot switch between Reverent and Blasphemer in a match and must choose
  beforehand. **T3, not official** - but nothing contradicts it. If true this
  makes Seer's stance choice a harder commitment than any other class's.
- DevNote #7's language implies named sub-paths within each weapon, but only two
  were found: a "Support playstyle" under Catalyst (core talent Ebb and Flow) and
  a "Super Armor playstyle" under Mace (core talent Relentless). Whether each
  weapon has a second, unnamed talent path is not established.
- **Which id is Catalyst and which is Mace is not established.** The pixel-join
  method used for class ids has never been run for weapon ids on this class. The
  same method should work.

### Skills

Names in bold appeared verbatim in an official post. Others are attested by
Mobalytics (T3), cross-checked against GameRant (T3) and Steam Community posts
(T2).

**Reverent (Catalyst):** Psionic Orb (chargeable basic ranged attack; landing it
feeds Psionic Energy). Rune Summon plants a **Rune Pillar**, an explicitly
destructible Construct with a limited active window, and the selected rune
changes what it does: **Punishment Rune** (auto-attacks the lowest-HP enemy in
range, prioritising players over monsters; the kit's main damage tool),
**Healing Rune** (heals allies in range, limited uses per match), Shelter Rune
(shields allies, with continuous extra shielding for whoever is lowest), Stealth
Rune (grants allies Stealth that persists through taking damage), Burst Rune
(impact hit refunding Psionic Energy per player hit, marks targets for a delayed
follow-up plus stagger), Binding Rune (immobilises and blocks jumping, refunds
energy per enemy caught), Intimidation Rune (instant cast, no energy cost, knocks
back nearby enemies - one of the kit's best panic buttons precisely because it is
free and instant), Windwalker Rune (boosts ally dodge distance, shortens enemy
dodge distance).

Divine Arts, used like normal ability-bar skills: Wind Surge (knockback cone),
Healing Art (a second limited-use heal, mutually exclusive with Psionic Shield),
Blinding Rune (obstructs the screen of any enemy facing it after a short delay),
Psionic Shield (stacking-charge ally shield scaling off the caster's Attack,
mutually exclusive with Healing Art), Death Ward (grants Super Armor and prevents
death outright for nearby allies).

**Blasphemer (Mace): Rune: Heavy Strike** (a forward leap; when Curse Mana is
full it upgrades into "Rune: Enchanted Heavy Strike" and takes on the selected
rune's effect) with **Rune: Drain** (magic damage with lifesteal plus a short
attack-down debuff - called a strong dueling answer to melee DPS classes),
Rune: Sweep (wide sweep, the best burst option among the runes), Rune: Ankle Cut
(shockwave; direct hits immobilised, wider shockwave slowed),
**Rune: Corruption** (magic damage plus healing reduction; situational, best
against enemy teams also running a Seer), Rune: Stun. Plus **Shapeshift** (short
transformation granting heavy movement speed and stagger immunity, next attack
becomes a dash-strike), **Thorn Sigil** (immobilises then slows and ticks damage;
strongest in tight spaces), Impact Sigil (delayed sigil drawing enemies toward
the Seer), **Paralysis Curse** (roots the Seer to cast; a second press fires a
slowing bolt; a commitment, not a poke), and **Unleash Zeal** (self-buff raising
Attack and Defense, a hyperarmor window, at the cost of pausing Curse Mana
regeneration).

One player term did not corroborate anywhere: "Prophet", used by a Steam
commenter as if it were a named talent or build archetype. No other source uses
the word for Seer. Flagged as possibly informal.

### How it plays

Two genuinely different playstyles behind one class-select entry.

- **Reverent** plays at range, managing Psionic Energy to plant and reposition a
  stationary Construct while poking with a chargeable orb. Officially: faster
  skillcasting than most classes, slower basic attacks than close-combat
  specialists. Success is about *where* the pillar goes and *which* rune is
  loaded, not about aim in the FPS sense.
- **Blasphemer** plays as a curse melee duelist: gap-close with Shapeshift, land
  control, then spend a burst window under Unleash Zeal for a hyperarmor duel it
  is favoured to win before the buff expires and Curse Mana regeneration stops.

Both are control-first rather than sustained-damage-first. Even the offensive
path's win condition runs through immobilise, slow and stun chaining into a timed
buff window, not through raw weapon damage.

### Strengths

- **Officially** stated to have faster skillcasting than most classes.
- **Officially** stated to scale with player proficiency: experienced Seers
  extend the duration of their effects and amplify healing and damage. DevNote #7
  corroborates this for Reverent specifically, and says it is why the developers
  chose not to touch its offensive power despite calling its raw damage weak.
- Reportedly **the only healing playstyle in the game** (T3) - a structural
  niche, not merely a strong option. If a trio wants a dedicated healer, this is
  the only way to get one.
- Multiple lists describe it as an attrition class built to keep a fight going
  long after other classes would have folded, and to excel in prolonged
  encounters and PvE boss fights - monsters do not walk away from a Seer's
  constructs, which is exactly the scenario where a stationary Construct is least
  punished.
- Blasphemer has real duel teeth: DevNote #7 had to nerf its disengage and kiting
  for being overly dominant pre-launch, and player testimony describes
  stagger-locking melee opponents outright. A player was still asking for area
  stun nerfs weeks after those changes shipped.

### Weaknesses

- **Official, and the most load-bearing weakness statement available:** Seer's
  greatest weakness is being overwhelmed by concentrated attacks or by powerful
  disablers restricting movement and vision, because it lacks the means to escape
  intense battles quickly.
- **Official:** Catalyst's raw damage output leans on the weaker side. Low
  personal damage is intended design, not only a community complaint.
- **Official:** the class suffers from a steep learning curve and the Support
  playstyle's base healing efficiency remains overly dependent on landing
  enhanced orbs.
- Rune Pillars are destructible and this gets punished in real matches. The
  clearest concrete instance found: a player describing being stunlocked by a
  knight while their construct was destroyed, leaving no shield, no healing and
  no damage - the official "lacks the means to escape" weakness actually
  happening.
- **Healing is finite, not a faucet.** Both Healing Rune and Healing Art are
  capped per match, and a player makes the point that opponents wrongly treat
  Seer as a pure healer when the caps mean it runs out mid-match.
- A social rather than mechanical problem specific to the genre: a player notes
  Seer functions only as a support in groups, where teammates often loot its
  equipment to sell - so even when the class does its job, extraction loot
  incentives can leave the support player under-geared relative to the value it
  provided.
- Blasphemer is high-commitment: very reliant on cooldowns, struggles against
  other duelists once Zeal is down, and Paralysis Curse roots the caster while
  channeling.

### Gearing and gems

Dev Team FAQ #2 (T1) states the system directly: equipment itself may carry
affixes but the number of inherent affixes will be limited, and in mid to
late-game most equipment affixes will come from gems.

Per-path affix picks (T3, Mobalytics): **Reverent** - Seamless (cooldown
uptime), Eloquence (faster chants), Creation (extends Rune Summon's active time),
Spirit Shield (boosts Shelter Rune specifically). **Blasphemer** - Strife (melee
damage), Blessing (extends Zeal and other buff durations), Fervor (melee-general,
health and healing), Swift (movement speed).

A T2 player independently corroborates playing named runes (Binding, Burst,
Blinding) as a real in-match loadout, which lines up with the T3 rune list -
cross-tier corroboration rather than cross-copy.

Gearing has to commit to a stance the same way the pre-match loadout does:
Reverent wants cooldown, cast speed and rune uptime; Blasphemer wants melee
damage, buff duration and self-sustain.

### Solo vs group

Closer to two classes sharing one name for this question.

**Reverent** is near-universally called trio-dependent to the point of being
close to non-functional alone: Mobalytics' solo list calls it the worst solo
class outright, on low damage plus healing wasted with no allies nearby; player
testimony reports major disadvantages solo against melee; a beta-era GameSpot
list said the same thing for the same reasons.

**Blasphemer** is independently called the better solo option by more than one
source, though how much better is disputed - Mobalytics places it closer to
A-tier specifically because Rune: Drain provides the self-sustain Reverent lacks,
while GameRant floats it as a possible S-tier melee option solo. That spread is
between two T3 sources on magnitude; both agree it beats Reverent solo.

**In trios** Reverent is the strong side, placed top tier on its unique healer
identity, with Blasphemer lower in the same list as high-risk and
Zeal-timing-dependent.

Structural note: Dev Team FAQ #2 (T1) confirms there is no duo mode and none
planned, so there is no smaller-group format between solo and a full trio where
Reverent's kit could find a middle ground.

### Patch history

**No post-launch balance changes as of 2026-08-09**, checked post by post against
the official feed rather than inferred from a wiki.

- **2026-07-24, DevNote #7** (T1, pre-launch, shipped in the launch build):
  Catalyst's Healing Rune and Punishment Rune channel times reduced; the Support
  playstyle's Ebb and Flow given a larger hitbox for more reliable healing;
  Mace's Shapeshift duration and speed bonus reduced; Thorn Sigil's slow reduced;
  Paralysis Curse given cast-window and range restrictions; Rune: Drain's
  lifesteal against players increased; Rune: Corruption's healing-reduction
  effect lowered and shortened; the Super Armor playstyle's Relentless bonus
  duration per hit slightly reduced.
- **2026-07-30, Launch Rewards and July 30 Update:** Withered Knight only.
- **2026-08-06, August 6 Live Update:** Blackarrow, Withered Knight, Mercenary
  and Sorcerer. No Seer changes. That post explicitly states that a class not
  tweaked in the patch is not therefore considered perfectly balanced, only still
  under review.
- **2026-08-07, Server Online Update Notice:** no Seer changes.

**Consequence worth knowing:** unlike Blackarrow, where a list stamped only
"August 2026" cannot be placed relative to the nerf, **every Seer tier list dated
after 2026-07-30 describes the same unchanged balance state.** Date ambiguity is
much less of a problem for this class.

### Tier placement

See C8 - the apparent disagreement is a methodology split.

- **GameSpot**, 2026-06-17: C-tier, bottom of four. **Beta-era, predates launch
  and DevNote #7 entirely.** Discount outright.
- **FandomWire**, 2026-08-02: **6th of 6**, single ordinal ranking with no
  solo/group split. Reasoning: accuracy dependency and lower raw damage than
  every class above it, while acknowledging it is especially valuable in
  three-player squads.
- **GameRant**, 2026-08-04 (build) and 2026-08-02 (tier list): **A-tier** in
  both, broken out as good in team fights, poor solo, strong in PvE against
  bosses.
- **Mobalytics**, 2026-08-06: the only source that splits by context. Trio:
  Reverent **S-tier**, Blasphemer **B-tier**. Solo: **B-tier**, explicitly the
  worst solo class, with Blasphemer carved out as better than that placement
  implies.

### Difficulty

**Officially acknowledged**, not just a community read: the Support playstyle
suffers from a steep learning curve and its healing remains overly dependent on
landing enhanced orbs, so accuracy under pressure is intended difficulty rather
than a tuning side effect.

Mechanical ceiling components: resource management on both paths, since Psionic
Energy and Curse Mana both build primarily off landing basic attacks before the
real kit can be spent; positioning a stationary destructible object that is
simultaneously the offense and the defense on Reverent; a full-commitment root on
Paralysis Curse; and a hard buff-timing window on Blasphemer, which is weak and
exposed once Zeal expires. Mobalytics separately calls Reverent not recommended
for beginners. A broader claim that Seer may be the hardest class to start with
could not be traced to a specific article and is noted as loose sentiment.

### Open for this class

- Which weapon config id, `30507` or `30508`, is Catalyst and which is Mace. The
  category is resolved; the binding is not. Pixel-join should work.
- Whether each weapon has a second named talent path beyond Support and Super
  Armor.
- Whether the 2025 "energy charges" language maps onto Psionic Energy and Curse
  Mana.
- Whether anything other than enemies attacking a Rune Pillar can end its uptime.
- Systematic hard-counter data beyond the specific sourced points above.
- **A real evidence gap, not a null result:** no Reddit or YouTube first-party
  testimony specific to Seer was reachable - reddit.com is blocked by the
  browsing policy and generic searches are heavily polluted by unrelated fantasy
  works using the same words. Steam Community substituted reasonably well, but an
  independent cross-check was not possible and should not be reported as
  "checked and found nothing".
- Whether a third Seer weapon or season content is planned.

## Withered Knight (id 15)

Heavy melee built around a mark-and-detonate rhythm: light attacks build a
charge, the next attack applies a debuff mark, and heavy or execute attacks
consume that mark for burst damage plus energy restore and cooldown reduction.

**Read the id caveat first.** Class id 15 is the weakest binding in this repo. It
was established by elimination plus in-game sidebar order; unlike the other five
classes its ROLE panel was never captured and pixel-joined to the log. This
document does not attempt to strengthen that binding from a wiki, because wiki
agreement is not the same kind of fact as a pixel-joined log observation. Every
in-repo statement below that depends on the id, including the weapon config ids
`30409` and `30410`, inherits that caveat.

**Terminology drifted between dev notes and launch guides.** DevNote #4 names the
loop "Withering Sigils" detonated via "Reckoning"; every launch-era guide calls
the same thing Judgment, Wither and Execute. This document treats it as one
system under two name-sets, but **no source explicitly confirms the rename.**

**Tank, bruiser, or something else?** No official source uses the word "tank".
The most repeated framing is melee bruiser and chaser. One wiki is explicit that
the class rewards patient spacing and team utility rather than passive tanking.
Fextralife does use "tanking" but only for the Polearm and Shield stance. Read
together: a bruiser and duelist at its core on Greatsword, with tank-adjacent
utility on Polearm and Shield, and no dedicated aggro-tank role in either. The
trio format may not enforce a hard tank/damage/support trinity in the first
place.

**Does "Withered" imply a self-damage or decay cost? Verified, not assumed: no.**
No source describes a default self-damage or self-decay mechanic. Wither is an
enemy-facing debuff-and-detonate system. The one thing that comes close is the
optional Crime, Bad Karma and Legacy talent path (corroborated by two sources),
which lets Wither stack instead of being consumed and adds lowered movement
speed, vulnerability and slight health loss over time while extended, with the
Withered Knight recovering health when Withered enemies die. The balance of
phrasing points to those debuffs, including the health loss, landing on the
**marked enemy** - but no single sentence in either source states this
unambiguously, so that is the best-supported reading, not a confirmed fact.
Outside that one talent, "Withered" appears to be lore rather than a cost.

Lore, official: once glorious Rose Knights of the Kingdom of Gaenaria, fallen
from grace. Secondary sources add detail found in no official post - exile after
a grave failure, worn armour, shattered honour, a Nordic-inspired aesthetic - and
one calls the order "Rose Knights of the Church" where the only directly quoted
official line says Kingdom of Gaenaria. Both are recorded rather than reconciled.

### Weapons and stances

Two, matching the two weapon config ids measured here, and **both live at
launch** - the opposite of Blackarrow's situation.

- **Greatsword** - the original weapon, present from DevNote #4 months before
  launch. Two-handed, described as having excellent killing power with a sluggish
  feel. Reportedly the most-played stance. Aggressive and combo-and-detonate.
- **Polearm and Shield** - added late in development. Previewed in DevNote #6 as
  an "eventual polearm weapon archetype", confirmed for launch in the
  2026-07-17 Official Launch Announcement, fully revealed in DevNote #7 five
  days before launch. Official framing: the polearm offers a major attack range
  advantage, and its thrusting attacks demand precise timing and aim, with block
  protection on several skills. Guides add a ranged teammate-rescue utility not
  present on Greatsword.

Per the repo's own rule, no inference is drawn from these ids sitting in the
304xx range alongside Mercenary rather than the 305xx range - the id space is
already known not to be class-ordered.

### Skills

**Greatsword:** Radiant Retribution (three wide slashes in quick succession, each
counting as a Light Strike, used to build the charge quickly); Breakthrough
Charge (forward thrust gap-closer into a sweeping arc; a launch patch reduced the
second stage's knockback, and a player thread says it currently lacks Super Armor
during the charge, making it interruptible); **Parry** (officially named and
described in DevNote #4 as requiring precise timing and being very effective in
skilled hands; the 2026-07-30 patch lowered its unlock level and extended the
counter window); **Thorn Guide** (officially described as grappling and dragging
enemies, giving the class a crucial tactical team role; the 2026-08-06 patch
stopped it dragging the Richie the Merchant NPC, which incidentally confirms it
is a positional pull rather than a pure damage skill).

**Polearm and Shield:** Charged Dash (raise shield, charge, dash; energy drain
reduced and Tier-1 turning improved on 2026-07-30); Basic Attack thrusts (1st and
3rd hits slightly increased same patch); Spear Barrage (damage multiplier
slightly increased); Rainbow Piercer (charging thrust with a shield component;
energy cost and cooldown slightly reduced); Block (energy cost reduced); Intervene
(dashes to an ally and grants a damage-reduction shield); Sacred Bulwark (an area
block or barrier, described by one source as blocking all damage while
maintained); and the ranged **teammate rescue**, which every source discussing
this stance mentions and none disputes. DevNote #7 also officially names both a
Quick Shield Bash and an Enhanced Shield Bash for this weapon.

"Javelin Thrust" appeared in exactly one search-synthesised source and is
corroborated by none of the direct fetches. Recorded as unconfirmed - and note
the same word appears, equally unconfirmed, as the alleged name of Blackarrow's
future weapon.

### How it plays

Mark an enemy, chain strikes to build the charge, consume the mark for a burst
hit that also restores energy and cuts cooldowns, then repeat - a rhythm rather
than attack-speed spam. Both stances share the loop and differ in how they get
into and out of range. Greatsword duels: gap-close with Thorn Guide or
Breakthrough Charge, land the combo, Parry the reply. Polearm and Shield plays
frontline-support hybrid: hold a choke, block and counter, peel, and use the
ranged ally rescue.

### Strengths

- Repeatedly cited as having one of the, or the, highest damage and execute
  ceilings among melee classes.
- Strong in direct duels per multiple independent guides.
- **Parry is named as a hard answer to Shadowstrix** - GameRant says it nullifies
  Shadowstrix burst strategies, and this repo's Shadowstrix research
  independently records the same relationship from the other side. Note that a
  T2 thread disputes that Parry works in practice at all (C5).
- Unique team utility: ranged teammate rescue on Polearm and Shield, undisputed
  by any source.
- **Buffed twice post-launch with zero nerfs found in any source.** The most
  actively buffed class in this research.

### Weaknesses

- **Kited by ranged classes once mobility is on cooldown.** The best-corroborated
  weakness in the pass, agreed by guide sites (Blackarrow, Sorcerer and
  Shadowstrix-at-range all named) **and** by first-party testimony describing
  being focus-fired and stunlocked by three ranged players at once, with the
  argument that ranged trios are overwhelmingly superior against this class.
- Slow, telegraphed attacks - a direct player quote calls them slow, predictable
  and easy to dodge.
- Reported over-reliance on tactical items and consumables, and gameplay that can
  become repetitive (T3).
- A player thread states the class does not function at a core level without
  three specific skills - a narrow mandatory core rather than build diversity.
  Single-thread, uncorroborated.
- Leaderboard representation is contested: one thread cites 2 of the top 20 and
  0 of the top 10 as evidence of weak standing; a separate thread argues
  kill-count leaderboards structurally favour assassin archetypes and
  high-playtime players. Two different threads, not a reply exchange. Recorded as
  contested, not as fact either way.
- A third thread sits between the two poles: swordplay felt good but the wither
  effect needs more.

### Gearing and gems

- **Burst** (increases execution and Wither-detonation damage) is the only affix
  name independently corroborated by two separate sources.
- Single-sourced affix names: Seeker (movement speed on hit), Aegis and Stoic
  (defensive), Fervid, Tenacious (max health and healing efficiency).
- **Greatsword Specialization** - a talent adding an extra skill socket to the
  Greatsword loadout at the cost of a socket on the Polearm and Shield loadout.
  Two sources give near-identical wording, which is itself a copying signature
  rather than independent confirmation. Treat with mild caution despite the
  count.
- No numeric gem values were found anywhere for this class.

### Solo vs group

The dominant framing is Greatsword for solo, Polearm and Shield for group, with
the ranged rescue and shield-bash knockback peel consistently framed as trio
tools. It is not unanimous: one wiki ranks the class lower in solo specifically
on speed and mobility gaps even on Greatsword while calling it significantly
stronger in trio; a YouTube guide title (title only, content not watched) markets
a **solo** Polearm and Shield build, which cuts against the clean
"Polearm equals group" split; and the pessimistic Steam thread arguing there is
no scenario where the class is a better pick than Mercenary, Shadowstrix or Seer
does not carve out solo versus group at all, so its pessimism would apply to
both. **Direction agreed, magnitude unsettled, and the underlying "is this class
good" question unsettled with it.**

### Patch history

- **2026-03-18, DevNote #4:** class development described as complete. Greatsword
  only at this point. Names Withering Sigils, Reckoning, Parry, Thorn Guide.
- **2026-04-12, DevNote #5:** invitation-only beta of the Greatsword archetype.
  Also announces the game-wide split of Energy and Dodge into separate resources.
  (One other pass dates DevNote #5 to 2026-04-14; unresolved, low stakes.)
- **2026-06-09, DevNote #6:** character-design deep dive, and previews the
  eventual polearm archetype.
- **2026-07-17, Official Launch Announcement:** confirms Polearm and Shield ships
  at launch, alongside new "Holy weapons" and Season 1 ("Soul Hunt") content.
- **2026-07-24, DevNote #7:** full Polearm and Shield reveal - range advantage,
  block-protection skills, a steeper learning curve requiring precise timing and
  positioning.
- **2026-07-30, Launch Rewards and July 30 Update:** an official balance pass,
  **entirely buffs, all on Polearm and Shield** - Charged Dash energy drain
  reduced, Tier-1 charged dash turning improved, basic attack 1st and 3rd thrust
  damage increased, Spear Barrage damage multiplier increased, Rainbow Piercer
  energy cost and cooldown reduced, Block energy cost reduced. All changes stated
  qualitatively as "slightly".
- **2026-08-06, August 6 Live Update:** energy cost slightly reduced on **two**
  Withered Knight skills - **the skill names did not survive extraction from the
  source** and are not established here. Three bug fixes: skills no longer launch
  the character vertically when catching on obstacles; casting can no longer be
  prematurely interrupted by the Inspect action; Thorn Guide can no longer drag
  the merchant NPC.
- **2026-08-07, Server Online Update Notice:** fixed cancelling a Polearm and
  Shield charge abnormally triggering the Focused affix's movement-speed bonus -
  closing an exploit rather than adjusting a base number.

### Tier placement

- **KeenGamer**, 2026-07-30: **A-tier**, and the article states it reflects the
  July 30 launch build including the final balance update - so it accounts for
  the Polearm and Shield buffs but predates 2026-08-06 and 2026-08-07.
- **FandomWire**, 2026-08-02: **5th of 6.** Same patch state as KeenGamer. See
  C6 - this is a genuine disagreement between two dated, named, non-wiki-farm
  outlets three days apart.
- **Pro Game Guides**: reported A-tier by search snippet only; direct fetch
  blocked (HTTP 403) and publish date unconfirmed, so its relationship to the
  August 6 patch cannot be stated.
- **A wiki-tier source** claims the July 30 patch pushed it to "S-tier frontline
  status".
- **Mobalytics**: a "middle ground" placement in a trio-weighted framing, snippet
  only, no confirmed date.
- **No tier list found is dated after 2026-08-06**, the only post-launch patch
  that touched the class's numbers.
- **First-party sentiment skews more negative than any guide list**, and under
  this repo's trust ordering that testimony outranks the outlets - though it is
  contested within its own thread.

### Difficulty

Consistently described as high difficulty with high payoff: one of the highest
damage ceilings of any melee class paired with a punishing skill floor. A missed
Parry is often fatal, Wither is slow to build against mobile targets, and a
whiffed Thorn Guide leaves a window with no safety net. The gap between a
precisely played and a sloppily played Withered Knight is described as enormous.

Player testimony complicates the "hard but rewarding" framing: rather than high
skill expression, some experienced players describe specific tools as unreliable
in practice and the kit as narrow. The difficulty may be as much a currently
unforgiving or undertuned kit as a high ceiling. The two readings are not
mutually exclusive and nothing found adjudicates between them.

### Open for this class

- **The class id 15 binding itself.** Capture the ROLE panel and pixel-join it.
- Which two skills received the 2026-08-06 energy-cost reduction.
- Whether the Bad Karma and Crime talent's health-loss-over-time lands on the
  enemy or on the Withered Knight.
- The in-fiction affiliation name - Kingdom of Gaenaria versus "the Church".
- Whether Parry actually works as guides describe (C5).
- Whether the class is currently strong or weak at all (C6).
- Precise interrupt rules for Parry and for Wither buildup.
- Whether the class was in the June 2026 open beta or invitation-only throughout.

## What nobody knows

Consolidated across all six passes. This is what Emberforge exists to fill, and
it is a first-class section rather than an appendix.

### Game-wide, reconfirmed independently by all six passes

1. **No cooldowns, damage coefficients, durations, heal amounts, energy costs or
   crowd-control durations are published anywhere, at any trust tier.** This is
   the project's standing doctrine and six independent passes found no exception.
   Every official balance note describes changes qualitatively - "slightly
   reduced", "slightly increased", "sped up" - with no before or after value.
2. **No tier list verifiably dated after the 2026-08-06 patch exists for any of
   the six classes.** Every statement of current standing anywhere in this
   document is an inference from what that patch contained, not a citation. This
   is the largest cross-cutting gap the merge exposed, and it is cheap to
   re-check as new lists appear.
3. **The attribute system** - Strength and Dexterity semantics or whatever the
   game actually uses - is unpublished at any trustworthy tier. All six passes.
4. **The gem system's numbers**: no drop rates, socket counts per slot, roll
   ranges, affix weights, tiers or best-in-slot data. The August 6 update
   confirms gem affixes exist and publishes none of that.
5. **Community "affix" vocabulary versus official "gem" vocabulary** is
   unreconciled by any guide found. Keep the two distinct in Emberforge's schema
   rather than assuming they map cleanly.
6. **Stance-swap rules per class.** Only Seer is claimed hard-locked, at T3.
   Every other class's ability to swap mid-match is inferred by omission from
   that claim, and no source states it for any class by name.
7. **Resource-bar names.** "Energy" is used throughout guides by convention and
   was never sourced to an official glossary in any pass.
8. **No authoritative full skill or talent list exists for any class.** Every
   complete list found is a community reconstruction, and reconstructions
   disagree with each other.

### Per class

- **Mercenary:** Sword Tip's structure; mid-combat stance swap; whether the two
  weapons' gem sockets are independent pools; the status of three Hammer skill
  names that appear in exactly one outlet.
- **Sorcerer:** the single-weapon question (design choice or capture gap) - the
  core open item, closed only by a deliberate re-walk; whether any official
  statement about a second weapon exists (C2); Meteor Charm versus Meteor Impact;
  whether "Focus" is real; chant interrupt rules; the Chant Guard description
  fix.
- **Blackarrow:** the second weapon's real name and date; whether Archer and
  Hunter is a hard talent lock or a power gradient; Predator's Senses; the source
  thread for the dodge-length range testimony; the full verbatim DevNote #7
  class-balance text.
- **Shadowstrix:** whether incoming damage breaks stealth; the detection
  mechanism and radius; reveal consumables versus "certain skills"; Shadow Veil's
  ownership (C3); whether "Ambush Momentum" exists.
- **Seer:** which weapon id is Catalyst and which is Mace; whether each weapon
  has a second talent path; whether the 2025 resource language maps onto the
  launch resources; Rune Pillar interrupt rules; systematic hard-counter data.
  Plus a real evidence gap: no Reddit or YouTube first-party testimony was
  reachable, which is not the same as having checked and found nothing.
- **Withered Knight:** the class id 15 binding itself; which two skills got the
  August 6 energy cut; whether Bad Karma's health loss lands on the enemy or the
  player; the in-fiction order name; whether Parry works as described; whether
  the class is currently strong or weak.

### Cross-class questions nobody has answered

- **Which class is actually the squishiest** (C4). No source compares any two
  classes' health directly.
- **Solo versus trio strength for Shadowstrix, Sorcerer and Withered Knight**
  (C1, C6, C7). Disputed for three of six classes, and no source has published
  anything that would settle any of them.
- **Whether Shadow Veil belongs to Sorcerer or Shadowstrix** (C3).

## Fabrications identified

Naming these protects the next reader. The section is split three ways on
purpose: calling an unverified skill name a "fabrication" would itself be an
unsupported claim, and flattening the three categories would destroy the
distinction between "traced to no real source", "real number, no publisher" and
"name nobody else uses".

### Fabrications - claims that trace to no real source

| Claim | Where it appears | Why it is a fabrication |
|---|---|---|
| "Shield Block cuts incoming damage by 70%" (Mercenary) | allthings.how (2026-08-01) and, per a search index, ggwtb.com | Appears **verbatim, word for word, on two unrelated domains with zero citation on either**. False precision manufactured by cross-copy. The second domain returned HTTP 403 and was only seen via a search snippet. |
| A full set of affix percentages presented as "Bellring Games' official beginner-friendly Mercenary setup" - including Physical Resistance +5.5%, Magic Resistance +5.5%, Restores 15% Health, Cooldown 120s, Maximum Health +12.6%, Healing +7.5%, Charging Speed +21%, Movement Speed +10% | metamist.io, "official-beginner-setup-hammer" | Claims provenance from a graphic in an official Bellring Discord **while the same site carries a sitewide disclaimer that it is fan-made and not affiliated with Bellring Games.** No corroboration anywhere. Fabrication wearing an official-sounding citation. |
| An "SS tier" | One launch-window wiki, and separately a search summary floating "Valor, Eloquence, Stoic and Ranged" as game-wide "SS tier" affixes | No other tier list uses an SS tier. Invented, and it has now recurred in a second context, which is how an invention becomes a "known fact". |
| An August 5 Blackarrow nerf | One launch-window wiki | No such patch exists. The real nerf is 2026-08-06. |
| "Javelin" as the name of Blackarrow's second weapon, arriving in "Season 2" | mmoexp, IGGM, PlayerAuctions (all excluded vendors), echoed through the wiki cluster | **No official source names it.** The Wave 3 roadmap - the likeliest place - does not mention a javelin or any weapon name when fetched directly. One lore sentence about it recurs near-verbatim across unrelated queries, the cross-copy signature. Compounding the suspicion, "Javelin Thrust" separately appears as an alleged **Withered Knight** skill in exactly one search-synthesised source and in none of the direct fetches. The same invented word attached to two unrelated classes is a contamination smell, not two findings. |
| "Sorcerer's second weapon is confirmed to be in development", attributed to the 2026-07-14 Community AMA | A search-engine summary | **Caught in the act.** The AMA was fetched directly and read; it contains no such content. A separate T4 site (dtgre.com) makes the same claim citing nothing. See C2 for the one version of this claim that is not dismissed. |
| Blackarrow at S-tier, credited in prior art to an unnamed "one tier list" | SkyCoach | Traced to a boosting vendor on this project's exclusion list. Drop it rather than carrying it as an anonymous data point. |
| "Parry lasts 5 seconds and blocks 5 attacks or 1 powerful blow" (Withered Knight) | Fextralife and GameRant | Two guide sites agreeing is not corroboration under the cross-copy rule - it may mean one copied the other, or both copied a third. No duration for anything is published for this game. |
| A specific percentage threshold attached to the "Stoic" affix (Seer) | GameRant | A number of exactly the kind that is not published anywhere. Only the affix name is carried forward. |
| "Fervid: bonus damage above 70 percent health" (Withered Knight) | GameRant | Same category - a percentage with no publisher. |

### Unpublished numbers circulating at guide tier

Not proven invented, but not published either. None is officially sourced, so
none may be carried into Emberforge as a value. Several are cheaply falsifiable
in game, which is the right way to settle them.

- **Wound detonates at 10 stacks** (Shadowstrix, Dual Blades). Multiple guides
  give the same count. It is a discrete count rather than a coefficient or a
  duration, so it is more testable than most of these - but it is still T3 and T4
  only.
- **Shadow Veil usable up to 3 times after exiting Stealth** (Shadowstrix). Same
  status, and the ability's class ownership is itself disputed (C3).
- **Sword Tip: 6 stacks** (Mercenary) versus **a two-tier "Blade Edge" then
  "Strong Edge" 6-then-6 progression.** Two incompatible structures. The
  single-threshold version comes from a page that explicitly labels its own
  unverified claims and cites a named creator video (2026-08-02) it did not
  itself view - a secondhand citation of first-party evidence, which is better
  practice than most of this tier and still not confirmation.
- **Blackarrow's effective heavy-shot range of about two dodge-lengths, and about
  one for uncharged shots.** T2 by origin and independently re-derived rather
  than inherited, but the exact thread could not be re-opened, so the citation
  gap is real and open.
- **An ambiguous "60 seconds" and "120 seconds" pair** found attached to vaguely
  described energy-management and health-restoration effects during the
  Blackarrow pass. It could not be established what they refer to - possibly a
  shared consumable system rather than anything class-specific - and they are
  **deliberately not recorded as Blackarrow numbers in either direction.**
- **Two mutually inconsistent heal use-counts and cooldowns for Seer**, given by
  two different players in Steam Community threads. Neither is recorded. Their
  disagreement is itself the useful datum: it demonstrates why the doctrine
  exists.
- **Which two Withered Knight skills received the August 6 energy-cost
  reduction** - the count is official, the names did not survive extraction.

### Unverified names

Named once, or by one source, with no corroboration. Not fabrications - just not
established.

- **"Ambush Momentum"** (alleged Shadowstrix talent) - one low-confidence search
  pass, uncorroborated anywhere.
- **"Prophet"** (alleged Seer talent or build archetype) - one player's word, no
  other source uses it for Seer.
- **"Assault Hammer", "Power Hammer", "Punishing Hammer"** (alleged Mercenary
  skills) - Destructoid only, in no other source checked. Possibly talent names
  miscategorised as base skills.
- **"Javelin Thrust"** (alleged Withered Knight skill) - see the Javelin entry
  above.
- **"Focus"** as a Sorcerer second stance or item - informal guide shorthand, and
  no official source uses the word for Sorcerer at all.
- **"Sonic Arrow" versus "Soundwave Arrow"** (Blackarrow) - the same ability
  under inconsistent community naming, no official name confirmed either way.
- **"Meteor Impact"** (Sorcerer) - real enough as a name, but its relationship to
  Meteor Charm (rank, talent, or separate skill) is unresolved.
- **"Predator's Senses"** (Blackarrow) - named once, never described.
- **"Rose Knights of the Church"** (Withered Knight lore) - secondary sources
  only; the official line says Kingdom of Gaenaria.

## Sources

Deduplicated across all six passes and the prior art. Where the passes disagreed
about a date or an access result, the disagreement is recorded rather than
smoothed over.

### T0 - in-repo first-party measurement

- [`docs/OBSERVED_IDS.md`](OBSERVED_IDS.md) - class ids 10-15, weapon config ids,
  gender ids, live item cfgIds, method recorded per row. Observed 2026-08-09,
  Steam build `24619162`. The authority for every id in this document.
  **That build no longer exists.** The game was patched to buildid `24813185`
  on 2026-08-19 and none of these ids has been re-confirmed since; see the
  banner at the top of `OBSERVED_IDS.md`. Treat every id here as measured on a
  build that is gone - probably still true, and nothing has checked.
- [`docs/CLASS_RESEARCH.md`](CLASS_RESEARCH.md) - the earlier adjudicated
  Blackarrow-versus-Shadowstrix pass and the operator decision, 2026-08-09.

### T1 - official

Steam news and dev posts for appid 3282300, plus the store page. Accessed
2026-08-09 unless noted.

**How to reach any post below, and why no post ids appear here.** Every item is
listed at `steamcommunity.com/app/3282300/allnews/` and returned by
`api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=3282300`, and each is
uniquely identified by its title and date. The 18-digit announcement ids that
form the deep-link URLs are **deliberately omitted**: this repo's PII guard
(`lanternlight/redact.py`, rule `LONG_ID`) fires on any bare digit run of 15 or
more, because that is what catches an unfamiliar GSDK id, and it scans every
tracked file. Pasting the deep links back in would fail
`tests/test_no_pii.py`. Do not re-add them - fetch by title and date instead.

| Post | Date | Note |
|---|---|---|
| Class Introduction - Seer | 2025-03-23 | Pre-launch by over a year. Durable lore and kit shape, not launch balance. |
| Dev Team FAQ #2 | **disputed - 2026-03-04 or 2026-07-02, see C11** | Gems replace affix rolls; no summoner class planned; no duo mode planned. Load-bearing for C2. |
| DevNote #4 | 2026-03-18 | Withered Knight; Withering Sigils, Reckoning, Parry, Thorn Guide. |
| DevNote #5 | 2026-04-12 (one pass says 2026-04-14) | Combat overhaul; Energy and Dodge split into separate resources. |
| DevNote #6 | 2026-06-09 | Gems replace affix rolls; previews the polearm archetype. |
| Gyldenhunters' Council Phase 1 - Community AMA | 2026-07-14 | Fetched and read line by line for Sorcerer weapon content. Contains none. |
| Official Launch Announcement | 2026-07-17 | Confirms Polearm and Shield ships at launch. |
| **DevNote #7** | **2026-07-24 09:50 UTC** (confirmed by recomputing Unix `1784886600` during this merge; see C10) | The pre-launch balance pass across all six classes. Full class-balance section never read end to end - see the access caveat below. |
| Official Launch FAQ | 2026-07-24 10:13 UTC (Unix `1784888020`) | Launch at 2026-07-30 01:00 UTC on three platforms. |
| Known Issues | 2026-07-30 | Sorcerer tutorial key prompts; Flameblade visual mismatch. |
| Launch Rewards and July 30 Update | 2026-07-30 17:04 UTC | Withered Knight Polearm and Shield buffs only. |
| The Second Wave of Launch Rewards | 2026-08-01 17:24 UTC | No class content. |
| Fair Play Penalty Announcement | 2026-08-03 14:52 UTC | No class content. |
| Roadmap and Launch Rewards: Wave 3 | 2026-08-05 13:45 UTC | 1 million players; Solo Mode announced for September. No weapon name. |
| **August 6 Live Update** | 2026-08-06 08:25 UTC | The Blackarrow nerf, read directly and quoted verbatim. Also Withered Knight, Mercenary, Sorcerer. No Shadowstrix or Seer content. |
| August 7 Server Online Update Notice | 2026-08-07 09:40 UTC | Focused-affix exploit fix. The last patch of any kind. |
| Steam store page | evergreen, undated | `store.steampowered.com/app/3282300/Mistfall_Hunter/` - the "two unique weapon stances" line is known-generic marketing with at least one real exception |

Also T1 by origin, reached through other channels:

- Developer balance-philosophy quote, Bellring Games interviewed by GamingBolt,
  published 2026-07-28 - the developers' own words via an established outlet.
- Official class reveal trailers (Mercenary, Sorcerer) on YouTube, labelled
  official. **No pass could fetch a trailer's own description or date**, so the
  wording of the widely-copied class blurbs cannot be confirmed to originate
  there.

**Two access caveats that apply to T1.** Several individual announcement detail
pages would not render through available fetch tools and were reached via the
Steam allnews listing or the news API instead. And the full verbatim class-
balance section of DevNote #7 - roughly 8500 words - was never read end to end;
four attempts truncated. Its quotations here are corroborated across passes but
are held slightly below the August 6 quotations, which were read directly.

**One data-quality anomaly, recorded so nobody trips on it:** the news feed also
returned an item dated 2026-11-10 sorted ahead of items from earlier in August.
It postdates today and cannot be a published patch note. Nothing here relies on
it.

### T2 - first-party player evidence

All Steam Community discussions under `steamcommunity.com/app/3282300/discussions/`,
accessed 2026-08-09, findable by title. **The numeric thread ids are omitted for
the same reason as the announcement ids above** - they are 18 digits and would
trip the repo's `LONG_ID` guard.

| Thread | Date | What it evidences |
|---|---|---|
| "What is the best class?" | not confirmed | General class sentiment |
| "Make Knight and Mercenary more skill based" | not confirmed | The Mercenary "no skill" complaint and the pushback to it (C13); a ranged player conceding Mercenary wins if it closes |
| "Suggestion: Nerf the sorcerer." | 2026-07-30 | Sorcerer area burst being hard to escape in tight spaces |
| "Game is ungodly balanced" | 2026-07-31 | Seer solo weakness; the support-gets-looted problem; named Seer rune loadouts |
| "The Blackarrow SUCKS, buff him." | 2026-08-01 | Pre-nerf Blackarrow complaints, with in-thread pushback |
| Crow Storm nerf thread | 2026-08-01, reply 2026-08-02 | Shadowstrix stun-lock complaint, postdating the pre-launch nerf |
| "Archers make me wanna ragequit" | 2026-08-02 | The melee side of the Blackarrow matchup - the strongest testimony for it |
| "seer" | 2026-08-02 | Seer stagger-locking melee; finite healing |
| "I'm Done Playing Until They Nerf the Seer and the Shadowstrix..." | 2026-08-04 per one pass, unconfirmed per another | Area-stun complaints. **Title and snippet only, never fetched in full.** |
| "What exactly is the point of the Seer?" | 2026-06-19, beta era | A Rune Pillar destroyed mid-fight leaving no shield, healing or damage |
| "Wither Knight Feedback" | undated | Parry called "a disaster" (C5); the three-skill core claim; leaderboard argument |
| "Make Withered Knights faster.." | undated | Being focus-fired by ranged trios; slow telegraphed attacks; leaderboard counter-argument |
| "Just my thoughts." | undated | The lukewarm middle position on Withered Knight |

Creator video, cited secondhand and **never watched by any pass**: a
DrybearGamers video published 2026-08-02, cited by one wiki page as its source
for the Sword Tip mechanic. A YouTube Withered Knight solo build video is cited
by **title only** - content not fetched.

### T3 - established outlets

- **KeenGamer** - class tier list (2026-07-30); Shadowstrix build (2026-08-04);
  Mercenary build (2026-08-05); Blackarrow build (2026-08-08).
- **Destructoid** - Blackarrow build (2026-08-02); Sorcerer build (2026-08-03,
  updated 2026-08-04); Mercenary build (date unconfirmed); class tier list
  self-labelled "(Launch)".
- **GameRant** - class tier list (2026-08-02 21:53 EDT); Blackarrow build
  (2026-08-01); Withered Knight build (2026-07-30); Seer build (2026-08-04);
  Shadowstrix and Sorcerer builds (dates unconfirmed, snippet only).
- **Mobalytics** - classes explained; class tier list (2026-08-06 per one pass,
  undated per others); Seer guide (2026-08-01); Shadowstrix, Sorcerer and
  Withered Knight guides. **Access conflict: four passes report HTTP 403 on
  mobalytics.gg and used search snippets only; the Seer pass reports fetching two
  Mobalytics pages in full. This unresolved conflict is load-bearing for C1.**
- **FandomWire** - classes tier list (2026-08-02 06:21 US-Eastern).
- **GameSpot** - class tier list (2026-06-17, beta era, stale - excluded on its
  own date wherever it appears); "Best Class Just Got Even Better" (HTTP 403,
  headline only, date unconfirmed).
- **GamingBolt** - Bellring interview (2026-07-28); Mercenary trailer coverage.
- **Deltia's Gaming** - Mercenary build (date unconfirmed).
- **Pro Game Guides** - class tier list (HTTP 403, snippet only, date
  unconfirmed).
- **Worthplaying** - one-million-players and Wave 3 coverage (2026-08-06), used
  for general context only.
- **allthings.how** - Withered Knight build (2026-08-02) and Mercenary build
  (2026-08-01). **Tier conflict between passes: one graded this domain T3, another
  T4.** Graded at the lower tier here; the disagreement is recorded rather than
  resolved.
- **gamerfuzion.com** - Withered Knight guide, and gems-and-affixes explainer.
  Same tier disagreement between passes; graded low here.

### T4 - launch-window wiki cluster

**This entire cluster counts as one source.** Named so the next reader
recognises the pattern, deduplicated across all six passes:

mistfallhunters.wiki, mistfallhunters.com, mistfallhunter.app,
mistfall-hunter.wiki, mistfall-hunter.com, mistfall-hunter.online,
mistfallhunter.wiki, mistfallhunter.xyz, mistfallhunterwiki.org,
mistfallhunterwiki.wiki, mistfallhuntergg.wiki, mistfallhunterguide.org,
mistfallhunterclasses.net, mistfallhunter.grandwiki.com, mistfalldb.com,
metamist.io, questlog.gg, fextralife.com, egamersworld.com, dtgre.com,
thegameswiki.com, gmtreks.com, tposegaming.com, gamingpromax.com, games.gg,
grindnstrat.com, drawpie.com, thegamesedge.com, showgamer.com, gamerblurb.com,
onehitkill.space, ggwtb.com, captain-carry.com.

Two notes on that list. **questlog.gg's equipment-overhaul explainer reads as a
genuine mechanics write-up rather than copy-farmed guide text**, and one pass
flagged it as such. And **captain-carry.com appears in one pass's T4 cluster
despite a name that suggests a carry vendor** - it should probably move to the
excluded list; flagged rather than silently reclassified.

### Excluded - never cited as evidence

Cheat, boosting and currency vendors, named only to record what was thrown out:
**skycoach.gg, mmoexp.com, iggm.com, playerauctions.com, lagofast.com, u4gm.com,
gladiatorboost.com.** Two of these (iggm, playerauctions) were added to the
exclusion set during this round of research. Content from these sites matched the
consensus in several places, which is not a reason to cite them - it is a reason
to note that a vendor repeating a true thing does not make the vendor evidence.

### Search-engine synthesis

Used throughout the six passes as a pointer to sources, **never as a source in
itself.** Three separate passes caught a search layer manufacturing a specific,
confident, sourced-sounding claim that dissolved on direct inspection of the
cited primary source. Every load-bearing claim in this document is either traced
to a fetchable page, or explicitly marked as search-synthesis-only with
correspondingly reduced confidence.
