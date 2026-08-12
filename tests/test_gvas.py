"""Tests for lanternlight.gvas against the game's real save files.

Fixtures - what they are, and what was done to them
--------------------------------------------------

``tests/fixtures/gvas/*.gvas.b64`` are derived from the files the game writes
into ``%LOCALAPPDATA%/MistfallHunter/Saved/SaveGames/``, measured on
2026-08-09, base64-encoded. The **structure** is the engine's - the 1760-byte
custom-version table, every property name, every type name, every length - and
the **values** are this repository's, spliced over the engine's wherever the
engine's value described the operator's machine, account or progress rather
than the format.

A fixture is an authored artifact, not a raw dump. For one commit three of
these were byte-identical to the live saves; they scanned clean, which is
exactly the trap, because "clean" is a claim about the shapes
:mod:`lanternlight.redact` knows rather than about the bytes. A dump publishes
every field the game writes, including the ones nobody has decoded.
``tests/test_gvas_fixtures.py`` is the mechanical guard that keeps them from
drifting back into copies; the splices themselves are listed below.

The save set is not fixed
-------------------------

``Deck.sav`` did not exist when this reader was written. It appeared during a
session, making a five-file save set a six-file one, and the fixture set that
had been pinned at five silently stopped covering the surface. So every check
here that ranges over "the fixtures" enumerates the directory, and
:data:`FIXTURES` is a registry the enumeration is checked against rather than
the list the tests walk.

Why base64 rather than the files themselves
-------------------------------------------

``.gitignore`` line 82 is ``*.sav``. That rule exists so that a stray copy of
the operator's save directory can never be committed, and it is not this lane's
file to weaken; ``git add -f`` would have smuggled a binary past a deliberate
guard and left it invisible to the untracked-file walker every other guard
depends on. So the fixtures are committed as text instead.

Base64 also keeps ``tests/test_ascii_hygiene.py`` honest. ``tests/_tracked.py``
excludes ``.sav`` from the hygiene walk by suffix but knows nothing about a
hypothetical ``.gvas``, so committing raw bytes under a fresh extension would
have failed the ASCII guard on the first high byte. Base64 is 7-bit ASCII and
passes that guard truthfully rather than by exemption.

What it does NOT buy: ``tests/test_no_pii.py`` will scan these files and learn
nothing, because base64 hides every shape its detectors look for.
:func:`test_fixtures_carry_no_identifiers` decodes first and is the only real
coverage this directory has.

The redactions and the splices
------------------------------

Found by scanning, and therefore also caught by the repo-wide guards:

1. ``CampData_<19-digit userId>.sav`` -> ``camp_data.gvas.b64``. **The userId is
   in the FILENAME**, not in the contents, so content-only redaction would have
   published it in the directory listing.
2. ``Notice.sav`` ``readedGameBulletinId``: a 19-digit id, replaced with
   ``<LONG_ID>``, Size patched from 24 to 14. The ``LONG_ID`` detector fires on
   it. It is very likely a bulletin id rather than operator data, and it is
   redacted anyway - over-redaction costs a duller fixture, and under-redaction
   costs a permanent public record.

Found by parsing, which is the only way they could be found:

3. ``LoginOptions.sav``, the account-name property: the ``TextProperty``
   payload string was replaced with the placeholder below and the tag's 4-byte
   Size patched from 23 to 28. **No detector in lanternlight.redact fires on
   that value in the raw file** - GVAS separates a key from its value by a type
   name and a tag, so the keyed shape the redactor looks for never occurs.
4. ``CampData`` ``LevelModeMap``: progression state. One int->int pair kept, so
   the shape is the engine's; the pair is now ``{3: 5}`` rather than two equal
   numbers, so a decoder that swapped key and value would fail here.
5. ``Deck`` ``DeckDefaultOpenPage``: UI state. Two pairs kept - the only
   capture that runs the pair loop more than once - values authored, one of
   them zero so "measured zero" stays covered.
6. ``UserSettings_v1``: ``AutoDetectedBenchmarkCPUResult`` and
   ``...GPUResult`` are hardware fingerprints, the quality levels are derived
   from them, and DLSS and ray-tracing settings name a GPU class. Every number
   in the file is authored (a rising ladder, so a mis-offset read is obvious,
   with one non-integer double so an int decoder could not masquerade as the
   double one), and two bools are flipped so the set is not the operator's
   preferences. Both bool states are still present, in both directions, because
   the value of a ``BoolProperty`` lives in tag flag ``0x10`` and nothing else
   pins that decode.
7. ``EnhancedInputUserSettings``: the ``EnhancedPlayerMappableKeyProfile_``
   instance suffix is a runtime object id, and the two bound keys are the
   operator's own configuration. All three replacements are the **same length**
   as what they replaced, so no ``Size`` moved and the 627-byte trailing block
   is still 627 bytes. The replacement keys are real Unreal ``EKeys`` names, so
   the fixture still says something true about the format's vocabulary, and two
   rows stay bound so the key-profile decode stays under test.

Deliberately NOT changed: ``SelectedServer`` is ``official_NA``, a server
region the game offers to everyone. It names a continent-sized region and no
person, and a fixture carrying one real ``TextProperty`` value is worth more
than one with a placeholder in every string. Property names, type names, the
header and the class paths are the game's vocabulary rather than the operator's
data, and replacing those would leave a fixture that pins nothing.

Synthetic saves
---------------

The format edge cases - an unmeasured property type, an unmeasured map
parameterisation, a truncated stream - are exercised against blobs built by
:func:`_save` rather than against captured bytes. The game does not write those
shapes, so there is nothing to capture, and a synthetic blob lets a test point
at the byte that is wrong. The real fixtures are what stop that builder from
drifting into a private dialect: the engine wrote them, so if the builder and
the reader agreed on a fiction the fixtures would fail.
"""

import base64
import dataclasses
import json
import re
import struct
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight import paths  # noqa: E402
from lanternlight.gvas import (  # noqa: E402
    EPILOGUE_SIZE,
    KNOWN_PROPERTY_TYPES,
    MAGIC,
    MAX_VALUE_DEPTH,
    MEASURED_BARE_TYPES,
    MEASURED_NATIVE_STRUCTS,
    MEASURED_TEXT_HISTORIES,
    MEASURED_TRAILING_OBJECT_CLASS,
    ArrayValue,
    GvasParseError,
    GvasSave,
    GvasSerialiseError,
    MapValue,
    Property,
    SourceText,
    StructValue,
    TextValue,
    TypeName,
    UndecodedStruct,
    UnknownPropertyTypeError,
    load,
    parse,
    rebuild,
    serialise,
    transform,
)
from lanternlight.redact import (  # noqa: E402
    ALL_LABELS,
    AUTHORED_NAME_MARKER,
    NAME_BEARING_PROPERTIES,
    iter_encoded_sensitive,
    iter_sensitive,
)

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "gvas"

#: Every fixture, with the Blueprint class path the game recorded in it. This
#: is a registry, not the list the tests walk: ``test_the_fixture_registry_and
#: _the_directory_agree`` enumerates the directory and fails if the two drift,
#: so a fixture added without a class path here is a failure rather than an
#: uncovered file.
FIXTURES: dict[str, str] = {
    "camp_data.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Camp/CampSaveData.CampSaveData_C"
    ),
    "deck.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Deck/DeckSaveData.DeckSaveData_C"
    ),
    "enhanced_input_user_settings.gvas.b64": (
        "/Game/Project/Misc/Input/BP_InputSettings.BP_InputSettings_C"
    ),
    "login_options.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Login/LoginSaveData.LoginSaveData_C"
    ),
    "notice.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Notice/NoticeSaveData.NoticeSaveData_C"
    ),
    "standalone_slot.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Level/StandaloneLevelSaveData."
        "StandaloneLevelSaveData_C"
    ),
    "user_settings_v1.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Settings/SettingsSaveData.SettingsSaveData_C"
    ),
}

#: The placeholder the account-name property was rewritten to. Assembled at
#: runtime so this file never carries the keyed shape the PII guard hunts for.
ACCOUNT_PLACEHOLDER = "<" + "ACCOUNT" + "_NAME>"


def _fixture_bytes(name: str) -> bytes:
    """Decode one committed fixture back into the engine's bytes."""
    return base64.b64decode((FIXTURE_DIR / name).read_text(encoding="ascii"))


def _fixture(name: str) -> GvasSave:
    return parse(_fixture_bytes(name))


# --------------------------------------------------------------------------
# synthetic GVAS construction - see the module docstring for why these exist
# --------------------------------------------------------------------------

_SYNTHETIC_CLASS = "/Game/Test/TestSave.TestSave_C"


def _fstring(text: str) -> bytes:
    """Serialise an FString the way the engine does: length includes the NUL."""
    raw = text.encode("ascii") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _header(class_name: str = _SYNTHETIC_CLASS) -> bytes:
    """A GVAS header with an empty custom-version table."""
    return b"".join(
        (
            MAGIC,
            struct.pack("<i", 3),  # save game file version
            struct.pack("<i", 522),  # package file version UE4
            struct.pack("<i", 1018),  # package file version UE5
            struct.pack("<HHHI", 5, 7, 4, 0),  # engine version
            _fstring("UE5"),  # engine branch
            struct.pack("<i", 3),  # custom version format
            struct.pack("<i", 0),  # custom version count
            _fstring(class_name),
        )
    )


def _type(name: str, *params: bytes | str) -> bytes:
    """Serialise a recursive property type name: name, param count, params.

    A parameter may be a bare string, which becomes a leaf type name, or bytes
    already produced by this function, which is how the nested shapes the game
    actually writes get built - a struct spells its own name, and that name
    spells its package path, and only then does the GUID follow.
    """
    parts = [_fstring(name), struct.pack("<i", len(params))]
    for param in params:
        parts.append(param if isinstance(param, bytes) else _type(param))
    return b"".join(parts)


def _prop_typed(name: str, type_bytes: bytes, value: bytes = b"", flags: int = 0) -> bytes:
    """One tagged property whose type name is already serialised."""
    return b"".join(
        (_fstring(name), type_bytes, struct.pack("<i", len(value)), bytes([flags]), value)
    )


def _prop(
    name: str,
    type_name: str,
    value: bytes = b"",
    params: tuple[str, ...] = (),
    flags: int = 0,
) -> bytes:
    """One tagged property: name, type name, type params, size, flags, value."""
    return _prop_typed(name, _type(type_name, *params), value, flags)


def _save(
    *properties: bytes,
    trailing: bytes = b"\0\0\0\0",
    class_name: str = _SYNTHETIC_CLASS,
) -> bytes:
    """A whole synthetic save: header, tag-extension byte, properties, None."""
    return b"".join((_header(class_name), b"\0", *properties, _fstring("None"), trailing))


def _int_prop(name: str, value: int) -> bytes:
    return _prop(name, "IntProperty", struct.pack("<i", value))


def _bool_prop(name: str, value: bool) -> bytes:
    return _prop(name, "BoolProperty", b"", flags=0x10 if value else 0x00)


def _text_prop(name: str, namespace: str, key: str, source: str) -> bytes:
    """A TextProperty carrying a source history: namespace, key, source."""
    body = b"".join(
        (
            struct.pack("<i", 8),  # FText flags
            bytes([0x00]),  # history: source
            _fstring(namespace),
            _fstring(key),
            _fstring(source),
        )
    )
    return _prop(name, "TextProperty", body)


#: A stand-in for the dashed hex string the engine writes as a game struct's
#: second type parameter. Authored: the real ones are this game's Blueprint
#: struct GUIDs and nothing here depends on their values.
_STRUCT_GUID = "1234abcd-5678-ef90-1234-56789abcdef0"


def _struct_type(
    struct_name: str = "F_TestData",
    path: str = "/Game/Test/F_TestData",
    guid: str | None = _STRUCT_GUID,
) -> bytes:
    """A StructProperty type name, in the shape measured off StandaloneSlot.

    Two forms occur there and both are built here. A game struct spells its
    name, that name's package path, and then a GUID as a second parameter; an
    engine core struct (Vector, Quat, Transform) spells only the first, with no
    GUID parameter at all. Pass ``guid=None`` for the engine form.
    """
    params: list[bytes] = [_type(struct_name, _type(path))]
    if guid is not None:
        params.append(_type(guid))
    return _type("StructProperty", *params)


def _struct_body(*properties: bytes) -> bytes:
    """A struct payload: a tagged property list closed by "None".

    Deliberately no epilogue. The four-byte epilogue follows the outer object's
    property list and a trailing object's, and measurably does NOT follow a
    nested struct's - the struct lands exactly on its tag's Size.
    """
    return b"".join((*properties, _fstring("None")))


def _struct_prop(
    name: str,
    *properties: bytes,
    struct_name: str = "F_TestData",
    path: str = "/Game/Test/F_TestData",
    guid: str | None = _STRUCT_GUID,
    body: bytes | None = None,
    flags: int = 0,
) -> bytes:
    """A tagged StructProperty whose value is a nested property list."""
    payload = _struct_body(*properties) if body is None else body
    return _prop_typed(name, _struct_type(struct_name, path, guid), payload, flags)


def _map_prop(name: str, key_type: bytes, value_type: bytes, body: bytes) -> bytes:
    """A tagged MapProperty. ``body`` is keys-to-remove, count, then pairs."""
    return _prop_typed(name, _type("MapProperty", key_type, value_type), body)


