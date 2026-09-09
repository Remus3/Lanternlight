# Contributing to Lanternlight

Thanks for looking. This project has a few rules that are stricter than usual,
and they exist because of measured failures rather than taste. Read the four
below before writing code; the rest is ordinary.

## Getting set up

```
git clone https://github.com/Remus3/Lanternlight.git
cd Lanternlight
python scripts/install_hooks.py
python -m pytest
```

**Run `scripts/install_hooks.py` first.** `core.hooksPath` is local git config
and is never cloned, so a fresh clone runs zero hooks until you wire them. The
tracked `.githooks/` directory does nothing on its own.

Python 3.14. No third-party runtime dependencies.

Run the suite with `python -m pytest` and no extra flags. `pytest.ini` already
carries `-q`; adding a second one makes it `-qq`, which prints dots and **no
summary line at all** while still exiting 0. Anyone "confirming N passed" that
way read a count that was never printed.

## The four rules

### 1. Never touch the game process

Mistfall Hunter ships kernel-level anti-cheat. This project never injects a
plugin or DLL, opens a handle to the game, reads its memory, captures or proxies
its traffic, hooks its swapchain or window, or synthesises input into it.

Permitted: reading files the game writes into user-writable space, passive
screen capture of the operator's own display, and a separate always-on-top
window of our own.

There is no debug flag or one-off experiment that makes any of that acceptable.
If a feature needs one, the feature is rejected, not the rule.
[ADR-001](docs/adr/ADR-001-no-game-process-interaction.md).

### 2. Every feature and every bugfix starts with a failing test

1. Write the failing test. **Watch it fail.**
2. Implement the minimum that makes it pass.
3. Run the full suite before committing.

**A green test proves nothing until you have seen it go red.** Before trusting a
new guard, break the thing it protects, confirm the test fails, restore, confirm
green - and say in the pull request what you saw. A guard that stays green when
you delete the behaviour it protects is not a test, it is decoration.

Related traps this project has already hit, all worth knowing:

- A mutation that fails to apply looks exactly like a passing test. Assert the
  anchor text matched before believing a survivor.
- A raising spy is vacuous under fail-soft code, because `AssertionError` is an
  `Exception` and a bare `except Exception` swallows it.
- A negative assertion rules something out without pinning anything down.

### 3. Omit rather than guess

Nobody has published cooldowns, damage coefficients or stealth durations for
this game, and nothing is extractable from the encrypted paks. So every number
here is measured, and:

- **A missing field is absent** - not null, not `0`, not `-1`. A missing number
  is recoverable; a confident wrong one is not.
- **Keep "unmeasured" distinguishable from "measured zero".** They are different
  facts, and conflating them is how a build engine starts lying.
- Every id-to-name binding is recorded in
  [`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) with the observation method
  named. An id learned later from a wiki is not the same fact as an id watched
  being emitted.

[ADR-005](docs/adr/ADR-005-omit-rather-than-guess.md).

### 4. Redact before anything leaves the machine

The game's log and save files carry account identifiers. None of them crosses
off the machine or into git history - `lanternlight/redact.py` is the only
sanctioned path and `tests/test_no_pii.py` is the backstop.

**Never paste a raw log excerpt into an issue, a pull request, or a test
fixture.** If you need to show a shape, sanitise it first. The known identifiers
are a floor, not a definition: anything that identifies an operator counts,
however it was produced. [ADR-004](docs/adr/ADR-004-redaction-is-mandatory.md).

## House style

- **7-bit ASCII only, everywhere** - code, comments, docstrings, Markdown,
  commit messages. No em-dashes, no en-dashes, no smart quotes. Use ` - ` for a
  clause break. Enforced by `tests/test_ascii_hygiene.py` and by
  `.githooks/pre-commit`.
- **Atomic writes** for anything a reader might poll:
  `tmp.write_text(...); tmp.replace(target)`.
- Match the surrounding code's naming, comment density and idiom.
- Say what a thing is for and what it is blind to. A caveat you mentioned in
  passing but left out of the file is a lie in the file.

## Pull requests

Fill in the template. The parts that matter most are what you measured and what
you watched go red - a PR that says "added tests" without either is hard to
review and will get those questions back.

Small and focused beats large and sweeping. If you found a second problem while
fixing the first, say so in the PR rather than folding it in silently; it may
deserve its own issue.

## Decisions already made

Check [`docs/adr/README.md`](docs/adr/README.md) before re-opening a settled
question. [`ROADMAP.md`](ROADMAP.md) carries the open items with their
acceptance criteria, and its closed ones are in
[`docs/ROADMAP_ARCHIVE.md`](docs/ROADMAP_ARCHIVE.md) - nothing was deleted, so
an empty search of one file is not a claim about the project.

## Licence

Contributions are accepted under the [Apache License 2.0](LICENSE), the same
licence as the project. By opening a pull request you confirm you have the right
to contribute the code under it.

Do not paste in code from a GPL or AGPL project - vendoring it would relicense
this one. Techniques and protocol facts are not copyrightable; source is.
Re-implementing from observed behaviour is always fine.
