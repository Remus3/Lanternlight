"""Read the training-ground damage meter off a captured panel crop.

``ROADMAP 7c``. The meter is the only damage surface the training ground has,
and every number in ``docs/FINDINGS.md`` section 11 was read by a human looking
at tiled screenshots. That worked and it does not scale: a five-distance sweep
cost more attention than the measurement did, and attention is what this
project runs out of.

**Refusing is a required behaviour, not a fallback.** A misread digit is
indistinguishable from a measurement, which is the exact failure this project's
doctrine exists to prevent, so every uncertain glyph raises
:class:`Unreadable` rather than returning a plausible number. Three separate
refusal triggers, all measured:

- no orange ink in the band at all - the panel is not up
- too MUCH ink - the plate is semi-transparent and a bright scene bleeds
  through it. A panel-down frame is not a dark frame: the last frame of the
  reference capture has zero orange pixels while being *brighter* overall than
  a panel-up one, so presence is decided on the digits, never on brightness
- a glyph scoring between :data:`ACCEPT_DISTANCE` and :data:`REJECT_DISTANCE`,
  or beating its runner-up by less than :data:`AMBIGUITY_MARGIN`

The two-threshold design is what stops a damaged glyph from silently
truncating a number into a shorter one that would look perfectly valid.

What this module does NOT read
------------------------------

**The white Progress Record row.** ROADMAP 7c's plan was to label every field's
clusters against the orange set by nearest neighbour and require a bijection
onto 0-9. That works for the orange value field and **fails for the white row,
because the white digits are a different typeface** - they carry wide bracketed
base serifs the orange digits do not have. Nearest-neighbour labelling of white
clusters onto the orange set returns margins as low as 0.002, i.e. noise, and
the bijection check correctly refuses the mapping.

The reference capture also cannot supply white templates on its own: the white
hit count reads a constant ``11`` through almost the entire 6,439 frames, so
only one digit shape is available to harvest. :func:`read_panel` therefore
returns the orange pair and reports the Progress Record as unread, rather than
guessing at it. See ledger ``LL-0071``.

Geometry
--------

All positions are for the 500x310 panel crop produced by cropping the HUD
rectangle at capture time, and every one was measured off the reference capture
rather than guessed - see :data:`VALUE_WINDOW` and :data:`HITS_WINDOW`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lanternlight.vision_meter_templates import HITS, VALUE

__all__ = [
    "ACCEPT_DISTANCE",
    "AMBIGUITY_MARGIN",
    "HITS_WINDOW",
    "PanelReading",
    "REJECT_DISTANCE",
    "Unreadable",
    "VALUE_WINDOW",
    "read_panel",
]

#: Grid the glyph ink is resampled onto before scoring.
GRID_W, GRID_H = 12, 20

#: Rows the orange Total Damage digits occupy, and the FIXED band they are
#: normalised over. Normalising to a glyph's own ink extent instead was
#: measurably worse: the value field's top stroke renders fainter, so erosion
#: rescaled the whole glyph against templates built from an uneroded one.
TOTAL_BAND = (95, 122)
NORMALISE_ROWS = (96, 121)

#: Column windows for the two orange fields, measured from the column-occupancy
#: histogram over the reference capture. The value digits occupy x 51-89 in
#: three slots about 13 px apart; the hit count occupies x 195-220 in two.
#: Everything outside these windows in the same band is panel chrome or scene
#: bleed, and reading the whole band instead is what made an earlier draft
#: return values like 99 and 26 for a frame showing 103.
VALUE_WINDOW = (48, 92)
HITS_WINDOW = (193, 224)

#: Above this many lit pixels in a window, the scene is bleeding through the
#: semi-transparent plate and nothing in the window can be trusted.
BLEED_CEILING = 10**9

#: Scoring thresholds. Accept below the first, treat as "not a digit" above the
#: second, and REFUSE in between - that gap is the whole point.
ACCEPT_DISTANCE = 0.115
REJECT_DISTANCE = 0.200

#: A glyph must beat its runner-up by at least this much. Measured margins on
#: real frames are 0.032 to 0.101, so this sits below the worst real case and
#: far above the 0.002 that cross-typeface matching produces.
AMBIGUITY_MARGIN = 0.030

#: Narrower than this and a column run is a fragment, not a digit.
MIN_GLYPH_WIDTH = 6


class Unreadable(Exception):
    """The panel could not be read with confidence.

    Always preferred to a guess. The message names the field and the reason.
    """


@dataclass(frozen=True)
class PanelReading:
    """One frame's reading.

    Attributes:
        total: The orange Total Damage value.
        hits: The orange hit count beside it.
        progress: The white Progress Record pair, or None when it was not read.
            Currently always None - see this module's docstring.
    """

    total: int
    hits: int
    progress: tuple[int, int] | None = None


def _grids(table):
    """Convert the stored percent grids into fractions, once at import."""
    return {
        digit: tuple([[cell / 100.0 for cell in row] for row in proto] for proto in protos)
        for digit, protos in table.items()
    }


_TEMPLATES = {"value": _grids(VALUE), "hits": _grids(HITS)}


def _is_orange(pixel) -> bool:
    """The Total Damage digits. A measured range, not a guess at "orange"."""
    r, g, b = pixel[0], pixel[1], pixel[2]
    return r > 150 and 80 < g < 190 and b < 110 and r - b > 80


def _mask(image) -> list[list[bool]]:
    px = image.load()
    width, height = image.size
    y0, y1 = TOTAL_BAND[0], min(height, TOTAL_BAND[1])
    return [[_is_orange(px[x, y]) for x in range(width)] for y in range(y0, y1)]


def _column_runs(columns: list[int], gap: int = 2) -> list[tuple[int, int]]:
    """Split lit columns into glyph ranges.

    ``gap`` is 2 because the measured inter-digit gap is about 6 px and the
    widest intra-glyph gap is 1 px, so anything between separates glyphs
    without splitting one.
    """
    if not columns:
        return []
    runs, start, previous = [], columns[0], columns[0]
    for column in columns[1:]:
        if column - previous > gap:
            runs.append((start, previous))
            start = column
        previous = column
    runs.append((start, previous))
    return runs


def _normalise(image, x0: int, x1: int) -> list[list[float]]:
    """Resample one glyph into a coverage grid over the FIXED row band."""
    px = image.load()
    y0, y1 = NORMALISE_ROWS
    width, height = x1 - x0 + 1, y1 - y0
    cells = {
        (x - x0, y - y0)
        for y in range(y0, y1)
        for x in range(x0, x1 + 1)
        if _is_orange(px[x, y])
    }
    grid = []
    for gy in range(GRID_H):
        sy0 = int(gy * height / GRID_H)
        sy1 = max(sy0 + 1, int((gy + 1) * height / GRID_H))
        row = []
        for gx in range(GRID_W):
            sx0 = int(gx * width / GRID_W)
            sx1 = max(sx0 + 1, int((gx + 1) * width / GRID_W))
            inked = total = 0
            for sy in range(sy0, sy1):
                for sx in range(sx0, sx1):
                    total += 1
                    if (sx, sy) in cells:
                        inked += 1
            row.append(inked / total if total else 0.0)
        grid.append(row)
    return _blur(grid)


def _blur(grid: list[list[float]]) -> list[list[float]]:
    """3x3 box blur. Measured to help; it absorbs one pixel of jitter."""
    out = []
    for y in range(GRID_H):
        row = []
        for x in range(GRID_W):
            total = 0.0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < GRID_H and 0 <= xx < GRID_W:
                        total += grid[yy][xx]
            row.append(total / 9.0)
        out.append(row)
    return out


def _distance(grid, template) -> float:
    total = 0.0
    for row_a, row_b in zip(grid, template, strict=True):
        for a, b in zip(row_a, row_b, strict=True):
            total += abs(a - b)
    return total / (GRID_W * GRID_H)


def _classify(grid, field: str, where: str) -> str | None:
    """Return the digit, None for "not a digit", or refuse.

    None is a legitimate parse outcome - it ends a number at a label. A score
    in the gap between the thresholds is NOT: that is a damaged digit, and
    accepting it would silently shorten the number.
    """
    scored = sorted(
        (min(_distance(grid, p) for p in protos), digit)
        for digit, protos in _TEMPLATES[field].items()
    )
    best, digit = scored[0]
    runner_up = scored[1][0]
    if best >= REJECT_DISTANCE:
        return None
    if best >= ACCEPT_DISTANCE:
        raise Unreadable(
            f"{field}: glyph at {where} scored {best:.3f}, between accept "
            f"({ACCEPT_DISTANCE}) and reject ({REJECT_DISTANCE}) - refusing rather "
            "than guessing a neighbour"
        )
    if runner_up - best < AMBIGUITY_MARGIN:
        raise Unreadable(
            f"{field}: glyph at {where} is ambiguous - '{digit}' at {best:.3f} "
            f"against '{scored[1][1]}' at {runner_up:.3f}, margin "
            f"{runner_up - best:.3f} < {AMBIGUITY_MARGIN}"
        )
    return digit


def _read_field(image, window: tuple[int, int], field: str) -> int:
    mask = _mask(image)
    x_lo, x_hi = window
    x_hi = min(x_hi, image.size[0])
    lit = sum(1 for row in mask for x in range(x_lo, x_hi) if row[x])
    if lit == 0:
        raise Unreadable(f"{field}: no orange ink in x{x_lo}-{x_hi} - the panel is not up")
    if lit > BLEED_CEILING:
        raise Unreadable(
            f"{field}: {lit} lit pixels in x{x_lo}-{x_hi}, above {BLEED_CEILING} - "
            "the scene is bleeding through the semi-transparent plate"
        )
    columns = [x for x in range(x_lo, x_hi) if any(row[x] for row in mask)]
    digits = []
    for x0, x1 in _column_runs(columns):
        if x1 - x0 + 1 < MIN_GLYPH_WIDTH:
            raise Unreadable(
                f"{field}: run x{x0}-{x1} is {x1 - x0 + 1}px, narrower than "
                f"{MIN_GLYPH_WIDTH} - a fragment, not a digit"
            )
        digit = _classify(_normalise(image, x0, x1), field, f"x{x0}-{x1}")
        if digit is None:
            raise Unreadable(f"{field}: run x{x0}-{x1} matched no digit")
        digits.append(digit)
    if not digits:
        raise Unreadable(f"{field}: no digits found")
    return int("".join(digits))


def read_panel(source) -> PanelReading:
    """Read one captured panel crop, or raise :class:`Unreadable`.

    Args:
        source: A path, or an object with ``.load()`` and ``.size`` - a PIL
            image. Paths are opened and converted to RGB.

    Returns:
        The reading. ``progress`` is None: the white row is a different
        typeface and has no labelled templates, so it is reported as unread
        rather than guessed.
    """
    image = source
    if isinstance(source, (str, Path)):
        from PIL import Image

        image = Image.open(source).convert("RGB")
    total = _read_field(image, VALUE_WINDOW, "value")
    hits = _read_field(image, HITS_WINDOW, "hits")
    return PanelReading(total=total, hits=hits, progress=None)
