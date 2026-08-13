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

import base64
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _tracked  # noqa: E402  (sits beside this file in tests/)
import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight import redact as redact_module  # noqa: E402
from lanternlight.redact import (  # noqa: E402
    ALL_LABELS,
    AUTHORED_NAME_MARKER,
    FILE_SCAN_LABELS,
    NAME_BEARING_PROPERTIES,
    PERSONA_PLACEHOLDER,
    RedactionError,
    assert_clean,
    discover_personas,
    iter_encoded_sensitive,
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


_DASH = "-"
_COLON = ":"
_QUOTE = '"'

#: A two-token display name, the shape the real Steam persona has. Invented.
FAKE_NAME = "Zephyr" + "wynd"
FAKE_SURNAME = "Kestrel" + "vane"
FAKE_FULL_NAME = FAKE_NAME + " " + FAKE_SURNAME

#: A 19-digit role id, the number the game glues onto an actor token. Invented.
FAKE_ROLE_ID = "1122334455" + "667788990"

#: The ``NAME_<role id>`` actor token shape. Invented.
FAKE_ACTOR_TOKEN = FAKE_NAME + "_" + FAKE_ROLE_ID


def _kv(key: str, value: str) -> str:
    """Join a key and value without ever writing the pair as a literal."""
    return key + _EQ + value


def _kd(key: str, value: str) -> str:
    """Join a key and value with the dash separator the game also emits."""
    return key + _DASH + value


def _kc(key: str, value: str, space: str = " ") -> str:
    """Join a key and value with a colon."""
    return key + _COLON + space + value


def _kj(key: str, value: str) -> str:
    """Join a JSON ``"key":"value"`` pair without writing it as a literal."""
    return _QUOTE + key + _QUOTE + _COLON + _QUOTE + value + _QUOTE


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


def test_a_key_word_at_the_end_of_a_sentence_does_not_reach_the_next_line():
    # A prose sentence ending in a word this module uses as a key, followed by
    # a blank line and a table, is not a key/value pair. It used to match one
    # and fail the repository scan on an innocent document.
    prose = "the name the operator plays under gives this " + "persona" + _COLON
    document = prose + "\n\n| Player | Tags |\n"
    assert list(iter_sensitive(document, labels=FILE_SCAN_LABELS)) == []
    assert redact(document) == document


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


# --------------------------------------------------------------------------
# the persona leak
#
# Every shape below was measured in the real 2026-08-09 log before it was
# written down here, with the operator's own display name substituted for an
# invented one. The counts in the comments are occurrences of the real name in
# that capture, so a shape that looks exotic is not hypothetical - it is the
# reason 684 of 686 occurrences used to survive redact().
# --------------------------------------------------------------------------


def _shape_periodic_buff() -> str:
    return "[TSGameplayEffectComponent]: PeriodicBuff, " + _kd("instigator", FAKE_NAME)


def _shape_periodic_debuff() -> str:
    return "[TSGameplayEffectComponent]: PeriodicDebuff, " + _kd("instigator", FAKE_NAME)


def _shape_ammunition_csv() -> str:
    return "AmmunitionComponent_C_2147406943," + FAKE_NAME + ",32758"


def _shape_open_treasure_box() -> str:
    return (
        "[DungeonLevelModel] PlayerOpenTreasureBox "
        + FAKE_NAME
        + " -> BP_TreasureBox_FTE_08_C_2147446982"
    )


def _shape_kill_monster() -> str:
    return "[DungeonLevelModel] PlayerKillMonster " + FAKE_NAME + " -> 99"


def _shape_steam_channel_json() -> str:
    return (
        "{"
        + _kj("channel", "Steam")
        + ","
        + _kj("uId", FAKE_STEAMID64)
        + ","
        + _kj("uName", FAKE_FULL_NAME)
        + "}"
    )


def _shape_role_json() -> str:
    return (
        "{"
        + _kj("userId", FAKE_OPEN_ID)
        + ","
        + _kj("roleId", FAKE_ROLE_ID)
        + ","
        + _kj("name", FAKE_NAME)
        + ","
        + _kj("gender", "2")
        + "}"
    )


def _shape_possessed_by() -> str:
    return "Adventurer::PossessedBy Controller " + FAKE_FULL_NAME


def _shape_radar_scan() -> str:
    return "OnRep_RadarScanResult uiProxy " + FAKE_NAME + " Result: 0 Monsters"


def _shape_play_state_tag() -> str:
    return (
        "OnRep_PlayStateTag "
        + _kv("PlayerName", FAKE_NAME)
        + " "
        + _kv("TagName", "Game.PlayState.Gaming")
        + " "
        + _kv("lastState", "undefined")
    )


def _shape_play_state_tag_two_token() -> str:
    return (
        "OnRep_PlayStateTag "
        + _kv("PlayerName", FAKE_FULL_NAME)
        + " "
        + _kv("TagName", "Game.PlayState.Gaming")
    )


def _shape_check_hud() -> str:
    return "n rep pawn checkHUD, ps " + _kc("Name", FAKE_NAME + " " + FAKE_NAME)


def _shape_login_request() -> str:
    return (
        "[Login] Request to login: "
        + _kv("dungeonVer", "123")
        + ", "
        + _kv("campVer", "114")
        + ", "
        + _kv("onlineUserId", FAKE_STEAMID64)
        + ", "
        + _kv("onelineDisplayName", FAKE_FULL_NAME)
    )


def _shape_role_id_json() -> str:
    return "{" + _kj("role_id", FAKE_NAME) + "}"


def _shape_init_new_player() -> str:
    return (
        "DungeonGameMode K2_InitNewPlayer no roleId, option: ?"
        + _kv("levelId", "1")
        + "&"
        + _kv("roomModeId", "9")
        + "&"
        + _kv("matchId", "0")
        + "?"
        + _kv("Name", FAKE_FULL_NAME)
    )


def _shape_post_login() -> str:
    return (
        "onPlayerPostLogin, "
        + _kc("PlayerName", FAKE_FULL_NAME)
        + ", "
        + _kc("NetStateTag", "Game.Net.Online")
        + ", "
        + _kc("OnlinePlayerCount", "0")
    )


def _shape_add_member() -> str:
    return (
        "[DungeonTeamState] addMember "
        + _kc("roleId", FAKE_ROLE_ID, space="")
        + ", "
        + _kc("name", FAKE_NAME, space="")
    )


def _shape_init_adventurer() -> str:
    return "[DungeonGameMode]: InitAdventurer, " + _kd("name", FAKE_NAME) + ", subChannel-steam"


def _shape_on_rep_display_name() -> str:
    return "[DungeonPlayerState]: OnRep_OnlineDisplayName, " + _kd("displayName", FAKE_FULL_NAME)


def _shape_adventurer_inited() -> str:
    return "[DungeonGameState] onAdventurerInited " + FAKE_NAME


def _shape_pickup_loot() -> str:
    return (
        "[DungeonInventoryComponent] RequestPickupLoot, "
        + _kc("actor", FAKE_ACTOR_TOKEN, space="")
        + ", "
        + _kc("itemId", "27", space="")
        + ", "
        + _kc("cfgId", "901201", space="")
    )


def _shape_reactive_channel() -> str:
    return "[DungeonPlayerState]: reactive, " + _kd("channel", FAKE_FULL_NAME)


def _shape_member_name() -> str:
    return "[TeamInfoView]: " + _kc("memberName", FAKE_NAME)


def _shape_possessive() -> str:
    return "TS.Dungeon: Player " + FAKE_NAME + "'s state destroyed"


def _shape_start_point() -> str:
    return "BeginPlay playerStartPoint " + FAKE_NAME + " : X=18107.0"


def _shape_response_init_inventory() -> str:
    return "ResponseInitInventory " + FAKE_NAME + " 204 inventory"


def _shape_glued_to_following_text() -> str:
    # Measured once: the game concatenates the actor label and the verb with no
    # separator, so the name is welded to the next word on both sides.
    return "[BP_PlacedEscapePortal_C_2147369647] Give Bell: BP_Adventurer_C_2147381775__" + (
        FAKE_NAME + "enter portal area"
    )


#: ``(name, line, carries_its_own_key)``. The third field records which
#: mechanism has to reach the name: ``True`` means the line names a key the
#: module recognises, ``False`` means the name sits in a bare slot with nothing
#: marking it. Both are required to survive redaction *in isolation* - the
#: keyless ones are the excerpt case, and they are the ones that used to leak.
PERSONA_SHAPES: tuple[tuple[str, str, bool], ...] = (
    ("periodic_buff", _shape_periodic_buff(), True),
    ("periodic_debuff", _shape_periodic_debuff(), True),
    ("ammunition_csv", _shape_ammunition_csv(), False),
    ("open_treasure_box", _shape_open_treasure_box(), False),
    ("kill_monster", _shape_kill_monster(), False),
    ("steam_channel_json", _shape_steam_channel_json(), True),
    ("role_json", _shape_role_json(), True),
    ("possessed_by", _shape_possessed_by(), False),
    ("radar_scan", _shape_radar_scan(), False),
    ("play_state_tag", _shape_play_state_tag(), True),
    ("play_state_tag_two_token", _shape_play_state_tag_two_token(), True),
    ("check_hud", _shape_check_hud(), True),
    ("login_request", _shape_login_request(), True),
    ("role_id_json", _shape_role_id_json(), True),
    ("init_new_player", _shape_init_new_player(), True),
    ("post_login", _shape_post_login(), True),
    ("add_member", _shape_add_member(), True),
    ("init_adventurer", _shape_init_adventurer(), True),
    ("on_rep_display_name", _shape_on_rep_display_name(), True),
    ("adventurer_inited", _shape_adventurer_inited(), False),
    ("pickup_loot", _shape_pickup_loot(), True),
    ("reactive_channel", _shape_reactive_channel(), True),
    ("member_name", _shape_member_name(), True),
    ("possessive", _shape_possessive(), False),
    ("start_point", _shape_start_point(), False),
    ("response_init_inventory", _shape_response_init_inventory(), False),
    ("actor_token", "spawned " + FAKE_ACTOR_TOKEN + " ok", True),
    ("glued", _shape_glued_to_following_text(), False),
)

KEYED_SHAPES = tuple((name, line) for name, line, keyed in PERSONA_SHAPES if keyed)
POSITIONAL_SHAPES = tuple(
    (name, line) for name, line, keyed in PERSONA_SHAPES if not keyed
)
ALL_SHAPES = tuple((name, line) for name, line, _keyed in PERSONA_SHAPES)

#: Every measured shape in one document, which is how the scrubber meets them:
#: the keyed lines are what let the positional ones be found at all.
PERSONA_LOG = "\n".join(
    f"[2026.08.09-14.{index:02d}.00:000][{index:3d}]TS.Dungeon: {line}"
    for index, (_, line, _keyed) in enumerate(PERSONA_SHAPES)
)


@pytest.mark.parametrize(
    ("index", "name"), [(i, shape[0]) for i, shape in enumerate(PERSONA_SHAPES)]
)
def test_no_persona_token_survives_any_measured_shape(index, name):
    cleaned = redact(PERSONA_LOG).splitlines()[index]
    assert FAKE_NAME not in cleaned, name
    assert FAKE_SURNAME not in cleaned, name
    assert FAKE_FULL_NAME not in cleaned, name


@pytest.mark.parametrize(("name", "line"), KEYED_SHAPES)
def test_a_shape_that_carries_a_key_is_clean_on_its_own(name, line):
    cleaned = redact(line)
    assert FAKE_NAME not in cleaned, name
    assert FAKE_SURNAME not in cleaned, name
    assert FAKE_FULL_NAME not in cleaned, name


@pytest.mark.parametrize(("name", "line"), POSITIONAL_SHAPES)
def test_a_keyless_shape_is_clean_on_its_own_too(name, line):
    # THE property that was missing. Each of these lines carries no key at all,
    # so discovery has nothing to read - they are clean alone only because the
    # slot itself is a rule. A log excerpt is exactly this: a handful of
    # dungeon lines with no login line anywhere near them.
    cleaned = redact(line)
    assert FAKE_NAME not in cleaned, name
    assert FAKE_SURNAME not in cleaned, name
    assert FAKE_FULL_NAME not in cleaned, name


@pytest.mark.parametrize(("name", "line"), ALL_SHAPES)
def test_assert_clean_rejects_every_measured_shape_on_its_own(name, line):
    with pytest.raises(RedactionError):
        assert_clean(line)


def test_an_excerpt_of_keyless_lines_is_clean_without_a_login_line():
    # The ROADMAP scenario, end to end: cut the interesting dungeon lines out
    # of a session, redact, commit. Nothing in this excerpt names the operator
    # under a key.
    excerpt = "\n".join(line for _, line in POSITIONAL_SHAPES)
    cleaned = redact(excerpt)
    assert FAKE_NAME not in cleaned
    assert FAKE_SURNAME not in cleaned
    assert_clean(cleaned)


def test_no_persona_token_survives_the_whole_document():
    cleaned = redact(PERSONA_LOG)
    assert FAKE_NAME not in cleaned
    assert FAKE_SURNAME not in cleaned
    assert FAKE_FULL_NAME not in cleaned
    assert FAKE_ROLE_ID not in cleaned


def test_a_multi_token_display_name_is_masked_whole_not_by_halves():
    # The bug this test exists for: the keyed value pattern stopped at the
    # first space, so the surname was published.
    line = _kv("onelineDisplayName", FAKE_FULL_NAME)
    assert redact(line) == _kv("onelineDisplayName", "<PERSONA>")


def test_a_keyed_display_name_does_not_swallow_the_next_key():
    cleaned = redact(_shape_play_state_tag())
    assert "TagName" in cleaned
    assert "Game.PlayState.Gaming" in cleaned
    assert "undefined" in cleaned
    assert FAKE_NAME not in cleaned


def test_a_keyed_display_name_stops_at_a_comma():
    cleaned = redact(_shape_post_login())
    assert "NetStateTag" in cleaned
    assert "Game.Net.Online" in cleaned
    assert "OnlinePlayerCount" in cleaned
    assert FAKE_FULL_NAME not in cleaned


def test_surrounding_telemetry_survives_a_positional_persona():
    cleaned = redact(_shape_ammunition_csv(), personas=[FAKE_NAME])
    assert "AmmunitionComponent_C_2147406943" in cleaned
    assert "32758" in cleaned
    assert FAKE_NAME not in cleaned


def test_the_actor_token_is_masked_whole_not_just_its_digits():
    # The old behaviour left the name and masked only the role id, which is
    # exactly backwards: the id is replaceable, the name is not.
    assert redact("spawned " + FAKE_ACTOR_TOKEN + " ok") == "spawned <ACTOR> ok"


def test_the_actor_rule_carves_out_unreal_class_tokens():
    # A ``_C_`` token is an Unreal class instance, not a player. Its id is
    # still masked, its class name is not.
    token = "BP_Adventurer_C_" + FAKE_ROLE_ID
    assert redact("owner " + token) == "owner BP_Adventurer_C_<LONG_ID>"


def test_short_unreal_instance_ids_are_still_left_alone():
    text = "BP_Preview_C_2147475781 and LocalPlayer_2147482542"
    assert redact(text) == text


# --------------------------------------------------------------------------
# persona discovery
# --------------------------------------------------------------------------


def test_discovery_finds_the_full_name_and_each_token():
    found = discover_personas(_shape_steam_channel_json())
    assert FAKE_FULL_NAME in found
    assert FAKE_NAME in found
    assert FAKE_SURNAME in found


def test_discovery_orders_the_longest_candidate_first():
    found = discover_personas(_shape_steam_channel_json())
    assert found.index(FAKE_FULL_NAME) < found.index(FAKE_NAME)


def test_discovery_reads_the_actor_token():
    assert FAKE_NAME in discover_personas("spawned " + FAKE_ACTOR_TOKEN + " ok")


def test_discovery_reads_the_dash_separated_keys():
    assert FAKE_NAME in discover_personas(_shape_periodic_buff())
    assert FAKE_FULL_NAME in discover_personas(_shape_on_rep_display_name())


def test_discovery_rejects_boolean_and_object_values():
    # ``instigator-`` also carries booleans and Unreal class instances. If
    # those were harvested, every ``true`` in the log would be masked.
    assert discover_personas(_kd("instigator", "true")) == ()
    assert discover_personas(_kd("instigator", "false")) == ()
    assert discover_personas(_kd("instigator", "BP_Warden_C_2147408590")) == ()


def test_discovery_rejects_pure_digit_values():
    assert discover_personas(_kj("role_id", FAKE_ROLE_ID)) == ()


def test_discovery_rejects_already_redacted_placeholders():
    assert discover_personas(redact(PERSONA_LOG)) == ()


def test_discovery_ignores_bare_name_assignments_that_are_not_json():
    # This is the whole reason discovery is not a RULES entry: source trees
    # and log preambles are full of ``name`` keys holding things that are not
    # people.
    source_shaped = _kc("name", "MistfallHunter") + "\n" + _kv("Name", "CoreStyle")
    assert discover_personas(source_shaped) == ()


def test_the_rules_path_never_harvests_a_bare_word():
    # test_no_pii.py scans every tracked file with iter_sensitive(). If
    # discovery lived in RULES, that scan would harvest ordinary identifiers
    # out of source and then flag every occurrence of them. A word in ordinary
    # prose, in no key and no known slot, must stay invisible to that path.
    text = "the hunter " + FAKE_NAME + " reached the camp before dusk"
    assert list(iter_sensitive(text, labels=FILE_SCAN_LABELS)) == []


def test_the_rules_path_does_flag_a_known_slot():
    # The other half of the same claim: a name in a slot the log is measured to
    # fill IS structural, so the repository scan sees it. A fixture with this
    # line in it fails tests/test_no_pii.py instead of shipping.
    text = "PlayerOpenTreasureBox " + FAKE_NAME + " -> BP_TreasureBox_FTE_08_C_2147446982"
    labels = {label for label, _, _ in iter_sensitive(text, labels=FILE_SCAN_LABELS)}
    assert "PERSONA" in labels


def test_an_explicit_persona_is_masked_without_any_key():
    text = "greeting from " + FAKE_NAME
    assert redact(text, personas=[FAKE_NAME]) == "greeting from <PERSONA>"


def test_an_explicit_empty_persona_list_disables_discovery():
    # A bare occurrence in no key and no known slot is reachable only by the
    # discovery pass, so it is the one that shows personas=[] turning discovery
    # off. The keyed half of the line is a rule and is masked either way.
    text = "the hunter " + FAKE_NAME + " arrived; " + _kj("uName", FAKE_NAME)
    assert FAKE_NAME in redact(text, personas=[])
    assert FAKE_NAME not in redact(text)


# --------------------------------------------------------------------------
# assert_clean is not allowed to be vacuous about the persona
# --------------------------------------------------------------------------


def test_assert_clean_rejects_a_surviving_persona():
    with pytest.raises(RedactionError):
        assert_clean(_shape_periodic_buff())


def test_assert_clean_rejects_a_positional_persona_when_told_the_name():
    with pytest.raises(RedactionError):
        assert_clean(_shape_adventurer_inited(), personas=[FAKE_NAME])


def test_assert_clean_names_the_label_without_echoing_the_name():
    with pytest.raises(RedactionError) as excinfo:
        assert_clean(_shape_periodic_buff())
    message = str(excinfo.value)
    assert "PERSONA" in message
    assert FAKE_NAME not in message


def test_assert_clean_passes_on_the_redacted_persona_document():
    cleaned = redact(PERSONA_LOG)
    assert_clean(cleaned)
    assert_clean(cleaned, personas=[FAKE_NAME, FAKE_SURNAME, FAKE_FULL_NAME])


def test_persona_redaction_is_idempotent():
    once = redact(PERSONA_LOG)
    assert redact(once) == once
    twice = redact(once, personas=[FAKE_NAME, FAKE_SURNAME, FAKE_FULL_NAME])
    assert twice == once


# --------------------------------------------------------------------------
# the third outcome: cannot certify
# --------------------------------------------------------------------------


def _unnamed_slot_line() -> str:
    """A dungeon line in a known name slot whose occupant is not a name."""
    return "[DungeonInventoryComponent] RequestPickupLoot, " + _kc(
        "actor", "BP_Adventurer_C_2147381775", space=""
    )


def test_assert_clean_refuses_to_certify_a_slot_it_could_not_read():
    # The failure this exists to prevent: a guard that answers "clean" when the
    # honest answer is "I had nothing to go on".
    with pytest.raises(RedactionError) as excinfo:
        assert_clean(_unnamed_slot_line())
    assert "cannot certify" in str(excinfo.value)


def test_an_explicit_empty_persona_list_is_an_assertion_and_is_accepted():
    # The escape hatch, and the only way to say "I looked, there is no name".
    assert_clean(_unnamed_slot_line(), personas=[])


def test_a_named_excerpt_certifies_without_the_cannot_certify_path():
    assert_clean(_unnamed_slot_line(), personas=[FAKE_NAME])


def test_redacted_text_carries_its_own_evidence_and_certifies():
    # A redacted dungeon excerpt is full of risk markers, so the refusal must
    # not fire once a persona pass has visibly run.
    excerpt = "\n".join(line for _, line in POSITIONAL_SHAPES)
    assert_clean(redact(excerpt))


def test_ordinary_text_with_no_slot_in_it_is_not_refused():
    assert_clean("the hunter reached the camp before dusk")


def test_persona_placeholder_is_stable_across_two_different_names():
    one = redact("hunter " + FAKE_NAME, personas=[FAKE_NAME])
    two = redact("hunter " + FAKE_SURNAME, personas=[FAKE_SURNAME])
    assert one == two == "hunter <PERSONA>"


# --------------------------------------------------------------------------
# encoded content - iter_encoded_sensitive
# --------------------------------------------------------------------------
#
# The defect these pin, measured before the fix: every rule in this module
# reads plain text, so one base64 pass blinded all of them at once and
# tests/test_no_pii.py could not see into an encoded fixture at all. That is
# not hypothetical - `.gitignore` blocks `*.sav`, so the pressure to commit an
# ENCODED copy of the exact file that carries the operator's identity is
# permanent.
#
# Nothing below is a literal encoded string. Every blob is encoded at runtime
# from an invented identifier, for the same reason the plain fixtures are
# assembled at runtime: this file is itself scanned, now including its encoded
# runs, and a literal blob here would be a real finding.


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _labels(text: str, **kwargs) -> set[str]:
    return {label for label, _, _ in iter_encoded_sensitive(text, **kwargs)}


def test_a_base64_encoded_steamid_is_caught():
    planted = "player " + FAKE_STEAMID64 + " connected"
    assert "STEAMID64" in _labels(_b64(planted))


def test_the_plain_scanner_is_still_blind_to_it():
    # Pins WHY the encoded scanner has to exist. If this ever starts failing,
    # the plain rules grew a decoder and this whole section needs rereading.
    assert not list(iter_sensitive(_b64("player " + FAKE_STEAMID64 + " connected")))


def test_a_base64_encoded_product_user_id_is_caught():
    assert "PRODUCTUSERID" in _labels(_b64("eos " + FAKE_PRODUCT_USER_ID + " ready"))


def test_a_base64_encoded_keyed_account_name_is_caught():
    assert "ACCOUNT_NAME" in _labels(_b64("login " + _kv("AccountName", FAKE_ACCOUNT)))


def test_a_base64_encoded_unkeyed_long_id_is_caught():
    assert "LONG_ID" in _labels(_b64("trace " + FAKE_UNKEYED_ID + " end"))


def test_an_unpadded_base64_run_is_still_decoded():
    # A blob clipped out of a larger stream arrives with its padding gone.
    # Refusing those would blind this to every unpadded encoder for no gain.
    encoded = _b64("player " + FAKE_STEAMID64 + " connected").rstrip("=")
    assert encoded.endswith("=") is False
    assert "STEAMID64" in _labels(encoded)


def test_a_wrapped_base64_block_is_joined_before_decoding():
    # The one that a per-line decoder gets wrong. An encoder that wraps at a
    # width not divisible by 4 puts the line break wherever it lands, so every
    # individual line decodes to garbage and only the JOINED block carries the
    # identifier.
    encoded = _b64("padding-padding " + FAKE_STEAMID64 + " tail-tail-tail")
    wrapped = "\n".join(encoded[i : i + 30] for i in range(0, len(encoded), 30))
    assert len(wrapped.splitlines()) >= 3
    per_line_blind = all(
        not _labels(line) for line in wrapped.splitlines()
    )
    assert per_line_blind, "this fixture is only meaningful if line-at-a-time fails"
    assert "STEAMID64" in _labels(wrapped)


def test_a_standard_76_column_wrapped_blob_is_caught():
    payload = ("filler " * 40) + FAKE_STEAMID64 + (" tail" * 40)
    wrapped = base64.encodebytes(payload.encode("ascii")).decode("ascii")
    assert "\n" in wrapped.strip()
    assert "STEAMID64" in _labels(wrapped)


def test_a_utf16_identifier_inside_a_blob_is_caught():
    # Unreal writes a save's strings as UTF-16 whenever they are not pure
    # ASCII, and a 17-digit id stored that way has a NUL between every digit,
    # so no digit-run rule can see it until the NULs are dropped.
    raw = ("id " + FAKE_STEAMID64).encode("utf-16-le")
    assert b"\x00" in raw
    assert not list(iter_sensitive(raw.decode("latin-1")))
    assert "STEAMID64" in _labels(base64.b64encode(raw).decode("ascii"))


def test_a_hex_encoded_blob_is_caught():
    raw = ("save\xff " + FAKE_STEAMID64 + " \xfeend").encode("latin-1")
    encoded = raw.hex()
    assert "STEAMID64" in _labels(encoded)


def test_a_double_encoded_identifier_is_caught():
    assert "STEAMID64" in _labels(_b64(_b64("player " + FAKE_STEAMID64 + " ok")))


def test_depth_one_stops_at_the_first_layer():
    # Pins the depth contract rather than leaving it to be discovered.
    doubled = _b64(_b64("player " + FAKE_STEAMID64 + " ok"))
    assert "STEAMID64" in _labels(doubled, depth=2)
    assert "STEAMID64" not in _labels(doubled, depth=1)


def test_a_long_decimal_literal_is_not_treated_as_hex():
    # The one systematic false-positive class measured on a 20,077-file
    # corpus: 0x33 is the character '3', so hex-decoding "0.3333..." hands
    # back a run of digits and trips LONG_ID. Skipping letterless runs costs
    # nothing, because a hex dump of an ASCII id is itself a long digit run
    # and the PLAIN rule already catches it - which the second assertion pins.
    literal = "0." + "3" * 40
    assert not _labels(literal)
    assert "LONG_ID" in {label for label, _, _ in iter_sensitive(literal)}


def test_a_short_base64_run_is_not_a_finding():
    # Below 20 characters a run cannot hold the shortest identifier that
    # exists, so decoding it can only manufacture noise.
    assert not _labels(_b64("abc"))


def test_ordinary_source_text_produces_no_findings():
    prose = (
        "The walker asks git what is tracked rather than guessing from "
        "extensions, and MIN_EXPECTED_FILES is a floor not a target. "
        "SomeVeryLongCamelCaseIdentifierName appears here on purpose."
    )
    assert not _labels(prose)


def test_encoded_random_noise_produces_no_findings():
    # The claim the whole design rests on: decoded garbage matches nothing.
    # Seeded, so a green run today is a green run tomorrow.
    rng = random.Random(20260809)
    for _ in range(40):
        blob = bytes(rng.randrange(256) for _ in range(2048))
        assert not _labels(base64.b64encode(blob).decode("ascii"))


def test_an_equals_sign_before_a_blob_does_not_shift_the_decode():
    # `=` is in the base64 alphabet only as trailing padding. Letting it into
    # the body would weld `key=` onto the value and push the whole decode out
    # of phase, which silently loses the identifier.
    line = _kv("payload", _b64("player " + FAKE_STEAMID64 + " connected"))
    assert "STEAMID64" in _labels(line)


def test_offsets_index_the_input_text():
    encoded = _b64("player " + FAKE_STEAMID64 + " connected")
    prefix = "log line: "
    findings = list(iter_encoded_sensitive(prefix + encoded))
    assert findings
    for _label, _description, offset in findings:
        assert (prefix + encoded)[offset:].startswith(encoded[:8])


def test_the_description_never_carries_the_decoded_value():
    # This message can land in CI output. Quoting the decoded match would turn
    # an encoded identifier into a plaintext one at the exact moment the guard
    # fires, which is the one thing this must not do.
    encoded = _b64("player " + FAKE_STEAMID64 + " " + FAKE_PERSONA)
    for _label, description, _offset in iter_encoded_sensitive(encoded):
        assert FAKE_STEAMID64 not in description
        assert FAKE_PERSONA not in description
        assert encoded not in description


def test_findings_are_deduplicated_across_passes():
    # A wrapped blob is reached by BOTH the per-line pass and the joined-block
    # pass, so the same identifier would otherwise be reported twice.
    #
    # The preconditions below are the point. Mutation testing caught an earlier
    # version of this test passing while deduplication was disabled: the
    # payload was short enough to encode onto a single line, so there was never
    # a second pass and nothing to deduplicate. It asserted 1 and got 1 for the
    # wrong reason.
    payload = ("filler " * 20) + FAKE_STEAMID64 + (" tail" * 20)
    wrapped = base64.encodebytes(payload.encode("ascii")).decode("ascii")

    lines = wrapped.splitlines()
    assert len(lines) >= 2, "fixture must wrap, or the block pass never runs"
    assert any("STEAMID64" in _labels(line) for line in lines), (
        "fixture is only meaningful if a single line also carries the id - "
        "otherwise the per-line pass finds nothing and there is no duplicate"
    )
    assert "STEAMID64" in _labels(wrapped)

    hits = [f for f in iter_encoded_sensitive(wrapped) if f[0] == "STEAMID64"]
    assert len(hits) == 1, f"expected one deduplicated finding, got {len(hits)}"


# --------------------------------------------------------------------------
# raw wide-character content - the layer above base64
# --------------------------------------------------------------------------
#
# The gap these pin, measured on 2026-08-09 against the merged tree::
#
#     UTF-16 identifier INSIDE a base64 blob -> caught
#     RAW UTF-16 identifier in a file        -> MISSED
#
# The NUL-stripped reading in _views only ever ran on DECODED bytes, so it
# reached a wide-character string one layer down and never the file's own
# content. That is backwards for this project: the game's `.sav` files are raw
# UTF-16 on disk, and Unreal writes any non-ASCII string that way, so the raw
# case is the likely accident and the encoded one is the exotic one.


def _utf16(text: str, big_endian: bool = False) -> str:
    """Return ``text`` as UTF-16 bytes read back the way a file scan reads them.

    latin-1 because that is exactly what ``tests/test_no_pii.py`` does to a
    binary: total, length-preserving, one character per byte.
    """
    codec = "utf-16-be" if big_endian else "utf-16-le"
    return text.encode(codec).decode("latin-1")


def test_a_raw_utf16_identifier_in_a_file_is_caught():
    # The reported gap, end to end at the module level. A `.sav` renamed to
    # `.bin` and committed carries its ids in exactly this shape.
    raw = _utf16("steamId" + _EQ + FAKE_STEAMID64)
    assert "\x00" in raw
    assert not list(iter_sensitive(raw, labels=FILE_SCAN_LABELS)), (
        "the plain scan is expected to be blind here - that is the defect"
    )
    assert "STEAMID64" in _labels(raw, labels=FILE_SCAN_LABELS)


def test_a_raw_utf16_identifier_is_caught_big_endian_too():
    # Unreal writes little-endian, but a hand-converted copy or a UTF-16-BE
    # export is the same leak with the NUL on the other side of every digit.
    #
    # The shape here is deliberate and mutation testing is why. A KEYED value
    # is caught even with the big-endian pattern deleted, because the
    # little-endian pattern matches the same bytes one byte in and
    # the keyed rule does not care how many digits follow. What the
    # little-endian reading loses is the LAST character of the run - it can only
    # take whole pairs - so an UNKEYED id that runs to the end of the string
    # comes back one digit short, which is a LONG_ID and not a SteamID64. That
    # is the case only the big-endian pattern reaches, so that is the case this
    # test pins.
    raw = _utf16("id " + FAKE_STEAMID64, big_endian=True)
    assert not list(iter_sensitive(raw, labels=FILE_SCAN_LABELS))
    assert "STEAMID64" in _labels(raw, labels=FILE_SCAN_LABELS)


def test_a_raw_utf16_product_user_id_is_caught():
    raw = _utf16("puid " + FAKE_PRODUCT_USER_ID + " ready")
    assert "PRODUCTUSERID" in _labels(raw, labels=FILE_SCAN_LABELS)


def test_a_raw_utf16_display_name_slot_is_caught():
    raw = _utf16("PlayerName" + _EQ + FAKE_FULL_NAME + " Tag" + _COLON + "x")
    assert "PERSONA" in _labels(raw, labels=FILE_SCAN_LABELS)


def test_the_wide_reading_does_not_bridge_a_run_of_nul_padding():
    # The false-positive this rule is shaped to avoid. Stripping every NUL in a
    # file would weld a digit before a padding run onto a digit after it and
    # manufacture a long id out of two short numbers that were never adjacent.
    # Collapsing only (char, NUL) PAIR runs cannot do that, because a pair of
    # NULs breaks the alternation.
    text = "12345678" + ("\x00" * 64) + "9012345678"
    assert not list(iter_sensitive(text, labels=FILE_SCAN_LABELS))
    assert "LONG_ID" in {
        label
        for label, _, _ in iter_sensitive(
            text.replace("\x00", ""), labels=FILE_SCAN_LABELS
        )
    }, "the naive whole-file NUL strip is only a fair comparison if it fires"
    assert not _labels(text, labels=FILE_SCAN_LABELS)


def test_a_wide_run_too_short_to_hold_an_identifier_is_not_read():
    # Below the shortest identifier that exists there is nothing to find and
    # only noise to manufacture, so the run is not collapsed at all.
    short = _utf16("abc1234")
    assert not _labels(short, labels=FILE_SCAN_LABELS)


def test_ordinary_binary_alternating_bytes_produce_no_findings():
    # An array of little-endian uint16 values looks exactly like UTF-16 to this
    # pass. Seeded, so a green run today is a green run tomorrow.
    rng = random.Random(20260810)
    for _ in range(40):
        blob = bytes(
            byte
            for _ in range(1024)
            for byte in (rng.randrange(256), 0)
        )
        assert not _labels(blob.decode("latin-1"), labels=FILE_SCAN_LABELS)


def test_the_wide_reading_reports_a_container_not_the_value():
    raw = _utf16("steamId" + _EQ + FAKE_STEAMID64)
    findings = list(iter_encoded_sensitive(raw, labels=FILE_SCAN_LABELS))
    assert findings
    for _label, description, _offset in findings:
        assert FAKE_STEAMID64 not in description
        assert "wide" in description


def test_the_wide_offset_indexes_the_input_text():
    prefix = "header padding "
    raw = prefix + _utf16("steamId" + _EQ + FAKE_STEAMID64)
    findings = list(iter_encoded_sensitive(raw, labels=FILE_SCAN_LABELS))
    assert findings
    for _label, _description, offset in findings:
        assert offset >= len(prefix) - 2
        assert offset < len(raw)


def test_a_base64_wrapped_raw_utf16_file_is_still_caught():
    # Belt and braces: the previously working path must not regress when the
    # raw path is added.
    raw = ("id " + FAKE_STEAMID64).encode("utf-16-le")
    assert "STEAMID64" in _labels(base64.b64encode(raw).decode("ascii"))


def test_a_label_subset_is_respected():
    encoded = _b64("player " + FAKE_STEAMID64 + " connected")
    assert not _labels(encoded, labels={"ACCOUNT_NAME"})
    assert "STEAMID64" in _labels(encoded, labels={"STEAMID64"})


def test_empty_text_yields_nothing():
    assert not list(iter_encoded_sensitive(""))


def test_output_is_deterministic():
    encoded = _b64("player " + FAKE_STEAMID64 + " " + _kv("AccountName", FAKE_ACCOUNT))
    assert list(iter_encoded_sensitive(encoded)) == list(iter_encoded_sensitive(encoded))


def test_assert_clean_deliberately_does_not_decode():
    # Recorded so nobody assumes coverage that is not there. redact() cannot
    # rewrite bytes inside a blob without corrupting it, so if assert_clean
    # decoded, it would raise on text redact() has no way to fix - a wedge with
    # no remedy. The gate for encoded content is the repository scan in
    # tests/test_no_pii.py, which runs over every published file. The rule for
    # callers is simply: redact BEFORE encoding, never after.
    encoded = _b64("player " + FAKE_STEAMID64 + " connected")
    assert_clean(encoded)
    assert "STEAMID64" in _labels(encoded)


# --------------------------------------------------------------------------
# save-file identifier shapes - ROADMAP 2b
# --------------------------------------------------------------------------
#
# The transient StandaloneSlot save carries four id shapes that the length-only
# LONG_ID rule catches without naming. Naming them is the point: LONG_ID says
# "a long number is here", and a fixture reviewer needs to know WHICH field
# leaked, because a BattleId and the operator's own roleId are different facts
# with different blast radii.
#
# Every number below is invented and assembled at runtime, exactly as the rest
# of this file does - see the module docstring. The real capture is never
# quoted, here or anywhere.

#: A second 19-digit id sharing the invented roleId's first 12 digits, which is
#: the relationship measured between the real BattleId and the real roleId.
FAKE_BATTLE_ID = FAKE_ROLE_ID[:12] + "7700001"

#: The save-slot name shape: ``StandaloneSlot_<19-digit roleId>``.
FAKE_SLOT_NAME = "Standalone" + "Slot_" + FAKE_ROLE_ID
FAKE_TEMP_SLOT_NAME = FAKE_SLOT_NAME + "_Temp"


def _labels_of(text: str) -> set[str]:
    """Return the labels the structural rules report for ``text``."""
    return {label for label, _, _ in iter_sensitive(text)}


def test_a_battle_id_is_named_rather_than_only_measured_for_length():
    assert "BATTLEID" in _labels_of(_kv("BattleId", FAKE_BATTLE_ID))


def test_a_battle_id_is_masked_with_its_own_placeholder():
    assert redact(_kv("BattleId", FAKE_BATTLE_ID)) == _kv("BattleId", "<BATTLEID>")


def test_a_battle_id_in_json_keeps_the_quotes_around_it():
    text = _kj("BattleId", FAKE_BATTLE_ID)
    expected = _QUOTE + "BattleId" + _QUOTE + _COLON + _QUOTE + "<BATTLEID>" + _QUOTE
    assert redact(text) == expected


def test_every_battle_id_spelling_is_covered():
    for key in ("BattleId", "battleId", "BattleID", "battle_id", "battleid"):
        assert "BATTLEID" in _labels_of(_kv(key, FAKE_BATTLE_ID)), key


def test_an_owner_role_id_is_named():
    assert "OWNER_ROLEID" in _labels_of(_kv("ownerRoleId", FAKE_ROLE_ID))
    assert "OWNER_ROLEID" in _labels_of(_kv("OwnerRoleId", FAKE_ROLE_ID))


def test_an_owner_role_id_is_masked_with_its_own_placeholder():
    assert redact(_kv("ownerRoleId", FAKE_ROLE_ID)) == _kv("ownerRoleId", "<OWNER_ROLEID>")


def test_a_role_id_is_named():
    for key in ("roleId", "RoleId", "roleid", "role_id", "RoleID"):
        assert "ROLEID" in _labels_of(_kv(key, FAKE_ROLE_ID)), key


def test_a_role_id_is_masked_with_its_own_placeholder():
    assert redact(_kc("RoleId", FAKE_ROLE_ID)) == _kc("RoleId", "<ROLEID>")


def test_owner_role_id_does_not_collapse_into_the_plain_role_id_label():
    # Two different facts. An ownerRoleId inside an ItemCell blob can name a
    # DIFFERENT player than the operator - a traded item carries its owner -
    # so a reviewer must be able to tell the two apart in a finding.
    #
    # LONG_ID is expected in both sets and is not asserted away: iter_sensitive
    # runs every rule over the same text rather than substituting in sequence,
    # so the length rule still reports the same digits. That overlap is the
    # point - these rules RENAME a finding, they do not replace the backstop.
    owner = _labels_of(_kv("OwnerRoleId", FAKE_ROLE_ID))
    plain = _labels_of(_kv("RoleId", FAKE_ROLE_ID))
    assert "OWNER_ROLEID" in owner and "ROLEID" not in owner
    assert "ROLEID" in plain and "OWNER_ROLEID" not in plain
    assert "LONG_ID" in owner and "LONG_ID" in plain


def test_the_slot_name_shape_is_masked_whole():
    assert redact("slot " + FAKE_SLOT_NAME) == "slot <SAVE_SLOT>"


def test_the_temp_slot_suffix_survives_so_the_fixture_stays_readable():
    assert redact(FAKE_TEMP_SLOT_NAME) == "<SAVE_SLOT>_Temp"


def test_the_slot_name_is_not_swallowed_by_the_actor_rule():
    # ``StandaloneSlot_<19 digits>`` fits the actor-token shape exactly - a
    # leading identifier welded to a 15-or-more-digit run - so without an
    # earlier rule it comes out as <ACTOR>, which says a player's display name
    # was found where in fact a save slot was.
    assert redact(FAKE_SLOT_NAME) == "<SAVE_SLOT>"
    assert "SAVE_SLOT" in _labels_of(FAKE_SLOT_NAME)


def test_the_slot_name_under_its_measured_keys_is_masked():
    for key in ("AutoSaveTempSlot", "AutoSaveFinalSlot"):
        assert redact(_kv(key, FAKE_SLOT_NAME)) == _kv(key, "<SAVE_SLOT>")


def test_the_new_save_labels_all_reach_the_repository_scan():
    # A label outside FILE_SCAN_LABELS is a detector the tree guard never runs,
    # which is precisely the guard the committed fixture has to pass.
    for label in ("BATTLEID", "OWNER_ROLEID", "ROLEID", "SAVE_SLOT"):
        assert label in ALL_LABELS, label
        assert label in FILE_SCAN_LABELS, label


def test_the_save_shapes_are_still_refused_by_assert_clean():
    for text in (
        _kv("BattleId", FAKE_BATTLE_ID),
        _kv("ownerRoleId", FAKE_ROLE_ID),
        _kc("RoleId", FAKE_ROLE_ID),
        FAKE_SLOT_NAME,
    ):
        with pytest.raises(RedactionError):
            assert_clean(text, personas=[])


def test_masking_the_save_shapes_is_idempotent():
    document = " ".join(
        [
            _kv("BattleId", FAKE_BATTLE_ID),
            _kv("ownerRoleId", FAKE_ROLE_ID),
            _kc("RoleId", FAKE_ROLE_ID),
            FAKE_TEMP_SLOT_NAME,
        ]
    )
    once = redact(document, personas=[])
    assert redact(once, personas=[]) == once
    assert_clean(once, personas=[])


def test_a_generated_bot_role_id_is_not_flagged_and_a_real_one_is():
    # MEASURED COLLISION, recorded rather than discovered again. docs/FINDINGS.md
    # carries a bot roleId from TS.AI generateBotPlayerStateData: five digits,
    # negative, naming no person, and already committed. A ROLEID rule taking
    # any value at all would fire on it and turn tests/test_no_pii.py red on an
    # innocent published file.
    #
    # So the keyed id rules take a digit run at LONG_ID's own floor and nothing
    # else. The pairing below is what makes that a scoping decision rather than
    # a hole: the short bot id is ignored, the long real-shaped id is caught.
    bot = "roleId" + _COLON + " " + "-14801"
    assert "ROLEID" not in _labels_of(bot)
    assert redact(bot) == bot
    assert "ROLEID" in _labels_of("roleId" + _COLON + " " + FAKE_ROLE_ID)


def test_the_keyed_id_rules_cover_exactly_what_long_id_already_covered():
    # The claim that makes these rules a RENAMING and not a narrowing: any value
    # the new keyed rules decline is a value LONG_ID declines too, so nothing
    # that used to be caught stops being caught.
    short = "roleId" + _COLON + "1234567890"
    assert _labels_of(short) == set()


# --------------------------------------------------------------------------
# measured false positives - Unreal Blueprint property GUIDs
# --------------------------------------------------------------------------
#
# Characterization, not a defect report. The transient save carries Unreal
# Blueprint property names in the shape ``Name_Index_<32 uppercase hex GUID>``
# - a variable called ``Hp`` is stored as ``Hp_10_<GUID>``. Measured on the
# largest StandaloneSlot generation, 177,878 bytes:
#
#   - 772 occurrences of a bare 32-hex run, 67 distinct. 770 occurrences (65
#     distinct) are the Blueprint property shape; the other 2 are
#     ``monsterGuid`` values inside JSON. All 772 are uppercase, and ZERO equal
#     the operator's real ProductUserId harvested from the live log.
#   - 100 occurrences of a 15-or-more digit run. 62 of them sit INSIDE one of
#     just TWO of those GUIDs, which happen to contain a 17-digit and a
#     16-digit decimal stretch; the 17-digit one recurs 61 times because the
#     same property name repeats per MonsterData entry. The remaining 38 are
#     genuine ids.
#
# So one cause - a hex GUID baked into the shipped Blueprint asset - trips TWO
# independent rules, PRODUCTUSERID by shape and LONG_ID by length.
#
# NEITHER RULE IS NARROWED. A GUID is a format fact of the shipped asset, not a
# machine fact, so the fixture authors its own GUID suffixes and both
# false-positive classes vanish without a detector being touched. Weakening a
# detector to make a build pass is prohibited outright, and here the failure
# direction is the safe one anyway: the guard refuses a commit rather than
# publishing an identity.


def _blueprint_property(name: str, index: str, guid: str) -> str:
    """Build a UE Blueprint property name at runtime. Nothing here is real."""
    return name + "_" + index + "_" + guid


#: 32 uppercase hex, the Blueprint GUID shape. Invented, and deliberately
#: carrying a 17-digit decimal stretch so it trips the length rule too.
#: The digit stretch is split across two literals for the same reason every
#: other identifier in this file is: tests/test_no_pii.py scans this source
#: with these very detectors, and a literal 17-digit run in it is a finding.
FAKE_BLUEPRINT_GUID = "AB" + "1234567" + "8901234567" + "CDEF" + "9876543" + "EF"


def test_the_blueprint_guid_shape_is_reported_as_a_product_user_id():
    assert len(FAKE_BLUEPRINT_GUID) == 32
    text = _blueprint_property("Hp", "10", FAKE_BLUEPRINT_GUID)
    assert "PRODUCTUSERID" in _labels_of(text)


def test_the_blueprint_guid_shape_also_trips_the_length_rule():
    # The second half of the same false-positive family, and the reason it is
    # worth writing down: a reader who only knew about the hex rule would
    # conclude that lowercasing or keying the hex rule fixes this. It does not.
    inner = {label for label, _, _ in iter_sensitive(FAKE_BLUEPRINT_GUID)}
    assert "LONG_ID" in inner


def test_a_real_shaped_product_user_id_is_still_caught_in_the_same_position():
    # The positive control that keeps the characterization above honest. If a
    # narrowing were ever introduced, this is the assertion that has to survive
    # it: a real-shaped puid sitting in the SAME textual position as a Blueprint
    # property GUID must still be caught.
    text = _blueprint_property("Hp", "10", FAKE_PRODUCT_USER_ID)
    assert "PRODUCTUSERID" in _labels_of(text)
    assert FAKE_PRODUCT_USER_ID not in redact(text)


def test_the_hex_rule_is_case_blind_by_design():
    # Why uppercase is not a safe discriminator: the same 32 hex characters are
    # the same identifier in either case, and any tool in the path can change
    # the case of one without changing what it identifies.
    assert "PRODUCTUSERID" in _labels_of(FAKE_PRODUCT_USER_ID.upper())
    assert "PRODUCTUSERID" in _labels_of(FAKE_PRODUCT_USER_ID.lower())


# --------------------------------------------------------------------------
# a third party's display name inside a GVAS record - the structural rule
# --------------------------------------------------------------------------
#
# MEASURED 2026-08-11 in the transient save. LeaderRankScoreData carries
# KillPlayerHistoryDatas, one record of ten fields, three of which are
# unbounded strings: PlayerName, MsgSubChannelString and MsgAppearanceString.
# In the captured run IsBot is true and PlayerName holds a generated bot name,
# so no real person's data is in this capture. That is luck. In a run with real
# players that field holds SOMEBODY ELSE'S DISPLAY NAME.
#
# WHY NO CONTENT RULE CAN REACH IT, which is the part worth writing down:
#
#   - A keyed rule cannot see it. In GVAS the property name and its value are
#     two separate length-prefixed strings; the bytes between them are the type
#     token and a binary size, and there is no ``=`` or ``:`` anywhere. The
#     module already has ``PlayerName`` as a persona key and it does not fire.
#   - Persona discovery cannot see it, for the same reason - it harvests from
#     key/value shapes, and there is no key/value shape here.
#   - A shape rule cannot see it. SAVE_SLOT works because a slot name has a
#     fixed shape; a display name has NO shape at all. A rule matching arbitrary
#     strings in a save would flag the whole file and train people to ignore it.
#
# So the rule implemented is STRUCTURAL, not content-based: these three named
# properties must carry an AUTHORED value in any committed artifact. It fires on
# the property when the authored marker is absent and goes quiet when it is
# present, which is what makes it a satisfiable condition rather than a
# permanent red.

#: A 32-character decoration that is deliberately NOT a hex run, which is what
#: an authored Blueprint GUID has to look like - see the test below.
NON_HEX_GUID = "SYNTHETICGUID" + "Z" * 19


def _gvas_string_property(
    name: str,
    value: str,
    guid: str,
    index: str = "19",
    type_token: str = "StrProperty",
) -> str:
    """Assemble one GVAS StrProperty exactly as the save writes it.

    Layout measured on the real capture: the decorated property name as an
    FString, a 4-byte length and the type token ``StrProperty``, then an 8-byte
    size, a has-guid byte, a 4-byte value length and the value. Built here from
    parts so this file never contains the byte sequence as a literal.

    ``type_token`` is a parameter because the same three property names can be
    written as ``NameProperty`` or ``TextProperty``, which carry strings the
    same way - see the hole-(b) tests at the end of this section.
    """
    return (
        name + "_" + index + "_" + guid + "\x00"
        + chr(len(type_token) + 1) + "\x00\x00\x00"
        + type_token + "\x00"
        + "\x00" * 8
        + "\x00"
        + chr(len(value) + 1) + "\x00\x00\x00"
        + value + "\x00"
    )


#: A third party's display name. Invented, and never taken from the capture.
FAKE_OTHER_PLAYER = "Some" + "OtherHunter"


def test_no_key_or_persona_mechanism_reaches_a_name_inside_a_gvas_record():
    # The refutation, pinned. Every CONTENT mechanism in this module is blind
    # here, and each for a reason that cannot be patched by adding a key.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    assert discover_personas(record) == ()
    assert FAKE_OTHER_PLAYER in redact(record, personas=[])


def test_the_structural_rule_refuses_an_unauthored_name_field():
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    assert "NAME_FIELD" in _labels_of(record)


def test_authoring_the_value_satisfies_the_rule():
    # The other half, and the one that makes this a satisfiable condition
    # rather than a permanent red that trains people to ignore it.
    record = _gvas_string_property("PlayerName", AUTHORED_NAME_MARKER, NON_HEX_GUID)
    assert "NAME_FIELD" not in _labels_of(record)


def test_all_three_measured_name_bearing_properties_are_covered():
    for prop in ("PlayerName", "MsgSubChannelString", "MsgAppearanceString"):
        assert prop in NAME_BEARING_PROPERTIES, prop
        unauthored = _gvas_string_property(prop, FAKE_OTHER_PLAYER, NON_HEX_GUID)
        authored = _gvas_string_property(prop, AUTHORED_NAME_MARKER, NON_HEX_GUID)
        assert "NAME_FIELD" in _labels_of(unauthored), prop
        assert "NAME_FIELD" not in _labels_of(authored), prop


def test_the_rule_needs_the_gvas_shape_and_not_merely_the_word():
    # Tree safety. These property names are discussed in this repository's own
    # prose, and a rule that fired on the WORD would redden the scan on every
    # document that mentions it. The NUL and the type token are what make this
    # a GVAS record rather than a sentence.
    prose = "the record carries PlayerName, MsgSubChannelString and MsgAppearanceString\n"
    assert list(iter_sensitive(prose, labels=FILE_SCAN_LABELS)) == []
    assert redact(prose) == prose


def test_the_rule_needs_a_string_valued_property_not_just_a_nul():
    # Pins the StrProperty anchor specifically. Mutation found that the prose
    # test above passes on the NUL requirement alone, so deleting this anchor
    # left every assertion green - the anchor was unpinned and would have been
    # free to delete.
    #
    # The distinction is real rather than defensive: an integer-valued property
    # cannot hold a display name, so firing on one would be a false positive in
    # a rule whose entire value is that it fires rarely and means it.
    int_valued = (
        "PlayerName" + "_19_" + NON_HEX_GUID + "\x00"
        + chr(len("IntProperty") + 1) + "\x00\x00\x00"
        + "IntProperty" + "\x00" + "\x00" * 13
    )
    assert "NAME_FIELD" not in _labels_of(int_valued)

    str_valued = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    assert "NAME_FIELD" in _labels_of(str_valued)


def test_redact_does_not_rewrite_a_gvas_name_field():
    # Detector only, deliberately. Substituting a placeholder for the property
    # name would change the byte length of a length-prefixed record and corrupt
    # the blob, while leaving the value it was supposed to protect in place -
    # strictly worse than doing nothing. The remedy is to author the value.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    assert redact(record, personas=[]) == record


def test_assert_clean_refuses_the_field_and_says_how_to_fix_it():
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    with pytest.raises(RedactionError) as excinfo:
        assert_clean(record, personas=[])
    message = str(excinfo.value)
    assert "NAME_FIELD" in message
    # Pin the REMEDY, not merely the word "author". Mutation caught this: the
    # first version asserted 'author' in message.lower(), and passed even with
    # the remedy branch disabled, because the fallback quotes the matched text
    # and the test's own sentinel GUID contained that substring. An assertion
    # satisfied by the fixture rather than by the behaviour is decoration.
    assert "AUTHOR the value" in message
    assert AUTHORED_NAME_MARKER in message
    # The message travels. It must not carry the name it just caught.
    assert FAKE_OTHER_PLAYER not in message


def test_the_name_field_label_reaches_the_repository_scan():
    assert "NAME_FIELD" in ALL_LABELS
    assert "NAME_FIELD" in FILE_SCAN_LABELS


def test_a_blueprint_hex_guid_decoration_does_not_hide_the_field():
    # The real capture decorates all three properties with a 32-hex GUID. The
    # rule must see through that decoration, not just the authored one.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, FAKE_BLUEPRINT_GUID)
    assert "NAME_FIELD" in _labels_of(record)


def test_the_name_field_survives_authoring_the_guid_away():
    # THE COUPLING THAT MAKES THIS URGENT. Today the record region is refused,
    # but only by the PRODUCTUSERID false positive firing on the Blueprint GUID
    # beside the field. A fixture builder clearing that false positive - which
    # is exactly what the fixture is required to do - removes the only thing
    # currently objecting to the record, and the display name then ships in
    # silence. So: with the GUID authored to a non-hex value, PRODUCTUSERID
    # correctly goes quiet and NAME_FIELD must still object.
    hexed = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, FAKE_BLUEPRINT_GUID)
    authored_guid = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    assert "PRODUCTUSERID" in _labels_of(hexed)
    assert "PRODUCTUSERID" not in _labels_of(authored_guid)
    assert "NAME_FIELD" in _labels_of(authored_guid)


