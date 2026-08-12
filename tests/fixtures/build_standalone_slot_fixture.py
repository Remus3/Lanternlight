"""Build ``tests/fixtures/gvas/standalone_slot.gvas.b64`` from a captured save.

This script is committed for PROVENANCE. The fixture it writes is an authored
artifact, and the only honest way to say what was authored is to ship the thing
that authored it - so a reader can see exactly which values the repository
chose, which values the game wrote, and which containers were dropped.

It is not run by the test suite and it is not importable-with-side-effects. The
source save lives OUTSIDE the repository, is never committed, and does not
exist on most machines, so this module must import cleanly with no captures
anywhere. Every path comes in as an argument::

    python tests/fixtures/build_standalone_slot_fixture.py <path-to-capture>

What the source is
------------------

``StandaloneSlot_<19-digit roleId>.sav`` is the game's transient in-run level
save: created at match start, rewritten every few seconds, destroyed at run
end. It is the only save this project has seen that carries a
``StructProperty``, an ``ArrayProperty``, a ``ByteProperty``, a natively
serialised struct, or a map keyed by anything but a string - so it is the only
place those shapes can be pinned from. It is also, by a wide margin, the
save that carries the most identifying data.

Three classes of value are AUTHORED, and each is authored for a measured
reason rather than a general sense of caution.

1. **Identifiers - 38 of them, every one 19 digits.** ``lanternlight.redact``'s
   ``LONG_ID`` rule is length-only: any run of 15 or more digits fires. So a
   same-length substitution changes nothing at all - an authored 19-digit id
   trips exactly the same rule a real one does. Every authored id here is
   therefore SHORTER than the floor, which moves FString lengths, which is
   what :func:`lanternlight.gvas.serialise` exists to make safe.

2. **The 32-character hex GUIDs - 67 distinct.** Unreal decorates a Blueprint
   property name as ``Name_Index_<32 uppercase hex>``, and a bare 32-hex run is
   exactly the shape of an Epic ``ProductUserId``, so ``PRODUCTUSERID`` fires on
   all 772 occurrences. Every one is a false positive on this capture and the
   rule is deliberately NOT narrowed - uppercase is not a safe discriminator and
   neither is position. The fixture authors the GUIDs instead. **An authored
   token that is still 32 hex characters would change nothing**, because the
   rule keys on shape and cannot tell an authored hex run from a real
   ProductUserId; so the replacement stops being a hex run at all. Two of the 67
   also contain 16- and 17-digit decimal stretches that trip ``LONG_ID``, so one
   decision closes both false-positive classes.

3. **A third party's display name.** ``LeaderRankScoreData`` records the last
   kill, including ``PlayerName``, ``MsgSubChannelString`` and
   ``MsgAppearanceString``. In this capture the record is a bot, but the format
   is the same one a real player's name would arrive in, and that person never
   consented to anything. ``lanternlight.redact.DETECT_ONLY_RULES`` carries a
   structural rule that recognises the PROPERTY and stays red unless
   :data:`lanternlight.redact.AUTHORED_NAME_MARKER` sits beside it. Authoring
   those three values is what satisfies it.

Size
----

The largest captured generation is 177878 bytes, chosen as the base because it
is the one with the most shape coverage. The repetitive containers are pruned
to two or three entries each, and every JSON blob is truncated to one
representative element - keeping at least one of every distinct SHAPE, because
a fixture exists to pin a format rather than to preserve a play session.

The gate, which is the point
----------------------------

:func:`build` refuses to return bytes that are not clean, and :func:`main`
refuses to write what :func:`build` did not certify. A builder that can emit a
leaking fixture is the wrong shape for this job: the scan has to run between
the transform and the write, not after somebody remembers to look.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import redact  # noqa: E402  (path bootstrap must run first)
from lanternlight.gvas import (  # noqa: E402
    MapValue,
    Property,
    StructValue,
    UndecodedStruct,
    parse,
    serialise,
    transform,
)

#: Where the fixture lands. The name is a RENAME of the game's own
#: ``StandaloneSlot_<19-digit roleId>.sav`` - the filename carried an
#: identifier, so content sanitisation alone would still have published it in a
#: directory listing.
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "gvas" / "standalone_slot.gvas.b64"

#: Authored ids. All are shorter than :data:`lanternlight.redact`'s 15-digit
#: ``LONG_ID`` floor, which is the whole point - see the module docstring.
AUTHORED_ROLE_ID = "100000000001"
AUTHORED_BATTLE_ID = "900000000001"

#: Authored ``IdGeneratorData`` values, one per SHAPE observed in the source:
#: a long id (19 digits there, 12 here), a negative 8-digit run and a negative
#: 2-digit run. Distinct, because they are also map keys one level over.
AUTHORED_UUIDS = ("200000000001", "-20000001", "-21")

#: Shapes required of the ``IdGeneratorData`` entries kept, in order. The first
#: is the one that matters: it is the identifier-shaped value, and a fixture
#: that dropped it would stop pinning the case this whole exercise is about.
_UUID_SHAPES = (r"\d{15,}", r"-\d{8}", r"-\d{2}")

#: Prefix of every authored GUID. Deliberately not hex - ``U``, ``T``, ``H``,
#: ``O``, ``R`` and ``D`` are all outside ``[0-9a-f]``, and they recur often
#: enough that no 32-character window of an authored decoration can be a hex
#: run. That is the property that matters: an authored token which was STILL 32
#: hex characters would leave ``PRODUCTUSERID`` firing exactly as before,
#: because the rule keys on shape and cannot tell the two apart.
_AUTHORED_GUID_PREFIX = "AUTHORED"

#: Digits of index appended to the prefix. Three is enough for the 67 distinct
#: GUIDs the source carries, with room to spare, and the width is fixed so the
#: decorations sort and diff in a stable order.
_GUID_INDEX_DIGITS = 3

#: The authored decoration keeps the source's 32-character width, and that is
#: NOT cosmetic - it was measured. An 11-character decoration was built first
#: and :func:`findings` refused it, with one ``NAME_FIELD`` hit "inside a
#: 76-character base64 run".
#:
#: The reason is the encoded scan's per-LINE reading.
#: :func:`lanternlight.redact.iter_encoded_sensitive` decodes each base64 run it
#: finds, and a fixture wrapped at 76 columns is a stack of separate 76-column
#: runs, each decoding to a 57-byte WINDOW of the save. The structural
#: name-field rule needs the property name, its NUL and the ``StrProperty``
#: token - ``len(name) + 17`` bytes - and it goes quiet only when the authored
#: marker follows within 64 bytes. A 57-byte window that holds the first can
#: never hold the second, so any name-bearing property short enough to fit the
#: rule's head inside one window is reported, correctly by the rule's own logic
#: and uselessly for this file.
#:
#: ``len(name) + 17 > 57`` is the condition that puts the head out of reach, so
#: a decorated name must exceed 40 characters. ``PlayerName_19_`` is 14, so the
#: decoration must be at least 27; 32 is the source's own width and clears it
#: with margin. ``tests/test_gvas.py`` pins that inequality rather than leaving
#: the next person to rediscover it by shortening a token and getting a red
#: repository scan with no obvious cause.
_GUID_WIDTH = 32

#: An all-zero native struct payload is REPLACED with this pattern, and the
#: reason is a property of base64 rather than of the save.
#:
#: Measured while building this fixture: 24 consecutive zero bytes encode to 32
#: consecutive ``A`` characters, ``A`` is a hexadecimal digit, and
#: ``PRODUCTUSERID`` is a bare 32-hex run - so the committed base64 TEXT trips
#: the repository's plain scan even though the save it encodes is clean. Three
#: native ``Vector`` payloads in the pruned save are entirely zero (a monster's
#: ``Translation``, and the ``ExtraTreasureBoxTransform`` of a box that was
#: never created), and no choice of entries avoids it: ``ExtraTreasureBoxCreated``
#: is false for every one of the 61 monsters in the capture.
#:
#: Narrowing the detector is not this lane's call and the module forbids it, so
#: the fixture authors the payload instead - which is the same remedy it applies
#: to the Blueprint GUIDs, for the same reason.
#:
#: The pattern is ascending bytes rather than anything float-shaped ON PURPOSE.
#: Read as three doubles it is denormal garbage, which says "authored" out loud;
#: a plausible-looking coordinate would say "measured" and be a lie. What is
#: lost - that the game writes an all-zero ``Vector`` for an uncreated extra
#: treasure box - is a fact about the GAME rather than about the format, and the
#: format claim it would have pinned (a native struct of zero bytes round-trips
#: verbatim) is pinned directly by a synthetic test in ``tests/test_gvas.py``.
#:
#: See :func:`authored_native_payload`.
_MAX_AUTHORED_PAYLOAD = 255

#: How many entries survive in each pruned container.
_KEEP_MAP_ENTRIES = 2
_KEEP_ID_ENTRIES = 3
_KEEP_JSON_ELEMENTS = 1

#: A Blueprint-decorated property name: ``Hp_10_<32 hex>``.
_DECORATION = re.compile(r"^(?P<base>.+)_(?P<index>\d+)_(?P<guid>[0-9A-Fa-f]{32})$")

#: The exact shape ``PRODUCTUSERID`` keys on. Copied in shape rather than
#: imported because the point is to enumerate every run that rule would find,
#: and a private pattern that drifted from it would leave one behind.
_HEX32 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")

#: A digit run at ``LONG_ID``'s floor.
_LONG_DIGITS = re.compile(r"(?<!\d)\d{15,}(?!\d)")

#: The game writes its JSON with no spaces. Measured: re-dumping every one of
#: the 50 non-empty JSON payloads in the source with these separators
#: reproduces the game's own text byte for byte, so editing a payload through
#: Python's json module changes only what this script meant to change.
_JSON_SEPARATORS = (",", ":")


class BuildError(RuntimeError):
    """Raised when the source is not the save this script was measured against.

    A wrong guess about the source is not something to work around. Every
    selection below asserts that the shape it is looking for was actually
    found, because a container quietly pruned to nothing would produce a
    fixture that parses, passes, and pins a format the game does not write.
    """


# --------------------------------------------------------------------------
# small helpers over the parsed tree
# --------------------------------------------------------------------------


def base_name(name: str) -> str:
    """Return a property name with its Blueprint decoration stripped."""
    match = _DECORATION.match(name)
    return match.group("base") if match else name


def _fields(struct: StructValue) -> dict[str, object]:
    """Map undecorated property name to value for one struct."""
    return {base_name(prop.name): prop.value for prop in struct.properties}


def authored_guid(index: int) -> str:
    """Return the authored decoration for the ``index``-th distinct GUID.

    Alphanumeric, because ``lanternlight.redact``'s structural name-field rule
    matches a decoration as ``[0-9A-Za-z]{1,64}`` and has to keep seeing
    through an authored one. Never a hex run, because that is the whole point.
    """
    stem = f"{_AUTHORED_GUID_PREFIX}{index:0{_GUID_INDEX_DIGITS}d}"
    if len(stem) > _GUID_WIDTH:
        raise BuildError(f"more distinct GUIDs than {_GUID_WIDTH} characters allow")
    return stem + "Z" * (_GUID_WIDTH - len(stem))


def authored_native_payload(length: int) -> bytes:
    """Return ``length`` authored bytes, none of them zero.

    Used only where the game wrote a payload that is entirely zero. See the
    block above :data:`_MAX_AUTHORED_PAYLOAD` for why that case cannot be
    committed as written.
    """
    if not 0 < length <= _MAX_AUTHORED_PAYLOAD:
        raise BuildError(f"no authored payload defined for {length} bytes")
    return bytes(range(1, length + 1))


def guid_registry(raw: bytes) -> dict[str, str]:
    """Map every distinct 32-hex run in ``raw`` to an authored replacement.

    Ordered by first appearance in the file, so the mapping is a function of
    the source bytes alone and re-running this script on the same capture
    produces the same fixture.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for match in _HEX32.finditer(raw.decode("latin-1")):
        guid = match.group(0)
        if guid not in seen:
            seen.add(guid)
            ordered.append(guid)
    if not ordered:
        raise BuildError("no 32-hex runs in the source; this is not that save")
    return {guid: authored_guid(index) for index, guid in enumerate(ordered)}


