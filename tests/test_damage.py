"""The damage series reader, and the clock trap sitting underneath it.

`DamageCollectonDataSet` - the game's own spelling, missing "i" included - is
the only local surface carrying per-hit damage numbers. Two of its properties
drive almost every test here, and both were measured rather than assumed:

**It is a rolling window, not a cumulative log.** Summed `totalDamage` across
generations falls as well as rises, so entries age out. A reader that treats one
snapshot as a run total is wrong, and a reader that forgets a hit once it
rotates out is worse.

**Its `timeStamp` is NOT a Unix epoch**, however exactly it looks like one. See
`TestTheClockTrap` - this is the sharpest thing in the module and the one a
caller will otherwise get silently wrong.
"""

import base64
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import damage, gvas  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "gvas" / "standalone_slot.gvas.b64"


def _fixture_save():
    return gvas.parse(base64.b64decode(FIXTURE.read_text(encoding="utf-8")))


def _record(**over):
    """One entry in the game's own shape, so tests author what the game writes."""
    body = {
        "sourceType": 1,
        "totalDamage": 10.0,
        "monsterGuid": "GUID-A",
        "monsterId": 1005,
        "bDeathCauser": False,
        "damageChildList": [
            {
                "Key": "",
                "nameId": 0,
                "damageValue": 10.0,
                "timeStamp": 1786297000.0,
                "bChildDeathCauser": False,
            }
        ],
    }
    body.update(over)
    return body


def _payload(*records):
    return json.dumps(list(records))


class TestAbsentIsNotEmpty:
    """The whole measurement doctrine, applied to one property.

    The first captured generation - 2,190 bytes, written at match start before
    any combat - does not carry the property AT ALL. That is a different fact
    from a run in which nothing dealt damage, and conflating them is how a
    build engine starts lying.
    """

    def test_an_absent_property_reads_as_none(self):
        save = gvas.GvasSave(properties={}, header=None, epilogue=b"")
        assert damage.damage_set_from_save(save) is None

    def test_a_present_but_empty_payload_reads_as_an_empty_tuple(self):
        save = gvas.GvasSave(
            properties={damage.DAMAGE_PROPERTY: "[]"}, header=None, epilogue=b""
        )
        assert damage.damage_set_from_save(save) == ()

    def test_none_and_empty_are_not_the_same_answer(self):
        # Stated as its own test because `not x` is true of both, and that is
        # exactly the line a careless caller writes.
        absent = damage.damage_set_from_save(
            gvas.GvasSave(properties={}, header=None, epilogue=b"")
        )
        empty = damage.damage_set_from_save(
            gvas.GvasSave(properties={damage.DAMAGE_PROPERTY: "[]"}, header=None, epilogue=b"")
        )
        assert absent is None
        assert empty == ()
        assert absent != empty
        assert not absent and not empty  # both falsy - which is the trap


class TestTheCommittedFixtureParses:
    """Characterisation against real game bytes, not authored ones.

    Everything else in this file authors its own JSON, which proves the reader
    handles the shapes we believe in. Only this class proves those shapes are
    the ones the game actually wrote.
    """

    def test_the_fixture_carries_exactly_one_record_and_one_hit(self):
        records = damage.damage_set_from_save(_fixture_save())
        assert records is not None
        assert len(records) == 1
        assert len(records[0].hits) == 1

    def test_the_recorded_values_are_exact(self):
        record = damage.damage_set_from_save(_fixture_save())[0]
        hit = record.hits[0]
        assert record.source_type == 1
        assert record.monster_id == 2017
        assert record.total_damage == 118.453857421875
        assert record.death_causer is False
        assert hit.damage_value == 118.453857421875
        assert hit.time_stamp == 1786297499.5909998
        assert hit.name_id == 0
        assert hit.key == ""
        assert hit.child_death_causer is False

    def test_the_damage_value_survives_as_float32_exactly(self):
        # 118.453857421875 is exactly representable; a reader that round-trips
        # through a lower precision would shift it and no assertion above
        # would necessarily notice.
        hit = damage.damage_set_from_save(_fixture_save())[0].hits[0]
        assert hit.damage_value.hex() == 118.453857421875.hex()


class TestUnmeasuredStaysDistinguishableFromZero:
    def test_a_missing_name_id_is_none_not_zero(self):
        payload = _payload(_record(damageChildList=[{"damageValue": 1.0, "timeStamp": 1.0}]))
        hit = damage.parse_damage_set(payload)[0].hits[0]
        assert hit.name_id is None

    def test_a_name_id_of_zero_is_zero_not_none(self):
        payload = _payload(
            _record(damageChildList=[{"damageValue": 1.0, "timeStamp": 1.0, "nameId": 0}])
        )
        hit = damage.parse_damage_set(payload)[0].hits[0]
        assert hit.name_id == 0
        assert hit.name_id is not None

    def test_a_null_monster_id_is_none_not_zero(self):
        # sourceType 0 carries monsterId null - the PLAYER is the source. A
        # reader that coerces that to 0 invents a monster with id 0.
        payload = _payload(_record(sourceType=0, monsterId=None))
        assert damage.parse_damage_set(payload)[0].monster_id is None


