"""Tests for lanternlight.logparse against verbatim real log lines.

The SAMPLE_LINES below are copied byte-for-byte from a real
MistfallHunter.log captured on 2026-08-09, including the double space in
``inclassid  ==10`` and the trailing space at end of line. They are stored as
one string per line rather than one triple-quoted block precisely so the
trailing spaces live inside the quotes and cannot be eaten by an editor, a
formatter or a trailing-whitespace lint rule.

None of these lines carry an identifier - they were chosen from the parts of
the log that contain only actor names and content ids.

The same rule governs the fixtures added for the level-switch, map-URL,
match-id and sublevel families further down. Two extra exclusions were applied
when picking those, because the real log does carry both in this area:

- Lines that append the player's persona to a map URL as a query option were
  rejected outright. No reworded or partially masked version of one is used
  either: ``tests/test_no_pii.py`` flags the whole ``<key>=<value>`` shape for
  that key regardless of the value, which is the correct behaviour for a
  pattern guard, so the allowlist test below uses a synthetic extra key
  instead and a verbatim ``?kicked`` line for the real-shape coverage.
- Lines carrying ``battleId`` were rejected. It is a long opaque server-side
  run identifier whose sensitivity has not been assessed, so it is not
  committed and not extracted.

The ``levelId``/``roomModeId``/``matchType``/``matchId`` values below are the
ones already published in ``ROADMAP.md`` item 1.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight.logparse import (  # noqa: E402  (path bootstrap must run first)
    CLASS_NAMES,
    ClassSelectionEvent,
    LevelSwitchEvent,
    LogLine,
    MapTransitionEvent,
    MapUrlEvent,
    MatchIdEvent,
    MatchStateEvent,
    SubLevelEvent,
    WeaponConfigEvent,
    WeaponHoldingEvent,
    class_name,
    iter_events,
    parse_line,
    parse_lines,
)

CLASS_GENDER_LINE = (
    "[2026.08.09-13.21.28:440][656]TS.Dungeon: [basedatacomponent] "
    "setClassGender inclassid  ==10, inGender ==1 "
)
OLD_CLASS_GENDER_LINE = (
    "[2026.08.09-13.21.28:440][656]TS.Dungeon: [basedatacomponent] "
    "setClassGender oldClassId  ==0, oldgender ==0 "
)
KNIGHT_FEATURE_LINE = (
    "[2026.08.09-13.21.28:626][656]TS.Avatar: [AvatarComponent] "
    "server_refreshKnightFeature: BP_Preview_C_2147475781 class-10 holding-30402"
)
ARMOR_PARTS_LINE = (
    "[2026.08.09-13.21.28:646][657]TS.Avatar: [AvatarComponent] "
    "server_refreshArmorParts: BP_Preview_C_2147475781 class-10 gender-1 "
    "spiritual-false hideHead-false armors-[0,12301,13301,14301,15301,0] "
    "appearance-[0,0,0,0,0]"
)
MATCH_STATE_LINE = (
    "[2026.08.09-13.20.16:590][980]TS.Camp: Display: [CampControllerColorComp] "
    "match state changed to NotMatch, update color accordingly"
)
PAWN_SET_LINE = (
    "[2026.08.09-13.20.16:624][980]TS.System: [TSGameInstance] "
    "HandleLocalPlayerPawnSet LocalPlayer_2147482382 BP_CampAdventurer_C_2147476332"
)
WINDOW_OPEN_LINE = (
    "[2026.08.09-14.16.59:725][150]TS.UI: Verbose: [WindowHandle] "
    "open WBP_CreateRole_CreateView at world CampMap"
)

SAMPLE_LINES = [
    CLASS_GENDER_LINE,
    OLD_CLASS_GENDER_LINE,
    KNIGHT_FEATURE_LINE,
    ARMOR_PARTS_LINE,
    MATCH_STATE_LINE,
    PAWN_SET_LINE,
    WINDOW_OPEN_LINE,
]

#: The whole fixture as one blob, the way a reader would see it off disk.
SAMPLE_LOG = "\n".join(SAMPLE_LINES) + "\n"


# --------------------------------------------------------------------------
# parse_line
# --------------------------------------------------------------------------


def test_every_sample_line_parses():
    parsed = [parse_line(line) for line in SAMPLE_LINES]
    assert all(p is not None for p in parsed), [
        line for line, p in zip(SAMPLE_LINES, parsed, strict=True) if p is None
    ]


def test_header_fields_are_split_correctly():
    line = parse_line(KNIGHT_FEATURE_LINE)
    assert line is not None
    assert line.frame == 656
    assert line.category == "TS.Avatar"
    assert line.verbosity is None
    assert line.message.startswith("[AvatarComponent] server_refreshKnightFeature:")


def test_dotted_category_and_verbosity_word_are_separated():
    line = parse_line(MATCH_STATE_LINE)
    assert line is not None
    assert line.category == "TS.Camp"
    assert line.verbosity == "Display"
    assert line.message.startswith("[CampControllerColorComp] match state changed")

    verbose = parse_line(WINDOW_OPEN_LINE)
    assert verbose is not None
    assert verbose.category == "TS.UI"
    assert verbose.verbosity == "Verbose"


def test_component_bracket_is_not_mistaken_for_a_verbosity_word():
    line = parse_line(PAWN_SET_LINE)
    assert line is not None
    assert line.verbosity is None
    assert line.message.startswith("[TSGameInstance]")


# --------------------------------------------------------------------------
# whitespace quirks
# --------------------------------------------------------------------------


def test_double_space_before_operator_is_preserved_in_the_message():
    # The real log writes "inclassid  ==10" with two spaces. Preserving it
    # matters: it is evidence about the emitting code, and any parser that
    # normalises it is a parser that split on a single space somewhere.
    assert "inclassid  ==10" in CLASS_GENDER_LINE
    line = parse_line(CLASS_GENDER_LINE)
    assert line is not None
    assert "inclassid  ==10" in line.message


def test_double_space_does_not_break_field_extraction():
    events = list(iter_events([CLASS_GENDER_LINE]))
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ClassSelectionEvent)
    assert event.class_id == 10
    assert event.gender == 1


def test_trailing_space_is_stripped_from_the_message():
    assert CLASS_GENDER_LINE.endswith(" ")
    line = parse_line(CLASS_GENDER_LINE)
    assert line is not None
    assert not line.message.endswith(" ")
    assert line.message.endswith("inGender ==1")


def test_crlf_line_ending_is_tolerated():
    line = parse_line(KNIGHT_FEATURE_LINE + "\r\n")
    assert line is not None
    assert line.frame == 656


# --------------------------------------------------------------------------
# junk tolerance
# --------------------------------------------------------------------------


def test_junk_lines_return_none_and_never_raise():
    junk = [
        "",
        "   ",
        "\n",
        "this is not a log line",
        "[incomplete",
        "    at SomeContinuationFrame()",
        "[2026.08.09-13.21.28:44",
        "LogInit: Display: no bracket header at all",
        "[2026.13.45-99.99.99:999][1]TS.Bad: impossible calendar date",
    ]
    for text in junk:
        assert parse_line(text) is None, text


def test_parse_lines_drops_junk_and_keeps_the_rest():
    mixed = ["garbage", CLASS_GENDER_LINE, "", KNIGHT_FEATURE_LINE]
    kept = list(parse_lines(mixed))
    assert len(kept) == 2
    assert all(isinstance(item, LogLine) for item in kept)


# --------------------------------------------------------------------------
# timestamps
# --------------------------------------------------------------------------


def test_timestamp_is_aware_and_utc():
    line = parse_line(CLASS_GENDER_LINE)
    assert line is not None
    assert line.timestamp.tzinfo is not None
    assert line.timestamp.utcoffset().total_seconds() == 0
    assert line.timestamp == datetime(2026, 8, 9, 13, 21, 28, 440000, tzinfo=UTC)


def test_milliseconds_become_microseconds():
    line = parse_line(WINDOW_OPEN_LINE)
    assert line is not None
    assert line.timestamp == datetime(2026, 8, 9, 14, 16, 59, 725000, tzinfo=UTC)


def test_timestamps_are_ordered_as_written_not_reinterpreted_locally():
    earlier = parse_line(MATCH_STATE_LINE)
    later = parse_line(WINDOW_OPEN_LINE)
    assert earlier is not None
    assert later is not None
    assert earlier.timestamp < later.timestamp


# --------------------------------------------------------------------------
# class ids
# --------------------------------------------------------------------------


def test_class_names_are_the_measured_mapping():
    assert CLASS_NAMES == {
        10: "Mercenary",
        11: "Sorcerer",
        12: "Blackarrow",
        13: "Shadowstrix",
        14: "Seer",
        15: "Withered Knight",
    }


def test_class_name_resolves_known_ids():
    assert class_name(10) == "Mercenary"
    assert class_name(15) == "Withered Knight"


def test_class_name_returns_none_for_unknown_ids_rather_than_guessing():
    for unknown in (0, 9, 16, 99, -1, 30402):
        assert class_name(unknown) is None, unknown


def test_class_selection_event_exposes_the_label():
    event = next(iter(iter_events([CLASS_GENDER_LINE])))
    assert isinstance(event, ClassSelectionEvent)
    assert event.class_label == "Mercenary"


# --------------------------------------------------------------------------
# holding ids
# --------------------------------------------------------------------------


def test_holding_id_is_extracted_with_actor_and_class():
    events = list(iter_events([KNIGHT_FEATURE_LINE]))
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, WeaponHoldingEvent)
    assert event.holding_id == 30402
    assert event.class_id == 10
    assert event.actor == "BP_Preview_C_2147475781"
    assert event.class_label == "Mercenary"


def test_measured_creation_holding_ids_parse_for_every_class():
    # Confirmed holding ids seen at character creation, per class.
    observed = {
        10: [30401, 30402],
        11: [30503],
        12: [30504],
        13: [30505, 30506],
        14: [30507, 30508],
        15: [30409, 30410],
    }
    for class_id, holdings in observed.items():
        for holding in holdings:
            text = (
                "[2026.08.09-13.21.28:626][656]TS.Avatar: [AvatarComponent] "
                "server_refreshKnightFeature: BP_Preview_C_2147475781 "
                f"class-{class_id} holding-{holding}"
            )
            event = next(iter(iter_events([text])))
            assert isinstance(event, WeaponHoldingEvent)
            assert event.holding_id == holding
            assert event.class_id == class_id
            assert event.class_label == CLASS_NAMES[class_id]


def test_field_order_is_not_assumed():
    swapped = (
        "[2026.08.09-13.21.28:626][656]TS.Avatar: [AvatarComponent] "
        "server_refreshKnightFeature: holding-30506 BP_Preview_C_2147475781 class-13"
    )
    event = next(iter(iter_events([swapped])))
    assert isinstance(event, WeaponHoldingEvent)
    assert event.holding_id == 30506
    assert event.class_id == 13
    assert event.actor == "BP_Preview_C_2147475781"


def test_armor_parts_line_is_not_a_holding_event():
    # It carries class- and gender- but no holding-, and its bracketed
    # armors-[...] payload must not be mis-read as a key/value pair.
    assert list(iter_events([ARMOR_PARTS_LINE])) == []


def test_old_class_gender_line_is_not_a_selection_event():
    assert list(iter_events([OLD_CLASS_GENDER_LINE])) == []


# --------------------------------------------------------------------------
# other events
# --------------------------------------------------------------------------


def test_match_state_event():
    event = next(iter(iter_events([MATCH_STATE_LINE])))
    assert isinstance(event, MatchStateEvent)
    assert event.state == "NotMatch"


def test_map_transition_event():
    event = next(iter(iter_events([WINDOW_OPEN_LINE])))
    assert isinstance(event, MapTransitionEvent)
    assert event.world == "CampMap"
    assert event.subject == "WBP_CreateRole_CreateView"


def test_iter_events_over_the_whole_fixture():
    events = list(iter_events(SAMPLE_LOG.splitlines()))
    kinds = [type(event).__name__ for event in events]
    assert kinds == [
        "ClassSelectionEvent",
        "WeaponHoldingEvent",
        "MatchStateEvent",
        "MapTransitionEvent",
    ]


def test_iter_events_accepts_already_parsed_lines():
    parsed = list(parse_lines(SAMPLE_LINES))
    from_raw = list(iter_events(SAMPLE_LINES))
    from_parsed = list(iter_events(parsed))
    assert from_raw == from_parsed


def test_iter_events_ignores_junk_without_raising():
    assert list(iter_events(["garbage", "", "[nope"])) == []


# ==========================================================================
# Fixtures for the families added for the live tail (ROADMAP item 3).
#
# Every line below is verbatim from the same 2026-08-09 log, re-measured on
# 2026-08-12. That file is STATIC - one log, mtime 2026-08-09 18:03:53, size
# 12,899,997 bytes, unchanged across this whole session. The game is not
# running and the counts quoted below are exact, not lower bounds.
#
# Do not restate its line count without naming the reading mode: the same
# bytes give 101198 (LF count), 101199 (split on newline) and 101299
# (text-mode readlines, which also splits on the 101 lone CRs). An earlier
# draft of this file inferred from that spread that the log was growing. It
# was not; the spread is a reading-mode artifact.
# ==========================================================================

# --- OnRep_WeaponCfgId: 270 lines, one field, sometimes 0 and sometimes -1.
WEAPON_CFG_LINE = "[2026.08.09-13.21.28:446][656]TS.Dungeon: OnRep_WeaponCfgId: 30402"
WEAPON_CFG_ZERO_LINE = (
    "[2026.08.09-14.36.10:491][ 98]TS.Dungeon: OnRep_WeaponCfgId: 0"
)
WEAPON_CFG_NEGATIVE_LINE = (
    "[2026.08.09-14.42.13:367][283]TS.Dungeon: OnRep_WeaponCfgId: -1"
)
WEAPON_CFG_WIDE_LINE = (
    "[2026.08.09-14.43.25:052][770]TS.Dungeon: OnRep_WeaponCfgId: 3020401"
)

# --- [LevelSwitch]: 44 lines, exactly 11 per verb, so 11 real switches.
LEVEL_SWITCH_OPEN_LINE = (
    "[2026.08.09-20.38.35:441][757]TS.Utils: [LevelSwitch] openLevel -> "
    "openLevelWithTransition (dev phase, plan B) "
    "target=/Game/Project/Maps/Map_2/Whitewoods_Day"
)
LEVEL_SWITCH_FOUR_AXIS_LINE = (
    "[2026.08.09-20.38.35:441][757]TS.Utils: [LevelSwitch] "
    "openLevelWithTransition begin target=/Game/Project/Maps/Map_2/Whitewoods_Day "
    "options=levelId=117&roomModeId=0&matchType=1&matchId=11111&"
)
LEVEL_SWITCH_THREE_AXIS_LINE = (
    "[2026.08.09-14.03.58:947][149]TS.Utils: [LevelSwitch] "
    "openLevelWithTransition begin "
    "target=/Game/Project/Maps/Prologue_New/Prologue_New "
    "options=levelId=1&roomModeId=9&matchId=0"
)
LEVEL_SWITCH_SINGLE_HOP_LINE = (
    "[2026.08.09-14.53.35:681][122]TS.Utils: [LevelSwitch] "
    "openLevelWithTransition: CVar disabled (delayMs=0), bypass transition and "
    "single-hop to /Game/Project/Maps/CampMap/CampMap"
)
LEVEL_SWITCH_KICKED_LINE = (
    "[2026.08.09-14.07.25:527][ 75]TS.Utils: [LevelSwitch] "
    "openLevelWithTransition begin target=/Game/Project/Startup options=kicked"
)
LEVEL_SWITCH_DIRECT_LINE = (
    "[2026.08.09-13.20.15:384][980]TS.Utils: [LevelSwitch] openLevelDirect "
    "(second hop, bypass transition) target=/Game/Project/Maps/CampMap/CampMap "
    "options=option=GAA="
)

# --- The engine-side map URL, five producers.
BROWSE_THREE_AXIS_LINE = (
    "[2026.08.09-14.03.58:998][150]LogGlobalStatus: UEngine::Browse Started "
    'Browse: "/Game/Project/Maps/Prologue_New/Prologue_New'
    '?levelId=1&roomModeId=9&matchId=0"'
)
BROWSE_OPAQUE_OPTION_LINE = (
    "[2026.08.09-13.20.15:394][980]LogNet: Browse: "
    "/Game/Project/Maps/CampMap/CampMap?option=GAA="
)
LOADMAP_FOUR_AXIS_LINE = (
    "[2026.08.09-20.38.35:493][758]LogLoad: LoadMap: "
    "/Game/Project/Maps/Map_2/Whitewoods_Day"
    "?levelId=117&roomModeId=0&matchType=1&matchId=11111&"
)
OPTIONS_STRING_LINE = (
    "[2026.08.09-14.03.59:786][150]TS.Dungeon: [DungeonGameMode]OptionsString: "
    "?levelId=1&roomModeId=9&matchId=0."
)
BROWSE_KICKED_LINE = (
    "[2026.08.09-14.07.25:534][ 75]LogNet: Browse: /Game/Project/Startup?kicked"
)

#: Synthetic, not from the log. The real line this stands in for appends the
#: player's persona as a further query option and so cannot be committed; this
#: substitutes a harmless extra key to pin the same property, which is that
#: anything outside the four measured axes is never lifted into a field.
SYNTHETIC_EXTRA_KEY_LINE = (
    "[2026.08.09-14.03.58:998][150]LogNet: Browse: "
    "/Game/Project/Maps/Prologue_New/Prologue_New"
    "?levelId=1&roomModeId=9&matchId=0&someUnmeasuredKey=4242"
)

# --- "match id" in prose, four producers. Irregular whitespace throughout.
MAP_ACTOR_TAG_LINE = (
    "[2026.08.09-13.20.15:385][980]TS.Dungeon: getMapActorFilterTagByURL "
    "tag is  with level id 0, match id 0"
)
PLAYER_START_LINE = (
    "[2026.08.09-14.04.00:002][150]TS.Dungeon: InitPlayerStartSelect: "
    "get start point 0-0 :  undefined, match id 0, mapMatchIdTag : PrologueMap"
)
ENTER_STANDALONE_LINE = (
    "[2026.08.09-20.38.19:373][915]TS.Dungeon: StandaloneLevel "
    "requestEnterStandaloneLevel: match id 11111 rooModeId undefined "
    "bIsReconnect undefined, IsNormalAsyncSaveGameSlot false"
)

# --- Sublevels. Note "levelid" here and "levelId" on the error line.
SUBLEVEL_UNLOAD_LINE = (
    "[2026.08.09-14.03.58:947][149]TS.Dungeon: setUnloadSubLevelSet with "
    "mapResCfg levelid 1 unloaded subLevel 0!"
)
SUBLEVEL_ERROR_LINE = (
    "[2026.08.09-13.20.15:385][980]TS.Dungeon: setUnloadSubLevelSet errors with "
    "missing mapResCfg levelId 0!"
)
SUBLEVEL_LOAD_LINE = (
    "[2026.08.09-20.38.38:198][758]TS.Default: MapSelector: onPostLoadMap "
    "Whitewoods_Day loadSubLevel WhiteWoods_Level_Easy"
)

#: Synthetic. The literal text "loadSubLevel" occurs inside the game's own
#: identifier "setUnloadSubLevelSet", so a recogniser that searches for it
#: without a left word-boundary guard reads an unload as a load. Every real
#: occurrence happens to be followed by "Set" rather than a space, which hides
#: the bug; this line is the shape that would expose it.
SUBLEVEL_SUBSTRING_TRAP_LINE = (
    "[2026.08.09-13.20.15:385][980]TS.Dungeon: setUnloadSubLevel 3 requested"
)

# --- Real lines that carry "<key>=<digits>" and are NOT map URLs. 1313 lines
# carry a bare "id=<digits>" alone, so a map-URL recogniser that reads any
# key/value pair instead of the four measured axes re-creates the same
# over-firing defect that MapTransitionEvent has.
ARROW_ID_LINE = (
    "[2026.08.09-13.21.53:479][728]TS.Dungeon: addDefaultArrow, id=120500"
)
DURABILITY_LINE = (
    "[2026.08.09-14.51.03:875][356]TS.Inventory: reduceItemDurability "
    "itemId=46 reduceDurability=384 durability=616"
)

TAIL_SAMPLE_LINES = [
    WEAPON_CFG_LINE,
    WEAPON_CFG_ZERO_LINE,
    WEAPON_CFG_NEGATIVE_LINE,
    WEAPON_CFG_WIDE_LINE,
    LEVEL_SWITCH_OPEN_LINE,
    LEVEL_SWITCH_FOUR_AXIS_LINE,
    LEVEL_SWITCH_THREE_AXIS_LINE,
    LEVEL_SWITCH_SINGLE_HOP_LINE,
    LEVEL_SWITCH_KICKED_LINE,
    LEVEL_SWITCH_DIRECT_LINE,
    BROWSE_THREE_AXIS_LINE,
    BROWSE_OPAQUE_OPTION_LINE,
    LOADMAP_FOUR_AXIS_LINE,
    OPTIONS_STRING_LINE,
    BROWSE_KICKED_LINE,
    MAP_ACTOR_TAG_LINE,
    PLAYER_START_LINE,
    ENTER_STANDALONE_LINE,
    SUBLEVEL_UNLOAD_LINE,
    SUBLEVEL_ERROR_LINE,
    SUBLEVEL_LOAD_LINE,
]


def _only(text):
    """Return the single event for ``text``, asserting there is exactly one."""
    events = list(iter_events([text]))
    assert len(events) == 1, (text, events)
    return events[0]


def test_every_tail_sample_line_parses():
    parsed = [parse_line(line) for line in TAIL_SAMPLE_LINES]
    assert all(p is not None for p in parsed), [
        line for line, p in zip(TAIL_SAMPLE_LINES, parsed, strict=True) if p is None
    ]


# --------------------------------------------------------------------------
# OnRep_WeaponCfgId
# --------------------------------------------------------------------------


def test_weapon_cfg_id_is_an_event():
    # It carries neither "holding-" nor "==", so neither pre-existing field
    # extractor fires on it; before this recogniser the whole family was 270
    # unrecognised lines.
    assert "holding-" not in WEAPON_CFG_LINE
    assert "==" not in WEAPON_CFG_LINE
    event = _only(WEAPON_CFG_LINE)
    assert isinstance(event, WeaponConfigEvent)
    assert event.weapon_cfg_id == 30402


def test_weapon_cfg_id_zero_is_a_measured_value_not_an_absence():
    # 0 is observed 6 times. It must arrive as an event carrying 0, not as a
    # dropped line, or "unarmed" becomes indistinguishable from "unmeasured".
    event = _only(WEAPON_CFG_ZERO_LINE)
    assert isinstance(event, WeaponConfigEvent)
    assert event.weapon_cfg_id == 0


def test_weapon_cfg_id_negative_sentinel_parses():
    # -1 is observed twice. What it means is NOT measured, so it is carried
    # through verbatim rather than translated into an absence.
    event = _only(WEAPON_CFG_NEGATIVE_LINE)
    assert isinstance(event, WeaponConfigEvent)
    assert event.weapon_cfg_id == -1


def test_weapon_cfg_id_spans_two_id_widths():
    # Five-digit ids overlap the creation-time "holding-" space; seven-digit
    # ids do not appear there at all. No claim is made that they are one space.
    narrow = _only(WEAPON_CFG_LINE)
    wide = _only(WEAPON_CFG_WIDE_LINE)
    assert isinstance(wide, WeaponConfigEvent)
    assert wide.weapon_cfg_id == 3020401
    assert narrow.weapon_cfg_id == 30402


def test_weapon_cfg_line_is_not_a_weapon_holding_event():
    assert not isinstance(_only(WEAPON_CFG_LINE), WeaponHoldingEvent)
    # ... and the holding- family is untouched.
    assert isinstance(_only(KNIGHT_FEATURE_LINE), WeaponHoldingEvent)


# --------------------------------------------------------------------------
# [LevelSwitch] - the real map transition
# --------------------------------------------------------------------------


def test_level_switch_is_a_distinct_event_from_map_transition():
    # This is the defect fix. [LevelSwitch] names an actual map change and was
    # recognised 0 times out of 44; "at world" matched 4408 lines that are
    # overwhelmingly UI widgets. The two must not be the same event type.
    switch = _only(LEVEL_SWITCH_OPEN_LINE)
    assert isinstance(switch, LevelSwitchEvent)
    assert not isinstance(switch, MapTransitionEvent)

    widget = _only(WINDOW_OPEN_LINE)
    assert isinstance(widget, MapTransitionEvent)
    assert not isinstance(widget, LevelSwitchEvent)


def test_level_switch_extracts_verb_target_and_map_name():
    event = _only(LEVEL_SWITCH_OPEN_LINE)
    assert isinstance(event, LevelSwitchEvent)
    assert event.verb == "openLevel"
    assert event.url.target == "/Game/Project/Maps/Map_2/Whitewoods_Day"
    assert event.url.map_name == "Whitewoods_Day"


def test_level_switch_target_after_single_hop_phrasing():
    # This shape has no "target=" at all, and it does carry "delayMs=0" which
    # must not be mistaken for the target.
    assert "target=" not in LEVEL_SWITCH_SINGLE_HOP_LINE
    event = _only(LEVEL_SWITCH_SINGLE_HOP_LINE)
    assert isinstance(event, LevelSwitchEvent)
    assert event.url.target == "/Game/Project/Maps/CampMap/CampMap"
    assert event.url.map_name == "CampMap"
    assert event.verb == "openLevelWithTransition"


def test_level_switch_parses_all_four_url_axes():
    event = _only(LEVEL_SWITCH_FOUR_AXIS_LINE)
    assert isinstance(event, LevelSwitchEvent)
    assert event.url.level_id == 117
    assert event.url.room_mode_id == 0
    assert event.url.match_type == 1
    assert event.url.match_id == 11111
    assert event.url.axes == {
        "levelId": 117,
        "roomModeId": 0,
        "matchType": 1,
        "matchId": 11111,
    }


def test_absent_match_type_is_omitted_and_measured_zero_is_kept():
    # The single most important distinction in this slice. On the Prologue URL
    # matchType is simply not written, while roomModeId and matchId ARE
    # written and one of them is zero. Defaulting matchType to 0 would forge a
    # measurement; dropping matchId would lose one.
    assert "matchType" not in LEVEL_SWITCH_THREE_AXIS_LINE
    event = _only(LEVEL_SWITCH_THREE_AXIS_LINE)
    assert isinstance(event, LevelSwitchEvent)
    assert event.url.match_type is None
    assert "matchType" not in event.url.axes
    assert event.url.match_id == 0
    assert event.url.axes["matchId"] == 0
    assert event.url.axes == {"levelId": 1, "roomModeId": 9, "matchId": 0}


def test_level_switch_without_any_axes_reports_no_axes_at_all():
    kicked = _only(LEVEL_SWITCH_KICKED_LINE)
    assert isinstance(kicked, LevelSwitchEvent)
    assert kicked.url.target == "/Game/Project/Startup"
    assert kicked.url.axes == {}
    assert kicked.url.level_id is None
    assert kicked.url.match_id is None

    direct = _only(LEVEL_SWITCH_DIRECT_LINE)
    assert isinstance(direct, LevelSwitchEvent)
    assert direct.verb == "openLevelDirect"
    assert direct.url.map_name == "CampMap"
    # "options=option=GAA=" is opaque and is not decoded into anything.
    assert direct.url.axes == {}


def test_one_map_change_emits_four_level_switch_lines():
    # Measured: 44 [LevelSwitch] lines, 11 per verb, so a consumer that treats
    # each event as a distinct map change will overcount by four.
    verbs = [
        _only(text).verb
        for text in (
            LEVEL_SWITCH_OPEN_LINE,
            LEVEL_SWITCH_FOUR_AXIS_LINE,
            LEVEL_SWITCH_SINGLE_HOP_LINE,
            LEVEL_SWITCH_DIRECT_LINE,
        )
    ]
    assert verbs == [
        "openLevel",
        "openLevelWithTransition",
        "openLevelWithTransition",
        "openLevelDirect",
    ]


# --------------------------------------------------------------------------
# The engine-side map URL
# --------------------------------------------------------------------------


def test_browse_line_parses_target_and_axes_through_the_quotes():
    event = _only(BROWSE_THREE_AXIS_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.target == "/Game/Project/Maps/Prologue_New/Prologue_New"
    assert event.url.map_name == "Prologue_New"
    assert event.url.axes == {"levelId": 1, "roomModeId": 9, "matchId": 0}


def test_loadmap_line_parses_four_axes_despite_the_trailing_ampersand():
    assert LOADMAP_FOUR_AXIS_LINE.endswith("&")
    event = _only(LOADMAP_FOUR_AXIS_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.map_name == "Whitewoods_Day"
    assert event.url.axes == {
        "levelId": 117,
        "roomModeId": 0,
        "matchType": 1,
        "matchId": 11111,
    }


def test_options_string_line_has_no_target_and_a_trailing_period():
    # "?levelId=1&roomModeId=9&matchId=0." - the period must not be read into
    # matchId, and the absent map path must be absent, not an empty string.
    assert OPTIONS_STRING_LINE.endswith("0.")
    event = _only(OPTIONS_STRING_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.target is None
    assert event.url.map_name is None
    assert event.url.match_id == 0


def test_opaque_option_map_url_still_reports_the_map():
    event = _only(BROWSE_OPAQUE_OPTION_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.map_name == "CampMap"
    assert event.url.axes == {}


def test_a_bare_option_map_url_yields_a_target_and_no_axes():
    event = _only(BROWSE_KICKED_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.target == "/Game/Project/Startup"
    assert event.url.map_name == "Startup"
    assert event.url.axes == {}


def test_query_keys_outside_the_four_axes_are_never_lifted_into_a_field():
    # Why this matters: exactly ONE of the five real map-URL producers
    # appends the player's persona to the query string (KN_InitNewPlayer, 4
    # lines); the three engine producers write the literal default "Player",
    # which is not a persona. One producer is enough - an open-ended
    # key/value sweep would carry that persona into an event payload.
    # Extraction is an allowlist. The extra key here is synthetic.
    event = _only(SYNTHETIC_EXTRA_KEY_LINE)
    assert isinstance(event, MapUrlEvent)
    assert event.url.axes == {"levelId": 1, "roomModeId": 9, "matchId": 0}
    rendered = repr(
        (event.url.target, event.url.map_name, event.url.axes)
    )
    assert "someUnmeasuredKey" not in rendered
    assert "4242" not in rendered


def test_an_unrelated_key_equals_digits_line_is_not_a_map_url():
    # The teeth behind the allowlist. "id=<digits>" alone occurs on 1313 real
    # lines and "itemId=/reduceDurability=/durability=" on 45 more. If the
    # axis pattern were relaxed to any key, every one of those would become a
    # MapUrlEvent - the identical failure mode to MapTransitionEvent matching
    # 4408 UI widget lines.
    assert "id=120500" in ARROW_ID_LINE
    assert list(iter_events([ARROW_ID_LINE])) == []
    assert list(iter_events([DURABILITY_LINE])) == []
    # ... while a line that really does carry the axes still is one.
    assert isinstance(_only(OPTIONS_STRING_LINE), MapUrlEvent)


def test_level_switch_wins_over_map_url_when_a_line_is_both():
    # 8 lines carry both "[LevelSwitch]" and the axes. They are switches.
    event = _only(LEVEL_SWITCH_THREE_AXIS_LINE)
    assert isinstance(event, LevelSwitchEvent)
    assert not isinstance(event, MapUrlEvent)


# --------------------------------------------------------------------------
# "match id" in prose
# --------------------------------------------------------------------------


def test_match_id_prose_survives_the_doubled_space():
    assert "tag is  with" in MAP_ACTOR_TAG_LINE
    event = _only(MAP_ACTOR_TAG_LINE)
    assert isinstance(event, MatchIdEvent)
    assert event.match_id == 0
    assert event.level_id == 0


def test_match_id_without_a_level_id_omits_the_level_id():
    # This producer writes a match id and no level id at all.
    assert "level id" not in PLAYER_START_LINE
    event = _only(PLAYER_START_LINE)
    assert isinstance(event, MatchIdEvent)
    assert event.match_id == 0
    assert event.level_id is None


def test_non_zero_match_id_parses():
    event = _only(ENTER_STANDALONE_LINE)
    assert isinstance(event, MatchIdEvent)
    assert event.match_id == 11111
    assert event.level_id is None


def test_match_state_line_is_still_a_match_state_event():
    # "match state changed to" must keep beating "match id"; both start with
    # the word "match" and only ordering separates them.
    event = _only(MATCH_STATE_LINE)
    assert isinstance(event, MatchStateEvent)
    assert not isinstance(event, MatchIdEvent)


# --------------------------------------------------------------------------
# Sublevels
# --------------------------------------------------------------------------


def test_sublevel_unload_is_an_event():
    assert "levelid 1" in SUBLEVEL_UNLOAD_LINE  # lower-case d on this shape
    event = _only(SUBLEVEL_UNLOAD_LINE)
    assert isinstance(event, SubLevelEvent)
    assert event.action == "unload"
    assert event.sublevel == "0"
    assert event.level_id == 1
    assert event.map_name is None


def test_sublevel_load_names_the_map_and_the_sublevel():
    event = _only(SUBLEVEL_LOAD_LINE)
    assert isinstance(event, SubLevelEvent)
    assert event.action == "load"
    assert event.sublevel == "WhiteWoods_Level_Easy"
    assert event.map_name == "Whitewoods_Day"
    assert event.level_id is None


def test_the_sublevel_error_shape_is_not_a_transition():
    # Deliberate: "setUnloadSubLevelSet errors with missing mapResCfg levelId
    # 0!" reports a lookup failure. No sublevel is named and none was
    # unloaded, so emitting a SubLevelEvent would assert a transition that did
    # not happen. Paired with a positive assertion on the sibling shape so this
    # is not a bare negative.
    assert "levelId 0" in SUBLEVEL_ERROR_LINE  # upper-case D on this shape
    assert list(iter_events([SUBLEVEL_ERROR_LINE])) == []
    assert isinstance(_only(SUBLEVEL_UNLOAD_LINE), SubLevelEvent)


def test_a_huge_digit_run_never_raises_from_any_recogniser():
    # CPython 3.11+ caps int(str) at 4300 digits and raises ValueError past it.
    # parse_line and iter_events both promise never to raise on junk, and a
    # tailer hands this parser whatever bytes are on disk, so every integer
    # conversion has to be guarded. A field that cannot be read is ABSENT -
    # the event is dropped rather than invented with a wrong number.
    bomb = "9" * 5000
    stem = "[2026.08.09-13.20.15:385][980]"
    cases = [
        stem + "TS.Dungeon: OnRep_WeaponCfgId: " + bomb,
        stem + "TS.Dungeon: getMapActorFilterTagByURL with level id 1, match id " + bomb,
        stem + "TS.Dungeon: getMapActorFilterTagByURL with level id " + bomb + ", match id 1",
        stem + "LogNet: Browse: /Game/A?levelId=" + bomb + "&matchId=0",
        stem + "LogNet: Browse: /Game/A?matchId=" + bomb,
        stem + "TS.Dungeon: setClassGender inclassid  ==" + bomb + ", inGender ==1",
        stem + "TS.Avatar: server_refreshKnightFeature: class-10 holding-" + bomb,
        stem + "TS.Dungeon: setUnloadSubLevelSet with mapResCfg levelid " + bomb
        + " unloaded subLevel 0!",
        stem + "TS.Utils: [LevelSwitch] openLevelDirect target=/Game/A options=matchId=" + bomb,
    ]
    for text in cases:
        parsed = parse_line(text)
        assert parsed is None or isinstance(parsed, LogLine), text[:80]
        events = list(iter_events([text]))
        assert len(events) <= 1, text[:80]


def test_an_unreadable_required_id_drops_the_event_rather_than_guessing():
    bomb = "9" * 5000
    stem = "[2026.08.09-13.20.15:385][980]"
    # The defining field is unreadable, so there is no event at all.
    assert list(iter_events([stem + "TS.Dungeon: OnRep_WeaponCfgId: " + bomb])) == []
    assert list(iter_events([stem + "TS.Dungeon: xx match id " + bomb])) == []
    # An unreadable OPTIONAL axis is simply omitted, and the rest survives.
    event = _only(stem + "LogNet: Browse: /Game/A?levelId=" + bomb + "&matchId=7")
    assert isinstance(event, MapUrlEvent)
    assert event.url.level_id is None
    assert "levelId" not in event.url.axes
    assert event.url.match_id == 7


def test_a_huge_frame_number_never_raises():
    # The frame group is unbounded \d+ in the line header, so the bomb reaches
    # parse_line itself, before any recogniser runs.
    text = "[2026.08.09-13.20.15:385][" + "9" * 5000 + "]TS.Dungeon: OnRep_WeaponCfgId: 1"
    assert parse_line(text) is None
    assert list(iter_events([text])) == []


def _gift_hazard(path):
    """A LogUGiftAgent redemption line whose URL path is ``path``.

    A structural stand-in for the real thing. Neither the real values nor the
    real parameter names are committed: tests/test_no_pii.py has a detector for
    one of those names and flags it regardless of the value, which is correct,
    and a fake secret in a fixture is still noise for anyone grepping this repo
    for real ones. The real line's captured path would be 26 characters over
    five segments; the stand-in keeps the shape, not the bytes.

    Nothing in the query string is one of the four measured axes, so the axis
    branch cannot fire and the "/Game/" anchor is the only thing deciding
    whether these lines become events.
    """
    return (
        "[2026.08.09-14.55.01:001][ 12]LogUGiftAgent: Display: GetCDKeyGift, "
        "url == https://example.invalid" + path
        + "?aid=222222&credentialA=REDACTED&credentialB=REDACTED"
    )


#: The path shape that IS under /Game/ - the twin every hazard below is one
#: character (or one word) away from. Kept here so each test can show that its
#: hazard is rejected for the anchor and for no other reason.
_GIFT_TWIN_PATH = "/Game/redeem/api/use/111111"


def test_a_non_game_url_with_a_query_is_not_a_map_url():
    # The "/Game/" anchor in the map-URL pattern is the only thing keeping a
    # secrets-bearing line out of the event stream. The real log carries a
    # LogUGiftAgent redemption URL whose query string holds a redemption key
    # and an auth token; relaxing the anchor to a bare "/<path>?" - or adding
    # re.IGNORECASE - takes the match count from 36 lines to 37 and that line
    # is the extra one. Its path is lower-case "/game/", which is why case
    # alone is enough to discriminate this particular case.
    hazard = _gift_hazard("/game/redeem/api/use/111111")
    assert list(iter_events([hazard])) == []
    # ... while a genuine /Game/ map URL still is a map URL.
    assert isinstance(_only(BROWSE_OPAQUE_OPTION_LINE), MapUrlEvent)


def test_a_map_url_target_stops_at_the_query_so_a_secret_would_ride_in_the_raw():
    # Pins the MECHANISM the anchor guards, which the comment beside
    # _MAP_URL_TARGET_RE used to state incorrectly. If the anchor let one of
    # these lines through, no MapUrl FIELD would hold the key or the token -
    # target stops dead at the "?". The whole query string reaches a consumer
    # through the LogLine the event embeds instead. The hazard is therefore a
    # whole extra event on a secrets-bearing line, not a poisoned field.
    #
    # This also proves the hazard fixtures below are well formed: they parse,
    # they reach the map-URL branch, and their rejection is the anchor's doing
    # rather than a malformed header quietly returning None.
    event = _only(_gift_hazard(_GIFT_TWIN_PATH))
    assert isinstance(event, MapUrlEvent)
    assert event.url.target == _GIFT_TWIN_PATH
    assert "?" not in event.url.target
    assert "credentialA" not in event.url.target
    assert event.url.axes == {}
    # ... and the query string is right there in the embedded line.
    assert "credentialA=REDACTED" in event.line.raw
    assert "credentialA=REDACTED" in event.line.message


def test_a_path_starting_game_without_the_trailing_slash_is_not_a_map_url():
    # Discriminates the trailing slash. "/GameGift/..." starts with "/Game"
    # but not with "/Game/", so relaxing the anchor to a bare "/Game" admits
    # it. That weakening is INERT on the 2026-08-09 log - "/Game" and "/Game/"
    # both match the same 36 lines there - so this constructed line is the
    # only thing pinning it.
    assert list(iter_events([_gift_hazard("/GameGift/redeem/api/use/111111")])) == []
    # The same URL one inserted slash later IS under /Game/ and does parse, so
    # the rejection above is attributable to the slash and to nothing else.
    twin = _only(_gift_hazard("/Game/Gift/redeem/api/use/111111"))
    assert isinstance(twin, MapUrlEvent)
    assert twin.url.target == "/Game/Gift/redeem/api/use/111111"
    assert twin.url.map_name == "111111"


def test_a_path_starting_with_g_but_not_game_is_not_a_map_url():
    # Discriminates the word, not just its first letter. Truncating the anchor
    # to "/G" is likewise inert on the 2026-08-09 log (still 36 lines), and
    # "/Gift/..." is the shape that notices.
    assert list(iter_events([_gift_hazard("/Gift/redeem/api/use/111111")])) == []
    # Swap that one word for "Game" and the very same line parses.
    twin = _only(_gift_hazard(_GIFT_TWIN_PATH))
    assert isinstance(twin, MapUrlEvent)
    assert twin.url.target == _GIFT_TWIN_PATH


def test_a_hyphen_in_the_path_is_outside_the_measured_character_class():
    # The character class is an allowlist of the characters observed in real
    # map paths, and no measured map path carries a "-". Widening it to
    # [A-Za-z0-9_/.-] is inert on the 2026-08-09 log (still 36 lines), so only
    # a constructed pair can tell the two apart.
    #
    # Caveat, written down rather than left in someone's head: this case
    # asserts that a hyphen has never been MEASURED in a map path, not that
    # the game can never write one. If a hyphenated map path is ever observed,
    # widen the class and retire this test - do not weaken it to stay green.
    assert list(iter_events([_gift_hazard("/Game/redeem-api/use/111111")])) == []
    # One character apart: an underscore is inside the measured class, so the
    # otherwise identical URL parses and yields the whole path.
    twin = _only(_gift_hazard("/Game/redeem_api/use/111111"))
    assert isinstance(twin, MapUrlEvent)
    assert twin.url.target == "/Game/redeem_api/use/111111"


def test_match_state_beats_match_id_when_a_line_carries_both():
    # No real line carries both tokens, so branch order is inert on today's
    # log and a reorder passes the rest of this file. This constructed line is
    # what actually pins the ordering.
    both = (
        "[2026.08.09-13.20.16:590][980]TS.Camp: Display: [CampControllerColorComp] "
        "match state changed to NotMatch, match id 11111"
    )
    event = _only(both)
    assert isinstance(event, MatchStateEvent)
    assert event.state == "NotMatch"


def test_a_key_ending_in_an_axis_name_is_not_read_as_that_axis():
    # The lookbehind on the axis pattern is inert on today's log. These are
    # the shapes that make it matter.
    stem = (
        "[2026.08.09-14.03.58:998][150]LogNet: Browse: "
        "/Game/Project/Maps/Prologue_New/Prologue_New?"
    )
    # A decoy with NO real matchId anywhere: nothing may invent one.
    alone = _only(stem + "levelId=1&submatchId=4242")
    assert isinstance(alone, MapUrlEvent)
    assert alone.url.match_id is None
    assert alone.url.axes == {"levelId": 1}

    # A decoy AFTER the real axis. Order matters here: with the decoy first,
    # a dict write from the real axis would overwrite the bogus one and hide
    # the bug entirely - which is exactly how an earlier version of this test
    # let the mutant survive.
    after = _only(stem + "matchId=7&submatchId=4242")
    assert after.url.match_id == 7
    assert after.url.axes == {"matchId": 7}


def test_a_level_switch_target_that_is_not_a_path_is_not_a_switch():
    # The leading slash on the target is inert on today's log: all 44 real
    # lines write a real path. The game's TS layer does write "undefined"
    # elsewhere, so this is the shape the anchor exists for. A switch whose
    # destination is not a path is not reported as a switch to somewhere.
    text = (
        "[2026.08.09-14.07.25:527][ 75]TS.Utils: [LevelSwitch] "
        "openLevelWithTransition begin target=undefined options=kicked"
    )
    assert list(iter_events([text])) == []
    # ... and a real path still switches.
    assert isinstance(_only(LEVEL_SWITCH_KICKED_LINE), LevelSwitchEvent)


def test_unload_is_not_read_as_a_load_by_substring():
    # "loadSubLevel" is a substring of the game's own "setUnloadSubLevelSet".
    assert "loadSubLevel" in SUBLEVEL_SUBSTRING_TRAP_LINE
    assert "setUnloadSubLevel" in SUBLEVEL_SUBSTRING_TRAP_LINE
    assert list(iter_events([SUBLEVEL_SUBSTRING_TRAP_LINE])) == []
    # ... and the genuine load shape still reads as a load.
    assert _only(SUBLEVEL_LOAD_LINE).action == "load"


# --------------------------------------------------------------------------
# Contract: the new recognisers must not break parse_line's promises
# --------------------------------------------------------------------------


def test_new_families_survive_a_half_written_trailing_line():
    # A tailer reading a live append will hand the parser a truncated line.
    # The contract is: never raise, return LogLine-or-None, and emit at most
    # one event per line. It is NOT that a truncated line yields no event -
    # a line cut after "matchId=111" really does read 111, which is why the
    # tailer must only hand over complete lines.
    for text in TAIL_SAMPLE_LINES:
        for cut in range(len(text) + 1):
            fragment = text[:cut]
            parsed = parse_line(fragment)
            assert parsed is None or isinstance(parsed, LogLine), fragment
            events = list(iter_events([fragment]))
            assert len(events) <= 1, fragment
            for event in events:
                assert isinstance(event.line, LogLine), fragment
        # and the complete line is still recognised afterwards
        assert len(list(iter_events([text]))) <= 1


def test_iter_events_over_the_tail_fixture_yields_the_expected_kinds():
    kinds = [type(e).__name__ for e in iter_events(TAIL_SAMPLE_LINES)]
    assert kinds == [
        "WeaponConfigEvent",
        "WeaponConfigEvent",
        "WeaponConfigEvent",
        "WeaponConfigEvent",
        "LevelSwitchEvent",
        "LevelSwitchEvent",
        "LevelSwitchEvent",
        "LevelSwitchEvent",
        "LevelSwitchEvent",
        "LevelSwitchEvent",
        "MapUrlEvent",
        "MapUrlEvent",
        "MapUrlEvent",
        "MapUrlEvent",
        "MapUrlEvent",
        "MatchIdEvent",
        "MatchIdEvent",
        "MatchIdEvent",
        "SubLevelEvent",
        # SUBLEVEL_ERROR_LINE deliberately yields nothing.
        "SubLevelEvent",
    ]


def test_the_original_fixture_is_unchanged_by_the_new_recognisers():
    # Regression guard: none of the new branches may fire on the lines the
    # shipped recognisers already covered, and the two non-events must stay
    # non-events.
    kinds = [type(event).__name__ for event in iter_events(SAMPLE_LOG.splitlines())]
    assert kinds == [
        "ClassSelectionEvent",
        "WeaponHoldingEvent",
        "MatchStateEvent",
        "MapTransitionEvent",
    ]
    assert list(iter_events([ARMOR_PARTS_LINE])) == []
    assert list(iter_events([OLD_CLASS_GENDER_LINE])) == []
