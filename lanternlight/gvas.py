"""Read Mistfall Hunter's Unreal GVAS save files.

The game writes five files into ``%LOCALAPPDATA%/MistfallHunter/Saved/
SaveGames/``. Measured 2026-08-09, all five plain, unencrypted UE GVAS with
magic ``47 56 41 53``::

    CampData_<19-digit userId>.sav    1986 bytes
    EnhancedInputUserSettings.sav     2603
    LoginOptions.sav                  2067
    Notice.sav                        1968
    UserSettings_v1.sav               2668

This module only ever reads them. The save directory is operator data, and a
reader that writes into it is a bug with a permanent cost.

Why this is written here rather than vendored
---------------------------------------------

GVAS parsers exist, but the property tag in this build is **not** the layout
those parsers implement. Unreal 5.4 replaced ``FPropertyTag``'s
``FName Type; int32 Size; int32 ArrayIndex`` with a recursive type name and a
flags byte, and every published GVAS reader written against UE4 desynchronises
on the first property. Vendoring one would also have meant a license review for
a few hundred lines of struct unpacking.

The format, as measured off the real files
------------------------------------------

Header, identical in all five::

    b"GVAS"                        magic
    int32   save_game_version      3
    int32   package_file_ue4       522
    int32   package_file_ue5       1018
    uint16  engine major/minor/patch, uint32 changelist, FString branch
                                   5.7.4-0, branch "UE5"
    int32   custom_version_format  3 (Optimized)
    int32   custom_version_count   88
    88 x   (16-byte GUID, int32 version)
    FString save_game_class_name

``FString`` is a signed length that INCLUDES the NUL terminator. Positive means
ANSI, negative means UTF-16LE with the length in characters.

Then one ``uint8`` tag-extension byte - measured ``0x00`` in all five files -
followed by tagged properties, each::

    FString name                   "None" ends the list
    FString type name
    int32   type parameter count, then that many nested type names
    int32   value size in bytes
    uint8   flags
    [int32  array index]           only when flags & 0x01
    [16     property GUID]         only when flags & 0x02
    size bytes of value

Two things in there are new in UE 5.4 and are why an off-the-shelf parser
fails. The type is a **recursive type name**, so a map spells its key and value
types as parameters rather than as extra tag fields; and ``ArrayIndex`` is now
optional, announced by a flag, while a bool's value is carried in flag bit
``0x10`` with a payload size of zero.

After the ``"None"`` terminator the files carry trailing bytes: exactly four
zero bytes in four of the five, and 627 in ``EnhancedInputUserSettings.sav``,
which serialises its key profiles after its tagged properties and ends with the
literal ``ObjectEnd``. **This module does not decode them.** They are handed
back verbatim as :attr:`GvasSave.trailing` because pretending they are not
there is how a reader starts lying about what a file contains.

Unknown means unknown
---------------------

:func:`parse` **raises** :class:`UnknownPropertyTypeError` on any property type
it has not measured, and on any known type whose value does not decode the way
it was measured to. That is the single most important behaviour in this file. A
partial parse is indistinguishable from a complete one at the call site, so a
reader that skipped what it did not understand would hand Emberforge a save
that looks whole and is not.

The types below are the complete measured set. Each is decoded because it was
observed in one of the five files, and nothing is decoded because it looked
easy:

===================================  =========================  ==============
Type                                 Python                     Seen in
===================================  =========================  ==============
``BoolProperty``                     ``bool``                   UserSettings
``IntProperty``                      ``int``                    LoginOptions
``DoubleProperty``                   ``float``                  UserSettings
``StrProperty``                      ``str``                    Notice
``TextProperty``                     ``str``                    LoginOptions
``MapProperty<IntProperty, ...>``    ``dict[int, int]``         CampData
===================================  =========================  ==============

``FloatProperty``, ``NameProperty``, ``ArrayProperty``, ``StructProperty`` and
the rest are absent from that table on purpose. The encodings are published, but
this project's rule is that a value it has not watched being emitted is not a
value it reports.

``strict=False`` records instead of raising, for the same reason
:mod:`lanternlight.avgprice` offers it: this file is written by a live game and
a poller can catch a torn write. Faced with a parser that only ever raises, the
author of that poller writes ``except Exception: pass`` and drops the whole
save. In that mode an unreadable property is **omitted from**
:attr:`GvasSave.properties` entirely - not ``None``, not ``0`` - and recorded in
:attr:`GvasSave.unknown_properties`, so "unmeasured" stays distinguishable from
"measured zero". Structural damage still raises in both modes, because there is
no way to skip past a length you cannot trust.

Header versions are pinned, not guessed. Only ``save_game_version`` 3 and
``custom_version_format`` 3 have ever been observed here, and both select the
field layout of everything after them, so a different value raises rather than
being parsed on the strength of a published spec nobody has checked against
this game.

Typical use::

    save = load(paths.save_games_dir() / "UserSettings_v1.sav")
    if save.properties.get("bWarehouseAutomation"):
        ...
"""

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "KNOWN_PROPERTY_TYPES",
    "MAGIC",
    "MEASURED_CUSTOM_VERSION_FORMAT",
    "MEASURED_SAVE_GAME_VERSION",
    "CustomVersion",
    "EngineVersion",
    "GvasHeader",
    "GvasParseError",
    "GvasSave",
    "UnknownProperty",
    "UnknownPropertyTypeError",
    "load",
    "parse",
]

