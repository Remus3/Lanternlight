# Mistfall Hunter third-party ecosystem survey

Surveyed 2026-08-09, eleven days after the 2026-07-29 launch. Steam appid 3282300,
dev Bellring Games, pub Skystone Games. Official Steam page confirms: price
$22.49 (10% off $24.99), review score 65% positive of 4,675 English-language
reviews / 10,424 total, rated "Mixed" as of this survey. Official site
mistfallhunter.com confirmed live (copyright line "(c) 2024 Bellring Games,
Mistfall Hunter" - note the year does not match the 2026 launch, likely stale
boilerplate rather than a hostile domain, since it links out to the real Steam
store page and the studio's real Discord/X/YouTube/Facebook accounts).

Ground-truth check that shapes every judgement below: Bellring's own Steam
patch notes (fetched directly from steamcommunity.com/app/3282300/allnews and
cross-checked against a fan transcription) use **qualitative language only**
- "slightly reduced," "marginally toned down," "cooldown now starts after
firing" - never a percentage, a seconds value, or a coefficient. This directly
confirms the CLAUDE.md premise: the developer has not published a single hard
number for cooldowns or damage. Any site quoting one is doing something else
(tooltip transcription, self-measurement, or invention) - see each category
below.

## Source register - the single entry point

Added 2026-08-29. **Read this table before consulting or citing any source for
this game.** It exists because the vetting below had already been done and was
scattered across four documents - this survey by category, `ROADMAP.md` item 8,
the [`docs/CLASSES.md`](CLASSES.md) tier ladder and fabrication catalogue, and a
ledger entry - so a cold session had no entry point and re-vetted from scratch.
Re-deriving a source's trust is the exact rediscovery this project's continuity
design exists to prevent.

**The rule that governs the table: provenance beats category.** "Third-party
site" is not a trust tier. Two sites for this game, reviewed on the same day,
turned out to have opposite provenances - one datamined from the encrypted
paks, one walked by hand - and they fail in opposite directions. Check how a
source was built before quoting it, every time.

**What a non-T0 source is licensed to do**, in every case in this table:

- Supply a **canonical noun** - a class, zone, NPC or item name - subject to the
  game's own word winning any conflict. The game says *dungeon* and *escape*;
  `raid` and `extract` appear zero times in the log, so a grep for a term
  learned from a site returns a clean negative that means nothing.
- Supply a **hypothesis** or an **expectation to test**. A count is the most
  useful form, because a count that disagrees is immediately informative.
- Supply a **cross-check**. A contradiction with our own measurement is a real
  result worth chasing. **An agreement is not corroboration.**

**What no source in this table may ever do:** write a row into
[`docs/OBSERVED_IDS.md`](OBSERVED_IDS.md), or put a number into Emberforge.
Promotion from any tier below T0 is forbidden by
[ADR-005](adr/ADR-005-omit-rather-than-guess.md).

Tier definitions live in [`docs/CLASSES.md`](CLASSES.md) under "Trust tiers" and
are not restated here.

### First-party and official

| Source | How it was built | Tier | Use it for | Basis |
|---|---|---|---|---|
| This repo's log and save reads, and passive capture of the operator's screen | Measured here, method recorded per row | T0 | Everything. Outranks every row below. | `OBSERVED_IDS.md`, `FINDINGS.md` |
| `steamcommunity.com/app/3282300/allnews`, `api.steampowered.com` ISteamNews | Bellring's own posts | T1 | Canonical names, patch bookkeeping, what changed. **Never a magnitude** - patch notes are qualitative only, verified by direct fetch. | This survey's header; `CLASSES.md` T1 table |
| `store.steampowered.com/app/3282300` | Publisher marketing copy | T1, with a caveat | Product facts. Its "two unique weapon stances" line is known-generic and has at least one measured exception (Blackarrow). | `CLASSES.md` C-series |
| `mistfallhunter.com` | Official site | T1 | Canonical nouns. Carries a stale "(c) 2024" line; links resolve to real first-party accounts. | Section 10 below |
| `steamdb.info`, `raijin.gg` | Third-party scrapes of Steam metadata | T1-derived | Build ids, player counts. Metadata about the app, never about game mechanics. | Section 9 below |

### Third-party, provenance individually assessed

| Source | How it was built | Tier | Use it for | Basis |
|---|---|---|---|---|
| `gyldforge.com` | **Dated Auction House capture** - states its snapshot date (2026-08-07) and game build (`24589503`), and explicitly refuses to backfill absent combinations | T4 by category, **best-documented method in the survey** | Gear, affix and gem cross-checks, and only for what it says it captured - never for what it is silent on | Section 4 below |
| `questlog.gg` | **DATAMINED.** Measured, not inferred: addresses monsters by numeric id in the same space our save uses, and lists `[Debug]`, `Test Dummy` and `[Discarded]` rows no player can ever see | T4 | Hypothesis and cross-check only. Its ids are **never** written to `OBSERVED_IDS.md`. Its category slugs are internal (`BigElite` where the UI says "Greater Elite") | `ROADMAP.md` item 8, 2026-08-11 |
| `gamerguides.com` | **HAND-MAPPED**, crowd-sourced - maintainer states a small team "filling them out as we play" with reader-suggested markers | Higher than a datamined dump for *where a thing is*, lower for *completeness* | Map expectations. Two self-declared caveats: its database's first iteration was built on the **DEMO**, and it is "mindful of randomization" - so a marker that fails to match refutes nothing on its own | `ROADMAP.md` item 8, 2026-08-11 |
| `mistfallhunterguide.org` | States an explicit editorial policy - "no invented player counts, drop rates, class names, weapon stats" - and tiers its own sources | **Disputed, see conflicts below** | Narrative and progression facts where being wrong is low-stakes | Section 5 below vs `CLASSES.md` T4 cluster |
| `mistfallhunter.app` | Declares its own data tiers (official / tooltip / creator-tested / tentative) | T4 | Cross-check, honouring its own tier marks | Section 1 below |
| `mistfalldb.com` | **No sourcing method disclosed** - one vague line, "faithful to the current build" | T4 | Cross-check only | Section 1 below |
| `mistfallhunter.grandwiki.com` | Wiki-farm template; its "mined fields" language reads as multi-game boilerplate, **not** a decryption claim, and is uncorroborated | T4 | Cross-check only | Section 8 below |
| `mistfall.market` | Watching the player-run Auction House UI. No market API exists | T4 | Price bands as a dated snapshot, never as a spec | Section 7 below |
| `mobalytics.gg` | Established outlet | T3 | Tier context. **Access is unresolved:** four research passes report HTTP 403, one claims full fetches. This conflict is load-bearing for `CLASSES.md` C1 | `CLASSES.md` T3, C1 |
| KeenGamer, Destructoid, GameRant, FandomWire, GameSpot, GamingBolt, Deltia's Gaming, Pro Game Guides, Worthplaying | Dated and bylined, frequently uncited on mechanics | T3 | Context and dated claims. GameSpot's tier list is beta-era (2026-06-17) and stale on its own date | `CLASSES.md` T3 |
| `allthings.how`, `gamerfuzion.com` | Guide sites | **T3 or T4 - passes disagreed**; graded T4 here | Cross-check only, at the lower grade | `CLASSES.md` T3, disagreement recorded |

### The launch-window wiki cluster - one source in total

`mistfallhunters.wiki`, `mistfallhunters.com`, `mistfallhunter.app`,
`mistfall-hunter.wiki`, `mistfall-hunter.com`, `mistfall-hunter.online`,
`mistfallhunter.wiki`, `mistfallhunter.xyz`, `mistfallhunterwiki.org`,
`mistfallhunterwiki.wiki`, `mistfallhunterwiki.vercel.app`,
`mistfallhuntergg.wiki`, `mistfallhunterclasses.net`,
`mistfallhunter.grandwiki.com`, `mistfalldb.com`, `mistfallhunter.me`,
`mistfallloadouts.blog`, `metamist.io`, `questlog.gg`, `fextralife.com`,
`egamersworld.com`, `dtgre.com`, `thegameswiki.com`, `gmtreks.com`,
`tposegaming.com`, `gamingpromax.com`, `games.gg`, `grindnstrat.com`,
`drawpie.com`, `thegamesedge.com`, `showgamer.com`, `gamerblurb.com`,
`onehitkill.space`, `ggwtb.com`, `captain-carry.com`.

**These count as one source, not thirty-five.** They cross-copy each other close
to verbatim; two catalogued fabrications were caught precisely because a
specific false-precision claim appeared word for word on unrelated domains with
zero citation on either. Agreement across this cluster is one source repeating
itself. Rows above that name a cluster member individually (`gyldforge.com` is
not a member; `questlog.gg`, `mistfalldb.com`, `mistfallhunter.app` and
`mistfallhunter.grandwiki.com` are) carry an assessment that supersedes the
cluster default for that domain only.

### Excluded - never cited as evidence

`skycoach.gg`, `mmoexp.com`, `iggm.com`, `playerauctions.com`, `lagofast.com`,
`u4gm.com`, `gladiatorboost.com`. Cheat, boosting and currency vendors, named
only to record what was thrown out. Their content has matched the consensus in
places; that is a reason to note that a vendor repeating a true thing is not
evidence, not a reason to cite one.

Cheat-storefront domains selling ESP or aimbot access for this game are
deliberately not named anywhere in this repo. The category exists and is
commercially active; that is the whole record.

### Community hubs and infrastructure - not evidence about mechanics

| Source | What it is | Use it for |
|---|---|---|
| Official Discord (member counts via `discordbotlist.com`) | Run by Bellring | Population figures, and as the venue where first-party statements appear |
| `reddit.com` / `old.reddit.com` r/MistfallHunter | Player community | T2 testimony if a thread is read directly. **Not fetchable from this environment** - every figure in this repo about it is secondhand and marked so |
| `steamcommunity.com/.../discussions` | Player threads | T2 first-party player evidence. Thread ids are omitted repo-wide because 18-digit runs trip the `LONG_ID` redaction guard |
| `twitch.tv` category | Streams | Not characterised |
| `github.com` | Code hosting | The license gate, and the overlays-and-safety-gate table below. `api.githubcopilot.com` appears in the ledger as tooling, not as a game source |

### Conflicts between documents, recorded rather than smoothed

Four sources are treated inconsistently across this repo's own docs. Each is
named here so the next reader sees the disagreement instead of inheriting
whichever document they happened to open first.

1. **`questlog.gg`** sits in the `CLASSES.md` T4 copy-farm cluster (2026-08-09),
   but was **measured as datamined** two days later in `ROADMAP.md` item 8. The
   later, measured assessment is the one this register carries. It stays T4 - a
   datamined source is not more trustworthy, it fails differently.
2. **`mistfallhunterguide.org`** sits in the `CLASSES.md` T4 cluster, and is
   simultaneously ranked the second-best upstream in this survey for its stated
   editorial policy. **Unresolved.** A stated policy is a claim about a source,
   not a measurement of it, and nothing here has tested whether it is honoured.
3. **`lagofast.com`** is on the `CLASSES.md` excluded-vendor list and is also
   cited in section 2 of this survey as a tier-list site. **Excluded wins** -
   the stricter treatment governs, and section 2's citation should be read as a
   record that the site exists, not as evidence.
4. **`captain-carry.com`** sits in the T4 cluster despite a name suggesting a
   carry vendor. `CLASSES.md` already flags that it should probably move to
   Excluded. **Flagged, not silently reclassified** - it needs someone to look
   at the site once and decide.

Also recorded: **`gyldforge.com` and `gamerguides.com` appear nowhere in the
`CLASSES.md` tier ladder**, because that document was written before either was
assessed. They are not absent because they were rejected.

### When to re-vet

A row here is a statement about a source at a date, not a permanent property.

- **Re-vet on a build pin change.** The current pin is buildid `24813185`
  (2026-08-19); the assessments in this table were made against the survey of
  2026-08-09 and the review of 2026-08-11. A site's data can go stale silently,
  where our own measurements at least carry a banner naming the build they were
  read on.
- **Re-vet any source that changes its stated method**, since for most rows here
  the method is the only thing being trusted.
- **A decline reason goes stale faster than a count does.** Re-check why
  something was rejected before citing the rejection.

## 1. Item / loot databases

Real and numerous, all unofficial:

- **MistfallDB** (mistfalldb.com) - claims 599 weapons, 1,584 armor pieces,
  104 skills, plus talents/affixes/bestiary/missions/bosses/gems/crafting.
  Methodology statement is one vague line: "faithful to the current Mistfall
  Hunter build." No sourcing method disclosed.
- **Mistfall Hunter Grand Wiki** (mistfallhunter.grandwiki.com/items) -
  filterable item DB, explicitly "unofficial fan-made" in its footer. Its
  page states it excludes "internal persistence flags, storage rules, table
  identifiers, and other mined fields that the game does not show in this
  tooltip" - see the Data mining section, this reads as templated wiki-farm
  boilerplate rather than a real decryption claim.
- **MistfallHunter.app** items/affixes DB - "source-checked," distinguishes
  official/tooltip/creator-tested/tentative data tiers explicitly.
- **Gamer Guides** (gamerguides.com/mistfall-hunter/database) - item/weapon/
  armor/collectible tables; the specific items sub-page 403'd on fetch.
- **Mistfall Hunter Guide** (mistfallhunterguide.org/database) - items and
  affixes tables, part of the site with the strongest stated sourcing policy
  in the whole survey (see section 5).

**Contradiction found, load-bearing for the whole survey**: three independent
sites give three different, incompatible rarity ladders for the same seven-tier
system:
- MistfallDB: "Worn, Normal, Delicate, Extraordinary, Epic, Legend, Holy"
- Grand Wiki: "Holy, Legendary, Epic, Excellent, Rare, Common, Damaged"
- MistfallHunter.app: uses "Common, Refined, Excellent, Epic" for a voucher item
Only "Holy" (top) and "Epic" (upper-mid) recur across all three; the rest do
not match at all. Item rarity is about as basic and easily-observed a fact as
a game has. At least two of these three sites are simply wrong. Treat every
specific number on every one of these sites as unverified until Lanternlight
observes it directly.

## 2. Stat and meta sites

Multiple tier lists exist (mistfallhunterguide.org/builds/tier-list,
mistfallhunter.app/tier-list, metamist.io, lagofast.com, egamersworld.com).
Launch-window consensus: Sorcerer and Shadowstrix in S-tier, Mercenary/
Blackarrow/Withered Knight in A-tier, Seer in B-tier. **None of these
sites cite a methodology, a sample size, or a win-rate percentage** - they
read as editorial/community-consensus opinion, not measured telemetry. This
matches expectation: no public API exposes match outcomes (see section 9),
so a real win-rate tracker is not currently possible for anyone outside
Bellring. Measured NULL: no statistically-grounded meta site exists; every
"tier list" found is an opinion piece.

## 3. Interactive maps

Real, several competing implementations, all fan-made:
- Gamer Guides (gamerguides.com/mistfall-hunter/maps) - Brandrgarde and
  Hallowgrove, chest/monster/named-area/escape-portal-timing markers.
- MistfallDB (mistfalldb.com/maps).
- A third-party aggregator (showgamer.com) reports 154 markers for Hallowgrove
  and 111 for Brandrgarde as of 2026-08-01 - i.e. only two maps exist in the
  live game so far.
- mistfallhunters.wiki/guides/maps, mistfall-hunter.online, and others.

Fan terminology is inconsistent about extraction: search results surfaced a
Soul Tree chime, a Smuggler Woodling, a Soul Ferry + Soul Threads, and (from
the official site itself) a Returner Woodling who grants a "Soul of Return."
This is consistent with the CLAUDE.md framing that "escape portal" is the
precise in-game term while "extraction" is fan/genre shorthand - the fan sites
mix both freely and do not agree on how many distinct escape mechanics exist.

## 4. Character / build planners

Real, and this is the one category with a standout responsible actor:
- **Gyldforge** (gyldforge.com) - "UNOFFICIAL BUILD LAB" but by far the best
  sourcing discipline found in this entire survey. States its equipment data
  comes from a dated Auction House capture ("exact market snapshot captured
  August 7, 2026... game build 24589503") and explicitly refuses to backfill
  gaps: "Gyldforge does not invent missing shape combinations. A profile
  absent from the capture is excluded, even if it may exist elsewhere." This
  is the only site in the survey that states its data has a timestamp, a
  build number, and a capture method, and explicitly commits to omitting
  rather than guessing - the same discipline CLAUDE.md mandates for Emberforge.
- MistfallDB build/talent planner (mistfalldb.com/builds).
- mistfallhunterguide.org/builds - per-class build pages.
No skill-tree/gem-socketing planner claims to be anything but fan-made; no
official planner exists.

## 5. Progression guides and walkthroughs

Real and broad coverage: leveling, camp/warehouse upgrades, and quest lines
are covered by thegameswiki.com (progression/skills/talents), mmoexp.com
(economy guide, "hidden quests" guide), onehitkill.space (market/warehouse
guide), and mistfallhunters.wiki. Best-practice example:
**mistfallhunterguide.org** states an explicit editorial policy - "No invented
player counts, drop rates, class names, weapon stats or code lists. Every page
answers one clear player question, and says where it learned the answer" -
and separately marks unverified launch data as unverified. It cites three tiers
of source (official Bellring/Steam materials, published dev communications,
community/creator hands-on testing) rather than presenting all three as equally
authoritative. This is the second standout for methodological transparency
alongside Gyldforge.

## 6. Overlays and companion apps

This is the important one. See the consolidated table below. Short version:
every dedicated Windows tool found that actually touches the running game is a
memory-cheat trainer, mod menu, or ESP/aimbot. Every safe, read-only resource
found is a plain website (wiki/planner/tracker) with **no local app and no
game-process interaction at all** - you alt-tab to a browser tab, nothing more.
**No tool of any kind was found occupying Lanternlight's actual niche**
(local companion app that reads game-written files or does passive screen
capture into its own window). That gap is the most important finding of this
whole survey for our purposes - see "What does NOT exist."

TH.GL, a legitimate multi-game overlay/companion platform (33 games listed),
was checked by name and does **not** list Mistfall Hunter among its supported
titles - a second confirmation of the same gap.

Also found, out of scope but worth recording: a fork of the DPI-circumvention
tool "zapret" (github.com/mihael13400-collab/Fork-zapret-for-MistfallHunter)
used by Russian players to reach the game's AWS-hosted servers around
regional ISP blocking. This is a network-censorship workaround, not a game
data tool, and does not touch the game process - noted for completeness only.

Cheat-storefront sites selling ESP/aimbot access for this game rank
prominently in search for "Mistfall Hunter hacks/cheats" (multiple vendor
domains observed). Per instructions these are not named or linked here; record
only that this category exists and is commercially active around this game.

## 7. Store / market content

Real, active player-driven economy, multiple competing fan trackers:
- **Mistfall Market** (mistfall.market) - dedicated Auction House price tracker
  (live prices, reference bands, "flip finder," stash value, price alerts).
- MistfallDB prices page (mistfalldb.com/prices).
- Gyldforge gem prices (captured/dated, see section 4).
- mistfallhunters.wiki/guides/auction-house.
Currency is "the blood of fallen gods." Reported price bands: a Legendary
lists roughly 220-325 floor to 7,000 ceiling, ~1,500 recommended. All tradable
gear from Common through Holy rarity except Damaged-tier, which is bound.
These figures come from watching the player-run Auction House UI, not from any
public market API (none exists - see section 9), so treat exact numbers as a
snapshot, not a spec.

## 8. Data mining / datamined content

**Measured NULL** on any credible decryption claim. No site claims to have
cracked the AES-encrypted pak chunks, and none would need to for most of what
they show: in-game tooltips already expose stat numbers directly to any player,
which is a legitimate (if tedious) source distinct from decryption. The one
piece of language that sounded like a datamining claim - Grand Wiki's mention
of excluding "mined fields" like internal table identifiers - reads on
inspection as templated copy from a multi-game wiki-hosting platform
("grandwiki.com" hosts wikis for many titles under the same subdomain pattern)
rather than a specific claim about this game, and it is not corroborated
anywhere else. Given the pak encryption fact in CLAUDE.md, the more likely
explanation for any "hidden" field a site claims to have is GVAS save-file
parsing (legitimate, same file format Lanternlight itself reads) or plain
invention, not pak decryption.

## 9. API surfaces

**Measured NULL** on anything game-specific. The only real API surface is the
generic Steam Web API that exists for every Steam title by virtue of appid
3282300 - ISteamUserStats endpoints (GetNumberOfCurrentPlayers, achievement
percentages if the game defines Steam achievements) and SteamDB's own
scraping (steamdb.info/app/3282300, raijin.gg/app/3282300). No Bellring/
Skystone-run API, no documented market API, no companion-app API, nothing
that would expose build math, drop tables, or match results. Every "database"
and "price tracker" in this survey is built by reading the game's own UI
(tooltips, Auction House screen) or files, not by calling an API - the same
constraint Lanternlight operates under.

## 10. Community hubs

Real and active:
- **Official Discord** - run by Bellring Games itself. Directly fetched from
  discordbotlist.com: 71,924 members, 22,194 online at fetch time (a second,
  independently-styled source put total members at ~70,344, consistent within
  normal drift). Channels include #mistfall-hunter-news and #bug-reports per
  the dev team, plus community LFG/build-sharing channels.
- **r/MistfallHunter** - exists (confirmed via multiple citing sites); could
  not be fetched directly (Claude Code's WebFetch cannot reach reddit.com in
  this environment, old.reddit.com included). Secondhand, unverified estimate
  from a fan-site aggregator: "~4,000+ weekly visitors, a few hundred posts/
  comments per week" - moderate size, smaller than Discord, treat as
  directionally useful only, not confirmed firsthand.
- **Steam Community discussion boards** for appid 3282300 - confirmed active,
  used as a live source in this survey for anti-cheat questions and the
  Russia connectivity threads referenced in section 6.
- A Twitch category for the game exists (twitch.tv/directory/category/
  mistfall-hunter); not further characterized.

## Overlays and the safety gate

| Tool | How it gets data | Classification | License |
|---|---|---|---|
| Mistfall Hunter Trainers (github.com/Mistfall-Hunter-Trainers) | Own words: "attaches to the running process, reads player health, resource stocks, skill charges, movement scalars and enemy vitality, then applies the selected modifications in real time," rendered via a DirectX overlay | **BANNABLE** - process memory read/write plus swapchain hook | No LICENSE file found |
| Mistfall-Hunter-Trainer (github.com/Speedatpinpoint) | Same trainer pattern - "Infinite Health, Stamina, and more" | **BANNABLE** - memory patching | Not visible |
| Mistfall-Hunter-Trainer (github.com/14219919973) | Same pattern, C++, "Infinite Health, Stamina" | **BANNABLE** - memory patching | Not visible |
| mistfall-hunter-esp (github.com/mistfall-hunter-esp) | Self-described: "see enemies, loot & traps through walls," radar overlay, "precision aimbot," claims "fully undetected" | **BANNABLE** - memory read and/or render hook for ESP, input synthesis for aimbot | Not visible |
| Mistfall-Hunter-Mod-Menu (github.com/toothflowcurse) | Name and topic tag match the trainer/mod-menu category; README returned 404 on fetch | **UNKNOWN**, leans BANNABLE by category convention - not independently confirmed | Not visible |
| Mistfall-Hunter-Executor-2026 (github.com/leonb-dev1903i8) | No description available; "Executor" is the standard naming convention for script-injection cheat loaders in this genre | **UNKNOWN**, leans BANNABLE by naming convention only - not independently confirmed | Not visible |
| Cheat storefronts (multiple vendor domains, not linked per instructions) | Advertise ESP/aimbot for this game | **BANNABLE** by their own advertised functionality | N/A, commercial, closed |
| TH.GL (th.gl) | Established multi-game overlay platform | **N/A - does not support this game** (checked by name, absent from its 33-title list) | N/A |
| MistfallDB, Gyldforge, MistfallHunter.app, Grand Wiki, Gamer Guides, mistfallhunterguide.org, etc. | Plain websites - browser tab only, no local install, no game-process contact of any kind | **SAFE-PATTERN by default (trivially so: they never touch the process)**, but see the data-provenance caveats above | Closed-source web services; no public repos found for most |
| guo812/mistfall-hunter-tools (github.com/guo812) | Static Next.js/Cloudflare Workers site, "10 tools, 58 routes," reads no game data at runtime, is itself a fan-data front end | **SAFE-PATTERN** (it is a website, same as above) | **MIT**, copyright "guo812 (via ShipSolo main assistant)" 2026 - confirmed by fetching the raw LICENSE file. No contradicting license field in package.json (which simply omits one, not a conflict) |
| Fork-zapret-for-MistfallHunter (github.com/mihael13400-collab) | DPI-circumvention network tool for regional ISP blocking, not a game-data tool | **Out of scope / does not touch game process** - noted, not classified | Not checked, irrelevant to vendoring |

Overall pattern for the license gate: **no repository found in this survey
carries a copyleft or source-available-but-restrictive license** (no GPL,
AGPL, or BUSL-1.1 turned up), so the specific traps CLAUDE.md warns about
(contradictory MIT-vs-UNLICENSED, unrendered `{{ organization }}` templates,
undisclosed co-authors) did not have a case to test against. Most repos simply
have no LICENSE file at all (default all-rights-reserved, not vendorable
regardless of the bannable-technique question). The one exception, guo812's
MIT-licensed tools repo, is clean and Apache-2.0-compatible - but it is a
website's frontend code, not something Lanternlight has a use for, and its
underlying data carries the same unverified-fan-data caveat as every other
site in this survey.

## What does NOT exist

- **No safe-pattern companion app or overlay for this game, anywhere**, from
  anyone. Not one log-reader, save-file viewer, second-screen tracker, or
  passive-capture OCR tool was found. The overlay/companion space for this
  title is currently binary: browser-tab websites with zero game contact, or
  memory-injection cheat tools with total game contact. Lanternlight's actual
  approach (read game-written files plus passive screen capture into an
  independent window) is not just untested by competitors, it is unoccupied.
- **No published numeric balance data from the developer** - patch notes are
  qualitative only, confirmed by direct fetch (section header note above).
- **No credible datamining / pak-decryption claim** by anyone (section 8).
- **No dedicated game API** of any kind, official or reverse-engineered
  (section 9) - only generic Steam Web API plumbing that predates this title.
- **No statistically-grounded win-rate or usage-rate meta site** - every tier
  list found is unsourced editorial opinion (section 2).
- **No Steam Workshop, level editor, or mod support**, and all 15 pak chunks
  are AES-encrypted - this was given as already-measured in CLAUDE.md and
  nothing found in this survey contradicts or adds to it.
- **A single, agreed-upon fact set does not exist even for basics.** Item
  rarity tier naming - about the most basic fact a fan site could get right -
  was found stated three incompatible ways across three independent sites
  (section 1). Treat cross-site "agreement" elsewhere in this ecosystem as
  possibly just everyone reading the same one primary source (the Steam page,
  which is genuinely public), not as independent corroboration.

## Usable as upstream for Lanternlight

Ranked by how much the source's own stated methodology can be trusted, not by
popularity. None of these should be vendored as code or trusted for exact
numbers - all are read-only cross-check candidates, to be verified against
Lanternlight's own observation before any figure is recorded in OBSERVED_IDS.md.

1. **Gyldforge** (gyldforge.com) - unofficial, but the only site that dates
   and build-numbers its data and explicitly refuses to backfill gaps. Best
   candidate for sanity-checking gear/affix/gem observations. No code license
   applies (closed-source web app, nothing to vendor) - use as a read-only
   cross-reference only, and only for facts it says it captured, not for
   anything it is silent on.
2. **mistfallhunterguide.org** - explicit "no invented... class names, weapon
   stats" editorial policy and per-page sourcing. Useful for cross-checking
   narrative/progression facts (quest names, camp/warehouse upgrade names)
   where being wrong is low-stakes. Same caveat: unofficial, no code to vendor.
3. **Official Steam news/patch notes** (steamcommunity.com/app/3282300/allnews)
   and **mistfallhunter.com** - highest trust tier per the doctrine (first-party),
   but limited value for Emberforge specifically: patch notes are directional
   only ("slightly increased"), never numeric, so they confirm *what changed*
   between versions, never *the value itself*. Still the correct source for
   canonical names (classes, zones, NPCs like the Returner Woodling) and for
   patch-version bookkeeping.
4. **guo812/mistfall-hunter-tools** (MIT license, confirmed) - the only
   permissively-licensed repository found in the entire survey. Worth a look
   purely as a UI/structure reference (Next.js tools/tier-list layout) if
   Lanternlight ever wants prior art for its own dashboard scaffolding - never
   for its embedded game data, which carries the same unverified-fan-data
   caveat as everything else here.

Nothing in this survey should be trusted for a cooldown, a damage coefficient,
or a stealth duration. Per the measurement doctrine, those stay unmeasured
until Emberforge measures them itself.

## Sources

Official / primary:
- https://store.steampowered.com/app/3282300/Mistfall_Hunter/
- https://steamcommunity.com/app/3282300/allnews/
- https://steamcommunity.com/app/3282300
- https://mistfallhunter.com/
- https://steamdb.info/app/3282300/

Databases / item and build data:
- https://mistfalldb.com/ (and /maps, /prices, /builds, /mechanics/items-and-affixes, /mechanics/trading-and-economy)
- https://mistfallhunter.grandwiki.com/ (and /items)
- https://mistfallhunter.app/ (and /items/, /affixes/, /skills/, /tier-list/, /codes/, /database/, /patch-notes/, /updates/)
- https://www.gamerguides.com/mistfall-hunter/ (database, maps)
- https://www.mistfallhunterguide.org/ (and /builds, /builds/tier-list, /database/items, /database/affixes, /guides/mistfall-hunter-community, /guides/mistfall-hunter-patch-notes)
- https://gyldforge.com/
- https://mistfall.market/
- https://mistfallhunters.wiki/ (guides/maps, guides/auction-house, items/gems, builds, updates/patch-notes, updates/official-links, tools/system-requirements)
- https://mistfallhunterwiki.org/patch-notes/
- https://showgamer.com/en/guides/4948-interaktivnaya-karta-mistfall-hunter-vse-lokacii-i-baza-dannyh
- https://thegameswiki.com/mistfall-hunter/
- https://mistfallhunter.me/ (game-data, news/bellring-anti-cheat-disclosure)
- https://mistfallhunterwiki.vercel.app/guides/economy-guide
- https://www.mmoexp.com/News/ (two guide URLs, economy and hidden-content)
- https://www.onehitkill.space/mistfall-hunter/market-warehouse-guide/
- https://questlog.gg/mistfall-hunter/

GitHub / code:
- https://github.com/topics/mistfall-hunter
- https://github.com/Mistfall-Hunter-Trainers
- https://github.com/Speedatpinpoint/Mistfall-Hunter-Trainer
- https://github.com/Mistfall-Hunter-Trainer (14219919973)
- https://github.com/mistfall-hunter-esp
- https://github.com/toothflowcurse/Mistfall-Hunter-Mod-Menu
- https://github.com/xiaozhuoluo/Mistfall-Hunter
- https://github.com/guo812/mistfall-hunter-tools (+ raw LICENSE, raw package.json)
- https://github.com/mihael13400-collab/Fork-zapret-for-MistfallHunter
- https://github.com/senlingll/mistfallloadouts.blog (found via search, not independently fetched)

Community:
- https://discordbotlist.com/servers/mistfallhunter
- https://www.mistfallhunterguide.org/guides/mistfall-hunter-community
- https://www.twitch.tv/directory/category/mistfall-hunter

Note: cheat-storefront domains that appeared in search results for
"Mistfall Hunter hacks/cheats" are deliberately not listed here per
instructions not to cite or link them.
