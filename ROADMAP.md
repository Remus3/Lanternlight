# Lanternlight roadmap

What is actually next, in priority order. Every item carries an acceptance
criterion, because "worked on it" is not a state this project recognises.

Aspirational ideas that nobody has committed to live in [`BACKLOG.md`](BACKLOG.md).
Nothing is moved from there to here without an acceptance criterion attached.

Status vocabulary: **NEXT** (the current item), **READY** (specified, unblocked),
**BLOCKED** (waiting on something named), **OPEN** (a question, not a task).

**Allocating an `OPS-` id: ask, do not count.** Numbering by eye from the OPEN
items is what produced `OPS-12`, because a spent id may have been closed long
ago and be invisible among them.

```
python -c "from ops import ops_ids; print(ops_ids.next_free_id())"
```

It walks this file and `docs/LEDGER.md` at run time, so it cannot go stale.
`tests/test_ops_ids.py` fails if an already-spent id is allocated anyway.

---

## 1. Raid recon pass - PARTLY DONE, remainder is BLOCKED on a real raid

Reframed 2026-08-09 after the data turned out to be on disk already. No capture
session was needed: the operator had played 3h44m and the log had grown from
567 KB to 6.1 MB. Section 7's "unmeasured" was a statement about the world at
08:28, not about the game.

**What is now measured** and written up in `docs/FINDINGS.md` section 9 and
`docs/OBSERVED_IDS.md`: the dungeon lifecycle across two runs, both outcomes
(one disconnect, one successful escape), the escape-portal mechanic, the
`Game.PlayState.*` tag namespace including `Death` and `Escape`, six inventory
opcodes, four loot source contexts, 35 item cfgIds, and the join proving the
live `holding-` id space and the item cfgId space are the same space.

Also corrected here: the game's own nouns are **dungeon** and **escape**. The
words `raid` and `extract` appear **zero** times in the log. A grep for the
wrong word returns a clean negative that means nothing.

**PARTLY REFUTED 2026-08-09c, by an operator attestation plus a log join.** The
operator named the mode - "Hallowgrove, Normal, Solo explore" - and the log was
checked against it immediately. What that overturned:

- **Non-zero `matchId` values EXIST**: `11111` and `11112`. This item's
  acceptance treated "non-zero `matchId`" as a proxy for "a real matchmade
  raid". **That proxy is refuted.** Both belong to *solo explores*. `matchId=0`
  is the Prologue; a solo explore gets a low sequential id. Whatever
  distinguishes a matchmade run, it is not simply a non-zero `matchId`.
- **A better discriminator is available**, straight from the map URL:
  `?levelId=119&roomModeId=0&matchType=1&matchId=11112`. Four axes, not one.
- **A second escape type exists.** `FixEscapeBell` / `WindChime` appears
  alongside `GroveSprite` in one run, so "only one escape type has ever been
  seen" is no longer true.
- **The player-facing and internal names differ.** "Hallowgrove" is the name
  the operator sees; the map loaded is `/Game/Project/Maps/Map_2/Whitewoods_Day`
  with sublevel `WhiteWoods_Level_Easy2`. A grep for the player-facing name
  finds only cosmetics.
- **Match state machine**, observed in order: `onRequestMatch`, `InMatch`,
  `MatchSuccessful`, `EnterBattle`, `NotMatch`.
- **A loot pity system exists** - `OnHandleFirstLoot` carries `dropValue`,
  `dropPity` and `addPityDropValue exceed threshold`. Unmeasured beyond its
  existence; no coefficient is claimed here.

**What is still unmeasured:** a run with another player in it. Everything above
is solo. PvP mechanics remain a clean null.

**And the transient save's trigger is now known.** `StandaloneSlot_<roleId>.sav`
is created at match start and destroyed when the run ends - it is not on a
timer at all. Measured on two independent runs: `matchId=11112` entered battle
at 22:27:00 UTC and the file appeared 17 seconds later at 22:27:17; the run
ended around 22:46 and the file was gone by 22:48:48. The previous session's
file, which appeared at 20:39 UTC, fits `matchId=11111` starting at 20:38:19.
The "about 13 minutes" lifetime was never a timer - it was simply how long that
run lasted. Its producer is named too: `StandaloneLevelCtrl.battleSnapUpdate`
emits battle snapshots throughout, and the controller name matches the file.

**The operator has never been observed dying.** The log's single
`Game.PlayState.Death` belongs to a second player, not to them
(`docs/FINDINGS.md` 9.3). So the original "one run to an extraction, one to a
death" pairing is still half open, and no amount of re-reading this log will
close it.

A second player and PvP analytics events **were** present, so PvP is no longer a
clean null - it is "contact observed, mechanics unmeasured" (`docs/FINDINGS.md`
9.10). That also means captures can contain a third party's identity, which the
safety item above now has to cover.

**Acceptance for the remainder:** a redacted log excerpt from a run with a
**non-zero `matchId`**, committed as a fixture, covering entry, at least one
loot event, and an outcome; plus new `docs/OBSERVED_IDS.md` rows for every id
observed, each with its method named. Confirming or refuting that `matchId=0`
is what distinguishes the Prologue from a real raid is itself a result worth
recording. Blocked only on the operator entering one - nothing here needs a
deliberate capture session any more, because the log is sufficient on its own.

## 2. GVAS `.sav` reader - DECODED 2026-08-09, fixture split out to 2b

Ledger `LL-0011`. `lanternlight/gvas.py` parses every `.sav` file. The save set
keeps growing and any count written here goes stale within the day: four at
first probe, then five, six, seven, and as of 2026-08-09 **eight distinct
names** - `Scav.sav` appeared at 17:51 local mid-session and parses cleanly
with one property, `bIsMaskReward`. A reader must enumerate the directory,
never assume a list. Published
GVAS parsers do not work on this build: UE 5.4+ replaced `FPropertyTag`'s
`FName Type; int32 Size; int32 ArrayIndex` with a recursive type name plus a
flags byte. All 627 trailing bytes of `EnhancedInputUserSettings.sav` decode,
and the result cross-corroborates the log - save and log independently agree
that `KB_Blackarrow_Major_Action` is bound to `RightMouseButton`.

**Reopened the same day.** A seventh save, `StandaloneSlot_<roleId>.sav`,
appeared at 15:39 and does not parse: it uses
`StructProperty<F_PlayzoneSaveData>`, never measured here. The reader **raises**
rather than guessing, which is the correct behaviour and is why this is an open
item rather than a silent partial parse.

It is the real character and progression store's best candidate, and therefore
the most valuable save surface for Emberforge. Its filename also embeds the
operator's roleId, so any fixture must be renamed, not just redacted.

