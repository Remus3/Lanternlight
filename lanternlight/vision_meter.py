"""Read the training-ground damage meter off a captured panel crop.

``ROADMAP 7c``. The meter is the only damage surface the training ground has,
and every number in ``docs/FINDINGS.md`` section 11 was read by a human looking
at tiled screenshots. That worked and it does not scale: a five-distance sweep
cost more attention than the measurement did, and attention is what this
project runs out of.

**Refusing is a required behaviour, not a fallback.** A misread digit is
indistinguishable from a measurement, which is the exact failure this project's
doctrine exists to prevent, so every uncertain glyph raises
:class:`Unreadable` rather than returning a plausible number. Six refusal
triggers, all measured:

- no orange ink in the band at all - the panel is not up
- too MUCH ink - the plate is semi-transparent and a bright scene bleeds
  through it. A panel-down frame is not a dark frame: the last frame of the
  reference capture has zero orange pixels while being *brighter* overall than
  a panel-up one, so presence is decided on the digits, never on brightness
- a glyph scoring between :data:`ACCEPT_DISTANCE` and :data:`REJECT_DISTANCE`,
  or beating its runner-up by less than :data:`AMBIGUITY_MARGIN`
- a run narrower than :data:`MIN_GLYPH_WIDTH` that is not the thousands
  separator - see :func:`_is_separator`
- a run wider than :data:`MAX_GLYPH_WIDTH` without exactly one interior gap to
  split it at - see :func:`_split_merged`
- digits that do not group as a number around a separator - see
  :func:`_regroup`

The two-threshold design is what stops a damaged glyph from silently
truncating a number into a shorter one that would look perfectly valid.

**These guards are load-bearing, and that is measured.** Over the 1.0.15
capture's 124 panel-up frames the reader returns 118 readings and refuses 6,
with ZERO disagreements against the human transcription. Disabling the accept
band and the ambiguity margin raises that to 123 readings - and THREE of them
are wrong: 262 for a true 261, 633 for 618, and 3334 for 1834, that last wrong
in its leading digit. The six refusals are the module working, not a threshold
being timid, so do not widen a constant to chase them.

What this module does NOT read
------------------------------

**The white Progress Record row.** ROADMAP 7c's plan was to label every field's
clusters against the orange set by nearest neighbour and require a bijection
onto 0-9. That works for the orange value field and **fails for the white row,
because the white digits are a different typeface** - they carry wide bracketed
base serifs the orange digits do not have. Nearest-neighbour labelling of white
clusters onto the orange set returns margins as low as 0.002, i.e. noise, and
the bijection check correctly refuses the mapping.

The white row is also capture-limited, though the reason stated here first was
wrong and is worth not repeating. It is NOT that the field never changes: the
white *hit count* reads a constant ``11``, but the white *value* takes 26
distinct values and covers all ten digits (``LL-0072``). The real limit is that
the value changes so OFTEN that only about five record epochs last long enough
to yield clean training frames, and those few repeat the same digits - so ten
digits costs accuracy and accuracy costs coverage, with no usable point on that
curve (``LL-0074``).

:func:`read_panel` therefore returns the orange pair and reports the Progress
Record as unread, rather than guessing at it.

Geometry
--------

All positions are for the 500x310 panel crop produced by cropping the HUD
rectangle at capture time, and every one was measured off the reference capture
rather than guessed - see :data:`VALUE_WINDOW` and :data:`HITS_WINDOW`.

**The geometry is a property of the HUD, not of a purpose-built crop.** A
2560x1440 full-scene frame reads unmodified by taking the same 500x310 crop at
origin ``(2058, 390)``. The x origin is tolerant across 2056-2061; y 390 is the
best of five rows swept and every offset gave ZERO disagreements, so vertical
misalignment costs readings and never produces a wrong one.
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
#:
#: **The value window was widened from (48, 92) and that was NOT optional.**
#: (48, 92) was sized for three digits. A four-digit value spans x54-115, so
#: the old window dropped the last digit entirely and clipped the third - an
#: adversarial pass that taught the reader the separator WITHOUT widening this
#: read a true 2,000 as a confident 2,06. Measured over the 1.0.15 capture: the
#: full value extent across all 124 panel-up frames is x53-115, no value run
#: ever reaches x>=193, and the hit count starts at x199, so 84 columns of
#: guaranteed-empty gap separate the two fields. Widening cannot collide.
VALUE_WINDOW = (40, 120)
HITS_WINDOW = (193, 224)

#: Above this many lit pixels in a window, the scene is bleeding through the
#: semi-transparent plate and nothing in the window can be trusted.
BLEED_CEILING = 800

#: Scoring thresholds. Accept below the first, treat as "not a digit" above the
#: second, and REFUSE in between - that gap is the whole point.
ACCEPT_DISTANCE = 0.115
REJECT_DISTANCE = 0.200

#: A glyph must beat its runner-up by at least this much.
#:
#: **The headroom is thin and the number first filed here was the wrong one.**
#: "0.032 to 0.101" described the margins when CLUSTERS were labelled against
#: the reference set, not the margins this reader sees at read time. Measured
#: over the reference capture at read time, the tightest margin is **0.0311**
#: against this 0.030 threshold - about a thousandth of headroom - and the worst
#: accepted distance is 0.105 to 0.115 against an accept threshold of 0.115.
#:
#: That is uncomfortable but it fails SAFE: a glyph that drifts past either
#: bound is refused, not guessed. Do not widen either constant to make a frame
#: read; re-harvest the templates instead.
AMBIGUITY_MARGIN = 0.030

#: Narrower than this and a column run is a fragment, not a digit.
MIN_GLYPH_WIDTH = 6

#: Wider than this and a column run cannot be ONE glyph, so it is split.
#:
#: ``_column_runs`` breaks on a gap of 3 or more, because the widest measured
#: intra-glyph gap is 1px. Two digits separated by a single blank column give
#: ``column - previous == 2``, which does not break, so the pair merges into
#: one run - 19 such runs in the 1.0.15 capture, 18 of them with a ``4`` on the
#: left whose crossbar spills a column right.
#:
#: **The width gate is the safety property, not the valley.** Measured: a run
#: that is definitely one glyph is 8-13px in the value field and 10-12px in the
#: hit count, a run that is definitely two is 24-27px, and NOTHING lands in
#: 14-23. Splitting on an interior gap alone would be unsafe - 12
#: definitely-single glyphs carry an interior blank column of their own, 11 of
#: them the digit ``0``, whose hollow centre looks exactly like a join.
#:
#: Both directions of a mis-set gate fail safe: too low splits a real glyph
#: into halves that then score as nothing, too high leaves a pair merged. Both
#: end in a refusal rather than a number, which is why 18 - the middle of the
#: measured gap - is chosen rather than tuned.
MAX_GLYPH_WIDTH = 18

#: The thousands separator, measured over all 55 four-digit frames of the
#: 1.0.15 capture inside this module's own row band - not inside some probe's
#: private crop, which is how an earlier pass measured the comma at 5px and
#: drew the wrong conclusion from it.
#:
#: | property | separator | digit |
#: |---|---|---|
#: | width | 3-4 | 8-13 |
#: | first inked row | 19-20 | 4-6 |
#: | height | 6-8 | 17-20 |
#:
#: **The first inked row is the discriminator**, with a 13-row gap, and it is
#: strongest exactly where an ink count is weakest: the faintest genuine digit
#: measured - value 618 at 18 lit pixels against a median of 56 - still starts
#: at row 4 and stands 19 rows tall. An ink-count rule would have had 5 pixels
#: of headroom there; this one has 13 rows.
#:
#: **x position is NOT a discriminator and must never become one.** The comma
#: sits at x68-72 and 49 genuine digit runs from 2- and 3-digit values overlap
#: that span - a value of 116 puts a real digit at x68-75, the comma's own left
#: edge.
#:
#: ``row_max`` is deliberately not a criterion: the comma is CLIPPED by
#: ``TOTAL_BAND``, whose last row is 26, so its bottom edge is a property of
#: the crop rather than of the glyph.
SEPARATOR_MIN_ROW = 12
SEPARATOR_MAX_HEIGHT = 10


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


def _is_separator(mask, x0: int, x1: int) -> bool:
    """Is this narrow run the thousands comma rather than a broken digit?

    **Only ever asked about a run that is ALREADY being refused** as narrower
    than :data:`MIN_GLYPH_WIDTH`. That ordering is the safety property: this
    test can reclassify a refusal into a separator, and it can never touch a
    run that currently reads as a digit. Teaching the reader the comma
    therefore cannot change any number this module already returns.

    Decided on the run's vertical position and extent - see
    :data:`SEPARATOR_MIN_ROW`. A comma hangs below the digit baseline; an
    eroded digit does not move.
    """
    rows = [y for y in range(len(mask)) for x in range(x0, x1 + 1) if mask[y][x]]
    if not rows:
        return False
    top, bottom = min(rows), max(rows)
    if top < SEPARATOR_MIN_ROW:
        return False
    return bottom - top + 1 <= SEPARATOR_MAX_HEIGHT


def _split_merged(mask, x0: int, x1: int, field: str) -> list[tuple[int, int]]:
    """Split a run too wide to be one glyph, at its interior gap.

    Only ever called on a run wider than :data:`MAX_GLYPH_WIDTH`, which the
    measured populations say cannot be a single glyph.

    The two digits do NOT touch - an earlier description of this said they did.
    They are separated by exactly one blank column, and every one of the 19
    merged runs measured carries exactly one such gap, at the run's interior
    minimum. Requiring exactly one is deliberate: three merged glyphs were
    never observed, so a run with two gaps is refused rather than presumed to
    be a triple.
    """
    lit = [any(row[x] for row in mask) for x in range(x0, x1 + 1)]
    gaps, start = [], None
    for index, inked in enumerate(lit):
        if not inked and start is None:
            start = index
        elif inked and start is not None:
            gaps.append((start, index - 1))
            start = None
    if len(gaps) != 1:
        raise Unreadable(
            f"{field}: run x{x0}-{x1} is {x1 - x0 + 1}px, too wide for one "
            f"glyph, and has {len(gaps)} interior gaps rather than 1 - there "
            "is no defensible place to split it"
        )
    gap_start, gap_end = gaps[0]
    return [(x0, x0 + gap_start - 1), (x0 + gap_end + 1, x1)]


def _regroup(tokens: list[str | None], field: str) -> str:
    """Join the run sequence into digits, enforcing the thousands grouping.

    ``tokens`` carries one entry per column run - the digit, or None for a
    separator.

    **This is the check that catches a truncation.** An adversarial pass that
    taught the reader the comma while leaving the value window sized for three
    digits returned ``2,06`` for a true ``2,000``: the window had clipped the
    last two digits, and nothing downstream objected because ``206`` is a
    perfectly plausible number. Two digits after a thousands separator is not a
    number, so the shape of the grouping is itself evidence, and refusing a
    malformed one costs nothing.
    """
    groups: list[list[str]] = [[]]
    for token in tokens:
        if token is None:
            groups.append([])
        else:
            groups[-1].append(token)

    if len(groups) == 1:
        if not groups[0]:
            raise Unreadable(f"{field}: no digits found")
        return "".join(groups[0])

    sizes = [len(group) for group in groups]
    if not 1 <= sizes[0] <= 3 or any(size != 3 for size in sizes[1:]):
        raise Unreadable(
            f"{field}: separator grouping {sizes} is not a number - a "
            "thousands separator must be preceded by one to three digits and "
            "followed by exactly three"
        )
    return "".join("".join(group) for group in groups)


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
    tokens: list[str | None] = []
    for x0, x1 in _column_runs(columns):
        if x1 - x0 + 1 < MIN_GLYPH_WIDTH:
            if _is_separator(mask, x0, x1):
                tokens.append(None)
                continue
            raise Unreadable(
                f"{field}: run x{x0}-{x1} is {x1 - x0 + 1}px, narrower than "
                f"{MIN_GLYPH_WIDTH} - a fragment, not a digit"
            )
        pieces = (
            [(x0, x1)]
            if x1 - x0 + 1 <= MAX_GLYPH_WIDTH
            else _split_merged(mask, x0, x1, field)
        )
        for a, b in pieces:
            if b - a + 1 < MIN_GLYPH_WIDTH:
                raise Unreadable(
                    f"{field}: splitting x{x0}-{x1} left a {b - a + 1}px piece "
                    f"at x{a}-{b}, narrower than {MIN_GLYPH_WIDTH}"
                )
            digit = _classify(_normalise(image, a, b), field, f"x{a}-{b}")
            if digit is None:
                raise Unreadable(f"{field}: run x{a}-{b} matched no digit")
            tokens.append(digit)
    return int(_regroup(tokens, field))


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
