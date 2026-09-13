# Which slice kinds need the strongest model, and which do not

`OPS-87` criterion 5. `CLAUDE.md` says to pick the model per slice and says
nothing about how, so a cold session picks uniformly and either overpays for a
mechanical sweep or underpays for the pass that decides whether the work is
right. This document is read AT DISPATCH TIME. It is short on purpose.

Everything below is grounded in a measurement recorded in
[`REFUTATION_CENSUS.md`](REFUTATION_CENSUS.md) or in the session that wrote it.
Where it is an opinion, it says so.

## The one rule that is not negotiable

**The grader never gets a weaker model than the producer.** An adjudicator that
is cheaper than the agent it grades is a rubber stamp with a second invoice.

This is not a preference. Measured 2026-09-12: five extraction slices at the
middle tier produced 135 classified events; three adjudicators at the strongest
tier moved 12 of them, and the moves changed the answer to the question the
whole item was asked - the largest bucket went from "a stale recital in a
document" to "a real defect in the deliverable". Every move but one ran the same
direction, from a cheap bucket to the expensive one. Cheap graders would have
reported the cheap answer.

## The tiers

**STRONGEST MODEL. Do not economise here.**

* **Adjudication and refutation.** Any pass whose job is to decide between two
  outputs, or to break a done-claim. See above - this is the measured case.
* **Anything touching the hard boundary.** The rule against interacting with the
  game process ([ADR-001](adr/ADR-001-no-game-process-interaction.md)) and
  anything that could carry an operator identifier off this machine
  ([ADR-004](adr/ADR-004-redaction-is-mandatory.md)). The cost of one mistake is
  a permanent ban on a real account, or a published identifier that cannot be
  unpublished. This is a judgement about consequence, not a measurement.
* **Subtle logic where the failure is silent.** A guard that can be vacuous, a
  check whose green means nothing, an atomic-write path, a lock protocol. The
  census's 12 harness-artifact and over-report events all live here, and each
  one looked like a result until somebody re-derived it.

**MIDDLE MODEL. The default for producing work.**

* **Extraction and classification over a long corpus.** Five slices read 960
  lines of ledger and produced anchored, verbatim-quoted rows with a 8.9 per
  cent adjudicated error rate. That is a real error rate and it is bounded, and
  the adjudicator above is what makes it acceptable.
* **Implementing against a written test.** The test is the specification and it
  either passes or it does not.
* **Documentation written from evidence already gathered.**

**WEAKEST MODEL THAT CAN DRIVE THE TOOLS RELIABLY.**

* **Mechanical sweeps.** Listing files, running a command and reporting its
  output, counting occurrences, applying a rename.
* **Broad web research** where the finding will be re-measured here anyway.

## Run the pre-flight BEFORE you spend an adversary

Measured on this machine, 2026-09-12:

| What | Cost | When |
|---|---|---|
| `python -m ops.preflight` | 17.8 to 24.6 s, 14 guard modules | a slice, before it claims done |
| `python -m pytest` | 396.2 s | before a commit, always |
| an adversarial slice | minutes of wall clock, plus its own fix cycle | after the pre-flight is green |

Dispatching an adversarial pass to discover that a new test module has no row in
`docs/INVENTORY.md` costs the adversarial rate for a twenty-second answer.
That happened in the session that filed `OPS-87`, and it happened AGAIN in the
session that built the pre-flight, before the pre-flight existed to catch it.

**And read what the pre-flight says it does not cover.** 93 of 135 events in the
census were judged unreachable by any program, and 60 of 135 were real defects
in the deliverable. The pre-flight moves the cheap classes off the expensive
path. It does not shorten the expensive path, and a session that treats a green
pre-flight as permission to skip an adversarial pass has made the cycle worse,
not better.

## What this document is not

It is not a claim that the tiers above are optimal. They are the tiers this
project's own measured failures justify, on one machine, over one five-day
window. A slice kind that is not listed here has not been measured, and the
honest default for an unmeasured slice is the middle model plus a grader above
it.
