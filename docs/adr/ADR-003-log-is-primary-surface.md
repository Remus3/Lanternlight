# ADR-003: The game log is the primary data surface

## Context

With process interaction forbidden
([ADR-001](ADR-001-no-game-process-interaction.md)) and asset extraction blocked
([ADR-002](ADR-002-no-asset-extraction.md)), three surfaces remain, all read-only:
the game log, the GVAS save files, and passive screen capture of the operator's
own display.

A pre-launch sweep of `%LOCALAPPDATA%` found nothing, and that negative was
nearly recorded as final. It was wrong for a mundane reason: the game had never
been run, so it had not yet written its Saved tree. After the operator launched
the game on 2026-08-09 at 08:18, a second read-only sweep found
`%LOCALAPPDATA%\MistfallHunter\Saved\` created at 08:18:56.

What the log turned out to carry, without touching the process: map and sublevel
transitions with ms timestamps, `match state changed to <state>`, a `match id`
field, `setClassGender inclassid ==NN`, weapon config ids via
`OnRep_WeaponCfgId` and `server_refreshKnightFeature`, equipment asset paths,
`seasonId`, server region, gateway hostname, `roleLimit`. Categories are
namespaced (`LogStk`, `TS.Avatar`, `TS.Dungeon`, `TS.Camp`, `TS.Inventory`,
`TS.Network`, `Puerts`). It reached 567 KB in ten minutes and appends live.

The saves are small (four files, 2-2.7 KB) and slow-changing. Screen capture is
rich but requires a human or an OCR pipeline to interpret.

Measured: [`../FINDINGS.md`](../FINDINGS.md) section 4.

## Decision

The game log is the primary data surface. The GVAS saves are secondary, answering
"what is the current state" rather than "what just happened". Passive screen
capture is the third surface, used where the game renders a value it never writes
down.

Consuming the log is done read-only and shared, never holding a lock on a file
the game is writing.

## Consequences

- The log tail is a foundational component rather than a convenience, and is
  ranked accordingly on the roadmap. It has to survive truncation and replacement
  on game restart.
- Log line shapes are an **undocumented, unversioned interface owned by someone
  else.** A patch can silently change or remove any of them. Parsers must fail
  loudly on an unrecognised shape rather than quietly dropping it, or the project
  will lose a data source without noticing.
- The log is the surface that carries PII, which is what makes
  [ADR-004](ADR-004-redaction-is-mandatory.md) mandatory rather than tidy.
- **What the log carries in a raid is unmeasured, not absent.** The probed session
  reached camp and character creation only. Loot names, extraction events and
  match results have not been seen, and no schema should be designed against a
  guess about them.
- Ids in the log arrive as numbers with no name string attached, so a log-only
  reading is insufficient on its own. The class-id table was established by
  joining log lines to screen-rendered text on wall clock
  ([`../OBSERVED_IDS.md`](../OBSERVED_IDS.md)) - surface 1 and surface 3
  together.

## Status

**Accepted.** 2026-08-09.

Carrying a process lesson worth keeping: the pre-launch negative was a correct
measurement of the wrong world state. Anything probed before the game had ever
run needs re-probing after it has.
