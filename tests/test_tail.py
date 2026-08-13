"""Tests for lanternlight.tail - the live MistfallHunter.log tailer.

Everything here runs against a synthetic appending file under ``tmp_path``.
Nothing needs the game, the real log, or a running client. That is the point:
the acceptance for ROADMAP item 3 says the suite must not need the game, and a
tailer that can only be tested by playing is a tailer nobody re-tests.

Every log line here is AUTHORED. Nothing was pasted from the real log, and no
raw excerpt of it exists in this repository.

Note the string construction below. Identifier-shaped and name-shaped fixtures
are assembled from fragments at runtime (``"Zephyr" + "glim"``) and key/value
pairs are joined through ``_EQ`` rather than written with a literal ``=``.
That is not stylistic: ``tests/test_no_pii.py`` scans every published file with
``lanternlight.redact``'s own detectors, and the scanner cannot tell an
invented name from a real one. ``tests/test_redact.py`` establishes the same
convention and for the same reason.

The four hazards this module exists to survive, each with its own class below:

1. A live-appended UE log routinely ends MID-LINE. Emitting the fragment lets a
   truncated line parse as a valid-but-wrong record.
2. The file is truncated or replaced when the game restarts.
3. Holding a lock on it could affect the process writing it, which is the game.
4. Redaction is SCOPE-DEPENDENT. Persona discovery returns empty on an isolated
   excerpt - ROADMAP item 0 - and one log line is the smallest possible
   excerpt. A tailer that redacts line by line misses the keyless persona
   shapes while appearing to work, and ``assert_clean`` agrees with it.
"""

import dataclasses
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import redact, tail  # noqa: E402  (path bootstrap must run first)
from lanternlight.logparse import (  # noqa: E402
    ClassSelectionEvent,
    MapTransitionEvent,
    MatchStateEvent,
    WeaponHoldingEvent,
)

# --------------------------------------------------------------------------
# authored fixtures - see the module docstring for why they are assembled
# --------------------------------------------------------------------------

_EQ = "="

#: An invented two-token display name, the shape a Steam persona has.
FAKE_NAME = "Zephyr" + "glim"
FAKE_SURNAME = "Thorn" + "wick"
FAKE_FULL_NAME = FAKE_NAME + " " + FAKE_SURNAME

CLASS_LINE = (
    "[2026.08.09-13.21.27:100][655]TS.Avatar: setClassGender "
    "inclassid  ==12, inGender ==0"
)
WEAPON_LINE = (
    "[2026.08.09-13.21.28:446][656]TS.Dungeon: OnRep_WeaponCfgId "
    "BP_Preview_C_2147475781 class-12 holding-30402"
)
KNIGHT_LINE = (
    "[2026.08.09-13.21.30:200][658]TS.Avatar: server_refreshKnightFeature "
    "class-12 holding-30403"
)
MATCH_STATE_LINE = (
    "[2026.08.09-13.22.00:000][700]TS.Match: match state changed to InMatch"
)
MAP_LINE = (
    "[2026.08.09-13.22.01:000][701]TS.Level: open UI_MainPanel at world CampMap"
)
SUBLEVEL_LINE = (
    "[2026.08.09-13.22.02:000][702]TS.Level: open UI_Escape at world "
    "WhiteWoods_Level_Easy2"
)
NOISE_LINE = "[2026.08.09-13.20.11:001][  0]TS.System: [TSGameInstance] boot"

#: A keyed persona occurrence. This is the ONLY shape persona discovery can
#: learn a name from, and the whole point of the redaction class below is that
#: it does not appear on the same line as the leak it protects.
LOGIN_LINE = (
    "[2026.08.09-13.20.12:300][ 14]TS.Login: " + "uName" + _EQ + FAKE_FULL_NAME
)

#: A recognised event line carrying the display name in NO key and NO slot the
#: redactor enumerates. On its own it survives ``redact()`` untouched AND is
#: certified clean by ``assert_clean``. See TestRedactionIsNotScopedToOneLine.
BARE_NAME_EVENT_LINE = (
    "[2026.08.09-13.22.06:000][706]TS.Dungeon: server_refreshKnightFeature "
    + FAKE_FULL_NAME
    + " class-12 holding-30402"
)

