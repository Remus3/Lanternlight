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
| Build pin | buildid `24813185`, LastUpdated epoch `1787126796` (2026-08-19T08:06:36Z) | appmanifest, re-read 2026-08-25 |
| Previous build pin | buildid `24619162`, epoch `1786281053` (2026-08-09T13:10:53Z) | appmanifest, 2026-08-09 - every id observed on or before 2026-08-09 predates the patch and is UNCONFIRMED on the current build |

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
| Four `.sav` files | **Six** - `CampData_<userId>.sav`, then `Deck.sav` |

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

### 9.3.1 The death state machine, resolved

This section was wrong twice before it was right, and the thing that settled it
was **the operator saying "I had one death, in the tutorial"**. That is
first-party attestation, and it beat two rounds of log-reading that had each
produced a confident wrong answer. The arc is recorded because the failure mode
is instructive, not to be tidy.

The operator's own `OnRep_PlayStateTag` transitions, in order:

| Time (UTC) | Transition |
|---|---|
| 14:48:24.787 | `Gaming` -> `WaitSpiritual` |
| 14:48:31.798 | `WaitSpiritual` -> `Spiritual` |
| 14:48:47.909 | `Spiritual` -> `Gaming` |
| 14:53:21.443 | `Gaming` -> `Escape` |

At 14:48:24.786, one millisecond before the first transition,
`TS.Dungeon: OnPlayerDead` carries the operator's name. Within the same second
the client creates the widget `WBP_GameMode_Lost` and starts
`SpectatingCtrlComponent`; five seconds later `tryStartSpiritual` runs with
`spiritualResurrectCfg 3` and plays `SpiritualRebornCinematicView`.

So, measured and no longer a question:

- **`WaitSpiritual` is the downed/dead state.** It is entered at the instant of
  `OnPlayerDead` and it is what shows the loss screen.
- **`Spiritual` is the resurrection state.** `SpiritualResurrectModel`,
  `AdventurerSpiritualComponent` and `BP_ResurrectVolume_C_*` drive it, and the
  component caches the nearest resurrect volume as the player moves - four such
  cache lines appear in the minutes before the death.
- **The operator died exactly once, and recovered.** One death, one
  resurrection, then an escape - which matches the attestation precisely.

**The critical consequence for any future death detection:** the operator's
death is **not** recorded by a `Game.PlayState.Death` tag. It is recorded by
`OnPlayerDead` plus the `WaitSpiritual` transition. Keying a death detector on
`Game.PlayState.Death` would have missed this death entirely - which is exactly
what the first two versions of this section did.

### 9.3.2 The one `Game.PlayState.Death` belongs to a bot the operator killed

The single `Death` tag carries a different, human-looking name. It is a bot:

```
TS.AI: generateBotPlayerStateData classId 13, Level: 1, roleId: -14801, temaId: 254, name: <name>
[leaderRankScoreComponent]: ... "bIsPlayer":true, "bIsBot":true ...
[DungeonLevelModel] PlayerKillPlayer <operator> -> <bot>
[DungeonPlayerStae] OnPlayerKillPlayerMatchScoreRecord, victimPlayerState.name-<bot>, beKilldByPlayer = true
```

**Bots are indistinguishable from players by name, and `bIsPlayer` is `true`
for them.** This one carries a plausible human display name in CJK characters,
`classId 13` (Shadowstrix) and level 1. The only reliable discriminators
observed are `bIsBot: true` and a **negative** `roleId`. Any future analysis
that counts opponents, kills or deaths must use those, or it will report bot
kills as player kills - which is precisely the error this section made.

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

### 9.9.1 Not every setting is persisted locally - some exist only in the log

Operator-attested 2026-08-09: they swapped the primary and secondary attack
binds (right click as primary) and turned **off** invert-look.

Both statements are confirmed by first-party data, and the two settings behave
completely differently:

**The keybind swap is in the save.** `EnhancedInputUserSettings.sav` persists
exactly three mapping rows - `KB_Blackarrow_Major_Action -> RightMouseButton`,
`KB_Blackarrow_Minor_Action -> LeftMouseButton`, and one unbound row - while the
log carries 81 default pairs. **The operator changing exactly those binds
confirms the save stores only OVERRIDES**, which had previously been recorded as
a strong reading rather than an established fact. It is now attested.

**The invert setting is nowhere on disk.** `InvertCameraYAxis` appears in
`TS.Settings: [Settings]InvertCameraYAxis changed:` - set to `1`, then to `0`,
matching the operator turning it on and back off - and is then reported through
`[GSDKAnalytics] Report setting`. A search of the entire `Saved` tree finds it
in **one** file: the log. It is absent from `UserSettings_v1.sav`, from
`EnhancedInputUserSettings.sav`, and from `Config\Windows\GameUserSettings.ini`.

So it is most likely held **server-side**, against the account. That is a
design constraint, not a curiosity:

> **A settings reader built on the `.sav` files alone is silently incomplete.**
> Some settings never touch local storage, and the log is their only local
> witness. Worse, the log is the *transient* surface - it rotates - so a setting
> observed once may become unobservable.

Full local property inventory, measured, so the gap is visible rather than
assumed:

| File | Properties |
|---|---|
| `UserSettings_v1.sav` | 14 graphics and gameplay flags (`bEnableDLSS`, `bMotionBlurEnabled`, `bWarehouseAutomation`, `bHurtedAutoCloseInventory`, `bEnableCrossPlay`, ...) |
| `LoginOptions.sav` | `SelectedServer`, `SDKType`, `AccountName` |
| `EnhancedInputUserSettings.sav` | `CurrentProfileIdentifierString` plus the key-profile object |
| `CampData_<userId>.sav` | `LevelModeMap` |
| `Notice.sav` | `readedGameBulletinId` |
| `Deck.sav` | `DeckDefaultOpenPage`, a `MapProperty<IntProperty, IntProperty>` |

**Updated the same day, twice more.** A seventh save,
`StandaloneSlot_<roleId>.sav`, appeared at 15:39 at **41,564 bytes** and had
grown to 46,619 bytes minutes later while still being written. It is twenty
times larger than any other save and its **filename embeds the operator's
roleId**, so it carries the same name-level PII hazard as `CampData_<userId>.sav`.

It does **not** parse: it uses `StructProperty<F_PlayzoneSaveData>`, a property
type never measured here, and `lanternlight/gvas.py` **raises** on it rather
than returning a partial parse. That is the raise-on-unknown guard being
validated in the wild by a genuinely new type - better evidence than any test
could give, and the reason the guard exists.

`Deck.sav` did not exist before this session. It appeared at 14:36 local, during the mail-and-equip sequence, and `CampData_<userId>.sav` was rewritten at 14:41. **The set of save files is not fixed** - a reader must enumerate the directory rather than expect a known list, and a fixture set pinned to five files silently stops covering the surface.

Also attested and not yet located in any surface: the operator owns the **Deluxe
edition**, has claimed **three Twitch drops**, and has linked Discord for its
drop. No entitlement, DLC or drop id has been observed in the log or the saves.
Recorded as unmeasured, not absent.

### 9.9.2 Camp is a different surface, and the log is not an inventory ledger

Measured over a 953 KB log segment bracketed by wall clock around the
operator's first NPC quest turn-in - talking to the camp NPC, opening mail,
claiming rewarded items, equipping some, and a currency change.

The headline is a **measured negative** and it constrains everything downstream:

| Marker | Before the segment | During |
|---|---|---|
| `IvtrOperation` | 55 | **0** |
| `DungeonInventoryComponent` | present | **0** |
| `TS.Camp` | 109 | 340 |
| `TS.NPC` | 137 | 324 |

**The inventory-mutation line is dungeon-only.** Items granted by mail arrived
with no logged `cfgId` at all - not one new item id appears in the whole
segment, even though items were received and equipped. `TS.Inventory` still
appears, but carries UI and state rather than mutations.

> A tracker built on the log would silently miss **everything** granted outside
> a dungeon. The log records loot picked up in a raid; it does not record what
> the game hands you.

What camp does emit, via `TS.Camp: [CampPlayerController]`:

```
server_ApplyEquipData {"cfgId":1110301}
server_ApplyEquipData {"slot":1,"cfgId":1210301}
```

and an equipment slot array from `TS.Avatar`:

```
server_EquipArmors: <actor> cfgIds-[1110301,1210301,1310301,1410301,1510301,0,1720201]
```

Seven slots, slot index 5 empty (`0`). Every id in it was already known from the
dungeon and market surfaces, which is further evidence for the single shared
item id space in 9.6.

NPC interaction ids observed: `npcId` values 1, 2, 4, 5, 6, 18, 22; dialog ids
10001 through 10004, each followed by `deliver award`; greeting ids 820105,
820402, 820504, 821305, 829002, 901011. **No npcId is bound to a name** - that
needs a screen capture joined on wall clock, exactly as the class ids were, and
was not done.

**A caution about how this was nearly miscounted.** The first pass reported "no
new item ids" using `cfgIds?[:\-]\s*(\d+)`, which cannot match
`cfgIds-[1110301,...]` because of the bracket. The conclusion happened to be
right and the evidence for it was worthless. Third time this session that a
pattern, not the codebase, was the thing being measured.

### 9.10 PvP is still a clean null, and how that was got wrong twice

This section previously claimed a second player was present and that PvP had
moved to "contact observed". **Both are retracted.** The second `PlayerName` is
a bot (9.3.2), `OnlinePlayerCount: 0` was correct all along, and no human
opponent appears anywhere in this log.

The full arc, kept because each step failed differently:

1. The first version filed PvP as unmeasured **without ever grepping `pvp`** -
   an unsearched word reported as an absence.
2. An adversarial pass found 6 `pvp` hits and correctly called that out.
3. Reacting to those hits, this section over-corrected to "a second player was
   present" - reading a human-looking display name as a human.
4. The operator's own attestation, plus `generateBotPlayerStateData` and
   `bIsBot: true`, settled it: bot.

What the `pvp` hits actually are: `TS.SDK: [GSDKAnalytics]` emits
`client_battle_enter_pvp` and `client_battle_leave_pvp` twice each between
14:50:24 and 14:51:15, and `CalculatePvpSkillScoreState, not pvp death` runs at
the operator's death. So the client **has** a PvP-vs-not classification and
emits PvP-named telemetry inside a bot-only Prologue run. That means the
telemetry name describes a mode or a scoring path, **not** the presence of a
human opponent, and it must not be used as a PvP detector.

**Also corrected:** team tags are `1-1`, `1-2` **and `1-3`**, two occurrences
each. The first version listed only the first two.

**Redaction note, corrected.** An earlier version of this section called the
second name "a third party's persona" and treated it as somebody's real
identity. It is a generated bot name, so nothing here was a consent problem.
The underlying rule still stands for a different reason: a real raid **will**
contain real other players, so `lanternlight/redact.py` treating any
`PlayerName` as in scope is correct - it just was not demonstrated by this log.

## 10. The transient dungeon save, decoded from its whole lifetime

