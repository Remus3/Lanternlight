# Lanternlight backlog

**This file is aspirational.** Nothing here is planned, scheduled, promised, or
being worked on. It exists so that ideas stop occupying anyone's head, not so
that they get built.

Committed work with acceptance criteria lives in [`ROADMAP.md`](ROADMAP.md).
Nothing moves from this file to that one without an acceptance criterion
attached and a real reason to do it now.

Everything below inherits the two permanent constraints without restating them
each time: no game-process interaction of any kind
([ADR-001](docs/adr/ADR-001-no-game-process-interaction.md)), and no asset
extraction ([ADR-002](docs/adr/ADR-002-no-asset-extraction.md)). An idea that
needs either is not aspirational, it is rejected.

---

## Dashboard

A local read-only web view over whatever the log tail and save reader have
produced - current character, class, session history, extraction record, market
snapshots. Port **8810** is reserved for it. Nothing listens there and no code
exists.

Deliberately a **separate window on a second display**, never an overlay. An
overlay that hooks the game's swapchain is forbidden outright, and even a
borderless always-on-top window sitting over a kernel-anti-cheat title is a
category of thing this project does not want to be near.

Blocked in practice on there being something worth displaying, which means the
raid recon pass.

## OCR pipeline for in-game numbers

Passive capture of the operator's own display, plus OCR, to read numbers the
game shows but never writes to disk - damage numbers, cooldown sweeps, stat
panels, item tooltips.

This is the only realistic route to Emberforge having inputs at all, because
none of those values are published and none are extractable. It is also the
hardest thing on this list to make trustworthy: OCR that is 98 percent right
produces a table that is 100 percent unusable, since the wrong 2 percent is
indistinguishable from the rest.

If it is ever built, the design constraint is that every OCR-derived value
carries its provenance - source frame, timestamp, confidence - and that a value
which fails confidence is **dropped, never rounded to something plausible**
([ADR-005](docs/adr/ADR-005-omit-rather-than-guess.md)). A read that is
uncertain must be able to say so.

The class-id join in `docs/OBSERVED_IDS.md` is the ancestor of this idea, and
worth learning from: it worked precisely because the value was read as **rendered
text off a screenshot by a human**, joined to a log line on wall clock. No OCR
was involved and no guesswork was needed. Any pipeline here should aim for that
standard rather than assume it can be automated down to nothing.

## Build planner UI

The thing Emberforge would exist to serve: pick a class, pick weapons and gems,
see the resulting numbers, compare two builds. Gems replaced random gear affix
rolls, so mid-game power comes from sockets - which is a comparatively small and
combinatorially tractable space, and a good fit for a planner.

Completely blocked on Emberforge computing anything, which is blocked on there
being measured numbers, which is blocked on the measurement harness below. Three
layers deep. Do not start at this end.

## Measurement harness for the unpublished cooldown and damage numbers

As of 2026-08-09, no cooldown values, damage coefficients or stealth durations
are published anywhere trustworthy, and any site quoting one is fabricating
(`docs/CLASS_RESEARCH.md`). The attribute system semantics are unpublished at
any trustworthy tier too.

So the numbers have to be produced, not found. A harness for this would be a
repeatable protocol plus the tooling to record it: a fixed scenario, a stated
number of trials, capture running, and a written-down result including the
variance and the trial count - not a single observation promoted to a constant.

Open design questions, none of them answered:

- What is even measurable passively? A cooldown sweep is visible on screen; a
  damage coefficient is a derived quantity that needs a controlled target.
- How is a trial made repeatable in a PvPvE extraction game where the
  environment is not under the operator's control?
- What sample size makes a number publishable, and what does the repo do with a
  number measured three times when it wants thirty?

This is the deepest item on the list and the one most likely to define whether
Lanternlight becomes a real analysis project or stays a log reader. It is also
the one most likely to be superseded by the developer simply publishing the
numbers, which would be a good outcome and should not be resented.

## Steam Web API enrichment

`GetGlobalAchievementPercentagesForApp` returns 20 achievements with opaque
names (`TrophyNo_2` and so on), and `GetNewsForApp` returns patch note titles
and works keyless - usable as a patch-detection trigger, which matters because a
patch can silently invalidate every measured number in the repo.

`GetSchemaForGame` and `GetUserStatsForGame` would give real achievement names
and per-user stats, but both need a Steam Web API key and no key exists on this
machine. Registering one is a small decision nobody has made.
