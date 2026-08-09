"""The thin tkinter shell for the Lanternlight overlay.

THE SAFETY BOUNDARY
===================

Mistfall Hunter ships a kernel-level anti-cheat. This module is written to sit
on the far side of that boundary, and the boundary is restated here rather
than left to the package docstring, because this is the one file in the
project where somebody might be tempted to cross it.

What this window IS:

- a separate top-level always-on-top window owned by our own process, exactly
  like any ordinary desktop application window
- click-through where the platform allows it, so it cannot steal focus or
  clicks from the game
- painted only with data the game already wrote to disk, plus passive capture
  of the operator's own screen

What this window NEVER does:

- inject into the game, by any mechanism
- hook DirectX, Present, the swapchain, or the game's render loop
- call SetWindowsHookEx, or any other hook, against the game
- read the game's process memory
- synthesize keyboard or mouse input into the game
- enumerate, subclass, reparent, or otherwise touch the game's window

The one Windows API call in this file, :meth:`OverlayWindow.apply_click_through`,
sets extended window styles on OUR OWN window handle, obtained from our own tk
widget. It never names, finds, or touches the game's window. Setting a style on
a window your own process created is ordinary window management and is the same
call any transparent desktop widget makes. If that distinction ever stops being
true of a change to this file, the change is wrong.

If a feature seems to require anything on the "never" list, it is rejected and
the limitation is written down in ``docs/OVERLAY.md`` instead.

Structure
=========

Everything interesting is pure and lives elsewhere:

- placement geometry in :mod:`overlay.anchors`
- panel content in :mod:`overlay.render`

What is left here is widget construction and a repaint timer. The class is
constructible without a display: ``OverlayWindow(config)`` imports no tkinter
and creates no widget. Widgets appear only inside :meth:`OverlayWindow.build`,
which is the guard - tests exercise the config, the placement and the style
table without ever calling it. There is no ``mainloop`` at import time, and
tkinter itself is imported lazily inside :meth:`build` so that importing this
module on a headless box is harmless.

Ports
=====

The project's reserved local ports are dashboard 8810, log-tail 8811 and
Emberforge 8813, and 8814 is reserved for an overlay control channel. This
module binds NONE of them. It has no socket, no server and no client. If a
control channel is ever needed it goes on 8814 and in its own module, and it
still must not bind at import time.
"""

import contextlib
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from overlay import anchors, render

#: Environment kill switch. When set to a non-empty value, :meth:`build`
#: refuses to create a window. This is a safety net for CI and for headless
#: automation: a stray ``run()`` in a test job fails loudly instead of hanging
#: forever on a mainloop nobody can see or close.
ENV_NO_WINDOW = "LH_OVERLAY_NO_WINDOW"

#: Reserved for a future overlay control channel. Documented so nobody
#: allocates it twice. Nothing in this module binds it - see the docstring.
CONTROL_PORT = 8814

#: Windows extended-window-style constants, applied to our own window only.
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080


