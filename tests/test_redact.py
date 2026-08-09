"""Tests for lanternlight.redact.

Every identifier here is invented. Nothing was pasted from a real log.

Note the odd string construction below: fake identifiers are assembled from
fragments at runtime (``"887766554433" + "22110"``) rather than written as one
literal, and key/value pairs are joined through ``_EQ`` instead of containing
a literal ``=``. That is not stylistic. ``tests/test_no_pii.py`` scans every
source file in the repository with this very module's detectors, so a test
file containing a literal 17-digit number or a literal ``key=value`` secret
shape would fail that scan - correctly, since the scanner cannot tell an
invented identifier from a real one. Building the fixtures at runtime keeps
the scanner honest instead of carving an exemption for the one file most
likely to leak.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight.redact import (  # noqa: E402
    ALL_LABELS,
    FILE_SCAN_LABELS,
    RedactionError,
    assert_clean,
    iter_sensitive,
    redact,
)

# --------------------------------------------------------------------------
# invented identifiers, assembled at runtime - see the module docstring
# --------------------------------------------------------------------------

_EQ = "="

#: 17 digits beginning 7656119, the SteamID64 shape. Invented.
FAKE_STEAMID64 = "76561190" + "000000042"

#: 32 hexadecimal characters, the EOS ProductUserId shape. Invented.
FAKE_PRODUCT_USER_ID = "0f1e2d3c4b5a6978" + "8796a5b4c3d2e1f0"

#: An 18-digit GSDK-style open id. Invented.
FAKE_OPEN_ID = "887766554433" + "221100"

#: A 16-digit GSDK-style user id. Invented.
FAKE_USER_ID = "112233445566" + "7788"

#: A 15-digit bare id under no key this module knows. Invented.
FAKE_UNKEYED_ID = "1234567890" + "12345"

FAKE_PERSONA = "lanternlight_test_persona"
FAKE_ACCOUNT = "lanternlight_test_account"
FAKE_TOKEN = "abcdefabcdefabcdefabcdef"
FAKE_IPV4 = "203.0.113.7"


def _kv(key: str, value: str) -> str:
    """Join a key and value without ever writing the pair as a literal."""
    return key + _EQ + value


SYNTHETIC_LOG = "\n".join(
    [
        "[2026.08.09-13.20.11:001][  0]TS.System: [TSGameInstance] boot",
        "[2026.08.09-13.20.12:100][ 12]TS.Login: Display: steam session "
        + _kv("steamId", FAKE_STEAMID64)
        + " "
        + _kv("AccountName", FAKE_ACCOUNT),
        "[2026.08.09-13.20.12:180][ 12]TS.Login: gsdk handshake "
        + _kv("openID", FAKE_OPEN_ID)
        + " "
        + _kv("userId", FAKE_USER_ID),
        "[2026.08.09-13.20.12:240][ 13]TS.Login: eos "
        + _kv("ProductUserId", FAKE_PRODUCT_USER_ID),
        "[2026.08.09-13.20.12:250][ 13]TS.Login: eos bare " + FAKE_PRODUCT_USER_ID,
        "[2026.08.09-13.20.12:300][ 14]TS.Login: "
        + _kv("onelineDisplayName", FAKE_PERSONA),
        "[2026.08.09-13.20.12:330][ 14]TS.Login: " + _kv("accessToken", FAKE_TOKEN),
        "[2026.08.09-13.20.12:400][ 15]TS.Net: resolved endpoint " + FAKE_IPV4,
        "[2026.08.09-13.20.12:450][ 15]TS.Net: unkeyed trace " + FAKE_UNKEYED_ID,
        "[2026.08.09-13.21.28:626][656]TS.Avatar: [AvatarComponent] "
        "server_refreshKnightFeature: BP_Preview_C_2147475781 class-10 holding-30402",
    ]
)


# --------------------------------------------------------------------------
# the whole snippet is scrubbed
# --------------------------------------------------------------------------


def test_synthetic_snippet_is_fully_scrubbed():
    cleaned = redact(SYNTHETIC_LOG)
    assert_clean(cleaned)


def test_no_invented_identifier_survives_verbatim():
    cleaned = redact(SYNTHETIC_LOG)
    for secret in (
        FAKE_STEAMID64,
        FAKE_PRODUCT_USER_ID,
        FAKE_OPEN_ID,
        FAKE_USER_ID,
        FAKE_UNKEYED_ID,
        FAKE_PERSONA,
        FAKE_ACCOUNT,
        FAKE_TOKEN,
        FAKE_IPV4,
    ):
        assert secret not in cleaned, secret


def test_every_expected_placeholder_appears():
    cleaned = redact(SYNTHETIC_LOG)
    for placeholder in (
        "<STEAMID64>",
        "<ACCOUNT_NAME>",
        "<OPENID>",
        "<USERID>",
        "<PRODUCTUSERID>",
        "<PERSONA>",
        "<TOKEN>",
        "<IPV4>",
        "<LONG_ID>",
    ):
        assert placeholder in cleaned, placeholder


def test_keys_survive_so_the_fixture_stays_readable():
    cleaned = redact(SYNTHETIC_LOG)
    # The point of a labelled placeholder is that structure is preserved.
    assert "AccountName" in cleaned
    assert "openID" in cleaned
    assert "accessToken" in cleaned


def test_non_sensitive_game_telemetry_is_untouched():
    line = (
        "[2026.08.09-13.21.28:626][656]TS.Avatar: [AvatarComponent] "
        "server_refreshKnightFeature: BP_Preview_C_2147475781 class-10 holding-30402"
    )
    assert redact(line) == line


def test_empty_input_is_returned_unchanged():
    assert redact("") == ""


# --------------------------------------------------------------------------
# individual rules
# --------------------------------------------------------------------------


def test_bare_steamid64_is_masked():
    assert redact("player " + FAKE_STEAMID64 + " joined") == "player <STEAMID64> joined"


def test_a_short_number_starting_with_the_steam_prefix_is_not_a_steamid():
    # 7656119 followed by fewer than 10 digits is not a SteamID64. It must not
    # be mislabelled - though the generic long-run rule may still catch it if
    # it is long enough, which is the intended over-redaction direction.
    labels = {label for label, _, _ in iter_sensitive("id 765611901234")}
    assert "STEAMID64" not in labels


def test_bare_32_hex_is_masked():
    text = "puid " + FAKE_PRODUCT_USER_ID
    assert redact(text) == "puid <PRODUCTUSERID>"


def test_31_and_33_hex_runs_are_not_product_user_ids():
    short = "a" * 31
    long_run = "a" * 33
    assert "PRODUCTUSERID" not in {label for label, _, _ in iter_sensitive(short)}
    assert "PRODUCTUSERID" not in {label for label, _, _ in iter_sensitive(long_run)}


def test_long_bare_digit_run_is_masked():
    assert redact("trace " + FAKE_UNKEYED_ID) == "trace <LONG_ID>"


def test_short_digit_runs_are_left_alone():
    # Actor instance ids and content ids are 10 digits or fewer and must
    # survive, or every fixture becomes useless.
    text = "BP_Preview_C_2147475781 class-10 holding-30402"
    assert redact(text) == text


def test_colon_separated_key_values_are_masked_too():
    text = "openID: " + FAKE_OPEN_ID
    assert redact(text) == "openID: <OPENID>"


def test_quoted_values_are_masked():
    quote = '"'
    text = "personaName" + _EQ + quote + FAKE_PERSONA + quote
    assert redact(text) == "personaName" + _EQ + "<PERSONA>"


def test_ue_timestamp_is_not_mistaken_for_an_ip_address():
    header = "[2026.08.09-13.21.28:440][656]TS.Dungeon: ok"
    assert redact(header) == header


# --------------------------------------------------------------------------
# assert_clean
# --------------------------------------------------------------------------


def test_assert_clean_raises_on_a_leak():
    with pytest.raises(RedactionError):
        assert_clean("player " + FAKE_STEAMID64 + " joined")


def test_assert_clean_names_the_offending_match():
    with pytest.raises(RedactionError) as excinfo:
        assert_clean("line one\nplayer " + FAKE_STEAMID64 + " joined")
    message = str(excinfo.value)
    assert "STEAMID64" in message
    assert FAKE_STEAMID64 in message
    assert "line 2" in message


def test_assert_clean_passes_on_already_redacted_text():
    assert_clean(redact(SYNTHETIC_LOG))


def test_assert_clean_accepts_a_label_subset():
    # IPV4 is excluded from the file scan, so a bare dotted quad must pass
    # under FILE_SCAN_LABELS and fail under the full set.
    text = "endpoint " + FAKE_IPV4
    assert_clean(text, labels=FILE_SCAN_LABELS)
    with pytest.raises(RedactionError):
        assert_clean(text, labels=ALL_LABELS)


# --------------------------------------------------------------------------
# stability and idempotency
# --------------------------------------------------------------------------


def test_placeholders_are_stable_across_runs():
    first = redact(SYNTHETIC_LOG)
    second = redact(SYNTHETIC_LOG)
    assert first == second


def test_redaction_is_idempotent():
    once = redact(SYNTHETIC_LOG)
    twice = redact(once)
    assert once == twice


def test_placeholder_is_a_fixed_literal_not_a_derived_value():
    # Two different SteamID64 values must collapse to the same placeholder, or
    # redacted fixtures stop diffing cleanly against the next capture.
    one = redact("id " + "76561190" + "000000042")
    two = redact("id " + "76561199" + "999999999")
    assert one == two == "id <STEAMID64>"


def test_iter_sensitive_reports_offsets_that_index_the_input():
    text = "prefix " + FAKE_STEAMID64
    hits = list(iter_sensitive(text))
    assert len(hits) >= 1
    label, matched, offset = hits[0]
    assert label == "STEAMID64"
    assert text[offset : offset + len(matched)] == matched
