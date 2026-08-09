"""Pure placement geometry for the Lanternlight overlay.

Nothing in this module imports tkinter, imports ctypes, touches the
filesystem, reads the clock, or opens a window. Every function is a pure
function of its arguments. That is deliberate and it is tested: it is what
lets the entire placement model be exercised on a machine with no display, and
it is what keeps the interesting logic out of the tk shell where it could only
be checked by looking at pixels.

Two concepts live here.

Anchors
-------

A nine-position 3x3 grid, ``top-left`` through ``bottom-right``. Given a screen
size, a panel size, an anchor name and a margin, :func:`anchor_position`
returns the raw ``(x, y)`` of the panel's top-left corner.

Placement is always clamped, never negative. A panel larger than the screen
does not produce an off-screen negative coordinate; it produces ``0`` on the
offending axis, so the operator sees a clipped panel rather than no panel at
all. Silently vanishing is the worse failure of the two.

Safe zones
----------

Named rectangles of the game screen that the overlay must not cover because
the game draws critical HUD there. :func:`place` takes the raw anchor position
and pushes the panel clear of them.

    WARNING - THE SAFE ZONES BELOW ARE AN UNVERIFIED FIRST GUESS.

    Nobody has measured Mistfall Hunter's HUD. :data:`DEFAULT_SAFE_ZONES` is
    an educated guess at where an action game at 2560x1440 puts its vitals,
    ability bar, minimap, reticle and pickup feed. It is almost certainly
    wrong in the details and it may be wrong in the large.

    This is why the zones are exposed as DATA - a tuple of :class:`SafeZone`
    records with a note on each - and not as branches in the placement logic.
    When somebody finally measures the real HUD from a screen capture, the fix
    is to correct the numbers in :data:`DEFAULT_SAFE_ZONES` and to replace the
    note on each row. No function in this module needs to change, and no
    caller needs to change. Callers that already know better can pass their
    own ``safe_zones`` to :func:`place` today.

    Do not let these numbers harden into folklore. Until a capture is
    measured they are a placeholder wearing a coordinate's clothes, and
    ``docs/OVERLAY.md`` says so as well.

The reference resolution is the operator's own display, 2560x1440 on a single
monitor. :func:`safe_zones_for` scales the reference zones proportionally to
another screen size, which is a guess layered on a guess - a real HUD does not
scale uniformly - and it is labelled as such at the call site.
"""

from collections.abc import Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# anchor names
# ---------------------------------------------------------------------------

TOP_LEFT = "top-left"
TOP_CENTER = "top-center"
TOP_RIGHT = "top-right"
MIDDLE_LEFT = "middle-left"
MIDDLE_CENTER = "middle-center"
MIDDLE_RIGHT = "middle-right"
BOTTOM_LEFT = "bottom-left"
BOTTOM_CENTER = "bottom-center"
BOTTOM_RIGHT = "bottom-right"

#: The nine anchors, in reading order. Iteration order is part of the contract
#: so that a UI listing them is stable between runs.
ANCHORS: tuple[str, ...] = (
    TOP_LEFT,
    TOP_CENTER,
    TOP_RIGHT,
    MIDDLE_LEFT,
    MIDDLE_CENTER,
    MIDDLE_RIGHT,
    BOTTOM_LEFT,
    BOTTOM_CENTER,
    BOTTOM_RIGHT,
)

ANCHOR_SET = frozenset(ANCHORS)

#: Fraction of the free space consumed before the panel, per axis band.
_VERTICAL_FRACTION = {"top": 0.0, "middle": 0.5, "bottom": 1.0}
_HORIZONTAL_FRACTION = {"left": 0.0, "center": 0.5, "right": 1.0}

#: Gap between the panel and the screen edge, in pixels, unless overridden.
DEFAULT_MARGIN = 24


