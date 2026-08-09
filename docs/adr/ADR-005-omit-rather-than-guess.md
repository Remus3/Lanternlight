# ADR-005: Omit rather than guess

## Context

Because there is no extractable data ([ADR-002](ADR-002-no-asset-extraction.md))
and no process access ([ADR-001](ADR-001-no-game-process-interaction.md)), every
number in this project has to be observed. That makes the dataset small, slow to
grow, and permanently incomplete - and it creates constant pressure to fill a gap
with something plausible.

Two measured facts make that pressure dangerous rather than merely untidy:

- **No cooldown values, damage coefficients or stealth durations are published
  anywhere as of 2026-08-09.** Any site quoting a second value is fabricating one
  ([`../CLASS_RESEARCH.md`](../CLASS_RESEARCH.md)). So the obvious fallback -
  look it up - is actively poisonous here.
- **The launch-window wiki farms cross-copy each other verbatim**, so agreement
  among ten of them is one source, not ten. One invented an "SS tier" no other
  list uses; another invented an August 5 Blackarrow nerf that does not exist.

A guessed number is worse than a missing one in a specific, asymmetric way. A
missing field is visibly missing and can be filled later at the cost of one
measurement. A wrong number is invisible, propagates into every derived quantity,
and is only discovered when something downstream is inexplicably off - at which
point the cost is not one measurement but an audit of everything that touched it.

## Decision

When a value is not known, **omit the field**. Do not default it, do not
interpolate it, do not infer it from a sibling, and do not import it from a wiki.

Corollaries:

- **"Unmeasured" stays distinguishable from "measured zero".** These are
  different facts and must not collapse into the same representation.
- **Every value records how it was established.** `OBSERVED_IDS.md` is the
  reference implementation: each row names its method, and the one row derived by
  elimination rather than direct observation says so explicitly.
- A failed probe is written down as a failed probe. The weapon-stance toggle
  probe produced no distinguishable event, and that is recorded as such rather
  than being quietly dropped or reported as a negative result.
- Community data may be consulted but is marked unverified third-party and is
  never promoted into a first-party table.
- An open question stays open in writing. Sorcerer shows a single weapon config
  id that the official statement does not explain, so **nothing in this repo may
  claim Blackarrow is the only single-weapon class** until that is settled - even
  though it is the natural-sounding sentence.

## Consequences

- The project ships slowly and starts mostly empty. Accepted deliberately.
- Emberforge computes nothing today and will stay that way until measured inputs
  exist. That is the correct state, not a gap to be papered over with plausible
  constants.
- Consumers of this data have to handle absent fields as a normal case rather
  than an error, which is a real cost paid on purpose.
- Schemas need a representation for "not measured" that is distinct from both
  zero and null-as-default.
- Reviewers should treat a suspiciously complete table as a red flag and ask
  where each number came from.

## Status

**Accepted.** 2026-08-09.

Inherited directly from the RedMoon doctrine, and load-bearing here in a way it
was not there, because there is no extraction path to fall back on.