#: The four bytes every GVAS file starts with.
MAGIC = b"GVAS"

#: The only ``save_game_version`` observed from this game. It selects the
#: header layout, so a different one is refused rather than guessed at.
MEASURED_SAVE_GAME_VERSION = 3

#: The only ``custom_version_format`` observed. 3 is Unreal's "Optimized"
#: format: a 16-byte GUID and an int32 per entry, and nothing else.
MEASURED_CUSTOM_VERSION_FORMAT = 3

# Property tag flag bits, UE 5.4 and later.
_FLAG_HAS_ARRAY_INDEX = 0x01
_FLAG_HAS_PROPERTY_GUID = 0x02
_FLAG_HAS_EXTENSIONS = 0x04
_FLAG_BINARY_OR_NATIVE = 0x08
_FLAG_BOOL_TRUE = 0x10

# Flags whose effect on the tag layout and on the value has been measured.
_UNDERSTOOD_FLAGS = _FLAG_HAS_ARRAY_INDEX | _FLAG_HAS_PROPERTY_GUID | _FLAG_BOOL_TRUE

# The one tag-extension byte value seen in every file: no extension follows.
_NO_TAG_EXTENSION = 0x00

# FText history type for a culture-invariant literal. It is the only history
# this game has been observed writing, and it is stored as a signed byte.
_TEXT_HISTORY_NONE = 0xFF

#: A type parameter list longer than this is a corrupt length, not a type.
#: Nothing in Unreal's tagged-property format nests anywhere near it.
_MAX_TYPE_PARAMS = 8

#: Recursion cap on nested type names, for the same reason.
_MAX_TYPE_DEPTH = 8


class GvasParseError(ValueError):
    """Raised when a file is not GVAS, is truncated, or is structurally wrong.

    Structural damage raises in both strict and non-strict mode. Once a length
    cannot be trusted there is nothing to skip forward to.
    """


class UnknownPropertyTypeError(GvasParseError):
    """Raised when a property's type or value encoding has not been measured.

    This is the error that keeps a partial parse from masquerading as a
    complete one. ``strict=False`` turns it into an :class:`UnknownProperty`
    record instead of letting it propagate.
    """


@dataclass(frozen=True)
class EngineVersion:
    """The engine version stamped into the save header."""

    major: int
    minor: int
    patch: int
    changelist: int
    branch: str

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.changelist}+{self.branch}"


@dataclass(frozen=True)
class CustomVersion:
    """One entry of the header's custom-version table.

    The GUID is kept as raw bytes rather than formatted. Unreal writes these
    as four little-endian uint32s and the conventional textual rendering of
    that is not obvious from the bytes, so formatting one here would be a
    guess about presentation dressed up as data.
    """

    guid: bytes
    version: int


@dataclass(frozen=True)
class GvasHeader:
    """The fixed part of a GVAS file, before any property."""

    save_game_version: int
    package_file_version_ue4: int
    package_file_version_ue5: int
    engine_version: EngineVersion
    custom_version_format: int
    custom_versions: tuple[CustomVersion, ...]
    save_game_class_name: str


@dataclass(frozen=True)
class UnknownProperty:
    """One property :func:`parse` refused to decode, recorded rather than faked.

    ``offset`` is the byte offset of the property's name in the source, so a
    finding points at the property rather than merely announcing that one
    exists.
    """

    name: str
    type_name: str
    size: int
    offset: int
    reason: str

    def describe(self) -> str:
        """Return a one-line human-readable rendering of this finding."""
        return (
            f"{self.name!r} ({self.type_name}, {self.size} bytes at offset "
            f"{self.offset}): {self.reason}"
        )