def _map_body(*pairs: bytes, count: int | None = None, removes: int = 0) -> bytes:
    return b"".join(
        (
            struct.pack("<i", removes),
            struct.pack("<i", len(pairs) if count is None else count),
            *pairs,
        )
    )


def _array_prop(name: str, element_type: bytes, *elements: bytes) -> bytes:
    """A tagged ArrayProperty: an int32 count, then bare elements."""
    body = struct.pack("<i", len(elements)) + b"".join(elements)
    return _prop_typed(name, _type("ArrayProperty", element_type), body)


def _byte_prop(
    name: str,
    enumerator: str,
    enum_name: str = "E_TestState",
    path: str = "/Game/Test/E_TestState",
    with_enum_param: bool = True,
) -> bytes:
    """A tagged ByteProperty, whose value is the qualified enumerator name.

    The engine writes the enumerator as an FString here rather than as a raw
    byte, and names the enum as the type's one parameter. ``with_enum_param``
    builds the parameterless form, which has never been observed.
    """
    params = (_type(enum_name, _type(path)),) if with_enum_param else ()
    return _prop_typed(name, _type("ByteProperty", *params), _fstring(enumerator))


def _mapping(name: str, keys: tuple[str, str, str], tail: bytes = b"\0" * 6) -> bytes:
    """One row of a key profile's mapping table."""
    return b"".join((_fstring(name), *(_fstring(k) for k in keys), tail))


def _profile(
    *properties: bytes,
    class_path: str = MEASURED_TRAILING_OBJECT_CLASS,
    object_name: str = "EnhancedPlayerMappableKeyProfile_1",
    mappings: tuple[bytes, ...] = (),
    mapping_count: int | None = None,
    identifier: str = "InputUserSettings.Profiles.Default",
    epilogue: bytes = b"\0\0\0\0",
    sentinel: str = "ObjectEnd",
) -> bytes:
    """One serialised object of the kind the trailing section carries."""
    count = len(mappings) if mapping_count is None else mapping_count
    return b"".join(
        (
            _fstring(class_path),
            _fstring(object_name),
            struct.pack("<i", count),
            *mappings,
            _fstring(identifier),
            b"\0",  # tag-extension byte
            *properties,
            _fstring("None"),
            epilogue,
            _fstring(sentinel),
        )
    )


def _trailing(
    *profiles: bytes,
    epilogue: bytes = b"\0\0\0\0",
    header: int = 2,
    object_count: int | None = None,
) -> bytes:
    """A whole trailing region: epilogue, section header, objects."""
    count = len(profiles) if object_count is None else object_count
    return b"".join(
        (epilogue, struct.pack("<i", header), struct.pack("<i", count), *profiles)
    )


# --------------------------------------------------------------------------
# the real files
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_exists(name: str):
    assert (FIXTURE_DIR / name).is_file()


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_no_fixture_is_gitignored(name: str):
    # The first version of these fixtures was committed as .sav and silently
    # matched .gitignore line 82, so they existed locally, passed every test,
    # and would have been absent from a fresh clone. Cheap guard, real trap.
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", f"tests/fixtures/gvas/{name}"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    # 0 means "this path is ignored", 1 means "it is not".
    assert proc.returncode == 1, f"{name} is gitignored and would vanish from a clone"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_file_parses_into_plain_dicts(name: str):
    save = _fixture(name)
    assert isinstance(save, GvasSave)
    assert save.header.save_game_class_name == FIXTURES[name]
    assert save.save_game_class_name == FIXTURES[name]
    assert type(save.properties) is dict
    assert save.properties, "every one of these files carries at least one property"
    assert save.is_complete
    assert save.unknown_properties == ()


def test_the_fixture_registry_and_the_directory_agree():
    # Enumerated rather than counted. The set of save files the game writes is
    # not fixed - Deck.sav appeared mid-session - so a test asserting "there
    # are exactly five" both fails for the right reason and, once somebody
    # bumps the number, stops being a check that each fixture is registered.
    found = sorted(p.name for p in FIXTURE_DIR.iterdir() if p.is_file())
    assert found == sorted(FIXTURES), (
        "a fixture on disk has no class path registered in FIXTURES, or a "
        "registered fixture is missing from the directory"
    )


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_header_is_the_measured_ue5_shape(name: str):
    header = _fixture(name).header
    assert header.save_game_version == 3
    assert header.package_file_version_ue4 == 522
    assert header.package_file_version_ue5 == 1018
    assert (header.engine_version.major, header.engine_version.minor) == (5, 7)
    assert header.engine_version.patch == 4
    assert header.engine_version.branch == "UE5"
    assert str(header.engine_version) == "5.7.4-0+UE5"
    assert header.custom_version_format == 3
    assert len(header.custom_versions) == 88
    assert all(len(cv.guid) == 16 for cv in header.custom_versions)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_starts_with_the_gvas_magic(name: str):
    assert _fixture_bytes(name).startswith(MAGIC)


def test_login_options_values():
    save = _fixture("login_options.gvas.b64")
    assert sorted(save.properties) == ["AccountName", "SDKType", "SelectedServer"]
    assert save.properties["SelectedServer"] == "official_NA"
    assert save.properties["SDKType"] == 2
    assert save.properties["AccountName"] == ACCOUNT_PLACEHOLDER
    assert save.property_types["SelectedServer"] == "TextProperty"
    assert save.property_types["SDKType"] == "IntProperty"


def test_user_settings_values():
    # Every number here is authored - see the module docstring. What the file
    # pins is the *encoding*: a DoubleProperty is 8 little-endian IEEE-754
    # bytes and an IntProperty is 4, at the offsets the engine's own property
    # names and Size fields put them. The values rise so a read that landed one
    # property off would come back with a neighbour's number rather than a
    # plausible one, and lowQualityResLimit is deliberately not a whole number
    # so an int decoder could not pass as the double one.
    props = _fixture("user_settings_v1.gvas.b64").properties
    assert props["bWarehouseAutomation"] is True
    assert props["bHasFirstSetup"] is True
    assert props["bEnableCrossPlay"] is True
    assert props["DLSSMode"] == 7
    assert props["AnimationQuality"] == 8
    assert props["AutoDetectedBenchmarkCPUResult"] == 1.0
    assert props["AutoDetectedBenchmarkGPUResult"] == 2.0
    assert props["FirstTimeAutoSetQualityLevel"] == 3.0
    assert props["LatestManualLevel"] == 4.0
    assert props["RayTracingQuality"] == 5.0
    assert props["lowQualityResLimit"] == 6.5
    assert len(props) == 14


def test_user_settings_property_types_are_the_engines():
    # The splices moved values, never types. This is the assertion that would
    # catch a sanitising pass that quietly turned a double into something else
    # and left a fixture pinning a format the game does not write.
    types = _fixture("user_settings_v1.gvas.b64").property_types
    assert types["bWarehouseAutomation"] == "BoolProperty"
    assert types["DLSSMode"] == "IntProperty"
    assert types["AutoDetectedBenchmarkCPUResult"] == "DoubleProperty"
    assert sorted(set(types.values())) == ["BoolProperty", "DoubleProperty", "IntProperty"]


def test_a_false_bool_is_a_measurement_not_an_absence():
    # A False bool has to come back present-and-False; a reader that dropped it
    # would be reporting "unmeasured" for something the file plainly states.
    # bMotionBlurEnabled is the engine's own False - it was False in the capture
    # and was left alone - and the sanitising pass kept both bool states present
    # deliberately, because a BoolProperty's value lives in tag flag 0x10 and a
    # fixture with only True bools would not pin the other branch.
    props = _fixture("user_settings_v1.gvas.b64").properties
    assert "bMotionBlurEnabled" in props
    assert props["bMotionBlurEnabled"] is False
    bools = {k: v for k, v in props.items() if isinstance(v, bool)}
    assert True in bools.values()
    assert False in bools.values()


def test_camp_data_map_property():
    # One pair, as the engine wrote it. The pair itself is authored, and the
    # key and the value are different numbers on purpose: the real file carried
    # equal ones, which a decoder that swapped them would have passed.
    save = _fixture("camp_data.gvas.b64")
    assert save.properties == {"LevelModeMap": {3: 5}}
    assert save.property_types["LevelModeMap"] == "MapProperty<IntProperty, IntProperty>"


def test_deck_map_property_carries_more_than_one_pair():
    # Deck.sav is the only capture whose map runs the pair loop more than once,
    # which is what makes it worth a fixture of its own rather than a second
    # copy of CampData's shape. The zero value is kept: a MapProperty that
    # decoded an absent pair and a zero-valued one the same way would be
    # conflating "unmeasured" with "measured zero".
    save = _fixture("deck.gvas.b64")
    assert save.properties == {"DeckDefaultOpenPage": {2: 3, 4: 0}}
    assert (
        save.property_types["DeckDefaultOpenPage"] == "MapProperty<IntProperty, IntProperty>"
    )
    assert save.properties["DeckDefaultOpenPage"][4] == 0


def test_notice_and_enhanced_input_values():
    assert _fixture("notice.gvas.b64").properties == {
        "readedGameBulletinId": "<LONG_ID>"
    }
    assert _fixture("enhanced_input_user_settings.gvas.b64").properties == {
        "CurrentProfileIdentifierString": "InputUserSettings.Profiles.Default"
    }


#: The one fixture that serialises objects after its tagged properties. Named
#: once, and every "all the quiet files" check below is the enumerated set
#: minus this one - so a new save file joins those checks by existing rather
#: than by being added to a list.
NOISY = "enhanced_input_user_settings.gvas.b64"

#: Every other fixture, derived rather than listed.
QUIET = sorted(set(FIXTURES) - {NOISY})


def test_trailing_bytes_are_exposed_rather_than_dropped():
    # Every file but one carries exactly four zero bytes after the None
    # terminator. EnhancedInputUserSettings carries 627, because that object
    # serialises its key profiles after its tagged properties and ends with a
    # literal ObjectEnd. The point of this test is that the reader does not
    # pretend either region is absent.
    for name in QUIET:
        save = _fixture(name)
        assert save.trailing == b"\0\0\0\0"
        assert save.has_trailing_bytes

    enhanced = _fixture("enhanced_input_user_settings.gvas.b64")
    assert len(enhanced.trailing) == 627
    assert enhanced.trailing.startswith(b"\0\0\0\0")
    assert enhanced.trailing.endswith(_fstring("ObjectEnd"))


def test_load_reads_a_file_without_writing_to_it(tmp_path: Path):
    # The real save directory is operator data. A reader that touches it is a
    # bug with a permanent cost, so this pins bytes and mtime across a load.
    path = tmp_path / "login_options.sav"
    path.write_bytes(_fixture_bytes("login_options.gvas.b64"))
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    save = load(path)

    assert save.properties["SDKType"] == 2
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime


def test_load_accepts_a_string_path(tmp_path: Path):
    path = tmp_path / "notice.sav"
    path.write_bytes(_fixture_bytes("notice.gvas.b64"))
    assert load(str(path)).properties["readedGameBulletinId"] == "<LONG_ID>"


def test_missing_file_raises_rather_than_returning_an_empty_save(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "does_not_exist.sav")


# --------------------------------------------------------------------------
# the acceptance criterion that matters: unmeasured types raise
# --------------------------------------------------------------------------


def test_unknown_property_type_raises():
    # FloatProperty is a real Unreal type that this game has never been
    # observed writing, so this reader has never measured its encoding. A
    # reader that guessed would be inventing a number.
    blob = _save(_prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    message = str(excinfo.value)
    assert "Mystery" in message
    assert "FloatProperty" in message


def test_unknown_property_type_is_not_a_partial_parse():
    # The whole failure this guard exists to prevent: a save whose known
    # properties come back looking complete while an unknown one is dropped.
    blob = _save(
        _int_prop("Before", 7),
        _prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)),
        _int_prop("After", 9),
    )
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_unknown_map_parameterisation_raises():
    # This test used to use MapProperty<StrProperty, IntProperty> as its
    # never-measured example. StandaloneSlot_<roleId>.sav, captured 2026-08-09,
    # writes exactly that parameterisation, so the premise was falsified by the
    # game and the example had to move. FloatProperty is the replacement for
    # the same reason it is used above: a real Unreal type this game has never
    # been observed writing.
    body = struct.pack("<ii", 0, 0)
    blob = _save(_prop("Odd", "MapProperty", body, params=("FloatProperty", "IntProperty")))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "FloatProperty" in str(excinfo.value)


def test_unknown_text_history_raises():
    # Two TextProperty history shapes have been measured here: the
    # culture-invariant "none" history (0xff) and the source history (0x00).
    # Anything else is a layout this reader has not seen, and guessing at it
    # would fabricate a string.
    body = struct.pack("<i", 2) + bytes([0x03]) + struct.pack("<i", 1) + _fstring("x")
    blob = _save(_prop("Odd", "TextProperty", body))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_a_native_serialised_value_is_not_decoded_as_a_tagged_one():
    # Tag flag 0x08 says the value went through a native serializer, so the
    # bytes are not the layout measured here even though the type name is.
    blob = _save(_prop("Odd", "IntProperty", struct.pack("<i", 5), flags=0x08))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_a_size_that_disagrees_with_the_type_raises():
    blob = _save(_prop("Odd", "IntProperty", b"\x01\x02"))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_non_strict_records_the_unknown_and_omits_the_value():
    blob = _save(
        _int_prop("Before", 7),
        _prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)),
        _int_prop("After", 9),
    )
    save = parse(blob, strict=False)

    # Omitted, not None and not 0. A missing number is recoverable.
    assert "Mystery" not in save.properties
    assert "Mystery" not in save.property_types
    assert save.properties == {"Before": 7, "After": 9}

    assert not save.is_complete
    assert [u.name for u in save.unknown_properties] == ["Mystery"]
    assert save.unknown_properties[0].type_name == "FloatProperty"
    assert save.unknown_properties[0].size == 4
    assert "Mystery" in save.unknown_properties[0].describe()


