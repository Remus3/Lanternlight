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
        assert totals == [55, 109, 164, 219, 275, 330, 386, 441, 496, 552]

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
#: independent refuter found it immediately.
#:
#: **Hit 8 (441) was recorded as "genuinely not in the capture at this cadence"
#: and that is now REFUTED - it is at p01216 and p01217.** It was never absent;
#: the reader of the day REFUSED those frames, and a claim about the reader was
#: written down as a claim about the data. Widening VALUE_WINDOW and splitting
#: merged runs made 121 previously-refused frames of this capture readable, and
#: 441 is one of them, so the series is now pinned COMPLETE at all ten values.
#: This repo's own rule, arriving from a new direction: an empty search is a
#: claim about the search.
SECOND_SERIES = (
    ("p01185_19.02.34.191.png", 55, 1),
    ("p01189_19.02.36.427.png", 109, 2),
    ("p01193_19.02.38.651.png", 164, 3),
    ("p01198_19.02.41.443.png", 219, 4),
    ("p01202_19.02.43.672.png", 275, 5),
    ("p01207_19.02.46.460.png", 330, 6),
    ("p01211_19.02.48.692.png", 386, 7),
    ("p01216_19.02.51.472.png", 441, 8),
    ("p01219_19.02.53.145.png", 496, 9),
    ("p01224_19.02.55.931.png", 552, 10),
)


#: A single reviewed frame from the reference capture, redacted down to the
#: pixels `read_panel` actually consumes and committed so a FRESH CLONE can
#: verify a successful read. Derived from `p01146` of the 2026-08-25 capture,
#: which reads 103 with 10 hits in the hand-read floor series.
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "panel_total_103_hits_10.png"


class TestTheCommittedFixture:
    """`ROADMAP 7c`. A clone with no capture could not verify a SUCCESSFUL read.

    That was the honest gap in this module: everything above needs 1.1 GB of
    the operator's screen and skips without it, and everything below is built
    from the same templates the reader scores against, so it cannot prove the
    templates match anything the game rendered. A fresh clone therefore tested
    segmentation and every refusal path, and never once saw the reader get a
    real number right.

    WHY A REDACTED FRAME CLOSES IT RATHER THAN A SYNTHESISED ONE. The pixels
    kept here are REAL, unmodified capture - the game's own rendering of `103`
    and `10`. That is exactly what a synthesised frame cannot supply and what
    makes this a ground-truth test instead of a restatement of the templates.

    WHY IT IS SAFE TO COMMIT, measured rather than asserted. `read_panel` reads
    only :data:`vision_meter.TOTAL_BAND` within two column windows, so 98.69%
    of the frame is irrelevant to it and is blacked out - all of the game scene
    visible through the semi-transparent plate, the white Progress Record row,
    and both headers. What survives is 2,025 pixels showing two orange numbers.
    The source frame was reviewed before selection, carried no PNG text or time
    chunks, and the fixture is renamed so the filename does not carry the
    capture wall-clock. The redaction is not left to trust: the two tests below
    re-derive it from the committed bytes on every run.
    """

    def test_a_clone_can_verify_a_SUCCESSFUL_read_not_only_refusals(self):
        """The gap this fixture exists to close. Never skips."""
        reading = read_panel(FIXTURE)
        assert (reading.total, reading.hits) == (103, 10), (
            f"the committed fixture read {reading.total}/{reading.hits}, not "
            "103/10. Either the reader regressed or the fixture was replaced - "
            "check which before touching either"
        )
        assert reading.progress is None, "the white row is still unread by design"

    def test_the_fixture_stays_redacted_to_the_bands_the_reader_uses(self):
        """A guard on the REDACTION, so it cannot quietly erode.

        If someone later regenerates this fixture from a fuller crop, this goes
        red. Without it the redaction is a one-time act that nothing maintains,
        and the next person to refresh the fixture ships the scene with it.
        """
        Image = _pillow()
        image = Image.open(FIXTURE).convert("RGB")
        top, bottom = vision_meter.TOTAL_BAND
        allowed = set()
        for x0, x1 in (vision_meter.VALUE_WINDOW, vision_meter.HITS_WINDOW):
            for y in range(top, bottom):
                for x in range(x0, x1):
                    allowed.add((x, y))

        px = image.load()
        width, height = image.size
        stray = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if px[x, y] != (0, 0, 0) and (x, y) not in allowed
        ]
        assert not stray, (
            f"{len(stray)} non-black pixel(s) outside the bands read_panel "
            f"uses, first at {stray[0]}. The fixture must carry ONLY the "
            "pixels the reader consumes - everything else is the operator's "
            "screen and does not belong in a public repository"
        )

    def test_the_fixture_carries_no_png_metadata(self):
        """PNG metadata is a leak a visual check cannot see.

        **Widened after a refutation pass caught this guard being narrower than
        its own docstring.** The first version denylisted four chunk names -
        ``tEXt``, ``zTXt``, ``iTXt``, ``tIME`` - and passed on both of these,
        each carrying an arbitrary payload into a public repository:

        * bytes appended AFTER ``IEND``, which the walk simply never reached;
        * a chunk with any other ancillary name, e.g. ``prVt``.

        A denylist of four names is the `LL-0079` shape again - it decides what
        to look for instead of what to allow. So this now ALLOWLISTS the four
        chunk types a redacted screenshot legitimately needs and rejects every
        other, which covers ancillary types nobody has thought of. PNG marks
        ancillary chunks with a lowercase first letter, so an unknown chunk is
        rejected by construction rather than by enumeration.

        The EOF assertion is the other half: a walk that ends early cannot see
        what is past it.
        """
        import struct

        #: The only chunks a plain redacted screenshot needs. PLTE is included
        #: because a future fixture could legitimately be palettised.
        CRITICAL = {"IHDR", "PLTE", "IDAT", "IEND"}

        raw = FIXTURE.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        offset, chunks = 8, []
        while offset < len(raw):
            (length,) = struct.unpack(">I", raw[offset : offset + 4])
            chunks.append(raw[offset + 4 : offset + 8].decode("ascii", "replace"))
            offset += 12 + length

        assert offset == len(raw), (
            f"the chunk walk ended at byte {offset} but the file is "
            f"{len(raw)} bytes - {len(raw) - offset} trailing byte(s) sit past "
            "IEND where no PNG reader will show them and any payload could hide"
        )
        extra = [c for c in chunks if c not in CRITICAL]
        assert not extra, (
            f"fixture carries non-essential PNG chunk(s): {extra}. Only "
            f"{sorted(CRITICAL)} belong in a redacted screenshot; anything else "
            "can carry text, timestamps or arbitrary bytes into a public repo"
        )