def test_an_authored_guid_must_not_be_a_hex_run():
    # Recorded because the obvious reading of "author the GUID" is wrong. The
    # hex rule keys on SHAPE and cannot tell an authored GUID from a real
    # ProductUserId, so authoring a GUID that is still 32 hex characters
    # changes nothing at all. It has to stop being a hex run.
    assert len(NON_HEX_GUID) == 32
    assert "PRODUCTUSERID" not in _labels_of(NON_HEX_GUID)
    still_hex = "ABCDEF0123456789" * 2
    assert len(still_hex) == 32
    assert "PRODUCTUSERID" in _labels_of(still_hex)


# --------------------------------------------------------------------------
# the guard against the guard - redacting the file must not disarm the rule
# --------------------------------------------------------------------------
#
# REPRODUCED 2026-08-11 against the real capture, and the reason this section
# exists. redact() rewrites the Blueprint decoration beside a name-bearing
# property to a placeholder, and a placeholder is not alphanumeric. The first
# version of the anchor spelled the decoration as ``_\d+_[0-9A-Za-z]{1,64}``,
# so once redact() had run the anchor no longer matched, NAME_FIELD went quiet,
# and assert_clean() certified a record with a third party's display name still
# verbatim in it. Redacting the file is what broke the guard.
#
# It was invisible because the test above uses NON_HEX_GUID, a 32-character
# ALPHANUMERIC decoration that satisfies the old anchor. The tested case was not
# the case redact() actually produces - a test passing for the wrong reason,
# which is this repository's most expensive recurring failure.
#
# The fix does not widen a character class by hand. The decoration tolerates
# whatever the module's OWN placeholder shape is, and the test below derives the
# placeholder set from RULES rather than listing it, so a placeholder added
# tomorrow is covered without anyone remembering to come back here.


