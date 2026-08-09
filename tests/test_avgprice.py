"""Tests for lanternlight.avgprice against the real market cache file.

``tests/fixtures/avgprice_sample.ini`` is a byte-for-byte copy of
``%LOCALAPPDATA%/MistfallHunter/Saved/AvgPrice_937566.ini`` as measured on
2026-08-09: 343 bytes, LF line endings, pure 7-bit ASCII. It is committed raw
because it carries no identifier of any kind - the ``937566`` in the game's own
filename is the publisher app_id, already public in ``docs/FINDINGS.md``. That
claim is not taken on trust; :func:`test_fixture_carries_no_identifiers` runs
the fixture through the redactor's own detectors.

Two facts drive most of the assertions here:

- The file is NOT valid INI. ``[PriceTime]`` holds a bare value on its own line
  with no ``key=``, which the stdlib rejects.
  :func:`test_stdlib_configparser_cannot_read_this_file` pins that, so nobody
  later "simplifies" this module into a configparser call.
- ``prices == {}`` on its own is not a fact. It could mean the section was
  present and held nothing, or that the section was never written at all. Those
  are different observations and the tests below keep them apart.
"""

import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight.avgprice import (  # noqa: E402
    PRICE_TIME_SECTION,
    TRADE_PRICES_SECTION,
    AvgPriceParseError,
    AvgPriceSnapshot,
    UnknownLine,
    load,
    parse,
)
from lanternlight.redact import ALL_LABELS, assert_clean  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "avgprice_sample.ini"

#: The measured byte size of the real file on 2026-08-09.
FIXTURE_BYTES = 343

#: The bare epoch on line 2 of the real file, and the instant it denotes.
MEASURED_EPOCH = 1786285800
MEASURED_PRICE_TIME = datetime(2026, 8, 9, 14, 30, 0, tzinfo=UTC)

#: Every ``cfgId=price`` row of the real file, in file order.
MEASURED_PRICES: dict[int, int] = {
    901201: 26,
    904303: 44,
    903303: 41,
    903201: 26,
    903203: 23,
    903205: 28,
    903302: 40,
    903202: 22,
    904403: 113,
    904204: 27,
    901205: 29,
    901206: 20,
    904302: 52,
    904203: 27,
    901207: 33,
    3020401: 31,
    901301: 94,
    903401: 93,
    904205: 28,
    904206: 27,
    903402: 104,
    904202: 26,
    904307: 48,
    903307: 52,
    903501: 194,
    903306: 44,
    903308: 47,
    903405: 101,
    1720201: 31,
    901208: 24,
}

#: The shape the file had when it was first measured at 37 bytes: both section
#: headers present, a stamp, and not one trade row. Built here as an explicit
#: string rather than read from disk so the byte count below is a statement
#: about the format and not about how git checked a file out.
EMPTY_SHELL = "[PriceTime]\n1786285800\n[TradePrices]\n"


def fixture_text() -> str:
    return FIXTURE.read_text(encoding="ascii")


# ---------------------------------------------------------------------------
# The fixture is the artifact, not a paraphrase of it
# ---------------------------------------------------------------------------


def test_fixture_is_the_measured_artifact():
    data = FIXTURE.read_bytes()
    assert len(data) == FIXTURE_BYTES
    assert b"\r\n" not in data, "fixture must stay LF; see .gitattributes"
    assert data.endswith(b"\n")
    assert all(byte < 0x80 for byte in data)


def test_fixture_carries_no_identifiers():
    # Every label, IPV4 included. This file is committed raw, so it gets the
    # strict scan rather than the relaxed file-scan label set.
    assert_clean(fixture_text(), labels=ALL_LABELS)


def test_stdlib_configparser_cannot_read_this_file():
    # The justification for hand-rolled parsing, pinned as a fact. If a future
    # Python ever accepts a keyless line by default, this test fails loudly and
    # the design decision gets re-examined on purpose rather than by accident.
    import configparser

    parser = configparser.ConfigParser()
    with pytest.raises(configparser.Error):
        parser.read_string(fixture_text())


# ---------------------------------------------------------------------------
# Round trip against the real file
# ---------------------------------------------------------------------------


