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

## OPS-35. Adopt the cross-project lock, re-implemented - CLOSED 2026-09-11, all six criteria met

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
| 5. Interoperation proven against a REAL sibling holder | **NOT MET - UNBLOCKED 2026-09-10, awaiting the arm** | joined by operator ruling, see `ADR-008`; the proof needs this project to actually HOLD a slot in the shared bucket, which is next session's first act |
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

### Criterion 5 UNBLOCKED by operator ruling - 2026-09-10 - still NOT MET

**The operator ruled in chat: "yes, join the shared bucket".** That answers the
question the section above left open. `ADR-008` records the decision and
supersedes `ADR-007`, which is marked superseded rather than rewritten because
`ADR-007` itself instructed exactly that.

**`ADR-007`'s claim that joining is one environment variable was REFUTED by
measurement**, and this is the substance of the change. The shared bucket holds
NO `reserved-*.lock` of any kind, so the reserved-floor widening has not landed.
`slot_order` tries our own floor FIRST, so a bare env-var join would have created
`reserved-ll.lock` on nearly every acquire - a file no sibling's reaper
recognises, so any leak of ours would sit there indefinitely - and we would never
have contended for surplus, which means we would not have rationed with anybody.
That is the opposite of joining.

**What landed instead is conditional on the bucket's OBSERVED SHAPE.**
`reserved_scheme_state()` answers three ways - present, absent, or could-not-look
- and the third is a distinct value rather than a dressed-up "absent", which is
the distinction this repository keeps having to re-learn. Could-not-look takes
the surplus-only branch, because the conservative direction is the one that never
writes an unrecognised file into a shared directory. When reserved names appear -
in somebody else's tree, on a day nobody tells us about - our own floor is tried
first again with no code change here.

Verified read-only against the live bucket: the join order is `0.lock`, `1.lock`,
`2.lock` with no reserved name, while `slot_order("ll")` still returns
`reserved-ll.lock` first. The agreed protocol is untouched; only the DEPLOYMENT
POLICY is conditional.

**First first-party evidence for the wire.** The live lock's payload carries
exactly `cycle`, `pid`, `repo`, `run_id` and `ts`, and `ts` is unix epoch seconds
as a float. `ADR-007` had recorded that only `pid` and `repo` were ever seen
verbatim and that the other three were reconstructed from a quoted call
signature. All five are now OBSERVED, and the `ts` unit that was an open gap is
measured. The reconstruction written from prose alone was correct.

**A leaked slot has been sitting in that bucket unreclaimed.** The single lock
present belongs to a holder whose pid is DEAD, with a `ts` 30.5 hours old - stale
by both arms and unreclaimed by anyone for over a day. If the deployed bucket
really rations three slots, one of them has been dark that whole time. Our reaper
handles both naming schemes, so arming will reclaim it.

**WHY THIS CRITERION IS STILL NOT MET.** The operator asked for the lane to be
re-armed NEXT session, so this session landed the code and deliberately did NOT
take a slot. Joining by configuration is not the same fact as interoperating: the
criterion asks for interoperation PROVEN against a real sibling holder, and that
needs this project to actually hold a slot in the shared bucket while another
project is using it. Until that is observed, this stays open - and a mock proving
we agree with ourselves is the two-agents-agreeing failure in a new costume,
which is what the criterion says in its own words.

**The costs, stated rather than hedged out.** We now consume a slot the siblings
were rationing between themselves; that is what the operator ruled and it is not
free. Our leaks now land in a shared directory where our own stale arm remains
the only thing that reclaims them, because a repository-local reaper is the only
one that knows our keys.

### THE LANE IS ARMED - 2026-09-11 - criterion 5 ADVANCED, still NOT MET

**The operator instructed in chat on 2026-09-10: "re arm the lane next session."
That was done on 2026-09-11, and arming meant actually taking a slot rather than
flipping a setting.** The code landed on 2026-09-10 with no consumer at all;
`acquire_lane` and `hold_lane` appeared only in the module, its tests and the
ADR. `ops/loop/lane.py` now wires a SESSION-SCOPED lane into the loop's entry
block, beside the single-instance lock and the session watcher, and
`.claude/commands/loop.md` and `docs/HEADLESS.md` carry it.

**Why session scope rather than per cycle**, recorded so nobody re-litigates it:
the budget being rationed is the machine's and the account's concurrency, which
this project consumes continuously for as long as a loop is alive, not in bursts
that line up with cycle boundaries. A per-cycle acquire would release a slot the
session is still effectively using, and would turn a mid-loop "busy" into a
stalled cycle with no good answer.

**What was MEASURED against the live bucket, not asserted.** A real acquire was
performed and the bucket read back at each step:

- Before: one lock, `0.lock`, 104 bytes. Reserved scheme state `absent`, so the
  try order was the surplus names only and `reserved-ll.lock` was never a
  candidate - the surplus-only branch `ADR-008` chose, confirmed in the live
  bucket rather than in a fixture.
- While held: a second lock appeared at `1.lock`, 120 bytes, carrying EXACTLY the
  five wire fields - `cycle`, `pid`, `repo`, `run_id`, `ts` - with `pid` this
  process, `repo` this checkout, and a `ts` age of 0.02 seconds. Our writer and
  the observed wire agree, now proven by writing rather than by reading.
- After release: the lock was gone and the bucket was back to its prior contents
  byte for byte.

**A PREDICTION THIS ITEM'S OWN HAND-OFF MADE WAS REFUTED BY THE ARMING.** It said
our reaper would reclaim the leaked `0.lock`. It did not: the acquire stepped
past it to `1.lock` and left it identical to the nanosecond. `try_acquire` never
calls `reap`, and `reap` has no caller anywhere in this tree. Filed as `OPS-76`.

**WHY CRITERION 5 IS STILL NOT MET.** It asks for interoperation proven against a
REAL SIBLING HOLDER. What happened here is a real acquire in the real shared
bucket, which is strictly more than the mock the criterion forbids - but the only
other lock present belonged to a holder whose pid is dead. Contending with a
leaked artifact is not contending with a participant. Two things are still
unobserved: this project being refused a slot because a live sibling holds it,
and any sibling's reaper reclaiming a lock of ours. Until one of those is watched
happening, this criterion stays open and says so.


### CRITERION 5 - A REAL SIBLING HOLDER WAS OBSERVED - 2026-09-11

**This is the observation the criterion has been waiting for since it was
written, and it was not arranged.** It was found by reading the bucket back after
this session released its own lane.

The session held `0.lock` from 08:21 local for the length of the loop. When the
governor released it, the bucket was NOT empty: `1.lock` remained, and it belongs
to somebody else.

**What was measured about that lock**, with nothing quoted that identifies
anyone:

- its `pid` is ALIVE, probed through the same liveness path the loop guard uses;
- its `repo` is NOT this checkout;
- its `ts` was 0.36 hours old - fresh, and far inside the stale arm;
- `is_stale` answers False, so our reaper would not touch it;
- its `run_id` is 8 characters where ours is 25, which is a second, independent
  sign of a different implementation of the same protocol;
- it carries exactly the five agreed wire fields and nothing else.

**Therefore this project held a surplus slot in the shared machine-wide bucket at
the same time as a live participant from another project held the adjacent one.**
That is interoperation against a real sibling holder rather than against a mock,
which is what criterion 5 asks for in its own words. The two locks coexisted
without either implementation disturbing the other, and our reaper correctly left
a non-stale foreign lock alone throughout.