def _placeholders_the_module_emits() -> set[str]:
    """Every ``<LABEL>`` literal that appears in a rule's replacement.

    Derived from the module rather than listed, on purpose: a hand-maintained
    list is exactly the thing that fell out of sync and disarmed the rule.
    """
    found: set[str] = set()
    for rule in redact_module.RULES + redact_module.DETECT_ONLY_RULES:
        found.update(re.findall(r"<[A-Z0-9_]+>", rule.replacement))
    found.add(PERSONA_PLACEHOLDER)
    return found


def test_the_module_emits_more_than_a_handful_of_placeholders():
    # Guards the derivation above. If the replacements ever stop carrying their
    # placeholders literally, every test built on this set silently tests
    # nothing, and an empty loop body is the classic vacuous pass.
    emitted = _placeholders_the_module_emits()
    assert len(emitted) >= 10, sorted(emitted)
    assert "<PRODUCTUSERID>" in emitted
    assert PERSONA_PLACEHOLDER in emitted


def test_every_placeholder_the_module_emits_has_the_shape_the_anchor_tolerates():
    # The coupling, pinned. The decoration anchor is built from
    # redact._PLACEHOLDER; if a rule ever emitted a placeholder outside that
    # shape, the anchor would go blind on it and this fails instead.
    shape = re.compile(redact_module._PLACEHOLDER)
    for placeholder in sorted(_placeholders_the_module_emits()):
        assert shape.fullmatch(placeholder), placeholder
    assert shape.fullmatch(AUTHORED_NAME_MARKER)


