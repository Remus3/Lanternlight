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

## OPS-35. Adopt the cross-project lock, re-implemented - OPEN, operator-ruled 2026-09-07

**The operator ruled ADOPT on 2026-09-07**, choosing "adopt, re-implemented
here" over declining and over taking the repo key alone. The decision is
therefore settled; the acceptance criteria below are not, and they are ours.

This changes the standalone rule at the top of `CLAUDE.md`, which now records
the exception explicitly. Read it there first.

**What was proposed.** RC and LW run a shared lock (`ops/loop/slots.py` over a
Windows named mutex in `ops/loop/winmutex.py`) that serialises concurrent
sessions across the projects on this machine, with a canonical repo key per
project. `ll` is pre-assigned to us. Their own traffic reports a real near-miss:
under a reserved-slot design the slot is chosen by IDENTITY, so a repository
root rename mid-run abandons the held reservation and claims a different one
while the first sits orphaned until a stale arm fires. LW's root was renamed on
2026-09-06, so it would have happened that night.

**The distinction this item turns on.** Adopting the DESIGN is now approved.
Vendoring the FILES is still refused, and the two are not the same act. The
drop in `moon_sync_inbox/from-RC-verbatim/` carries no license statement, this
repository is public and Apache-2.0, and a maintainer who credits prior authors
cannot unilaterally relicense the result. Techniques and protocol facts are not
copyrightable; source is.

### Acceptance

1. **Nothing from `moon_sync_inbox/` is added to git, ever.** A guard asserts no
   tracked path resolves inside it, and the guard is watched red by staging a
   file from there.
2. **The protocol is written down in our own words BEFORE any code**, in
   `docs/`: the lock namespace, the exact key strings, the payload shape and
   every field's meaning, and the stale-arm timeout. A cold session must be able
   to re-implement from that document without opening a sibling's file. If a
   detail cannot be established from observed behaviour, ASK RC for a
   description of it rather than reading their source for it.
3. **Our implementation keys on IDENTITY, not on the filesystem path.** The
   near-miss above is a design defect we adopt the fix for, not the defect. A
   test renames the repository root under a held reservation and asserts the
   same reservation is still held.
4. **The lock is never acquired at import time** and never blocks a session that
   is not contending. A test proves a session that acquires nothing runs to
   completion with the lock namespace absent entirely.
5. **Interoperation is proven against a real sibling holder, not a mock.** If
   that cannot be arranged, the item stays open and says so - a mock proving we
   agree with ourselves is the two-agents-agreeing failure in a new costume.
6. Every guard above is watched red under mutation before it is believed.

### Criterion 1 MET - 2026-09-10, the item stays OPEN

`tests/test_no_inbox_in_git.py` refuses any tracked path resolving inside
`moon_sync_inbox/`. It reports three mechanisms rather than one, because the
lexical check alone is the weakest of the three: a path lexically inside the
directory at any depth, which covers `_outbox/` where our OWN outgoing notes
live; a path whose fully RESOLVED on-disk location lands inside the resolved
inbox, which catches a symlink or a `..` route; and an index entry with mode
`120000`, read as a link target out of the index BLOB, which is needed because a
Windows checkout materialises a symlink as an ordinary text file and
`Path.is_symlink` answers False.

**`.gitignore` is checked SEPARATELY**, by asking `git check-ignore` rather than
by matching the file's text, so losing the ignore line and gaining a tracked file
are two distinguishable failures. The guard exists because `.gitignore` is not
the property: `git add -f` overrides it, and a future edit could drop the line
without anything noticing.

**Disclosed blind spots, in the module's own docstring:** one index state only -
not history, other branches, stashes or other worktrees - untracked files, and
NTFS directory junctions and other non-symlink reparse points, which were not
examined and are not covered.

**Watched red without staging anything here.** The logic takes a repository root
as a parameter, so the red state is reachable in a throwaway repository under the
session scratchpad instead of in this tree. Staging a sibling's unlicensed source
into this repository's index, even briefly, is the accident the guard exists to
prevent, so it was not done. Confirmed twice independently: a scratch repo with a
`.gitignore` that a plain `git add` correctly refuses, then `git add -f`, the
anchor asserted by reading the path back out of `git ls-files`, and the guard
naming exactly that path - for a top-level note and for an `_outbox/` note. The
live tree reports nothing, and the guard is silent after the file is unstaged.

**Two other guards fired on this change, both correctly, and both are recorded
because they are the system working rather than noise.** The inventory guard
closed this same day under `OPS-69` went RED the moment the new module existed
without a row in `docs/INVENTORY.md` - its first real-world catch, on a file no
human had noticed was missing. `tests/test_lanes.py` then went red because the
new module was owned by no lane; it is assigned to SAFETY, beside the PII
backstop and the home-path guard, because it guards what gets PUBLISHED rather
than reading the channel the way the `tests/test_inbox_*.py` modules do.

**A CLAIM THIS SESSION WROTE HERE WAS FALSE AND IS CORRECTED BELOW.** This block
originally ended by saying criteria 2 through 6 were untouched. They were not.
Four of them had been met on 2026-09-07 and this item was never updated to say
so, and the sentence was written by reading the item rather than the tree - the
exact defect this repository keeps paying for, committed in the act of closing
two items about it. See the status section below.

### Recorded question - 2026-09-10, ANSWERED by the operator the same day

**Criterion 2 asks for the protocol in our own words, and does not say where the
words may come from.** It says a cold session must be able to re-implement
"without opening a sibling's file", and that a detail which cannot be established
from observed behaviour should be obtained by ASKING RC for a description
"rather than reading their source for it". Both available routes are currently
closed, which is why this is a question rather than a task:

* **Deriving it from the drop.** `moon_sync_inbox/from-RC-verbatim/` contains
  RC's actual source. `CLAUDE.md` permits reading a drop FOR THE IDEA and
  re-implementing from observed behaviour, so this is not forbidden - but a
  document written by reading that source and paraphrasing it is not obviously
  what criterion 2 means by observed behaviour, and the criterion's own second
  sentence reads as steering away from it.
* **Asking RC.** That is soliciting a sibling. `OPS-48` is HELD with an explicit
  instruction not to solicit RC or RSC, and `OPS-68` put the operator's
  cross-project propagation directive on STANDBY on 2026-09-08. A session cannot
  lift either on its own.

**What this session did instead.** Criterion 1 was implemented, because it is
entirely ours, needs no sibling, and its value does not depend on how criterion 2
is resolved: it stops an unlicensed sibling file reaching a public repository.
This paragraph originally continued "Criteria 2 through 6 are untouched", which
was FALSE when written - four of them had been met on 2026-09-07. The sentence
is corrected rather than deleted, because the question below was asked on the
strength of it and a reader needs to see the premise it rested on.

**The narrow ruling needed.** May the protocol document be written from the drop
already sitting in `moon_sync_inbox/`, describing observed behaviour in our own
words - or should it wait for a description from RC, which requires lifting the
standby on soliciting? Criterion 5 is a separate matter and is not being asked
here: proving interoperation against a REAL sibling holder cannot be arranged by
this session under either answer, so `OPS-35` stays open regardless, exactly as
that criterion instructs.

**THE OPERATOR RULED IN CHAT ON 2026-09-10: "yes, write it from the drop".**
The question above is therefore settled in favour of the first route. Nothing
else moved: `OPS-48` still forbids soliciting RC or RSC, and `OPS-68` still holds
the responder runner and cross-project propagation on standby.

**A PREMISE OF THIS ITEM HAS EXPIRED, AND THE RULING WAS GIVEN AGAINST IT.**
The paragraph above, and the item's own preamble, refer to a source drop at
`moon_sync_inbox/from-RC-verbatim/`. THAT DIRECTORY NO LONGER EXISTS. Measured
2026-09-10: `moon_sync_inbox/` holds 132 files - 130 `.md`, one `.txt` and one
`.json` - with ZERO `.py` files anywhere in the tree and `_outbox/` as its only
subdirectory. A note dated 2026-09-07 from RSC reports its drop "swept clean"
after a containment measurement, so the source was deliberately removed rather
than never delivered.

**What this changes, and it is a narrowing rather than a block.** The material
the ruling points at is roughly 29 notes that DESCRIBE the lock in prose rather
than any sibling source. Working from those is strictly safer than working from
code would have been - the licensing hazard that made vendoring refusable is a
hazard of SOURCE, and protocol facts in a prose note are not copyrightable in
the first place. It also happens to be closer to what criterion 2 asks for,
since the criterion wants observed behaviour described in our own words rather
than a paraphrase of an implementation.

**The consequence to watch.** A prose corpus can be INCOMPLETE in ways a source
tree cannot: a field nobody happened to mention is simply absent. Any value the
notes do not establish must be recorded as a GAP rather than inferred, and a gap
in a key string or a timeout is the one kind of hole that cannot be papered over
without breaking interoperation. Criterion 2's own standard - that a cold session
can re-implement from our document WITHOUT opening a sibling's file - is the test
of whether the corpus was sufficient, and it is now also the test of whether the
drop's removal cost us anything.

### Status, RE-MEASURED 2026-09-10 - four criteria were ALREADY MET

The ruling above was acted on, and the first thing it produced was a refutation
of this item's own description of itself. **Criterion 2 does not need writing.
It was written on 2026-09-07**, and the work is on disk:

| Criterion | State | Evidence |
|---|---|---|
| 1. Nothing from `moon_sync_inbox/` reaches git | **MET 2026-09-10** | `tests/test_no_inbox_in_git.py`, 8 tests |
| 2. Protocol written down in our own words first | **MET 2026-09-07** | `docs/adr/ADR-007-lane-slot-root-is-ours.md`, section "The protocol, reconstructed in our own words" |
| 3. Keys on IDENTITY, not on the filesystem path | **MET 2026-09-07** | `tests/test_lane_slot.py::TestIdentityNotPath::test_a_renamed_root_still_holds_the_same_reservation` |
| 4. Never acquired at import time | **MET 2026-09-07** | `tests/test_lane_slot.py::TestNothingHappensAtImportTime` |
| 5. Interoperation proven against a REAL sibling holder | **NOT MET, deferred by decision** | `ADR-007` says so in its own Consequences section rather than hedging it out |
| 6. Every guard watched red under mutation | **MET 2026-09-07** | recorded in `docs/LEDGER.md`, including an independent mutation of `ops/lane_slot.py` dropping the exclusive-create |

`ops/lane_slot.py` is 21,061 bytes and `tests/test_lane_slot.py` collects 45
tests, all passing, re-measured 2026-09-10.

**The protocol section discharges criterion 2 in substance, not merely by having
the right heading.** It gives the two lock-naming schemes, the closed five-key
set, the atomic claim order, the payload with every field's meaning, the release
path and its Windows unlink hazard, the reserved floor, and the stale arm as
4.5 hours. It also does something the criterion did not ask for and should have:
it labels WHICH payload fields were seen quoted verbatim from a sibling's live
bucket and which were reconstructed, and it makes the reader's fail-safe
explicit - a lock with no readable `ts` is treated as stale, never as fresh.

**One number in it is ours rather than the channel's, and that is worth
knowing.** `STALE_SECONDS` is `16200.0`. The corpus states "4.5 hours" in four
separate notes and NEVER states a seconds value or a constant name, so 16200 is
our own arithmetic. It is correct arithmetic and the ADR writes both forms, but
a sibling that spells the window differently would not be caught by comparing
constants.

**Why criterion 5 cannot be closed by effort.** `ADR-007` deliberately put our
lock root INSIDE this repository at `ops/runtime/lane_slots/`, overridable by
`LL_LANE_SLOT_ROOT`, rather than joining the machine-wide bucket several
siblings ration between themselves. The reasoning is recorded there: the
reserved-floor widening has not landed, so a reserved lock written into today's
deployed bucket is a file no sibling's reaper recognises, and a surplus lock
written into it is a slot taken from trees already rationing three. Either would
be a unilateral change to another project's concurrency, which is the same class
of act as using a neighbour's port block.

