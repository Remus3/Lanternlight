# NOTICE - vendored work, MAIN's fleet kit

This directory holds a work that Lanternlight did not write. It is vendored
under Apache-2.0, the same license this repository carries, and this file is
the attribution and the statement of changes that Apache-2.0 section 4(b)
requires.

## Provenance - CURRENT PIN

| Field | Value |
|---|---|
| Files | `FLEET-COMMON.md`, `fleet_headless.py`, `MANIFEST.json` |
| Origin project | MAIN, the supervisor tree on this machine's note channel |
| Published copy | MAIN's outbox, directory `2026-10-03-1016-from-MAIN-FLEET-KIT-v3/`, announced by MAIN note 1016 |
| Kit version | `KIT_VERSION = 3` |
| License | Apache-2.0 |
| Copyright holder | this repository's own sole copyright holder, the operator - the same holder named in this repository's `LICENSE` and `NOTICE` |
| Vendored | 2026-10-03, `OPS-120` |

| File | SHA-256 of what was licensed |
|---|---|
| `FLEET-COMMON.md` | `5f3385eef377fa127a5d5e5741acd302bb5bf9fc13e92fdc610bf3f0630f0f54` |
| `fleet_headless.py` | `c76c03c3ca830e157a78e00e0e97e25e8d1c88804b15d3aaa0580ce23851dbac` |
| `MANIFEST.json` | `9e7a68333096b278d0b9d511e336f1df8bbd05d24d5565e657567b05b67fc255` |

All three were hashed against MAIN's outbox copy before a byte was copied: 3 of
3 MATCH. The order notes (MAIN 0955, 1014, 1016) were also byte-identical to
MAIN's outbox copies.

## How the license gate was satisfied, not waived

The kit arrived with no license statement and no copyright line, and the order
notes named none. `CLAUDE.md` lists the license gate as a floor that MAIN's
authority cannot lift, so the vendoring was HELD by a distinct adjudicator on
2026-10-03. The operator - the kit's owner and copyright holder - then ruled in
this repository's own session chat the same day: the kit may be vendored into
Lanternlight under Apache-2.0 with the operator as copyright holder, at
`ops/fleet_kit/` rather than `third_party/fleet_kit/`.

## Why this lives at `ops/fleet_kit/` and not `third_party/`

The kit's own `conformance()` hardcodes `ops/fleet_kit/`, and MAIN's drift
sweep checks every tree at that path. The operator chose that path over this
repository's `third_party/<name>/` convention; `CLAUDE.md` records the
exception in its vendored inventory.

## Changes

None. The three files are byte-identical to what was licensed, and
`tests/test_fleet_kit_conformance.py` fails if any of them changes. This
NOTICE is the only file Lanternlight added to the directory. Do not edit a kit
file: a defect is reported to MAIN, which ships a new kit version to every tree
at once, and the new version replaces all three files in one commit.
