"""Parse MistfallHunter.log into typed lines and typed events.

The game is Unreal Engine 5, so the log carries the stock UE line header::

    [YYYY.MM.DD-HH.MM.SS:mmm][frame]Category: message

with two Mistfall-Hunter-specific wrinkles worth stating up front, because
both were measured from the real file on 2026-08-09 and both break a naive
splitter:

- **Timestamps are UTC.** They are not local time and they carry no offset, so
  a reader that builds a naive ``datetime`` and then compares it against
  ``datetime.now()`` will be wrong by the operator's timezone. Every timestamp
  produced here is tz-aware and pinned to UTC.
- **The whitespace is irregular.** Real lines carry a double space before an
  operator (``inclassid  ==10``) and a trailing space at end of line. Nothing
  in this module splits on a single space or trusts ``len(parts)``.

Categories may be dotted (``TS.Avatar``) and may be followed by a UE verbosity
word (``Display:``, ``Verbose:``) that is *not* part of the message.

Field order is not assumed beyond what the measured samples show. Key/value
payloads are extracted by pattern (``key-value`` and ``key ==value``), not by
position, so a patch that reorders or inserts a field does not silently shift
every value by one.

``parse_line`` never raises on junk. A UE log interleaves continuation lines,
stack traces, blank lines and half-written trailing lines from a live append;
all of those return ``None``.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = [
    "CLASS_NAMES",
    "ClassSelectionEvent",
    "Event",
    "LogLine",
    "MapTransitionEvent",
    "MatchStateEvent",
    "VERBOSITY_WORDS",
    "WeaponHoldingEvent",
    "class_name",
    "iter_events",
    "parse_line",
    "parse_lines",
]


#: Measured, first-party class id mapping. Ids outside this table are unknown,
#: not guessable - see :func:`class_name`.
CLASS_NAMES: dict[int, str] = {
    10: "Mercenary",
    11: "Sorcerer",
    12: "Blackarrow",
    13: "Shadowstrix",
    14: "Seer",
    15: "Withered Knight",
}

#: UE verbosity words that may sit between the category and the message.
VERBOSITY_WORDS: frozenset[str] = frozenset(
    {
        "Fatal",
        "Error",
        "Warning",
        "Display",
        "Log",
        "Verbose",
        "VeryVerbose",
    }
)


_LINE_RE = re.compile(
    r"^\[(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})"
    r"-(?P<hour>\d{2})\.(?P<minute>\d{2})\.(?P<second>\d{2}):(?P<milli>\d{3})\]"
    r"\[\s*(?P<frame>\d+)\s*\]"
    r"(?P<category>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*):"
    r"(?P<rest>.*)$"
)

_VERBOSITY_RE = re.compile(r"^(?P<word>[A-Za-z]+):\s*(?P<rest>.*)$")

# "inclassid  ==10" and "inGender ==1" - note the tolerated double space.
_EQEQ_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*==\s*(?P<value>-?\d+)")

# "class-10", "holding-30402", "gender-1", "spiritual-false". Bracketed values
# such as "armors-[0,12301]" are deliberately not matched here.
_DASHKV_RE = re.compile(
    r"(?<![\w\-])(?P<key>[A-Za-z_][A-Za-z0-9_]*)-(?P<value>[^\s\[\]]+)"
)

# Unreal actor instance names, e.g. BP_Preview_C_2147475781.
_ACTOR_RE = re.compile(r"\b(?P<actor>[A-Za-z_][A-Za-z0-9_]*_C_\d+)\b")

_MATCH_STATE_RE = re.compile(
    r"match\s+state\s+changed\s+to\s+(?P<state>[A-Za-z0-9_]+)", re.IGNORECASE
)

_WORLD_RE = re.compile(r"\bat\s+world\s+(?P<world>[A-Za-z0-9_]+)")

_OPEN_SUBJECT_RE = re.compile(r"\bopen\s+(?P<subject>[A-Za-z0-9_]+)\s+at\s+world\b")

# Byte-order mark, built via chr() so this source file stays 7-bit ASCII.
_BOM = chr(0xFEFF)


@dataclass(frozen=True)
class LogLine:
    """One parsed UE log line.

    ``timestamp`` is timezone-aware and always UTC. ``verbosity`` is ``None``
    when the line carried no verbosity word. ``message`` has trailing
    whitespace stripped - the game emits a trailing space on many lines - but
    internal whitespace is left exactly as written, because the double-space
    quirk is load-bearing evidence about the emitting code.
    """

    timestamp: datetime
    frame: int
    category: str
    verbosity: str | None
    message: str
    raw: str


@dataclass(frozen=True)
class ClassSelectionEvent:
    """The player's class/gender selection was applied."""

    line: LogLine
    class_id: int
    gender: int

    @property
    def class_label(self) -> str | None:
        """Human-readable class name, or ``None`` if the id is unknown."""
        return class_name(self.class_id)