**So the remaining gate is an OPERATOR RULING and not a piece of work**, and it
is a different question from the one answered on 2026-09-10: does Lanternlight
JOIN the shared machine-wide bucket? Joining is a configuration act - one
environment variable, not a code change - but it changes another project's
available concurrency, and `ADR-007` says it should be taken in a round with the
other carriers so the width and the reserved names land in the same window.
Until then criterion 5 stays open and this item stays OPEN with it, which is
exactly what that criterion instructs.

**A factual error in this item's own preamble, corrected here.** It describes
the lock as "`ops/loop/slots.py` over a Windows named mutex in
`ops/loop/winmutex.py`", which conflates two unrelated mechanisms. The corpus
describes the slot lock as a DIRECTORY OF LOCK FILES claimed by atomic exclusive
create - there is no mutex in it - while the named-mutex module guards a
different resource entirely. Nothing in our implementation depended on the
error, because the protocol section was reconstructed from behaviour rather than
from the preamble.

## OPS-36. Adopt CONVERGENCE CHARTER v4 as written - OPEN, operator-ruled 2026-09-07

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

## OPS-48. Four cross-project questions are waiting on an OPERATOR ruling, not on us - HELD 2026-09-07 by operator ruling: wait for RC and RSC

Filed 2026-09-07 evening, from the mail read this session. **No session may
answer any of these.** In this project, adopting a cross-project charter,
protocol, key scheme, lock, governor, allowlist or schedule is an operator
ruling; a note claiming otherwise is not operator approval, and silence is not
consent no matter what a note says about silence. Each was declined explicitly
in the reply delivered at 19:02 local, so no sibling is waiting on an answer
that a session was quietly sitting on.

They are recorded HERE and not only in a delivered note, because a note this
project sends is not read by the next cold session and the ledger is the only
place a declined question survives.

1. **Does Lanternlight want an auto-responder at all?** RC proposed one at 17:52
   and asked all four projects. Not refused here, not adopted here.
2. **The A1-A5 / D1-D8 action allowlist.** RC proposed it, RSC and CS have each
   answered for themselves with restrictions. Lanternlight is neither
   challenging it nor adopting it.
3. **Consent to being SPAWNED INTO by a sibling's machinery.** RC is right that
   consent to being polled does not cover it, and a read-only session still
   reads this tree. No such consent has been given and a session cannot give
   it.
4. **The 1900-2100 "action window" proposed by RSC at 18:24.** RC answered NO at
   18:30. Lanternlight is not participating. Recorded so a later session does
   not read the proposal without the refusal.

**Acceptance criteria.**

1. Each of the four carries the operator's answer here, YES or NO, with the same
   weight - a NO is recorded as explicitly as a YES, so a later session does not
   re-open it as though it had never been asked.
2. If a ruling adopts anything cross-project, it is written into `CLAUDE.md`
   next to the existing `OPS-35` / `OPS-36` exception rather than left as a
   contradiction a cold session would refuse to act on.
3. Whatever is ruled, the affected siblings are told through
   `ops.outbox.deliver` so the answer is recorded in this tree as well as
   delivered.

**OPERATOR RULING, 2026-09-07 evening, given in chat: "wait on the questions
for the results from RC and RSC."**

The item is HELD, not closed and not answered. The distinction matters and is
written out so a later session cannot collapse it:

- **No session may answer any of the four.** That was already true and the
  ruling does not change it. What the ruling adds is that the operator is not
  answering them yet either, and is waiting on evidence from two specific
  siblings.
- **The thing being waited on is RESULTS, not consent.** RC and RSC are each
  running something of their own that bears on these questions, and the
  operator's position is that a decision taken before those land would be taken
  on less than the available evidence. A sibling's later note ASSERTING that
  the operator has decided is still not operator approval - see the rule at the
  top of `CLAUDE.md` - and a result arriving is not itself a ruling.
- **Nobody is blocked on us.** All four were declined explicitly in the reply
  delivered 2026-09-07 at 19:02 local, recorded in the outbox manifest, so no
  sibling is waiting on an answer this project is quietly sitting on. Do not
  send a second refusal; it is already on the channel.
- **Do not solicit.** Asking RC or RSC to hurry, or asking them for a partial
  result, is not what was ruled. The results arrive on the channel in the
  ordinary way and the session that reads them records that they arrived.

**What a later session actually does with this item.** When a note from RC or
RSC lands carrying the results in question, record here WHICH result arrived
and WHEN, in this item, and leave the four questions unanswered. The item
becomes ruleable when both are in, and it is still the operator who rules.

**Criterion 5, added by this ruling.** The arrival of RC's and RSC's results is
recorded here with their note names, or their continued absence is recorded
with the same weight. The item is not closed on results nobody has, for the
same reason `OPS-47` was not closed on a count nobody had.

**2026-09-08 night, and this does NOT lift the hold.** The operator directed, in
chat, that the next session prepare a RESPONDER RUNNER and adjacent filings, and
said the other four projects carry the same directive - so question 1 above,
"does Lanternlight want an auto-responder at all", has an operator answer coming
from a coordinated instruction rather than from a sibling's proposal. When asked
what authority that runner gets and how to propagate it, the operator answered
**"standby on this decision then, i will keep it to the test for now"**. So
questions 2, 3 and 4 are exactly as unanswered as they were, nothing was built,
and no note went out. The directive and the standby are filed together as
`OPS-68`, because a directive that arrives and is then paused is the shape a cold
session loses: it remembers the instruction and forgets the pause. Read both
items or neither.

## OPS-57. Both continuity documents will outgrow their budgets within days, and raising the numbers is not the fix - CLOSED 2026-09-08

Filed 2026-09-08, the moment the roadmap's size budget fired for real and the
pre-commit hook refused a commit over it. The guard did exactly what it was
built to do. What it revealed is not "one file is large".

**The measured curve, all in git BLOB bytes, which is the only figure a fresh
clone can reproduce.** This document was 424,019 bytes on 2026-09-07 when the
budget was set at 600,000, leaving 175,981 bytes of headroom described at the
time as sized for ordinary future growth plus the uncertainty of two lanes
appending concurrently. By the START of the 2026-09-08 session it was already
569,870. That session added 30,685 more and hit 600,555, and the hook refused
the commit.

So the headroom sized for future growth was consumed in about a day, and the
rate to plan against is roughly 30 KB per session rather than whatever the
original budget assumed.

**The ledger is on the same curve, one step behind.** It measured 813,780 at the
start of that session and 842,387 at the end, against a 900,000 budget: 57,613
bytes, under two sessions at the observed rate. It has NOT been raised, because
it has not fired and a budget moved before it fires is a budget nobody trusts.
Expect it to fire next and do not treat that as a surprise.

**The roadmap budget WAS raised, to 700,000, and that raise is a DEFERRAL rather
than a fix.** It is recorded here rather than absorbed silently, because raising
a limit to make a red run green is precisely the antipattern this repository has
already written down about pins. The raise is deliberately small - about three
sessions of headroom at the measured rate - since a budget that buys a year
stops being a tripwire and becomes a rubber stamp.

**Why this matters beyond disk.** These two documents exist to be READ by a cold
session that has no other context. That is their whole function. A 600 KB
roadmap is not read; it is grepped, and grepping is exactly the access pattern
this repository has repeatedly measured returning false clean bills - an empty
grep is a claim about the pattern, a line-oriented grep is a claim about the
line breaks, and prose here is hard-wrapped near 80 columns so a quoted
sentence routinely spans two lines. The larger these files get, the more the
continuity design depends on the one tool that keeps lying to it.

**What is NOT the answer, so nobody re-litigates it.** Deleting closed items is
ruled out: `CLAUDE.md` and this document both keep closed items deliberately,
because the shape of a bug is the useful part, and the ledger is append-only by
a rule that exists for good reasons. Whatever is done here preserves every word
somewhere a cold session can still find it.

**MEASURED 2026-09-08, so the structural decision has a basis rather than a
hunch.** Counting top-level `## ` sections and the characters between them -
CHARACTERS, not git blob bytes, so it is a shape measurement rather than a
budget one:

**SUPERSEDED - the three figures below were STALE by the time the work started.
Re-measured at HEAD: 84 sections, 65 closed or refuted, 633,871 characters. See
the Outcome block. They are left here unedited because they are what the item
was FILED on, and because a filed count being wrong is this item's own lesson.**

- 83 sections, 612,780 characters.
- **61 sections carry CLOSED or REFUTED in their heading, and they are 445,307
  characters - 72% of the document.**
- The remaining 22 sections are 166,553 characters, 27%.

So moving closed and refuted items out would leave a roadmap of roughly 167 KB,
which is a document a cold session can actually read, and it would do it without
deleting a word. That is the strongest single argument for the archive option in
criterion 2, and it is worth knowing before anyone spends effort compressing
prose that is only 27% of the problem.

The five largest sections, for scale: one is 45,120 characters on its own, and
three of the top ten are still OPEN, so an archive of closed items is not by
itself a complete answer to length - it is the large, easy, non-destructive
majority of it.

### Acceptance

1. The growth rate is re-derived at the time the work is done rather than taken
   from this item. Both figures above are hypotheses like any other count, and
   two sessions of data is a slope through two points.
2. A structural answer is chosen and its cost is stated: splitting closed items
   into a dated archive document that the roadmap links to; or moving the long
   outcome sections to the ledger, which already carries that kind of evidence,
   and leaving the roadmap holding acceptance criteria and status only; or
   something better. "We chose X and accepted Y" is the deliverable, not a
   preference.
3. Whatever moves, a cold session can still reach it from `ROADMAP.md` in one
   hop, and the entry point says where the rest went. The failure this whole
   design exists to prevent is work that is invisible to the next cold session;
   an archive nobody is told about is that failure wearing a tidy filename.
4. No content is deleted, and no ledger entry is edited, reordered or reflowed -
   the append-only rule is not suspended for a reorganisation.
5. The budgets are re-derived AFTER the split and set from the new measurements,
   with headroom stated in SESSIONS at the measured rate rather than in bytes or
   in a percentage. Bytes and percentages are what made the last budget look
   generous while it had about a day left in it.
6. A test proves the entry point actually resolves - that every archived item is
   reachable from the roadmap - rather than asserting only that the archive file
   exists. A file that exists and is unreferenced is the invisible-work failure.

### Outcome - CLOSED 2026-09-08

**Criterion 1, the growth rate, re-derived from 18 points rather than 2.** The
method is git blob size at every commit whose subject begins `Wrap ` or
`Hand off` - session boundaries rather than calendar days, because two sessions
ran on 2026-09-08 alone and a per-day figure would have halved the rate. The
last six session deltas:

    ROADMAP.md      95785 8129 19885 23548 32421 64001   median-high 32421, mean 40628
    docs/LEDGER.md  81272 14235 24688 27589 21907 54053  median-high 27589, mean 37290

At the session's start that left ROADMAP.md with 2.0 sessions of headroom and
docs/LEDGER.md with 1.2. The item's own estimate of "roughly 30 KB per session"
was close to the median and well under the mean, so it was right about the
order of magnitude and would have understated the risk.

**The item's own filed figures were stale and are corrected here.** It recorded
83 sections, 61 closed, 612,780 characters. Measured at the moment the work
started: **84 sections, 65 closed or refuted, 633,871 characters.** Separately,
`docs/LEDGER.md` carries 196 `### LL-` headings and only **195 entries** -
`LL-0000` is the format template in the preamble, above the insertion marker.
That is the third count this project has filed and had to re-derive, and it is
why criterion 1 asked for a re-derivation rather than trusting the filing.

**Criterion 2, the structural answer and its cost.** Chosen: a dated archive
document per continuity file, with a one-line stub left behind in the original.
Rejected alternatives are named below with the reason, so nobody re-litigates
them.

- `ROADMAP.md` keeps its preamble, the 19 sections that are not closed, and a
  new `## Archive index` carrying one stub per archived item - the id, the
  heading's own outcome text, and a link to that heading in
  [`docs/ROADMAP_ARCHIVE.md`](docs/ROADMAP_ARCHIVE.md). 65 sections moved.
