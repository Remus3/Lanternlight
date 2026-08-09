"""Tests for overlay.render.

The load-bearing test in this file is the no-reflow one. The panel is read at
a glance mid-combat, so if a row vanishes when its value goes missing, every
row below it shifts and the operator's next glance lands on the wrong number.
That is worse than showing nothing, because it is confidently wrong.

The no-reflow tests are therefore written to fail if the renderer ever drops,
adds, or reorders a line in response to CONTENT rather than SHAPE. They
compare a fully-populated payload against the same payload with values
removed, and assert the line count, the keys and the ordering are identical -
not merely that the count is some expected constant, which would still pass if
the renderer dropped one line and gained another.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from overlay.render import (  # noqa: E402
    DEFAULT_LABEL_WIDTH,
    DEFAULT_VALUE_WIDTH,
    ELLIPSIS,
    FIXED_LINE_COUNT,
    KEY_NOTE,
    KEY_STATUS,
    KEY_TITLE,
    MISSING_VALUE,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_WAITING,
    STYLE_NOTE,
    STYLE_ROW,
    STYLE_ROW_MISSING,
    STYLE_STATUS_ERROR,
    STYLE_STATUS_OK,
    STYLE_STATUS_WAITING,
    STYLE_TITLE,
    STYLES,
    Line,
    Payload,
    Row,
    is_missing,
    line_count,
    render,
    texts,
    truncate,
    waiting_payload,
)

FULL = Payload(
    title="Lanternlight",
    status_text="tailing the game log",
    status=STATUS_OK,
    rows=(
        Row("run state", "in dungeon"),
        Row("map", "Ashen Hollow"),
        Row("class", "Ranger"),
        Row("elapsed", "07:41"),
    ),
    note="log line 12043",
)


def _keys(payload: Payload) -> tuple[str, ...]:
    return tuple(line.key for line in render(payload))


# ---------------------------------------------------------------------------
# the basic shape
# ---------------------------------------------------------------------------


def test_render_emits_title_status_rows_and_note_in_that_order():
    lines = render(FULL)
    assert len(lines) == FIXED_LINE_COUNT + len(FULL.rows)
    assert lines[0].key == KEY_TITLE
    assert lines[1].key == KEY_STATUS
    assert lines[-1].key == KEY_NOTE
    assert lines[0].text == "Lanternlight"
    assert lines[1].text == "tailing the game log"
    assert lines[-1].text == "log line 12043"


def test_every_row_renders_its_label_and_value():
    lines = render(FULL)
    body = texts(lines)[2:-1]
    assert len(body) == 4
    assert body[0].startswith("run state")
    assert body[0].endswith("in dungeon")
    assert body[2].startswith("class")
    assert body[2].endswith("Ranger")


def test_the_label_column_is_padded_so_values_line_up():
    body = texts(render(FULL))[2:-1]
    for text, row in zip(body, FULL.rows, strict=True):
        assert text[:DEFAULT_LABEL_WIDTH] == row.label.ljust(DEFAULT_LABEL_WIDTH)
        assert text[DEFAULT_LABEL_WIDTH:] == row.value


def test_line_count_matches_render_without_rendering():
    assert line_count(FULL) == len(render(FULL))
    assert line_count(Payload("t", "s")) == FIXED_LINE_COUNT


def test_every_emitted_style_is_a_declared_style():
    for payload in (FULL, waiting_payload("no game"), Payload("t", "s", STATUS_ERROR)):
        for line in render(payload):
            assert line.style in STYLES, line


@pytest.mark.parametrize(
    ("status", "expected_style"),
    [
        (STATUS_OK, STYLE_STATUS_OK),
        (STATUS_WAITING, STYLE_STATUS_WAITING),
        (STATUS_ERROR, STYLE_STATUS_ERROR),
    ],
)
def test_status_severity_picks_the_status_style(status, expected_style):
    lines = render(Payload("t", "s", status))
    assert lines[1].style == expected_style


def test_an_unknown_status_is_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown status"):
        Payload("t", "s", "catastrophe")


def test_title_and_note_carry_their_own_styles():
    lines = render(FULL)
    assert lines[0].style == STYLE_TITLE
    assert lines[-1].style == STYLE_NOTE


# ---------------------------------------------------------------------------
# NO REFLOW - the load-bearing contract
# ---------------------------------------------------------------------------


def test_a_missing_value_keeps_its_line_and_shows_a_placeholder():
    partial = Payload(
        title=FULL.title,
        status_text=FULL.status_text,
        status=FULL.status,
        rows=(
            Row("run state", "in dungeon"),
            Row("map", None),  # the value went away
            Row("class", "Ranger"),
            Row("elapsed", "07:41"),
        ),
        note=FULL.note,
    )
    full_lines = render(FULL)
    partial_lines = render(partial)

    assert len(partial_lines) == len(full_lines)
    assert _keys(partial) == _keys(FULL)

    missing_line = partial_lines[3]
    assert missing_line.text.startswith("map")
    assert missing_line.text.endswith(MISSING_VALUE)
    assert missing_line.style == STYLE_ROW_MISSING

    # Every OTHER line must be byte-identical. A renderer that reflowed would
    # show up here even if it happened to keep the count the same.
    for index, (before, after) in enumerate(zip(full_lines, partial_lines, strict=True)):
        if index == 3:
            continue
        assert before == after, index


def test_a_payload_with_every_value_missing_still_renders_every_line():
    empty = Payload(
        title=FULL.title,
        status_text="waiting for the game",
        status=STATUS_WAITING,
        rows=tuple(Row(row.label) for row in FULL.rows),
        note=None,
    )
    lines = render(empty)
    assert len(lines) == len(render(FULL))
    assert _keys(empty) == _keys(FULL)
    for line in lines[2:]:
        assert line.text.endswith(MISSING_VALUE), line


def test_a_missing_note_still_occupies_its_line():
    with_note = render(FULL)
    without_note = render(
        Payload(FULL.title, FULL.status_text, FULL.status, FULL.rows, None)
    )
    assert len(without_note) == len(with_note)
    assert without_note[-1].key == KEY_NOTE
    assert without_note[-1].text == MISSING_VALUE


@pytest.mark.parametrize("value", [None, "", "   ", "\t"])
def test_blank_values_count_as_missing_not_as_a_reading(value):
    assert is_missing(value)
    lines = render(Payload("t", "s", STATUS_OK, (Row("thing", value),)))
    assert lines[2].text.endswith(MISSING_VALUE)
    assert lines[2].style == STYLE_ROW_MISSING


def test_a_present_value_is_not_styled_as_missing():
    lines = render(Payload("t", "s", STATUS_OK, (Row("thing", "0"),)))
    # "0" is falsy as a string is not - a renderer using truthiness would get
    # this wrong and call a real zero reading "missing".
    assert lines[2].style == STYLE_ROW
    assert lines[2].text.endswith("0")


def test_row_count_is_the_only_thing_that_changes_the_line_count():
    one = Payload("t", "s", STATUS_OK, (Row("a", "1"),))
    two = Payload("t", "s", STATUS_OK, (Row("a", "1"), Row("b", None)))
    assert len(render(two)) == len(render(one)) + 1


def test_two_rows_sharing_a_label_keep_distinct_keys():
    payload = Payload("t", "s", STATUS_OK, (Row("dupe", "1"), Row("dupe", "2")))
    keys = [line.key for line in render(payload)]
    assert len(keys) == len(set(keys)), keys


# ---------------------------------------------------------------------------
# truncation
# ---------------------------------------------------------------------------


def test_a_long_value_is_truncated_and_marked():
    long_value = "A" * 200
    lines = render(Payload("t", "s", STATUS_OK, (Row("thing", long_value),)))
    value = lines[2].text[DEFAULT_LABEL_WIDTH:]
    assert len(value) == DEFAULT_VALUE_WIDTH
    assert value.endswith(ELLIPSIS)
    assert value.startswith("A")


def test_a_long_value_does_not_wrap_onto_another_line():
    long_value = "word " * 200
    payload = Payload("t", "s", STATUS_OK, (Row("thing", long_value),))
    assert len(render(payload)) == FIXED_LINE_COUNT + 1


def test_a_long_label_is_truncated_and_still_leaves_a_gap():
    lines = render(Payload("t", "s", STATUS_OK, (Row("L" * 100, "value"),)))
    text = lines[2].text
    label = text[:DEFAULT_LABEL_WIDTH]
    assert len(label) == DEFAULT_LABEL_WIDTH
    assert label.endswith(" "), f"no gap between label and value: {text!r}"
    assert text[DEFAULT_LABEL_WIDTH:] == "value"


def test_long_titles_notes_and_status_lines_are_truncated_too():
    width = DEFAULT_LABEL_WIDTH + DEFAULT_VALUE_WIDTH
    payload = Payload("T" * 300, "S" * 300, STATUS_OK, (), "N" * 300)
    lines = render(payload)
    for line in lines:
        assert len(line.text) <= width, line


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        ("short", 10, "short"),
        ("exactly10!", 10, "exactly10!"),
        ("elevenchars", 10, "elevenc" + ELLIPSIS),
        ("abcdef", 3, "abc"),
        ("abcdef", 4, "a" + ELLIPSIS),
        ("abcdef", 0, ""),
        ("", 5, ""),
    ],
)
def test_truncate_never_exceeds_its_width(text, width, expected):
    result = truncate(text, width)
    assert result == expected
    assert len(result) <= width


# ---------------------------------------------------------------------------
# the degraded payload
# ---------------------------------------------------------------------------


def test_waiting_payload_shows_dashes_rather_than_invented_numbers():
    payload = waiting_payload("game not running")
    lines = render(payload)
    assert payload.status == STATUS_WAITING
    assert lines[1].text == "game not running"
    for line in lines[2:]:
        assert line.text.endswith(MISSING_VALUE), line


def test_waiting_payload_has_the_same_shape_as_a_populated_one():
    labels = tuple(row.label for row in FULL.rows)
    waiting = waiting_payload("game not running", labels=labels)
    assert line_count(waiting) == line_count(FULL)
    assert _keys(waiting) == _keys(FULL)


# ---------------------------------------------------------------------------
# value semantics
# ---------------------------------------------------------------------------


def test_lines_are_comparable_values_so_two_renders_can_be_diffed():
    assert render(FULL) == render(FULL)
    assert Line("a", STYLE_ROW, "k") == Line("a", STYLE_ROW, "k")
    assert Line("a", STYLE_ROW, "k") != Line("b", STYLE_ROW, "k")


def test_negative_widths_are_rejected():
    with pytest.raises(ValueError, match="widths must be non-negative"):
        render(FULL, label_width=-1)


# ---------------------------------------------------------------------------
# headless isolation
# ---------------------------------------------------------------------------

_ISOLATION_PROBE = """
import sys
assert "tkinter" not in sys.modules, "tkinter was already loaded at startup"
import overlay.render
leaked = sorted(m for m in sys.modules if m == "tkinter" or m.startswith("tkinter."))
assert not leaked, "overlay.render pulled in " + repr(leaked)
print("clean")
"""


def test_importing_render_pulls_in_no_tkinter_in_this_interpreter():
    import overlay.render  # noqa: F401

    leaked = sorted(m for m in sys.modules if m == "tkinter" or m.startswith("tkinter."))
    assert not leaked, f"tkinter reached sys.modules: {leaked}"


def test_importing_render_pulls_in_no_tkinter_in_a_fresh_interpreter():
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATION_PROBE],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"isolation probe failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip() == "clean"
