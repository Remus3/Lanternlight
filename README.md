# Lanternlight

A companion and analysis project for **Mistfall Hunter** (Steam appid 3282300),
the dark fantasy PvPvE extraction ARPG by Bellring Games / Skystone Games.

**Emberforge** is the combat and build math engine that Lanternlight is built
around.

## What makes this one unusual

Most game companion tools read the game. Lanternlight cannot, and does not want
to. Two measured facts set the whole design:

1. **The game ships kernel-level anti-cheat** (Bellring Anti-Cheat, disclosed on
   the store page). So there is no injected plugin, no process memory read, no
   packet capture, no hooked overlay, and no synthetic input into the game
   window. Not as a default that gets relaxed later - as a permanent boundary.
   See [ADR-001](docs/adr/ADR-001-no-game-process-interaction.md).
2. **All 15 shipped pak chunks are AES-encrypted** under a single global key
   (`flags=Compressed|Encrypted|Indexed`, `keyguid=ZERO`). A loose-file sweep of
   the entire 41.6 GB install returned zero game data files. There is no static
   data table to extract, and getting one would require exactly the process
   access that rule 1 forbids. See
   [ADR-002](docs/adr/ADR-002-no-asset-extraction.md).

So Lanternlight deliberately does the opposite of a typical companion tool. **It
touches nothing.** Everything it knows, it derives from what the game itself
writes into user-writable space, plus passive reading of the operator's own
screen:

- the live-appending log at `%LOCALAPPDATA%\MistfallHunter\Saved\Logs\MistfallHunter.log`
- a growing set of unencrypted UE GVAS `.sav` files under the same tree - four at
  first probe and **eight distinct names** within two days, one of which exists
  only for the duration of a run, so a reader enumerates rather than assumes
- `AvgPrice_937566.ini`, a market and trade-price cache
- passive desktop screen capture, on the operator's own display, with no overlay

That is a narrower surface than an injected tool would have. It is also the only
surface that is safe to use on an account you care about.

The second constraint follows from the first. Because nothing is extractable,
**no number in this repo can be looked up - it has to be measured**, and the
hard engineering problem is provenance: proving where every value came from, and
refusing to emit one that has no source. Where a value is unknown, Lanternlight
omits the field rather than guessing it, and keeps "unmeasured" distinguishable
from "measured zero". See [ADR-005](docs/adr/ADR-005-omit-rather-than-guess.md).

## Status

Honest as of 2026-08-11. This project is days old and most of it does not exist.

One caveat before the table, because a new contributor hits it first: **a fresh
clone runs one failing test.** `tests/test_lane_contract.py` bakes the absolute
checkout path into a rendered contract, so the suite is only green *in place*.
It is a known defect, filed as `ROADMAP.md` item 2d, and it predates the work
below. Every test count in this repository is an in-place number.

| Area | State | Notes |
|---|---|---|
| Feasibility probe | **Done** | Anti-cheat and encryption measured, not assumed. `docs/FINDINGS.md` |
| Pak / encryption probe | **Done** | 15/15 chunks encrypted, 101,500 TOC entries |
| Class id table | **Done** | Ids 10-15 bound to class names by a log-to-pixel join. `docs/OBSERVED_IDS.md` |
| Weapon config ids | **Partial** | Creation-preview ids recorded. The live id space is now **joined**: it is the same space as item cfgIds |
| Class reference | **Done** | All six researched independently and adjudicated into `docs/CLASSES.md` |
| Specialist lanes | **Done** | Eight lanes, ownership enforced by tests, worktree-isolated, each with on-disk state and its own ledger fragment so no two lanes race |
| Log parsing | **Early** | `lanternlight.logparse` reads the surfaces named above |
| Redaction | **Hardened** | Sees through base64, hex and raw UTF-16, scans binaries, and refuses to certify what it cannot assess. `ROADMAP.md` item 0 |
| Market cache | **Parser done** | `AvgPrice_937566.ini` filled. `lanternlight.avgprice` parses it; watcher not built |
| Save watcher | **Done** | `lanternlight.savewatch` snapshots every generation of every save, refuses any destination inside a repo working directory, and never writes to the source |
| Dungeon data | **Prologue measured** | Lifecycle, escape portals, loot, death and escape states all observed. `docs/FINDINGS.md` section 9 |
| Raid / PvP data | **Solo measured, PvP unmeasured** | Solo explores are now measured at non-zero `matchId`, which **refutes** the old assumption that a non-zero `matchId` means a matchmade run. No run with another player has been observed |
| GVAS `.sav` reader | **Done, one gap named** | Every save parses with zero undecoded bytes, including 263 captured generations of the transient run-scoped save. Natively serialised structs (`Vector`, `Rotator`, `Quat`, `Vector2D`) are handed back verbatim and **named** undecoded rather than guessed - `Vector` and `Rotator` share a width, so only the name separates them. Published parsers do not work on this build - UE 5.4+ changed the property tag |
| GVAS `.sav` **writer** | **Done** | `serialise(parse(raw)) == raw`, byte-identical on **276** files - 6 fixtures, 7 live saves, all 263 captures. Byte identity is a far harsher oracle than value equality: it immediately caught a `TextProperty` flags word the reader had been silently discarding since it was written. `transform()` and `rebuild()` recompute every enclosing `Size`, so nothing is hand-patched |
| Transient-save fixture | **Committed** | `tests/fixtures/gvas/standalone_slot.gvas.b64`, 19,867 bytes, built by a committed and reproducible builder. It scans **zero** identifiers where its 177,878-byte source scans **882** - the positive control is what makes the zero mean anything |
| Live log tail | **Not started** | Port 8811 reserved, nothing listening |
| **Emberforge** | **Empty, but no longer blocked** | It still **computes nothing**. What changed on 2026-08-11 is that the input exists: the game writes **per-hit damage** with sub-millisecond timestamps, and the log binds damage to ability names. No formula is published anywhere; the numbers are now measurable anyway. `ROADMAP.md` item 7 |
| Dashboard | **Does not exist** | Port 8810 reserved. See `BACKLOG.md` |
| Packaged release | **None** | No wheel, no installer, no tagged version |

