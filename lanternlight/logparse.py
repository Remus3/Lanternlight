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
    "LevelSwitchEvent",
    "LogLine",
    "MapTransitionEvent",
    "MapUrl",
    "MapUrlEvent",
    "MatchIdEvent",
    "MatchStateEvent",
    "SubLevelEvent",
    "VERBOSITY_WORDS",
    "WeaponConfigEvent",
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

# "OnRep_WeaponCfgId: 30402", "OnRep_WeaponCfgId: 0", "OnRep_WeaponCfgId: -1".
_WEAPON_CFG_RE = re.compile(r"\bOnRep_WeaponCfgId:\s*(?P<value>-?\d+)")

# The token straight after the tag: openLevel, openLevelWithTransition,
# openLevelWithTransition:, openLevelDirect. The character class stops at the
# colon, so the "begin" and bypass shapes report the same verb.
_LEVEL_SWITCH_VERB_RE = re.compile(
    r"\[LevelSwitch\]\s+(?P<verb>[A-Za-z_][A-Za-z0-9_]*)"
)

# Two measured phrasings, "target=/Game/..." and "single-hop to /Game/...".
# The leading slash requires the destination to look like a path. That is
# INERT on the 2026-08-09 log - all 44 lines write a real path, and "delayMs=0"
# on the bypass shape was never a candidate anyway, because "\btarget=" cannot
# match "delayMs=". It is kept for the shape the game's TS layer writes
# elsewhere, "target=undefined", and it is pinned by a constructed test rather
# than by an observed line.
_LEVEL_SWITCH_TARGET_RE = re.compile(
    r"(?:\btarget=|\bsingle-hop\s+to\s+)(?P<target>/\S+)"
)

# The four measured map-URL axes and nothing else - see MapUrl for why this is
# an allowlist rather than a generic key/value sweep. The \d+ stopping before
# the trailing "." that OptionsString appends IS exercised by a real line. The
# lookbehind, which stops a longer key merely ending in one of these names
# (e.g. "submatchId=") from matching, is INERT on the 2026-08-09 log and is
# pinned by a constructed test instead.
_MAP_URL_AXIS_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<key>levelId|roomModeId|matchType|matchId)"
    r"=(?P<value>-?\d+)"
)

# The "/Game/" anchor is load-bearing and is NOT decoration. Relaxing it to a
# bare "/<path>?", or adding re.IGNORECASE, takes this from 36 matching lines
# to 37 on the 2026-08-09 log, and the extra one is a LogUGiftAgent redemption
# URL whose query string carries a redemption key and an access token.
#
# What the leak would look like, measured rather than assumed: the capture
# stops dead at the "?", so on that line MapUrl.target would be the
# 26-character path alone and NO MapUrl field would ever hold the key or the
# token. They would reach a consumer through the LogLine the event embeds -
# .raw and .message carry the whole line, query string included. The hazard is
# therefore a whole extra event on a secrets-bearing line, not a poisoned
# target field. What happens to that line downstream is lanternlight.redact's
# business; this anchor's own job is simply not to promote the line to an
# event in the first place, and that job does not depend on what any other
# module does or does not mask.
#
# The character class is an allowlist of the characters observed in real map
# paths, and no measured map path carries a "-". Three weakenings are INERT on
# the 2026-08-09 log - dropping the trailing slash, truncating to "/G", and
# widening the class to admit "-" each still match exactly the same 36 lines -
# so each is pinned by a constructed test rather than by an observed line.
# Pinned by test_a_non_game_url_with_a_query_is_not_a_map_url and the four
# tests beside it in tests/test_logparse.py.
_MAP_URL_TARGET_RE = re.compile(r"(?P<target>/Game/[A-Za-z0-9_/.]*)\?")

# "..., match id 11111" and "with level id 117,". Irregular whitespace, and
# the unload sublevel shape writes "levelid" with a lower-case d, hence \s*.
_MATCH_ID_RE = re.compile(r"\bmatch\s+id\s+(?P<value>-?\d+)", re.IGNORECASE)
_LEVEL_ID_PROSE_RE = re.compile(r"\blevel\s*id\s+(?P<value>-?\d+)", re.IGNORECASE)

# "unloaded subLevel 0!". The trailing "!" is part of the log, not the value.
_SUBLEVEL_UNLOAD_RE = re.compile(
    r"\bunloaded\s+sublevel\s+(?P<sublevel>[^\s!]+)", re.IGNORECASE
)

# "loadSubLevel WhiteWoods_Level_Easy". The lookbehind matters: the string
# "loadSubLevel" also occurs inside "setUnloadSubLevelSet".
_SUBLEVEL_LOAD_RE = re.compile(
    r"(?<![A-Za-z])loadSubLevel\s+(?P<sublevel>[^\s!]+)"
)

