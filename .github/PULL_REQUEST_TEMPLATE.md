<!--
Thanks for contributing. CONTRIBUTING.md has the four rules; this template just
asks you to show your working. Delete any section that genuinely does not apply,
and say why rather than leaving it blank.
-->

## What this changes

<!-- One or two sentences. What is different afterwards? -->

## Why

<!-- The problem, not the solution. If it closes an issue or a ROADMAP item,
     name it: "Closes #12", "ROADMAP OPS-42". -->

## What you measured

<!-- Numbers, not adjectives. Where a value came from, and how you got it.
     "Omit rather than guess" applies to PR descriptions too: if you did not
     measure something, say so instead of estimating it. -->

## The test you watched FAIL

<!-- Required for any feature or bugfix. Paste the red output, or describe the
     failure you saw before the fix existed.

     If you added a guard, break the thing it protects, confirm it goes red,
     restore, confirm green - and say what you saw. A guard that stays green
     when you delete the behaviour it protects is decoration, and this is the
     one part of a review that cannot be reconstructed later. -->

## Suite result

<!-- Paste the LAST LINE of a bare `python -m pytest` run.

     Not `-q`: pytest.ini already carries it, so a second one prints dots and no
     summary line at all while still exiting 0. -->

```
```

## Checklist

- [ ] The full suite passes, and the line above is from this run rather than an
      earlier one.
- [ ] **Nothing here touches the game process** - no injection, no memory read,
      no traffic capture, no rendering hook, no synthetic input. ADR-001.
- [ ] **No raw log or save excerpt** is included, in the diff, the tests, or this
      description. No operator identifier of any kind. ADR-004.
- [ ] Every number added is measured, with its source recorded. Anything
      unmeasured is OMITTED rather than defaulted to `0`, `-1` or null. ADR-005.
- [ ] 7-bit ASCII everywhere, including this description. No em-dashes, no smart
      quotes.
- [ ] Docs updated if behaviour changed - and any caveat mentioned in review is
      written into the file, not just the thread.

## Anything you are unsure about

<!-- Genuinely useful. Say what you could not verify, what you guessed at, or
     what you think might be wrong. It is treated as information here, not as a
     weakness in the PR. -->