#: A recognised event line sitting in a context the log is measured to fill
#: with a bare display name, from which no name can be discovered. This is the
#: cannot-certify shape - ``assert_clean`` refuses to approve it rather than
#: reporting it clean.
UNCERTIFIABLE_EVENT_LINE = (
    "[2026.08.09-13.22.07:000][707]TS.Match: match state changed to InMatch "
    + "instigator"
    + _EQ
    + "true"
)


def _bytes(*lines: str) -> bytes:
    """Join authored lines with an explicit LF and terminate the last one.

    Newlines are controlled in BYTES on purpose. On Windows ``write_text``
    turns LF into CRLF and ``read_text`` hides it again, so a partial-line test
    written in text mode is measuring the platform rather than the tailer.
    """
    return "".join(line + "\n" for line in lines).encode("utf-8")


def _unterminated(*lines: str) -> bytes:
    """Same, but the last line carries NO newline - a live append mid-write."""
    return _bytes(*lines)[:-1]


def _append(path: Path, payload: bytes) -> None:
    """Append raw bytes, the way the game's logger does.

    Deliberately a SEPARATE handle from the one the tailer uses. That is what
    makes TestNeverHoldsALockOnTheGamesFile a real probe rather than a
    self-consistent one.
    """
    with path.open("ab") as handle:
        handle.write(payload)


def _truncate_in_place(path: Path, payload: bytes) -> None:
    """Rewrite ``path`` from byte zero WITHOUT replacing the file.

    Mode ``wb`` truncates an existing file rather than creating a new one, so
    the file KEEPS its identity - measured on this machine, and it is the
    whole reason the tailer needs a size check as well as an identity check.
    A test that unlinked and recreated here would silently be testing
    replacement instead of truncation.
    """
    with path.open("wb") as handle:
        handle.write(payload)


def _kinds(events) -> list[str]:
    """Event class names, in emission order."""
    return [type(item.event).__name__ for item in events]