def test_the_name_field_survives_the_module_redacting_the_decoration_away():
    # THE DEFECT, reproduced. The capture decorates the property with a 32-hex
    # Blueprint GUID; redact() rewrites that GUID to <PRODUCTUSERID>, and the
    # anchor used to stop matching at that point.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, FAKE_BLUEPRINT_GUID)
    redacted = redact(record, personas=[])

    # Assert the rewrite actually happened before believing anything about the
    # survivor - a mutation that fails to apply looks exactly like a pass.
    assert FAKE_BLUEPRINT_GUID not in redacted
    assert "<PRODUCTUSERID>" in redacted
    # And assert the hazard is still there. This is why the guard matters: the
    # display name is untouched by redact(), because no content rule reaches it.
    assert FAKE_OTHER_PLAYER in redacted

    assert "NAME_FIELD" in _labels_of(redacted)


def test_assert_clean_refuses_redacted_output_that_still_carries_the_name():
    # The other half of the same defect. iter_sensitive going quiet is only a
    # missing label; assert_clean going quiet is a published identity.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, FAKE_BLUEPRINT_GUID)
    redacted = redact(record, personas=[])
    assert FAKE_OTHER_PLAYER in redacted
    with pytest.raises(RedactionError) as excinfo:
        assert_clean(redacted, personas=[])
    assert "NAME_FIELD" in str(excinfo.value)


