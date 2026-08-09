"""Tests for lanternlight.gvas against the game's real save files.

Fixtures - what they are, and what was done to them
--------------------------------------------------

``tests/fixtures/gvas/*.gvas.b64`` are the five files the game writes into
``%LOCALAPPDATA%/MistfallHunter/Saved/SaveGames/``, measured on 2026-08-09,
base64-encoded, with two value splices and one rename. Everything else - the
1760-byte custom-version table, every property name, every setting - is the
engine's own bytes.

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

The three redactions
--------------------

1. ``CampData_<19-digit userId>.sav`` -> ``camp_data.gvas.b64``. **The userId is
   in the FILENAME**, not in the contents, so content-only redaction would have
   published it in the directory listing. Its contents needed no change.
2. ``LoginOptions.sav``, the account-name property: the ``TextProperty``
   payload string was replaced with the placeholder below and the tag's 4-byte
   Size patched from 23 to 28. **No detector in lanternlight.redact fires on
   that value in the raw file** - GVAS separates a key from its value by a type
   name and a tag, so the keyed shape the redactor looks for never occurs. It
   was found by parsing, not by scanning, which is precisely why a binary
   fixture cannot be cleared by running the text guards over it.
3. ``Notice.sav`` ``readedGameBulletinId``: a 19-digit id, replaced with
   ``<LONG_ID>``, Size patched from 24 to 14. This one the ``LONG_ID`` detector
   did fire on. It is very likely a bulletin id rather than operator data, and
   it is redacted anyway - over-redaction costs a duller fixture, and
   under-redaction costs a permanent public record.

Deliberately NOT redacted: ``SelectedServer`` is ``official_NA``, a server
region the game offers to everyone. It names a continent-sized region and no
person, and a fixture carrying one real ``TextProperty`` value is worth more
than one with a placeholder in every string.

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
import struct
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight.gvas import (  # noqa: E402
    EPILOGUE_SIZE,
    KNOWN_PROPERTY_TYPES,
    MAGIC,
    MEASURED_TEXT_HISTORIES,
    MEASURED_TRAILING_OBJECT_CLASS,
    GvasParseError,
    GvasSave,
    SourceText,
    UnknownPropertyTypeError,
    load,
    parse,
)
from lanternlight.redact import ALL_LABELS, iter_sensitive  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "gvas"

#: Every fixture, with the Blueprint class path the game recorded in it.
FIXTURES: dict[str, str] = {
    "camp_data.gvas.b64": (
        "/Game/Blueprints/TypeScript/module/Camp/CampSaveData.CampSaveData_C"
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


def _prop(
    name: str,
    type_name: str,
    value: bytes = b"",
    params: tuple[str, ...] = (),
    flags: int = 0,
) -> bytes:
    """One tagged property: name, type name, type params, size, flags, value."""
    parts = [_fstring(name), _fstring(type_name), struct.pack("<i", len(params))]
    for param in params:
        parts.append(_fstring(param))
        parts.append(struct.pack("<i", 0))
    parts.append(struct.pack("<i", len(value)))
    parts.append(bytes([flags]))
    parts.append(value)
    return b"".join(parts)


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
def test_all_five_files_parse_into_plain_dicts(name: str):
    save = _fixture(name)
    assert isinstance(save, GvasSave)
    assert save.header.save_game_class_name == FIXTURES[name]
    assert save.save_game_class_name == FIXTURES[name]
    assert type(save.properties) is dict
    assert save.properties, "every one of the five files carries at least one property"
    assert save.is_complete
    assert save.unknown_properties == ()


def test_there_are_exactly_five_fixtures():
    found = sorted(p.name for p in FIXTURE_DIR.iterdir() if p.is_file())
    assert found == sorted(FIXTURES)


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
    props = _fixture("user_settings_v1.gvas.b64").properties
    assert props["bWarehouseAutomation"] is True
    assert props["bHasFirstSetup"] is True
    assert props["bEnableCrossPlay"] is True
    assert props["DLSSMode"] == 6
    assert props["AnimationQuality"] == 2
    assert props["AutoDetectedBenchmarkCPUResult"] == -1.0
    assert props["FirstTimeAutoSetQualityLevel"] == -2.0
    assert props["RayTracingQuality"] == 1.0
    assert len(props) == 14


def test_a_false_bool_is_a_measurement_not_an_absence():
    # bMotionBlurEnabled is the only False bool in the capture. It has to come
    # back present-and-False; a reader that dropped it would be reporting
    # "unmeasured" for something the file plainly states.
    props = _fixture("user_settings_v1.gvas.b64").properties
    assert "bMotionBlurEnabled" in props
    assert props["bMotionBlurEnabled"] is False


def test_camp_data_map_property():
    save = _fixture("camp_data.gvas.b64")
    assert save.properties == {"LevelModeMap": {1: 1}}
    assert save.property_types["LevelModeMap"] == "MapProperty<IntProperty, IntProperty>"


def test_notice_and_enhanced_input_values():
    assert _fixture("notice.gvas.b64").properties == {
        "readedGameBulletinId": "<LONG_ID>"
    }
    assert _fixture("enhanced_input_user_settings.gvas.b64").properties == {
        "CurrentProfileIdentifierString": "InputUserSettings.Profiles.Default"
    }


def test_trailing_bytes_are_exposed_rather_than_dropped():
    # Four of the five files carry exactly four zero bytes after the None
    # terminator. EnhancedInputUserSettings carries 627, because that object
    # serialises its key profiles after its tagged properties and ends with a
    # literal ObjectEnd. This reader decodes neither, and the point of this
    # test is that it does not pretend they are absent.
    quiet = (
        "camp_data.gvas.b64",
        "login_options.gvas.b64",
        "notice.gvas.b64",
        "user_settings_v1.gvas.b64",
    )
    for name in quiet:
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
    # MapProperty is known, but only with int keys and int values. A different
    # parameterisation is a different encoding, and decoding it as the measured
    # one would produce confidently wrong numbers.
    body = struct.pack("<ii", 0, 0)
    blob = _save(_prop("Odd", "MapProperty", body, params=("StrProperty", "IntProperty")))
    with pytest.raises(UnknownPropertyTypeError) as excinfo:
        parse(blob)
    assert "StrProperty" in str(excinfo.value)


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
    assert sorted(KNOWN_PROPERTY_TYPES) == [
        "BoolProperty",
        "DoubleProperty",
        "IntProperty",
        "MapProperty<IntProperty, IntProperty>",
        "StrProperty",
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
    save = _fixture("enhanced_input_user_settings.gvas.b64")
    assert len(save.key_profiles) == 1
    profile = save.key_profiles[0]
    assert profile.class_path == MEASURED_TRAILING_OBJECT_CLASS
    assert profile.object_name == "EnhancedPlayerMappableKeyProfile_2147482261"
    assert profile.identifier == "InputUserSettings.Profiles.Default"


def test_key_profile_mapping_rows():
    # Corroborated out of band: the game log writes
    # "decode key mapping KB_Blackarrow_Major_Action RightMouseButton" and
    # "... KB_Blackarrow_Minor_Action LeftMouseButton", naming the same pairs
    # the first slot of each row carries here.
    profile = _fixture("enhanced_input_user_settings.gvas.b64").key_profiles[0]
    assert [m.name for m in profile.mappings] == [
        "KB_Blackarrow_Major_Action",
        "KB_Blackarrow_Minor_Action",
        "KB_EmptyHands_Minor_Action",
    ]
    assert [m.key_names[0] for m in profile.mappings] == [
        "RightMouseButton",
        "LeftMouseButton",
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


@pytest.mark.parametrize(
    "name",
    [
        "camp_data.gvas.b64",
        "login_options.gvas.b64",
        "notice.gvas.b64",
        "user_settings_v1.gvas.b64",
    ],
)
def test_the_other_four_files_wrote_no_object_section(name: str):
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