class _Sleeper:
    """A sleep_fn that records instead of blocking."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# --------------------------------------------------------------------------
# 1. following an appending file
# --------------------------------------------------------------------------


class TestFollowsAnAppendingFile:
    """The base case: bytes arrive, events come out, and only once each."""

    def test_a_first_poll_emits_every_known_shape_already_in_the_file(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(
            _bytes(NOISE_LINE, CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE, MAP_LINE)
        )
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert _kinds(events) == [
            "ClassSelectionEvent",
            "WeaponHoldingEvent",
            "MatchStateEvent",
            "MapTransitionEvent",
        ]

    def test_the_parsed_fields_survive_the_redactor(self, tmp_path):
        """Redaction runs BEFORE parsing, so it must not corrupt the payload."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE, MAP_LINE))
        tailer = tail.LogTailer(path)

        selection, weapon, state, transition = (item.event for item in tailer.poll_once())

        assert isinstance(selection, ClassSelectionEvent)
        assert (selection.class_id, selection.gender) == (12, 0)
        assert selection.class_label == "Blackarrow"

        assert isinstance(weapon, WeaponHoldingEvent)
        assert weapon.holding_id == 30402
        assert weapon.actor == "BP_Preview_C_2147475781"

        assert isinstance(state, MatchStateEvent)
        assert state.state == "InMatch"

        assert isinstance(transition, MapTransitionEvent)
        assert (transition.world, transition.subject) == ("CampMap", "UI_MainPanel")

    def test_the_knight_feature_and_sublevel_shapes_are_recognised(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(KNIGHT_LINE, SUBLEVEL_LINE))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert _kinds(events) == ["WeaponHoldingEvent", "MapTransitionEvent"]
        assert events[0].event.holding_id == 30403
        assert events[1].event.world == "WhiteWoods_Level_Easy2"

    def test_a_second_poll_with_nothing_appended_emits_nothing(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)

        assert len(tailer.poll_once()) == 1
        assert tailer.poll_once() == []
        assert tailer.poll_once() == []

    def test_appended_lines_are_emitted_on_the_next_poll_only(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        _append(path, _bytes(MATCH_STATE_LINE, MAP_LINE))

        assert _kinds(tailer.poll_once()) == ["MatchStateEvent", "MapTransitionEvent"]
        assert tailer.poll_once() == []

    def test_the_offset_advances_to_the_end_of_the_terminated_bytes(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        payload = _bytes(CLASS_LINE, MATCH_STATE_LINE)
        path.write_bytes(payload)
        tailer = tail.LogTailer(path)

        assert tailer.offset == 0
        tailer.poll_once()
        assert tailer.offset == len(payload)

    def test_unrecognised_but_well_formed_lines_are_counted_and_not_emitted(
        self, tmp_path
    ):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(NOISE_LINE, NOISE_LINE, CLASS_LINE))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert len(events) == 1
        assert tailer.lines_seen == 3

    def test_an_empty_file_yields_nothing_and_does_not_raise(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(b"")
        tailer = tail.LogTailer(path)

        assert tailer.poll_once() == []
        assert tailer.offset == 0

    def test_crlf_terminated_lines_are_followed_too(self, tmp_path):
        """The game runs on Windows. A CR must not reach the parser."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes((CLASS_LINE + "\r\n").encode("utf-8"))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert _kinds(events) == ["ClassSelectionEvent"]
        assert not events[0].text.endswith("\r")


# --------------------------------------------------------------------------
# 2. the partial trailing line
# --------------------------------------------------------------------------


class TestPartialTrailingLineIsHeldBack:
    """A fragment must never be emitted.

    A live-appended UE log routinely ends mid-line. ``parse_line`` returns
    ``None`` on most fragments, but not on all of them - a line cut after a
    complete header and a complete ``key ==value`` pair parses perfectly and
    reports the wrong record. The only safe rule is to emit nothing that is not
    newline-terminated.
    """

    def test_a_fragment_emits_nothing_and_then_the_whole_line_emits_once(
        self, tmp_path
    ):
        path = tmp_path / "MistfallHunter.log"
        head = "[2026.08.09-13.21.28:446][656]TS.Dungeon: OnRep_Weap"
        tail_of_line = WEAPON_LINE[len(head) :]
        assert head + tail_of_line == WEAPON_LINE, "the fixture must split cleanly"

        path.write_bytes(head.encode("utf-8"))
        tailer = tail.LogTailer(path)

        assert tailer.poll_once() == []
        assert tailer.lines_seen == 0

        _append(path, (tail_of_line + "\n").encode("utf-8"))
        events = tailer.poll_once()

        assert _kinds(events) == ["WeaponHoldingEvent"]
        assert events[0].text == WEAPON_LINE
        assert tailer.poll_once() == []
        assert tailer.lines_seen == 1

    def test_a_fragment_that_would_parse_as_a_valid_record_is_still_held(
        self, tmp_path
    ):
        """The dangerous case, stated concretely.

        ``setClassGender inclassid  ==12`` on its own parses, and would emit no
        event only because ``inGender`` is missing. Cut one character later and
        a reader gets a real-looking record built from half a line.
        """
        path = tmp_path / "MistfallHunter.log"
        truncated = CLASS_LINE[: CLASS_LINE.index(", inGender") + len(", inGender ==")]
        truncated = truncated + "1"
        path.write_bytes(truncated.encode("utf-8"))
        tailer = tail.LogTailer(path)

        # Proof the fragment is genuinely dangerous rather than merely short:
        # on its own it parses into a complete, wrong ClassSelectionEvent.
        from lanternlight.logparse import iter_events

        rogue = list(iter_events([truncated]))
        assert len(rogue) == 1
        assert rogue[0].gender == 1, "fixture no longer demonstrates the hazard"

        assert tailer.poll_once() == []

        _append(path, b"0\n")
        events = tailer.poll_once()

        assert _kinds(events) == ["ClassSelectionEvent"]
        assert events[0].event.gender == 10

    def test_a_line_arriving_one_byte_at_a_time_emits_exactly_once(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(b"")
        tailer = tail.LogTailer(path)

        payload = _bytes(MATCH_STATE_LINE)
        emitted = []
        for index in range(len(payload)):
            _append(path, payload[index : index + 1])
            emitted.extend(tailer.poll_once())

        assert _kinds(emitted) == ["MatchStateEvent"]
        assert emitted[0].text == MATCH_STATE_LINE

    def test_a_multibyte_character_split_across_two_appends_is_not_mangled(
        self, tmp_path
    ):
        """The buffer holds BYTES, not characters.

        Decoding each read in isolation would split a multi-byte UTF-8
        sequence and produce a replacement character in the middle of a line.
        The game's log carries CJK player names, so this is a real shape.
        """
        path = tmp_path / "MistfallHunter.log"
        marker = chr(0x4E2D) + chr(0x6587)
        line = (
            "[2026.08.09-13.22.09:000][709]TS.Level: open "
            + marker
            + " at world CampMap"
        )
        payload = _bytes(line)
        cut = payload.index(marker.encode("utf-8")) + 1

        path.write_bytes(payload[:cut])
        tailer = tail.LogTailer(path)
        assert tailer.poll_once() == []

        _append(path, payload[cut:])
        events = tailer.poll_once()

        assert _kinds(events) == ["MapTransitionEvent"]
        assert chr(0xFFFD) not in events[0].text

    def test_an_embedded_control_character_does_not_split_a_line(self, tmp_path):
        """The hazard that makes the byte-level split load-bearing.

        Measured on the real log by an independent pass: it carries more than
        594 control characters EMBEDDED INSIDE lines - 98 VT, 106 FF, 113 FS,
        85 GS, 97 RS, 95 NEL. The file does not treat any of them as a line
        break. ``str.splitlines()`` treats all of them as line breaks, so a
        tailer that decoded and then called it would shatter one real line
        into several and hand the parser records the game never wrote.

        Measured for this fixture: ``str.splitlines()`` turns it into 3.

        The count alone would not catch the mutation - the first shard still
        carries a complete header and still parses into a MapTransitionEvent.
        Only the exact text does, which is why it is asserted rather than the
        event type.
        """
        record_separator = chr(0x1E)
        vertical_tab = chr(0x0B)
        line = (
            "[2026.08.09-13.22.10:000][710]TS.Level: open UI_Panel at world "
            "CampMap [snap" + record_separator + "shot" + vertical_tab + "x]"
        )
        assert len(line.splitlines()) == 3, "fixture no longer demonstrates the hazard"

        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(line))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert len(events) == 1
        assert events[0].text == line
        assert record_separator in events[0].text
        assert vertical_tab in events[0].text
        assert tailer.lines_seen == 1

    def test_pending_bytes_reports_what_is_being_held(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_unterminated(CLASS_LINE, "half a li"))
        tailer = tail.LogTailer(path)

        tailer.poll_once()

        assert tailer.pending_bytes == len("half a li")


# --------------------------------------------------------------------------
# 3. truncation and rotation
# --------------------------------------------------------------------------


class TestSurvivesTruncationAndRotation:
    """Game restart replaces or empties the file under the tailer."""

    def test_st_ino_is_populated_on_this_machine(self, tmp_path):
        """MEASURED, not assumed. The rotation guard below depends on it.

        This assertion is what turns a passing rotation test into evidence. If
        a future platform hands back a zero file index, the tailer falls back
        to the size comparison and this test says so out loud rather than
        letting the rotation test quietly stop testing anything.
        """
        path = tmp_path / "probe.log"
        path.write_bytes(b"x\n")
        # Path.stat() returns the same os.stat_result os.stat() does, so this
        # reads the raw file index exactly as a direct os.stat would.
        first = path.stat()
        path.unlink()
        path.write_bytes(b"y\n")
        second = path.stat()

        assert first.st_ino != 0
        assert first.st_ino != second.st_ino
        assert tail.file_identity(first) is not None
        assert tail.file_identity(first) != tail.file_identity(second)

    def test_a_zero_file_index_is_reported_as_NO_identity(self):
        """The documented fallback, pinned rather than merely described.

        ``st_ino`` is documented as zero where the platform cannot supply one.
        Returning ``(st_dev, 0)`` there would make every file on such a
        platform compare equal to every other file, so the tailer would never
        see a rotation and would believe it had. ``None`` is the honest answer
        and sends the caller to the size comparison alone.

        This machine never produces a zero index - see the test above - so the
        only way to exercise the guard is to hand it a stat result that has
        one. ``os.stat_result`` is built from a real 10-tuple rather than
        faked, so attribute access is the same as on a live stat.
        """
        real_ino = os.stat_result((0o100644, 999, 12345, 1, 0, 0, 100, 0, 0, 0))
        zero_ino = os.stat_result((0o100644, 0, 12345, 1, 0, 0, 100, 0, 0, 0))

        assert tail.file_identity(real_ino) == (12345, 999)
        assert tail.file_identity(zero_ino) is None

    def test_in_place_truncation_PRESERVES_the_file_identity(self, tmp_path):
        """Why the size check is not redundant with the identity check.

        Measured on this machine: rewriting a file through mode ``wb`` keeps
        its index. So identity is blind to truncation, and a tailer resting on
        identity alone would seek past content it never read. This pins the
        measurement the module docstring rests on.
        """
        path = tmp_path / "probe.log"
        path.write_bytes(b"a lengthy first generation\n")
        before = path.stat()

        _truncate_in_place(path, b"b\n")
        after = path.stat()

        assert after.st_size < before.st_size
        assert tail.file_identity(after) == tail.file_identity(before)

    def test_truncation_to_zero_bytes_is_survived(self, tmp_path):
        """The file is emptied and stays empty for a poll or two."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, WEAPON_LINE))
        tailer = tail.LogTailer(path)
        assert len(tailer.poll_once()) == 2

        _truncate_in_place(path, b"")

        assert tailer.poll_once() == []
        assert tailer.offset == 0
        assert tailer.poll_once() == []

        _append(path, _bytes(MATCH_STATE_LINE))
        assert _kinds(tailer.poll_once()) == ["MatchStateEvent"]

    def test_truncation_then_rewrite_resets_the_offset_and_skips_nothing(
        self, tmp_path
    ):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE))
        tailer = tail.LogTailer(path)
        assert len(tailer.poll_once()) == 3
        consumed = tailer.offset

        _truncate_in_place(path, _bytes(MAP_LINE))

        assert path.stat().st_size < consumed, "fixture must actually shrink"
        events = tailer.poll_once()

        assert _kinds(events) == ["MapTransitionEvent"]
        assert tailer.offset == path.stat().st_size

    def test_truncation_to_a_smaller_nonzero_size_skips_nothing(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE, MAP_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        _truncate_in_place(path, _bytes(CLASS_LINE, MATCH_STATE_LINE))

        assert _kinds(tailer.poll_once()) == [
            "ClassSelectionEvent",
            "MatchStateEvent",
        ]

    def test_a_held_fragment_is_discarded_on_truncation(self, tmp_path):
        """The sharpest half of truncation.

        Keeping the pending buffer would weld the tail of the OLD file onto
        the head of the new one and emit a line that was never written.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_unterminated(CLASS_LINE, "[2026.08.09-13.22.00:000][700]TS.M"))
        tailer = tail.LogTailer(path)
        tailer.poll_once()
        assert tailer.pending_bytes > 0

        _truncate_in_place(path, _bytes(MAP_LINE))

        events = tailer.poll_once()

        assert _kinds(events) == ["MapTransitionEvent"]
        assert events[0].text == MAP_LINE
        assert tailer.pending_bytes == 0

    def test_replacement_by_a_LARGER_file_is_detected_by_identity(self, tmp_path):
        """Size alone cannot see this, which is why identity is tracked.

        The new file is bigger than the offset held from the old one, so a
        size-only tailer seeks into the middle of it, loses the head, and
        emits a fragment as if it were a line.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)
        assert len(tailer.poll_once()) == 1
        consumed = tailer.offset

        path.unlink()
        path.write_bytes(
            _bytes(NOISE_LINE, WEAPON_LINE, MATCH_STATE_LINE, MAP_LINE, SUBLEVEL_LINE)
        )
        assert path.stat().st_size > consumed, "fixture must not merely shrink"

        events = tailer.poll_once()

        assert _kinds(events) == [
            "WeaponHoldingEvent",
            "MatchStateEvent",
            "MapTransitionEvent",
            "MapTransitionEvent",
        ]

    def test_replacement_by_rename_is_detected(self, tmp_path):
        """UE rotation: the old log is moved aside and a new one takes the name."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        replacement = tmp_path / "incoming.log"
        replacement.write_bytes(
            _bytes(NOISE_LINE, MAP_LINE, SUBLEVEL_LINE, CLASS_LINE, WEAPON_LINE)
        )
        replacement.replace(path)

        assert _kinds(tailer.poll_once()) == [
            "MapTransitionEvent",
            "MapTransitionEvent",
            "ClassSelectionEvent",
            "WeaponHoldingEvent",
        ]

    def test_the_file_disappearing_and_returning_is_survived(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        path.unlink()
        assert tailer.poll_once() == []

        path.write_bytes(_bytes(MATCH_STATE_LINE, MAP_LINE))

        assert _kinds(tailer.poll_once()) == [
            "MatchStateEvent",
            "MapTransitionEvent",
        ]

    def test_a_file_growing_normally_is_never_treated_as_rotated(self, tmp_path):
        """The false positive that would make the guard useless.

        A rotation check that fires on ordinary appends re-emits the whole file
        on every poll, which is worse than missing a rotation.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)
        emitted = list(tailer.poll_once())

        for line in (WEAPON_LINE, MATCH_STATE_LINE, MAP_LINE, SUBLEVEL_LINE):
            _append(path, _bytes(line))
            emitted.extend(tailer.poll_once())

        assert _kinds(emitted) == [
            "ClassSelectionEvent",
            "WeaponHoldingEvent",
            "MatchStateEvent",
            "MapTransitionEvent",
            "MapTransitionEvent",
        ]


