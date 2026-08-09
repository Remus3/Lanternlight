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
