# Architecture

Module map and data flow, as of 2026-08-09.

**Most of the boxes below are empty.** This document describes the shape the
project is being built into, and marks each part with whether it exists. Where a
box says "not built", nothing is there - not a stub with a TODO, nothing. Read it
as a map of intent with the honest bits called out, not as a description of a
running system.

## The constraint that determines the whole shape

Mistfall Hunter ships kernel-level anti-cheat and fully encrypted content paks.
There is therefore no client integration and no data extraction, permanently
(`FINDINGS.md` sections 2 and 3, [ADR-001](adr/ADR-001-no-game-process-interaction.md),
[ADR-002](adr/ADR-002-no-asset-extraction.md)).

Every arrow in this document points **out of** the game and into Lanternlight.
None point back. There is no write path to the game, no hook, no injection, and
no input synthesis. If a future design ever needs an arrow pointing the other
way, the design is wrong.

## The three data surfaces

Everything Lanternlight can ever know arrives through one of these three.

### 1. The game log - primary

`%LOCALAPPDATA%\MistfallHunter\Saved\Logs\MistfallHunter.log`

Written by the game itself into user-writable space, live-appending (567 KB in
the first ten minutes of play). Reading it touches nothing. Categories are
namespaced: `LogStk`, `TS.Avatar`, `TS.Dungeon`, `TS.Camp`, `TS.Inventory`,
`TS.Network`, `Puerts`.

Known-readable today: map and sublevel transitions with ms timestamps, `match
state changed to <state>`, a `match id` field, `setClassGender inclassid ==NN`,
weapon config ids via `OnRep_WeaponCfgId` and `server_refreshKnightFeature`,
equipment asset paths, `seasonId`, server region, gateway hostname, `roleLimit`.

Unmeasured: everything that only happens in a raid. No raid has been entered, so
loot names, extraction events and match results are **unmeasured, not absent**.

This is the primary surface, and that is a decision rather than an accident -
see [ADR-003](adr/ADR-003-log-is-primary-surface.md).

### 2. GVAS save files

`%LOCALAPPDATA%\MistfallHunter\Saved\SaveGames\*.sav` - four files, 2-2.7 KB
each, plain Unreal GVAS (magic `47 56 41 53`), **not encrypted**. Also under the
same tree: `Config\Windows\GameUserSettings.ini`, `Config\Windows\Engine.ini`,
and `AvgPrice_937566.ini` (the market and trade-price cache, empty when
measured).

Read-only, snapshot-at-a-time. Small and slow-changing, so this surface answers
"what is the current state" rather than "what just happened".

### 3. Passive screen capture

Screenshots of the operator's own display. **No overlay, no window hook, no
capture of the game's swapchain** - a desktop-level poller writing timestamped
frames, and nothing more.

This surface exists because it is the only route to values the game renders but
never writes down. Its proven use so far is the class-id join: the log emits
`inclassid ==NN` and never a name, so the name was read as rendered text off a
frame and joined to the log line on wall clock (`OBSERVED_IDS.md`). That worked
because a human read the panel. Automating it with OCR is a `BACKLOG.md` item,
not a current capability.

## Flow

```
  GAME (never touched)
    |  writes
    v
  %LOCALAPPDATA%\MistfallHunter\Saved\        operator's display
    |                    |                          |
    | log                | .sav / .ini              | passive frames
    v                    v                          v
  logparse            (save reader)            (frame poller)
   EARLY               NOT BUILT                 SCRATCHPAD
    |                    |                          |
    +--------------------+--------------------------+
                         |
                         v
                +------------------+
                |     REDACT       |   <-- mandatory, tested, no bypass
                +------------------+
                         |
         +---------------+----------------+
         |                                |
         v                                v
   committable artifacts            in-memory / local use
   (fixtures, docs, samples)        (never leaves the machine)
         |                                |
         v                                v
      git / public repo             Emberforge  (EMPTY - computes nothing)
                                          |
                                          v
                                    dashboard :8810  (NOT BUILT)
```

