"""Tests for lanternlight.logparse against verbatim real log lines.

The SAMPLE_LINES below are copied byte-for-byte from a real
MistfallHunter.log captured on 2026-08-09, including the double space in
``inclassid  ==10`` and the trailing space at end of line. They are stored as
one string per line rather than one triple-quoted block precisely so the
trailing spaces live inside the quotes and cannot be eaten by an editor, a
formatter or a trailing-whitespace lint rule.

None of these lines carry an identifier - they were chosen from the parts of
the log that contain only actor names and content ids.
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
    LogLine,
    MapTransitionEvent,
    MatchStateEvent,
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
