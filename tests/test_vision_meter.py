"""The meter reader must read the real capture, and refuse when it cannot.

``ROADMAP 7c``. Two kinds of test live here and they cover different things.

**Against the real capture.** The frames under
``C:/ll-captures/2026-08-25/panel`` carry series that were read by HAND during
the 2026-08-25 session and written into ``docs/FINDINGS.md`` section 11, so
they are ground truth this reader did not get to choose. Those tests skip when
the capture is not on the machine - it is 1.1 GB of screenshots and can never
be committed, because it is capture of the operator's own screen. A skip is
honest; inventing a synthetic frame and calling it ground truth would not be.

**Against synthesised frames.** Geometry, segmentation, assembly and every
refusal path are exercised on images this module builds, so a fresh clone with
no capture still tests the pipeline rather than skipping everything. These are
deliberately NOT a substitute for the real-frame tests: they are built from the
same templates the reader scores against, so they cannot prove the templates
match reality. Only the capture can do that.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import vision_meter  # noqa: E402
from lanternlight.vision_meter import Unreadable, read_panel  # noqa: E402

PANEL = Path("C:/ll-captures/2026-08-25/panel")

#: The ten frames whose readings reproduce the series recorded by hand in
#: FINDINGS section 11: 10 21 31 41 52 62 72 83 93 103, the damage floor at
#: 10.35 per hit. Pinned by NAME so the test is deterministic and cheap - the
#: alternative is re-scanning 6,439 frames on every run.
GROUND_TRUTH_RUN = (
    ("p01101_19.01.47.446.png", 10, 1),
    ("p01107_19.01.50.783.png", 21, 2),
    ("p01110_19.01.52.455.png", 31, 3),
    ("p01116_19.01.55.793.png", 41, 4),
    ("p01119_19.01.57.461.png", 52, 5),
    ("p01125_19.02.00.804.png", 62, 6),
    ("p01128_19.02.02.471.png", 72, 7),
    ("p01137_19.02.07.473.png", 83, 8),
    ("p01140_19.02.09.137.png", 93, 9),
    ("p01146_19.02.12.471.png", 103, 10),
)


def _require_capture():
    if not PANEL.is_dir():
        pytest.skip(f"reference capture not on this machine: {PANEL}")


def _pillow():
    pytest.importorskip("PIL")
    from PIL import Image

    return Image


class TestTheRealCapture:
    def test_the_hand_read_series_is_reproduced_exactly(self):
        """The acceptance criterion, against frames nobody chose for it.

        This is the whole item: the series in FINDINGS 11 was read by a human
        off tiled screenshots, and the reader has to agree with it digit for
        digit. A reader that agreed only with itself would prove nothing.
        """
        _require_capture()
        read = []
        for name, _total, _hits in GROUND_TRUTH_RUN:
            frame = PANEL / name
            assert frame.is_file(), f"ground-truth frame missing: {frame}"
            reading = read_panel(frame)
            read.append((reading.total, reading.hits))

        assert read == [(t, h) for _n, t, h in GROUND_TRUTH_RUN], (
            "the reader disagreed with the series read by hand in FINDINGS 11"
        )

    def test_the_totals_alone_are_the_documented_floor_series(self):
        _require_capture()
        totals = [read_panel(PANEL / name).total for name, _t, _h in GROUND_TRUTH_RUN]
        assert totals == [10, 21, 31, 41, 52, 62, 72, 83, 93, 103]

    def test_the_second_hand_read_series_is_reproduced_too(self):
        """ROADMAP 7c names TWO series. This is the one I said was absent.

        Both are acceptance criteria for the item, and only the first was pinned
        because the second was wrongly reported missing. Pinning it here is what
        stops that claim being made again from a partial scan.
        """
        _require_capture()
        read = []
        for name, _total, _hits in SECOND_SERIES:
            frame = PANEL / name
            assert frame.is_file(), f"ground-truth frame missing: {frame}"
            reading = read_panel(frame)
            read.append((reading.total, reading.hits))
        assert read == [(t, h) for _n, t, h in SECOND_SERIES]

    def test_the_second_series_totals_match_the_roadmap(self):
        _require_capture()
        totals = [read_panel(PANEL / name).total for name, _t, _h in SECOND_SERIES]
        assert totals == [55, 109, 164, 219, 275, 330, 386, 496, 552]

    def test_a_panel_down_frame_is_refused(self):
        """Presence is decided on the digits, never on brightness.

        The last frame of the capture has ZERO orange pixels while being
        brighter overall than a panel-up frame - bright fraction 0.0668 against
        0.0153. A brightness test would have called it present.
        """
        _require_capture()
        last = sorted(PANEL.glob("*.png"))[-1]
        with pytest.raises(Unreadable, match="panel is not up"):
            read_panel(last)


#: The SECOND series ROADMAP 7c names as ground truth, at about 55 per hit.
#: A 2026-08-27b pass declared this series absent from the capture and wrote that
#: into ROADMAP and LL-0071. That was wrong: the scratch scan sampled every third
#: frame, found a DIFFERENT run that starts at 55, and generalised from one run to
#: the whole directory - a false negative stated as a positive claim. An
#: independent refuter found it immediately. Hit 8 (441) is genuinely not in the
#: capture at this cadence, so it is not pinned.
SECOND_SERIES = (
    ("p01185_19.02.34.191.png", 55, 1),
    ("p01189_19.02.36.427.png", 109, 2),
    ("p01193_19.02.38.651.png", 164, 3),
    ("p01198_19.02.41.443.png", 219, 4),
    ("p01202_19.02.43.672.png", 275, 5),
    ("p01207_19.02.46.460.png", 330, 6),
    ("p01211_19.02.48.692.png", 386, 7),
    ("p01219_19.02.53.145.png", 496, 9),
    ("p01224_19.02.55.931.png", 552, 10),
)


class TestSynthesisedFrames:
    """Geometry and every refusal path, without needing the capture."""

    def _frame(self, value="103", hits="10", field_ink=True):
        Image = _pillow()
        image = Image.new("RGB", (500, 310), (20, 20, 24))
        px = image.load()
        if field_ink:
            self._draw(px, value, vision_meter.VALUE_WINDOW[0] + 3, "value")
            self._draw(px, hits, vision_meter.HITS_WINDOW[0] + 4, "hits")
        return image

    def _draw(self, px, digits, x_start, field):
        """Paint template ink back into a frame at the measured geometry."""
        table = vision_meter._TEMPLATES[field]
        y0, y1 = vision_meter.NORMALISE_ROWS
        height = y1 - y0
        for index, digit in enumerate(digits):
            grid = table[digit][0]
            # 16px advance, not the real 13. A binarised prototype fills more
            # columns than real ink does, so at the real advance two synthetic
            # glyphs touch and segment as one run. Widening it keeps this a test
            # of segmentation rather than of the synthesiser.
            left = x_start + index * 16
            for gy in range(vision_meter.GRID_H):
                for gx in range(vision_meter.GRID_W):
                    if grid[gy][gx] <= 0.18:
                        continue
                    for yy in range(
                        y0 + int(gy * height / vision_meter.GRID_H),
                        y0 + max(int(gy * height / vision_meter.GRID_H) + 1,
                                 int((gy + 1) * height / vision_meter.GRID_H)),
                    ):
                        px[left + gx, yy] = (230, 140, 40)

    def test_a_synthesised_panel_segments_into_the_right_glyph_runs(self):
        """Geometry and segmentation, which synthesis CAN test.

        It cannot test a successful READ. A prototype is an average of many
        anti-aliased glyphs and carries fractional coverage, while a grid cell
        here is about one pixel, so painting a prototype back into a frame
        binarises it and the result no longer scores like a real glyph. Saying
        so is better than tuning the synthesis until a number falls out - that
        would be a test of the synthesiser, not of the reader.

        The successful-read path is covered against the real capture above.
        """
        image = self._frame("103", "10")
        mask = vision_meter._mask(image)
        for window, expected in ((vision_meter.VALUE_WINDOW, 3), (vision_meter.HITS_WINDOW, 2)):
            columns = [
                x for x in range(*window) if any(row[x] for row in mask)
            ]
            runs = vision_meter._column_runs(columns)
            assert len(runs) == expected, f"{window}: {runs}"
            for x0, x1 in runs:
                assert x1 - x0 + 1 >= vision_meter.MIN_GLYPH_WIDTH

    def test_a_frame_with_no_orange_at_all_is_refused(self):
        with pytest.raises(Unreadable, match="panel is not up"):
            read_panel(self._frame(field_ink=False))

    def test_a_scene_bleeding_through_the_plate_is_refused(self):
        """Too MUCH ink is a refusal, not a reading.

        The plate is semi-transparent, so a bright orange scene behind it lights
        the whole band. Measured on the reference capture: one frame carries
        5,368 lit pixels in the band against the 130-290 a rendered number
        produces.
        """
        image = self._frame()
        px = image.load()
        for y in range(vision_meter.TOTAL_BAND[0], vision_meter.TOTAL_BAND[1]):
            for x in range(*vision_meter.VALUE_WINDOW):
                px[x, y] = (230, 140, 40)
        with pytest.raises(Unreadable, match="bleeding through"):
            read_panel(image)

    def test_a_corrupted_glyph_is_refused_rather_than_guessed(self):
        """The two-threshold gap, which is the point of the whole design.

        Half a digit still segments as one column run and still scores closest
        to SOME template. Accepting it would silently turn 103 into another
        perfectly plausible three-digit number, and nothing downstream could
        tell. So the middle band refuses.
        """
        image = self._frame("103", "10")
        px = image.load()
        y0, y1 = vision_meter.NORMALISE_ROWS
        for y in range(y0, y0 + (y1 - y0) // 2):
            for x in range(vision_meter.VALUE_WINDOW[0], vision_meter.VALUE_WINDOW[0] + 20):
                px[x, y] = (20, 20, 24)
        with pytest.raises(Unreadable):
            read_panel(image)

    def test_a_fragment_too_narrow_to_be_a_digit_is_refused(self):
        """Note what this does and does not prove.

        An independent pass measured that neither `MIN_GLYPH_WIDTH` nor
        `BLEED_CEILING` changes a single READING across all 6,439 reference
        frames: the frames they would catch are refused anyway, by "matched no
        digit". So these two tests pin the refusal MESSAGE and the ordering of
        the checks, not an outcome the reader would otherwise get wrong.

        They are kept because a clear refusal reason is what makes a refusal
        actionable, and because a future capture with different framing is
        exactly where a fragment would otherwise be scored. But they are not
        evidence that the constants are load-bearing on this capture.
        """
        image = self._frame(field_ink=False)
        px = image.load()
        for y in range(*vision_meter.NORMALISE_ROWS):
            for x in range(60, 63):
                px[x, y] = (230, 140, 40)
        with pytest.raises(Unreadable, match="narrower than"):
            read_panel(image)


class TestTheDesignHoldsItsShape:
    def test_the_refusal_band_is_a_real_gap(self):
        assert vision_meter.ACCEPT_DISTANCE < vision_meter.REJECT_DISTANCE, (
            "accept must sit below reject or there is no refusal band, and a "
            "damaged glyph would be accepted or silently dropped"
        )

    def test_every_digit_has_at_least_one_prototype_in_both_fields(self):
        for field in ("value", "hits"):
            table = vision_meter._TEMPLATES[field]
            assert set(table) == set("0123456789"), field
            for digit, protos in table.items():
                assert protos, f"{field} '{digit}' has no prototype"

    def test_a_glyph_landing_IN_the_refusal_band_is_refused(self):
        """The two-threshold gap itself, which nothing else here reached.

        Measured while checking this file was not vacuous: the corrupted-glyph
        test above refuses with "matched no digit", i.e. it scores ABOVE the
        reject threshold. That is the wrong side of the design - it would still
        refuse if the accept and reject thresholds were equal, so it proves
        nothing about the gap.

        The gap is what stops a DAMAGED digit from silently truncating a number
        into a shorter one that looks perfectly valid, so it is pinned directly:
        blend one prototype toward another until the best distance lands between
        the thresholds, and require a refusal.
        """
        table = vision_meter._TEMPLATES["value"]
        prototype = table["1"][0]
        found = None
        for step in range(20, 0, -1):
            # Erode the ink, which is the real failure this guard exists for:
            # a glyph whose faint top stroke the colour threshold ate.
            weight = step / 20.0
            eroded = [
                [weight * prototype[y][x] for x in range(vision_meter.GRID_W)]
                for y in range(vision_meter.GRID_H)
            ]
            best = min(
                min(vision_meter._distance(eroded, proto) for proto in protos)
                for protos in table.values()
            )
            if vision_meter.ACCEPT_DISTANCE < best < vision_meter.REJECT_DISTANCE:
                found = eroded
                break

        assert found is not None, (
            "no erosion landed inside the refusal band, so this test cannot "
            "exercise it - the band or the prototypes changed"
        )
        with pytest.raises(Unreadable, match="between accept"):
            vision_meter._classify(found, "value", "blend")

    def test_every_prototype_classifies_as_its_own_digit(self):
        """The template set must be internally separable, and this proves it.

        ROADMAP 7c measured that ten digits produced 430 distinct exact bitmaps
        across the capture, because the plate is semi-transparent and the scene
        behind it moves - so only a tolerant scorer has any chance, and a
        tolerant scorer is exactly the kind that can confuse two digits. This
        runs every prototype back through the real classifier: it must return
        its own digit, which a duplicated, mislabelled or corrupted template
        would fail. It needs no capture, so a fresh clone still tests it.
        """
        for field in ("value", "hits"):
            for digit, protos in vision_meter._TEMPLATES[field].items():
                for index, proto in enumerate(protos):
                    got = vision_meter._classify(proto, field, f"{digit}#{index}")
                    assert got == digit, (
                        f"{field} prototype '{digit}' #{index} classified as {got!r}"
                    )

    def test_the_progress_record_is_reported_unread_not_guessed(self):
        """The white row is a DIFFERENT typeface - see the module docstring.

        Nearest-neighbour labelling of white clusters onto the orange set gives
        margins as low as 0.002, and the reference capture's white hit count
        reads a constant 11 throughout, so there is nothing to harvest from.
        Reporting None is the honest answer; a number would not be.
        """
        assert vision_meter.PanelReading(total=1, hits=1).progress is None