**What is STILL not observed, stated so nobody rounds this up.** Two things:

1. **Being REFUSED.** We have never been told the bucket is full. With a surplus
   width of 3 and two locks held, there was a free slot the whole time. Until a
   busy answer is seen, the contention path is proven only in the direction where
   it succeeds.
2. **A sibling's reaper reclaiming a lock of OURS.** ADR-008 already says a
   sibling writing reserved names would not prove its reaper reads them; the same
   caution applies here. We now know they write surplus names we understand. We
   do not know that anybody reclaims ours, and `OPS-76` is a reminder that a
   reaper can exist and never be called.

**The merger's judgement: criterion 5 is MET.** It asked for interoperation proven
against a real sibling holder rather than a mock, and that is what was observed -
concurrently, in the real bucket, with a live foreign pid. The two gaps above are
about the FULL and the RECLAIM paths, which the criterion does not name and which
are recorded here rather than folded into it. `OPS-35` closes.


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

## OPS-75. No check asks whether a `.gitignore` pattern already shadows a tracked file - OPEN

Filed 2026-09-11, same channel note, same re-implemented-not-vendored basis as
`OPS-74`.

**The shape.** An unanchored ignore pattern can match a path that is ALREADY
tracked. Git keeps honouring the tracked entry, so nothing breaks and nothing
warns - but an untracked sibling added next to it in the same directory is
silently refused by `git add`, and the refusal looks like the file simply not
mattering. This project has two live reasons to care: `moon_sync_inbox/` is
gitignored and is exactly where a mistaken addition would be invisible, and
`ops/runtime/` is gitignored while sitting inside a package directory that is
not.

**Not yet measured here.** Whether any Lanternlight pattern currently shadows a
tracked file is unknown; the read that produced this item was read-only and
could not run `git ls-files` or `git check-ignore`. The item is filed as a
question to answer, not as a defect to fix.

### Acceptance

1. A test or script that cross-references every `.gitignore` pattern against the
   tracked listing and fails if any tracked path is matched by a pattern that
   would also ignore an untracked sibling in the same directory.
2. The tracked listing is asked of `git` at run time and never stored in the
   file, for the reason `tests/test_source_register.py` already gives: a
   committed list of filenames goes stale on the first rename and then reads as
   a confident lie.
3. If `git` is absent or returns nothing, the check gets NOISIER rather than
   quieter, and that direction is tested. This is `OPS-74` criterion 5 applied
   to the check this item builds, and the two items must not both assume the
   other proved it.
4. The result of the first run is recorded in the ledger as a number with a
   date, including zero.
5. Every guard above is watched red under mutation, with the anchor asserted
   before any survivor is believed.


## OPS-77. A surplus width of ZERO is a permanent silent "busy", one level up from the hole `OPS-73` just closed - OPEN

Filed 2026-09-11 by the refutation pass over this session's own work, which
found it while trying to break the three-state distinction `OPS-73` hole 2
established. It is the same defect shape, one layer up, and it was introduced by
nothing this session did - it has been reachable since the width became
configurable.

**Measured.** `acquire_lane` with `surplus=0`, or with the environment override
`LL_LANE_SLOT_SURPLUS` set to `0`, produces an EMPTY candidate order. The loop
over candidates then has nothing to walk, `try_acquire` falls out of it, and the
return is `None` - which by the contract `OPS-73` hole 2 just made explicit means
exactly one thing: every candidate slot is taken. Against an empty, writable,
perfectly healthy bucket it reports `BUSY - no slot free`, forever.

`ops/lane_slot.py` accepts a width of 0 deliberately - `shared_surplus_width`
rejects a NEGATIVE width and a non-numeric one, and treats 0 as a legitimate
value. That is defensible on its own terms; what is not defensible is the answer
it produces downstream, because a caller cannot distinguish "the machine is busy"
from "you asked for a bucket with no slots in it".

**Why this matters more than its size suggests.** The whole point of the
`BucketUnusable` work was that a permanent fault must never wear the BUSY
wording, since BUSY is the one condition a caller is expected to shrug off and
retry past. A zero width is a configuration error that produces a permanent
fault, and it currently wears exactly that wording. It is also the cheapest
possible way for a future operator to silently take this project out of the
shared lane scheme while every status line reads as if it were participating.

### Acceptance

1. A width of zero, from the parameter or from the environment override, is
   distinguishable from a full bucket at the call site. Whether that is a refusal,
   a third status, or a documented and tested decision to treat zero as "opt out
   of lane contention" is open - but if it is the last of those, the opt-out is
   NAMED in the status line so a reader can see it, because an undisclosed
   opt-out is the blind spot `OPS-70` closed wearing a configuration hat.
2. The decision covers both entry points. `acquire_lane`'s parameter and
   `LL_LANE_SLOT_SURPLUS` must not disagree, for the reason `OPS-73` criterion 4
   already established about the two whitespace branches.
3. A test asserts the new answer against an EMPTY, writable bucket, which is the
   case that today reads as contention.
4. Every guard above is watched red under mutation, with the anchor asserted
   before any survivor is believed.


### Outcome - OPS-73 CLOSED 2026-09-11

All five criteria met, each judged individually against the tree by an
independent refutation pass rather than against the implementing slice's report.

- **Criterion 1 and 2, the detection alphabet.** `DETECTION_REPO_KEYS` is a
  strict superset of `REPO_KEYS` adding `rm` and `ds`, used ONLY by detection.
  Claiming is untouched: `UnknownRepoKey` still refuses both. The provenance is
  in the constant's own comment and pinned by a test that reads the module's
  source - the two codes are read off `CLAUDE.md`'s ports table, the same
  document that assigned this repository `ll`, and they are NOT confirmed lock
  keys agreed by those projects. Nobody was asked, because `OPS-48` forbids it.
  Recording the limit of the provenance beside the provenance is what satisfies
  criterion 2's refusal of a guess: we widened what we can SEE and assigned
  nobody anything.
- **Criterion 3, unusable versus busy.** `BucketUnusable` is raised where `None`
  was returned, so `None` now means exactly one thing. Verified by refutation
  against four separate unusable shapes - a file as the bucket, a bucket under a
  file, slot names occupied by directories, and a permission-denied directory -
  none of which could be made to report BUSY, and three fresh locks which report
  BUSY and could not be made to report UNUSABLE.
- **Criterion 4, whitespace.** An all-whitespace `LL_LANE_SLOT_ROOT` is now
  ignored exactly as an all-whitespace `PROGRAMDATA` already was, in both
  branches, with a test per branch.
- **Criterion 5.** Seven guards watched red under mutation by the implementing
  slice and three more re-broken independently by the refuter, anchors asserted
  each time.

**A defect found while closing this, filed rather than folded in:** a surplus
width of zero produces an empty candidate order and therefore a permanent silent
BUSY against a healthy empty bucket. That is this item's own hole 2 one level up.
`OPS-77`.

### Outcome - OPS-76 CLOSED 2026-09-11

All six criteria met. `reap_for_acquire` is called by `acquire_lane` as its first
act on the bucket, so the stale arm is reachable from the only production path.