@dataclass(frozen=True)
class WeaponHoldingEvent:
    """An actor was refreshed with a held weapon id."""

    line: LogLine
    actor: str | None
    class_id: int | None
    holding_id: int

    @property
    def class_label(self) -> str | None:
        """Human-readable class name, or ``None`` if the id is unknown."""
        if self.class_id is None:
            return None
        return class_name(self.class_id)


@dataclass(frozen=True)
class MatchStateEvent:
    """Match state transition, e.g. ``NotMatch``."""

    line: LogLine
    state: str


@dataclass(frozen=True)
class MapTransitionEvent:
    """A world/level context was named, e.g. ``CampMap``.

    ``subject`` is whatever was reported as being opened in that world when the
    line names one - typically a widget blueprint - and is ``None`` otherwise.
    """

    line: LogLine
    world: str
    subject: str | None


Event = (
    ClassSelectionEvent | WeaponHoldingEvent | MatchStateEvent | MapTransitionEvent
)


def class_name(class_id: int) -> str | None:
    """Return the class name for ``class_id``, or ``None`` when unknown.

    Deliberately returns ``None`` rather than a synthesised label such as
    ``"Class 16"``. A fabricated name reads as data downstream and outlives the
    memory that it was fabricated.
    """
    return CLASS_NAMES.get(class_id)


def parse_line(text: str) -> LogLine | None:
    """Parse one raw log line. Returns ``None`` for anything unparseable.

    Never raises. Continuation lines, blank lines, banner text and the partial
    trailing line of a live-appended file all return ``None``.
    """
    if not isinstance(text, str):
        return None
    raw = text.rstrip("\r\n")
    candidate = raw.lstrip(_BOM)
    match = _LINE_RE.match(candidate)
    if match is None:
        return None

    try:
        timestamp = datetime(
            int(match["year"]),
            int(match["month"]),
            int(match["day"]),
            int(match["hour"]),
            int(match["minute"]),
            int(match["second"]),
            int(match["milli"]) * 1000,
            tzinfo=UTC,
        )
    except ValueError:
        # A malformed date such as month 13 is junk, not a crash.
        return None

    rest = match["rest"]
    verbosity: str | None = None
    stripped = rest.lstrip()
    verb_match = _VERBOSITY_RE.match(stripped)
    if verb_match is not None and verb_match["word"] in VERBOSITY_WORDS:
        verbosity = verb_match["word"]
        stripped = verb_match["rest"]

    return LogLine(
        timestamp=timestamp,
        frame=int(match["frame"]),
        category=match["category"],
        verbosity=verbosity,
        message=stripped.strip(),
        raw=raw,
    )


def parse_lines(lines: Iterable[str]) -> Iterator[LogLine]:
    """Parse an iterable of raw lines, dropping the unparseable ones."""
    for text in lines:
        parsed = parse_line(text)
        if parsed is not None:
            yield parsed


def _eqeq_fields(message: str) -> dict[str, int]:
    """Collect ``key ==value`` integer pairs, keyed by lowercased name."""
    return {
        m["key"].lower(): int(m["value"]) for m in _EQEQ_RE.finditer(message)
    }


def _dash_fields(message: str) -> dict[str, str]:
    """Collect ``key-value`` pairs, keyed by lowercased name."""
    return {
        m["key"].lower(): m["value"] for m in _DASHKV_RE.finditer(message)
    }


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _event_for(line: LogLine) -> Event | None:
    message = line.message

    if "setClassGender" in message:
        fields = _eqeq_fields(message)
        class_id = fields.get("inclassid")
        gender = fields.get("ingender")
        if class_id is not None and gender is not None:
            return ClassSelectionEvent(line=line, class_id=class_id, gender=gender)
        # The paired "oldClassId ==0, oldgender ==0" line carries no new
        # selection, so it is intentionally not an event.
        return None

    if "holding-" in message:
        fields = _dash_fields(message)
        holding_id = _as_int(fields.get("holding"))
        if holding_id is not None:
            actor_match = _ACTOR_RE.search(message)
            return WeaponHoldingEvent(
                line=line,
                actor=actor_match["actor"] if actor_match else None,
                class_id=_as_int(fields.get("class")),
                holding_id=holding_id,
            )
        return None

    state_match = _MATCH_STATE_RE.search(message)
    if state_match is not None:
        return MatchStateEvent(line=line, state=state_match["state"])

    world_match = _WORLD_RE.search(message)
    if world_match is not None:
        subject_match = _OPEN_SUBJECT_RE.search(message)
        return MapTransitionEvent(
            line=line,
            world=world_match["world"],
            subject=subject_match["subject"] if subject_match else None,
        )

    return None


def iter_events(lines: Iterable[str | LogLine]) -> Iterator[Event]:
    """Yield recognised events from raw lines or already-parsed lines.

    Unrecognised but well-formed lines are skipped silently; this is a
    recogniser, not a validator. Accepts either raw strings or
    :class:`LogLine` instances so a caller can parse once and fan out.
    """
    for item in lines:
        parsed = item if isinstance(item, LogLine) else parse_line(item)
        if parsed is None:
            continue
        event = _event_for(parsed)
        if event is not None:
            yield event