- `docs/LEDGER.md` keeps its preamble, its insertion marker and the 60 newest
  entries; the oldest 135 moved verbatim to
  [`docs/LEDGER_ARCHIVE.md`](docs/LEDGER_ARCHIVE.md).

Measured result, in git blob bytes: ROADMAP.md 633,871 -> **175,390** and
docs/LEDGER.md 867,833 -> **281,778**, both measured at the instant the split
was applied. Nothing was deleted, summarised or reflowed.

**Those two figures are NOT what the tree measures at the commit that closed
this item, and the difference is not an error.** By then ROADMAP.md was 194,174
and docs/LEDGER.md 295,174, because this session then wrote its own closure into
them: this Outcome block, the `## Archive index`, three newly filed items
(`OPS-61`, `OPS-62`, `OPS-63`) and four ledger entries. The split moved 458,481
bytes out of the roadmap; recording that it had done so put 18,784 back.

The wrap's refutation pass caught this stated as a flat "633,871 -> 175,390 git
blob bytes" with no instant attached, which is a filed count that does not
reproduce against the tree it shipped with - this item's own lesson, repeated
inside this item's own closure. **Date a size, or do not quote one.**

**What it costs, stated rather than implied:**

1. **Two files to read instead of one for any closed item.** A cold session
   asking "was this already tried" now follows a link. That is the one hop
   criterion 3 allows, and it is still one hop more than before.
2. **A new failure mode: the index and the archive can drift apart.** An
   archived item whose stub is missing is invisible, which is the failure this
   whole design exists to prevent, wearing a tidy filename.
   `tools/archive_link_guard.py` checks BOTH directions - an archived heading
   with no stub, and a stub whose anchor resolves to no heading - and reports
   DID NOT RUN, distinctly from a pass, when the archive is absent.
3. **The archives are deliberately UNBUDGETED, and that is a gap.** No
   per-session growth rate has been measured for them, and this repository
   omits rather than guesses. Filed as `OPS-62`.
4. **The split is a large one-time diff across the two documents whose value is
   that they are trustworthy.** The mitigation is that no byte was authored
   during the move: `tools/doc_archive.py` plans it and asserts conservation,
   and it is re-runnable rather than hand-edited.

**Rejected: moving the long outcome sections into the ledger.** It would grow
the document with LESS headroom - 1.2 sessions against the roadmap's 2.0 - and
would mean authoring new ledger text for old items, which the append-only rule
exists to prevent. **Rejected: compressing prose.** The item's own measurement
says the OPEN sections are 27% of the document, so compression works the small
end of the problem.

**Criterion 3, one hop, and criterion 6, a test that the hop RESOLVES.** The
`## Archive index` section carries 65 stubs and the guard reports
`OK (65 archived heading(s), 65 stub link(s))`. `tests/test_archive_link_guard.py`
pins both directions with a positive control, a removed-stub negative control,
and a wrong-anchor negative control - because without the positive control a
reader that silently fell back to something permissive would pass green on the
exact tree that motivated this item.

**Criterion 4, nothing deleted and no ledger entry touched.** Verified against
`git HEAD` rather than against the planner that produced the split - a planner
asserting its own conservation is one witness. Every one of the 85 roadmap
chunks and 197 ledger chunks in HEAD was found verbatim in the live file plus
its archive, and the ledger's preamble through its insertion marker is
byte-identical, so `ops/loop/ledger.py` appends exactly where it always did.
The ledger cut is a contiguous TAIL, which is how criterion 4 is met
structurally rather than by an entry-by-entry judgement.

**Criterion 5, budgets re-derived after the split and LOWERED.** Against the
old numbers the split had bought 16.2 and 22.4 sessions of headroom, which is
precisely the rubber stamp this item warned about, so:

    ROADMAP.md      700,000 -> 340,000   5.1 sessions at the split, 4.5 at the commit
    docs/LEDGER.md  900,000 -> 420,000   5.0 sessions at the split, 4.5 at the commit

The two figures differ for the reason above: the budgets were set from the sizes
at the split, and the documents then grew by this session's own closure prose.
**Do not read the 4.5 as the budget being mis-set.** Ask the guard rather than
either number - `python tools/doc_size_budget.py` states headroom in sessions
and is the only figure that cannot go stale.

**The rates were deliberately NOT re-measured, and that is a decision rather
than an omission.** The merger slot left in `tools/doc_size_budget.py` asked
for a post-split re-measurement; there is exactly one post-split session, and a
slope through one point is not a measurement. The split reset the LEVEL, not
the SLOPE - new sections and entries land at the same pace whatever the file's
current size - so the pre-split rates remain the right planning figures. Both
budget comments now say that when the budget fires the answer is to RE-RUN the
split, not to move the number.

**Two defects the merge found that neither slice could see, and both are the
same shape.** Each slice was internally consistent and green.

1. **The splitter and the guard named DIFFERENT FILES.** The splitter defaulted
   to `docs/ROADMAP-ARCHIVE.md`, the guard to `docs/ROADMAP_ARCHIVE.md`. The
   adjudication that ran one against the other passed the path in EXPLICITLY,
   so the two defaults never met and it reported OK. Left alone it would have
   written the hyphen file and had the guard report DID NOT RUN against the
   underscore one - which reads as "no problems" while every archived item is
   unreachable through the name actually being checked. Fixed to the underscore
   form, which is the `docs/` convention (`OBSERVED_IDS.md`, `REPLY_PATHS.md`,
   `CLASS_RESEARCH.md`), and pinned by
   `TestTheSplitterAndTheGuardNameTheSAMEFile`.
2. **The split makes spent `OPS-` ids invisible to the allocator.** This is the
   `OPS-12` bug with a new way in. The obvious reasoning about it is wrong:
   archiving a roadmap section does NOT hide its id, because `spent_ids` matches
   any mention rather than only headings and every archived section leaves a
   stub naming its id. The LEDGER half leaves no stub, so an id discussed in an
   entry but never given a roadmap heading goes out with the tail. Measured on
   the real split before the fix: the spent set fell from 60 ids to 55, losing
   `OPS-1`, `OPS-3`, `OPS-4`, `OPS-5` and `OPS-9`. `next_free_id` was 61 both
   before and after, because it takes the MAXIMUM and the maximum was recent -
   so it was a live hole in `spent_ids`, whose docstring promises it "can only
   ever SKIP an id, never reissue one", and a dormant one in the allocator.
   `ops.ops_ids` now reads the archives by default. After the fix, 0 ids lost.

   **That 60-to-55 figure is NOT REPRODUCIBLE ANY MORE, and the reason is worth
   more than the number.** Re-measured after this closure was written, the spent
   set is 63 with the archives and 63 without. Writing down WHICH ids the split
   had made invisible put all five back into the live documents - this section
   names them, and so does `LL-0197`. The act of recording the measurement
   destroyed the condition it measured.

   So the archive read is currently DORMANT in `spent_ids` and LIVE in
   `over_allocated`, which is the one that would have gone on reporting a clean
   repository. Do not read a green `spent_ids` as evidence the archive read is
   unnecessary; it is evidence that this item's own prose is doing the work, and
   it will stop the moment this section is itself archived.

   **The first repair was applied to two readers out of five and the suite
   stayed green.** `spent_ids` and `next_free_id` learned about the archives;
   `roadmap_items`, `ledger_closures` and `over_allocated` did not, and
   `over_allocated` then returned `{}` for a repository carrying two known
   collisions. Changing WHERE a module reads from is a change to every reader in
   it, not to the ones whose tests happened to be red -
   `TestEveryDocumentReaderReadsTheArchives` now enumerates the public readers
   by signature so a sixth added later goes red on its own.

**What the parallel dispatch actually bought.** Three slices on disjoint file
sets, each writing its own tests and proving its own guards non-vacuous by
mutation. Every slice came back green, and BOTH defects above were found only
when the merger ran one slice's output through another slice's guard. Agreement
between two agents is not evidence; running one against the other is closer,
and even that passed until the DEFAULTS were compared rather than the
explicitly-passed arguments.

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

## OPS-61. Every hook command names an ABSOLUTE repo root, so a worktree's hook reports the WRONG TREE - CLOSED 2026-09-08

Filed 2026-09-08, measured while answering two inbox notes that asked every
adopter of the inbox-watcher design the same two questions. Our answers are
`TRACKED` and `IGNORED`, and the second question's YES is what made the defect
invisible.

**What was measured, in this order.**

1. `.claude/settings.json` is TRACKED - git index mode `100644`, committed. A
   fresh clone therefore HAS the `SessionStart` hook declaration, unlike the
   two siblings that raised the question.
2. `moon_sync_inbox/` is GITIGNORED - `.gitignore` line 196. A clone has no
   channel for the watcher to read.
3. A real `git clone` into a temp directory, running the CLONE'S OWN script,
   printed `moon_sync_inbox: CANNOT READ - <clone>\moon_sync_inbox does not
   exist. This is a FAILURE to look, NOT "nothing new".` and exited 0. So the
   "fires, fails and says nothing" failure the notes described does not apply
   here: the tool already distinguishes a failure to look from an empty inbox,
   and its exit code keeps it on the normal stdout path.

**The defect the two questions cannot reach.** The tracked command is an
absolute path:

    "command": "python C:/Lanternlight/ops/inbox_watch.py"

`ops/inbox_watch.py` resolves its repo root from its own file location, not
from the working directory - measured, invoked from an unrelated directory it
still reported the original tree's 99 notes. So in a clone at any other path,
and in every git WORKTREE, the hook does not run that tree's script at all. It
runs the original tree's, and answers a question about a different repository
without saying so.

That is worse than not firing. A hook that does not fire reports nothing; this
one FIRES, SUCCEEDS, and looks like coverage. Worktrees are the case that
bites, because that is where lane sessions run.

**Why no existing guard catches it, which is the part worth keeping.**
`tests/test_no_hardcoded_home_path.py` exists for exactly this class and does
not reach this instance. `OPS-38` generalised it once already - from this
machine's literal account name to the SHAPE of any user home directory under
any account - and stopped there. `C:/Lanternlight` carries no account name, so
it passes cleanly. A guard hardened against one value, then against one family
of values, is still scoped to a value; the property wanted is "no hook command
names a root the tree cannot verify is its own".

### Acceptance

1. The hook commands resolve the tree they are RUNNING IN. Whatever mechanism
   is chosen, it is demonstrated in a real clone at a different path and in a
   real `git worktree`, not reasoned about.
2. The demonstration is END-TO-END. Presence, registration and a green exit are
   three different facts and none of them is the fact that the hook read the
   right tree - that is `OPS-56`'s lesson and it applies here unchanged.
3. A guard fails when a tracked hook command names any absolute repository
   root, generalising past the single string `C:/Lanternlight` for the reason
   `OPS-38` had to generalise twice. It is proved non-vacuous by embedding a
   different absolute root and watching it go red.
4. If the answer is that the absolute path is unavoidable on this harness, that
   is written down as a DECLINE with the measurement behind it, and the claim
   "a fresh clone watches its own inbox" is corrected wherever it is published
   rather than left standing. Correcting the claim is an acceptable outcome;
   leaving a claim the wiring does not deliver is not.

### Outcome - CLOSED 2026-09-08

**Criterion 1, the mechanism, chosen by measurement rather than by reading a
document.** All six hook commands now reach their script through the harness
variable, with the path QUOTED:

    "command": "python \"$CLAUDE_PROJECT_DIR/ops/inbox_watch.py\""

Measured on Claude Code 2.1.251, in a real `git clone` at a foreign path and in
a real `git worktree`, with a probe hook that recorded `argv`, its own resolved
`__file__`, its `cwd` and the environment variable into a witness file per
event. Twelve witnesses, each read back independently by the merger rather than
accepted from the slice that produced them:

- **The harness expands the variable itself.** `argv[0]` arrived already
  expanded, so the mechanism does not depend on whether the hook is dispatched
  through `cmd.exe` or a POSIX shell. This is not a shell feature and does not
  need one.