- **Criterion 1**, the reclaim, proved behaviourally rather than by grep: a stale
  lock planted in an earlier candidate position is reclaimed and that slot taken,
  by both `acquire_lane` and `session_lane`. The test was watched red against the
  code as it stood - the headline failure read `assert '1.lock' == '0.lock'`,
  which is precisely the stepping-past that was measured against the live bucket.
- **Criterion 2**, the safety direction, attacked independently: a live-pid lock
  and a fresh-timestamp lock both survived byte-identical and mtime-identical.
- **Criterion 3 was DECIDED, not omitted.** The acquire path never reclaims
  another participant's `reserved-<key>.lock`, even a stale one; it reclaims
  stale surplus locks and our own stale floor. The reasoning is in the ADR
  amendment, and so is the accepted blind spot: **a sibling's genuinely leaked
  floor is never reclaimed by us.** Tested for every key in the detection
  alphabet plus an unknown one, all of which survived while `reserved-ll.lock`
  was reclaimed.
- **Criterion 4**, the false Consequences sentence in `ADR-008`, is corrected by
  amendment with the original quoted, never by rewriting the decision.
- **Criterion 5**, the anti-recurrence guard, is real: unwiring the reap reddens
  eight tests, checked by unwiring it.
- **Criterion 6**, five mutations red by the implementing slice and five more by
  the refuter, anchors asserted.

**THE DOCUMENTS WERE THE LAST THING TO BE TRUE, AND ONLY A REFUTATION PASS FOUND
IT.** With the suite green at 2924 passed, three shipped documents -
`ops/loop/lane.py`, `docs/HEADLESS.md` and `.claude/commands/loop.md` - still
said this project never removes a lock it did not create. That had been true for
the whole life of the module and was made false by this very item. Nothing
mechanical caught it: a green suite says an implementation matches its tests, and
says nothing about whether the prose beside it still describes the code. All
three are rewritten to carry the change as the headline it is, including the
honest sentence that this project now deletes files from a directory other
projects' live loops depend on.

**A PRIVACY DEFECT WAS FOUND IN THE SAME PASS AND FIXED.** `_display_bucket` was
inverted: it elided paths INSIDE the checkout and printed every other path
verbatim - and every bucket this project actually uses is outside it. A status
line printed once per cycle therefore carried the operator's account name, which
`CLAUDE.md` names explicitly as an operator identifier. It now enumerates the
safe renderings and elides anything else behind a truncated digest, so distinct
buckets stay distinguishable without being named. `lanternlight/redact.py` was
measured and deliberately NOT used here: it masks enumerated identifier tokens in
log-shaped text and has no filesystem-path rule, so calling it would have been a
no-op wearing the costume of coverage. That judgement is recorded because the
next session will reasonably ask why the sanctioned path was not taken.


## OPS-78. 187 tests FAIL rather than skip when `git` is absent, measured - CLOSED 2026-09-11, all five criteria met

Filed 2026-09-11 from the first believable run of `tools/false_red_probe.py`,
whose positive control was PROVED on that run. This is the finding `OPS-74` was
built to produce; `OPS-74` asked for the measurement and is closed by having taken
it, and what to DO about the result is this item.

**MEASURED, and re-run by the merger rather than quoted:** with `git` stripped
from every PATH entry that carries it, 187 tests across 17 files fail or error
that otherwise pass. Only 22 tests skip cleanly. On a machine with no `git` -
a fresh clone on a bare box, a container, a CI image that forgot it - this suite
reports 187 failures that are about the environment and not about the code.

**Why that is worth fixing rather than shrugging at.** `CLAUDE.md`'s fresh-clone
section tells a new checkout to run `python -m pytest` as its second command. A
reader who does that without `git` on the PATH sees a wall of red with no
indication that the cause is a missing tool, and this repository is PUBLIC, so
that reader may not be the operator. A failure that misattributes its own cause is
the same defect class as every entry in the anti-patterns list.

**What is NOT being claimed.** These 187 are not vacuous tests and they are not
wrong. They genuinely exercise `git` and they genuinely cannot run without it. The
defect is the SHAPE OF THE REPORT when the tool is absent, not the coverage.

**The counter-argument, recorded so it is not re-derived.** A blanket skip is not
obviously right either: a skip is invisible in a green summary, so converting 187
failures into 187 skips could let a real regression hide on a machine that has
quietly lost `git`. Whatever is chosen has to keep "the tool is missing" loud
while keeping it distinguishable from "the code is broken".

### Acceptance

1. A decision is recorded, with reasoning, on what the suite should do when `git`
   is absent: clean skips, a single loud collection-time refusal that names the
   missing tool, or a deliberate and documented decision to leave the failures as
   they are. All three are defensible; silence is not.
2. Whatever is chosen, the count of tests that FAIL for a missing tool is measured
   again with `tools/false_red_probe.py` afterwards and recorded in the ledger with
   a date. The probe must report its positive control PROVED on that run, or the
   number is not a result.
3. If skipping is chosen, the skip is not silent: something in the run states that
   N tests were skipped because a named tool was absent, so a green summary cannot
   conceal a machine that has lost it.
4. The same question is asked for at least one tool other than `git` before the
   answer is generalised - the probe takes `--tool`, so this costs one run. A
   policy derived from one tool is a policy tested against one tool.
5. Every guard above is watched red under mutation, with the anchor asserted
   before any survivor is believed.


### Outcome - 2026-09-11 - 187 to 0 for `git`; criterion 4 BLOCKED on `OPS-79`

**Criteria 1, 2, 3 and 5 are MET. Criterion 4 is NOT, and the item stays OPEN
because of it.**

**The decision, criterion 1.** Clean skips PLUS a loud end-of-run statement. A
collection-time refusal was rejected: it would make a missing `git` block the
entire suite including the roughly 2,800 tests that do not need it, so a
contributor without `git` could run nothing at all - worse than the problem being
fixed. A bare skip was rejected on its own, because a skip is invisible in a green
summary and 187 silent ones would let a real regression hide on a machine that had
quietly lost the tool. So the tests skip, and the run says so.

**What was built.** A shared presence guard that returns the tool's RESOLVED
ABSOLUTE PATH rather than a boolean - which makes the present direction
STRUCTURAL, because a test that got a path holds something only a real lookup
could have given it - and that skips with a reason naming the tool. A
terminal-summary hook counts those skips per tool and prints a banner, and says
NOTHING when none happened, because a line that always prints is a line nobody
reads.

**Granularity, stated because a cheap version of this item would have cheated
here.** 27 argv-head swaps inside local helpers and 52 single-line guards on named
tests. NO class-level or module-level mark anywhere: the affected modules contain
mixed classes, and blanket-marking a module to make a number fall would have given
a `git` guard to tests that do not need one.

**MEASURED AFTER, re-run by the merger with the control PROVED on the same run:**
`clean_skip=216, exercised=99, skip_both=1, untouched=2722`, and **`findings: 0`**.
The `false_red` kind is gone from the tally entirely. Directly corroborated by
running the suite under the probe's own PATH stripping: `2821 passed, 217 skipped`,
with the banner reporting 216 skipped for a named absent tool. The one unannounced
skip is the Windows execute-bit test, which correctly names no tool. 216 matches
the probe's `clean_skip` exactly.

