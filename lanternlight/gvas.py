"""Read - and write back - Mistfall Hunter's Unreal GVAS save files.

The game writes into ``%LOCALAPPDATA%/MistfallHunter/Saved/SaveGames/``.
Measured 2026-08-09, seven files, all plain unencrypted UE GVAS with magic
``47 56 41 53``::

    CampData_<19-digit userId>.sav       1986 bytes
    Deck.sav                             2001
    EnhancedInputUserSettings.sav        2603
    LoginOptions.sav                     2067
    Notice.sav                           1968
    StandaloneSlot_<19-digit roleId>.sav 2190 and climbing
    UserSettings_v1.sav                  2668

**That list is a snapshot, not the set.** Every part of it has moved under
observation: ``Deck.sav`` did not exist when this module was written and
appeared mid-session; ``UserSettings_v1.sav`` was 2668 bytes when captured and
2713 an hour later; and ``StandaloneSlot`` went from 2190 bytes to 172823
during a single run, gaining four whole top-level properties on the way,
because it is the live in-run level save and the operator was playing. A caller
that expects a known list of filenames, or a known size, is writing down a
guess about a live directory. Enumerate it.

That growth is not a curiosity, it is the reason this reader raises. 249
generations of ``StandaloneSlot`` were captured while the game wrote it, and a
property type that had never appeared in the first 200 - a ``MapProperty``
keyed by ``DoubleProperty`` - turned up in the rest. The reader refused it,
which is how it got measured instead of being silently misread.

**This module never writes to the game's save directory.** :func:`serialise`
returns bytes and nothing here opens a file for writing at all. The save
directory is operator data, and a module that writes into it is a bug with a
permanent cost.

The writer, and why identity is the only acceptable oracle
----------------------------------------------------------

:func:`serialise` is the inverse of :func:`parse`, and the contract is
byte-for-byte::

    serialise(parse(raw)) == raw

Measured 2026-08-10 across three corpora and holding for every file in all
three: the 6 committed fixtures, the 7 live saves on the machine that has the
game, and all 263 captured generations of the transient ``StandaloneSlot``
save, 105 distinct sizes, largest 177878 bytes. 276 files, 276 identical.

Identity is the oracle because nothing weaker catches a field the READER
dropped. Every assertion about a decoded value passes just as happily when a
tag field went in the bin on the way past, and re-emitting is the only thing
that notices. It found one immediately: ``TextProperty``'s int32 flags word,
read and discarded since this module was written, worth 2 in all 276 files.
It is on :class:`TextValue` now.

Retaining what a decoder had no use for
---------------------------------------

Four things had to start being kept, and one turned out not to need keeping:

* the STRUCTURED type name. :meth:`TypeName.render` is one-way - nothing can
  split ``MapProperty<IntProperty, IntProperty>`` back into the FStrings and
  parameter counts the engine wrote without guessing.
* the ``FText`` flags word, above.
* ``ArrayIndex`` and the per-property GUID, which the reader used to skip.
  Neither is set by a single property in any of the 276 files - no tag anywhere
  carries flag ``0x01`` or ``0x02`` - and they are retained anyway, because a
  reader that silently drops a field the format has is the failure this whole
  module is built against.
* the tag's flags BYTE, which is deliberately **not** kept. Every bit of it is
  implied by something that is - see :class:`Property` - and storing a second
  copy of four facts is how an edit writes a file that says the opposite of
  what the object says.

Why a writer at all
-------------------

A sanitised fixture has to SHORTEN identifier strings, because the repository's
``LONG_ID`` detector fires on any run of 15 or more digits and a same-length
substitution does not help; and it has to DROP map entries, because the
transient save reaches 177878 bytes. Both move byte lengths, so every enclosing
property ``Size`` and every container count moves with them - about a hundred
of them, nested five levels deep, for one edit. Hand-patching those is exactly
the fragile move this repository has already been burned by. :func:`serialise`
recomputes all of them from bytes that already exist, so they are right by
construction rather than by inspection. :func:`transform` and :func:`rebuild`
are the supported ways to make the edit.

The writer RAISES rather than emitting a near-miss, for the same reason
:func:`parse` does. A file that parses and is subtly wrong is worse than no
file, because it looks like evidence. Anything it cannot account for -
a property a non-strict parse refused and whose bytes are therefore gone, a
value that does not match the type name describing it, a non-ASCII string
(the engine's UTF-16 FString branch is real and not one of the 671318 non-empty
FStrings measured takes it) - is a :class:`GvasSerialiseError`.

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

Header, identical in all six::

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

Then one ``uint8`` tag-extension byte - measured ``0x00`` in all six files -
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

After the ``"None"`` terminator
------------------------------

Every file but one carries exactly four bytes there;
``EnhancedInputUserSettings.sav`` carries 627. The whole 627 decodes, and the
grammar is::

    4 bytes                        epilogue - see below
    int32                          section header, 2 here, NOT the object count
    int32                          object count, 1 here
    per object:
      FString class path           "/Script/EnhancedInput.EnhancedPlayerMappableKeyProfile"
      FString instance name        "EnhancedPlayerMappableKeyProfile_<uniqueness suffix>"
      int32   key mapping count    3 here
      per mapping:
        FString mapping name       "KB_Blackarrow_Major_Action"
        FString x3                 FName-shaped key slots, "None" when unbound
        6 bytes                    undecoded, zero in all three rows
      FString profile identifier   "InputUserSettings.Profiles.Default"
      uint8   tag extension byte   0, exactly as the outer object writes it
      tagged properties            the same tag layout as the outer object
      FString "None"
      4 bytes                      epilogue again
      FString "ObjectEnd"          sentinel; the only end-of-object marker there is

That grammar lands exactly on the end of the file, and :func:`parse` raises if
it does not - a section it cannot consume whole is a section it has misread.
Slot 0 of a mapping is corroborated out of band: the game log writes
``decode key mapping KB_Blackarrow_Major_Action <key>``, pairing the same
mapping names with the same slot the reader reads. The key itself is the
operator's own configuration, so it is not written down here or carried in the
fixture - what is measured is the pairing, not which button they chose.

**The four-byte epilogue is not identified, and it is not padding.** It follows
*every* tagged property list, not only the file's last one: the nested key
profile carries its own, 21 bytes before EOF rather than at it. Seven
occurrences observed - one per file plus the nested object - and all seven are
zero. An int32 zero fits, an empty FString fits, four zero flag bytes fit, and
nothing observed tells those readings apart, so it is handed back as
:attr:`GvasSave.epilogue` and left unnamed. The section header is unidentified
for the same reason, with
one thing ruled out: it is **not** the object count, because reading it as one
demands a second object and the block ends on the first sentinel with nothing
to spare.

:attr:`GvasSave.trailing` still hands back every one of those bytes verbatim
regardless, because pretending they are not there is how a reader starts lying
about what a file contains.

Unknown means unknown
---------------------

:func:`parse` **raises** :class:`UnknownPropertyTypeError` on any property type
it has not measured, and on any known type whose value does not decode the way
it was measured to. That is the single most important behaviour in this file. A
partial parse is indistinguishable from a complete one at the call site, so a
reader that skipped what it did not understand would hand Emberforge a save
that looks whole and is not.

The types below are the complete measured set. Each is decoded because it was
observed in one of those files, and nothing is decoded because it looked
easy:

===================================  =========================  ==============
Type                                 Python                     Seen in
===================================  =========================  ==============
``BoolProperty``                     ``bool``                   UserSettings
``IntProperty``                      ``int``                    LoginOptions
``DoubleProperty``                   ``float``                  UserSettings
``StrProperty``                      ``str``                    Notice
``ByteProperty<Enum>``               ``str`` enumerator name    StandaloneSlot
``TextProperty`` history ``0xff``    ``str``                    LoginOptions
``TextProperty`` history ``0x00``    :class:`SourceText`        EnhancedInput
``StructProperty``                   ``dict[str, object]``      StandaloneSlot
``StructProperty`` flag ``0x08``     :class:`UndecodedStruct`   StandaloneSlot
``MapProperty<K, V>``                ``dict``                   CampData, Deck
``ArrayProperty<E>``                 ``tuple``                  StandaloneSlot
===================================  =========================  ==============

That is the complete set of type names present: grepping all seven files for
``[A-Za-z]+Property`` yields ``Array``, ``Bool``, ``Byte``, ``Double``,
``Int``, ``Map``, ``Str``, ``Struct`` and ``Text`` and nothing else.
``FloatProperty``, ``NameProperty``, ``SetProperty``, ``ObjectProperty`` and
the rest are absent from the table on purpose. Their encodings are published,
but this project's rule is that a value it has not watched being emitted is not
a value it reports - and an unused parser branch is an untested claim about a
file nobody has.

Nested values, and where the measurement actually stops
-------------------------------------------------------

``StandaloneSlot`` is the first save here that nests. A ``StructProperty``'s
value is a nested tagged property list closed by the FString ``"None"``, in
exactly the outer grammar, with **no epilogue** and no length of its own - the
enclosing tag's ``Size`` is what bounds it. Containers hold their elements
**bare**: a map is keys-to-remove, a count, then that many key/value pairs with
no tag, no flags and no ``Size`` between them, and an array is a count then its
elements, with none of the inner struct header UE4 used to write.

Because containers are decoded generically over their element types rather than
by a pinned rendered name, this reader decodes *compositions* of measured
pieces - it will read an ``ArrayProperty<IntProperty>`` that no capture
contains, because the array header and a bare ``IntProperty`` were each
measured separately. Two things keep that from being a guess dressed up as a
measurement. :data:`MEASURED_BARE_TYPES` and :data:`MEASURED_MAP_KEY_TYPES`
refuse an element type nobody has watched in that POSITION, which is a real
distinction - a tagged ``BoolProperty`` has a zero-byte payload and lives in
flag ``0x10``, so a bare one cannot be the same thing. And every value is
decoded through a reader sliced to exactly the property's ``Size``, so a
composition that is wrong stops short or overruns and is reported instead of
being believed. Across 249 captured generations, every value landed exactly on
its bound.

What is **not** decoded is the natively serialised struct. ``Vector``,
``Vector2D``, ``Quat`` and ``Rotator`` carry tag flag ``0x08``, their payload
is not a property list, and this module hands the bytes back as an
:class:`UndecodedStruct` naming the struct rather than reading numbers out of
them. 24 bytes divides by 8 three times and the samples look like world
coordinates, and none of that is the file saying so - ``Vector`` and
``Rotator`` are both 24 bytes and mean different things.

The two ``TextProperty`` rows are two encodings behind one type name, and both
were observed. The invariant history is a bare string; the source history
writes a namespace, a localisation key and the source text, and decodes to a
:class:`SourceText` - a ``str`` carrying the other two, so no caller has to
branch on Unreal's text serialisation to read a label and no measured string is
dropped.

``strict=False`` records instead of raising, for the same reason
:mod:`lanternlight.avgprice` offers it: this file is written by a live game and
a poller can catch a torn write. Faced with a parser that only ever raises, the
author of that poller writes ``except Exception: pass`` and drops the whole
save. In that mode an unreadable property is **omitted from**
:attr:`GvasSave.properties` entirely - not ``None``, not ``0`` - and recorded in
:attr:`GvasSave.unknown_properties`, so "unmeasured" stays distinguishable from
"measured zero". Structural damage still raises in both modes, because there is
no way to skip past a length you cannot trust.

A property is decoded whole or not at all, however deep it goes. An unmeasured
value five levels down inside ``MonsterData`` makes ``MonsterData`` unknown; it
does not yield a dict quietly missing a field, because a caller cannot tell a
dict with a field missing from a dict that never had one.

Header versions are pinned, not guessed. Only ``save_game_version`` 3 and
``custom_version_format`` 3 have ever been observed here, and both select the
field layout of everything after them, so a different value raises rather than
being parsed on the strength of a published spec nobody has checked against
this game.

Two views of one save
---------------------

:attr:`GvasSave.properties` is the reader's view: plain Python values keyed by
name, which is what every caller in this repository wants.
:attr:`GvasSave.property_list` is the writer's view: one :class:`Property` per
tag, in file order, carrying the type structure and the tag fields. Both come
out of the SAME walk, so they cannot disagree about what the file said.

They can disagree about what an EDIT said, which is why
``dataclasses.replace(save, property_list=...)`` is not the way to make one -
it would leave the plain dict describing a save that no longer exists.
:func:`rebuild` recomputes the derived views, and :func:`transform` is
:func:`rebuild` with a walk over every property at every depth in front of it.

Typical use::

    save = load(paths.save_games_dir() / "UserSettings_v1.sav")
    if save.properties.get("bWarehouseAutomation"):
        ...

and, to author a sanitised copy::

    def sanitise(path, prop):
        if prop.type_name.name == "StrProperty" and prop.value.isdigit():
            return replace(prop, value="<LONG_ID>")
        return prop

    Path("fixture.sav").write_bytes(serialise(transform(load(source), sanitise)))
"""