class TestSynthesisedFrames:
    """Geometry and every refusal path, without needing the capture."""

    def _frame(self, value="103", hits="10", field_ink=True):
        Image = _pillow()
        image = Image.new("RGB", (500, 310), (20, 20, 24))
        px = image.load()
        if field_ink:
            self._draw(px, value, vision_meter.VALUE_WINDOW[0] + 3, "value")
            # +3, not +4. At +4 a two-digit synthetic value spilled to x224,
            # one column OUTSIDE the window, where real two-digit ink stops at
            # 222-223. That was a fixture artifact - the binarised prototypes
            # are fatter than real ink - and it tripped the EDGE_LOOKAHEAD
            # guard on a frame that models a perfectly legal reading.
            self._draw(px, hits, vision_meter.HITS_WINDOW[0] + 3, "hits")
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


#: The 1.0.15 full-screen capture, and the human transcription taken off it.
#:
#: These frames are 2560x1440 full-scene PNGs rather than the 500x310 panel
#: crops the reader was built for, so they test something the reference capture
#: cannot: that the geometry is a property of the HUD and not of a purpose-built
#: crop. The transcription is the cycle-34 reading, taken by eye before any
#: reader was pointed at these frames, so it is ground truth this module did not
#: get to choose - the same standard as FINDINGS section 11.
FULLSCREEN = Path("C:/ll-captures/2026-08-30/frames")
TRANSCRIPTION = Path("C:/ll-captures/2026-08-30/meter_transcription_cycle34.csv")

#: Where the 500x310 panel sits inside a 2560x1440 frame. Measured, and
#: tolerant across x 2058-2064 after ROADMAP 7d - it read 2056-2061 before,
#: which was wrong at both ends; y 390 is the best row of five swept, and every
#: offset gave ZERO disagreements, so vertical misalignment costs readings and
#: never produces a wrong one.
FULLSCREEN_CROP_ORIGIN = (2058, 390)


def _require_fullscreen():
    if not FULLSCREEN.is_dir():
        pytest.skip(f"1.0.15 capture not on this machine: {FULLSCREEN}")
    if not TRANSCRIPTION.is_file():
        pytest.skip(f"human transcription not on this machine: {TRANSCRIPTION}")


def _panel_up_rows():
    """The transcribed panel-up frames, as (filename, total, hits)."""
    import csv

    with TRANSCRIPTION.open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["panel_state"] == "up"]
    return [(r["frame"], int(r["live_total"]), int(r["live_hits"])) for r in rows]


def _crop_fullscreen(name):
    Image = _pillow()
    x, y = FULLSCREEN_CROP_ORIGIN
    return Image.open(FULLSCREEN / name).convert("RGB").crop((x, y, x + 500, y + 310))