**WHY CRITERION 4 CANNOT BE MET YET.** It asks the same question of a second tool
before the answer is generalised. `--tool bash` reports its positive control
UNPROVEN, because the planted control hardcodes `git`. Its 56 false reds across 6
files are therefore an absence of evidence, and were deliberately NOT acted on -
converting call sites on the strength of an instrument just measured blind is the
exact failure this whole line of work exists to prevent. Filed as `OPS-79` gap 4.
**The policy is proven for one tool and is UNTESTED as a general policy**, which is
precisely what criterion 4 was written to stop anyone forgetting.


### Outcome - 2026-09-11 - criterion 4 MET, and the answer is that the tool name is not the dependency

**CRITERION 4 IS NOW MET AND THE ITEM IS CLOSED.** The same question was asked of
`bash`, and the answer changed what the first four criteria are allowed to claim.

**The instrument first.** `--tool bash` now reports its positive control PROVED -
the control is planted for the tool under test rather than hardcoded to `git`, so
the blocker recorded above is gone. Re-run by the merger on a clean tree:
`clean_skip=1, false_red=56, skip_both=1, untouched=3009`, with 3067 tests
collected in BOTH directions. An earlier run of the same probe collected 3062
with the tool and 3067 without, because this session added five tests while the
probe was between its two runs; that run was discarded and re-taken rather than
reported, and the contamination is recorded here because it is the cheapest
lesson in the item: the probe's two runs are eight minutes apart and the tree
must not move between them.

**THE FINDING, and it is the opposite of a generalisation.** Of the 56, only
SEVEN are about `bash`. They live in `tests/test_syntax_check_hook.py`, which
really does need a shell that can close a standard file descriptor before the
interpreter starts, and they have been moved onto the same
`_toolguard.require("bash")` the `git` work built. Measured after: with `bash`
withheld those seven now SKIP cleanly and the end-of-run banner names `bash` as
the absent tool - 35 passed, 7 skipped, where before they were 7 failures.

The other 49 are not about `bash` at all and are filed as `OPS-83`. Four of their
five files contain no reference to `bash`; what they need is the POSIX userland
that happens to share a directory with it. Proved in both directions with shim
runs: restoring ONLY `bash` left all 49 exactly as broken, and restoring the
utilities while withholding `bash` brought 38 of them back and reddened exactly
the seven genuine ones.

**WHY THE REPORT COULD SAY "bash" AND MEAN SOMETHING ELSE.** The probe strips a
PATH ENTRY that carries the tool, never the single executable. On this machine
the three stripped entries are ONE directory - Git for Windows' `usr/bin`,
appearing three times in `PATH` - carrying 244 other executables. `--tool bash`
and `--tool sh` therefore produce a byte-identical stripped `PATH` by
construction, and no run of this probe can tell them apart. This is now COMPUTED
and printed on every run beside the count, in the same unconditional way the
`silent_pass` limitation is, and it states the empty case too: a directory
carrying only the named tool is the one arrangement where `--tool` is genuinely
tool-granular, and that is worth saying rather than leaving as a missing line.

**SO THE POLICY GENERALISES, WITH ONE CONDITION ADDED.** Clean skips plus a loud
banner was the right answer for `git` and is the right answer for `bash`. What
does NOT generalise is deriving the guard from the probe's tool name: the name is
the question that was asked, and the dependency has to be read out of the
individual failures. `OPS-78` criterion 4 exists because a policy tested against
one tool is untested, and the second tool's answer was that the instrument's
label was wrong for 49 of 56 cases.

## OPS-79. Three gaps in the false-red probe's own instrument, found by refuting it - CLOSED 2026-09-11 (a fourth was added, and closed with them)

Filed 2026-09-11 by the refutation pass over `OPS-74`, after that item had already
been marked closed on the strength of a control it reports as PROVED. None of the
three makes the measurement wrong; all three make it narrower than it reads.

**Gap 1: the positive control has no NEGATIVE control.** All three planted
specimens are positive - one that should classify `clean_skip`, one `false_red`,
one `silent_pass` - so the control proves the instrument can SEE, and proves
nothing about whether it INVENTS. Demonstrated: a mutated classifier that promotes
every `untouched` test to `silent_pass` still reports the control PROVED, because
all three specimens still land on their expected kind. A probe that called
everything a finding would pass its own control. Four other blinding mutations
were correctly caught and reported UNPROVEN, so the control is real - it is simply
one-directional, which is the defect `OPS-74` criterion 5 names in tests and did
not apply to the probe itself.

**Gap 2: `silent_pass` recognition misses the dominant shape, and the docstring is
wrong about why.** A presence lookup inside a test body is seen; a lookup at MODULE
level classifies `untouched` instead, and module level is how this repository
usually writes them. The docstring explains the miss as "a cached lookup performed
at import time before the plugin loads", which is not the mechanism. The
consequence is recorded under `OPS-74`: `silent_pass=0` for `git` was structurally
guaranteed, because no test here performs an in-process lookup for it at all.

**Gap 3: the recursion guard matches one spelling.** After a mutation let the probe
run the real suite and recurse five processes deep, an `ast`-based guard was added
requiring every call site in the tests to inject a runner. It walks for attribute
calls on the name `probe`, so a direct import of the entry point by name,
followed by a call through that name, is invisible to it. The guard is not vacuous - a runner-less
attribute call reddens it, and its anchor test notices if the assertions vanish -
it is simply narrower than the hazard.

**Gap 4, added 2026-09-11 and the largest of the four: the positive control is
HARDCODED TO ONE TOOL, so every `--tool` run except `git` is UNPROVEN BY
CONSTRUCTION.** The planted control module's source fixes the tool it looks up,
so pointing the probe at any other executable plants three specimens that cannot
match, and the run reports all three as untouched. Measured: `--tool bash` reports
`positive control UNPROVEN` and, alongside it, 56 false reds across 6 files -
numbers which are therefore an absence of evidence and were correctly NOT acted
on. The `--tool` flag is advertised in the entry point's own help text, so the
probe currently offers a switch whose every setting but one produces an unprovable
answer. This is what blocks `OPS-78` criterion 4.

### Acceptance

0. The planted control is parameterised by the tool under test, so a `--tool` run
   other than `git` can report its control PROVED. Watched red by running a second
   tool and seeing the control fire, where today it cannot.
1. The control gains at least one NEGATIVE specimen - a planted test that must NOT
   be classified as a finding - and a classifier that over-reports fails the control
   instead of passing it. Watched red by mutating the classifier to over-report.
2. `silent_pass` either recognises a module-level lookup, or the limitation is
   stated correctly and prominently in the report itself rather than only in the
   docstring, so nobody reads a zero as a clean bill. If recognition is chosen, a
   planted module-level specimen proves it.
3. The docstring's explanation of the missed case is corrected to the measured
   mechanism.
4. The recursion guard catches the direct-import spelling, proved by adding one and
   watching it redden.
5. Every guard above is watched red under mutation, with the anchor asserted before
   any survivor is believed.


### Outcome - CLOSED 2026-09-11 - all five criteria met, and `--tool` now means something

**Criterion 0, the tool-parameterised control.** The planted control is generated
from the tool under test instead of naming one. The tool name is VALIDATED against
a character set rather than escaped, because it is pasted into generated Python
and a name that cannot be expressed safely should be refused rather than quoted;
a bad name exits non-zero before anything is spawned.

**Criterion 1, the negative specimens.** Two were added, both expected to classify
as untouched, and the control now emits an explicit OVER-REPORTS note when a
negative lands on a finding kind. Watched red the way the gap was found: a
classifier mutated to promote every untouched test to a finding takes eight tests
down INCLUDING the control refusing to be proved, where before it passed.