class TestTheRollingWindow:
    """The window rotates. Forgetting that loses most of a run."""

    def test_one_hit_seen_in_many_generations_counts_once(self):
        series = damage.DamageSeries()
        for _ in range(5):
            series.add_payload(_payload(_record()))
        assert len(series.hits) == 1
        assert series.readings == 5

    def test_a_hit_that_rotates_out_is_retained(self):
        series = damage.DamageSeries()
        series.add_payload(_payload(_record()))
        series.add_payload("[]")  # the window dropped it
        assert len(series.hits) == 1

    def test_hits_are_distinguished_by_guid_timestamp_and_value(self):
        series = damage.DamageSeries()
        series.add_payload(_payload(_record()))
        series.add_payload(_payload(_record(monsterGuid="GUID-B")))
        series.add_payload(
            _payload(
                _record(
                    damageChildList=[
                        {
                            "damageValue": 10.0,
                            "timeStamp": 1786297001.0,
                            "nameId": 0,
                            "Key": "",
                            "bChildDeathCauser": False,
                        }
                    ]
                )
            )
        )
        assert len(series.hits) == 3

    def test_the_same_value_at_a_different_time_is_a_separate_hit(self):
        # Damage is deterministic here - three values repeat exactly - so
        # collapsing on value alone would erase real hits.
        series = damage.DamageSeries()
        for stamp in (1786297000.0, 1786297001.5, 1786297003.0):
            series.add_payload(
                _payload(
                    _record(
                        damageChildList=[
                            {"damageValue": 9.7454833984375, "timeStamp": stamp}
                        ]
                    )
                )
            )
        assert len(series.hits) == 3

    def test_hits_come_back_in_timestamp_order(self):
        series = damage.DamageSeries()
        for stamp in (1786297003.0, 1786297000.0, 1786297001.5):
            series.add_payload(
                _payload(_record(damageChildList=[{"damageValue": 1.0, "timeStamp": stamp}]))
            )
        assert [h.time_stamp for h in series.hits] == [
            1786297000.0,
            1786297001.5,
            1786297003.0,
        ]

    def test_an_absent_payload_counts_as_a_generation_but_not_a_payload(self):
        series = damage.DamageSeries()
        series.add_save(gvas.GvasSave(properties={}, header=None, epilogue=b""))
        series.add_payload(_payload(_record()))
        assert series.generations == 2
        assert series.generations_with_payload == 1


class TestDirectionIsReadNotGuessed:
    """sourceType 0 and 1 are measured. Nothing else is."""

    def test_zero_is_the_player_as_source(self):
        assert damage.source_of(0) == damage.PLAYER

    def test_one_is_the_monster_as_source(self):
        assert damage.source_of(1) == damage.MONSTER

    def test_an_unobserved_source_type_is_none_rather_than_a_guess(self):
        for value in (2, 3, 7, -1):
            assert damage.source_of(value) is None, value

    def test_a_missing_source_type_is_none(self):
        assert damage.source_of(None) is None


