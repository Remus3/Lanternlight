"""Emberforge - the Mistfall Hunter math engine. It computes nothing yet.

This package is an honest placeholder. There is no damage formula here, no
stat model, no build scorer, no simulation. Nothing in Emberforge has been
derived from measured game data yet, so nothing in Emberforge returns a
number.

That is deliberate. A stubbed ``compute_damage()`` that returns a plausible
looking float is worse than an empty package: downstream code starts trusting
it, tests get written against the fiction, and the fiction outlives the memory
of it being fiction. An empty honest package beats a lying one.

What has to exist before a formula is added here:

1. Measured, first-party observations of the quantity being modelled - not a
   value copied from a wiki, a spreadsheet or another tool.
2. A written note of how the observation was taken, so it can be re-taken when
   the game patches.
3. A test that fails if the formula drifts from the observation.

Until then the only thing this package exports is its version, so that
consumers can pin against it and so that a future engine change has a number
to bump.
"""

ENGINE_VERSION = "0.0.1"

__all__ = ["ENGINE_VERSION"]
