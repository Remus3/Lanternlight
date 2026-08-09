# ADR-002: No asset extraction - measured blocked

## Context

The natural foundation for a build-math engine is the game's own data tables,
pulled out of its assets. For a UE5 title that usually means reading the IoStore
containers under `Content\Paks`.

This was probed directly rather than assumed either way. `probe_paks.py` read 144
bytes from each `.utoc` and 221 bytes from the end of each `.pak`, opening no
process and writing nothing. Results:

- `global.utoc` / `global.ucas` plus **15 content chunks**, 101,500 TOC entries
  in total, `tocver=8`.
- **Every content chunk carries `flags=Compressed|Encrypted|Indexed`.** Not some.
  All 15.
- Every legacy `.pak` sidecar reports `pakver=12 encrypted_index=True`.
- `keyguid=ZERO`, meaning a single global AES key rather than per-chunk named
  keys. That key is not on disk in plaintext.

A loose-file sweep of the entire 41.6 GB install for `*.ini *.json *.csv
*.uasset *.cfg` returned exactly three files: a zero-byte
`StagedBuild_MistfallHunter.ini` and two GSDK config files sitting next to the
anti-cheat binaries. None of them game data.

Measured: [`../FINDINGS.md`](../FINDINGS.md) section 3.

## Decision

No asset extraction. Lanternlight will not attempt to obtain, derive, or use the
pak encryption key, and will not vendor or redistribute any extracted game data.

This is not merely "we choose not to". Obtaining the key would require either
dumping it from the running process - forbidden outright by
[ADR-001](ADR-001-no-game-process-interaction.md) - or statically reverse
engineering a binary that ships with kernel anti-cheat. Neither is acceptable
here, so the decision is forced as well as chosen.

## Consequences

- **There is no first-party static data table available to this project.** The
  RedMoon extractor half is dead alongside its live-state half.
- Every value Emberforge could ever use has to be measured or observed, not
  looked up. This is the single fact that most shapes the project's cost and
  pace.
- The "no game assets or extracted data are redistributed" statement in the
  README is trivially true and will stay true.
- Community reference data may be consulted, but stays clearly marked as
  unverified third-party, is never promoted into a first-party table, and is
  never vendored without a license check.
- `probe_paks.py` is kept and re-run after patches. The purpose is not to
  re-confirm the finding - it is to detect a future patch that ships
  **unencrypted** paks, rather than assuming that will never happen.

## Status

**Accepted.** 2026-08-09.

The measurement, not the conclusion, is what would change this. If a probe after
some future patch reports a chunk without the Encrypted flag, write a new ADR
citing that run. Do not reopen this one on the strength of a rumour or of a tool
that claims to support the title.