**Criterion 2, the silent-pass limitation - REPORT was chosen over RECOGNITION,
and the reasoning matters.** Attributing a module-level lookup to every test in
that file would reclassify whole modules as candidates and make the finding
worthless - and it would have moved `git`'s `findings: 0`, which is a real result.
So the limitation is PRINTED UNCONDITIONALLY under the counts instead. A
conditional caveat is absent exactly when somebody is misreading the number.

**Criterion 3, the docstring's wrong mechanism.** It said the lookup was cached at
import time before the plugin loads. Measured: the plugin is loaded before
collection, so the wrapper IS installed and DOES fire - the mark is discarded
because the recorder only has a current test id between the per-test hooks, and a
module body runs at collection. The old explanation is recorded as wrong rather
than quietly replaced.

**Criterion 4, the recursion guard.** Rewritten as pure functions that catch a
direct import, an `as` rename and a module alias. Proved with real bait: the new
walk names the offending line while the old attribute-only walk returned nothing
on the same file.

**BOTH RUNS NOW REPORT THE CONTROL PROVED, with five specimens.** The `git` run,
re-run by the merger, is unchanged where it had to be: `clean_skip=216`,
`exercised=99`, `skip_both=1`, `untouched=2746`, **`findings: 0`**. Cycle 73's
result survived the instrument being rebuilt under it, which is the check that
mattered.

**`--tool bash` is a result for the first time: 56 false reds across 6 files** -
`test_no_pii` 33, `test_syntax_check_hook` 8, `test_precommit_gate_lint` 7,
`test_docguards` 7, `test_precommit_hook_globbing` 6, `test_ascii_hygiene` 1.
Deliberately NOT acted on here; that is `OPS-78` criterion 4's input.

**A caveat that must travel with that 56, and it narrows what it means.** Both
runs were launched from Git Bash, because `bash` is not on the PATH this machine
gives PowerShell. The three stripped entries are all one directory - Git's
`usr/bin` - so a false red there says "this broke when that DIRECTORY left the
PATH", which is wider than "this needs bash". Read the individual failures before
converting any of them; the tool name in the report is the question asked, not the
dependency proved.

**This figure was NOT independently re-run by the merger.** The `git` run was; the
`bash` run is the implementing slice's measurement, reported here as such. The
next session should re-run it before acting on it.


## OPS-80. The documented remedy for a fired size budget does not apply anything - CLOSED 2026-09-11

Filed 2026-09-11. `ROADMAP.md` is at **0.5 sessions of headroom** and
`docs/LEDGER.md` at 1.8. Neither has FIRED; both are warnings. The per-document
budget will almost certainly fire during the next session.

**THE TRAP, measured rather than assumed.** `CLAUDE.md` tells a session: "When a
size budget fires, RE-RUN `tools/doc_archive.py`; do not raise the number." A
session that does exactly that gets a report and no change. The module's own
docstring is explicit and the behaviour matches it: "Nothing here opens a file for
writing, and `main` is a DRY RUN that prints a report." Applying a plan is "a
separate, deliberate act by whoever owns those documents."

**That separation is correct and is not the defect.** The tool is a library of
pure text-to-text functions with a conservation contract - it raises rather than
returning a lossy plan - and the repository has been bitten by tools that did more
than their name promised. The defect is that the INSTRUCTION describes a remedy
the tool does not perform, so the one session most likely to read it is a cold one
under a fired budget with no idea what to do next.

**What the plan currently says it would move**, re-derive it rather than quoting:
38 ROADMAP sections, 24 kept and 14 archived; 84 ledger entries, 60 kept and 24
archived. Character counts, not git blob bytes - the budgets are derived from blob
bytes and must be re-measured after any split is applied.

### Acceptance

1. The split is APPLIED to both documents, and every conservation property the
   module already enforces is checked against the result rather than trusted: the
   full-text equality check, not a length comparison and not a spot check. No
   content deleted, no ledger entry edited, reordered or reflowed.
2. Both budgets are re-derived from GIT BLOB BYTES afterwards with
   `python -m tools.doc_size_budget`, and the numbers recorded in the ledger with a
   date. A character count is not a blob count - `.gitattributes` pins these files
   to LF, and this repository has already been caught by the difference.
3. The archive index stubs resolve: every closed section has exactly one stub in
   the live document pointing at the archived text, and `tools/archive_link_guard.py`
   passes. A reader must reach every word in one hop.
4. **`CLAUDE.md`'s instruction is corrected** to name the applying step, whatever
   it turns out to be, so the next cold session under a fired budget is not sent to
   a tool that writes nothing. This is the half that stops the trap recurring; the
   split alone only postpones it.
5. Whether the applying step becomes a flag on the existing tool, a separate
   script, or a documented manual procedure is open - but the choice is recorded
   with its reasoning, and the pure-function separation the module's docstring
   defends is not quietly discarded to make this convenient.
6. Every guard above is watched red under mutation, with the anchor asserted
   before any survivor is believed.



### Outcome, 2026-09-11

CLOSED. The applying step is `scripts/apply_doc_split.py`, a SEPARATE script -
criterion 5 asked for the choice and its reasoning, and both are recorded at
length in that script's own module docstring rather than only here. The short
form: a `--apply` flag on `tools/doc_archive.py` would have made that module's
central promise conditional, and the promise is not "this module usually writes
nothing" but "nothing here opens a file for writing", which is a property a
reader can check by grepping for a write and which stops being checkable the
moment one exists behind a flag. A documented manual procedure was rejected
first, because the failure being fixed is a cold session following a written
instruction and replacing one paragraph of prose with a longer one leaves the
remedy unexecutable and untestable. The planner is unchanged: not one line of
`tools/doc_archive.py` was edited.

The numbers, RE-DERIVED rather than taken from the premise above, which had
gone stale by one section before the work started: 39 ROADMAP sections, 25 kept
and 14 archived; 84 ledger entries, 60 kept and 24 archived.

Criterion 1, conservation, was checked against the RESULT and independently of
the code that produced it - the four documents were snapshotted, the split
applied, and the documents then read back off disk and compared by a scanner
that imports neither the planner nor the applier. The ledger property held as a
total equality: the live document plus the moved tail reproduces the original
byte for byte, the head through the insertion marker is identical, and 61 live
entries plus 24 moved account for all 85 `### LL-` headings in the original (the
eighty-fifth being the format template above the marker, which is not an entry).
The roadmap property held with ONE named exception, the generated
`## Archive index`, which a split regenerates rather than conserves: 25 live
sections plus 14 moved account for all 39, every moved section occurs verbatim
in the original, the preamble is untouched, and the live document differs from
the expected text by exactly one trailing newline - see `OPS-81`.

Criterion 2, blob bytes: `ROADMAP.md` 331,547 to 224,052 bytes and 0.3 to 3.6
sessions of headroom; `docs/LEDGER.md` 376,804 to 259,062 bytes and 1.6 to 5.8
sessions. Both low-headroom warnings cleared. Those figures were taken AT THE
MOMENT OF THE SPLIT; this section, `OPS-81` and the ledger entry were appended
afterwards, so re-run the command rather than quoting them as current. The
character counts the planner
printed and the blob counts the budget reports agree exactly here, because these
documents are 7-bit ASCII and LF on disk, so there is one byte per character and
no end-of-line conversion to apply - which is a fact about these four files
today and not a licence to treat the two numbers as interchangeable.