class TestTheClockTrap:
    """`timeStamp` looks exactly like a Unix epoch and is not one.

    MEASURED, first-party, on two independent surfaces:

    The capture files' own mtimes put the run at 22:27:00 to 22:46:54 UTC
    (17:27 to 17:46 local, machine at UTC-5). Reading the hit timestamps as a
    Unix epoch renders them 17:28:10 to 17:45:11 "UTC" - five hours before the
    run started, which is impossible, and numerically equal to the LOCAL wall
    clock of the run.

    Confirmed against the log, which timestamps in real UTC and emits the same
    payload: across five readings at three separate times of day, the log line's
    UTC minus the timestamp-read-as-epoch is 18009 to 18015 seconds - 5.0025 to
    5.0041 hours. Exactly the operator's UTC offset, plus a few seconds of
    event-to-emission lag.

    So the game writes local wall-clock time as though it were UTC. The offset
    is a property of the machine that played, is not recoverable from the save,
    and changes with DST. The reader therefore hands back a NAIVE local
    datetime and refuses to invent a UTC instant without being told the offset.
    """

    STAMP = 1786297499.5909998

    def test_the_reading_is_naive_local_wall_clock(self):
        when = damage.as_local_naive(self.STAMP)
        assert when.tzinfo is None
        assert (when.year, when.month, when.day) == (2026, 8, 9)
        assert (when.hour, when.minute, when.second) == (17, 44, 59)

    def test_it_is_not_silently_treated_as_utc(self):
        # The bug this whole class exists to prevent, stated as an assertion.
        naive = damage.as_local_naive(self.STAMP)
        wrong = dt.datetime.fromtimestamp(self.STAMP, dt.UTC)
        assert naive != wrong.replace(tzinfo=None) or naive.tzinfo is None
        assert naive.replace(tzinfo=dt.UTC) != damage.to_utc(
            self.STAMP, dt.timedelta(hours=-5)
        )

    def test_a_supplied_offset_yields_the_true_instant(self):
        when = damage.to_utc(self.STAMP, dt.timedelta(hours=-5))
        assert when.tzinfo is dt.UTC
        assert (when.hour, when.minute, when.second) == (22, 44, 59)

    def test_the_true_instant_lands_inside_the_measured_run_window(self):
        # The run, from the capture files' own mtimes: 22:27:00 to 22:46:54 UTC.
        when = damage.to_utc(self.STAMP, dt.timedelta(hours=-5))
        start = dt.datetime(2026, 8, 9, 22, 27, 0, tzinfo=dt.UTC)
        end = dt.datetime(2026, 8, 9, 22, 46, 54, tzinfo=dt.UTC)
        assert start <= when <= end

    def test_reading_it_as_an_epoch_falls_OUTSIDE_that_window(self):
        # The non-vacuity of the test above: prove the naive reading is wrong,
        # otherwise "it lands in the window" proves nothing.
        wrong = dt.datetime.fromtimestamp(self.STAMP, dt.UTC)
        start = dt.datetime(2026, 8, 9, 22, 27, 0, tzinfo=dt.UTC)
        assert wrong < start

    def test_it_refuses_to_invent_an_offset(self):
        with pytest.raises(damage.UnknownClockOffset):
            damage.to_utc(self.STAMP, None)

    def test_an_offset_may_be_given_as_a_timezone(self):
        when = damage.to_utc(self.STAMP, dt.timezone(dt.timedelta(hours=-5)))
        assert (when.hour, when.minute, when.second) == (22, 44, 59)


class TestSeriesSummary:
    def _series(self):
        series = damage.DamageSeries()
        series.add_payload(
            _payload(
                _record(
                    monsterId=1005,
                    damageChildList=[{"damageValue": 10.0, "timeStamp": 1786297000.0}],
                ),
                _record(
                    monsterGuid="GUID-B",
                    monsterId=2003,
                    damageChildList=[{"damageValue": 5.5, "timeStamp": 1786297010.0}],
                ),
            )
        )
        return series

    def test_span_is_measured_between_first_and_last_hit(self):
        assert self._series().span_seconds == pytest.approx(10.0)

    def test_span_of_a_single_hit_is_zero_and_of_no_hits_is_none(self):
        one = damage.DamageSeries()
        one.add_payload(_payload(_record()))
        assert one.span_seconds == 0.0
        assert damage.DamageSeries().span_seconds is None

    def test_total_sums_the_deduplicated_hits(self):
        assert self._series().total_damage == pytest.approx(15.5)

    def test_monster_ids_are_sorted_and_unique(self):
        assert self._series().monster_ids == (1005, 2003)

    def test_instances_are_counted_by_guid(self):
        assert self._series().instance_count == 2

    def test_a_null_monster_id_is_not_reported_as_an_id(self):
        series = damage.DamageSeries()
        series.add_payload(_payload(_record(sourceType=0, monsterId=None)))
        assert series.monster_ids == ()


class TestMalformedInputIsRefusedNotAbsorbed:
    def test_a_non_list_payload_raises(self):
        with pytest.raises(damage.MalformedDamageSet):
            damage.parse_damage_set('{"sourceType": 1}')

    def test_invalid_json_raises(self):
        with pytest.raises(damage.MalformedDamageSet):
            damage.parse_damage_set("not json at all")

    def test_a_hit_with_no_timestamp_raises_rather_than_defaulting(self):
        # A defaulted timestamp would silently join to the wrong moment, and
        # the dedup key includes it - so a default also merges distinct hits.
        with pytest.raises(damage.MalformedDamageSet):
            damage.parse_damage_set(_payload(_record(damageChildList=[{"damageValue": 1.0}])))

    def test_a_hit_with_no_damage_value_raises(self):
        with pytest.raises(damage.MalformedDamageSet):
            damage.parse_damage_set(_payload(_record(damageChildList=[{"timeStamp": 1.0}])))

    def test_an_empty_payload_string_is_not_a_parse_error(self):
        # The game writes an empty string on some generations. That is absence,
        # not corruption.
        assert damage.parse_damage_set("") == ()