class TestTheFullScreenCapture:
    """ROADMAP 7c's acceptance: read the 124, and never misread one.

    **The reader USED to go blind at 1000**, because the meter renders a
    thousands separator - a 3px column run against ``MIN_GLYPH_WIDTH`` 6 - and
    every four-digit frame was refused. It failed safe, but it bit where it
    hurt: a long run is the run that crosses 1000, and a long run is what a
    distance sweep produces.

    Closed 2026-09-01d by widening ``VALUE_WINDOW``, teaching the separator and
    splitting merged runs. **54 of the 55 four-digit frames now read**, and 118
    of the 124 overall, with ZERO disagreements.

    This docstring described the BEFORE state in the present tense for two
    commits after the behaviour changed, while a method 130 lines below said
    "54 of the 55 read". A file that contradicts itself is worse than one that
    says nothing, and the class docstring is the half a cold session reads
    first.
    """

    def test_the_transcription_has_the_shape_the_roadmap_records(self):
        """Guard the ground truth itself before trusting it."""
        _require_fullscreen()
        rows = _panel_up_rows()
        assert len(rows) == 124, f"expected 124 panel-up frames, got {len(rows)}"
        tally = {}
        for _name, total, _hits in rows:
            tally[len(str(total))] = tally.get(len(str(total)), 0) + 1
        assert tally == {1: 20, 2: 7, 3: 42, 4: 55}, (
            f"digit-length tally moved: {tally}"
        )

    def test_no_panel_up_frame_is_ever_MISREAD(self):
        """ZERO DISAGREEMENTS. The property that may never be traded.

        A refusal and a wrong number are not two grades of the same failure.
        A refusal is a required behaviour of this module; a wrong number is the
        thing it exists to prevent, and it is indistinguishable from a
        measurement once it reaches a document. So this is asserted on its own,
        with nothing else in the test that could go red first and mask it.
        """
        _require_fullscreen()
        disagreements = []
        for name, total, hits in _panel_up_rows():
            try:
                reading = read_panel(_crop_fullscreen(name))
            except Unreadable:
                continue
            if (reading.total, reading.hits) != (total, hits):
                disagreements.append(
                    (name, (total, hits), (reading.total, reading.hits))
                )
        assert disagreements == [], (
            f"{len(disagreements)} frames DISAGREED with the human "
            f"transcription: {disagreements[:5]}"
        )

    def test_the_refusals_are_exactly_the_six_frames_with_a_measured_reason(self):
        """118 of 124 read. The six that do not are PINNED BY NAME.

        Naming them is what stops this from being a weakened test. A seventh
        refusal fails it, and so does one of the six starting to read - either
        direction is a change worth noticing rather than a threshold quietly
        absorbing it. Every one is an ink-quality or registration limit of the
        frame, and NONE is a segmentation failure:

        - ``f0661`` carries ZERO orange pixels anywhere in the band. The
          transcription itself flags it not legible and a human read it at 8x.
          Refusing is correct and no window or template can change it.
        - ``f0469`` and ``f0470`` catch the panel sliding IN, vertically
          misregistered: the glyphs sit at rows 97-116 where every accepted
          glyph in both captures sits at 100-101/117-118. A +2px shift scores
          them 0.0601 at margin 0.0910, so a registration search would recover
          them - and would also be a search for an alignment that makes a glyph
          match, which is a different fix with a different risk. ROADMAP 7c
          carries it as an open item rather than this module carrying it now.
        - ``f0527``, ``f0537`` and ``f0581`` are dithered or smeared transition
          frames with a glyph scoring 0.122 to 0.165 against an accept bound of
          0.115. It is the LEADING glyph on ``f0527`` (x54-66) and ``f0581``
          (x55-64); on ``f0537`` it is the MIDDLE digit at x69-78, the ``1`` of
          618, whose runs are (54,65) (69,78) (82,92). Two of the three are
          within 0.007 of accepting, which is exactly the band the
          two-threshold design exists to refuse.
        """
        _require_fullscreen()
        expected = {
            "f0469_00.41.12.png",
            "f0470_00.41.14.png",
            "f0527_00.42.36.png",
            "f0537_00.42.50.png",
            "f0581_00.43.50.png",
            "f0661_00.45.40.png",
        }
        refused = set()
        for name, _total, _hits in _panel_up_rows():
            try:
                read_panel(_crop_fullscreen(name))
            except Unreadable:
                refused.add(name)
        assert refused == expected, (
            f"refusal set moved - newly refusing {sorted(refused - expected)}, "
            f"newly reading {sorted(expected - refused)}"
        )
        assert len(_panel_up_rows()) - len(refused) == 118

    def test_the_refusal_band_prevents_three_REAL_misreads(self, monkeypatch):
        """The guards are LOAD-BEARING here, and that is measured not asserted.

        It would be easy to read the six refusals as a threshold being timid,
        and to widen a constant until 124 of 124 came back. Disabling the
        accept band and the ambiguity margin does exactly that - the reader
        returns 123 of 124 - and THREE of them are wrong:

        | frame | true | read with the guards off |
        |---|---|---|
        | ``f0527`` | 261 | 262 |
        | ``f0537`` | 618 | 633 |
        | ``f0581`` | 1834 | **3334** |

        The last is wrong in the LEADING digit, a 1500-unit error that would
        sit unremarked in a damage series. On ``f0581`` the two candidates tie
        at 0.165 to three decimals and the true digit is neither of them.

        So the count that matters is not how many frames read - it is that no
        frame is misread. This test fails if a future pass widens a constant to
        chase the last few frames.
        """
        _require_fullscreen()
        monkeypatch.setattr(vision_meter, "ACCEPT_DISTANCE", 0.199)
        monkeypatch.setattr(vision_meter, "AMBIGUITY_MARGIN", 0.0)
        truth = {name: total for name, total, _h in _panel_up_rows()}
        for name in (
            "f0527_00.42.36.png",
            "f0537_00.42.50.png",
            "f0581_00.43.50.png",
        ):
            got = read_panel(_crop_fullscreen(name)).total
            assert got != truth[name], (
                f"{name} now reads correctly at a loosened threshold, so this "
                "test no longer demonstrates what the guard prevents"
            )

    def test_the_four_digit_frames_are_read(self):
        """The gap this cycle closed, pinned so a regression names itself.

        54 of the 55 read. The one that does not is ``f0581``, a smeared frame
        whose LEADING glyph scores 0.165 - it never reaches the separator, and
        it refused before this work for the same reason it refuses now.
        """
        _require_fullscreen()
        four = [r for r in _panel_up_rows() if r[1] >= 1000]
        assert len(four) == 55, f"expected 55 four-digit frames, got {len(four)}"
        wrong, refused = [], []
        for name, total, hits in four:
            try:
                reading = read_panel(_crop_fullscreen(name))
            except Unreadable:
                refused.append(name)
                continue
            if (reading.total, reading.hits) != (total, hits):
                wrong.append((name, total, f"read {reading.total}/{reading.hits}"))
        assert wrong == [], f"a four-digit frame was MISREAD: {wrong}"
        assert refused == ["f0581_00.43.50.png"], f"refusal set moved: {refused}"