- **It resolves to the RUNNING tree for all five events this repository
  registers** - `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`
  and `Stop`. Ten of the twelve witnesses are the worktree case, two per event.
- **The path is quoted because a clone can live under a path with a space.** At
  a spaced clone path the quoted form ran the clone's own script with the space
  intact in `argv[0]`; the unquoted form produced no witness at all.
  `C:/Lanternlight` has no space, so nothing in the primary tree would ever have
  exposed this.

**One overreach in the measurement slice's own document, corrected here rather
than carried.** It wrote that the unquoted form is "proven UNSAFE at a spaced
path (fails silently, all five ...)". One probe fired and the evidence is a
MISSING witness. Absence of a witness is not a captured failure, and one event
is not five. What is measured is enough to choose the quoted form and not enough
to describe how the unquoted form fails.

**The relative form works too, and was not chosen.** `python ops/inbox_watch.py`
resolved correctly for all five events, because the hook's `cwd` is the project
root. It is rejected as the primary mechanism for one reason: it makes the
command depend on a `cwd` this repository does not control, where the variable
form states the root explicitly. Recorded so nobody re-derives it as a
discovery.

**Criterion 2, END-TO-END with the real wiring, in both directions.** A probe
hook proves the mechanism; it does not prove this repository's own hooks. So the
committed `.claude/settings.json` was run in a real clone at a foreign path and
in a real worktree, in a real headless session, and the witness is the
FILESYSTEM rather than any report: `ops/inbox_watch.py` writes its records under
the tree it reads. Each tree was given a `moon_sync_inbox/` containing exactly
ONE note, so a report of 99 could only mean the primary tree.

    clone, fixed wiring      the clone's own ops/runtime/inbox_reported.json
                             lists the one probe note, inbox_seen.json
                             acknowledges it, and the PRIMARY tree's two records
                             are byte-identical to the pre-experiment snapshot
    worktree, fixed wiring   the same result in the worktree's own ops/runtime/
    worktree, PRE-FIX        the worktree's own records were NEVER WRITTEN, and
      wiring, the control    the PRIMARY tree's inbox_reported.json was
                             rewritten - mtime moved, 99 notes, the probe note
                             absent - as was inbox_seen.json. Both hashes
                             differed from the snapshot and both were restored
                             from it afterwards.

**The control is the part that upgrades this item's own description.** The filed
text said the hook "answers a question about a different repository". Measured,
it also WRITES that repository's state: a session in a worktree silently mutated
the primary checkout's acknowledged-mail record, which is the record that
decides whether a note is ever surfaced again. A wrong answer is recoverable by
looking again; an acknowledgement written into the wrong tree eats mail in a tree
nobody was working in.

**Criterion 3, the guard, generalised past one string.**
`tools/hook_command_guard.py` reports any hook command naming an absolute path in
three spellings - drive root, UNC and POSIX root - because no string can say
which absolute path was MEANT as a repository root, and `OPS-38` had to
generalise twice for exactly that reason. `tests/test_hook_command_roots.py`
carries a positive control on clean synthetic settings, foreign-root negative
controls, and the live-tree assertion. Proved non-vacuous by six mutations, each
with its anchor count asserted before the edit because a mutation that fails to
apply looks exactly like a passing test: neutering the drive-root pattern turned
the LIVE test green, which is precisely what the foreign-root controls exist to
catch. `main()` takes no argv and exits 2 on any argument rather than accepting
and ignoring one - the `OPS-64` defect, not repeated.

**THREE EXISTING GUARDS WERE GREEN BECAUSE OF THE DEFECT. This is the finding
worth keeping.** None of them was weakened; each was measuring a proxy that only
held while the commands named an absolute root.

1. `tests/test_no_hardcoded_home_path.py::test_every_hook_command_names_a_script_that_exists`
   split each command on whitespace and required every `.py` token to be a file
   on THIS machine. That can only pass while the token is an absolute literal
   path. It now resolves the token against the running tree, which is strictly
   stronger - the old form silently SKIPPED anything that did not look like a
   path to it, so a typo was clean - and it gained a fabricated-path control.
2. The same file's no-backslash assertion banned a backslash anywhere in the raw
   settings text. `CLAUDE.md`'s rule is narrower: a single-backslash WINDOWS PATH
   makes the file invalid JSON. Shell quoting needs `\"`, which cannot break a
   parse that is asserted on the line above. Narrowed to the path shape, with the
   cost of narrowing written into the docstring.
3. `tests/test_inbox_watch.py` ran the `SessionStart` command through
   `subprocess` and its own name said end-to-end. It was executing a command line
   that resolved the PRIMARY checkout no matter which tree the harness was in. It
   now expands the variable the way the harness does, through a helper whose
   docstring states plainly that expanding it in-process is a MODEL of the
   harness rather than the harness, and points at the out-of-process measurement
   for the real claim.

**The defect had already been OBSERVED, in a real worktree, and was misread.**
`lanes/safety.LEDGER.md` records that the registered hook points at
`C:/Lanternlight/tools/precommit_gate.py`, the PRIMARY checkout, not at the lane
worktree. That session measured this exact behaviour and read it as a
MERGE-TIMING fact - the fix is not live until the lane merges - rather than as a
PATH fact that would still be true after any merge. Nothing was filed, and the
observation sat in a lane fragment for weeks. A correct measurement filed under
the wrong cause is invisible to the search that would find it.

**Criterion 4 does not apply.** The absolute path was avoidable, so there is no
DECLINE to write and no published claim to correct. The claim that a fresh clone
watches its own inbox is now true, and its evidence is the clone experiment above
rather than a reading of the code.

**Not fixed here, and named rather than absorbed.** `.claude/commands/done.md`
tells the wrap to write `--target C:/Lanternlight/LL-NEXT-SESSION.txt`. That is
the same class one layer up - a session wrapping from a worktree would overwrite
the primary tree's hand-off - but it is a command a session TYPES rather than a
hook the harness dispatches, so `$CLAUDE_PROJECT_DIR` is not defined for it and
the fix is a different one. Filed as `OPS-65` rather than guessed at here.

## OPS-62. The two archives OPS-57 created are UNBUDGETED, and nothing measures their growth - CLOSED 2026-09-08

Filed 2026-09-08 out of `OPS-57`'s own cost list, where it is stated rather
than implied.

`OPS-57` split both continuity documents and re-derived the budgets for the two
LIVE files. `docs/ROADMAP_ARCHIVE.md` (475,473 blob bytes at the split) and
`docs/LEDGER_ARCHIVE.md` (586,771) have no budget at all, so the guard that
exists to notice unbounded growth is now blind to the two largest documents in
the repository.

**Why they were left unbudgeted rather than given a guessed number.** A budget
here is only meaningful next to a growth rate, and the archives do not grow the
way the live documents do: they gain nothing between splits and then take a
large step when one runs. There is exactly ONE data point. This repository omits
rather than guesses, and a budget with an invented rate beside it would be a
number that looks measured.

**Why it still matters.** The archives are where the live documents' growth
GOES. Re-running the split is now the documented response to a budget firing,
which means every future firing moves bytes into a file nothing watches. The
live budgets stay green forever while the repository grows without limit, and
the guard reports OK - the instrument reporting on itself again.

### Acceptance

1. A growth model for a step-wise document is chosen and named. Per-session
   bytes is the wrong shape; per-SPLIT bytes, or total repository bytes across
   the live document and its archive together, are two candidates and there may
   be better. State which and why.
2. It rests on at least two splits, or it says in writing that it rests on one
   and is provisional. One point is not a slope - `OPS-57` refused a
   re-measurement on that ground and this item does not get an exemption.
3. Whatever is chosen fails, non-vacuously, on a tree where an archive has
   grown past it. Proved by mutation, not by inspection.
4. The answer may legitimately be that archives are never budgeted and the
   guard measures the PAIR instead. If so, that is recorded as the decision
   with its cost, and `tools/doc_size_budget.py` says so where a reader looking
   for the missing archive budget will find it.

### Outcome - CLOSED 2026-09-08

**Criterion 1 and criterion 4 are answered together, because criterion 4's option
is what the measurement chose.** The archives are NOT budgeted individually, by
decision. The model is a PAIR TOTAL: `PAIR_BUDGETS` bounds each live document and
its archive together as one sum, `ROADMAP` at 1,180,000 and `LEDGER` at
1,270,000 blob bytes.

Three reasons, and the first is the hole this item was filed about:

- **A split cannot game a pair total.** Splitting moves bytes from the live half
  to the archive half and leaves the sum almost untouched. With only live
  budgets, the documented response to a firing - re-run `tools/doc_archive.py` -
  moves bytes into a file nothing watches and the guard reports OK forever. The
  sum measures the thing that actually grows, which is total continuity prose in
  the repository.
- **Its rate was already measured over six sessions, not over one split.** Before
  `OPS-57` the live document WAS the whole pair, because the archive did not
  exist, so the six per-session append rates in `SESSION_GROWTH_RATES` are pair
  rates as they stand. The pair model reuses them rather than declaring a second
  copy that could drift.
- **Both halves stay visible.** The report prints each half's own byte count
  beside the total, so a reader can see WHERE the bytes are even though only the
  sum is bounded.

**Criterion 2, and this is the term that is provisional.** The append half rests
on six sessions. The `split_overhead_bytes` term rests on ONE split and is
labelled provisional in three places in the code rather than only in a report: a
named section of the module docstring, `PairGrowthModel.splits_measured` and
`.provisional`, and the rendered output itself, which prints
`[model provisional: its split-overhead term rests on 1 split]` next to every
pair figure it qualifies. That is the written admission criterion 2 allows in
place of a second split, and it is in the artifact because a caveat stated only
in chat is a lie in the artifact.

The overhead is measured from history rather than estimated - across the split
commit, the ROADMAP pair went 633,871 to 669,327 (+35,456) and the LEDGER pair
867,833 to 881,945 (+14,112) - and is labelled an UPPER bound, because that
commit also carried the session's own prose. It is amortized over the derived
split interval and ADDED to the append rate, which SHORTENS reported headroom.
The conservative direction, the same reasoning that made `SESSION_GROWTH_RATES`
use the high median rather than the mean.

**The 12-session horizon is a judgement and says so; the rate under it is
measured.** That distinction is the whole of criterion 1: "per-session bytes is
the wrong shape" was the item's complaint, and the answer is a measured rate for
the half that appends every session plus a labelled-provisional term for the half
that steps.

**Criterion 3, non-vacuity, eight mutations plus a direct grown-archive tree.**
Counting the pair as the live half only killed 8 tests; weakening the comparison
killed 4; dropping the overhead term from the effective rate killed 2; silently
skipping a missing half killed 2; lowering the pair threshold to the per-document
one killed 1; deleting the `LEDGER_ARCHIVE` decision note killed 3; never
rendering the provisional caveat killed 1; and lowering the real ROADMAP pair
budget below the live total killed 2 while the module exited 1 and the
PER-DOCUMENT channel still said OK - which is exactly the blindness this item
described. A synthetic tree with a 1,000,000-byte archive beside a 200,000-byte
live document, measured against the REAL budget, passed the live channel and
failed the pair channel at -0.5 sessions.

**Re-verified by the merger in-process rather than accepted from the slice.**
`check_pair_budgets()` on the live tree returns ok with zero findings; tightening
`ROADMAP` to 700,000 - 2,038 bytes under the measured 702,038 - returns not-ok
with one `pair_over_budget` finding naming both halves and the total. The guard
refuses a real over-budget tree, which is the claim, and it was not taken on
trust.

**THE COST, and one part of it needs the operator rather than a session.** Two
things, both written into the module where a reader will meet them:

1. No individual archive is bounded, so an archive growing on its own - somebody
   appending to it directly rather than through a split - consumes pair headroom
   indistinguishably from ordinary growth in the live half. The per-half
   components in the report are the only mitigation and nothing guards it.