def _top(save, name: str) -> Property:
    for prop in save.property_list:
        if base_name(prop.name) == name:
            return prop
    raise BuildError(f"the source carries no top-level {name!r}")


# --------------------------------------------------------------------------
# JSON payloads
# --------------------------------------------------------------------------


def shrink_json(node: object, limit: int = _KEEP_JSON_ELEMENTS) -> object:
    """Truncate every list, and every map-shaped dict, to ``limit`` entries.

    A dict is treated as a MAP - and therefore truncated - only when every one
    of its keys is a number written as a string, which is how this game spells
    a keyed collection inside JSON (``activatedBag`` is keyed by bag id). A dict
    with named keys is a RECORD and keeps all of its fields, because dropping
    one would pin a record shape the game does not write.
    """
    if isinstance(node, list):
        return [shrink_json(item, limit) for item in node[:limit]]
    if isinstance(node, dict):
        items = list(node.items())
        if items and all(key.lstrip("-").isdigit() for key in node):
            items = items[:limit]
        return {key: shrink_json(value, limit) for key, value in items}
    return node


def _author_json_strings(node: object, registry: dict[str, str]) -> object:
    """Replace hex GUIDs and long digit runs inside a decoded JSON payload."""
    if isinstance(node, list):
        return [_author_json_strings(item, registry) for item in node]
    if isinstance(node, dict):
        return {key: _author_json_strings(value, registry) for key, value in node.items()}
    if isinstance(node, str):
        if node in registry:
            return registry[node]
        if _LONG_DIGITS.fullmatch(node):
            return AUTHORED_ROLE_ID
    return node


