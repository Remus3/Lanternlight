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
