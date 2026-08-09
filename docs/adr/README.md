# Architectural decisions

Short records of choices that would otherwise get re-litigated. **Before
re-opening any of these, read the record first** - most of them were decided
against a measurement, and the measurement is cited.

Each ADR follows the same four headings: **Context**, **Decision**,
**Consequences**, **Status**.

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-no-game-process-interaction.md) | No game-process interaction, ever | Accepted, permanent |
| [ADR-002](ADR-002-no-asset-extraction.md) | No asset extraction - measured blocked | Accepted |
| [ADR-003](ADR-003-log-is-primary-surface.md) | The game log is the primary data surface | Accepted |
| [ADR-004](ADR-004-redaction-is-mandatory.md) | Redaction is mandatory and tested | Accepted |
| [ADR-005](ADR-005-omit-rather-than-guess.md) | Omit rather than guess | Accepted |
| [ADR-006](ADR-006-apache-2-and-public.md) | Apache-2.0 and public from the first commit | Accepted |

## Conventions

- **Accepted** means in force. **Accepted, permanent** means it is not subject to
  revision by this project at all - only ADR-001 carries that, and it carries it
  because the cost of being wrong is someone's account.
- An ADR is superseded, never edited into a different decision. If the world
  changes, write a new record that names the one it replaces.
- Ground truth lives in [`../FINDINGS.md`](../FINDINGS.md) and
  [`../OBSERVED_IDS.md`](../OBSERVED_IDS.md). An ADR cites those; it does not
  restate measurements as if it were their source.