def _rewrite_json(text: str, registry: dict[str, str], *, shrink: bool) -> str:
    """Decode, edit and re-emit one JSON payload in the game's own spelling."""
    data = json.loads(text)
    if shrink:
        data = shrink_json(data)
    data = _author_json_strings(data, registry)
    return json.dumps(data, separators=_JSON_SEPARATORS)


#: Properties whose value is a JSON blob big enough to be worth truncating.
_JSON_PROPERTIES = frozenset(
    {
        "Inventory",
        "TreasurableItems",
        "TreasureData",
        "DamageCollectonDataSet",  # the game's own spelling
    }
)

#: A JSON blob that is kept whole because it is already small and because it
#: carries an identifier this fixture exists to show authored.
_SMALL_JSON_PROPERTIES = frozenset({"ItemCell"})


# --------------------------------------------------------------------------
# choosing which container entries survive
# --------------------------------------------------------------------------


def pick_doors(pairs: tuple) -> tuple:
    """Keep two doors that differ in BOTH enumerators.

    ``ByteProperty`` is written as an FString of a qualified enumerator here,
    not as a raw byte, and a fixture carrying one door state twice would let a
    reader that pinned a single literal pass. Two differing values in each of
    the two enums is what keeps that shape exercised.
    """
    first = pairs[0]
    head = _fields(first[1])
    for pair in pairs[1:]:
        row = _fields(pair[1])
        if row["Opened"] != head["Opened"] and row["Locked"] != head["Locked"]:
            return (first, pair)
    raise BuildError("no two DoorData entries differ in both enumerators")


