# Code of Conduct

## The short version

Be decent. Argue with the work, not the person. Bring evidence.

## Scope

This applies to everything in this repository and its issues, pull requests and
discussions.

## Expected behaviour

- **Disagree about the measurement, not the messenger.** This project's whole
  method is that a claim carries its evidence. "That is wrong" is a fine thing
  to say here; say what you measured and how.
- **Assume the other person read the docs and still disagrees.** They may have
  found something.
- **Accept correction the same way you give it.** Several of this repository's
  own records exist because a claim it made about itself turned out to be false,
  and saying so plainly is the norm rather than an embarrassment.

## Unacceptable behaviour

- Harassment, insults, or personal attacks.
- Discriminatory language or imagery, or unwelcome attention of any kind.
- Publishing anyone's private information without their explicit permission.
- Sustained disruption of discussion.

## A rule specific to this project

**Do not ask for, or contribute, anything that touches the game process.**

Mistfall Hunter ships kernel-level anti-cheat. This project never injects a
plugin, loads a DLL into the game, reads its memory, captures its traffic, hooks
its rendering, or synthesises input into it. That boundary is permanent and is
not open to negotiation in an issue - see
[ADR-001](docs/adr/ADR-001-no-game-process-interaction.md).

Requests to relax it, or contributions that quietly cross it, will be closed.
The stake is somebody's account, and it may not be yours.

The same applies to asset extraction: all 15 shipped pak chunks are encrypted,
and getting at them would require exactly the access above. See
[ADR-002](docs/adr/ADR-002-no-asset-extraction.md).

## Reporting

Raise a concern by opening an issue, or - if it involves a specific person and
should not be public - through GitHub's own
[reporting tools](https://docs.github.com/en/communities/maintaining-your-safety-on-github/reporting-abuse-or-spam).

The maintainer will review what is reported and decide what to do about it,
which may include editing or deleting comments, closing a thread, or blocking an
account. This is a small project run by one person; there is no committee and no
appeals process, and pretending otherwise would be theatre.

## Attribution

This document is written for this project rather than adapted from a template.
It borrows the shape of the [Contributor Covenant](https://www.contributor-covenant.org/)
without copying its text.