class TestTheThousandsSeparator:
    """A narrow run is only a separator when it sits LOW in the band.

    The measured populations over all 55 four-digit frames of the 1.0.15
    capture, taken inside the module's own row band:

    | property | separator | digit |
    |---|---|---|
    | width | 3-4 | 8-13 |
    | first inked row | 19-20 | 4-6 |
    | height | 6-8 | 17-20 |

    The first inked row is the discriminator - a 13-row gap - and it is the
    axis that stays strong exactly where ink count is weakest, because the
    faintest genuine digit measured (value 618, 18 lit pixels against a median
    of 56) still starts at row 4 and stands 19 rows tall.

    **x position is NOT a discriminator and must never be used as one.** The
    separator occupies x68-72, and 49 genuine digit runs from 2- and 3-digit
    values overlap that span - value 116 puts a real digit at x68-75, the same
    left edge as the comma.
    """

    def _band_blob(self, px, x0, width, row0, row1):
        """Paint orange ink at rows measured RELATIVE to TOTAL_BAND."""
        top = vision_meter.TOTAL_BAND[0]
        for x in range(x0, x0 + width):
            for y in range(top + row0, top + row1 + 1):
                px[x, y] = (230, 140, 40)

    def _frame_with_blob(self, row0, row1, width=3, x0=68):
        Image = _pillow()
        image = Image.new("RGB", (500, 310), (20, 20, 24))
        px = image.load()
        self._band_blob(px, x0, width, row0, row1)
        return image

    def test_a_narrow_run_HIGH_in_the_band_is_still_a_fragment(self):
        """NON-VACUITY. This is the test that keeps the rule honest.

        If the separator rule ever degrades into "skip anything narrow", a
        damaged digit that erodes to a few columns would be silently DROPPED
        and the number would shorten into something that still looks valid.
        That is the exact failure this module exists to prevent, so a narrow
        run at DIGIT height must keep refusing.
        """
        image = self._frame_with_blob(row0=4, row1=22)
        with pytest.raises(Unreadable, match="fragment, not a digit"):
            vision_meter._read_field(image, vision_meter.VALUE_WINDOW, "value")

    def test_a_narrow_run_LOW_in_the_band_is_taken_as_a_separator(self):
        """The comma's own geometry: 3px wide, rows 20-26 of the band."""
        image = self._frame_with_blob(row0=20, row1=26)
        with pytest.raises(Unreadable) as caught:
            vision_meter._read_field(image, vision_meter.VALUE_WINDOW, "value")
        assert "fragment, not a digit" not in str(caught.value), (
            "a comma-shaped run was refused as a fragment instead of being "
            "recognised as a thousands separator"
        )

    def test_a_tall_narrow_run_low_in_the_band_is_not_a_separator(self):
        """Height is an independent check, so erosion cannot fake a comma."""
        image = self._frame_with_blob(row0=12, row1=26)
        with pytest.raises(Unreadable, match="fragment, not a digit"):
            vision_meter._read_field(image, vision_meter.VALUE_WINDOW, "value")

    def test_a_one_or_two_pixel_SPECK_low_in_the_band_is_not_a_separator(self):
        """A height FLOOR, which the rule had no test for at all.

        The rule had a height ceiling and no floor, so a 1px speck sitting low
        in the band passed as a thousands separator. Measured across both
        captures, 354 runs fire the predicate without being a comma, at heights
        1x25, 2x27, 3x290, 4x6, 6x2, 7x2, 8x2. **Six of them sit INSIDE the
        genuine comma's range**, so no floor separates the populations cleanly;
        this one removes the short tail, 342 of the 354.

        **The bound is 4, and the first version of it was 5 on a table that
        omitted an offset.** That table swept y=389 to 392 and left out y=388,
        the one offset in this module's own advertised tolerance band where the
        comma is shortest - height 4 in 45 of the 55 four-digit frames. A floor
        of 5 therefore refused 45 real commas there and 6 would have refused all
        55. See ``SEPARATOR_MIN_HEIGHT`` for the full per-offset table.

        This is also why ``SEPARATOR_MIN_ROW`` and ``SEPARATOR_MAX_HEIGHT`` are
        NOT tightened to the comma population: a bound of top>=19 with height
        6-8 and width 3-4 looks tidy and rejects a real comma at y=391 and all
        54 at y=392, destroying the measured property that every offset in
        388-392 yields zero disagreements. Those two constants buy tolerance,
        not discrimination.
        """
        for height in (1, 2, 3):
            image = self._frame_with_blob(row0=20, row1=20 + height - 1)
            with pytest.raises(Unreadable, match="fragment, not a digit"):
                vision_meter._read_field(
                    image, vision_meter.VALUE_WINDOW, "value"
                )

    def test_the_floor_accepts_the_comma_at_its_SHORTEST_measured_offset(self):
        """The floor is pinned from ABOVE by the comma's own worst case.

        ``LL-0116``. The first version of this floor was 5, justified by a
        geometry table that swept y=389 to 392 and OMITTED y=388 - the one
        offset in the module's own advertised 388-392 tolerance band where the
        comma is shortest. At y=388 it is height 4 in 45 of the 55 four-digit
        frames and height 5 in the other 10, so a floor of 5 refused 45 real
        commas and a floor of 6 would refuse all 55.

        Measured minimum across the whole band is 4, so the floor is 4: the
        largest value that never refuses a genuine comma at any offset the
        module claims to tolerate.
        """
        top = 22  # the comma's first inked row at y=388
        for height in (4, 5):
            mask = [
                [top <= y <= top + height - 1 for _ in range(240)]
                for y in range(27)
            ]
            assert vision_meter._is_separator(mask, 68, 70), (
                f"a genuine comma of height {height} at row {top} - its measured "
                "geometry at crop offset y=388 - was refused by the floor"
            )

    def test_a_SHORT_narrow_run_HIGH_in_the_band_is_still_a_fragment(self):
        """The row rule ISOLATED, and the first version of this suite missed it.

        The earlier high-fragment test painted a run 19 rows tall, so the
        HEIGHT check refused it and the row check was never exercised - a
        mutation that deleted the row rule entirely left the suite green. This
        run is 7 rows tall, exactly a comma's height, and differs from a comma
        only in sitting at the top of the band. It is the shape an eroded digit
        actually takes, and it is the case the row rule alone can refuse.
        """
        image = self._frame_with_blob(row0=2, row1=8)
        with pytest.raises(Unreadable, match="fragment, not a digit"):
            vision_meter._read_field(image, vision_meter.VALUE_WINDOW, "value")


class TestTheGroupingRule:
    """Digits are regrouped after a separator, and bad grouping REFUSES.

    This is what would have caught the truncation an adversarial pass shipped
    while implementing the naive fix: with the value window still sized for
    three digits it read a true 2,000 as `2,06`. Two digits after a thousands
    separator is not a number, and refusing it costs nothing.
    """

    def test_a_well_formed_thousands_group_is_accepted(self):
        assert vision_meter._regroup(["1", None, "0", "2", "5"], "value") == "1025"

    def test_a_plain_number_with_no_separator_is_untouched(self):
        assert vision_meter._regroup(["1", "0", "3"], "value") == "103"

    def test_too_few_digits_after_the_separator_is_refused(self):
        """The exact shape of the `2,06` truncation."""
        with pytest.raises(Unreadable, match="grouping"):
            vision_meter._regroup(["2", None, "0", "6"], "value")

    def test_too_many_digits_after_the_separator_is_refused(self):
        with pytest.raises(Unreadable, match="grouping"):
            vision_meter._regroup(["2", None, "0", "6", "1", "4"], "value")

    def test_a_leading_separator_is_refused(self):
        with pytest.raises(Unreadable, match="grouping"):
            vision_meter._regroup([None, "0", "2", "5"], "value")

    def test_a_trailing_separator_is_refused(self):
        with pytest.raises(Unreadable, match="grouping"):
            vision_meter._regroup(["1", "0", "2", "5", None], "value")

    def test_a_group_longer_than_three_before_the_separator_is_refused(self):
        with pytest.raises(Unreadable, match="grouping"):
            vision_meter._regroup(["1", "2", "3", "4", None, "5", "6", "7"], "value")