def test_parse_round_trips_the_real_fixture():
    snapshot = parse(fixture_text())
    assert isinstance(snapshot, AvgPriceSnapshot)
    assert snapshot.prices == MEASURED_PRICES
    assert len(snapshot.prices) == 30
    assert snapshot.price_time == MEASURED_PRICE_TIME


def test_real_fixture_yields_no_unknown_lines():
    # If the strict path silently recorded unknowns instead of raising, the
    # round-trip test above would still pass. This one would not.
    assert parse(fixture_text()).unknown_lines == ()


def test_prices_keep_file_order():
    # The file is not sorted. Sorting it here would destroy an observation
    # about how the game writes the cache, so insertion order is preserved.
    keys = list(parse(fixture_text()).prices)
    assert keys == list(MEASURED_PRICES)
    assert keys[0] == 901201
    assert keys[-1] == 901208


def test_price_time_is_timezone_aware_utc():
    snapshot = parse(fixture_text())
    assert snapshot.price_time is not None
    assert snapshot.price_time.tzinfo is not None
    assert snapshot.price_time.utcoffset() == timedelta(0)
    assert snapshot.price_time.timestamp() == MEASURED_EPOCH
    assert snapshot.price_time.isoformat() == "2026-08-09T14:30:00+00:00"


def test_both_known_sections_are_recorded_as_seen():
    snapshot = parse(fixture_text())
    assert snapshot.sections_seen == frozenset(
        {PRICE_TIME_SECTION, TRADE_PRICES_SECTION}
    )
    assert snapshot.has_price_time
    assert snapshot.has_trade_prices_section


def test_load_matches_parse_of_the_same_text():
    assert load(FIXTURE) == parse(fixture_text())


def test_load_of_a_missing_file_raises_rather_than_returning_an_empty_snapshot():
    with pytest.raises(FileNotFoundError):
        load(FIXTURE.parent / "no_such_avgprice.ini")


def test_crlf_input_parses_identically():
    # The measured file is LF, but a copy that has been through a Windows
    # editor is still the same observation.
    assert parse(fixture_text().replace("\n", "\r\n")) == parse(fixture_text())


def test_snapshot_is_frozen():
    snapshot = parse(fixture_text())
    with pytest.raises(FrozenInstanceError):
        snapshot.price_time = None


# ---------------------------------------------------------------------------
# Empty states - the whole point of the measurement doctrine
# ---------------------------------------------------------------------------


def test_empty_shell_is_exactly_the_measured_37_bytes():
    # The file was measured at 37 bytes and called empty. Both section headers
    # plus a ten-digit stamp plus three LFs is exactly 37 bytes, which is what
    # that state was.
    assert len(EMPTY_SHELL.encode("ascii")) == 37


def test_empty_shell_has_a_stamp_and_zero_prices():
    snapshot = parse(EMPTY_SHELL)
    assert snapshot.prices == {}
    assert snapshot.has_price_time
    assert snapshot.has_trade_prices_section
    assert snapshot.price_time == MEASURED_PRICE_TIME
    assert snapshot.unknown_lines == ()


def test_an_absent_section_is_not_the_same_fact_as_an_empty_one():
    # THE distinction this parser exists to preserve. Both snapshots have zero
    # prices. Only one of them has ever been told anything about prices.
    shell = parse(EMPTY_SHELL)
    absent = parse("[PriceTime]\n1786285800\n")

    assert shell.prices == absent.prices == {}
    assert shell.has_trade_prices_section is True
    assert absent.has_trade_prices_section is False
    assert shell != absent


def test_an_empty_file_records_nothing_at_all():
    snapshot = parse("")
    assert snapshot.prices == {}
    assert snapshot.price_time is None
    assert snapshot.has_price_time is False
    assert snapshot.has_trade_prices_section is False
    assert snapshot.sections_seen == frozenset()
    assert snapshot.unknown_lines == ()


def test_whitespace_only_file_is_the_same_as_an_empty_one():
    assert parse("\n\n   \n") == parse("")


def test_blank_lines_inside_a_section_are_not_unknown():
    snapshot = parse("[TradePrices]\n\n901201=26\n\n")
    assert snapshot.prices == {901201: 26}
    assert snapshot.unknown_lines == ()


# ---------------------------------------------------------------------------
# Nothing unrecognised is ever dropped
# ---------------------------------------------------------------------------