@dataclass(frozen=True, slots=True)
class OverlayConfig:
    """Everything the shell needs, as one immutable value.

    Panel size is two ints rather than an :class:`overlay.anchors.Size` so the
    dataclass has no constructed default, and :attr:`panel` rebuilds the value
    object on demand.

    Colours are deliberately high-contrast against an ARBITRARY background.
    The overlay floats over whatever the game is drawing - a snow field, a
    torchlit cave, a white loading screen - so a mid-grey on mid-grey scheme
    that looks tasteful on a mockup is unreadable in play. Hence a near-opaque
    dark plate under bright text, rather than text alone on transparency.
    """

    anchor: str = anchors.TOP_LEFT
    margin: int = anchors.DEFAULT_MARGIN
    panel_width: int = 380
    panel_height: int = 240
    #: Screen size. ``None`` means "ask tk at build time".
    screen_width: int | None = None
    screen_height: int | None = None
    avoid_safe_zones: bool = True

    #: Whole-window opacity. Not zero-alpha: a panel you cannot see is a panel
    #: that is silently broken.
    alpha: float = 0.88
    background: str = "#0b0d10"
    click_through: bool = True
    topmost: bool = True

    #: Repaint period. 500 ms is a glance-rate panel, not an animation.
    refresh_ms: int = 500

    font_family: str = "Consolas"
    #: Base size. Read at a glance mid-combat from normal desk distance on a
    #: 2560x1440 display, so this is larger than a desktop-app default.
    font_size: int = 15
    padding: int = 12
    line_spacing: int = 6

    #: Foreground colour per render style name.
    colors: dict[str, str] = field(
        default_factory=lambda: {
            render.STYLE_TITLE: "#f2f5f7",
            render.STYLE_STATUS_OK: "#7ddc8a",
            render.STYLE_STATUS_WAITING: "#f0c674",
            render.STYLE_STATUS_ERROR: "#ff8a7a",
            render.STYLE_ROW: "#e6e9ec",
            render.STYLE_ROW_MISSING: "#8b939c",
            render.STYLE_NOTE: "#8b939c",
        }
    )

    @property
    def panel(self) -> anchors.Size:
        """Panel size as a value object."""
        return anchors.Size(self.panel_width, self.panel_height)

    @property
    def screen(self) -> anchors.Size | None:
        """Configured screen size, or ``None`` to resolve it at build time."""
        if self.screen_width is None or self.screen_height is None:
            return None
        return anchors.Size(self.screen_width, self.screen_height)


# ---------------------------------------------------------------------------
# pure helpers - no tkinter, no display, no side effects
# ---------------------------------------------------------------------------


def geometry_string(x: int, y: int, panel: anchors.Size) -> str:
    """Format a tk geometry string, ``WxH+X+Y``.

    Pure string arithmetic, kept out of :meth:`OverlayWindow.build` so the
    exact value handed to tk can be asserted without a display.
    """
    return f"{panel.width}x{panel.height}+{x}+{y}"


def resolve_placement(config: OverlayConfig, screen: anchors.Size) -> tuple[int, int]:
    """Top-left corner for ``config`` on ``screen``.

    Honours ``avoid_safe_zones``. The zones are scaled to the actual screen
    when it is not the 2560x1440 reference - see
    :func:`overlay.anchors.safe_zones_for`, and note that the zones themselves
    are an unverified first guess.
    """
    if not config.avoid_safe_zones:
        return anchors.anchor_position(screen, config.panel, config.anchor, config.margin)
    zones = anchors.safe_zones_for(screen)
    return anchors.place(screen, config.panel, config.anchor, config.margin, zones)


def font_for(config: OverlayConfig, style: str) -> tuple[str, int, str]:
    """Tk font tuple for a render style: ``(family, size, weight)``.

    Size and weight carry the hierarchy, because colour alone cannot: the
    panel sits over an arbitrary background and any single colour can be
    camouflaged by the frame behind it.
    """
    if style == render.STYLE_TITLE:
        return (config.font_family, config.font_size + 1, "bold")
    if style in (
        render.STYLE_STATUS_OK,
        render.STYLE_STATUS_WAITING,
        render.STYLE_STATUS_ERROR,
    ):
        return (config.font_family, config.font_size, "bold")
    if style == render.STYLE_NOTE:
        return (config.font_family, config.font_size - 2, "normal")
    return (config.font_family, config.font_size, "normal")


def color_for(config: OverlayConfig, style: str) -> str:
    """Foreground colour for a render style, falling back to the row colour."""
    return config.colors.get(style, config.colors[render.STYLE_ROW])


def estimated_panel_height(config: OverlayConfig, line_count: int) -> int:
    """Height in pixels needed for ``line_count`` lines under ``config``.

    An estimate, not a measurement - real text metrics need a live tk font
    object. It exists so a caller can size the panel from
    :func:`overlay.render.line_count` before any window is created, which
    keeps window height a function of the payload SHAPE and never of the
    payload's contents. See the no-reflow contract in :mod:`overlay.render`.
    """
    if line_count <= 0:
        return 2 * config.padding
    # Rough vertical advance for a monospaced face at this point size.
    line_height = int(config.font_size * 1.6) + config.line_spacing
    return 2 * config.padding + line_count * line_height