class TestSplittingAMergedRun:
    """Two glyphs separated by ONE blank column segment as a single run.

    ``_column_runs`` uses ``gap=2`` because the widest intra-glyph gap is 1px,
    so a run only breaks on a gap of 3 or more. One blank column between two
    digits gives ``column - previous == 2``, which is not ``> 2``, so the pair
    merges. The design margin is exactly one column and 18 of the 19 merged
    runs measured have a ``4`` on the left, whose crossbar spills a column
    right.

    **The width gate is what makes splitting safe, not the valley.** Measured
    over the 1.0.15 capture: a run that is definitely ONE glyph is 8-13px in
    the value field and 10-12px in the hit count; a run that is definitely TWO
    is 24-27px, and nothing lands in 14-23 ON THAT CAPTURE. The scope matters
    and ``LL-0113`` was filed for dropping it: on the 6,439-frame 2026-08-25
    capture, 18 value-window runs and 309 hit-window runs DO land in 14-23.
    What carries the gate is a different number - the widest run that ever
    CLASSIFIES as a digit anywhere in that capture is 13px, so a gate at 18
    sits 5px above the widest real glyph.

    **The valley alone would be unsafe** and that is the whole reason for the
    gate: 12 definitely-single glyphs across 9 frames carry an interior blank
    column of their own - 11 of them the digit ``0`` - so a rule that split on
    any interior gap would shred them into 4-7px pieces and lose nine frames
    that currently read correctly.
    """

    def _mask(self, lit_columns, width=240, rows=27):
        """A band mask with the named columns inked over every row."""
        return [[x in lit_columns for x in range(width)] for _ in range(rows)]

    def test_a_merged_pair_splits_at_its_single_blank_column(self):
        mask = self._mask(set(range(53, 65)) | set(range(66, 77)))
        assert vision_meter._split_merged(mask, 53, 76, "value") == [(53, 64), (66, 76)]

    def test_a_single_glyph_carrying_an_interior_gap_is_NOT_split(self):
        """NON-VACUITY against a real frame, and the glyph is the digit ``0``.

        A zero renders as two strokes round a hollow centre, so it carries a
        blank column exactly like a merged pair does. ``f0549`` reads 1,025 and
        its ``0`` is a 10px run at x74-83 with an interior gap - 12 such runs
        exist across the capture. Only the width gate tells them apart, so if
        splitting were ever driven by the valley alone this frame would be
        shredded into 4-5px pieces and refuse.
        """
        _require_fullscreen()
        mask = vision_meter._mask(_crop_fullscreen("f0549_00.43.06.png"))
        gapped = [
            x for x in range(74, 84) if not any(row[x] for row in mask)
        ]
        assert gapped, "the anchor frame no longer has an interior gap at x74-83"
        assert vision_meter.MAX_GLYPH_WIDTH >= 10, "a 10px zero must clear the gate"
        reading = read_panel(_crop_fullscreen("f0549_00.43.06.png"))
        assert (reading.total, reading.hits) == (1025, 20)

    def test_the_gate_sits_in_the_measured_gap(self):
        """13px is the widest single glyph, 24px the narrowest merged pair."""
        assert 13 < vision_meter.MAX_GLYPH_WIDTH < 24

    def test_a_wide_run_with_no_interior_gap_is_refused(self):
        """No valley means no defensible split point, so refuse."""
        mask = self._mask(set(range(53, 77)))
        with pytest.raises(Unreadable, match="interior gap"):
            vision_meter._split_merged(mask, 53, 76, "value")

    def test_a_wide_run_with_two_interior_gaps_is_refused(self):
        """Three glyphs merged were never observed - refuse, do not presume."""
        mask = self._mask(
            set(range(53, 60)) | set(range(61, 68)) | set(range(69, 77))
        )
        with pytest.raises(Unreadable, match="interior gap"):
            vision_meter._split_merged(mask, 53, 76, "value")

    def test_a_piece_that_is_STILL_too_wide_after_splitting_is_refused(self):
        """The splitter must guarantee its own postcondition.

        A 24-27px run is two glyphs. A 30-57px run is something else - three
        merged glyphs, or scene bleed welding a row together - and splitting it
        once leaves a piece that is still far too wide to be one digit. Nine
        such pieces exist in the 2026-08-25 capture, 22 to 54px. Six reach this
        postcondition; the other three refuse earlier, on no ink, a 5px
        fragment and the bleed ceiling.

        **"All six were caught by the distance threshold at 0.1489" was written
        here and is WRONG on two counts.** 0.1489 is one piece, ``p05718``.
        Force-scored, the six break down as: ``p05718`` refusing on the
        over-wide piece itself (0.1489); ``p02435``, ``p02722``, ``p03302`` and
        ``p05611`` refusing on the SIBLING piece first, which is scanned before
        the over-wide one (0.1511, 0.1200, 0.1264, 0.1278); and ``p06217`` at
        0.2115, which is past ``REJECT_DISTANCE`` and so refuses as "matched no
        digit" rather than in the accept band at all.

        The point survives and is narrower than the slogan: before this
        postcondition existed, an over-wide piece was left to whatever the
        distance machinery happened to do with it or with its neighbour, and
        that is not a guarantee a splitter should be relying on.

        That is one guard where the design intends two, and the distance
        threshold is the guard most likely to move. The splitter now refuses a
        piece it cannot vouch for, by name.
        """
        mask = self._mask(set(range(50, 74)) | set(range(75, 100)))
        with pytest.raises(Unreadable, match="still wider than"):
            vision_meter._split_merged(mask, 50, 99, "value")

    def test_a_piece_too_NARROW_after_splitting_is_refused(self):
        """The other half of the same postcondition."""
        mask = self._mask(set(range(50, 53)) | set(range(54, 74)))
        with pytest.raises(Unreadable, match="narrower than"):
            vision_meter._split_merged(mask, 50, 73, "value")

    #: The nine frames of the 2026-08-25 capture that produce an over-wide
    #: piece, found by scanning column RUNS directly. Under the full
    #: ``read_panel`` pipeline only six reach the splitter - the other three are
    #: refused earlier, by the no-ink check, the fragment check and the bleed
    #: ceiling. Both counts are exact and they answer different questions, so
    #: the criterion is published beside each rather than one being picked.
    OVERWIDE_PIECE_FRAMES = (
        ("p02435_19.14.09.936.png", "still wider than"),
        ("p02722_19.16.49.669.png", "still wider than"),
        ("p03302_19.22.12.802.png", "still wider than"),
        ("p03758_19.26.26.506.png", "panel is not up"),
        # Was "fragment, not a digit" until ROADMAP 7d. It has stray ink at
        # x120-127, immediately RIGHT of the value window, so EDGE_LOOKAHEAD
        # now refuses it earlier and for a truer reason - a digit really has
        # been pushed out of this field.
        ("p03763_19.26.29.270.png", "outside the x40-119 window"),
        ("p03827_19.27.04.914.png", "scene is bleeding"),
        ("p05611_19.43.48.662.png", "still wider than"),
        ("p05718_19.44.48.996.png", "still wider than"),
        # Was "still wider than" until ROADMAP 7d. Stray ink at x32-39, this
        # time on the LEFT. This one COSTS COVERAGE and the loss is recorded
        # rather than hidden: it no longer reaches the splitter postcondition,
        # so that guard is now exercised by 5 real frames rather than 6.
        ("p06217_19.49.29.035.png", "outside the x40-119 window"),
    )

    def test_every_overwide_frame_refuses_and_names_its_reason(self):
        """All nine refuse; FIVE of them at the splitter postcondition.

        It was six until ROADMAP 7d added ``EDGE_LOOKAHEAD``, which refuses
        ``p06217`` earlier on stray ink to the LEFT of the value window. The
        frame still refuses - no reading was gained or lost anywhere in the
        6,439 - but one fewer real frame now reaches the splitter's own
        postcondition, and shrinking coverage is worth saying out loud rather
        than quietly re-pointing the assertion.

        Before this guard existed, the six were caught by the DISTANCE
        threshold alone at 0.1489 against an accept bound of 0.115. They still
        refuse either way - the point is that they now refuse for a reason the
        module can state, behind a guard that does not move when a distance
        constant is retuned.
        """
        _require_capture()
        for name, expected in self.OVERWIDE_PIECE_FRAMES:
            frame = PANEL / name
            assert frame.is_file(), f"cited frame missing: {frame}"
            with pytest.raises(Unreadable) as caught:
                read_panel(frame)
            assert expected in str(caught.value), (
                f"{name}: expected {expected!r}, got {str(caught.value)!r}"
            )