MALFORMED = "[PriceTime]\n1786285800\n[TradePrices]\n901201=26\nnot a price row\n903303=41\n"


def test_a_malformed_line_raises_by_default():
    with pytest.raises(AvgPriceParseError) as excinfo:
        parse(MALFORMED)
    message = str(excinfo.value)
    assert "not a price row" in message
    assert "5" in message, "the message must name the 1-based line number"


def test_a_malformed_line_is_recorded_rather_than_dropped_when_not_strict():
    snapshot = parse(MALFORMED, strict=False)
    assert len(snapshot.unknown_lines) == 1
    unknown = snapshot.unknown_lines[0]
    assert isinstance(unknown, UnknownLine)
    assert unknown.text == "not a price row"
    assert unknown.line_no == 5
    assert unknown.section == TRADE_PRICES_SECTION
    assert unknown.reason
    # The rows that did parse are still there, and the caller can see that the
    # result is incomplete instead of having to guess.
    assert snapshot.prices == {901201: 26, 903303: 41}
    assert snapshot.is_complete is False


def test_a_clean_parse_reports_itself_complete():
    assert parse(fixture_text()).is_complete is True


def test_a_non_integer_price_is_not_silently_skipped():
    with pytest.raises(AvgPriceParseError):
        parse("[TradePrices]\n901201=twenty-six\n")


def test_a_row_before_any_section_header_is_loud():
    # configparser's MissingSectionHeaderError case. A row with no section is
    # unattributable, so it is never folded into TradePrices on a hunch.
    with pytest.raises(AvgPriceParseError):
        parse("901201=26\n[TradePrices]\n903303=41\n")


def test_an_unrecognised_section_is_loud():
    # A new section is exactly the schema change worth hearing about.
    with pytest.raises(AvgPriceParseError):
        parse("[PriceTime]\n1786285800\n[SellPrices]\n901201=26\n")


def test_an_unrecognised_section_is_recorded_when_not_strict():
    snapshot = parse(
        "[PriceTime]\n1786285800\n[SellPrices]\n901201=26\n", strict=False
    )
    assert [u.text for u in snapshot.unknown_lines] == ["[SellPrices]", "901201=26"]
    assert snapshot.prices == {}
    assert "SellPrices" not in snapshot.sections_seen


def test_a_bare_value_in_the_wrong_section_is_loud():
    with pytest.raises(AvgPriceParseError):
        parse("[TradePrices]\n1786285800\n")


def test_a_key_value_pair_in_price_time_is_loud():
    with pytest.raises(AvgPriceParseError):
        parse("[PriceTime]\nstamp=1786285800\n")


def test_a_comment_line_is_recorded_rather_than_assumed():
    # No comment syntax has ever been observed in this file. Skipping ';' and
    # '#' lines would be inventing a convention the writer may not use, and
    # would silently discard real content the day it turns out to be data.
    with pytest.raises(AvgPriceParseError):
        parse("[TradePrices]\n; average of last 24h\n901201=26\n")


def test_a_duplicate_cfg_id_never_silently_overwrites():
    with pytest.raises(AvgPriceParseError) as excinfo:
        parse("[TradePrices]\n901201=26\n901201=99\n")
    assert "901201" in str(excinfo.value)


def test_a_duplicate_cfg_id_keeps_the_first_value_when_not_strict():
    snapshot = parse("[TradePrices]\n901201=26\n901201=99\n", strict=False)
    assert snapshot.prices == {901201: 26}
    assert len(snapshot.unknown_lines) == 1
    assert snapshot.is_complete is False


def test_a_second_bare_stamp_never_silently_overwrites():
    with pytest.raises(AvgPriceParseError):
        parse("[PriceTime]\n1786285800\n1786285801\n")


def test_an_unconvertible_epoch_is_loud_rather_than_clamped():
    # A stamp this project cannot turn into an instant is a fact about the
    # file, not a reason to invent a datetime.
    #
    # The oversized value is built at runtime rather than written as a literal.
    # tests/test_no_pii.py scans every tracked file with the redactor's own
    # detectors, and its LONG_ID rule fires on any bare run of 15+ digits - so
    # a literal here would be committed as a permanent false-positive PII hit.
    too_big = "9" * 21
    with pytest.raises(AvgPriceParseError):
        parse(f"[PriceTime]\n{too_big}\n")