def test_non_strict_still_reads_the_property_after_an_unknown_one():
    # Proves the skip length is right. A reader that mis-sized the skip would
    # desynchronise and either raise or invent a property name.
    blob = _save(
        _prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)),
        _int_prop("After", 9),
    )
    save = parse(blob, strict=False)
    assert save.properties == {"After": 9}


def test_known_property_types_is_exactly_what_was_measured():
    # Pinned so that adding a type is a deliberate act with a measurement
    # behind it, not something that drifts in.
    #
    # These are type constructors now, not fully rendered names. They used to
    # be rendered, which meant MapProperty could only be spelled one way;
    # StandaloneSlot writes seven parameterisations of it, and a struct's
    # rendered name embeds a per-struct GUID that nothing should be pinned to.
    # What gates a container now is its ELEMENT types, which is a stricter
    # statement and not a looser one: an element type nobody has measured still
    # raises, and MEASURED_BARE_TYPES gates the container position separately.
    assert sorted(KNOWN_PROPERTY_TYPES) == [
        "ArrayProperty",
        "BoolProperty",
        "ByteProperty",
        "DoubleProperty",
        "IntProperty",
        "MapProperty",
        "StrProperty",
        "StructProperty",
        "TextProperty",
    ]


def test_unknown_property_type_error_is_a_parse_error():
    assert issubclass(UnknownPropertyTypeError, GvasParseError)


# --------------------------------------------------------------------------
# measured zero versus unmeasured
# --------------------------------------------------------------------------


def test_measured_zero_is_distinguishable_from_absent():
    blob = _save(_int_prop("Zero", 0), _bool_prop("Off", False))
    save = parse(blob)
    assert save.properties["Zero"] == 0
    assert save.properties["Off"] is False
    assert "NeverWritten" not in save.properties
    assert save.properties.get("NeverWritten") is None


def test_an_empty_save_is_empty_not_broken():
    save = parse(_save())
    assert save.properties == {}
    assert save.is_complete


# --------------------------------------------------------------------------
# structural failures
# --------------------------------------------------------------------------


def test_bad_magic_raises():
    blob = b"XXXX" + _save()[4:]
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "GVAS" in str(excinfo.value)


def test_empty_input_raises():
    with pytest.raises(GvasParseError):
        parse(b"")


@pytest.mark.parametrize("cut", [8, 40, 60])
def test_truncated_header_raises(cut: int):
    with pytest.raises(GvasParseError):
        parse(_save()[:cut])


def test_an_unmeasured_save_game_version_raises():
    blob = bytearray(_save())
    blob[4:8] = struct.pack("<i", 4)
    with pytest.raises(GvasParseError) as excinfo:
        parse(bytes(blob))
    assert "save_game_version" in str(excinfo.value)


def test_an_unmeasured_tag_extension_raises():
    # The extension byte sits directly after the class name and changes the
    # length of every tag after it, so it cannot be skipped over.
    blob = _save(_int_prop("Zero", 0))
    offset = blob.index(_fstring(_SYNTHETIC_CLASS)) + len(_fstring(_SYNTHETIC_CLASS))
    corrupt = bytearray(blob)
    corrupt[offset] = 0x02
    with pytest.raises(GvasParseError):
        parse(bytes(corrupt))


def test_an_unmeasured_tag_flag_raises():
    blob = _save(_prop("Odd", "IntProperty", struct.pack("<i", 5), flags=0x40))
    with pytest.raises(GvasParseError):
        parse(blob)


def test_a_tag_extension_block_raises():
    # Flag 0x04 announces an extension block of unmeasured length, so nothing
    # after it can be located and there is no partial answer to give.
    blob = _save(_prop("Odd", "IntProperty", struct.pack("<i", 5), flags=0x04))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "extension" in str(excinfo.value)


@pytest.mark.parametrize("strict", [True, False])
def test_a_repeated_property_name_raises_rather_than_overwriting(strict: bool):
    # Overwriting the first value would lose a measurement without saying so,
    # and a repeat means this is not the stream it appears to be. Structural,
    # so it raises in both modes.
    blob = _save(_int_prop("Twice", 1), _int_prop("Twice", 2))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob, strict=strict)
    assert "Twice" in str(excinfo.value)


def test_truncated_property_value_raises():
    blob = _save(_int_prop("Zero", 0))
    with pytest.raises(GvasParseError):
        parse(blob[:-8])


def test_a_length_larger_than_the_file_raises_rather_than_allocating():
    # A corrupt or torn write can carry an FString length of hundreds of
    # megabytes. Bounds-check it rather than trusting it.
    blob = _save()
    corrupt = bytearray(blob)
    offset = blob.index(_fstring("None"))
    corrupt[offset : offset + 4] = struct.pack("<i", 1 << 28)
    with pytest.raises(GvasParseError):
        parse(bytes(corrupt))


def test_missing_none_terminator_raises():
    blob = _header() + b"\0" + _int_prop("Zero", 0)
    with pytest.raises(GvasParseError):
        parse(blob)


def test_a_parsed_save_is_frozen():
    save = parse(_save(_int_prop("Zero", 0)))
    with pytest.raises(FrozenInstanceError):
        save.header = None  # type: ignore[misc]


# --------------------------------------------------------------------------
# the epilogue that follows every property terminator
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_file_carries_a_four_byte_epilogue(name: str):
    save = _fixture(name)
    assert save.epilogue == b"\0\0\0\0"
    assert len(save.epilogue) == EPILOGUE_SIZE


def test_the_epilogue_is_not_end_of_file_padding():
    # The reason this field is called an epilogue and not padding: the same
    # four bytes appear after the key profile's OWN property terminator, 21
    # bytes before the end of the file rather than at it. Six occurrences in
    # total across the five files, all zero, none of them at EOF but four.
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    assert profile.epilogue == b"\0\0\0\0"


def test_the_epilogue_is_handed_back_as_bytes_not_a_number():
    # Every reading that fits - int32 zero, an empty FString, four flag bytes -
    # consumes exactly four bytes, and nothing observed tells them apart. A
    # named guess would be worse than the honest opaque field.
    save = _fixture("notice.gvas.b64")
    assert isinstance(save.epilogue, bytes)


def test_a_file_that_ends_without_an_epilogue_raises():
    blob = _save(_int_prop("Zero", 0), trailing=b"")
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "epilogue" in str(excinfo.value)


def test_a_truncated_epilogue_raises():
    blob = _save(_int_prop("Zero", 0), trailing=b"\0\0")
    with pytest.raises(GvasParseError):
        parse(blob)


# --------------------------------------------------------------------------
# the 627 trailing bytes: one serialised key profile
# --------------------------------------------------------------------------


def test_the_trailing_block_decodes_into_one_key_profile():
    # The instance suffix is authored. Unreal builds these with
    # MakeUniqueObjectName, so the real one is a per-run counter value and says
    # nothing about the format beyond "the name ends in an underscore and
    # digits" - which this one still does, at the same length.
    save = _fixture("enhanced_input_user_settings.gvas.b64")
    assert len(save.key_profiles) == 1
    profile = save.key_profiles[0]
    assert profile.class_path == MEASURED_TRAILING_OBJECT_CLASS
    assert profile.object_name == "EnhancedPlayerMappableKeyProfile_0000000001"
    assert profile.identifier == "InputUserSettings.Profiles.Default"


def test_key_profile_mapping_rows():
    # The mapping NAMES are the game's own input actions and are untouched.
    # The bound keys are the operator's configuration and are authored: two
    # rows stay bound, so the slot-0 decode is still exercised, and both
    # replacements are real Unreal EKeys names of exactly the length they
    # replaced - so no FString length and no enclosing block size moved.
    #
    # What binds slot 0 to a real binding is out of band and remains true of
    # the file this fixture came from: the game log writes "decode key mapping
    # KB_Blackarrow_Major_Action <key>", pairing the same mapping names with
    # the same slot the reader reads.
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    assert [m.name for m in profile.mappings] == [
        "KB_Blackarrow_Major_Action",
        "KB_Blackarrow_Minor_Action",
        "KB_EmptyHands_Minor_Action",
    ]
    assert [m.key_names[0] for m in profile.mappings] == [
        "ThumbMouseButton",
        "MouseScrollDown",
        "None",
    ]
    assert all(m.key_names[1:] == ("None", "None") for m in profile.mappings)


def test_an_unbound_slot_is_the_string_none_not_python_none():
    # "None" is Unreal's unbound-key sentinel and it is what the file says.
    # Translating it to Python None would turn a measured "no key here" into
    # something a caller reads as "not measured".
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    unbound = profile.mappings[2]
    assert unbound.key_names == ("None", "None", "None")
    assert all(k is not None for k in unbound.key_names)


def test_key_mapping_rows_keep_their_undecoded_tail():
    # Six bytes end every row and they are zero in all three. An empty FString
    # plus two bytes fits, an int32 plus two bytes fits, six flag bytes fit,
    # and nothing observed separates them - so the bytes are handed back.
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    assert all(m.undecoded == b"\0" * 6 for m in profile.mappings)


def test_key_profile_tagged_properties():
    # Written as subscripts rather than a dict literal on purpose. A literal
    # puts a quoted key ending in Name immediately before a colon and a quoted
    # value, which is the keyed shape the PERSONA detector in
    # lanternlight.redact hunts for - and it fires on it, measured.
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    props = profile.properties
    assert sorted(props) == ["DisplayName", "ProfileIdentifierString"]
    assert props["ProfileIdentifierString"] == "InputUserSettings.Profiles.Default"
    assert props["DisplayName"] == "Default Profile"
    assert profile.property_types["ProfileIdentifierString"] == "StrProperty"
    assert profile.property_types["DisplayName"] == "TextProperty"
    assert profile.is_complete


def test_the_whole_627_byte_block_is_accounted_for():
    # The acceptance criterion for this slice: nothing in the block is left
    # over. The grammar has to land exactly on the end of the file.
    save = _fixture("enhanced_input_user_settings.gvas.b64")
    assert len(save.trailing) == 627
    assert save.undecoded_trailing == b""
    assert save.object_section_header == struct.pack("<i", 2)


def test_the_section_header_is_not_the_object_count():
    # Stated because it is the reading that had to be ruled out. The header
    # int32 is 2; taking it for the object count demands a second object, and
    # the block ends on the first one's sentinel with zero bytes to spare.
    save = _fixture("enhanced_input_user_settings.gvas.b64")
    assert struct.unpack("<i", save.object_section_header)[0] == 2
    assert len(save.key_profiles) == 1


@pytest.mark.parametrize("name", QUIET)
def test_the_other_files_wrote_no_object_section(name: str):
    # An empty object_section_header is how "the file wrote no section" stays
    # distinguishable from "a section was there and did not decode", which
    # would leave undecoded_trailing non-empty instead.
    save = _fixture(name)
    assert save.trailing == b"\0\0\0\0"
    assert save.object_section_header == b""
    assert save.key_profiles == ()
    assert save.undecoded_trailing == b""


def test_an_unmeasured_trailing_object_class_raises():
    blob = _save(trailing=_trailing(_profile(class_path="/Script/Other.SomethingElse")))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "SomethingElse" in str(excinfo.value)


def test_a_missing_object_end_sentinel_raises():
    blob = _save(trailing=_trailing(_profile(sentinel="NotTheSentinel")))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "ObjectEnd" in str(excinfo.value)


def test_an_object_count_the_block_cannot_hold_raises():
    blob = _save(trailing=_trailing(_profile(), object_count=2))
    with pytest.raises(GvasParseError):
        parse(blob)


def test_a_mapping_count_the_block_cannot_hold_raises():
    blob = _save(trailing=_trailing(_profile(mapping_count=64)))
    with pytest.raises(GvasParseError):
        parse(blob)


def test_bytes_left_over_after_the_last_object_raise():
    blob = _save(trailing=_trailing(_profile()) + b"\x01\x02\x03")
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "3" in str(excinfo.value)


def test_a_key_profile_carries_its_mappings_and_properties():
    blob = _save(
        trailing=_trailing(
            _profile(
                _prop("ProfileIdentifierString", "StrProperty", _fstring("Tag.Name")),
                object_name="Profile_7",
                mappings=(_mapping("Act", ("A", "None", "None")),),
                identifier="Tag.Name",
            )
        )
    )
    profile = parse(blob).key_profiles[0]
    assert profile.object_name == "Profile_7"
    assert profile.identifier == "Tag.Name"
    assert profile.mappings[0].name == "Act"
    assert profile.mappings[0].key_names == ("A", "None", "None")
    assert profile.properties == {"ProfileIdentifierString": "Tag.Name"}


def test_two_objects_in_the_section_both_decode():
    # The count drives the loop rather than the one object ever observed.
    blob = _save(trailing=_trailing(_profile(object_name="P1"), _profile(object_name="P2")))
    assert [p.object_name for p in parse(blob).key_profiles] == ["P1", "P2"]