def _rows_with_state(state):
    """The transcribed rows in one panel state, as (filename, total, hits)."""
    import csv

    with TRANSCRIPTION.open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["panel_state"] == state]
    if state != "up":
        return [(r["frame"], None, None) for r in rows]
    return [(r["frame"], int(r["live_total"]), int(r["live_hits"])) for r in rows]


def _fullscreen_frame(name):
    """One full 2560x1440 frame, UNCROPPED - what read_frame is given."""
    Image = _pillow()
    return Image.open(FULLSCREEN / name).convert("RGB")


class TestConsensusRegistration:
    """ROADMAP 7c's OPTIONAL registration search, done as CONSENSUS instead.

    ``f0469`` and ``f0470`` are refused by the single shipped offset while the
    panel is still animating in. **They do not "sit 2px high", which is what
    ``ROADMAP`` 7c said and what an earlier draft of this file repeated without
    measuring it.** Measured 2026-09-02: both read at y=389 and REFUSE at 388
    and 392, so the effective offset is 1px, not 2. And it is not a translation
    at all - their value ink band is rows (2, 21), height 20, against (5, 23),
    height 19, on a settled frame: 3px at the top, 2px at the bottom, one row
    TALLER. The panel is SCALING in, not sliding. The hits band is (3, 20) on
    both, unshifted, which is why a 2px row refuses on hits rather than value.

    The item warned that a shift
    SEARCH is a different fix with a worse risk profile: scoring the same glyph
    at offset after offset until one matches multiplies scoring attempts and
    erodes the margin guarantee.

    So this does not search. It reads at every offset and requires the readings
    to AGREE, and a conflict is a REFUSAL rather than a tie broken in favour of
    whichever offset scored best. That makes it strictly a NEW GUARD rather than
    a relaxed one - two offsets returning different numbers is a refusal trigger
    that did not exist before, and on this capture it has never fired.

    ``read_panel`` is deliberately untouched: the 2026-08-25 reference capture
    is 6,439 pre-cropped panels with no offset to vary, so consensus is a
    property of reading a FULL-SCREEN frame and belongs in its own function.
    """

    def test_it_reads_at_least_120_of_the_124(self):
        """The acceptance figure. Single-offset reads 118."""
        _require_fullscreen()
        read = [
            name
            for name, _total, _hits in _panel_up_rows()
            if _tries(_fullscreen_frame(name)) is not None
        ]
        assert len(read) >= 120, f"consensus read only {len(read)} of 124"

    def test_no_panel_up_frame_is_ever_MISREAD(self):
        """ZERO DISAGREEMENTS against the human transcription.

        Asserted on its own, with nothing else in the test that could go red
        first and mask it. Offsets agreeing with EACH OTHER is not the property
        that matters - they could agree on a wrong number. This checks the
        agreed value against the number a human read off the screen.
        """
        _require_fullscreen()
        wrong = []
        for name, total, hits in _panel_up_rows():
            got = _tries(_fullscreen_frame(name))
            if got is not None and (got.total, got.hits) != (total, hits):
                wrong.append((name, (total, hits), (got.total, got.hits)))
        assert wrong == [], f"consensus MISREAD {len(wrong)} frames: {wrong[:5]}"

    def test_it_recovers_the_two_frames_the_panel_slide_cost_us(self):
        """The whole point of the item. Both read at y=389 only."""
        _require_fullscreen()
        for name, total, hits in (
            ("f0469_00.41.12.png", 0, 0),
            ("f0470_00.41.14.png", 0, 0),
        ):
            assert (FULLSCREEN / name).is_file(), f"cited frame missing: {name}"
            with pytest.raises(Unreadable):
                read_panel(_crop_fullscreen(name))
            got = vision_meter.read_frame(_fullscreen_frame(name))
            assert (got.total, got.hits) == (total, hits), f"{name}: got {got}"

    def test_a_DISAGREEMENT_refuses_rather_than_picking_a_winner(self):
        """The new guard. It has never fired on real data, so force it.

        This is the property that makes consensus safer than a search. If this
        ever starts returning a value instead of raising, the function has
        silently become the alignment search the ROADMAP item rejected.
        """
        Image = _pillow()
        seen = []

        def fake_read_panel(crop):
            seen.append(crop)
            return vision_meter.PanelReading(
                total=1234 if len(seen) == 1 else 9999, hits=5
            )

        original = vision_meter.read_panel
        vision_meter.read_panel = fake_read_panel
        try:
            with pytest.raises(Unreadable) as caught:
                vision_meter.read_frame(Image.new("RGB", (2560, 1440)))
        finally:
            vision_meter.read_panel = original
        assert len(seen) > 1, "consensus must consult more than one offset"
        assert "DISAGREE" in str(caught.value), f"got {str(caught.value)!r}"

    def test_no_panel_DOWN_frame_produces_a_reading(self):
        """0 of 231. Reading more offsets must not invent a panel."""
        _require_fullscreen()
        read = [
            name
            for name, _t, _h in _rows_with_state("down")
            if _tries(_fullscreen_frame(name)) is not None
        ]
        assert read == [], f"{len(read)} panel-down frames produced a reading: {read[:5]}"

    def test_every_row_in_the_band_is_safe_ON_ITS_OWN(self):
        """Pins BOTH ends of FRAME_CONSENSUS_ROWS, which nothing else did.

        Shrinking the band to ``(389, 390, 391)`` left every other test in this
        class green, so the two outer rows were pinned by nothing at all. They
        are not there for throughput - 388 and 392 read far fewer frames than
        390 - they buy CROP TOLERANCE, so the property worth pinning is that
        each row is safe ALONE, not that it is productive.
        """
        _require_fullscreen()
        assert vision_meter.FRAME_CONSENSUS_ROWS == (388, 389, 390, 391, 392)
        x = vision_meter.FRAME_PANEL_X
        w, h = vision_meter.PANEL_SIZE
        wrong, reads = {}, {}
        for name, total, hits in _panel_up_rows():
            full = _fullscreen_frame(name)
            for y in vision_meter.FRAME_CONSENSUS_ROWS:
                try:
                    got = read_panel(full.crop((x, y, x + w, y + h)))
                except Unreadable:
                    continue
                reads[y] = reads.get(y, 0) + 1
                if (got.total, got.hits) != (total, hits):
                    wrong.setdefault(y, []).append(name)
        assert wrong == {}, f"a row in the band MISREAD: {wrong}"
        assert all(reads.get(y, 0) > 0 for y in vision_meter.FRAME_CONSENSUS_ROWS), (
            f"a row in the band reads nothing at all: {reads}"
        )

    def test_a_frame_too_small_for_the_crop_refuses(self):
        """A short frame must not silently read a black padded crop."""
        Image = _pillow()
        with pytest.raises(Unreadable) as caught:
            vision_meter.read_frame(Image.new("RGB", (800, 600)))
        assert "too small" in str(caught.value), f"got {str(caught.value)!r}"