**CAPTURED 2026-08-09, whole lifetime, and three filed claims are corrected.**
A snapshotter was armed at 17:27:14 local, before the file existed. It took
**263 generations** across **105 distinct sizes**, from first appearance to
deletion. The bytes are held outside the repository at `C:\ll-captures\saves\`
and are **not committed** - the filename embeds the operator's roleId.

Measured, first-party, this session:

- **It is not 46 KB.** It appeared at 17:27:17 at **2,190** bytes and was last
  seen at 17:46:54 at **177,878** bytes - about **62 times** the next largest
  save (`UserSettings_v1.sav`, 2,867 bytes), not twenty. The earlier "46 KB"
  was a reading of a file mid-write, mistaken for its size.
- **It is not append-only.** At 17:40:02 it measured 125,765 bytes, *smaller*
  than the 126,078-byte peak recorded 50 seconds earlier. It is rewritten in
  place with a varying size, so a reader must not assume a prefix stays put
  between two polls, and a single snapshot can be a torn read.
- **It does not live about 13 minutes.** It was still being written **19
  minutes 37 seconds** after appearing, and was gone by 17:48:48 - a lifetime
  of roughly 20 to 21 minutes. Whatever removes it is not a simple elapsed-time
  rule from creation. Leaving the mode remains the more likely trigger, and is
  still unmeasured.

None of this was reachable by re-reading a document, and the previous session
lost the file entirely. It came from arming a watcher **before** the file
existed, which is the whole lesson of this item and the reason
`lanternlight/savewatch.py` now exists rather than a scratch script.

**Acceptance - THREE OF FOUR MET 2026-08-09.** Ledger `LL-0019`, `LL-0020`.

- **Decoded.** All **263** captured generations, 105 distinct sizes up to
  177,878 bytes, parse in strict mode with `undecoded_trailing == 0` and zero
  unknown properties. Re-measured by the merger rather than relayed. All seven
  live saves still parse, so nothing regressed.
- **Types recorded.** A struct value is a nested tagged property list closed by
  `"None"` - no epilogue, no inner length, bounded by the tag's `Size`. New:
  `ByteProperty<Enum>` is an FString of the qualified enumerator and **not** a
  raw byte, plus `ArrayProperty`, generic `MapProperty`, and `StructProperty`.
- **Undecoded is named, not guessed.** Natively serialised structs (tag flag
  `0x08`) - `Vector` (24 bytes), `Rotator` (24), `Quat` (32), `Vector2D` (16) -
  come back verbatim as `UndecodedStruct`. 401 leaves, 10,600 bytes, in the
  largest capture. `Vector` and `Rotator` share a width, so they are separable
  only by name: the concrete case against guessing.
- **NOT met: no fixture.** See item 2b - it is safety-lane work, not ingest's,
  and doing it quietly here would be exactly the wrong move.

The reader **raised twice** on genuinely new things mid-work rather than
misreading them - a `MapProperty` keyed by `DoubleProperty`, and `Rotator`.
That is the raise-on-unknown guard validated in the wild for the second time,
which is better evidence than any test.

## 7c. Read the training ground meter without a human reading it - ORANGE PAIR DONE 2026-09-01d, white row still open

Opened 2026-08-25, straight out of the session that measured 10.35. The meter
is the only damage surface the training ground has, and every number in
`docs/FINDINGS.md` section 11 was read by a human looking at tiled screenshots.
That worked and it does not scale: a five-distance sweep cost more attention
than the measurement did, and attention is the thing this project runs out of.

**Tesseract is not installed and is not to be installed for this.** Downloading
a binary to read eight glyphs off a fixed HUD is the wrong trade. The digits
are a fixed font at fixed positions in a fixed rectangle, which is the easiest
possible template-matching problem.

**Acceptance:**

- A reader that takes a captured panel image and returns the total, the hit
  count, and the Progress Record pair, or **refuses**. Refusing is a required
  behaviour, not a fallback - a misread digit is indistinguishable from a
  measurement, which is exactly the failure mode this project's doctrine
  exists to prevent.
- Ground truth for the test comes from this session's capture: the frames under
  `C:/ll-captures/2026-08-25/panel` include series already read by hand and
  written into section 11, so a test can assert the reader reproduces
  `10 21 31 41 52 62 72 83 93 103` and `55 109 164 219 275 330 386 441 496 552`
  from the real frames rather than from synthesised ones.
- **Prove the guard is not vacuous**: feed it a frame where the panel is down
  and assert it refuses, and corrupt one glyph and assert it refuses rather
  than guessing a neighbour.

**Two traps already measured while doing this by hand.** The panel plate is
semi-transparent, so hashing its pixels keys on the scene behind it and reports
a new state on every frame - a coarse column-occupancy signature is what
actually dedupes. And a full-screen poller writes 4.8 MB a frame, 34 GB an
hour; cropping the HUD rectangle at capture time costs about 150 KB a frame and
loses nothing.

### Groundwork MEASURED 2026-08-25b - the naive approach is refuted

A reader was built far enough to find out what does not work, then **removed
from the repository rather than left half-working**, because a reader that
refuses every real frame is worse than no reader. The draft, its templates and
the calibration scripts are kept at
`C:/ll-captures/2026-08-25/meterread-wip/`. What follows is the part worth
having: nobody should pay for these measurements twice.

**The panel geometry, measured off the 6,439 captured crops** (500x310 RGB,
`C:/ll-captures/2026-08-25/panel`):

- Orange **Total Damage** digits occupy rows **y 98-118**; white **Progress
  Record** digits occupy **y 255-273**.
- The value is left-aligned near **x=51**; the hit count near **x=197**
  (orange) or **x=200** (white), so **x=190** separates the two fields.
  **It is NOT empty space** - an earlier draft claimed it was "empty in every
  frame examined" and an independent pass refuted that: **109 of 6,439 frames
  carry ink at x=190**, and 45 orange plus 61 white column runs straddle the
  split. A splitter must therefore tolerate a glyph crossing the boundary
  rather than assume none does.
- Glyphs are **10-12 px wide and 17-21 px tall**, advancing about **12-13 px**.
- **The colours separate the two rows for free:** Total Damage digits are
  orange, Progress Record digits white. The word `Hit` is white in BOTH rows,
  so it never pollutes the orange mask and always pollutes the white one.

**A panel-down frame is not a dark frame.** The last frame of the capture has
**zero** orange pixels while being *brighter* overall than a panel-up frame -
bright fraction 0.0668 against 0.0153. So presence must be decided on the
digits or the headers, never on brightness. The upside: zero orange pixels is
itself a clean, correct refusal trigger.

**Exact template matching is dead on arrival**, and now there is a number for
it: ten digits produced **430 distinct exact bitmaps** across the capture,
because the plate is semi-transparent and the scene behind it moves. Only a
tolerant scorer has any chance.

**The digit shapes ARE cleanly separable, and the templates exist.** Clustering
normalised patches from the orange hit-count field gives **exactly 10**
clusters, and they were labelled two independent ways that agreed on all ten:
by reading the rendered ASCII art, and by the counter itself - seven clusters
first appear at consecutive scan positions and read 1,2,3,4,5,6,7 under the
shape labelling. Those templates are in the wip directory.

**THE DEFECT THAT KILLED THE SIMPLE VERSION: one template set cannot serve
four fields.** Scored against the orange-hit-field templates, the share of
glyphs matching within distance 0.12 was:

| field | n | matched |
|---|---|---|
| orange hit count (where the templates came from) | 367 | **100%** |
| orange total | 599 | **40%** (39.2% unrounded) |
| white progress total | 494 | **9%** |
| white hit count | 432 | **0%** |

The white hit-count row was omitted from an earlier draft of this table. It is
the worst of the four and leaving it out flattered the result.

Two attempts to close that gap, both measured, both insufficient:

- **Normalised cross-correlation made it worse** - orange total fell to 17%.
  So the difference is not a linear intensity scaling.
- **Fixed-row normalisation, a 3x3 blur and a +/-3 row shift search helped and
  did not finish the job** - orange total reached 28% within 0.06, and the
  white fields sat at a stubbornly *consistent* 0.11-0.12. A consistent
  distance is the signature of a systematic rendering difference, not noise.

**The root cause, seen by dumping the art side by side:** in the value field a
glyph's top stroke is rendered fainter, so a hard colour threshold erodes it,
and normalising to the glyph's own ink extent then rescales the whole glyph
against a template built from an uneroded one. The same digit in two fields is
the same shape at a different weight and offset.

**So the next attempt should build one template set PER FIELD.** Each field
sits at a fixed position over a fixed background, which is exactly why the
orange hit field matches its own templates at distance 0.00-0.02. A first pass
at per-field harvesting is also recorded, because it shows the remaining
problem: at a fixed clustering distance of 0.05 the fields gave **11, 13 and 7**
clusters rather than 10, 10 and 10, so **the clustering threshold cannot be a
constant across fields either**. Labelling the extra sets is the tractable part
- map each field's clusters onto the labelled orange set by nearest neighbour
and **require the assignment to be a bijection onto 0-9**, which a wrong
mapping would almost certainly fail.

**None of this changes the acceptance**, and in particular the refusal
requirement now has measured teeth: the two-threshold design (accept below,
reject above, **refuse in between**) is what stops a damaged glyph from
silently truncating a number into a shorter one that would look perfectly
valid.

### PARTLY DONE 2026-08-27b - the ORANGE pair is read; the white pair is refused

`lanternlight/vision_meter.py` reads the Total Damage value and its hit count
off a captured panel crop, and **reproduces the hand-read series exactly**:
`10 21 31 41 52 62 72 83 93 103`, from ten named frames in
`C:/ll-captures/2026-08-25/panel`. Five other floor runs in the same capture
read the same series ending `104` rather than `103` - the rounding tie 10.35
predicts, so that is corroboration rather than disagreement.

**The per-field plan works, and the labelling method in this item did not.**
Clustering per field reproduced the counts recorded above (orange hits exactly
10, orange value 13, white value 7). Labelling those clusters is where two
attempts went wrong:

- The wip's label list is by cluster CREATION ORDER, which is **not portable**
  across harvest runs. Reusing it produced a confident, entirely wrong reading.
- Reading the shapes off rendered ASCII art by eye produced a second wrong set.

What worked is the counter itself. Walking the capture in time order and
recording which cluster follows which gives an unambiguous successor chain, and
the cluster preceding every two-glyph reading is `9`. Walking that chain back
labels all ten, and the assignment is checked as a bijection. A lone cluster
whose successor is `1` turns out to be the meter's `0 Hit` reset state, which
independently confirms the zero. **Derive labels from behaviour, never from
shape.**

**REFUTED - the white row is not the same glyphs at a different weight.** This
item's stated root cause says "the same digit in two fields is the same shape at
a different weight and offset". That holds WITHIN the orange row, where value
clusters label onto the hit-count set with margins of 0.032 to 0.101. It is
false across the colours: the white Progress Record digits carry **wide
bracketed base serifs the orange digits do not have**. Nearest-neighbour
labelling of white clusters onto the orange set returns margins as low as
**0.002**, and the bijection check correctly refuses the mapping.

**The reference capture also cannot supply white templates.** Its white hit
count reads a constant `11` for almost the whole 6,439 frames, so only one digit
shape is available to harvest there - 3 clusters, one of them the letter `t`
from the `Hit` label.

So `read_panel` returns the orange pair and reports `progress=None`. That is the
refusal requirement applied to a whole field rather than a glyph.

**A claim made here on 2026-08-27b was WRONG and is withdrawn.** It said the
second cited series, `55 109 164 219 275 330 386 441 496 552`, was "not in
`panel/`". It is there, at `p01185` to `p01224`, and the reader reproduces it
exactly - 55, 109, 164, 219, 275, 330, 386, 496, 552, with hit 8 simply not
captured at that cadence. Both cited series are now pinned by tests.

**AND THE "hit 8 not captured" HALF OF THAT IS ITSELF NOW WITHDRAWN, measured
2026-09-01d.** 441 IS in the capture, at `p01216_19.02.51.472.png` and
`p01217_19.02.52.028.png`, both reading `441 / 8 Hit` and sitting exactly
between `386 / 7` at `p01211` and `496 / 9` at `p01219`. It was never absent - the
reader of the day REFUSED those frames, because 441's `4` and `1` merge into one
24px column run. Widening the value window and splitting merged runs made 121
previously-refused frames of this capture readable and 441 is one of them, so
the second series is now pinned COMPLETE at all ten values.

**What that claim was measuring, before overturning it (`LL-0100`):** that the
reader of 2026-08-27b could not produce 441 from any frame. That was TRUE of
that reader. The error was generalising from "the reader cannot read it" to "it
is not in the capture" - a claim about the INSTRUMENT written down as a claim
about the DATA. This repo's own rule arriving from a new direction: an empty
search is a claim about the search, and a refusal is a claim about the reader.

The error is worth keeping: the scratch scan sampled every THIRD frame, found a
different run that also starts at 55 (`55 110 166 221 ...`, about 55.6 per hit),
and generalised from that one run to the whole directory. A partial search
produced a false negative, and it was written down as a positive claim about the
capture. An independent refuter found the real run immediately. **An empty
search is a claim about the search.**

**Guards proven non-vacuous - FOUR mutations, each red in a different place:**
closing the accept/reject gap kills 2 tests; disabling the bleed ceiling kills
the bleed test; accepting any glyph width kills the fragment test; swapping two
VALUE template labels kills BOTH ground-truth tests. (Filed as "five" in three
places at first, including the append-only ledger, while enumerating four. The
count is four.)

And one test here was found vacuous while checking: the corrupted-glyph test
refuses with "matched no digit", i.e. it scores ABOVE the reject threshold, so
it would still pass if the two thresholds were equal. The gap now has its own
test that erodes a prototype until it lands inside the band.

**What is left**, and it is the white pair only:

- **Acceptance:** a labelled template set for the white Progress Record digits,
  and `read_panel` returning the pair instead of None. **BLOCKED on a new
  capture** - but read the two sections below in order before acting, because
  the REASON was refuted once and then re-established differently.

### White-row groundwork MEASURED 2026-08-27d - not blocked on data after all

**The "blocked on a capture where the record changes" claim above is REFUTED,
and it was mine.** It generalised from the white HIT COUNT, which really does
read a constant `11` throughout, to the whole row. The white VALUE field varies
freely: **26 distinct values** appear in the reference capture - 104, 123, 158,
231, 264, 265, 309, 350, 438, 531, 546, 552, 556, 559, 651, 684, 687, 689, 690,
692, 705, 799, 817, 818, 896, 980 - and a labelled harvest covers **all ten
digits**. The data was there the whole time.

**Segmentation must be FIXED-PITCH SLOTS, not column runs.** The white glyphs
are 1px-stroke outlines, so a `1` splits into two column runs and the run-based
segmentation that works for the thicker orange digits returns 0, 1, 2, 3, 4, 5
or 7 glyphs for a 3-digit number. Measured slot geometry, from a column
occupancy histogram over the capture:

| field | slots | pitch |
|---|---|---|
| white value | x52, x65, x78 | 13 |
| white hit count | x200, x213 | 13 |

The white `Hit` label starts at **x233** and must never be read as a digit.

**The Progress Record shows the PREVIOUS COMPLETED RUN**, not the best ever, and
that is what makes labelling possible: the orange reader already knows what that
run totalled, so every white patch has a known label and **no clustering is
needed**. Measured - grouping frames by the previous completed run's total gives
a single dominant white pattern in **22 of 26 epochs**, most at 100%. The
best-so-far model was tried first and is refuted by its own output: it makes the
"record" DECREASE, and within one supposed epoch the first slot goes empty, then
a 7-shape, then a 1-shape.

That independently corroborates `LL-0064`, which reached the same conclusion
from a single frame reading `42, 3 Hit` beside `0, 0 Hit`. This is the pixel
evidence for it, and it was in the ledger before this work started.

**Clustering was the wrong tool and is abandoned.** Pooled and per-slot, one
cluster absorbs several digits - cluster 0 alone took 1, 0, 6, 5, 4 and 9 - and
44 clusters emerged for what should be 10 shapes. The strokes are 1px and the
plate is semi-transparent, so the scene behind moves under them.

**What is left is a REPRESENTATION problem, and it is measured.** With templates
averaged per (slot, digit) from the record labels, held-out accuracy is:

| representation | held-out | median margin |
|---|---|---|
| 20x12, 3x3 blur | 58.8% | 0.022 |
| 20x12, no blur | **65.5%** | 0.040 |
| 25x10, no blur | 65.5% | 0.040 |
| 25x10, blur | 59.2% | 0.030 |

Blur HURTS here, the opposite of the orange row, because it destroys 1px
strokes. Grid size is irrelevant, which says the loss is not resolution. The
worst confusions are `1`->`9` (89), `5`->`4` (50) and `6`->`7` (30).

**Nothing shipped from this pass**, deliberately: 65.5% is not a reader, it is a
guesser, and this project would rather have no white row than a wrong one.

### Alignment search done 2026-08-27e - REFUTED, and the real cause is the LABEL

**The alignment hypothesis above is refuted.** Six variants were measured on one
cached mask set and one train/held-out split, so only the alignment varied:

| variant | held-out glyph |
|---|---|
| fixed slot crop (baseline) | 65.5% |
| crop to ink bounding box | 65.4% |
| crop x to ink, fixed rows | 65.5% |
| fixed + dx/dy search when scoring | 63.9% |
| bbox + dx/dy search | 64.2% |
| bbox-x + dx/dy search | 63.9% |

Nothing moves. Neither does the white threshold (61.1% to 63.9% across five
settings from `>165` to `>105`), nor grid size, nor dropping outliers from each
class before averaging.

**The cause is the LABEL, not the pixels, and there are two independent proofs.**

First, two classes are identical: the mean grids for `(slot 0, '1')` and
`(slot 0, '9')` differ by **0.0000**, with 149 and 15 members. Fifteen patches
labelled `9` are averaging to the same thing as 149 labelled `1`, which can only
mean those fifteen frames display a `1`.

Second, excluding frames near a label change fixes it, monotonically:

| frames excluded within N of a label change | glyph | frame-exact | digits covered |
|---|---|---|---|
| 0 | 65.5% | 39.4% | 10 |
| 8 | 76.1% | 51.0% | 10 |
| 12 | 89.2% | 78.3% | 9 |
| 16 | 93.7% | 86.5% | 9 |
| 20 | 94.4% | 89.2% | 9 |
| **25** | **96.8%** | **92.3%** | 9 |
| 30 | 96.5% | 91.7% | 9 |

So the templates and the labelling METHOD are sound. **The measured ceiling is
96.8% per glyph and 92.3% per frame, at a median margin of 0.052** - comfortably
above `AMBIGUITY_MARGIN`. Only the timing of the label is wrong.

**And the timing error is JITTER, not a constant lag.** Shifting the whole label
sequence to model a fixed display lag makes it monotonically worse - 65.5% at
shift 0 down to 46.2% at shift 12 - so the record does not simply appear N
frames late. Detecting the change from the white pixels directly is worse again
(68.2%): it finds **51 segments where there are about 26 records**, because
scene bleed through the semi-transparent plate creates spurious change points.

**Nothing shipped from this pass either.** 92.3% per frame is not a reader.

### Boundary fix done 2026-08-27f - also refuted, and the real limit is the CAPTURE

**The run-boundary hypothesis is refuted too.** Three rules were derived offline
from one cache of raw orange readings, so they were compared on identical
pixels:

| boundary rule | held-out glyph, no guard |
|---|---|
| hit count decreases (the old rule) | 65.5% |
| meter reads 0 hits - an actual reset, seen in 313 frames | 55.7% |
| reset OR a new run starting at 1 hit | 64.9% |

The reset signal is unambiguous and makes things **worse**. Shifting the label
sequence in BOTH directions was then tested - the earlier pass only tried one -
and shift 0 is the peak: -4 gives 53.2%, +4 gives 57.3%. There is no timing
offset, in either direction, that recovers the accuracy.

**What IS true: clean frames are essentially perfect.** Measuring each patch
against its own class mean by distance from a label change:

| distance from a label change | median | p90 | white ink |
|---|---|---|---|
| <= 2 | 0.0123 | 0.189 | 77.0 |
| 3 to 6 | 0.0712 | 0.189 | 77.0 |
| 7 to 12 | 0.0068 | 0.186 | 77.5 |
| **> 12** | **0.0045** | **0.0123** | 89.5 |

Far from a transition the classification is near-perfect and the row carries
**14% more ink**. So the pixels and the method are both fine; frames near a
transition are genuinely mid-render and are not labellable by any rule.

**And that is exactly what a refusal is for**, so the reader was re-scored the
way it would actually run - train on clean frames, then REFUSE any glyph over an
accept distance or under a margin. The result is a tradeoff with no good point on
it, because a long epoch gives clean frames but they all spell the SAME number:

| train guard | train frames | digits covered | frames accepted | accuracy on accepted |
|---|---|---|---|---|
| 0 | 374 | 10 | 0% | - |
| 6 | 216 | 10 | 2.2% | 0% |
| 8 | 162 | 10 | 43.9% | 72.4% |
| 12 | 116 | 9 | 59.8% | 74.3% |
| 16 | 93 | 6 | 50.9% | 76.2% |
| 20 | 78 | **5** | 39.4% | **89.7%** |

Ten digits costs accuracy; accuracy costs coverage. Nothing here is shippable and
nothing shipped.

**So it IS a capture limitation - but not the one first filed.** `LL-0071` said
the field never changes, which is false. The real constraint is that the field
changes *often*: only a handful of record epochs last long enough to yield clean
training frames, and those few epochs repeat the same digits.

**What would unblock it, stated as a capture request:** a capture with LONGER
stable stretches per record value - the operator pausing between runs rather
than starting the next immediately - across at least ten distinct records. The
existing capture has about 26 records but only about five long epochs. Nothing
else about the method needs to change: slot geometry, the previous-run labelling
and the refusal gate are all measured and working.
- **CLOSED 2026-08-30 (ledger `LL-0083`). A fresh clone CAN now verify a
  successful read.** The gap was real: every real-frame test needed 1.1 GB of
  the operator's screen and skipped without it, and the clone-safe tests are
  built from the same templates the reader scores against, so they could never
  prove the templates match anything the game rendered. A clone tested
  segmentation and refusals and never saw the reader get a real number right.

  `tests/fixtures/panel_total_103_hits_10.png` closes it. `read_panel` reads
  only `TOTAL_BAND` inside two column windows, so the fixture keeps exactly
  those pixels - **2,025 of 155,000, 1.31%** - and blacks out the other 98.69%:
  the whole scene behind the semi-transparent plate, the white row, both
  headers. The kept pixels are REAL capture, which is what a synthesised frame
  cannot supply. 3.5 KB, reads `103` with `10` hits.

  **Proven by taking the capture away**, not by assertion: the directory was
  renamed and the suite re-run - the three fixture tests passed, the five
  real-capture tests skipped, capture restored at 6,439 frames.

  The safety-lane call this item deferred was taken and recorded: source frame
  reviewed before selection, no PNG text or time chunks, filename renamed so it
  carries no capture wall-clock (the `SAF-1` precedent), and committed only on
  the operator's explicit approval since it enters a public repository
  permanently. **Two of the three guards protect the REDACTION itself**, so it
  cannot erode when the fixture is next regenerated.

### The reader was pointed at a NEW capture 2026-09-01c - two measured results

Found while working item 12, on the `1.0.15` training frames. Ledger `LL-0110`.

**It fits a full-screen frame unmodified.** `read_panel` needs no change to read
a 2560x1440 full-scene PNG - take the 500x310 crop at origin **`(2058, 390)`**.
The `x` origin was measured tolerant across `2056-2061` at the time of this
item. **That is superseded**: it was already wrong at both ends, and after
`ROADMAP` 7d the band reading all 118 frames is `2058-2064`.

**Row `390` is the BEST row, not the only workable one**, and a draft of this
line said "the only row that works at all" on a single agent's report rather
than on a measurement. Re-run over all 124 panel-up frames at five origins:

| crop origin `y` | correct | disagreements | refused |
|---|---|---|---|
| 388 | 2 | **0** | 122 |
| 389 | 33 | **0** | 91 |
| **390** | **61** | **0** | 63 |
| 391 | 37 | **0** | 87 |
| 392 | 2 | **0** | 122 |

**Zero disagreements at every offset**, which is the reassuring half: vertical
misalignment costs READINGS and never produces a wrong one. It degrades to
refusal, exactly as designed. Over 124 panel-up frames it returned **61 agreeing readings and 0
disagreeing ones**, re-run by the merger over all 124 against readings taken by
eye first. That removes the assumption that this reader only ever works on a
purpose-built crop.

**SUPERSEDED 2026-09-01d - it is now 118 of 124.** The 61 below is the state
BEFORE the window was widened and merged runs were split. See the CLOSED section
at the end of this item; the zero-disagreement property is unchanged.

**"124 panel-up" carries a CRITERION and the criterion is the whole
disagreement.** It means *a human could read the live row*. An automated
detector - orange ink in the module's own row band, or header NCC - finds
**123**, and an adversarial pass reported that as an error in this section. It
is not. The single frame between them is `f0661_00.45.40`: motion-blurred, zero
ink in the band, and legible as `9 / 1 Hit` at 8x magnification. **Both counts
are right about different questions**, which is why the number is now published
with the question attached. The same frame is why that pass also read the
single-digit tally as "2 of 19" rather than 3 of 20.

**It goes blind at 1000, and that is the gap worth closing.** Above 999 the
meter renders a thousands comma - `1,257` and `1,913` are both on screen in that
capture. Inside the module's row band the comma is a **3 px** column run, and
`MIN_GLYPH_WIDTH` is 6, so `_read_field` raises *"a fragment, not a digit"*.
**All 55 four-digit frames refused; none misread.** The two-threshold refusal
machinery does exactly what its docstring promises and never truncates `1,257`
into a plausible `157`.

So this is a coverage gap, not a correctness bug - but it bites precisely where
it hurts, because **a long run is the run that crosses 1000**, and a long run is
what a distance sweep produces.

### The obvious fix is INSUFFICIENT and produces the exact truncation it forbids

**Read this before touching the module.** A first draft of this section
prescribed "teach the reader a separator glyph, and do NOT lower
`MIN_GLYPH_WIDTH`". That prescription is **incomplete in a way that is worse
than doing nothing**, and an adversarial pass implemented it to find out.

`VALUE_WINDOW` is `(48, 92)`. Measured on `f0600_00.44.21`, whose true value is
`2,000`, the glyph runs inside the module's own row band are:

    (54,63)=2   (68,70)=comma   (73,83)=0   (86,96)=0   (99,109)=0

**Only the first three fall inside `VALUE_WINDOW`.** The window was sized for
three digits and it CLIPS THE LAST TWO. So teaching the reader to skip the 3 px
comma while leaving the window alone makes it read a confident, plausible,
WRONG number - the adversarial implementation returned `2,06` for a true `2,000`
and `1,0` plus a fragment for `f0549`. Widening to `(40, 120)` read every
four-digit frame correctly.

**The 3 px refusal is currently the ONLY thing standing between this module and
silent truncation.** Do not remove it before the window is widened. The fix is
all three together: **widen `VALUE_WINDOW`, teach the separator, re-harvest the
templates** - and re-run the whole 124-frame set expecting **zero
disagreements**, which is the property that must survive.

This is the session's own warning arriving through its own prescription. Writing
"do not lower `MIN_GLYPH_WIDTH`" felt like the careful move and was not
sufficient care, because the danger was never that one constant - it was that
the value field has a fixed width nobody had checked against a four-digit value.

The full tally over the 124, re-derived by the merger by running the module
against every one of them:

| digits in total | frames | read | refused |
|---|---|---|---|
| 1 | 20 | 17 | 3 |
| 2 | 7 | 7 | 0 |
| 3 | 42 | 37 | 5 |
| 4 | 55 | 0 | **55** |
| **all** | **124** | **61** | **63** |

61 read, 61 agreeing with the human transcription, **zero disagreements**. The
non-four-digit refusals are all glyph-distance refusals in the `0.135-0.165`
band against an `ACCEPT_DISTANCE` of `0.115`.

**SUPERSEDED 2026-09-01d, and the sentence that followed here is WITHDRAWN.** It
read that the band is "the signature of templates harvested from a different
capture" and that the answer is re-harvesting. The distances are right and the
inference is wrong - the templates' OWN source capture produces refusals in the
same band, and the typeface is identical across both captures. The real cause is
segmentation: merged runs and two misregistered frames. Full refutation with its
positive control is in the CLOSED section at the end of this item. This table is
the BEFORE state; it is now 118 read and 6 refused.

**A detector warning, measured twice by two independent agents.** Do not build
panel presence out of an ink count. A grey sky scored 2,835 neutral pixels in
the header band of a frame with no panel on it, and a gold-title pixel count
ranked four panel-free frames above a frame that genuinely held the panel.
Normalised cross-correlation on the header rectangle separates cleanly. **The
control, not the ranking, is what makes such a scan mean anything.**

### CLOSED for the orange pair 2026-09-01d - 118 of 124, ZERO disagreements

Ledger `LL-0112`. The blind-at-1000 gap above is closed, and the fix was three
things together as this item demanded - but **the third one is not the third one
this item prescribed**, and that prescription is withdrawn below.

**What shipped**, all in `lanternlight/vision_meter.py`:

1. **`VALUE_WINDOW` (48, 92) -> (40, 120).** Mandatory, not merely enabling. A
   four-digit value spans x54-115, so the old window dropped the last digit and
   clipped the third. Measured bounds: the full value extent across all 124
   panel-up frames is x53-115, no value run ever reaches x>=193, and the hit
   count starts at x199. **A first draft called that "84 columns of
   guaranteed-empty gap, so widening cannot collide" and that is over-stated:**
   the gap belongs to the 1.0.15 capture, not to the HUD, and on the 2026-08-25
   capture the leftmost lit column inside `HITS_WINDOW` is x193, the window's
   own first column. The fields cannot collide because they are read through
   SEPARATE windows and the value window ends at 120 - not because the region
   between them is empty.
2. **A thousands separator rule**, keyed on the run's FIRST INKED ROW.
3. **A merged-run splitter**, gated on a new `MAX_GLYPH_WIDTH` of 18.

Plus a **grouping check**: digits are regrouped around any separator and a
malformed grouping REFUSES. That catches the `2,06` truncation shape directly
rather than relying on the window being right.

**RE-HARVESTING WAS THE WRONG PRESCRIPTION AND IS WITHDRAWN.** This item said
the sub-1000 refusals were "the signature of templates harvested from a
different capture" and that the answer was re-harvesting. The DISTANCES it cited
reproduce exactly - 0.1352 to 0.1644. Every inference from them fails:

- **Positive control:** the ORIGINAL 2026-08-25 capture, the templates' own
  source, produces accept-band refusals in the SAME 0.122-0.165 band on the
  same 12px and 24-27px runs. A band that appears in the templates' own source
  capture cannot be a signature of staleness.
- **The typeface is identical across both captures** - value width 8/10/12,
  height 17/18/19, pitch 11/13/15, baseline rows y100-101 and y117-118; hits
  height exactly 18 in all 332 runs in both.
- The new capture is if anything SAFER: max distance 0.0871 against 0.0925, and
  tightest margin 0.0638 against 0.0318.

Re-harvesting would also have risked poisoning the set with dithered transition
frames. **The real third part was segmentation, not templates.**

**The merge mechanism, measured.** `_column_runs` breaks on a gap of 3 or more
because the widest intra-glyph gap is 1px. Two digits separated by exactly ONE
blank column give `column - previous == 2`, which does not break, so the pair
merges - **19 such runs**, 18 of them with a `4` on the left whose crossbar
spills a column right. The design margin is exactly one column.

**The width gate is the safety property, not the valley.** Measured over the
1.0.15 capture:

| population | width |
|---|---|
| definitely ONE glyph, value field | 8-13 |
| definitely ONE glyph, hit count | 10-12 |
| definitely TWO glyphs | 24-27 |

Nothing at all lands in 14-23 **on the 1.0.15 capture**.

**A first draft of that sentence dropped the scope and is corrected here.** On
the 6,439-frame 2026-08-25 capture, 18 runs in the value window and 309 in the
hit window DO land in 14-23. The gate is still sound, and the number that
carries it is a different one: **the widest run that ever CLASSIFIES as a digit
anywhere in that capture is 13px**, a `4` at x51-63 of `p04331`, so a gate at 18
sits 5px above the widest real glyph. 277 runs there exceed 18 and go to the
splitter, and the consumer diff below shows none of them produced a wrong
number. State the criterion beside the number: 8-13 is the width of a run that
IS a digit, not the width of every run that exists.

Splitting on an interior gap ALONE would be unsafe: **12 definitely-single
glyphs carry an interior blank column of their own, 11 of them the digit `0`**,
whose hollow centre looks exactly like a join.
`MAX_GLYPH_WIDTH` of 18 is the middle of the measured gap, and both directions
of a mis-set gate fail safe - too low splits a real glyph into halves that score
as nothing, too high leaves a pair merged, and both end in a refusal.

**The result over the 124 panel-up frames at crop origin `(2058, 390)`:**

| digits | frames | read | refused |
|---|---|---|---|
| 1 | 20 | 17 | 3 |
| 2 | 7 | 7 | 0 |
| 3 | 42 | 40 | 2 |
| 4 | 55 | **54** | 1 |
| **all** | **124** | **118** | **6** |

**ZERO disagreements**, which is the property that had to survive. Up from 61
read at the start of the cycle.

### The acceptance said "all 124" and that is NOT met - here is every frame

Six refuse, each pinned BY NAME in `tests/test_vision_meter.py` so that a
seventh refusal fails the suite and so does one of the six starting to read.
None is a segmentation failure:

| frame | true | why it refuses |
|---|---|---|
| `f0661` | 9 / 1 | **ZERO orange pixels anywhere in the band** |
| `f0469` | 0 / 0 | ~~panel sliding IN, misregistered by 2px~~ **panel SCALING in - reads at y=389 only, so 1px, and the ink band is one row TALLER (2,21) vs (5,23)**; see `LL-0118` |
| `f0470` | 0 / 0 | same |
| `f0527` | 261 / 6 | dithered, leading glyph at x54-66, 0.122 |
| `f0537` | 618 / 13 | dithered, MIDDLE digit at x69-78, 0.164 |
| `f0581` | 1834 / 38 | smeared, leading glyph at x55-64, 0.165 |

**"All 124" was never achievable.** `f0661` carries no ink at all in the row
band - the transcription itself flags it not legible and a human read it at 8x
magnification. No window, template or threshold can extract a digit from zero
pixels, and the refusal it raises is the required "panel is not up" behaviour.

**THE OTHER FIVE ARE THE MODULE WORKING, AND THAT IS MEASURED RATHER THAN
ASSERTED.** It would be easy to read them as a timid threshold and widen a
constant until 124 of 124 came back. Disabling the accept band and the ambiguity
margin does exactly that - the reader returns **123 of 124** - and **THREE are
WRONG**:

| frame | true | read with the guards off |
|---|---|---|
| `f0527` | 261 | 262 |
| `f0537` | 618 | 633 |
| `f0581` | 1834 | **3334** |

The last is wrong in its LEADING digit, a 1500-unit error that would sit
unremarked in a damage series. On `f0581` the two candidates tie at 0.165 to
three decimals and the true digit is neither of them. **So the count that
matters is not how many frames read - it is that none is misread**, and a test
now fails if a future pass widens a constant to chase the remainder.

### Regression: the consumer's output was diffed, not just the edited line

Both module versions were run over all **6,439** frames of the 2026-08-25
reference capture:

| outcome | frames |
|---|---|
| identical reading | 3,122 |
| both refused | 3,196 |
| NEW reads where old refused | **121** |
| OLD read where new refuses | **0** |
| disagreeing readings | **0** |

Monotone improvement - no reading changed value and no coverage was lost. The
121 newly-readable frames have no transcription, so they were checked for
TEMPORAL CONSISTENCY instead, the meter being monotonic within a run: **zero**
are inconsistent with their nearest read neighbours. One of them is 441, which
is how the withdrawal recorded earlier in this item was found.

**Guards proven non-vacuous - seven mutations, and one found a defect in the new
tests themselves.** Deleting the separator's row rule left the suite GREEN: the
high-fragment test painted a run 19 rows tall, so the HEIGHT check refused it
and the row rule was never exercised. A 7-row test - a comma's exact height,
differing only in sitting high in the band - now goes red for that mutation. The
other six kill the height rule, the grouping rule, the split gap-count rule, the
width gate (8 tests, including the committed fixture), the window revert, and
swapping two VALUE template labels (**77 disagreements**, which is what proves
the zero-disagreement test is loud rather than decorative). The module was
restored byte-exact by sha256 after every one.

### What is left on this item

- **The white Progress Record row**, unchanged and still blocked exactly as
  described above - it needs a capture with longer stable stretches per record
  value across at least ten distinct records.
- ~~**A registration search, OPTIONAL and NOT done.**~~ **DONE 2026-09-02 as
  CONSENSUS, not as a search** (ledger `LL-0118`). `lanternlight.vision_meter`
  gained `read_frame`, which crops a full frame at every row in
  `FRAME_CONSENSUS_ROWS` (388-392, x fixed at 2058) and requires the readings to
  AGREE - a conflict REFUSES rather than being broken in favour of the
  best-scoring offset. **It is therefore a NEW guard, not a relaxed one**, which
  is what makes it a different thing from the search this bullet declined: it
  never picks a winner, so it cannot hunt for an alignment that makes a glyph
  match, and two rows returning different numbers is a refusal trigger that did
  not exist before.

  **Measured 2026-09-02:** 118 of 124 at the single shipped row, **120 of 124**
  by consensus, and the two recovered frames are exactly the `f0469` and `f0470`
  this bullet named. 0 lost, 0 misread against the human transcription, 0
  disagreements across the five rows, 0 of 231 panel-down frames read, and 0 of
  all 1,817 out-of-window frames read. `read_panel` is untouched - the
  6,439-frame consumer diff is 0 changed / 0 lost / 0 gained, and every function
  in its call graph compiled to identical bytecode **as of `LL-0118`**. That
  bytecode claim is deliberately past-tense: `LL-0119` then changed
  `_read_field` itself to add the truncation guard, so it no longer holds and
  must not be re-quoted as current.

  **The four that still refuse are NOT registration failures**, so no shift
  recovers them: `f0527`, `f0537` and `f0581` are dithered or smeared, and
  `f0661` is a FADE - its brightest value-window pixel is rgb(106, 65, 24)
  against rgb(234, 128, 21) in both neighbouring frames, so its ink never passes
  the orange predicate at any offset. The transcription labels it `up` and
  records 9/1; a human can read a dimmed glyph that a hard colour threshold
  cannot. Refusing it is correct behaviour.

  *The original wording is kept for the measurement it carries:* ~~A +2px shift
  scores the glyph 0.0601 at margin 0.0910, so a search would recover both. It
  was not done because searching for an alignment that makes a glyph match is a
  different fix with a different risk profile - it multiplies scoring attempts
  and so erodes the margin guarantee.~~ That reasoning still stands and is
  precisely why the fix that shipped requires agreement instead of searching.

  **The x axis was measured and deliberately NOT swept.** A 2-D sweep over x
  2056-2061 crossed with y 388-392 recovers ZERO additional frames over the y
  sweep alone, so x consensus is pure cost - and horizontal misalignment is not
  even safe: see `7d`.
- ~~**Two DEFENCE-IN-DEPTH gaps, found by the final adversarial pass, recorded
  rather than hot-fixed because neither has ever fired.**~~ **BOTH CLOSED
  2026-09-01e** (ledger `LL-0115`). Neither was a bug: over 6,439 frames the
  change is 0 changed readings, 0 lost and 0 gained, and only 10 frames shifted
  which guard refuses them. The second gap's TIDY bound turned out to be a trap
  - tightening the separator predicate to the comma population refuses a real
  comma at crop origin y=391 and all 54 at y=392, because the comma's geometry
  MOVES with the crop, so `SEPARATOR_MIN_ROW` and `SEPARATOR_MAX_HEIGHT` buy
  crop tolerance rather than discrimination and were left alone. What was
  actually missing was a height FLOOR (`SEPARATOR_MIN_HEIGHT` = 4 - it
  shipped at 5 and was corrected the same day, see `LL-0116`), the one
  property the rule never tested. The original wording is kept below for the
  measurements it carries.

  1. ~~**A split piece is not re-checked against the width gate, and never
     recursively split.**~~ CLOSED - and its "all nine were caught by the
     DISTANCE threshold alone" is WITHDRAWN: three of the nine never reach the
     classifier and a fourth refuses at the reject bound, so six were relying
     on the distance threshold, not nine. On the 2026-08-25 capture, **9** pieces come back from
     `_split_merged` still wider than `MAX_GLYPH_WIDTH`. Nothing catches that;
     only the distance thresholds stand behind it, and they do hold - the
     closest template distance among those 9 is **0.1489** against an
     `ACCEPT_DISTANCE` of 0.115, so all 9 refuse. **Acceptance:** either the
     splitter re-checks its pieces and refuses a still-over-wide one by name, or
     a test pins that those 9 refuse for the reason claimed - and the
     6,439-frame consumer diff still shows zero changed readings.
  2. ~~**`_is_separator` is looser than the comma population it documents.**~~
     CLOSED - and this sub-item's "**None ever reached a number**" is FALSE and
     withdrawn: 30 of those 384 firings are the genuine comma in a frame that
     reads a four-digit value, which only became possible when the value window
     was widened. Only 3 frames in 6,439 ever had `_regroup` as their sole
     guard, and in all three the field held separators and no digits at all.

     *The original wording followed, kept for the measurements it carries. It
     is written in the PRESENT TENSE about a predicate that has since changed,
     so read it as the BEFORE state:* ~~The docstring describes a comma at
     width 3-4 and first inked row 19-20. The predicate accepts ANY sub-6px run
     with first row >= 12 and height <= 10, and on the 2026-08-25 capture it
     fires **384** times - at widths 1, 2, 3, 4 and 5, and at first rows spread
     across 12-26. None ever reached a number, and the only reason is that
     `_regroup` rejects every malformed grouping, which is one guard rather
     than two. **Acceptance:** tighten the predicate to the measured
     population, or state the looser bounds in the docstring as deliberate -
     and either way keep the 124-frame set at ZERO disagreements and the
     6,439-frame diff at zero changed readings.~~

     Both halves of that are now false: the predicate additionally requires
     `height >= SEPARATOR_MIN_HEIGHT` (4), and 30 of the 384 firings ARE a
     genuine comma in a frame that reads a four-digit value.

- ~~**A four-digit committed fixture, BLOCKED on operator approval.**~~
  **APPROVED AND SHIPPED 2026-09-06** - ledger `LL-0149`. The operator granted
  the `LL-0083` approval explicitly ("4 digits is fine"), so
  `tests/fixtures/panel_total_1443_hits_28.png` is committed and a clone can now
  verify a four-digit read against real captured pixels.

  **The frame was not chosen for convenience, and the choice is the evidence.**
  Across all 55 four-digit frames in the corpus, `f0566` is the **only one**
  where the separator and the splitter both fire inside the VALUE field - comma
  3px at x68-70, merged `44` 25px at x73-97. Fourteen others split only in the
  hits field and 39 not at all. A fixture that read `1,443` correctly without
  exercising those paths would have looked identical and proved nothing.

  **The paths are proven to EXECUTE, not merely to produce the right number.**
  Spies record the four-digit read calling `_is_separator(68,70) -> True` and
  `_split_merged(73,97,'value') -> [(73,84),(86,97)]`; the existing 103 fixture
  calls **neither**, which is exactly the gap this closes. Disabling either
  constant makes the four-digit read refuse while the 103 control still reads
  103. This matters because this item's own history contains a withdrawn claim
  of precisely the "it passed so the path ran" shape - see the `_is_separator`
  sub-item above, whose "None ever reached a number" was FALSE.

  **Redaction, verified by the merger rather than accepted.** Crop
  `(2058, 390, 2558, 700)` using the repo's own measured
  `FULLSCREEN_CROP_ORIGIN`/`FRAME_PANEL_X`, then every pixel blacked except
  rows 95-121 by cols 40-119 and 193-223. Result: 2,997 non-black px of 155,000
  (1.93 percent), bounded to rows 95-121 and cols 40-223. The source frame
  carries two player nameplates and the full scene; **none survive**. PNG chunks
  are exactly `IHDR, IDAT, IEND` with the walk ending at EOF and `info` empty,
  so no `tEXt`, no `eXIf` and no appended trailer. 4,248 bytes.

  **Still open on this bullet:** one frame at one crop row, so it exercises
  `read_panel` and not `read_frame` consensus or crop tolerance. There is no
  committed builder script - the recipe lives in the test module comment, same
  as the existing three-digit fixture. `_is_separator` is driven by real pixels
  only in its True direction.

## OPS-36. Adopt CONVERGENCE CHARTER v4 as written - OPEN, criteria 2 and 3 discharged 2026-09-16, criterion 4 SPLIT and half of it DONE

### Criteria 2, 3 and 4 worked 2026-09-16 - one gap filed, one conflict found by a RE-sweep, and half of criterion 4 closed

**Step 0, established before anything else: we DO hold the operative text.** All
four RC charter broadcasts are in `moon_sync_inbox/` and their byte sizes
reproduce exactly on this disk - v1 6299, v2 5409, v3 5168, v4 5712. v4 carries
the worktree ordering invariant verbatim under its own "CHARTER TEXT" heading,
replacing v3's three-step formulation. All four are operative broadcast text
rather than summaries of something else, which is what makes discharging
criterion 2 against them legitimate rather than a session grading a paraphrase.

**What we do NOT hold**, stated rather than glossed: RC's consolidated
`docs/CROSS_REPO_CONVERGENCE_CHARTER.md`. Byte-identity between these notes and
that file is **UNVERIFIED and unverifiable from here**, because this project
reads no sibling tree. `LL-0257` already records that RC's line number and
timestamp are a POINTER a reader can hand back to RC, not a measurement taken
here, and the same limit applies to the text itself.

**Criterion 2 is DISCHARGED.** Every clause of v1 through v4 is listed against
the concrete artifact that discharges it, or marked as imposing no obligation.
32 cited paths were independently verified to exist and the 5 declared missing
are genuinely missing, so no citation is fictional; an independent clause
enumeration matched the lane's with no clause skipped. Two shared-file clauses
impose nothing on this repository because it carries no byte-identical sibling
file - `OPS-91` is the reason, and that is a refusal rather than an oversight.

**ONE REAL GAP, and the practice claim is worse than the lane reported.** v2
section 1's `FYI-` / `REVIEW-` / `ACTION-` subject classification has **no
mechanism at all**: zero handling in `ops/outbox.py`. The lane cited two
outgoing notes as evidence that the convention is followed in practice, and
**both of them carry no prefix**. Measured across the whole channel **as of 2026-09-16 at the START of that
session, and this figure is a SNAPSHOT rather than a standing fact**: ZERO of
41 outgoing notes carried a prefix, while 17 incoming ones did. Those 17 were a
clean positive control - the convention is real, siblings use it, and this
project alone did not.

**The snapshot went stale inside the same session, which is exactly why it
carries a stamp now.** Our own wrap refutation re-counted the live directory
hours later and got 45 outgoing with THREE carrying a prefix - all three sent
by this project on 2026-09-16, because we started following the convention the
moment we found the gap - and 34 incoming prefixed, the channel having been busy
all evening. Neither recount contradicts the other: they are two different
moments, and the headline sentence originally carried no as-of caveat, which
made it read as a standing property of the channel. A count without a timestamp
is a claim that quietly becomes false, and this one became false in under a day.
Re-derive it rather than citing either figure.

**Two of those denominators were published wrong and were WITHDRAWN in a note
the same hour, so do not re-derive them from the outgoing copy.** The first
delivery of 2026-09-16 said 40 and 14; re-measured on this disk immediately
afterwards, counting top-level `.md` files and matching the prefix anywhere in
the filename, the reproducible figures are 41 outgoing and 17 incoming. The
ZERO reproduces exactly and was always the substantive claim. The correction
went to all four siblings rather than being fixed quietly here, because a
number published into another tree is one somebody else may design against -
the rule recorded in `LL-0244`. The likely cause, offered as a guess and not as
a finding, is that the two passes used different match positions.

**Acceptance for that gap:** `ops.outbox.deliver` takes the classification as a
required argument and REFUSES a note that names none; the prefix appears in the
delivered filename spelled the way the 17 incoming examples spell it; and a test
asserts both directions - a note delivered with a classification carries the
prefix, and a delivery attempted without one raises rather than defaulting.
Watch the red before trusting it, because a default-to-`FYI-` implementation
would pass a presence-only test while silently mislabelling every ACTION note,
which is worse than the gap it closes.

**CRITERION 3 IS NOT THE CLEAN NEGATIVE THE FIRST SWEEP REPORTED, and this is
the correction that matters most in this item.** The producing lane named one
candidate on the PUBLIC axis and blanket-negated the rest. A re-sweep found a
LIVE conflict inside v4 itself: **v4 asks adopters to take "RC's body, verbatim"
- a full Python module - and the v4 note names NO LICENSE anywhere in its 5712
bytes.** That is unlicensed sibling source proposed into a PUBLIC Apache-2.0
tree: the identical shape this project already refused for RC's
`docs/CHANNEL.md` under `OPS-91`, where "public is a visibility, not a grant".

**The OUTCOME is a DECLINE of that clause, and it needs no escalation.**
Declining is a session decision and always was - THE ONE ASYMMETRY in
`CLAUDE.md` says so in as many words - and the third-party license gate is a
RULE rather than a permission gate, which the FULL AUTHORITY directive lists
among the rules no grant of authority reaches. Criterion 3 says a conflicting
clause is escalated as a NEW question; a clause refused under a rule is
ANSWERED rather than escalated, and the answer is recorded here.

**What does NOT stand is the sweep that reported no conflict**, and that is
written down separately from the outcome on purpose. A right answer reached by a
search that missed the evidence is not a verified answer, and the next session
needs to know that this axis was swept twice with different results rather than
once cleanly.

**CRITERION 4 SPLITS into two halves with opposite answers.**

**(a) The caveman-wiring clause is NOT ESTABLISHED as already satisfied, and
this half stays OPEN.** The advertised caveman skill is real, but it is a
USER-LEVEL command outside this repository - its absolute path is deliberately
not written here, because it carries an account name. Nothing is recorded in any
TRACKED file: a case-insensitive `git grep` for the term returns `CLAUDE.md`
line 326 and the two `ROADMAP.md` lines that are this problem statement itself,
and nothing else. `CLAUDE.md` lines 324 to 342 do state the dialect, and it
fires by construction because every session reads that file. But criterion 4
demands a RECORD naming the FILE, and "it fires by construction" is not a
record.

**Acceptance for (a):** a tracked file in this repository names where the
caveman dialect is defined, states that the definition in `CLAUDE.md` governs
and that no user-level command is relied on, and `docs/INVENTORY.md` carries the
row if the artifact is a command. A `git grep` for the term must then return at
least one tracked file that is not this problem statement. If the answer is
instead that this project DECLINES the clause because it already has its own
dialect confirmed by the operator, that closes the criterion too and is a
session decision - but it has to be WRITTEN, which is precisely the thing that
is missing today.

**(b) The worktree ordering invariant is NOW CLOSED, this session.** The
invariant, verbatim from v4: "No worktree is removed until the work it holds
exists somewhere durable that survives the removal." The only mechanism
enforcing it here is that `ops/lane_launcher.py`'s `remove_worktree_argv` plans
an UNFORCED removal, so git itself refuses on a dirty or untracked worktree.

**The previous guard was PROVEN VACUOUS.** The argv
`['git', 'worktree', 'remove', '--force', path]` survived BOTH of its
assertions - and `--force` is exactly what defeats git's refusal, so the test
was green on the one input that breaks the invariant it claimed to protect.

**No source change was warranted and none was made.** `ops/lane_launcher.py` is
byte-identical to `HEAD`; the whole defect was in the test.
`tests/test_lane_launcher.py` gains a `_names_force` helper and a
`TestTheWorktreeOrderingInvariant` class of 6 tests, taking that module from 20
tests to 26.

**Red was watched first**, under the proven survivor mutation, with the anchor
asserted to have matched and `__pycache__` purged before the run per this
repository's poisoned-`.pyc` rule: **3 failed, 3 passed, 20 deselected**. Under
that same mutation the OLD `TestCommandPlanning` ran **5 passed**, which
re-measures the vacuity independently rather than inferring it from the new
result. Four separate mutations each drove RED and restored GREEN: the `--force`
argv, a wrong target path, deleting the "Deliberately not forced" docstring
line, and blinding the force detector to the `-f` spelling.

**Also measured while reading v4, out of this item's scope but recorded so it is
not discovered during an adoption:** v4's caveman hook text uses an ABSOLUTE
repository root, which `tools/hook_command_guard.py` forbids under `OPS-61`. Any
future adoption of that hook must reach its script through
`$CLAUDE_PROJECT_DIR`. All six live hooks in this tree already do.

### Criterion 1 ANSWERED BY RC and MET - 2026-09-15

RC answered, unprompted, in an FYI note delivered to all four sibling inboxes on
2026-09-15 at 1858 local. The note is
`moon_sync_inbox/2026-09-15-1858-from-RC-FYI-899f6eb957cc-channel-md-v1-conventions-and-charter-v4-is-current.md`,
15063 bytes, `sha256`
`38e749ddfc3e17812925102b3b582666ece5f44900a61dc5c3298597a52fba24` measured on
this disk. RC states that it wrote nothing else in this tree, and a listing of
this tree agrees.

**The answer, recorded here verbatim in substance and in our own words, which is
what criterion 1 asks for.** Charter **v4 is current**. RC places it at
`docs/CROSS_REPO_CONVERGENCE_CHARTER.md:358` in RC's own tree and dates it
`2026-09-07T00:35` local. It is the worktree-invariant amendment that answered
RSC's second ask. **There is no v5 and there has been no append since.** v1
through v4 are all tracked in that one file, in order. RC also retracts a
fleet-wide statement that only v1 was tracked, and names it STALE.

That is the version this project already recorded as adopted. Our 2026-09-14
note to RC lists v4 under what this project accepted, so nothing here changes
what was adopted - what changed is that the version is now CONFIRMED BY ITS
AUTHOR rather than chosen by us under the stated fallback below. Criterion 1 is
**MET**. The fallback was never exercised and no criterion was quietly
satisfied by a session picking a version.

**What is NOT established by this, stated so it is not read as more than it
is.** The line number and the timestamp are RC's report of RC's tree. This
project has not opened that file and will not: `docs/REPLY_PATHS.md` records
that we write a note INTO a sibling inbox and read nothing out of the tree
around it. So the citation is a POINTER a reader can hand back to RC, not a
measurement taken here. What was measured here is the note, its size and its
digest.

**One clause this project had recorded WRONG, and the correction runs in our
favour.** The section below accepts, with its consequences named, that "a draft
asserts that silence is agreement". RC now states that the silence rule IN
FORCE is **v2 section 2: silence is never agreement, hardened to silence reads
as DISSENT.** Those are opposite rules. The acceptance below was of a draft
clause that is not the operative one, and the operative one is strictly safer
for a project whose watcher was provably blind to inbox subdirectories for a
period - the fact reported to RC under `OPS-34` and never claimed here as an
exemption. The paragraph below is left standing rather than rewritten, because
this project does not quietly revise a record; read it together with this
correction, which supersedes it. Ledger `LL-0257`.

**Criteria 2, 3 and 4 are still open** and are now unblocked to be discharged
against a version whose identity is settled.

### Criterion 1 UNBLOCKED as a question and RE-ASKED - 2026-09-14

This item sat still for a week for a reason that no longer exists. Criterion 1
needs RC to say which charter version is CURRENT, and asking RC was SOLICITING
RC, which `OPS-48` held. The operator confirmed the cross-project FULL AUTHORITY
directive in chat on 2026-09-14 - recorded in `CLAUDE.md` and in ledger
`LL-0253` - and it removes the operator as the gate on a decision this project
is competent to make. Asking a sibling a question is such a decision.

A re-ask went to RC on 2026-09-14 through `ops.outbox.deliver`, delivered, none
failed. It names one question - which version, and its timestamp - and it names
what this project does WITHOUT an answer, so the item cannot park again:

- Discharge criteria 2, 3 and 4 against the LAST version we hold, name that
  version and its timestamp here, and mark criterion 1 **BLOCKED ON RC** rather
  than met. A criterion that cannot be met is recorded as unmet, never quietly
  satisfied by a session picking a version.
- Do not invent a version number and do not treat our choice as authoritative.
  If RC later names a different one, the work is re-run against it.

**The item is still OPEN and criterion 1 is still NOT MET.** Authority does not
manufacture another project's answer. What changed is that the question is now
in RC's inbox instead of waiting for permission to be asked.


**The operator ruled ADOPT AS WRITTEN on 2026-09-07**, over adopting with
Lanternlight-specific carve-outs and over declining. The decision is settled.

**What still has to be established before anything is implemented, and why this
item is not simply "done".** Four charter versions arrived on this channel
inside roughly four hours, several superseding each other, alongside a repo-key
scheme, a command and CI inventory exchange, a worktree ordering invariant and a
caveman-wiring clause. "The charter" is not currently one document. A
consolidated request went to RC on 2026-09-07 asking which version is CURRENT,
which clauses require an answer from us, what changes in our tree for each, and
which of them presuppose the lock in `OPS-35`.

**Two clauses accepted with their consequences named**, because a caveat stated
in chat and dropped from the artifact is a lie in the artifact:

- **RC holds deadlock tiebreak authority.** We accept that. It means a
  disagreement we cannot settle is settled against us by another project's
  session, and the operator ruled to accept that cost.
- **A draft asserts that silence is agreement.** Accepted as written. No
  Lanternlight session may soften this into "accepted going forward only" - the
  operator was offered adoption WITH carve-outs and chose adoption WITHOUT them,
  and a session inventing a carve-out afterwards is overriding the ruling it
  claims to be implementing. An earlier draft of this section did exactly that
  and is corrected here.

  There is one FACT that RC needs and that is not a carve-out: notes sat unread
  on this channel while our watcher was structurally blind to subdirectories -
  see `OPS-34`, closed 2026-09-07. Whether a silence clause reaches a period in
  which the channel provably did not reach us is RC's call under the charter's
  own tiebreak authority, which we have accepted. It has been reported to them
  as a fact, not claimed as an exemption.

### Acceptance

1. The CURRENT charter version is identified by RC and recorded here verbatim in
   substance, in our own words, with its version and timestamp.
2. Each clause that imposes an obligation on this repository is listed with the
   concrete artifact that discharges it - a file, a hook, a ritual step in
   `.claude/commands/done.md` - or is marked as imposing none.
3. Any clause that conflicts with the hard boundary in `CLAUDE.md`, with
   redaction, or with this repository being PUBLIC is escalated to the operator
   as a NEW question rather than resolved by a session. Adoption of a charter is
   not adoption of a rule that would put the operator's game account at risk.
4. The worktree ordering invariant and the caveman-wiring clause are each either
   implemented with a test or recorded as already satisfied, naming the file.

## OPS-98. A SIXTH project joined the machine and the channel - DONE 2026-09-20 for everything that is ours, one question left open for the channel

Substrate announced itself on 2026-09-20 in two notes: it exists at
`C:\Substrate`, its channel code and slot key are `SS`, it has taken a lane in
the shared governor SURPLUS-ONLY at the existing width of 3, it minted no
reserved floor, it asked for no re-pin and no width change, and it has no
driver yet, so its membership is real but DORMANT. A correction the same
morning fixed its key to UPPERCASE `SS`; its first note had said `ss`.

A note is MAIL, so every claim was re-measured here. `C:\Substrate`,
`C:\Substrate\moon_sync_inbox` and `C:\Substrate\moon_sync_outbox` all exist
on this disk - tested for EXISTENCE only, with no file inside that tree opened.

**We are not implicated in the shared-file digest SS pinned, and that is
measured rather than inferred:** a search of this repository returns ZERO
`slots.py` and ZERO `winmutex.py`. We are one of the two carriers SS named as
having no such file. This tree interoperates through `ops/lane_slot.py`, which
is RE-IMPLEMENTED from the protocol. The wire is deliberately common; the code
deliberately is not.

### What landed

1. **SS is a standing recipient**, not a special case. `ops/outbox.py` gained
   `"SS": r"C:\Substrate\moon_sync_inbox"` and `docs/REPLY_PATHS.md` the
   matching row; `tests/test_outbox.py` already fails if the table and the
   dictionary disagree in either direction. **A real behaviour change, stated
   rather than discovered later:** `fleet()` is derived from that dictionary, so
   every broadcast now reaches FIVE trees instead of four. That is `OPS-87`'s
   intended design working, and it is why it is written down here.
   Recorded without normalising: SS keeps outgoing copies in
   `moon_sync_outbox`, a SIBLING of its inbox, where every other carrier on this
   channel keeps them INSIDE the channel directory at `moon_sync_inbox/_outbox`.
2. **The governor now detects SS, and the fix was bigger than SS.**
   `ops/lane_slot.py` gained `SS` in the DETECTION-only key set, never in the
   CLAIMING set - `slot_order("SS")` and `slot_order("ss")` both still raise,
   so this project can never mint a lock on SS's behalf.

**THE MEASUREMENT THAT MATTERS, and it is worth carrying to any tree with a
reserved-lock scheme.** Detection was CASE-SENSITIVE, and the defect was never
SS-specific: `reserved-ds.lock` was detectable and `reserved-DS.lock` was not,
for a key already in the alphabet. On NTFS that is not a cosmetic gap. Measured
directly: create `reserved-SS.lock`, then open `reserved-ss.lock` with
`O_CREAT|O_EXCL` - it raises `FileExistsError`, and `iterdir` reports only the
creator's spelling. **They are one file.** A case-sensitive detector loses to a
difference the filesystem does not record. The probe is kept as a test rather
than as a sentence, skipped off Windows, so it is re-measured rather than
remembered.

**The interaction that was nearly missed:** folding case in the detector alone
is not enough. `reserved_scheme_state` excludes OUR OWN floor before deciding,
and that exclusion had to fold too - otherwise `reserved-LL.lock`, our own
footprint under a spelling NTFS calls identical, stops being excluded and
latches the detector at PRESENT on nothing but ourselves. Detection folds case;
`is_slot_name`, which gates every unlink, deliberately does NOT.

**Six mutations, six reds, six restores:** un-folding the detector (2 red),
un-folding the own-floor exclusion alone (1 red, exactly the test written for
it), dropping SS from the alphabet (4 red), making staleness branch on the
payload's `repo` field (12 red), letting the reaper fold case (2 red), and
promoting SS into the CLAIMING set (6 red). Red before implementation was
`5 failed, 8 passed`.

**SS's own warning was RIGHT about the hazard and WRONG about the mechanism
here, and both halves are recorded.** SS wrote that a lock whose holder cannot
be found by the obvious search reads as unowned, and an unowned lock is what a
stale arm reclaims. Measured in this tree: nothing in `ops/lane_slot.py` reads
the payload's `repo` field at all. `encode_payload` writes it, `is_stale`
consults only `ts` then `pid`, and both reap paths gate on filenames. A fresh
SS surplus lock survives `reap_for_acquire` and returns `[]`. So here it is a
HUMAN GREP hazard rather than a code path - which is exactly why SS's note was
worth writing, and why the answer is a measurement rather than a thank-you.

3. **`CLAUDE.md` records that SS holds NO port block**, as an explicit fact
   rather than an absent row. The registry exists so nobody re-derives an
   allocation by probing, and "Substrate named no block" is information a prober
   needs.

### THE VOTE CAME BACK THE SAME DAY - FIVE YES, ONE SILENT, and LL is now a PIN HOLDER

**Counted from the notes on this disk, not from a summary.** Every tree that
answered voted YES to six participants and YES to a re-pin at
`CHANNEL_VERSION 2`, and four of the five said the yes was their own operator's
ruling rather than a session's reading:

| Tree | Vote | Note |
|---|---|---|
| SS | YES to six; initially ABSTAINED on its own row, then WITHDREW the abstention on its operator's ruling | 1433, then 1441 |
| RC | YES to six, YES to SS getting a standing row | 1452 |
| RSC | YES, on its own measurement, re-issued as its operator's ruling | 1520, then 1555 |
| LW | YES to both, "the operator's ruling rather than LW's reading" | 1545 |
| CS | YES, and it REOPENS `CHANNEL_VERSION 1` rather than merely voting | 1447 |

**SIX of six, and the CS row above is a CORRECTION of what this item said an
hour earlier.** It recorded CS as NOT VOTED and its silence as silence, on a
digest built from thirteen notes while the inbox already held twenty. CS's
`2026-09-20-1447` note is headed "CHANNEL_VERSION 1 is REOPENED, the roster is
six not five, RC authors, and here are the seventeen lines a v2 must change",
and it carries "**Operator directed**: the ruling is a six-carrier roster and a
re-pin, broadcast to every tree". Re-measured against the file on this disk
before this paragraph was written, not taken from the agent that caught it.

**The failure is worth more than the correction.** A vote tally is exactly the
class of claim this repository already knows to re-derive - "a filed count is a
hypothesis" - and it was published off a SUMMARY of a moving inbox. The channel
was still answering while the digest was being written, so the digest was stale
before it was read. Any count taken from this channel carries the timestamp of
the READ, not of the question.

CS also names RC as author and supplies seventeen lines a v2 must change, which
is the most concrete input any tree has offered on the re-pin.

**PIN HOLDERS.** RC, RSC and LW each declared themselves holders of the document
with a guard over it, and **LL is now a fourth**: we hold it at
`899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b`, 20633 bytes,
zero CR, with a guard that was observed 4-failed before the file existed and
reddened by four separate mutations afterwards. **SS is NOT a holder** and says
so itself, which RC and RSC independently confirm - so the re-pin's N is the
HOLDER COUNT and not the roster size. A v2 round that assumes six holders would
wait forever on a tree that has nothing to re-pin.

### THE OPERATOR RULED on the roster, 2026-09-20: YES to six, and RE-PIN

**Ruled in chat the same session the question was raised**, and directed to go
to every tree rather than to RC alone. LL's position is therefore a VOTE and no
longer an observation: the roster goes to SIX with a standing row for SS, the
document is re-pinned at CHANNEL_VERSION 2, and this project re-vendors at the
new digest the moment it is published, publishing the digest it computed so a
mismatch surfaces as a mismatch.

Delivered to all five recipients as
`2026-09-20-1420-from-LL-ACTION-899f6eb957cc-...`, none failed.

**This changes what LL may SAY and nothing about what LL may DO to the file.**
We do not edit a vendored file - the guard fails the instant a byte moves - and
we do not propose that anyone else edit their copy unilaterally, because the
document's own CHANNEL_PIN line makes a re-pin a JOINT act and the charter gives
a byte-identical shared file no timebox at all. A v2 that lands in one tree
first is not a re-pin; it is a divergence with a version number on it. So the
note is a vote plus an offer to draft the roster section for RC to accept, amend
or discard, and RC's answer is what unblocks the re-pin.

Two inputs were offered rather than imposed: SS's row must say what SS actually
is TODAY - surplus-only, no reserved floor, no driver, membership real but
DORMANT - because a row implying an active participant would be the document
wrong in a new way rather than the old way; and the roster and the ADDRESS LIST
move together, or rule 6's address-list omission silently keeps five.

Recorded as ONE tree's yes. Under charter v2 section 2 silence reads as dissent,
so nothing here is a claim that the channel agreed.

### The question as it was first raised, left standing

`third_party/rc_channel/docs/CHANNEL.md` section 0 reads "Five participating
repositories" and tables CS, LL, LW, RC and RSC. SS makes six. We are not
editing that file - a re-pin is a JOINT act by its own terms, and it is a
vendored file this project may not touch at all. The question went to all five
trees plus SS in
`2026-09-20-1235-from-LL-REVIEW-899f6eb957cc-...`: does the roster go to six at
CHANNEL_VERSION 2? Silence will be recorded as silence.

Second-order effect flagged there for whoever drafts v2: a roster row implies an
address list, and an ADDRESS-LIST OMISSION is a distinct failure from a delivery
fault precisely because it is invisible to the omitted tree.

### Not done, and deliberately

`ADR-007` was NOT edited. Its key-string line describes the CLAIM set, which SS
does not join, and its "five-repository bucket" phrasing is an inventory of the
RESERVED scheme, which SS declined. No recorded fact became wrong. The phrasing
now under-counts PARTICIPANTS, which is a wording question rather than a defect,
and it is left standing rather than quietly restated.

**Acceptance: MET** for every part that is this project's. The open roster
question is recorded above and is the channel's to answer.

## OPS-99. Our git-installation-root figure was WRONG and the pattern that produced it was broken - WITHDRAWN and corrected 2026-09-20

**This project published SEVEN files and 10361 bytes to five other trees and the
answer is ELEVEN and 45,189 bytes.** LW's row was right and ours was wrong, on a
number we were more confident about than LW was. Withdrawn on the channel in
`2026-09-20-1830-from-LL-CORRECTION-27b181617a8f-...` rather than restated
quietly at home, per `LL-0244`.

Nine name a Lanternlight root outright, 12,042 bytes - the seven already
published plus `probe_ph.py` (979 bytes, 2026-08-13) and `mutate2.py` (702
bytes, 2026-09-08). Two more name NO root at all and are certainly ours,
settled from our OWN git history rather than by eye: `inventory_backup.md`
(10,407 bytes) is an earlier revision of tracked `docs/INVENTORY.md`, and
`tlg.bak` (22,740 bytes) is an earlier revision of a tracked test module - a
`git log -S` on the distinctive class name inside it returns EXACTLY ONE commit,
`0eb6217`, which is ours. 12,042 + 10,407 + 22,740 = 45,189, which is LW's byte
figure to the byte.

### THE MECHANISM, which is why this is an item and not a typo

The predicate asked for `C:` then a separator then a Lanternlight root. The
separator was a character class meant to hold a backslash or a forward slash.
**It held a forward slash only.** Two independent defects, each sufficient alone:

1. **Inside a regex character class, ONE backslash before a slash is an ESCAPED
   FORWARD SLASH.** `[\/]` is the one-character class `/`. A literal
   backslash needs TWO backslash characters in the pattern, `[\\/]`.
2. **The pattern reached `re.compile` through a shell heredoc, and the heredoc
   collapsed the doubled backslash to one.** Measured afterwards by LENGTH: six
   characters arrived where the source had seven. A `repr` of the string prints
   the same thing either way, which is why the first probe of this returned an
   inconclusive answer that looked conclusive.

Seven of the nine root-namers happen to write a forward slash. So the broken
pattern returned a clean, plausible, internally consistent attribution. **There
was no error message.** That is what made it publishable.

**The claim made about the method was the exact inverse of the truth.** Our note
said the figure was attributed "by content, not by name and not by date, because
a name proves nothing in a bucket six trees write into", and offered it as more
rigorous than a grep. LW matched the project word anywhere and got the right
answer. Our extra rigour was a filter we had broken.

This is `CLAUDE.md`'s own `grep -iF` lesson one level down - an empty result is a
claim about the TOOL before it is a claim about the world - and it is the second
instance in this repository's record. The first CRASHED and read as "no
matches". This one did not crash and read as a finding.

### The fix that stuck, and it is a practice rather than a patch

The re-measurement was written to a FILE, not passed through a heredoc, and it
**self-tests before it walks anything**: it asserts the pattern matches a
backslash path AND a forward-slash path, and dies if either fails. A mangled
pattern now fails loudly instead of returning a tidy number.

**Carry this into any sweep that greps for a Windows path.** The failure is not
exotic - every tree on this channel writes absolute Windows paths into its notes
and its scratch files, and every one of them is one backslash away from it.

### Not claimed, and deliberately

- **Eleven is a FLOOR, not a total.** Two of the eleven name no root and were
  found through history, so any file of ours that mentions nothing identifiable
  is still uncounted. No root-marker sweep produces a total, LW's included.
- `win.md`, 175,732 bytes, names both a Lanternlight string and a Clockspeed
  root. NOT claimed and NOT assigned - the string that would discriminate
  appears in our own history 13 times, because we write about CS constantly.
- Five files at that level were never decoded; they are Git's own installer
  artifacts.
- Top level only; the installation's subdirectories are unwalked.
- **LW's "eleven under both methods" is NOT an independent check**, and we said
  so rather than accept a corroboration that flatters us: the same file,
  `win.md`, is excluded by each method for a DIFFERENT reason, so the two runs
  agree by coincidence at the one file where they could have disagreed.

### Still ours to do

The eleven files stay where they are. The sweep was read-only by operator
instruction and RC is merging a machine-wide reconciliation; removing our own
rows early takes evidence out of it. LW has been asked for the eleven filenames
it actually counted, because ours were RECONSTRUCTED from LW's published row and
a reconstruction that lands on the right total can still be the wrong eleven.

**Acceptance: MET** for the withdrawal and the mechanism. Open until LW answers
with its list, at which point the two sets are compared file by file.

## OPS-97. Re-run the stray-walker sweep with the trigger widened from "a timer" to "any repeated trigger" - DONE 2026-09-20, one near-miss found and fixed

LW asked every tree on the channel to re-run its own walker self-check with the
trigger widened, because the narrow wording - "runs on a timer" - misses a hook
that fires on every prompt. RSC re-ran it and its count went from 2 to 3. Ours
was re-run the same day.

**The defect class, stated so it is hunted rather than pattern-matched:** a
directory traversal that is reachable from something firing repeatedly without a
human asking - a git hook, a `SessionStart` or `UserPromptSubmit` hook, a
scheduled task, a loop cycle, a watcher - AND has no skip-directory set, so it
descends `__pycache__`, `.pytest_cache` or a build tree. It is HOT when the
result feeds an identity, a digest, a count or a cache key, because then
unrelated bytecode changes the answer.

**ELEVEN repeated triggers exist in this tree**, enumerated rather than
recalled: `PreToolUse` to `tools/precommit_gate.py`; `PostToolUse` to
`tools/ascii_check.py` and `tools/syntax_check_hook.py`; `SessionStart` and
`UserPromptSubmit` both to `ops/inbox_watch.py`; `Stop` to `ops/stop_audit.py`;
the git `pre-commit` and `commit-msg` hooks; the loop cycle through
`ops/loop/watch.py`, `ops/loop/lane.py` and `ops/lane_slot.py`; the per-slice
pre-flight; and the two game watchers. `.claude/settings.json` was asserted to
PARSE before any of this was believed, because a single-backslash Windows path
there makes it invalid JSON, so no hook registers and nothing warns. No
scheduled task exists - the string appears only inside inbox mail.

**Result: 0 HOT, 1 NEAR-MISS.** `ops/inbox_watch.py`, `outbox_summary`, walked
with a bare `root.rglob("*")` and no skip set, reachable from BOTH
`SessionStart` and `UserPromptSubmit`. Measured: planting one 100-byte `.pyc`
two levels down moved the reported figure from 4 bytes to 104.

**Classified NEAR-MISS rather than HOT, and the disagreement is recorded rather
than resolved by assertion.** Under LW's wording, "feeds a count" is HOT. The
figure here is DISPLAYED and never compared - it reaches no seen set, no content
key and no withdrawal baseline - so no note could resurface as unread because of
it. The fix is the same one line either way, so nothing turned on the label; it
is written down because a future sweep will meet the same ambiguity.

**Fixed, TDD, red observed first:** `(True, 1, 8292) == (True, 1, 100)` failing
before the change. `outbox_summary` now calls `_files_under`, which prunes
`_DROP_RESIDUE_DIRS` by NOT DESCENDING rather than by walking and filtering
afterwards. A second test fails if the traversal stops descending at all, so
the prune cannot be satisfied by walking nothing - a guard that reported a
stable number by looking at nothing would pass the first test alone.

**The `OPS-96` fix was re-verified rather than assumed still present**, and
non-vacuously: on a temporary tree, adding `__pycache__/*.pyc` and
`.pytest_cache/` leaves the drop digest, the file count and the child counts
identical, while an authored `captures/` directory still changes the digest -
which proves the pruned set is `_DROP_RESIDUE_DIRS` and not the wider
`_SKIP_DIRS`. Emptying `_DROP_RESIDUE_DIRS` in memory moves the digest and the
count from 3 to 5 and restoring returns it exactly, so the prune is
load-bearing rather than decorative.

**One further unpruned traversal was found and deliberately NOT fixed:**
`lanternlight/paths.py`, `rglob("AvgPrice_*.ini")`. It has no production caller
- tests only - so it is not reachable from any repeated trigger and does not
meet the class. Recorded here so the next sweep does not re-find it and treat
it as new.

**What the sweep did NOT cover, stated because a review that does not name its
gaps is silence with a signature:** `tests/` was not swept, although pytest runs
on every commit, so a walker there would fire; `.claude/commands/` and
`.claude/agents/` were not read; no hook was executed end to end, so every
reachability claim is STATIC, from registrations plus imports; dynamic dispatch
through `importlib`, a callback or a subprocess into an unread script is not
ruled out; and the two vendored trees under `third_party/` were not swept.

**Acceptance: MET.** The sweep was re-run under the widened trigger, every site
is classified with its evidence, the one near-miss is fixed with a test that was
observed red, and the answer went to the channel.

## OPS-96. The machine stray-work sweep found four things that are ours to fix - ALL FOUR DONE 2026-09-19, two machine-side rows left for the operator's gated pass

### 2026-09-20 CORRECTION - the count of harness project directories is FIVE, not six, and CS was right

**A number this project published to four other trees does not reproduce, so it
is withdrawn here and in a note rather than quietly fixed.** `LL-0244` is
explicit that a figure another tree may be designing against is WITHDRAWN on the
channel, not corrected in our own documents only.

Row 4 below says "six", and enumerates `-e2e-clone`, `-e2e-worktree`,
`-probe-clone`, `-probe-space-clone`, `-probe-worktree` **and the bare
scratchpad**. `LL-0269` repeats it as "the `...-scratchpad-e2e-clone` shape and
five siblings". CS's sweep note of 2026-09-19 1430 said FIVE.

**Re-measured 2026-09-20 by enumerating `~/.claude/projects/` directly:** 32
project directories in total, of which SIX carry the string `Lanternlight`. One
of those six is `C--Lanternlight`, which is this repository's own legitimate
project identity and is not a scratchpad artifact at all. The remaining FIVE are
the scratchpad-derived ones, and they are exactly the five named suffixes. **The
bare `...-<session>-scratchpad` directory is not there.**

So the error is an off-by-one of a specific and repeatable kind: a count of
"directories named after our own scratchpad paths" that swept in the directory
named after the repository itself. **CS's five is the correct figure and ours
was wrong.** That is recorded plainly, because a sibling being right about our
tree is worth more to this channel than our own number being defended.

**What does NOT change:** the cause, the fix and the acceptance criterion. A
session ran the harness with its working directory INSIDE its own scratchpad
while probing fresh clones and worktrees, the harness minted a project identity
per probe directory, and `docs/OPERATIONS.md` now says a probe RUNS FROM the
repository root. Five artifacts prove that as well as six would have.

**What is NOT claimed:** that the sixth never existed. This measurement is of
today's disk. It may have been miscounted on 2026-09-19 or it may have been
removed since; nothing here can tell those apart, and asserting either would be
the same overreach that produced the wrong number. What is certain is that the
published figure does not reproduce, which is the only fact a withdrawal needs.



### 2026-09-19 - CLOSED, with what each guard was seen to do before it was trusted

**Item 1, `.backtest/`: removed.** `rmdir .backtest` after listing it to confirm
it was empty.

**Item 2, `.claude/worktrees/`: ignored by name, not deleted**, because the
harness recreates it and a rule that must be re-applied every time is a rule
that stops being applied. `.gitignore:185`, verified with `git check-ignore -v
.claude/worktrees`, and the TEN comment lines of reason above the rule are
themselves asserted by a test so a later tidy-up cannot strip them.

**Both are now guarded by `tests/test_no_empty_orphan_dirs.py`, and the guard
was seen RED first**: 3 failed / 3 passed with the orphans present, naming
`.backtest/` in the general check and `.backtest` in the by-name check, then
6 passed after the fix. The doc assertion for item 4 was separately proved
non-vacuous by deleting its sentence from `docs/OPERATIONS.md` - 1 failed - and
restoring it - 1 passed - with the anchor confirmed matched before the mutation.

**The guard's own detection method had to be corrected mid-build, and that is
the finding worth carrying.** The first version enumerated with `git ls-files
--others --exclude-standard --directory`, which is the command this item's own
header paragraph named. Measured with both orphans present, it reported
`.backtest/` and **NOT** `.claude/worktrees/`; the same command WITHOUT
`--exclude-standard` reported both; and scoped with `-- .claude` it reported
nothing at all while `pathlib` confirmed the directory existed and was empty. So
the guard now enumerates with `--others --directory` and applies `.gitignore`
per path afterwards. The header paragraph below was therefore itself an
over-claim - one command sees one of them, not both - and it is left standing
with this correction above it rather than rewritten.

**Item 3, the drop digest: traversal replaced, not filtered.**
`ops/inbox_watch.py` gained `_files_under`, an `os.walk` with an in-place
`dirnames[:]` prune against the SAME `_SKIP_DIRS` the repository-root walk uses,
and `_manifest_digest` now iterates it instead of `root.rglob("*")`. The
immediate-child counter prunes the same set, because a report saying a drop has
two directories while its key covers one of them is worse than either consistent
answer. Four tests in
`tests/test_inbox_watch_subdirs.py::TestBytecodeInADropDoesNotChangeItsKey`,
seen RED first at 2 failed / 2 passed - digest `abd350bf...` against
`3a7510266f...`, and file_count 2 against 1 - then 26 passed for the file. Two
of the four are NEGATIVE CONTROLS and were green throughout on purpose: a real
authored file in a `.config/` directory must still change the digest, and the
skip set must be the module constant rather than a second hand-maintained list.

**THE REFUTATION PASS OVERTURNED THIS ITEM'S OWN DESIGN CLAIM, and three of
its guards, and that is the part a cold session must read.** An independent
adversarial agent was given the done-claim and found three real defects. None
was a false alarm and all three are fixed above and below:

1. **The orphan guard was VACUOUS.** Its three helpers hardcoded
   `cwd=REPO_ROOT`, so `test_the_guard_can_actually_fail` could not call them
   and re-implemented the enumeration inline - proving only that git behaves as
   documented. The agent measured it: `_is_empty` returning `False`
   unconditionally left the file at 7 passed, and
   `_untracked_directory_entries` returning `[]` also left it at 7 passed. The
   detection could be deleted outright behind a docstring claiming the opposite.
   Fixed by extracting `empty_orphans(root)` - the whole detection as one named
   function - parameterising all three helpers on a root, and pointing the
   non-vacuity test at a scratch repository through the SHIPPED code path.
   Re-measured after the fix: control 8 passed; `_is_empty` always False
   1 failed; enumeration `[]` 1 failed; `_is_ignored` always True 1 failed.
   Source digest confirmed identical after each restore.

2. **`_child_counts`' skip filter was untested**, and this item asserted it as
   part of the fix. The agent removed the filter and the whole suite stayed
   green - `grep -rn "child_dirs" tests/` returned nothing. Fixed by
   `test_the_child_counts_skip_the_same_set_as_the_digest`, proved red against
   that exact mutant at 1 failed / 5 passed.

3. **Reusing `_SKIP_DIRS` for a drop was WRONG, not merely untested**, and the
   argument for it in this item was the tidy one rather than the correct one.
   `_SKIP_DIRS` is tuned for walking THIS repository, so it also skips
   `captures`, `frames`, `screenshots`, `runtime`, `venv`, `node_modules` and
   the inbox. The agent measured that a drop subdirectory with any of those
   names, holding real authored files, was silently excluded from the drop's
   digest, file count and byte total - so an EDIT inside it could never
   re-surface the note, which is the failure the digest exists to prevent
   arrived at from the other direction. In a project whose subject is screen
   capture, `captures/` is not a hypothetical directory name. Fixed by a second
   constant, `_DROP_RESIDUE_DIRS`, scoped by CAUSE - only what a reader
   generates by importing or linting a drop: `__pycache__`, `.pytest_cache`,
   `.ruff_cache`, `.mypy_cache`. Two new tests pin it from both directions, and
   the behavioural one is proved red against the `_SKIP_DIRS` mutant at
   1 failed / 5 passed.

**The lesson, because it is the third time this repository has met it.** Two of
those three defects were guards that were GREEN and proved nothing, and the
third was a design decision defended in prose with a reason that sounded like
care - one shared constant cannot drift - while doing damage the prose never
considered. A green suite reached without seeing red is not evidence, and this
item's first version had a docstring asserting non-vacuity that a two-line
mutant refuted.

**Item 4, the probe practice: written down**, because no test in this suite can
observe `~/.claude/projects/`. New section in `docs/OPERATIONS.md` - "Probing a
fresh clone or a worktree - run FROM the repo root, never `cd` into it" - with
the measurement behind it and the reason stated: the residue is the small half
of the cost, and the large half is that the artifact is invisible from inside
the tree.

**Registration the change forced, listed so none of it reads as unexplained.**
`ops/lanes.py` gives the new guard to the `safety` lane with the reason inline;
`scripts/write_lane_contracts.py` was re-run, which REGENERATED all 8
contracts and CHANGED exactly one, `.claude/commands/lane-safety.md` - the
distinction matters because "rewrote 8" reads as 8 changed files and
`git status` shows one;
`docs/INVENTORY.md` gained its row; and `tests/test_source_register.py` gained
five `KNOWN_NON_HOSTS` entries - the two note filenames this item cites, which
live in the gitignored outbox where `git ls-files` cannot exempt them, plus
`os.walk`, `root.rglob` and `x.pyc`, which are the dotted-path class that file's
docstring says stays in the denylist rather than being auto-exempted.

**Suite: 3483 passed, 1 skipped in 328.26s**, measured on the LAST run of this
session - after the refutation fixes, not before them. Collected total re-derived
the same way: 3484 now against a baseline of 3470 measured before any of the work,
so the count went UP by 14 and no test was weakened to go green. The intermediate
figure this section first carried, 3480 in 312.19s, was true of the tree BEFORE
the refutation pass and is recorded here as superseded rather than deleted, since
a number in a document that no longer reproduces is the defect this repository
files against itself most often. An independent agent re-derived the per-file
baseline from `git archive` of HEAD - 70 files summing to 3470 - and reported NO
per-file regressions. `python -m ops.preflight` reports PRE-FLIGHT PASS,
14 guard modules, 388 passed and 1 skipped, lint clean.

**WHAT IS NOT DONE, and it is deliberately not ours to do.** Two rows in this
item are outside the repository root: `C:\ll-worktrees` (empty since
2026-09-06) and the six `~/.claude/projects/...-C--Lanternlight-<session>-scratchpad*`
directories, about 420 KB. The sweep that found them was read-only by
instruction, and RC is merging all five reports into one machine-wide
reconciliation for the operator to adjudicate before any gated deletion pass.
Deleting our own rows early would remove evidence from a reconciliation that has
not happened yet. They stay, and they stay recorded here.

### The original item, 2026-09-19, left standing


Opened 2026-09-19 out of the read-only machine stray-work sweep the operator
asked all five projects to run. The full inventory went to CS, LW, RC and RSC as
`2026-09-19-1426-from-LL-REVIEW-machine-stray-work-sweep-our-tree-is-clean-the-107-GB-is-ours-and-referenced-and-three-drive-root-path-bug-artifacts.md`,
`sha256` `d618d01f3db46b0d92469353833c046e0c9e117e14309e70aca261999e6adcb7`, with
a correction of one claim in
`2026-09-19-1435-from-LL-CORRECTION-we-withdraw-one-claim-from-our-stray-work-sweep-rc-did-name-the-license-and-ops-91-is-blocked-on-our-operator.md`.
Both are in `moon_sync_inbox/_outbox/`. That sweep DELETED NOTHING, and this item
is the part of it that is ours to act on.

**The header finding, because it changes how a future sweep is run here.** An
orphaned EMPTY directory is reported by exactly ONE of the four enumeration
commands in common use. `git status --ignored --porcelain` does not list it,
`git status --porcelain --untracked-files=all <path>` does not list it, and
`git check-ignore -v <path>` exits 1 saying only that no rule matches. Only
`git ls-files --others --exclude-standard --directory` sees it, because git does
not report empty directories at all. Two of them existed here and both were
invisible to the command most sweeps run first. This is the repository's own
"an empty grep is a claim about your pattern" rule wearing a `git` costume: a
clean `git status --ignored` is a claim about git's reporting rule, not a claim
about the tree.

1. **`.backtest/` at the repository root is an untracked, unignored, EMPTY
   orphan.** Created 2026-09-12 18:43; it is the leftover staging root of this
   project's own back-test of whether a git hook could replace the in-session
   pre-flight, recorded in `docs/CYCLE_COST.md`. It is 0 files and 0 bytes.
   **Acceptance:** the directory is gone, OR it is in `.gitignore` with a comment
   saying what writes it. Whichever is chosen, a test asserts that
   `git ls-files --others --exclude-standard --directory` returns no line for it,
   and that test is seen to go RED by re-creating the directory before it is
   trusted. A guard that stays green when the condition it guards is restored is
   decoration.

2. **`.claude/worktrees/` is an empty, unignored directory inside a TRACKED
   directory in a PUBLIC repository.** Created 2026-09-12 21:18. `.claude/` is
   deliberately tracked here, unlike in the sibling trees, and
   `.claude/worktrees/` matches no `.gitignore` rule. It is harmless while empty
   and stops being harmless the moment a session uses it: the first file to land
   there is an untracked orphan with no owning lane, which is the exact condition
   `tests/test_lanes.py` fails on, and it would be a worktree's contents sitting
   one `git add -A` from publication. `C:\ll-worktrees` is the same shape outside
   the tree, also empty, also created before any worktree existed, and git
   registers neither - `git worktree list --porcelain` reports only the main
   worktree and `.git/worktrees` does not exist.
   **Acceptance:** `.claude/worktrees/` is either removed or gitignored with a
   comment naming why a tracked `.claude/` needs the exception, and the orphan
   guard is shown to fire on a planted file under it before the fix and not
   after. `C:\ll-worktrees` is outside this tree, so it is recorded here and
   removed by hand rather than by a test.

3. **`ops/inbox_watch.py:1232` hashes every file in a drop with no
   skip-directory filter, which is RC's content-key defect latent in our code.**
   The function walks `root.rglob("*")` and calls `read_bytes()` on each file to
   build a drop's content key. Nothing excludes `__pycache__` or `.pytest_cache`.
   RC measured that bytecode written into a verbatim drop changes its content key
   and re-surfaces the note as UNREAD in every reader. Measured here 2026-09-19:
   a `find` for `__pycache__` and `*.pyc` under `moon_sync_inbox` and
   `ops/runtime` returns zero rows, and `moon_sync_inbox/` currently has exactly
   one subdirectory, `_outbox`, which is classified as ours and never takes this
   path. **So the defect is UNEXERCISED, not absent**, and it becomes live again
   the next time a sibling drops a directory of Python files - which has already
   happened once, in the 49-file drop `OPS-34` was filed for.
   `rglob` cannot prune, so a filter added after the walk still pays the metadata
   cost and still reads the bytes; the fix is a different traversal.
   **Acceptance:** a regression test plants a `__pycache__/x.pyc` inside a
   synthetic drop directory, asserts the content key is UNCHANGED, and is seen to
   go RED against the current traversal first. The walk is converted to a pruning
   `os.walk` reusing `_SKIP_DIRS` rather than gaining a post-filter. The sibling
   inboxes are never touched by the test.

4. **Six harness project directories outside this tree are named after our own
   scratchpad paths, and the cause is ours.** Under `~/.claude/projects/` there
   are entries of the form
   `C--Users-<account>-AppData-Local-Temp-claude-C--Lanternlight-<session>-scratchpad-e2e-clone`
   plus `-e2e-worktree`, `-probe-clone`, `-probe-space-clone`, `-probe-worktree`
   and the bare scratchpad: 1 to 2 files each, roughly 420 KB in total. They
   exist because a session of ours ran with its working directory set INSIDE its
   own scratchpad while probing fresh clones and worktrees, so the harness minted
   a project identity per probe directory. CS has four of the same shape, so the
   cause is a shared practice rather than a bug unique to us.
   **Acceptance:** the fresh-clone and worktree probe procedure is amended to say
   that a probe RUNS FROM the repository root and addresses the clone by path,
   never by changing directory into it, with the reason stated - a change of
   working directory leaves a permanent artifact in a store no repository guard
   can see. The existing directories are outside this tree and are removed by
   hand.

**What this item explicitly does NOT claim.** `C:\ll-captures` is 10.7 GB in
19,241 files and is KEEP, not a cleanup target: it is the `--dest-base` in
`.claude/commands/continue.md:25`, `.claude/commands/loop.md:48` and
`docs/HEADLESS.md:136`, and individual frames in it are the cited evidence for
measured findings in `docs/AFFIXES.md` and `docs/FINDINGS.md`. Deleting any of it
would silently unfoot published measurements in a public repository. Whether a
subset is prunable is a per-frame reference audit nobody has run, and a read-only
sweep did not run it.

**And one thing was DECLINED rather than deferred.** RC asked every project to
set `tmp_path_retention_policy = failed` in `pytest.ini`, citing 68,630 temp
files across about nine pytest runs. Measured here: `%TEMP%\pytest-of-<account>`
holds 1,327 files in 932,552 bytes across three numbered directories, against a
whole-`%TEMP%` tree of 76,518 files and 3,263,424,324 bytes dominated by harness
scratchpads. Our pytest temp footprint is 0.03 per cent of the problem on this
machine, so the setting would be a real change with a nearly worthless effect.
Recorded as declined WITH the measurement, so a future session re-opens it on
evidence rather than on the recollection that somebody asked.

## OPS-95. Four items this session generated, three of them commitments already made to siblings - READY

Opened 2026-09-16. Each of these is either a defect measured here or a promise
this project put in writing into four sibling inboxes. A commitment that lives
only in an outgoing note is invisible to the next cold session, which is the one
failure this project's continuity design exists to prevent.

### 1. The licence gate needs a FIFTH trap: the wrapper does not clear the payload

`CLAUDE.md`'s third-party licence gate lists four traps: a repo contradicting
itself, a `LICENSE` naming nobody, the clearer not being the owner, and
source-available licences being DO-NOT-VENDOR. It does NOT carry the one RSC
named and this session walked into: **a permissively licensed wrapper can
package payload data under different and stricter terms.**

Measured here on archify: the root `LICENSE` is MIT with two copyright lines,
and `THIRD_PARTY_NOTICES.md` records packaged brand-mark data under
CC-BY-NC-SA-4.0, CC-BY-SA-3.0 and CC-BY-SA-4.0, plus a font under an open font
licence embedded as subsets in EVERY delivered artifact rather than only in ones
drawing a mark. This project PRACTISED the check and did not have it as a RULE -
and then published an FYI describing archify as MIT with two copyright lines,
which is a WRAPPER-level statement. A reader of that note would not have learned
about the non-commercial mark.

**The mechanism differs by outbound licence and both forms must be written
down**, because a tree reasoning only about its own outbound misses the other.
With a copyleft outbound a non-commercial term is a compatibility CONFLICT. With
a permissive outbound like ours the bite is different: republishing
non-commercial or share-alike bytes out of a PUBLIC permissive repository under
a permissive label.

**Acceptance:** a fifth trap is written into the licence gate section of
`CLAUDE.md` in this project's own words - read the third-party notices and
enumerate marks, icons, fonts, sample data and committed binaries with their own
terms BEFORE recording a decision - citing the archify measurement as its
instance, and naming both mechanisms. Not a vendored or shared document. This
was promised to four siblings in the note delivered 2026-09-16 at 0800.

### 2. A merge-gate baseline taken at HEAD is blind to uncommitted test work

Measured this session and stated in an outgoing note, so it is on the record
outside this tree already. The per-file baseline for `ops/merge_gate.py` was
derived in a detached worktree at HEAD. That correctly measured HEAD - a control
worktree reproduced 3439 across 70 files exactly, and exactly 2 of 70 files
differed from the primary tree, both of them modified-but-uncommitted test
files, with the deltas summing to the whole gap. CS's worktree divergence class
did NOT corrupt it.

**But a HEAD baseline is the wrong floor when work is already uncommitted.**
Ours would have handed the gate a per-file floor of 46 for a file the working
tree holds at 60, so a lane could delete 13 of the tests it added in the same
session and still pass the per-file check. That is exactly the failure the
per-file floor exists to prevent, one level down, and it is a property of
measuring at HEAD rather than of the worktree.

**Acceptance:** `ops/merge_gate.py` or its documented usage states that the
per-file baseline is measured in the PRIMARY WORKING TREE immediately before
dispatch, never at HEAD when uncommitted work exists; and a test pins the
distinction by constructing a baseline that is lower than the working tree for
one file and asserting the gate still reports the drop. Watch the red first.

### 3. `tests/test_provenance.py` has a latent row-swallowing slice

Found by a lane while reading for something else, probed in memory, and NOT
patched because that lane did not own the file. Four sites use `block[2:]` to
skip a Markdown table's header and separator rows - `tests/test_provenance.py`
lines 191, 365, 376 and 392. If a separator row is ever deleted from a table the
slice silently swallows **the first data row** instead, and the guard keeps
passing over a table it is no longer fully reading.

It is LATENT rather than a live false green: the consumers compare full
dictionaries, so a missing row currently surfaces as a mismatch elsewhere. That
makes it a trap waiting for a refactor rather than a present defect, which is
exactly the kind this project writes down rather than leaves for rediscovery.

**Acceptance:** the slice is replaced by something that locates the separator
row rather than assuming its index, or asserts the row it is skipping IS a
separator; and a test deletes a separator from a fixture table and fails. Prove
it non-vacuous - break the table, watch the red, restore.

### 4. The fleet position on a shared machine-wide skills directory is NO, and it is recorded here rather than only in an outgoing note

LW and RSC each asked the fleet whether there should be a shared machine-wide
agent-skills directory. **This project answered NO on 2026-09-16** and the
answer is recorded here so a cold session does not have to re-derive it or,
worse, answer differently.

The grounds are this repository's own, not agreement with siblings: the
standalone rule at the top of `CLAUDE.md` (no shared code, no shared ports, no
shared keys, and a shared import is a shared failure); `OPS-48` question 3,
which refuses granting an outside party access to this tree or this machine by
default and says a SESSION may not grant it; and THE ONE ASYMMETRY, under which
a session can say NO with full authority and cannot say YES at all.

RSC's argument is stronger than our scope argument and is recorded as the better
form: **the act is unreviewable AFTER the fact** - a directory every tree reads
and no tree owns has no diff to inspect - and that holds even for a change all
five trees would have approved.

Measured here so the position rests on something: this repository has ZERO
`SKILL.md` files, no `.claude/skills/` directory, and the skills this session can
see under its own name are user-level and absent from a fresh clone. We already
carry a small version of the invisibility being proposed at fleet scale, and it
is already a cost.

**What would change it:** an operator ruling in a session of ours, written into
`CLAUDE.md` the way the three existing exceptions are, plus an owner, an
allow-list, an admission rule, and a digest pin. Even then this project would
want a local guard asserting that no file outside the repository root is
load-bearing for its gates. **No session may adopt it without that ruling.**

## OPS-92. Evaluate `archify` for this repository's diagrams - DECLINED 2026-09-16

### DECLINED 2026-09-16 - the trial ran, and the producing lane's headline was struck by its own adversarial pass

**The decision is DECLINE.** `archify` is not adopted. Nothing is vendored, no
committed artifact here is generated by it, and no Node dependency enters this
repository. Criteria 1 through 4 are discharged below; criterion 5 is moot
because nothing was vendored. The reason is written out rather than left as a
verdict, because a decline reason goes stale faster than a count does and the
next session handed this link needs to re-check it rather than re-run it.

**Criterion 1 is MET - the `LICENSE` was read directly, name and copyright
lines.** It is MIT, and it carries **two** copyright lines rather than one:
`Copyright (c) 2026 tt-a1i (Archify)` and `Copyright (c) 2025 Cocoon AI`. The
file's sha256 is
`b799ab081703e7821ae5096d2c1abdf14bbdc75e8ea1c4045998c36ed6db9706`. Nothing in
the `LICENSE`, the README or the manifest contradicts the MIT name, so this
repository's second license-gate trap does not fire - but the third one is live,
because a second holder means the first cannot unilaterally relicense.
`THIRD_PARTY_NOTICES.md` additionally records packaged brand-mark data under
CC-BY-NC-SA-4.0, CC-BY-SA-3.0 and CC-BY-SA-4.0. Those bear on **vendoring** and
not on **running**, and since the decision is to decline they are recorded
rather than acted on.

**Three premise corrections, so the next session does not repeat the search.**
The npm package named `archify` is an unrelated squatter, `justin-calleja/archify`,
and is not this project. This project is an agent **Skill**, installed through
`npx skills add`. Its `archify/package.json` is marked `"private": true` and the
repository has no root `package.json`, so an `npm install archify` reaches
entirely different software.

**Criterion 2 - the trial ran, and the producing lane's headline is STRUCK
ENTIRELY rather than softened.** The lane reported an INVERSION: that archify
passed the FALSE version of the `LL-0256` data-flow diagram and REJECTED the
corrected one, which would have made the tool an active hazard. **That finding
is refuted and must not be cited.** The adversarial pass reproduced the failure,
then fixed it with four cosmetic layout edits, after which the truthful topology
passes cleanly - 9 artifact checks, 0 errors, 0 warnings, exit 0,
`evidence.verified` true, 4 references. The cause was the lane's own
hand-authored geometry: it had placed the `ember` node at x=520, to the LEFT of
`tail` and `readers`, which forces right-to-left edges. The corrected graph is
simply DENSER than the false one - it contains a K2,2 where the false one is a
funnel - and density is not falsity. The tool was never judging truth.

Recorded here explicitly as a lane error caught by the adversarial pass, because
it is this repository's own rule arriving live: a producer never grades its own
output, and agreement between two agents is not evidence.

**The graded answer to criterion 2, stated precisely, because the flat version
of it is overstated in BOTH directions.**

- archify's `validate` mode would **NOT** have caught the `LL-0256` renamed-node
  repair, and the reason is STRUCTURAL rather than a tuning miss. In its typed
  intermediate representation `sources` exists only on `components`;
  `connections` carry `from`, `to`, `label` and geometry, and the schema sets
  `additionalProperties: false`. So adding provenance to an EDGE is REFUSED by
  the schema rather than merely unsupported, and no configuration reaches it.
  Probed both ways: node citations deliberately pointed at the wrong modules
  still return `verified` true, and an edge labelled "injects DLL" running from
  the redactor to the game process - an `ADR-001` violation on its face - passes
  the showcase clean. The negative controls DO fire (a missing file, a line
  number out of range), so the checks are SCOPED rather than dead, which is the
  distinction that matters when deciding whether the gap is fixable.
- **But the flat claim "archify would not have caught it" is itself OVERSTATED,
  and this is the half a cold session most needs.** A `compare` mode exists and
  the producing lane never ran it. Run against the `LL-0256` defect itself - a
  label-only rename - it prints `changedFields ["/label","/sublabel"]` with
  `connections {added 0, changed 0, removed 0, rerouted 0}`. That is exactly the
  discriminator for "a node was renamed and the topology did not move", which is
  the shape of the defect. It does NOT fail: exit 0. And it diffs two AUTHORED
  intermediate representations against each other rather than diffing a diagram
  against the code. So `compare` SIGNALS the defect to a reader who runs it and
  reads the field; it does not CATCH it mechanically. Adopting it would have
  bought a signal that still depends on a human reading a line of output, not a
  guard that turns something red.

**Check counts, re-derived from source rather than from the README:** 11
`addCheck` call sites producing **9 distinct check names**. Two of the nine,
`single_svg` and `finite_svg`, are well-formedness checks rather than geometry
checks, so "9 checks" over-describes what is actually verified about a diagram.

**Criterion 3 - the decision and its grounds, each one re-checkable later.**

1. **No edge provenance, by schema design.** The failure this repository
   actually had - `LL-0256` and `LL-0254` - is a false EDGE, and edges are the
   one thing archify's verification cannot reach. That is the hypothesis this
   item was opened to test, and it fails.
2. **A fresh clone could not reproduce a committed artifact without Node.** It
   needs Node 18 or newer plus a bootstrap that is either a network fetch or
   about 8.5M of vendored dependencies. `CLAUDE.md`'s continuity story is that a
   cold session resumes from files alone, and this item named that cost before
   the work started.
3. **Artifact size, quoted as approximate on purpose.** About 810 KB of
   self-contained HTML for an 11-node diagram. **Do NOT quote an exact byte
   count**: the adversarial pass's own two artifacts measured 811,309 and
   809,757 bytes, so an exact figure is not reproducible and saying so IS the
   finding.
4. **Committing the artifact would turn the suite red.** The generated HTML
   carries 322 non-ASCII bytes, and `tests/test_ascii_hygiene.py` walks 221
   files, treats `.html` as text, includes `third_party/` in scope and walks
   UNTRACKED files as well. That is a measured mechanical consequence rather
   than a preference.

**Criterion 4 is discharged by the decline** - there is no integration shape to
name because nothing is integrated, and no Node cost reaches `README.md` or
`docs/OPERATIONS.md` because nothing runs. **Criterion 5 is moot**: nothing was
vendored and the `OPS-84` shape was never reached.

**What would reverse this, named so the decline can be revisited on evidence
rather than re-argued from the README.** Edge-level `sources` in the IR schema,
so a connection can cite the code that proves it, together with a `validate`
exit code that is non-zero when an edge's citation does not hold. That is one
named change and it is the only one that would make this tool address the
failure this item was opened for. The Node cost and the artifact size would not
need to change: those are costs, and the edge gap is the disqualifier.

The operator named this in chat on 2026-09-15 and asked that the next session
implement it: `https://github.com/tt-a1i/archify`. Written down here rather than
left in a transcript, because a direction that lives in one context window is a
direction a cold session never sees.

### What it is, from its own README, read once and not yet verified

A Node.js tool that turns a codebase or a system description into interactive,
self-contained HTML diagrams. Five diagram types - architecture, workflow,
sequence, data-flow, lifecycle. A typed JSON intermediate representation is
compiled deterministically into HTML and SVG, with a validation pass that emits
machine-readable repair receipts, a before/delta/after comparison mode aimed at
PR review, and source verification with revision-checked file references. It is
written for agent use - it names Claude Code among its intended callers.

Every sentence above is that project's description of itself. Nothing in it has
been run or measured here.

### Why this repository in particular should want it

Because the failure it targets has already happened here, twice, in the last two
days.

- `LL-0256`: the README's mermaid diagram drew all four data surfaces flowing
  into the redactor when only the log reader redacts. The fix RENAMED the node
  and left the topology alone, so the picture still made the false claim after
  the repair, and only the wrap's refutation pass caught it by reading the
  committed edges rather than the claim.
- `LL-0254`: eight false claims in a rewritten public README, one of them a
  diagram drawing a data flow the code does not have.

A diagram in this repository is an artifact that asserts something about the
code and that nothing checks. "Source verification with revision-checked file
references" and "deterministic checks" are aimed exactly there. That is the
hypothesis worth testing, and it is a hypothesis rather than a finding.

### The two gates this runs into, named up front so neither is discovered late

**The license gate.** Its README says MIT, which is permissive and compatible
with this repository's Apache-2.0. That is NOT yet a cleared license. A summary
read of a project page is not a read of a `LICENSE` file, and this repository's
own gate says to read the copyright LINE and not just the license name - a
`LICENSE` can name nobody, a repo can contradict itself, and the person who
cleared it may not own it. So the license is UNVERIFIED and is recorded that
way.

**The vendoring question may not even arise.** USING a tool is not vendoring it.
If archify is run as an external generator whose OUTPUT we commit, the third
party gate is not reached at all, and the only question is whether committed
output derived from an MIT tool carries an attribution obligation - which for
generator output it normally does not, but which is a question to answer rather
than to assume. Prefer that shape. Copying source into `third_party/` is the
expensive path and needs the full `OPS-84` treatment plus an operator ruling.

**A third cost, which is not a gate but is real.** This is a Node.js toolchain
in a repository that is Python and Windows and has no Node dependency today.
Anything that makes a fresh clone need `npm` to reproduce a committed artifact
is a regression in this project's continuity story. A generator that runs on
the operator's machine and commits a static HTML or SVG file does not have that
problem; a build step wired into the suite does.

### Acceptance

1. The `LICENSE` file is read directly from the repository - the license name
   AND the copyright line - and the answer is recorded here with whatever
   contradiction, if any, exists between the `LICENSE`, the README and any
   package manifest. An unread license is not a cleared license.
2. One diagram in this repository is regenerated through it as a TRIAL, against
   a claim that can be checked - the README data-flow diagram from `LL-0256` is
   the obvious candidate, because the false version and the corrected version
   are both on record and the tool's output can be graded against a known
   answer. Record whether it would have caught the renamed-node repair.
3. The decision is recorded either way. Adopting it is a decision; declining it
   is a decision; and a decline reason goes stale faster than a count does, so
   whichever way it goes, the reason is written down with the date.
4. If adopted, the integration shape is named explicitly: what runs it, when,
   what is committed, and whether a fresh clone can reproduce the committed
   artifact WITHOUT Node. If it cannot, that cost is stated in `README.md` or
   `docs/OPERATIONS.md` rather than discovered by the next person who clones.
5. Nothing is vendored under `third_party/` without the full `OPS-84` shape - a
   pre-copy hash against the published digest, a NOTICE naming upstream,
   license, holder, digest and every change - and an operator ruling. Using it
   needs neither.

## OPS-93. Evaluate `context-mode` for this project's context discipline - DECLINED 2026-09-16

### DECLINED 2026-09-16 - and the grounds are CORRECTED from the ones the producing lane reported

**The decision is DECLINE.** `context-mode` is not installed, nothing is
vendored, no hook entry was written, and no `.claude/settings.json` was touched
in this tree or outside it. The grounds below are NOT the grounds the producing
lane reported: its headline safety finding was refuted by the adversarial pass,
and the correction runs against the tool rather than for it.

**Criterion 1 is MET, and criterion 2 is answered in one sentence.** The
`LICENSE` file is 3840 bytes, sha256
`92f11a867c41c9e575ccb978ff205ae2011c244a14aa3c576e914e537105caa0`, byte
identical at `main`, at `master` and at `HEAD`. Line 1 reads
`Elastic License 2.0 (ELv2)`; line 3 reads `Copyright 2026 Mert Koseoglu`.
`package.json` declares `"license": "Elastic-2.0"`, the README badge says ELv2,
and the GitHub API reports `spdx_id` `NOASSERTION` - which is the API declining
to recognise the identifier, not a contradiction inside the repository. Full
recursive trees at `main`, at tag `v1.0.169` and at branch `next` were scanned:
exactly ONE license blob, no `NOTICE`, no `AUTHORS`, no second copyright holder.
**DO-NOT-VENDOR, recorded explicitly so nobody re-derives it** - ELv2 is
source-available rather than open source, the same category `CLAUDE.md` names
for BUSL-1.1 and marks DO-NOT-VENDOR whatever anyone offers. The
USE-versus-VENDOR sentence: **using it is permitted by its own grant clause, and
copying any byte of it into this tree is refused permanently.**

**THE FINDING THAT DECIDES THIS ITEM, and the producing lane had it backwards.**
The lane reported "no upload, sync or telemetry found". That is REFUTED against
the SHIPPED npm tarball. `hooks/platform-bridge.mjs` is a self-described
fire-and-forget event forwarder: line 286 POSTs to a configured URL with the
full event envelope as the body and a bearer `Authorization` header built from a
configured `api_key`. It is WIRED IN rather than dead code -
`hooks/session-loaders.mjs:161` calls `maybeForward`, and that loader is
imported by the `sessionstart`, `posttooluse`, `userpromptsubmit`, `precompact`
and `stop` hooks. It is **DORMANT rather than absent**: the forwarder is gated
on a config file holding an `api_key` with a `ctxm_` prefix, and no writer for
that file ships today. Lines 286 to 292 and line 30 were confirmed in the
tarball by the merger independently rather than relayed from the report.

**Why the lane missed it, which is the transferable lesson and the reason this
paragraph exists at all.** The lane audited `src/`, 117 files. The forwarder
lives in `hooks/`, 98 files. That is `CLAUDE.md`'s own anti-pattern - "an empty
grep is a claim about your pattern, not about the codebase" - landing on a live
safety question rather than on a count. A clean negative from a search is a
claim about where you searched.

**The published artifact is NOT reproducible from the repository.** Three
measurements of the same nominal build: the tag at 673,945 bytes, `main` at
674,733 bytes, and the npm tarball at 674,738 bytes, with 267 differing lines.
**Auditing a published package means auditing the PACKAGE**, written down here
so it is not learned again the expensive way.

**But the CAUSAL half of that sentence was WRONG and is WITHDRAWN - 2026-09-16,
on LW's refutation, re-measured here before conceding.** An earlier version of
this paragraph said "so auditing the source would never have settled this", and
this project published that claim to four sibling trees in two separate notes.
It is false for the file that actually matters. `hooks/platform-bridge.mjs` is
BYTE-IDENTICAL between the shipped tarball and the public repository: 12,160
bytes in both, `sha256`
`74d18338a4fbcc46c406f8791a819a213fd78551bbfbc99eba1f914692699294`, identical at
`main`, `master` and `HEAD`, measured on this machine against our own copy of
the tarball. Nit corrected 2026-09-16 on our own wrap refutation: `master` is NOT a separate branch upstream - only `main` and `next` exist and the raw host ALIASES `master` to the default - so "identical at main, master and HEAD" is two distinct refs wearing three names. The byte claim is unaffected and the digest reproduces; the ref count was loose. The forwarder was always readable on GitHub.

**So the audit did not fail for the reason we published. It failed for the
reason we had already written down one paragraph above, and only that one: it
searched `src/` and the forwarder lives in `hooks/`.** Downloading the tarball
is what the adversarial pass HAPPENED to do; it is not what made the difference,
and a repository-wide read would have found the same file. The two facts are
independent - package divergence is real at PACKAGE scope and is not a fact
about this file - and we welded them into a causal claim that the evidence does
not support. That is this repository's own "a rendered field is not evidence of
a producer" in a new costume: a true observation next to a true observation does
not make one the cause of the other.

The correction went to all four siblings rather than being fixed quietly here,
on the `LL-0244` rule. LW is credited for the refutation.

**"Not the MSIX exposed shape" is REFUTED IN PART**, against this item's own
point 3. The database path claim STANDS: the store resolves to
`<resolveClaudeConfigDir()>/context-mode/{sessions,content}/<sha256-16>[suffix].db`,
which lands under the user profile's `.claude` directory, and `os.homedir()`
ignores `HOME` on win32 - measured here, not assumed. But
`hooks/platform-bridge.mjs` writes its config under
`%APPDATA%\context-mode\platform.json`, and `build/cli.js:312` uses
`%LOCALAPPDATA%`. **Both are the exposed shape** named in the MSIX
package-shadow section of `docs/OPERATIONS.md` and measured on this machine in
`LL-0259`. One sub-claim survives intact: the shipped `build/session/extract.js`
imports only `./pricing.js` and has no network at all, and its `sentry`,
`apiKey` and `Authorization` hits are comments inside a redaction scrubber.

**Criterion 3 is ANSWERED rather than left as a gap.** It asked for the store's
gitignore status to be asserted by a test in the family of
`tests/test_no_inbox_in_git.py`. Nothing lands inside the repository under this
decision, so there is no path for such a test to assert about, and writing one
would be decoration - a guard that cannot go red is not a guard. That is the
answer, recorded as an answer so the criterion is not later read as skipped.

**Criterion 4's PREMISE is REFUTED, and the real risk is the opposite of the one
this item named.** The item said an installer rewriting `.claude/settings.json`
"will trip those guards". It would not. The installer writes the USER-level
`~/.claude/settings.json`, not this repository's, so
`tools/hook_command_guard.py` never sees it. **The real risk is SILENCE, not a
red suite** - a machine-wide hook this repository's guards are structurally
unable to observe. There is no `--local`, `--scope` or `--global` flag that
narrows it; `--project` affects index and search only.

**It is worse than "writes a user-level file", and this was measured here on
2026-09-16 rather than taken from a sibling.** RSC reported the shape in a note
the same day; the standing rule is to re-measure a claim rather than relay it,
so the shipped npm tarball's `scripts/postinstall.mjs` was read directly. It
does three things at INSTALL time, none of them requested by the installing
user:

- resolves the user-level `.claude/settings.json` and REWRITES its
  `enabledPlugins`, in a code path whose own comment calls that file "the file
  Claude Code's plugin loader actually reads";
- rewrites `.claude/plugins/installed_plugins.json`, twice, in two separate
  repair passes;
- runs `execSync` on `mklink /J` to create a filesystem DIRECTORY JUNCTION when
  the resolved package directory is not where it expects.

The script calls these "heal" operations and they are plainly meant as
robustness rather than as anything hostile - no claim to the contrary is made
here, and none is needed. The point is the BLAST RADIUS and who can see it. This
is not a new file appearing beside our guards; it is an unprompted edit to the
configuration that decides what loads into every agent session on this machine,
for all seven repositories in the port registry at once, performed by a
`postinstall` hook that runs before anyone has read anything. A repository-local
guard cannot observe it, and the edit has no diff anybody reviews.

That converts decline ground 3 below from "no local guard can see the file it
writes" into something sharper: the install MUTATES the loader's own
configuration, machine-wide, at install time.

Two facts about the LOCAL guards were re-measured while establishing that, and
one of them was undocumented. Pin-by-exact-string is CONFIRMED, and the pin is
**BIDIRECTIONAL**: DELETING a pinned rule also turns the suite red, which
nothing had recorded. And this item's claim that "a fourth turns the suite red"
is OVERSTATED - only a fourth ABSOLUTE permission rule does. Verified by
mutating a scratch COPY through `check_settings_text` with the anchor asserted
to have matched first, and by `python -m pytest
tests/test_hook_command_roots.py` -> 60 passed.

**Criterion 5 is UNMET, and is recorded as unmet rather than quietly
satisfied.** The context saving was not measured on this repository, because
nothing was installed and measuring it would have required installing it. The
vendor's 98 percent figure therefore stays attributed as a CLAIM and is never
repeated here as a measurement. That is omit-rather-than-guess applied to a
number somebody else published.

**Criterion 6 - the decline grounds, with the date, each re-checkable.**

1. **A default install is machine-wide.** Seven repositories share this box.
   There is no per-project install mode, so an audit of this tool would be an
   audit on behalf of every one of them, and this session speaks for one.
2. **There is no version pin**, so the audit expires on every silent
   self-update. What was audited today is not what runs tomorrow.
3. **No local guard can see the file it writes.** The user-level settings file
   sits outside every guard this repository has, so the failure mode is silence
   rather than a red suite - and silence is the one failure this project's
   whole guard design is built to avoid.
4. **The dormant forwarder plus the non-reproducible published artifact.**
   Dormant is a configuration state and not a property of the code, and the code
   that would actually run is not the code that can be read in the repository.

**THE REVERSAL CONDITION, so the decline can be revisited on evidence rather
than re-argued.** Reverse this if ALL of the following hold: the project ships a
documented per-project or per-directory install that does not write the
user-level settings file; the event forwarder is either removed or made
refusable by a configuration this repository can assert in a test of its own;
and the published package is reproducible from a tagged source tree, so what is
audited is what runs. A version pin and a different license would both be
welcome and neither is sufficient on its own.

The operator named this in chat on 2026-09-15 alongside `OPS-92` and asked that
the next session implement it: `https://github.com/mksglu/context-mode`.
Recorded here for the same reason as `OPS-92` - a direction that lives in one
context window is a direction a cold session never sees.

### What it is, from its own README, read once and not yet verified

A TypeScript tool that shrinks an agent's context window cost by SANDBOXING tool
output, which it advertises as a 98 percent reduction, and by persisting session
memory in SQLite with FTS5 full-text search. It ships six sandbox MCP tools that
execute code in twelve languages, five meta-tools, a hook system that captures
file edits, git operations, errors, tasks and user decisions, and adapters for
seventeen agent platforms including Claude Code. It needs Node 22.5 or Bun.

Every sentence above is that project's description of itself. Nothing in it has
been run or measured here, and the 98 percent figure is a vendor claim rather
than a measurement - this project's own doctrine is that a number with no
measured source is omitted rather than repeated, so it is quoted as a claim and
attributed.

### Why this project might want it

Context exhaustion is a real cost here. `CLAUDE.md`'s own orchestration section
exists because the merger's context is the one that must not fill, and its
standing remedy - agents write bulk output to a file and return a few hundred
words - is exactly the problem this tool addresses mechanically. A session that
has to be compacted mid-merge is the failure this repository's whole continuity
design works around.

### FOUR THINGS THAT MUST BE SETTLED BEFORE ANYTHING IS INSTALLED

These are stated up front because each one would be expensive to discover after
an install, and none of them is a reason not to evaluate it.

**1. The license is ELv2, and that is DO-NOT-VENDOR here.** The README badge
reads Elastic License v2 with `mksglu` as the holder. ELv2 is SOURCE-AVAILABLE,
not open source - the same category `CLAUDE.md` already names for BUSL-1.1,
which it lists as DO-NOT-VENDOR "whatever anyone offers". No byte of it goes
into this tree. USING it is a separate question from vendoring it and is not
blocked by that sentence: ELv2 permits use. The distinction to hold onto is that
this can be a tool on the machine and can never be a file in the repository.

**2. It writes a SQLite store of captured session content, and this repository
has a redaction rule.** Its hook system captures file edits, git operations and
errors. In THIS tree those carry game-log excerpts, and the log contains the
operator's SteamID64, Steam persona, GSDK openID and userId, an EOS
ProductUserId and an IP-resolved location. `ADR-004` scopes redaction to a CLASS
OF DATA and a DIRECTION - any operator identifier crossing off this machine or
into git history. A local SQLite file crosses neither, so this is not
automatically a violation. What it IS: a new unredacted store outside
`ops/runtime/`, whose path, gitignore status and backup behaviour must be known
before it is created rather than after. If that database can ever be
synchronised, uploaded, or swept into a commit, it is a live `ADR-004` failure.

**3. Where its database lives decides whether it is readable at all.**
`docs/OPERATIONS.md` now records the MSIX package shadow measured on this
machine on 2026-09-15: a harness-written file under `%LOCALAPPDATA%` or
`%APPDATA%` can land in the package twin, and later reads from the harness can
return the twin silently. A tool that stores session memory under AppData and is
driven from inside the harness is exactly the exposed shape. Repo roots are not
virtualised. Settle the path before trusting anything the store says.

**4. It installs HOOKS, and this repository guards its hook configuration
hard.** `.claude/settings.json` here is pinned by `tools/hook_command_guard.py`
and `tests/test_hook_command_roots.py`: every hook command must reach its script
through `$CLAUDE_PROJECT_DIR` and never an absolute root, the three absolute
permission rules are pinned by exact string, and a fourth turns the suite red.
An installer that rewrites that file will trip those guards. That is the guards
working, not a defect - `OPS-61` exists because absolute roots made hooks answer
about the wrong repository in every clone and worktree. Any adopted wiring is
written by hand into that file, with its reason, the way every other entry there
was.

### Acceptance

1. The `LICENSE` file is read directly - name and copyright line - and recorded
   here, with any contradiction between it, the README badge and the package
   manifest. A badge is not a license file. If it is ELv2 as advertised, record
   DO-NOT-VENDOR explicitly so nobody re-derives it.
2. The USE-versus-VENDOR decision is stated in one sentence and nothing is
   copied into this tree under either answer without an operator ruling and the
   full `OPS-84` shape - which ELv2 would not survive anyway.
3. Before any install: the store's on-disk path is located and recorded, its
   gitignore status is asserted by a test in the family of
   `tests/test_no_inbox_in_git.py`, and whether it sits under `%LOCALAPPDATA%`
   or `%APPDATA%` is answered against the shadow section in
   `docs/OPERATIONS.md`.
4. If it is installed, no hook entry reaches `.claude/settings.json` by an
   installer. Each is hand-written with its reason in the `$comment`, reaches
   its script through `$CLAUDE_PROJECT_DIR`, and `python -m pytest
   tests/test_hook_command_roots.py tests/test_no_hardcoded_home_path.py` is
   green afterwards.
5. The context saving is MEASURED on this repository rather than quoted. A
   before-and-after on one real orchestrated session, with the numbers recorded.
   The 98 percent figure is the vendor's; if it cannot be reproduced here, that
   is the finding and it gets written down.
6. The decision is recorded either way, with the date and the reason, because a
   decline reason goes stale faster than a count does.

## OPS-94. Review `timharris707/skills` for adoption - REVIEW COMPLETE 2026-09-16, three candidates recorded, nothing adopted

### REVIEW COMPLETE 2026-09-16 - all 23 classified, three candidates, nothing adopted this session

**Every count below was re-derived at commit
`a9317e03733da7f54b5da0eaa8edcb2697495cf5`.** An unpinned count goes stale the
moment upstream pushes, and this review's own producing lane filed five wrong
counts, so the ref is part of the finding rather than a footnote to it.

**THE COUNT IS 23 AND THE ROADMAP NEEDED NO CORRECTION.** The producing lane's
headline was that the number is "24, not 23". That is REFUTED. The upstream
README states at line 224 that only PROMOTED buckets ship and that nothing under
`in-progress/` appears in the marketplace, and `buckets.json` and the CI
configuration agree with it. `skills/in-progress/fit-audit` is therefore not one
of the shipped skills. All 23 names this item listed from the README resolve to
a real directory at the pinned sha, with no spurious name and none missing.
**Recorded as the lane's own error**: a filed count is a hypothesis, and that
rule applies to a subagent's count exactly as it applies to a document's.

**Four subsidiary tallies from the same lane were also wrong and are corrected
here**, because each would otherwise be cited later as a measurement:
`references/` holds **14** files and not 8; `CHANGELOG.md` records **8** entries
and not 4; `_conductor` is **29** and not 30; and `fit-audit` carries no
`agents/openai.yaml`, so "every skill ships a Codex adapter" is wrong as stated
- it is 23 of 24.

**What the lane MISSED matters more than what it got wrong.** Repository-wide
there are **48** `SKILL.md` files, not 24. The other 23 are a complete mirror at
`plugins/clickai-codex/skills/`, with DIFFERENT blobs from the `skills/` tree
and its own `LICENSE.md`. **Anyone adopting from this repository must say WHICH
tree they copied from**, because a digest taken from one tree does not identify
a file in the other.

**Criterion 1 - the license chain, read directly at every hop.** The root
`LICENSE.md` is MIT, `Copyright (c) 2026 Tim Harris`; a plain `LICENSE` at the
root 404s, so the filename matters. MIT into Apache-2.0 clears this
repository's gate. Each upstream holder was confirmed by fetching that project's
own `LICENSE` rather than by reading a credit line: Matt Pocock (MIT), Lauren
Tan (MIT), and Siqi Chen (MIT, `blader/humanizer`, credited upstream only by
handle).

**Two corrections to the lane on the license axis.** First,
`human-copywrite`'s Apache-2.0 `LICENSE` DOES name a holder, at line 189 - the
lane reported that it named nobody - and that name is **non-ASCII and therefore
cannot be quoted verbatim in this repository**. That collision is itself worth
recording: a license gate that requires reading the copyright LINE meets an
authoring rule that forbids reproducing it, and the resolution is to record that
a holder exists and to cite the line where it is. Second, the `cursor/plugins`
scope worry is **CLOSED rather than left open**: that root is genuinely
unlicensed (the API returns null and three filename spellings 404), but
`pstack/README.md` states MIT and all 15 plugin directories carry their own
`LICENSE`.

**Two genuinely UNLICENSED sources exist and NO candidate depends on either**:
an on-camera reviewer whose grading frame `fit-audit` credits, and two private
repositories behind `ingest`. Both belong to skills that are DECLINED anyway.
One hop the lane missed - `blader/humanizer` builds on Wikipedia content under
CC BY-SA - likewise touches only DECLINED skills. And exactly three skills carry
**no Attribution section at all**, despite the README claiming that section is
the record: `advisory-board`, `handoff` and `orchestrate`. The README's promise
about attribution is not true of its own tree.

**Criterion 2 - the classification, all of them, so an unmentioned skill is not
indistinguishable from an overlooked one.** 8 DUPLICATE, 3 CANDIDATE, 13
DECLINED. That is 24 entries covering the 23 SHIPPED skills plus `fit-audit`,
which is classified because it exists and is marked as not shipped so that it is
never counted among the 23.

| # | skill | class | reason |
|---|---|---|---|
| 1 | router | DUPLICATE | `docs/INVENTORY.md`'s command table plus `CLAUDE.md`'s living-docs header block are this project's orientation entry point. |
| 2 | setup | DECLINED | A once-per-repo interview that asks the decider to confirm each answer. `CLAUDE.md` IS the binding doc, and FULL AUTHORITY item 2 forbids the question. |
| 3 | domain-memory | DUPLICATE | `docs/adr/` for decisions, `docs/OBSERVED_IDS.md` and `docs/FINDINGS.md` for the glossary, with the observation method recorded - a stricter bar than the upstream's. |
| 4 | grilling | DECLINED | Overturns the ROADMAP guess. A blocking interview - "Put each one to them and wait" - against `loop.md`'s "Never block on the operator". |
| 5 | decision-map | DECLINED | Overturns the ROADMAP guess. "the round brief is the deliverable, never the answer" is the verbatim inverse of FULL AUTHORITY item 2. |
| 6 | advisory-board | DECLINED | Overturns the ROADMAP guess. Shells out to `codex exec`, `gemini -p` and `grok` - egress plus an API key, refused under `ADR-004` and the no-shared-keys rule. |
| 7 | research | DUPLICATE | `.claude/commands/lane-research.md` plus `CLAUDE.md`'s measurement doctrine, which fixes a trust order the upstream lacks. |
| 8 | prototype | DECLINED | Its own text exempts prototype branches from test-first rules. TDD is a rule no authority here reaches. |
| 9 | codebase-review | DECLINED | Its "defer-and-carry" disposition is a fourth destination for found work; `CLAUDE.md` names exactly three. |
| 10 | ingest | DECLINED | No measured need, and its transcription pipeline would route operator-recorded audio through a path with no `redact.py` in it. Also not vendorable - two private upstreams. |
| 11 | to-tickets | DECLINED | Overturns the ROADMAP guess. Targets a GitHub issue tracker - a second tracker beside `ROADMAP.md` - and carries an "iterate until they approve" gate. |
| 12 | wizard | DECLINED | Generates interactive bash for human-only procedures. The one real instance here is a fresh clone, already covered by `scripts/install_hooks.py`. |
| 13 | handoff | DUPLICATE | `.claude/commands/done.md` and `ops/handoff.py`, where the handoff is a tracked file rather than a chat message. |
| 14 | show-me-your-work | DUPLICATE | `docs/LEDGER.md`, the lane fragments and `ops/stop_audit.py`. Its closing gate re-enters advisory-board's egress by a side door. |
| 15 | orchestrate | DUPLICATE | `CLAUDE.md`'s Session Default, the eleven `lane-*.md` contracts and `ops/lane_contract.py`. |
| 16 | adversarial-review | DUPLICATE | `CLAUDE.md`'s self-adversarial baseline, `lane-verify.md`, `.claude/agents/verifier.md` and `ops/merge_gate.py`. |
| 17 | diagnose | **CANDIDATE** | Ranked second. No TRACKED local equivalent exists - see the criterion 3 correction below. Cannot be adopted as-is. |
| 18 | implement | DUPLICATE, and it WEAKENS | "the seam-scoped bar lets code at no named seam ship with its tests in the same commit". `CLAUDE.md` permits none. Local rule wins. |
| 19 | blast-radius | **CANDIDATE** | Ranked first. `ops/merge_gate.py` is a done-claim checker and says nothing about what a change breaks. |
| 20 | writing-for-agents | **CANDIDATE** | Ranked third. `CLAUDE.md`'s authoring rules govern bytes; nothing local governs what to CUT from an agent-facing document. |
| 21 | writing-for-humans | DECLINED | Aimed at public marketing prose. This repository's public surface is read by engineers and by cold sessions, and the register is already fixed. |
| 22 | plainspoken | DECLINED | Overturns the ROADMAP guess. Always-on prose governance - a second answer to CAVEMAN ULTRA. |
| 23 | huh | DECLINED | Overturns the ROADMAP guess. Triggered by a human reading chat and saying it did not land; the operator here cannot read chat while playing. |
| - | fit-audit | DECLINED, and NOT one of the 23 | Lives under `skills/in-progress/`, which README line 224 excludes from what ships. Its grading frame is credited to an on-camera reviewer with no license statement. |

**The ROADMAP's six guessed candidates are ALL OVERTURNED**, and the reasons
were confirmed verbatim against the upstream bodies at the pinned sha, on
whitespace-collapsed copies because a line-oriented grep is a claim about line
breaks. Seven decline reasons were spot-checked verbatim and seven held.

- `decision-map`'s hard guardrail reads "record the recommendation and stop
  there: the round brief is the deliverable, never the answer". FULL AUTHORITY
  item 2 says the best recommendation is taken IMMEDIATELY. A direct
  contradiction rather than a near miss.
- `advisory-board` literally shells out to `codex exec`, `gemini -p` and `grok`.
  That is egress plus an API key, refused under `ADR-004` and under the
  no-shared-keys rule that binds under every exception in `CLAUDE.md`.
- `plainspoken` is an always-on prose governor and would be a second answer to
  CAVEMAN ULTRA, which the operator confirmed in chat on 2026-09-06.
- `huh` is triggered by a human reading chat. The operator here cannot.
- `grilling` is a blocking interview whose Done-when requires the decider to
  confirm, and `to-tickets` carries the same approval gate on top of a second
  tracker.

**The three CANDIDATES, with the gap each fills.**

- **`blast-radius`**, ranked first, and it survives an adversarial check of the
  gap it claims. This item said it "overlaps `ops/merge_gate.py`". Read at the
  source: the gate is a **done-claim checker** by its own docstring - it asks
  whether claimed files exist, re-runs the suite, and refuses a dropped test
  count. It says nothing about what a change BREAKS elsewhere. The gap is real,
  and it operationalises a `CLAUDE.md` rule that is stated and never mechanised:
  "Proving your change happened is not the same as proving it matters."
- **`diagnose`**, ranked second, and **this item's criterion 3 premise about it
  is FALSE.** It says diagnose "is already a local skill in this tree". There
  are **zero** `SKILL.md` files anywhere under the repository root and no
  tracked diagnose command. The only copy is a USER-LEVEL command outside this
  repository, absent from a fresh clone, which makes it a continuity gap of
  exactly the kind this project's design exists to prevent. Its absolute path is
  deliberately NOT written here: a user-profile path carries an account name,
  and `tests/test_no_hardcoded_home_path.py` exists for that reason.
- **`writing-for-agents`**, ranked third, filling the half of document design
  that `CLAUDE.md`'s authoring rules do not cover - what to CUT, as against how
  to spell it.

**A caveat on `diagnose` that is NOT dropped**, because a caveat stated out loud
and left out of the artifact is a lie in the artifact. The local user-level
diagnose command contains the phrase "ask the operator" and holds 14 non-ASCII
characters. Those are two non-starters here - FULL AUTHORITY item 2 and the
7-bit ASCII rule. It is the USER-LEVEL copy rather than the upstream skill, so
it does not by itself condemn the candidate. **But diagnose cannot be adopted
as-is**, and any adoption must fix both defects and say that it did.

**Criterion 4's guard was measured, and it does NOT cover what the criterion
assumed.** `tests/test_inventory.py` matches **one directory deep**. Proven
non-vacuously by calling `_group_of` directly rather than by reading it: a
nested `.claude/skills/<name>/SKILL.md` returns `None` while a flat command
returns `'commands'`, against six positive controls. **So a skill adopted at a
nested path would be guarded by NOTHING and would turn nothing red** - the
inventory row the criterion promises would simply never be required. Any
adoption therefore goes in as `.claude/commands/*.md`, which the inventory's
scope does cover.

**Criterion 5 - the decision, with its date.** 2026-09-16: **nothing is adopted
this session.** The three candidates are recorded as candidates with their
adoption shape named, which is a decision about what an adoption would look like
rather than a deferral of one.

**Acceptance for a later adoption, so the next session does not re-derive it.**
The file lands at `.claude/commands/<name>.md`; it carries BOTH attributions -
the root MIT holder and the credited upstream holder for that specific skill,
naming which of the two upstream trees the text came from; it is 7-bit ASCII
with every "ask the operator" construction removed; and it gets its
`docs/INVENTORY.md` row. Deleting that row must be watched turning
`tests/test_inventory.py` RED before the adoption is called done, because the
measurement above shows a nested path would stay green.

The operator named this in chat on 2026-09-15, third after `OPS-92` and
`OPS-93`, asking that it be reviewed for implementation next session:
`https://github.com/timharris707/skills`. Recorded here for the same reason as
the other two.

### What it is, from its own README, read once and not yet verified

Twenty-three agent skills as Markdown `SKILL.md` playbooks, with supporting
Python scripts and YAML adapters, aimed at letting a non-engineer lead
AI-assisted development. Grouped into five buckets - Orient (`router`, `setup`,
`domain-memory`), Decide (`grilling`, `decision-map`, `advisory-board`),
Investigate (`research`, `prototype`, `codebase-review`, `ingest`), Run
(`to-tickets`, `wizard`, `handoff`, `show-me-your-work`, `orchestrate`,
`adversarial-review`, `diagnose`, `implement`, `blast-radius`) and Author
(`writing-for-agents`, `writing-for-humans`, `plainspoken`, `huh`).

Every sentence above is that project's description of itself.

### THE LICENSE, and the specific trap it walks into

MIT, held by Tim Harris, with the README saying free to use, copy, modify and
adapt WITH ATTRIBUTION. MIT into Apache-2.0 is acceptable at this repository's
gate.

**But the repository credits prior authors - it acknowledges adaptation from
Matt Pocock's skills project, also MIT, and says individual skills carry their
own attribution sections.** That is verbatim the third trap in `CLAUDE.md`'s
license gate: "The person who cleared it may not own it. A repo crediting prior
authors has multiple copyright holders and its maintainer cannot unilaterally
relicense it." Here both licenses are MIT so the answer is probably fine, which
is exactly why it must be CHECKED rather than assumed - the cheap case is where
this gate gets skipped. Any adopted file carries BOTH attributions, not just the
one on the repository root.

### The reason this needs a review and not an install

**Most of it already has a local equivalent here, and a duplicate is worse than
a gap.** `orchestrate` and `adversarial-review` are this project's Session
Default in `CLAUDE.md`, which is a written doctrine with a merge gate behind it.
`handoff` is `/done`. `diagnose` is already a local skill in this tree, itself
borrowed from `mattpocock/skills`. `blast-radius` overlaps `ops/merge_gate.py`.
`codebase-review` overlaps the verify lane.

`OPS-48` question 2 settled the shape of this argument once already, declining a
second action-shaped permission scheme because "a second scheme layered on top
would create two answers to one question". The same reasoning applies to a
second orchestration playbook. So the value here is in the few skills that have
NO local equivalent - `grilling`, `decision-map`, `advisory-board`, `to-tickets`,
`plainspoken`, `huh` look like candidates from the names alone - and the review
is what separates those from the duplicates.

**One clear non-starter, named so it is not re-argued.** Nothing adopted may
weaken the Session Default, TDD, the hard boundary, redaction, or the license
gate. A skill that says "skip the failing test first" or "just ask the operator"
is incompatible with written rules here, and the rule wins.

### Acceptance

1. `LICENSE.md` is read directly - identifier and copyright LINE - along with
   the attribution section of any skill considered for adoption, and every
   copyright holder found is recorded here. A README sentence is not a license
   file, and a repository that credits prior authors has more than one holder.
2. Each of the 23 is classified in one line: DUPLICATE of a named local
   artifact, CANDIDATE with the gap it fills, or DECLINED with the reason. All
   23, so an unmentioned skill is not indistinguishable from an overlooked one -
   the same rule `docs/INVENTORY.md` states for its own scope.
3. Nothing is adopted that conflicts with `CLAUDE.md`. Where a candidate is
   close to a local rule but differs, the difference is stated and the local
   rule wins unless the operator rules otherwise.
4. An adopted skill is a FILE IN THIS TREE under `.claude/`, re-implemented or
   copied with both attributions preserved, and it gets an inventory row -
   `docs/INVENTORY.md`'s scope already covers every `.claude/commands/*.md` and
   `.claude/agents/*.md`, and `tests/test_inventory.py` runs in both directions,
   so a new one that is not listed turns the suite red.
5. The decision is recorded either way, with the date and the reason.

## OPS-91. Vendoring RC's `docs/CHANNEL.md` - THE OPERATOR RULED VENDOR 2026-09-20, criteria 1, 2 and 3 are MET and the file is in the tree

### 2026-09-20 - the ruling, and what landed on the strength of it

**This section supersedes every section below it.** They are left standing
rather than rewritten, because this project does not quietly revise a record.
Read them in order: the item was refused, then unblocked by RC naming a license,
then blocked on a ruling, and the ruling is here.

**The operator ruled VENDOR in chat on 2026-09-20**, directing that RC's choices
be taken. THE ONE ASYMMETRY in `CLAUDE.md` reserves an ADOPTION to the operator
and no grant of authority reaches it, which is why this item sat waiting for a
sentence rather than for a measurement. That sentence arrived.

**Criterion 3 is discharged in the shape it specified, and every step was
measured rather than trusted.** A note is MAIL, so none of RC's claims were
taken on their own authority:

- The file was fetched ANONYMOUSLY from the public remote at the commit RC
  published, `6e3c1c752`, which is the route RC's own note invited. That also
  measures the visibility claim: an anonymous HTTP 200 is what PUBLIC means, and
  it is a stronger fact than a sibling saying so. No sibling TREE was read - the
  standalone rule is untouched, because a public remote is not a tree on this
  machine.
- **The digest was checked BEFORE a byte was copied.** The 20633 bytes served
  hash to
  `899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b`, equal to
  the value RC published on 2026-09-15.
- `LICENSE` at the same commit was fetched too: Apache License 2.0, 219 lines,
  with a `SCOPE OF THIS LICENSE` block putting authored documentation - "the
  Markdown that describes them" in its own words - inside the grant, and a
  carve-out only for third-party data under `data/`. `docs/CHANNEL.md` is
  authored documentation outside `data/`.
- **The copyright LINE was read, not just the license name**, because a
  `LICENSE` can name nobody. Two copyright lines, both RENDERED - a year and a
  non-empty holder, no unfilled template. The holder's name is NOT recorded in
  this repository as a literal: it is the operator's git identity.
- **The 2026-09-07 three-way contradiction was measured on the half that
  mattered rather than accepted as resolved.** `Share/LICENSE.md`, the file that
  forbade redistribution, returns HTTP 404 at that commit. That is this
  project's own evidence, taken at the exact commit whose bytes are now here.
- The copy was made with `shutil.copyfile` - byte level, never `write_text`,
  which on Windows turns LF into CRLF while `read_text` hides it.

**What is in the tree**, and it is byte-identical with zero changes to the work:

| Path | What |
|---|---|
| `third_party/rc_channel/docs/CHANNEL.md` | the vendored file, 20633 bytes, upstream relative path preserved |
| `third_party/rc_channel/NOTICE.md` | the Apache-2.0 section 4(b) attribution and statement of changes |
| `tests/test_vendored_channel_md.py` | the guard that fails if any byte moves |

**One digest here, where `lw_write_tracer` has two, and that was measured.**
That file arrived CRLF and `.gitattributes` pins the checkout to LF, so its
working-file hash and its git blob hash are different facts. This one was
fetched LF: zero CRLF pairs, zero bare CR, zero non-ASCII bytes, and `*.md` is
stored LF, so disk, blob and what RC published are the same 20633 bytes.

**The guard was proved non-vacuous before it was believed.** Four mutations,
four reds, four restores to green, all observed this session: a one-character
edit to a heading (1 failed), a whole-file CRLF rewrite (2 failed - the
line-ending assertion fires separately so a text-mode copy reports as what it
is rather than as an unexplained digest mismatch), the NOTICE naming a digest
the guard does not pin (1 failed), and the NOTICE losing its statement of
changes (1 failed). The first run, before the file existed, was 4 failed.

**`ops/lanes.py` gained a row** for the new test module, for the same reason
`tests/test_vendored_write_tracer.py` has one: `third_party/**` already owns the
vendored tree, but a test module under `tests/` matches no other glob and would
be an unowned file that nothing arbitrates.

**What the refusal cost, now recovered.** The section below states plainly that
holding no copy meant this project could not pin the digest all five trees
agree on, and chose that over a private near-copy that would look like agreement
without being it. That cost is now paid off rather than argued away: the digest
is pinned, and it is the same one RC published.

**Criterion 4 is the remainder** - the seven portable assertions as OUR OWN test
module. RC's gate module is NOT vendored under any answer, because RC states it
hard-imports RC-only tooling that no sibling has.



### 2026-09-16 LATER - RC ANSWERED, and criteria 1 and 2 are MET

**This section supersedes the one below it, which was written earlier the same
day and was correct when written.** The earlier section is left standing rather
than rewritten, because this project does not quietly revise a record. Read them
in order: RC had not answered at the time of the first, and answered afterwards.

RC's note is
`moon_sync_inbox/2026-09-16-0024-from-RC-FYI-amberstone-is-apache-2-0-and-channel-md-is-covered-license-named-for-your-gate.md`,
8272 bytes measured on this disk. What it supplies, which is exactly what
criterion 1 asked for and no more:

- **The repository, by name: `Remus3/Amberstone`**, which RC states its own
  `origin` remote resolves to. Criterion 1 required a named repository and a
  statement that does not name one was explicitly declared insufficient.
- **Visibility PUBLIC**, which RC says it probed live against the host rather
  than asserting from a document.
- **Root `LICENSE`: Apache License 2.0**, 219 lines.
- **The copyright LINE and not merely the license name**, which is what this
  repository's gate demands because a `LICENSE` can name nobody. RC reports it
  as a rendered grant with a named grantor rather than an unfilled template.
  **The holder's name is NOT recorded here, and that is deliberate.** It is the
  operator's git identity, which `CLAUDE.md` names as an operator identifier and
  forbids writing into a tracked file as a literal - the rule that already bit
  this project once in `LL-0170`, when a session quoted `git log` output into
  four sibling inboxes. A reader who needs the literal reads RC's note, which is
  in a gitignored directory. Recording "one holder, sole, named in both `LICENSE`
  and `NOTICE`" carries the whole legal fact and none of the exposure.

  **One NUANCE measured while enforcing that, because a future session will
  otherwise "fix" a file and break the licence.** A blunt check - "the
  operator's git identity must appear in NO tracked file" - is FALSE here, and
  it fired on `README.md:270` while this section was being written. The literal
  appears deliberately in `LICENSE`, `NOTICE` (twice), `CITATION.cff` and that
  README line, which is precisely where Apache-2.0 requires the copyright holder
  to be NAMED. Removing it would not be redaction, it would be stripping the
  attribution this repository's own licence depends on. The rule in `CLAUDE.md`
  is about INCIDENTAL leakage - quoting `git` output into a note, hardcoding the
  value inside a guard that exists to protect it, letting it cross off the
  machine through an unredacted channel - and not about the copyright notice of
  a public repository, where publication is the point. So the test to write, if
  one is ever written, is scoped by LOCATION and DIRECTION rather than by the
  value: the four attribution files are the allowed set, and anywhere else is a
  finding. That distinction is the same one `CLAUDE.md` already makes when it
  warns that a rule enforced by hardcoding the value it protects is scoped to
  one VALUE, which is the defect one level down.
- **Scope, stated inside `LICENSE` itself**: a `SCOPE OF THIS LICENSE` block
  putting the repository's source code AND its authored documentation inside the
  grant, with the README's licence paragraph saying the same.
- **The only carve-out is third-party-sourced DATA under `data/`**, listed
  source by source in `NOTICE` under a heading saying that material is NOT
  covered. Documentation appears nowhere in that carve-out, and `docs/CHANNEL.md`
  is authored documentation outside `data/`.
- **Vendoring is intended**, which RC states plainly, and RC asks for nothing
  beyond the attribution Apache-2.0 already requires.

**The 2026-09-07 three-way contradiction is reported RESOLVED**, and RC gave the
evidence rather than the conclusion: `Share/LICENSE.md` is absent from disk AND
returns zero rows from `git ls-files`, so it is gone rather than merely
untracked; the all-rights-reserved phrasing is absent from `README.md` and from
`docs/CHANNEL.md`. RC also volunteered the incomplete half rather than claiming
a clean tree - the phrase still occurs in append-only history records and in
RC's own notes ABOUT other people's unlicensed repositories, neither of which is
a competing grant over RC's files. That is the honest shape of the answer and it
is worth more than a bare assertion of cleanliness would have been.

**CRITERION 1: MET. CRITERION 2: MET.** Apache-2.0 into Apache-2.0 is exactly
what the gate accepts. The refusal recorded below was never a judgement about
RC and is now discharged on its own stated terms: this project refused an
unlicensed drop, asked the owner to name a license and a repository, and the
owner did. That is the second time this sequence has run to completion here -
the first produced `third_party/lw_write_tracer/` under `OPS-84`.

**WHAT THIS DOES NOT DO, and it is the whole of what remains.** It does not
authorise vendoring. `CLAUDE.md`'s SECOND EXCEPTION permits a vendor when a
license is named and accepted, and criterion 3 below says in its own words "on a
yes AND AN OPERATOR RULING to vendor". THE ONE ASYMMETRY governs: declining was
always a session decision, and ADOPTING is an operator ruling that no grant of
authority reaches and that a session may not manufacture. RC says the same from
its side and explicitly is not asking. So the item moves from BLOCKED-ON-RC to
**BLOCKED ON AN OPERATOR RULING**, which is a real unblock of the question and
not of the act. A ruling of NO VENDOR with the license in hand is a legitimate
outcome and RC has already said it would record it as one.

**If the operator rules VENDOR**, criterion 3 already fixes the shape and
nothing in it is relaxed by the license being clean: hash the file against the
digest RC published BEFORE a byte is copied, copy at the BYTE level and never
through `write_text` - `.gitattributes` and Windows CRLF translation make a
working-file hash a different fact from a git blob hash, measured here on
2026-09-01e - place it at the same relative path under `third_party/`, and give
it a NOTICE naming upstream, license, holder, the digest of what was licensed
and every change made, per Apache-2.0 section 4(b). Criterion 4 also still
stands: the seven portable assertions become OUR OWN test module, and RC's gate
module is NOT vendored under any answer, because RC states it hard-imports
RC-only tooling.

### 2026-09-16 EARLIER - RC had NOT answered, a second silence was recorded, and the conformance gap is DONE

**RC has not answered.** The newest item on this channel is still RC's
2026-09-15 1858 FYI, which PREDATES this project's reply delivered
2026-09-15T23:46:47 local. That was verified on a WHITESPACE-COLLAPSED copy of
the note, 15063 bytes, because a line-oriented grep is a claim about the file's
line breaks and this repository has already returned two false clean bills that
way in a single session: **ZERO occurrences of "licen", "copyright", "apache" or
"repositor".**

**A false-positive class worth recording, because it would read as a hit.** The
eight apparent "MIT" matches in that note are all substrings of **"commit"** and
**"committed"**. A case-insensitive search for a three-letter license identifier
inside English prose is a trap rather than a search, and the same trap is
waiting in any future note that discusses commits.

**Criterion 1 remains UNMET. The item stays BLOCKED and the refusal stands.** RC
names a commit sha and the phrase "public tree"; a visibility is not a grant,
and nothing in the note names a license, a copyright holder or a repository.
Under the rule RC itself named as operative - v2 section 2, silence reads as
DISSENT rather than as consent - **a SECOND silence is recorded here AS a
silence**, which is what criterion 5 asks for. Nothing about the refusal changes
and no criterion is quietly satisfied by the passage of time.

### The conformance gap in the section below is CLOSED - 2026-09-16

`ops/inbox_watch.py` now implements the clause. It gains `NAME_LIST_CAP = 10`,
`REPORT_FILENAME`, `default_report_path()`, `write_report()`, a shared
`_write_atomic` using temp-then-replace, `render(result, cap, report_path)`
which caps ALL FOUR name lists, and `report_and_render()` which writes the file
FIRST and then returns the capped text. On a write failure it prints everything
plus a WARNING rather than leaving a dangling pointer to a file that does not
exist - a pointer to a missing report is worse than no cap at all.

`Group.mtime` and `Drop.mtime` are now `stat`ed in `scan` and in `_read_drops`,
so "newest" is MEASURED rather than inferred from an ordering that nothing
guarantees. A `--report-file` flag was added with `allow_abbrev=False`, and the
report path derives from `--state`, so a fixture cannot reach live runtime
state - `tests/test_inbox_live_state.py` exists because a fixture writing
`ops/runtime/` marks the operator's real backlog as read.

**No `.gitignore` edit was needed, and that was measured rather than assumed:**
`git check-ignore -v ops/runtime/inbox_report.txt` answers
`.gitignore:41:ops/runtime/`, exit 0.

**THE VACUITY CAUGHT MID-TDD, and it is the most instructive thing in this
item.** The first draft named the flag `--report`. **argparse PREFIX-EXPANDED it
to `--reported`**, an existing flag, so two ordering and completeness tests
passed GREEN against ZERO implementation - they were reading the reported-set
JSON and finding it well-formed. The fix is `--report-file` plus
`allow_abbrev=False`, pinned by a test that probes `--trac`, which is the only
probe that discriminates: it must be REFUSED, and under `allow_abbrev=True` it
would silently expand to `--trace`.

**Red was observed first: 14 failed in 0.71s.** Six mutations each drove RED and
restored GREEN - the cap raised from 10 to 1000, the pointer removed, the write
moved after stdout, the atomic write replaced with `write_text`, the cap
spending its budget on the OLDEST names instead of the newest, and
`allow_abbrev=True`. A live smoke run rendered 182 unread capped, with a
360-line full report written.

Opened 2026-09-15, when the operator handed this session the moon-sync stage 4
adoption prompts. The prompt's item 8 for this project reads, in full: "Vendor
`docs/CHANNEL.md` byte-identical and port the seven PORTABLE tests." That is the
one item of the eight this project does NOT do, and this is why.

### The gate, and why no authority in this repository reaches it

`CLAUDE.md`'s SECOND EXCEPTION permits vendoring a sibling's file **when that
sibling NAMES A LICENSE this repository can accept**, and it says in its own
words that the gate "was satisfied, not waived, and that is the whole point."
The FULL AUTHORITY directive lists "the third-party license gate" among the
RULES that no grant of authority touches. So this is not a decision being
deferred to the operator and it is not a session being cautious - declining is a
session decision and always was. It is a rule applying.

### What RC actually stated, measured from the note on this disk

The 2026-09-15 FYI says the doc is "committed in RC's public tree at
`6e3c1c752`", gives its LF-normalised `sha256` as
`899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b`, and invites
a byte-level copy "from RC's checkout on this box, or from the public remote at
that commit."

**It names no license, no copyright holder, and no repository.** "Public" is a
visibility, not a grant. `CLAUDE.md` is explicit that an unlicensed drop is
refused and that a note ASSERTING a license would not be one either; the FYI
does not even assert one.

### The part that makes this more than a missing sentence

RC itself reported, in
`moon_sync_inbox/2026-09-07-0055-from-RC-pre-public-audit-findings-eight-checks-two-of-you-are-public.md`,
a **three-way licence contradiction** in RC's own repository: an Apache-2.0
`LICENSE`, a `Share/LICENSE.md` forbidding redistribution, and a README saying
all rights reserved, personal use only. That is verbatim the first trap listed
under the license gate in `CLAUDE.md` - "a repo can contradict itself". Whether
RC has resolved it in the eight days since is **UNVERIFIED from here and is not
ours to assume**: this project reads no sibling tree, so the only admissible
evidence is a statement from RC.

A copy taken under a contradiction like that would put an unclearable file into
a PUBLIC Apache-2.0 repository, which is the exact harm the gate exists to
prevent.

### What this project does instead, and it is not nothing

The FYI reproduces the six watcher-contract clauses **verbatim in its own text,
saying it does so "so this note is self-contained for anyone who does not vendor
it"**. Reading a drop for the IDEA is always permitted here and needs no gate.
So the conventions are adopted from the prose and the other seven items of the
prompt were implemented this session. Only the FILE is refused.

The cost of refusing is real and is stated rather than glossed: the value of a
byte-identical vendor is that all five trees can pin one digest and prove they
hold the same text. A paraphrase cannot do that. This project therefore holds
NO copy and NO pin, rather than a private near-copy that would look like
agreement without being it.

### Sent, not asked

A note went to RC through `ops.outbox.deliver` asking them to name the license
and the repository if they want the doc vendorable, and saying plainly that the
answer decides between vendoring and reading for the idea. Delivered
2026-09-15T23:46:47 local, 11520 bytes, `sha256`
`6fc3065455c12bfea40ec489f00aff836aaa811f9f27310e78a4eb786672a666`, one
recipient, none failed; the local copy and the manifest row are under
`moon_sync_inbox/_outbox/`.

**That sentence was a LIE for about twenty minutes and it is worth recording
why.** It was written in the past tense while the note was still a draft in a
scratch directory, and this session's own adversarial pass caught it by listing
the outbox rather than by reading the paragraph - `ls` found no 2026-09-15 entry
and the newest manifest rows were both from 2026-09-14. A committed artifact
asserting a send that had not happened is exactly the failure `OPS-43` exists to
make visible, one level up: there the risk was a session not knowing it HAD
replied, here it was a session claiming it had. The fix was to send the note,
not to soften the sentence. That is the same
sequence that worked with LW: this project refused an unlicensed drop, asked LW
to name a license, LW named `Remus3/Legion-Wallpaper`, PUBLIC, Apache-2.0, sole
copyright holder, vendoring intended - and only then did the operator rule
VENDOR, which is now `third_party/lw_write_tracer/` under `OPS-84`. The ask is a
session decision under the 2026-09-12 standing ruling; the ADOPTION that a yes
would enable is still an operator ruling, per THE ONE ASYMMETRY in `CLAUDE.md`.

### Acceptance

1. RC states, in a note in this project's inbox, the repository the file lives
   in by name and the license it is under, and either resolves the three-way
   contradiction it reported on 2026-09-07 or says which statement governs this
   file. A statement that does not name a repository does not close this.
2. The license named is one the gate accepts. Apache-2.0 into Apache-2.0 is
   fine. GPL, AGPL and BUSL-1.1 are DO-NOT-VENDOR whatever is offered, and a
   refusal under this criterion CLOSES this item as REFUSED rather than leaving
   it open.
3. On a yes and an operator ruling to vendor: the file is hashed against the
   digest RC published BEFORE a byte is copied, copied at the BYTE level and
   never through `write_text`, placed at the same relative path, and given a
   NOTICE naming the upstream, the license, the holder, the digest of what was
   licensed and every change made - the shape `OPS-84` already established.
4. The seven portable assertions are then written as our own test module, and
   RC's own gate module is NOT vendored under any answer to criterion 1: RC
   states it hard-imports RC-only tooling that no sibling has.
5. Either way, this item records the ANSWER. A second silence is recorded as a
   silence - and under the rule RC named as operative, v2 section 2, silence
   reads as dissent rather than as consent.

### One conformance gap found while reading the contract, recorded rather than claimed green

Clause 3 of the watcher contract asks for the counts line plus at most N full
names, then a "+k more" pointer naming a gitignored report file written
atomically BEFORE stdout. `ops/inbox_watch.py` implements **no list cap and no
report file** today. RC's per-sibling line for this project did not raise it and
the stage 4 prompt did not ask for it, so it is neither done nor claimed done
here. It matters when a large subdirectory drop arrives, which has happened once
already (`OPS-34`, 49 files). Acceptance: a cap of 10 newest names plus a
pointer to a gitignored report file, the report written atomically before
stdout, and a synthetic test at a name count well above the cap.

## 4b. Ammo-family and talent measurement - READY, cheap, needs the client

Opened 2026-08-09 after the talent and skills screens were captured. The class's
whole kit is gated on ammo families, and the following are **unmeasured**:

- Whether "carrying at least 2 Archer's Arrows" counts equipped **types** or
  available **charges**. At level 2 the operator has both, so the capture cannot
  separate the readings.
- How arrows are acquired at all - loot, craft or vendor. Everything about which
  family a player holds first currently rests on the tree's unlock ordering
  (Archer's Lv. 3, Hunter's Lv. 6) as a proxy.
- How `roll` differs from `dodge`. Both Dodge nodes say they convert one to the
  other and neither says how they differ, and the class's effective range is
  counted in dodge-lengths.
- The three locked Archer's Arrows and all five Hunter's Arrows.

**Acceptance:** each answered by observation and recorded in
`docs/OBSERVED_IDS.md` with its method, or written up as a measured negative
naming what was tried. A guide site does not close any of these.

**PARTLY ADVANCED 2026-08-25b, and one sub-question now has a clean experiment.**
Captured at level 5; full write-up in `docs/OBSERVED_IDS.md`.

- **The types-versus-charges question is still NOT separated, but it is now
  separable.** At level 5 the operator holds **exactly one** Hunter's Arrow -
  unlocked, not equipped, with four still locked. `Battle-fed` requires
  "carrying at least 2 Hunter's Arrows". **So: equip that single Hunter's arrow,
  take Battle-fed, and watch whether it fires.** One arrow type carrying
  multiple charges is precisely the case that tells the two readings apart, and
  it did not exist at level 2 when the operator had 2 types and 3 charges at
  once. **Do not spend the point on this alone** - it costs a talent point to
  answer, so fold it in only when Battle-fed is worth taking anyway.
- **A slot-state reading rule was established** and it matters for every future
  loadout count: gold border = equipped, dashed border = owned but not equipped,
  padlock = locked. Counting the middle state as owned-and-active would
  overstate a loadout, which is exactly how a talent gate gets mis-evaluated.
- **Still unmeasured:** how arrows are acquired, and how `roll` differs from
  `dodge`. The Dodge nodes remain the only source on the latter and still do not
  say.

## 5. Sorcerer single-weapon question - OPEN, needs the client

Four classes surfaced two weapon config ids in character creation, two surfaced
one (`docs/OBSERVED_IDS.md`). Blackarrow's single id independently corroborates
the official statement that its second weapon ships in a future season.
**Sorcerer's single id has no such explanation.** Either Sorcerer is genuinely
single-weapon, or its second weapon simply was not surfaced during that walk.

Until this is settled, nothing in this repo may state that Blackarrow is the
only single-weapon class.

**Acceptance:** either a second Sorcerer `holding-` id observed and recorded, or
a deliberate re-walk of the Sorcerer creation screen that surfaces none, written
up as a measured negative with the walk described. A wiki claim does not close
this.

**THE ARCHIVE ROUTE IS EXHAUSTED - probed 2026-08-30, do not repeat it.** The
whole log corpus was searched for anything that could close this from disk and
it carries nothing: **zero** `class-11` occurrences, **zero** 5-digit
creation-preview `holding-` ids, and **zero** `BP_Preview_C_` creation-preview
actors, measured across the three distinct sessions known then - and RE-DERIVED
2026-08-31 across all FOUR sessions (22 log files, 14 distinct hashes), still
zero, zero and zero. The 2026-08-09 creation
walk that produced the recorded ids is gone, because the game truncates its log
on launch (item 4c). See `docs/OBSERVED_IDS.md`, "The archived logs hold NO
creation walk".

**So this item needs the client and nothing else will do.** It is otherwise
cheap - one pass over the Sorcerer creation screen with the frame poller
running. Worth pairing with item 6, whose acceptance needs the same screen.

## 6. Weapon-stance toggle probe - OPEN, did not produce a result

Step 4 of the original capture plan - hold on one class, cycle the stance
toggle, watch whether the `holding-` id changes - **ran and produced no
distinguishable event.** That is a failed probe, not evidence either way.

The pair-versus-singleton reading currently rests on the class carousel instead,
which is indirect for the stance question specifically. It is consistent with
the published weapon kits (Mercenary hammer plus sword-and-shield, Shadowstrix
dagger plus dual blades) and it refutes the gender-variant hypothesis, but it
does not directly show a stance toggle changing an id.

**Acceptance:** a re-run where the toggle is exercised slowly and repeatedly on
a single class with the frame poller running, yielding either a `holding-` id
change joined to the toggle input, or a documented negative stating what was
tried and over how many attempts. Note item 1 may answer this incidentally - the
toggle may be more legible in a raid than on the creation screen.

## 7. Emberforge is NOT blocked - the save records damage - OPEN, both routes BLOCKED on fresh gameplay

Opened 2026-08-11. This item exists because the "deliberately not on this list"
section at the bottom of this file was **wrong**, and it was wrong in the
direction that cost the most: it said Emberforge cannot be filled until numbers
exist, and named item 1 as the only unblocker.

**Measured this session, first-party, from bytes already on disk.** The
transient save carries `DamageCollectonDataSet`, a JSON array of per-source
damage records. Each entry has `sourceType`, `monsterId`, `monsterGuid`,
`bDeathCauser`, `totalDamage`, and a `damageChildList` of individual hits. Each
hit carries `damageValue` (a float), `timeStamp` (a Unix epoch float with
sub-millisecond resolution), `nameId`, `Key` and `bChildDeathCauser`.

Two consecutive hits on one target in the captured run measured 17.356201171875
and 92.13079833984375, 0.256 seconds apart. Those are the first damage numbers
this project has ever held, and nobody published them - the game wrote them.

**263 generations of that file are already captured** at `C:\ll-captures\saves\`,
so a damage timeline for a whole 20-minute run exists right now without the
operator doing anything.

> **CONSTRAINT ADDED 2026-08-25b, and it changes what this item can promise.**
> A full dungeon run was captured live and wrote **no**
> `StandaloneSlot_<roleId>.sav` at all - the substring `StandaloneLevel` occurs
> **zero** times in its log, against a `requestEnterStandaloneLevel` at the
> start of the runs that did write one. **A dungeon run is therefore not a
> guarantee of damage data.** Any reader must treat the file's absence as a
> normal mode rather than a parse failure, and any plan of the form "play a
> dungeon and collect damage" is underspecified until the mode is named. What
> selects the two behaviours is **unmeasured**. `docs/FINDINGS.md` 12.1.

Two properties of the field are measured and constrain any reader:

- It is a **rolling window, not a cumulative log.** Summed `totalDamage` across
  generations went 74.66, 251.20, 137.52, 89.09, 89.09, 227.94 - it falls as
  well as rises, so entries age out. A reader must accumulate across
  generations and must not treat one snapshot as a run total.
- `nameId` was **0** on every hit observed. If `nameId` binds to the ability
  that dealt the damage, that is damage-per-ability and it is the single most
  valuable binding available to Emberforge. It is **unmeasured** - 0 may mean
  basic attack, or unset. Do not assume.

**EXTRACTED 2026-08-11.** All **263** generations parsed, **424** window
readings deduplicated by `(monsterGuid, timeStamp, damageValue)` down to
**21 distinct hits** over a **1020.344-second** span. Damage ranged 9.745483 to
137.517426 against **8 distinct monsterIds** (1005, 1006, 1014, 1029, 2003,
2007, 2017, 2021) across 9 monster instances.

**RE-DERIVED INDEPENDENTLY 2026-08-12 by the integrator, and it corrected two
filed counts.** Every headline above held on re-measurement - 263 parsed with
zero failures, 21 distinct hits, 1020.344 s, the same 8 monsterIds, 9
instances, total 1284.835785, and all three repeat groups with their gaps. Two
things did not:

1. **The deduped-from count was 278 and is 424.** This document said "**278**
   window readings deduplicated by `(monsterGuid, timeStamp, damageValue)`",
   and then said "`nameId` is 0 on all **424** readings" a few paragraphs
   later - two numbers for one quantity, in one item. Both are real and they
   count **different things**: summed across generations there are **278
   top-level entries** (one per monster instance per generation) and **424
   child hit readings**. The dedup key is a **child-level** key, so the number
   being deduped is 424. The sentence paired the right operation with the
   wrong count. A filed count is a hypothesis - this file's own anti-pattern,
   and the correction matters because an extractor test encoding "278 deduped
   to 21" would freeze a wrong intermediate.
2. **It is 262 generations carrying the field, not 263.** The **first**
   generation - 2,190 bytes, the smallest, written at match start before any
   combat - does not carry `DamageCollectonDataSet` **at all**. The property is
   **absent**, not present-and-empty. That is a fact worth keeping rather than
   smoothing over: the field is created when the first damage lands, so
   "unmeasured" and "measured zero" stay distinguishable on this surface
   exactly as the measurement doctrine requires, and a reader must treat a
   missing property as normal rather than as a parse failure.

**The load-bearing result: damage is DETERMINISTIC, not rolled.** Three values
repeat exactly, and every repeat has a distinct timestamp, so none is a
deduplication artifact:

| value | hits | detail |
|---|---|---|
| `9.745483398` | 5 | one monster instance, gaps 1.712, **1.501, 1.499, 1.499** |
| `83.740417480` | 3 | monsterId 2003, across **two different instances** |
| `30.472595215` | 2 | gap 1.709 |

**Both halves of that were overstated, and an adversarial pass corrected them.**
Kept visible rather than edited away, because the overstatement is instructive:

- **"a float to nine places" is wrong.** Every value is exactly `float32`; the
  ULP at 83.74 is 7.6e-6, so a repeat pins about **7 significant digits**, not
  9. Still far too tight for a per-hit roll, but say the true number.
- **The five repeats of `9.745483398` are ONE computation, not five.** They are
  the 1.5-second tick itself, so counting them as independent evidence
  double-counts. The genuinely independent evidence is a single fact:
  `83.740417480` landing identically on **two different instances of the same
  monster type**.
- **"the first timing constant this project has measured" is too strong.** It
  is n=3 intervals, from one monster instance in one encounter, at a 1 ms
  quantisation floor. It is a strong lead, not a constant.

**Three negatives, each worth as much as the positives:**

- `nameId` is **0 on all 424 readings** in every one of the **262** generations
  that carry the field, and `Key` is empty on all 424. So the save's window
  carries no attribution
  at all, and the ~1.5 s interval cannot be attributed from the save alone.

  **PROBABLY the same id space as `SkillNameId` - a strong hypothesis, NOT
  proven.** The value `6130017` appears as `skillNameId` in the log's
  kill-history payload and as `nameId` inside a `damageChildList` in the same
  log. An earlier draft of this item called that "proven" and "not inferred".
  **Both were over-claims and an adversarial pass refuted them:**

  - **n = 1.** `skillNameId` has exactly **one** distinct value in the entire
    12.7 MB log. One shared value between two fields is a strong lead, not a
    demonstration that the spaces coincide.
  - **`6130007` never appears as a `skillNameId` at all**, so the overlap is
    not reciprocal on the sample available.
  - **"from the same component family" was simply WRONG.** `skillNameId` is
    emitted by `leaderRankScoreComponent`, `battleSnapUpdate` and
    `battleSettlement` - **not** by `DamageCollectionComponent`. That sentence
    asserted a shared provenance that does not exist, which is exactly the kind
    of detail that makes a weak claim read as a strong one.

  `nameId: 0` still most likely means **unset**. Closing this needs a second
  distinct `skillNameId` seen also as a `nameId`.

**Acceptance, added 2026-08-30 - this item had none, which made it permanently
ineligible for the unattended loop.** Every cycle skips items with no acceptance
criterion, so an item marked READY and high value was never once picked up. That
is an ops defect in the roadmap, not in the item.

Close it with **either**:

- a `nameId` other than `0` observed inside a save's `DamageCollectonDataSet`,
  which would settle whether that field is ever populated on that surface; **or**
- a second distinct `skillNameId` value seen also as a `nameId`, which is what
  the paragraph above asks for.

**The second route is BLOCKED ON A FRESH LOG, and the reason is measured.**
`skillNameId` occurs **zero** times across every MistfallHunter log on this
machine - 18 when this line was written, re-derived 2026-08-31 across 22 files,
14 distinct hashes and four sessions, and re-derived again **2026-09-01 across
25 log files, still zero** - the 12.7 MB log that carried `6130017` was
truncated away by the game's launch truncation (item 4c). No probe of the
existing corpus can close it. Recorded so nobody runs that search again.

### ROUTE 1 IS EXHAUSTED - measured 2026-09-01 across the COMPLETE save corpus

**Do not run this search again.** It has now been run to completion over every
save on this machine and the answer is a definitive NO.

- **353 `.sav` files** scanned across `C:/ll-captures` and the live `Saved/`
  tree, **zero parse failures**.
- **The damage field is confined to ONE save type.** Only
  `StandaloneSlot_<roleId>.sav` carries `DamageCollectonDataSet`. The seven
  other save types - `CampData_<id>.sav` (26 files), `Deck.sav` (17),
  `Scav.sav` (14), `UserSettings_v1.sav` (9),
  `EnhancedInputUserSettings.sav` (8), `LoginOptions.sav` (8), `Notice.sav`
  (8), **90 files in total** - do not carry it in a single instance. No other
  save surface is worth searching, which is a result rather than an absence of
  one.
- Of the **263** transient generations: **1 ABSENT, 10 present-and-EMPTY, 252
  carrying records.** That empty ten is finer than this item previously
  recorded and it matters - "the game had not written the field yet" and "the
  game wrote an empty window" stay distinguishable, exactly as the measurement
  doctrine requires.
- **424 child hit readings. `nameId` is `0` on all 424 and `Key` is empty on
  all 424.** No non-zero value exists anywhere.

**Two independent instruments, because a broken search and a true negative are
indistinguishable.** The repo's own reader was one. The other was a regex over
the **raw JSON text** of every payload, which bypasses `DamageHit` entirely and
found 424 occurrences of `"nameId"` carrying the single distinct token `0`.

**The instrument was proved non-vacuous BEFORE the negative was believed.** The
same pass re-derived every headline figure this item already carried, and all
of them matched: 262 generations carrying the field, 21 distinct hits,
1020.344 s span, 9 monster instances, the same 8 monsterIds, total damage
1284.835785, range 9.745483 to 137.517426, and **both** the 278 top-level and
424 child counts that this item once confused for each other. A search that
reproduces eight filed numbers is reading the data.

**Three new constants**, each measured over the whole corpus: `sourceType` is
**1 on all 278** entries, `bDeathCauser` is **False on all 278**, and
`bChildDeathCauser` is **False on all 424**. The second and third independently
confirm item 7a's recorded claim that the save's rolling window **drops the
killing blow** - the save has never captured a death-causing record.

### The two surfaces do not overlap - but the claim is narrower than it first looked

Measured the same day over the log corpus, 25 files:

- The **save** corpus is **100 percent `sourceType: 1`** - by item 7a's reading,
  damage the operator TOOK.
- The log's **JSON** payloads are **100 percent `sourceType: 0`**.

**An earlier draft of this line said "the log corpus is 100 percent
`sourceType: 0`" and that was too broad**, caught by the pre-push refutation. It
holds for the twelve JSON payload occurrences only. The verbose per-hit lines
described below carry **no `sourceType` field at all**, so they are neither, and
a claim about "the log corpus" that was measured on one emission shape does not
cover the other.

What survives is narrower and still useful: **no damage value on the log side
matches any damage value in the save corpus**, and the two sets of events are 17
days apart - the save run is 2026-08-09 17:28 to 17:45 UTC, the verbose log
events are 2026-08-26. So no wall-clock join between the surfaces is available
**for the events currently on disk**. A future capture in which both surfaces
cover the same encounter is what would make the join possible.

**What the log corpus actually holds right now, deduplicated.** `nameId` values
`6150251`, `6152203` and `6152206` with Keys `LightAttack`, `SpearFlurry` and
`ShieldImpact` - which is item 7a's 2026-08-30 table, re-derived. They appear 12
times each, but that is **ONE distinct payload duplicated across 12 archived
copies** of a growing log, so it is **n=1**, not n=12. Counting the raw
occurrences would have inflated a single observation twelvefold - the byte-prefix
trap this repo already recorded for session counts, hit again on a different
quantity.

**7a's three original bindings are absent from the LOGS but `6130017` is NOT
absent from disk**, and an earlier draft of this paragraph got that wrong.
`6130017` (`NormalArrow`), `6130007` (`ExplosionArrow`) and `6250000`
(`MonsterDamage`) occur nowhere in the 25 logs, which is consistent with this
item's record that the 12.7 MB log carrying them was truncated away. But
**`6130017` is re-derivable from the SAVES today**: 139 of the 263 generations
carry the token `SkillNameId` and the int32 `6130017` (bytes `61895d00`)
together, nested under the top-level `LeaderRankScoreData` property. Already
filed at `docs/FINDINGS.md`.

That matters for how route 2 is stated. **"No probe of the existing corpus can
close it" is a LOG-scoped claim wearing corpus-scoped clothes.** The corpus does
contain a `SkillNameId`; what it does not contain is a **SECOND DISTINCT** one -
139 generations carry exactly one value. Route 2 is still blocked, and the
correct reason is the missing second value, not a missing field.

The one thing that genuinely **cannot** be re-checked is the conclusion "the log
populates the same attribution the save blanks, for the same event class": the
only `sourceType: 1` log payload was in the truncated log. That remains a
recorded observation rather than a re-measured one, and is flagged rather than
repeated as though it were fresh.

### A THIRD SPELLING, and a per-hit log surface nobody had enumerated

**This section exists because an earlier draft of the one below it said
"nothing further can be extracted from disk". That was FALSE**, and the
pre-push refutation found the counter-example. Route 1's negative is unaffected;
the framing around it was suppressing a real surface.

`[DamageCollectionComponent]` emits a second, **non-JSON** line whose field is
spelled **`nameid`, all lowercase** - a THIRD spelling, neither the save's
`DamageCollecton` nor the log's `DamageCollection`. A search built on the two
known spellings walks straight past it.

Measured 2026-09-01: **44 raw occurrences across 8 archived logs**, which
deduplicate by their own log timestamp to **10 distinct hit events** carrying
**7 distinct damage values** against **8 distinct `insId` values**. The raw 44
would have inflated 10 events fourfold - the byte-prefix trap again, since the
archived logs are prefixes of one another.

Every event carries `nameid: 0`, `instigator: true`, and
`causer: BP_HermitSprites_C`. **So route 1 fails here too** - this surface adds
no non-zero `nameid`. What it adds is `insId`, which distinguishes individual
monster instances, and seven damage numbers that were not previously enumerated.

**THE DIRECTION OF THIS SURFACE IS CONTESTED AND IS NOT SETTLED HERE.** The
refutation pass that found it read these as the operator's outgoing bow hits.
The surrounding lines do not support that confidently, and they do not support
the opposite confidently either:

- **For outgoing:** 2 of 7 in the largest log sit immediately before a
  `HitIndicator` view-cell bind and a bow `GA_Aimingattack End`, with
  ammunition-index updates just before.
- **For incoming:** 2 of 7 sit beside `GameplayCue.Damage.BeDamaged` and an
  Adventurer `Hit.Light` line, with a monster combo ability active.
- **Decisive field absent:** the verbose line carries **no `sourceType`**, which
  is the field item 7a identifies as the direction flag. Neither reading is
  decidable from this surface alone.

Both readings are adjacency arguments, which is the weak method this repo has
already been bitten by. It is recorded as UNSETTLED rather than resolved in
either direction, and what would settle it is a capture where the same value
appears on a surface that does carry `sourceType`.

**A determinism result that does NOT depend on the direction.** The three-value
sequence `16.99298095703125`, `16.0489501953125`, `75.52435302734375` occurs
**twice**, against different monster instances each time:

| occurrence | timestamps (UTC) | gaps | insIds |
|---|---|---|---|
| first | `04.03.27:692`, `04.03.28:771`, `04.03.29:049` | 1.079 s, 0.278 s | 466, then 469 twice |
| second | `04.06.25:024`, `04.06.26:107`, `04.06.26:391` | 1.083 s, 0.284 s | 536, then 541 twice |

Same three values, same order, same structure - one instance then a second
instance hit twice - and gaps agreeing to about 5 ms. This **independently
corroborates item 7's "damage is DETERMINISTIC, not rolled"** on a different
emission surface and a different encounter from the one that produced it. It is
n=2 sequences and should not be called a constant, the same hedge item 7 already
applies to its own 1.5 s interval.

### What this item now needs

Both acceptance routes require **fresh gameplay**. Route 1 is exhausted; route 2
needs a second distinct `SkillNameId`, and the corpus holds exactly one.

When the client is next open, the cheapest thing that would move this item is a
capture in which **both** surfaces cover the **same** event class - concretely, a
run where the operator DEALS damage while `StandaloneSlot_<roleId>.sav` exists,
so the save's window and the log's `DamageCollectionComponent` payload describe
the same hits. That is what would let the two surfaces be joined at all, and it
is a precondition for either acceptance route rather than a third route.

Note the constraint already recorded above: a dungeon run is **not** a guarantee
that the transient save is written at all, and what selects the two behaviours is
unmeasured.

**What the log CAN already do is bind abilities**, and item 7a now carries six
such bindings rather than three. The save's window remains the surface with no
attribution; the log remains the surface that has it.

## 7a. The log carries what the save's window does not - MEASURED 2026-08-11

The log's `[DamageCollectionComponent]: jsonString:` emits the **same structure**
the save stores in `DamageCollectonDataSet`, but with `Key` **populated** where
all 424 save readings had it empty. That makes the log the attribution surface
and the save the sampling surface.

**Three id-to-name bindings, first-party, read off the game's own emission:**

| id | Key | range |
|---|---|---|
| 6130017 | `NormalArrow` | `613xxxx` - player ability |
| 6130007 | `ExplosionArrow` | `613xxxx` - player ability |
| 6250000 | `MonsterDamage` | `625xxxx` - monster as source |

No Key maps to two ids and no id maps to two Keys across the sample. These are
the first ability bindings the project holds, and they are **distinct from the
`1205xx` ammoId space** already recorded, so ability and ammo are not one space.

**`sourceType` is the direction flag, and it is now read rather than guessed:**

- `sourceType: 0` - `monsterId` is **null** and the Key is a player ability.
  The **player** is the source.
- `sourceType: 1` - `monsterId` is **populated** and the Key is `MonsterDamage`.
  The **monster** is the source.

**CONSEQUENCE, and it inverts the natural reading of item 7's series.** All 21
extracted hits carry `sourceType: 1` with a populated `monsterId`, so they are
**damage the operator TOOK**. This was written as a strong inference from a
single log payload; it has since been **CONFIRMED independently** by the
`PlayerData.Hp` join in item 7 above, which is first-party and does not depend
on the log at all.

**One caveat on generalising the log half.** The only `sourceType: 1` payload
in the log carries `monsterId` **99021**, which appears **once** in the whole
log against 105 mentions of the `1xxx`/`2xxx` space. It looks like a synthetic
death-source bucket rather than a real monster, so its semantics should not be
stretched. The direction conclusion does not rest on it any more - the Hp join
carries it.

**Also measured here:** the log emits **one payload per death event** with
`bDeathCauser: true`, so the log holds the killing blow that the save's rolling
window drops. A reader that wants complete combat needs both surfaces. And a
new monsterId, **99021**, appears only as the source that killed the operator -
a range no other observation has touched.

### THREE MORE ABILITY BINDINGS, and a new id range - 2026-08-30, client `1.0.15`

The live log carries a second death payload, and it binds three ids at once.
Read straight out of the death-statistics line (the label is Chinese and is not
reproduced here; match on `damageChildList`, not on the label):

| nameId | `Key` | `iconPath` leaf | damageValue |
|---|---|---|---|
| 6150251 | `LightAttack` | `T_UI_Icon_Skill_914` | 384.573104858 |
| 6152203 | `SpearFlurry` | `T_UI_Icon_Skill_917` | 384.007812500 |
| 6152206 | `ShieldImpact` | `T_UI_Icon_Skill_919` | 61.545669556 |

`sourceType: 0`, `bDeathCauser: true`, `totalDamage: 830.1265869140625`, and
`monsterId` **absent** rather than null.

**Internally consistent, which is a check worth running:** the three children sum
to `totalDamage` **bit-exactly** in IEEE754, not merely to the last displayed
digit. A payload that did not sum would mean the child list is a sample rather
than a decomposition, so this is the cheap check that a death payload is
complete.

**THIRD-PARTY PII LIVES IN THIS PAYLOAD, and the redactor was tested against the
real bytes.** The same object carries the KILLER's 19-digit `roleId`, 16-digit
`onlineUserId`, a short `name` and a 15-character `onlineDisplayName`, plus
`appearanceStr` and `gender`. `CLAUDE.md` puts third-party players in scope, not
only the operator. **Checked, and the guard holds:** `lanternlight/redact.py`
masks all four identity fields plus `appearanceStr` on the real line, and
`assert_clean` then certifies the result. Only `onlineChannel`, a single digit,
survives.

Recorded as **checked and clean rather than filed as a gap**, deliberately -
`LL-0090` withdrew a redaction-gap claim that had been raised against a
FABRICATED input. This one was derived from the measured bytes, which is the
only test that means anything here.

**`iconPath` is a field nothing had recorded**, and it is the first surface
joining an ability id to a rendered ASSET name. `615xxxx` is also a **new range**
beside the recorded `613xxxx` (player ability) and `625xxxx` (monster source).

**THE SOURCE IS IDENTIFIED, and a first draft of this section said it could not
be.** That draft reasoned that the Keys `SpearFlurry` and `ShieldImpact` cannot
belong to the operator's bow class, offered "another player killed the operator"
as an inference, and then declared that **"nothing observed separates"** that
reading from a broader `sourceType`. **The payload separates it, and the field
was in the line the section had already decoded:**

| Field | Value | Reading |
|---|---|---|
| `classId` | **15** | `Withered Knight` - bound in `docs/OBSERVED_IDS.md` |
| `damagePlayerType` | 0 | a second source-kind flag, semantics unmeasured |
| `sourceType` | 0 | player is the source, per the rule above |

The operator is `class-12`, Blackarrow. The killer is `class-15`. **So this is a
PvP death, the project's first recorded, and `615xxxx` is a Withered Knight
ability range** - matching a spear-and-shield kit rather than a bow.

**HOW THE ERROR HAPPENED, because the shape recurs.** The decode script pulled a
hand-picked list of fields, printed them, and the output was then treated as the
whole record. The payload actually carries thirteen top-level keys. **A selective
extractor's output is a claim about the extractor**, exactly as an empty grep is
a claim about the pattern - and this one was used to assert an absence. Dump the
KEYS before trusting a decode.

**Still unmeasured:** what `damagePlayerType` distinguishes, and whether
`615xxxx` is Withered-Knight-specific or a shared player-ability range that the
recorded `613xxxx` also sits in.

**This does NOT close item 7's open thread.** That asks for a second distinct
`skillNameId` seen also as a `nameId`. **`skillNameId` occurs ZERO times in every
log on this machine**, re-derived 2026-08-31 across 22 files and four sessions
(18 when this was written) - the 12.7 MB log that carried `6130017` was truncated
away, so the thread cannot be closed from the current corpus at all. Recorded so
nobody re-runs that probe.

**SAFETY, routed to the safety lane:** the log line adjacent to these payloads
carries the operator's persona in a bare `name:` field, and the kill-history
line carries a third party's `playerName` **in CJK**, confirming `SAF-4` on a
second surface. No excerpt of this region may be committed, and the
`DamageCollectionComponent` region is now a named redaction target.
- `bDeathCauser` and `bChildDeathCauser` are **False on all 21**, yet the run
  recorded kills. So `DamageCollectonDataSet` is **not a complete combat log** -
  it drops or rotates out the killing blow.
- `sourceType` is **1** on all 21 and `Key` is empty on all 21. One source type,
  no key. Whatever those fields discriminate was never exercised here.

**DIRECTION - SETTLED 2026-08-11. These are damage the operator TOOK.**

Not an inference and not from the log. The answer was in the captured bytes the
whole time, in a **second field of the same file**: `PlayerData.Hp`, sampled
262 times across the run.

- **13 HP drops, totalling 1286.**
- **21 damage hits, totalling 1284.84.**
- The 1.16 gap is integer rounding across 13 drops, and the drops pair to hits
  **individually**: 108.53 + 83.74 = 192.27 against a 192 drop, 17.36 + 92.13 =
  109.49 against a 110 drop, 137.52 against 138, 89.09 against 89.
- **No HP drop is unaccounted for.**

Found by the adversarial pass and re-measured independently by the integrator.
An earlier draft of this item left direction open and called it the blocking
question; it was answerable from data already on disk, and the reason it stayed
open is that nobody joined the two fields.

**AND THIS IS THE DEFLATING PART, which matters more than the result.** The 21
hits are **incoming** damage. Emberforge needs **outgoing** damage - what the
player's build does - and the save's rolling window does not carry it. So:

- Everything above describes what monsters do to the player. It constrains
  survivability, not build math.
- **Outgoing damage exists, but only in the log**, in the four
  `DamageCollectionComponent` payloads at `sourceType: 0` - `NormalArrow` at
  409.03, 278.26 and 378.79, `ExplosionArrow` at 273.22. Four samples, emitted
  at kill events, WITH ability attribution.
- So item 7's headline holds but shrinks: Emberforge is unblocked by the
  **log**, at four samples, not by the save at twenty-one.

Item 7b is now more important, not less: the training ground is the only route
to outgoing damage in quantity, and `sourceType: 0` is what to look for.

**Remaining acceptance - MET 2026-08-12 for the shipped-code half.** Ledger
`LL-0035`. `lanternlight/damage.py`, owned by **ingest**, with 37 tests.

- **A home in a lane.** Ownership declared in `ops/lanes.py` and the contracts
  regenerated. This was `OPS-2`'s second option - the integrator declares it at
  merge - taken deliberately, because the orphan guard goes red the moment the
  file exists, so the file and its ownership cannot land separately. **`OPS-2`
  is now CLOSED** (`LL-0041`) with a third option that neither of its two
  offered: a lane may **claim** a path in its own `STATE.json`, the orphan
  guard honours exactly one claimant, and the claim goes **stale** - failing
  the suite - once the roster absorbs it. That works for a lane running alone,
  which is what the two filed options did not.
- **Tests.** The JSON shape is characterised against the **committed fixture**,
  which does carry `DamageCollectonDataSet` (one record, one hit), so no
  out-of-repo data is needed to ship or to test. Cross-generation dedup is our
  logic rather than the game's, so it is tested on authored generations.
- **Timestamps joined to wall-clock - and the join found a trap.** See below.
- **Verified end to end** against all 263 captures, the shipped module
  reproducing the scratch analysis exactly: 262 generations with payload, 424
  readings, 21 distinct hits, 1020.344 s, total 1284.835785, the same 8 ids, 9
  instances, direction `monster` only, `nameId` 0 only.

**`timeStamp` IS NOT A UNIX EPOCH. It encodes LOCAL wall clock as though it
were UTC.** This was in nobody's plan and it silently breaks every join between
this surface and the log.

Measured on two independent surfaces:

- The capture files' own **mtimes** put the run at **22:27:00 to 22:46:54 UTC**
  (17:27 to 17:46 local, machine at UTC-5). Reading the hit timestamps as an
  epoch renders them **17:28:10 to 17:45:11 "UTC"** - five hours *before* the
  run began, which is impossible, and numerically equal to the run's **local**
  clock.
- The **log**, which timestamps in real UTC and emits the same payload:
  across 5 readings at **three separate times of day**, log-UTC minus
  timestamp-read-as-epoch is **18009 to 18015 seconds**, i.e. 5.0025 to 5.0041
  hours. Exactly the operator's offset, plus a few seconds of event-to-emission
  lag - and the lag is positive, which is the physically correct direction.

So `as_local_naive()` returns a **naive** datetime, and `to_utc()` **refuses**
without an explicit offset rather than inventing one. The offset is a property
of the machine that played, is absent from the save, and moves with daylight
saving. With the offset supplied, the first and last hits land at 22:28:10 and
22:45:11 UTC - both inside the mtime-measured window, which is the join working.

**Still open on this item:** no damage coefficient may be published until the
same value is seen from an **independent run** - one run cannot separate a
coefficient from a lucky repeat, however precise. Nothing here computes one.

**A sampling limit to design against:** 424 window readings over ~20 minutes of
play yielded only 21 hits, because the window holds roughly two monster entries
at a time and combat rotates them out fast. Most of the run's combat was never
observed. Polling faster will not fix a window that small - this is a ceiling
on what this surface can ever give, and it is an argument for the controlled
environment in item 7b rather than for a faster poller.

## 7b. Training grounds as a controlled measurement rig - ANSWERED 2026-08-25

Opened 2026-08-11 from third-party player testimony (see item 8), and it is the
cheapest unblocker on this list.

The game ships a **training ground** where the host can spawn bots of chosen
class, difficulty and gear quality, freeze them, and restore their own health
and consumables. If that is accurate, it is a repeatable, zero-stake
environment with a controlled input - which is exactly what item 7 needs to
turn a damage number into a coefficient. Every previous plan for measuring
combat math assumed a real run, with its gear loss, its variance and its
single-attempt sampling.

**This claim is UNVERIFIED.** It comes from one creator's video and no
first-party observation here has seen the training ground at all.

**Acceptance:** enter the training ground with the log tailing and a frame
poller running, and record whether (a) it exists, (b) `DamageCollectonDataSet`
is written there at all - it lives in `StandaloneSlot_<roleId>.sav`, which is
created at match start, and a training ground may not be a "match", so this may
be a clean negative - and (c) whether a repeated identical attack yields an
identical `damageValue`. A written negative on any of the three is a result.

**All three answered, 2026-08-25, operator in the client.** Full write-up in
`docs/FINDINGS.md` section 11; ids in `docs/OBSERVED_IDS.md`.

| acceptance | answer |
|---|---|
| (a) does it exist | **YES** - `/Game/Project/Maps/TrainingGround/Training`, `DA_DungeonSettings_Training`, `BP_Adventure_Bot_C` |
| (b) is `DamageCollectonDataSet` written there | **NO** - a clean negative. It is not a match: no `StandaloneSlot_<roleId>.sav`, empty `StandaloneLevel/`, no `EnterBattle`, no `damageValue` anywhere on disk |
| (c) does a repeated identical attack repeat its value | **YES for body, NO for head** |

The rig is real but it is a **pixel** rig, not a file rig. The room renders a
cumulative **Total Damage** meter and writes nothing, so the measurement path
is frame capture joined to the log on wall clock - the same join that bound
class ids - and `lanternlight/damage.py` has nothing to read here.

Two body runs eight minutes apart are **identical hit for hit** and solve to a
**fractional** per-hit value in `[10.3500, 10.3571)`, no integer in the
interval. Two of three head runs are likewise identical to each other and the
third is not, and no single value fits them under either display model.

**What this opens, and it is now the highest-value thread on this list:**

- **The distance term - SUPERSEDED by the ten-point curve below, kept for
  the record.** The first controlled sweep was six points. Ten body
  hits at 10, 8, 6, 4, 2 and 0 paces gave 104, 104, 309, 546, 687 and 691. The
  curve is **clamped at both ends**: 10 and 8 paces are identical - a floor,
  where the per-hit value is exactly **10.35** - and 2 and 0 are within 0.6%, a
  ceiling. The slope between them is steep and the ceiling is 6.64x the floor.
  A pace is defined: a full stride counted off the run-cycle animation loop
  reset, no crouch, sprint or roll.
- **Constancy tracks the flat parts of the curve.** A constant per-hit value
  fits both floor runs and NO run on the slope, and the only same-distance
  readings that disagree across the session are on the slope - 6 paces read 265
  once and 309 once, 16.6% apart. Nothing observed requires the game to roll
  damage; the uncontrolled variable is the operator's own position, which he
  reported himself. A delta wobbling by one is NOT evidence of variance - a
  constant value produces that wobble too, and the floor runs prove it.
- **The floor is CONFIRMED under a recorded label.** After the mapping was
  challenged, the ambiguous pair was re-run under wide-shot capture: ten body
  hits at 10 paces and ten at 8, both reading **104**. See `docs/FINDINGS.md`
  11.10 and 11.11.
- **The FLOOR breakpoint is LOCATED: between 8 and 7 paces.** Ten-hit runs at
  10, 9 and 8 paces all read **104** and all solve to `[10.3500, 10.3571]`; at
  7 paces the total is **231**, a 2.221x step in one pace against 1.338x for
  the next. An abrupt clamp, not a flattening curve. Constancy changes at the
  same step - every floor run admits a constant per-hit value and no run off
  the floor does.
- **The CEILING breakpoint is LOCATED too: reached by 3 paces.** Runs at 3, 2,
  1 and 0 paces read 687, 687, 689 and 691 - a four-distance plateau spanning
  0.6% - while 4 paces reads 546. Unlike the floor, the ceiling is approached
  gently: 4 -> 3 is 1.258x, slightly less than the slope's own ~1.3x per pace.
- **The curve is now ten measured points** at 10, 9, 8, 7, 6, 4, 3, 2, 1 and 0
  paces: 104, 104, 104, 231, 309, 546, 687, 687, 689, 691. Three regimes - a
  clamped floor, about 1.3x per pace for four consecutive paces, a clamped
  ceiling.
- **Why is the floor a STEP and not a tangent?** Extrapolating the slope
  outward from 7 paces predicts about 174 at 8 paces; it reads 104. The game is
  not running out of curve, something is clamping. **Acceptance:** a mechanism,
  or a written negative saying the gap is real and unexplained. Do not publish
  a falloff formula from four interior points either way.
  **Record the distance in the capture, not in anyone's memory** - the
  wide-shot poller exists for this and the first sweep had to be re-run without
  it.
- **Measure apparent size properly, or not at all.** Turning "the target looks
  closer" into a number was attempted twice and saturated twice, because a dark
  character against a dark cave is the wrong segmentation problem.
  **Acceptance:** a fixed high-contrast marker placed in frame at a known
  position, or a written negative saying apparent size is not recoverable from
  this scene.
- **Is the headshot bonus a constant multiplier? - SWEEP RUN, and it is not
  that simple.** Seven ten-hit head runs across the six distances gave 123,
  123, 350, 651, 799, 817, 818. **Not one admits a constant per-hit value** -
  including the two on the floor, at the ranges where body shots are perfectly
  constant at 10.35. The totals reproduce (123 twice, 817 against 818, and 122
  / 123 / 123 from earlier runs) while the individual hits do not, so a
  headshot is not a body shot times a number.
  **Open, and blocking the ratio table:** seven runs were fired at six
  distances and the mapping of the last three is unconfirmed, so no
  per-distance ratio is recorded. The ratio is roughly 1.18 where both were
  measured at the same nominal range.
  **Acceptance for the mechanism:** something that separates a headshot from a
  crit. The client renders headshots in red crit text, so the eye cannot do it
  and neither can this data.
- **What separates a headshot from a crit.** The client renders headshots in
  red crit text (operator), so the two cannot be told apart by eye and were not
  separated by this data. **Acceptance:** a run where the two are forced apart,
  or a written negative saying they cannot be.
- **What `Progress Record` counts.** Measured: it holds the PREVIOUS run's
  total and hit count, not a best. That is established; what resets a run is
  not.
- **`capabilityId 13003`** is emitted beside `DA_DungeonSettings_Training` and
  its meaning is unknown. Recorded, not interpreted.

## 8. Third-party data sources - reviewed 2026-08-11, tier and provenance fixed

Reviewed at the operator's request. Recorded here so the assessment is not
re-done, and so nothing absorbs these as facts by accident.

**`questlog.gg` is DATAMINED, not hand-mapped.** Measured, not inferred: its
monster database is addressed by numeric id at `/db/monster/<id>` in the same
id space this project observed in the save's `Id2cnt` maps, and its listing
carries developer-internal rows no player can ever see - a
`[Debug]OrdinaryMonsterTemplate`, a `Test Dummy Monster` and a `[Discarded]`
entry. A wiki built from play cannot contain a discarded placeholder. Its
category slugs are internal too: the UI says "Greater Elite" while the URL says
`BigElite`.

The consequence is **not** that we use it more, and **not** that we relax
[ADR-002](docs/adr/ADR-002-no-asset-extraction.md). Someone else decrypted the
paks; this project still does not, and nothing about that changes. What it
means is that the site is a **hypothesis and cross-check source**, tier 4, and
that an id learned there is **never** written into
[`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) as an observation. A
**contradiction** between their table and our measurement is a real result and
is worth chasing; an agreement is not corroboration.

**One cross-check already ran and held.** Their `1029` is "Hallowgrove
Woodling". This project independently measured `1029` in the save's
`TeamKillMonsterData` on a run the operator attested was Hallowgrove, whose
internal map is `Whitewoods_Day` with the save's own zone key
`WhiteWoodsOutskirts`. Their player-facing name and our internal name agree
from opposite directions, which is worth something precisely because neither
was derived from the other.

**A second map name is now known and unmeasured here: `Brandrgarde`.** Their
Brandrgarde (South) layer counts 316 treasure chests, 63 extraction points, 327
enemies (2 Boss, 4 Greater Elite, 22 Elite, 68 Mini-Elite, 231 Normal), 13
merchants and 9 quest interactables. **None of that is recorded as fact here.**
It is a set of expectations to test the first time the operator loads that map,
and the useful form of the test is the count, because a count that disagrees is
immediately informative.

**A live example of why the word matters.** That site says "Extraction Point".
The game says **escape**, and `extract` appears zero times in the log - already
recorded under item 1. Anyone grepping the log for a term learned from a map
site gets a clean negative that means nothing.

**`gamerguides.com` is HAND-MAPPED, and it is a DIFFERENT provenance from the
site above.** Its maintainer states it plainly in the announcement thread: a
small team "filling them out as we play", with a "Suggest Markers" function for
readers to add their own findings. So it is **first-party player observation,
crowd-sourced** - a higher trust tier than a datamined dump for anything about
where a thing actually is, and a **lower** one for completeness, because
whatever nobody has walked past yet is simply absent.

Two caveats the maintainer volunteers, and both matter more than the maps:

- **Its database's first iteration was built on the DEMO.** A demo-derived
  table is stale by construction against a shipped build, and this is
  self-declared rather than inferred. Nothing from that database may be treated
  as current without a first-party check.
- **They are "being mindful of randomization"**, which implies spawn or loot
  randomization exists. That is a game-mechanic claim from a credible source
  and it is **UNMEASURED here**. It also means a hand-placed marker for
  randomised content is a probability, not a location - so a marker that fails
  to match observation refutes nothing on its own.

Also from that thread, unmeasured here: **Brandrgarde has North and South
layers**, and **Chaos Mode gets its own map layers**, which implies difficulty
changes map content rather than only scaling it. If true, `roomModeId` or
`matchType` in the map URL is the axis that selects it - see item 1, which
already established that four axes exist and that `matchId` is not the
discriminator.

**The general rule this item exists to fix:** "third-party site" is not a trust
tier. Two sites for the same game, reviewed on the same day, turned out to have
opposite provenances - one datamined from encrypted assets, one walked by hand.
They fail in opposite directions and must be cited differently. Check how a
source was built before quoting it, every time.

## 10. The stack buff - measure it AT THE CEILING - READY, needs the client

**READ [`docs/AFFIXES.md`](docs/AFFIXES.md) BEFORE WORKING THIS ITEM - 2026-08-30
moved the ground under it.** Three things were read off the game's own UI that
this item did not have. (1) `Focus Fire`'s tooltip is now quoted exactly:
"Rapid Arrows increase the Damage Multiplier with each hit on the same enemy" -
so the thing that climbs is a named `Damage Multiplier`. (2) A THIRD candidate
exists that this item never considered: the `Ranged` weapon AFFIX grants a
TEMPORARY damage increase gated on distance greater than 5 metres, which is
neither a talent nor a base mechanic. (3) `Focus Fire` is currently ALLOCATED
while the operator reports the buff no longer appearing at all - so something
here is wrong and the item cannot be worked as written.

**(4) A FOURTH candidate, added 2026-08-30b, and it is the first one carrying
the number 5 from the GAME rather than from a memory of the screen.** The
`SKILLS` screen states that `Rapid Arrows` enters a mode called `Volley`
"allowing you to hold to rapidly fire **up to 5 arrows** for a certain
duration". This item chases an icon that climbs to 5. The icon may simply be the
Volley arrow COUNT and not a stacking buff at all.

**That candidate got WEAKER the same day it was raised, and the reason matters
more than the candidate.** `Sky Piercer` also states 5 - its arrow can "pierce
5 units". **Two unrelated skills in one kit both state 5**, so matching this
item's climbing icon on that number discriminates nothing at all. The candidate
survives only on the Volley MECHANIC, never on its maximum.

**(5) A FIFTH candidate, added 2026-08-30, and it is the first one that is
actually a STACKING BUFF.** The `Fervor` affix ladder, read off
`f0980_00.52.15` and quoted in `docs/AFFIXES.md`, states: after hitting an
enemy, increase `Physical Damage` and `Magic Damage` for 3s, **"stacking up to
5 times"**.

**Why this one is different in kind, not just another 5.** The four candidates
above are an arrow count, a pierce count and a duration-bounded fire mode; none
of them is a buff that stacks. This item describes an ICON THAT CLIMBS TO 5,
which is what a stack counter looks like. `Fervor` is a stack counter with a cap
of 5 and a 3-second window, stated by the game.

**It also makes the number even less discriminating**, which is the honest half:
three separate things in reach of this character now state 5. **The candidate
rests on the stacking MECHANIC and on the 3s window, never on the number.**

**The distinguishing test is cheap and it is the same target-switch run this
item already needs:** `Fervor` is affix-borne, so it should be present only
while an item or gem granting it is equipped, and it decays 3s after the last
hit. `Focus Fire` is talent-borne and per-target. Unequipping the `Fervor`
source and re-running is a clean separation that needs no new measurement rig.

Note also that Volley is bounded by a DURATION while this item reports the icon
climbing per HIT, which is a behavioural difference worth testing - and that
nothing observed ties the on-screen icon to Volley in the first place.

**So the item now needs TWO runs, not one, and they are different tests.**

1. **Target-switch**, which separates `Focus Fire` from the `Ranged` affix.
   `Focus Fire` is scoped to one enemy; the affix is scoped to distance and does
   not care about the target. Ten hits alternating between two enemies.
2. **Fire-and-stop**, which separates a Volley COUNTER from a per-hit STACK.
   Fire `Rapid Arrows`, then stop without dodging, and watch the icon. A
   duration counter decays on its own; a per-hit stack does not.

These are not exclusive candidates - a Volley counter and a per-hit multiplier
could both be on screen at once, which is itself a reason to run both tests
rather than stopping at the first explanation that fits. **Record the weapon's affix set with every run from now on** - no
previous run recorded it, so no previous run can be re-attributed.

Opened 2026-08-26. **The highest-value open question this project has**, because
it may mean an existing headline finding is an artifact.

The operator spotted a buff icon that climbs to **5** while he keeps hitting the
same target inside a time limit, centre screen above the energy bar. It is
readable in the wide shots at `x 600-690, y 600-665` of a 1280x720 frame, and
joining that crop to the meter crop by wall clock gives stack count and
cumulative damage on one row. Nine ten-hit runs at one fixed floor distance came
out monotone non-decreasing in stack count: 1 -> 135, 135; 2 -> 135; 3 -> 136;
4 -> 136; 5 -> 137, 139, 139, 139. See `docs/FINDINGS.md` section 15.

**Why it matters beyond itself.** `FINDINGS` 11.7 reports that a constant
per-hit value fits every FLOOR run and no off-floor run, and reads that as
constancy being a property of the clamp. **A buff of about 1% per stack
reproduces that exact split with no distance term at all** - invisible at 10.35
per hit where it rounds away, visible at 55 to 69 per hit where it does not. The
ten-point curve is untouched; the INFERENCE is contested.

**Measure it at the CEILING, not the floor.** At ~13.5 per hit a 1%-per-stack
effect is ~0.135 and rounds away - which is why the floor runs above give a
4-count spread and no more. At ~90 per hit it is ~0.9 per stack and ~3.6 at
five, several display units clear of rounding.

**Acceptance:**

- Ten hits pinned at ONE stack against ten allowed to reach five, at the near
  end of the curve, without moving between them. Report the solved interval for
  each, not the eyeballed deltas.
- A written statement of whether the buff survives switching targets: ten hits
  alternating between two enemies. "With each hit on the same enemy" implies the
  stack resets per enemy, so if it survives the switch it is not `Focus Fire`.
- Either a per-stack figure with its interval, or a written negative saying the
  effect cannot be separated from run-to-run variation at this precision.

**Do not attribute it to `Focus Fire` without that target-switch test.** The
talent was taken the same session, its tooltip scopes it to `Rapid Arrows`, and
measured inter-hit intervals of 2.27 to 2.87 s prove drawn shots rather than
Volley. Either its scope exceeds its tooltip or the buff is a base mechanic that
was always there. **The logs that could settle it were destroyed before anything
archived them.**

## 11. Bind the remaining affix ids - TWO LEFT (101, 214), both now need the client

Opened 2026-08-30. Ledger `LL-0085` and `LL-0086`.

**Five are already bound** - `201 = Valor`, `208 = Fervid`, `211 = Ranged` by
the wall-clock join, **`209 = Seeker`** and **`212 = Fervor`** added 2026-09-01
by two different methods described below. **Two remain: `101` and `214`**, and
each is now blocked for a MEASURED reason rather than an assumed one.

### `212 = Fervor`, by SLOT ATTRIBUTION on the `Affix Details` panel

**The strongest binding this item has produced, because it is confirmed twice on
two different loadouts.** The `Affix Details` screen prints one row per active
affix with a per-slot count, and for ARMOUR the second cfgId digit gives the slot (see
`docs/OBSERVED_IDS.md`), so a row can be attributed to a specific equipped item.

**There are exactly TWO openings of that screen in the entire corpus and both
have full-scene frame coverage.** The first, `f0119_22.28.15`, was already
transcribed. **The second, `f0124_22.54.52` in `reanchor`, had never been
opened by any session** - found by listing the window-open events rather than by
looking where frames were expected.

| panel | rows and the slots carrying them |
|---|---|
| `f0119_22.28.15` | `Fervid` Lv.2 pants+boots, `Fervor` Lv.2 **helm+chest**, `Seeker` Lv.1 weapon, `Wealth` Lv.1 necklace |
| `f0124_22.54.52` | `Fervid` Lv.2 pants+boots, `Ranged` Lv.2 weapon+gloves, `Fervor` Lv.2 **weapon+chest**, `Wealth` Lv.1 necklace |

**In both, the CHEST slot contributes a `Fervor`, and in both the chest item is
`1230304`, which carries item-borne affix `212` and has NO gem.** Every other
row on both panels is independently accounted for, so nothing else can be
supplying it.

**Every row reconciles, which is what makes this more than a set difference:**
`Fervid` is affix 208 on `1430303` (pants) and `1530303` (boots); `Ranged` is
affix 211 on the weapon `3060404` and on `1360303` at gloves; `Seeker` is affix
`209` on the weapon `3030403`, **confirming that binding a third independent
way**; `Wealth` is the necklace `1630103`, which has no item-borne affix and
carries gem `224110`; and the second `Fervor` source is gem `223106`, rendered
in the gem row of two separate item tooltips.

**A BARE SET DIFFERENCE WOULD HAVE GOT THIS WRONG, and nearly did.** Counting
only affix instances leaves `{212, gem 223106, gem 224110}` mapping onto
`{Fervor, Fervor, Wealth}` with two consistent assignments, and the first draft
of this section picked the wrong one - `212 = Wealth`. **The per-slot counts are
what disambiguate it**, and they are the reason this panel is worth more than
any tooltip.

### `101` and `214` - why each is blocked, measured rather than assumed

- **`101`** sits on item `1430301`, the PANTS slot. It was never equipped during
  either panel opening - `1430303` held that slot both times - so the panel
  route cannot reach it. Its tooltip route fails for a sharper reason than
  "no tooltip was on screen": at its only frame-covered event, `19:54:35`, the
  hover lasted **262 ms** before the next item was hovered, against a capture
  running at about **1 frame per second**. `s01222_19.54.35` shows the warehouse
  with a slot highlighted and no tooltip, exactly as recorded. **The capture
  cadence, not the capture resolution, is what loses it.**
- **`214`** has no `exEquip` record, no durability record and appears on neither
  panel. It is known only from trade-filter requests. **Nothing on disk can
  reach it**, and that is now a measured statement rather than an inference.

### THE DURABILITY JOIN - added 2026-09-01, ledger `LL-0107`

**A frame can be joined to the log by DURABILITY instead of by wall clock**, and
that removes this item's hardest constraint. Item records carry
`"durability":<int>`; the tooltip renders it as a percentage of a per-tier
maximum, and **that maximum is `900 + (third cfgId digit) * 100`** - measured at
every tier 1 to 6 as 1000, 1100, 1200, 1300, 1400 and 1500, with every tier's
largest observed value landing exactly on it.

So an on-screen `97%` on a tier-3 item means a logged durability of 1164 to
1175, which picks one record out of the corpus without needing the frame and the
log line to coincide in time.

**`209 = Seeker` was bound this way, and the argument does not even need the
durability** - that only corroborates it:

- The frame `s01223_19.54.36` (`25/scene`, 1280x720) shows an **Equipped**
  `Oil-soaked Wooden Bow`, `Rare Bow and Arrow`, carrying **`Seeker` Lv.1** at
  **97%** durability, in the item-borne affix position with no gem slot.
- The log's affixed WEAPONS are `3030403` (affix 209), `3030404` (affix 211) and
  `3060404` (affix 211). **`211 = Ranged` is confirmed three independent ways**
  and the frame does not show `Ranged`, so the item is neither of those two.
- `3030403` is the only affixed weapon left, so its affix `209` is `Seeker`.
- **Corroboration:** `3030403` is logged at 1166/1200 = 97.17%, which is what
  renders as `97%`, and it is the ONLY weapon-range record that would.

**The limit, stated:** this assumes the bow on screen is one of the eight
affixed `cfgId`s the log records. A ninth affixed weapon never logged would
break it. The durability record is also 77 minutes older than the frame, so it
holds only if the bow was not used in between - which the `97%` reading is
itself evidence for, and which is why the elimination argument is the primary
one and durability the corroboration.

**The recipe for the two ids this could still reach**, from the same table:
`101` sits on item `1430301` at 98% and 100%, and `212` on `1230304` at 94%,
98% and 100%. **Prefer a distinctive percentage** - 97% picked out one weapon,
whereas 100% is shared by many items and 98% is shared by `1430301` and
`1230304` both. `214` has no durability record at all and is unreachable this
way.

### Why the wall-clock sweep missed this, and it is NOT the sweep being careless

The recorded conclusion was that `101` and `209` "are lost because **no usable
tooltip was on screen** at any instant a full-scene capture was running". **The
narrow half of that survives and the generalisation does not.** The sweep
selected frames at the four tooltip-EVENT timestamps and correctly found no
usable tooltip at any of them. But the tooltip for `3030403` was on screen at
`19:54:36` - **one second after** the 19:54:35 event the sweep checked, and 33
seconds after the 19:54:03 event for that same item.

**A tooltip is rendered when the player hovers, and the `cfgid ==` line fires on
its own schedule.** Selecting frames by the log event's timestamp therefore
looks in the wrong second. That is `LL-0100`'s rule turned on the sweep itself:
the measurement was exact and answered a different question from the one that
mattered.

**They are not blocked on the game. They are blocked on the CAPTURE**, and that
distinction is the whole item. Every one of the four failed for a reason that a
different capture would have prevented:

- `212` has FOUR trade-filter requests, two of them singletons - ideal join
  material - at 22:43:54 to 22:44:11 local on 2026-08-25. That falls between the
  `talents` capture (ends 22:29:52) and `reanchor` (starts 22:53:14). The frames
  were never taken. Checked against the COMPLETE 14-directory capture inventory,
  not a partial one - an earlier version of this item cited a five-window list
  that omitted nine directories.
- `214` occurs once in the whole corpus, inside `[212,211,214]`, in that same
  uncaptured window, and has never been seen on an item.
- `101` and `209` ARE covered by a **1280x720 full-scene** capture at their
  tooltip timestamps, and are still unrecoverable because **no usable tooltip
  was on screen** in any covering frame. This is the ORIGINAL diagnosis and it
  is correct. See `docs/AFFIXES.md` for the per-id table.

  **A "correction" to this line on 2026-08-30 was ITSELF WRONG and is
  withdrawn.** It claimed the two ids are "not covered by any capture at all"
  and cited three wall clocks - `18:37:02`, `18:38:16`, `21:29:30` - none of
  which any capture covers. Those three are real, but they are **`exEquip`
  inventory-snapshot events**, the wrong event family. The events that matter
  are the tooltip opens, `TS.UI: cfgid ==`, and they land at local `19:54:03`
  for item `3030403` (affix `209`) and `19:54:35` for item `1430301` (affix
  `101`) - both **inside** the `25/scene` window of `19:32:34` to `20:12:34`.
  Re-derived by walking every line mentioning either item id across the three
  distinct log sessions and bucketing by event kind.

  **HOW THE WRONG CORRECTION HAPPENED, because it is a NEW failure mode.** The
  two earlier versions of this line asserted coverage without deriving any
  timestamps. The third derived timestamps carefully - **for the wrong event
  type** - and never checked which event family the claim it was overturning
  referred to. A measurement can be exact and still answer a different question
  than the one asked. **Before overturning a recorded claim, establish what it
  was measuring**; re-deriving from a pattern of your own choosing measures your
  pattern, which is the same defect as an empty grep wearing better clothes.

There are EIGHT full-scene capture sets **within `C:/ll-captures`**, three at
2560x1440 - the claim that only one exists was false and is withdrawn. **A
NINTH sits outside that tree**, at `~/.lanternlight/frames` (2026-08-09,
2560x1440, 218 PNGs), invisible to a walk of `C:/ll-captures`; it is the only
set holding talent page-two hovers. No game video exists on the machine.
The binding constraint is not resolution alone: a tooltip has to be open, held
long enough to land in a frame, and identifiable as the right item.

**Two routes exist and they are COMPLEMENTARY** - neither reaches the whole id
space. Filter-only: `201`, `214`. Item-only: `101`, `209`. Both: `208`, `211`,
`212`. The item-tooltip route is validated against a known answer (item
`3060404` -> affix `211` -> `Ranged Lv.1` on frame `f0636`), so it is a proven
method and not a hopeful one.

**Cheapest first:** `212` needs no shopping. The operator still holds item
`1230304` carrying it, so it is one tooltip hover with a full-screen capture
running.

**A THIRD ROUTE was found 2026-08-30c and it is cheaper than either, because it
needs no deliberate action at all.** Equip an item whose affix cfgId the log
carries, with the **`Affixes` panel OPEN** across the equip, and the affix that
appears NAMES that id. It has never fired for a precise reason: of 23
single-slot equip events across three logs, exactly one involves a known-affix
item during a full-screen capture, and the panel is closed on both sides of it.
**The recipe is one sentence - keep the `Affixes` panel open while equipping** -
and it turns ordinary gear changes into id bindings. Recorded as `RES-26`.

**A fourth surface exists and is unexplored: WINE.** The log carries
`wines[{id:1, affixes:[208,211]}]`, so wine carries affixes too, and `Victory
Wine` is brewed from `Malt`. A wine screen showing an affix beside a wine id
would bind ids the same way.

**Acceptance:** for each id bound, a new row in `docs/OBSERVED_IDS.md` naming
the id, the name, and the method, plus the frame filename and the UTC log
timestamp it was joined to. A binding read off an ICON rather than a ROW LABEL
does not count - several glyphs are confusable at capture resolution. Recording
that `101` or `209` has no filter row at all is itself a result worth writing
down, since it is currently unknown whether they are filterable.

**Run a full-screen poller during ordinary menu use.** This item needs no
deliberate experiment; it needs the frames to exist when the operator happens to
open a tooltip or a filter.

### `101`'s blocker is now EXACT, measured 2026-09-01c - NOT a credit

Found while auditing configuration for item 12, and recorded here so the recipe
stops being approximate. **Nothing below binds `101`; this item stays open.**

The `Affix Details` screen opens as
`TS.UI: Verbose: [WindowHandle] open WBP_EquipSkill_DetailPrompt`, view class
`AffixDetailPromptView_C`. Counted over all four maximal logs, `LL-0108`'s
"exactly two openings in the whole corpus" is **re-measured and stands**: two,
both on 2026-08-25b, local `22:28:10` and `22:54:52`, and zero in every other
session including both `1.0.15` logs.

**And `1430301` - the item carrying `101` - is at the PANTS slot for the whole
of the 2026-08-25 session**, measured against `server_EquipArmors` rather than
against a single record: the array
`[1120301, 1230304, 1320301, 1430301, 1520301, 1630102, 1720201]` appears in
**46 payload lines from local 18:37:18 to 20:24:31**, and the only variant,
at `19:54:04`, differs solely by the helm coming off. That session has **zero**
`Affix Details` openings.

**It is worn in session B too, and saying otherwise was this paragraph's second
error.** `1430301` sits at pants on 2026-08-25b from `21:29:32` to `21:35:58`,
and is replaced by `1430303` from `21:36:22` onward. Both `Affix Details`
openings - `22:28:10` and `22:54:52` - fall **52 minutes or more after that
swap**, and the pants slot at each is pinned independently: the payload at
`22:26:39`, 91 seconds before the first opening, and the one at `22:28:56`, 46
seconds after it, both read `1430303`.

So the two facts never overlap: **the item was on the character for about six
minutes in a session whose screen openings came nearly an hour later, and for
two hours in a session that never opened the screen at all.** That is a
measured miss, not an assumed one - and it is tighter than the first draft,
which claimed the item was worn in only one session and rested the other half on
a `roleInfo` record 21 minutes after the opening it was supposed to describe.

**A payload-shape trap, found in that same sweep and worth one line:** the
unequip-all state serialises as `cfgIds-[0,0,0,0,0,0]` - **SIX** elements, where
every other payload in the session carries **seven**. A reader that assumes a
fixed seven-slot array will mis-index or crash on it. It occurs 3 times, at
local 19:51:09 through 19:51:36.

So the two facts are disjoint in time: **the one session where the item was on
the character never opened the screen, and every session that opened the screen
had a different item at pants.** No resolution, cadence or window-width change
could have bridged that, which retires the last hope that `101` is recoverable
from existing frames by looking harder.

**The recipe is therefore checkable BEFORE any frame is read.** Equip `1430301`
at pants, open the `Affix Details` screen while it is worn, and confirm success
by grepping the session log for `WBP_EquipSkill_DetailPrompt` - if the token is
absent the attempt failed and no capture needs opening at all.

## 12. The client was PATCHED - the backward comparison is IMPOSSIBLE, a forward baseline is OPEN

Opened 2026-08-30. The log's own marker `TS.Default: [Startup] Version:` reads
`1.0.14` / Build Date `20260818232428` in both rotated backups and **`1.0.15` /
`20260826170036`** in the 2026-08-30 log. The client changed between
2026-08-26 and 2026-08-30.

By `docs/OBSERVED_IDS.md`'s own standing rule, **every row in it dated
2026-08-25 is now provisional** - including the training-ground damage series
that `docs/FINDINGS.md` section 11 rests on.

Also recorded here so nobody re-derives it: the literal string `buildid` occurs
**zero** times in all three logs, so the Steam buildid `24813185` recorded in
`OBSERVED_IDS.md` is a depot value the log can neither confirm nor refute.
Anchor future passes on `Version` plus `Build Date`, which is first-party and
in-log.

**Acceptance, AS ORIGINALLY WRITTEN and now known to be unachievable - kept
here because the reason it fails is the result:** re-measure the 10.35-per-hit
floor value on `1.0.15` and record whether it moved. If it did not, say so
explicitly - a re-measurement that confirms is worth as much as one that
overturns, and this project has no record of any value being checked across a
patch boundary.

**That last clause was FALSE when it was written.** `LL-0098`, filed the same
day, recorded the safe-circle radius as checked across this very boundary and
found unmoved. Re-measured here rather than cited: `Radius 25597.265625` is
byte-identical in both `1.0.14` maximal logs and in the `1.0.15` maximal log,
and absent from the short `1.0.15` log which never loads a dungeon. The
defensible narrowing is that no measured **combat** quantity had been checked
across a patch boundary.

### WORKED 2026-09-01c - the data existed all along, and the acceptance cannot be met

Ledger `LL-0110`. The item said this needed the client. **It did not need the
client to get an answer, and the answer is that the question as posed can never
be answered.**

**A `1.0.15` training-ground capture has been on disk since 2026-08-30.** That
session entered `LoadMap(/Game/Project/Maps/TrainingGround/Training)` **twice**,
local `00:40:23-00:44:31` and `00:45:16-00:49:10`, and 355 full-screen
2560x1440 frames cover both windows with the `Total Damage` meter legible in
124 of them. **No session had read it - though the previous session's
hand-off had already NAMED that set as the one to check**, so this is a
follow-through on a live pointer rather than a discovery, and calling it
"nobody had looked" would take credit that belongs to whoever wrote the
pointer.

**What crossed the patch boundary intact.** One run of ten hits solves to a
constant per-hit value under the round-to-nearest model - `v` in
`[579/10, 695/12]` = `[57.9000, 57.9167]`, width `1/60`, with truncation empty
and no integer fitting. So **section 11's display model - a real-valued running
sum rounded for display - is reproduced on `1.0.15`.** The standard training bot
is also unchanged: `classId` 10, nine items, zero affixes, zero gems, **7 items
at durability 1400 and 2 at 0**, in every session on both clients - 20 spawns in
the 2026-08-25 session, 16 on 2026-08-25b, 4 on `1.0.15`.

**That "unchanged" is about the STANDARD bot and the 10.35 session had a second
kind.** A single `classId` **12** bot spawned at local 18:38:27 with 8 items -
**6 at durability 1100 and 2 at 0**, the necklace and ring, exactly as on every
other actor. It is the only non-class-10 bot in the corpus, and the room's own
`Weapon Archetype: Blackarrow` setting predicts exactly that. So section 11's
runs had at least two candidate targets on the floor and the log does not say
which was shot. It does not overturn 10.35; it means that measurement's TARGET
is one hypothesis short of pinned.

**Why it is nevertheless NOT a re-measurement of 10.35.** The configuration
differs on nearly every axis, and this is now measured rather than assumed,
from an `OnCustomInfoReady roleInfo` record the log emits within a second of
every training load. Against the session that produced 10.35: character level
**3 against 5**, **nine items equipped against four**, four affix instances
against none, and the held weapon `3030403` carrying affix `209` against a bare
tier-1 `3010401`. **All NINE of the nine equipment slots differ**, in both
1.0.15 windows - re-counted slot by slot at merge time after a first draft of
this line filed "eight of nine", which was the merger's own arithmetic and not
any agent's. A filed count is a hypothesis.

**THE ACCEPTANCE IS UNACHIEVABLE, AND NOT FOR WANT OF THE CLIENT.** 10.35 was
measured at character **level 3**. The character has been level 5 since
2026-08-25 and levelling does not reverse. Section 11's conditions cannot be
reconstructed on this character at all - not today, not with the client open,
not ever. The item asked for a comparison whose baseline was destroyed before
the item was written.

**The exact scope of "unachievable", because the word is doing real work here.**
It is unachievable ON THIS CHARACTER. A *new* character is not excluded in
principle - but it would have to be held at level 3 AND carry all nine of the
2026-08-25 items, `3030403` included, and this document does not claim to know
whether those items can be moved between characters. That is a materially
different and larger task than "re-measure a number", which is why the item is
being re-pointed forward rather than left open against a criterion nobody can
meet. If a future session establishes that item transfer works, this paragraph
is the one to revisit.

**Acceptance, REPLACED.** Since the backward comparison is closed, close the
item forward instead: **record a `1.0.15` combat baseline complete enough that
the NEXT patch boundary is testable.** That means one meter run whose full
configuration is captured at the same wall clock - the `roleInfo` equipped set,
the character level, and the `Training Room Settings` panel photographed open -
plus the run's own `(hit count, total)` pairs. The reason the current boundary
is untestable is precisely that this was never recorded; recording it once
costs one training session and permanently fixes the defect.

**A caution for whoever does it.** Constancy is NOT sufficient evidence that a
run sits on the floor. This session found two segments of one `1.0.15` visit
each admitting a constant, at about 57.9 and about 8.65, and they cannot both
be a minimum. See `docs/FINDINGS.md` section 16 - the likely reconciliation is
that constancy indicates a stationary shooter rather than a clamp, which
narrows the diagnostic `11.7` offers.

**Also delivered, and it is the reusable half:** the `Training Room Settings`
panel has three `Bot Settings` fields - `Weapon Archetype`, `Difficulty` and
`Equipment Rarity` - that configure the TARGET and so parameterise every damage
number the room has ever produced. This repo had recorded the panel's engine
names since 2026-08-25 and never once read its contents.

### DECISION GATE FOR THE OPERATOR - `CLAUDE.md` carries a claim the client refutes

Not answered here, because `CLAUDE.md` is cross-cutting and reserved for the
operator or a merger holding the whole picture - a lane may not edit it.

Its **Measurement doctrine** section says "Nobody has published cooldowns,
damage coefficients or stealth durations for this game. Any site quoting a
second value is fabricating one."

**The first sentence is now false as written.** The game publishes affix
cooldowns exactly, in seconds, in item tooltips - `10s` and `60s`, quoted in
`docs/AFFIXES.md` - along with full affix ladders carrying exact percentages.
`docs/CLASSES.md` had the same blanket in two places and both were narrowed on
2026-08-30 to say **class ability**, which is the form that survives contact
with the client.

The second sentence still stands and is the load-bearing half: a site quoting a
number it did not read off the client is still fabricating one.

**The decision:** whether to narrow `CLAUDE.md`'s wording the same way. The risk
of leaving it is that the doctrine reads as a licence to skip the client, which
is precisely the sourcing error that `LL-0079`, `LL-0081` and `CLASSES.md` C14
all record - the answer was not hard to get, it was being sought in the wrong
place.

## Ordering note

**Items 2b, 2c, 2d, item 7's shipped-code half and item 3 are CLOSED as of
2026-08-12.** `lanternlight/damage.py` reads the damage series and
`lanternlight/tail.py` follows the log, so both the extractor and the live spine
are shipped code rather than scratchpad analysis.

**Item 7b is ANSWERED as of 2026-08-25** (ledger `LL-0049`, `LL-0050` and
`LL-0051`, all corrected by `LL-0052`). The training ground exists, it is **not a match** so it
writes no `DamageCollectonDataSet`, and its damage surface is the on-screen
**Total Damage** meter - a pixel rig, not a file rig. Outgoing damage is
measured: **10.35 per hit** on the damage floor, plus a ten-point falloff curve.
What remains open under 7b is listed in that item: the step-versus-tangent
question, the headshot mechanism, and whether the ~1.3x per pace is real.

**10.35 CARRIES A SCOPE AND IT IS NOT OPTIONAL** - stated here because this
paragraph is where the number gets recited without one. It is a `Blackarrow`
right-click standard-arrow **body** shot, at floor distance, on client `1.0.14`,
**at character level 3 with the nine-item loadout of 2026-08-25 including weapon
`3030403`** - and against a target that is **not fully pinned**, because that
session spawned both the standard `classId` 10 bot and a single `classId` 12
one, and nothing recorded says which was shot. Writing "against the training
bot" here, as a first draft of this very paragraph did, commits the exact defect
the paragraph exists to prevent. That loadout is gone and the level does
not reverse, so 10.35 is now a HISTORICAL reading that cannot be reproduced -
see item 12. It remains correct as measured; it is simply no longer a value any
future session can check.

**The next item depends on whether the client is open.**

- **Client open:** 7b's remaining threads are all cheap and all need it. Fold
  in items 1, 4b, 5, 6, **11** and **13**, which also need the client and none
  of which deserves its own session. **Item 11's cheapest route needs no
  deliberate action at all**, only that the `Affixes` panel be left OPEN while
  equipping anything. **Item 13 is CLOSED** - all 16 page-two node tooltips are
  recorded in `docs/OBSERVED_IDS.md`, each frame-cited, so do not fold it into a
  client session. **Arm the wide-shot poller before the first run** -
  the first sweep of 2026-08-25 had to be re-run because its distances were
  inferred from clock order rather than recorded (`docs/FINDINGS.md` 11.10).
  **Make that poller FULL-SCREEN, not a crop** - though note the reason is NOT
  the one this paragraph used to give. It blamed a 500x310 HUD crop, and that
  cause was refuted: `101` and `209` sat inside a 1280x720 FULL-SCENE capture
  and are lost anyway, because no usable tooltip was on screen at the covering
  frames. Full-screen is necessary and NOT sufficient - the tooltip has to be
  open and held. A full-screen poller still costs disk and nothing else, and it
  turns ordinary menu use into evidence.

**Item 12 is BOTH a caveat and, since 2026-09-01c, a task.** The client moved
from `1.0.14` to `1.0.15` between 2026-08-26 and 2026-08-30, so any measurement
dated 2026-08-25 that a session leans on should be re-checked before being built
on rather than assumed to still hold. What changed is that the backward check is
now known to be **impossible** - 10.35's baseline was level 3 and the character
is level 5 - so item 12's replacement acceptance is a FORWARD one: capture a
`1.0.15` baseline whose configuration is recorded at the same wall clock as its
meter run. That needs the client and belongs in the client-open list.
- **Client closed:** item **7c** (read the meter without a human reading it) is
  now the only specified fallback. Item 4c closed 2026-08-25b, **OPS-8** closed
  2026-08-26b, and **OPS-12** and **OPS-7** both closed 2026-08-27, so none of
  them is the fallback any more. **`OPS-10`, `OPS-11` and `OPS-13` all closed
  2026-08-29b** (ledger `LL-0080`), so none of those three is the fallback
  either. `OPS-6` remains open and is an operator decision, not a task.
  `OPS-14` is likewise an operator question about this machine's disk.
  **`OPS-15` closed 2026-08-30** (ledger `LL-0082`), and item **7c's**
  fresh-clone gap closed the same day (`LL-0083`), leaving only 7c's WHITE
  row - which is blocked on a capture, not on a session. **So there is no
  fully specified client-closed task left.** **That ceased to be true on
  2026-08-31:** item **`4d`** - arm the session watcher automatically - is fully
  specified, is pure code and tests, and needs no client at all. It was split out
  of `4c` precisely because `4c` is in the loop's `completed` list and work
  parked there is invisible. ~~**`4d` is the client-closed task to pick up.**~~
  **`4d` CLOSED 2026-09-01** (ledger `LL-0109`), so it is not the fallback any
  more either. ~~**The client-closed task is now item `7c`'s reader**, with two jobs: teach
  it the thousands separator, and record that it fits a full-screen frame at
  crop origin `(2058, 390)`.~~ **BOTH DONE 2026-09-01d** (ledger `LL-0112`,
  corrected by `LL-0113`). `MIN_GLYPH_WIDTH` was not lowered; the reader now
  returns **118 of 124** panel-up frames with **ZERO disagreements**, up from
  61, and the crop origin is recorded in the module's own docstring.

  **So there is again no fully specified client-closed task.** What remains on
  `7c` is the WHITE row, still blocked on a capture rather than on a session,
  plus three items recorded in `7c` with acceptance criteria that are
  defence-in-depth rather than capability: a registration search for two
  misregistered frames, a re-check of split pieces against the width gate, and
  tightening `_is_separator` to the comma population it documents. **A
  four-digit committed fixture is BLOCKED on an operator decision**, not on
  work - capture-derived pixels enter this public repo only on explicit
  approval (`LL-0083` precedent). The other client-closed work is
  now reading more first-party data off the game's own menus into
  [`docs/AFFIXES.md`](docs/AFFIXES.md), which needs the operator in a menu
  but not in combat - and item 10 still supersedes everything the moment the
  client is open.

**Item 9 is CLOSED as of 2026-08-12** (ledger `LL-0046`). The `cdkey` hole is
shut, the `/Game/` anchor is genuinely pinned, and two of that item's four
surfaces turned out to have been closed already.

**Item 4's remaining acceptance is met by shipped code**, measured 2026-08-25:
`lanternlight/savewatch.py` pointed at `Saved/` snapshots `AvgPrice_<id>.ini` on
change with a timestamp and never writes to it, which is exactly what that item
asked for. Item **4c** is the part that is genuinely left - arming it without a
session having to remember. There is no longer an open safety item; the safety
lane's queue in `lanes/safety.STATE.json` is all blocked on a candidate fixture
existing.

Item 3 is closed, so it is no longer the fallback. The tailer exists; what does
not exist yet is anything consuming it, and nothing on this list currently asks
for that - do not invent a consumer without an acceptance criterion.

Item 7 itself stays **open**, but its blocker has been cleared once: no
coefficient may be published until the same value is seen in an **independent
run**, and **10.35 has now cleared that bar** - three runs at the damage floor,
whose only disagreement is a rounding tie that 10.35 itself predicts. It is a
floor value with its conditions attached, not a coefficient, and nothing has
entered Emberforge.

One ownership correction, measured this session: `tests/fixtures/**` is owned by
**ingest**, not safety. This document called 2b "safety-lane work" and the
roster in `ops/lanes.py` disagreed. What actually worked was a split - ingest
built the artifact, safety owned the detectors and held the veto. Read the
roster, not this file, for who owns a path.

Item 4 is closed. `4c`'s entry point is closed; arming it AUTOMATICALLY was
item `4d`, which CLOSED 2026-09-01 (`LL-0104`) - this line called it OPEN long
after it shut and was corrected at the cycle 47 wrap. Item 3 is closed.

Each lane now carries its own queue in `lanes/<lane_id>.STATE.json`, so the
right way to pick work is to read the state file of the lane that owns the
files, not to re-read this whole document. This list stays the single place an
item's acceptance criterion is defined; the lane files say who holds it and
what is blocked.

Item 1's remainder, and items 5 and 6, all need the client open. None of them
needs a *deliberate* capture session any more - the 2026-08-09 pass showed the
log alone was sufficient - so fold them into whichever session next has the game
running rather than scheduling them.

**HOW LONG HAVE THEY BEEN BLOCKED? ASK, do not guess.** `OPS-59` criterion 6.
The answer is not in this file, because a date typed here goes stale the day
after it is written - this repository's own first anti-pattern. It is in the
watcher, and this is the query:

```
python -c "from ops.loop import watch; print(watch.check_watcher().reason)"
```

That reports when a file was last actually COPIED, as distinct from when a
surface was last polled, and it distinguishes RECENT, QUIET and UNKNOWN. As
measured on 2026-09-08 the game's own tree had not changed since **2026-08-30**,
nine days, so all three of these items had been blocked that whole time and
nothing in this repository said so.

Read the number as an UPPER BOUND on "when game data last arrived", not as the
instant it did. Two reasons, both measured: the heartbeat lives under
`ops/runtime/`, which is gitignored, so a fresh clone starts with no history at
all; and re-arming the watcher re-copies unchanged files, because the copier's
seen-set is per instance. A QUIET answer is trustworthy - nothing arrived. A
RECENT one means a copy happened, which is not quite the same as new data. **Item 4b and items 5 and 6 are held as
open items on the `research` and `capture` lanes**, each naming what it is
blocked on, so they are no longer only a paragraph in a document nobody reads
mid-session.

## Deliberately not on this list

- Anything touching the game process. Permanently out of scope
  ([ADR-001](docs/adr/ADR-001-no-game-process-interaction.md)).
- Anything requiring decrypted paks
  ([ADR-002](docs/adr/ADR-002-no-asset-extraction.md)).
- ~~Emberforge formula work.~~ **REFUTED 2026-08-11 - see item 7.** This line
  said the engine could not be filled before measured numbers existed, and named
  item 1 as the unblocker. It is still true that **no cooldown values, damage
  coefficients or stealth durations are published anywhere**
  (`docs/CLASS_RESEARCH.md`). It is **false** that no numbers exist: the
  transient save writes per-hit `damageValue` with sub-millisecond timestamps,
  and 263 generations of it were captured on 2026-08-09. The blocker was never
  the game - it was that nobody had read the field. Left here struck through
  rather than deleted, because "we checked and there is nothing" was wrong for
  two days and the shape of that error is the useful part.

### Outcome - CLOSED 2026-09-08

**Criterion 1 and 2 together, because the decision joins them.** `main()` now
builds an `argparse` parser with `allow_abbrev=False`, so an unknown flag or a
stray positional exits 2 with a message naming the token, and `--arch` is refused
rather than silently accepted as `--archive`. The options are REAL, which is what
criterion 2 demanded: `--repo-root`, `--roadmap` and `--archive` map onto
`check_repo`'s existing parameters and change what is read.

Proved against a scratch pair rather than by inspection: a broken pair exited 1
naming the SCRATCH heading; adding the stub produced
`OK (2 archived heading(s), 2 stub link(s))`; pointing `--roadmap` at a different
file produced a dangling finding; and `--archive docs/NOPE.md` produced DID NOT
RUN, which is the distinct third answer this guard already knew how to give. The
live default is unchanged at `OK (65 archived heading(s), 65 stub link(s))`,
exit 0.

**The filed defect, stated positively.** Every run now prints its own scope line -
`scope ROADMAP.md vs docs/ROADMAP_ARCHIVE.md under C:\Lanternlight` - so a
verdict says what it was a verdict ABOUT. `check_texts` also takes the roadmap's
relative path for its MESSAGES, so a finding names the document actually read
instead of the default constant. A true verdict answering a different question is
this repository's recurring shape; a scope line is the cheapest possible defence
against it.

**Criterion 3, non-vacuity, three mutations, each anchor asserted before the
substitution because a mutation that fails to apply looks exactly like a passing
test.** Turning `parse_args` into `parse_known_args` - the rejection removed -
gave `5 failed, 31 passed`. Making the options accepted and ignored, by calling
`check_repo()` with no arguments, gave `5 failed, 31 passed` too, which is the
point of criterion 2: the same tests catch both halves. Reverting the finding text
to the default constant gave `1 failed, 35 passed`. Restored to `36 passed` after
each.

`tests/test_archive_link_guard.py` went 23 collected to 36. One existing test was
ADAPTED and not weakened: `main()` now reads `sys.argv[1:]` when its argument is
`None`, so the test that called `main()` bare under pytest was passing the test
runner's own argv; it calls `main([])` and a new test covers the `None` contract
with `sys.argv` monkeypatched.

**Criterion 4, the sweep, reported as a COUNT because an empty sweep is a claim
about the sweep.** Nine of nine `tools/` entry points - every module with a
`__main__` block - each invoked with an unknown flag, exit codes read WITHOUT a
pipe after a piped read returned the pager's status instead:

    refuse (exit 2)   doc_archive.py, frame_poller.py, hook_command_guard.py
    fixed here        archive_link_guard.py, 0 and a green line -> 2
    ignore argv       ascii_check.py, syntax_check_hook.py, probe_paks.py,
      and exit 0      doc_size_budget.py, precommit_gate.py

The merger re-probed the four remaining ignorers independently and all four exit
0 on an unknown flag.

**THE SWEEP FOUND A FAIL-OPEN IN A SAFETY GATE, which is filed and closed as
`OPS-66` rather than folded in here.** `tools/precommit_gate.py` recognised only
`lint-staged` as `argv[1]`; anything else fell through to the PreToolUse stdin
path, found no JSON, and returned 0 - which git reads as a pass. Since
`.githooks/pre-commit` invokes it by that exact string, a one-character typo in
that line turned the lint gate off and reported success. Measured both ways before
the fix: `--lintstaged` exited 0 silently and the real `lint-staged` also exits 0
on a clean repository, so the two were indistinguishable by the only thing a git
hook reads.

**The remaining four are `OPS-67`,** filed rather than swept in, because two of
them are stdin hooks whose wiring passes no argv at all and two are
manually-invoked tools whose numbers get quoted - a real difference in stakes
that deserves a decision rather than one uniform change.

## OPS-68. The operator directed a RESPONDER RUNNER - BUILT 2026-09-20 in the DRAFT-ONLY shape, refuted on its load-bearing property, repaired, and criteria 1 to 3 are MET

### 2026-09-20 - BUILT, then REFUTED on the one property that mattered, then repaired

**This section supersedes the ones below it**, which are left standing because
this project does not quietly revise a record.

**Criterion 2 said nothing is built before the scope is decided.** The scope was
adjudicated on 2026-09-14 and is written out below; the build follows it and
widens it nowhere.

**The shape chosen is DRAFT-ONLY - option 4 of the four recorded - and the
reason is MEASURED rather than cautious.** On 2026-09-20 this project published
two wrong numbers to five sibling trees inside four hours and withdrew both: a
six that was five (`LL-0271`) and a seven that was eleven (`LL-0277`, produced
by a regex character class that matched forward slashes only). A runner that
sends would have amplified those faster, not caught them. **Delivery therefore
stays a session act**, and that is a new acceptance criterion rather than a
permanent limit - criterion 6 below.

### What was built

`ops/responder.py` plus `tests/test_responder.py`. Per unread note addressed to
us it extracts the sender code, the classification prefix, the subject, the
note's own timestamp and its `## Reply` target, pulls out every question put to
us, and writes ONE draft per thread into `moon_sync_inbox/_drafts/` following
the vendored channel document's skeleton, with each question left as an explicit
UNANSWERED placeholder. It never overwrites a draft that has been edited - it
compares a recorded digest - and it writes atomically. A `--dry-run` prints what
it would write and writes nothing.

`git check-ignore -v moon_sync_inbox/_drafts/<name>` exits 0 on
`.gitignore:208:moon_sync_inbox/`, and that is RE-ASKED by a test on every run
rather than trusted once.

### THE REFUTATION, and it is the most valuable thing in this item

An independent adversarial pass was handed the done-claim and **REFUTED it on
axis 1, which is the whole point of the draft-only shape.** The runner had three
guards asserting it could not send. All three are STATIC, and the refuter
defeated every one of them at once with two lines inside `run()`:

```
_mod = importlib.import_module("ops." + "out" + "box")
_fn = getattr(_mod, "deli" + "ver")
```

The suite stayed GREEN at 50 of 50 while the runner could reach `deliver`. Each
guard missed it for its own reason and the reasons compose into one lesson: the
AST import check finds no import node because the module name is assembled at
run time; the `sys.modules` probe covers IMPORT TIME and not a lazy import
inside a function; and the `deliver`-call check records a `Call.func` that is a
`Name` or an `Attribute`, and `getattr(...)(...)` is neither.

**A static check is a claim about the SOURCE TEXT and will always lose to a name
built at run time.** That sentence is the item.

### The repair - a claim about the RUN, not about the source

`tests/test_responder.py` gained `TestTheRunnerCannotSendAtRUNTIME`. It runs
`responder.run()` in a `python -B` SUBPROCESS with `sys.addaudithook` installed
BEFORE `ops.responder` is imported, and fails on any audited `import`, `open`,
`compile`, `exec` or `os.rename` naming `outbox`, or any write outside the
fixture drafts directory. The inbox, the drafts directory and the seen set are
all under `tmp_path`, so the real channel and `ops/runtime/` are never touched.

**One thing was MEASURED rather than assumed, and it would have made the guard
vacuous:** the `import` audit event is NOT raised by `importlib.import_module`,
which calls the bootstrap directly. The FILE-level events are what carry this
guard. That is written into the constant's own comment, because a future reader
will otherwise "simplify" it to the obvious event and silently lose the arm.

The static checks are kept as defence in depth, and each docstring now says what
it can and cannot see.

**Verified by the merger independently rather than taken from the repair
report.** The refuter's exact mutation was re-applied, with `importlib` bound so
the mutated runner still WORKS rather than crashing - a crashing mutant proves
nothing, because the guard could be red for the wrong reason. Result: exactly
**2 failed, 55 passed**, and one of the two is the runtime audit guard. The 55
passing arms prove the runner was functional while it was able to send.
Restored byte-identical, digest checked. `ops/responder.py` was staged with
`git add -N`, so its index blob is the EMPTY blob and a `git checkout` restore
would have replaced 47 KB of source with nothing - the probe restores by COPY,
and that is written into it.

### The SECOND refutation: the question extractor is not as good as it looked

Graded against five REAL notes rather than its own fixtures: **precision 75.0
per cent, recall 54.5 per cent** - 6 true positives, 2 false positives, 5 false
negatives. A 34,807-byte note addressed to this project yielded ZERO questions,
because its two question marks sit in `###` HEADINGS that the paragraph scanner
never reads. A bolded imperative was missed purely because the request-verb
rule is anchored at the start of a line and the emphasis marker is not stripped.
**Neither limit appeared in the docstring that claims to list what the extractor
cannot see.**

After repair, on the SAME five notes: **precision 77.8 per cent, recall 63.6 per
cent** - 7 true positives, 2 false positives, 4 false negatives.

**A change that HURT is recorded rather than hidden.** Stripping underscore and
backtick as emphasis added TWO false positives and zero true positives, because
`_read on a truncated write` and a backticked `State : Ready` both begin with a
request verb once the marker is gone. It was narrowed to asterisks only.
Heading scanning is rule-one only and is never sentence-split: rule two on
headings would invent one false positive per note from `## Reply`, and splitting
would fire on a heading of the form `### Is X? NO.` On these five notes heading
scanning gained nothing and cost nothing, so it is proved by unit test rather
than by the sample, and that distinction is stated rather than glossed.

Every remaining limit is in `extract_questions.__doc__` and a test asserts the
docstring names them: the four remaining false negatives are all conditional or
non-anchored openings, the two false positives are narrative imperatives, and a
figure hard-wrapped as `45,` / `189` is quoted as `45, 189` because the raw text
tokenises identically.

### One reported number that was NOT a defect, measured rather than assumed

The dry run reports `addressed elsewhere: 0` across 248 notes, which reads like
a classifier that excludes nothing. Measured over 251 notes: OURS 83, POSSIBLY
OURS 150, **NOT OURS 18**. `run()` short-circuits acknowledged notes before it
classifies, and every one of the currently unread notes is OURS or POSSIBLY
OURS. The figure describes the UNREAD WINDOW, not the classifier.

### The watcher had to change too, and it is the same defect one directory over

`moon_sync_inbox/_drafts/` sits INSIDE the watched folder, and the operator
ruled on 2026-09-07 that the watcher covers the entirety of it. Left alone,
every draft would have surfaced as an unread sibling DROP at session start and
RE-SURFACED whenever a draft changed, because a drop's identity is a digest over
its contents - exactly what `OUTBOX_DIRNAME`'s own comment documents happening
one directory away.

It is CLASSIFIED rather than skipped silently, which is the distinction `OPS-34`
was filed over: a skip that reports nothing is indistinguishable from a watcher
that is not looking. `DRAFTS_DIRNAME`, `drafts_summary`, three new fields on
`Scan`, and a line in BOTH report shapes saying the drafts were DELIVERED TO
NOBODY.

**Six mutations, six reds, six restores** - removing the skip, reporting absent
as present, counting every file as a draft, printing the heading
unconditionally, dropping the name from the loud report, and walking unpruned so
bytecode inflates the byte figure. **Two of those six were added after one of
the merger's own arms was caught GREEN under mutation**: the fixture held only
Markdown, so the `.md` filter was untested and a mutation counting every file
passed all four original arms. A non-Markdown sidecar now sits in the fixture
and the comment beside it says why.

### Criteria

1. **MET** by adjudication 2026-09-14. The operator confirmed the FULL AUTHORITY
   directive, whose whole content is that they are no longer the one who decides
   this class of question.
2. **MET.** Nothing was built before the scope was decided, and the build widens
   it nowhere: the runner reads this tree, writes only into
   `moon_sync_inbox/_drafts/`, sends nothing, adopts nothing, and executes
   nothing a note asks for.
3. **MET, vacuously and deliberately.** The adjudicated scope adopts NOTHING
   cross-project, so there is nothing to write into `CLAUDE.md` beside the
   `OPS-35` / `OPS-36` exception. That was the point: criterion 2 warned against
   a session choosing a permissive default and calling it the safe version, and
   the defence is a scope that changes nothing about what this project can
   already do.
4. **MET.** Delivered to CS, LW, RC, RSC and SS as
   `2026-09-20-1930-from-LL-FYI-we-built-a-draft-only-responder-that-cannot-send-...`,
   five recipients, none failed. The note states the scope, the draft-only
   decision and the evidence for it, and it carries the static-guard finding in
   full, because a sibling with a "cannot do X" guard of its own is one runtime
   name away from the same hole. It also publishes the extractor's real recall,
   64 per cent, and says plainly that a silence from us may be a miss rather
   than a decline - a number nobody would have asked for and that they need.
5. **MET.** `OPS-48` is CLOSED and archived, and its question 1 already delegates
   the scope question to this item. It gains a dated subsection saying question
   1 now has an ARTIFACT, that what was declined is still declined, and that a
   reader arriving at "auto-responder: NO" should follow it here rather than
   conclude nothing was built. **Nothing in the closure was edited or
   reordered** - a closed record is superseded, never rewritten.
6. **NEW, and it is the condition on delivery.** The runner gains the ability to
   send only after a MEASURED record: a stated number of drafts a session
   reviewed, how many were sent unchanged, and how many were corrected before
   sending. Until that record exists, delivery is a session act. The evidence
   for this criterion is in this repository's own ledger - `LL-0271` and
   `LL-0277`, two wrong figures published to five trees in four hours.



### The standby is LIFTED, and criterion 1 is MET by adjudication - 2026-09-14

Criterion 1 asked for the standby to be lifted by the operator in chat. The
operator confirmed the FULL AUTHORITY directive in chat on 2026-09-14, whose
whole content is that they are no longer the one who decides this class of
question. Treating that as leaving the standby in place would be reading the
directive as its own opposite.

**The scope question, adjudicated.** A responder runner here gets exactly the
permission this project already has and not one step more:

- It may READ this tree.
- It may WRITE into the sibling sync inboxes, through `ops.outbox.deliver`, so
  every outgoing note leaves a copy and a manifest row here first (`OPS-43`).
- It may write NOWHERE else outside this tree.
- It has no spawn-in consent in either direction - see `OPS-48` question 3,
  closed 2026-09-14.
- It may not adopt anything. A runner that can accept a charter, a key scheme, a
  lock or a governor on this project's behalf is a session with a schedule, and
  `CLAUDE.md` still reserves adoption to a ruling.

This deliberately grants the runner NO new authority. That is the point:
criterion 2 warned against a session choosing a permissive default and calling
it the safe version, and the defence against that is to pick a scope that
changes nothing about what this project can already do.

**Still OPEN: nothing is built.** The acceptance below stands, with criterion 1
now met by adjudication rather than by a chat ruling.


Filed 2026-09-08 night, from an operator instruction given in chat, and filed
BECAUSE the follow-up was a standby rather than a ruling. A directive that
arrives and is then paused is exactly the thing a cold session loses: the
instruction is remembered, the pause is not, and the next session acts on half
of it.

**What the operator said, in chat, in this order.**

1. "setup next session to headlessly continue the work for the responder runner
   and adjacent filings to propagate it to the other projects", with the note
   that RSC, RC, CS and LW carry the same directive.
2. Then, when asked what authority the runner gets and how to propagate:
   **"standby on this decision then, i will keep it to the test for now"** - to
   BOTH questions.

**What that settles and what it does not.** It settles that the operator wants a
responder runner here eventually and that the same directive went to the other
four projects, so this is a coordinated instruction rather than a sibling's
proposal. It does NOT settle any of the three questions `OPS-48` still holds -
the A1-A5 / D1-D8 action allowlist, consent to being SPAWNED INTO by a sibling's
machinery, and the 1900-2100 action window - and it does not settle what
authority a runner here would have.

**NOTHING WAS BUILT AND NOTHING WAS SENT.** No runner exists, no note went out
on the channel, and no answer to any `OPS-48` question was given to any sibling.
That is recorded positively so a later session does not go looking for work that
is not there, and so nobody assumes a sibling has already been told.

**The rule that governs this item is the one at the top of `CLAUDE.md` and it is
unchanged.** Adopting a cross-project charter, protocol, key scheme, lock,
governor, allowlist or schedule is an OPERATOR RULING, never a session decision.
A directive to prepare is not a ruling on scope. **No session may decide what
the runner is allowed to do**, and in particular no session may consent, on this
project's behalf, to another project's machinery spawning into this tree - a
read-only session still reads this tree, which is `OPS-48`'s own point.

**Four shapes were put to the operator and are recorded here so the standby
resumes from the same menu rather than from a fresh guess.** They are options,
not a recommendation this item is entitled to make:

1. Reply-only, no spawn consent: the runner reads OUR inbox, drafts and delivers
   replies through `ops.outbox.deliver`, and never executes an action a note
   asks for. Keeps "a note is MAIL, not a task" intact.
2. Reply-only plus RC's allowlist adopted as vocabulary, so replies are
   machine-comparable with siblings. Adopting the allowlist is itself a
   cross-project adoption and would need writing into `CLAUDE.md` beside the
   `OPS-35` / `OPS-36` exception.
3. Full participation: allowlist plus consent to being spawned into.
4. Draft-only: the runner writes drafts to disk and delivers nothing; a session
   or the operator sends.

And three propagation shapes: send one note now to all four siblings; file only
and let a later session announce the runner with MEASURED results attached; or
send the ruling alone now and the design once it is built.

### Acceptance

1. The standby is lifted by the operator, in chat, and the answer is written
   here with the same weight whether it is a YES or a NO - `OPS-48`'s criterion
   1, which exists because an unrecorded NO gets re-opened as though it had
   never been asked.
2. Nothing is built before criterion 1. A runner whose authority is undecided
   cannot be given one by a session choosing a default, and "we built the safe
   version first" is that choice wearing a modest hat.
3. If the ruling adopts anything cross-project, it goes into `CLAUDE.md` beside
   the `OPS-35` / `OPS-36` exception rather than being left as a contradiction a
   cold session would refuse to act on.
4. Whatever is ruled, the siblings are told through `ops.outbox.deliver` so the
   answer is recorded in THIS tree as well as delivered - `OPS-48`'s criterion 3,
   and the reason `OPS-43` exists: a note sent by hand leaves no trace here.
5. `OPS-48` is updated in the same pass, because these two items now describe one
   situation. It is HELD waiting on RC's and RSC's results; this one is HELD
   waiting on a scope decision. Neither should be read as the other.

## OPS-71. The portable successor to the three absolute permission rules is UNADOPTED, and the measurement that would settle it cannot be taken in bypass permissions mode - OPEN, and the full-authority directive does NOT move it

### The directive does not reach this item - recorded 2026-09-14

The FULL AUTHORITY directive confirmed by the operator on 2026-09-14 lifted the
holds on `OPS-36`, `OPS-48` and `OPS-68`. It does NOT lift this one, and the
distinction is worth stating so a later session does not sweep it up with the
others.

Those items were blocked on PERMISSION - on the operator being the one who
decided. This item is blocked on a MODE. Settling it needs a session running in
DEFAULT permission mode with its working directory in a clone at a path other
than this checkout, because a did-it-prompt test taken in bypass mode cannot
distinguish a MATCHED rule from a BYPASSED one and returns a false green either
way. Authority does not manufacture a measurement.

Under the directive this is no longer RAISED with the operator as a question. It
is recorded here and left blocked until a session happens to run in that mode.
Everything else about the item is ready.


Filed 2026-09-10 out of `OPS-70`'s own decision. `OPS-70` measured what it could
and DECLINED the rest, which is the correct outcome and is why this is a separate
item rather than an unfinished one.

`.claude/settings.json` keeps three rules anchored at a filesystem root:

    "Read(//C/Lanternlight/**)",
    "Write(//C/Lanternlight/**)",
    "Edit(//C/Lanternlight/**)"

**What `OPS-70` established, with its trust tier attached.** A permission rule's
content is gitignore syntax with four anchors - `//path` from the filesystem
root, `~/path` from the home directory, `/path` from the SETTINGS SOURCE, and a
bare path from the working directory - and no environment variable is
substituted into any of them, so `OPS-61`'s `$CLAUDE_PROJECT_DIR` fix does not
carry across. That rests on TWO NON-OBSERVATIONAL SOURCES that agree with each
other: the published permissions documentation, and the shipped client's own
rule-anchoring code read on this machine. Neither is an observation of a rule
MATCHING on this machine, and this repository's own rule is that two agreeing
sources are a hypothesis rather than a verification.

**Why it was not observed, and this is the whole difficulty.** The session that
measured it ran in BYPASS PERMISSIONS MODE, where every tool call is pre-approved
regardless of the allow list. A did-it-prompt test there cannot distinguish a
MATCHED rule from a BYPASSED one and returns a false green either way. The
measurement is not hard, it is unavailable in the mode the work was done in.

**The candidate change, deliberately not made.** The documented portable form is
a rule anchored at the settings source - `Edit(/**)` in place of
`Edit(//C/Lanternlight/**)` - which would match in a clone and in every git
worktree rather than in this checkout alone. It was NOT adopted because it is a
live change to what this machine pre-approves, made on exactly the class of claim
the session could not observe. Adopting a broader pre-approval on an unverified
inference is the wrong direction to be wrong in.

**The cost of leaving it.** A clone or a worktree prompts for the reads and
writes this file pre-approves here. That is a nuisance, not a wrong answer, which
is why nothing is urgent about this item.

### Acceptance

1. The expansion question is settled by OBSERVATION, not by a third agreeing
   document: a session in DEFAULT permission mode, with its working directory in
   a clone at a path other than this repository's primary checkout, records
   whether a tool call inside that clone is pre-approved or prompts. Presence in
   the file is not the fact; a matched rule is.
2. The same session records the same observation for the settings-source form
   (`Edit(/**)`), because the portable claim is a SEPARATE fact from the
   non-expansion claim and this item must not repeat `OPS-70`'s own lesson by
   inferring one from the other.
3. Whatever is then adopted, the `$comment` in `.claude/settings.json` says which
   sentences are observations and which are inferences, keeping the distinction
   `OPS-70`'s repair pass had to install after stating two of them flat.
4. A DECLINE remains acceptable if the observation says the current rules are
   correct, provided the decline carries the observation behind it.

## Archive index

Every closed and refuted item is still here, one hop away, in
[`docs/ROADMAP_ARCHIVE.md`](docs/ROADMAP_ARCHIVE.md). Nothing was deleted. Each line below
links to that item's full original text.

- **0** - Redactor persona leak - CLOSED 2026-08-09 - [full text](docs/ROADMAP_ARCHIVE.md#0-redactor-persona-leak---closed-2026-08-09)
- **1b** - Specialist lane build-out - CLOSED 2026-08-09 - [full text](docs/ROADMAP_ARCHIVE.md#1b-specialist-lane-build-out---closed-2026-08-09)
- **2c** - Ledger fragments have an ID-ALLOCATION race - CLOSED 2026-08-11 - [full text](docs/ROADMAP_ARCHIVE.md#2c-ledger-fragments-have-an-id-allocation-race---closed-2026-08-11)
- **2d** - The suite is only green IN PLACE - CLOSED 2026-08-12 - [full text](docs/ROADMAP_ARCHIVE.md#2d-the-suite-is-only-green-in-place---closed-2026-08-12)
- **2b** - Sanitised fixture for the transient save - CLOSED 2026-08-11 - [full text](docs/ROADMAP_ARCHIVE.md#2b-sanitised-fixture-for-the-transient-save---closed-2026-08-11)
- **3** - Live log tail - CLOSED 2026-08-12 - [full text](docs/ROADMAP_ARCHIVE.md#3-live-log-tail---closed-2026-08-12)
- **4** - `AvgPrice` market cache - CLOSED 2026-08-25 - [full text](docs/ROADMAP_ARCHIVE.md#4-avgprice-market-cache---closed-2026-08-25)
- **7d** - A digit pushed OUTSIDE a field window is SILENTLY DROPPED - CLOSED 2026-09-02 - [full text](docs/ROADMAP_ARCHIVE.md#7d-a-digit-pushed-outside-a-field-window-is-silently-dropped---closed-2026-09-02)
- **4c** - Archive the log and the market cache on every session - CLOSED 2026-08-25b, successor 4d OPEN - [full text](docs/ROADMAP_ARCHIVE.md#4c-archive-the-log-and-the-market-cache-on-every-session---closed-2026-08-25b-successor-4d-open)
- **4d** - Arm the session watcher AUTOMATICALLY - CLOSED 2026-09-01 - [full text](docs/ROADMAP_ARCHIVE.md#4d-arm-the-session-watcher-automatically---closed-2026-09-01)
- **4e** - Re-check the watcher's LIVENESS at the WRAP, not only at entry - CLOSED 2026-09-03 - [full text](docs/ROADMAP_ARCHIVE.md#4e-re-check-the-watchers-liveness-at-the-wrap-not-only-at-entry---closed-2026-09-03)
- **4f** - One wedged surface out of four still reads as ARMED - CLOSED 2026-09-03 - [full text](docs/ROADMAP_ARCHIVE.md#4f-one-wedged-surface-out-of-four-still-reads-as-armed---closed-2026-09-03)
- **OPS-16** - The termination-path guard has three spellings it cannot see - CLOSED 2026-09-03 - [full text](docs/ROADMAP_ARCHIVE.md#ops-16-the-termination-path-guard-has-three-spellings-it-cannot-see---closed-2026-09-03)
- **OPS-17** - `_dead_pid()` reopens the pid-reuse hole its own docstring warns about - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-17-deadpid-reopens-the-pid-reuse-hole-its-own-docstring-warns-about---closed-2026-09-04)
- **OPS-18** - `pid_is_alive` calls a DEAD process ALIVE when it exited with 259 - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-18-pidisalive-calls-a-dead-process-alive-when-it-exited-with-259---closed-2026-09-04)
- **OPS-19** - `pid_is_alive` calls RUNNING processes DEAD on access-denied - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-19-pidisalive-calls-running-processes-dead-on-access-denied---closed-2026-09-04)
- **OPS-20** - Nothing tests `guard.py`'s access mask, and a docstring says otherwise - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-20-nothing-tests-guardpys-access-mask-and-a-docstring-says-otherwise---closed-2026-09-04)
- **OPS-21** - `guard.read_owner` folds four facts onto `None`, and a corrupt lock is reclaimed - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-21-guardreadowner-folds-four-facts-onto-none-and-a-corrupt-lock-is-reclaimed---closed-2026-09-04)
- **OPS-22** - `precommit_gate` matches a forbidden cmdlet as a bare substring - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-22-precommitgate-matches-a-forbidden-cmdlet-as-a-bare-substring---closed-2026-09-04)
- **OPS-23** - A recycled watcher pid can now read ARMED when no watcher exists - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-23-a-recycled-watcher-pid-can-now-read-armed-when-no-watcher-exists---closed-2026-09-04)
- **OPS-24** - `OPS-22`'s accepted false block fired on its own commit - DECLINED, CLOSED 2026-09-05 - [full text](docs/ROADMAP_ARCHIVE.md#ops-24-ops-22s-accepted-false-block-fired-on-its-own-commit---declined-closed-2026-09-05)
- **OPS-25** - A cycle that closes TWO items credits only one - CLOSED 2026-09-04 - [full text](docs/ROADMAP_ARCHIVE.md#ops-25-a-cycle-that-closes-two-items-credits-only-one---closed-2026-09-04)
- **OPS-26** - A watcher that cannot WRITE reads ARMED forever and leaves no trace - CLOSED 2026-09-05 - [full text](docs/ROADMAP_ARCHIVE.md#ops-26-a-watcher-that-cannot-write-reads-armed-forever-and-leaves-no-trace---closed-2026-09-05)
- **OPS-27** - Nothing is written when the context is about to COMPACT - CLOSED 2026-09-08 on a write at DISPATCH, headline REFUTED, hook DECLINED - [full text](docs/ROADMAP_ARCHIVE.md#ops-27-nothing-is-written-when-the-context-is-about-to-compact---closed-2026-09-08-on-a-write-at-dispatch-headline-refuted-hook-declined)
- **OPS-28** - Provenance is DOCUMENT-scoped, so an extracted number arrives naked - CLOSED 2026-09-06 - [full text](docs/ROADMAP_ARCHIVE.md#ops-28-provenance-is-document-scoped-so-an-extracted-number-arrives-naked---closed-2026-09-06)
- **OPS-29** - The ecosystem survey is 28 days stale AND was incomplete on the day it ran - CLOSED 2026-09-06 - [full text](docs/ROADMAP_ARCHIVE.md#ops-29-the-ecosystem-survey-is-28-days-stale-and-was-incomplete-on-the-day-it-ran---closed-2026-09-06)
- **OPS-30** - `pytest` dies with MemoryError in TWO different internal paths - CLOSED 2026-09-06, and the finding was the GATE - [full text](docs/ROADMAP_ARCHIVE.md#ops-30-pytest-dies-with-memoryerror-in-two-different-internal-paths---closed-2026-09-06-and-the-finding-was-the-gate)
- **OPS-31** - The gate is run BEFORE the ledger entry that ships with it - CLOSED 2026-09-06, all three criteria met plus both structural holes - [full text](docs/ROADMAP_ARCHIVE.md#ops-31-the-gate-is-run-before-the-ledger-entry-that-ships-with-it---closed-2026-09-06-all-three-criteria-met-plus-both-structural-holes)
- **OPS-32** - The hand-off is written by NOTHING, so nothing can gate it - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-32-the-hand-off-is-written-by-nothing-so-nothing-can-gate-it---closed-2026-09-08)
- **OPS-33** - `moon_sync_inbox/` has no watcher, and 14 of 15 notes were not ours - CLOSED 2026-09-06, watcher BUILT and FIRING - [full text](docs/ROADMAP_ARCHIVE.md#ops-33-moonsyncinbox-has-no-watcher-and-14-of-15-notes-were-not-ours---closed-2026-09-06-watcher-built-and-firing)
- **OPS-34** - The inbox watcher was blind to SUBDIRECTORIES, and a 700 KB drop sat unseen - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-34-the-inbox-watcher-was-blind-to-subdirectories-and-a-700-kb-drop-sat-unseen---closed-2026-09-07)
- **OPS-37** - Three guards this repository does not have - CLOSED 2026-09-07, all three built and each verified OUTSIDE its own tests - [full text](docs/ROADMAP_ARCHIVE.md#ops-37-three-guards-this-repository-does-not-have---closed-2026-09-07-all-three-built-and-each-verified-outside-its-own-tests)
- **OPS-38** - Tracked files hardcoded this machine's account name - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-38-tracked-files-hardcoded-this-machines-account-name---closed-2026-09-07)
- **OPS-39** - Six defects the wrap's refutation found in the SAME session that shipped them - defects 1-5 CLOSED 2026-09-07, defect 7 and the pathspec defect CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-39-six-defects-the-wraps-refutation-found-in-the-same-session-that-shipped-them---defects-1-5-closed-2026-09-07-defect-7-and-the-pathspec-defect-closed-2026-09-08)
- **OPS-33 follow-up** - A subagent SessionStart consumed the inbox backlog - CLOSED 2026-09-07, report and acknowledge are now separate acts - [full text](docs/ROADMAP_ARCHIVE.md#ops-33-follow-up-a-subagent-sessionstart-consumed-the-inbox-backlog---closed-2026-09-07-report-and-acknowledge-are-now-separate-acts)
- **OPS-40** - This public repo's git history and tracked prose carried the operator's Windows account name - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-40-this-public-repos-git-history-and-tracked-prose-carried-the-operators-windows-account-name---closed-2026-09-07)
- **OPS-41** - Wire an automatic acknowledge trigger tied to the operator's own turn - CLOSED 2026-09-08, criterion 1 measured from a fresh session - [full text](docs/ROADMAP_ARCHIVE.md#ops-41-wire-an-automatic-acknowledge-trigger-tied-to-the-operators-own-turn---closed-2026-09-08-criterion-1-measured-from-a-fresh-session)
- **OPS-42** - Three cross-project questions still waiting on an operator ruling - CLOSED 2026-09-07, all four questions ruled on - [full text](docs/ROADMAP_ARCHIVE.md#ops-42-three-cross-project-questions-still-waiting-on-an-operator-ruling---closed-2026-09-07-all-four-questions-ruled-on)
- **OPS-43** - An outgoing note leaves no trace in this tree, so a cold session believes it has never replied - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-43-an-outgoing-note-leaves-no-trace-in-this-tree-so-a-cold-session-believes-it-has-never-replied---closed-2026-09-07)
- **OPS-44** - The source-register guard's denylist is absorbing this project's own filenames - CLOSED 2026-09-08 on OPTION 2 - [full text](docs/ROADMAP_ARCHIVE.md#ops-44-the-source-register-guards-denylist-is-absorbing-this-projects-own-filenames---closed-2026-09-08-on-option-2)
- **OPS-49** - `CLAUDE.md` cited a git index mode as though it were a claim about execution - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-49-claudemd-cited-a-git-index-mode-as-though-it-were-a-claim-about-execution---closed-2026-09-07)
- **OPS-55** - ruff GLOB-EXPANDS `--stdin-filename`, so a finding can be attributed to a DIFFERENT REAL FILE - and the docstring says that cannot happen - CLOSED 2026-09-08, and the sweep it forced found a SILENT-PASS hole in `--config` - [full text](docs/ROADMAP_ARCHIVE.md#ops-55-ruff-glob-expands---stdin-filename-so-a-finding-can-be-attributed-to-a-different-real-file---and-the-docstring-says-that-cannot-happen---closed-2026-09-08-and-the-sweep-it-forced-found-a-silent-pass-hole-in---config)
- **OPS-59** - The watcher status answers "is it alive and polling" and cannot answer "has it archived anything" - and today those two differ by nine days - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-59-the-watcher-status-answers-is-it-alive-and-polling-and-cannot-answer-has-it-archived-anything---and-today-those-two-differ-by-nine-days---closed-2026-09-08)
- **OPS-58** - The store-drift detector exists and NOTHING CALLS IT - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-58-the-store-drift-detector-exists-and-nothing-calls-it---closed-2026-09-08)
- **OPS-60** - The stash detector misses HALF of a messaged stash, and its "one stash is two commits" arithmetic is wrong in both directions - CLOSED 2026-09-08, and the enumeration found a THIRD stash commit nobody knew about - [full text](docs/ROADMAP_ARCHIVE.md#ops-60-the-stash-detector-misses-half-of-a-messaged-stash-and-its-one-stash-is-two-commits-arithmetic-is-wrong-in-both-directions---closed-2026-09-08-and-the-enumeration-found-a-third-stash-commit-nobody-knew-about)
- **OPS-56** - Only ONE module has been swept for filename-to-external-tool glob defects - CLOSED 2026-09-08, and it found two more, one of them SILENT - [full text](docs/ROADMAP_ARCHIVE.md#ops-56-only-one-module-has-been-swept-for-filename-to-external-tool-glob-defects---closed-2026-09-08-and-it-found-two-more-one-of-them-silent)
- **OPS-54** - Parallel slices share ONE worktree, and a slice that runs `git stash` stashes every other slice's uncommitted work - CLOSED 2026-09-08 on a ban plus a detector, NOT on worktrees - [full text](docs/ROADMAP_ARCHIVE.md#ops-54-parallel-slices-share-one-worktree-and-a-slice-that-runs-git-stash-stashes-every-other-slices-uncommitted-work---closed-2026-09-08-on-a-ban-plus-a-detector-not-on-worktrees)
- **OPS-53** - The watcher status reporter says "archiving into <a date that has passed>" in the PRESENT TENSE - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-53-the-watcher-status-reporter-says-archiving-into-a-date-that-has-passed-in-the-present-tense---closed-2026-09-08)
- **OPS-50** - The redaction rule is scoped to the GAME LOG, so an operator identifier from any other source is unguarded - CLOSED 2026-09-07 by operator ruling - [full text](docs/ROADMAP_ARCHIVE.md#ops-50-the-redaction-rule-is-scoped-to-the-game-log-so-an-operator-identifier-from-any-other-source-is-unguarded---closed-2026-09-07-by-operator-ruling)
- **OPS-45** - The Stop-hook transcript-claim auditor - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-45-the-stop-hook-transcript-claim-auditor---closed-2026-09-08)
- **OPS-46** - The hard-boundary capability backstop is now DERIVED rather than hand-typed - CLOSED 2026-09-07 - [full text](docs/ROADMAP_ARCHIVE.md#ops-46-the-hard-boundary-capability-backstop-is-now-derived-rather-than-hand-typed---closed-2026-09-07)
- **OPS-47** - A sibling's PUBLIC git history carries this project's name - CLOSED 2026-09-07 by operator ruling: NO scrub requested - [full text](docs/ROADMAP_ARCHIVE.md#ops-47-a-siblings-public-git-history-carries-this-projects-name---closed-2026-09-07-by-operator-ruling-no-scrub-requested)
- **OPS-51** - The operator's address sat in a tracked, published file as two halves, and every whole-address sweep called the tree clean - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-51-the-operators-address-sat-in-a-tracked-published-file-as-two-halves-and-every-whole-address-sweep-called-the-tree-clean---closed-2026-09-08)
- **OPS-52** - The operator's account email address is the author identity on 292 commits of this PUBLIC repository - CLOSED 2026-09-08 by operator ruling: LEAVE THE HISTORY AS IS - [full text](docs/ROADMAP_ARCHIVE.md#ops-52-the-operators-account-email-address-is-the-author-identity-on-292-commits-of-this-public-repository---closed-2026-09-08-by-operator-ruling-leave-the-history-as-is)
- **8b** - Source register - CLOSED 2026-08-29 - [full text](docs/ROADMAP_ARCHIVE.md#8b-source-register---closed-2026-08-29)
- **9** - `cdkey` was invisible to the redactor - CLOSED 2026-08-12 - [full text](docs/ROADMAP_ARCHIVE.md#9-cdkey-was-invisible-to-the-redactor---closed-2026-08-12)
- **OPS-7** - `advance_cycle` silently credits an item that was never started - CLOSED 2026-08-27 - [full text](docs/ROADMAP_ARCHIVE.md#ops-7-advancecycle-silently-credits-an-item-that-was-never-started---closed-2026-08-27)
- **OPS-8** - The suite is not safe to run CONCURRENTLY - CLOSED 2026-08-26b - [full text](docs/ROADMAP_ARCHIVE.md#ops-8-the-suite-is-not-safe-to-run-concurrently---closed-2026-08-26b)
- **OPS-12** - Two ops ids each name two different items - CLOSED 2026-08-27 - [full text](docs/ROADMAP_ARCHIVE.md#ops-12-two-ops-ids-each-name-two-different-items---closed-2026-08-27)
- **PORT-1** - The port block is guarded by a test - CLOSED 2026-08-29 - [full text](docs/ROADMAP_ARCHIVE.md#port-1-the-port-block-is-guarded-by-a-test---closed-2026-08-29)
- **OPS-13** - Source register completeness - REFUTED, then RE-CLOSED 2026-08-29c - [full text](docs/ROADMAP_ARCHIVE.md#ops-13-source-register-completeness---refuted-then-re-closed-2026-08-29c)
- **OPS-15** - `precommit_gate._block` fails OPEN when stderr is unusable - CLOSED 2026-08-30 - [full text](docs/ROADMAP_ARCHIVE.md#ops-15-precommitgateblock-fails-open-when-stderr-is-unusable---closed-2026-08-30)
- **OPS-14** - C: hit 100% mid-session, then recovered with nothing deleted - CLOSED 2026-09-06, cause ANSWERED BY THE OPERATOR - [full text](docs/ROADMAP_ARCHIVE.md#ops-14-c-hit-100-mid-session-then-recovered-with-nothing-deleted---closed-2026-09-06-cause-answered-by-the-operator)
- **13** - Page-2 talent NODE TEXT - CLOSED 2026-08-30e, and its OWN premise was false - [full text](docs/ROADMAP_ARCHIVE.md#13-page-2-talent-node-text---closed-2026-08-30e-and-its-own-premise-was-false)
- **14** - CLOSED 2026-09-01 - the premise is REFUTED, the two bows are two TYPES - [full text](docs/ROADMAP_ARCHIVE.md#14-closed-2026-09-01---the-premise-is-refuted-the-two-bows-are-two-types)
- **OPS-57** - Both continuity documents will outgrow their budgets within days, and raising the numbers is not the fix - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-57-both-continuity-documents-will-outgrow-their-budgets-within-days-and-raising-the-numbers-is-not-the-fix---closed-2026-09-08)
- **OPS-61** - Every hook command names an ABSOLUTE repo root, so a worktree's hook reports the WRONG TREE - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-61-every-hook-command-names-an-absolute-repo-root-so-a-worktrees-hook-reports-the-wrong-tree---closed-2026-09-08)
- **OPS-62** - The two archives OPS-57 created are UNBUDGETED, and nothing measures their growth - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-62-the-two-archives-ops-57-created-are-unbudgeted-and-nothing-measures-their-growth---closed-2026-09-08)
- **OPS-63** - The source register never reads `ROADMAP.md`, and the OPS-57 split made that visible rather than new - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-63-the-source-register-never-reads-roadmapmd-and-the-ops-57-split-made-that-visible-rather-than-new---closed-2026-09-08)
- **OPS-64** - `tools/archive_link_guard.py` accepts any argv and silently ignores it - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-64-toolsarchivelinkguardpy-accepts-any-argv-and-silently-ignores-it---closed-2026-09-08)
- **OPS-65** - The wrap ritual writes the hand-off to an ABSOLUTE target, so a wrap from a worktree overwrites the primary tree's hand-off - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-65-the-wrap-ritual-writes-the-hand-off-to-an-absolute-target-so-a-wrap-from-a-worktree-overwrites-the-primary-trees-hand-off---closed-2026-09-08)
- **OPS-66** - `tools/precommit_gate.py` read an unknown argument as a PASS, so a typo in `.githooks/pre-commit` would switch the lint gate off silently - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-66-toolsprecommitgatepy-read-an-unknown-argument-as-a-pass-so-a-typo-in-githookspre-commit-would-switch-the-lint-gate-off-silently---closed-2026-09-08)
- **OPS-67** - Four `tools/` entry points still read an unknown argument as a pass, and the four are not one decision - CLOSED 2026-09-08 - [full text](docs/ROADMAP_ARCHIVE.md#ops-67-four-tools-entry-points-still-read-an-unknown-argument-as-a-pass-and-the-four-are-not-one-decision---closed-2026-09-08)
- **OPS-69** - `docs/INVENTORY.md` is guarded in ONE direction, so a module missing from it is invisible - CLOSED 2026-09-10 - [full text](docs/ROADMAP_ARCHIVE.md#ops-69-docsinventorymd-is-guarded-in-one-direction-so-a-module-missing-from-it-is-invisible---closed-2026-09-10)
- **OPS-70** - `.claude/settings.json` still hardcodes an absolute repo root in `permissions.allow` - the OPS-61 defect surviving in the file OPS-61 cleaned - CLOSED 2026-09-10 - [full text](docs/ROADMAP_ARCHIVE.md#ops-70-claudesettingsjson-still-hardcodes-an-absolute-repo-root-in-permissionsallow---the-ops-61-defect-surviving-in-the-file-ops-61-cleaned---closed-2026-09-10)
- **OPS-72** - A store-drift guard failed intermittently - a one-second committer-timestamp race - CLOSED 2026-09-10 - [full text](docs/ROADMAP_ARCHIVE.md#ops-72-a-store-drift-guard-failed-intermittently---a-one-second-committer-timestamp-race---closed-2026-09-10)
- **OPS-73** - Two holes in the lane-slot join, both found by the wrap that shipped it - CLOSED 2026-09-11 - [full text](docs/ROADMAP_ARCHIVE.md#ops-73-two-holes-in-the-lane-slot-join-both-found-by-the-wrap-that-shipped-it---closed-2026-09-11)
- **OPS-74** - Nothing here measures whether a guard is GREEN only because a tool is absent - CLOSED 2026-09-11 - [full text](docs/ROADMAP_ARCHIVE.md#ops-74-nothing-here-measures-whether-a-guard-is-green-only-because-a-tool-is-absent---closed-2026-09-11)
- **OPS-76** - The stale arm is DEAD CODE on the live path - nothing calls `reap()`, so a leaked lock holds a shared slot forever - CLOSED 2026-09-11 - [full text](docs/ROADMAP_ARCHIVE.md#ops-76-the-stale-arm-is-dead-code-on-the-live-path---nothing-calls-reap-so-a-leaked-lock-holds-a-shared-slot-forever---closed-2026-09-11)
- **OPS-35** - Adopt the cross-project lock, re-implemented - CLOSED 2026-09-11, all six criteria met - [full text](docs/ROADMAP_ARCHIVE.md#ops-35-adopt-the-cross-project-lock-re-implemented---closed-2026-09-11-all-six-criteria-met)
- **OPS-48** - Four cross-project questions are waiting on an OPERATOR ruling, not on us - ADJUDICATED AND CLOSED 2026-09-14 - [full text](docs/ROADMAP_ARCHIVE.md#ops-48-four-cross-project-questions-are-waiting-on-an-operator-ruling-not-on-us---adjudicated-and-closed-2026-09-14)
- **OPS-75** - No check asks whether a `.gitignore` pattern already shadows a tracked file - CLOSED 2026-09-12 - [full text](docs/ROADMAP_ARCHIVE.md#ops-75-no-check-asks-whether-a-gitignore-pattern-already-shadows-a-tracked-file---closed-2026-09-12)
- **OPS-87** - The refute-then-repair-then-repair-the-repair cycle costs more than the work - OPERATOR-RULED, and laned for cross-project consensus - CLOSED 2026-09-13 - [full text](docs/ROADMAP_ARCHIVE.md#ops-87-the-refute-then-repair-then-repair-the-repair-cycle-costs-more-than-the-work---operator-ruled-and-laned-for-cross-project-consensus---closed-2026-09-13)
- **OPS-77** - A surplus width of ZERO is a permanent silent "busy", one level up from the hole `OPS-73` just closed - CLOSED 2026-09-12 - [full text](docs/ROADMAP_ARCHIVE.md#ops-77-a-surplus-width-of-zero-is-a-permanent-silent-busy-one-level-up-from-the-hole-ops-73-just-closed---closed-2026-09-12)
- **OPS-78** - 187 tests FAIL rather than skip when `git` is absent, measured - CLOSED 2026-09-11, all five criteria met - [full text](docs/ROADMAP_ARCHIVE.md#ops-78-187-tests-fail-rather-than-skip-when-git-is-absent-measured---closed-2026-09-11-all-five-criteria-met)
- **OPS-79** - Three gaps in the false-red probe's own instrument, found by refuting it - CLOSED 2026-09-11 (a fourth was added, and closed with them) - [full text](docs/ROADMAP_ARCHIVE.md#ops-79-three-gaps-in-the-false-red-probes-own-instrument-found-by-refuting-it---closed-2026-09-11-a-fourth-was-added-and-closed-with-them)
- **OPS-80** - The documented remedy for a fired size budget does not apply anything - CLOSED 2026-09-11 - [full text](docs/ROADMAP_ARCHIVE.md#ops-80-the-documented-remedy-for-a-fired-size-budget-does-not-apply-anything---closed-2026-09-11)
- **OPS-81** - Each applied split adds one blank line before the roadmap's archive index, forever - CLOSED 2026-09-12 - [full text](docs/ROADMAP_ARCHIVE.md#ops-81-each-applied-split-adds-one-blank-line-before-the-roadmaps-archive-index-forever---closed-2026-09-12)
- **OPS-82** - The guard that protects the operator's live mail records is the only NON-ATOMIC writer of them in the tree - CLOSED 2026-09-11, all six criteria met - [full text](docs/ROADMAP_ARCHIVE.md#ops-82-the-guard-that-protects-the-operators-live-mail-records-is-the-only-non-atomic-writer-of-them-in-the-tree---closed-2026-09-11-all-six-criteria-met)
- **OPS-83** - 49 tests need a POSIX userland, not `bash`, and no guard names what they actually need - CLOSED 2026-09-12 - [full text](docs/ROADMAP_ARCHIVE.md#ops-83-49-tests-need-a-posix-userland-not-bash-and-no-guard-names-what-they-actually-need---closed-2026-09-12)
- **OPS-86** - `tools/false_red_probe.py` cannot recognise its own control when the rootdir sits inside the system temp tree - CLOSED 2026-09-12 - [full text](docs/ROADMAP_ARCHIVE.md#ops-86-toolsfalseredprobepy-cannot-recognise-its-own-control-when-the-rootdir-sits-inside-the-system-temp-tree---closed-2026-09-12)
- **OPS-84** - Vendor Legion Wallpaper's write tracer under the license it named - CLOSED 2026-09-11, operator-ruled - [full text](docs/ROADMAP_ARCHIVE.md#ops-84-vendor-legion-wallpapers-write-tracer-under-the-license-it-named---closed-2026-09-11-operator-ruled)
- **OPS-85** - Two test probe files write into the live `ops/runtime/` - CLOSED 2026-09-11, NO DEFECT, and the first version of this item was wrong - [full text](docs/ROADMAP_ARCHIVE.md#ops-85-two-test-probe-files-write-into-the-live-opsruntime---closed-2026-09-11-no-defect-and-the-first-version-of-this-item-was-wrong)
- **OPS-88** - The suite-run recorder cannot see a target supplied through the environment, and its reason list says so by omission rather than by name - CLOSED 2026-09-13 - [full text](docs/ROADMAP_ARCHIVE.md#ops-88-the-suite-run-recorder-cannot-see-a-target-supplied-through-the-environment-and-its-reason-list-says-so-by-omission-rather-than-by-name---closed-2026-09-13)
- **OPS-89** - The single-instance loop guard is INERT when the loop is driven from a conversation rather than from one long-lived process - RE-CLOSED 2026-09-13 after the first close was REFUTED - [full text](docs/ROADMAP_ARCHIVE.md#ops-89-the-single-instance-loop-guard-is-inert-when-the-loop-is-driven-from-a-conversation-rather-than-from-one-long-lived-process---re-closed-2026-09-13-after-the-first-close-was-refuted)
- **OPS-90** - The lane slot is held only for the length of one command, so a conversational session rations with nobody - and the fix is a PROTOCOL change we may not make alone - CLOSED 2026-09-13 - [full text](docs/ROADMAP_ARCHIVE.md#ops-90-the-lane-slot-is-held-only-for-the-length-of-one-command-so-a-conversational-session-rations-with-nobody---and-the-fix-is-a-protocol-change-we-may-not-make-alone---closed-2026-09-13)