def test_non_strict_keeps_an_undecodable_trailing_region_verbatim():
    # Same contract as an unmeasured property: omitted rather than faked, and
    # the bytes handed back so the caller can see what was refused.
    section = _trailing(_profile(class_path="/Script/Other.SomethingElse"))
    blob = _save(trailing=section)
    save = parse(blob, strict=False)
    assert save.key_profiles == ()
    assert save.undecoded_trailing == section[EPILOGUE_SIZE:]
    assert save.object_section_header == b""


def test_non_strict_records_an_unknown_property_inside_a_key_profile():
    blob = _save(
        trailing=_trailing(
            _profile(_prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)))
        )
    )
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)
    profile = parse(blob, strict=False).key_profiles[0]
    assert "Mystery" not in profile.properties
    assert [u.name for u in profile.unknown_properties] == ["Mystery"]
    assert not profile.is_complete


def test_a_key_profile_is_frozen():
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    with pytest.raises(FrozenInstanceError):
        profile.identifier = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        profile.mappings[0].name = "x"  # type: ignore[misc]


# --------------------------------------------------------------------------
# FText carrying its own source string
# --------------------------------------------------------------------------


def test_a_source_history_text_decodes_to_its_source_string():
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    assert profile.properties["DisplayName"] == "Default Profile"
    assert isinstance(profile.properties["DisplayName"], str)


def test_a_source_history_text_keeps_its_namespace_and_key():
    # Dropping these would lose two measured strings for no reason. They are
    # what the file says the text is looked up by.
    display = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0].properties[
        "DisplayName"
    ]
    assert isinstance(display, SourceText)
    assert display.namespace == "EnhancedInputMappableUserSettings"
    assert display.key == "Default_Profile_name"


def test_a_source_history_text_is_still_a_plain_string_to_a_caller():
    blob = _save(_text_prop("Label", "NS", "KEY", "Hello"))
    value = parse(blob).properties["Label"]
    assert value == "Hello"
    assert value.upper() == "HELLO"
    assert f"{value}!" == "Hello!"


def test_an_invariant_text_is_not_a_source_text():
    # The two histories are different facts and stay distinguishable: only the
    # source history carries a namespace and a key at all.
    value = _fixture("login_options.gvas.b64").properties["SelectedServer"]
    assert value == "official_NA"
    assert not isinstance(value, SourceText)


def test_a_source_history_text_with_trailing_bytes_raises():
    body = b"".join(
        (
            struct.pack("<i", 8),
            bytes([0x00]),
            _fstring("NS"),
            _fstring("KEY"),
            _fstring("Hello"),
            b"\x01\x02",
        )
    )
    with pytest.raises(UnknownPropertyTypeError):
        parse(_save(_prop("Label", "TextProperty", body)))


def test_measured_text_histories_is_exactly_what_was_measured():
    # Pinned for the same reason KNOWN_PROPERTY_TYPES is: a history byte gets
    # added because it was observed, not because a spec lists it.
    assert sorted(MEASURED_TEXT_HISTORIES) == [0x00, 0xFF]


# --------------------------------------------------------------------------
# StructProperty and the container types, measured off StandaloneSlot
#
# StandaloneSlot_<roleId>.sav is the game's in-run level save. It is NOT
# committed as a fixture: its filename embeds the operator's roleId, and four
# of its properties carry ids derived from it - two of which no detector in
# lanternlight.redact fires on in the raw file. So the shapes below are
# synthetic blobs built to the layout measured off the live capture on
# 2026-08-09, in the same spirit as the other synthetic tests here: the real
# file was the measurement source, and the fixtures that ARE committed are what
# stop these builders from drifting into a private dialect.
# --------------------------------------------------------------------------


def test_a_struct_property_decodes_into_a_nested_dict():
    # The headline shape. A StructProperty's value is a nested tagged property
    # list closed by "None", using the same tag grammar as the outer object,
    # with no epilogue and no length of its own beyond the tag's Size.
    blob = _save(
        _struct_prop(
            "PlayzoneData",
            _int_prop("Wave", 3),
            _prop("Label", "StrProperty", _fstring("zone")),
        )
    )
    save = parse(blob)
    assert save.properties["PlayzoneData"] == {"Wave": 3, "Label": "zone"}
    assert save.property_types["PlayzoneData"] == (
        "StructProperty<F_TestData</Game/Test/F_TestData>, "
        "1234abcd-5678-ef90-1234-56789abcdef0>"
    )
    assert save.is_complete


def test_a_struct_type_name_without_a_guid_parameter_decodes():
    # Engine core structs spell only their name and path; game structs add a
    # GUID. Both forms occur in the same file, so both have to parse.
    blob = _save(
        _struct_prop(
            "Transform",
            _int_prop("Slot", 1),
            struct_name="Transform",
            path="/Script/CoreUObject",
            guid=None,
        )
    )
    save = parse(blob)
    assert save.properties["Transform"] == {"Slot": 1}
    assert save.property_types["Transform"] == (
        "StructProperty<Transform</Script/CoreUObject>>"
    )


def test_a_struct_nested_inside_a_struct_decodes():
    # Measured max nesting is five property-list levels deep. Two is enough to
    # prove the recursion; the cap is tested separately.
    inner = _struct_prop("Rotation", _int_prop("Yaw", 90), struct_name="F_Inner")
    blob = _save(_struct_prop("Outer", inner, _int_prop("Tag", 5)))
    assert parse(blob).properties["Outer"] == {"Rotation": {"Yaw": 90}, "Tag": 5}


def test_a_struct_that_does_not_fill_its_tag_size_raises():
    # The check that keeps a wrong reading of a nested shape from passing
    # silently: the nested list has to land exactly on the tag's Size.
    body = _struct_body(_int_prop("Wave", 3)) + b"\x01\x02\x03"
    blob = _save(_struct_prop("PlayzoneData", body=body))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "3" in str(excinfo.value)


def test_a_struct_missing_its_none_terminator_raises():
    blob = _save(_struct_prop("PlayzoneData", body=_int_prop("Wave", 3)))
    with pytest.raises(GvasParseError):
        parse(blob)


# --------------------------------------------------------------------------
# natively serialised structs: handed back, named, never guessed at
# --------------------------------------------------------------------------


def test_a_native_struct_is_handed_back_verbatim_and_named_undecoded():
    # Vector, Vector2D and Quat are written with tag flag 0x08 and their
    # payload is NOT a property list. The tag's Size bounds it exactly, so
    # handing the bytes back is a fact; reading them as doubles would not be.
    payload = bytes(range(24))
    blob = _save(
        _struct_prop(
            "Translation",
            body=payload,
            struct_name="Vector",
            path="/Script/CoreUObject",
            guid=None,
            flags=0x08,
        )
    )
    value = parse(blob).properties["Translation"]
    assert isinstance(value, UndecodedStruct)
    assert value.struct_name == "Vector"
    assert value.struct_path == "/Script/CoreUObject"
    assert value.data == payload
    assert "Vector" in value.describe()
    assert "undecoded" in value.describe()


def test_a_native_struct_is_not_mistaken_for_a_decoded_one():
    # The distinction this type exists to preserve. A caller that treats a
    # native struct as a decoded struct gets a type error, not a wrong number.
    payload = struct.pack("<ddd", 1.0, 2.0, 3.0)
    blob = _save(
        _struct_prop(
            "Translation",
            body=payload,
            struct_name="Vector",
            path="/Script/CoreUObject",
            guid=None,
            flags=0x08,
        )
    )
    value = parse(blob).properties["Translation"]
    assert not isinstance(value, dict)
    # Three doubles fit the 24 bytes, and the reader still refuses to say so.
    assert value.data == payload
    with pytest.raises(FrozenInstanceError):
        value.data = b""  # type: ignore[misc]


def test_a_native_struct_nested_in_a_decoded_struct_stays_undecoded():
    # Exactly the Transform shape: an ordinary property list whose Rotation is
    # a native Quat and whose Translation is a native Vector.
    rotation = _struct_prop(
        "Rotation",
        body=bytes(32),
        struct_name="Quat",
        path="/Script/CoreUObject",
        guid=None,
        flags=0x08,
    )
    blob = _save(
        _struct_prop(
            "Transform",
            rotation,
            struct_name="Transform",
            path="/Script/CoreUObject",
            guid=None,
        )
    )
    transform = parse(blob).properties["Transform"]
    assert isinstance(transform, dict)
    assert isinstance(transform["Rotation"], UndecodedStruct)
    assert transform["Rotation"].struct_name == "Quat"
    assert len(transform["Rotation"].data) == 32


def test_measured_native_structs_is_exactly_what_was_measured():
    # Recorded because they were watched being emitted, not because a spec
    # lists them. The set does NOT gate the decode - an unlisted native struct
    # is still handed back whole, because opaque bytes are never a guess.
    assert sorted(MEASURED_NATIVE_STRUCTS) == ["Quat", "Rotator", "Vector", "Vector2D"]


def test_two_native_structs_of_the_same_size_stay_distinguishable():
    # Vector and Rotator both carry 24 bytes. Whatever those bytes mean, the
    # only thing telling the two apart is the name, which is the argument
    # against decoding either from its length.
    def native(name: str) -> UndecodedStruct:
        blob = _save(
            _struct_prop(
                "Value",
                body=bytes(24),
                struct_name=name,
                path="/Script/CoreUObject",
                guid=None,
                flags=0x08,
            )
        )
        return parse(blob).properties["Value"]

    vector, rotator = native("Vector"), native("Rotator")
    assert vector.data == rotator.data
    assert vector != rotator
    assert (vector.struct_name, rotator.struct_name) == ("Vector", "Rotator")


# --------------------------------------------------------------------------
# ByteProperty: an enum written as its qualified enumerator name
# --------------------------------------------------------------------------


def test_a_byte_property_decodes_to_its_qualified_enumerator_name():
    # Not a raw byte. The engine writes an FString here, and the enum's own
    # name is the type's one parameter.
    blob = _save(_byte_prop("Opened", "E_TestState::NewEnumerator1"))
    save = parse(blob)
    assert save.properties["Opened"] == "E_TestState::NewEnumerator1"
    assert save.property_types["Opened"] == (
        "ByteProperty<E_TestState</Game/Test/E_TestState>>"
    )


def test_the_enumerator_prefix_is_kept_rather_than_stripped():
    # Stripping "E_TestState::" would drop a measured string for cosmetics, and
    # would make two enums that both spell NewEnumerator1 indistinguishable.
    value = parse(_save(_byte_prop("Locked", "E_TestState::NewEnumerator2"))).properties[
        "Locked"
    ]
    assert value.startswith("E_TestState::")


def test_a_byte_property_without_an_enum_parameter_raises():
    # A parameterless ByteProperty is a raw byte in Unreal, and that form has
    # never been observed here. Decoding this one as an FString would invent a
    # string out of whatever followed.
    blob = _save(_byte_prop("Raw", "x", with_enum_param=False))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "enum" in str(excinfo.value)


# --------------------------------------------------------------------------
# maps and arrays, generalised over their measured element types
# --------------------------------------------------------------------------


def test_a_map_of_strings_to_structs_decodes():
    # DoorData, MonsterData, BotData and TreasureBoxMap are all this shape.
    # Map elements are BARE: no tag, no size, just the value encoding, and a
    # struct element is a bare property list closed by "None".
    body = _map_body(
        _fstring("door_1") + _struct_body(_int_prop("Hp", 10)),
        _fstring("door_2") + _struct_body(_int_prop("Hp", 0)),
    )
    blob = _save(_map_prop("DoorData", _type("StrProperty"), _struct_type(), body))
    doors = parse(blob).properties["DoorData"]
    assert doors == {"door_1": {"Hp": 10}, "door_2": {"Hp": 0}}
    # Measured zero, not absent. The second door really is at zero.
    assert doors["door_2"]["Hp"] == 0


def test_a_map_of_ints_to_doubles_decodes():
    body = _map_body(
        struct.pack("<i", 3) + struct.pack("<d", 34.0),
        struct.pack("<i", 101) + struct.pack("<d", 0.0),
    )
    blob = _save(
        _map_prop("LevelDetail", _type("IntProperty"), _type("DoubleProperty"), body)
    )
    assert parse(blob).properties["LevelDetail"] == {3: 34.0, 101: 0.0}


def test_a_map_of_ints_to_strings_decodes():
    body = _map_body(struct.pack("<i", 1) + _fstring("first"))
    blob = _save(
        _map_prop("NumIdToUUID", _type("IntProperty"), _type("StrProperty"), body)
    )
    assert parse(blob).properties["NumIdToUUID"] == {1: "first"}


def test_a_map_of_strings_to_ints_decodes():
    body = _map_body(_fstring("spawner") + struct.pack("<i", 7))
    blob = _save(_map_prop("Counts", _type("StrProperty"), _type("IntProperty"), body))
    assert parse(blob).properties["Counts"] == {"spawner": 7}


def test_an_empty_map_is_measured_empty_not_absent():
    blob = _save(_map_prop("Empty", _type("StrProperty"), _type("IntProperty"), _map_body()))
    save = parse(blob)
    assert save.properties["Empty"] == {}
    assert "Empty" in save.properties


def test_a_duplicate_map_key_raises_rather_than_dropping_a_pair():
    # A dict would silently keep the last pair and lose the first, which is a
    # measurement disappearing without anyone being told. Same reasoning as the
    # repeated-property-name check.
    body = _map_body(
        _fstring("same") + struct.pack("<i", 1),
        _fstring("same") + struct.pack("<i", 2),
    )
    blob = _save(_map_prop("Dupes", _type("StrProperty"), _type("IntProperty"), body))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "same" in str(excinfo.value)