_POST_LOAD_MAP_RE = re.compile(r"\bonPostLoadMap\s+(?P<map>[^\s!]+)")

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

    **This is not a map transition, despite the name.** Measured on the
    2026-08-09 log: ``at world <X>`` matches 4408 lines and **every one of
    them** is category ``TS.UI`` - widget lines such as ``open
    WBP_Dialogue_Battle at world CampMap``. Not most of them; all of them.
    What the line reports is "some widget was handled, and the world it
    happened in was named X". The world name is reliable; the implied
    transition is not, because the same world is named on hundreds of
    consecutive lines while nothing changes.

    The event that really does mean "the map is changing" is
    :class:`LevelSwitchEvent`, which binds to ``[LevelSwitch]`` (44 lines on the
    same log, none of them matched here). Use this type to answer "which world
    is the player in right now"; use ``LevelSwitchEvent`` to answer "did the
    map just change".

    The name is kept as shipped rather than corrected in place, because it is
    public API and renaming it is a separate decision.

    ``subject`` is whatever was reported as being opened in that world when the
    line names one - typically a widget blueprint - and is ``None`` otherwise.
    """

    line: LogLine
    world: str
    subject: str | None


@dataclass(frozen=True)
class WeaponConfigEvent:
    """A replicated weapon config id, from ``OnRep_WeaponCfgId: <id>``.

    270 lines on the measured log, previously recognised as zero events: the
    line carries neither the ``holding-`` nor the ``key ==value`` shape that
    the other two extractors look for.

    ``weapon_cfg_id`` is carried through exactly as written, including the
    observed ``0`` (6 lines) and ``-1`` (2 lines). What those two mean is
    **not measured** - they are not translated into an absence here, because a
    written value is a measurement and an absent field is not.

    Two id widths were observed: five-digit ids that overlap the creation-time
    ``holding-`` ids, and seven-digit ids that do not appear there at all. No
    claim is made that they are one id space.
    """

    line: LogLine
    weapon_cfg_id: int


@dataclass(frozen=True)
class MapUrl:
    """The map path and the four measured axes of a Mistfall Hunter map URL.

    Measured shapes (``ROADMAP.md`` item 1)::

        /Game/Project/Maps/Prologue_New/Prologue_New?levelId=1&roomModeId=9&matchId=0
        /Game/Project/Maps/Map_2/Whitewoods_Day?levelId=117&roomModeId=0&matchType=1&matchId=11111&
        /Game/Project/Maps/CampMap/CampMap?option=GAA=

    ``levelId``, ``roomModeId``, ``matchType`` and ``matchId`` are FOUR
    independent axes. ``matchId`` alone does not discriminate a matchmade run -
    that proxy was refuted, since solo explores carry ``matchId`` 11111 and
    11112 while the Prologue carries 0.

    ``None`` on any axis means **the line did not write that field**, which is
    a different fact from the field being present and zero. ``matchType`` is
    written on the Whitewoods URLs and simply absent from the Prologue ones, so
    defaulting it to 0 would forge a measurement. Use :attr:`axes` when the
    distinction matters: it contains only the keys the line actually carried.

    Only those four keys are ever extracted. That is an allowlist, not an
    oversight, for two measured reasons:

    - **Over-firing.** 1313 lines carry a bare ``id=<digits>`` and 45 more
      carry ``itemId=``/``durability=``. A generic key/value sweep would turn
      every one of them into a map URL - the identical failure mode to
      :class:`MapTransitionEvent` matching 4408 UI lines.
    - **Persona.** Exactly ONE of the five producers appends the player's
      persona to the query string as a further option
      (``TS.Dungeon: DungeonGameMode KN_InitNewPlayer``, 4 lines). The three
      engine producers write the literal ``Player`` instead, which is a
      default and not a persona.

    Anything outside the four axes is left in the raw line for
    ``lanternlight.redact`` to deal with and is never lifted into a field.

    ``target`` is ``None`` for the two producers that log only the query
    string.
    """

    target: str | None = None
    level_id: int | None = None
    room_mode_id: int | None = None
    match_type: int | None = None
    match_id: int | None = None

    @property
    def map_name(self) -> str | None:
        """Last path segment of ``target``, e.g. ``Whitewoods_Day``."""
        if not self.target:
            return None
        return self.target.rstrip("/").rsplit("/", 1)[-1] or None

    @property
    def axes(self) -> dict[str, int]:
        """Only the axes this URL actually carried, under their log names.

        A key that is missing here was missing from the line. A key present
        with value ``0`` was written as zero.
        """
        pairs = (
            ("levelId", self.level_id),
            ("roomModeId", self.room_mode_id),
            ("matchType", self.match_type),
            ("matchId", self.match_id),
        )
        return {key: value for key, value in pairs if value is not None}


@dataclass(frozen=True)
class LevelSwitchEvent:
    """The game's own level switcher was asked to change map.

    Binds to ``TS.Utils: [LevelSwitch] <verb> ...``. This is the real map
    transition, as opposed to :class:`MapTransitionEvent`.

    **One user-visible map change emits four of these.** Measured: 44
    ``[LevelSwitch]`` lines, exactly 11 per verb, for 11 switches - the
    ``openLevel`` entry, the ``openLevelWithTransition begin``, the
    ``openLevelWithTransition:`` bypass decision, and the ``openLevelDirect``
    second hop. A consumer that counts events counts four times too many.

    ``verb`` is the token immediately after ``[LevelSwitch]``, with any
    trailing colon removed, so the ``begin`` and bypass shapes both report
    ``openLevelWithTransition``.
    """

    line: LogLine
    verb: str
    url: MapUrl


@dataclass(frozen=True)
class MapUrlEvent:
    """The engine or the game mode reported a map URL.

    Five producers were measured: ``LogNet: Browse:``,
    ``LogGlobalStatus: UEngine::Browse Started Browse:``, ``LogLoad: LoadMap:``,
    ``TS.Dungeon: [DungeonGameMode]OptionsString:`` and
    ``DungeonGameMode KN_InitNewPlayer ... option:``. The last two log the
    query string alone, so :attr:`MapUrl.target` is ``None`` there.

    ``[LevelSwitch]`` lines also carry a map URL; they yield
    :class:`LevelSwitchEvent` instead, which carries the same :class:`MapUrl`.
    """

    line: LogLine
    url: MapUrl


@dataclass(frozen=True)
class MatchIdEvent:
    """A match id written in prose, e.g. ``..., match id 11111``.

    Four producers were measured, all ``TS.Dungeon``:
    ``getMapActorFilterTagByURL``, ``InitPlayerStartSelect``,
    ``StandaloneLevel requestEnterStandaloneLevel`` and
    ``StandaloneLevel onSEnterStandaloneLevel``. The whitespace is irregular -
    one shape writes ``tag is  with level id 0`` with a doubled space.

    ``level_id`` is ``None`` when the line did not write one, which is the
    normal case for two of the four producers.

    Deliberately not extracted: ``battleId``, a long opaque server-side run
    identifier that appears on one of these shapes. Its sensitivity has not
    been assessed, so it is neither carried into an event nor committed as a
    fixture.
    """

    line: LogLine
    match_id: int
    level_id: int | None


@dataclass(frozen=True)
class SubLevelEvent:
    """A sublevel was loaded or unloaded.

    Two transition shapes were measured::

        setUnloadSubLevelSet with mapResCfg levelid 1 unloaded subLevel 0!
        MapSelector: onPostLoadMap Whitewoods_Day loadSubLevel WhiteWoods_Level_Easy

    Note the casing difference - ``levelid`` on the unload shape - and that the
    unload shape names its sublevel numerically while the load shape names it
    by asset name. ``sublevel`` is therefore a string in both cases rather than
    a number that is only sometimes a number.

    A third shape, ``setUnloadSubLevelSet errors with missing mapResCfg levelId
    0!``, is **deliberately not an event**. It reports a config lookup failure:
    no sublevel is named and none was unloaded, so emitting a transition for it
    would assert something that did not happen.
    """

    line: LogLine
    action: str
    sublevel: str
    map_name: str | None
    level_id: int | None


Event = (
    ClassSelectionEvent
    | WeaponHoldingEvent
    | MatchStateEvent
    | MapTransitionEvent
    | WeaponConfigEvent
    | LevelSwitchEvent
    | MapUrlEvent
    | MatchIdEvent
    | SubLevelEvent
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

    # The frame group is unbounded ``\d+``, so it reaches the 4300-digit cap
    # before any recogniser runs. A header that will not convert is junk.
    frame = _as_int(match["frame"])
    if frame is None:
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
        frame=frame,
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
    """Collect ``key ==value`` integer pairs, keyed by lowercased name.

    A pair whose value will not convert is omitted rather than guessed at, so
    a caller sees the key as absent.
    """
    fields: dict[str, int] = {}
    for match in _EQEQ_RE.finditer(message):
        value = _as_int(match["value"])
        if value is not None:
            fields[match["key"].lower()] = value
    return fields


def _dash_fields(message: str) -> dict[str, str]:
    """Collect ``key-value`` pairs, keyed by lowercased name."""
    return {
        m["key"].lower(): m["value"] for m in _DASHKV_RE.finditer(message)
    }


def _as_int(value: str | None) -> int | None:
    """The module's only integer conversion. Returns ``None`` when unreadable.

    Every ``int()`` in this module goes through here, and none is written
    inline, because CPython 3.11+ refuses ``int(s)`` for more than 4300 digits
    and raises ``ValueError``. A tailer feeds this parser whatever bytes are
    on disk, so a corrupt or adversarial line carrying a long digit run is
    reachable, and both :func:`parse_line` and :func:`iter_events` promise
    never to raise. An unreadable number is treated as an absent one.

    ``sys.set_int_max_str_digits`` is deliberately NOT called: it is a
    process-wide setting and a library has no business changing it.
    """
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _url_axes(message: str) -> dict[str, int]:
    """Collect the four measured map-URL axes that this message carries.

    Keys absent from the return value were absent from the line. Nothing else
    in the query string is read - see :class:`MapUrl`. An axis whose value
    will not convert is omitted too, which collapses "unreadable" into
    "absent" - acceptable here because both mean "no measurement", and the
    alternative is raising inside a tailer.
    """
    axes: dict[str, int] = {}
    for match in _MAP_URL_AXIS_RE.finditer(message):
        value = _as_int(match["value"])
        if value is not None:
            axes[match["key"]] = value
    return axes


def _map_url(target: str | None, axes: dict[str, int]) -> MapUrl:
    """Build a :class:`MapUrl`, leaving unwritten axes as ``None``."""
    return MapUrl(
        target=target,
        level_id=axes.get("levelId"),
        room_mode_id=axes.get("roomModeId"),
        match_type=axes.get("matchType"),
        match_id=axes.get("matchId"),
    )


def _sublevel_event(line: LogLine, message: str) -> SubLevelEvent | None:
    """Recognise a sublevel load or unload, or ``None`` for neither.

    The error shape carries neither a loaded nor an unloaded sublevel name and
    so falls out here rather than being reported as a transition.
    """
    level_id_match = _LEVEL_ID_PROSE_RE.search(message)
    level_id = _as_int(level_id_match["value"]) if level_id_match else None

    unload = _SUBLEVEL_UNLOAD_RE.search(message)
    if unload is not None:
        return SubLevelEvent(
            line=line,
            action="unload",
            sublevel=unload["sublevel"],
            map_name=None,
            level_id=level_id,
        )

    load = _SUBLEVEL_LOAD_RE.search(message)
    if load is not None:
        map_match = _POST_LOAD_MAP_RE.search(message)
        return SubLevelEvent(
            line=line,
            action="load",
            sublevel=load["sublevel"],
            map_name=map_match["map"] if map_match else None,
            level_id=level_id,
        )

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

    weapon_cfg_match = _WEAPON_CFG_RE.search(message)
    if weapon_cfg_match is not None:
        weapon_cfg_id = _as_int(weapon_cfg_match["value"])
        if weapon_cfg_id is None:
            # The only field this event has is unreadable, so there is no
            # event - inventing a number would be worse than reporting none.
            return None
        return WeaponConfigEvent(line=line, weapon_cfg_id=weapon_cfg_id)

    if "[LevelSwitch]" in message:
        # Checked before the generic map-URL branch below: 8 of the 44
        # [LevelSwitch] lines also carry the axes, and they are switches.
        verb_match = _LEVEL_SWITCH_VERB_RE.search(message)
        target_match = _LEVEL_SWITCH_TARGET_RE.search(message)
        if verb_match is not None and target_match is not None:
            return LevelSwitchEvent(
                line=line,
                verb=verb_match["verb"],
                url=_map_url(target_match["target"], _url_axes(message)),
            )
        # A [LevelSwitch] line with no target names no map. Reporting a switch
        # to nowhere would be worse than reporting nothing.
        return None

    # "match state changed to" is checked before "match id". No line on the
    # 2026-08-09 log carries both tokens, so this ordering is inert there and
    # a reorder passes every observed-line test in the suite; it is pinned by
    # a constructed test instead.
    state_match = _MATCH_STATE_RE.search(message)
    if state_match is not None:
        return MatchStateEvent(line=line, state=state_match["state"])

    match_id_match = _MATCH_ID_RE.search(message)
    if match_id_match is not None:
        match_id = _as_int(match_id_match["value"])
        if match_id is None:
            return None
        level_match = _LEVEL_ID_PROSE_RE.search(message)
        return MatchIdEvent(
            line=line,
            match_id=match_id,
            level_id=_as_int(level_match["value"]) if level_match else None,
        )

    if "SubLevel" in message:
        return _sublevel_event(line, message)

    axes = _url_axes(message)
    url_target_match = _MAP_URL_TARGET_RE.search(message)
    if axes or url_target_match is not None:
        return MapUrlEvent(
            line=line,
            url=_map_url(
                url_target_match["target"] if url_target_match else None, axes
            ),
        )

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