`StandaloneSlot_<roleId>.sav` is the file the game writes while a dungeon run is
in progress and deletes when the run ends. Its entire 263-generation lifetime
was captured on 2026-08-09, from first appearance at 2,190 bytes to last sight
at 177,878 bytes. **The bytes live at `C:\ll-captures\saves\`, outside this
repository, and are not committed** - the filename embeds the operator's roleId.

Everything in this section was re-measured from those bytes by the research
lane, against claims another agent had already filed. Two of the eight filed
claims did not survive, which is the point of re-measuring. Where a number here
corrects an older line in this document or in `ROADMAP.md`, the correction is
named rather than quietly applied.

Method for the whole section: `lanternlight/gvas.py` in strict mode over all 263
generations, plus regex over the raw bytes where the question was about byte
shapes rather than about parsed values. **All 263 parse, zero failures**, which
supersedes section 9.9.1's "It does **not** parse" - that was true of the reader
at 15:39 on 2026-08-09 and stopped being true the same day.

### 10.1 It starts as a stub and accretes properties in a fixed order

The class is `StandaloneLevelSaveData_C`, a Blueprint class under
`/Game/Blueprints/TypeScript/module/Level/`.

The **largest generation holds 17 top-level properties, not 19.** The filed
claim said 19 and then listed 17; the list was right and the count was wrong.
Recorded rather than silently fixed, because it is this repository's own
anti-pattern - a count beside a list, where only the list was checked.

Across all 263 generations there are exactly **six** distinct top-level key
sets, and they form a strict growth chain - every shape is a superset of the one
before it, and **nothing is ever removed**:

| Generation index | Properties | What appeared |
|---|---|---|
| 0 | 4 | `MatchID`, `BattleId`, `AutoSaveTempSlot`, `AutoSaveFinalSlot` |
| 1 | 12 | `PlayzoneData`, `PlayerData`, `DoorData`, `MonsterData`, `BotData`, `BotSpawnerData`, `IdGeneratorData`, `DamageCollectonDataSet` |
| 13 | 14 | `LeaderRankScoreData`, `LevelDetail` |
| 25 | 15 | `TreasureBoxMap` |
| 127 | 16 | `DropItemMap` |
| 259 | 17 | `EscapePortalTransforms_Full` |

`DamageCollectonDataSet` is spelled that way by the game. It is not a typo in
this document and must not be "corrected" in any reader.

So **a single snapshot of this file is a snapshot of a schema, not of the
schema.** A reader that assumes 17 properties fails on 259 of the 263
generations, and a reader that assumes 4 fails on 262 of them. The only safe
posture is to treat every top-level property as optional and absent-means-absent
- which is the measurement doctrine this project already commits to, arriving
here as a hard requirement rather than a preference.

Size is **not** monotonic even though the key set is: the byte length falls at 7
points across the 263 generations. Section 2 of `ROADMAP.md` already records
that the file is rewritten in place. Both facts together mean a poller can read
a shrinking file whose schema is still growing.

### 10.2 A filed count that was a snapshot - `NumIdToUUID`

`IdGeneratorData` holds three fields: `CurrentNum`, `NumIdToUUID` and
`UUIDToNumId`. The two maps are exact inverses of each other in every
generation checked.

`ROADMAP.md` item 2b describes "a 23-entry `IdGeneratorData.NumIdToUUID` map".
Measured over the whole lifetime:

| Fact | Measured |
|---|---|
| Entries in the largest generation | **91** |
| Entries in the first generation that has the map | 16 |
| Distinct entry counts across the lifetime | 35 |
| Generations where the count is exactly 23 | **5**, indices 25 to 29 |
| Monotonically non-decreasing | yes |

So the roadmap's 23 is neither wrong nor a property of the file. It is a reading
of one of 263 moments, filed as though it described the artifact. **A filed
count is a hypothesis**, and this is the same anti-pattern the roadmap itself
names two sections earlier. The practical cost is real: item 2b sizes the
sanitised fixture against a 23-entry map, and the fixture will meet a 91-entry
one if it is cut from the last generation.

**`CurrentNum` is not the map size.** In the first generation carrying the map
it reads 24 while the map holds 16 entries, and it disagrees in 123 of the 263
generations. It is a high-water allocation counter, not a length. Anything that
uses it as a count will be wrong roughly half the time.

The map's **values** are two different id shapes, and the split matters:

| Value shape | Count in the largest generation |
|---|---|
| 19-digit positive, sharing the operator roleId's leading 12 digits | 16 |
| Negative integers, 2 to 8 digits | 75 |

`docs/FINDINGS.md` section 9.3.2 established from the log that **a negative
roleId marks a bot**. The save agrees from a completely independent surface: 75
of 91 entities in the id table carry a negative id. That is a genuine
cross-surface corroboration rather than two readings of the same bytes.

### 10.3 `PlayerData` is a struct with six fields, one of which is a JSON blob

Confirmed as filed. `PlayerData` is not a map keyed by player - it is a single
struct holding `UseTransform` (bool), `Transform`, `Hp` (int), `Inventory`
(FString), `HealthFlaskCount` (int) and `Currencies` (array).

`Inventory` is a JSON document, 6,923 characters in the largest generation, with
seven top-level keys:

| Key | Shape |
|---|---|
| `activatedBag` | object of bag entries, each `bagId` plus `expireAt` |
| `consumableBagItems` | array of item cells |
| `equipments` | array of item cells |
| `ordinaryBagItems` | array of item cells |
| `safeBagItems` | array of item cells |
| `shortcutItems` | array of `cfgId` plus `slot` only |
| `spinnerItems` | array of `cfgId` plus `slot` only |

The four item-cell arrays share one element schema: `cfgId`, `count`,
`durability`, `exEquip`, `id`, `slot`, `tradeColdAt`. `shortcutItems` and
`spinnerItems` carry only `cfgId` and `slot`, so they are **references into**
the bags rather than copies of them - a distinction that matters for anything
counting inventory.

`Currencies` is an array of `{CfgId, Count}`, so currency sits in the same
id space discipline as everything else and is not a set of named fields.

`PlayerData.Transform` carries **only `Rotation` and `Translation`** - no
`Scale3D`. `EscapePortalTransforms_Full` elements carry all three. Two different
transform shapes in one file, so a reader must not assume a fixed field list
from the word "Transform".

### 10.4 One Blueprint GUID defeats two different redaction detectors

This is the section that changes what `lanternlight/redact.py` has to do, and it
is the first Blueprint-class save this project has decoded, which is why it is
the first to hit any of it.

Blueprint property names in this file take the shape
`Name_Index_<32 uppercase hex>`. Measured in the largest generation: **770
property-name occurrences drawing on 65 distinct GUIDs.**

**Failure one - the `PRODUCTUSERID` rule.** That rule is a bare 32-hex run. It
fires **772 times** on this file. Every single one is a false positive:

- 770 are Blueprint property-name GUIDs.
- 2 are `monsterGuid` values inside the `DamageCollectonDataSet` JSON.
- **Zero** equal the operator's real EOS ProductUserId, harvested for this check
  from the live log. Not one of the 67 distinct 32-hex runs in the file appears
  anywhere in the live log at all.
- All 772 are **uppercase**; the real ProductUserId is **lowercase**. Case is
  the discriminator, and it was measured rather than assumed.

**Failure two - the `LONG_ID` rule, and it was found by refuting a fresh
number.** `LONG_ID` matches any run of 15 or more digits. It fires **100 times**
on the largest generation. Only **38** are genuine identifiers. The other **62
sit inside a Blueprint property GUID**: two particular GUIDs happen to contain a
17-digit and a 16-digit decimal stretch, and they recur 61 and 1 times because
the same property names repeat in every `MonsterData` entry.

The one-sentence version, which is the durable finding: **a 32-hex Blueprint
property GUID defeats a hex-shaped detector and a length-based digit detector at
the same time, for one cause.** Any fix aimed at only one of them leaves the
other firing.

Worth recording how the second half arrived. The 100-hit figure was filed after
a first pass, then re-derived, and the re-derivation refuted the first reading
of it. A twenty-minute-old number went stale in the same session that produced
it, which is a sharper demonstration of "a filed count is a hypothesis" than any
of the older examples in this document.

**The 38 genuine long ids**, all 19 digits, all sharing the operator roleId's
leading 12 digits, located in the parse tree:

| Where | Count |
|---|---|
| `BattleId` | 1 |
| `AutoSaveTempSlot` | 1 |
| `AutoSaveFinalSlot` | 1 |
| `IdGeneratorData.NumIdToUUID` values | 16 |
| `IdGeneratorData.UUIDToNumId` keys | 16 |
| `ownerRoleId` inside `ItemCell` JSON under `DropItemMap` | 3 |

**`MonsterData` holds no instance ids at all.** An earlier reading that put them
there is retracted, not softened: `MonsterData` entries carry `MonsterID`, which
is a 4-digit config id, and nothing 15 digits long.

### 10.4.1 The roleId is inside the file, not only in its name

`AutoSaveFinalSlot` is exactly the string `StandaloneSlot_<roleId>` and
`AutoSaveTempSlot` is exactly `StandaloneSlot_<roleId>_Temp`. Both were checked
by direct string equality against the roleId taken from the filename.

Section 9.9.1 and `ROADMAP.md` item 2b both warn that the **filename** embeds
the roleId and that a fixture therefore needs renaming. That is correct and
insufficient. The roleId is also inside the bytes, twice, welded to a
recognisable prefix. **Renaming the file does not redact it.**

`BattleId` is a sibling hazard and must be treated as exactly as sensitive as
the roleId. It is a 19-digit value sharing the roleId's **leading 12 digits** -
measured as the longest common prefix, not assumed. Publishing a BattleId
publishes 12 of the 19 digits of the operator's roleId. A prior statement that
the shared prefix is 14 digits is **refuted**; 14 is the prefix shared by 5 of
the 16 in-file long ids, not by `BattleId`.

### 10.5 Enum values are unrenamed engine defaults, and the names are unmeasured

Enum-typed properties serialise as an FString of the qualified enumerator. Two
enums appear, and the field names are misleading: the field called `Opened`
holds an `E_DoorState` value and the field called `Locked` holds an
`E_LockState` value. **Neither is a boolean.**

Enumerators observed over all 263 generations, with occurrence counts:

| Enumerator | Occurrences | Where |
|---|---|---|
| `E_DoorState::NewEnumerator1` | 10,104 | `DoorData.<key>.Opened` |
| `E_DoorState::NewEnumerator2` | 699 | `DoorData.<key>.Opened` |
| `E_DoorState::NewEnumerator3` | 33 | `DoorData.<key>.Opened` |
| `E_LockState::NewEnumerator0` | 2,265 | `DoorData.<key>.Locked` |
| `E_LockState::NewEnumerator2` | 9,872 | `DoorData.<key>.Locked`, `TreasureBoxMap.<key>.LockState` |

**The enumerator NAMES are unknown, and this is a measured null rather than a
gap in the write-up.** `NewEnumeratorN` is Unreal's own default label for an
enumerator the developer never renamed, so the game itself does not carry the
player-facing meaning in these bytes. Nothing observed binds
`E_DoorState::NewEnumerator1` to "closed", "open" or anything else, and no
mapping is guessed here.

Two gaps are themselves observations: **`E_DoorState::NewEnumerator0` never
appears** in 10,836 door-state values, and **`E_LockState::NewEnumerator1` never
appears** in 12,137 lock-state values. Either they are unreachable in this
content, or they are the default that is never written. Unmeasured, not absent.

Binding these would need a capture joined on wall clock - watch one door on
screen, poll the save, and read the enumerator that changes. That is the same
method that bound the class ids, and it has not been done.

### 10.6 The three-integer key IS positional - and here is the test that shows it

`DoorData`, `MonsterData`, `BotData`, `BotSpawnerData` and `TreasureBoxMap` are
all keyed by a string of three underscore-separated signed integers. Confirmed
as filed, in every entry of every one of the five maps.

Rather than assert that this "looks like world coordinates", the file was made
to answer the question. `MonsterData` values carry a `Transform` with a
`Translation` vector, so the key and a real position sit side by side in the
same record. That is a test, and it was run.

**First result, and it is a finding in its own right:** `Dead` partitions
`Translation` perfectly. All 39 living monsters have a zero `Translation`; all
22 dead ones have a non-zero one. **The `Transform` is written at death, not
continuously** - so it is a death location, and comparing a key against a zero
vector for the other 39 would have "refuted" the coordinate reading on an
artifact of the comparison. The first pass at this did exactly that.

**Second result, over the 22 records where the comparison is meaningful:**

| Test | Result |
|---|---|
| key component vs `Translation` component, correlation | **+0.992, +0.941, +0.969** on the matching axes |
| key equals `round(Translation)` under any axis permutation, sign flip, or scale in {0.001, 0.01, 0.1, 1, 10, 100, 1000} | 0 of 22 |
| distance from `key / 100` to `Translation` | min 102, median 879, max 1,524 |

So the key is positional beyond reasonable doubt - a near-unity correlation on
all three axes is not something a hash produces - and it is **scaled by about
100 relative to the `Translation` units**, with a residual of roughly 1 to 15
metres' worth of units. The natural reading is that the key encodes the actor's
**placement or spawn** position in hundredths of a `Translation` unit, and the
monster died a short walk away from it. The single bot's residual is 8,865,
about six times the worst monster - consistent with a bot roaming further than a
monster does.

Stated precisely, because the difference matters: **that the key is positional
is measured. That it is the spawn position specifically, and what physical unit
either quantity is in, is not.** What would settle it: `DoorData` and
`TreasureBoxMap` carry no `Transform` at all, so the confirmation available here
comes only from monsters and the one bot. Reading a door's world position off a
capture, or observing the same actor across two runs to see whether its key is
stable, would separate "spawn position" from "position at first save".

One corroborating detail: across the five maps there are 136 key slots and 135
distinct keys, and the single collision is `BotData` and `BotSpawnerData`
sharing one key. A bot and the spawner that produced it sharing a positional
identity is exactly what a placement-derived key predicts.

### 10.7 Map key types - `DropItemMap` is float-keyed, `LevelDetail` is not

Half of this claim survived and half did not.

| Map | Key type | Measured over |
|---|---|---|
| `DropItemMap` | **float** | 1,058 key observations across all 263 generations, every one a float |
| `LevelDetail` | **int** | 1,102 key observations across all 263 generations, every one an int |

**`LevelDetail` being float-keyed is refuted.** It is `IntProperty`-keyed and
always has been. The float keys of `DropItemMap` are all integral-valued and
non-contiguous, so the game is using a `MapProperty<DoubleProperty, ...>` to
hold what are plainly small integer handles - which is a format fact worth
keeping precisely because a reader that "helpfully" coerces them will produce
`5` where the file says `5.0` and then fail to match.

`PlayzoneData`, `BotSpawnerData` and `LevelDetail` all have **float values**
too, and `PlayzoneData` is not a map at all - it is a struct whose keys are
Blueprint property names. A reader that groups these five together by their
`MapProperty` tag will mis-handle `PlayzoneData`.

### 10.8 Natively serialised structs, and the confirmation that they are named

Confirmed as filed. In the largest generation there are **401 undecoded struct
leaves totalling 10,600 bytes**: `Vector` 261, `Quat` 125, `Rotator` 12,
`Vector2D` 3. These match `ROADMAP.md` item 2's figures exactly, re-derived here
rather than relayed.

`EscapePortalTransforms_Full` is an array - length 1 in the only generation that
has it - of structs carrying `Rotation` (a `Quat`), `Translation` and `Scale3D`
(both `Vector`).

`Vector` and `Rotator` are both 24 bytes and are separable only by the name the
tag carries. That is the concrete argument against a reader that decodes by
width.

### 10.9 `PlayzoneData` is a shrinking-circle mechanic, in the game's own fields

Not in any filed claim, and the most substantive new structure in the file.
`PlayzoneData` holds six fields:

| Field | Type |
|---|---|
| `ElapseTime` | float |
| `DmgCircleLocation` | `Vector2D` |
| `DmgCircleRadius` | float |
| `SafeCircleLocation` | `Vector2D` |
| `SafeCircleRadius` | float |
| `FinialSafeCircleLocation` | `Vector2D` (spelled that way by the game) |

A damage circle, a safe circle, each with a centre and a radius, plus the
**final** safe circle's centre known in advance, and a running elapsed time.
That is a closing-zone mechanic stated in the developer's own field names.

Two things follow and neither is asserted beyond the evidence. First, this is
the first first-party evidence in this project of a zone-pressure mechanic at
all; `docs/OBSERVED_IDS.md` records a Blackarrow talent named **Gyldenmist
Tolerance**, and a mist that must be tolerated is a plausible player-facing name
for this - **plausible, and unbound**. Second, in the sampled generation the
damage circle and the safe circle share the same centre and the same radius to
the bit, so this capture caught the zone before it began to move.

#### 10.9.1 The talent's tooltip is now MEASURED - and it still does not bind

Read 2026-08-30 off frame `f0101_16.05.00` in the 2026-08-09 capture, verbatim:

> **`Gyldenmist Tolerance`** - Increases resistance to the `Gyldenmist`,
> slowing the rate of `Gyldening`.

Both `Gyldenmist` and `Gyldening` render as highlighted keyword terms, which in
this UI marks them as game nouns rather than prose.

**The guess is better specified and still refused.** The tooltip establishes a
resistible affliction that accumulates at a RATE over time. It contains **no
spatial term at all** - no circle, no zone, no radius, no safe area. The
`PlayzoneData` fields are the exact complement: purely spatial, with no
affliction term. The two records describe things that would fit together and
share not one token.

**A corpus test was run and it came back negative.** Across all three logs,
`Gylden` occurs 3 to 4 times and never once in a Playzone line. The only
`Gylden` strings in any log are a costume appearance entry for a cosmetic called
`Gyldening Horn` (costume id `1000009`, emitted by `setCostumeAppearanceList`)
and a granted arrow ability, `GA_DA_InspectGyldenJar_C`. Neither is the zone.

**A redaction note, because the shape matters more than this instance.** The
costume line is emitted in the log's keyed display-name form - a label ending in
the word name, a doubled equals sign, then the value - which is the same shape
that carries the operator's persona elsewhere in the same file.
`lanternlight/redact.py` refuses to certify a quote written that way and it
refused this one, correctly: the rule keys on the shape, not on whether the
value happens to be a game noun.

**It then refused the sentence explaining the refusal**, because that sentence
had spelled the template out literally. That is the rule working, not a bug in
it, and it is why this paragraph describes the form in words instead. **Do not
write that keyed shape into a doc even to talk ABOUT it** - a public repo does
not need a worked example of the pattern that leaks the real thing, and a doc
containing one trips this project's own backstop from then on.

**Weigh that negative honestly: it is weak.** `AStkPlayzone` carries a studio
prefix and is plainly an internal class name, and engine identifiers routinely
differ from player-facing nouns - this same game calls its currency
`Gyldenblod` on screen while the zone code says `SafeCircle`. The absence of a
shared token is therefore consistent with the binding being true. It simply is
not evidence FOR it, and this file does not write down a binding that nothing
observed supports.

**What would bind it:** a run watched from outside the safe circle with the
resulting debuff visible on the HUD, or any field naming the affliction. Until
then `Gyldenmist Tolerance` stays a talent about an unlocated mist.

#### 10.9.2 The LOG carries the zone too, live - and it never shrank

`PlayzoneData` was known only from the save. The log carries the same mechanic
as replicated actor events, which nothing had recorded:

| Token | Kind |
|---|---|
| `AStkPlayzone` | the actor class |
| `BP_Playzone_C_1` | the placed blueprint instance |
| `PlayzoneComponent` | a pawn component; 93 lines say `player state is ready`, and 3 more - one per log - are a Puerts bind of `module/Character/PlayzoneComponent`, so part of the zone logic is a scripted module |
| `InitPlayzoneInfo` | init event, carries `stageNum`, `roundNumb`, `Steps` |
| `OnRep_SafeCircleInfo` | the replication event carrying radius and origin |
| `playzoneCom` | a **separate HUD surface**, `TS.UI: MainHUD`, carrying a `corrosion event` counter |

**Every recorded session emits exactly two SafeCircle updates and no more** - but
the zone is not therefore inert, see the corrosion events below. An init at
`SafeCircle Radius -1.000000` - an uninitialised sentinel, not a measured zero -
then one `OnRep_SafeCircleInfo` to:

- `Radius 25597.265625`, `PrvRadius -1.000000`
- `Origin X=-1997.146 Y=-5288.619`, `PrevOrigin X=0.000 Y=0.000`
- `stageNum 2`, `roundNumb 1`, `Steps 1`

**Those values are byte-identical in all three logs and ACROSS THE CLIENT
PATCH** - `1.0.14` and `1.0.15` produce the same radius and the same origin to
six decimal places. Under `ROADMAP` item 12 this is a value checked across a
patch boundary and found unmoved, which this project had no example of.

**Why the circles have never been seen to diverge.** The zone emits ONE radius
in a session and never updates it again: three runs of roughly 11, 19 and 22
minutes each ended with `EndPlay ... CurStageIndex 0, Reason 1`, still at
`Steps 1`, with `stageNum 2` declared at init. **No recorded session advanced
the zone past its first step**, so no log on this machine shows a radius shrink.

**CORRECTED before publication - the zone DID apply pressure once, and a first
draft of this section said it never did.** One of the three logs carries two
`TS.UI: MainHUD playzoneCom corrosion event N` lines, `N` reaching **2**:

| Event | UTC |
|---|---|
| `InitPlayzoneInfo` | `02.56.21:926` |
| `OnRep_SafeCircleInfo`, radius set | `02.56.22:484` |
| `corrosion event 1` | `03.18.01:443` |
| `corrosion event 2` | `03.18.10:455` |
| `EndPlay` | `03.18.14:970` |

So corrosion begins **21m39s** after the zone initialises, the second event lands
**9.0s** after the first, and the run ends **4.5s** later. The other two logs
carry zero corrosion events - and they are the two SHORTER runs, at roughly 19
and 11 minutes, both ending before the 21m39s mark. That is consistent with a
timer the short runs never reached, and it is not proof of one: a single
occurrence cannot separate a timer from a position, and nothing here says the
player was outside the circle.

**`corrosion` is the closest thing on disk to observable zone pressure**, and it
is a COUNTER, not a radius. It also gives the zone a third non-`Gylden` name -
`Playzone`, `SafeCircle`, `corrosion` - which does not settle 10.9.1 either way.

**The transferable defect: one mechanic, two log surfaces, and I characterised
it from one.** The radius lives on the actor (`LogStk: AStkPlayzone`); the
corrosion counter lives on the HUD (`TS.UI: MainHUD`). A grep written against
the actor class returns a complete-looking picture and silently omits the half
that answers the question being asked. **A mechanic is not characterised until
you have looked for its OTHER emitters.** An adversarial pass found this; the
authoring pass did not.

**What is still unmeasured:** whether the safe circle ever shrinks. Item 10.9's
"a run watched to completion" remains the right experiment and none of the three
archived runs is one.

### 10.10 The save counts a bot kill as a player kill - a second surface for 9.3.2

`LeaderRankScoreData` holds ten fields:

| Field | Shape |
|---|---|
| `KillBotCount` | int |
| `TeamKillBotCount` | int |
| `KillMonsterNum` | int |
| `KillPlayerCount` | int |
| `teamKillPlayerCount` | int (note the lowercase initial - the game's own casing) |
| `FirstOpenContainerCount` | int |
| `TeamKillMonsterData` | nested: category -> zone name -> `Id2cnt` map of monster id to count |
| `TeamOpenTreasuresData` | zone name -> `Id2cnt` map of container id to count |
| `AssistMonsterCount` | 8-digit id -> `Id2cnt` map of monster id to count |
| `KillPlayerHistoryDatas` | array of structs |

A filed claim said `KillPlayerHistoryDatas` and `KillPlayerCount` are **empty**
in this solo capture and are therefore a measured null for solo play. **That is
refuted.** `KillPlayerCount` is 1, `teamKillPlayerCount` is 1, and
`KillPlayerHistoryDatas` holds one entry.

The entry's fields, and what they say:

| Field | Observed |
|---|---|
| `IsPlayer` | **true** |
| `IsBot` | **true** |
| `ClassId` | 15 |
| `Level` | 2 |
| `BotGender` | 1 |
| `SkillNameId` | 6130017 |
| `TimeStamp` | 544 |
| `PlayerName` | a 17-character string, not reproduced |
| `MsgAppearanceString` | 2 characters, not reproduced |
| `MsgSubChannelString` | empty |

So the save's own **player-kill counter counts a bot**, and the record it files
asserts `IsPlayer` and `IsBot` simultaneously. `docs/FINDINGS.md` section 9.3.2
established this trap from the log; it now holds on a second, independent
surface, and the discriminator is the same one - `IsBot`, never the counter and
never the name.

The filed claim's *conclusion* survives its refuted premise, and is worth
stating in the corrected form: **`KillPlayerHistoryDatas` is the structure that
would carry a real other player's display name in a PvP run.** It carries a
generated bot's name here only because this capture is a solo run. It needs a
redaction detector before any fixture is cut from it, and `PlayerName` inside a
struct array is not a shape any current rule reaches.

`MatchID` is `11112` in all 263 generations. `docs/LEDGER.md` entry LL-0022
already records that 11111 and 11112 both belong to **solo explores**, which is
what independently establishes this capture as solo - it is not an inference
from the kill counts.

### 10.11 Two JSON schemas for one item, differing by case and by state

Item records appear in the file under two distinct schemas, and the difference
is not cosmetic.

**lowerCamel schema** - `ItemCell`, inside `DropItemMap` values. Thirteen keys,
present on all 12 entries: `affixes`, `cfgId`, `count`, `durability`, `gems`,
`id`, `lock`, `ownerRoleId`, `resourceType`, `slot`, `space`, `teamIdContext`,
`tradeCold`. `ownerRoleId` is **non-empty on 3 of 12** and empty on the other 9.

**PascalCase schema** - `TreasureData` inside `TreasureBoxMap` values, and
`TreasurableItems` inside `BotData`. Twenty keys, identical between the two:
`AffixIdentifyNum`, `Affixes`, `BindState`, `CfgId`, `Count`, `GemIdentifyNum`,
`Gems`, `Id`, `IdBeforePityDrop`, `IdentifyRoleId`, `IdentifyStage`,
`IvtrContext`, `LootContext`, `OwnerRoleId`, `Slot`, `Space`, `TeamContext`,
`bIsIdentifying`, `bNeedIdentify`, `durability`. `OwnerRoleId` is present and
**empty in all 19** treasure-box items; it is non-empty on 8 of the bot's 22.

So the same logical field exists in two casings and in two states, and a reader
or a redactor that keys on one spelling silently misses the other. This is the
`cfgId:` versus `cfgId: ` lesson of section 9.6 recurring in a different
surface: **the field is the same, the pattern is not.**

`IdBeforePityDrop` is first-party corroboration from the save of the loot pity
system already noted from the log in the research lane's open items. Existence
only - no coefficient, no threshold, and none is inferred.

`PlayerData.Inventory` uses a **third**, shorter item schema again (section
10.3), so there are three item shapes in one file.

### 10.12 What this file means for the sanitised fixture, item 2b

Everything below is a consequence of the measurements above, gathered here so
the safety lane does not have to re-derive it.

- The roleId is **inside** the bytes twice, not merely in the filename (10.4.1).
  Renaming is necessary and not sufficient.
- `BattleId` leaks 12 of the roleId's 19 digits and must be masked (10.4.1).
- 38 genuine 19-digit ids are present, spread over six locations (10.4).
- `PlayerName` inside the `KillPlayerHistoryDatas` struct array is a shape no
  current detector reaches, and in a PvP run it is a third party's name (10.10).
- `ownerRoleId` / `OwnerRoleId` exist in two casings and two states (10.11).
- A fixture cut from the last generation meets a **91**-entry `NumIdToUUID`, not
  the 23 the roadmap plans against (10.2).
- Any detector added must be proven against the **772 uppercase false positives**
  the current `PRODUCTUSERID` rule generates and the **62** the `LONG_ID` rule
  generates, or the fixture will be unreadable rather than redacted (10.4).

### 10.13 Still unmeasured after this pass

Named so they are not later mistaken for absent:

- The player-facing meaning of every `E_DoorState` and `E_LockState`
  enumerator. The game ships Unreal's unrenamed defaults (10.5).
- `E_DoorState::NewEnumerator0` and `E_LockState::NewEnumerator1` - never seen
  in 22,973 enum values across the whole lifetime.
- Which frame the three-integer key is expressed in, and the physical unit of
  either it or `Translation` (10.6).
- Whether the damage circle and the safe circle ever diverge (10.9).
- Whether `Gyldenmist Tolerance` names the `PlayzoneData` mechanic. Its tooltip
  is now measured and it did NOT settle this - the talent text is purely
  temporal and the zone fields are purely spatial, and no log joins them.
  Suggestive, still unbound, still not to be written down as a binding (10.9.1).
- Whether the safe circle ever shrinks. No archived run reaches `Steps 2`, so
  this cannot be answered from disk at all (10.9.2).
- What a `corrosion event` is, and whether its counter is driven by elapsed time
  or by standing outside the safe circle. One session reached 2; two reached
  zero, and both were shorter than the first event's 21m39s mark (10.9.2).
- What `MatchID 11112` selects. It is constant across the run and matches the
  solo-explore ids in LL-0022, and nothing observed says what the number means.

## 11. The training ground is a damage meter, 2026-08-25

First-party, operator in the client, log plus frame capture joined on wall
clock. This closes the two open questions of ROADMAP 7b and hands item 7 its
first **outgoing** damage - every number before this one was damage taken.

### 11.1 It exists, and it is not a match

`LoadMap(/Game/Project/Maps/TrainingGround/Training)` at 23:38:16 UTC, 0.884s.
The room carries `DA_DungeonSettings_Training`, its configuration panel is
`WBP_Level_Room_Setting` / `PracticeRoomSettingView_C`, and the spawned dummy
is `BP_Adventure_Bot_C`. So 7b's question (a) is answered YES.

Question (b) is a **clean negative, and it matters**:

| checked | result |
|---|---|
| `StandaloneSlot_<roleId>.sav` created | **NO** - absent for the whole 36-minute session in the room, across roughly 200 shots |
| `Saved/StandaloneLevel/` populated | **NO** - still empty, mtime unchanged since 2026-08-09 |
| `EnterBattle` / `onRequestMatch` in log | **NO** - neither appears anywhere in the session |
| per-hit `damageValue` anywhere on disk | **NO** |

For scale on that first row: in the captured dungeon run the transient save
appeared **17 seconds** after `EnterBattle`. Thirty-six minutes without it is
not a slow write, it is a different code path.

The training ground is **not a match**, so it does not create the transient
save, so `DamageCollectonDataSet` is **not written there at all**. The entire
plan of measuring combat math out of that save in a zero-stake room does not
work. Anyone re-reading `lanternlight/damage.py` expecting training data will
find nothing to read.

The log is no better. Seven occurrences of the substring `damage` in the whole
session, and **not one of them carries a number**: a settings echo
(`ClientSideDamagePrediction changed: 0`), a Puerts module bind
(`module/Character/DamageCollectionComponent`), and gameplay-cue class loads
(`GameplayCue.Damage.BeDamaged`, `GameplayCue.NumberPops.DamageCrit`). Those
cue lines are **async-load** messages - they fire the first time the class
loads, not once per hit. Counting them as hits would be a wrong number.

### 11.2 What the room does provide: an on-screen cumulative meter

The HUD carries a **Total Damage** panel - a running total and a hit count -
and a **Progress Record** panel beneath it. Both are pixels only; nothing
writes them to a file.

`Progress Record` is **not** a best-single-hit. Measured at the reset of
18:41:46 local: the live meter went to `0 / 0 Hit` and the record became
`337 / 30 Hit`, which is exactly the total and hit count of the run that had
just ended. It holds the **previous run's** pair. An earlier reading of
`12 / 1 Hit` looked like a max-single-hit and was not one.

The meter resets per run, so a run is a self-delimiting measurement window.

### 11.3 The per-hit value is FRACTIONAL, and the display rounds

Ten consecutive hits from a clean reset, one identical bow attack, captured at
2 fps with no gap - local clock, then the displayed total:

| hit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| total | 10 | 21 | 31 | 41 | 52 | 62 | 72 | 83 | 93 | 104 |
| delta | 10 | 11 | 10 | 10 | 11 | 10 | 10 | 11 | 10 | 11 |

The deltas are not constant, and that is the interesting part. If each hit
dealt the same integer, every delta would be that integer. Solving
`round(n * v) == total_n` across all ten points gives

> **v is in [10.3500, 10.3571)** - exactly `[207/20, 145/14)`, width 0.0071 -
> and **NO integer fits all ten**.

So the meter holds a real-valued running sum and rounds it for display, and the
alternating 10/11 is that rounding, not variance in the hit. Reading a single
delta off the screen and calling it "the damage" would have published a number
that is wrong by up to half a point in either direction.

**Operator attestation, given in the same session:** every run above and below
used the right-click attack with the standard arrow, at the same distance and
the same spot on the bot. Runs 1 and 6 were **body** shots; runs 5 and 7 were
**headshots**, which the client renders in red crit text. The operator's own
reading off the screen was "10 damage going to 12".

Four ten-hit runs were captured with no gaps. Each row is the displayed total
after hits 1 through 10:

| run | target | series | sum |
|---|---|---|---|
| 1, 18:41:47 | body | 10 21 31 41 52 62 72 83 93 104 | 104 |
| 6, 18:49:32 | body | 10 21 31 41 52 62 72 83 93 104 | 104 |
| 5, 18:45:47 | head | 12 24 37 49 61 73 86 98 110 122 | 122 |
| 7, 18:51:17 | head | 12 24 37 49 61 74 86 99 111 123 | 123 |
| 8, 18:53:37 | head | 12 24 37 49 61 74 86 99 111 123 | 123 |

### The body value IS reproduced, and it is fractional

Runs 1 and 6 are **identical, hit for hit**, eight minutes and four intervening
runs apart, each from its own meter reset. Both solve to

> **[10.3500, 10.3571)** - exactly `[207/20, 145/14)` - with **NO integer** in
> the interval.

That is an independent reproduction, which is the bar this project sets before
a measured value may be called anything more than a reading. The per-hit body
damage of a Blackarrow right-click standard arrow, on this bot, at this
distance, on buildid `24813185`, is a **fractional** quantity in that interval,
and the meter displays a rounded running sum of it.

### A third run disagreed on one hit, and that is what pinned the value

A later body run at the same distance produced `10 21 31 41 52 62 72 83 93
103` - identical to the other two for nine hits and one lower on the tenth,
104 against 103. Taken alone it solves to `[10.3125, 10.3500)`, which is
**disjoint** from the earlier `[10.3500, 10.3571)`. Two runs said the value is
at least 10.35 and the third said it is less. Something had to give.

What gives is the assumption that the tenth display is determined. At
`v = 10.35` the cumulative after ten hits is `103.5` **exactly** - a rounding
tie - and it is the ONLY tie in the series:

| n | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| n * 10.35 | 10.35 | 20.7 | 31.05 | 41.4 | 51.75 | 62.1 | 72.45 | 82.8 | 93.15 | **103.5** |

The one hit that ever disagreed between runs is the one hit whose display is a
tie. Nothing else in ten hits, across three runs, moved at all.

Searching every two-decimal value that reproduces all three runs with ties free
to fall either way returns **exactly one candidate: 10.35**. At three decimals
it is still the only value consistent with all three. So:

> **The per-hit body damage is 10.35** - measured, not fitted to a pretty
> number, and reproduced across three independent runs whose only disagreement
> is a rounding tie that 10.35 itself predicts.

This is the first value in this project to clear the independent-run bar. It is
bound to everything around it and to nothing beyond: Blackarrow, right-click,
standard arrow, this bot, buildid `24813185`, and a range **on the damage floor
measured in 11.6** - at or beyond roughly 8 paces, where the value stops
falling. It is not a coefficient, a formula, or a claim about any other class
or range.

One caveat on the range, because it is an inference rather than a reading: the
first two runs were fired before the operator had defined a pace, from a spot
recorded only as "the same spot". They are ASSIGNED to the floor because they
produce the floor's series and its exact value, not because anybody counted
their distance. The sweep in 11.6 measured the floor properly, twice.

### The head series reproduces too, but NOT to a single value

Runs 7 and 8 are also identical hit for hit, two minutes apart. Run 5 is not:
it diverges from hit 6 and ends one point lower, 122 against 123. So headshots
are reproducible in the large and something still separates run 5 from the
other two.

Solving both display models across the three head runs is where this stops
being tidy:

| run | `round(n*v)` fits | `floor(n*v)` fits |
|---|---|---|
| 1, 6 body | **[10.3500, 10.3571)** | no fit |
| 5 head | [12.2143, 12.2500) | no fit |
| 7, 8 head | **no fit** | [12.3750, 12.4000) |

The body runs fit rounding and not truncation. The two identical head runs fit
truncation and not rounding. **One meter cannot display its total both ways**,
so at least one of those fits is a coincidence rather than a mechanism - ten
points and a free choice of two models is enough rope to fit noise. The
single-value model is simply wrong for headshots.

What that leaves, stated as measurement rather than theory: the per-hit head
damage is **not one constant**. The delta multiset is 8x12 + 2x13 in run 5 and
7x12 + 3x13 in runs 7 and 8, so the variation is in how many hits land on the
higher value, not in some third number appearing.

A crit roll on top of the headshot fits that shape and is **not established** -
the client does render headshots in red crit text per the operator, which makes
"headshot" and "crit" hard to separate by eye and impossible to separate from
this data. The body/head midpoint ratio is **1.1814** against run 5, recorded
as an observation and published as nothing.

**No coefficient enters Emberforge from this session.** The body interval has
earned its independent run; it has not earned a name, a formula slot, or a
claim about any other class, weapon, distance, or build. The head numbers have
not earned even that.

### The fractional result is corroborated from an unrelated surface

This did not have to agree with anything, and it does. The transient dungeon
save's `DamageCollectonDataSet` stores `damageValue` as a **float** - the two
hits read out of it in ROADMAP item 7 are `17.356201171875` and
`92.13079833984375`, neither remotely an integer.

So two independent surfaces, a save file written during a real dungeon and a
HUD meter rendered in a practice room, agree that the engine's damage quantity
is real-valued and that any integer a player sees is a presentation of it. A
build calculator that treats displayed damage as the underlying number is
wrong by construction, not merely imprecise.

**This is corroboration of a property, not of a value.** Nothing here says the
body interval `[10.3500, 10.3571)` and those two floats belong to the same
formula - they are different attacks, different targets, different directions
(dealt against taken) and different builds.
### 11.4 Two other runs provably were NOT uniform

Same solve, same session, applied to the two runs between them:

| run | points | result |
|---|---|---|
| 18:42:21-18:43:01 | 9 | **no single value fits** |
| 18:43:04-18:43:51 | 10 | **no single value fits** |

That is a positive result, not a failed measurement: it proves at least two
distinct per-hit values occurred inside each of those runs. The solve is what
separates "the attack varies" from "the display rounds", and by eye the two are
indistinguishable - both look like deltas that wobble by one.

### 11.5 What the log DOES carry per shot

`TS.Dungeon: SpawnDefaultAmmunition spawn id=0, AmmunitionComponent_C_<inst>,
BP_Adventure_Bot_C_<inst>` - 63 of them in this session, one per arrow. Also
`[AmmunitionComponent]: UsingCustomizedAmmunition: id=0`, which is the first
first-party sight of the ammo-family distinction ROADMAP 4b is about. Both
carry `id=0` only; no family id has been observed taking any other value.

So shot cadence is measurable from the log and damage is not, and the two join
on wall clock the same way class ids were bound.

### 11.6 The distance curve, measured at ten points

> **CONTESTED AND THEN RESOLVED, 2026-08-25 - see 11.10 for how.** The mapping
> below was an inference from clock order and was challenged within the hour.
> It was re-tested with a labelled pair of runs under wide-shot capture and it
> held: two runs at two different distances both read 104. The floor is real.


The operator ran a full sweep - 10, 8, 6, 4, 2 and 0 paces, ten body hits at
each, meter reset between runs, same right-click standard arrow. Two controls
were held that the earlier runs did not have: take the paces, **stop moving**,
then fire all ten without repositioning, aiming at one point on the bot.

**The distance unit is the operator's, and it is defined:** one pace is a full
stride, counted by watching the run-cycle animation loop reset while moving
straight forward, with no crouch, sprint or roll. It is not metres. It is a
unit this project can re-use, not a measurement of the world.

| paces | ten-hit total | per hit | a constant per-hit value fits? |
|---|---|---|---|
| 10 | **104** | 10.40 | **YES** - `[10.3500, 10.3571]` |
| 9 | **104** | 10.40 | **YES** - `[10.3500, 10.3571]` |
| 8 | **104** | 10.40 | **YES** - `[10.3500, 10.3571]` |
| 7 | 231 | 23.10 | no |
| 6 | 309 | 30.90 | no |
| 4 | 546 | 54.60 | no |
| 3 | **687** | 68.70 | no |
| 2 | **687** | 68.70 | no |
| 1 | **689** | 68.90 | no |
| 0 | **691** | 69.10 | no |

Per-pace factor, closing (geometric mean where a pace was skipped):

| step | per pace |
|---|---|
| 10 -> 9 | **1.000x** |
| 9 -> 8 | **1.000x** |
| 8 -> 7 | **2.221x** |
| 7 -> 6 | 1.338x |
| 6 -> 4 | 1.329x |
| 4 -> 3 | 1.258x |
| 3 -> 2 | **1.000x** |
| 2 -> 1 | **1.003x** |
| 1 -> 0 | **1.003x** |

**The curve is three regimes, and the middle one is startlingly regular.** A
flat floor at 104, a slope that multiplies by about **1.3x per pace** for four
consecutive paces, and a flat ceiling at 687-691. The ceiling plateau spans
**four** distances - 3, 2, 1 and 0 paces - with a total spread of 0.6%.

**A note on how the last four runs were labelled, since an inferred label
already cost this document once (11.10).** The operator reported "9 and 7 done"
and later "3 and 1 pace done", naming them in that order, and the runs were
assigned in clock order accordingly. That is an inference - but unlike the
earlier one it is **forced by monotonicity**, so it is checkable rather than
assumed:

- The 9/7 pair read 104 and 231. Damage rises as range closes, and 8 paces
  reads 104. If the assignment were reversed, 7 paces would read 104 while 8
  paces read 104 and 6 paces read 309 - putting the nearer shot at the floor
  and making the curve non-monotone across a single pace. Only one assignment
  survives.
- The 3/1 pair read 687 and 689. Both sit on the ceiling, so the choice barely
  moves anything, and the assignment taken is the one where the nearer shot is
  the higher of the two.

**The floor is a step, not a tangent.** If the 1.3x-per-pace slope simply
continued outward from 7 paces, 8 paces would read about `231 / 1.33 = 174`,
not 104. The measured floor is far below the extrapolation, so the game is not
running out of curve - something is **clamping** the value to 10.35 beyond a
range that lies between 7 and 8 paces. The ceiling, by contrast, is reached
gently: 4 -> 3 is 1.258x, slightly *less* than the slope's own rate, and then
it stops.

**The floor edge is between 8 and 7 paces, and it is abrupt.** Three
consecutive distances - 10, 9 and 8 paces - produce the **identical** ten-hit
total of 104 and all three solve to the same interval containing 10.35. One
pace closer, at 7, the total is 231: **2.221x in a single pace**, against
1.338x for the next pace after it. That is the signature of a clamp being left
behind, not of a curve flattening out.

So the far end is not "the curve gets shallow". It is a **hard minimum**: below
some range the value stops responding to distance entirely and sits at exactly
10.35.

**The curve is clamped at both ends.** Ten paces and eight paces produce the
identical ten-hit total, so damage stops falling somewhere at or before 8
paces - a **floor**. Two paces and zero paces are within 0.6% of each other, so
it stops rising too - a **ceiling**. Between them is a steep slope. End to end
the ceiling is **6.64x** the floor.

This was the acceptance test written into ROADMAP 7b before it was run: "if the
floor hypothesis holds it reads 10.35 again, and constant". It did, on the
nose, and the ceiling was not predicted at all.

### 11.7 Constancy tracks the flat parts of the curve exactly

This is the result that makes the rest interpretable, and it needed the solve
rather than the eye.

**A constant per-hit value always makes the displayed deltas wobble by one.**
A fully-captured floor run gives ten deltas of 10, 11, 10, 10, 11, 10, 10, 11,
10, 11 and is a perfectly constant 10.35 - the wobble is the rounding, not the
damage. A wobbling delta is therefore not evidence of variance, and reading one
off the screen proves nothing either way. What IS evidence is a contradiction,
and the contradictions line up with the curve:

- **On the floor - 10, 9 and 8 paces - a constant value fits every run**, and
  it is the same interval `[10.3500, 10.3571]` all three times.
- **Off the floor - 7, 6, 4, 3, 2, 1 and 0 paces - no constant value fits any
  run.** Not one.
- **That includes the ceiling.** Three, 2, 1 and 0 paces agree on the ten-hit
  total to within 0.6%, and none of them admits a constant per-hit value: the
  sums agree while the individual hits do not.

So constancy is **not** a property of the plateaus. It is a property of the
**floor specifically**, and the boundary of the constant set is exactly the
step between 8 and 7 paces. A flat total is not enough to make the hits
identical - only the clamp does that.

**The observed data, so this is checkable rather than assertable.** Each cell
is the displayed cumulative total after that many hits. A dash means that
intermediate state was **not captured** - the meter is sampled at 2 fps and two
hits inside one sample interval leave no frame between them. A dash is a gap in
observation, not a missing hit; the hit counter on screen never skipped.

| paces | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | constant v |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | - | - | - | - | - | 62 | 72 | 83 | - | 104 | `[10.3500, 10.3571]` |
| 9 | 10 | 21 | - | 41 | 52 | - | 72 | 83 | - | 104 | `[10.3500, 10.3571]` |
| 8 | 10 | 21 | - | 41 | 52 | - | 72 | 83 | - | 104 | `[10.3500, 10.3571]` |
| 7 | 23 | 45 | 68 | 91 | 114 | 137 | 162 | 186 | 208 | 231 | none, fails at hit 7 |
| 6 | 30 | 60 | 91 | 122 | 153 | 184 | 215 | 246 | 277 | 309 | none, fails at hit 4 |
| 4 | 53 | 108 | 162 | 216 | 271 | 325 | 380 | 436 | 491 | 546 | none, fails at hit 2 |
| 3 | 68 | 137 | 206 | 275 | 344 | 412 | 481 | 549 | 618 | 687 | none, fails at hit 4 |
| 2 | 68 | 137 | 206 | 275 | 344 | 414 | 482 | 550 | 618 | 687 | none, fails at hit 4 |
| 1 | 68 | 136 | 205 | 274 | 343 | 412 | 482 | 551 | 620 | 689 | none, fails at hit 4 |
| 0 | 68 | 137 | 206 | 275 | 344 | 414 | 483 | 552 | - | 691 | none, fails at hit 4 |

"Fails at hit N" is the first hit at which the feasible interval for a constant
`v` becomes empty.

**The solve needs one convention, so it is stated here rather than 300 lines
away in 11.3.** Solve `round(n * v) == total_n`, and where `n * v` lands on an
exact `.5` the display may round **either way** - both integers are accepted.
Without that allowance four of these rows report a different failure hit (7
paces fails at 6 rather than 7; 3, 2 and 0 paces at 3 rather than 4), which the
session's own wrap refutation duly reproduced by taking the obvious reading.
With it, every cell above is exactly reproducible. Ties are not a fudge - they
are the whole reason 10.35 is pinned at all, since the only hit that ever
disagreed between floor runs is the one that lands on `103.5`.

**The 9-pace and 8-pace rows are identical including their gaps, and that was
challenged.** Two runs sharing not just their totals but the exact hits the
sampler missed is the same shape as data copied from a neighbour, which is
precisely what the confession below describes. So it was re-sourced from the
capture rather than defended: tiling the three floor windows out of
`panel2/` gives 8 deduped frames for the 10-pace run, 9 for the 8-pace and 12
for the 9-pace - deduped frames, not distinct readings, which are 4, 8 and 8 -
and reading them off yields observed hits `{6,7,8,10}`,
`{1,2,4,5,7,8,10}` and `{1,2,4,5,7,8,10}` respectively - matching the table.
The shared gap pattern is real and has a dull cause: the operator fired both
runs at a steady cadence, and at 2 fps a steady cadence misses the same
positions every time.

**One correction made while producing it, and it matters more than the table
does.** An earlier pass solved the 10-pace run using the points `(1,10)` and
`(2,21)`. **Those belong to the 8-pace run.** The 10-pace run's early states
were never captured - the panel poller was started mid-run - and the pattern
was filled in from its neighbour without anyone noticing, because the two runs
genuinely do produce the same series. Re-solved on its four genuinely observed
points the interval is unchanged and no published conclusion moves. **The
conclusion being right is not the point.** Data was invented to fill a gap, in
the document that spends two sections on the cost of inferring what should have
been recorded.

**The same-distance runs disagree only on the slope.** Comparing nominally
identical distances across the session:

| nominal | earlier runs | sweep | spread |
|---|---|---|---|
| 8 paces | 103, 104, 104 | 104 | one point, and that point is a rounding tie |
| 6 paces | 265 | 309 | **16.6%** |
| 4 paces | 552, 548 | 546 | ~1% |
| 0 paces | 684 | 691, 690 | ~1% |

Six paces is the middle of the steep section and it is the reading that moved
16.6%. The operator's own account fits: he reported being "a little off the mark
on the 4 pace run" without being asked. **A pace counted by animation loop is
good to a fraction of a pace, and on a slope this steep a fraction of a pace is
several damage.**

**What is established:** damage depends on range across ten measured
distances, is clamped at both ends, is exactly 10.35 per hit on the floor for
this attack, this bot and this build, and the floor boundary sits between 7 and
8 paces while the ceiling is reached by 3.

**What is NOT established, and must not be written down as though it were:**

- That the game rolls damage at all. Every non-constant run is on the slope,
  where the operator's own position is the uncontrolled variable. There is no
  observation here that requires randomness to explain it.
- Why the floor is a step rather than a tangent. The extrapolated slope says 8
  paces should read about 174 and it reads 104. That gap is measured; its cause
  is not. **A first-party candidate cause arrived 2026-08-30 and is recorded in
  11.7.1 below. It is a candidate, not an answer.**
- Whether the ~1.3x per pace on the slope is a real rate or a coincidence of
  four points. It is regular enough to be worth testing and not enough to name.
- The shape between them as a formula. Four interior points that happen to sit
  near a constant ratio fit many functions, and this project has no business
  naming one from them.
- Anything about another class, weapon, arrow, target or build.

**No coefficient enters Emberforge from this.** A measured floor value with its
conditions attached is a fact; a falloff formula would be a story.

### 11.7.1 The game states an `Effective Range` mechanic - added 2026-08-30

Read off the client on 2026-08-30 and written up in
[`docs/AFFIXES.md`](AFFIXES.md), the `Ranged` affix's detail panel states, in
the game's own words:

> **Effective Range.** Different ranged attacks have different Effective
> Ranges. Beyond the Effective Range, both DMG and Impact will diminish.

**A stated mechanic that makes damage diminish past a range boundary is the
same SHAPE as the step this section measured** and could not explain. That is
worth recording immediately, because 11.7 was written believing no first-party
statement about range falloff existed.

**It is not an answer, and four things stop it from being one.**

1. **The units are not bound.** The affix panel speaks in **meters**; every
   measurement in section 11 is in **paces**, counted off an animation loop
   (11.2). Nothing in this project has ever measured a pace in meters. The
   affix's other clause gates at "greater than 5 meters" and this section's
   floor boundary sits between 7 and 8 paces - those two numbers are in
   different units and **must not be compared**. Writing "so a pace is under a
   meter" would be inventing the conversion that is missing.
2. **The affix state of the runs was never recorded.** No run in section 11
   recorded which affixes the weapon carried or at what level, so no run here
   can be re-attributed to this mechanic. `AFFIXES.md` makes the same point
   about `ROADMAP` item 10.
3. **The ladder gates the range bonus at Lv. 5.** The stated `Effective Range`
   column is blank for levels 1 to 4 and reads `+12%` from Lv. 5. Whether this
   character was at or above that level during the section 11 runs is
   unrecorded, so the mechanic's own precondition is unverified here.
4. **`Effective Range` is stated as a property of the ATTACK, not of the
   affix** - "different ranged attacks have different Effective Ranges". So
   falloff plausibly exists with no affix involved, and the affix only shifts
   the boundary. If so this is a base mechanic that was always there, and the
   step in the table needs no affix to explain it. That reading is at least as
   consistent with the data as the other.

**What would test it.** Re-run the pace sweep twice on the same target and
attack with a deliberately different `Ranged` level - the affix panel reports
the level directly, so it is a recorded input rather than an inferred one - and
see whether the floor boundary MOVES. A boundary that shifts with affix level
belongs to the affix; a boundary that does not is the attack's own Effective
Range. Either outcome is publishable, and the run costs the same as the sweep
already done.

**Do not fold this into 11.7's conclusion.** That section's "what is
established" list stands unchanged: the floor value, its conditions and the
boundary's location are measurements, and none of them moves because an
explanation became available. What changed is that the gap now has a named
first-party candidate instead of none.

### 11.8 The game log is PERISHABLE, and one was already lost

Checked at the start of this session and worth more than it looks. The log at
`%LOCALAPPDATA%\MistfallHunter\Saved\Logs\MistfallHunter.log` was **221 KB and
opened 2026-08-25 18:34:46 local**. The log this project measured on
2026-08-09 was **6.1 MB**. There is exactly one file in that directory and no
`MistfallHunter-backup-*.log` beside it.

**The game truncates its log on launch and keeps no backup.** Every line of
that 6.1 MB session that was not copied out, quoted into a document, or turned
into a committed fixture no longer exists anywhere.

> **The second half of that sentence is REFUTED - see 11.12.** A launch was
> watched directly on 2026-08-25 at 21:28:59 and it left a byte-identical
> backup of the previous run's log. The first half survives. The practical
> rule below is unchanged, because the backup is not guaranteed either.

Sections 9 and 10 of this document survive because somebody wrote them down;
the raw evidence behind them does not.

The practical rule: **a log is evidence only until the next launch.**
`lanternlight/savewatch.py` already does the copying - it is a generic
"snapshot every changed generation" watcher and pointing it at `Logs/` gives
timestamped, size-stamped archives for nothing. This session archived a copy
every five minutes from 18:38 onward, so its log survives whatever happens to
the live file.

The same watcher pointed at `Saved/` also gives ROADMAP item 4's `AvgPrice`
acceptance - "snapshots the file on change with a timestamp and never writes to
it" - without new code. Worth knowing before anyone writes a second watcher.

Related and also measured this session: `AvgPrice_937566.ini` is back to **37
bytes**, its empty-with-headers state. It had filled to 343 bytes on
2026-08-09. Nothing watched it empty, so what emptied it is unknown.

### 11.9 Headshots never give a constant value, even where body shots do

The same six-distance sweep was run again in headshots. Seven ten-hit runs
completed (one was aborted mid-run by the operator after a hit landed for 5,
and is discarded rather than salvaged):

| clock | ten-hit total | per hit | a constant per-hit value fits? |
|---|---|---|---|
| 19:20:16 | 123 | 12.3 | **no** |
| 19:20:51 | 123 | 12.3 | **no** |
| 19:21:26 | 350 | 35.0 | **no** |
| 19:22:28 | 651 | 65.1 | **no** |
| 19:23:06 | 799 | 79.9 | **no** |
| 19:23:46 | 817 | 81.7 | **no** |
| 19:24:30 | 818 | 81.8 | **no** |

**Not one head run admits a constant per-hit value - including the two on the
damage floor, at the exact ranges where body shots are perfectly constant at
10.35.** That is the finding, and it does not depend on which run was fired at
which pace count.

It is not noise, either. The totals **reproduce**: 123 twice on the floor,
matching 122 / 123 / 123 from three head runs earlier in the session, and
817 against 818 on the ceiling. The sum is stable to a point or two while the
individual hits are not.

So a headshot is not simply a body shot times a number. Something in the head
calculation has per-hit structure that the body calculation lacks at the same
range, on the same target, with the same weapon, fired the same way. Candidates
this session cannot separate: a crit roll that only applies to headshots, a
head hitbox with sub-regions, or a multiplier applied to an already-rounded
intermediate. The client renders headshots in red crit text, so "headshot" and
"crit" cannot be told apart by eye either.

**The head/body ratio is roughly 1.18** where both were measured at the same
nominal range, and it is deliberately not published per-distance here: seven
head runs were fired at six distances and the mapping of the last three is not
established, so any per-distance ratio table would be an assumption wearing a
number. What the ratio is good for right now is a sanity check, not a
coefficient.

### 11.10 The distance mapping WAS contested, and both arguments for the wrong answer were invalid

Recorded the moment it was noticed, because a section of this document was
already committed on the losing side of it.

**What happened.** Both sweeps produced **seven** completed ten-hit runs, not
six. Sections 11.6 and 11.7 assigned distances to the body runs by clock order,
first run to 10 paces, and treated the seventh as a repeat. When the operator
was asked to label the head runs he listed **six**, starting `123 = 10 paces`,
which implies the run before it was not part of the sweep.

If the same is true of the body sweep, every body run shifts by one:

| clock | body total | mapping A (as committed) | mapping B (operator-parallel) |
|---|---|---|---|
| 19:12:50 | 104 | 10 paces | not counted |
| 19:13:28 | 104 | 8 paces | 10 paces |
| 19:14:01 | 309 | 6 paces | 8 paces |
| 19:14:38 | 546 | 4 paces | 6 paces |
| 19:15:15 | 687 | 2 paces | 4 paces |
| 19:15:53 | 691 | 0 paces | 2 paces |
| 19:16:44 | 690 | a repeat | 0 paces |

**Under mapping A there is a damage floor** - 10 and 8 paces both read 104.
**Under mapping B there is none** - 10 reads 104 and 8 reads 309, a 2.97x step.

**Two arguments were made for B at the time. BOTH WERE INVALID, and the
session's own wrap refutation caught them.** They are kept here in full,
because an invalid argument that is quietly deleted teaches nobody anything.

*Argument 1, as written:* "the head runs step 123 -> 350 from 10 to 8 paces, a
2.85x change; body under B steps 2.97x over the same interval, body under A
steps 1.000x, so only B gives the two sweeps the same shape."

*Why it is invalid:* it compares the head runs under **B** against the body
runs under **A**. Applied consistently, mapping A labels the head runs
`123, 123, 350, ...` - so under A the head steps 123 -> 123 = **1.000x** from
10 to 8 paces, exactly matching body's 1.000x. The two sweeps have the same
shape under A as well. The argument's whole force came from mixing the
mappings.

*Argument 2, as written:* "pairing by B gives 1.183, 1.133, 1.192, 1.163,
1.182, 1.185 - a tight cluster; pairing by A puts a 3.37x against a 1.18x and
makes nonsense of the rest."

*Why it is invalid:* the same mix. Re-derived consistently:

| pairing | head/body ratios by distance |
|---|---|
| consistent A | 1.183, 1.183, 1.133, 1.192, 1.163, 1.182 |
| consistent B | 1.183, 1.133, 1.192, 1.163, 1.182, 1.186 |
| **mixed** - head B against body A | 1.183, **3.365**, **2.107**, 1.463, 1.189, 1.184 |

The 3.37x that supposedly "makes nonsense" of A is in the **mixed** row. Under
a consistent A the ratios cluster exactly as tightly as under B. The ratio test
does not discriminate between the mappings at all, in either direction.

**What actually argued for A** was the operator's earlier standalone protocol,
where "full distance is about 8 paces" produced **103** - and that was the
argument being explained away at the time.

**So the section originally leaned toward B on nothing.** Mapping A is correct,
which is worse rather than better: the reasoning pointed at the wrong answer
and only re-running the measurement (11.11) recovered it. Had the invalid
arguments pointed the right way, nothing would ever have flagged them.

The ceiling was never at stake: the last three body runs are within 0.6% of
each other under both mappings, as are the last two head runs.

**The lesson, which is the reusable part.** Every total in both sweeps was
measured exactly. The thing that broke was the **label**, and it broke silently
because clock order looked like an obvious ordering and nobody had said it was.
A measurement whose independent variable was inferred rather than recorded is
not a measurement of that variable - and it reads exactly like one.

**Update, same session:** asked to check, the operator corrected himself -
"so yes sorry the 10 pace and 8 pace were the same" - which is mapping **A**,
the one 11.6 was committed on, and restores the floor.

That was not treated as the resolution at the time. The same operator gave a
different mapping twenty minutes earlier, in good faith both times, which is
precisely the evidence that **recall is not a reliable instrument for this
variable**. **11.11 is the resolution** - a re-run under capture - and it
agrees with the correction.

The fix applied was to stop needing recall. A half-scale JPEG wide-shot poller
was armed alongside the panel poller at about 140 KB a frame, so the operator's
standing position is IN the capture. **Note the limit of that, measured in
11.11:** having the position on film is not the same as reading a distance off
it. The attempt to turn apparent size into a number saturated twice and
failed. What the wide shot actually delivers is a re-runnable, human-checkable
record of where the operator stood - which was enough.

**The general form of this, worth carrying past this game:** when a measurement
depends on a variable the instrument does not record, the fix is to record the
variable, not to ask someone to remember it. Two mappings from one honest
operator is not a failure of the operator.

### 11.11 How the mapping was resolved, including a measurement that failed

**The test.** A wide-shot poller was started - half-scale JPEG at 1 fps, about
140 KB a frame - and the operator was asked to redo just the ambiguous pair:
ten body hits at 10 paces, reset, ten body hits at 8 paces. Nothing was asked
of his memory.

**The result: both runs read 104.** Identical ten-hit totals at two distances
the operator walked between. That is the floor, measured under a label recorded
at the time rather than reconstructed afterwards, and it is the mapping 11.6
was committed on. The operator had also corrected himself independently -
"the 10 pace and 8 pace were the same" - and the runs agree with the
correction.

**A measurement that did NOT work, recorded because a silent failure here would
have been worse than no measurement.** The plan was to turn "the target looks
closer in run 2" into a number by thresholding the bot's dark silhouette
against the lit sandstone wall and comparing apparent heights. It was attempted
twice and **saturated both times** - the first attempt returned exactly the
band height for both frames, the second returned exactly the band height again
after the region was tightened, because the chosen region is mostly dark cave
rather than silhouette-against-wall. A ratio of 1.000 from a saturated read is
indistinguishable from a real null.

So the distance difference between the two runs rests on the operator having
walked between them and on the frames looking different, **not** on a measured
apparent size. Anyone wanting that number should put a fixed high-contrast
marker in frame rather than trying to segment a character against a cave.

**What actually made this resolvable** was not cleverness about pixels. It was
recording the independent variable at capture time, in the same stream as the
dependent one. That is the whole lesson of 11.10 and it cost about 140 KB a
frame.

### 11.12 A launch COPIES the log before it truncates - "keeps no backup" refuted

11.8 was written from a check at the start of that session which showed one
file in `Logs/` and no `MistfallHunter-backup-*.log` beside it, and it turned
that into **"the game truncates its log on launch and keeps no backup"**. The
observation was right. The generalisation was not, and it was load-bearing: it
was the stated premise of ROADMAP 4c and it is repeated in `WAKEUP_NOTES.md`
and in `NEXT_SESSION_PROMPT.md`, all of which are corrected alongside this
entry.

**A launch was watched directly this time.** The game exited at 20:27:09 local
and relaunched at 21:28:59. Measured immediately afterwards:

| file | bytes | created | last written |
|---|---|---|---|
| `MistfallHunter.log` | growing | **2026-08-09 08:18:56** | now |
| `MistfallHunter-backup-2026.08.26-01.27.09.log` | 5,080,313 | **2026-08-25 21:28:59** | 2026-08-25 20:27:09 |

Three things fall straight out of that table:

- **The backup is the previous run, intact.** Its sha256 is
  `1c44235c962a89a32dc97fdbf24e2afc0952e5fe7418dd4b8ba51ad41dc8f050`, which is
  byte-for-byte the previous session's final archived log. Nothing was lost at
  that launch.
- **The backup was made BY the launch.** Its creation time is 21:28:59, the
  same second the new log was opened, while its content stops at 20:27:09. A
  file born at that second holding only pre-launch content is a copy taken at
  launch. Its name had never been used before, so unlike the live log's
  timestamp this one cannot be a tunneling artifact.
- **Its name is the previous log's close time in UTC.** `2026.08.26-01.27.09`
  is 20:27:09 local, which is exactly the previous log's own last line,
  `Log file closed, 08/25/26 20:27:09`.

The previous run had exited **cleanly** - `LogExit: Exiting.` - so the backup
is not a crash artifact.

**After the launch, the live log still carries a creation time of 2026-08-09
08:18:56** - the same minute the rest of the `Saved/` tree was created, so that
is the game's own first run on this machine and not a Lanternlight artifact.
So THIS launch emptied
the file that was already there rather than deleting it and making a new one.
That is one launch, watched once. Nothing here shows the creation time survived
every launch in between, because nobody was looking during any of them.

**Caveat, and it is a real one: NTFS tunneling.** If a file is deleted and
recreated under the same name within about 15 seconds, NTFS restores the
original creation time, so creation time alone does NOT separate
truncate-in-place from delete-and-recreate here. The distinction does not
change anything actionable - the old content is gone from that path either way
- but the evidence does not settle it and this document should not pretend it
does.

**A backup is NOT guaranteed, and that is measured too.** Across **23**
archived generations of `Logs/` spanning 18:38:20 to 20:28:25 on 2026-08-25 -
gaps of 300 or 301 seconds, every one of them a copy of `MistfallHunter.log`
and not one of anything else - **no `*-backup-*.log` existed at any point**.
The watcher copies every file it finds in the directory, so a backup sitting
there would have been archived; and it can only have been watching the
directory, because pointing `SaveWatcher` at a file makes `iterdir()` raise and
yields no copies at all.

**Be careful what that licenses.** It establishes that no backup was present
between 18:38:20 and 20:28:25. It does **not** establish that the launch which
began that session failed to make one - nobody was watching before 18:38:20,
and a backup made at that launch and removed before the first listing looks
identical from here. What is measured is an absence over a window, not an
absence at a launch. **What decides whether a launch leaves a backup is
unmeasured.** Do not write a rule from n=1 in either direction.

**What actually changes as a result:**

- **Archiving stays mandatory.** A windfall that appeared once and was absent
  through an entire previous session is not a backup strategy.
- **Watch the Logs/ DIRECTORY, never the log FILE.** This is the whole
  difference between recovering the previous session and walking past it. The
  watcher armed at 21:30:40 this session picked the 5,080,313-byte backup up
  for nothing, which means arming at session start now recovers the PREVIOUS
  session as well as preserving the current one. `lanternlight/armwatch.py`
  does this by construction and `tests/test_armwatch.py` pins it.
- **The condition measures itself from here.** Because the watcher archives
  `Logs/` wholesale, every future launch records whether a backup appeared
  beside the log. Nobody has to run an experiment; the question answers itself
  over enough launches.

## 12. A real dungeon run that wrote NO transient save, 2026-08-25b

Captured live while the operator played, with the watchers of ROADMAP 4c armed
from the start of the session. **n = 1 run**, and every number below was read
off the live log and the live save directory as it happened.

**The run.** `BP_Dungeon_GameMode` on `/Game/Project/Maps/Map_2/Whitewoods_Day`
- the same map as the 2026-08-09 runs - `levelId=113`, `matchId=11114`. Solo:
exactly **one** roleId appears anywhere in the log.

| event | UTC |
|---|---|
| `match state changed to InMatch` | 02:54:56 |
| `match state changed to MatchSuccessful` | 02:55:57 |
| `match state changed to EnterBattle` | 02:56:01 |
| `LogNet: Welcomed by server` + `LoadMap` Whitewoods_Day | 02:56:19 |

### 12.1 The transient save was never written, and MODE vs PATCH is confounded

`StandaloneSlot_<roleId>.sav` is the file that carries
`DamageCollectonDataSet`, which is the entire basis of ROADMAP item 7. Section
10 and item 1 measured it appearing **17 seconds** after `EnterBattle` on
2026-08-09 and being deleted when the run ended.

**On this run it never appeared at all**, and the run is now known to have
gone to completion: the match state returned to `NotMatch` after an escape, so
this is a whole dungeon lifecycle from `EnterBattle` to exit rather than a
snapshot of a run still in progress. `SaveGames/` was polled every 3 seconds by
an armed watcher throughout, and `StandaloneLevel/` stayed empty from start to
finish. A `find` across the entire `Saved/` tree during the run
returned exactly three files touched in twenty minutes: `CampData`, the market
cache, and the log itself.

**The substring `StandaloneLevel` occurs ZERO times in this run's log**,
whereas the 2026-08-09 runs opened with `TS.Dungeon: StandaloneLevel
requestEnterStandaloneLevel: match id 11111`. The pattern was checked against a
file that does contain it before the negative was believed -
`tests/test_logparse.py` returns 2 - so this is a measured absence and not a
typo in a grep.

> **An earlier draft read that as "not a patch regression". That was REFUTED by
> an independent pass and the claim is withdrawn.** Every observation of
> `requestEnterStandaloneLevel` and of the transient save was made on buildid
> **24619162**; this run is on **24813185**. **Build and mode are perfectly
> confounded**, and a log with no `StandaloneLevel` in it is exactly what a
> patch removing that call would produce. Preferring the mode explanation was
> reasoning from which answer felt less exciting, which is not evidence.
> **Neither explanation is excluded.** What IS established is the absence
> itself, and the consequence below survives either way: a dungeon run is not a
> guarantee of damage data.

**So the transient save is not a property of "being in a dungeon".** It follows
a *standalone level request*, and this dungeon never made one. That is the
load-bearing consequence and it is a constraint on Emberforge:

> **A dungeon run is not a guarantee of damage data.** Item 7's source exists
> in some modes and not others, so a reader must treat the file's absence as a
> normal mode rather than as a failure, and any plan that says "play a dungeon
> and collect damage" is underspecified until the mode is named.

**What differs between the two, observed rather than concluded:** the map URL
of the runs that DID write the save carried four axes -
`?levelId=119&roomModeId=0&matchType=1&matchId=11112`. This run's URL carries
two: `?levelId=113?matchId=11114`, with **no `roomModeId` and no `matchType`
anywhere in the log**.

**PARTY SIZE IS REFUTED as the discriminator.** The obvious hypothesis was that
the save belongs to solo play and this run was something else. The operator
attested **solo**, and the game corroborates him independently: the run loaded
`/Game/Project/Maps/Map_2/Spawners_Day/WhiteWoods_Enemy_Day_Solo01`, a spawner
sublevel whose own name says `Solo01`. The 2026-08-09 runs that DID write the
save were attested "Hallowgrove, Normal, Solo explore". **Both are solo, and
only one wrote the file**, so being alone is not what selects the behaviour.

**A named mode asset appeared to be in evidence. IT IS NOT, and the claim is
withdrawn.** An earlier draft said `DA_DungeonSettings_Classic` "appears in this
run's log" and called the settings asset the sharpest discriminator candidate
available. An independent pass refuted it and direct checking confirms: the
string occurs **exactly twice** in the whole log, at 02:29:05 and 02:29:31 UTC -
**27 minutes before** this run's `EnterBattle` - and both occurrences sit inside
`Puerts: Error: call TsConstruct of DA_DungeonSettings_Classic(...)`, which are
construction-failure lines rather than evidence the run loaded that asset.

**This run's settings asset is UNKNOWN.** The name is real and is recorded as a
name in `docs/OBSERVED_IDS.md`, with the binding explicitly disowned.

**And here is why it cannot be settled from the artifact.** Checking it needs
the settings asset from the 2026-08-09 runs, and **that log no longer exists** -
it is the 6.1 MB log of 11.8, destroyed by a later launch before anything
archived it. The question is unanswerable today *because a log was lost*, which
is the single most concrete argument this project has yet produced for ROADMAP
4c, closed the same session. From here the watcher keeps every log, so the next
run that writes a transient save can be compared against this one directly.

Until then the discriminator is **unmeasured**: it may be the settings asset,
`levelId`, the absent `matchType`, or something not in the URL at all.

### 12.2 The market cache was finally watched changing

`AvgPrice_937566.ini` had been seen only at 37 bytes (empty) and 343 bytes
(filled), with ROADMAP item 4 recording that **nothing had ever watched it
change**. It has now been watched.

It went from **37 to 157 bytes at 02:56:21 UTC** - twenty seconds after
`EnterBattle` and **two seconds after the map finished loading**. Both
generations are archived, the 37-byte state at 21:29 and 21:46 local and the
157-byte state at 21:56.

**This sits in tension with what ROADMAP item 4 already filed, and the tension
is the interesting part.** Item 4 measured the write happening **0.975 s after
the camp level-switch that followed a successful escape** and concluded the
trigger is **returning to camp**. This observation is the opposite direction:
the operator was leaving camp, and the write landed 2 s after the DUNGEON
finished loading.

Both are single observations of a real event, and they are not in conflict
unless "returning to camp" is read as exclusive. The reading that fits both is
that the write follows a **level transition**, and the two measured occasions
happen to be one in each direction. That is a hypothesis with n=1 on each side,
so it is recorded as one and item 4's own measurement is not amended.

What is genuinely new is that the file was **watched crossing between states**
for the first time - the previous record had only the two endpoints, 37 bytes
and 343, with nothing observing the change. Whether leaving the dungeon or a
later launch is what empties it again is still unmeasured, and the watcher is
armed and will now catch that too, which is the whole argument of item 4c.

### 12.3 A third escape noun

`TS.UI: onPartEscape` and `TS.Dungeon: getPartEscape` appear in this run.
Section 9 recorded `GroveSprite` and `FixEscapeBell` / `WindChime` as the
escape mechanics seen so far. `PartEscape` is recorded here as an observed
token and is **not interpreted** - "part" may mean partial, or a party, and
nothing in this capture separates those.

## 13. A re-anchor run that refused to anchor, 2026-08-25b

Fired after the operator changed items, to test whether the loadout behind the
section 11 curve still holds. **It does not answer that question, and the
reason it cannot is the result.**

### 13.1 Why a re-anchor was needed at all

**Section 11 never records which loadout produced 10.35.** It is careful to
SCOPE its claims - "the same weapon", and it explicitly disclaims anything
about another weapon, arrow, target or build - but the configuration itself was
never written down. The whole ten-point curve therefore rested on an unstated
baseline, and an item change would have invalidated comparisons with nothing on
disk to reveal it.

**And it cannot be baselined from files.** Measured directly across the item
change: `Deck.sav` produced **7 generations, all byte-identical**, including
after the change; `CampData_<userId>.sav` produced **8 generations, all
byte-identical**, despite the game rewriting the file. Only `Scav.sav` changed
content, at 21:31, and it flipped straight back. **Equipment is server-side**,
like `InvertCameraYAxis`. So a loadout baseline can only be pixels, and the
equipment screen must ride in the same frame stream as the damage numbers.

### 13.2 The run, and the solve that refuses it

Meter reset observed at 22:55:17 (`0`, `0 Hit`), ten body shots. The poller
was configured for 2 fps and **actually delivered 1.19 fps** - 320 frames over
269 s - because a full-screen grab costs more than the interval assumes. Quote
the delivered rate, not the requested one.

| hits | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| total | 14 | **28** | 42 | 57 | 71 | 85 | 100 | 114 | 129 | 143 |

**The hit-2 cell was filed as a dash and that was wrong.** An earlier draft
recorded it as a sampling gap and explained it as "two hits inside one 0.5 s
interval". Frames `f0159` and `f0160` both plainly read `28`, `2 Hit`. The
reading was captured, missed in the read-out, and then given an explanation it
never needed - a fabricated justification for absent data that was not absent.
Recovered by an independent pass.

**No constant per-hit value fits, under either display model.**

- Round-to-nearest: **empty**. `129` at 9 hits forces `v >= 14.2778`; `42` at 3
  hits forces `v < 14.1667`.
- Truncation: **empty by a hairline**, both bounds meeting at exactly `43/3`.

Both binding readings were re-read individually at 3x zoom, so the
contradiction is not a misread. The solve was run again against only the
individually-verified readings and the contradiction survives unchanged.

**The deltas look constant and are not evidence.** From hit 1 they run 14, 14,
15, 14, 14, 15, 14, 15, 14 - the one-wobble a constant value produces through a
rounding display, which is the trap 11.7 exists to name. Only the solve
separates the two cases.

**A transposition in an earlier draft is worth keeping visible**: hits 3-10 were
filed as 14, 14, 15, 14, 15, 14, 15, 14 when the true sequence is 14, 15, 14,
14, 15, 14, 15, 14. **Both sum to 115**, so any check against the total would
have passed it. A sum is not a check on an ordering.

**The recovered hit-2 reading strengthens the contradiction rather than
softening it**: `28` at 2 hits forces `v < 14.25`, which conflicts with the
`v >= 14.2778` that `129` at 9 hits forces, independently of the `42`-at-3
bound that was already binding.

### 13.3 What that means, and what it deliberately does not

Constancy is the measured signature of the **floor** (11.7): every floor run
admits a constant value, no off-floor run does. This run admits none, so **it
was fired from inside the floor breakpoint.** Distance is therefore confounded
with gear and **neither can be attributed**. The 10-hit total is 143 against
the floor's 104, a ratio of 1.375, and this document does **not** claim that
ratio is a gear effect.

**Two candidate confounds, neither excluded:**

- **Pacing drift.** 143 sits in the gap between 7 paces (231) and 8 paces
  (104), which the ten-point sweep never measured.
- **An unfrozen target.** The room can freeze bots. A moving target varies the
  distance shot to shot, and no such run can ever solve constant. Not checked
  during this run - freeze the bot before the next one.

### 13.4 What the run did establish

- **The panel's screen rectangle is now known**: the Total Damage value and hit
  count occupy `x 2085-2330, y 468-520` at 2560x1440. A cropped poller can
  capture it at roughly 150 KB a frame against the 3.1 MB a full-screen frame
  costs - a 20x saving that makes a long run affordable.
- **The loadout is on disk for the first time**, captured as equipment-screen
  frames in the same stream as the meter.
- ~~The `Progress Record` independently read `42, 3 Hit`, corroborating the
  mid-run 42-at-3 from a second on-screen source.~~ **WITHDRAWN.** It already
  read `42  3 Hit` in the reset frame itself, at 22:55:17, beside `0, 0 Hit` -
  before a single hit of this run had landed. It is the PREVIOUS run's record
  row, exactly as 11.2 says, so citing it as a second reading of this run's
  hit 3 was circular. A prior 3-hit run totalling 42 is a separate instance,
  not corroboration of this one.

**The next attempt is specified:** freeze the bot, stand clearly past the old
breakpoint at 12-14 paces, fire ten body shots. Constant at ~10.35 means the
gear did not move the floor; constant at another value means it did, and that
is a real finding; still no solution means the target was moving.

## 14. The sweep re-run with new gear AND a new talent, 2026-08-25b

Eight complete ten-hit runs, panel captured at 2 fps with a half-scale wide
shot every 2 s. **Two variables changed since the section 11 curve** - the
operator's items, and a talent point spent on `Focus Fire`. Nothing below can
attribute an effect to either one alone, and this section does not try.

### 14.1 The totals

Runs are listed in **capture order**, which the wide shots confirm is order of
**decreasing distance** - the target grows monotonically across R1 to R8.
**No pace labels are assigned.** Eight runs were fired against six planned
distances and the operator did not state the mapping, so labelling them would
be reconstructing the independent variable from clock order - the exact defect
that forced the previous sweep to be re-run (11.10).

| run | 10-hit total | prior sweep, by pace |
|---|---|---|
| R1 (farthest) | **137** | 10p = 104 |
| R2 | **138** | 8p = 104 |
| R3 | **299** | 6p = 309 |
| R4 | **680** | 4p = 546 |
| R5 | **914** | 2p = 687 |
| R6 | **898** | 0p = 691 |
| R7 | 879 | - |
| R8 (nearest) | 893 | - |

**Both clamps survive.** R1 and R2 differ by 0.7%; R6, R7 and R8 span 2.2%. The
three-regime shape - floor, steep middle, ceiling - is unchanged.

**The level moved by about a third at both ends**: floor 104 -> ~137 (1.32x),
ceiling ~689 -> ~900 (1.31x). **The middle did not move the same way** - the
third run reads 299 against a prior 309, slightly LOWER. With the distance
mapping unstated and the prior 6-pace figure itself contested (265 once, 309
once, 16.6% apart), no ratio is published here.

### 14.2 The real change: within-run constancy is GONE

This is the finding, and it is a negative.

**Every floor run in the previous sweep admitted a constant per-hit value**, the
same interval `[10.3500, 10.3571]` three times over. That constancy is what
made 10.35 the first number in this project to clear the independent-run bar.

**Of the eight runs here, exactly one admits a constant value** - R2, and only
under a truncating display model. Every other run contradicts under both
round-to-nearest and truncation.

A **proportional ramp** - each consecutive hit worth slightly more - was fitted
against every run:

| run | first hit | increment/hit | %/hit | fit error |
|---|---|---|---|---|
| R1 | 13.45 | 0.045 | 0.335% | 0 |
| R2 | 13.75 | 0 | - | 1 |
| R3 | 29.92 | 0 | - | 1 |
| R4 | 66.49 | 0.343 | 0.516% | 1 |
| R5 | 89.78 | 0.383 | 0.427% | 1 |
| R6 | 86.26 | 0 | - | 3 |
| R7 | 83.50 | 0 | - | 3 |
| R8 | 87.42 | 0.409 | 0.468% | 2 |

**The model does not hold uniformly and is therefore not adopted.** Four runs
fit a ramp of roughly 0.34-0.52% per hit, two fit constant, and two fit neither
well. A two-parameter model reproducing ten cumulative readings with an
absolute error of 1 is a good fit where it lands - but a mechanic that appears
in half the runs and not the other half is not a mechanic this project will
write down.

### 14.3 What is NOT claimed, and why

**Not claimed: that `Focus Fire` causes the ramp.** Its tooltip reads *"Rapid
Arrows increase the Damage Multiplier with each hit on the same enemy"*, and
**the operator was not using Rapid Arrows.** Measured inter-hit intervals were
**2.27 to 2.87 seconds** across R4 and R5 - individually drawn shots. Rapid
Arrows is Volley mode, up to five arrows fired rapidly; it cannot produce a
2.3-second cadence. So either the talent's effect exceeds its stated scope, or
the ramp has another cause entirely. Both are open.

**Not claimed: that the 1.32x level shift is a gear effect.** A talent point
was also spent. Two variables, one observation.

**Not excluded: positional drift.** A steady creep toward the target during a
run reproduces exactly this signature on the steep middle of the curve. The
wide shots show the target's apparent size roughly constant across R4, which
weakens the explanation - but apparent size was already established as
unreliable in this scene, having saturated twice when it was attempted
deliberately, so this is a weak instrument and not a refutation.

### 14.4 The experiment that separates them

**Repeat ten-hit runs on the FLOOR, three or four times.** The floor is a
clamp: distance changes do not move the number there, which is what makes it
the only regime where positional drift cannot manufacture a ramp. **Any ramp
observed on the floor is a real mechanic.**

> **This was run, and the advice was HALF WRONG - see 15.3.** The reasoning
> about drift holds. What it ignored is the display: at ~13.5 per hit a
> ~1%-per-stack effect is ~0.135 and rounds away entirely, so the floor is
> insensitive rather than decisive. The ceiling is the instrument. The runs
> were still worth firing - they produced the stack-count table in 15.2 - but
> the "any ramp on the floor is real" framing overstated what the floor can
> show.

The two floor runs here **disagree with each other** - R1 fits a 0.335%/hit
ramp with zero error, R2 fits constant. One-all. That is precisely why it needs
repeating rather than interpreting.

A second, sharper test if the first shows a ramp: fire ten hits alternating
between **two different targets**. "With each hit on the same enemy" implies
the stack resets per enemy, so an alternating run should show no ramp. If it
does, whatever is happening is not a same-enemy stacking effect.

## 15. The stack buff - a mechanic the operator saw and the capture confirms

**The operator found this, not the analysis.** He reported an icon that climbs
to **5** while he keeps hitting the same target inside a time limit, and said
damage seemed "gently nudged" upward as it climbed. That is the mechanic
section 14 was circling without being able to name.

### 15.1 It is on screen, and it is readable

The icon sits **centre screen above the energy bar** (operator), which puts it
in the half-scale wide shots already being captured. Cropping `x 600-690,
y 600-665` of the 1280x720 wide frame renders it plainly, with its stack count
beside it. Joining that crop to the meter crop by wall clock gives a row per
hit carrying **both** the cumulative damage and the stack count - the same
frame-to-frame join that bound class ids, applied to two regions of one frame.

Observed: the count runs **1 to 5** and holds at 5 while hits continue.

**A bare icon was filed as meaning "one stack". That is UNVERIFIABLE and the
rule is withdrawn.** In the run-8 frames the icon renders bare at `0, 0 Hit`
and already reads `2` at `14, 1 Hit`, so every bare observation available sits
at zero hits - equally consistent with "no stacks yet" and with "one stack, no
digit drawn". Separating them needs a frame showing a bare icon at a non-zero
hit count, and no such frame was captured.

### 15.2 It explains the broken solves, and the magnitude is SMALL

The operator then ran the right experiment unprompted: **runs deliberately held
to a maximum of 1, 2, 3, 4 and 5 stacks**, slower cadence, without moving,
letting the buff reset between. Ten-hit totals, all at the same floor distance:

| max stacks reached | 10-hit totals |
|---|---|
| 1 | **135**, **135** |
| 2 | **135** |
| 3 | **136** |
| 4 | **136** |
| 5 | **137**, **139**, **139**, **139** |

**Nine runs, re-derived by an independent pass.** An earlier draft filed four
runs as "1 -> 135, 2 to 3 -> 136, 5 -> 137 and 139". That was wrong in three
ways: the 2-stack run reads **135** and not 136, a **4-stack run was missed
entirely**, and 139 replicates **three times** rather than once. The error was
under-reading the capture, not arithmetic.

**Monotone non-decreasing in stack count, and the correction makes it cleaner
rather than weaker** - the replication at 5 stacks is now n=4. Note the first
increment is not visible until 3 stacks: 1 and 2 stacks both read 135. Under a model where stack `s` multiplies damage by
`1 + (s-1)c`, a run that builds 1,2,3,4,5,5,5,5,5,5 totals `(10 + 30c)` against
`10` for a run pinned at one stack, so the observed ratios imply
**c ~ 0.5% to 1% per stack, about +2% to +4% at five stacks.**

Taking the modal 5-stack total of **139** against the 1-stack **135** gives
`c ~ 0.99%` per stack; the single 137 reading gives `c ~ 0.49%`.

**No coefficient is published from that**, and the reason is precision: the
spread is 135 to 139 on integer totals near 137, while run-to-run variation at
the same distance was already 137 against 138 in the same session. The signal
is barely above the noise.

### 15.3 The floor is the WRONG place to measure this - correcting 14.4

Section 14.4 proposed repeating floor runs as the decisive test, on the grounds
that a clamp makes positional drift harmless. **The reasoning about drift was
right and the conclusion was wrong**, because it ignored the display:

At the floor a hit is about **13.5**, so a 1%-per-stack effect is **0.135 per
hit** and the whole five-stack bonus is well under one displayed unit per hit.
It **rounds away**. That is exactly what the joined rows show - stacks climbing
2, 3, 4, 5 beside deltas that sit flat on 14.

**The ceiling is the sensitive instrument.** At about 90 per hit, 1% is 0.9 and
five stacks is roughly 3.6 - several display units, far above rounding. Any
future measurement of this mechanic belongs at the near end of the curve, not
the far end.

### 15.4 What this does to the earlier sections, and it is not small

**11.7's headline may be an artifact.** It reports that a constant per-hit value
fits every FLOOR run and no off-floor run, and reads that as constancy being a
property of the clamp. A stack buff of about 1% per stack reproduces that split
exactly **without any distance term**: invisible at 10.35 per hit where it
rounds away, visible at 55 to 69 per hit where it does not.

So the observation stands and **the interpretation is now contested**. Two
explanations survive:

- the operator's own positional variance off the floor, which 11.7 assumed, or
- this stack buff, which nobody knew existed when 11.7 was written.

**This is NOT a retraction of the ten-point curve.** The totals are measured and
unaffected. What is contested is the *inference* that constancy tracks the
clamp.

**Whether the buff predates tonight is UNMEASURED.** The operator spent a talent
point on `Focus Fire` this session, whose tooltip reads "Rapid Arrows increase
the Damage Multiplier with each hit on the same enemy" - a same-enemy stacking
multiplier, which matches. But **he was not using Rapid Arrows**: measured
inter-hit intervals of 2.27 to 2.87 seconds are individually drawn shots, and
Rapid Arrows is Volley. So either the talent's scope exceeds its tooltip, or
the icon is a base mechanic that was present all along and too small to see at
10.35 per hit. **The old logs that could settle it no longer exist.**

### 15.5 The measurement that would settle it

At the **ceiling**, where the effect clears rounding: ten hits pinned at one
stack, then ten allowed to reach five, without moving. The difference should be
about 3 to 4 display units per hit rather than a fraction of one, which turns
`c` from an inference into a measurement.

To separate talent from base mechanic, fire ten hits **alternating between two
targets**. "With each hit on the same enemy" implies the stack resets per
enemy; if the buff survives target switching it is not that talent.
