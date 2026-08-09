# ADR-004: Redaction is mandatory and tested

## Context

The primary data surface is a log file that identifies the operator. Measured in
`MistfallHunter.log`: the operator's **SteamID64**, their **Steam persona**, GSDK
**openID** and **userId**, an **EOS ProductUserId**, and an **IP-resolved city,
state and country**. The GVAS saves add `AccountName`, and `LoginOptions.sav`
also carries `SelectedServer`.

This repo is public from the first commit
([ADR-006](ADR-006-apache-2-and-public.md)), and the project's whole method
depends on committing real captured data as fixtures - a redacted log excerpt is
how a measurement stops being a memory.

Those two facts collide directly. A convention of "remember to scrub before
committing" resolves the collision on paper and not in practice: it fails silently,
it fails under time pressure, and a leak is not revocable by a later commit
because the history keeps it.

Measured: [`../FINDINGS.md`](../FINDINGS.md) section 4, "PII rule".

## Decision

Redaction is a mandatory, tested stage sitting **between any capture and any
artifact that could be committed**. Not a review-time check, not a habit.

Concretely:

- `lanternlight.redact` is the single gate. Log excerpts, fixtures, samples,
  issue text and screenshots all pass through it before they can be committed.
- **The redactor itself is tested**, and its tests are written before the
  parsers that feed it. A parser with an untested redactor downstream is a leak
  with extra steps.
- A `.gitignore` covering raw capture locations backs it up, as defence in depth
  rather than as the control.
- Fields known to require redaction today: SteamID64, Steam persona, GSDK openID
  and userId, EOS ProductUserId, IP-derived location, `AccountName`. The list is
  additive - a newly observed identifier is added the moment it is seen.

## Consequences

- Committed fixtures are redactor **output**, never raw captures. A test asserting
  against a raw excerpt is a defect regardless of whether it passes.
- Redaction must be stable and deterministic, so that a redacted identifier stays
  joinable across a fixture without revealing the original.
- Every new data surface inherits this gate before it is allowed to produce a
  committable artifact. Adding the surface and adding its redaction are one piece
  of work, not two.
- Some debugging is slower, because the convenient thing - pasting a raw log
  line into an issue or a chat - is exactly the thing that is forbidden.
- The raid recon pass will produce the largest capture this project has yet
  handled, and it will contain identifiers not on the list above. Extend the
  redactor as part of that work, not afterwards.

## Status

**Accepted.** 2026-08-09.