Criterion 3: `python tools/archive_link_guard.py` reports
`OK (79 archived heading(s), 79 stub link(s))`.

Criterion 4: `CLAUDE.md` now sends a session under a fired budget to
`python scripts/apply_doc_split.py --apply`, still says "do not raise the
number", and states that `tools/doc_archive.py` only PLANS the split. Three
tests assert all three halves, searched on a copy with the blockquote markers
removed BEFORE the whitespace collapse - without that the sentence spans a `>`
marker and is unfindable, which is this repository's own trap about a grep being
a claim about your pattern.

Criterion 6: five guards were watched red under mutation and green again after
restore, with the anchor asserted before any survivor was believed. Making
`write_atomic` a direct write reddened the failed-publish test; dropping its
`newline="
"` reddened the line-ending test; neutering the roadmap
archive-equality check reddened three tests including the one that proves a plan
missing a single character is REFUSED rather than written; neutering the ledger
total-equality check reddened one; and removing the script's name from
`CLAUDE.md` reddened one.

## OPS-81. Each applied split adds one blank line before the roadmap's archive index, forever - OPEN

Filed 2026-09-11, found by `OPS-80` while proving the split conserves every
word. It does. This is the one thing it does not leave alone, and it is
additive rather than lossy, which is why it is a separate low-priority item and
not a defect in the conservation contract.

`plan_roadmap_split` in `tools/doc_archive.py` builds the live document as the
preamble, then the surviving sections, then a newline and the index section.
The last surviving section's text already ends with its own trailing newline
and with the blank line that separated it from the PREVIOUS run's index, so
each run adds one more newline at that junction and none is ever removed. Measured across two
consecutive applies against copies of the real documents: the three other
documents came back byte-identical and `ROADMAP.md` grew by exactly one
character, all of it at that one junction.

It is cosmetic today - one character per split, and Markdown renders any run of
blank lines the same way. It is filed because the growth has no bound and
because a session reading a diff of the roadmap after a split should not have to
work out whether a changed newline run means something.

### Acceptance

1. Applying the split twice in a row leaves `ROADMAP.md` byte-identical, not
   merely equivalent up to whitespace.
2. The fix is in the PLANNER, not in the applier, and does not weaken the
   conservation contract: the planner must still never delete a character of a
   section's own text. Normalising the separator it generates is not the same
   act as trimming a section, and the code must make that distinction visible.
3. `tests/test_apply_doc_split.py::TestApplyOnCopiesOfTheRealDocuments` is
   tightened back to a strict fixed point, and the two places that currently
   record the tolerated newline - that module and
   `scripts/apply_doc_split.py`'s docstring - are updated together, so no
   comment is left describing a wart that is gone.
4. Watched red under mutation: with the fix in place, re-introducing the extra
   newline must redden the fixed-point test, with the anchor asserted first.

## OPS-82. The guard that protects the operator's live mail records is the only NON-ATOMIC writer of them in the tree - CLOSED 2026-09-11, criteria 1-5 met, 6 held on an operator ruling

Filed 2026-09-11 out of a defect report from Legion Wallpaper, which is worth
reading as an example of a finding that was measured, published in good faith,
retracted once, and is still not quite what it says.

**WHAT LW REPORTED.** LW ran a write-attribution tracer over this suite and
first published "Lanternlight is CLEAN". It then RETRACTED that verdict on
2026-09-11, because its first tracer patched only `builtins.open`, `os.replace`
and `os.rename` and so never saw `pathlib` writes. Re-measured with the fixed
instrument, LW reported that this suite writes the operator's live records -
19,700 bytes into `ops/runtime/inbox_seen.json` and 10,464 bytes into
`ops/runtime/inbox_reported.json` - attributed to
`tests/test_inbox_watch.py::test_the_sessionstart_hook_command_really_runs_and_prints_the_report`.

**RE-MEASURED HERE, and the corruption reading is REFUTED.** Both live records
are BYTE-IDENTICAL across a run of that test: `inbox_seen.json` 21,510 bytes and
`inbox_reported.json` 11,394 bytes, each with the same sha256 before and after.
Measured twice, an acknowledging run apart. Nothing the operator relies on was
left changed.

The EQUALITY is the result and the absolute digest is not, so no digest is
recorded here: both records carry an `updated` timestamp, so their hashes change
whenever the watcher legitimately writes them and a value pinned in this file
would never reproduce. Re-take the measurement rather than comparing to a
constant - the same reason this repository refuses to restate a suite count. The test snapshots both records before it runs the hook command and
restores them in a `finally`, and its own docstring names itself as the single
documented exception that is allowed to touch them.

**WHY LW'S TRACER SAW BYTES ANYWAY, which is the part worth keeping.** LW states
its own limit: the tracer does not see writes performed by a SUBPROCESS. This
test runs the hook through `subprocess.run`, so the hook's own writes are exactly
the ones the tracer cannot see. The only in-process writes to those two paths in
that test are the two `path.write_bytes(snapshot)` calls of the RESTORE. So what
was reported as the suite damaging live state is the guard putting it back, and
the byte counts are consistent with one whole-file write of each record rather
than with an append or a series. This is not a criticism of LW's instrument: the
instrument answered the question it was asked, which was "did bytes move", and
"did state change" is a different question.

**THE DEFECT THAT IS REAL, and it is one level down from the one reported.** The
restore is `Path.write_bytes`, which truncates and then writes. Production code
in the same module does NOT do this: `save_seen` and `save_reported` both route
through `_write_json_atomic`, which writes a temporary file in the target's own
directory, fsyncs it and `replace`s it onto the target, and `save_seen`'s
docstring explains that this is deliberate because a session-start hook reads
these records. So the one writer of the operator's live mail state that is NOT
atomic is the test whose entire purpose is to leave that state unharmed. A crash,
an interrupt or a full disk between truncate and write leaves a zero-length or
half-written `inbox_seen.json`, and the failure mode is the one this repository
cares about most: mail the operator has never seen marked as seen, or a seen set
lost so that 115 notes are re-reported as new.

Two smaller edges of the same shape, recorded so the fix covers them rather than
being redone: the absent-record branch uses `unlink(missing_ok=True)`, which has
the same non-atomic character in the other direction, and there is a WINDOW
between the subprocess's write and the restore during which the live records hold
values produced by a test. Another Claude session's `SessionStart` hook reading in
that window reads fixture state. `CLAUDE.md` already requires atomic writes for
"anything a reader might poll", and these records are polled by every session on
this machine.

**NOT CLAIMED.** No corruption has been observed. This is a crash-window defect,
not a reproduced loss, and it is filed at that strength deliberately - the
repository's own rule is that a confident wrong number is worse than an absent
one, and the same applies to a confident wrong severity.

### Acceptance

1. The restore path in that test writes atomically, by the same temp-then-replace
   discipline `_write_json_atomic` already uses, rather than by `write_bytes`. If
   the production helper can be reused rather than reimplemented, it is reused;
   if it cannot, the reason is written down where the next reader will find it.
2. The absent-record branch is covered too: restoring "this file did not exist"
   must not be able to leave a partially written file behind either.