def test_a_map_pair_count_the_value_cannot_hold_raises():
    # Asserted on the message, not just the exception type. Without the
    # up-front check the loop still dies - on running out of bytes, several
    # thousand iterations later - so a bare pytest.raises passes either way and
    # pins nothing. Measured: deleting the check left that version green.
    blob = _save(
        _map_prop(
            "Lying",
            _type("StrProperty"),
            _type("IntProperty"),
            _map_body(_fstring("one") + struct.pack("<i", 1), count=4096),
        )
    )
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "4096" in str(excinfo.value)


def test_a_map_that_announces_keys_to_remove_raises():
    body = _map_body(_fstring("k") + struct.pack("<i", 1), removes=1)
    blob = _save(_map_prop("Odd", _type("StrProperty"), _type("IntProperty"), body))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_an_array_of_structs_decodes():
    # ArrayProperty<StructProperty<F_CurrencyInfo<...>, guid>> is the one
    # parameterisation observed. There is no per-element header at all: the
    # UE4-era inner struct header is gone, because the UE 5.4 type name already
    # carries the struct identity.
    blob = _save(
        _array_prop(
            "Currency",
            _struct_type("F_CurrencyInfo", "/Game/Test/F_CurrencyInfo"),
            _struct_body(_int_prop("CfgId", 101), _int_prop("Count", 23)),
            _struct_body(_int_prop("CfgId", 102), _int_prop("Count", 0)),
        )
    )
    value = parse(blob).properties["Currency"]
    assert value == ({"CfgId": 101, "Count": 23}, {"CfgId": 102, "Count": 0})
    assert isinstance(value, tuple)


def test_an_empty_array_is_measured_empty_not_absent():
    blob = _save(_array_prop("Currency", _struct_type()))
    save = parse(blob)
    assert save.properties["Currency"] == ()
    assert "Currency" in save.properties


def test_an_array_element_count_the_value_cannot_hold_raises():
    # Same reasoning as the map version above: the count has to appear in the
    # message, or the test cannot tell the up-front rejection from the loop
    # eventually running out of bytes.
    body = struct.pack("<i", 4096)
    blob = _save(_prop_typed("Lying", _type("ArrayProperty", _type("IntProperty")), body))
    with pytest.raises(GvasParseError) as excinfo:
        parse(blob)
    assert "4096" in str(excinfo.value)


# --------------------------------------------------------------------------
# what stays refused: positions and element types nobody has measured
# --------------------------------------------------------------------------


def test_an_element_type_never_measured_bare_raises():
    # A tagged BoolProperty carries its value in flag 0x10 with a zero-byte
    # payload. A bool inside a map has no tag and therefore no flags, so its
    # encoding would have to be something else, and nothing has been observed.
    #
    # The pair below is deliberately a key and NOTHING else. An earlier version
    # gave the bool a spare byte, and deleting the gate left that byte over, so
    # the leftover-bytes check raised and the test passed while guarding
    # nothing - measured, by removing the gate and watching it stay green. With
    # a zero-byte payload the map decodes cleanly to {"k": False} once the gate
    # is gone, so this now fails when the thing it protects is broken.
    body = _map_body(_fstring("k"))
    blob = _save(_map_prop("Odd", _type("StrProperty"), _type("BoolProperty"), body))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    message = str(excinfo.value)
    assert "BoolProperty" in message
    assert "outside a property tag" in message


def test_a_map_of_doubles_to_structs_decodes():
    # DropItemMap really is keyed by a double: the keys observed were 5.0, 6.0,
    # 30.0 and friends, integer item ids carried as doubles because the save
    # class is a TypeScript module and a TypeScript number is a double.
    body = _map_body(
        struct.pack("<d", 35.0) + _struct_body(_int_prop("Slot", 6)),
        struct.pack("<d", 5.0) + _struct_body(_int_prop("Slot", 0)),
    )
    blob = _save(_map_prop("DropItemMap", _type("DoubleProperty"), _struct_type(), body))
    drops = parse(blob).properties["DropItemMap"]
    assert drops == {35.0: {"Slot": 6}, 5.0: {"Slot": 0}}
    # Python hashes 35.0 and 35 alike, which is worth a caller knowing.
    assert drops[35] == {"Slot": 6}


def test_a_map_key_type_never_measured_as_a_key_raises():
    # A struct is measured BARE - it is what every DoorData value is - and has
    # still never been measured as a KEY. That is the case this gate exists
    # for: without it the decode would get as far as building the dict and then
    # die on an unhashable key, from somewhere with nothing useful to say.
    body = _map_body(_struct_body(_int_prop("K", 1)) + struct.pack("<i", 1))
    blob = _save(_map_prop("Odd", _struct_type(), _type("IntProperty"), body))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "StructProperty" in str(excinfo.value)


def test_a_struct_with_no_type_parameters_raises():
    # Every StructProperty measured names its struct. One that names nothing
    # is a shape nobody has seen, and without the check the reader would reach
    # for params[0] and raise IndexError - a crash rather than a parse error,
    # and one a non-strict caller could not record.
    blob = _save(_prop_typed("Odd", _type("StructProperty"), _fstring("None")))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "type parameters" in str(excinfo.value)


def test_a_struct_with_more_type_parameters_than_measured_raises():
    # Name plus path plus GUID is two parameters; three is a shape that has
    # never been written. Without the check the extras would be ignored, which
    # is a reader deciding on its own that it understood something new.
    type_bytes = _type(
        "StructProperty",
        _type("F_TestData", _type("/Game/Test/F_TestData")),
        _type(_STRUCT_GUID),
        _type("SomethingElse"),
    )
    blob = _save(_prop_typed("Odd", type_bytes, _fstring("None")))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "type parameters" in str(excinfo.value)


def test_a_struct_naming_more_than_one_package_path_raises():
    type_bytes = _type(
        "StructProperty",
        _type("F_TestData", _type("/Game/Test/A"), _type("/Game/Test/B")),
    )
    blob = _save(_prop_typed("Odd", type_bytes, _fstring("None")))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "package path" in str(excinfo.value)


def test_a_leaf_type_carrying_type_parameters_raises():
    # ByteProperty is the only leaf measured with a parameter, and its
    # parameter is the enum whose enumerator it writes. An IntProperty that
    # grew one is not the IntProperty that was measured, and decoding it as
    # though the parameter were decoration would report a number for a shape
    # nobody has seen.
    blob = _save(_prop_typed("Odd", _type("IntProperty", "Weird"), struct.pack("<i", 5)))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "type parameters" in str(excinfo.value)


def test_a_map_with_the_wrong_number_of_type_parameters_raises():
    blob = _save(_prop_typed("Odd", _type("MapProperty", _type("StrProperty")), b""))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_an_array_with_the_wrong_number_of_type_parameters_raises():
    blob = _save(_prop_typed("Odd", _type("ArrayProperty"), struct.pack("<i", 0)))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


def test_a_struct_nested_deeper_than_the_cap_raises():
    # A corrupt length can spell an arbitrarily deep type, and unbounded
    # recursion on a hostile file is a crash rather than a parse error.
    # Measured depth in the real save is 5.
    inner = _struct_prop("Leaf", _int_prop("X", 1))
    for _ in range(MAX_VALUE_DEPTH + 2):
        inner = _struct_prop("Nest", inner)
    with pytest.raises(GvasParseError) as excinfo:
        parse(_save(inner))
    assert "deep" in str(excinfo.value) or "depth" in str(excinfo.value)


def test_measured_bare_types_is_exactly_what_was_measured():
    # The types observed as a container element rather than under a property
    # tag. Pinned for the same reason KNOWN_PROPERTY_TYPES is.
    assert sorted(MEASURED_BARE_TYPES) == [
        "DoubleProperty",
        "IntProperty",
        "StrProperty",
        "StructProperty",
    ]


def test_non_strict_records_a_struct_whose_nested_property_is_unmeasured():
    # A struct is decoded or it is not. An unmeasured property anywhere inside
    # it makes the whole top-level property unknown rather than handing back a
    # dict that is quietly missing a field.
    blob = _save(
        _int_prop("Before", 7),
        _struct_prop(
            "PlayerData",
            _int_prop("Level", 4),
            _prop("Mystery", "FloatProperty", struct.pack("<f", 1.5)),
        ),
        _int_prop("After", 9),
    )
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)

    save = parse(blob, strict=False)
    assert save.properties == {"Before": 7, "After": 9}
    assert "PlayerData" not in save.properties
    assert [u.name for u in save.unknown_properties] == ["PlayerData"]
    assert "FloatProperty" in save.unknown_properties[0].reason


def test_a_native_serialised_non_struct_still_raises():
    # Every flag-0x08 property in the capture is a StructProperty, so the
    # native branch is measured for structs and for nothing else. An
    # IntProperty written natively is a layout nobody here has seen.
    blob = _save(_prop("Odd", "IntProperty", struct.pack("<i", 5), flags=0x08))
    with pytest.raises(UnknownPropertyTypeError):
        parse(blob)


# --------------------------------------------------------------------------
# PII backstop - the repo-wide guards cannot see through base64
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixtures_carry_no_identifiers(name: str):
    # ALL_LABELS, not FILE_SCAN_LABELS. The repo-wide guard drops IPV4 because
    # a source tree is full of version strings; a save file is not, so this
    # scan is deliberately stricter than the one it stands in for.
    text = _fixture_bytes(name).decode("latin-1")
    findings = [
        f"{label} at offset {offset}"
        for label, _matched, offset in iter_sensitive(text, labels=ALL_LABELS)
    ]
    assert not findings, (
        f"{name} carries {len(findings)} potential identifier(s): "
        + "; ".join(findings)
        + ". tests/test_no_pii.py cannot see through base64, so nothing else "
        "will catch this, and deleting the file later will not remove it from "
        "git history."
    )


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_filenames_carry_no_identifiers(name: str):
    # The game names one of these files CampData_<19-digit userId>.sav.
    # Content redaction alone would have published that id in the listing.
    findings = list(iter_sensitive(name, labels=ALL_LABELS))
    assert not findings, f"{name} leaks {[f[0] for f in findings]} in its own filename"


def test_no_fixture_is_named_the_way_the_game_names_it():
    # The rename is the guard. If a fixture ever comes back named the way the
    # game names it, the userId came back with it.
    for name in FIXTURES:
        assert not name.startswith("CampData")


def test_the_fixture_scanner_would_actually_catch_a_leak():
    # A guard that cannot fail is not a guard. Prove the detectors fire on a
    # save-shaped blob carrying a synthetic identifier before trusting the
    # clean results above. Assembled at runtime so this file never contains
    # the shape it hunts for.
    leak = "7656119" + "0000000042"
    blob = _save(_prop("Leak", "StrProperty", _fstring(leak)))
    labels = {label for label, _, _ in iter_sensitive(blob.decode("latin-1"), ALL_LABELS)}
    assert "STEAMID64" in labels


def test_base64_hides_a_leak_from_the_repo_wide_guard():
    # Stated rather than assumed, because it is the reason the decoding scan
    # above exists at all. The same leak that fires on the raw bytes is
    # invisible once encoded, so test_no_pii.py passing means nothing here.
    leak = "7656119" + "0000000042"
    blob = _save(_prop("Leak", "StrProperty", _fstring(leak)))
    encoded = base64.b64encode(blob).decode("ascii")
    assert not list(iter_sensitive(encoded, ALL_LABELS))


# --------------------------------------------------------------------------
# standalone_slot.gvas.b64 - the authored transient-save fixture
#
# The other six fixtures are sanitised copies of small, dull files. This one is
# built by ``tests/fixtures/build_standalone_slot_fixture.py`` out of the
# largest captured generation of the game's in-run level save, and it is the
# only fixture in the repository that carries a StructProperty, an
# ArrayProperty, a ByteProperty, a natively serialised struct, or a map keyed
# by anything but a string. It is also the only one built from a source that
# carried identifiers - 38 of them, 67 GUIDs, and a third party's display name.
#
# So the tests below are in two halves, and the second half is the one that
# matters. Half one asserts the fixture is clean and carries the shapes it
# exists to pin. Half two POISONS it, one sanitisation class at a time, and
# requires the same scan to fire - because a clean result and a broken scan
# look identical, and every "the fixture is clean" assertion above is worth
# nothing until the scan has been watched saying otherwise.
# --------------------------------------------------------------------------

STANDALONE_SLOT = "standalone_slot.gvas.b64"

#: A Blueprint property-name decoration: ``Hp_10_<opaque token>``.
_DECORATION = re.compile(r"_\d+_[0-9A-Za-z]{1,64}$")

#: Bytes one 76-column base64 line decodes to. ``lanternlight.redact``'s
#: encoded pass decodes each base64 RUN it finds, and a wrapped fixture is a
#: stack of separate runs, so this is the width of the window its structural
#: rules actually see. See ``test_a_name_field_head_does_not_fit_one_base64_line``.
_B64_LINE_BYTES = 76 // 4 * 3


def _base(name: str) -> str:
    """Return a property name with its Blueprint decoration stripped."""
    return _DECORATION.sub("", name)


def _field(struct: dict, base: str):
    """The one value in a decoded struct dict whose undecorated name is ``base``."""
    matches = [key for key in struct if _base(key) == base]
    assert len(matches) == 1, f"{base!r} names {len(matches)} properties, expected 1"
    return struct[matches[0]]


