"""Lanternlight - a companion and analysis toolkit for Mistfall Hunter.

Lanternlight reads what the game already writes to disk (its Unreal Engine 5
log, its saved-game tree, its config ini files) and turns that into typed,
inspectable events. It does not inject, hook, patch or otherwise touch the
running game.

Two hard rules govern this package:

1. Everything authored here is 7-bit ASCII. No em-dashes, no en-dashes, no
   smart quotes. Use " - " for a clause break.
2. Nothing derived from a real log ever lands in the repository without going
   through :mod:`lanternlight.redact` first. The game log carries the
   operator's SteamID64, Steam persona name, platform account ids and an
   IP-resolved location. This is a public repository.

Submodules:

- :mod:`lanternlight.paths`    - pure path resolution for the game's Saved tree
- :mod:`lanternlight.logparse` - line and event parsing for MistfallHunter.log
- :mod:`lanternlight.redact`   - the scrubber that makes a log shareable

The math engine lives in the separate :mod:`emberforge` package.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