def pick_monsters(pairs: tuple) -> tuple:
    """Keep one live monster and one dead one.

    The two are not the same shape: a dead monster carries a non-empty
    ``TreasurableItems`` JSON blob and a live one carries an empty FString, so
    keeping only one of them would drop a measured case.
    """
    alive = next((p for p in pairs if not _fields(p[1])["Dead"]), None)
    dead = next((p for p in pairs if _fields(p[1])["Dead"]), None)
    if alive is None or dead is None:
        raise BuildError("MonsterData carries only one liveness state")
    return (alive, dead)


def pick_drops(pairs: tuple) -> tuple:
    """Keep one dropped item that names an owner and one that names none.

    ``ownerRoleId`` is the identifier this container exists to sanitise, so a
    fixture without one would stop pinning the case. The ``null`` owner is the
    other measured spelling - a JSON null rather than an empty string - and
    keeping both is what stops a consumer from assuming the field is a string.
    """
    owned = None
    unowned = None
    for pair in pairs:
        cell = json.loads(_fields(pair[1])["ItemCell"])
        owner = cell.get("ownerRoleId")
        if owned is None and isinstance(owner, str) and _LONG_DIGITS.fullmatch(owner):
            owned = pair
        elif unowned is None and owner is None:
            unowned = pair
    if owned is None or unowned is None:
        raise BuildError("DropItemMap does not carry both owner spellings")
    return (owned, unowned)