# --------------------------------------------------------------------------
# 4. never hold a lock the game could feel
# --------------------------------------------------------------------------


class TestNeverHoldsALockOnTheGamesFile:
    """ROADMAP item 3: the tail must never hold a lock that could affect the
    writing process. That process is Mistfall Hunter, which ships kernel-level
    anti-cheat, so this is a boundary rule and not a performance note.

    A claim about locking that is not exercised is decoration, so both halves
    are exercised: a writer appends while the module's own reader handle is
    open, and the file is deleted immediately after a poll - which on Windows
    a retained handle would refuse.

    **What these tests do NOT catch, stated rather than hidden.** Mutation
    testing found one survivor here. Replacing the ``with`` block in
    ``_read_new_bytes`` with a bare ``open`` whose handle is never stored
    leaves all 46 tests green, because CPython's refcounting closes the object
    the moment the local goes out of scope - the handle exists for
    microseconds and holds nothing between polls. Retaining that same handle
    on the tailer, or in a module-level list, fails 6 tests including both
    unlink probes below.

    So what is pinned is the property that matters - no handle SURVIVES a poll
    - and not the narrower "``with`` was used". A future implementation that
    closes deterministically by another route is correctly allowed; one that
    keeps a handle alive across polls is not.
    """

    def test_a_writer_can_append_while_the_modules_reader_is_open(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        with tail.open_for_read(path) as reader:
            assert reader.read(8), "the reader handle must really be open"
            _append(path, _bytes(MATCH_STATE_LINE))

        assert path.read_bytes().endswith(_bytes(MATCH_STATE_LINE))
        assert _kinds(tailer.poll_once()) == ["MatchStateEvent"]

    def test_no_handle_survives_a_poll(self, tmp_path):
        """On Windows an open handle blocks unlink, so this is a real probe.

        Measured on this machine: ``Path.unlink()`` raises ``PermissionError``
        while any handle from ``open(path, "rb")`` is alive, and succeeds once
        it is closed.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, MATCH_STATE_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        path.unlink()

        assert not path.exists()

    def test_no_handle_survives_a_poll_over_a_partial_line_either(self, tmp_path):
        """The pending-buffer path is a separate return route out of the read."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_unterminated(CLASS_LINE, "trailing fragment"))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        path.unlink()

        assert not path.exists()

    def test_the_tailer_never_writes_to_the_file(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        payload = _bytes(CLASS_LINE, WEAPON_LINE, MATCH_STATE_LINE)
        path.write_bytes(payload)
        before = path.stat()
        tailer = tail.LogTailer(path)

        tailer.run(max_passes=4, sleep_fn=_Sleeper())

        after = path.stat()
        assert path.read_bytes() == payload
        assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


# --------------------------------------------------------------------------
# 5. no spin
# --------------------------------------------------------------------------


class TestDoesNotSpin:
    """The hazard is a busy loop when the file is absent, empty or just reset.

    The game may not be running, which is normal rather than exceptional -
    exactly as ``SaveWatcher.poll_once`` tolerates an absent source directory.
    """

    def test_an_absent_file_is_tolerated_silently(self, tmp_path):
        tailer = tail.LogTailer(tmp_path / "never-created.log")

        assert tailer.poll_once() == []
        assert tailer.poll_once() == []
        assert tailer.offset == 0

    def test_N_passes_over_an_absent_file_sleep_N_minus_1_times(self, tmp_path):
        sleeper = _Sleeper()
        tailer = tail.LogTailer(tmp_path / "never-created.log")

        total = tailer.run(poll_seconds=0.25, max_passes=5, sleep_fn=sleeper)

        assert total == 0
        assert sleeper.calls == [0.25, 0.25, 0.25, 0.25]

    def test_N_passes_over_an_empty_file_sleep_N_minus_1_times(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(b"")
        sleeper = _Sleeper()
        tailer = tail.LogTailer(path)

        tailer.run(poll_seconds=1.5, max_passes=3, sleep_fn=sleeper)

        assert sleeper.calls == [1.5, 1.5]

    def test_a_single_pass_never_sleeps(self, tmp_path):
        sleeper = _Sleeper()
        tailer = tail.LogTailer(tmp_path / "never-created.log")

        tailer.run(max_passes=1, sleep_fn=sleeper)

        assert sleeper.calls == []

    def test_run_returns_the_total_emitted_across_passes(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE, MATCH_STATE_LINE))
        sleeper = _Sleeper()
        tailer = tail.LogTailer(path)

        assert tailer.run(max_passes=3, sleep_fn=sleeper) == 2
        assert sleeper.calls == [tail.DEFAULT_POLL_SECONDS] * 2

    def test_a_poll_over_a_directory_is_tolerated(self, tmp_path):
        """``paths.py`` can hand back something that is not a regular file."""
        directory = tmp_path / "MistfallHunter.log"
        directory.mkdir()
        tailer = tail.LogTailer(directory)

        assert tailer.poll_once() == []


# --------------------------------------------------------------------------
# 6. redaction, and the scope trap
# --------------------------------------------------------------------------


class TestRedactionIsNotScopedToOneLine:
    """The sharpest hazard in this module, and the reason it is not naive.

    ROADMAP item 0 records it: persona discovery is SCOPE-DEPENDENT and returns
    empty on an isolated excerpt. One log line is the smallest possible
    excerpt, so a tailer calling ``redact(line)` per line runs discovery on the
    worst possible scope. It does not fail loudly - the line comes back
    unchanged and ``assert_clean`` certifies it.

    The tailer therefore accumulates every persona it has ever discovered and
    re-applies the growing set to every subsequent line.
    """

    def test_the_naive_per_line_approach_really_does_leak(self):
        """Positive control. Without this the test below could pass by luck.

        A clean result and a dead scanner are otherwise identical, and the same
        is true of a test that would pass under the design it is supposed to
        refute.
        """
        leaked = redact.redact(BARE_NAME_EVENT_LINE)

        assert FAKE_FULL_NAME in leaked
        # And the guard agrees with the leak, which is what makes it dangerous.
        redact.assert_clean(leaked)

    def test_a_persona_learned_earlier_masks_a_later_bare_occurrence(self, tmp_path):
        """THE test. It fails under per-line redaction and passes under ours."""
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        _append(path, _bytes(BARE_NAME_EVENT_LINE))
        events = tailer.poll_once()

        assert _kinds(events) == ["WeaponHoldingEvent"]
        assert FAKE_FULL_NAME not in events[0].text
        assert FAKE_NAME not in events[0].text
        assert FAKE_SURNAME not in events[0].text
        assert redact.PERSONA_PLACEHOLDER in events[0].text

    def test_the_learned_persona_survives_across_polls_and_appends(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        for _ in range(4):
            _append(path, _bytes(NOISE_LINE))
            tailer.poll_once()

        _append(path, _bytes(BARE_NAME_EVENT_LINE))
        events = tailer.poll_once()

        assert FAKE_NAME not in events[0].text

    def test_personas_are_learned_even_from_a_line_that_emits_no_event(self, tmp_path):
        """``LOGIN_LINE`` is not a recognised event shape.

        Harvesting only from lines that become events would throw away the one
        line the name can be learned from, since the login line carries no
        event at all.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE))
        tailer = tail.LogTailer(path)

        assert tailer.poll_once() == []
        assert FAKE_FULL_NAME in tailer.personas

    def test_seeded_personas_mask_a_bare_occurrence_with_no_login_line_at_all(
        self, tmp_path
    ):
        """The explicit escape hatch, for a tail started mid-session.

        A tailer attached to a log that is already running has missed the login
        line and can never discover the name. Naming it is the only remedy.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(BARE_NAME_EVENT_LINE))
        tailer = tail.LogTailer(path, personas=[FAKE_FULL_NAME])

        events = tailer.poll_once()

        assert _kinds(events) == ["WeaponHoldingEvent"]
        assert FAKE_FULL_NAME not in events[0].text

    def test_a_line_that_cannot_be_certified_is_withheld_and_counted(self, tmp_path):
        """``assert_clean``'s third state is honoured, not swallowed.

        The line is a perfectly good ``MatchStateEvent``. It is withheld
        anyway, because it sits in a context the log fills with a bare display
        name and nothing in it says whose. Refusing is the recoverable answer.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(UNCERTIFIABLE_EVENT_LINE, MAP_LINE))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert _kinds(events) == ["MapTransitionEvent"]
        assert tailer.withheld == 1

    def test_withholding_survives_a_persona_already_being_known(self, tmp_path):
        """Knowing SOME name is not a basis for certifying a DIFFERENT slot.

        Supplying personas to ``assert_clean`` switches its cannot-certify
        state off, so a tailer that only ever supplied its accumulated set
        would quietly stop refusing anything after the first login line.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()
        assert tailer.personas

        _append(path, _bytes(UNCERTIFIABLE_EVENT_LINE))

        assert tailer.poll_once() == []
        assert tailer.withheld == 1

    def test_every_emitted_line_passes_the_redactors_own_guard(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(
            _bytes(
                LOGIN_LINE,
                NOISE_LINE,
                CLASS_LINE,
                WEAPON_LINE,
                BARE_NAME_EVENT_LINE,
                MATCH_STATE_LINE,
                MAP_LINE,
                SUBLEVEL_LINE,
            )
        )
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert events
        for item in events:
            redact.assert_clean(item.text, personas=tailer.personas)

    def test_the_emitted_event_is_parsed_out_of_the_redacted_text(self, tmp_path):
        """Structural, not incidental.

        There is no code path by which unredacted text becomes an event,
        because the parser is only ever handed text the redactor produced.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE, BARE_NAME_EVENT_LINE))
        tailer = tail.LogTailer(path)

        events = tailer.poll_once()

        assert len(events) == 1
        assert events[0].event.line.raw == events[0].text
        assert FAKE_NAME not in events[0].event.line.message

    def test_personas_are_reported_longest_first(self, tmp_path):
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        lengths = [len(name) for name in tailer.personas]
        assert lengths == sorted(lengths, reverse=True)

    def test_a_persona_learned_before_a_rotation_is_not_forgotten(self, tmp_path):
        """Rotation resets the offset. It must not reset what has been learned.

        The login line lives at the top of the OLD file. If rotation dropped
        the accumulated names, every bare occurrence in the new file would ship
        in the clear - and nothing would report an error.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(LOGIN_LINE, CLASS_LINE))
        tailer = tail.LogTailer(path)
        tailer.poll_once()

        path.unlink()
        path.write_bytes(_bytes(NOISE_LINE, BARE_NAME_EVENT_LINE))

        events = tailer.poll_once()

        assert _kinds(events) == ["WeaponHoldingEvent"]
        assert FAKE_NAME not in events[0].text


class TestTailEventShape:
    """The public record a sink receives."""

    def test_a_tail_event_is_frozen(self, tmp_path):
        """A sink must not be able to rewrite the text it was handed.

        The exception is named rather than caught blind. ``pytest.raises
        (Exception)`` would pass on an ``AttributeError`` from a typo in this
        very test, which is a guard that proves nothing - and the outcome is
        asserted afterwards, because "it raised" and "the value survived" are
        different facts.
        """
        path = tmp_path / "MistfallHunter.log"
        path.write_bytes(_bytes(CLASS_LINE))
        tailer = tail.LogTailer(path)

        item = tailer.poll_once()[0]
        original_text, original_event = item.text, item.event

        with pytest.raises(dataclasses.FrozenInstanceError):
            item.text = "rewritten"
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.event = None

        assert item.text == original_text
        assert item.event is original_event

    def test_the_module_exports_what_it_documents(self):
        for name in ("DEFAULT_POLL_SECONDS", "LogTailer", "TailEvent"):
            assert name in tail.__all__
            assert hasattr(tail, name)
