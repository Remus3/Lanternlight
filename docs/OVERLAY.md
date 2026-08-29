# The Lanternlight overlay

Design notes for the `overlay` package. Written 2026-08-09, when the package
was first scaffolded.

---

## 1. The safety boundary

**This comes first because it determines everything else in the design.**

Mistfall Hunter ships a kernel-level anti-cheat. The overlay is therefore built
as the most boring thing that can possibly work:

- a **separate top-level always-on-top window** owned by our own process,
  exactly like any ordinary desktop application window
- **never** injected into the game
- **never** hooking DirectX, Present, the swapchain, or the game's render loop
- **never** using `SetWindowsHookEx`, or any other hook, against the game
- **never** reading the game's process memory
- **never** synthesizing keyboard or mouse input into the game
- **click-through where possible**, so it cannot steal focus or clicks from the
  game

The same paragraph is in the module docstring of `overlay/__init__.py` and again
in `overlay/window.py`, in those terms. It is repeated on purpose. A rule that
lives only in a document is a rule that a future change will not be read
against.

### What this overlay will never do

Not a list of things we have not got round to. A list of things that are
rejected on sight, and that no benchmark, deadline, or "just for testing" flag
makes acceptable:

| Never | Why |
|---|---|
| Inject a DLL, plugin, or script into the game process | Textbook anti-cheat trigger, and outside the EULA |
| Hook DirectX / Present / the swapchain to draw in-game | The defining technique of a "cheat overlay". Not a grey area |
| `SetWindowsHookEx`, `SetWinEventHook`, or any hook targeting the game | Cross-process hooking is indistinguishable from the real thing |
| Read or write the game's process memory | Same |
| Open a handle to the game process at all | Same |
| Enumerate, subclass, reparent, or resize the game's window | Touching another process's window is not window management, it is interference |
| Synthesize keyboard or mouse input into the game | Automation of play. Ban-worthy on its own merits |
| Capture or proxy the game's network traffic | Out of scope permanently, see ADR-001 |
| Show a number the engine did not compute | Different kind of harm, same rule. See section 6 |

If a feature appears to need any of these, **the feature is rejected and the
limitation is written down** - here, in this section, rather than worked around.

### The one Windows API call

`OverlayWindow.apply_click_through` calls `GetWindowLongW` / `SetWindowLongW` to
set `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` on
a window handle. That handle comes from our own tk widget, via
`winfo_id()`. It is our window, created by our process, in this process's
address space.

This is ordinary window styling - the same call every transparent desktop widget
on Windows makes - and it is a different act from hooking. It never names,
finds, enumerates, or touches the game's window. If a change to that method ever
makes that untrue, the change is wrong.

The call is best-effort and never fatal: on a non-Windows platform, or if the
call fails, it returns `False` and the window simply stays clickable. A
click-through failure is a nuisance; an overlay that crashes at startup is a
broken tool.

---

## 2. The open question, and the risk we accepted

**Is an always-on-top window acceptable to the anti-cheat?**

We do not know for certain, and we are not going to pretend otherwise.

What we can say precisely:

- A separate, non-injected, top-level window is **an ordinary Windows window**.
  Discord, Steam's own non-overlay windows, OBS, a Notepad instance and a clock
  widget are all the same category of object. Nothing about it reaches into the
  game.
- That is **a different category from a hooked overlay**. A swapchain hook
  writes into the game's render path from inside the game's process. This window
  does not exist in the game's world at all; the compositor puts it in front,
  and the game is not consulted or affected.
- We therefore judge **the risk low**.
- **The risk is not provably zero.** An anti-cheat is a closed system, and a
  heuristic that flags topmost windows over a fullscreen game is a thing that
  can exist even if we believe it does not here. We cannot test our way to
  certainty without risking the account we would be testing with.

**The operator accepted this risk knowingly on 2026-08-09.** That is the record.
It is an accepted risk, not a proven safety property, and it should be re-read
as such rather than remembered as "we checked and it is fine".

Mitigations already in the design, none of which make the risk zero:

- The window never takes focus (`WS_EX_NOACTIVATE`) and is click-through, so it
  cannot interact with the game even accidentally.
- It stays out of the taskbar and the alt-tab list (`WS_EX_TOOLWINDOW`).
- It is trivially disabled: do not launch it. Nothing else in Lanternlight
  imports it, and `LH_OVERLAY_NO_WINDOW=1` makes `build()` refuse outright.

### A wording conflict with ADR-001, flagged not resolved

[ADR-001](adr/ADR-001-no-game-process-interaction.md) forbids "no overlay that
hooks the game's swapchain or window" - which this design obeys exactly - but
its Consequences section then says "No in-game surface of any kind. Any UI this
project grows is a separate window, ideally on a second display, and never an
overlay."

Read strictly, this package satisfies the **decision** and contradicts one
sentence of the **consequence**. The two readings differ on what the word
"overlay" means: the decision uses it to mean a hooked, in-process surface, and
the consequence uses it to mean any window drawn over the game.

This document does not get to settle that - an ADR is amended by its own
process, and `docs/adr/` is out of scope for the slice that wrote this file. It
is recorded here so the next person hits it deliberately instead of accidentally.
**Whoever picks this up should amend ADR-001 to say which meaning it intends, or
supersede it with a new ADR.** Until then, treat ADR-001 as governing and this
package as pending that clarification.

---

## 3. Architecture

Three modules, split so that everything worth testing is testable without a
display.

```
overlay/anchors.py   pure geometry      no tkinter, no ctypes, no I/O
overlay/render.py    pure content model no tkinter
overlay/window.py    thin tk shell      the only module that knows a screen exists
```

`overlay/__init__.py` deliberately imports **none** of them. Importing
`overlay.anchors` runs the package `__init__` first, so an import of the tk
shell there would drag tkinter into every headless test that only wanted the
geometry. `tests/test_overlay_anchors.py` asserts that, in a fresh interpreter.

### Why the split is this shape

Anything that lives in widget code can only be checked by looking at pixels -
slow, subjective, and unavailable in CI. So the two questions worth getting
right are lifted out into pure functions returning comparable values:

- **Where does the panel go?** `anchors.place()` returns an `(x, y)` tuple.
- **What does it say?** `render.render()` returns a tuple of `Line(text, style,
  key)` records.

Both are ordinary values: assertable, diffable between two runs, and
screenshot-diffable later without re-deriving what the panel was supposed to
contain. What is left in `window.py` is widget construction and a repaint timer.

### Testability without a window

- `OverlayWindow(config)` imports no tkinter and creates no widget.
- Widgets appear only inside `build()`, which is the guard.
- `tkinter` is imported lazily inside `build()` and `repaint()`, so importing
  `overlay.window` on a headless box is harmless.
- There is no `mainloop()` at import time. `run()` is the only blocking call and
  it is reached only from the `__main__` guard.
- `LH_OVERLAY_NO_WINDOW=1` makes `build()` raise immediately, so a stray `run()`
  in an automated job fails loudly instead of hanging on a mainloop nobody can
  see or close.

### Ports

This project's block is **8810-8819** (`CLAUDE.md` is the authority). Named so
far: dashboard **8810**, log-tail service **8811**, vision / OCR **8812**,
Emberforge **8813**, and **8814** for an overlay control channel.

**The overlay binds none of them.** It has no socket, no server, no client. 8814
is reserved and unused; the constant `overlay.window.CONTROL_PORT` exists only so
nobody allocates the number twice. If a control channel is ever built it goes on
8814, in its own module, and it still must not bind at import time.

---

## 4. Anchors

A nine-position 3x3 grid: `top-left`, `top-center`, `top-right`, `middle-left`,
`middle-center`, `middle-right`, `bottom-left`, `bottom-center`,
`bottom-right`.

`anchor_position(screen, panel, anchor, margin)` returns the raw top-left
corner. On a 2560x1440 screen with a 320x180 panel and a 24px margin:

| anchor | x, y |
|---|---|
| top-left | 24, 24 |
| top-center | 1120, 24 |
| top-right | 2216, 24 |
| middle-left | 24, 630 |
| middle-center | 1120, 630 |
| middle-right | 2216, 630 |
| bottom-left | 24, 1236 |
| bottom-center | 1120, 1236 |
| bottom-right | 2216, 1236 |

Two rules worth stating because they are easy to get wrong:

- **A centred panel ignores the margin.** A centred panel that respected the
  margin would not be centred.
- **Placement is clamped and never negative.** A panel bigger than the screen
  returns `0` on the offending axis, so it is clipped on the far edge and
  visibly wrong. A negative coordinate would clip the near edge too and hide the
  part of the panel that names it - the overlay would look like it never
  started.

---

## 5. Safe zones

Named rectangles of the game screen the overlay must not cover, because the game
draws critical HUD there. `place()` starts from the raw anchor position and, if
it collides, moves the panel to the nearest position that is both on screen and
clear of every zone.

> ### WARNING: the safe zones are an unverified first guess
>
> **Nobody has measured Mistfall Hunter's HUD.** `DEFAULT_SAFE_ZONES` in
> `overlay/anchors.py` is an educated guess at where an action game at 2560x1440
> puts its vitals, ability bar, minimap, reticle, buffs, objective text and
> pickup feed. It is very likely wrong in the details and it may be wrong in the
> large - the `objective_tracker` zone may correspond to nothing that exists.
>
> This is why they are exposed as **data**: a tuple of `SafeZone(name, rect,
> note)` records, each carrying a note about what its guess is a guess about.
> When somebody measures the real HUD from a screen capture, the fix is to
> correct the numbers and rewrite the notes. **No logic changes and no caller
> changes.**
>
> Do not let these numbers harden into folklore. Until a capture is measured
> they are placeholders wearing coordinates' clothes.

Current guesses, at the 2560x1440 reference:

| zone | rect (x, y, w, h) | guessing what |
|---|---|---|
| `reticle` | 1180, 660, 200, 120 | dead-centre aim point |
| `player_vitals` | 0, 1180, 620, 260 | bottom-left health and stamina |
| `ability_bar` | 960, 1240, 640, 200 | bottom-centre ability slots |
| `minimap` | 2140, 0, 420, 420 | top-right minimap or compass |
| `status_effects` | 0, 0, 560, 180 | top-left buff and debuff row |
| `objective_tracker` | 2020, 520, 540, 400 | right-hand objective text |
| `loot_feed` | 1960, 1120, 600, 320 | bottom-right pickup and damage feed |

### How avoidance works

"Nearest" is Manhattan distance from the raw anchor position, so the panel stays
as close to what the operator asked for as the HUD allows. The candidate set is
finite and small: for each axis, the raw coordinate plus, for every zone, the
coordinate that puts the panel immediately before or immediately after that
zone. Any minimal escape from a set of axis-aligned rectangles is flush against
one of their edges, so a solution that exists is in that set - roughly
`(2n+1)^2` candidates for `n` zones, or 225 for the seven above. Ties break on a
fixed key, so the same inputs always give the same pixel.

**When nothing is clear** - a panel too large to fit anywhere, or zones that
between them cover the screen - `place()` returns the raw anchor position. That
is deliberate: a panel over the HUD is bad, a panel that does not render is
worse, and a caller who cares can detect it with `overlapping_zones()`.

### Other resolutions

`safe_zones_for(screen)` scales the reference zones proportionally. That is a
guess layered on a guess - real HUDs anchor to edges and scale non-uniformly -
and it exists so a non-reference resolution degrades to "roughly right" instead
of "silently unprotected". The operator runs a single 2560x1440 display, so the
reference path is the one that matters today.

---

## 6. The render model, and the no-reflow rule

`render(payload)` turns a small structured payload into the exact lines the
panel draws:

1. the title
2. the status sentence, styled by severity (`ok` / `waiting` / `error`)
3. one line per row, in payload order
4. the note line

### The contract

