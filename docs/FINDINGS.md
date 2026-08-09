# Lanternlight - Feasibility Findings

Measured 2026-08-09 on Legion. Every line below is a probe result, not an
inference. Where something was not measured, it says so.

Project: **Lanternlight**. Combat / build math engine: **Emberforge**.
Target game: Mistfall Hunter (Steam appid 3282300).

Precedent: `C:\RedMoon` (Red Moon, V Rising). This document exists because the
RedMoon architecture does NOT transfer, and the reason had to be measured before
anything was designed.

## 1. The game

| Fact | Value | Source |
|---|---|---|
| Steam appid | 3282300 | store page, local appmanifest |
| Developer / publisher | Bellring Games / Skystone Games | Steam store |
| Released | 2026-07-29 (PC, PS5, Xbox Series) | Steam store |
| Genre | dark fantasy PvPvE extraction ARPG, solo or trio | Steam store |
| Classes | Mercenary, Sorcerer, Blackarrow, Shadowstrix, Seer, Withered Knight | community wikis, NOT yet verified in client |
| Engine | Unreal Engine 5 (IoStore, pak v12, utoc v8) | measured, section 3 |
| Installed locally | yes, `C:\Program Files (x86)\Steam\steamapps\common\Mistfall Hunter` | appmanifest_3282300.acf |
| Install size | 41,633,338,986 bytes (41.6 GB) | appmanifest |
| Build pin | buildid `24619162`, LastUpdated epoch `1786281053` | appmanifest |

The class list is the only line here taken from community sources. It is
UNVERIFIED and must not become an authoritative table without a first-party
check.

## 2. The blocking constraint: kernel anti-cheat

The Steam store page discloses **"Uses Kernel Level Anti-Cheat"**, named
**Bellring Anti-Cheat**, with a third-party EULA gate.

The shipped binary set corroborates a heavy commercial anti-cheat and SDK stack:

```
MistfallHunter\Binaries\Win64\gpHackerProc.dll        5.7 MB
MistfallHunter\Binaries\Win64\gpShell.dll
MistfallHunter\Binaries\Win64\sscronet.dll
MistfallHunter\Binaries\Win64\tgrpdownloader.dll
MistfallHunter\Binaries\Win64\GSDK_US\Steam\gp.dll gpm.dll gpmperf.dll
MistfallHunter\Binaries\Win64\GSDK_US\Steam\gsdk.dll parfait.dll bmf_hydra.dll
```

`GSDK_US\Steam\version.txt` reports `GSDK_VERSION_STRING "3.23.0.0"`.
`GSDK_US\Steam\config.json` declares `package_name "com.hermes.pstgame"`,
`app_id 937566`, `channel.steam_app_id 3282300`. The game therefore runs a
publisher account/SDK layer alongside Steam, plus an embedded CEF browser
(`libcef.dll`, full locale pak set).

### Consequences, non-negotiable

The entire RedMoon live-state half is **out of scope permanently**:

- No BepInEx or any other injected plugin.
- No process memory read, no handle open, no DLL load into the game.
- No packet capture or proxying of game traffic.
- No in-game overlay that hooks the game's swapchain or window.
- No input synthesis into the game window.

Any of these risks a permanent account ban on the operator's own account, and
several are plainly outside the EULA. This is a hard rule for the repo, not a
preference to be revisited when something is inconvenient.

## 3. Static data extraction: measured BLOCKED

UE5 IoStore. `MistfallHunter\Content\Paks` holds `global.utoc` / `global.ucas`
plus 15 chunks. Header fields were read directly (script:
`scratchpad/probe_paks.py`, read-only, 144 bytes per file).

Every content chunk carries the **Encrypted** container flag:

