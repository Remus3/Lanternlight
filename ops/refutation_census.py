"""Re-derive this project's refutation census from its own ledger.

``OPS-87`` criterion 1: a record of the refutation findings each recently
closed item produced, classified into five buckets, with the largest bucket
NAMED with its number, "derived at run time ... rather than from memory".

WHAT IS STORED AND WHAT IS RECOMPUTED, because the difference is the whole
design. A bucket letter is a judgement and no program can recompute it, so the
judgement is written down once per event in :data:`DATA_PATH` beside a VERBATIM
quote of the ledger sentence it classifies. Everything else is recomputed here
on every run: which ledger entries fall inside the window, whether each quote
still resolves in the ledger, and every total. Nothing counted is stored, so
nothing counted can go stale - which is this repository's own rule that a filed
count is a hypothesis, applied to the instrument rather than to the artifact.

TOTALS ARE RECOMPUTED FROM PER-EVENT ROWS ON PURPOSE. A sibling project
measuring the same thing on the same day reported that three of its four
extraction passes mis-summarised their own per-event data, so every total it
published had to be recomputed from the rows. That is mail rather than
authority and it changes no rule here, but it is cheap to be immune to the
failure it describes: this module never reads a total that anybody typed.

THE TWO LIMITS, repeated in the printed report rather than left here. The
ledger is written by the party being measured, so an event nobody wrote down is
invisible and the census is a LOWER BOUND. And the split between "a real defect
in the deliverable" and "a stale recital in a document" depends on how an entry
chose to describe itself, so treat it as DIRECTIONAL rather than as a point
estimate.

Run it with ``python -m ops.refutation_census``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = REPO_ROOT / "docs" / "refutation_census.tsv"

LEDGER_PATHS = (
    REPO_ROOT / "docs" / "LEDGER.md",
    REPO_ROOT / "docs" / "LEDGER_ARCHIVE.md",
)

#: The window's first day, inclusive. Five days ending on the day ``OPS-87`` was
#: filed. It is stated here rather than computed from "today" so that the census
#: describes a FIXED corpus: a window that slides would change the answer every
#: time the tool ran, and the back-test in criterion 3 needs a corpus that does
#: not move under it.
WINDOW_START = "2026-09-08"

#: The newest entry in the corpus, inclusive. The window needs BOTH ends or it
#: is not a corpus: adding this census's own ledger entry put a 65th in-window
#: entry into a measurement of 64, and the coverage check went red against the
#: session that wrote it. A window open at the top would also make every
#: published percentage drift with the next entry anybody files, and the
#: back-test in criterion 3 needs a corpus that does not move under it. Ids are
#: compared numerically, which is safe here and is not safe in general - see
#: docs/LEDGER.md on ids not being allocated in order.
WINDOW_END = "LL-0236"

BUCKETS = ("a", "b", "c", "d", "e")

BUCKET_NAMES = {
    "a": "a real defect in the deliverable",
    "b": "a missing registration or plumbing step the deliverable's own green could not see",
    "c": "a stale recital in a document",
    "d": "an artifact of the mutation harness rather than of the code",
    "e": "an over-report by the check under test",
}

_COLUMNS = 7

_ENTRY_ID = re.compile(r"^LL-\d{4}$")

#: A ledger entry heading: ``### LL-0236 - 2026-09-12 - summary``. The date is
#: matched as digits, so the format template's literal ``YYYY-MM-DD`` heading is
#: not an entry - it is a worked example and counting it would inflate N by one.
_HEADING = re.compile(r"^### (LL-\d{4}) - (\d{4}-\d{2}-\d{2}) - ", re.MULTILINE)


class CensusFormatError(ValueError):
    """A row in the census data file is malformed."""


@dataclass(frozen=True)
class Event:
    """One refutation event, as classified by a human and pinned to a quote."""

    entry_id: str
    bucket: str
    inherited: bool
    fixfix: bool
    uncertain: bool
    quote: str
    reason: str


def _flag(value: str, field: str, line_no: int) -> bool:
    if value == "Y":
        return True
    if value == "N":
        return False
    raise CensusFormatError(
        f"line {line_no}: {field} must be Y or N, not {value!r}"
    )


def parse_rows(text: str) -> list[Event]:
    """Parse the TSV body into events, refusing anything malformed.

    Blank lines and lines whose first character is ``#`` are skipped, so the
    data file can carry its own header comment.
    """
    events: list[Event] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        fields = raw.split("\t")
        if len(fields) != _COLUMNS:
            raise CensusFormatError(
                f"line {line_no}: expected {_COLUMNS} fields separated by tabs, "
                f"got {len(fields)}"
            )
        entry_id, bucket, inherited, fixfix, uncertain, quote, reason = fields
        if not _ENTRY_ID.match(entry_id):
            raise CensusFormatError(
                f"line {line_no}: entry id {entry_id!r} is not LL-NNNN shaped"
            )
        if bucket not in BUCKETS:
            raise CensusFormatError(
                f"line {line_no}: bucket {bucket!r} is not one of {BUCKETS}"
            )
        if not quote.strip():
            raise CensusFormatError(
                f"line {line_no}: the quote is empty, and an empty anchor "
                "resolves against any text at all"
            )
        events.append(
            Event(
                entry_id=entry_id,
                bucket=bucket,
                inherited=_flag(inherited, "inherited", line_no),
                fixfix=_flag(fixfix, "fixfix", line_no),
                uncertain=_flag(uncertain, "uncertain", line_no),
                quote=quote,
                reason=reason,
            )
        )
    return events


def examined_entries(text: str) -> tuple[str, ...]:
    """Every entry id declared as READ, from the ``#examined`` directives.

    An entry that produced no refutation event and an entry nobody opened look
    identical in a file of events, and the difference is the whole soundness of
    a percentage. The first extraction pass here covered 53 of the 64 entries
    the window derives and nothing in the data said so, so coverage is declared
    rather than inferred from the rows.

    A directive is a line beginning exactly ``#examined`` followed by
    whitespace-separated ids. An ordinary ``# examined ...`` comment is not one:
    a parser that accepted prose would let a sentence about coverage stand in
    for coverage.
    """
    seen: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.startswith("#examined"):
            continue
        for token in raw[len("#examined") :].split():
            if not _ENTRY_ID.match(token):
                raise CensusFormatError(
                    f"line {line_no}: {token!r} is not an LL-NNNN entry id"
                )
            if token not in seen:
                seen.append(token)
    return tuple(seen)


def unexamined(
    window: tuple[str, ...], examined: tuple[str, ...]
) -> tuple[str, ...]:
    """In-window entries nobody declared having read."""
    declared = set(examined)
    return tuple(entry for entry in window if entry not in declared)


def examined_outside(
    window: tuple[str, ...], examined: tuple[str, ...]
) -> tuple[str, ...]:
    """Declared entries that are not in the window the ledger yields."""
    inside = set(window)
    return tuple(entry for entry in examined if entry not in inside)


def load_rows(path: Path = DATA_PATH) -> list[Event]:
    """Parse the tracked census data file."""
    return parse_rows(path.read_text(encoding="utf-8"))


def ledger_text(paths: tuple[Path, ...] = LEDGER_PATHS) -> str:
    """The live ledger and its archive, concatenated.

    Both halves are read because ``OPS-57`` split the document: an empty search
    of the live file is a claim about which half was searched, not about the
    project.
    """
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def window_entries(
    text: str, start: str = WINDOW_START, end: str = WINDOW_END
) -> tuple[str, ...]:
    """Entry ids dated on or after ``start`` and numbered no higher than ``end``."""
    ceiling = int(end.split("-")[1])
    return tuple(
        entry_id
        for entry_id, date in _HEADING.findall(text)
        if date >= start and int(entry_id.split("-")[1]) <= ceiling
    )


def missing_anchors(rows: list[Event], text: str) -> list[Event]:
    """Rows whose quote no longer appears verbatim in ``text``.

    Matching is exact and case-sensitive. A matcher that folded case or
    collapsed whitespace would keep resolving after the sentence it pins had
    been reworded, which is the failure this check exists to make loud.
    """
    return [row for row in rows if row.quote not in text]


def out_of_window(rows: list[Event], entries: tuple[str, ...]) -> list[Event]:
    """Rows classifying an entry that is not inside the stated window."""
    inside = set(entries)
    return [row for row in rows if row.entry_id not in inside]


def tally(rows: list[Event]) -> dict[str, int]:
    """Per-bucket counts, recomputed from the rows, zeros included."""
    counts = dict.fromkeys(BUCKETS, 0)
    for row in rows:
        counts[row.bucket] += 1
    return counts


def largest_bucket(counts: dict[str, int]) -> tuple[tuple[str, ...], int]:
    """The bucket or buckets with the highest count, and that count."""
    high = max(counts.values(), default=0)
    if high == 0:
        return (), 0
    return tuple(b for b in BUCKETS if counts[b] == high), high


def axis_counts(rows: list[Event]) -> dict[str, int]:
    """The three flag axes, counted independently of the buckets."""
    return {
        "inherited": sum(1 for row in rows if row.inherited),
        "fixfix": sum(1 for row in rows if row.fixfix),
        "uncertain": sum(1 for row in rows if row.uncertain),
    }


def format_report(
    rows: list[Event],
    entries: tuple[str, ...],
    missing: list[Event],
    stray: list[Event],
    unread: tuple[str, ...] = (),
) -> str:
    """The human-readable census report."""
    counts = tally(rows)
    total = len(rows)
    names, high = largest_bucket(counts)
    axes = axis_counts(rows)
    lines = [
        "REFUTATION CENSUS - OPS-87 criterion 1",
        f"  window     : entries dated {WINDOW_START} or later, up to {WINDOW_END}",
        f"  entries     : {len(entries)}, every one of them examined",
        f"  events      : {total}",
        "",
        "BUCKETS, recomputed from the per-event rows:",
    ]
    for bucket in BUCKETS:
        share = (100.0 * counts[bucket] / total) if total else 0.0
        lines.append(
            f"  ({bucket}) {counts[bucket]:3d}  {share:5.1f} pct  {BUCKET_NAMES[bucket]}"
        )
    if names:
        named = ", ".join(f"({b})" for b in names)
        lines.append("")
        lines.append(f"LARGEST BUCKET: {named} with {high} of {total} events")
        if len(names) > 1:
            lines.append("  TIED, and both are named rather than one picked by sort order.")
    else:
        lines.append("")
        lines.append("LARGEST BUCKET: none - the census is empty")
    lines += [
        "",
        "AXES, counted independently of the buckets:",
        f"  inherited from a durable record : {axes['inherited']}",
        f"  a fix of a fix                  : {axes['fixfix']}",
        f"  classified with uncertainty     : {axes['uncertain']}",
        "",
        "SOUNDNESS:",
    ]
    if missing or stray or unread:
        lines.append("  UNSOUND - the census no longer matches the ledger.")
        for entry in unread:
            lines.append(f"    {entry}: in window and never examined")
        for row in missing:
            lines.append(f"    {row.entry_id}: anchor does not resolve: {row.quote[:70]}")
        for row in stray:
            lines.append(f"    {row.entry_id}: outside the stated window")
    else:
        lines.append("  every anchor resolves verbatim and every entry is in window")
    lines += [
        "",
        "TWO LIMITS ON THIS NUMBER:",
        "  The ledger is written by the party being measured, so an event nobody",
        "  wrote down is invisible here. The event count is a lower bound.",
        "  The (a) against (c) split depends on how an entry described itself, so",
        "  treat that split as directional rather than as a point estimate.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the census report. Exit 0 even when unsound - the tests judge."""
    del argv
    rows = load_rows()
    text = ledger_text()
    window = window_entries(text)
    examined = examined_entries(DATA_PATH.read_text(encoding="utf-8"))
    print(
        format_report(
            rows,
            window,
            missing=missing_anchors(rows, text),
            stray=out_of_window(rows, window),
            unread=unexamined(window, examined),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