def test_the_anchor_sees_through_every_placeholder_the_module_can_emit():
    # Not just <PRODUCTUSERID>. LONG_ID can eat an all-digit decoration and
    # SAVE_SLOT, ACTOR and the rest are all reachable in principle, so the
    # anchor is tested against the whole emitted set rather than the one
    # placeholder that happened to be reproduced.
    for placeholder in sorted(_placeholders_the_module_emits()):
        decoration = "AUTH" + placeholder + "ZZ"
        record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, decoration)
        assert "NAME_FIELD" in _labels_of(record), placeholder


def test_the_anchor_sees_through_a_placeholder_in_the_decoration_index():
    # The index is a digit run, and this module masks digit runs. An index long
    # enough for LONG_ID to eat is implausible rather than impossible, and the
    # branch that tolerates it is free - but an untested branch is decoration,
    # so it is pinned here rather than left to be believed.
    record = _gvas_string_property(
        "PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID, index="<LONG_ID>"
    )
    assert "NAME_FIELD" in _labels_of(record)


def test_the_anchor_sees_through_a_wholly_replaced_decoration():
    # The degenerate case: redact() replaced the entire decoration, leaving a
    # placeholder and nothing else beside the property name.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, "<LONG_ID>")
    assert "NAME_FIELD" in _labels_of(record)


