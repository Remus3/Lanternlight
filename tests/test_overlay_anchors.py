"""Tests for overlay.anchors.

Two things are being defended here.

1. The nine anchor positions are exact arithmetic, so they are asserted as
   exact numbers rather than as inequalities. An "x is somewhere on the left"
   assertion passes for a panel hanging off the edge.

2. A panel is never placed at a negative coordinate, whatever the panel size.
   The failure mode this guards is a large panel silently rendering
   off-screen, which looks identical to the overlay not starting.

The safe-zone test carries its own non-vacuity guard: it first asserts that
the RAW anchor positions do collide with the declared zones, so that the
"nothing overlaps" assertion cannot pass merely because the zones are
somewhere harmless. Without that, deleting the whole avoidance algorithm would
leave this file green.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from overlay import anchors  # noqa: E402
from overlay.anchors import (  # noqa: E402
    ANCHORS,
    DEFAULT_SAFE_ZONES,
    Rect,
    SafeZone,
    Size,
    anchor_position,
    overlapping_zones,
    place,
    safe_zones_for,
    split_anchor,
)

SCREEN = Size(2560, 1440)

#: Small enough that it fits in the gaps between the declared HUD zones.
SMALL_PANEL = Size(320, 180)

MARGIN = 24


# ---------------------------------------------------------------------------
# the nine anchors
# ---------------------------------------------------------------------------


def test_there_are_exactly_nine_anchors_and_they_are_unique():
    assert len(ANCHORS) == 9
    assert len(set(ANCHORS)) == 9
    assert ANCHORS[0] == "top-left"
    assert ANCHORS[-1] == "bottom-right"


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        # x: margin / centred / screen - panel - margin
        # y: margin / centred / screen - panel - margin
        ("top-left", (24, 24)),
        ("top-center", (1120, 24)),
        ("top-right", (2216, 24)),
        ("middle-left", (24, 630)),
        ("middle-center", (1120, 630)),
        ("middle-right", (2216, 630)),
        ("bottom-left", (24, 1236)),
        ("bottom-center", (1120, 1236)),
        ("bottom-right", (2216, 1236)),
    ],
)
def test_every_anchor_lands_on_its_exact_pixel(anchor, expected):
    assert anchor_position(SCREEN, SMALL_PANEL, anchor, MARGIN) == expected


def test_all_nine_anchors_are_covered_by_the_exact_pixel_test():
    # If someone adds a tenth anchor, the parametrised test above silently
    # stops covering the full set. This makes that a failure.
    covered = {
        "top-left",
        "top-center",
        "top-right",
        "middle-left",
        "middle-center",
        "middle-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    }
    assert covered == set(ANCHORS)


def test_every_anchor_keeps_a_small_panel_fully_on_screen():
    for anchor in ANCHORS:
        x, y = anchor_position(SCREEN, SMALL_PANEL, anchor, MARGIN)
        assert x >= 0, (anchor, x)
        assert y >= 0, (anchor, y)
        assert x + SMALL_PANEL.width <= SCREEN.width, (anchor, x)
        assert y + SMALL_PANEL.height <= SCREEN.height, (anchor, y)


def test_split_anchor_round_trips_every_name():
    for anchor in ANCHORS:
        vertical, horizontal = split_anchor(anchor)
        assert f"{vertical}-{horizontal}" == anchor


@pytest.mark.parametrize(
    "bad", ["", "left", "top", "centre", "top_left", "TOP-LEFT", "bottom-middle"]
)
def test_unknown_anchor_raises_rather_than_defaulting(bad):
    with pytest.raises(ValueError, match="unknown anchor"):
        anchor_position(SCREEN, SMALL_PANEL, bad, MARGIN)


# ---------------------------------------------------------------------------
# margins
# ---------------------------------------------------------------------------


def test_margin_moves_the_edge_anchors_and_not_the_centre():
    tight = anchor_position(SCREEN, SMALL_PANEL, "top-left", 0)
    loose = anchor_position(SCREEN, SMALL_PANEL, "top-left", 100)
    assert tight == (0, 0)
    assert loose == (100, 100)

    # A centred panel that respected the margin would not be centred, so the
    # margin must not move it at all.
    centred_tight = anchor_position(SCREEN, SMALL_PANEL, "middle-center", 0)
    centred_loose = anchor_position(SCREEN, SMALL_PANEL, "middle-center", 300)
    assert centred_tight == centred_loose == (1120, 630)


def test_margin_is_taken_off_the_far_edge_too():
    x, y = anchor_position(SCREEN, SMALL_PANEL, "bottom-right", 100)
    assert x == SCREEN.width - SMALL_PANEL.width - 100
    assert y == SCREEN.height - SMALL_PANEL.height - 100


def test_negative_margin_is_rejected():
    with pytest.raises(ValueError, match="margin must be non-negative"):
        anchor_position(SCREEN, SMALL_PANEL, "top-left", -1)


# ---------------------------------------------------------------------------
# oversized panels - clamp, never go negative
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "panel",
    [
        Size(3000, 2000),  # bigger on both axes
        Size(3000, 180),  # bigger horizontally only
        Size(320, 2000),  # bigger vertically only
        Size(2560, 1440),  # exactly the screen
    ],
)
def test_an_oversized_panel_clamps_instead_of_going_negative(panel):
    for anchor in ANCHORS:
        x, y = anchor_position(SCREEN, panel, anchor, MARGIN)
        assert x >= 0, (anchor, panel, x)
        assert y >= 0, (anchor, panel, y)


def test_a_panel_exactly_the_screen_size_sits_at_the_origin():
    for anchor in ANCHORS:
        assert anchor_position(SCREEN, Size(2560, 1440), anchor, MARGIN) == (0, 0)


def test_a_panel_that_fits_without_its_margins_gives_up_the_margins():
    # 2500 + 2 * 100 exceeds 2560, so the margin cannot be honoured, but the
    # panel itself still fits and must stay fully on screen.
    panel = Size(2500, 1400)
    x, y = anchor_position(SCREEN, panel, "bottom-right", 100)
    assert 0 <= x <= SCREEN.width - panel.width
    assert 0 <= y <= SCREEN.height - panel.height


def test_place_also_refuses_to_go_negative_for_an_oversized_panel():
    # The avoidance search must not be able to push a panel off the origin.
    for anchor in ANCHORS:
        x, y = place(SCREEN, Size(3000, 2000), anchor, MARGIN)
        assert (x, y) == (0, 0), anchor


# ---------------------------------------------------------------------------
# safe zones
# ---------------------------------------------------------------------------


def test_rect_overlap_uses_half_open_edges():
    a = Rect(0, 0, 10, 10)
    assert a.overlaps(Rect(9, 9, 10, 10))
    # Flush neighbours share an edge coordinate but no pixel.
    assert not a.overlaps(Rect(10, 0, 10, 10))
    assert not a.overlaps(Rect(0, 10, 10, 10))
    # A zero-area rectangle covers nothing.
    assert not a.overlaps(Rect(5, 5, 0, 0))


def test_the_declared_safe_zones_are_sane():
    assert DEFAULT_SAFE_ZONES, "no safe zones declared at all"
    names = [zone.name for zone in DEFAULT_SAFE_ZONES]
    assert len(names) == len(set(names)), f"duplicate zone name in {names}"
    for zone in DEFAULT_SAFE_ZONES:
        assert zone.rect.width > 0 and zone.rect.height > 0, zone.name
        assert zone.rect.x >= 0 and zone.rect.y >= 0, zone.name
        assert zone.rect.right <= anchors.REFERENCE_SIZE.width, zone.name
        assert zone.rect.bottom <= anchors.REFERENCE_SIZE.height, zone.name
        # The zones are an unverified guess and the note is where each one
        # says so. A zone with no note is a number with no provenance.
        assert zone.note.strip(), zone.name


def test_the_raw_anchor_positions_really_do_hit_the_safe_zones():
    # NON-VACUITY GUARD for the test below. If the declared zones happened to
    # sit where no anchor ever lands, "place() avoids them" would pass with
    # the avoidance algorithm deleted. Assert the problem exists first.
    colliding = [
        anchor
        for anchor in ANCHORS
        if overlapping_zones(
            Rect(*anchor_position(SCREEN, SMALL_PANEL, anchor, MARGIN),
                 SMALL_PANEL.width, SMALL_PANEL.height),
            DEFAULT_SAFE_ZONES,
        )
    ]
    assert len(colliding) >= 5, (
        "the raw anchor positions barely touch the declared HUD zones, so the "
        f"avoidance test below proves little; colliding anchors: {colliding}"
    )


def test_no_anchor_places_a_small_panel_over_a_safe_zone():
    for anchor in ANCHORS:
        x, y = place(SCREEN, SMALL_PANEL, anchor, MARGIN, DEFAULT_SAFE_ZONES)
        rect = Rect(x, y, SMALL_PANEL.width, SMALL_PANEL.height)
        hit = overlapping_zones(rect, DEFAULT_SAFE_ZONES)
        assert not hit, (
            f"anchor {anchor} placed the panel at ({x}, {y}), overlapping "
            f"{[zone.name for zone in hit]}"
        )
        # Avoiding a zone is no good if it walks off the screen doing it.
        assert x >= 0 and x + SMALL_PANEL.width <= SCREEN.width, (anchor, x)
        assert y >= 0 and y + SMALL_PANEL.height <= SCREEN.height, (anchor, y)


def test_place_leaves_an_already_clear_position_untouched():
    # A lone zone in the bottom-right cannot affect a top-left anchor.
    zones = (SafeZone("corner", Rect(2000, 1200, 500, 200), "test fixture"),)
    raw = anchor_position(SCREEN, SMALL_PANEL, "top-left", MARGIN)
    assert place(SCREEN, SMALL_PANEL, "top-left", MARGIN, zones) == raw


def test_place_with_no_zones_is_the_raw_anchor_position():
    for anchor in ANCHORS:
        raw = anchor_position(SCREEN, SMALL_PANEL, anchor, MARGIN)
        assert place(SCREEN, SMALL_PANEL, anchor, MARGIN, ()) == raw


def test_place_moves_the_panel_as_little_as_it_can():
    # One zone straddling the top-left anchor. The cheapest escape is
    # downward, to the zone's bottom edge, not sideways past its full width.
    zones = (SafeZone("bar", Rect(0, 0, 900, 100), "test fixture"),)
    x, y = place(SCREEN, SMALL_PANEL, "top-left", MARGIN, zones)
    assert (x, y) == (24, 100)


def test_place_falls_back_to_the_raw_position_when_nothing_is_clear():
    # A zone covering the entire screen leaves no clear candidate. The
    # documented behaviour is a visible panel over the HUD, not no panel.
    zones = (SafeZone("everything", Rect(0, 0, 2560, 1440), "test fixture"),)
    raw = anchor_position(SCREEN, SMALL_PANEL, "middle-center", MARGIN)
    assert place(SCREEN, SMALL_PANEL, "middle-center", MARGIN, zones) == raw


# ---------------------------------------------------------------------------
# scaling to a non-reference screen
# ---------------------------------------------------------------------------


def test_safe_zones_at_the_reference_resolution_are_returned_unchanged():
    assert safe_zones_for(Size(2560, 1440)) == tuple(DEFAULT_SAFE_ZONES)


def test_safe_zones_scale_proportionally_to_a_smaller_screen():
    half = safe_zones_for(Size(1280, 720))
    assert len(half) == len(DEFAULT_SAFE_ZONES)
    by_name = {zone.name: zone for zone in half}
    reticle = by_name["reticle"]
    assert reticle.rect == Rect(590, 330, 100, 60)
    # The note must survive, and must say the numbers were scaled.
    assert "Scaled from" in reticle.note


def test_scaled_zones_still_keep_a_small_panel_clear_at_1080p():
    screen = Size(1920, 1080)
    panel = Size(240, 140)
    zones = safe_zones_for(screen)
    for anchor in ANCHORS:
        x, y = place(screen, panel, anchor, MARGIN, zones)
        rect = Rect(x, y, panel.width, panel.height)
        assert not overlapping_zones(rect, zones), (anchor, x, y)


# ---------------------------------------------------------------------------
# headless isolation
# ---------------------------------------------------------------------------

_ISOLATION_PROBE = """
import sys
assert "tkinter" not in sys.modules, "tkinter was already loaded at startup"
import overlay.anchors
import overlay.render
leaked = sorted(m for m in sys.modules if m == "tkinter" or m.startswith("tkinter."))
assert not leaked, "overlay.anchors/overlay.render pulled in " + repr(leaked)
print("clean")
"""


def test_importing_anchors_pulls_in_no_tkinter_in_this_interpreter():
    # Cheap in-process check. The subprocess test below is the real one; this
    # one catches the mistake immediately and without process startup cost.
    import overlay.anchors  # noqa: F401

    leaked = sorted(m for m in sys.modules if m == "tkinter" or m.startswith("tkinter."))
    assert not leaked, f"tkinter reached sys.modules: {leaked}"


def test_importing_anchors_pulls_in_no_tkinter_in_a_fresh_interpreter():
    # The in-process check can be defeated by another test, or by pytest
    # itself, having imported tkinter first. A fresh interpreter cannot be.
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
