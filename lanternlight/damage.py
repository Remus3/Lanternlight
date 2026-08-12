"""Read the per-hit damage series the game writes into its transient save.

`DamageCollectonDataSet` - the game's own spelling, missing "i" included - is
the only local surface carrying per-hit damage numbers, and nobody has published
any for this game. It lives in `StandaloneSlot_<roleId>.sav`, which exists only
while a match is running.

Three measured properties of that field shape everything here, and each one
breaks a reader that assumes otherwise.

**It is a rolling window, not a cumulative log.** Summed `totalDamage` across
generations falls as well as rises - 74.66, 251.20, 137.52, 89.09, 89.09,
227.94 - so entries age out. One snapshot is never a run total, and a hit that
has rotated out has not stopped having happened. :class:`DamageSeries`
accumulates across generations and deduplicates on
``(monsterGuid, timeStamp, damageValue)``.

The sampling ceiling that follows is worth designing against rather than
fighting: 424 window readings over a 20-minute run yielded **21** distinct
hits, because the window holds roughly two monster entries at a time. Polling
faster does not widen a window that small.

**Absence is a fact, not a zero.** The first captured generation - 2,190 bytes,
written at match start before any combat - does not carry the property at all.
:func:`damage_set_from_save` returns ``None`` there and ``()`` for a payload
that is present and empty, because "no combat has happened yet" and "combat
happened and dealt nothing" are different facts and conflating them is how a
build engine starts lying.

**`timeStamp` is not a Unix epoch.** See :func:`as_local_naive`. This is the
sharpest trap in the module and the one a caller otherwise gets silently wrong.

What this module deliberately does NOT do
-----------------------------------------

It computes no coefficient, no damage-per-second and no per-ability attribution.
`nameId` is 0 and `Key` is empty on all 424 readings ever observed in a save, so
the save carries no attribution at all; the log carries it, on a different
surface. And no coefficient may be published from a single run, because one run
cannot separate a coefficient from a lucky repeat however precise the float.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DAMAGE_PROPERTY",
    "DamageHit",
    "DamageRecord",
    "DamageSeries",
    "MONSTER",
    "MalformedDamageSet",
    "ObservedHit",
    "PLAYER",
    "UnknownClockOffset",
    "as_local_naive",
    "damage_set_from_save",
    "parse_damage_set",
    "source_of",
    "to_utc",
]

#: The property name, spelled as the game spells it - "Collecton", not
#: "Collection". Restating it correctly would simply fail to find the field.
DAMAGE_PROPERTY = "DamageCollectonDataSet"

#: `sourceType` 0. Measured from the log's own emission: `monsterId` is null and
#: the `Key` is a player ability, so the PLAYER dealt this damage.
PLAYER = "player"

#: `sourceType` 1. `monsterId` is populated and the `Key` is `MonsterDamage`, so
#: the MONSTER dealt it - damage the operator took.
MONSTER = "monster"

#: Only 0 and 1 have ever been observed. Anything else reads as unknown rather
#: than being folded into whichever of the two looks closer.
_SOURCE_TYPES = {0: PLAYER, 1: MONSTER}


class MalformedDamageSet(ValueError):
    """The payload is not the shape the game writes, so it is refused."""


class UnknownClockOffset(ValueError):
    """A true UTC instant was asked for without saying what the offset was."""


@dataclass(frozen=True)
class DamageHit:
    """One entry of a record's ``damageChildList``.

    ``name_id`` is ``None`` when the field is absent and ``0`` when the game
    wrote a zero. Both have been seen and they are not the same fact: 0 may mean
    "basic attack" or may mean "unset", and that is **unmeasured**.
    """

    damage_value: float
    time_stamp: float
    name_id: int | None = None
    key: str = ""
    child_death_causer: bool = False


@dataclass(frozen=True)
class DamageRecord:
    """One top-level entry - all damage from one source against one target."""

    monster_guid: str
    hits: tuple[DamageHit, ...]
    source_type: int | None = None
    monster_id: int | None = None
    total_damage: float | None = None
    death_causer: bool = False

    @property
    def source(self) -> str | None:
        """:data:`PLAYER`, :data:`MONSTER`, or None when unobserved."""
        return source_of(self.source_type)


@dataclass(frozen=True)
class ObservedHit:
    """One deduplicated hit, carrying the record context it was seen in."""

    monster_guid: str
    time_stamp: float
    damage_value: float
    monster_id: int | None = None
    source_type: int | None = None
    name_id: int | None = None
    key: str = ""
    death_causer: bool = False
    child_death_causer: bool = False

    @property
    def identity(self) -> tuple[str, float, float]:
        """The deduplication key.

        Value alone is wrong: damage here is deterministic, and three values
        repeat exactly across the observed run, so collapsing on value would
        erase real hits. Timestamp alone is wrong for the mirrored reason - two
        sources can land in the same millisecond.
        """
        return (self.monster_guid, self.time_stamp, self.damage_value)

    @property
    def source(self) -> str | None:
        return source_of(self.source_type)


def source_of(source_type: int | None) -> str | None:
    """Return who dealt the damage, or None when that is not established.

    Only ``0`` and ``1`` have been observed, each corroborated by the log
    emitting the same structure with `Key` populated. Any other value returns
    ``None`` rather than a guess - a wrong direction flag would invert what a
    number means, and this project would rather have no answer.
    """
    if source_type is None:
        return None
    return _SOURCE_TYPES.get(source_type)


def as_local_naive(time_stamp: float) -> dt.datetime:
    """Return ``time_stamp`` as the NAIVE LOCAL wall clock the game meant.

    **`timeStamp` looks exactly like a Unix epoch and is not one.** Measured
    first-party on two independent surfaces:

    The capture files' own mtimes put one run at 22:27:00 to 22:46:54 UTC
    (17:27 to 17:46 local, machine at UTC-5). Reading the hit timestamps as a
    Unix epoch renders them 17:28:10 to 17:45:11 "UTC" - five hours *before*
    that run started, which is impossible, and numerically equal to the run's
    LOCAL wall clock.

    Confirmed against the log, which timestamps in real UTC and emits the same
    payload: across five readings at three separate times of day, the log line's
    UTC minus the timestamp-read-as-epoch is 18009 to 18015 seconds - 5.0025 to
    5.0041 hours, exactly the operator's offset plus a few seconds of
    event-to-emission lag.

    So the game writes local wall-clock time as though it were UTC. What comes
    back here is therefore **naive**: it carries no timezone because the save
    does not know one. Use :func:`to_utc` when you can say what the offset was.
    """
    return dt.datetime.fromtimestamp(time_stamp, dt.UTC).replace(tzinfo=None)


def to_utc(time_stamp: float, utc_offset: dt.timedelta | dt.tzinfo | None) -> dt.datetime:
    """Return the true UTC instant, given the offset that was in force.

    The offset is a property of the machine that played - it is not in the save,
    and it changes with daylight saving - so it must be supplied. Guessing it
    would silently shift every hit by hours, which is exactly the failure this
    module exists to prevent, so a missing offset raises instead.
    """
    if utc_offset is None:
        raise UnknownClockOffset(
            "the save's timeStamp encodes LOCAL wall clock as if it were UTC, so "
            "a true instant needs the UTC offset that was in force when the run "
            "was played. It is not recoverable from the save and it changes with "
            "daylight saving. Pass the offset, or use as_local_naive() and keep "
            "the reading naive."
        )
    naive = as_local_naive(time_stamp)
    if isinstance(utc_offset, dt.tzinfo):
        offset = utc_offset.utcoffset(naive)
        if offset is None:
            raise UnknownClockOffset(f"{utc_offset!r} yields no offset for {naive}")
    else:
        offset = utc_offset
    return (naive - offset).replace(tzinfo=dt.UTC)


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise MalformedDamageSet(
            f"{where}: no {key!r}. Refused rather than defaulted - a defaulted "
            f"timestamp joins to the wrong moment, and both fields are part of "
            f"the deduplication key, so a default also merges distinct hits."
        )
    return mapping[key]


def _hit(raw: Any, index: int) -> DamageHit:
    if not isinstance(raw, dict):
        raise MalformedDamageSet(f"damageChildList[{index}] is {type(raw).__name__}, not an object")
    where = f"damageChildList[{index}]"
    return DamageHit(
        damage_value=float(_require(raw, "damageValue", where)),
        time_stamp=float(_require(raw, "timeStamp", where)),
        name_id=raw.get("nameId"),
        key=raw.get("Key", "") or "",
        child_death_causer=bool(raw.get("bChildDeathCauser", False)),
    )


def parse_damage_set(payload: str) -> tuple[DamageRecord, ...]:
    """Parse the JSON string the game stores in :data:`DAMAGE_PROPERTY`.

    An empty or whitespace-only string is absence, not corruption, and reads as
    an empty tuple. Anything else that is not the game's shape raises - a reader
    that absorbs a shape it does not understand is how a wrong number reaches a
    build engine wearing a confident face.
    """
    if not payload or not payload.strip():
        return ()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MalformedDamageSet(f"{DAMAGE_PROPERTY} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise MalformedDamageSet(
            f"{DAMAGE_PROPERTY} is a JSON {type(data).__name__}, expected an array of records"
        )

    records = []
    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise MalformedDamageSet(f"record {index} is {type(raw).__name__}, not an object")
        children = raw.get("damageChildList") or []
        if not isinstance(children, list):
            raise MalformedDamageSet(f"record {index}: damageChildList is not an array")
        records.append(
            DamageRecord(
                monster_guid=str(raw.get("monsterGuid", "")),
                hits=tuple(_hit(child, position) for position, child in enumerate(children)),
                source_type=raw.get("sourceType"),
                monster_id=raw.get("monsterId"),
                total_damage=raw.get("totalDamage"),
                death_causer=bool(raw.get("bDeathCauser", False)),
            )
        )
    return tuple(records)


def damage_set_from_save(save: Any) -> tuple[DamageRecord, ...] | None:
    """Return the records in ``save``, or None when the property is ABSENT.

    ``None`` and ``()`` are different answers and the distinction is the point.
    ``None`` means the game never wrote the field - measured on the first
    generation of a run, before any combat. ``()`` means it wrote an empty one.
    A caller that treats both as falsy has thrown away a real observation.
    """
    payload = save.properties.get(DAMAGE_PROPERTY)
    if payload is None:
        return None
    if not isinstance(payload, str):
        raise MalformedDamageSet(
            f"{DAMAGE_PROPERTY} decoded as {type(payload).__name__}, expected a string"
        )
    return parse_damage_set(payload)


class DamageSeries:
    """Accumulate distinct hits across many generations of the rolling window.

    Deduplication is by :attr:`ObservedHit.identity`. First reading of a hit
    wins; later repeats are counted in :attr:`readings` and otherwise ignored,
    because the window re-reports an unchanged hit on every write.
    """

    def __init__(self) -> None:
        self._hits: dict[tuple[str, float, float], ObservedHit] = {}
        self.readings = 0
        self.generations = 0
        self.generations_with_payload = 0

    def add_records(self, records: tuple[DamageRecord, ...] | None) -> int:
        """Fold one generation in. Returns how many hits were NEW."""
        self.generations += 1
        if records is None:
            return 0
        self.generations_with_payload += 1
        added = 0
        for record in records:
            for hit in record.hits:
                self.readings += 1
                observed = ObservedHit(
                    monster_guid=record.monster_guid,
                    time_stamp=hit.time_stamp,
                    damage_value=hit.damage_value,
                    monster_id=record.monster_id,
                    source_type=record.source_type,
                    name_id=hit.name_id,
                    key=hit.key,
                    death_causer=record.death_causer,
                    child_death_causer=hit.child_death_causer,
                )
                if observed.identity not in self._hits:
                    self._hits[observed.identity] = observed
                    added += 1
        return added

    def add_payload(self, payload: str) -> int:
        """Fold in one generation given its raw JSON string."""
        return self.add_records(parse_damage_set(payload))

    def add_save(self, save: Any) -> int:
        """Fold in one generation given a parsed save."""
        return self.add_records(damage_set_from_save(save))

    @property
    def hits(self) -> tuple[ObservedHit, ...]:
        """Every distinct hit, oldest first."""
        return tuple(sorted(self._hits.values(), key=lambda hit: hit.time_stamp))

    @property
    def span_seconds(self) -> float | None:
        """Seconds between the first and last hit, or None when there are none.

        None rather than 0.0 for an empty series: no observation is not a
        measurement of zero duration.
        """
        if not self._hits:
            return None
        stamps = [hit.time_stamp for hit in self._hits.values()]
        return max(stamps) - min(stamps)

    @property
    def total_damage(self) -> float:
        return sum(hit.damage_value for hit in self._hits.values())

    @property
    def monster_ids(self) -> tuple[int, ...]:
        """Distinct monster ids, sorted. A null id is not an id."""
        ids = {h.monster_id for h in self._hits.values() if h.monster_id is not None}
        return tuple(sorted(ids))

    @property
    def instance_count(self) -> int:
        """Distinct monster INSTANCES, counted by guid.

        Not the same as :attr:`monster_ids` - one run saw 9 instances across 8
        ids, and one damage value repeated on two different instances of the
        same type, which is the strongest evidence the numbers are computed
        rather than rolled.
        """
        return len({hit.monster_guid for hit in self._hits.values()})

    def __len__(self) -> int:
        return len(self._hits)