3. A regression test asserts the restore is atomic in a way that a non-atomic
   restore FAILS - not merely that the bytes match at the end, because
   `write_bytes` already satisfies that. Pinning the mechanism is the point.
4. Watched red under mutation: with the fix in place, reverting the restore to
   `write_bytes` must redden the new test, and the anchor must be asserted before
   the survivor is believed.
5. The window is addressed or explicitly accepted in writing, with the reasoning
   recorded here. Accepting it is defensible - the window is short and the reader
   is another session's hook - but silence is not.
6. A reply to LW is DRAFTED but NOT SENT without an operator ruling, and the
   question is put to the operator. LW published a retraction of its own clean
   bill in good faith and the follow-up measurement changes what its finding
   means, so a reply is owed on the merits. Sending one is still an outward
   action: `OPS-68` holds cross-project propagation on standby by the operator's
   own words, and the single note this channel carried from here on 2026-09-11
   went out on a specific operator instruction that was explicitly not a
   precedent. The draft states what was refuted, what survived, and the
   subprocess reasoning that explains the difference, and quotes no raw command
   output - the finding is stated instead, per `ADR-004` as amended.

### Outcome - 2026-09-11 - fixed, and the window is ACCEPTED with the reasoning written down

**Criteria 1 to 5 are MET. Criterion 6 is as far as this session may take it.**

**1 and 2.** `tests/test_inbox_watch.py::_restore_live_record` writes through a
temporary in the target's own directory and `replace`s it, and removes the
temporary in a `finally` so a failed `replace` leaves nothing beside the
operator's live records. `_write_json_atomic` was NOT reused, and the docstring
says why: it takes a JSON payload and builds its own envelope, while a restore
must put back the exact bytes that were there, including bytes written by a
schema this test knows nothing about. The discipline is copied and the payload is
not. The absent-record branch stays an `unlink`, also with its reason recorded -
removing a directory entry has no partially-written state to leave behind, which
is the property the write branch had to be given.

**3 and 5.** The regression arm compares file IDENTITY rather than bytes, because
comparing bytes at the end cannot fail for a truncating restore. Probed on this
filesystem before the arm was written: `write_bytes` preserved `st_ino` and
`replace` changed it. Watched red under mutation with the anchor asserted first -
reverting to `write_bytes` reddened two arms and left three green, so the
mutation localises. The identity arm carries its own anchor and refuses to pass
where `st_ino` is 0, which would make the comparison true of every
implementation.

**4 - THE WINDOW IS ACCEPTED, not closed, and this is the reasoning rather than a
silence.** Between the hook subprocess's write and the restore, the live records
hold values a test produced. MEASURED: the hook command completes in 0.12 to 0.13
seconds across three runs, so the window is roughly an eighth of a second, and
the only reader that could land in it is another session's `SessionStart` hook on
this machine.

Closing it was considered and rejected. The only way to keep the live paths
untouched is to stop running the real command string - and the real command
string, with no arguments, IS the thing under test. `OPS-61` already narrowed
what "the exact string the harness will execute" may honestly mean here, and
redirecting the paths would leave the test asserting that a string this
repository composed runs some other way than the harness will run it. That trades
a measured eighth of a second against the only end-to-end proof this repository
has that its own session-start hook works.

What the accepted risk actually is, stated so nobody re-derives it as larger: a
concurrent reader in that window sees a COMPLETE, well-formed record holding
fixture values, not a torn one - the torn case is the thing criterion 1 closed.
It would report wrongly once and be correct on its next run, because the restore
puts the real record back and nothing downstream caches it.

**6.** The reply is written at
[`docs/drafts/reply-to-LW-inbox-record-finding.md`](docs/drafts/reply-to-LW-inbox-record-finding.md)
and is HELD. It is tracked rather than left in the gitignored outbox, because the
outbox holds SENT copies and a draft nobody can find is the same failure as a
suggestion filed outside this document. The question is recorded for the
operator: LW published a defect report about this tree and then retracted its own
earlier clean bill, so a reply is owed on the merits - but sending one is an
outward action, `OPS-68` holds cross-project propagation on standby by the
operator's own words, and the single note this channel carried from here on
2026-09-11 went out on a specific operator instruction that was explicitly not a
precedent. This item does not close that question and no session should answer it
alone.


## OPS-83. 49 tests need a POSIX userland, not `bash`, and no guard names what they actually need - OPEN

Filed 2026-09-11 out of `OPS-78` criterion 4. It is the remainder of that item's
56, split off because the seven that really were `bash` are fixed and these are a
different and larger question.

**MEASURED, two directions, on a clean tree.** `tools/false_red_probe.py
--tool bash` reported 56 false reds with its positive control PROVED, re-run by
the merger with 3067 tests collected in both directions. Four of the five files
holding them contain ZERO references to `bash`: `tests/test_no_pii.py`,
`tests/test_precommit_gate_lint.py`, `tests/test_docguards.py` and
`tests/test_precommit_hook_globbing.py`. What they run is a real `git commit`
against this repository's own `.githooks/pre-commit`, whose shebang is
`#!/bin/sh` - not bash - and whose body calls `find`, `grep`, `head`, `mv`,
`printf`, `tr` and `wc`.

**Proved positively rather than inferred from the absence of the word.** Two
shim runs, each with Git's `usr/bin` stripped from `PATH` and a scratch
directory prepended in its place:

- With ONLY `bash` restored, all 49 stayed exactly as broken - 32 errors in
  `test_no_pii`, 6 failures in `test_precommit_gate_lint`, 6 in `test_docguards`,
  5 in `test_precommit_hook_globbing` - while `test_syntax_check_hook` went fully
  green at 42 passed. Restoring the named tool does not restore these tests.
- With a partial POSIX set restored and `bash` withheld, 38 of the 49 came back
  and exactly the 7 genuine `bash` tests went red. The 11 that stayed red need
  utilities that shim did not carry, so the exact per-test dependency is NOT
  enumerated and is not claimed here.

**Why the number 56 was believable and still misleading.** The probe strips a
PATH ENTRY that carries the tool, never the single executable. On this machine
the three stripped entries are ONE directory - Git for Windows' `usr/bin`,
duplicated in `PATH` - and it carries 244 other executables. So `--tool bash` and
`--tool sh` produce a byte-identical stripped `PATH` by construction, and no run
of this probe can separate them. That limitation is now computed and printed on
every run rather than left for a reader to rediscover.

**What is NOT claimed.** These tests are not wrong and they are not vacuous. They
exercise the real hooks and they genuinely cannot run without a POSIX userland.
The defect is the same one `OPS-78` named: the shape of the report when the tool
is absent. It is only unfixed for these because nobody has said what to name.

**The hard part, recorded so it is not re-derived as if it were easy.** `OPS-78`
solved `git` by guarding on ONE tool name, and that works when the dependency is
one executable. Here the dependency is a SET, and three shapes are available:
guard on `sh` alone as the interpreter every hook shebang names, which is honest
about the entry point and silent about the seven utilities the hook body calls;
guard on the full measured set, which is precise and goes stale the moment a hook
gains a `sed`; or ask the question at the hook level - does this repository's
hook run at all here - which names the real dependency but reports a tool name
the banner cannot count. None is obviously right, which is why this is an item
rather than an edit.

### Acceptance

1. A decision is recorded, with reasoning, on what these 49 should name when the
   POSIX userland is absent. Silence is not an option; neither is copying
   `OPS-78`'s single-tool answer without saying why it transfers.