@dataclass(frozen=True)
class GvasSave:
    """One parsed save file.

    ``properties`` maps property name to a plain Python value, in the order the
    file wrote them. A property this module could not decode is **absent** from
    it - never ``None`` and never ``0`` - so an empty result and a zero result
    stay different facts.

    ``property_types`` records the rendered type name each decoded property
    came from, so "what was this" survives the decode.

    ``trailing`` is every byte after the ``"None"`` terminator, undecoded. See
    the module docstring.
    """

    header: GvasHeader
    properties: dict[str, object] = field(default_factory=dict)
    property_types: dict[str, str] = field(default_factory=dict)
    unknown_properties: tuple[UnknownProperty, ...] = ()
    trailing: bytes = b""

    @property
    def save_game_class_name(self) -> str:
        """Shorthand for the header's Blueprint class path."""
        return self.header.save_game_class_name

    @property
    def is_complete(self) -> bool:
        """True when every property in the source was decoded.

        Always True for a save returned by a strict parse, because a strict
        parse raises instead of returning an incomplete result.
        """
        return not self.unknown_properties

    @property
    def has_trailing_bytes(self) -> bool:
        """True when bytes followed the property terminator."""
        return bool(self.trailing)


# --------------------------------------------------------------------------
# byte reader
# --------------------------------------------------------------------------


class _Reader:
    """A bounds-checked cursor over the save bytes.

    Every read goes through :meth:`take`, so a corrupt length raises instead of
    asking Python to allocate several hundred megabytes.
    """

    __slots__ = ("data", "offset")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def take(self, count: int) -> bytes:
        if count < 0:
            raise GvasParseError(f"negative read of {count} bytes at offset {self.offset}")
        if count > self.remaining:
            raise GvasParseError(
                f"truncated: wanted {count} bytes at offset {self.offset}, "
                f"only {self.remaining} remain"
            )
        chunk = self.data[self.offset : self.offset + count]
        self.offset += count
        return chunk

    def int32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def uint32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def uint16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def uint8(self) -> int:
        return self.take(1)[0]

    def fstring(self) -> str:
        """Read an FString: signed length including the NUL terminator."""
        start = self.offset
        length = self.int32()
        if length == 0:
            return ""
        if length > 0:
            raw = self.take(length)
            if not raw.endswith(b"\0"):
                raise GvasParseError(f"unterminated ANSI FString at offset {start}")
            body = raw[:-1]
            try:
                return body.decode("ascii")
            except UnicodeDecodeError as exc:
                # The engine only takes the ANSI branch for a pure-ASCII
                # string, so a high byte here means the stream is not what this
                # reader thinks it is - not that the name is exotic.
                raise GvasParseError(
                    f"non-ASCII byte in an ANSI FString at offset {start}"
                ) from exc
        raw = self.take(-length * 2)
        if not raw.endswith(b"\0\0"):
            raise GvasParseError(f"unterminated UTF-16 FString at offset {start}")
        try:
            return raw[:-2].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise GvasParseError(f"undecodable UTF-16 FString at offset {start}") from exc


@dataclass(frozen=True)
class _TypeName:
    """A property type name and its parameters, as UE 5.4 and later spell it."""

    name: str
    params: tuple[_TypeName, ...] = ()

    def render(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}<{', '.join(p.render() for p in self.params)}>"


def _read_type_name(reader: _Reader, depth: int = 0) -> _TypeName:
    if depth > _MAX_TYPE_DEPTH:
        raise GvasParseError(f"type name nested deeper than {_MAX_TYPE_DEPTH}")
    name = reader.fstring()
    count = reader.int32()
    if count < 0 or count > _MAX_TYPE_PARAMS:
        raise GvasParseError(
            f"implausible type parameter count {count} for {name!r} at offset {reader.offset}"
        )
    params = tuple(_read_type_name(reader, depth + 1) for _ in range(count))
    return _TypeName(name=name, params=params)


# --------------------------------------------------------------------------
# value decoders - one per measured type
# --------------------------------------------------------------------------


def _expect_size(type_name: str, value: bytes, size: int) -> None:
    if len(value) != size:
        raise UnknownPropertyTypeError(
            f"{type_name} carried {len(value)} bytes, not the measured {size}"
        )


def _decode_bool(value: bytes, flags: int) -> bool:
    _expect_size("BoolProperty", value, 0)
    return bool(flags & _FLAG_BOOL_TRUE)


def _decode_int(value: bytes, flags: int) -> int:
    _expect_size("IntProperty", value, 4)
    return struct.unpack("<i", value)[0]