```
global.utoc            : tocver=8 entries=1     flags=none                        keyguid=ZERO
pakchunk0-Windows.utoc : tocver=8 entries=38825 flags=Compressed|Encrypted|Indexed keyguid=ZERO
pakchunk2-Windows.utoc : tocver=8 entries=2902  flags=Compressed|Encrypted|Indexed keyguid=ZERO
pakchunk4-Windows.utoc : tocver=8 entries=3906  flags=Compressed|Encrypted|Indexed keyguid=ZERO
pakchunk6-Windows.utoc : tocver=8 entries=15956 flags=Compressed|Encrypted|Indexed keyguid=ZERO
pakchunk8-Windows.utoc : tocver=8 entries=11310 flags=Compressed|Encrypted|Indexed keyguid=ZERO
pakchunk9-Windows.utoc : tocver=8 entries=9187  flags=Compressed|Encrypted|Indexed keyguid=ZERO
... 15 chunks total, all Encrypted, 101,500 entries across all TOCs
```

Every legacy `.pak` sidecar reports `pakver=12 encrypted_index=True`.

`keyguid=ZERO` means a single global AES key rather than per-chunk named keys.
That key is not on disk in plaintext. Recovering it means either dumping it from
the running process (forbidden by section 2) or static reverse engineering of a
binary that ships with a kernel anti-cheat. **Neither is acceptable here.**

Loose-file sweep of the whole 41.6 GB install for `*.ini *.json *.csv *.uasset
*.cfg` returned exactly three files, none of them game data:

```
Engine\Config\StagedBuild_MistfallHunter.ini            0 KB
MistfallHunter\Binaries\Win64\GSDK_US\Steam\config.json
MistfallHunter\Binaries\Win64\GSDK_US\Steam\vk_swiftshader_icd.json
```

**Conclusion: there is no first-party static data table available to this
project.** RedMoon's extractor half is dead too.

## 4. Local runtime surface: EXISTS, and it is the project's spine

The pre-launch sweep found nothing. The operator launched the game on
2026-08-09 08:18 and a second read-only sweep found a full UE Saved tree.
This section supersedes the pre-launch negative.