> `render(payload)` always returns `3 + len(payload.rows)` lines, for every
> payload, whatever is missing from it.

This is the dominant constraint, not a nicety. **The panel is read at a glance
mid-combat.** If a row disappears when its value goes missing, every row below it
moves, and the operator's next glance lands on the wrong number - worse than
showing nothing, because it is confidently wrong.

So:

- a missing value renders as `--`, in place, styled `row-missing`
- both `None` and a blank or whitespace-only string count as missing
- the note line is present even when there is no note, because a last line that
  comes and goes makes the panel's own outline twitch
- long values are **truncated** with a trailing `...`, never wrapped - wrapping
  changes the line count, which is the one thing the contract forbids
- `line_count(payload)` computes the height from the payload's **shape** without
  rendering, so a caller can size the window before any widget exists

`tests/test_overlay_render.py` enforces this by comparing a populated payload
against the same payload with values removed and asserting the line count, the
keys and the ordering are all identical - not merely that the count equals some
constant, which would still pass if the renderer dropped one line and gained
another.

### Nothing is fabricated

Emberforge deliberately computes nothing, and no cooldown or damage numbers are
published for this game. **The panel's first job is to display measured facts and
status, not coaching.** A number the operator cannot distinguish from a measured
one is worse than a dash - see
[ADR-005](adr/ADR-005-omit-rather-than-guess.md).

---

## 7. Running it

```
python -m overlay.window
```

That opens the panel with its default payload, which is the honest one: a status
line saying no data source is attached, and dashed rows where readings will go.
There is nothing to configure yet because there is nothing wired to it yet.

To place it somewhere else, construct it directly:

```python
from overlay.anchors import BOTTOM_LEFT
from overlay.window import OverlayConfig, OverlayWindow

OverlayWindow(OverlayConfig(anchor=BOTTOM_LEFT, margin=32)).run()
```

To attach data, pass a callable returning a `render.Payload`:

```python
OverlayWindow(payload_provider=my_provider).run()
```

To stop it opening a window at all - CI, headless automation:

```
set LH_OVERLAY_NO_WINDOW=1
```

`build()` then raises immediately rather than hanging on a mainloop.

Tests:

```
python -m pytest tests/test_overlay_anchors.py tests/test_overlay_render.py
python -m ruff check overlay tests
```

Both run headlessly. Neither needs a display, and both assert that
`overlay.anchors` and `overlay.render` pull in no tkinter, in a fresh
interpreter.

---

## 8. Degrading when the game is not running

The overlay is **not** gated on the game. It runs as its own window, and the
game's absence is a state it displays rather than a reason to exit.

| situation | what the panel shows |
|---|---|
| Game not running, or log not found | status `waiting`, the reason, all rows `--` |
| Log present but stale or silent | status `waiting`, all rows `--` |
| Data source raised an exception | status `error`, `data source failed: <ExceptionType>`, same layout |
| Data flowing | status `ok`, rows filled |

`OverlayWindow.current_payload()` wraps the provider in a catch-all on purpose.
A log file that vanished mid-session, or a parse that hit an unexpected line,
must not take the panel down. The operator gets an error status in the same
layout - more useful, and more honest, than a window that disappeared.

**Every one of those states has the same line count.** That is the no-reflow rule
doing its job at the whole-panel level: the panel's outline is a function of how
many rows it was configured with, never of whether the game is running.

`render.waiting_payload(reason)` is the factory for the degraded case. It fills
every row as missing rather than inventing plausible placeholders.

---

## 9. Not built yet

Honest inventory, so nobody reads intent as implementation:

- **No data source.** Nothing connects `lanternlight.logparse` to the panel yet.
  The default provider returns "no data source attached".
- **No control channel.** 8814 is reserved and unbound.
- **No hotkey, no settings UI, no persistence.** Configuration is a
  constructor argument.
- **No measured safe zones.** Section 5.
- **No screenshot-diff harness.** The render model is the seam that will make
  one cheap; it does not exist.
- **No multi-monitor handling.** The operator has one display. `build()` reads
  the primary screen size from tk and places against that.