If a row above says "not started", believe it. Nothing here is oversold.

## Requirements

- Windows (the game, and the paths, are Windows-only)
- Python 3.14
- A local install of Mistfall Hunter, if you want to run anything against real
  data. The tests do not require the game.

No third-party runtime dependencies are required for the current surface.

## Quick start

```
git clone https://github.com/Remus3/Lanternlight
cd Lanternlight
python scripts/install_hooks.py
python -m pytest
```

`install_hooks.py` is not optional housekeeping - a fresh clone runs **zero**
git hooks until you run it, because `core.hooksPath` is local config and is
never cloned. See `docs/OPERATIONS.md`.

## Documentation

| Document | What is in it |
|---|---|
| [`docs/FINDINGS.md`](docs/FINDINGS.md) | The feasibility probe. Every line is a measurement, and where something was not measured it says so |
| [`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) | First-party id observations, each with the method that established it |
| [`docs/CLASSES.md`](docs/CLASSES.md) | **Single source of truth for all six classes.** Six independent research passes, adjudicated by a seventh agent that wrote none of them |
| [`docs/CLASS_RESEARCH.md`](docs/CLASS_RESEARCH.md) | Blackarrow vs Shadowstrix, the earlier decision record behind the operator's class choice |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module map, the three data surfaces, and where the redactor sits |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | How to run things, plus the safety boundary as an operational rule |
| [`docs/adr/README.md`](docs/adr/README.md) | Architectural decisions, indexed |
| [`ROADMAP.md`](ROADMAP.md) | What is next, in priority order, each with an acceptance criterion |
| [`BACKLOG.md`](BACKLOG.md) | Aspirational. Nothing here is committed to |
| [`WAKEUP_NOTES.md`](WAKEUP_NOTES.md) | Session hand-off |

## Contributing

Two house rules, both enforced by tests rather than by review.

1. **7-bit ASCII only.** No em-dashes, no en-dashes, no smart quotes, anywhere
   in authored content - code, comments, docstrings, Markdown, commit messages.
   Use `" - "` for a clause break and `-` otherwise.
2. **Every feature starts with a failing test.** Write the characterization or
   regression test first, watch it fail, then implement. This matters more than
   usual here: almost every fact in this repo is a measurement, and a test is
   how a measurement stops being a memory.

Two smaller conventions worth knowing before your first PR:

- **No log excerpt, fixture or sample may be committed without passing through
  the redactor.** The game log carries a SteamID64, a Steam persona, publisher
  SDK and EOS account ids, and an IP-resolved location. See
  [ADR-004](docs/adr/ADR-004-redaction-is-mandatory.md).
- If you do not know a number, leave the field out. A missing value is
  recoverable later; a confident wrong one poisons everything downstream of it.

Do not add a `Co-Authored-By` trailer to commits.

## License

Apache License 2.0. Copyright 2026 Moonbeam. See [`LICENSE`](LICENSE).

**Not affiliated with, endorsed by, or connected to Bellring Games, Skystone
Games, or Valve.** Mistfall Hunter and all related names and marks belong to
their respective owners.

**No game assets or extracted game data are redistributed by this project.**
That statement is trivially true and will stay true: the game's content is
encrypted and this project has no means, and no intention, of decrypting it.
Everything Lanternlight publishes is either its own code, or an observation
recorded by an operator watching their own screen.