def _decode_double(value: bytes, flags: int) -> float:
    _expect_size("DoubleProperty", value, 8)
    return struct.unpack("<d", value)[0]


def _decode_str(value: bytes, flags: int) -> str:
    reader = _Reader(value)
    text = reader.fstring()
    if reader.remaining:
        raise UnknownPropertyTypeError(
            f"StrProperty left {reader.remaining} undecoded trailing bytes"
        )
    return text


def _decode_text(value: bytes, flags: int) -> str:
    reader = _Reader(value)
    reader.int32()  # FText flags; carries no value this module reports
    history = reader.uint8()
    if history != _TEXT_HISTORY_NONE:
        raise UnknownPropertyTypeError(
            f"TextProperty history type {history} has not been measured; only "
            f"{_TEXT_HISTORY_NONE} (none, culture-invariant) has"
        )
    has_culture_invariant = reader.int32()
    if has_culture_invariant != 1:
        raise UnknownPropertyTypeError(
            f"TextProperty culture-invariant flag {has_culture_invariant} has "
            "not been measured; only 1 has"
        )
    text = reader.fstring()
    if reader.remaining:
        raise UnknownPropertyTypeError(
            f"TextProperty left {reader.remaining} undecoded trailing bytes"
        )
    return text


def _decode_int_int_map(value: bytes, flags: int) -> dict[int, int]:
    reader = _Reader(value)
    keys_to_remove = reader.int32()
    if keys_to_remove != 0:
        raise UnknownPropertyTypeError(
            f"MapProperty announced {keys_to_remove} keys to remove; only 0 has "
            "been measured, and the removal encoding is unknown"
        )
    count = reader.int32()
    if count < 0:
        raise UnknownPropertyTypeError(f"MapProperty announced {count} pairs")
    pairs: dict[int, int] = {}
    for _ in range(count):
        key = reader.int32()
        pairs[key] = reader.int32()
    if reader.remaining:
        raise UnknownPropertyTypeError(
            f"MapProperty left {reader.remaining} undecoded trailing bytes"
        )
    return pairs


_DECODERS: dict[str, Callable[[bytes, int], object]] = {
    "BoolProperty": _decode_bool,
    "IntProperty": _decode_int,
    "DoubleProperty": _decode_double,
    "StrProperty": _decode_str,
    "TextProperty": _decode_text,
    "MapProperty<IntProperty, IntProperty>": _decode_int_int_map,
}

#: Every property type this module has measured and will decode. Anything else
#: raises. Adding an entry here is a claim that its encoding was observed, not
#: that it was looked up.
KNOWN_PROPERTY_TYPES: frozenset[str] = frozenset(_DECODERS)


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------


def _read_header(reader: _Reader) -> GvasHeader:
    magic = reader.take(4)
    if magic != MAGIC:
        raise GvasParseError(
            f"not a GVAS file: expected magic {MAGIC!r}, found {magic!r}"
        )

    save_game_version = reader.int32()
    if save_game_version != MEASURED_SAVE_GAME_VERSION:
        raise GvasParseError(
            f"save_game_version {save_game_version} has not been measured for "
            f"this game; only {MEASURED_SAVE_GAME_VERSION} has, and the value "
            "selects the header layout"
        )

    package_ue4 = reader.int32()
    package_ue5 = reader.int32()
    engine = EngineVersion(
        major=reader.uint16(),
        minor=reader.uint16(),
        patch=reader.uint16(),
        changelist=reader.uint32(),
        branch=reader.fstring(),
    )

    custom_version_format = reader.int32()
    if custom_version_format != MEASURED_CUSTOM_VERSION_FORMAT:
        raise GvasParseError(
            f"custom_version_format {custom_version_format} has not been "
            f"measured; only {MEASURED_CUSTOM_VERSION_FORMAT} (optimized) has, "
            "and the value selects the entry layout"
        )
    count = reader.int32()
    if count < 0:
        raise GvasParseError(f"negative custom version count {count}")
    # 20 bytes per entry. Reject a count the file cannot hold before looping,
    # so a corrupt length fails fast instead of after a million iterations.
    if count * 20 > reader.remaining:
        raise GvasParseError(
            f"custom version count {count} needs more bytes than the file has"
        )
    custom_versions = tuple(
        CustomVersion(guid=reader.take(16), version=reader.int32()) for _ in range(count)
    )

    return GvasHeader(
        save_game_version=save_game_version,
        package_file_version_ue4=package_ue4,
        package_file_version_ue5=package_ue5,
        engine_version=engine,
        custom_version_format=custom_version_format,
        custom_versions=custom_versions,
        save_game_class_name=reader.fstring(),
    )