# --------------------------------------------------------------------------
# hole (a) - the marker must authorise a value, not merely be near one
# --------------------------------------------------------------------------


def test_a_marker_glued_to_a_real_value_does_not_authorise_it():
    # The self-authorising file. The first version of the check asked only
    # whether the marker appeared within 64 bytes of the property name, so a
    # value that merely BEGINS with the marker silenced the rule and shipped
    # whatever followed it. The marker now has to be the whole value, spelled as
    # a complete FString with its own length prefix.
    record = _gvas_string_property(
        "PlayerName", AUTHORED_NAME_MARKER + FAKE_OTHER_PLAYER, NON_HEX_GUID
    )
    assert FAKE_OTHER_PLAYER in record
    assert "NAME_FIELD" in _labels_of(record)


def test_a_marker_trailing_a_real_value_does_not_authorise_it():
    record = _gvas_string_property(
        "PlayerName", FAKE_OTHER_PLAYER + AUTHORED_NAME_MARKER, NON_HEX_GUID
    )
    assert "NAME_FIELD" in _labels_of(record)


def test_a_marker_in_the_decoration_does_not_authorise_the_value():
    # Reachable only because the anchor now tolerates placeholders in the
    # decoration, which is the fix above. The two changes have to be made
    # together or this one opens a hole the other closes.
    record = _gvas_string_property(
        "PlayerName", FAKE_OTHER_PLAYER, "AUTH" + AUTHORED_NAME_MARKER + "ZZ"
    )
    assert "NAME_FIELD" in _labels_of(record)


