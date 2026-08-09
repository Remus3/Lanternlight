"""Parse the Mistfall Hunter market average-price cache.

The game maintains this file itself and Lanternlight only ever reads it.
Measured location on 2026-08-09::

    %LOCALAPPDATA%/MistfallHunter/Saved/AvgPrice_937566.ini

Note that this sits at the **root of the Saved tree**, not under ``Config``,
and the filename carries the publisher app_id suffix ``_937566``. That
contradicts the expectation encoded in :mod:`lanternlight.paths`, whose
``avg_price_ini`` points at ``<Saved>/Config/WindowsClient/AvgPrice.ini`` and
whose ``find_avg_price_ini`` searches for the exact name ``AvgPrice.ini``. Both
were flagged UNVERIFIED when written and both are now measured wrong. That
module is out of scope for this change; the discrepancy is recorded here rather
than left as a silent trap for whoever wires the watcher.

Format, measured from the real 343-byte file::

    [PriceTime]
    1786285800
    [TradePrices]
    901201=26
    904303=44
    ...

**This is not valid INI**, which is the whole reason this module exists.
``[PriceTime]`` holds a BARE VALUE on its own line with no ``key=``. Python's
``configparser`` raises ``ParsingError`` on that line, and the only
configuration that swallows it - ``allow_no_value=True, strict=False`` - then
misreads the epoch as a KEY whose value is ``None``. A wrong answer is worse
than a refusal, so the line parsing here is hand-rolled.
``tests/test_avgprice.py`` pins the stdlib rejection as a fact so nobody later
"simplifies" this back into a configparser call.

``1786285800`` is a Unix epoch in seconds: 2026-08-09T14:30:00+00:00. Every
instant this module produces is timezone-aware and pinned to UTC, matching
:mod:`lanternlight.logparse`. A naive datetime compared against ``now()`` would
be wrong by the operator's offset.

**Cross-surface id join - the first one found in this project.** The cfgIds in
this file are the same id space the game log's loot stream uses
(``RequestPickupLoot ... cfgId:901201, count:2, context:EnemyCorpse``). Measured
on 2026-08-09 against the live log: of the 30 ids in this file, **28 also
appear in the loot stream**. The two that do not are ``3020401`` and
``1720201``; the loot stream additionally carried ``101``, ``901101`` and
``999998``, which this file does not price.

That overlap is the finding - it means a name learned on either surface names
the item on both, so a single naming pass can light up the market cache and the
inventory at once. It is not evidence about what any id IS. **No item name has
been observed for any id**, so this module binds none and invents none. An id
is not an item.

Two facts this module refuses to conflate
-----------------------------------------

The file was previously measured at **37 bytes and called empty**. That state
was not a zero-byte file: 37 bytes is exactly ``[PriceTime]`` + a ten-digit
stamp + ``[TradePrices]`` + three newlines, so what was there was both section
headers, a stamp, and not one trade row. A fresh install will show it again.

So ``snapshot.prices == {}`` on its own is NOT a fact worth acting on. It means
either "the section was there and held nothing" or "the section was never
written". :attr:`AvgPriceSnapshot.has_trade_prices_section` is what separates
measured-zero from unmeasured, and callers that care about the difference must
read it rather than the emptiness of the dict.

Unknown lines are never silently dropped
----------------------------------------

:func:`parse` **raises** on anything it does not recognise. That is the
default because the alternative failure is invisible: a new section or a
changed row shape would otherwise yield a snapshot that looks complete while
quietly holding fewer prices, and a confidently wrong number is the one kind of
error this project cannot recover from.

``strict=False`` is offered anyway, and it records rather than drops - every
unrecognised line lands in :attr:`AvgPriceSnapshot.unknown_lines` with its line
number, the section in force and a reason, and :attr:`is_complete` goes False.
That mode exists for one concrete reason: this file is written by a live game
and a poller can catch a torn write. Faced with a parser that only ever raises,
the author of that poller writes ``except Exception: pass`` and drops the whole
snapshot on the floor - which is precisely the silent loss the strict default
was meant to prevent. Better to hand that caller a result that can say what it
missed.

Deliberately not interpreted here: a duplicate cfgId keeps the FIRST value and
reports the second rather than overwriting; no row is sorted, because the
file's own order is an observation about the writer; and no comment syntax is
assumed, so a ``;`` or ``#`` line is unrecognised rather than skipped. A
repeated known section header is not an error - it simply continues that
section, and no data is lost either way.

Typical use::

    snapshot = load(path)
    if snapshot.has_trade_prices_section:
        ...  # snapshot.prices is now a measurement, empty or not
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "KNOWN_SECTIONS",
    "PRICE_TIME_SECTION",
    "TRADE_PRICES_SECTION",
    "AvgPriceParseError",
    "AvgPriceSnapshot",
    "UnknownLine",
    "load",
    "parse",
]

#: Section holding a single bare Unix epoch in seconds.
PRICE_TIME_SECTION = "PriceTime"

#: Section holding ``cfgId=price`` rows.
TRADE_PRICES_SECTION = "TradePrices"

#: Every section header observed in this file. Anything else is unrecognised,
#: not assumed harmless - a new section is exactly the schema change worth
#: hearing about.
KNOWN_SECTIONS: frozenset[str] = frozenset({PRICE_TIME_SECTION, TRADE_PRICES_SECTION})

# Byte-order mark, built via chr() so this source file stays 7-bit ASCII.
_BOM = chr(0xFEFF)

_SECTION_RE = re.compile(r"^\[(?P<name>[^\[\]]*)\]$")
_BARE_INT_RE = re.compile(r"^-?\d+$")
_PRICE_ROW_RE = re.compile(r"^(?P<cfg_id>-?\d+)\s*=\s*(?P<price>-?\d+)$")


class AvgPriceParseError(ValueError):
    """Raised by :func:`parse` when a line cannot be recognised.

    The message names the 1-based line number, the section in force and the
    offending text, so a failure points at the line rather than merely
    announcing that one exists.
    """


@dataclass(frozen=True)
class UnknownLine:
    """One line :func:`parse` could not recognise, recorded rather than dropped.

    ``section`` is the section header in force when the line was read, exactly
    as written in the file - so it may name a section this module does not
    know. It is ``None`` for a line that appeared before any header at all.
    """

    line_no: int
    section: str | None
    text: str
    reason: str

    def describe(self) -> str:
        """Return a one-line human-readable rendering of this finding."""
        where = f"[{self.section}]" if self.section is not None else "no section"
        return f"line {self.line_no} ({where}): {self.reason}: {self.text!r}"


@dataclass(frozen=True)
class AvgPriceSnapshot:
    """One parse of the market cache.

    ``price_time`` is timezone-aware UTC, or ``None`` when the file carried no
    stamp. ``None`` here means "not present in the file" and never "zero" - the
    two are different observations and this module keeps them apart.

    ``prices`` maps cfgId to price, both plain integers, in the order the file
    wrote them. It is an ordinary mutable dict on purpose: callers get a
    structure they can use without unwrapping, and the frozen dataclass is
    about the snapshot's identity, not about defending the dict.

    ``sections_seen`` holds the known section headers that actually appeared.
    Read it, not the emptiness of ``prices``, to tell measured-zero from
    unmeasured.
    """

    price_time: datetime | None
    prices: dict[int, int] = field(default_factory=dict)
    sections_seen: frozenset[str] = frozenset()
    unknown_lines: tuple[UnknownLine, ...] = ()

    @property
    def has_price_time(self) -> bool:
        """True when the file carried a stamp this module could convert."""
        return self.price_time is not None

    @property
    def has_trade_prices_section(self) -> bool:
        """True when ``[TradePrices]`` appeared, whether or not it held rows.

        This is the measured-zero test. An empty ``prices`` with this True is
        a market cache that has been written and holds nothing; with this False
        it is a cache that has never been told anything.
        """
        return TRADE_PRICES_SECTION in self.sections_seen

    @property
    def is_complete(self) -> bool:
        """True when every line in the source was recognised.

        Always True for a snapshot returned by a strict parse, because a strict
        parse raises instead of returning an incomplete result.
        """
        return not self.unknown_lines


def _split_lines(text: str) -> list[str]:
    """Split on LF, CRLF or CR without ``str.splitlines`` extra separators.

    ``str.splitlines`` also breaks on form feed, vertical tab and several
    Unicode separators. None of those has been observed in this file, and
    treating one as a line break would silently split a value in half.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _to_utc(epoch: int) -> datetime | None:
    """Convert a Unix epoch in seconds to a tz-aware UTC instant, or None.

    Returns ``None`` when the value cannot be an instant at all. The caller
    turns that into a recorded unknown; it never substitutes a stand-in date.
    """
    try:
        return datetime.fromtimestamp(epoch, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def parse(text: str, *, strict: bool = True) -> AvgPriceSnapshot:
    """Parse market cache text into an :class:`AvgPriceSnapshot`.

    Raises :class:`AvgPriceParseError` on the first unrecognised line. Pass
    ``strict=False`` to collect them into ``unknown_lines`` instead; see the
    module docstring for why both modes exist and why raising is the default.

    Blank and whitespace-only lines are skipped and are not unknowns. Nothing
    else is skipped.
    """
    price_time: datetime | None = None
    prices: dict[int, int] = {}
    sections_seen: set[str] = set()
    unknowns: list[UnknownLine] = []
    current: str | None = None

    def record(line_no: int, raw: str, reason: str) -> None:
        unknown = UnknownLine(
            line_no=line_no, section=current, text=raw, reason=reason
        )
        if strict:
            raise AvgPriceParseError(unknown.describe())
        unknowns.append(unknown)

    body = text.lstrip(_BOM) if text else text
    for index, raw_line in enumerate(_split_lines(body), start=1):
        line = raw_line.strip()
        if not line:
            continue

        section_match = _SECTION_RE.match(line)
        if section_match is not None:
            name = section_match["name"].strip()
            current = name
            if name in KNOWN_SECTIONS:
                sections_seen.add(name)
            else:
                record(index, line, "unrecognised section header")
            continue

        if current == PRICE_TIME_SECTION:
            if not _BARE_INT_RE.match(line):
                record(index, line, "expected a bare epoch on its own line")
                continue
            if price_time is not None:
                record(index, line, "second stamp; the first one is kept")
                continue
            converted = _to_utc(int(line))
            if converted is None:
                record(index, line, "epoch is not a representable instant")
                continue
            price_time = converted
            continue

        if current == TRADE_PRICES_SECTION:
            row_match = _PRICE_ROW_RE.match(line)
            if row_match is None:
                record(index, line, "expected cfgId=price")
                continue
            cfg_id = int(row_match["cfg_id"])
            if cfg_id in prices:
                record(index, line, "duplicate cfgId; the first price is kept")
                continue
            prices[cfg_id] = int(row_match["price"])
            continue

        if current is None:
            record(index, line, "row before any section header")
        else:
            record(index, line, f"row inside unrecognised section {current!r}")

    return AvgPriceSnapshot(
        price_time=price_time,
        prices=prices,
        sections_seen=frozenset(sections_seen),
        unknown_lines=tuple(unknowns),
    )


def load(path: Path | str, *, strict: bool = True) -> AvgPriceSnapshot:
    """Read and parse the market cache at ``path``.

    A missing file raises ``FileNotFoundError`` rather than returning an empty
    snapshot. "The file is not there" and "the file is there and holds nothing"
    are different facts about the install, and collapsing them would hide the
    only one of the two that means something is wrong.

    This function never writes to ``path`` and never holds it open beyond the
    read.
    """
    return parse(Path(path).read_text(encoding="utf-8"), strict=strict)
