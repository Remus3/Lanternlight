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
for this - **plausible, and unbound**. Nothing observed connects the talent to
these fields. Second, in the sampled generation the damage circle and the safe
circle share the same centre and the same radius to the bit, so this capture
caught the zone before it began to move. **Whether the circles ever diverge is
unmeasured**, and a run watched to completion is what would show it.

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
- Whether `Gyldenmist Tolerance` names the `PlayzoneData` mechanic. Suggestive,
  unbound, and not to be written down as a binding (10.9).
- What `MatchID 11112` selects. It is constant across the run and matches the
  solo-explore ids in LL-0022, and nothing observed says what the number means.