# ---------------------------------------------------------------------------
# geometry primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Size:
    """A width and a height in pixels."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"size must be non-negative, got {self!r}")


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned rectangle: top-left corner plus a size.

    Edges are half-open. ``Rect(0, 0, 10, 10)`` covers x in [0, 10) and y in
    [0, 10), so it does NOT overlap ``Rect(10, 0, 10, 10)``. That convention
    is what makes "place the panel immediately to the right of this zone"
    produce a non-overlapping result rather than a one-pixel collision.
    """

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """x coordinate one pixel past the rightmost covered column."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """y coordinate one pixel past the lowest covered row."""
        return self.y + self.height

    def overlaps(self, other: Rect) -> bool:
        """True when this rectangle shares at least one pixel with ``other``."""
        if self.width <= 0 or self.height <= 0:
            return False
        if other.width <= 0 or other.height <= 0:
            return False
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )


@dataclass(frozen=True, slots=True)
class SafeZone:
    """A named region the overlay should not cover, plus why we think so.

    ``note`` is not decoration. Every zone here is a guess, and the note is
    where the guess records what it is a guess about, so the person holding a
    real screen capture knows what to check.
    """

    name: str
    rect: Rect
    note: str


#: The operator's display, and the resolution every zone below is written for.
REFERENCE_SIZE = Size(2560, 1440)


# ---------------------------------------------------------------------------
# safe zones - DATA, and an unverified first guess. See the module docstring.
# ---------------------------------------------------------------------------

#: Critical-HUD regions of a 2560x1440 Mistfall Hunter screen.
#:
#: UNVERIFIED. Not one of these rectangles has been measured against a real
#: capture of the game. They are the regions an action game of this shape
#: usually reserves. Correct the numbers here, not the logic elsewhere.
DEFAULT_SAFE_ZONES: tuple[SafeZone, ...] = (
    SafeZone(
        name="reticle",
        rect=Rect(1180, 660, 200, 120),
        note=(
            "Dead centre aim point. Guessed. Even if the game draws no "
            "crosshair, this is where the operator's eyes are during combat, "
            "so covering it is wrong regardless of what is rendered there."
        ),
    ),
    SafeZone(
        name="player_vitals",
        rect=Rect(0, 1180, 620, 260),
        note=(
            "Bottom-left health and stamina. Guessed from the genre "
            "convention, not observed. Could equally be bottom-centre."
        ),
    ),
    SafeZone(
        name="ability_bar",
        rect=Rect(960, 1240, 640, 200),
        note=(
            "Bottom-centre ability and consumable slots. Guessed. Width is "
            "the least trustworthy number here - slot count is unknown."
        ),
    ),
    SafeZone(
        name="minimap",
        rect=Rect(2140, 0, 420, 420),
        note=(
            "Top-right minimap or compass. Guessed. If the game uses a "
            "top-centre compass strip instead, this zone is in the wrong "
            "place entirely and a new zone is needed."
        ),
    ),
    SafeZone(
        name="status_effects",
        rect=Rect(0, 0, 560, 180),
        note="Top-left buff and debuff row. Guessed.",
    ),
    SafeZone(
        name="objective_tracker",
        rect=Rect(2020, 520, 540, 400),
        note=(
            "Right-hand objective or quest text. Guessed, and the most "
            "likely of the set to not exist at all."
        ),
    ),
    SafeZone(
        name="loot_feed",
        rect=Rect(1960, 1120, 600, 320),
        note=(
            "Bottom-right pickup and damage feed. Guessed. Feeds grow "
            "upward, so the real height is probably variable."
        ),
    ),
)


def safe_zones_for(
    screen: Size,
    zones: Sequence[SafeZone] = DEFAULT_SAFE_ZONES,
    reference: Size = REFERENCE_SIZE,
) -> tuple[SafeZone, ...]:
    """Scale ``zones`` from ``reference`` to ``screen`` proportionally.

    A guess layered on a guess: real HUDs anchor to edges and scale their
    elements non-uniformly, so a proportional stretch is only ever an
    approximation. It is here so a non-reference resolution degrades to
    "roughly right" instead of "silently unprotected".

    Returns the input unchanged when the sizes already match.
    """
    if reference.width <= 0 or reference.height <= 0:
        raise ValueError(f"reference size must be positive, got {reference!r}")
    if screen == reference:
        return tuple(zones)

    sx = screen.width / reference.width
    sy = screen.height / reference.height
    scaled = []
    for zone in zones:
        scaled.append(
            SafeZone(
                name=zone.name,
                rect=Rect(
                    x=round(zone.rect.x * sx),
                    y=round(zone.rect.y * sy),
                    width=round(zone.rect.width * sx),
                    height=round(zone.rect.height * sy),
                ),
                note=zone.note + " Scaled from the 2560x1440 reference.",
            )
        )
    return tuple(scaled)


def overlapping_zones(
    rect: Rect, zones: Sequence[SafeZone] = DEFAULT_SAFE_ZONES
) -> tuple[SafeZone, ...]:
    """Return every zone in ``zones`` that ``rect`` covers any pixel of."""
    return tuple(zone for zone in zones if rect.overlaps(zone.rect))


# ---------------------------------------------------------------------------
# anchor placement
# ---------------------------------------------------------------------------


def _clamp_axis(value: int, panel_len: int, screen_len: int, margin: int) -> int:
    """Clamp one axis so the panel stays on screen and never goes negative.

    Three regimes, in order of preference:

    1. Panel plus both margins fits. Clamp into ``[margin, screen - panel -
       margin]``.
    2. Panel fits but the margins do not. Give up the margins and clamp into
       ``[0, screen - panel]``, so the panel is fully visible and flush.
    3. Panel is larger than the screen. Return ``0``. The panel is clipped on
       the far edge, which is visible and diagnosable; a negative coordinate
       would clip the near edge too and hide the part that names the panel.
    """
    slack = screen_len - panel_len
    if slack < 0:
        return 0
    lo, hi = margin, slack - margin
    if hi < lo:
        lo, hi = 0, slack
    return max(lo, min(value, hi))


def _fraction_position(fraction: float, panel_len: int, screen_len: int, margin: int) -> int:
    """Unclamped ideal coordinate for one axis at ``fraction`` of the band."""
    if fraction == 0.0:
        return margin
    if fraction == 1.0:
        return screen_len - panel_len - margin
    # Centred: split the free space evenly and ignore the margin entirely.
    # A centred panel that respected the margin would not be centred.
    return (screen_len - panel_len) // 2


def split_anchor(anchor: str) -> tuple[str, str]:
    """Split ``"bottom-right"`` into ``("bottom", "right")``.

    Raises :class:`ValueError` on any name that is not one of the nine. An
    unknown anchor is a caller bug, and defaulting it to a corner would hide
    the bug behind a panel that renders in the wrong place forever.
    """
    if anchor not in ANCHOR_SET:
        raise ValueError(
            f"unknown anchor {anchor!r}; expected one of {', '.join(ANCHORS)}"
        )
    vertical, horizontal = anchor.split("-", 1)
    return vertical, horizontal


def anchor_position(
    screen: Size,
    panel: Size,
    anchor: str,
    margin: int = DEFAULT_MARGIN,
) -> tuple[int, int]:
    """Raw top-left ``(x, y)`` for ``panel`` at ``anchor`` within ``screen``.

    Clamped to the screen and never negative. Safe zones are NOT considered -
    use :func:`place` for that. This function exists on its own so the two
    behaviours can be tested apart, and so a caller that genuinely wants the
    literal corner can have it.
    """
    if margin < 0:
        raise ValueError(f"margin must be non-negative, got {margin}")
    vertical, horizontal = split_anchor(anchor)

    x = _fraction_position(
        _HORIZONTAL_FRACTION[horizontal], panel.width, screen.width, margin
    )
    y = _fraction_position(
        _VERTICAL_FRACTION[vertical], panel.height, screen.height, margin
    )
    return (
        _clamp_axis(x, panel.width, screen.width, margin),
        _clamp_axis(y, panel.height, screen.height, margin),
    )


def place(
    screen: Size,
    panel: Size,
    anchor: str,
    margin: int = DEFAULT_MARGIN,
    safe_zones: Sequence[SafeZone] = DEFAULT_SAFE_ZONES,
) -> tuple[int, int]:
    """Placement for ``panel`` at ``anchor``, pushed clear of ``safe_zones``.

    Starts from :func:`anchor_position`. If that lands clear, it is returned
    unchanged - the common case costs one overlap sweep and nothing else.

    Otherwise the panel is moved to the nearest position that is both on
    screen and clear of every zone. "Nearest" is Manhattan distance from the
    raw anchor position, so the panel stays as close to what the operator
    asked for as the HUD allows.

    The candidate set is finite and small: for each axis, the raw coordinate
    plus, for every zone, the coordinate that puts the panel immediately
    before or immediately after that zone. Any minimal escape from a set of
    axis-aligned rectangles is flush against one of their edges, so a
    solution that exists is in this set. Roughly ``(2n+1)^2`` candidates for
    ``n`` zones, which is 225 for the seven default zones.

    When no candidate is clear - a panel too large to fit anywhere, or zones
    that between them cover the screen - the raw anchor position is returned.
    That is a deliberate best-effort fallback: a panel over the HUD is bad, a
    panel that does not render is worse, and the caller can detect the case
    itself with :func:`overlapping_zones`.
    """
    raw_x, raw_y = anchor_position(screen, panel, anchor, margin)
    zones = tuple(safe_zones)
    if not zones:
        return raw_x, raw_y

    panel_rect = Rect(raw_x, raw_y, panel.width, panel.height)
    if not overlapping_zones(panel_rect, zones):
        return raw_x, raw_y

    xs = {raw_x}
    ys = {raw_y}
    for zone in zones:
        xs.add(zone.rect.x - panel.width)
        xs.add(zone.rect.right)
        ys.add(zone.rect.y - panel.height)
        ys.add(zone.rect.bottom)

    clamped_xs = {_clamp_axis(x, panel.width, screen.width, margin) for x in xs}
    clamped_ys = {_clamp_axis(y, panel.height, screen.height, margin) for y in ys}

    best: tuple[int, int, int] | None = None
    for cx in clamped_xs:
        for cy in clamped_ys:
            candidate = Rect(cx, cy, panel.width, panel.height)
            if overlapping_zones(candidate, zones):
                continue
            # Sort key is (distance, y, x): nearest wins, and the tie-break is
            # fixed so the same inputs always produce the same pixel.
            key = (abs(cx - raw_x) + abs(cy - raw_y), cy, cx)
            if best is None or key < best:
                best = key

    if best is None:
        return raw_x, raw_y
    return best[2], best[1]
