"""Row-scoped provenance for the numbers this project publishes - `OPS-28`.

WHY THIS EXISTS, and what it is NOT.

This project's documents are well sourced. `docs/OBSERVED_IDS.md` names the
method for every class id and warns that all of them were read on a build that
no longer exists. `docs/AFFIXES.md` heads its damage ladder `Affix Level ladder,
stated`, names the frame it was read from, quotes the tooltip, and records its
own withdrawn misreading of the row beside it. **Neither document is
under-sourced, and calling `AFFIXES.md` under-sourced is a specific withdrawn
misreading that `OPS-28` records precisely so it is not repeated.**

The defect is that none of that provenance TRAVELS. An outside consumer does not
read a document, it lifts a table. Slice the seven-row ranged-damage ladder out
of `docs/AFFIXES.md` the way a scraper would and you get percentages that cannot
say which build they were read on, by what method, on what date, or whether the
2026-08-19T08:06:36Z patch invalidated them. Downstream they are
indistinguishable from a fandom-wiki number, and a stranger is CORRECT to treat
them that way. Worse, they launder: the number gets reposted, a third site cites
the repost, and this project's own measurement re-enters the ecosystem as an
uncited claim it then has to compete with.

So this module generates a row-scoped emission in which every single row carries
its own build, method, date and reconfirmation status.

**THE MARKDOWN IS AUTHORITATIVE.** This emission is derived, never a second
source of truth. `tests/test_provenance.py` reads both the markdown and the
emitted file and fails when a value differs, so a drift is a red build rather
than a fork. Edit the table, regenerate; never hand-edit the emission.

Two representation rules from [ADR-005](../docs/adr/ADR-005-omit-rather-than-guess.md)
are enforced rather than documented:

* **A missing measurement is ABSENT.** Its key is simply not in ``values``.
  There is no ``null``, no ``0`` and no ``-1`` standing in for it, and
  :func:`measured_value` raises :class:`Unmeasured` rather than returning a
  default.
* **`unmeasured` stays distinguishable from `measured zero`.** The ladder's
  `Effective Range` column reads `-` at levels 1 to 4 and `+12%` from level 5,
  and the document states that the bonus "appears at Lv. 5". That dash is a
  STATED zero, so ``effective_range_pct`` is present and equal to ``0``. The
  tooltip also says Impact diminishes past the effective range and states no
  magnitude for it anywhere, so ``impact_pct`` is unmeasured and is simply not
  there. Each record keeps its literal ``source_row``, so that interpretation is
  auditable against the table rather than taken on trust.

**Two build schemes, deliberately not merged.** `docs/OBSERVED_IDS.md` anchors
on the Steam depot ``buildid``; `docs/AFFIXES.md` measures that the literal
string ``buildid`` occurs ZERO times in any log and that the client's own
``Version`` line is the identifier to anchor on. Collapsing those two into one
``buildid`` string would be exactly the confident-wrong this project's
measurement doctrine forbids, so ``build`` names its ``scheme`` and the
staleness query compares only within a scheme. A record whose scheme has no
current-build entry lands in an ``undetermined`` bucket and is never silently
counted as current.

**Prose is matched on a whitespace-collapsed copy.** The documents are
hard-wrapped near 80 columns, so a sentence this module needs routinely spans
two lines and a line-oriented pattern would miss it and fail closed - a false
clean bill this repository has already been burned by twice.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "AFFIXES_DOCUMENT",
    "CLASS_ID_HEADER",
    "DATA_PATH",
    "FORBIDDEN_PLACEHOLDERS",
    "LADDER_HEADER",
    "OBSERVED_IDS_DOCUMENT",
    "REQUIRED_BUILD_FIELDS",
    "REQUIRED_DATASET_FIELDS",
    "REQUIRED_RECORD_FIELDS",
    "REQUIRED_SOURCE_FIELDS",
    "SCHEMA_VERSION",
    "ProvenanceError",
    "Unmeasured",
    "build_dataset",
    "by_record_id",
    "is_measured",
    "is_measured_zero",
    "load",
    "measured_value",
    "parse_affix_ladder_records",
    "parse_class_id_records",
    "rebuild",
    "records_on_current_builds",
    "records_on_superseded_builds",
    "records_on_undetermined_builds",
    "records_predating_latest_patch",
    "validate_dataset",
    "validate_record",
    "write_dataset",
]

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Repo-relative paths, because a record has to name its source in a form a
#: consumer on another machine can follow.
OBSERVED_IDS_DOCUMENT = "docs/OBSERVED_IDS.md"
AFFIXES_DOCUMENT = "docs/AFFIXES.md"

#: Where the emission lives. Under ``docs/`` on purpose: it is published data,
#: not build output.
DATA_PATH = REPO_ROOT / "docs" / "data" / "provenance.json"

SCHEMA_VERSION = 1

#: Full header rows. A FIRST header cell is not unique in either document -
#: three tables in `OBSERVED_IDS.md` open with ``classId`` and five in
#: `AFFIXES.md` open with ``Level`` - so selecting on it would silently lift the
#: wrong table and the emission would be confidently about something else.
CLASS_ID_HEADER = ("classId", "Class", "How established")
LADDER_HEADER = ("Level", "Physical Damage", "Magic Damage", "Effective Range")

#: Heading text each table sits under, used as the record's ``source.anchor`` so
#: a lifted row can be walked back to the narrative that produced it.
CLASS_ID_ANCHOR = "Class ids"
LADDER_ANCHOR = "Affix Level ladder, stated"

#: Named required fields. Every one of them answers a question the naked rows
#: could not:
#:
#: * ``record_id``  - a stable, citable identity for ONE row.
#: * ``subject``    - what the row is about, in words.
#: * ``source``     - which document and which heading; the walk back to the
#:                    narrative that extraction throws away.
#: * ``source_row`` - the literal markdown cells, so the emission can be checked
#:                    against the table and every interpretation is auditable.
#: * ``values``     - the numbers a consumer lifts. An absent key is unmeasured.
#: * ``method``     - how it was established. Question 2.
#: * ``observed_on``- the date it was read. Question 3.
#: * ``build``      - the build it was read on, scheme-tagged. Question 1.
#: * ``claim_type`` - a developer's tooltip claim and a first-party observation
#:                    are different facts; `AFFIXES.md` opens by saying so.
#: * ``reconfirmations`` - a list. EMPTY IS A MEASURED FACT ("checked, none"),
#:                    which is why it is required rather than omitted. Omission
#:                    would mean nobody looked. Question 4.
REQUIRED_RECORD_FIELDS: tuple[str, ...] = (
    "record_id",
    "subject",
    "source",
    "source_row",
    "values",
    "method",
    "observed_on",
    "build",
    "claim_type",
    "reconfirmations",
)

REQUIRED_SOURCE_FIELDS: tuple[str, ...] = ("document", "anchor")
REQUIRED_BUILD_FIELDS: tuple[str, ...] = ("scheme", "buildid")
REQUIRED_DATASET_FIELDS: tuple[str, ...] = (
    "schema_version",
    "generated_from",
    "current_builds",
    "patches",
    "records",
)

#: Strings that mean "we do not know" and must never appear as a VALUE. A
#: measurement this project does not have is represented by omitting the key,
#: so a placeholder here is a missing measurement wearing a value's costume.
#:
#: Scoped to ``values`` only, and that scope is load-bearing: ``source_row``
#: legitimately contains a bare ``-`` because the ladder's Effective Range cell
#: reads exactly that at levels 1 to 4.
FORBIDDEN_PLACEHOLDERS: frozenset[str] = frozenset(
    {"", "-", "--", "?", "n/a", "na", "null", "none", "nil", "tbd", "unknown"}
)

#: Required string fields that must not be blank. A present-but-empty field is
#: a missing field that passes a presence check.
_NON_EMPTY_STRING_FIELDS = ("record_id", "subject", "method", "observed_on", "claim_type")


class ProvenanceError(ValueError):
    """A record or dataset violates the schema."""


class Unmeasured(KeyError):
    """Asked for a value this project has not measured.

    A ``KeyError`` on purpose - the honest answer to "what is the Impact
    magnitude" is that the key is not there, and callers that would otherwise
    have written ``values.get(key, 0)`` get an exception instead of a lie.
    """


# --------------------------------------------------------------------------
# markdown lifting
# --------------------------------------------------------------------------


def _collapse(text: str) -> str:
    """Whitespace-collapsed copy, for matching prose that is hard-wrapped."""
    return re.sub(r"\s+", " ", text)


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _table_blocks(markdown: str) -> Iterator[list[str]]:
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("|"):
            current.append(line)
            continue
        if len(current) >= 3:
            yield current
        current = []
    if len(current) >= 3:
        yield current


def _lift_rows(markdown: str, header: Sequence[str]) -> list[list[str]]:
    """Return the DATA rows of the one table whose header row is ``header``."""
    matches = [b for b in _table_blocks(markdown) if tuple(_cells(b[0])) == tuple(header)]
    if len(matches) != 1:
        raise ProvenanceError(
            f"expected exactly one table with header {tuple(header)!r}, found "
            f"{len(matches)} - the emission must not guess which table it means"
        )
    return [_cells(row) for row in matches[0][2:]]


def _require_match(pattern: str, text: str, what: str) -> re.Match[str]:
    match = re.search(pattern, text)
    if match is None:
        raise ProvenanceError(
            f"could not establish {what} from the source document - the "
            "generator refuses to emit a row whose provenance it had to guess"
        )
    return match


def _percent(cell: str) -> float:
    match = re.fullmatch(r"\+?(\d+(?:\.\d+)?)%", cell.strip())
    if match is None:
        raise ProvenanceError(f"not a percentage cell: {cell!r}")
    return float(match.group(1))


# --------------------------------------------------------------------------
# parsers - one per migrated table
# --------------------------------------------------------------------------


def parse_class_id_records(markdown: str) -> list[dict[str, Any]]:
    """Records for the `docs/OBSERVED_IDS.md` class-id table.

    Lifts the document-scope facts the table itself cannot carry - the buildid
    every id was read on, the observation date that rows 12 and 15 leave to the
    document default, and the explicit statement that NONE has been reconfirmed
    since the patch - and attaches them to every row.
    """
    prose = _collapse(markdown)
    read_on = _require_match(
        r"read on buildid `(\d+)` \((\d{4}-\d\d-\d\d)\)", prose, "the buildid the ids were read on"
    )
    patched = _require_match(
        r"patch landed (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", prose, "the patch instant"
    )
    # A MEASURED zero. The document states outright that none of these has been
    # reconfirmed, so the empty list below is a finding rather than a gap. If
    # that sentence ever changes, the generator must stop rather than keep
    # asserting it.
    _require_match(
        r"None of them has been re-confirmed on the current build",
        prose,
        "the reconfirmation status",
    )
    default_buildid, default_date = read_on.group(1), read_on.group(2)

    records: list[dict[str, Any]] = []
    for cells in _lift_rows(markdown, CLASS_ID_HEADER):
        class_id, name_cell, established = cells[0], cells[1], cells[2]
        name = name_cell.strip("*").strip()
        row_date = re.search(r"\b(\d{4}-\d\d-\d\d)\b", established)
        records.append(
            {
                "record_id": f"observed_ids.class_id.{class_id}",
                "subject": f"classId {class_id}",
                "source": {
                    "document": OBSERVED_IDS_DOCUMENT,
                    "anchor": CLASS_ID_ANCHOR,
                    "authority": "the markdown table is authoritative",
                },
                "source_row": list(cells),
                "values": {"class_id": int(class_id), "class": name},
                "method": established,
                "observed_on": row_date.group(1) if row_date else default_date,
                "observed_on_basis": "row" if row_date else "document_default",
                "build": {"scheme": "steam_buildid", "buildid": default_buildid},
                "claim_type": "first_party_observed",
                "reconfirmations": [],
                "reconfirmations_basis": (
                    "the document states that none of these ids has been "
                    "re-confirmed on the current build; measured empty, not unchecked"
                ),
                "superseded_by_patch_at": patched.group(1),
            }
        )
    return records


def parse_affix_ladder_records(markdown: str) -> list[dict[str, Any]]:
    """Records for the `docs/AFFIXES.md` ranged-damage ladder.

    The build is established by the wall-clock join this project already
    sanctions, and the join is named in the record rather than presented as a
    reading: the frame times fall inside the capture window and inside the
    same-day log session whose `Version` line the same document transcribes.
    """
    prose = _collapse(markdown)
    frame = _require_match(r"`(f0749_[\d.]+)`", prose, "the frame the ladder was read from")
    read_on = _require_match(
        r"`Ranged` affix - read (\d{4}-\d\d-\d\d) from a Legendary bow",
        prose,
        "the date the ladder was read",
    )
    client = _require_match(
        r"`(1\.0\.\d+)` / `(\d{14})` in the live (\d{4}-\d\d-\d\d) log",
        prose,
        "the client build the reading was taken on",
    )
    method = (
        "in-game item tooltip, affix detail panel, read off a passive screen "
        f"capture of the operator's own display (frame `{frame.group(1)}`)"
    )
    build = {
        "scheme": "client_version",
        "buildid": client.group(1),
        "build_date": client.group(2),
        "established": (
            "wall-clock join of the frame time to the `Version` line of the "
            "same-session log, both transcribed in the source document; NOT "
            "read off the frame itself"
        ),
    }

    records: list[dict[str, Any]] = []
    for cells in _lift_rows(markdown, LADDER_HEADER):
        level_cell, physical, magic, effective = cells[0], cells[1], cells[2], cells[3]
        level = int(_require_match(r"Lv\.\s*(\d+)", level_cell, "the affix level").group(1))
        # The dash is a STATED zero, not a gap: the document records that
        # Effective Range "appears at Lv. 5". `source_row` keeps the literal
        # cell so this resolution can be checked against the table.
        range_pct = 0 if effective == "-" else _percent(effective)
        records.append(
            {
                "record_id": f"affixes.ranged_ladder.lv{level}",
                "subject": f"Ranged affix, Lv. {level}",
                "source": {
                    "document": AFFIXES_DOCUMENT,
                    "anchor": LADDER_ANCHOR,
                    "authority": "the markdown table is authoritative",
                },
                "source_row": list(cells),
                # `impact_pct` is deliberately ABSENT. The tooltip says Impact
                # diminishes past the effective range and states no magnitude
                # for it anywhere, so there is nothing to record and a zero
                # would be a fabrication.
                "values": {
                    "level": level,
                    "physical_damage_pct": _percent(physical),
                    "magic_damage_pct": _percent(magic),
                    "effective_range_pct": range_pct,
                },
                "method": method,
                "observed_on": read_on.group(1),
                "observed_on_basis": "section heading",
                "build": build,
                "claim_type": "game_stated",
                "reconfirmations": [],
                "reconfirmations_basis": (
                    "no re-reading of this tooltip has been recorded since the "
                    "date above; measured empty, not unchecked"
                ),
            }
        )
    return records


# --------------------------------------------------------------------------
# dataset assembly
# --------------------------------------------------------------------------


def build_dataset(
    *, observed_ids_markdown: str, affixes_markdown: str
) -> dict[str, Any]:
    """Assemble the whole emission from the two authoritative documents."""
    ids_prose = _collapse(observed_ids_markdown)
    affix_prose = _collapse(affixes_markdown)
    current_steam = _require_match(
        r"Game build: Steam buildid `(\d+)`, observed (\d{4}-\d\d-\d\d)",
        ids_prose,
        "the current Steam buildid",
    )
    current_client = _require_match(
        r"`(1\.0\.\d+)` / `(\d{14})` in the live (\d{4}-\d\d-\d\d) log",
        affix_prose,
        "the current client version",
    )
    patched = _require_match(
        r"patch landed (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", ids_prose, "the patch instant"
    )
    records = parse_class_id_records(observed_ids_markdown)
    records += parse_affix_ladder_records(affixes_markdown)
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "Row-scoped provenance for numbers an outside consumer would lift "
            "out of this project's tables. GENERATED from the markdown named "
            "below, which stays authoritative - a drift between the two is a "
            "failing test, not a fork. Do not hand-edit."
        ),
        "generated_from": [
            {"document": AFFIXES_DOCUMENT, "role": "authoritative"},
            {"document": OBSERVED_IDS_DOCUMENT, "role": "authoritative"},
        ],
        "current_builds": [
            {
                "scheme": "steam_buildid",
                "buildid": current_steam.group(1),
                "observed_on": current_steam.group(2),
                "source": OBSERVED_IDS_DOCUMENT,
            },
            {
                "scheme": "client_version",
                "buildid": current_client.group(1),
                "build_date": current_client.group(2),
                "observed_on": current_client.group(3),
                "source": AFFIXES_DOCUMENT,
            },
        ],
        "patches": [
            {
                "at": patched.group(1),
                "source": OBSERVED_IDS_DOCUMENT,
                "note": (
                    "a record observed before this instant was read on a game "
                    "that has since changed"
                ),
            }
        ],
        "records": records,
    }


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _iter_scalars(value: Any) -> Iterator[Any]:
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_scalars(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_scalars(item)
    else:
        yield value


def validate_record(record: Any) -> None:
    """Raise :class:`ProvenanceError` naming the first violated rule.

    The message NAMES the offending field. A schema failure that says only
    "invalid record" costs more than it saves.
    """
    if not isinstance(record, Mapping):
        raise ProvenanceError(f"record is not a mapping: {type(record).__name__}")

    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise ProvenanceError(f"missing required field {field!r}")

    for field in _NON_EMPTY_STRING_FIELDS:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise ProvenanceError(f"required field {field!r} is blank or not a string")

    source = record["source"]
    if not isinstance(source, Mapping):
        raise ProvenanceError("required field 'source' is not a mapping")
    for field in REQUIRED_SOURCE_FIELDS:
        if not str(source.get(field, "")).strip():
            raise ProvenanceError(f"missing required source field {field!r}")

    build = record["build"]
    if not isinstance(build, Mapping):
        raise ProvenanceError("required field 'build' is not a mapping")
    for field in REQUIRED_BUILD_FIELDS:
        if not str(build.get(field, "")).strip():
            raise ProvenanceError(f"missing required build field {field!r}")

    row = record["source_row"]
    if not isinstance(row, (list, tuple)) or not row:
        raise ProvenanceError("required field 'source_row' is empty or not a list")
    if not all(isinstance(cell, str) for cell in row):
        raise ProvenanceError("required field 'source_row' must be the literal cells")

    if not isinstance(record["reconfirmations"], list):
        raise ProvenanceError(
            "required field 'reconfirmations' must be a list - an EMPTY list is "
            "the measured fact 'checked, none'; omission would mean nobody looked"
        )

    values = record["values"]
    if not isinstance(values, Mapping) or not values:
        raise ProvenanceError("required field 'values' is empty or not a mapping")

    # ADR-005. Absence is expressed by omitting the key, so nothing anywhere in
    # the record may be null, and no VALUE may be a placeholder meaning "we do
    # not know". Note what is deliberately NOT rejected: 0 and -1 are legitimate
    # measurements, and a guard that refused them would destroy the measured
    # zero it exists to protect. The rule is about how absence is REPRESENTED.
    for scalar in _iter_scalars(record):
        if scalar is None:
            raise ProvenanceError(
                f"record {record['record_id']!r} contains a null; an unmeasured "
                "field is ABSENT, never null"
            )
    for key, value in values.items():
        if isinstance(value, str) and value.strip().lower() in FORBIDDEN_PLACEHOLDERS:
            raise ProvenanceError(
                f"values[{key!r}] is the placeholder {value!r}; an unmeasured "
                "field is omitted, not filled with a token"
            )


def validate_dataset(dataset: Any) -> None:
    """Validate the whole emission, naming the offending record."""
    if not isinstance(dataset, Mapping):
        raise ProvenanceError(f"dataset is not a mapping: {type(dataset).__name__}")
    for field in REQUIRED_DATASET_FIELDS:
        if field not in dataset:
            raise ProvenanceError(f"missing required dataset field {field!r}")
    records = dataset["records"]
    if not isinstance(records, list) or not records:
        raise ProvenanceError("dataset has no records")
    for index, record in enumerate(records):
        identity = f"#{index}"
        if isinstance(record, Mapping):
            identity = record.get("record_id", identity)
        try:
            validate_record(record)
        except ProvenanceError as exc:
            raise ProvenanceError(f"record {identity}: {exc}") from exc
    seen = [r["record_id"] for r in records]
    if len(set(seen)) != len(seen):
        raise ProvenanceError("record_id is not unique across the dataset")


# --------------------------------------------------------------------------
# reading a record - absence never defaults
# --------------------------------------------------------------------------


def by_record_id(dataset: Mapping[str, Any], record_id: str) -> dict[str, Any]:
    for record in dataset["records"]:
        if record["record_id"] == record_id:
            return record
    raise KeyError(record_id)


def is_measured(record: Mapping[str, Any], key: str) -> bool:
    """True when ``key`` was measured. An absent key is not a zero."""
    return key in record["values"]


def measured_value(record: Mapping[str, Any], key: str) -> Any:
    """Return the measured value, or raise :class:`Unmeasured`.

    Deliberately has no ``default`` parameter. A default is how "we never
    measured this" becomes "it is zero".
    """
    values = record["values"]
    if key not in values:
        raise Unmeasured(
            f"{key!r} was not measured for {record['record_id']!r} - absent is "
            "not zero"
        )
    return values[key]


def is_measured_zero(record: Mapping[str, Any], key: str) -> bool:
    """True only when the value was measured AND is zero."""
    return is_measured(record, key) and record["values"][key] == 0


# --------------------------------------------------------------------------
# the staleness query - criterion 6, answerable from the data alone
# --------------------------------------------------------------------------


def _current_by_scheme(dataset: Mapping[str, Any]) -> dict[str, str]:
    return {entry["scheme"]: entry["buildid"] for entry in dataset["current_builds"]}


def _partition(dataset: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    current = _current_by_scheme(dataset)
    buckets: dict[str, list[dict[str, Any]]] = {
        "superseded": [],
        "current": [],
        "undetermined": [],
    }
    for record in dataset["records"]:
        build = record["build"]
        known = current.get(build["scheme"])
        if known is None:
            buckets["undetermined"].append(record)
        elif build["buildid"] == known:
            buckets["current"].append(record)
        else:
            buckets["superseded"].append(record)
    return buckets


def records_on_superseded_builds(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every record read on a build that is no longer current.

    In `docs/OBSERVED_IDS.md` this is a paragraph only a human reader can act
    on. Here it is a query.
    """
    return _partition(dataset)["superseded"]