def pick_id_generator(pairs: tuple) -> tuple:
    """Keep one ``IdGeneratorData`` entry of each measured value shape."""
    kept = []
    for shape in _UUID_SHAPES:
        pattern = re.compile(shape)
        match = next((p for p in pairs if pattern.fullmatch(p[1])), None)
        if match is None:
            raise BuildError(f"IdGeneratorData carries no value matching {shape!r}")
        kept.append(match)
    if len(kept) != _KEEP_ID_ENTRIES:
        raise BuildError("IdGeneratorData selection changed width")
    return tuple(kept)


# --------------------------------------------------------------------------
# the two transform passes
# --------------------------------------------------------------------------


def _content_pass(save, registry: dict[str, str]):
    """Prune containers and author every value that names somebody.

    Names are deliberately untouched here. :func:`lanternlight.gvas.transform`
    builds a child's path out of the name the callback RETURNED, so renaming in
    the same pass that matches on names would make the paths of everything
    below a renamed property depend on the rename. Two passes keep both halves
    readable.
    """
    id_pairs = pick_id_generator(_id_generator_pairs(save))
    num_to_uuid = tuple(
        (key, authored) for (key, _value), authored in zip(id_pairs, AUTHORED_UUIDS, strict=True)
    )
    uuid_to_num = tuple((value, key) for key, value in num_to_uuid)

    def edit(path: tuple[str, ...], prop: Property) -> Property:
        name = base_name(prop.name)
        top = len(path) == 1

        if top and name == "BattleId":
            return replace(prop, value=AUTHORED_BATTLE_ID)
        if top and name == "AutoSaveTempSlot":
            return replace(prop, value=f"StandaloneSlot_{AUTHORED_ROLE_ID}_Temp")
        if top and name == "AutoSaveFinalSlot":
            return replace(prop, value=f"StandaloneSlot_{AUTHORED_ROLE_ID}")

        if name in redact.NAME_BEARING_PROPERTIES:
            return replace(prop, value=redact.AUTHORED_NAME_MARKER)

        if name == "NumIdToUUID":
            return replace(prop, value=MapValue(pairs=num_to_uuid))
        if name == "UUIDToNumId":
            return replace(prop, value=MapValue(pairs=uuid_to_num))

        if name == "DoorData":
            return replace(prop, value=MapValue(pairs=pick_doors(prop.value.pairs)))
        if name == "MonsterData":
            return replace(prop, value=MapValue(pairs=pick_monsters(prop.value.pairs)))
        if name == "DropItemMap":
            return replace(prop, value=MapValue(pairs=pick_drops(prop.value.pairs)))
        if name in ("TreasureBoxMap", "LevelDetail", "Id2cnt"):
            return replace(
                prop, value=MapValue(pairs=prop.value.pairs[:_KEEP_MAP_ENTRIES])
            )
        if name in ("Normal", "TeamOpenTreasuresData", "AssistMonsterCount"):
            return replace(prop, value=MapValue(pairs=prop.value.pairs[:1]))

        if isinstance(prop.value, UndecodedStruct) and not any(prop.value.data):
            return replace(
                prop,
                value=replace(
                    prop.value, data=authored_native_payload(len(prop.value.data))
                ),
            )

        if isinstance(prop.value, str) and prop.value:
            if name in _JSON_PROPERTIES:
                return replace(
                    prop, value=_rewrite_json(prop.value, registry, shrink=True)
                )
            if name in _SMALL_JSON_PROPERTIES:
                return replace(
                    prop, value=_rewrite_json(prop.value, registry, shrink=False)
                )
        return prop

    return transform(save, edit)


def _id_generator_pairs(save) -> tuple:
    """The source's ``NumIdToUUID`` pairs, or a clear failure."""
    holder = _top(save, "IdGeneratorData")
    if not isinstance(holder.value, StructValue):
        raise BuildError("IdGeneratorData is not a struct")
    for prop in holder.value.properties:
        if base_name(prop.name) == "NumIdToUUID":
            if not isinstance(prop.value, MapValue):
                raise BuildError("NumIdToUUID is not a map")
            return prop.value.pairs
    raise BuildError("IdGeneratorData carries no NumIdToUUID")


