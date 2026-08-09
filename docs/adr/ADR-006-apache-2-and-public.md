# ADR-006: Apache-2.0 and public from the first commit

## Context

The licensing and visibility posture had to be settled before the first commit
rather than after, because both are expensive to change later - a repo that
starts private accumulates content nobody audited for publication, and a
relicensing after contributions arrive needs every contributor's agreement.

The precedent project (RedMoon) is Apache-2.0 and public, so the default was
continuity unless something about this project argued otherwise.

Two things about this project bear on the choice:

- It analyses a **commercial game owned by someone else** (Bellring Games /
  Skystone Games), which makes an explicit non-affiliation statement necessary
  rather than decorative.
- It **cannot redistribute game assets even in principle**, because the content
  paks are encrypted and this project has no means of decrypting them
  ([ADR-002](ADR-002-no-asset-extraction.md)). The usual hardest question for a
  game-adjacent repo answers itself.

## Decision

Apache License 2.0, copyright **Moonbeam 2026**. Public at
`github.com/Remus3/Lanternlight` from the first commit.

The README carries, and keeps carrying:

- a **non-affiliation disclaimer** naming Bellring Games, Skystone Games and
  Valve, and stating that Mistfall Hunter and related marks belong to their
  owners;
- a **no-redistributed-assets statement**, noting that it is trivially true and
  will stay true.

Third-party code is not vendored without a license check. GPL and other copyleft
sources are do-not-vendor outright, since vendoring one would relicense this
project. Verbal clearance from a maintainer is not a substitute for a license
file, and a license file that names no copyright holder is not a grant.

## Consequences

- Apache-2.0 brings the explicit patent grant and the `NOTICE` mechanism, which
  is the reason to prefer it over MIT for anything that might grow contributors.
- **Public from commit one means the PII controls have to exist from commit one.**
  This is the single largest consequence, and it is why
  [ADR-004](ADR-004-redaction-is-mandatory.md) is a tested gate rather than a
  convention. There is no private grace period in which a raw log excerpt is
  harmless.
- Every commit is permanent and world-readable. A leak is not undone by a later
  commit.
- Being public is also a benefit the project should use: measured findings are
  publishable, and publishing them is how a fabricated wiki number gets displaced
  by a sourced one.
- The non-affiliation notice must survive future README rewrites. It is not
  boilerplate to be trimmed for tone.

## Status

**Accepted.** 2026-08-09.