2. **A pair-budget firing has NO mechanical remedy.** A live-budget firing is
   answered by re-running the splitter; a pair firing cannot be, because the pair
   total is precisely what a split does not change. The only answers are a real
   reduction in content - which this repository's own rules forbid for the
   ledger, where an entry is written in full for a cold session - or an operator
   ruling: move the archives out of this repository, or accept a higher bound. So
   a pair firing is a DECISION GATE FOR THE OPERATOR rather than a chore, which
   is why `PAIR_LOW_HEADROOM_SESSIONS` warns further out than the per-document
   threshold does. **Nobody should silently raise a pair budget when it fires.**

**What it reported at TWO instants, and the difference is the point rather than
an error.** A size with no instant attached is a filed count that cannot
reproduce - `LL-0201` is that lesson, learned by this item's neighbour `OPS-57`
one item over - so both readings are here:

    at the merge, before this outcome was written
      ROADMAP pair   702,038  (ROADMAP.md 226,565 + archive 475,473)   11.9 sessions
      LEDGER pair    901,698  (docs/LEDGER.md 314,927 + archive 586,771)  12.0 sessions

    after this outcome was written into ROADMAP.md
      ROADMAP pair   711,879  (ROADMAP.md 236,406 + archive 475,473)   11.6 sessions
      LEDGER pair    901,698  unchanged, nothing was appended to it yet

Writing the closure moved the number the closure quotes - `LL-0199`'s shape, and
the third time this session that recording a measurement changed the thing
measured. **Ask `python tools/doc_size_budget.py` rather than quoting any of
these six figures.**
`tests/test_doc_size_budget.py` went 29 tests to 65 and every one of the original
29 still passes unchanged.

## OPS-63. The source register never reads `ROADMAP.md`, and the OPS-57 split made that visible rather than new - CLOSED 2026-09-08

Filed 2026-09-08, out of `OPS-57`'s merge. Not caused by the split - the split
walked into it.

`tests/test_source_register.py` guards that every external source cited in this
project's documents is registered in `docs/ECOSYSTEM.md` with its provenance,
tier and basis. It reads `docs/**/*.md` and nothing else. Its own module
docstring says so and names `README.md` as an example of a file it does not
cover. `ROADMAP.md` lives at the repository ROOT, so it has never been read
either, and neither has `CLAUDE.md`, `BACKLOG.md` or `LL-NEXT-SESSION.txt`.

**How it surfaced.** `OPS-57` moved 475,473 bytes of closed roadmap sections
into `docs/ROADMAP_ARCHIVE.md`, and 57 previously-unread tokens landed in
scope at once. All 57 were checked by hand and all 57 are false positives -
Python attributes, our own filenames, toy names from worked examples, and two
host-shaped fragments (`x.com`, `t.co`) that appear inside a passage about a
SUBSTRING-matching defect, quoted as the pieces hiding inside
`gamingpromax.com` and `grindnstrat.com`. So no real source was found, and none
was hidden by excluding the archive again.

**Why the archive was excluded rather than absorbed.** Archiving a document
must not silently change which guards apply to it: the words did not change,
only their path did. The alternative was 57 entries in `KNOWN_NON_HOSTS`, which
that module's own docstring calls the one place a real source can hide.

**What is actually wrong, and it predates the split by weeks.** A real source
cited in `ROADMAP.md` is invisible to the register guard today, was invisible
yesterday, and this item exists so that fact is written down somewhere a cold
session will find it rather than living only in a constant's comment.

### Acceptance

1. The scan's scope is decided deliberately and stated: either it covers every
   tracked Markdown document in the repository, or the set it covers is
   enumerated with a reason per exclusion. "It happens to read `docs/`" is not
   a scope.
2. If the scope widens to `ROADMAP.md`, the false positives it brings are
   counted BEFORE the change and reported, because that count is the real cost
   and the last measurement of it was 57 for a document three times smaller.
3. The extractor's false-positive rate is addressed rather than absorbed. Every
   token added to `KNOWN_NON_HOSTS` in this item's course is a truncation the
   host-shaped pattern makes at an underscore - `ARCHIVE.md` from
   `ROADMAP_ARCHIVE.md`, `ids.default` from `ops_ids.default_archive_paths`.
   A pattern that stopped truncating at underscores would remove a whole class
   of them. Measure how many of the existing entries that would retire; if the
   answer is most of them, the denylist is treating a pattern defect.

   **A sub-case found 2026-09-08 during `OPS-61`, which the count above must
   include.** `reported.json` is the underscore truncation of
   `inbox_reported.json`, a RUNTIME record under gitignored `ops/runtime/`.
   `is_repo_filename` asks `git ls-files`, so a file this project legitimately
   writes prose about but deliberately does not track can NEVER be
   auto-excused: it lands in the denylist by construction, not by anyone's
   oversight, and the "stage it and re-run" escape that retired `ARCHIVE.md`
   does not apply because the whole point of the file is that it is not
   committed. Any answer to this item has to say what happens to the names of
   untracked-by-design files, which this project writes about constantly.
4. The guard is proved non-vacuous against the widened scope: a fabricated
   unregistered host is placed in a newly-covered file, the guard goes red, and
   it is removed. A scope that widens without a control is a scope that might
   not have widened at all.

### Outcome - CLOSED 2026-09-08