def _name_pass(save, registry: dict[str, str]):
    """Author every Blueprint GUID, in a property name or in a string value."""

    def edit(_path: tuple[str, ...], prop: Property) -> Property:
        name = prop.name
        match = _DECORATION.match(name)
        if match is not None:
            guid = match.group("guid")
            if guid not in registry:
                raise BuildError("a property name carries a GUID the raw scan missed")
            name = f"{match.group('base')}_{match.group('index')}_{registry[guid]}"
        value = prop.value
        if isinstance(value, str) and _HEX32.search(value):
            value = _HEX32.sub(lambda m: registry.get(m.group(0), m.group(0)), value)
        if name == prop.name and value is prop.value:
            return prop
        return replace(prop, name=name, value=value)

    return transform(save, edit)


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------


def findings(raw: bytes) -> list[str]:
    """Return every reason the fixture built from ``raw`` may not be committed.

    FOUR scans, over TWO artifacts, and the second artifact is the one that is
    easy to forget. ``raw`` is what the fixture decodes to; the file that gets
    committed is its base64, and the repository's guards read that file as
    TEXT before they read it as an encoding. A first pass here scanned only the
    save bytes and the decoded view of the base64, and missed a ``PRODUCTUSERID``
    that the tree scan then found in the base64 itself - 24 zero bytes encode to
    32 ``A`` characters, and ``A`` is a hex digit. So the encoded form is
    scanned both ways too.

    ``ALL_LABELS`` rather than ``FILE_SCAN_LABELS``: the tree scan drops
    ``IPV4`` because a source tree is full of version strings, and a save file
    is not, so this is deliberately the stricter of the two.

    Findings are described, never quoted. This function runs at the exact
    moment something sensitive is known to be present, and a message that
    prints it defeats the purpose of noticing.
    """
    text = raw.decode("latin-1")
    encoded = base64.encodebytes(raw).decode("ascii")
    found = [
        f"{label} in the save bytes at byte {offset}"
        for label, _matched, offset in redact.iter_sensitive(text, labels=redact.ALL_LABELS)
    ]
    found += [
        f"{label} inside {description} of the save bytes at byte {offset}"
        for label, description, offset in redact.iter_encoded_sensitive(
            text, labels=redact.ALL_LABELS
        )
    ]
    found += [
        f"{label} in the committed base64 at byte {offset}"
        for label, _matched, offset in redact.iter_sensitive(
            encoded, labels=redact.ALL_LABELS
        )
    ]
    found += [
        f"{label} inside {description} of the committed base64"
        for label, description, _offset in redact.iter_encoded_sensitive(
            encoded, labels=redact.ALL_LABELS
        )
    ]
    return found


def build(source: bytes) -> bytes:
    """Return the sanitised, pruned fixture bytes, or raise.

    The scan runs HERE rather than in :func:`main`, so that no caller of this
    function - including a future test, or a future script - can obtain
    unsanitised bytes from it by forgetting to check.
    """
    registry = guid_registry(source)
    save = parse(source)
    save = _content_pass(save, registry)
    save = _name_pass(save, registry)
    raw = serialise(save)

    # The output must still be the file it claims to be. serialise() raises on
    # anything it cannot account for, and re-parsing proves the result is a
    # save rather than merely a byte string that came out of a writer.
    round_tripped = parse(raw)
    if not round_tripped.is_complete or round_tripped.undecoded_trailing:
        raise BuildError("the sanitised save no longer parses whole")
    if serialise(round_tripped) != raw:
        raise BuildError("the sanitised save does not round-trip")

    leaks = findings(raw)
    if leaks:
        raise BuildError(
            f"refusing to emit a fixture with {len(leaks)} finding(s): "
            + "; ".join(leaks)
        )
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="path to a captured .sav")
    parser.add_argument(
        "--out",
        type=Path,
        default=FIXTURE_PATH,
        help="where to write the base64 fixture",
    )
    args = parser.parse_args(argv)

    raw = build(args.source.read_bytes())

    # Atomic, and written as BYTES so Windows cannot turn the line endings into
    # CRLF behind the wrapper. The fixtures are LF and a test says so.
    body = base64.encodebytes(raw)
    tmp = args.out.with_name(args.out.name + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(args.out)

    print(f"{args.out}: {len(raw)} raw bytes, {len(body)} base64 bytes")
    return 0


if __name__ == "__main__":  # pragma: no cover - a script entry point
    raise SystemExit(main())