import struct
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

__all__ = [
    "EPILOGUE_SIZE",
    "KNOWN_PROPERTY_TYPES",
    "MAGIC",
    "MAX_VALUE_DEPTH",
    "MEASURED_BARE_TYPES",
    "MEASURED_CUSTOM_VERSION_FORMAT",
    "MEASURED_CULTURE_INVARIANT_FLAG",
    "MEASURED_MAP_KEY_TYPES",
    "MEASURED_NATIVE_STRUCTS",
    "MEASURED_SAVE_GAME_VERSION",
    "MEASURED_TEXT_HISTORIES",
    "MEASURED_TRAILING_OBJECT_CLASS",
    "ArrayValue",
    "CustomVersion",
    "EngineVersion",
    "GvasHeader",
    "GvasParseError",
    "GvasSave",
    "GvasSerialiseError",
    "KeyMapping",
    "KeyProfile",
    "MapValue",
    "Property",
    "SourceText",
    "StructValue",
    "TextValue",
    "TypeName",
    "UndecodedStruct",
    "UnknownProperty",
    "UnknownPropertyTypeError",
    "load",
    "parse",
    "rebuild",
    "serialise",
    "transform",
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

# FText history bytes. 0xff is a culture-invariant literal with no localisation
# identity; 0x00 is a text that carries its own namespace, key and source
# string. Both were observed - 0xff in LoginOptions' SelectedServer, 0x00 in
# the key profile's DisplayName inside EnhancedInputUserSettings' trailing
# block - and nothing else has been.
_TEXT_HISTORY_NONE = 0xFF
_TEXT_HISTORY_SOURCE = 0x00

#: FText history bytes whose payload layout has been measured. Pinned for the
#: same reason :data:`KNOWN_PROPERTY_TYPES` is: a history is added because it
#: was watched being emitted, never because a spec lists it.
MEASURED_TEXT_HISTORIES: frozenset[int] = frozenset(
    {_TEXT_HISTORY_SOURCE, _TEXT_HISTORY_NONE}
)

#: The only value the invariant history's culture-invariant flag has been
#: observed carrying. :func:`parse` refuses any other, which is what lets
#: :func:`serialise` write this constant back rather than having to retain it:
#: a save that reached a :class:`GvasSave` at all had a 1 here.
MEASURED_CULTURE_INVARIANT_FLAG = 1

#: Bytes of epilogue written after every tagged-property ``"None"``
#: terminator. See :attr:`GvasSave.epilogue` for what is and is not known
#: about them.
EPILOGUE_SIZE = 4

#: The only object class observed in a save's trailing object section. The
#: body layout is measured per class, so a different one is refused rather
#: than parsed as this one.
MEASURED_TRAILING_OBJECT_CLASS = "/Script/EnhancedInput.EnhancedPlayerMappableKeyProfile"

#: The literal FString that closes a trailing object.
_OBJECT_END = "ObjectEnd"

#: FName-shaped slots per key mapping row. Fixed: the row carries no count,
#: and this is the only width on which the block lands exactly on its end.
_KEY_SLOTS = 3

#: Undecoded bytes closing each key mapping row. See :class:`KeyMapping`.
_KEY_MAPPING_TAIL = 6

#: Smallest a serialised trailing object can be: two FStrings, a count, an
#: identifier, a tag-extension byte, a "None", an epilogue and the sentinel.
#: Used only to reject a count the block cannot hold before looping on it.
_MIN_TRAILING_OBJECT = 40

#: Smallest a container element can be in any measured position: an int32, or
#: an empty FString's length. Used only to reject an element count the value
#: cannot possibly hold before looping on it.
_MIN_CONTAINER_ELEMENT = 4

#: A type parameter list longer than this is a corrupt length, not a type.
#: Nothing in Unreal's tagged-property format nests anywhere near it.
_MAX_TYPE_PARAMS = 8

#: Recursion cap on nested type names, for the same reason.
_MAX_TYPE_DEPTH = 8

#: Recursion cap on nested VALUES - a struct inside a struct inside a map.
#: Measured maximum in ``StandaloneSlot_<roleId>.sav`` on 2026-08-09 is 5
#: property-list levels; this is that with headroom, and exists only so a
#: corrupt length cannot recurse until the interpreter dies. Reaching it is a
#: structural failure, not an unmeasured type.
MAX_VALUE_DEPTH = 32

#: Types measured OUTSIDE a property tag - as a map key, a map value or an
#: array element, where there is no tag, no flags and no Size.
#:
#: Position matters because it changes the encoding. A tagged ``BoolProperty``
#: has a zero-byte payload and carries its value in flag ``0x10``; a bare one
#: would have to spell its value some other way, and nothing has been observed
#: doing so. ``ByteProperty`` and ``TextProperty`` are absent for the same
#: reason: measured under a tag, never bare.
MEASURED_BARE_TYPES: frozenset[str] = frozenset(
    {"IntProperty", "DoubleProperty", "StrProperty", "StructProperty"}
)

#: Types measured as a ``MapProperty`` KEY. Narrower than
#: :data:`MEASURED_BARE_TYPES` on purpose - a struct has been observed as a map
#: value and never as a map key, and a dict cannot hold an unhashable one
#: anyway, so letting one through would turn a parse error into a ``TypeError``
#: from somewhere much less informative.
#:
#: ``DoubleProperty`` looks wrong for a key and is not. ``DropItemMap`` is
#: keyed by one, and the keys observed were 5.0, 6.0, 30.0, 32.0, 35.0 and 38.0
#: - integer item ids carried as doubles. The save class is
#: ``.../TypeScript/module/Level/StandaloneLevelSaveData``, and a TypeScript
#: number is a double, so this is the game's scripting layer showing through
#: rather than a misread. Callers should know that Python hashes ``35.0`` and
#: ``35`` alike, so ``m[35]`` finds such a key.
MEASURED_MAP_KEY_TYPES: frozenset[str] = frozenset(
    {"IntProperty", "StrProperty", "DoubleProperty"}
)

#: Struct types observed written through a native serializer (tag flag
#: ``0x08``), whose payload is therefore NOT a tagged property list.
#:
#: This set is a record, not a gate. It does not decide anything: a native
#: struct is handed back whole whatever its name, because the tag's Size bounds
#: the payload exactly and returning opaque bytes is never a guess. Payload
#: sizes observed on 2026-08-09 were 24 bytes for ``Vector``, 24 for
#: ``Rotator``, 32 for ``Quat`` and 16 for ``Vector2D``. Those are byte COUNTS
#: and nothing more - they are not a claim that the fields are doubles, and
#: this module does not make one. ``Vector`` and ``Rotator`` sharing a count is
#: the reason why: two different meanings behind identical bytes, told apart
#: only by the name.
MEASURED_NATIVE_STRUCTS: frozenset[str] = frozenset(
    {"Vector", "Vector2D", "Quat", "Rotator"}
)


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


class GvasSerialiseError(ValueError):
    """Raised when :func:`serialise` cannot write a byte it can account for.

    Deliberately not a subclass of :class:`GvasParseError` - reading a damaged
    file and being handed an object that cannot be written are different
    failures with different fixes, and a caller catching one should not
    accidentally swallow the other.

    Every raise from the writer means the same thing: something in the tree
    would have to be guessed at. A near-miss that parses is worse than a raise,
    because the whole point of this writer is that a sanitised fixture's
    lengths are correct by construction rather than by inspection.
    """


class SourceText(str):
    """An ``FText`` that carried its own localisation identity.

    The engine writes two ``FText`` shapes here. The culture-invariant one
    (history ``0xff``) is a bare string and decodes to a plain :class:`str`.
    The source history (``0x00``) writes three strings - a namespace, a
    localisation key, and the source text itself - and this class is the second
    one: a ``str`` holding the source text, with the other two attached.

    It subclasses ``str`` on purpose. Returning a bespoke record for one
    history and a ``str`` for the other would make every caller branch on a
    detail of Unreal's text serialisation before it could read a label, and
    returning only the source string would silently drop two measured values.
    ``isinstance(value, SourceText)`` is the honest test for "did this text
    carry a namespace and a key"; ``==``, formatting and every other ``str``
    operation behave exactly as they do for the invariant history.
    """

    namespace: str
    key: str

    def __new__(cls, source: str, *, namespace: str, key: str) -> SourceText:
        text = super().__new__(cls, source)
        text.namespace = namespace
        text.key = key
        return text

    def __repr__(self) -> str:
        return (
            f"SourceText({str.__str__(self)!r}, namespace={self.namespace!r}, "
            f"key={self.key!r})"
        )


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
class UndecodedStruct:
    """A struct the engine wrote natively, handed back whole and named as such.

    Three struct types in ``StandaloneSlot_<roleId>.sav`` carry tag flag
    ``0x08``: ``Vector``, ``Vector2D`` and ``Quat``. That flag says the value
    went through a native serializer, so the payload is **not** a tagged
    property list and there is nothing inside it to read. What the file does
    state is the payload's exact length, because the tag's ``Size`` bounds it -
    so handing the bytes back is a fact, and this class is that fact with the
    struct's identity attached.

    It is deliberately not a tuple of numbers. 24 bytes divides by 8 three
    times, the sampled values read as plausible world coordinates, and a
    sampled ``Quat`` has unit norm - none of which is the file saying so. A
    caller that wants those numbers can take :attr:`data` and say out loud that
    it is guessing; a caller that gets a ``dict`` from a decoded struct and an
    ``UndecodedStruct`` from this one cannot confuse the two by accident.

    ``struct_path`` is the package path the type name carried, which is what
    distinguishes ``/Script/CoreUObject`` ``Vector`` from any Blueprint struct
    that happens to share the name.
    """

    struct_name: str
    struct_path: str
    data: bytes

    def describe(self) -> str:
        """Return a one-line human-readable rendering of this value."""
        return (
            f"{self.struct_name} ({self.struct_path}): {len(self.data)} bytes "
            "left undecoded, written by a native serializer"
        )


@dataclass(frozen=True)
class KeyMapping:
    """One row of a key profile's mapping table.

    ``name`` is the mapping's name and ``key_names`` the three FName-shaped
    slots that follow it. Unreal's unbound-key sentinel is the *string*
    ``"None"``, and that is what this reports - translating it to Python
    ``None`` would turn a measured "no key bound here" into something a caller
    reads as "not measured".

    Only slot 0 has ever been observed carrying a key. The game log names the
    same pairs slot 0 holds ("decode key mapping KB_Blackarrow_Major_Action
    <key>"), which is what binds slot 0 to a real binding; slots 1 and 2 are
    named by position and have never been seen holding anything. Which key the
    operator bound is their own configuration and is not recorded here - the
    measured fact is that the log's pairing and slot 0 agree.

    ``undecoded`` is the six bytes that close the row, zero in all three rows
    of the only capture. An empty FString plus two bytes fits them, an int32
    plus two bytes fits them, and six flag bytes fit them. Nothing observed
    separates those readings, so the bytes are handed back rather than named.
    """

    name: str
    key_names: tuple[str, ...]
    undecoded: bytes


@dataclass(frozen=True)
class KeyProfile:
    """One object serialised into a save's trailing section.

    Structurally this is a whole nested object: a class path, an instance
    name, its natively written body, and then a tagged property list closed by
    the same ``"None"`` terminator and four-byte epilogue the outer file uses.

    ``properties`` follows exactly the contract :class:`GvasSave` sets - a
    property this reader could not decode is absent from it rather than
    ``None``, and recorded in ``unknown_properties``.
    """

    class_path: str
    object_name: str
    identifier: str
    mappings: tuple[KeyMapping, ...] = ()
    properties: dict[str, object] = field(default_factory=dict)
    property_types: dict[str, str] = field(default_factory=dict)
    unknown_properties: tuple[UnknownProperty, ...] = ()
    epilogue: bytes = b""
    property_list: tuple[Property, ...] = ()

    @property
    def is_complete(self) -> bool:
        """True when every property in this object was decoded."""
        return not self.unknown_properties


@dataclass(frozen=True)
class GvasSave:
    """One parsed save file.

    ``properties`` maps property name to a plain Python value, in the order the
    file wrote them. A property this module could not decode is **absent** from
    it - never ``None`` and never ``0`` - so an empty result and a zero result
    stay different facts.

    ``property_types`` records the rendered type name each decoded property
    came from, so "what was this" survives the decode.

    ``trailing`` is every byte after the ``"None"`` terminator, verbatim and
    unparsed. It is the escape hatch: whatever this reader does or does not
    make of that region, the bytes themselves stay available. The fields below
    are that same region decoded.

    ``epilogue`` is the first :data:`EPILOGUE_SIZE` of them. It is written
    after *every* tagged property list, not only the file's last one - the key
    profile nested in ``EnhancedInputUserSettings.sav`` carries its own, 21
    bytes before EOF rather than at it - so it is an object epilogue and not
    end-of-file padding. All seven observed occurrences are zero. An int32 zero
    fits, an empty FString fits, four zero flag bytes fit, and nothing observed
    tells them apart, so the bytes are handed back and **not named**.

    ``object_section_header`` is the four bytes that open the object section,
    and is **empty when the file wrote no object section at all**. That is how
    "this file has no such section" stays distinguishable from "a section was
    there and did not decode", which leaves ``undecoded_trailing`` non-empty
    instead. Its value is 2 as a little-endian int32 in the only capture.
    Reading it as the object count is ruled out: that demands a second object,
    and the block ends on the first one's sentinel with nothing to spare.

    ``key_profiles`` holds the decoded objects. ``undecoded_trailing`` holds
    the object section verbatim when a non-strict parse refused it, and is
    empty otherwise.
    """

    header: GvasHeader
    properties: dict[str, object] = field(default_factory=dict)
    property_types: dict[str, str] = field(default_factory=dict)
    unknown_properties: tuple[UnknownProperty, ...] = ()
    trailing: bytes = b""
    epilogue: bytes = b""
    object_section_header: bytes = b""
    key_profiles: tuple[KeyProfile, ...] = ()
    undecoded_trailing: bytes = b""
    property_list: tuple[Property, ...] = ()

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
class TypeName:
    """A property type name and its parameters, as UE 5.4 and later spell it.

    Public because :func:`serialise` needs the STRUCTURE back, and
    :meth:`render` is one-way: ``MapProperty<IntProperty, IntProperty>`` cannot
    be re-split into the FStrings and counts the engine wrote without guessing
    at how a name containing a comma or an angle bracket was spelled.
    :attr:`GvasSave.property_types` keeps the rendered form because that is what
    a reader wants to look at; :attr:`Property.type_name` keeps this one because
    that is what a writer needs.
    """

    name: str
    params: tuple[TypeName, ...] = ()

    def render(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}<{', '.join(p.render() for p in self.params)}>"


@dataclass(frozen=True)
class TextValue:
    """An ``FText``, with the two fields a plain string cannot carry.

    ``flags`` is the int32 word the engine writes before the history byte - 2
    in every occurrence measured, and retained rather than pinned because
    nothing observed says it is a constant. ``history`` is the history byte
    itself; ``text`` is a :class:`SourceText` when it is
    :data:`_TEXT_HISTORY_SOURCE` and a plain ``str`` when it is
    :data:`_TEXT_HISTORY_NONE`, which is exactly what the plain view hands back.

    The invariant history's culture-invariant flag is NOT retained. :func:`parse`
    refuses any value but :data:`MEASURED_CULTURE_INVARIANT_FLAG`, so a text that
    reached this class had a 1 there and writing one back is a fact rather than
    a default.
    """

    flags: int
    history: int
    text: str


@dataclass(frozen=True)
class StructValue:
    """A ``StructProperty`` whose payload is a nested tagged property list."""

    properties: tuple[Property, ...] = ()


@dataclass(frozen=True)
class MapValue:
    """A ``MapProperty``'s pairs, in the order the file wrote them.

    A tuple of pairs rather than a ``dict`` because this is the writer's view:
    order is part of the bytes, and a ``dict`` would also merge two keys Python
    happens to hash alike. The plain view on :attr:`GvasSave.properties` is
    still a ``dict``, and :func:`parse` refuses a map whose keys would collide
    there, so nothing is lost by the conversion.
    """

    pairs: tuple[tuple[object, object], ...] = ()


@dataclass(frozen=True)
class ArrayValue:
    """An ``ArrayProperty``'s elements, in file order."""

    elements: tuple[object, ...] = ()


@dataclass(frozen=True)
class Property:
    """One tagged property, carrying everything its tag spelled.

    This is the writer's view of a property and the unit :func:`transform`
    hands out. :attr:`GvasSave.properties` is the reader's view of the same
    thing, and is derived from these - see :func:`rebuild`, which is the only
    supported way to change one without the two disagreeing.

    ``value`` is a :class:`StructValue`, :class:`MapValue`, :class:`ArrayValue`,
    :class:`TextValue`, :class:`UndecodedStruct`, or a plain ``int``, ``float``,
    ``str`` or ``bool``, according to :attr:`type_name`.

    **The tag's flags byte is deliberately not stored.** Every bit of it is
    derivable from data that is: ``0x01`` from ``array_index`` being present,
    ``0x02`` from ``property_guid``, ``0x08`` from ``value`` being an
    :class:`UndecodedStruct`, and ``0x10`` from a ``BoolProperty``'s value.
    :func:`parse` refuses every other bit, so there is nothing left to keep.
    Storing the byte as well would create a second copy of four facts that
    could disagree with the first, and an edit that set ``value`` to ``False``
    while leaving a stale ``0x10`` would write a file saying ``True``.

    ``array_index`` and ``property_guid`` are ``None`` in every one of the 276
    files measured on 2026-08-10 - no property in any fixture, any live save or
    any of the 263 captured generations sets ``0x01`` or ``0x02``. They are
    retained anyway, because the alternative is a reader that silently drops a
    field the format has and a writer that cannot put it back.
    """

    name: str
    type_name: TypeName
    value: object
    array_index: int | None = None
    property_guid: bytes | None = None


def _read_type_name(reader: _Reader, depth: int = 0) -> TypeName:
    if depth > _MAX_TYPE_DEPTH:
        raise GvasParseError(f"type name nested deeper than {_MAX_TYPE_DEPTH}")
    name = reader.fstring()
    count = reader.int32()
    if count < 0 or count > _MAX_TYPE_PARAMS:
        raise GvasParseError(
            f"implausible type parameter count {count} for {name!r} at offset {reader.offset}"
        )
    params = tuple(_read_type_name(reader, depth + 1) for _ in range(count))
    return TypeName(name=name, params=params)


# --------------------------------------------------------------------------
# value decoders - one per measured type
# --------------------------------------------------------------------------


def _take_fixed(reader: _Reader, count: int, type_name: str) -> bytes:
    """Take a fixed-width value, or say the width disagrees with the type.

    A short fixed-width payload is an unmeasured ENCODING rather than a torn
    file - the tag's Size was honoured, the bytes inside it just are not the
    shape this type was measured to have - so it raises the recoverable error
    and a non-strict parse can record the property instead of losing the save.
    """
    if reader.remaining < count:
        raise UnknownPropertyTypeError(
            f"{type_name} needs {count} bytes and only {reader.remaining} remain"
        )
    return reader.take(count)


def _decode_bool(reader: _Reader, flags: int) -> bool:
    # Reads nothing. A tagged bool has a zero-byte payload and carries its
    # value in flag 0x10, so a non-zero Size is caught by the caller's
    # "left N undecoded trailing bytes" check rather than here.
    return bool(flags & _FLAG_BOOL_TRUE)


def _decode_int(reader: _Reader) -> int:
    return struct.unpack("<i", _take_fixed(reader, 4, "IntProperty"))[0]


def _decode_double(reader: _Reader) -> float:
    return struct.unpack("<d", _take_fixed(reader, 8, "DoubleProperty"))[0]


def _decode_str(reader: _Reader) -> str:
    return reader.fstring()


def _decode_byte(reader: _Reader, type_name: TypeName) -> str:
    """Decode a ``ByteProperty``, which this game writes as an enumerator name.

    Measured 2026-08-09 in ``StandaloneSlot_<roleId>.sav``: every
    ``ByteProperty`` there names its enum as its one type parameter and writes
    an FString of the qualified enumerator - ``E_DoorState::NewEnumerator1``,
    32 bytes for a Size, which is the 4-byte length plus 28 bytes of string.
    Nothing raw-byte-shaped has ever been seen.

    The prefix is kept rather than stripped. It is measured text, and two enums
    in this file both spell ``NewEnumerator1``, so dropping it would make two
    different states compare equal.
    """
    if len(type_name.params) != 1:
        # Unreal's parameterless ByteProperty is a single raw byte. That form
        # has never been observed here, and reading one as an FString would
        # invent a string out of whatever followed it.
        raise UnknownPropertyTypeError(
            f"a ByteProperty with {len(type_name.params)} type parameters has not "
            "been measured; the only form observed names its enum and writes the "
            "enumerator as an FString"
        )
    return reader.fstring()


def _decode_text(reader: _Reader, flags: int) -> TextValue:
    text_flags = reader.int32()
    history = reader.uint8()
    if history not in MEASURED_TEXT_HISTORIES:
        raise UnknownPropertyTypeError(
            f"TextProperty history type {history} has not been measured; "
            f"measured histories are {sorted(MEASURED_TEXT_HISTORIES)}"
        )
    if history == _TEXT_HISTORY_NONE:
        has_culture_invariant = reader.int32()
        if has_culture_invariant != MEASURED_CULTURE_INVARIANT_FLAG:
            raise UnknownPropertyTypeError(
                f"TextProperty culture-invariant flag {has_culture_invariant} "
                f"has not been measured; only {MEASURED_CULTURE_INVARIANT_FLAG} has"
            )
        text: str = reader.fstring()
    else:
        # A source history spells the text's localisation identity before the
        # text: namespace, key, then the source string itself.
        namespace = reader.fstring()
        key = reader.fstring()
        text = SourceText(reader.fstring(), namespace=namespace, key=key)
    if reader.remaining:
        raise UnknownPropertyTypeError(
            f"TextProperty left {reader.remaining} undecoded trailing bytes"
        )
    return TextValue(flags=text_flags, history=history, text=text)


def _struct_identity(type_name: TypeName) -> tuple[str, str]:
    """Pull a struct's name and package path out of its type name.

    Two shapes occur, both measured on 2026-08-09. A game struct spells
    ``StructProperty<F_DoorSaveData</Game/.../F_DoorSaveData>, <guid>>`` - the
    struct, its package path, and a dashed hex GUID as a second parameter. An
    engine core struct spells ``StructProperty<Vector</Script/CoreUObject>>``
    with no GUID parameter at all.

    The GUID is read past rather than returned. It identifies the struct
    DEFINITION for the engine's own versioning and says nothing about the
    value, so surfacing it would add a field every caller has to ignore.
    """
    if not 1 <= len(type_name.params) <= 2:
        raise UnknownPropertyTypeError(
            f"a StructProperty with {len(type_name.params)} type parameters has "
            "not been measured; the measured forms are <Name<Path>> and "
            "<Name<Path>, Guid>"
        )
    struct_type = type_name.params[0]
    if len(struct_type.params) != 1:
        raise UnknownPropertyTypeError(
            f"struct {struct_type.name!r} named {len(struct_type.params)} package "
            "paths; every struct measured names exactly one"
        )
    return struct_type.name, struct_type.params[0].name


def _read_struct(
    reader: _Reader, type_name: TypeName, *, flags: int, tagged: bool, depth: int
) -> object:
    """Decode a ``StructProperty`` value in place.

    Measured 2026-08-09 across 78 generations of
    ``StandaloneSlot_<roleId>.sav``: a struct's value is a nested tagged
    property list closed by the FString ``"None"``, using exactly the tag
    grammar the outer object uses. There is no length inside it - the
    enclosing tag's ``Size``, or the enclosing container, is what bounds it -
    and there is **no epilogue**, unlike the outer property list and a trailing
    object's. Every value in every generation landed exactly on its bound,
    which is what turns that from a plausible reading into a measured one.
    """
    struct_name, struct_path = _struct_identity(type_name)
    if tagged and flags & _FLAG_BINARY_OR_NATIVE:
        # The value went through a native serializer, so there is no property
        # list in there to read. The tag's Size bounds it exactly and the
        # caller has already sliced the reader to it, so the remaining bytes
        # ARE the payload - handing them back is a fact rather than a guess.
        return UndecodedStruct(
            struct_name=struct_name,
            struct_path=struct_path,
            data=reader.take(reader.remaining),
        )
    property_list, _plain_map, _types, _unknowns = _read_properties(
        reader, strict=True, depth=depth + 1
    )
    return StructValue(properties=property_list)


def _read_map(reader: _Reader, type_name: TypeName, *, depth: int) -> MapValue:
    """Decode a ``MapProperty`` value in place.

    ``int32`` keys-to-remove, ``int32`` pair count, then that many key/value
    pairs written BARE - no tag, no flags and no Size, just the value encoding
    for the parameter type. A struct element is therefore a bare property list
    closed by ``"None"``.

    Seven parameterisations have been measured and this decodes all of them,
    because it is generic over the element types rather than pinned to a
    rendered name. That is not a loosening: an element type nobody has measured
    in a bare position still raises, via :data:`MEASURED_BARE_TYPES`.
    """
    if len(type_name.params) != 2:
        raise UnknownPropertyTypeError(
            f"a MapProperty with {len(type_name.params)} type parameters has not "
            "been measured; a map names exactly one key type and one value type"
        )
    key_type, value_type = type_name.params
    if key_type.name not in MEASURED_MAP_KEY_TYPES:
        raise UnknownPropertyTypeError(
            f"a MapProperty keyed by {key_type.render()} has not been measured; "
            f"measured key types are {', '.join(sorted(MEASURED_MAP_KEY_TYPES))}"
        )

    keys_to_remove = reader.int32()
    if keys_to_remove != 0:
        raise UnknownPropertyTypeError(
            f"MapProperty announced {keys_to_remove} keys to remove; only 0 has "
            "been measured, and the removal encoding is unknown"
        )
    count = _element_count(reader, "MapProperty", "pairs")

    pairs: list[tuple[object, object]] = []
    seen: set[object] = set()
    for _ in range(count):
        key = _read_value(reader, key_type, flags=0, tagged=False, depth=depth + 1)
        value = _read_value(reader, value_type, flags=0, tagged=False, depth=depth + 1)
        plain_key = _plain(key)
        if plain_key in seen:
            # A dict would keep the last pair and drop the first, which is a
            # measurement disappearing with nobody told. Same reasoning as the
            # repeated-property-name check, one level down. Checked against the
            # PLAIN key, because that is the one the dict view would collide on.
            raise UnknownPropertyTypeError(
                f"MapProperty repeated the key {plain_key!r}, so one measured "
                "pair would be lost silently"
            )
        seen.add(plain_key)
        pairs.append((key, value))
    return MapValue(pairs=tuple(pairs))


def _read_array(reader: _Reader, type_name: TypeName, *, depth: int) -> ArrayValue:
    """Decode an ``ArrayProperty`` value in place.

    ``int32`` element count, then that many bare elements. There is no
    per-element header of any kind: UE4 wrote an inner struct header before an
    array of structs, and UE 5.4 does not, because the recursive type name
    already carries the struct's identity. Measured on the one parameterisation
    this game writes, ``ArrayProperty<StructProperty<F_CurrencyInfo<...>, ...>>``.
    """
    if len(type_name.params) != 1:
        raise UnknownPropertyTypeError(
            f"an ArrayProperty with {len(type_name.params)} type parameters has "
            "not been measured; an array names exactly one element type"
        )
    (element_type,) = type_name.params
    count = _element_count(reader, "ArrayProperty", "elements")
    return ArrayValue(
        elements=tuple(
            _read_value(reader, element_type, flags=0, tagged=False, depth=depth + 1)
            for _ in range(count)
        )
    )


def _element_count(reader: _Reader, type_name: str, noun: str) -> int:
    """Read a container's element count and reject one it cannot possibly hold.

    The cheapest element in any measured position is four bytes - an int32, or
    an empty FString's length. Rejecting before the loop keeps a corrupt length
    from spending a million iterations on its way to the same error.
    """
    count = reader.int32()
    if count < 0:
        raise UnknownPropertyTypeError(f"{type_name} announced {count} {noun}")
    if count * _MIN_CONTAINER_ELEMENT > reader.remaining:
        raise UnknownPropertyTypeError(
            f"{type_name} announced {count} {noun}, which needs more bytes than "
            f"the {reader.remaining} its value has left"
        )
    return count


def _plain(node: object) -> object:
    """Convert a writer-view value node into the plain value callers read.

    This is the ONE place the two views are related, so they cannot drift. A
    struct becomes a ``dict`` keyed by property name, a map becomes a ``dict``,
    an array becomes a ``tuple``, and an ``FText`` becomes the string it
    carries - a :class:`SourceText` when it had a localisation identity, so
    nothing measured is dropped. Every other node is already the plain value.
    """
    if isinstance(node, StructValue):
        return {prop.name: _plain(prop.value) for prop in node.properties}
    if isinstance(node, MapValue):
        return {_plain(key): _plain(value) for key, value in node.pairs}
    if isinstance(node, ArrayValue):
        return tuple(_plain(element) for element in node.elements)
    if isinstance(node, TextValue):
        return node.text
    return node


def _read_value(
    reader: _Reader, type_name: TypeName, *, flags: int, tagged: bool, depth: int
) -> object:
    """Decode one value in place, tagged or bare.

    ``tagged`` is False for a container element, which carries no tag and
    therefore no flags and no Size. That distinction is not cosmetic: a tagged
    ``BoolProperty`` has a zero-byte payload and lives entirely in flag
    ``0x10``, so a bare one would have to be encoded some other way, and
    :data:`MEASURED_BARE_TYPES` is the record of which types have actually been
    watched in that position.
    """
    if depth > MAX_VALUE_DEPTH:
        raise GvasParseError(
            f"value nested deeper than {MAX_VALUE_DEPTH}, which is a corrupt "
            "length rather than a shape this game writes"
        )
    name = type_name.name
    if not tagged and name not in MEASURED_BARE_TYPES:
        raise UnknownPropertyTypeError(
            f"{type_name.render()} has never been measured outside a property "
            f"tag; types measured as a container element are "
            f"{', '.join(sorted(MEASURED_BARE_TYPES))}"
        )

    if name == "StructProperty":
        return _read_struct(reader, type_name, flags=flags, tagged=tagged, depth=depth)
    if flags & _FLAG_BINARY_OR_NATIVE:
        # Every natively serialised property in every capture is a struct, so
        # the branch above is the whole measured extent of this flag. Anything
        # else carrying it is a layout nobody here has seen.
        raise UnknownPropertyTypeError(
            f"{type_name.render()} was written with a native serializer, whose "
            "layout differs from the tagged one measured here"
        )
    if name == "MapProperty":
        return _read_map(reader, type_name, depth=depth)
    if name == "ArrayProperty":
        return _read_array(reader, type_name, depth=depth)
    if name not in _LEAF_DECODERS:
        raise UnknownPropertyTypeError(
            f"property type {type_name.render()} has not been measured for this "
            f"game; measured types are {', '.join(sorted(KNOWN_PROPERTY_TYPES))}"
        )
    if type_name.params and name != "ByteProperty":
        # A leaf that grew parameters is not the leaf that was measured.
        raise UnknownPropertyTypeError(
            f"{type_name.render()} carries type parameters, and only the "
            f"parameterless {name} has been measured"
        )
    if name == "BoolProperty":
        return _decode_bool(reader, flags)
    if name == "ByteProperty":
        return _decode_byte(reader, type_name)
    if name == "TextProperty":
        return _decode_text(reader, flags)
    return _LEAF_DECODERS[name](reader)


#: Leaf decoders that need nothing but the reader. ``BoolProperty``,
#: ``ByteProperty`` and ``TextProperty`` are listed for membership but
#: dispatched by hand above, because each needs something the others do not -
#: the tag flags, the type parameters, and the tag flags again.
_LEAF_DECODERS: dict[str, Callable[[_Reader], object]] = {
    "IntProperty": _decode_int,
    "DoubleProperty": _decode_double,
    "StrProperty": _decode_str,
    "BoolProperty": _decode_bool,  # type: ignore[dict-item]
    "ByteProperty": _decode_byte,  # type: ignore[dict-item]
    "TextProperty": _decode_text,  # type: ignore[dict-item]
}

#: Every property type this module has measured and will decode. Anything else
#: raises. Adding an entry here is a claim that its encoding was observed, not
#: that it was looked up.
#:
#: These are type CONSTRUCTORS, not fully rendered names. They were rendered
#: names until ``StandaloneSlot_<roleId>.sav`` was measured, which writes seven
#: parameterisations of ``MapProperty`` and a dozen struct types whose rendered
#: names each embed a per-struct GUID. A container is gated by its ELEMENT
#: types now - see :data:`MEASURED_BARE_TYPES` and
#: :data:`MEASURED_MAP_KEY_TYPES` - which is a stricter statement than a list of
#: rendered names, not a looser one, because it also constrains shapes nobody
#: has written down yet.
KNOWN_PROPERTY_TYPES: frozenset[str] = frozenset(
    set(_LEAF_DECODERS) | {"StructProperty", "MapProperty", "ArrayProperty"}
)


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
# tagged property list - the outer file and every nested object share it
# --------------------------------------------------------------------------


def _read_properties(
    reader: _Reader, *, strict: bool, depth: int = 0
) -> tuple[
    tuple[Property, ...], dict[str, object], dict[str, str], tuple[UnknownProperty, ...]
]:
    """Read tagged properties up to and including the ``"None"`` terminator.

    Returns the writer's view (a :class:`Property` per tag, in file order), the
    plain reader's view, the rendered type names and the refusals. Both views
    come out of the same walk on purpose: a second pass that rebuilt one from
    the other could disagree with the bytes, and this reader's whole value is
    that it does not.

    ``depth`` counts nested property lists, because a struct's value is one of
    these too. It is passed on to the value reader and bounded by
    :data:`MAX_VALUE_DEPTH`.
    """
    property_list: list[Property] = []
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

        parsed_type = _read_type_name(reader)
        type_name = parsed_type.render()
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
        array_index = reader.int32() if flags & _FLAG_HAS_ARRAY_INDEX else None
        property_guid = reader.take(16) if flags & _FLAG_HAS_PROPERTY_GUID else None

        # Slicing to exactly Size is what keeps a nested decode honest: a
        # value can never read past its own property, and a value that stops
        # short is caught below rather than quietly leaving bytes behind.
        value_reader = _Reader(reader.take(size))

        try:
            value = _read_value(
                value_reader, parsed_type, flags=flags, tagged=True, depth=depth
            )
            if value_reader.remaining:
                raise UnknownPropertyTypeError(
                    f"{type_name} left {value_reader.remaining} undecoded "
                    "trailing bytes"
                )
        except UnknownPropertyTypeError as exc:
            if strict:
                raise UnknownPropertyTypeError(f"{name!r} at offset {name_offset}: {exc}") from exc
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

        property_list.append(
            Property(
                name=name,
                type_name=parsed_type,
                value=value,
                array_index=array_index,
                property_guid=property_guid,
            )
        )
        properties[name] = _plain(value)
        property_types[name] = type_name

    return tuple(property_list), properties, property_types, tuple(unknowns)


# --------------------------------------------------------------------------
# the trailing object section
# --------------------------------------------------------------------------


def _read_key_profile(reader: _Reader, *, strict: bool) -> KeyProfile:
    """Read one serialised object out of the trailing section."""
    start = reader.offset
    class_path = reader.fstring()
    if class_path != MEASURED_TRAILING_OBJECT_CLASS:
        # The body layout below was measured for exactly one class. Another
        # class writes a different body, and there is no length to skip it by.
        raise UnknownPropertyTypeError(
            f"trailing object class {class_path!r} at offset {start} has not "
            f"been measured; only {MEASURED_TRAILING_OBJECT_CLASS!r} has"
        )
    object_name = reader.fstring()

    count = reader.int32()
    if count < 0:
        raise GvasParseError(f"negative key mapping count {count} at offset {start}")
    # Cheapest possible row is a name, three slots and the tail: 4 empty
    # FStrings would still be 16 bytes plus 6. Reject a count the block cannot
    # hold before looping on it.
    if count * (4 * (_KEY_SLOTS + 1) + _KEY_MAPPING_TAIL) > reader.remaining:
        raise GvasParseError(
            f"key mapping count {count} needs more bytes than the block has"
        )
    mappings = tuple(
        KeyMapping(
            name=reader.fstring(),
            key_names=tuple(reader.fstring() for _ in range(_KEY_SLOTS)),
            undecoded=reader.take(_KEY_MAPPING_TAIL),
        )
        for _ in range(count)
    )

    identifier = reader.fstring()
    extension = reader.uint8()
    if extension != _NO_TAG_EXTENSION:
        raise GvasParseError(
            f"property tag extension {extension:#04x} in trailing object "
            f"{object_name!r} has not been measured"
        )

    property_list, properties, property_types, unknowns = _read_properties(
        reader, strict=strict
    )
    epilogue = reader.take(EPILOGUE_SIZE)
    sentinel = reader.fstring()
    if sentinel != _OBJECT_END:
        # The sentinel is the only end-of-object marker there is. Without it
        # the reader cannot tell a decoded object from a lucky alignment.
        raise GvasParseError(
            f"trailing object {object_name!r} ended with {sentinel!r}, not the "
            f"measured {_OBJECT_END!r} sentinel"
        )

    return KeyProfile(
        class_path=class_path,
        object_name=object_name,
        identifier=identifier,
        mappings=mappings,
        properties=properties,
        property_types=property_types,
        unknown_properties=unknowns,
        epilogue=epilogue,
        property_list=property_list,
    )


def _read_object_section(
    section: bytes, *, strict: bool
) -> tuple[bytes, tuple[KeyProfile, ...]]:
    """Decode the object section that follows a file's epilogue.

    Returns the section's four unidentified header bytes and its objects.
    Raises rather than returning a partial section: a half-read object section
    is the same failure as a half-read property list.
    """
    reader = _Reader(section)
    header = reader.take(EPILOGUE_SIZE)
    count = reader.int32()
    if count < 0:
        raise GvasParseError(f"negative trailing object count {count}")
    if count * _MIN_TRAILING_OBJECT > reader.remaining:
        raise GvasParseError(
            f"trailing object count {count} needs more bytes than the section has"
        )
    profiles = tuple(_read_key_profile(reader, strict=strict) for _ in range(count))
    if reader.remaining:
        raise GvasParseError(
            f"{reader.remaining} bytes left undecoded after the last trailing "
            "object, so the section is not the shape it was read as"
        )
    return header, profiles


# --------------------------------------------------------------------------
# the writer - every length recomputed, nothing carried over from the source
# --------------------------------------------------------------------------


class _Writer:
    """An append-only byte sink, the mirror of :class:`_Reader`.

    Deliberately has no seek and no patch. Every ``Size`` and every container
    count is computed from bytes that already exist, by serialising the value
    first and asking how long it came out - so there is no such thing here as a
    length that was written early and forgotten. That is the whole reason this
    class exists rather than a bytearray with offsets in it: hand-patching
    around a hundred nested ``Size`` fields is exactly the fragile move a
    sanitised fixture must not depend on.
    """

    __slots__ = ("parts",)

    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def raw(self, data: bytes) -> None:
        self.parts.append(bytes(data))

    def int32(self, value: int) -> None:
        try:
            self.parts.append(struct.pack("<i", value))
        except struct.error as exc:
            raise GvasSerialiseError(f"{value!r} does not fit an int32: {exc}") from exc

    def uint8(self, value: int) -> None:
        if not 0 <= value <= 0xFF:
            raise GvasSerialiseError(f"{value!r} does not fit a uint8")
        self.parts.append(bytes([value]))

    def fstring(self, text: str) -> None:
        """Write an FString the way every measured one in this game is written.

        Empty is length 0 and nothing else: across the 276 files measured on
        2026-08-10 there are 5701 empty FStrings and every one of them is a
        bare zero, with not a single length-1 lone-NUL form anywhere. Non-empty
        is ANSI with the NUL counted, because all 671318 non-empty FStrings in
        those files take that branch and **not one is UTF-16**.

        A non-ASCII string therefore raises. The engine's negative-length
        UTF-16 branch is real and published, and nothing this project has
        watched has ever emitted it, so writing one would be this module
        inventing an encoding rather than reproducing one.
        """
        if not isinstance(text, str):
            raise GvasSerialiseError(f"expected a string to write, got {type(text).__name__}")
        if text == "":
            self.int32(0)
            return
        if not text.isascii():
            raise GvasSerialiseError(
                f"{text!r} is not ASCII, and the engine's UTF-16 FString branch "
                "has never been observed in this game - writing one would be an "
                "invented encoding rather than a measured one"
            )
        raw = text.encode("ascii") + b"\0"
        self.int32(len(raw))
        self.raw(raw)

    def bytes(self) -> bytes:
        return b"".join(self.parts)


def _write_type_name(writer: _Writer, type_name: TypeName) -> None:
    writer.fstring(type_name.name)
    writer.int32(len(type_name.params))
    for param in type_name.params:
        _write_type_name(writer, param)


def _tag_flags(prop: Property) -> int:
    """Rebuild a property's flags byte from the data that implies each bit.

    See :class:`Property` for why the byte is not stored. Every bit here is
    derived from something that cannot be edited out of sync with it.
    """
    flags = 0
    if prop.array_index is not None:
        flags |= _FLAG_HAS_ARRAY_INDEX
    if prop.property_guid is not None:
        flags |= _FLAG_HAS_PROPERTY_GUID
    if isinstance(prop.value, UndecodedStruct):
        flags |= _FLAG_BINARY_OR_NATIVE
    if prop.type_name.name == "BoolProperty":
        if not isinstance(prop.value, bool):
            raise GvasSerialiseError(
                f"BoolProperty {prop.name!r} carries a "
                f"{type(prop.value).__name__}; its whole value is the 0x10 flag "
                "bit, so there is nothing else to write it as"
            )
        if prop.value:
            flags |= _FLAG_BOOL_TRUE
    return flags


def _write_property(writer: _Writer, prop: Property) -> None:
    if prop.name == "None":
        # It would serialise fine and then read back as the terminator, so the
        # file would parse, be short, and say nothing about the loss.
        raise GvasSerialiseError(
            "a property named 'None' would be read back as the list terminator, "
            "silently truncating everything after it"
        )
    value = _value_bytes(prop.type_name, prop.value, tagged=True)
    flags = _tag_flags(prop)

    writer.fstring(prop.name)
    _write_type_name(writer, prop.type_name)
    writer.int32(len(value))
    writer.uint8(flags)
    if prop.array_index is not None:
        writer.int32(prop.array_index)
    if prop.property_guid is not None:
        if len(prop.property_guid) != 16:
            raise GvasSerialiseError(
                f"property {prop.name!r} carries a {len(prop.property_guid)}-byte "
                "GUID; the tag field is 16"
            )
        writer.raw(prop.property_guid)
    writer.raw(value)


def _write_properties(writer: _Writer, properties: tuple[Property, ...]) -> None:
    seen: set[str] = set()
    for prop in properties:
        if prop.name in seen:
            # Same rule the reader enforces, on the way out: a repeated name
            # would parse back to one value and lose the other with nobody told.
            raise GvasSerialiseError(f"property {prop.name!r} appears twice")
        seen.add(prop.name)
        _write_property(writer, prop)
    writer.fstring("None")


def _value_bytes(type_name: TypeName, node: object, *, tagged: bool) -> bytes:
    writer = _Writer()
    _write_value(writer, type_name, node, tagged=tagged)
    return writer.bytes()


def _write_value(
    writer: _Writer, type_name: TypeName, node: object, *, tagged: bool
) -> None:
    """Write one value, tagged or bare, driven entirely by ``type_name``.

    The type name is the authority, not the Python type of ``node``: a ``str``
    is a ``StrProperty`` payload in one position and a ``ByteProperty``
    enumerator in another, and only the tag says which.
    """
    name = type_name.name
    if not tagged and name not in MEASURED_BARE_TYPES:
        raise GvasSerialiseError(
            f"{type_name.render()} has never been measured outside a property "
            "tag, so there is no bare encoding to write"
        )

    if name == "StructProperty":
        _struct_identity(type_name)  # refuse a shape the reader would not accept
        if isinstance(node, UndecodedStruct):
            if not tagged:
                raise GvasSerialiseError(
                    f"{node.struct_name} was written by a native serializer, and "
                    "no native struct has been measured as a container element"
                )
            writer.raw(node.data)
            return
        if not isinstance(node, StructValue):
            raise GvasSerialiseError(
                f"a StructProperty needs a StructValue or an UndecodedStruct, "
                f"got {type(node).__name__}"
            )
        _write_properties(writer, node.properties)
        return

    if name == "MapProperty":
        if len(type_name.params) != 2:
            raise GvasSerialiseError(
                f"a MapProperty names exactly one key type and one value type, "
                f"not {len(type_name.params)}"
            )
        if not isinstance(node, MapValue):
            raise GvasSerialiseError(
                f"a MapProperty needs a MapValue, got {type(node).__name__}"
            )
        key_type, value_type = type_name.params
        if key_type.name not in MEASURED_MAP_KEY_TYPES:
            raise GvasSerialiseError(
                f"a MapProperty keyed by {key_type.render()} has not been measured"
            )
        writer.int32(0)  # keys to remove; only 0 has ever been observed
        writer.int32(len(node.pairs))
        for key, value in node.pairs:
            _write_value(writer, key_type, key, tagged=False)
            _write_value(writer, value_type, value, tagged=False)
        return

    if name == "ArrayProperty":
        if len(type_name.params) != 1:
            raise GvasSerialiseError(
                f"an ArrayProperty names exactly one element type, not "
                f"{len(type_name.params)}"
            )
        if not isinstance(node, ArrayValue):
            raise GvasSerialiseError(
                f"an ArrayProperty needs an ArrayValue, got {type(node).__name__}"
            )
        (element_type,) = type_name.params
        writer.int32(len(node.elements))
        for element in node.elements:
            _write_value(writer, element_type, element, tagged=False)
        return

    if name not in KNOWN_PROPERTY_TYPES:
        raise GvasSerialiseError(
            f"property type {type_name.render()} has not been measured for this "
            f"game; measured types are {', '.join(sorted(KNOWN_PROPERTY_TYPES))}"
        )
    if type_name.params and name != "ByteProperty":
        raise GvasSerialiseError(
            f"{type_name.render()} carries type parameters, and only the "
            f"parameterless {name} has been measured"
        )

    if name == "BoolProperty":
        # Nothing at all. A tagged bool's payload is zero bytes and its value
        # lives in the 0x10 flag bit, which _tag_flags has already written.
        return
    if name == "IntProperty":
        if not isinstance(node, int) or isinstance(node, bool):
            raise GvasSerialiseError(
                f"an IntProperty needs an int, got {type(node).__name__}"
            )
        writer.int32(node)
        return
    if name == "DoubleProperty":
        if not isinstance(node, (int, float)) or isinstance(node, bool):
            raise GvasSerialiseError(
                f"a DoubleProperty needs a float, got {type(node).__name__}"
            )
        writer.raw(struct.pack("<d", node))
        return
    if name in ("StrProperty", "ByteProperty"):
        if name == "ByteProperty" and len(type_name.params) != 1:
            raise GvasSerialiseError(
                f"a ByteProperty with {len(type_name.params)} type parameters has "
                "not been measured; the only form observed names its enum"
            )
        writer.fstring(node)  # type: ignore[arg-type]  - fstring type-checks it
        return
    _write_text(writer, node)


def _write_text(writer: _Writer, node: object) -> None:
    if not isinstance(node, TextValue):
        raise GvasSerialiseError(
            f"a TextProperty needs a TextValue, got {type(node).__name__}. The "
            "plain view hands back only the string, which cannot say which "
            "history wrote it"
        )
    if node.history not in MEASURED_TEXT_HISTORIES:
        raise GvasSerialiseError(
            f"TextProperty history {node.history} has not been measured; "
            f"measured histories are {sorted(MEASURED_TEXT_HISTORIES)}"
        )
    writer.int32(node.flags)
    writer.uint8(node.history)
    if node.history == _TEXT_HISTORY_NONE:
        writer.int32(MEASURED_CULTURE_INVARIANT_FLAG)
        writer.fstring(node.text)
        return
    if not isinstance(node.text, SourceText):
        raise GvasSerialiseError(
            "a source-history TextProperty needs a SourceText, which is what "
            "carries the namespace and key it has to write"
        )
    writer.fstring(node.text.namespace)
    writer.fstring(node.text.key)
    writer.fstring(str(node.text))


def _write_header(writer: _Writer, header: GvasHeader) -> None:
    writer.raw(MAGIC)
    writer.int32(header.save_game_version)
    writer.int32(header.package_file_version_ue4)
    writer.int32(header.package_file_version_ue5)
    engine = header.engine_version
    try:
        writer.raw(
            struct.pack(
                "<HHHI", engine.major, engine.minor, engine.patch, engine.changelist
            )
        )
    except struct.error as exc:
        raise GvasSerialiseError(f"engine version does not fit its fields: {exc}") from exc
    writer.fstring(engine.branch)
    writer.int32(header.custom_version_format)
    writer.int32(len(header.custom_versions))
    for entry in header.custom_versions:
        if len(entry.guid) != 16:
            raise GvasSerialiseError(
                f"a custom version GUID is {len(entry.guid)} bytes; the field is 16"
            )
        writer.raw(entry.guid)
        writer.int32(entry.version)
    writer.fstring(header.save_game_class_name)


def _write_key_profile(writer: _Writer, profile: KeyProfile) -> None:
    if profile.unknown_properties:
        raise GvasSerialiseError(
            f"trailing object {profile.object_name!r} holds "
            f"{len(profile.unknown_properties)} properties a non-strict parse "
            "refused, whose bytes were not kept; there is nothing to write back"
        )
    writer.fstring(profile.class_path)
    writer.fstring(profile.object_name)
    writer.int32(len(profile.mappings))
    for mapping in profile.mappings:
        if len(mapping.key_names) != _KEY_SLOTS:
            raise GvasSerialiseError(
                f"key mapping {mapping.name!r} has {len(mapping.key_names)} slots; "
                f"the row carries no count and every measured one has {_KEY_SLOTS}"
            )
        if len(mapping.undecoded) != _KEY_MAPPING_TAIL:
            raise GvasSerialiseError(
                f"key mapping {mapping.name!r} closes with "
                f"{len(mapping.undecoded)} undecoded bytes; every measured row "
                f"closes with {_KEY_MAPPING_TAIL}"
            )
        writer.fstring(mapping.name)
        for key_name in mapping.key_names:
            writer.fstring(key_name)
        writer.raw(mapping.undecoded)
    writer.fstring(profile.identifier)
    writer.uint8(_NO_TAG_EXTENSION)
    _write_properties(writer, profile.property_list)
    if len(profile.epilogue) != EPILOGUE_SIZE:
        raise GvasSerialiseError(
            f"trailing object {profile.object_name!r} carries a "
            f"{len(profile.epilogue)}-byte epilogue; every measured one is "
            f"{EPILOGUE_SIZE}"
        )
    writer.raw(profile.epilogue)
    writer.fstring(_OBJECT_END)


def _write_tail(
    writer: _Writer,
    *,
    epilogue: bytes,
    object_section_header: bytes,
    key_profiles: tuple[KeyProfile, ...],
    undecoded_trailing: bytes,
) -> None:
    """Write everything after the outer ``"None"``: epilogue, object section."""
    if len(epilogue) != EPILOGUE_SIZE:
        raise GvasSerialiseError(
            f"the epilogue is {len(epilogue)} bytes; every measured property "
            f"list is followed by {EPILOGUE_SIZE}"
        )
    writer.raw(epilogue)

    if undecoded_trailing:
        if object_section_header or key_profiles:
            raise GvasSerialiseError(
                "undecoded_trailing holds the object section verbatim AND the "
                "decoded fields are populated; writing both would duplicate it"
            )
        writer.raw(undecoded_trailing)
        return
    if not object_section_header:
        if key_profiles:
            raise GvasSerialiseError(
                "there are key profiles to write but no object_section_header, "
                "and the four bytes that open the section are not derivable "
                "from anything else"
            )
        return
    if len(object_section_header) != EPILOGUE_SIZE:
        raise GvasSerialiseError(
            f"object_section_header is {len(object_section_header)} bytes; the "
            f"measured one is {EPILOGUE_SIZE}"
        )
    writer.raw(object_section_header)
    writer.int32(len(key_profiles))
    for profile in key_profiles:
        _write_key_profile(writer, profile)


# --------------------------------------------------------------------------
# rebuilding an edited save, so the two views can never disagree
# --------------------------------------------------------------------------


def _plain_views(
    properties: tuple[Property, ...],
) -> tuple[dict[str, object], dict[str, str]]:
    plain: dict[str, object] = {}
    types: dict[str, str] = {}
    for prop in properties:
        if prop.name in plain:
            raise GvasSerialiseError(f"property {prop.name!r} appears twice")
        plain[prop.name] = _plain(prop.value)
        types[prop.name] = prop.type_name.render()
    return plain, types


def _transform_value(
    node: object, function: Callable[[tuple[str, ...], Property], Property | None],
    path: tuple[str, ...],
) -> object:
    if isinstance(node, StructValue):
        return StructValue(properties=_transform_properties(node.properties, function, path))
    if isinstance(node, MapValue):
        return MapValue(
            pairs=tuple(
                (
                    _transform_value(key, function, (*path, f"[{index}].key")),
                    _transform_value(value, function, (*path, f"[{index}].value")),
                )
                for index, (key, value) in enumerate(node.pairs)
            )
        )
    if isinstance(node, ArrayValue):
        return ArrayValue(
            elements=tuple(
                _transform_value(element, function, (*path, f"[{index}]"))
                for index, element in enumerate(node.elements)
            )
        )
    return node


def _transform_properties(
    properties: tuple[Property, ...],
    function: Callable[[tuple[str, ...], Property], Property | None],
    path: tuple[str, ...],
) -> tuple[Property, ...]:
    out: list[Property] = []
    for prop in properties:
        replacement = function((*path, prop.name), prop)
        if replacement is None:
            continue
        if not isinstance(replacement, Property):
            raise GvasSerialiseError(
                f"transform returned a {type(replacement).__name__} for "
                f"{prop.name!r}; it must return a Property or None"
            )
        here = (*path, replacement.name)
        out.append(
            replace(
                replacement,
                value=_transform_value(replacement.value, function, here),
            )
        )
    return tuple(out)


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

    property_list, properties, property_types, unknowns = _read_properties(
        reader, strict=strict
    )

    trailing = reader.take(reader.remaining)
    if len(trailing) < EPILOGUE_SIZE:
        # All seven observed property lists - one per file, plus the key
        # profile nested in EnhancedInputUserSettings - are followed by four
        # bytes. Fewer means this is not the stream it appears to be, and a
        # short epilogue reported as the whole one would be a quiet lie.
        raise GvasParseError(
            f"only {len(trailing)} bytes follow the property terminator; every "
            f"measured property list is followed by a {EPILOGUE_SIZE}-byte epilogue"
        )
    epilogue = trailing[:EPILOGUE_SIZE]
    section = trailing[EPILOGUE_SIZE:]

    section_header = b""
    profiles: tuple[KeyProfile, ...] = ()
    undecoded_trailing = b""
    if section:
        try:
            section_header, profiles = _read_object_section(section, strict=strict)
        except GvasParseError:
            if strict:
                raise
            # Same contract as an unmeasured property: nothing invented, and
            # the refused bytes handed back so the caller can see what they were.
            undecoded_trailing = section

    return GvasSave(
        header=header,
        properties=properties,
        property_types=property_types,
        unknown_properties=unknowns,
        trailing=trailing,
        epilogue=epilogue,
        object_section_header=section_header,
        key_profiles=profiles,
        undecoded_trailing=undecoded_trailing,
        property_list=property_list,
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


def serialise(save: GvasSave) -> bytes:
    """Write a :class:`GvasSave` back out as GVAS bytes.

    The contract is byte-for-byte round-trip identity::

        serialise(parse(raw)) == raw

    measured on 2026-08-10 to hold for all 6 committed fixtures, all 7 live
    saves on the machine that has the game, and all 263 captured generations of
    the transient ``StandaloneSlot`` save - 276 files, largest 177878 bytes.

    Every ``Size`` and every container count is **recomputed** from the bytes
    the value actually produced. That is the point: sanitising a save means
    shortening identifier strings and dropping map entries, both of which move
    byte lengths, and hand-patching the roughly one hundred enclosing lengths
    that follow from one such edit is how a fixture ends up pinning a format
    nobody has. Edit the tree, serialise, and the lengths are right by
    construction.

    Raises :class:`GvasSerialiseError` rather than emitting a near-miss. A file
    that parses but is subtly wrong is worse than no file, because it looks
    like evidence. The cases are:

    * the save came from a non-strict parse that refused a property, so those
      bytes are simply not in the object;
    * a value node does not match the type name that has to describe it;
    * a string is not ASCII, an encoding the engine has but this game has never
      been watched using;
    * a length-bearing field - a GUID, a key-mapping tail, an epilogue - is not
      the width every measured one is.

    This function returns bytes and writes no file. Nothing in this module ever
    writes into the game's save directory.
    """
    if save.unknown_properties:
        names = ", ".join(repr(u.name) for u in save.unknown_properties)
        raise GvasSerialiseError(
            f"this save holds {len(save.unknown_properties)} properties a "
            f"non-strict parse refused ({names}), whose bytes were not kept; "
            "there is nothing to write back for them, and a file missing them "
            "would look complete"
        )
    writer = _Writer()
    _write_header(writer, save.header)
    writer.uint8(_NO_TAG_EXTENSION)
    _write_properties(writer, save.property_list)
    _write_tail(
        writer,
        epilogue=save.epilogue,
        object_section_header=save.object_section_header,
        key_profiles=save.key_profiles,
        undecoded_trailing=save.undecoded_trailing,
    )
    return writer.bytes()


def rebuild(
    save: GvasSave,
    *,
    property_list: tuple[Property, ...] | None = None,
    key_profiles: tuple[KeyProfile, ...] | None = None,
) -> GvasSave:
    """Return a copy of ``save`` carrying edited properties, views recomputed.

    This is the supported way to change a save, and the reason it exists is
    that :attr:`GvasSave.properties` is DERIVED. Reaching for
    ``dataclasses.replace(save, property_list=...)`` would leave the plain
    dict, the rendered type names and :attr:`GvasSave.trailing` describing the
    save you no longer have, and the object would then disagree with the bytes
    :func:`serialise` writes from it.

    ``trailing`` is recomputed too, so it keeps meaning "the bytes after the
    terminator" for the edited save rather than for the one it came from.
    """
    properties = save.property_list if property_list is None else tuple(property_list)
    profiles = save.key_profiles if key_profiles is None else tuple(key_profiles)
    plain, types = _plain_views(properties)

    tail = _Writer()
    _write_tail(
        tail,
        epilogue=save.epilogue,
        object_section_header=save.object_section_header,
        key_profiles=profiles,
        undecoded_trailing=save.undecoded_trailing,
    )

    return GvasSave(
        header=save.header,
        properties=plain,
        property_types=types,
        unknown_properties=save.unknown_properties,
        trailing=tail.bytes(),
        epilogue=save.epilogue,
        object_section_header=save.object_section_header,
        key_profiles=profiles,
        undecoded_trailing=save.undecoded_trailing,
        property_list=properties,
    )


def transform(
    save: GvasSave,
    function: Callable[[tuple[str, ...], Property], Property | None],
) -> GvasSave:
    """Rebuild ``save`` with ``function`` applied to every tagged property.

    ``function`` is called as ``function(path, prop)`` for every property at
    every depth - top level, inside a struct, inside a struct inside a map -
    and returns the property to keep, or ``None`` to drop it. ``path`` is the
    chain of names down to that property, with container positions spelled
    ``[3].key`` and ``[3].value`` for a map pair and ``[3]`` for an array
    element, so a rule can be scoped to one place rather than to a name that
    might occur in several.

    Recursion happens into whatever ``function`` RETURNS, not into what it was
    given, so a replacement's children are visited too and a wholesale subtree
    swap is a single return rather than a special case.

    Both edits a sanitised fixture needs go through here. Shortening a string
    is returning the property with a shorter one; dropping map entries is
    returning it with a filtered :class:`MapValue`::

        def sanitise(path, prop):
            if prop.name == "ownerRoleId":
                return replace(prop, value="<LONG_ID>")
            if isinstance(prop.value, MapValue):
                return replace(prop, value=MapValue(prop.value.pairs[:2]))
            return prop

    Neither the caller nor this function patches a single ``Size``.
    :func:`serialise` recomputes all of them.
    """
    return rebuild(
        save,
        property_list=_transform_properties(save.property_list, function, ()),
        key_profiles=tuple(
            _rebuild_key_profile(
                profile,
                _transform_properties(
                    profile.property_list, function, (profile.object_name,)
                ),
            )
            for profile in save.key_profiles
        ),
    )


def _rebuild_key_profile(
    profile: KeyProfile, property_list: tuple[Property, ...]
) -> KeyProfile:
    """The :func:`rebuild` contract, one level down, for a trailing object."""
    plain, types = _plain_views(property_list)
    return replace(
        profile,
        properties=plain,
        property_types=types,
        property_list=property_list,
    )