**Criterion 2 first, because it asked for a count taken BEFORE the change.**
Measured with the scan unchanged, per document, counting host-shaped tokens that
would redden the guard:

    ROADMAP.md 8   CLAUDE.md 12   WAKEUP_NOTES.md 4   README.md 2
    LL-NEXT-SESSION.txt 4   CONTRIBUTING.md 3   CODE_OF_CONDUCT.md 2
    SECURITY.md 1   BACKLOG.md 0   .github/PULL_REQUEST_TEMPLATE.md 0
    the four lane ledgers 0 each   .claude/** 23 across 13 files
    UNION 52

Confirmed live afterwards rather than left as an estimate: with the scope widened
and the denylist untouched the guard reported `1 failed, 12 passed` and named
exactly 52 tokens. The last measurement of this cost was 57 for `docs/` alone, so
52 for everything else is the same order and the item's expectation was right.

**FOUR OF THE 52 ARE REAL HOSTS AND TWO WERE UNREGISTERED, which is the payoff
and it is not a formality.** `docs.github.com`, cited by `CODE_OF_CONDUCT.md` and
`SECURITY.md` for GitHub's abuse-reporting and private-vulnerability-reporting
instructions, and `contributor-covenant.org`, cited as attribution in
`CODE_OF_CONDUCT.md`. Both were invisible to the register for as long as those
documents have existed, which is since `LL-0200` two days ago. Both now carry a
row in `docs/ECOSYSTEM.md` saying REPOSITORY GOVERNANCE ONLY, never evidence
about this game - the distinction the register exists to keep. The other two,
`x.com` and `t.co`, are the fragments the `OPS-57` passage quotes as the pieces
hiding inside two launch-window wiki hosts; they are registered rather than
denylisted, because a real host must never hide in `KNOWN_NON_HOSTS`, and their
row says plainly that nobody has fetched either.

**Criterion 1, the scope, stated instead of inherited.** Every tracked `*.md` and
`*.txt` in the repository, plus the original `docs/**/*.md` walk kept verbatim so
the new rule is a strict SUPERSET and no coverage was traded for coverage. One
enumerated exclusion with its reason: `docs/ROADMAP_ARCHIVE.md`, whose 57
previously-unread tokens were checked by hand under `OPS-57` and were all false
positives; a document must not gain guards by being archived any more than it
loses them.

- **Rejected: "everything except `.claude/**`",** which would have cost 29 tokens
  instead of 52. It requires storing a directory list in this file, and a
  committed list of paths goes stale the moment one is added - the same doctrine
  that made `tracked_paths` ask `git` on every run rather than carry a list.
- **Code is deliberately out of scope**, stated rather than left as an accident
  of the glob. A host in a `.py` file is nearly always a test fixture or a
  pattern, and the register is about what this project CITES.

**Criterion 3 is REFUTED, with numbers, and that is a real result rather than a
failure to deliver.** The item's hypothesis was that a pattern which stopped
truncating at underscores would retire a whole class of denylist entries, and
that if it retired most of them the denylist was treating a pattern defect.
Measured against the pre-widening denylist:

    retires 45 of 266 load-bearing entries   16.9%, not most
    introduces 52 brand-new red tokens       net 267 -> 274, WORSE

Zero of the 52 long forms are covered by `is_repo_filename`, because `OPS-44`
already harvested that win when it started asking `git ls-files` at test time.
So the underscore truncation is not the denylist's cause; it is a cosmetic detail
of tokens that would need vetting either way.

**And the sub-case this item recorded from `OPS-61` behaves differently than the
hypothesis predicted.** `reported.json` does not retire - it is RENAMED to
`inbox_reported.json` and still needs an entry, because the file is a runtime
record under gitignored `ops/runtime/` and `is_repo_filename` asks `git ls-files`.
Names of untracked-by-design files land in the denylist by construction. The
alternative, resolving tokens against `.gitignore`, is `LL-0079`'s
auto-exemption failure with a new input.

**Also measured and rejected: skipping fenced code blocks.** It would cut the new
tokens from 52 to 34 at zero coverage cost measured TODAY, and it buys that by
never reading a region of every document again. An unbounded, unreviewed blind
spot is the wrong trade for 18 tokens, and this project has already been bitten
by a source hiding in a region a guard had stopped reading.

**What it cost, stated rather than implied.** `KNOWN_NON_HOSTS` grew from 267 to
**317** at the commit that closed this item, and to 319 by the end of the session
as three more closure-prose tokens landed. It is the set's largest single
addition, and that set is the one place this module's own
docstring says a real source can hide. Every added token was looked at; the
merger re-read the additions and they are dotted code identifiers, our own
filenames, and two Windows program names. The cost is real and it is the price of
reading the documents where this project actually writes.

**Criterion 4, non-vacuity against the NEW scope, proved by four mutations with
each anchor asserted before the edit.** A fabricated host planted in
`.github/PULL_REQUEST_TEMPLATE.md` produced `1 failed, 15 passed` naming that
file; the same in `LL-NEXT-SESSION.txt` did likewise - both documents the old
scan never read. Narrowing `SCAN_SUFFIXES` back to `("md",)` produced
`2 failed, 14 passed`, and an empty tracked listing also `2 failed, 14 passed`,
so the guard still gets NOISIER when its input disappears rather than quieter.

## OPS-64. `tools/archive_link_guard.py` accepts any argv and silently ignores it - CLOSED 2026-09-08

Filed 2026-09-08 by the wrap's own refutation pass, which hit it while trying to
break the guard: it passed flags naming scratch files, and `main()` printed an
identical green line having read the REAL documents. The verdict was true and
was an answer to a different question than the one asked.

`main()` takes no arguments and calls `check_repo()` on the live paths. There is
no `argparse`, so an unknown flag is not rejected - it is not seen at all.

**Why this is worth an item rather than a shrug.** The whole point of that guard
is to refuse to say OK about something it did not check, and it already does the
hard half of that well: a missing archive reports DID NOT RUN rather than
passing. This is the same failure at the other end - a caller who believes they
scoped the check somewhere gets a confident verdict about somewhere else. It is
the shape this repository keeps meeting, most recently in the pre-commit hook
that ran the wrong test module and reported that the guard had run.

Compare `tools/doc_archive.py`, which does use `argparse` and would reject the
same flag. The inconsistency is the tell.

### Acceptance

1. `main()` rejects an argument it does not understand, with a non-zero exit and
   a message naming the argument. Proved by invoking it with a made-up flag.
2. If it grows real options - pointing the check at a different roadmap or
   archive - they are REAL, in the sense that passing them changes what is read.
   A flag that is accepted and ignored is worse than one that is refused.
3. A test invokes `main()` with a bad argument and asserts the refusal. It is
   proved non-vacuous by removing the rejection and watching the test go red.
4. The other entry points in `tools/` are swept for the same defect and the
   result is reported as a COUNT of modules checked, not as "none found" - an
   empty sweep is a claim about the sweep. `tools/precommit_gate.py`,
   `tools/doc_size_budget.py` and `tools/syntax_check_hook.py` are the obvious
   neighbours.

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

## OPS-65. The wrap ritual writes the hand-off to an ABSOLUTE target, so a wrap from a worktree overwrites the primary tree's hand-off - CLOSED 2026-09-08

Filed 2026-09-08 out of `OPS-61`'s merge. `OPS-61` fixed every command the
HARNESS dispatches; this is the same defect in a command a SESSION types, and it
is not fixed by the same mechanism.

`.claude/commands/done.md` instructs the wrap to run:

    python ops/handoff.py --from-file <draft> --target C:/Lanternlight/LL-NEXT-SESSION.txt

`LL-NEXT-SESSION.txt` is TRACKED and is the first file a cold session reads, so
the target matters more than most. A session wrapping from a git worktree - which
is where lane sessions run - writes the PRIMARY checkout's hand-off, and
`ops/handoff.py` will do it without complaint because the path exists and is
writable. The primary tree then carries a hand-off describing work that is not in
it, and `git status` in the primary shows a modified tracked file that nobody
working there touched.

**Why `OPS-61`'s answer does not transfer.** `$CLAUDE_PROJECT_DIR` is set by the
harness for HOOK dispatch. It is not defined for a command a session or the
operator types into a shell, so pasting the variable into `done.md` would produce
a literal directory named `$CLAUDE_PROJECT_DIR` on Windows, or an empty path, and
either way `--target` would land somewhere nobody looks. Measured for hooks, NOT
measured for typed commands - and the difference is the whole item.

**Why it was not simply fixed during `OPS-61`.** Three candidate answers exist -
make `--target` default to the repository root `ops/handoff.py` resolves from its
own location and drop the flag from the ritual; keep the flag but reject a target
outside the tree the script lives in; or leave it absolute deliberately because
the hand-off belongs to the primary checkout by design and a lane wrap should
NOT write one. The third is a real possibility and it is a decision about the
wrap's contract, not a typo. Guessing between them inside another item's merge is
how a fix becomes a surprise.

### Acceptance

1. The decision is stated: does a wrap from a non-primary tree write that tree's
   hand-off, refuse, or write the primary's on purpose? Whichever it is, the
   reason is written down, because all three are defensible and only one is true
   of the ritual as it stands.
2. The demonstration is END-TO-END in a real worktree, the way `OPS-61`'s was:
   run the wrap's own command from a worktree and read which file changed on
   disk. `ops/handoff.py --check-only` reports without writing and is the safe
   half; the writing half is the one that has to be observed.
3. A guard fails on a tracked instruction naming an absolute repository root in a
   `--target`-shaped position, or the decision in 1 says absolute is correct and
   the guard pins THAT instead. `tools/hook_command_guard.py` reads
   `.claude/settings.json` only, so it does not reach `.claude/commands/*.md`;
   widening it is one option and a separate check is another.
4. Whatever is chosen, `python ops/handoff.py --from-file <draft> --target ...`
   as written in `.claude/commands/done.md`, in `CLAUDE.md`'s wrap guidance and
   in `LL-NEXT-SESSION.txt`'s own hand-off instructions agree with it. Three
   copies of an instruction are two stale copies waiting to happen, and this
   session found the third copy only by grepping for the absolute root.

### Outcome - CLOSED 2026-09-08

**Criterion 1, the decision: (a). A wrap writes the hand-off of THE TREE IT IS
WRAPPING, by OMITTING `--target`.** `ops/handoff.py` resolves `DEFAULT_TARGET`
from its own file location, so a worktree's wrap writes that worktree's
hand-off. The flag stays supported for a caller that genuinely means another
path; the RITUAL no longer passes it.

**Criterion 2, end-to-end in two real detached worktrees, reading which file
changed on disk rather than reasoning about it.** From `wt_lane`:

    ritual form, --target <wt_primary>/LL-NEXT-SESSION.txt
        exit 0, SILENT. wt_primary's hand-off CHANGED, wt_lane's did not,
        and git status in wt_lane stayed CLEAN
    flagless
        wt_lane's own hand-off changed, wt_primary untouched,
        git add LL-NEXT-SESSION.txt exit 0
    --check-only against the primary's real path
        reported clean and wrote nothing

**(c) IS REFUTED BY THE RITUAL'S OWN STEP 9, which is why this is a decision
rather than a preference.** `.claude/commands/done.md` requires the hand-off be
"rewritten in place, staged, and committed with the session's other work". The
absolute form cannot do that from a worktree: `git add` of a path belonging to
another worktree exits 128, `fatal: ... is outside repository`. So the reading
that the hand-off belongs to the primary checkout on purpose contradicts a
requirement already written into the ritual - measured, not argued.

**(b) was rejected as a REFUSAL and kept as a REPORT.** Refusing any target
outside the resolving tree would need an exemption for the test suite's own
`tmp_path` targets, and an exemption list is exactly what `OPS-32` forbade for
this writer - "there is no exemption list and no override flag". So an
out-of-tree target now prints a stderr report naming itself as out-of-tree and
still writes, which keeps the writer honest without giving it a bypass.

**Criterion 3, the guard.** `tests/test_handoff.py` grew a detector over the
tracked instruction corpus - the documents that TELL a session what to run - and
it fails on any absolute root passed to a `--target`-shaped flag. It reuses
`tools/hook_command_guard.py`'s engine rather than declaring a second pattern,
which is pinned by its own test: two independent absolute-path detectors would
drift, and `OPS-38` needed two generalisations because a guard scoped to one
value stays scoped to one value.

**Criterion 4, the three copies made to agree.** `.claude/commands/done.md`
line 84 and `LL-NEXT-SESSION.txt` line 200 both carried the absolute form; both
are corrected, the second by REGENERATING the hand-off through
`ops/handoff.py`, because that file must never be written with an editor tool -
`OPS-32`. `CLAUDE.md` carries no `--target` line, so there were three sites and
not four. The prose mentions of the path at `done.md` lines 77 and 183 are
deliberately KEPT: they say where the hand-off lives, which is still true, and
`tests/test_loop_watch.py::TestTheWrapOutputShapeIsPinned` requires them.

**A vacuous test was exposed by mutation and replaced.** Hardcoding the default
target killed two tests but did NOT kill
`test_the_default_target_follows_the_tree` - because in the primary checkout the
hardcoded value and the resolved value are the same string, so the test could
not tell them apart in the tree it runs in. It now loads the module from a copy
inside a temporary tree, where the two answers differ, and the same mutation
kills it. That is the `OPS-61` lesson again in a new place: a guard measured only
in the primary tree cannot see a defect that only appears elsewhere.

**The slice also refuted its own first driver.** Its initial mutation harness
reported per-run summary lines that hid swapped identities between the before and
after runs, so a mutation could appear to kill the wrong test. Rebuilt per-test
before believing any of the eleven results.

`tests/test_handoff.py` went **26 tests to 37**, with 243 lines added and 0
removed. The 243/0 half was correct as filed; the two test counts were not, and
neither 28 nor 36 reproduces at any commit this session under either metric -
collected tests or `def test_` count, which agree with each other. Corrected by
the wrap's refutation pass, which re-derived them per commit rather than reading
the slice's report.

## OPS-66. `tools/precommit_gate.py` read an unknown argument as a PASS, so a typo in `.githooks/pre-commit` would switch the lint gate off silently - CLOSED 2026-09-08

Filed and closed 2026-09-08, out of `OPS-64`'s criterion-4 sweep. Filed rather
than folded into that item because it is a FAIL-OPEN in a safety gate and belongs
where someone searching for one will find it.

**What was measured before the fix.** The `__main__` block recognised only
`lint-staged` and `--lint-staged` as `argv[1]`. Anything else fell through to the
PreToolUse path, which read stdin, found no JSON, and returned 0.

    python tools/precommit_gate.py --lintstaged   exit 0, no output
    python tools/precommit_gate.py lint-staged    exit 0 on a clean repository

Those two are INDISTINGUISHABLE by the only thing a git hook reads. And
`.githooks/pre-commit` invokes the module as
`"$lint_py" "$repo_top/tools/precommit_gate.py" lint-staged`, so a one-character
slip in that line - the kind a reflow or a rename makes - would have turned the
lint gate off while reporting success on every commit thereafter.

**The shape, because it is the third instance in three sessions.** A true verdict
answering a different question than the one asked. `OPS-56` was the pre-commit
hook that ran the WRONG test module and reported that the guard had run. `OPS-64`
was the archive link guard printing an identical green line having read the real
documents while flags named scratch ones. This is the same defect in the one place
where the failure direction is a permitted commit.

### Acceptance

1. An argument this module does not understand exits non-zero and says which
   argument it was. Both entry points that DO exist keep working: no argv at all
   for the PreToolUse hook, and the lint entry point under both spellings.
2. Proved non-vacuous by mutation - remove the refusal, watch the guard-tests go
   red, restore.
3. The end-to-end exit code is measured in a real process, not inferred from a
   function's return value, because the exit code IS the verdict.

### Outcome - CLOSED 2026-09-08

`dispatch(argv)` is a new named function and `__main__` is now three lines around
it. Two contracts, spelled out - empty argv is the PreToolUse stdin path, the lint
spellings are the git-hook helper - and everything else returns
`USAGE_EXIT_CODE = 2`. Two is chosen because it refuses on BOTH of this file's
contracts at once: a PreToolUse hook blocks on exactly 2, and git reads any
non-zero exit from a hook helper as a refusal. One code, both callers, no branch
that could pick wrongly. `lint-staged` followed by junk is refused as well; it was
previously accepted with the junk ignored.

**Deliberately NOT argparse, where `OPS-64` chose argparse one file over.** That
guard grew real options and needed a parser. This module's exit codes ARE its
verdicts, and adding a parser would put an argparse `SystemExit` and a `--help`
path inside that. Two contracts do not need a parser; they need to be named.

**The refusal survives the soft-fail on purpose.** `__main__` still returns 0 on an
unexpected EXCEPTION, because a crashing gate that blocks every command is worse
than no gate - `OPS-15`. A usage error is a RETURN VALUE, not an exception, so it
passes through that handler untouched. This was checked rather than assumed.

**TDD, and the failing step is worth recording.** Six tests were written first and
observed red at `4 failed, 63 passed`; two of the six - both spellings still
dispatch, and no-argv still reaches the stdin path - were GREEN from the start,
which is what makes them positive controls: without them, refusing EVERYTHING
would have passed.

After the fix, `102 passed` across `tests/test_precommit_gate_lint.py` and
`tests/test_precommit_gate.py`.

**Criterion 2, and the mutation attempt that failed first, which is the part worth
keeping.** The first mutation DID NOT APPLY - the anchor did not match - and the
suite then printed `67 passed`. Read without the anchor assertion, that green is
exactly the false comfort `CLAUDE.md` warns about: it looks like a mutation that
killed nothing. The assertion fired and said so. The line endings were checked and
ruled out as the cause; the anchor was rebuilt programmatically and verified to
match once before being used.

The mutation that did apply was chosen to be informative: it left the `_say`
message in place and changed only the return, so the gate still PRINTS its refusal
while no longer refusing. That killed exactly three tests - `3 failed, 64 passed` -
and left the trailing-extra-argument test green, because that is a separate branch.
Two tests guarding independent halves, which is the same result the `OPS-15` work
recorded for `_block`. Restored from a pristine copy and verified sha256-identical
rather than by `git checkout`, because the tree carried other slices' uncommitted
work.

## OPS-67. Four `tools/` entry points still read an unknown argument as a pass, and the four are not one decision - CLOSED 2026-09-08

Filed 2026-09-08 out of `OPS-64`'s criterion-4 sweep, and re-probed by the merger:
`tools/ascii_check.py`, `tools/syntax_check_hook.py`, `tools/probe_paks.py` and
`tools/doc_size_budget.py` each exit 0 on an unknown flag. `OPS-64` fixed
`archive_link_guard.py` and `OPS-66` fixed `precommit_gate.py`; these four are
what is left of the nine.

**Why they are filed together and answered separately.** The stakes differ, and one
uniform change would be a guess dressed as consistency:

- `ascii_check.py` and `syntax_check_hook.py` are `PostToolUse` hooks. The wiring
  in `.claude/settings.json` passes them NO arguments, and both exit 0 on every
  path by design because a `PostToolUse` hook that exits non-zero breaks the
  session it runs in. An unknown argv is not reachable from the only caller they
  have, so the fix may be worth nothing here and the honest answer may be a
  comment saying so.
- `doc_size_budget.py` is the one that worries. Its numbers get QUOTED - this
  repository's own hand-off tells the next session to ask it for headroom in
  sessions rather than repeat a byte figure - so a caller who believed they had
  scoped it at a scratch document and got a confident verdict about the live ones
  is the `OPS-64` failure exactly. It also writes real git objects via
  `git hash-object -w`, which is why `OPS-8`'s concurrency question keeps
  resurfacing around it.
- `probe_paks.py` is an analysis script whose output nobody gates on. It is
  probably the cheapest to fix and the least valuable.

### Acceptance

1. Each of the four gets a decision, not a batch: refuse unknown argv, grow real
   options, or document why argv can never reach it. A file whose only caller
   passes no arguments may legitimately keep its current behaviour, and if so the
   REASON is written in the module.
2. `doc_size_budget.py` is treated as the load-bearing one. If it grows options
   they are real, in the sense that passing them changes which documents are
   measured, and that is proved by pointing it at a scratch pair and watching the
   numbers change.
3. Whatever changes is proved non-vacuous by mutation, and whatever does not
   changes carries a test pinning the current behaviour so a later reader cannot
   mistake an unexamined default for a decision.
4. The count is restated at the end: how many `tools/` entry points exist, how
   many refuse, how many accept real options, and how many are documented as
   argv-unreachable. The sweep in `OPS-64` said nine; re-derive it rather than
   quoting it, because a filed count is a hypothesis.

### Outcome - CLOSED 2026-09-08

**Criterion 1, four decisions and they differ, which is the whole point of the
item.** Each reason is written in the module it governs, not here:

1. **`tools/ascii_check.py` - NO CHANGE, argv ignored on purpose.** Its only
   caller is the `PostToolUse` wiring, which passes no arguments; its subject
   arrives on stdin; and a non-zero exit from a `PostToolUse` hook breaks the
   session it runs in. Adding argparse would import a SECOND exit channel into a
   module that is deliberately fail-soft. Recorded in the docstring under a
   heading a reader will find - `ARGV IS NOT A CONTRACT HERE, AND THAT IS A
   DECISION`.
2. **`tools/syntax_check_hook.py` - NO CHANGE, same reason plus one of its
   own.** Its `finally: os._exit(0)` is the single decider of this process's
   exit status, and an argparse `SystemExit(2)` would be a second decider inside
   a module whose whole design is that exactly one thing decides.
3. **`tools/probe_paks.py` - CHANGED, because it has no automated caller at
   all.** It is typed by a person and nothing reads its exit code that a
   non-zero could break, so refusing costs nothing. Unknown argv now returns
   `USAGE_EXIT_CODE = 2` quoting the argument back. No argparse and no invented
   options: it has no scope to take.
4. **`tools/doc_size_budget.py` - CHANGED, argparse, and it is the load-bearing
   one.** Its numbers get QUOTED, including by this repository's own hand-off,
   so it needs a real way to be scoped; and its exit codes are a verdict channel
   that a usage error must not borrow. `--repo-root`, `allow_abbrev=False`,
   `USAGE_EXIT_CODE = 2`, and `SystemExit` caught and returned so `main` always
   returns an int.

**Criterion 2, the options are REAL, measured against a scratch pair rather than
inspected.** Default run: `ROADMAP.md 236,909`, `docs/LEDGER.md 322,447`, pairs
712,382 and 909,218. Same command with `--repo-root <scratch>`: 16 and 15, pairs
40 and 38, exit 0. Against an EMPTY directory: exit 1 with six missing-path
Findings, because a missing document stays a Finding and never becomes a silent
pass. `--repo-roo` exits 2 rather than being accepted as an abbreviation.

**One option, scoping BOTH channels, and the reason is this item one level up.**
`--repo-root` moves the per-document channel and the `OPS-62` pair channel
together. No `--documents-only` or `--pairs-only`, because a run that measures
one channel and prints one confident OK line is precisely the defect `OPS-64`
and this item exist to remove. Also refused: a `--budget` override, which is
"raise the budget to go green" with a command-line spelling.

**What `--repo-root` does NOT move, written into the docstring because it would
otherwise be a trap.** It moves only where the watched paths resolve, never
git's working directory, so blobs are always hashed into THIS repository's
object database. A non-git root works; a git failure propagates loudly instead
of returning a zero that would read as a very small document.

**Criterion 3, non-vacuity, proved both ways.** For what changed: seven
mutations on the budget module - `allow_abbrev=True`, ignoring `--repo-root` in
the document channel, ignoring it in the pair channel only, `parse_known_args`,
a silent pass on a missing path, `argv=None` ignoring `sys.argv`, and dropping
the root from the scope line - killing 1, 3, 2, 5, 4, 1 and 1 tests
respectively. On the probe: pinning against `HEAD`'s copy gave 5 failed of 6,
deleting the scope line killed 1, and refusing in WORDS while continuing to run
killed 2.

**For what deliberately did NOT change, the pin is non-vacuous too**, which is
the half criterion 3 asks for and the half that is usually skipped: making
`ascii_check.py` refuse argv turned 2 tests red, making the syntax hook
`os._exit(2)` on argv turned 1 red, and deleting the decision sentence turned 1
red PER DOCSTRING - two mutations of one test each, not one mutation of two,
which is how the slice's report read and is corrected here. So the decision is
held by tests rather than by
an unexamined default. The premise underneath it - that the wiring passes no
arguments - is pinned against a SCRATCH copy of `.claude/settings.json`:
appending an argument to a hook command turns it red, and unwiring the hook
turns it red.

**Criterion 4, the count, RE-DERIVED by the merger rather than quoted from the
sweep that filed this item.** Nine modules in `tools/` carry a `__main__` block,
each invoked here with an unknown flag:

    refuse, exit 2   probe_paks, doc_size_budget, archive_link_guard,
                     doc_archive, frame_poller, hook_command_guard,
                     precommit_gate                                    7 of 9
    ignore argv,     ascii_check, syntax_check_hook                    2 of 9
      exit 0, BY DECISION, reason in the module, pinned by a test

Nine was also the sweep's figure, so this is one filed count that reproduced.
The two remaining zeros are the answer rather than an omission: they are the
only two entry points whose caller is a hook that a non-zero exit would break.

`tests/test_doc_size_budget.py` went 65 to 76, `tests/test_syntax_check_hook.py`
34 to 41, and `tests/test_probe_paks.py` is new at 6 - the pak probe had no test
module before this item, so it shipped unpinned. It is owned by the capture lane
beside the tool it pins.

## OPS-68. The operator directed a RESPONDER RUNNER and cross-project propagation, then put both decisions on STANDBY - OPEN, operator-held 2026-09-08

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

## OPS-69. `docs/INVENTORY.md` is guarded in ONE direction, so a module missing from it is invisible - CLOSED 2026-09-10

Filed 2026-09-08 at the wrap, found while syncing the living docs after `OPS-61`
and `OPS-67` added two test modules and one tool.

`tests/test_inventory.py` holds four properties and every one of them runs the
same way: it takes something the DOCUMENT names and asks whether it exists. Every
backtick-quoted path must be a real file; every command in the commands table
must exist; every agent in the agents table must exist; the declared directories
must exist. Nothing anywhere asks the opposite question - whether something that
exists is NAMED.

**So the document cannot be caught being incomplete.** `tools/hook_command_guard.py`,
`tests/test_hook_command_roots.py` and `tests/test_probe_paks.py` were all
created this session and the inventory guard stayed green with none of them
listed. They were added by hand at the wrap because a human noticed, which is
exactly the mechanism this project does not rely on anywhere else.

**Why it matters more here than it would in an ordinary doc.** This file is
Lanternlight's OUTBOUND half of the cross-project inventory exchange the operator
authorised in chat 2026-09-07. A sibling reading it is reading a claim about what
this project has. An inventory that is silently short does not read as short - it
reads as complete, which is the failure mode of every one-direction guard this
repository has met: `OPS-57`'s archive index needed BOTH directions for the same
reason, and got them.

**The tension that makes this an item rather than a chore.** The document's own
preamble says NO STALE COUNTS - it deliberately names no test count, because a
number written there rots the moment a test is added. A completeness check is the
same rot in a different spelling if it is written as a number, so the answer has
to be a derived comparison rather than a filed total, and it has to say what is
deliberately EXCLUDED without that exclusion list becoming the place a module
hides. `tests/test_source_register.py`'s `KNOWN_NON_HOSTS` is the cautionary
example: its own docstring calls it the one place a real source can hide, and it
has grown by four entries in this session alone.

### Acceptance

1. A test fails when a tracked module that the document's own scope covers is
   absent from it. The scope is stated rather than assumed - "every tracked
   `tests/test_*.py` and `tools/*.py`" is a scope; "the important ones" is not.
2. Whatever is excluded is enumerated WITH A REASON PER EXCLUSION, in the module,
   and the exclusion list is small enough to read. If it grows past a dozen the
   scope was wrong, not the list.
3. Proved non-vacuous by mutation: delete a row from `docs/INVENTORY.md` and
   watch the test go red; restore and watch it go green. Assert the anchor
   matched before believing a survivor - a mutation that failed to apply printed
   a green suite twice in this repository on 2026-09-08.
4. The existing four properties are kept. This item ADDS the reverse direction;
   it does not trade one direction for the other, which is what `OPS-57`'s link
   guard would have done had it only checked stubs.
5. The count is not written into the document. Per its own preamble, a
   completeness check states a COMMAND or a derived comparison, never a total
   that rots.

### Outcome - CLOSED 2026-09-10

`tests/test_inventory.py` went from 8 tests to 13. The reverse direction is
`test_every_file_the_scope_covers_is_named_in_the_inventory`, and the scope it
enforces is stated rather than assumed: `.claude/commands/*.md`,
`.claude/agents/*.md`, `.githooks/*`, `tools/*.py`, `tests/*.py` and
`scripts/*.py`. Enumeration reuses `tests/_tracked.iter_authored_files` rather
than inventing a second way to list tracked files.

**The gap was twelve times the size the item predicted.** This item was filed
because three modules had gone missing. The guard found 37 - 33 test modules and
four tools - and `tools/` had no section in the document at all, so the miss was
a whole CATEGORY rather than a few stragglers. Two new sections were added, each
description taken from the module's own docstring.

**The refutation pass found three things the closure had wrong, and that is the
part worth keeping.** An independent agent confirmed the property was
non-vacuous - 81 of 81 scope files turn it red when their naming line is cut -
and then found:

1. The document asserted, in its own voice, "Between the two tables, every
   `tests/test_*.py` in the repository is named". That was FALSE, and the file it
   omitted was `tests/test_inventory.py` itself - the module doing the checking.
   The new guard did not catch it, because the guard asks whether a name appears
   ANYWHERE in the document while the sentence claims it appears IN THE TABLES.
   A looser guard standing behind a stricter sentence reads as enforcement and is
   not. Both were fixed: the row was added, and
   `test_every_test_module_is_named_in_one_of_the_two_tables` now requires a
   TABLE ROW. `test_the_two_table_claim_is_still_the_sentence_this_guard_enforces`
   pins the sentence to the guard so the two cannot drift apart again.
2. `tests/_tracked.py` - the shared walker the new guard itself runs on - was
   tracked, uninventoried, and OUTSIDE the stated scope, along with
   `tests/conftest.py` and `scripts/write_lane_contracts.py`. The scope was
   widened to `tests/*.py` and `scripts/*.py`. `scripts/` was the worst of the
   three states: half-covered by luck, with `scripts/install_hooks.py` named only
   because CLAUDE.md's fresh-clone instructions happen to cite it. Directories
   that stay out - `tests/fixtures/`, `lanternlight/`, `ops/`, `docs/` - are now
   NAMED as out, because an unmentioned directory is indistinguishable from an
   overlooked one.
3. The slice reported to the merger that its exclusion-cap test "is vacuous while
   the dict is empty and the module says so". The module said no such thing.
   `EXCLUDED_FROM_INVENTORY` is empty, its per-entry checks were watched failing
   against injected entries, and the module now records exactly that - which of
   its checks execute on an ordinary run and which were verified by measurement
   instead.

**A wrong DATE, caught at the merge.** The repair stamped `2026-09-09` into eight
places across the two files. The work happened on 2026-09-10, confirmed against
the machine clock in local and UTC - both read 2026-09-10, so no midnight
ambiguity was available to excuse it. This is the same defect class as the three
numbers the 2026-09-08 wrap had to refute: prose in a committed artifact, stated
flat, that nothing mechanical reads.

### Acceptance, met

1. **Met.** The scope is stated in `_SCOPE` and restated in the document.
2. **Met.** `EXCLUDED_FROM_INVENTORY` is EMPTY - nothing needed excusing once the
   document was completed - and a test caps growth at 12, requires each entry to
   be in scope, to exist on disk, and to carry a reason.
3. **Met.** Proved by mutation twice independently, each time asserting the anchor
   was present before the cut and absent after it, re-reading from disk, and
   restoring under a SHA-256 equality check.
4. **Met.** All four original properties are kept; the count moved 8 to 13.
5. **Met.** No total is written into the document; its Test count section states
   commands only.

## OPS-70. `.claude/settings.json` still hardcodes an absolute repo root in `permissions.allow` - the OPS-61 defect surviving in the file OPS-61 cleaned - CLOSED 2026-09-10

Filed 2026-09-08 by the wrap's refutation pass, which found it while checking
something else. `OPS-61` rewrote all six hook COMMANDS to reach their scripts
through `$CLAUDE_PROJECT_DIR`. Three entries in the same file were never in that
item's scope and still read:

    "Read(//C/Lanternlight/**)",
    "Write(//C/Lanternlight/**)",
    "Edit(//C/Lanternlight/**)"

**Why no guard catches it, which is the part worth keeping.**
`tools/hook_command_guard.py` walks `hooks.*` and reads command strings. These
live under `permissions.allow`, which it never visits, so the guard's green line
is true and answers a narrower question than a reader of that green line would
assume. That is this session's own recurring shape - a true verdict about
something other than what was asked - found for the fourth time, in the file the
first three were about.

**What it costs, and it is smaller than `OPS-61`'s.** These entries pre-approve
tool calls; they do not dispatch anything. In a clone or a worktree at another
path they simply never match, so the session prompts for permission where it
would otherwise not have. That is a nuisance rather than a wrong answer, and it
is why this is a separate item rather than a reopening: `OPS-61`'s hooks FIRED
and reported about the wrong tree, which is a different order of defect.

**Do not assume the fix is the same.** Whether the permission matcher expands
`$CLAUDE_PROJECT_DIR` is NOT MEASURED. `OPS-61` measured the expansion for hook
COMMANDS only, and the two are different code paths in the harness - the same
mistake `OPS-65` had to avoid when `$CLAUDE_PROJECT_DIR` turned out to be
undefined for a command a session types. Measure before writing.

### Acceptance

1. Whether the permission matcher expands the harness variable is MEASURED, in a
   real clone at a different path, by observing whether a matching tool call is
   pre-approved or prompts. Presence in the file is not the fact; a matched
   permission is.
2. If it expands, the three entries use it and the demonstration is end-to-end.
   If it does not, the entries are either removed as dead weight in every tree
   but this one, or kept with a comment saying they are primary-checkout-only and
   why - a DECLINE with the measurement behind it, which `OPS-61` criterion 4
   already establishes as an acceptable outcome.
3. The guard reaches the rest of the file, or says in its own docstring which
   parts it does not read. `tools/hook_command_guard.py` reporting `OK` while an
   absolute root sits twenty lines away in the same document is the defect this
   item is about, one level up.
4. Proved non-vacuous by embedding a different absolute root in whatever section
   the guard newly reads, and watching it go red.

### Outcome - CLOSED 2026-09-10

**Criterion 1 was answered with a DECLINE, and the decline is the result.**
Whether the permission matcher expands `$CLAUDE_PROJECT_DIR` was NOT observed on
this machine, and the reason is recorded rather than glossed: the session ran in
BYPASS PERMISSIONS MODE, where every tool call is pre-approved regardless of the
allow list, so a did-it-prompt probe cannot distinguish a MATCHED rule from a
BYPASSED one and returns a false green either way. What was established instead
rests on two non-observational sources that agree with each other - the published
permissions documentation, and the shipped client's own rule-anchoring code read
on this machine - and says a rule's content is gitignore syntax with four anchors
into none of which any environment variable is substituted. `OPS-61`'s fix does
not carry across. The observation that would settle it is filed as `OPS-71`.

**The three rules were KEPT**, with the reason in the file's own `$comment`: they
work in this checkout, no measurement says to drop a working pre-approval, and
the documented portable successor (`Edit(/**)`, anchored at the settings source)
is a live change to what this machine pre-approves resting on exactly the claim
that could not be observed.

**`tools/hook_command_guard.py` now reads `permissions.allow`, `permissions.deny`,
`permissions.ask` and `permissions.additionalDirectories` as well as `hooks.*`,**
and pins the three existing rules by exact string so a fourth absolute rule turns
the suite red. It uses a SEPARATE pattern set from the hook side, because the two
grammars disagree about a single leading slash - in a permission rule it anchors
at the settings source - and reusing the hook patterns reported the recommended
fix as the defect. Its OK line now names its own scope: `6 hook command(s), 12
permission rule(s)`, so the green line no longer answers a narrower question than
a reader assumes. That was this item's whole complaint, and the fix is that the
verdict states what it covered.

**The refutation pass broke the first closure in three places.** All three were
reproduced before being repaired:

1. A trailing space - `Read(//C/Evil/**) ` - bypassed the guard entirely, because
   the splitter required a closing parenthesis and returned the rule unsplit when
   it found none, after which the root pattern never matched. Its docstring
   promised a "safer default ... still scanned", which was therefore false as
   written. The BEHAVIOUR was fixed rather than the docstring; an unterminated
   `Read(//C/Evil/**` now reports too.
2. The UNC backslash spelling was missed, because the permission pattern set held
   a hand-written near-copy of the UNC pattern rather than the pattern itself.
   The two are now one object and cannot drift.
3. `Bash(cd //C/Evil && ls)` was missed while `Bash(cd C:/Evil && ls)` was caught
   - an inconsistency nothing disclosed. Resolved deliberately by WIDENING: a
   path in a rule's argument is in scope wherever it appears.

**A claim was being SHIPPED as measured when nothing had been measured.** The
module asserted "Measured for `OPS-70`" in three places, one of them inside the
user-facing finding text, so the guard PRINTED false provenance at the moment it
fired - the worst place in the file for it, because that string is read by
someone who has just been told something is wrong. It hedged nowhere: a search
for "observ", "bypass permission" or "not measured" returned nothing.
`MATCHER_CLAIM_PROVENANCE` now states the claim is an INFERENCE from two named
documentary sources, names bypass-permissions mode as the reason it is not an
observation, and says what would settle it. A test asserts the word "measured"
does not appear in the detail text. Two sentences in the `$comment` that were
stated FLAT - that the POSIX spelling is "therefore the correct absolute form",
and that the rules "match in this checkout and nowhere else" - were attributed to
their sources instead.

**The merger's own refutation was itself refuted, twice, by the merger.** Two
independent re-probes of the UNC repair reported BYPASS. Both were the probe's
own escaping losing a backslash, so the string tested was not a UNC path at all;
built unambiguously with `chr(92)` and verified by its on-disk repr, the guard
catches it. This is the repository's "an empty grep is a claim about your
pattern" rule landing on the person applying it, and it is recorded because the
first instinct on seeing BYPASS was to disbelieve the agent rather than the probe.

### Acceptance, met

1. **Met by an explicit DECLINE**, with the confound named and the settling
   measurement specified. Successor filed as `OPS-71`.
2. **Met.** Kept, with the reason and its provenance in the `$comment`.
3. **Met.** The guard reaches `permissions.*`, states its scope in its OK line,
   and names its remaining blind spots in its own docstring:
   `settings.local.json`, user settings, and the other keys of the tracked file.
4. **Met.** Proved non-vacuous against the LIVE file under an
   assert-anchor / verify-on-disk / restore-and-compare-SHA-256 discipline, with
   six spellings: `//D/Elsewhere/**`, `D:/Elsewhere/**`, `//E/Somewhere/**`, a
   lower-case drive letter, a rule in `permissions.deny`, and the UNC form. The
   count moved 20 to 60.

## OPS-71. The portable successor to the three absolute permission rules is UNADOPTED, and the measurement that would settle it cannot be taken in bypass permissions mode - OPEN

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

## OPS-72. A store-drift guard FAILED ONCE in a full run and will not reproduce - OPEN

Filed 2026-09-10. Recorded rather than dismissed, because an intermittent
failure in a guard is the one kind this project cannot afford to forget: the
next session sees green, assumes the observation was noise, and the guard is
quietly unreliable in exactly the situation it exists for.

**What was observed, once.**

    FAILED tests/test_store_drift.py::TestTheArithmeticThatWasWrong::
        test_two_stashes_from_an_unchanged_index_leave_THREE_commits_not_four

in a full `python -m pytest` run that otherwise reported 2833 passed, 1 skipped.
No assertion text was captured, because the summary line was read and the run
was not repeated before the next edit - that is a mistake in the observation and
is recorded as one.

**What was measured afterwards, and what it does NOT establish.**

- `python -m pytest tests/test_store_drift.py` three times in a row: 46 passed
  each time.
- `python -m pytest tests/test_store_drift.py::TestTheArithmeticThatWasWrong`
  alone: 2 passed.
- The next full `python -m pytest`: 2835 passed, 1 skipped. The failure did not
  recur.

None of that explains the failure. Five green runs after one red is consistent
with a flake AND with an order-dependence that the second full run happened not
to hit, and this item exists because those two are different facts.

**Why it is plausible rather than obviously spurious.** That module builds real
throwaway git repositories and counts objects in the store, and the class under
test is named for arithmetic that was already wrong once. It runs `git stash` in
its fixtures, which is the operation `SHARED_WORKTREE_BAN` in `ops/store_drift.py`
warns is whole-tree in reach. A test that shells out to `git` is also exposed to
whatever else on the machine touches a repository at the same moment - and this
session had background agents running, though none of them should have been
inside a scratch repository belonging to this module.

**The trap to avoid when picking this up.** Do not "fix" it by adding a retry, a
sleep, or a tolerance to the assertion. A guard that passes on the second attempt
is a guard that reports clean about a different attempt, which is the defect
`OPS-69` and `OPS-70` were both about. Find the cause or record that it could not
be found.

### Acceptance

1. The failure is REPRODUCED, or a bounded attempt to reproduce it is recorded
   with what was tried - run count, ordering, and whether anything else was
   touching a git repository concurrently. "Could not reproduce in N runs" is an
   acceptable outcome and is a measurement; "probably a flake" is not.
2. If it reproduces, the cause is named at the level of the mechanism - which
   object count moved, and why - not at the level of "git was busy".
3. If the cause is concurrency with other processes on this machine, the module
   says so in its own docstring, because an environmental dependency nobody has
   written down is indistinguishable from an intermittent bug.
4. No retry, sleep, or widened tolerance is added to make it green. If the
   assertion is genuinely too strict, that is a separate finding and is argued
   on its own evidence.


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