def test_an_authored_neighbour_does_not_authorise_an_unauthored_field():
    # Two fields, the first unauthored and the second authored. The authored
    # one's marker must not satisfy the unauthored one's check.
    unauthored = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    authored = _gvas_string_property(
        "MsgSubChannelString", AUTHORED_NAME_MARKER, NON_HEX_GUID
    )
    hits = [
        offset for label, _, offset in iter_sensitive(unauthored + authored)
        if label == "NAME_FIELD"
    ]
    assert len(hits) == 1, hits
    assert hits[0] == 0


def test_authoring_every_field_still_satisfies_the_rule_after_the_tightening():
    # Satisfiability, re-pinned against the tightened check. A guard that can
    # never be satisfied is an outage, not a guard - and the committed fixture
    # has to keep passing.
    record = "".join(
        _gvas_string_property(prop, AUTHORED_NAME_MARKER, NON_HEX_GUID)
        for prop in NAME_BEARING_PROPERTIES
    )
    assert "NAME_FIELD" not in _labels_of(record)


# --------------------------------------------------------------------------
# hole (b) - NameProperty and TextProperty carry strings too
# --------------------------------------------------------------------------


def test_the_same_property_written_as_a_name_or_text_property_is_covered():
    # The first version anchored on the literal token StrProperty, so the same
    # field written under either of the other two string-valued type tokens
    # walked straight past the guard.
    for type_token in ("NameProperty", "TextProperty"):
        unauthored = _gvas_string_property(
            "PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID, type_token=type_token
        )
        assert "NAME_FIELD" in _labels_of(unauthored), type_token
        authored = _gvas_string_property(
            "PlayerName", AUTHORED_NAME_MARKER, NON_HEX_GUID, type_token=type_token
        )
        assert "NAME_FIELD" not in _labels_of(authored), type_token


def test_a_non_string_type_token_is_still_not_covered():
    # The complement, and the reason the type token is an enumerated list rather
    # than "any word ending in Property": an integer-valued property cannot hold
    # a display name, and a rule whose value is that it fires rarely must not
    # fire on one.
    int_valued = _gvas_string_property(
        "PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID, type_token="IntProperty"
    )
    assert "NAME_FIELD" not in _labels_of(int_valued)


# --------------------------------------------------------------------------
# hole (c) - the property list grows by measurement only, said out loud
# --------------------------------------------------------------------------


def test_the_refusal_states_that_the_property_list_is_measured_only():
    # Hole (c) is not a defect to fix, it is a limit to publish. The list cannot
    # be widened by imagination without making it look authoritative when it is
    # not, so the honest move is to say so where a reader meets it: in the
    # refusal message and in the module's own stated limits.
    record = _gvas_string_property("PlayerName", FAKE_OTHER_PLAYER, NON_HEX_GUID)
    with pytest.raises(RedactionError) as excinfo:
        assert_clean(record, personas=[])
    assert "measurement only" in str(excinfo.value)


def test_the_module_docstring_states_the_property_list_limit():
    doc = redact_module.__doc__ or ""
    assert "measurement only" in doc
    assert "NAME_BEARING_PROPERTIES" in doc


# --------------------------------------------------------------------------
# ROADMAP item 9 - the cdkey detector
# --------------------------------------------------------------------------
#
# Measured first-party against the live log on 2026-08-12: 7 lines mention
# cdkey/cdk and FIVE of them carry a value token. All five hold the SAME token,
# 15 alphanumeric characters carrying upper case, lower case and digits, in four
# syntactic positions - a bare word, a bare key=value, a query parameter and
# JSON. Before this section redact() masked 0 of 5 and assert_clean certified
# 7 of 7 lines. The seventh line is a ``cDk`` inside a run of binary garbage and
# carries no value at all. ROADMAP item 9 filed 9 tokens; that count is refuted.
#
# Nothing here is copied from the log. FAKE_CDKEY is invented, and it is
# assembled from fragments and joined to its key at runtime for the reason the
# module docstring gives: this file is itself scanned by tests/test_no_pii.py
# with these very detectors, so a literal cdkey pair in the source would fail
# that scan, and correctly.

#: 15 alphanumeric characters with upper, lower and digits - the SHAPE measured
#: in the log, with invented content.
FAKE_CDKEY = "Lntrn" + "8kQ4" + "wZ2" + "j7X"

#: 19-digit runs, the shape measured under both TS.SDK keys. Invented.
FAKE_DEVICE_ID = "9182736450" + "918273645"
FAKE_USER_UNIQUE_ID = "1029384756" + "102938475"

_NEW_LABELS = frozenset({"CDKEY", "DEVICE_ID", "USER_UNIQUE_ID"})


def _ks(key: str, value: str) -> str:
    """Join a key and value with the bare space the get-cdkey line uses."""
    return key + " " + value


def test_the_cdkey_detector_fires_on_an_injected_code():
    # THE POSITIVE CONTROL, and it comes first on purpose. Item 9 exists because
    # a guard returned cleanly, so every "zero findings" claim below is
    # worthless unless the same scanner is first shown to fire.
    assert "CDKEY" in _labels_of(_kv("cdkey", FAKE_CDKEY))


def test_a_cdkey_after_the_bare_word_is_masked():
    # Position 1 of 4: the bare word, space separated, no key syntax at all.
    anchored = "get " + "cdkey"
    assert redact(_ks(anchored, FAKE_CDKEY)) == _ks(anchored, "<CDKEY>")


def test_a_cdkey_in_a_bare_key_value_list_is_masked():
    # Position 2 of 4: a bare key=value inside a comma-separated TS.UI list. The
    # trailing field must survive - a rule that ate the rest of the line would
    # be masking by accident rather than by design.
    line = _kv("cdkey", FAKE_CDKEY) + ", " + _kv("count", "32758")
    assert redact(line) == _kv("cdkey", "<CDKEY>") + ", " + _kv("count", "32758")


def test_a_cdkey_query_parameter_is_masked():
    # Position 3 of 4: a query parameter in the redemption URL. The neighbouring
    # parameter is the contrast that shows CDKEY was the only gap - the module
    # already masked the credential sitting beside it.
    query = (
        "?aid=123456&"
        + _kv("cdkey", FAKE_CDKEY)
        + "&"
        + _kv("access_token", FAKE_TOKEN)
        + "&app=1"
    )
    cleaned = redact(query)
    assert FAKE_CDKEY not in cleaned
    assert FAKE_TOKEN not in cleaned
    assert cleaned == (
        "?aid=123456&"
        + _kv("cdkey", "<CDKEY>")
        + "&"
        + _kv("access_token", "<TOKEN>")
        + "&app=1"
    )


def test_a_cdkey_in_json_is_masked_without_eating_the_quote():
    # Position 4 of 4. The closing quote has to survive or a redacted telemetry
    # blob stops being parseable - the same reason _ID_KEY_SEP steps over the
    # opening one.
    assert redact(_kj("cdkey", FAKE_CDKEY)) == _kj("cdkey", "<CDKEY>")


def test_assert_clean_refuses_a_line_carrying_a_cdkey():
    # The half that actually failed. iter_sensitive going quiet is a missing
    # label; assert_clean going quiet is a redeemable account-bound code
    # certified as safe to publish.
    for text in (
        _ks("get " + "cdkey", FAKE_CDKEY),
        _kv("cdkey", FAKE_CDKEY),
        _kj("cdkey", FAKE_CDKEY),
    ):
        with pytest.raises(RedactionError) as excinfo:
            assert_clean(text, personas=[])
        assert "CDKEY" in str(excinfo.value)


def test_redacting_a_cdkey_is_idempotent():
    for text in (
        _ks("get " + "cdkey", FAKE_CDKEY),
        _kv("cdkey", FAKE_CDKEY),
        _kj("cdkey", FAKE_CDKEY),
        "&" + _kv("cdkey", FAKE_CDKEY) + "&",
    ):
        once = redact(text)
        assert FAKE_CDKEY not in once
        assert redact(once) == once