def _poison(function):
    """Serialise the fixture with ``function`` applied, and prove it applied.

    A mutation that silently matches nothing looks exactly like a passing
    control, which is a trap this repository has already been caught by. The
    wrapper counts the properties the mutation actually replaced and fails if
    that count is zero, so a rename that drifts out of date is a red test
    rather than a quiet one.
    """
    touched: list[str] = []

    def watched(path, prop):
        replacement = function(path, prop)
        if replacement is not prop:
            touched.append(prop.name)
        return replacement

    raw = serialise(transform(_fixture(STANDALONE_SLOT), watched))
    assert touched, "the mutation matched no property, so this control proves nothing"
    return raw


def _native_structs(save: GvasSave) -> dict[str, bytes]:
    """Every natively serialised struct in a save, by struct name."""
    found: dict[str, bytes] = {}

    def walk(properties):
        for prop in properties:
            value = prop.value
            if isinstance(value, UndecodedStruct):
                found[value.struct_name] = value.data
            elif isinstance(value, StructValue):
                walk(value.properties)
            elif isinstance(value, MapValue):
                for _key, item in value.pairs:
                    if isinstance(item, StructValue):
                        walk(item.properties)
            elif isinstance(value, ArrayValue):
                for item in value.elements:
                    if isinstance(item, StructValue):
                        walk(item.properties)

    walk(save.property_list)
    return found


def test_the_standalone_slot_fixture_pins_the_shapes_nothing_else_carries():
    # The reason this fixture is worth 27 KB of base64. Every shape listed here
    # is absent from all six of the others and from all seven live saves, so
    # without it they are covered only by synthetic bytes this repository wrote
    # - which prove the reader is self-consistent, not that it matches the game.
    save = _fixture(STANDALONE_SLOT)
    types = " ".join(save.property_types.values())
    assert "StructProperty" in types
    assert "ArrayProperty" in types
    assert "MapProperty" in types

    assert set(_native_structs(save)) == set(MEASURED_NATIVE_STRUCTS)

    # Map keys: a string, a double and an int, all three in one file.
    assert all(isinstance(key, str) for key in save.properties["DoorData"])
    assert all(isinstance(key, float) for key in save.properties["DropItemMap"])
    assert all(isinstance(key, int) for key in save.properties["LevelDetail"])

    # ByteProperty is written as a qualified enumerator FString here, not as a
    # raw byte, and the fixture keeps two DIFFERENT door states so a reader
    # that pinned one literal cannot pass.
    doors = list(save.properties["DoorData"].values())
    assert len(doors) == 2
    opened = {_field(door, "Opened") for door in doors}
    locked = {_field(door, "Locked") for door in doors}
    assert len(opened) == 2, "both doors share an E_DoorState enumerator"
    assert len(locked) == 2, "both doors share an E_LockState enumerator"
    assert all(state.startswith("E_DoorState::") for state in opened)
    assert all(state.startswith("E_LockState::") for state in locked)


def test_the_standalone_slot_fixture_keeps_both_drop_item_owner_spellings():
    # ``ownerRoleId`` is the identifier inside the ItemCell JSON, and the game
    # spells "nobody owns this" as a JSON null rather than as an empty string.
    # A fixture carrying only one of the two would let a consumer assume the
    # field is always a string, and would also stop pinning the authored case.
    cells = [
        json.loads(_field(item, "ItemCell"))
        for item in _fixture(STANDALONE_SLOT).properties["DropItemMap"].values()
    ]
    owners = [cell["ownerRoleId"] for cell in cells]
    assert len(owners) == 2
    assert None in owners
    authored = [owner for owner in owners if owner is not None]
    assert len(authored) == 1
    assert authored[0].isdigit()
    # Shorter than LONG_ID's floor, which is the whole point - a same-length
    # substitution would fire exactly as the real id did.
    assert len(authored[0]) < 15


def test_the_standalone_slot_fixture_keeps_its_two_id_maps_consistent():
    # NumIdToUUID and UUIDToNumId are the same mapping inverted. Pruning them
    # independently, or authoring one side's values and not the other's, would
    # pin a shape the game never writes.
    generator = _fixture(STANDALONE_SLOT).properties["IdGeneratorData"]
    forward = _field(generator, "NumIdToUUID")
    backward = _field(generator, "UUIDToNumId")
    assert len(forward) == 3
    assert {value: key for key, value in forward.items()} == backward


def test_the_standalone_slot_fixture_authors_every_name_bearing_value():
    # LeaderRankScoreData records who was killed last, and in a run with real
    # players that is somebody else's display name. redact's structural rule
    # goes quiet only when the authored marker sits beside the property, and
    # test_an_unauthored_name_field_in_this_fixture_would_be_caught is what
    # proves the rule is live rather than merely silent.
    save = _fixture(STANDALONE_SLOT)
    history = _field(save.properties["LeaderRankScoreData"], "KillPlayerHistoryDatas")
    assert len(history) == 1
    for name in NAME_BEARING_PROPERTIES:
        assert _field(history[0], name) == AUTHORED_NAME_MARKER


def test_the_standalone_slot_fixture_carries_no_run_of_fifteen_digits():
    # LONG_ID is length-only, so this is the property the whole sanitisation
    # pass exists to establish, stated directly rather than inferred from the
    # scanner being quiet.
    text = _fixture_bytes(STANDALONE_SLOT).decode("latin-1")
    assert not re.search(r"(?<!\d)\d{15,}(?!\d)", text)


def test_the_standalone_slot_fixture_carries_no_thirty_two_character_hex_run():
    # Same statement for the other class. An authored decoration that was still
    # 32 hex characters would have changed nothing at all, because PRODUCTUSERID
    # keys on shape and cannot tell an authored hex run from a real one.
    text = _fixture_bytes(STANDALONE_SLOT).decode("latin-1")
    assert not re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])", text)
    # The decorations are still there - the shape the engine writes is kept,
    # only the opaque value is authored.
    assert re.search(r"_\d+_[0-9A-Za-z]{20,}\x00", text)


def test_the_committed_base64_of_this_fixture_hides_nothing():
    # Acceptance in its own right, and the pass that test_no_pii.py runs over
    # the tree. Scoped here so a failure names this fixture rather than
    # arriving as one line in a whole-tree report.
    encoded = (FIXTURE_DIR / STANDALONE_SLOT).read_text(encoding="ascii")
    assert not list(iter_encoded_sensitive(encoded, labels=ALL_LABELS))
    assert not list(iter_sensitive(encoded, labels=ALL_LABELS))


# --------------------------------------------------------------------------
# the controls - one per sanitisation class, each poisoning the real fixture
# --------------------------------------------------------------------------


def test_a_long_identifier_in_this_fixture_would_be_caught():
    planted = "1" * 19

    def poison(_path, prop):
        if _base(prop.name) == "BattleId":
            return dataclasses.replace(prop, value=planted)
        return prop

    raw = _poison(poison)
    labels = {label for label, _, _ in iter_sensitive(raw.decode("latin-1"), ALL_LABELS)}
    assert "LONG_ID" in labels, (
        "a 19-digit id put back into the fixture was not detected, so the clean "
        "scan of the real fixture says nothing"
    )


def test_a_hex_decoration_in_this_fixture_would_be_caught():
    # Assembled in halves so this file does not itself carry a 32-hex run - the
    # scanner cannot tell an invented ProductUserId from a real one.
    planted = "0123456789abcdef" + "fedcba9876543210"

    def poison(_path, prop):
        if _base(prop.name) == "MonsterID":
            return dataclasses.replace(prop, name=f"MonsterID_19_{planted}")
        return prop

    raw = _poison(poison)
    labels = {label for label, _, _ in iter_sensitive(raw.decode("latin-1"), ALL_LABELS)}
    assert "PRODUCTUSERID" in labels, (
        "a 32-hex decoration put back into the fixture was not detected, so "
        "authoring the GUIDs cannot be shown to have achieved anything"
    )


def test_an_unauthored_name_field_in_this_fixture_would_be_caught():
    # The one that had to be proven rather than assumed. Until this fixture was
    # built, that record was refused ONLY because the Blueprint GUID beside it
    # tripped PRODUCTUSERID - a false positive that happened to be load-bearing.
    # Authoring the GUIDs removes it, so the structural rule is now the only
    # thing standing between a third party's display name and a public history.
    committed = _fixture_bytes(STANDALONE_SLOT).decode("latin-1")
    assert not [
        label for label, _, _ in iter_sensitive(committed, ALL_LABELS)
        if label == "NAME_FIELD"
    ]

    def poison(_path, prop):
        if _base(prop.name) == NAME_BEARING_PROPERTIES[0]:
            return dataclasses.replace(prop, value="a display name")
        return prop

    raw = _poison(poison)
    labels = {label for label, _, _ in iter_sensitive(raw.decode("latin-1"), ALL_LABELS)}
    assert "NAME_FIELD" in labels, (
        "the structural name-field rule did not fire on an unauthored value, so "
        "the marker in the committed fixture is not what is keeping it quiet"
    )


def test_a_name_field_head_does_not_fit_one_base64_line():
    # Why the authored decorations keep the source's 32-character width.
    #
    # The encoded scan decodes each base64 RUN it finds, and a fixture wrapped
    # at 76 columns is a stack of runs, each decoding to a 57-byte WINDOW. The
    # structural rule needs the property name, its NUL and the StrProperty
    # token - len(name) + 17 bytes - and goes quiet only if the authored marker
    # follows within 64. No 57-byte window can hold both, so any name-bearing
    # property whose head FITS in one window is reported, correctly by the
    # rule's logic and uselessly for this file.
    #
    # An 11-character decoration was built first and did exactly that. The
    # window is taken from the property name itself, which is the worst case.
    text = _fixture_bytes(STANDALONE_SLOT).decode("latin-1")
    for name in NAME_BEARING_PROPERTIES:
        window = text[text.index(name) :][:_B64_LINE_BYTES]
        assert not list(iter_sensitive(window, labels=["NAME_FIELD"])), (
            f"{name} fits inside one base64 line's worth of bytes"
        )

    def shorten(_path, prop):
        base = _base(prop.name)
        if base in NAME_BEARING_PROPERTIES and base != prop.name:
            return dataclasses.replace(prop, name=f"{base}_19_AUTHORED000")
        return prop

    short = _poison(shorten).decode("latin-1")
    fired = sum(
        len(list(iter_sensitive(short[short.index(name) :][:_B64_LINE_BYTES], ["NAME_FIELD"])))
        for name in NAME_BEARING_PROPERTIES
    )
    assert fired == len(NAME_BEARING_PROPERTIES), (
        "a short decoration was expected to bring the rule's head inside one "
        f"base64 line for all {len(NAME_BEARING_PROPERTIES)} properties, got {fired}"
    )


def test_a_zeroed_native_struct_still_round_trips():
    # The fixture authors the three native payloads that were entirely zero,
    # because 24 zero bytes encode to 32 'A' characters and 'A' is a hex digit,
    # so the committed base64 would trip PRODUCTUSERID as TEXT. That removes a
    # case from the fixture, so the format claim it would have carried is
    # pinned here instead: an all-zero payload is handed back and written back
    # verbatim, exactly like any other.
    payload = bytes(24)
    raw = _save(
        _struct_prop(
            "Translation",
            struct_name="Vector",
            path="/Script/CoreUObject",
            guid=None,
            body=payload,
            flags=0x08,
        )
    )
    save = parse(raw)
    assert save.properties["Translation"].data == payload
    assert serialise(save) == raw


# --------------------------------------------------------------------------
# the serialiser: byte-for-byte round-trip identity
#
# The oracle is identity, not plausibility. ``serialise(parse(raw)) == raw`` is
# the only check that catches a field the reader quietly dropped, because a
# dropped field is invisible in every assertion about the decoded values and
# shows up immediately as a short or shifted byte string. It found the FText
# flags word, which nothing else here was looking at.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURES), ids=lambda n: n)
def test_every_fixture_round_trips_byte_for_byte(name: str):
    raw = _fixture_bytes(name)
    assert serialise(parse(raw)) == raw


def test_every_live_save_round_trips_byte_for_byte():
    # The fixtures are authored, so they pin only the shapes this repository
    # chose to keep. The live directory is the engine's own output and is the
    # one place a shape nobody anticipated can turn up - which is how Deck.sav
    # and Scav.sav were found. Enumerated, never listed.
    #
    # Skips rather than passes when the game is not installed, so the suite
    # still runs on a machine without it, and the skip is narrow enough that
    # the machine which HAS the game cannot be quietened by it.
    directory = paths.save_games_dir()
    if not directory.is_dir():
        pytest.skip(f"no save directory at {directory}; nothing to round-trip")
    files = [p for p in sorted(directory.iterdir()) if p.is_file()]
    if not files:
        pytest.skip(f"{directory} holds no save files; nothing to round-trip")

    # Only the file NAME is ever reported, and only for one that failed. A live
    # save's bytes carry the operator's SteamID64 and role ids, so a pasted
    # assertion diff would publish them.
    mismatched = []
    for path in files:
        raw = path.read_bytes()
        if serialise(parse(raw)) != raw:
            mismatched.append(path.name)
    assert not mismatched, (
        "these live saves did not round-trip byte for byte: " + ", ".join(mismatched)
    )