`%LOCALAPPDATA%\MistfallHunter\Saved\` created 08:18:56:

| Artifact | Size | Value |
|---|---|---|
| `Logs\MistfallHunter.log` | 567 KB after 10 min, live-appending | primary live surface |
| `SaveGames\*.sav` (4) | 2-2.7 KB each | plain UE GVAS, magic `47 56 41 53`, NOT encrypted |
| `Config\Windows\GameUserSettings.ini` | 1398 B | settings only |
| `Config\Windows\Engine.ini` | 7228 B | plugin roster only |
| `AvgPrice_937566.ini` | 37 B | market/trade-price cache, currently empty |

Readable from the log without touching the process: map and sublevel
transitions with ms timestamps, `match state changed to <state>`, a `match id`
field, `setClassGender inclassid ==NN`, weapon config ids (`OnRep_WeaponCfgId`),
equipment asset paths, `seasonId`, server region, gateway hostname. Log
categories are namespaced (`LogStk`, `TS.Avatar`, `TS.Dungeon`, `TS.Camp`,
`TS.Inventory`, `TS.Network`, `Puerts`).

GVAS saves parse with any GVAS reader: `LoginOptions.sav` yields
`SelectedServer` (`official_NA`) and `AccountName`; `UserSettings_v1.sav` yields
the settings block including `bWarehouseAutomation`.

### Measured limits, not assumptions

- The probed session reached camp and character creation only. **No raid was
  entered**, so loot names, extraction events and match results are
  **unmeasured, not absent**. A second recon after a real raid is required
  before any of that is designed against.
- `GSDKCache\accountList.json`, `user.json`, `user_infos.json` and
  `gsdk_app_log.db` sit under the install dir beside the anti-cheat binaries.
  They were listed, never opened. Treat as out of bounds.
- The registry sweep was capped at depth 2 and found nothing. Not exhaustive.

### PII rule, binding on the public repo

The log carries the operator's SteamID64, Steam persona, GSDK openID/userId, an
EOS ProductUserId, and an IP-resolved city/state/country. **No log excerpt,
fixture or test sample may be committed without redaction**, and the redactor
must be tested. This is a `.gitignore` plus a scrubber, not a habit.

## 5. Steam Web API: thin but real

Probed keyless, live:

- `GetGlobalAchievementPercentagesForApp` returns **20 achievements**, names are
  opaque (`TrophyNo_2` 91.1 pct, `TrophyNo_3` 87.9, `TrophyNo_9` 69.3, ...). No
  display names without a key and the schema call.
- `GetNewsForApp` works (patch note titles, e.g. "August 7 Server Online Update
  Notice", "August 6 Live Update"). Usable as a patch-detection trigger.
- Player counts are available via SteamDB / the current-players endpoint.

Not probed: `GetSchemaForGame` and `GetUserStatsForGame`, both of which need a
Steam Web API key. No Steam key exists on this machine yet.

## 6. What is left, and it is a real project

Three surfaces survive section 2, all of them read-only and none touching the
game process:

1. **Operator-measured data.** Numbers observed in the client and recorded by
   hand or by OCR. This is slow, and it is the only first-party-truthful path.
   It inherits RedMoon's doctrine directly: omit a field rather than guess it,
   and keep "unmeasured" distinguishable from "measured zero".
2. **Passive screen capture and OCR** of the operator's own display, on a second
   screen, with no overlay and no injection. RC already runs this pattern.
3. **Community reference data**, clearly marked as unverified third-party, never
   promoted to a first-party table, and never vendored without a license check.

The shape that follows is the inverse of RedMoon: **Emberforge (the math) plus a
build planner is roughly 90 percent of the project, and live state is close to
zero.** The hard engineering problem is not extraction, it is data provenance -
proving where every number came from and refusing to emit one that has no
source.

## 7. Open questions for the next session

1. Launch the game once and re-sweep for `Saved\Logs`. Decides whether surface
   (4) exists at all.
2. Is a curated, measurement-backed dataset acceptable as the foundation, given
   it means the project ships slowly and starts mostly empty?
3. Scope of the first slice: which single class, and which single question does
   Emberforge answer first?
4. Does the planner target the operator only, or a public web-facing tool?
5. Steam Web API key: worth registering for achievement schema and patch
   detection?
6. Licensing posture. RedMoon is Apache-2.0 public. Same here, with a Bellring
   Games / Skystone Games non-affiliation notice and a no-redistributed-assets
   statement that is trivially true because nothing is extractable anyway.

## 8. Probe reproducibility

`scratchpad/probe_paks.py` reads only the first 144 bytes of each `.utoc` and
the last 221 bytes of each `.pak`. It opens no process, loads no game module and
writes nothing. It should move into the repo as `tools/probe_paks.py` with a
test asserting the encrypted-flag finding, so a future patch that ships
unencrypted paks is detected rather than assumed away.

## 9. Dungeon recon, 2026-08-09 second pass

Measured by re-reading the live log after the operator had played for 3h44m. No
capture session was needed: the data was already on disk, and section 7's
framing of these as "unmeasured" was a statement about the world at 08:28, not
about the game.

**Re-probe first.** Three documented facts had gone stale within one session:

| Fact as written | Measured on re-probe |
|---|---|
| Log is 567 KB | 6.1 MB and growing |
| `AvgPrice_937566.ini` is 37 bytes and empty | 343 bytes, 30 trade prices |
| Four `.sav` files | Five - `CampData_<userId>.sav` is new |

Log span 13:18:57Z to 17:03:01Z at the time of analysis, 142 distinct categories,
48,032 lines of which 47,013 parse.

**The size, the line count and the span above were three separate reads of a
file that was still being appended to**, and the first version of this section
presented them as one snapshot. They are not: the 48,032-line boundary sits at
byte 6,206,426, while byte 6,125,488 falls at line 47,364. Nothing downstream
depends on the exact byte count, so the figure is given as "6.1 MB and growing"
rather than a spurious exact number. Recorded because this section opens by
scolding stale numbers and then produced some.

### 9.1 The vocabulary is not the one the roadmap assumed

Searching for the words we expected returned nothing, and that is the finding.
`extract` and `extraction` appear **zero** times; `raid` appears **zero** times.
The game's own nouns are **dungeon** and **escape**. A grep for the wrong word
returns a clean negative that means nothing, so this is recorded before anything
else that depends on it.

### 9.2 Dungeon lifecycle, both runs

`TS.Utils: [LevelSwitch]` carries the spine. Two dungeon entries were made, and
their outcomes differ, which is what makes the pair worth keeping:

| Time (UTC) | Target | Options | Reading |
|---|---|---|---|
| 13:20:15 | `CampMap` | `option=GAA=` | hub |
| 14:03:58 | `Prologue_New` | `levelId=1&roomModeId=9&matchId=0` | entry, run 1 |
| 14:07:25 | `Startup` | `kicked` | run 1 ended by disconnect |
| 14:10:44 | `CampMap` | `option=GAA=` | back to hub |
| 14:32:40 | `Prologue_New` | `levelId=1&roomModeId=9&matchId=0` | entry, run 2 |
| 14:53:35 | `CampMap` | `option=GAU=` | back to hub after a successful escape |

`matchId=0` on both entries. The Prologue is not matchmade, so a real raid
should carry a non-zero `matchId` - that is the discriminator to check next, and
it is a prediction, not yet an observation.

**Hypothesis, two samples, not a finding:** the camp-return option string
differs between the kicked run (`GAA=`) and the escaped run (`GAU=`). These
base64-decode to bytes `[24, 0]` and `[24, 5]`. A one-byte difference correlated
with outcome is suggestive and nothing more. Two samples cannot establish an
encoding, and this must not be treated as an outcome field until it is watched
varying deliberately.

### 9.3 Outcome states are a gameplay-tag namespace

Counted over the whole log:

| Tag | Count |
|---|---|
| `Game.PlayState.Gaming` | 13 |
| `Game.PlayState.Spiritual` | 12 |
| `Game.Net.Online` | 6 |
| `Game.PlayState.WaitSpiritual` | 6 |
| `Game.PlayState.Escape` | 5 |
| `Game.PlayState.Death` | 1 |
| `Game.EscapeType.GroveSprite` | 1 |

**Attribution matters here and the first version of this section got it wrong.**
Comparing the `PlayerName` on each `OnRep_PlayStateTag` line against the name
the operator actually plays under gives this split.

| Player | Tags |
|---|---|
| the operator | `Escape` 2, `Gaming` 5, `Spiritual` 1, `WaitSpiritual` 1 |
| a second player | `Death` 1 |

**The operator has no `Death` tag. The single death in this log is somebody
else's.** The earlier sentence here - "both sides of the roadmap's acceptance
criterion are present" - was false, and it would have closed half a roadmap
item on another player's death. It is retracted.

Separately, `TS.Dungeon: OnPlayerDead` at 14:48:24.786 does carry the operator's
persona, and `LogBlueprintUserMessages` at the same millisecond reads
`CalculatePvpSkillScoreState, not pvp death`. Whether that line names the victim
or the killer is **not** established by the line alone, so no death is claimed
for the operator from it either.

`Spiritual` and `WaitSpiritual` remain unexplained. The operator holding exactly
one of each, in a run that ended in `Escape`, is suggestive of a downed-then-
recovered state - but that is inference, and it is written here as a question,
not an answer.

### 9.4 The escape mechanic, named

`FixEscapeActor` spawns and destroys `FixEscapeBell` map points - 13 distinct
handles, `{1..10, 14, 15, 19}`, **not a contiguous 1-to-19 range**; 11 through 13
and 16 through 18 never appear.

`SEscapePortalSpawner` **did not place anything.** All six of its lines are two
`Check SEscapePortalSpawner Initialize event` and four
`Warning: SEscapePortalSpawner.initialize: No escape portal cfg found for !`.
The first version of this section said it "places a portal", which is a producer
inferred from a name - the exact trap `CLAUDE.md` names as "a rendered field is
not evidence of a producer". The portal actually used is a
`BP_PlacedEscapePortal_GroveSprite_CE_C`, spawned at 14:51:54.638 by
`BP_EscapePortalSpawner_GroveSprite_C`.

The extraction itself is two blueprint lines about nine seconds apart:

```
[BP_PlacedEscapePortal_GroveSprite_CE_C_...] Give Bell: <actor> enter portal area <portal>
[BP_PlacedEscapePortal_GroveSprite_CE_C_...] Player<actor> use portal : <portal>
```

`Game.EscapeType.GroveSprite` implies escape types are a taxonomy with more than
one member. Only `GroveSprite` has been seen. The others are unmeasured.

### 9.5 Inventory verb space

Six opcodes observed via `TS.Inventory: [SInventoryManager] IvtrOperation opt:`:

| Opcode | Count |
|---|---|
| `server_AddItem_addItem` | 32 |
| `server_PickupLootItem_setItemCount` | 6 |
| `RequestUseItem_setItemCount` | 5 |
| `server_MoveItem_removeItem` | 5 |
| `server_EquipItemFromPickupLoot_addItem` | 4 |
| `RequestUseItem_removeItem` | 3 |

Loot pickups carry `itemId`, `cfgId`, `count`, `toSlot`, `fromActor` and a
`context` - `EnemyCorpse` observed. No item **names** appear anywhere in the log,
only numeric `cfgId`s, so no id-to-name binding is claimed here.

### 9.6 The market cache and the loot stream share one id space

The most useful structural result of the pass, and the project's first
cross-surface join.

The log carries item ids in two field shapes - `cfgId:` and a short `cfg:` -
and "appeared in the item stream" is **not** the same fact as "was picked up
off the ground". Two independent measurements of this disagreed until they were
scoped precisely, so the scope is stated with every number:

| Scope | Distinct ids |
|---|---|
| `RequestPickupLoot` lines only (89 lines) | 31 |
| `cfgId:` **with no space**, which is the `TS.Inventory` shape | 35 |
| `cfgId:` **allowing a space**, anywhere in the log | 45 |
| `cfg:` short form anywhere | 33 |
| priced in `AvgPrice_937566.ini` | 30 |

**The two `cfgId:` rows are the same field and differ only by one space.**
`TS.Inventory` writes `cfgId:901201`; `TS.FTE` writes `cfgId: 3010401` with a
space. A pattern of `cfgId:(\d+)` silently drops every `TS.FTE` line, and the
first version of this table reported that 35 under the label "anywhere in the
log", which it is not. Ten ids are only visible with the space allowed: `0`,
`10001`, `10101`, `10231`, `10301`, `10401`, `1210301`, `1410301`, `1510301`,
`3010401`. An empty grep is a claim about the pattern.

That correction pays for itself immediately: `3010401` is the live `holding-`
id from section 9.6's join, and it appears in the `TS.FTE` stream as
`FTE.Event.ChangeWeapon, cfgId: 3010401` - a weapon swap emitting the holding id
in a cfgId field. That is independent corroboration of the join below, and the
narrow pattern had hidden it.

- **All 30 priced ids appear somewhere in the item id stream. Zero exceptions.**
  (True under either `cfgId:` scope - the ten space-only ids add nothing priced.)
- **28 of the 30 were actually picked up.** The two that were never picked up
  are `1720201` and `3020401` - and `3020401` is the id the operator's character
  was observed *holding*, so an equipped weapon is priced without ever being
  looted. That is the expected result, and it is why the distinction matters.
- 5 ids appear in the item stream but carry no price: `101`, `901101`, `999998`,
  `1110301`, `1310301`.

Stated carefully, because one session cannot separate the two readings: this
establishes that the market cache and the item stream are **keyed the same way**.
It does **not** establish that the game prices an item *because* it was
encountered. A second session that loots a disjoint set is what would separate
those.

The first version of this section said "every one of the 30 priced ids was
looted, with zero exceptions". That was measured over `cfgId:` anywhere and then
described using the word "looted", which is a narrower claim than what was
measured. Both underlying numbers were right; the sentence joining them was not.

### 9.7 The post-run write chain, to the second

File modification times joined against log timestamps, all UTC:

| Time | Event |
|---|---|
| 14:53:16 | escape portal used |
| 14:53:35 | `LevelSwitch` back to `CampMap` |
| 14:53:36.66 | `AvgPrice_937566.ini` written |
| 14:53:37.67 | `CampData_<userId>.sav` written |

So the market cache and the camp save are written on **return to camp**, about a
second apart, not continuously and not at the moment of extraction. A watcher
polling either file should expect a burst at camp re-entry and silence
otherwise.

The file's own `[PriceTime]` is `1786285800` = 14:30:00Z, twenty-three minutes
*before* the file was written, so `PriceTime` is a market-bucket stamp and not a
write time. `TS.Default: [TradeModel]` refreshes a price stamp roughly once per
minute in 30-minute buckets, and at 13:21 it was emitting buckets stamped around
05:30 - an offset of about eight hours that is **not explained** and is not
assumed to be a timezone.

### 9.8 A P0 defect this pass exposed in our own code

Running the current redactor over this log leaves **684 of 686 occurrences of
the operator's Steam persona in place**, and `assert_clean()` returns cleanly on
a line that still contains it. Two independent root causes:

1. Keyed rules stop their value match at whitespace, so a two-token display
   name is only half masked.
2. The persona also appears with no key at all - as a positional field between
   commas, and after verbs such as `PlayerOpenTreasureBox` - which no key
   pattern can reach.

This blocks the roadmap's raid-recon acceptance criterion outright, because that
criterion requires committing a redacted log excerpt as a fixture and the
excerpt would carry the persona. See `docs/LEDGER.md`.

Related and separate: `CampData_<userId>.sav` embeds the operator's numeric
userId **in its filename**. Redaction that only cleans file *contents* would
publish it anyway. Any `.sav` fixture must have its name rewritten too.

### 9.9 Still unmeasured after this pass

Named so they are not later mistaken for absent:

- A real matchmade raid. Everything above is the **Prologue**, `matchId=0`. No
  non-zero `matchId` exists anywhere in this log under any spelling.
- Any escape type other than `GroveSprite`.
- What `Spiritual` and `WaitSpiritual` actually are.
- Any item name. Only numeric `cfgId`s exist in the log.
- Whether the camp-return option byte carries the outcome (see 9.2).
- Whether the operator has ever died. No `Game.PlayState.Death` is attributed to
  them (see 9.3).

### 9.10 A second player was present, and PvP is not a clean null

Retracting a claim the first version of 9.9 made. It listed "PvP of any kind" as
unmeasured on the strength of `OnlinePlayerCount: 0`, and asserted "no second
player was present". Both are wrong, and the second one was contradicted by
evidence already in the file:

- **Exactly two distinct `PlayerName` values appear.** One is the operator. The
  other is a different player whose display name carries 6 non-ASCII
  codepoints. It is not a bot - bots are actors (`BP_Adventure_Bot_C`), not
  `PlayerName` values.
- That second player owns the log's only `Game.PlayState.Death`.
- `TS.SDK: [GSDKAnalytics]` emits `client_battle_enter_pvp` twice and
  `client_battle_leave_pvp` twice, between 14:50:24 and 14:51:15 - bracketing
  that death at 14:51:03.
- And `CalculatePvpSkillScoreState, not pvp death` at 14:48:24 shows the client
  runs a PvP-vs-not classification on death events at all.

What this does **not** establish: that the operator fought anyone. The analytics
event names may cover a mode, a zone, or a scoring pass rather than combat, and
`OnlinePlayerCount: 0` is genuinely in the log and genuinely unexplained
alongside a second `PlayerName`. So PvP moves from "unmeasured" to **"contact
observed, mechanics unmeasured"**, which is a different and more useful state.

The process lesson is the one this document already teaches and then broke:
`pvp` was never grepped before being filed as absent.

**Also corrected:** team tags are `1-1`, `1-2` **and `1-3`**, two occurrences
each. The first version listed only the first two.

**Safety consequence, and it is new.** The log carries a **third party's**
persona, not just the operator's, and that persona is non-ASCII. Any fixture
drawn from a session with other players in it leaks somebody who never consented
and is not the operator. `lanternlight/redact.py` must treat other players'
names as in scope, and the ASCII-only rule means such a name cannot even be
committed verbatim without also failing `tests/test_ascii_hygiene.py` - a second
guard that happens to help here, but only by accident, and accidents are not a
redaction strategy.