def test_an_existing_cdkey_placeholder_is_not_remasked():
    # A placeholder lookahead in _CDKEY_VALUE was DEAD REGEX and was removed
    # rather than pinned - a guard that cannot fire is not made real by a test
    # that cannot fail.
    #
    # THIS TEST DOES NOT PIN THE CHARACTER CLASS, and saying so is the point.
    # An earlier version of this comment claimed that widening the class to
    # admit angle brackets would redden it. That mutation was run and it
    # SURVIVED. Idempotence is over-determined: every placeholder RULES can
    # emit is blocked by at least two of the class, the digit requirement and
    # the length floor - <PRODUCTUSERID> is the only one long enough, and it
    # has no digit. So no single edit exposes any of them, and this test is a
    # characterization rather than a guard. See the block above _CDKEY_VALUE.
    already = _kv("cdkey", "<CDKEY>")
    assert redact(already) == already
    assert "CDKEY" not in _labels_of(already)
    assert_clean(already, personas=[])

    # The one condition that IS load-bearing on its own for a placeholder both
    # long enough and digit-bearing - the shape no current placeholder has, and
    # the one a future label could. Pins the class directly, without a mutation.
    assert not list(iter_sensitive("cdkey=<FUTUREPLACEHOLDER9>", labels={"CDKEY"}))


def test_a_camelcase_mention_with_no_separator_is_not_a_cdkey():
    # A CHARACTERIZATION, NOT A GUARD, and it is labelled that way on purpose.
    #
    # This shape is real - the log writes a handler name of exactly this form,
    # and the ROADMAP's filed count of 9 came from a probe that read the word
    # after such a mention as a value. So it is worth having a test that says
    # out loud what this rule does with it.
    #
    # But it pins NOTHING on its own, which was established the hard way. Three
    # separate claims about which condition protects this shape were written
    # and each was refuted by its own mutation: removing "\b" left the suite
    # green, making the separator optional left it green, and removing BOTH at
    # once still left it green. The real protection is the VALUE SHAPE - the
    # following token is "Gift", four characters with no digit - and that is
    # pinned by the floor and digit tests, not by this one.
    #
    # Do not read a green here as evidence that the key or separator handling
    # is correct. It is evidence about the value shape, which is tested
    # elsewhere.
    mention = "Display: GetCDKeyGift, url == https://example.invalid/x"
    assert redact(mention) == mention
    assert "CDKEY" not in _labels_of(mention)

    # The discriminator: the SAME CamelCase token, but now followed by a real
    # separator and a code-shaped value. Here the key genuinely does introduce a
    # value and the rule must fire - so the test above is not passing merely
    # because nothing in it can ever match.
    with_sep = "Display: GetCDKeyGift " + _kv("cdkey", FAKE_CDKEY)
    assert FAKE_CDKEY not in redact(with_sep)
    assert "CDKEY" in _labels_of(with_sep)


def test_the_cdkey_label_reaches_the_repository_scan():
    assert "CDKEY" in ALL_LABELS
    assert "CDKEY" in FILE_SCAN_LABELS


# --- the design constraint: RULES also runs over every tracked file ----------


def test_the_cdkey_rule_is_quiet_on_the_prose_this_repository_already_contains():
    # The word cdkey appears in ordinary prose in this repository in code
    # blocks, sentences and comments. A naive rule reading the next word masks
    # "parameter", "and" and "tokens", and reddens the tree scan on every
    # commit. The first ten lines are the real shapes, transcribed from the
    # tracked files.
    #
    # The last three are NOT in the tree, and they are the ones that make this
    # test earn its place. Measured while mutation-testing this rule: dropping
    # the digit requirement did NOT redden the tree scan, because no word of 12
    # or more characters happens to follow the key anywhere in the repository
    # today. That is luck, not a property of the rule. An ordinary English word
    # of 12 or more letters clears the length floor on its own, so the digit is
    # the constraint that separates a code from a word - and without a case
    # that contains one, the digit requirement would be untested here and would
    # look like decoration to whoever removed it.
    prose = "\n".join(
        (
            "    lines matching cdkey/cdk            : 7",
            "URL carrying both a cdkey parameter and an access-token parameter",
            "  while admitting a redemption URL - carrying a cdkey and an",
            "**`cdkey` tokens survive `redact()` 9 of 9, and the guard CERTIFIES",
            "cdkey tokens survive redact() 9 of 9. Same vacuous-guard shape.",
            "# a redemption URL whose query string carries a cdkey and an",
            "# currently masks a cdkey, so until that is fixed this anchor is",
            "        Display: GetCDKeyGift, ",
            "an item 9 (the cdkey hole, safety lane) is next",
            "**Acceptance:** a `CDKEY` detector in `lanternlight/redact.py`",
            "the cdkey configuration is documented in the section below",
            "cdkey documentation lives beside the redaction rules",
            "a cdkey implementation note, filed against the safety lane",
        )
    )
    assert list(iter_sensitive(prose, labels=FILE_SCAN_LABELS)) == []


def test_cdk_on_its_own_is_not_a_cdkey_key():
    # ROADMAP.md's code block writes ``cdk            : 7``, which a keyed rule
    # reading ``cdk`` would parse as key and value. ``cdk`` is also the only
    # shape that produced a false positive in the log - a run of binary garbage
    # - so it is deliberately not a key.
    assert list(iter_sensitive("cdk            : 7", labels=FILE_SCAN_LABELS)) == []
    assert list(iter_sensitive(_kv("cdk", FAKE_CDKEY), labels=FILE_SCAN_LABELS)) == []


def test_the_tracked_tree_is_quiet_under_the_new_labels():
    # The positive control runs FIRST, inside this test, with the same labels
    # and the same scanner. A zero finding over the tree proves nothing unless
    # the scanner that produced it is shown alive in the same breath.
    planted = "\n".join(
        (
            "&" + _kv("cdkey", FAKE_CDKEY) + "&",
            _kv("device_id", FAKE_DEVICE_ID),
            _kj("user_unique_id", FAKE_USER_UNIQUE_ID),
        )
    )
    fired = {label for label, _, _ in iter_sensitive(planted, labels=_NEW_LABELS)}
    assert fired == set(_NEW_LABELS), fired

    findings = []
    scanned = 0
    for path in _tracked.iter_scannable_files():
        try:
            text = path.read_bytes().decode("latin-1")
        except OSError:
            continue
        scanned += 1
        for label, matched, offset in iter_sensitive(text, labels=_NEW_LABELS):
            findings.append((str(path), label, offset, len(matched)))
    assert scanned >= _tracked.MIN_EXPECTED_FILES, scanned
    assert findings == [], findings


# --- the limits, written down rather than hedged in chat ---------------------


def test_a_code_with_no_digit_in_it_is_not_caught():
    # THE ACCEPTED LIMIT, pinned so it cannot quietly be forgotten. The digit
    # requirement is the only thing keeping this rule off ordinary prose, and
    # prose is the binding constraint because RULES runs over every tracked
    # file. A purely alphabetic gift code walks past this detector.
    alphabetic = "LanternKeyAbcde"
    assert len(alphabetic) == len(FAKE_CDKEY)
    assert not any(char.isdigit() for char in alphabetic)
    assert redact(_kv("cdkey", alphabetic)) == _kv("cdkey", alphabetic)


def test_a_code_below_the_measured_floor_is_not_caught():
    # The other accepted limit. The floor sits below the 15 characters measured
    # so a rotated format has headroom, but it is a floor and a shorter code is
    # not reached.
    short = "Ab1" + "cd2"
    assert len(short) < redact_module._CDKEY_MIN_CHARS
    assert redact(_kv("cdkey", short)) == _kv("cdkey", short)


def test_the_module_states_the_cdkey_limits():
    # A caveat stated in chat but dropped from the artifact is a lie in the
    # artifact. These limits have to be readable where somebody meets the rule.
    doc = redact_module.__doc__ or ""
    assert "CDKEY" in doc
    assert "no digit in it is not caught" in doc


# --- device_id and user_unique_id: the recorded decision ---------------------


def test_a_device_id_is_named_rather_than_only_measured_for_length():
    assert "DEVICE_ID" in _labels_of(_kv("device_id", FAKE_DEVICE_ID))
    assert redact(_kv("device_id", FAKE_DEVICE_ID)) == _kv("device_id", "<DEVICE_ID>")


def test_a_user_unique_id_is_named_rather_than_only_measured_for_length():
    assert "USER_UNIQUE_ID" in _labels_of(_kj("user_unique_id", FAKE_USER_UNIQUE_ID))
    assert redact(_kj("user_unique_id", FAKE_USER_UNIQUE_ID)) == _kj(
        "user_unique_id", "<USER_UNIQUE_ID>"
    )


def test_the_two_sdk_labels_reach_the_repository_scan():
    for label in ("DEVICE_ID", "USER_UNIQUE_ID"):
        assert label in ALL_LABELS, label
        assert label in FILE_SCAN_LABELS, label


def test_the_two_sdk_rules_are_a_renaming_and_not_a_widening():
    # The BATTLEID / OWNER_ROLEID / ROLEID precedent. Each takes a digit run at
    # LONG_ID's own floor, so every value they decline LONG_ID declines too -
    # nothing that was caught before stops being caught, and nothing new starts.
    short = "1234567890" + "123"
    assert len(short) < redact_module._LONG_ID_MIN_DIGITS
    for key in ("device_id", "user_unique_id"):
        assert redact(_kv(key, short)) == _kv(key, short)
        assert list(iter_sensitive(_kv(key, short))) == []


def test_the_two_sdk_shapes_were_already_masked_before_being_named():
    # The measured fact this decision rests on, re-derived here rather than
    # cited: a bare 19-digit run is LONG_ID's business already. Naming it adds a
    # label, not coverage - and the module says so.
    assert "LONG_ID" in _labels_of(FAKE_DEVICE_ID)
    assert redact(FAKE_DEVICE_ID) == "<LONG_ID>"


def test_the_two_sdk_shapes_are_refused_by_assert_clean():
    for text in (
        _kv("device_id", FAKE_DEVICE_ID),
        _kj("user_unique_id", FAKE_USER_UNIQUE_ID),
    ):
        with pytest.raises(RedactionError):
            assert_clean(text, personas=[])


def test_the_module_records_the_device_id_decision():
    doc = redact_module.__doc__ or ""
    assert "DEVICE_ID" in doc
    assert "USER_UNIQUE_ID" in doc