# --------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------


def parse(data: bytes, *, strict: bool = True) -> GvasSave:
    """Parse GVAS bytes into a :class:`GvasSave`.

    Raises :class:`UnknownPropertyTypeError` on the first property whose type
    or value encoding has not been measured. Pass ``strict=False`` to collect
    those into :attr:`GvasSave.unknown_properties` instead; the property is
    then omitted from :attr:`GvasSave.properties` rather than given a stand-in
    value. See the module docstring for why both modes exist.

    :class:`GvasParseError` is raised in either mode for a file that is not
    GVAS, is truncated, carries a header version this reader has not measured,
    or announces a length it cannot honour.
    """
    reader = _Reader(data)
    header = _read_header(reader)

    extension = reader.uint8()
    if extension != _NO_TAG_EXTENSION:
        raise GvasParseError(
            f"property tag extension {extension:#04x} has not been measured; "
            f"only {_NO_TAG_EXTENSION:#04x} (none) has, and an extension "
            "changes the length of every tag that follows"
        )

    properties: dict[str, object] = {}
    property_types: dict[str, str] = {}
    unknowns: list[UnknownProperty] = []

    while True:
        name_offset = reader.offset
        name = reader.fstring()
        if name == "None":
            break
        if name in properties or any(u.name == name for u in unknowns):
            # A tagged property stream does not repeat a name, so a repeat
            # means this is not the stream it appears to be. Overwriting the
            # earlier value would lose a measurement without saying so.
            raise GvasParseError(
                f"property {name!r} appears twice, the second time at offset {name_offset}"
            )

        type_name = _read_type_name(reader).render()
        size = reader.int32()
        if size < 0:
            raise GvasParseError(
                f"negative value size {size} for {name!r} at offset {name_offset}"
            )
        flags = reader.uint8()

        if flags & _FLAG_HAS_EXTENSIONS:
            # An extension block of unmeasured length follows the tag. Nothing
            # after it can be located, so there is no partial answer to give.
            raise GvasParseError(
                f"property {name!r} at offset {name_offset} announces a tag "
                "extension block, whose layout has not been measured"
            )
        unsupported = flags & ~(_UNDERSTOOD_FLAGS | _FLAG_BINARY_OR_NATIVE)
        if unsupported:
            # An unmeasured flag bit can add fields to the tag itself, so the
            # stream position after it is unknown and there is nothing safe to
            # skip to. Structural, therefore fatal in both modes.
            raise GvasParseError(
                f"property {name!r} at offset {name_offset} carries unmeasured "
                f"tag flags {unsupported:#04x}"
            )
        if flags & _FLAG_HAS_ARRAY_INDEX:
            reader.int32()
        if flags & _FLAG_HAS_PROPERTY_GUID:
            reader.take(16)

        value_bytes = reader.take(size)

        try:
            if flags & _FLAG_BINARY_OR_NATIVE:
                raise UnknownPropertyTypeError(
                    f"{type_name} was written with a native serializer, whose "
                    "layout differs from the tagged one measured here"
                )
            decoder = _DECODERS.get(type_name)
            if decoder is None:
                raise UnknownPropertyTypeError(
                    f"property type {type_name} has not been measured for this "
                    f"game; measured types are {', '.join(sorted(KNOWN_PROPERTY_TYPES))}"
                )
            value = decoder(value_bytes, flags)
        except UnknownPropertyTypeError as exc:
            if strict:
                raise UnknownPropertyTypeError(
                    f"{name!r} at offset {name_offset}: {exc}"
                ) from exc
            unknowns.append(
                UnknownProperty(
                    name=name,
                    type_name=type_name,
                    size=size,
                    offset=name_offset,
                    reason=str(exc),
                )
            )
            continue

        properties[name] = value
        property_types[name] = type_name

    return GvasSave(
        header=header,
        properties=properties,
        property_types=property_types,
        unknown_properties=tuple(unknowns),
        trailing=reader.take(reader.remaining),
    )


def load(path: Path | str, *, strict: bool = True) -> GvasSave:
    """Read and parse the save file at ``path``.

    A missing file raises ``FileNotFoundError`` rather than returning an empty
    save. "The file is not there" and "the file is there and holds nothing" are
    different facts about the install.

    This function never writes to ``path`` and never holds it open beyond the
    read.
    """
    return parse(Path(path).read_bytes(), strict=strict)