class TestADigitPushedOutsideTheWindow:
    """ROADMAP 7d. A glyph outside a field window was SILENTLY DROPPED.

    ``_read_field`` collected the column runs inside its window and assembled
    whatever it found. It never asked whether the ink STOPPED before the
    window's edge, so a glyph pushed entirely outside was simply not seen and
    the survivors formed a valid number. That is the failure class this whole
    module exists to prevent: not a refusal, a WRONG NUMBER.

    **A PARTIAL cut fails safe and a CLEAN cut fails dangerous**, which is why
    it had no detector. A half-visible glyph scores badly and lands in the
    ambiguity band, so it refuses; a glyph that misses the window entirely
    leaves a clean, confident, wrong reading behind.

    It was live rather than theoretical. Both fields are LEFT-aligned - the left
    ink extent does not move with digit count - so values grow rightward, and
    the hits window had ZERO right margin at two digits, so a third digit lands
    outside it. **That 100 would have read as exactly 10 is a PREDICTION from
    the measured geometry, not an observation** - no capture on this machine
    contains a 3-digit hit count, the largest ``live_hits`` being 50. What IS
    measured is the mechanism, on real ink: a frame whose true hits is 14 reads
    as 1 through a window that cuts the last digit.
    """

    #: A real frame whose true hits is 14, and a window that cuts the '4' off
    #: cleanly. Before the guard this returned 1.
    TRUNCATING_CASE = ("f0539_00.42.52.png", (193, 212), 14)

    #: Crop origins that shift the panel far enough to push a digit out of a
    #: window. Measured 2026-09-02 against the pre-guard module, over the whole
    #: 2046-2070 sweep: {2046: 69, 2047: 9, 2048: 12, 2066: 1, 2068: 17} = 108
    #: WRONG readings across the 124 panel-up frames. An earlier version of this
    #: comment said 30 and listed only the last three, omitting 2046 - the worst
    #: offset - while the assertion below sweeps the full range.
    MISALIGNED_X = (2046, 2047, 2048, 2066, 2068)

    def test_a_cleanly_cut_digit_REFUSES_instead_of_returning_a_number(self):
        """The defect itself, on real captured ink."""
        _require_fullscreen()
        name, window, true_hits = self.TRUNCATING_CASE
        assert (FULLSCREEN / name).is_file(), f"cited frame missing: {name}"
        panel = _crop_fullscreen(name)
        assert vision_meter._read_field(panel, vision_meter.HITS_WINDOW, "hits") == (
            true_hits
        ), "the fixture must read correctly through its REAL window"
        with pytest.raises(Unreadable) as caught:
            vision_meter._read_field(panel, window, "hits")
        assert "outside" in str(caught.value), f"got {str(caught.value)!r}"

    def test_a_MISALIGNED_crop_never_returns_a_wrong_number(self):
        """The property that may never be traded, on the x axis.

        Vertical misalignment was already measured to degrade to refusal and
        never to error. HORIZONTAL misalignment did not: at these three origins
        the reader returned 108 confidently wrong numbers, because a digit had
        been pushed out of the window and the rest still parsed.
        """
        _require_fullscreen()
        Image = _pillow()
        wrong = []
        for name, total, hits in _panel_up_rows():
            frame = Image.open(FULLSCREEN / name).convert("RGB")
            for x in self.MISALIGNED_X:
                try:
                    got = read_panel(frame.crop((x, 390, x + 500, 390 + 310)))
                except Unreadable:
                    continue
                if (got.total, got.hits) != (total, hits):
                    wrong.append((name, x, (total, hits), (got.total, got.hits)))
        assert wrong == [], f"{len(wrong)} WRONG readings at a shifted crop: {wrong[:5]}"

    def test_the_guard_refuses_NO_frame_that_reads_today(self):
        """NEVER REFUSE MEASURED DATA - LL-0116's rule, applied on the way in.

        The tidy version of this guard - refuse when ink touches the window's
        last column - would have refused 8 real frames, because the hits field
        legitimately reaches its last usable column at two digits. This one
        looks OUTSIDE the window instead, where the measured captures are empty.
        """
        _require_fullscreen()
        reads = 0
        for name, total, hits in _panel_up_rows():
            try:
                got = read_panel(_crop_fullscreen(name))
            except Unreadable:
                continue
            reads += 1
            assert (got.total, got.hits) == (total, hits), f"{name} misread"
        assert reads == 118, f"the shipped origin must still read 118, got {reads}"

    def test_a_THREE_DIGIT_hits_value_refuses_AT_THE_LOOKAHEAD(self):
        """A third digit lands outside the window, and this is why it refuses.

        The hits field is LEFT-aligned and its window has ZERO right margin at
        two digits, so the third digit of 100 falls entirely outside it.

        **This fixture did NOT previously read as 10, and an earlier version of
        this test said it did.** Measured against the pre-guard module: it
        refused with "run x199-204 matched no digit". So this pins WHICH guard
        refuses it - the lookahead, naming the pushed side - and not a rescue
        from a wrong number that was never measured on this input. The wrong
        number is real and is demonstrated on REAL ink by the truncating-window
        and misaligned-crop tests above; a synthesised glyph is not evidence
        about what the HUD does.
        """
        frame = TestSynthesisedFrames()._frame(value="103", hits="100")
        with pytest.raises(Unreadable) as caught:
            vision_meter._read_field(frame, vision_meter.HITS_WINDOW, "hits")
        assert "outside" in str(caught.value), f"got {str(caught.value)!r}"
        assert "pushed right" in str(caught.value), f"got {str(caught.value)!r}"

    def test_an_image_too_NARROW_for_the_window_cannot_defeat_the_guard(self):
        """The hole the first version of this guard left open.

        ``_read_field`` clamps ``x_hi`` to the image width. When the image is
        narrower than the window, that clamp SHRINKS the field and then leaves
        the right-hand lookahead with zero columns to scan - so the truncation
        it exists to catch becomes invisible and the survivors are returned as
        a measurement. Measured on real ink before this was closed: a 212px
        crop of a frame whose true hits is 14 returned 1.

        A clamped window is not a narrower field, it is a CUT field.
        """
        _require_fullscreen()
        name, _window, true_hits = self.TRUNCATING_CASE
        panel = _crop_fullscreen(name)
        assert vision_meter._read_field(panel, vision_meter.HITS_WINDOW, "hits") == (
            true_hits
        ), "the fixture must read correctly at full width"
        narrow = panel.crop((0, 0, 212, 310))
        with pytest.raises(Unreadable) as caught:
            vision_meter._read_field(narrow, vision_meter.HITS_WINDOW, "hits")
        assert "narrower than" in str(caught.value), f"got {str(caught.value)!r}"

    def test_the_lookahead_is_bounded_from_BOTH_sides_by_measurement(self):
        """The constant, and why it may not drift in either direction.

        Too small and it misses a displaced glyph; too large and it refuses
        real data because it reaches legitimate panel chrome. Both ends are
        measured, not reasoned about.
        """
        n = vision_meter.EDGE_LOOKAHEAD
        assert n >= 6, (
            "a displaced glyph begins within 6 columns - the largest gap between "
            f"lit columns inside a field is 5 - so {n} could miss one"
        )
        assert n <= 19, (
            "sweeping this constant over the 3,243 frames that read costs zero "
            f"readings up to 19 and loses 3 at 20, so {n} would REFUSE MEASURED "
            "DATA"
        )


def _tries(frame):
    """read_frame, or None when it refuses. Keeps the tests above readable."""
    try:
        return vision_meter.read_frame(frame)
    except Unreadable:
        return None
