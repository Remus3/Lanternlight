"""The overlay's text-panel render model. Pure data in, lines out.

This module imports no tkinter, and it must not start. It is the seam: the
panel's content is decided here, as a value that can be compared, asserted on,
and diffed between two runs, and the tk shell in :mod:`overlay.window` only
paints what it is handed. Anything interesting that lives in the widget code
can only be checked by looking at pixels, which is slow, subjective and
unavailable in CI.

The no-reflow contract
----------------------

    render(payload) always returns 3 + len(payload.rows) lines, for every
    payload, whatever is missing from it.

This is the dominant constraint on this panel, not a nicety. The panel is read
at a glance during combat. If a row disappears when its value goes missing,
every row below it moves, and the operator's next glance lands on the wrong
number - worse than showing nothing, because it is confidently wrong. So a
missing value renders as :data:`MISSING_VALUE` with the style
:data:`STYLE_ROW_MISSING`, in the same place, and the line count does not
move.

Both ``None`` and a blank or whitespace-only string count as missing. A
producer that has no reading and one that hands over an empty string are the
same fact to a reader, and forcing every producer to normalise would be a rule
nobody remembers at the call site.

Truncation, not wrapping
------------------------

Long values are truncated with a trailing ``...``, never wrapped. Wrapping
would change the line count, which is the one thing the contract above forbids.
A truncated value is legibly incomplete; a wrapped one silently shoves the rest
of the panel down.

Nothing is fabricated here
--------------------------

Emberforge computes nothing yet and no cooldown or damage numbers are published
for this game, so the panel's first job is to display measured facts and
status. :func:`waiting_payload` is the honest default: it says what the overlay
is waiting for, and it shows the rows it will eventually fill as missing rather
than filling them with plausible-looking placeholders. A number the operator
cannot tell apart from a measured one is worse than a dash.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# rendering constants
# ---------------------------------------------------------------------------

#: What a missing value renders as. Two hyphens, ASCII, visibly not a number.
MISSING_VALUE = "--"

#: Truncation marker. Three ASCII dots, never the single-glyph ellipsis - this
#: repository is 7-bit ASCII by rule.
ELLIPSIS = "..."

#: Width of the label column, in characters, including its trailing gap.
DEFAULT_LABEL_WIDTH = 14

#: Width allowed for a value before it is truncated, in characters.
DEFAULT_VALUE_WIDTH = 24


# ---------------------------------------------------------------------------
# styles - names only. The tk shell owns fonts and colours.
# ---------------------------------------------------------------------------

STYLE_TITLE = "title"
STYLE_STATUS_OK = "status-ok"
STYLE_STATUS_WAITING = "status-waiting"
STYLE_STATUS_ERROR = "status-error"
STYLE_ROW = "row"
STYLE_ROW_MISSING = "row-missing"
STYLE_NOTE = "note"

#: Every style name this module can emit. The shell is expected to have a
#: concrete font and colour for each; a style outside this set is a bug in
#: this module, and the tests assert the rendered output stays inside it.
STYLES = frozenset(
    {
        STYLE_TITLE,
        STYLE_STATUS_OK,
        STYLE_STATUS_WAITING,
        STYLE_STATUS_ERROR,
        STYLE_ROW,
        STYLE_ROW_MISSING,
        STYLE_NOTE,
    }
)

STATUS_OK = "ok"
STATUS_WAITING = "waiting"
STATUS_ERROR = "error"

#: Recognised status values, in severity order.
STATUSES: tuple[str, ...] = (STATUS_OK, STATUS_WAITING, STATUS_ERROR)

_STATUS_STYLES = {
    STATUS_OK: STYLE_STATUS_OK,
    STATUS_WAITING: STYLE_STATUS_WAITING,
    STATUS_ERROR: STYLE_STATUS_ERROR,
}

#: Stable per-line keys for the two fixed lines. A caller diffing two renders
#: matches on ``Line.key``, not on position, so inserting a row later does not
#: silently re-point an existing comparison.
KEY_TITLE = "title"
KEY_STATUS = "status"
KEY_NOTE = "note"
KEY_ROW_PREFIX = "row:"

#: Number of lines that are always present regardless of payload contents:
#: title, status, note.
FIXED_LINE_COUNT = 3


# ---------------------------------------------------------------------------
# payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    """One label/value pair. ``value`` of ``None`` means "not measured"."""

    label: str
    value: str | None = None


@dataclass(frozen=True, slots=True)
class Payload:
    """Everything the panel is asked to show, as one immutable value.

    ``status_text`` is the human sentence, ``status`` is the machine severity
    that picks the style. They are separate because the sentence changes far
    more often than the severity, and colour should not shift every time the
    wording is reworded.
    """

    title: str
    status_text: str
    status: str = STATUS_WAITING
    rows: tuple[Row, ...] = field(default_factory=tuple)
    note: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _STATUS_STYLES:
            raise ValueError(
                f"unknown status {self.status!r}; expected one of "
                f"{', '.join(STATUSES)}"
            )


@dataclass(frozen=True, slots=True)
class Line:
    """One rendered line: the text to draw, its style, and its stable key."""

    text: str
    style: str
    key: str


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def truncate(text: str, width: int) -> str:
    """Cut ``text`` to ``width`` characters, marking the cut with ``...``.

    Never wraps and never returns more than ``width`` characters. When
    ``width`` is too small to hold the marker itself the text is hard-cut,
    because a line consisting only of dots carries less information than a
    truncated word.
    """
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= len(ELLIPSIS):
        return text[:width]
    return text[: width - len(ELLIPSIS)] + ELLIPSIS


def is_missing(value: str | None) -> bool:
    """True when ``value`` carries no reading: ``None``, empty, or whitespace."""
    return value is None or not value.strip()


def line_count(payload: Payload) -> int:
    """Lines :func:`render` will produce for ``payload``.

    Depends only on the NUMBER of rows, never on their contents. This is the
    no-reflow contract expressed as a function, so a caller sizing a window
    can compute the height without rendering, and a test can assert the
    contract without inspecting text.
    """
    return FIXED_LINE_COUNT + len(payload.rows)


def texts(lines: Sequence[Line]) -> tuple[str, ...]:
    """Just the text of each line - convenience for assertions and logging."""
    return tuple(line.text for line in lines)


# ---------------------------------------------------------------------------
# the render
# ---------------------------------------------------------------------------


def render(
    payload: Payload,
    label_width: int = DEFAULT_LABEL_WIDTH,
    value_width: int = DEFAULT_VALUE_WIDTH,
) -> tuple[Line, ...]:
    """Turn ``payload`` into the exact lines and styles the panel will draw.

    Emits, always and in this order:

    1. the title
    2. the status sentence, styled by severity
    3. one line per row, in payload order
    4. the note line - :data:`MISSING_VALUE` when there is no note

    The note line is unconditional for the same reason a row is: it is the
    last line, and a last line that comes and goes makes the panel's own
    outline twitch.
    """
    if label_width < 0 or value_width < 0:
        raise ValueError(
            f"widths must be non-negative, got label={label_width} value={value_width}"
        )

    total_width = label_width + value_width
    lines = [
        Line(
            text=truncate(payload.title, total_width),
            style=STYLE_TITLE,
            key=KEY_TITLE,
        ),
        Line(
            text=truncate(payload.status_text, total_width),
            style=_STATUS_STYLES[payload.status],
            key=KEY_STATUS,
        ),
    ]

    for index, row in enumerate(payload.rows):
        missing = is_missing(row.value)
        value = MISSING_VALUE if missing else truncate(str(row.value), value_width)
        # Reserve one character of the label column as the gap, so a
        # full-width label cannot butt straight up against its value.
        label = truncate(row.label, max(0, label_width - 1)).ljust(label_width)
        lines.append(
            Line(
                text=label + value,
                style=STYLE_ROW_MISSING if missing else STYLE_ROW,
                # Index-prefixed so two rows sharing a label stay distinct.
                key=f"{KEY_ROW_PREFIX}{index}:{row.label}",
            )
        )

    note_missing = is_missing(payload.note)
    lines.append(
        Line(
            text=MISSING_VALUE if note_missing else truncate(str(payload.note), total_width),
            style=STYLE_NOTE,
            key=KEY_NOTE,
        )
    )
    return tuple(lines)


def waiting_payload(
    reason: str,
    labels: Sequence[str] = ("run state", "map", "class", "elapsed"),
    title: str = "Lanternlight",
) -> Payload:
    """The degraded payload: the panel says what it is waiting for.

    Used when the game is not running, the log has not appeared, or the tail
    has gone quiet. Every row is rendered missing rather than blank, so the
    panel keeps its exact shape and the operator sees dashes where numbers
    will be instead of a panel that changed size.
    """
    return Payload(
        title=title,
        status_text=reason,
        status=STATUS_WAITING,
        rows=tuple(Row(label=label) for label in labels),
        note=None,
    )