def test_the_round_trip_oracle_actually_discriminates():
    # An equality oracle is worthless if the two sides are the same object by
    # construction. One byte changed in the source and the comparison has to
    # fail, or every round-trip assertion above is decoration.
    raw = _fixture_bytes("notice.gvas.b64")
    assert serialise(parse(raw)) == raw
    mutated = bytearray(raw)
    mutated[-1] ^= 0xFF
    assert serialise(parse(raw)) != bytes(mutated)


def test_serialise_does_not_copy_the_trailing_bytes_it_was_handed():
    # The cheap way to pass every round-trip test is to emit GvasSave.trailing
    # verbatim, which would look perfect here and make an edited key profile
    # silently unwritable. Corrupt that field and the output must not move: the
    # object section is rebuilt from the decoded objects, not copied.
    raw = _fixture_bytes("enhanced_input_user_settings.gvas.b64")
    save = parse(raw)
    assert len(save.trailing) == 627, "this is the fixture with an object section"
    poisoned = dataclasses.replace(save, trailing=b"\xff" * len(save.trailing))
    assert serialise(poisoned) == raw


def test_an_edited_key_profile_changes_the_bytes():
    # The other half of the same proof. If the object section were copied from
    # trailing, editing a decoded mapping would be ignored without a word.
    raw = _fixture_bytes("enhanced_input_user_settings.gvas.b64")
    save = parse(raw)
    profile = save.key_profiles[0]
    renamed = dataclasses.replace(
        profile,
        mappings=(
            dataclasses.replace(profile.mappings[0], name="KB_Renamed"),
            *profile.mappings[1:],
        ),
    )
    edited = serialise(dataclasses.replace(save, key_profiles=(renamed,)))
    assert edited != raw
    reparsed = parse(edited)
    assert reparsed.key_profiles[0].mappings[0].name == "KB_Renamed"
    assert reparsed.undecoded_trailing == b""


# --------------------------------------------------------------------------
# what the tag now carries, because a writer needs what a reader did not
# --------------------------------------------------------------------------


def test_the_property_list_and_the_plain_view_describe_the_same_properties():
    save = _fixture("login_options.gvas.b64")
    assert [p.name for p in save.property_list] == list(save.properties)
    assert [p.type_name.render() for p in save.property_list] == list(
        save.property_types.values()
    )


def test_a_type_name_keeps_its_structure_not_only_its_rendering():
    # render() is one-way. A map's key and value types are separate FStrings
    # with their own parameter counts, and nothing can split them back out of
    # "MapProperty<IntProperty, IntProperty>" without guessing at how a name
    # containing a comma would have been spelled.
    save = _fixture("camp_data.gvas.b64")
    (prop,) = save.property_list
    assert prop.type_name.name == "MapProperty"
    assert [p.name for p in prop.type_name.params] == ["IntProperty", "IntProperty"]
    assert prop.type_name.render() == "MapProperty<IntProperty, IntProperty>"


def test_a_text_property_keeps_the_ftext_flags_word_the_plain_view_drops():
    # Measured 2 in every FText across all 276 files, and retained rather than
    # pinned because nothing observed says it is a constant. The plain view is
    # the string alone, so this is a field only the node can carry.
    save = _fixture("login_options.gvas.b64")
    (text,) = [p for p in save.property_list if p.name == "SelectedServer"]
    assert text.type_name.name == "TextProperty"
    assert isinstance(text.value, TextValue)
    assert text.value.flags == 2
    assert text.value.history == 0xFF
    assert text.value.text == "official_NA"
    assert save.properties["SelectedServer"] == "official_NA"


def test_the_ftext_flags_word_is_written_back_rather_than_assumed():
    # Non-vacuity for the field above. Change it and the bytes have to move; a
    # writer that pinned a constant here would still equal the original.
    raw = _fixture_bytes("login_options.gvas.b64")
    edited = transform(
        parse(raw),
        lambda path, prop: (
            dataclasses.replace(prop, value=dataclasses.replace(prop.value, flags=7))
            if isinstance(prop.value, TextValue)
            else prop
        ),
    )
    written = serialise(edited)
    assert written != raw
    (text,) = [p for p in parse(written).property_list if p.name == "SelectedServer"]
    assert text.value.flags == 7


def test_no_committed_fixture_carries_an_array_index_or_a_property_guid():
    # Written down as the measurement it is: no property in any fixture sets
    # tag flag 0x01 or 0x02, and nor does any live save or any of the 263
    # captured generations. The fields exist on Property anyway, and the two
    # tests below are why that is not decoration.
    for name in FIXTURES:
        for prop in parse(_fixture_bytes(name)).property_list:
            assert prop.array_index is None, f"{name}:{prop.name}"
            assert prop.property_guid is None, f"{name}:{prop.name}"


def test_an_array_index_survives_a_round_trip():
    raw = _save(
        _fstring("Indexed")
        + _type("IntProperty")
        + struct.pack("<i", 4)
        + bytes([0x01])
        + struct.pack("<i", 7)
        + struct.pack("<i", 99)
    )
    save = parse(raw)
    (prop,) = save.property_list
    assert prop.array_index == 7
    assert save.properties == {"Indexed": 99}
    assert serialise(save) == raw


def test_a_property_guid_survives_a_round_trip():
    guid = bytes(range(16))
    raw = _save(
        _fstring("Identified")
        + _type("IntProperty")
        + struct.pack("<i", 4)
        + bytes([0x02])
        + guid
        + struct.pack("<i", 5)
    )
    save = parse(raw)
    (prop,) = save.property_list
    assert prop.property_guid == guid
    assert serialise(save) == raw


def test_the_flags_byte_is_derived_from_the_value_not_stored_beside_it():
    # A stored flags byte plus a stored bool is two copies of one fact, and an
    # edit that changed one and not the other would write a file saying the
    # opposite of what the object says. Property keeps no flags byte at all.
    assert not hasattr(Property("x", TypeName("IntProperty"), 1), "flags")
    raw = _save(_bool_prop("On", True))
    flipped = transform(
        parse(raw), lambda path, prop: dataclasses.replace(prop, value=False)
    )
    assert flipped.properties == {"On": False}
    assert serialise(flipped) != raw
    assert parse(serialise(flipped)).properties == {"On": False}


# --------------------------------------------------------------------------
# editing: the reason the writer exists
#
# ROADMAP 2b needs a sanitised StandaloneSlot fixture, and sanitising it means
# SHORTENING identifier strings - a same-length substitution does not help,
# because the LONG_ID detector fires on any run of 15 or more digits - and
# DROPPING map entries to cut the size. Both move byte lengths, so every
# enclosing Size and every container count has to move with them. These are
# the proof that happens by construction rather than by hand.
# --------------------------------------------------------------------------


def _nested_save() -> bytes:
    """A save shaped like the parts of StandaloneSlot that have to be edited.

    A long identifier inside a struct inside a struct, so shortening it moves
    the Size of every enclosing property; and a four-pair map of structs, so
    dropping entries moves a count as well.
    """
    inner = _struct_prop(
        "Inner",
        _prop("ownerRoleId", "StrProperty", _fstring("3" * 19)),
        _int_prop("Level", 4),
    )
    pairs = b"".join(
        _fstring(f"slot{index}") + _struct_body(_int_prop("Count", index))
        for index in range(4)
    )
    return _save(
        _struct_prop(
            "Outer",
            inner,
            _map_prop(
                "ItemCells",
                _type("StrProperty"),
                _struct_type(),
                _map_body(pairs, count=4),
            ),
        ),
        _prop("BattleId", "StrProperty", _fstring("7" * 19)),
    )


def _shorten_ids(path, prop):
    """Replace every all-digit StrProperty value with a shorter placeholder."""
    if prop.type_name.name == "StrProperty" and prop.value.isdigit():
        return dataclasses.replace(prop, value="<LONG_ID>")
    return prop


def _skip_type_name(blob: bytes, offset: int) -> int:
    """Step over a serialised recursive type name and return the next offset."""
    length = struct.unpack("<i", blob[offset : offset + 4])[0]
    offset += 4 + length
    count = struct.unpack("<i", blob[offset : offset + 4])[0]
    offset += 4
    for _ in range(count):
        offset = _skip_type_name(blob, offset)
    return offset


def _tag_size(blob: bytes, name: str) -> int:
    """Read the Size field out of the tag of the property called ``name``.

    Located by walking the bytes rather than by a hard-coded offset, so it
    cannot go stale when the blob it is pointed at changes shape.
    """
    marker = _fstring(name)
    assert blob.count(marker) == 1, f"{name!r} is not a unique anchor in this blob"
    offset = _skip_type_name(blob, blob.index(marker) + len(marker))
    return struct.unpack("<i", blob[offset : offset + 4])[0]


def test_the_nested_save_this_section_edits_is_what_it_claims_to_be():
    # Everything below asserts on an edit to this blob, so if the blob were not
    # the shape described, the whole section would be testing nothing.
    save = parse(_nested_save())
    assert save.properties["Outer"]["Inner"]["ownerRoleId"] == "3" * 19
    assert save.properties["Outer"]["Inner"]["Level"] == 4
    assert len(save.properties["Outer"]["ItemCells"]) == 4
    assert save.properties["BattleId"] == "7" * 19
    assert serialise(save) == _nested_save()


def test_shortening_a_string_inside_a_nested_struct_re_parses_whole():
    raw = _nested_save()
    edited = serialise(transform(parse(raw), _shorten_ids))
    assert len(edited) < len(raw), "a shorter identifier has to make a shorter file"

    reparsed = parse(edited)
    assert reparsed.undecoded_trailing == b""
    assert reparsed.is_complete
    assert reparsed.unknown_properties == ()
    assert reparsed.properties["Outer"]["Inner"]["ownerRoleId"] == "<LONG_ID>"
    assert reparsed.properties["BattleId"] == "<LONG_ID>"
    # Untouched neighbours stay untouched. A Size patched wrong would have
    # shifted these rather than raising, which is the failure this exists for.
    assert reparsed.properties["Outer"]["Inner"]["Level"] == 4
    assert len(reparsed.properties["Outer"]["ItemCells"]) == 4
    assert reparsed.properties["Outer"]["ItemCells"]["slot3"] == {"Count": 3}


def test_the_edited_structure_itself_round_trips():
    # The acceptance criterion applied to the EDITED save rather than only to a
    # captured one: whatever serialise wrote, parse reads back to bytes that
    # serialise writes identically.
    edited = serialise(transform(parse(_nested_save()), _shorten_ids))
    assert serialise(parse(edited)) == edited


def test_every_enclosing_size_moved_with_the_shortened_string():
    # The specific failure this module exists to prevent. "Outer" is two levels
    # above the edited string and "Inner" one, so both tags' Size fields have to
    # shrink by exactly what the string lost, with nobody computing that by hand.
    raw = _nested_save()
    edited = serialise(transform(parse(raw), _shorten_ids))
    lost = len("3" * 19) - len("<LONG_ID>")
    assert lost == 10
    assert _tag_size(edited, "Outer") == _tag_size(raw, "Outer") - lost
    assert _tag_size(edited, "Inner") == _tag_size(raw, "Inner") - lost


def test_dropping_map_entries_re_parses_whole():
    def drop_all_but_two(path, prop):
        if isinstance(prop.value, MapValue):
            return dataclasses.replace(prop, value=MapValue(prop.value.pairs[:2]))
        return prop

    raw = _nested_save()
    edited = serialise(transform(parse(raw), drop_all_but_two))
    assert len(edited) < len(raw)

    reparsed = parse(edited)
    assert reparsed.undecoded_trailing == b""
    assert reparsed.is_complete
    assert reparsed.unknown_properties == ()
    assert list(reparsed.properties["Outer"]["ItemCells"]) == ["slot0", "slot1"]
    assert reparsed.properties["Outer"]["ItemCells"]["slot1"] == {"Count": 1}
    assert serialise(reparsed) == edited


def test_dropping_map_entries_from_a_real_fixture_re_parses_whole():
    # The synthetic blob above could share a mistake with the writer. deck's
    # DeckDefaultOpenPage is the engine's own two-pair map, so it cannot.
    raw = _fixture_bytes("deck.gvas.b64")
    assert parse(raw).properties["DeckDefaultOpenPage"] == {2: 3, 4: 0}
    edited = serialise(
        transform(
            parse(raw),
            lambda path, prop: dataclasses.replace(
                prop, value=MapValue(prop.value.pairs[:1])
            ),
        )
    )
    reparsed = parse(edited)
    assert reparsed.properties == {"DeckDefaultOpenPage": {2: 3}}
    assert reparsed.undecoded_trailing == b""
    assert reparsed.is_complete
    assert len(edited) == len(raw) - 8, "one int-to-int pair is eight bytes"
    assert serialise(reparsed) == edited


def test_transform_can_drop_a_whole_property():
    save = parse(_save(_int_prop("Keep", 1), _int_prop("Drop", 2)))
    edited = transform(save, lambda path, prop: None if prop.name == "Drop" else prop)
    assert edited.properties == {"Keep": 1}
    assert edited.property_types == {"Keep": "IntProperty"}
    assert parse(serialise(edited)).properties == {"Keep": 1}


def test_transform_visits_every_depth_and_names_the_path():
    seen = []

    def record(path, prop):
        seen.append(path)
        return prop

    transform(parse(_nested_save()), record)
    assert ("Outer",) in seen
    assert ("Outer", "Inner") in seen
    assert ("Outer", "Inner", "ownerRoleId") in seen
    assert ("Outer", "ItemCells", "[2].value", "Count") in seen
    assert ("BattleId",) in seen


