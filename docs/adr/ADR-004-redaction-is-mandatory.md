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

Redaction is a mandatory, tested stage sitting **between any operator
identifier and anything that leaves this machine or enters a commit**. Not a
review-time check, not a habit.

**AMENDED 2026-09-07 by operator ruling, and the amendment is the whole point
of this paragraph.** As originally written this decision was scoped to a
CAPTURE and to a COMMIT, and both halves of that scope turned out to be too
narrow on the same day:

- **Scoped to a source.** The rule, the redactor and its backstop test were all
  written around the game log and its identifiers. On 2026-09-07 a session
  answered a sibling project's question by quoting the raw output of
  `git log --format='%ae %ce'` - the operator's own email address - and nothing
  in the redaction path was consulted, because the string had not come from a
  log parser. It had come from `git`. A rule scoped to one SOURCE is a rule with
  a hole in it, and this was the hole.
- **Scoped to a commit.** The bytes went into `moon_sync_inbox/`, which is
  gitignored, and then into four sibling projects' directories. Every
  commit-time guard in this tree was silent by construction, correctly, because
  nothing was being committed. The leak was caught by an unrelated
  source-provenance guard objecting that a domain was not in the citation
  register - a privacy failure found by accident, by a test that was not looking
  for one.

So the scope is now a CLASS OF DATA and a DIRECTION, not a source and not a
commit: an operator identifier, however it was produced, is redacted before it
crosses out of this machine or into git history. `LL-0170` records the incident
and `ROADMAP.md` `OPS-50` records the repair.

Concretely:

- `lanternlight.redact` is the single gate. Log excerpts, fixtures, samples,
  issue text and screenshots all pass through it before they can be committed.
- **The redactor itself is tested**, and its tests are written before the
  parsers that feed it. A parser with an untested redactor downstream is a leak
  with extra steps.
- A `.gitignore` covering raw capture locations backs it up, as defence in depth
  rather than as the control.
- Fields known to require redaction today: SteamID64, Steam persona, GSDK openID
  and userId, EOS ProductUserId, IP-derived location, `AccountName`, and the
  operator's **git identity** - the author and committer address `git` reports.
  The list is additive - a newly observed identifier is added the moment it is
  seen.
- **The list is a floor, not the definition.** It enumerates what has been
  observed; it does not scope the rule. An identifier that is not on it is still
  an operator identifier, and the 2026-09-07 leak is what that distinction costs
  when it is not written down: the address was not on the list, so nothing
  looked for it, so nothing found it.
- **The git identity is never written into a tracked file as a literal**, not
  even inside the redactor or its tests. A rule enforced by hardcoding the value
  it protects is scoped to one VALUE, which is the same defect one level down.
  It is derived at run time or matched by shape.

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
- **Answering a question by quoting a command's raw output is publishing that
  output.** This is the specific habit the 2026-09-07 leak came from: the answer
  was true, the evidence was genuine, and quoting it whole was the mistake. A
  finding can almost always be stated without the identifier in it - "exactly
  one identity across all refs, in both roles" carries the entire result and
  none of the exposure.
- The raid recon pass will produce the largest capture this project has yet
  handled, and it will contain identifiers not on the list above. Extend the
  redactor as part of that work, not afterwards.

## Status

**Accepted.** 2026-08-09. **Amended 2026-09-07** by operator ruling, widening
the scope from the game log and the commit to any operator identifier crossing
off this machine. The original decision is not reversed - everything it required
is still required - it was too narrow, and the amendment says where.