## Where the redactor sits

**Between any capture and any artifact that could be committed.** That position
is the whole point and it is load-bearing.

The log carries the operator's SteamID64, Steam persona, GSDK openID and userId,
an EOS ProductUserId, and an IP-resolved city, state and country. The saves carry
`AccountName`. This is a public repo. A redactor invoked "when you remember to"
is not a control, it is an intention, so the flow places it upstream of the
commit boundary rather than at review time.

Three consequences that follow from the position, not from taste:

- **No raw sample reaches a fixture.** If a test needs log data, the fixture is
  redacted output, and the redactor that produced it is itself tested.
- **The redactor is tested before the thing that feeds it.** A parser with an
  untested redactor downstream is a leak with extra steps.
- **In-memory and local-only paths still go through it** where they can, because
  a local path acquires a log file or a crash dump sooner or later.

See [ADR-004](adr/ADR-004-redaction-is-mandatory.md).

## Packages

| Package | State | Responsibility |
|---|---|---|
| `lanternlight.paths` | early | Locating the Saved tree, the log, the saves, the market cache. One place that knows Windows paths |
| `lanternlight.logparse` | early | Log lines to structured events |
| `lanternlight.redact` | early, tested | Strip PII. The gate on the commit boundary |
| `lanternlight.gvas` (save reader and writer) | **done** | GVAS parse and byte-identical re-serialise. ROADMAP item 2. This row read "not built" until 2026-08-12, long after the reader shipped - a stale recital found while closing item 3 |
| `lanternlight.tail` (log tail) | **done, library only** | Follows the appending log; no service and nothing bound. ROADMAP item 3 |
| `lanternlight.damage` | **done** | The rolling damage window, accumulated and deduplicated across generations. ROADMAP item 7 |
| `lanternlight.savewatch` | **done** | Snapshots every generation of every save; refuses a destination inside a repo working directory |
| `emberforge` | **empty** | The combat and build math engine. **It computes nothing.** No formulas are published anywhere, so there is nothing yet to encode |
| `tests/` | early | Every feature starts with a failing test here |
| `tools/` | **not built** | Operator-run probes. `probe_paks.py` currently lives in `scratchpad/` and is slated to move here |

`emberforge` being empty is not a gap to be embarrassed about - it is the
accurate state. As of 2026-08-09 no cooldown values, damage coefficients or
stealth durations are published anywhere trustworthy (`CLASS_RESEARCH.md`), so
the engine has no inputs. Filling it is blocked on measurement, not on coding.

One design constraint is already fixed: Blackarrow now and Shadowstrix at slot 2
means **two-class coverage is scheduled rather than accidental, so the data model
must not hard-code a single class shape.**

## Reserved ports

All local-only. **None of these are built and nothing is listening on any of
them.** They are reserved so that two future services do not collide.

| Port | Service | State |
|---|---|---|
| 8810 | Dashboard | not built (`BACKLOG.md`) |
| 8811 | Log-tail service | not built - the `lanternlight.tail` **library** shipped 2026-08-12 and deliberately binds nothing (ROADMAP item 3) |
| 8813 | Emberforge | not built |

8814 is reserved for an overlay control channel and is unbound; 8815-8819 are
free. **`CLAUDE.md` is the authority** for the block and for the machine-wide
registry - this table lists only what has a named service.

Corrected 2026-08-27: this section used to say "8812 is deliberately skipped",
which contradicted `CLAUDE.md`, where 8812 has been allocated to a vision / OCR
service all along. Two copies of an allocation is two chances to drift, so the
range now lives in one place and this file defers to it.

## Data provenance

The recurring rule, stated once here because it shapes every schema: a value
carries how it was established, and **"unmeasured" stays distinguishable from
"measured zero"**. `OBSERVED_IDS.md` is the reference implementation of this in
prose - every row names its method, and the one row established by elimination
rather than observation says so. Structured data in this project should meet the
same bar. See [ADR-005](adr/ADR-005-omit-rather-than-guess.md).