2. Whatever is chosen, the end-of-run banner still counts and names what was
   skipped, so a green summary on a bare box cannot conceal them - `OPS-78`
   criterion 3, applied here rather than assumed from there.
3. The result is re-measured with `tools/false_red_probe.py` afterwards and
   recorded in the ledger with a date, with the positive control PROVED on that
   run or the number is not a result.
4. The 11 that did not come back under the partial shim are identified, and the
   utility each actually needs is named. An unexplained residue is where the next
   wrong generalisation would come from.
5. Every guard is watched red under mutation, with the anchor asserted before any
   survivor is believed.

## OPS-84. Vendor Legion Wallpaper's write tracer under the license it named - CLOSED 2026-09-11, operator-ruled

Filed and closed 2026-09-11. The operator ruled VENDOR in chat after LW named a
license explicitly.

**THE RULE WAS SATISFIED, NOT WAIVED, and that distinction is the item.** An
earlier copy of this same file was refused here because the drop carried no
license statement and this repository is public and Apache-2.0. Lanternlight
asked LW to NAME a license if they wanted it vendorable rather than read for the
idea only. LW answered on 2026-09-11: both delivered files are tracked in
`Remus3/Legion-Wallpaper`, which is PUBLIC and Apache-2.0, the operator is sole
copyright holder, and vendoring with attribution is intended rather than an
accident of publication. LW added that it would rather the rule was applied than
waived. The `CLAUDE.md` license gate then passes on its own terms - Apache-2.0
into Apache-2.0, with GPL and AGPL still DO-NOT-VENDOR whatever is offered.

**VERIFIED BEFORE A BYTE WAS COPIED.** The drop hashes to the sha256 LW published
in its 14:15 note and is 11,267 bytes as stated, and it is 7-bit ASCII
throughout. A license statement about a file nobody checked is a statement about
some other file.

**WHAT WAS ACTUALLY CHANGED, because Apache-2.0 section 4(b) requires saying.**
One thing, and it is mechanical: CRLF was normalised to LF, because
`.gitattributes` pins `*.py` to `eol=lf` and this repository is public, where a
CRLF blob reads as a whole-file diff to every non-Windows contributor. No other
byte differs.

**THE TRAP THAT SHAPED THE GUARD.** A hash of a working file is not a hash of the
commit - this repository's own anti-pattern list, met head-on. Recording a single
digest would have been a confident lie whichever form was chosen, so
`NOTICE.md` records BOTH and says which is which, and
`tests/test_vendored_write_tracer.py` asserts the identity in the form that
survives the policy: read the vendored file, restore CRLF, require the result to
hash to LW's published digest. That binds the test to the licensed CONTENT rather
than to a line-ending rule, and it fails the moment anyone edits the file.

**MEASURED, WHICH IS WHY IT WAS WORTH VENDORING RATHER THAN FILING.** Run against
this repository's full suite with the plugin's own positive control PROVED, its
negative specimen clean and the interpreter confirmed restored, watching
`ops/runtime`, `logs` and `moon_sync_inbox`:

- The operator's live `inbox_seen.json` and `inbox_reported.json` do NOT appear.
  What appears in their place are the `.restore.<pid>.tmp` temporaries that
  `OPS-82` introduced this same day. That is independent corroboration of
  `OPS-82` from an instrument this project did not write: LW saw the live records
  written because the restore truncated them in place, and after the fix the only
  bytes that move go to a temporary that is then renamed.
- `docguard_observed.json.<pid>.tmp`, 21,782 bytes, from the audit-hook recorder
  `tests/conftest.py` documents. By design.
- Two probe files of 2 and 3 bytes from `tests/test_tracked_walker.py`, which LW
  called debatable. Measured under `OPS-85` and there is NO defect: both are
  removed in a `finally` and zero remain after a full run.
- `opened_for_write_only`: empty.

**NOT CLAIMED.** Every number above is a LOWER BOUND. The plugin does not see
writes performed by a CHILD PROCESS, it says so itself, and this suite spawns
processes constantly - every hook test does. That limit is load-bearing here
rather than a footnote, and it is the exact limit that made LW's original finding
about this tree wrong.

### Acceptance - all met

1. The license is named by the upstream, verified, and recorded with the
   upstream, the holder and the digest of what was licensed. MET -
   `third_party/lw_write_tracer/NOTICE.md`.
2. The statement of changes is checkable rather than promised. MET - the
   round-trip assertion, watched red under mutation: a one-comment edit to the
   vendored file reddened two arms with the anchor asserted first, and the file
   was restored from a byte copy.
3. The vendored work actually runs here, proving its own control. MET - end to
   end through a real pytest subprocess, `proved` true, `negative_clean` true,
   `restored` true.
4. The first run against this tree is recorded as a result with a date. MET -
   above, and in the ledger.

## OPS-85. Two test probe files write into the live `ops/runtime/` - CLOSED 2026-09-11, NO DEFECT, and the first version of this item was wrong

Filed and closed 2026-09-11, in that order and within minutes, because the filing
was wrong and the correction is the part worth reading.

**WHAT THE INSTRUMENT SAW.** The first run of the vendored write tracer against
this suite reported two files written into the operator's live `ops/runtime/`:

    2 B  ops/runtime/_walker_probe_ignored_<pid>.bin
    3 B  ops/runtime/_walker_probe_ignored_<pid>.json

by `tests/test_tracked_walker.py`. Legion Wallpaper's own report of the same
shape called them debatable rather than clearly wrong.

**WHAT THIS ITEM FIRST CLAIMED, AND IT WAS FALSE.** That the files carry a pid in
the name, are not removed, and accumulate in the operator's live runtime
directory one pair per suite run indefinitely. That was written from the tracer's
report alone, without opening the test. It is the exact failure this repository's
standing rule exists to prevent - a claim about a file, made from a report about
that file - and it was committed to nothing only because the measurement was
taken before the commit.

**MEASURED, and it settles it.** Both probes are removed in a `finally` block by
the tests that write them, at `tests/test_tracked_walker.py:88` and
`tests/test_tracked_walker.py:160`. Counted in the live `ops/runtime/`
immediately after a full suite run that the tracer had just watched write them:
ZERO remain. The writes are real and they are transient.

**WHY THE LOCATION IS CORRECT AND MUST NOT BE "FIXED".** The thing under test is
that a GITIGNORED file stays out of the scannable view. `ops/runtime/` is
gitignored, which is why the probe goes there. A probe in `tmp_path` would not be
inside this repository at all and would be excluded for the wrong reason, turning
a real guard into decoration that passes no matter what the walker does. Anyone
arriving here with a plan to move these into `tmp_path` should read this
paragraph first.

**THE ONE RESIDUE, CONSIDERED AND DISMISSED IN WRITING.** A `finally` does not
survive a hard kill, so a process killed mid-test could leave one 2 or 3 byte
file behind in a gitignored directory. That is not worth an item, and saying so
here is cheaper than having the question re-opened by the next reader of a trace
report.

**THE GENERALISATION, which is why this stayed on the record instead of being
deleted.** A write tracer reports that BYTES MOVED. It cannot report that state
CHANGED, and the difference is the whole of `OPS-82` and the whole of this. Both
findings from the same instrument on the same day were writes that a `finally`
undid, and in both cases the instrument was working perfectly and the reading was
the error.

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
