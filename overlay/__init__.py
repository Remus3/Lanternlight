"""Lanternlight overlay - a separate, non-injected, always-on-top window.

THE SAFETY BOUNDARY
===================

Mistfall Hunter ships a kernel-level anti-cheat. Everything in this package is
built to sit on the far side of that boundary, and the boundary is stated here
in the terms it has to be judged in.

This overlay IS:

- a separate top-level always-on-top window owned by our own process, exactly
  like any ordinary desktop application window
- click-through where the platform allows it, so it cannot steal focus or
  clicks from the game
- a consumer of data the game already wrote to disk, plus passive screen
  capture of the operator's own screen

This overlay NEVER:

- injects into the game, by any mechanism
- hooks DirectX, Present, the swapchain, or the game's render loop
- uses SetWindowsHookEx or any other hook against the game
- reads the game's process memory
- synthesizes keyboard or mouse input into the game

If a feature appears to need any of those, the feature is rejected and the
limitation is written down instead. See ``docs/OVERLAY.md`` for the full
argument and for the recorded, operator-accepted residual risk, and
``docs/adr/ADR-001-no-game-process-interaction.md`` for the governing rule.

Layout
------

- :mod:`overlay.anchors` - pure placement geometry and the HUD safe zones.
  No tkinter, no ctypes, no I/O.
- :mod:`overlay.render`  - pure payload-to-lines model. No tkinter.
- :mod:`overlay.window`  - the thin tkinter shell. The only module here that
  knows a display exists.

This ``__init__`` deliberately imports NONE of them. Importing
:mod:`overlay.anchors` runs this file first, so an import of the tk shell here
would drag tkinter into every headless test that only wanted the geometry.
``tests/test_overlay_anchors.py`` asserts exactly that, in a fresh
interpreter. Import the submodule you want, explicitly.

Everything authored here is 7-bit ASCII. No em-dashes, no en-dashes, no smart
quotes. Use " - " for a clause break.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