def test_transform_recurses_into_what_it_returns_not_into_what_it_was_given():
    # Otherwise a wholesale subtree swap would leave the new subtree unvisited,
    # and a rule that fires on a parent and on its children would half-apply.
    def swap_then_shorten(path, prop):
        if prop.name == "Outer":
            return dataclasses.replace(
                prop,
                value=StructValue(
                    (Property("Injected", TypeName("StrProperty"), "9" * 19),)
                ),
            )
        return _shorten_ids(path, prop)

    edited = transform(parse(_nested_save()), swap_then_shorten)
    assert edited.properties["Outer"] == {"Injected": "<LONG_ID>"}
    assert parse(serialise(edited)).properties["Outer"] == {"Injected": "<LONG_ID>"}


def test_rebuild_recomputes_the_plain_view_so_it_cannot_go_stale():
    # dataclasses.replace on property_list alone would leave properties and
    # property_types describing a save that no longer exists, and every caller
    # in this repository reads those rather than the node tree.
    save = parse(_save(_int_prop("Count", 1)))
    edited = rebuild(
        save, property_list=(Property("Count", TypeName("StrProperty"), "one"),)
    )
    assert edited.properties == {"Count": "one"}
    assert edited.property_types == {"Count": "StrProperty"}
    assert parse(serialise(edited)).properties == {"Count": "one"}


def test_rebuild_recomputes_the_trailing_bytes_too():
    raw = _fixture_bytes("enhanced_input_user_settings.gvas.b64")
    save = parse(raw)
    profile = save.key_profiles[0]
    edited = rebuild(
        save,
        key_profiles=(dataclasses.replace(profile, object_name="Profile_Renamed"),),
    )
    assert edited.trailing != save.trailing
    assert serialise(edited).endswith(edited.trailing)


def test_a_transformed_key_profile_keeps_its_two_views_agreeing():
    raw = _fixture_bytes("enhanced_input_user_settings.gvas.b64")
    edited = transform(
        parse(raw),
        lambda path, prop: (
            dataclasses.replace(prop, value="Shorter")
            if prop.name == "ProfileIdentifierString"
            else prop
        ),
    )
    profile = edited.key_profiles[0]
    assert profile.properties["ProfileIdentifierString"] == "Shorter"
    assert profile.property_types["ProfileIdentifierString"] == "StrProperty"
    written = serialise(edited)
    assert len(written) < len(raw)
    reparsed = parse(written)
    assert reparsed.undecoded_trailing == b""
    assert reparsed.key_profiles[0].properties == profile.properties
    assert reparsed.key_profiles[0].is_complete


# --------------------------------------------------------------------------
# the writer raises rather than emitting a near-miss
#
# Every one of these is a byte the writer cannot account for. A file that
# parses but is subtly wrong is worse than no file, because it looks like
# evidence.
# --------------------------------------------------------------------------


def test_a_save_holding_a_refused_property_cannot_be_written():
    # A non-strict parse omits the property and does NOT keep its bytes, so a
    # file written from that object would be missing it and still look whole.
    blob = _save(_int_prop("Before", 7), _prop("Mystery", "FloatProperty", b"\0" * 4))
    save = parse(blob, strict=False)
    assert save.unknown_properties
    with pytest.raises(GvasSerialiseError, match="nothing to write back"):
        serialise(save)


def test_a_key_profile_holding_a_refused_property_cannot_be_written():
    blob = _save(
        trailing=_trailing(_profile(_prop("Mystery", "FloatProperty", b"\0" * 4)))
    )
    save = parse(blob, strict=False)
    assert save.key_profiles[0].unknown_properties
    with pytest.raises(GvasSerialiseError, match="nothing to write back"):
        serialise(save)


def test_a_non_ascii_string_raises_rather_than_inventing_utf16():
    # The engine's negative-length UTF-16 branch is real and published, and not
    # one of the 671318 non-empty FStrings measured across all 276 files takes
    # it. Writing one would be this module inventing an encoding. The literal
    # is escaped so this file stays 7-bit ASCII.
    save = rebuild(
        parse(_save(_prop("Name", "StrProperty", _fstring("plain")))),
        property_list=(Property("Name", TypeName("StrProperty"), "caf\u00e9"),),
    )
    with pytest.raises(GvasSerialiseError, match="not ASCII"):
        serialise(save)


def test_a_property_named_none_raises():
    # It would serialise fine and read back as the terminator, so the file
    # would parse, be short, and say nothing about what it lost.
    save = rebuild(
        parse(_save(_int_prop("Count", 1))),
        property_list=(Property("None", TypeName("IntProperty"), 1),),
    )
    with pytest.raises(GvasSerialiseError, match="read back as the list terminator"):
        serialise(save)


def test_a_repeated_property_name_raises_on_the_way_out_too():
    save = parse(_save(_int_prop("Count", 1)))
    doubled = dataclasses.replace(
        save, property_list=(save.property_list[0], save.property_list[0])
    )
    with pytest.raises(GvasSerialiseError, match="appears twice"):
        serialise(doubled)


def test_a_value_that_does_not_match_its_type_name_raises():
    save = rebuild(
        parse(_save(_int_prop("Count", 1))),
        property_list=(Property("Count", TypeName("IntProperty"), "not an int"),),
    )
    with pytest.raises(GvasSerialiseError, match="needs an int"):
        serialise(save)


def test_a_text_property_given_a_bare_string_raises():
    # The plain view is the string alone and cannot say which history wrote it,
    # so writing one would mean picking a history at random.
    save = parse(_fixture_bytes("login_options.gvas.b64"))
    broken = dataclasses.replace(
        save,
        property_list=tuple(
            dataclasses.replace(p, value="official_NA")
            if p.type_name.name == "TextProperty"
            else p
            for p in save.property_list
        ),
    )
    with pytest.raises(GvasSerialiseError, match="needs a TextValue"):
        serialise(broken)


def test_an_unmeasured_property_type_raises_on_the_way_out():
    save = rebuild(
        parse(_save(_int_prop("Count", 1))),
        property_list=(Property("Count", TypeName("FloatProperty"), 1.0),),
    )
    with pytest.raises(GvasSerialiseError, match="has not been measured"):
        serialise(save)


def test_an_element_type_never_measured_bare_raises_on_the_way_out():
    save = rebuild(
        parse(_save(_int_prop("Count", 1))),
        property_list=(
            Property(
                "Flags",
                TypeName("ArrayProperty", (TypeName("BoolProperty"),)),
                ArrayValue((True,)),
            ),
        ),
    )
    with pytest.raises(GvasSerialiseError, match="outside a property tag"):
        serialise(save)


def test_a_mis_sized_property_guid_raises():
    raw = _save(
        _fstring("Identified")
        + _type("IntProperty")
        + struct.pack("<i", 4)
        + bytes([0x02])
        + bytes(16)
        + struct.pack("<i", 5)
    )
    save = parse(raw)
    broken = dataclasses.replace(
        save,
        property_list=(
            dataclasses.replace(save.property_list[0], property_guid=b"\0" * 8),
        ),
    )
    with pytest.raises(GvasSerialiseError, match="the tag field is 16"):
        serialise(broken)


def test_a_mis_sized_epilogue_raises():
    save = parse(_save(_int_prop("Count", 1)))
    with pytest.raises(GvasSerialiseError, match="every measured property list"):
        serialise(dataclasses.replace(save, epilogue=b"\0\0"))


def test_a_mis_sized_key_mapping_tail_raises():
    save = parse(_fixture_bytes("enhanced_input_user_settings.gvas.b64"))
    profile = save.key_profiles[0]
    broken = dataclasses.replace(
        profile,
        mappings=(
            dataclasses.replace(profile.mappings[0], undecoded=b"\0"),
            *profile.mappings[1:],
        ),
    )
    with pytest.raises(GvasSerialiseError, match="undecoded bytes"):
        serialise(dataclasses.replace(save, key_profiles=(broken,)))


def test_key_profiles_without_a_section_header_raise():
    # The four bytes that open the object section are unidentified, so they
    # cannot be reconstructed from anything else. A save carrying objects but
    # not those bytes is unwritable, and saying so beats writing a guess.
    save = parse(_fixture_bytes("enhanced_input_user_settings.gvas.b64"))
    with pytest.raises(GvasSerialiseError, match="not derivable"):
        serialise(dataclasses.replace(save, object_section_header=b""))


def test_a_custom_version_guid_of_the_wrong_width_raises():
    save = parse(_fixture_bytes("notice.gvas.b64"))
    versions = save.header.custom_versions
    assert len(versions) == 88, "this fixture carries the engine's table"
    broken = dataclasses.replace(
        save.header,
        custom_versions=(
            dataclasses.replace(versions[0], guid=b"\0" * 4),
            *versions[1:],
        ),
    )
    with pytest.raises(GvasSerialiseError, match="the field is 16"):
        serialise(dataclasses.replace(save, header=broken))


def test_a_bool_property_carrying_something_other_than_a_bool_raises():
    # A tagged bool's entire value is the 0x10 flag bit, so there is no other
    # place to put a non-bool and no honest way to coerce one.
    save = rebuild(
        parse(_save(_bool_prop("On", True))),
        property_list=(Property("On", TypeName("BoolProperty"), 1),),
    )
    with pytest.raises(GvasSerialiseError, match="whole value is the 0x10 flag"):
        serialise(save)


# --------------------------------------------------------------------------
# round-trip coverage for shapes NO committed file carries
#
# Measured 2026-08-10: not one fixture and not one live save holds an
# ArrayProperty, a StructProperty, a ByteProperty or a natively serialised
# struct. Every one of those lives only in the transient StandaloneSlot save,
# which is machine-specific and is not committed and must not be. So the
# committed corpus cannot cover them and these synthetic blobs do - built by
# the same builders the reader's own tests use, which the six real fixtures
# keep honest by refusing to parse if the builders drift into a private
# dialect.
# --------------------------------------------------------------------------


def test_an_array_of_structs_round_trips():
    raw = _save(
        _array_prop(
            "Currencies",
            _struct_type(),
            _struct_body(_int_prop("Id", 1), _int_prop("Amount", 250)),
            _struct_body(_int_prop("Id", 2), _int_prop("Amount", 0)),
        )
    )
    save = parse(raw)
    assert save.properties["Currencies"] == (
        {"Id": 1, "Amount": 250},
        {"Id": 2, "Amount": 0},
    )
    assert serialise(save) == raw


def test_an_empty_array_round_trips_as_empty_rather_than_absent():
    raw = _save(_array_prop("Currencies", _struct_type()))
    save = parse(raw)
    assert save.properties["Currencies"] == ()
    assert serialise(save) == raw


def test_an_empty_map_round_trips_as_empty_rather_than_absent():
    raw = _save(
        _map_prop("Cells", _type("StrProperty"), _type("IntProperty"), _map_body())
    )
    save = parse(raw)
    assert save.properties["Cells"] == {}
    assert serialise(save) == raw


def test_a_map_of_doubles_to_structs_round_trips():
    # DropItemMap's real shape: integer item ids carried as doubles, because
    # the save class is TypeScript and a TypeScript number is a double. It is
    # also the parameterisation that turned up only after 200 generations.
    pairs = b"".join(
        struct.pack("<d", key) + _struct_body(_int_prop("Weight", index))
        for index, key in enumerate((5.0, 30.0, 35.0))
    )
    raw = _save(
        _map_prop(
            "DropItemMap",
            _type("DoubleProperty"),
            _struct_type(),
            _map_body(pairs, count=3),
        )
    )
    save = parse(raw)
    assert save.properties["DropItemMap"][35.0] == {"Weight": 2}
    assert serialise(save) == raw


def test_a_native_struct_round_trips_verbatim():
    # Vector, Rotator, Quat and Vector2D carry tag flag 0x08 and are handed
    # back as opaque bytes. The writer puts exactly those bytes back and
    # derives the flag from the value's type, so nothing about them is guessed
    # on the way out either.
    payload = bytes(range(24))
    raw = _save(
        _struct_prop(
            "Location",
            struct_name="Vector",
            path="/Script/CoreUObject",
            guid=None,
            body=payload,
            flags=0x08,
        )
    )
    save = parse(raw)
    assert isinstance(save.properties["Location"], UndecodedStruct)
    assert save.properties["Location"].data == payload
    assert serialise(save) == raw


def test_a_byte_property_round_trips_as_its_enumerator_name():
    raw = _save(_byte_prop("DoorState", "E_DoorState::NewEnumerator1"))
    save = parse(raw)
    assert save.properties["DoorState"] == "E_DoorState::NewEnumerator1"
    assert serialise(save) == raw


def test_a_source_history_text_round_trips_with_its_namespace_and_key():
    raw = _save(_text_prop("Label", "NS", "KEY_1", "Default Profile"))
    save = parse(raw)
    assert isinstance(save.properties["Label"], SourceText)
    assert save.properties["Label"].namespace == "NS"
    assert serialise(save) == raw


def test_a_struct_five_levels_deep_round_trips():
    # The measured maximum nesting in StandaloneSlot is 5 property-list levels.
    body = _struct_body(_prop("Leaf", "StrProperty", _fstring("bottom")))
    for level in range(4):
        body = _struct_body(_prop_typed(f"Level{level}", _struct_type(), body))
    raw = _save(_prop_typed("Root", _struct_type(), body))
    save = parse(raw)
    deepest = save.properties["Root"]
    for level in reversed(range(4)):
        deepest = deepest[f"Level{level}"]
    assert deepest == {"Leaf": "bottom"}
    assert serialise(save) == raw