# ---------------------------------------------------------------------------
# the shell
# ---------------------------------------------------------------------------

PayloadProvider = Callable[[], render.Payload]


def _default_provider() -> render.Payload:
    """The honest default: nothing is wired up yet, and the panel says so."""
    return render.waiting_payload("no data source attached")


class OverlayWindow:
    """A borderless, always-on-top, click-through panel.

    Constructing this object opens nothing, imports no tkinter and needs no
    display. Widgets exist only after :meth:`build`. That split is what makes
    the config, the placement and the style table testable headlessly, and it
    is also why there is no work in ``__init__`` worth hiding.
    """

    def __init__(
        self,
        config: OverlayConfig | None = None,
        payload_provider: PayloadProvider | None = None,
    ) -> None:
        self.config = config or OverlayConfig()
        self.payload_provider = payload_provider or _default_provider
        self._root = None
        self._frame = None
        self._labels: list = []
        self._timer = None
        self._last_lines: tuple[render.Line, ...] = ()

    # -- state ------------------------------------------------------------

    @property
    def is_built(self) -> bool:
        """True once :meth:`build` has created the widgets."""
        return self._root is not None

    @property
    def last_lines(self) -> tuple[render.Line, ...]:
        """The lines most recently painted. Empty before the first repaint."""
        return self._last_lines

    def current_payload(self) -> render.Payload:
        """Ask the provider for a payload, degrading rather than raising.

        A provider that throws - a log file that vanished, a parse that hit an
        unexpected line - must not take the panel down with it. The operator
        gets an error status in the same layout instead, which is both more
        useful and more honest than a window that disappeared.
        """
        try:
            return self.payload_provider()
        # Deliberate catch-all: see the docstring above. A provider fault must
        # degrade the panel, not remove it.
        except Exception as exc:
            return render.Payload(
                title="Lanternlight",
                status_text=f"data source failed: {type(exc).__name__}",
                status=render.STATUS_ERROR,
                rows=(),
                note="see the log for the traceback",
            )

    def placement(self, screen: anchors.Size) -> tuple[int, int]:
        """Where this window would sit on ``screen``. Pure, no widgets."""
        return resolve_placement(self.config, screen)

    def geometry_for(self, screen: anchors.Size) -> str:
        """The tk geometry string this window would use. Pure, no widgets."""
        x, y = self.placement(screen)
        return geometry_string(x, y, self.config.panel)

    # -- construction -----------------------------------------------------

    def build(self):
        """Create the window and its labels. The one place widgets appear.

        Imports tkinter lazily, so importing this module costs nothing on a
        headless machine. Refuses to run when :data:`ENV_NO_WINDOW` is set, so
        an accidental call in CI fails immediately instead of hanging.
        """
        if os.environ.get(ENV_NO_WINDOW):
            raise RuntimeError(
                f"{ENV_NO_WINDOW} is set; refusing to create an overlay window. "
                "Unset it to run the overlay for real."
            )
        if self._root is not None:
            raise RuntimeError("overlay window is already built")

        import tkinter as tk

        root = tk.Tk()
        root.title("Lanternlight overlay")
        root.configure(background=self.config.background)
        # Borderless: no titlebar, no resize grips, nothing to click.
        root.overrideredirect(True)
        if self.config.topmost:
            root.attributes("-topmost", True)
        root.attributes("-alpha", self.config.alpha)

        screen = self.config.screen or anchors.Size(
            int(root.winfo_screenwidth()), int(root.winfo_screenheight())
        )
        root.geometry(self.geometry_for(screen))

        frame = tk.Frame(
            root,
            background=self.config.background,
            padx=self.config.padding,
            pady=self.config.padding,
        )
        frame.pack(fill="both", expand=True)

        self._root = root
        self._frame = frame
        self._labels = []
        if self.config.click_through:
            self.apply_click_through()
        return root

    def apply_click_through(self) -> bool:
        """Make our own window ignore the mouse. Best effort, never fatal.

        Sets ``WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE |
        WS_EX_TOOLWINDOW`` on the handle of the window THIS PROCESS created.
        Clicks pass through to whatever is underneath, the window never takes
        focus, and it stays out of the taskbar and the alt-tab list.

        Read the safety note at the top of this module before changing
        anything here. This call names our own handle and nothing else; it is
        not a hook, and it does not touch the game's window.

        Returns True when the style was applied. Windows-only; on any other
        platform, or if the call fails, it returns False and the window simply
        remains clickable. A non-click-through overlay is a nuisance; a crash
        at startup is a broken tool.
        """
        if self._root is None:
            raise RuntimeError("build() the window before applying click-through")
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            self._root.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = int(self._root.winfo_id())
            # tk's widget handle is a child; the styles belong on the
            # top-level frame that owns it.
            parent = int(user32.GetParent(hwnd))
            target = parent or hwnd
            current = int(user32.GetWindowLongW(target, _GWL_EXSTYLE))
            user32.SetWindowLongW(
                target,
                _GWL_EXSTYLE,
                current
                | _WS_EX_LAYERED
                | _WS_EX_TRANSPARENT
                | _WS_EX_NOACTIVATE
                | _WS_EX_TOOLWINDOW,
            )
        # Catch-all on purpose: click-through is cosmetic and must never be
        # able to stop the overlay from starting.
        except Exception:
            return False
        return True

    # -- painting ---------------------------------------------------------

    def repaint(self) -> tuple[render.Line, ...]:
        """Render the current payload and push it into the labels.

        Labels are created once and only their text, colour and font are
        updated afterwards. Rebuilding the widget tree on every tick would
        make the panel flicker and would throw away any state the widgets
        hold. The label count only ever changes when the payload's row COUNT
        changes, which the no-reflow contract makes rare and deliberate.
        """
        if self._root is None:
            raise RuntimeError("build() the window before repainting")

        import tkinter as tk

        lines = render.render(self.current_payload())

        while len(self._labels) < len(lines):
            label = tk.Label(
                self._frame,
                text="",
                anchor="w",
                justify="left",
                background=self.config.background,
            )
            label.pack(fill="x", pady=(0, self.config.line_spacing))
            self._labels.append(label)
        while len(self._labels) > len(lines):
            self._labels.pop().destroy()

        for label, line in zip(self._labels, lines, strict=True):
            label.configure(
                text=line.text,
                foreground=color_for(self.config, line.style),
                font=font_for(self.config, line.style),
            )

        self._last_lines = lines
        return lines

    def schedule_repaint(self) -> None:
        """Repaint now and book the next one ``refresh_ms`` from now."""
        if self._root is None:
            raise RuntimeError("build() the window before scheduling repaints")
        self.repaint()
        self._timer = self._root.after(self.config.refresh_ms, self.schedule_repaint)

    def run(self) -> None:
        """Build if needed, start the repaint loop, and enter the mainloop.

        The only blocking call in this package, and it is never reached by an
        import - see the ``__main__`` guard at the bottom of this file.
        """
        if self._root is None:
            self.build()
        self.schedule_repaint()
        self._root.mainloop()

    def close(self) -> None:
        """Tear the window down. Safe to call when it was never built."""
        if self._root is None:
            return
        # Both suppressions are the same fact: tearing down something tk has
        # already torn down is not an error worth propagating out of close().
        if self._timer is not None:
            with contextlib.suppress(Exception):
                self._root.after_cancel(self._timer)
            self._timer = None
        with contextlib.suppress(Exception):
            self._root.destroy()
        self._root = None
        self._frame = None
        self._labels = []


def main() -> int:
    """Run the overlay with its default, honest, waiting-for-data panel.

        python -m overlay.window

    Nothing is computed yet - Emberforge deliberately computes nothing - so
    what appears is a status line and dashed rows. That is the point: the
    panel shows measured facts and status, never fabricated coaching.
    """
    OverlayWindow().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