def records_on_current_builds(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _partition(dataset)["current"]


def records_on_undetermined_builds(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Records whose build scheme has no current-build entry to compare against.

    Neither current nor stale, and kept separate rather than folded into either
    - "we cannot tell" is a third answer, and collapsing it into "current" is
    how a stale number gets published as fresh.
    """
    return _partition(dataset)["undetermined"]


def records_predating_latest_patch(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every record observed before the most recent recorded patch instant."""
    patches: Iterable[Mapping[str, Any]] = dataset["patches"]
    instants = sorted(patch["at"] for patch in patches)
    if not instants:
        return []
    latest_date = instants[-1][:10]
    return [r for r in dataset["records"] if r["observed_on"] < latest_date]


# --------------------------------------------------------------------------
# io
# --------------------------------------------------------------------------


def load(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or DATA_PATH).read_text(encoding="ascii"))


def write_dataset(dataset: Mapping[str, Any], path: Path | None = None) -> Path:
    """Write the emission atomically, LF-terminated and pure ASCII.

    Atomic because a reader may poll it, and ``newline="\\n"`` because Windows
    ``write_text`` silently turns LF into CRLF and ``.gitattributes`` pins the
    committed blob to LF.
    """
    target = path or DATA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataset, indent=2, ensure_ascii=True) + "\n"
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload, encoding="ascii", newline="\n")
    tmp.replace(target)
    return target


def rebuild(path: Path | None = None) -> Path:
    """Regenerate the emission from the authoritative markdown."""
    dataset = build_dataset(
        observed_ids_markdown=(REPO_ROOT / OBSERVED_IDS_DOCUMENT).read_text(encoding="ascii"),
        affixes_markdown=(REPO_ROOT / AFFIXES_DOCUMENT).read_text(encoding="ascii"),
    )
    validate_dataset(dataset)
    return write_dataset(dataset, path)


if __name__ == "__main__":  # pragma: no cover - a hand-run regeneration step
    print(f"wrote {rebuild()}")
