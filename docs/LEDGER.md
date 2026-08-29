# Lanternlight ledger

The per-item record of what actually landed. One entry per item, **newest
first**, each carrying the acceptance evidence that justified calling it done.

This file exists because continuity in this project lives on disk, not in a
context window. A session that has been cleared or compacted reads the top few
entries here, plus `ROADMAP.md` and `git log`, and knows where it is. Nothing
about the work is expected to survive in conversation.

## Format

Each entry is a level-3 heading followed by its evidence:

```
### LL-0000 - YYYY-MM-DD - one-line summary of what changed

**Evidence:**
- the test, file, or command that proves it
- one line per piece of evidence
```

`ops/loop/ledger.py` writes these. It inserts new entries directly below the
marker line at the bottom of this preamble, and it writes atomically through a
temporary file, so a reader polling this file never sees a half-written entry.

## Append-only

Entries are added. They are never edited, reordered, reflowed or deleted. If an
entry turns out to be wrong, the correction is a **new entry** that says so and
names the entry it corrects. The value of a ledger is that it is a record; a
record that can be quietly revised - especially by an unattended loop - is
worth nothing.

## Do not verify an entry by its commit hash

Entries may cite a commit. Treat that citation as a hint, not as proof, and
expect a meaningful share of older hashes to resolve to nothing.

This is not history rewriting and it is not corruption. Work is done on
branches and in worktrees; when a branch is squashed on merge, or a commit is
cherry-picked onto another branch, the sha that existed when the entry was
written stops existing. The change still landed. Only its address moved.

**Verify by file and by test.** Open the file the entry names and read it; run
the test the entry names and watch it pass. Those survive squash, rebase,
cherry-pick and reclone. A hash does not. If a hash is dead and the file and
test check out, the entry is good - do not reopen the item, and do not "fix"
the history.

## Item ids

`LL-NNNN` is the convention. An id that appears in a roadmap item, a branch
name, a commit message and a ledger entry is what ties those four records to
each other, which is the whole reason ids exist.

**Two things this section used to claim are not true, and saying them anyway
hid a real defect.**

It said ids are "allocated in order". Nothing serialises allocation. Lanes work
on separate branches cut from a common base, so two lanes each asking "what is
the next free id?" get the same answer and both take it - and because each lane
appends only to its own `lanes/<lane_id>.LEDGER.md`, the two fragments merge
cleanly with nothing anywhere complaining. That happened on 2026-08-11: `ingest`
and `research` both took `LL-0023` for different work. Order is a convention the
integrator maintains by hand, not a property the machinery provides.

It said `LL-NNNN`, while the parser accepts any `### <id> - ` heading and the
safety lane's fragment had already used `SAF-0001` and `SAF-0002`, which
`integrate()` parsed without a murmur. Those two were renumbered by hand to
`LL-0026` and `LL-0027`. The format is still `LL-NNNN` and a fragment that uses
anything else will need renumbering before it lands here, but nothing enforces
it, so do not read a well-formed id as evidence of a checked one.

**"Never reused" is the part that is now enforced.** `ops.lane_state.integrate`
compares content, not just the id: an entry already present with the same text
is skipped, so the function stays idempotent and safe to re-run after a partial
merge, while an id present with DIFFERENT text raises `LedgerIdCollision` and
writes nothing. It will not renumber for you - the new id has to change in the
roadmap item, the branch and the commit message too, and quietly rewriting an
append-only record is its own defect. `ops.lane_state.duplicate_claims()` lists
every clash across this file and every lane fragment, so the collision can be
found before an integration rather than during one.

<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->

### LL-0076 - 2026-08-27 - Port block widened to 8810-8819 and the machine-wide registry recorded, which exposed a contradiction between CLAUDE.md and ARCHITECTURE.md over 8812

**Evidence:**
- OPERATOR-SUPPLIED REGISTRY, recorded verbatim in CLAUDE.md: RM Red Moon 8770-8789, LL Lanternlight 8810-8819, DS Daemon Slayer 8860-8879, RC Amberstone 8888-8895 and 2999, LW LegionWallpaper 8900-8919, CS Clockspeed 8920-8939. Lanternlight's block widens from 8810-8814.
- RE-DERIVED RATHER THAN TRUSTED: expanding all six blocks to individual ports gives 99 allocations with ZERO overlaps. Lanternlight's block is exactly 10 ports, 8810 to 8819, and 8790-8809 plus 8820-8859 remain unallocated between neighbours - 72 free ports in that span.
- A CONTRADICTION FOUND WHILE EDITING, and it predates this change: CLAUDE.md's table has always allocated 8812 to a vision / OCR service, while docs/ARCHITECTURE.md said '8812 is deliberately skipped, leaving a gap between the two surfaces most likely to grow a sibling'. Two copies of one allocation, disagreeing. ARCHITECTURE.md now defers to CLAUDE.md and records the correction rather than silently flipping.
- THE OLD BOUNDARY CLAIM IS GONE. CLAUDE.md previously justified the block by naming a partial occupied set - '8777-8783 and 8860, 8888, 8889, 8895'. That was a hand-derived subset and is replaced by the full registry; grepped to confirm no *.md outside the append-only ledger and wakeup notes still recites it.
- FOUR DOCUMENTS SYNCED, with CLAUDE.md named as the single authority so the range is not restated five times: docs/ARCHITECTURE.md, docs/OPERATIONS.md and docs/OVERLAY.md now defer to it and list only named services. docs/OPERATIONS.md and docs/OVERLAY.md gained the 8812 and 8814 rows they were missing.
- SUITE THIS RUN, clean tree with __pycache__ purged: 1297 passed / 1297 collected, ruff check All checks passed. CLAUDE.md is scanned by the ASCII and PII guards, so the edit is covered.

NOTHING BINDS ANY OF THESE PORTS. The widening is an allocation, not a service: no code in this repository opens a socket, and the rule that nothing binds at import time is unchanged.
KNOWING A NEIGHBOUR'S BLOCK IS NOT PERMISSION TO TALK TO IT, and CLAUDE.md now says so beside the table. The standalone rule at the top of that file still holds - no shared code, no shared ports, no shared keys - and the registry exists so an allocation avoids a collision, not so a service can find a sibling. A table of other projects' ports is exactly the kind of thing a later session could misread as an integration surface.
NOT ADDED, and recorded so the omission is deliberate: there is no test asserting that no source file references a port outside 8810-8819. Nothing binds a port today so it would guard nothing yet, but it is the obvious guard the moment a service is built.

### LL-0075 - 2026-08-27 - Wrap refutation - I committed a subagent's live mutation and left HEAD RED, and LL-0071's 'the second series is not in the capture' is withdrawn as a false negative

**Evidence:**
- D1, CRITICAL AND MINE. Commit d7b96ce says 'Docs only. Suite untouched.' It is not: its diffstat carries lanternlight/vision_meter.py with BLEED_CEILING changed 800 -> 10**9, and a clean checkout of it fails 1 failed / 1294 passed on test_a_scene_bleeding_through_the_plate_is_refused. Verified by stashing and re-running. Cause: an independent refuter was mid-run mutating that constant to prove the guard is not vacuous, and 'git add -A' staged its live probe. The risk was noticed earlier in the same session and the command was run anyway. Fixed in bc2aad7; the false message cannot be amended because it is pushed, so bc2aad7 is the correction.
- D5, AND IT CORRUPTED THE RECORD. LL-0071 and ROADMAP both stated that 7c's second cited series, 55 109 164 219 275 330 386 441 496 552, is NOT in panel/. IT IS. Re-verified with the shipped reader: p01185 to p01224 reads 55, 109, 164, 219, 275, 330, 386, 496, 552 - every value matching, hit 8 simply not captured at that cadence. The scratch scan sampled every THIRD frame, caught a different run that also starts at 55 (55 110 166 221, about 55.6 per hit), and generalised from one run to the whole directory. A partial search produced a false negative and it was filed as a positive claim about the capture.
- BOTH CITED SERIES ARE NOW PINNED BY TESTS. test_the_second_hand_read_series_is_reproduced_too and test_the_second_series_totals_match_the_roadmap were added against the nine real frames. Suite 1295 -> 1297.
- THE READER SURVIVED EVERYTHING ELSE, and more strongly than claimed. An independent pass scanned all 6,439 frames: zero four-digit totals, ZERO monotonicity violations at any gap, zero merged-glyph runs. Three off-fit frames it checked by rendering the mask were correct reads. It also found the reader reproduces a FINDINGS run no test touches - 12 24 37 [refused] 61 74 86 99 111 123.
- D3, a miscount: 'five mutations' was filed in three places, including the append-only ledger, while four are enumerated. The count is FOUR. Corrected in ROADMAP; this entry is the ledger's correction.
- D8, headroom measured rather than assumed: at read time over the capture the tightest margin is 0.0311 against AMBIGUITY_MARGIN 0.030, and the worst accepted distance is 0.105 in my quarter-sample and 0.115 in the refuter's full scan, against ACCEPT_DISTANCE 0.115. The module docstring claimed measured margins of '0.032 to 0.101', which were the CLUSTER LABELLING margins, not read-time ones. Corrected in place with an instruction not to widen either constant.
- D2 and D6, stale claims still shipping: vision_meter.py's docstring and ROADMAP line 1019 still carried LL-0071's refuted 'the capture cannot supply white templates', contradicting the later section of the same item. Both corrected to LL-0074's account.
- SUITE AFTER ALL CORRECTIONS, clean tree with __pycache__ purged: 1297 tests collected, 1297 passed, ruff check All checks passed.

D4, RECORDED RATHER THAN PAPERED OVER: neither MIN_GLYPH_WIDTH nor BLEED_CEILING changes a single READING across all 6,439 reference frames - the frames they would catch are refused anyway by 'matched no digit'. Their tests pin the refusal MESSAGE and the ordering of the checks, not an outcome the reader would otherwise get wrong. Kept, because a clear refusal reason is what makes a refusal actionable, but the docstring in the test now says so.
THE PROCESS LESSON, and it is the expensive one: never run 'git add -A' while another process may be writing to the tree. Stage named paths, or diff what is staged against what you intended. This session spent four passes teaching itself to verify claims and then shipped a red HEAD under a message asserting the opposite.
AND THE FALSE NEGATIVE IS THE SAME SHAPE AS THE REPO'S OLDEST TRAP. 'An empty grep is a claim about your pattern' has been in CLAUDE.md for weeks. This was an empty SEARCH stated as a fact about the world, and it went into two documents that tell future sessions an acceptance criterion is unachievable. A negative that closes an avenue needs the same evidence as a positive - the third time that lesson has been paid for in three days.

### LL-0074 - 2026-08-27 - The run-boundary fix is refuted too - clean frames are near-perfect and the real limit is a cleanliness-versus-coverage tradeoff in the capture

**Evidence:**
- BOUNDARY RULES REFUTED. Three rules derived offline from ONE cache of raw orange readings, so all three saw identical pixels: hit count decreases (the old rule) 65.5%, meter reads 0 hits 55.7%, reset-or-restart 64.9%. The reset signal is unambiguous - 313 frames read 0 hits - and it makes things WORSE. LL-0073 predicted this rule was the fix; it is not.
- AND THERE IS NO TIMING OFFSET AT ALL. Shifting the label sequence was tested in BOTH directions this time, which the previous pass did not do: -4 gives 53.2%, -2 gives 56.2%, 0 gives 65.5%, +2 gives 65.0%, +4 gives 57.3%, +12 gives 61.0%. Shift 0 is the peak, so the boundary is neither systematically early nor late.
- WHAT IS TRUE: CLEAN FRAMES ARE NEAR-PERFECT. Distance of each patch to its own class mean, bucketed by distance from a label change - within 2: median 0.0123, p90 0.189; 3 to 6: median 0.0712; 7 to 12: median 0.0068; beyond 12: median 0.0045, p90 0.0123. Frames far from a transition also carry 14% more white ink (89.5 against 77.0). The pixels and the method are fine; near-transition frames are mid-render and no labelling rule can fix them.
- SO THE READER WAS RE-SCORED THE WAY IT WOULD ACTUALLY RUN - train on clean frames, then REFUSE any glyph over an accept distance or under a margin. That is the metric the design promises, and every earlier number in LL-0072 and LL-0073 was measured on all frames including ones the reader would reject.
- THE TRADEOFF HAS NO GOOD POINT ON IT, because a long epoch yields clean frames that all spell the SAME number. train guard 0: 10 digits, 0% accepted. guard 8: 10 digits, 43.9% accepted, 72.4% correct. guard 12: 9 digits, 59.8%, 74.3%. guard 16: 6 digits, 50.9%, 76.2%. guard 20: 5 digits, 39.4%, 89.7%. Ten digits costs accuracy; accuracy costs coverage.
- NOTHING SHIPPED. lanternlight/vision_meter.py is untouched and the suite is unchanged at 1295 passed / 1295 collected on a clean tree.

IT IS A CAPTURE LIMITATION AFTER ALL, BUT NOT THE ONE FIRST FILED, and the difference matters. LL-0071 said the white field never changes - that is false and LL-0072 was right to refute it. The real constraint is the opposite: the field changes OFTEN, so only about five record epochs last long enough to yield clean training frames, and those few repeat the same digits. Same conclusion, entirely different cause, and only the second version tells a future session what capture to ask for.
THE CAPTURE REQUEST, stated concretely so it can be actioned rather than re-derived: longer stable stretches per record value - the operator pausing between runs rather than starting the next immediately - across at least ten distinct records. The existing capture has about 26 records but only about five long epochs. Nothing else needs to change: slot geometry, the previous-run labelling method and the refusal gate are all measured and working.
THREE SPECIFIED NEXT-STEPS IN A ROW HAVE NOW BEEN WRONG - data, then alignment, then boundary detection. Each was an inference from the shape of a symptom. The thing that finally located the limit was measuring the metric the DESIGN promises (accuracy on frames the reader accepts) rather than the one that was easy to compute (accuracy on every frame). Three passes were spent optimising a number the reader would never have been judged on.

### LL-0073 - 2026-08-27 - The alignment search LL-0072 specified is refuted - the white row's blocker is the LABEL's timing, and the measured ceiling is 96.8% per glyph

**Evidence:**
- ALIGNMENT REFUTED. Six variants on one cached mask set and one train/held-out split, so only alignment varied: fixed slot crop 65.5% (baseline), ink bounding box 65.4%, x-only bbox 65.5%, fixed plus a dx/dy scoring search 63.9%, bbox plus shift 64.2%, bbox-x plus shift 63.9%. Nothing moves. LL-0072 predicted this would be the fix; it is not.
- NEITHER IS ANYTHING ELSE ABOUT THE PIXELS. White threshold from >165 down to >105 gives 61.1% to 63.9%. Grid size makes no difference. Dropping outliers from each class before averaging makes no difference (62.3% to 63.3% across four cut-offs).
- PROOF 1 THAT THE LABELS ARE THE PROBLEM: the class means for (slot 0, '1') and (slot 0, '9') differ by 0.0000, with 149 and 15 members. Fifteen patches labelled 9 average to the same grid as 149 labelled 1, which can only mean those fifteen frames display a 1.
- PROOF 2, and it also measures the ceiling: excluding frames near a label change fixes it monotonically. Guard 0 -> 65.5% glyph / 39.4% frame; guard 8 -> 76.1/51.0; guard 12 -> 89.2/78.3; guard 16 -> 93.7/86.5; guard 20 -> 94.4/89.2; guard 25 -> 96.8/92.3 at median margin 0.052; guard 30 -> 96.5/91.7. So the templates and the labelling METHOD are sound and only the label's timing is wrong.
- THE TIMING ERROR IS JITTER, NOT A CONSTANT LAG. Shifting the whole label sequence to model a fixed display lag makes it monotonically WORSE - 65.5% at shift 0, 56.2% at 2, 50.1% at 6, 46.2% at 12. The record does not simply appear N frames late.
- DETECTING THE CHANGE FROM WHITE PIXELS DIRECTLY IS WORSE AGAIN, 68.2%. It finds 51 segments where there are about 26 records, because scene bleed through the semi-transparent plate creates spurious change points. Full digit coverage is recovered (10 per slot) but accuracy is not.
- LABELS SPOT-CHECKED BY EYE before any of this was concluded: the white row was rendered for frames in two epochs and read manually. The frame labelled 556 shows two top-bar glyphs then a 6-shape; the frame labelled 705 shows a 7, a two-stroke 0, and a third glyph. The previous-completed-run model from LL-0072 holds - it is only its timing that drifts.
- NOTHING SHIPPED. 92.3% per frame is not a reader, lanternlight/vision_meter.py is untouched, and the suite is unchanged at 1295 passed / 1295 collected on a clean tree.

THE NEXT STEP, now well-founded rather than guessed: the jitter is in the ORANGE run-boundary detection, not in the white row. A boundary is declared when the hit counter goes backwards, but the orange reader refuses a large fraction of frames, so a boundary is noticed at an irregular moment after it happened. Carry the counter across refused frames and require the count to plateau before declaring a run over, then re-label. The guard table puts the ceiling at 96.8% per glyph, so it is worth doing.
TWO SPECIFIED NEXT STEPS IN A ROW HAVE BEEN WRONG - LL-0071 said the white row was blocked on data, LL-0072 said the blocker was alignment. Both were inferences from the shape of a symptom rather than measurements of a cause. What actually located it was a class-mean collision nobody was looking for and a guard sweep that was cheap to run. Prefer the cheap sweep that isolates a variable over the plausible story about a mechanism.
A METHOD NOTE WORTH KEEPING: every experiment here reused one cached mask set and one fixed train/held-out split, so the numbers are comparable across variants. Re-deriving the cache per variant would have made six incomparable measurements and none of the tables above would mean anything.

### LL-0072 - 2026-08-27 - White-row groundwork - LL-0071's 'the capture cannot supply white templates' is REFUTED by me; the data covers all ten digits and the blocker is representation

**Evidence:**
- SELF-REFUTATION, and it is the main result. LL-0071 and ROADMAP 7c both said the white row was blocked on a capture in which the Progress Record changes. That generalised from the white HIT COUNT - which really is a constant 11 throughout - to the whole row. The white VALUE field varies freely: 26 distinct values appear in the reference capture (104 123 158 231 264 265 309 350 438 531 546 552 556 559 651 684 687 689 690 692 705 799 817 818 896 980), and a labelled harvest covers ALL TEN digits, slot 2 on its own covering ten. The data was there before that claim was written.
- SEGMENTATION MUST BE FIXED-PITCH SLOTS, not column runs. The white glyphs are 1px-stroke outlines, so a '1' splits into two runs and run-based segmentation returns 0, 1, 2, 3, 4, 5 or 7 glyphs for a 3-digit number. Measured from a column-occupancy histogram: white value slots at x52, x65, x78; white hit count at x200, x213; pitch 13 in both. The white 'Hit' label starts at x233 and must never be read as a digit.
- THE PROGRESS RECORD IS THE PREVIOUS COMPLETED RUN, measured from pixels: grouping frames by the previous completed run's total gives a single dominant white pattern in 22 of 26 epochs, most at 100%. That INDEPENDENTLY CORROBORATES LL-0064, which reached the same conclusion from one frame reading '42, 3 Hit' beside '0, 0 Hit'.
- THE BEST-SO-FAR MODEL WAS TRIED FIRST AND IS REFUTED BY ITS OWN OUTPUT: it makes the record DECREASE, and within one supposed epoch the first slot goes empty, then shows a 7-shape, then a 1-shape. A record cannot decrease. Checked by rendering the same slot across the epoch rather than by trusting the grouping.
- CLUSTERING WAS THE WRONG TOOL AND IS ABANDONED. Pooled and per-slot, one cluster absorbs several digits - cluster 0 alone took 1, 0, 6, 5, 4 and 9 - and 44 clusters emerged for what should be 10 shapes. It was never necessary: the record gives every patch a known label, so templates are averaged per (slot, digit) directly.
- WHAT IS LEFT IS A REPRESENTATION PROBLEM, and it is measured on a held-out half. 20x12 with a 3x3 blur: 58.8% correct, median margin 0.022. 20x12 without blur: 65.5%, margin 0.040. 25x10 without blur: 65.5%, 0.040. 25x10 with blur: 59.2%. Blur HURTS here, the opposite of the orange row, because it destroys 1px strokes. Worst confusions 1->9 (89), 5->4 (50), 6->7 (30).
- NOTHING SHIPPED, deliberately. 65.5% is not a reader, it is a guesser, and lanternlight/vision_meter.py is unchanged - suite still 1295 passed / 1295 collected on a clean tree. A reader that refuses every real frame is worse than no reader, and one that answers wrongly is worse again.

THE NEXT STEP IS SPECIFIED BY THE SHAPE OF THE FAILURE. Grid size making no difference while blur hurts points at ALIGNMENT rather than resolution: a glyph sitting a pixel or two differently inside its fixed slot smears the average the templates are built from. Align each patch within its slot before averaging - a small dx/dy search, which the orange labelling already does - and mask the plate's scene bleed before normalising. The bar is roughly 99% held-out with a margin comfortably above AMBIGUITY_MARGIN; below that the row stays unread.
THE LESSON REPEATS THE ONE FROM LL-0071, one item later and in the other direction. There it was 'derive labels from behaviour, not shape'. Here the behaviour needed was already written down in LL-0064 - 'it is the previous run's record row' - and I built and discarded a best-so-far model before using it. Reading the ledger for the ENTRY rather than for the id would have saved the detour.
AND A CLAIM MADE CONFIDENTLY ONE SESSION EARLIER WAS WRONG IN THE SAFE-SOUNDING DIRECTION. 'The capture cannot supply templates' closes an avenue; it is exactly the kind of negative that stops a future session looking. A measured null needs the same evidence as a positive, and this one had none - it was inferred from a neighbouring field.

### LL-0071 - 2026-08-27 - ROADMAP 7c partly done - the meter's ORANGE pair is read and reproduces the hand-read series exactly; the white row is a different typeface and is refused

**Evidence:**
- THE ACCEPTANCE MET, against frames nobody chose for it: lanternlight/vision_meter.py reads 10 21 31 41 52 62 72 83 93 103 from ten named frames in C:/ll-captures/2026-08-25/panel - the series read BY HAND during the 2026-08-25 session and written into FINDINGS section 11. Five other floor runs in the same capture give the same series ending 104, the rounding tie 10.35 predicts, so that corroborates rather than disagrees.
- THE PER-FIELD PLAN WORKS. Clustering normalised glyph patches per field reproduced the counts this item recorded: orange hits exactly 10, orange value 13, white value 7. The 13 orange-value clusters cover all ten digits with three duplicate variants, and keeping more than one prototype per digit is better than forcing one.
- LABELLING IS WHERE IT WENT WRONG, TWICE, AND BOTH FAILURES ARE THE SAME SHAPE. The wip's label list is by cluster CREATION ORDER, which is NOT portable across harvest runs - reusing it gave a confident, entirely wrong reading (a frame showing 103 read as 16). Reading the shapes off rendered ASCII art by eye gave a second wrong set. Both were caught only by comparing against a frame read by eye.
- WHAT WORKED IS THE COUNTER. Walking the capture in time order and recording which cluster follows which gives an unambiguous successor chain; the cluster preceding every two-glyph reading is 9, and walking back from there labels all ten. The result is checked as a BIJECTION onto 0-9. A lone cluster whose successor is 1 turns out to be the meter's '0 Hit' reset state, independently confirming the zero. Derive labels from behaviour, never from shape.
- REFUTED - 7c's stated root cause. The item says 'the same digit in two fields is the same shape at a different weight and offset'. That holds WITHIN the orange row: value clusters label onto the hit-count set with margins 0.032 to 0.101. It is FALSE across colours - the white Progress Record digits carry wide bracketed base serifs the orange digits do not have. Nearest-neighbour labelling of white clusters onto the orange set returns margins as low as 0.002, and the bijection check correctly refuses it.
- AND THE CAPTURE CANNOT SUPPLY WHITE TEMPLATES ANYWAY: its white hit count reads a constant 11 through almost all 6,439 frames, giving 3 clusters, one of which is the letter t from the Hit label. So read_panel returns the orange pair and reports progress=None - the refusal requirement applied to a whole field rather than a glyph.
- AN ACCEPTANCE DETAIL IN 7c IS WRONG. Its second cited series, 55 109 164 219 275 330 386 441 496 552, is NOT in panel/. The run beginning at 55 there reads 55 110 166 221 277 333 388 - 500 556, about 55.6 per hit against the cited 55.2. Frame p00504 was checked BY EYE at hit 3 and reads 166, agreeing with the reader. Either the series came from a different capture or it was mis-transcribed.
- GEOMETRY RE-MEASURED, and the first draft's windows were wrong: reading the whole band returned 99 and 26 for a frame showing 103, because the band carries panel chrome and scene bleed as well as digits. A column-occupancy histogram over the capture puts the value digits at x 51-89 in three slots about 13 px apart and the hit count at x 195-220 in two. Windows are now 48-92 and 193-224.
- FIVE MUTATIONS, each red in a different place: closing the accept/reject gap kills 2 tests; disabling the bleed ceiling kills the bleed test; accepting any glyph width kills the fragment test; swapping two VALUE template labels kills BOTH ground-truth tests. Every mutation script asserted its anchor matched first.
- SUITE THIS RUN, clean tree with __pycache__ purged: 1295 tests collected, 1295 passed, ruff check All checks passed, merge gate OK. Baseline 1282.

A TEST OF MINE WAS VACUOUS AND WAS CAUGHT BY MUTATING, not by reading. test_a_corrupted_glyph_is_refused_rather_than_guessed refuses with 'matched no digit' - it scores ABOVE the reject threshold, so it would still pass if the two thresholds were equal, and it therefore proved nothing about the two-threshold GAP that is the whole point of the design. The gap now has its own test, which erodes a prototype until the best distance lands strictly inside the band. Closing the gap now kills two tests instead of one.
WHAT A FRESH CLONE CANNOT VERIFY, stated rather than hidden: the reference capture is 1.1 GB of the operator's own screen and is never committed, so every real-frame test SKIPS on a machine without it. The clone-safe tests cover segmentation, all four refusal paths, and that every prototype classifies as its own digit - but nothing proves a successful read there. Synthesising a frame from the templates cannot fill that hole either: a prototype is an average of anti-aliased glyphs and a grid cell is about one pixel, so painting one back binarises it and it no longer scores like a real glyph. Tuning the synthesis until a number fell out would have tested the synthesiser. Closing this needs a reviewed, redacted single-frame fixture, which is a safety-lane call and was not taken here.
TESSERACT WAS NOT INSTALLED, as the item required. The digits are a fixed font at fixed positions and template matching handles them; the templates module is generated, 36 KB of integer coverage grids, and carries an instruction not to hand-edit it.

### LL-0070 - 2026-08-27 - OPS-7 closed - carrying an item forward is a retry, so advance_cycle no longer credits it as finished

**Evidence:**
- THE DEFECT, hit for real three times: advance_cycle(directive, item=X) defaults to complete_current=True, which credits the PREVIOUS cycle's in-flight item. When X was also the previous item - the ordinary shape of 'I did not get to this, carry it forward' - X was recorded as finished with nothing done to it. Caught during the LL-0048 wrap only because the return value happened to be printed and read, then hit again on 2026-08-26b and 2026-08-27 and worked around by hand with complete_current=False both times.
- WHY IT IS WORSE THAN ITS SIZE: completed is, in the docstring's own words, the honest answer to what the loop finished. A cold session reads it to learn what is already done, skips the item, and there is NO operation that un-completes anything. Continuity in this project lives on disk and nothing else remembers, so a silent false entry there is permanent.
- THE RULE: carrying an item forward is a retry, so X -> X credits nothing whatever complete_current says. Only X -> Y or X -> None says X is finished. complete_current=False stays as the explicit hatch for 'abandoned while moving away', which is the one case the rule cannot infer.
- ALL FOUR TRANSITIONS RUN AGAINST THE REAL FUNCTION rather than reasoned about: None -> None credits nothing and still advances the cycle; X -> None credits X; X -> X credits nothing; X -> Y credits X.
- FIVE TESTS, TWO OF THEM RED FIRST - test_carrying_the_same_item_forward_is_a_retry_not_a_completion and test_carrying_forward_twice_never_credits_the_item. The other three are NEGATIVE CONTROLS and they are what stops the cheap wrong fix: a change that simply stopped crediting anything would satisfy the acceptance and quietly destroy the record.
- THE MULTI-HOP TEST EXISTS FOR A MEASURED REASON: an item needing the game client gets carried across several sessions - ROADMAP 10 has now been carried three - and one bad hop loses it for good.
- VACUITY PROVED AS THE ACCEPTANCE DEMANDED: deleting 'and not carried_forward' reddens exactly the two acceptance tests and nothing else; deleting complete_current from the same condition reddens exactly the escape-hatch test. Anchors asserted before each mutation.
- A CLAUSE OF THE FIX WAS INERT AND WAS DELETED. The first version read 'item is not None and item == current.item'. Mutating that guard away killed NO test, because None -> None is already blocked by current.item being falsy. Removed rather than kept with a confident comment on it.
- A SECOND BRITTLE TEST OF MY OWN, caught by closing this item. tests/test_ops_ids.py::test_both_states_actually_occur_in_the_real_roadmap demanded that the real roadmap contain both an OPEN and a CLOSED OPS- heading. Closing OPS-7 left NO open ops item, so it went red on correct work. That is the same mistake as the OPS-12 status test it had already replaced: whether any ops item happens to be open is a fact about the WORKLOAD, not about the scanner. Narrowed to what is actually about parsing - real headings are found at all, and CLOSED is recognised in the wild where headings carry trailing dates and backticks a fixture does not. A closed item does not reopen, so it cannot rot the same way; the OPEN half is covered on a fixture, which is where a statement about parsing belongs.
- SUITE THIS RUN, clean tree with __pycache__ purged: 1282 tests collected, 1282 passed, ruff check All checks passed. Baseline 1277.

DOCS UPDATED AT THE POINT OF USE, not only in the roadmap: docs/HEADLESS.md step 8 and .claude/commands/loop.md step 8 both now state the retry rule, because those are what a session reads while calling the function. A rule recorded only where nobody looks mid-session is a rule that gets re-broken.
AN OBSERVED LIMIT OF THE OPS-12 GUARD, worth recording because it surfaced live while closing this item. Flipping OPS-7's heading from OPEN to CLOSED dropped its allocation count from 2 to 1 and over_allocated() briefly read [8] alone - the CLOSED heading nets against its single closure. The collision is NOT resolved; OPS-7 still names two unrelated items. The count is correct again now that this entry announces the second closure, giving 2 closures against 1 closed heading. So the guard's reading is transiently wrong DURING an edit, between closing a heading and writing the entry that closes it. Harmless because the test runs at commit time when both halves are written, but a session that runs the detector mid-edit should not be alarmed by it.
THE HABIT THIS ITEM ADDS: verify your own defensive code with the same mutation discipline as the thing it guards. The inert clause looked like prudence and was decoration, and only mutating it showed the difference.

### LL-0069 - 2026-08-27 - A refuter could not overturn LL-0068 but found the new scanner was fence-blind - the same bug OPS-9 closed, rebuilt in a module written the day after

**Evidence:**
- THE PASS: one out-of-domain refuter, eight numbered claims, instructed to default to REFUTED. It confirmed the arithmetic everywhere - re-derived OPS-7=2, OPS-8=2, OPS-9=1, OPS-12=1, over_allocated={7,8}, next_free_id=13 by hand and got the same answers as the module - and found three defects in what surrounded it.
- D1, THE SERIOUS ONE, AND IT IS A REPEAT OFFENCE. ops/ops_ids.py did its own line matching with no fence tracking, so a worked example inside a code block reads as a live heading. The refuter BUILT the false positive: a fenced example of an item heading, beside a genuine heading for the same id, reports that id as over-allocated. (Written with a placeholder rather than a number on purpose - see the note below.) docs/LEDGER.md line 16 already carries a fenced entry template that matches the ledger-heading pattern, inert only because it happens to carry no id and no closure word.
- WHY THAT IS WORSE THAN A NEW BUG: OPS-9 / LL-0038 was this exact defect - the heading GUARD and the heading PARSER disagreeing because only one tracked fences - and its stated conclusion was that there must be ONE fence scan every reader shares. ops_ids.py was written as a THIRD private reader, in a repository whose own ledger records why not to, one day after that ledger entry was re-read.
- D1 FIXED BY SHARING THE SCAN, not by patching a second copy. ops/mdscan.py now holds the one CommonMark fence walk - a fence closes only on the same character, a run at least as long, and no info string; an unclosed fence is REPORTED rather than silently swallowing the file. ops/lane_state.py and ops/ops_ids.py both use it, and lane_state's duplicate _fence_marker and _FENCE_MARKS were DELETED rather than left beside it.
- THE EXTRACTION IS PROVEN FAITHFUL BY THE TESTS THAT ALREADY EXISTED: tests/test_lane_state.py carries 29 fence assertions including tilde fences, unbalanced fences, and 'a fence is closed only by the delimiter that opened it'. All pass against the extracted module unchanged, which is what makes this a refactor rather than a rewrite.
- TDD ON THE FIX: three tests written first and watched failing - a fenced roadmap heading is not an allocation, a fenced ledger heading is not a closure, and a real heading AFTER a closed fence is still found. The third is the one that matters: a fence-aware reader that swallows the rest of the document would pass the first two.
- D2, AND IT IS AN UNDERSTATED CAVEAT, WHICH THIS PROJECT CALLS A LIE IN THE ARTIFACT. The docstring admitted the guard scores 0 for OPS-4. Re-measured independently: OPS-4, OPS-6, OPS-10 and OPS-11 all score 0 - 4 of 12 ids, not 1. OPS-6 is called 'THE ONLY OPEN OPS ITEM' in docs/LEDGER.md and is invisible to the guard. Corrected in the module docstring and in ROADMAP, with the mitigating fact stated too: next_free_id uses spent_ids, which counts any mention anywhere, so all four are still disqualified from being handed out.
- D3, A TABLE STALED BY ITS OWN COMMIT. The docstring said 'checked against the repository as it stood on 2026-08-27' and listed OPS-12 as closures 0 / open 1 / closed 0. Writing LL-0068 and closing the heading made it closures 1 / open 0 / closed 1 in the same commit. The score is still 1 but the derivation was wrong. The table is replaced with the SHAPE of the rule and an instruction to re-derive rather than cite.
- D4, MINOR AND CORRECTED: 'four mutations, the regex one kills 6' was measured against an earlier draft of the test file. Re-measured against the final code - over_allocated -> {} kills 6, ledger_closures -> {} kills 7, dropping open_headings kills 4, a never-matching heading regex kills 8, and a new mutation making roadmap_items ignore fences kills 2. Five mutations, no survivors.
- D5, FOUND BY DOGFOODING WITHIN A MINUTE OF THE FENCE FIX LANDING, and it is the one a refuter did not find. This entry's own heading reads '... the same bug OPS-9 closed, rebuilt ...' - a sentence in which 'OPS-9 closed' is subject and verb. The closure pattern accepted any id anywhere in a heading containing the word 'closed' anywhere, so it credited that as a SECOND closure of OPS-9 and the real-repository guard went red with [7, 8, 9]. A heading that TALKS about an id has not allocated it. The pattern is now anchored: a summary must BEGIN with the id, or a list of them, then 'closed' - which is the convention every genuine closure already follows, LL-0042's three-id heading included. A false positive is worse than a missed one here: the first time a red means 'you wrote a sentence' rather than 'you reused an id', somebody adds an exemption and the guard stops being read.
- D6, same session, same shape: spent_ids counts any mention anywhere, so writing a worked example in ROADMAP.md with a real number in it SPENT that number and pushed next_free_id past it - burning an id on a hypothetical and leaving a future reader hunting for an item that never existed. Both mentions reworded to a placeholder. Note this line itself had to be rewritten twice: the first draft documented the problem by quoting the offending number, which spent it again. Documented in the spent_ids docstring: write examples with a placeholder, not a digit.
- SUITE THIS RUN, clean tree with __pycache__ purged: 1277 tests collected, 1277 passed, ruff check All checks passed. Baseline 1253. (1274 while this entry was being drafted; D5 and D6 below added three more.)

WHAT THE REFUTER EXPLICITLY DID NOT OVERTURN, which is worth recording because it was the judgement call the pass was asked to challenge: tests/test_ops_ids.py's KNOWN_COLLISIONS = {7, 8} is not the 'checked-in list of spent ids' the acceptance forbade. The acceptance forbade a stored list as the SOURCE of the id set; this is an expected-value assertion on the OUTPUT, and it was proven bidirectional - a stale spent-list silently permits a collision, while a stale KNOWN_COLLISIONS fails loudly in both directions.
THE PATTERN ACROSS THREE REFUTATION PASSES IS NOW UNAMBIGUOUS. LL-0064: zero arithmetic errors, eight bad readings. LL-0067: zero arithmetic errors, one PII hole opened by the fix. LL-0069: zero arithmetic errors, one repeat of a closed bug plus two overstated documents. Verification effort aimed at the numbers keeps finding nothing, because the numbers keep being right. The defects live in scope, in blind spots, and in what the prose claims.
AND THE SPECIFIC FAILURE MODE TO CARRY: a module written to enforce a rule can violate a DIFFERENT rule the same repository already closed. Reading docs/LEDGER.md for OPS ids on 2026-08-27 meant reading LL-0038's heading beside LL-0039's and LL-0040's, and still writing a fence-blind parser. Grepping the ledger for an id is not the same as reading what the entry says.

### LL-0068 - 2026-08-27 - OPS-12 closed - the OPS- namespace gets the allocator it never had, and reusing a spent id now fails a test in both directions

**Evidence:**
- THE GAP: unlike LL- ids, which ops/loop/ledger.py hands out and collision-checks, an OPS- id was picked by a human reading ROADMAP.md. Numbering resumed from the highest id visible among the OPEN items, so OPS-7 and OPS-8 were reissued over items LL-0039 and LL-0040 had closed on 2026-08-12. The ledger already knew; nothing asked it.
- NOTHING IS CHECKED IN, which the acceptance required explicitly. ops/ops_ids.py recomputes spent_ids() from ROADMAP.md and docs/LEDGER.md on every call. next_free_id() returns max(spent)+1 - above the maximum, never into a gap, because a gap means an id was retired and reissuing it re-creates the confusion. It answers 13 today.
- WHAT COUNTS AS ALLOCATION, since an id appears in prose constantly and prose is not allocation. Exactly two sites: a top-level '## OPS-<n>.' ROADMAP heading, and a ledger ENTRY HEADING announcing a closure. One item normally produces both over its life, so a CLOSED heading is read as the same item as its closure: allocations = closures + open_headings + max(0, closed_headings - closures).
- THE FORMULA WAS CHECKED AGAINST THE REAL DOCUMENTS BEFORE BEING TRUSTED, and it reproduces the hand-derived table exactly: OPS-9 scores 1 (one closure, no heading), OPS-12 scores 1 (heading, no closure), OPS-7 scores 2 (LL-0039 plus an OPEN heading), OPS-8 scores 2 (LL-0040 and LL-0066 plus a CLOSED heading). Both real collisions caught, no correctly-numbered item flagged.
- ACCEPTANCE DEMONSTRATED AGAINST THE REAL ROADMAP, not only fixtures. Planting '## OPS-9.' - an id LL-0038 closed on 2026-08-12 - turned the guard red with 'expected: [7, 8] / found: [7, 8, 9]' and a message naming ops_ids.next_free_id(). Reverted, green.
- AND IN THE OTHER DIRECTION, which is the half that stops the exemption rotting: renumbering the OPEN OPS-7 item to 13, simulating a resolution, ALSO turned it red - 'expected: [7, 8] / found: [8]'. The known-collision set is a record of a measured state, not a list of spent ids, and it fails on a third collision AND on a repair. Same shape as lane_state.stale_claims().
- FOUR MUTATIONS, each watched killing a different set: over_allocated -> {} kills 6 tests; ledger_closures -> {} kills 7; dropping open_headings from the formula kills 4; breaking the heading regex kills 6. The regex mutation's first attempt DID NOT APPLY and its anchor assert caught it, rather than letting a non-mutation read as a survivor.
- ONE FALSE-POSITIVE RISK CHECKED RATHER THAN ASSUMED: the closure text added to ROADMAP.md quotes the very heading pattern the scanner matches. Re-derived after writing it - roadmap_items() still finds exactly 7, 8 and 12, and over_allocated() still reports exactly {7, 8}. The backticked mentions sit mid-line so the line-anchored pattern skips them. LL-0038 is the entry about a parser that did not respect its own document's structure.
- SUITE THIS RUN, clean tree with __pycache__ purged: 1271 tests collected, 1271 passed, ruff check All checks passed. Baseline 1253. The count moved 1270 -> 1271 after this entry was first drafted, because one test in the new module pinned OPS-12's own OPEN status and went red the moment OPS-12 was closed - it was split into a fixture-based discrimination test plus a non-vacuity check that names no item. Corrected here rather than in a follow-up entry because nothing had been committed yet, and committing a count known to be wrong is worse than editing a draft.

THE COUNT MAY UNDER-REPORT AND MUST NEVER OVER-REPORT, and that is a decision rather than a limitation. OPS-4 was closed by an entry whose heading avoids the word 'closed', so it scores 0 here and a second OPS-4 would go unflagged. Under-reporting costs a missed warning; over-reporting makes the guard red on correctly-numbered items, and a guard that cries wolf is one people learn to override - which is the same argument OPS-8 made about the merge gate.
A SECOND COPY OF THE ROSTER EXISTS, found the hard way: adding tests/test_ops_ids.py to the ops lane's owns tuple made .claude/commands/lane-ops.md stale and tests/test_lane_contract.py went red until scripts/write_lane_contracts.py regenerated it. The failure was correct and the message named the fix. Worth knowing before editing ops/lanes.py: the roster is not the only place the roster lives.
RENUMBERING IS STILL REFUSED. OPS-7 and OPS-8 keep their double meaning, signposted at each reference, on LL-0040's own reasoning that renumbering records one piece of work under two ids. What changed is that a THIRD collision can no longer happen quietly.

### LL-0067 - 2026-08-26 - An independent refuter could not overturn LL-0066 but found the fix had opened a PII hole - a name filter that hid TRACKED files from the guard

**Evidence:**
- THE PASS: one out-of-domain refuter, read-only, instructed to default to REFUTED, given eight numbered claims to attack. It confirmed all eight and found three defects the self-run work had not.
- D1, AND IT IS A HYGIENE HOLE THE FIX ITSELF OPENED. _is_foreign_probe() filtered by NAME across the whole candidate list, tracked files INCLUDED, while _own_probes() only re-added from the root's iterdir(). The refuter proved it: git add -f docs/_guard_probe_notes.md carrying a SteamID64 gave 'scanned: False, REPO-WIDE PII GUARD: GREEN'. .githooks/pre-commit does no content scan, so nothing else would have caught it.
- D1 FIXED, not filed. A name test cannot tell a concurrent suite's scratch file from a tracked file under the same name, and on the git path .gitignore already draws that line correctly - it removes untracked probes and leaves tracked files alone. The filter now applies ONLY on the non-git fallback walk, which is the one path that has no .gitignore to consult.
- TDD ON THE FIX: TestTheProbeFilterCannotHideATrackedFile builds a throwaway git repo in tmp_path, commits a file named _guard_probe_notes.md, asserts git really tracks it BEFORE asserting anything else, then requires iter_scannable_files to yield it. Watched failing first - 'assert _guard_probe_notes.md in set()'. The real repository's index is never touched.
- BOTH DIRECTIONS MUTATED after the fix. _is_foreign_probe -> False reddens exactly test_a_foreign_probe_is_filtered_on_the_non_git_fallback_path; re-applying the filter to the git listing - the D1 defect itself - reddens exactly test_a_tracked_file_with_a_probe_name_is_still_scanned. Each mutation kills one test and a different one.
- D2, a tally: LL-0066 and ROADMAP said 'all THREE git-based walkers'. Re-derived by grep, there are FOUR --exclude-standard sites - ops/lanes.py, tests/_tracked.py, tests/test_lane_state.py and tests/test_tracked_walker.py:54. The mechanism holds; the count was wrong. Corrected in ROADMAP and .gitignore. LL-0066 is append-only and stands as written.
- D3, a stale tense: ROADMAP's OPS-8 preamble stated '1244 passed' in the present tense under a CLOSED heading. Reworded to say it was the count at the time.
- SUITE THIS RUN, on a clean tree with __pycache__ purged: 1253 tests collected, 1253 passed, ruff check All checks passed. 1252 was the count before the D1 regression test.

A SECOND DEFECT, FOUND BY EYE DURING THE CORRECTION AND WORTH MORE THAN D2 OR D3: the script applying the D2 fix reused a variable named 'new' from an earlier block, so when the first anchor matched, .gitignore was rewritten with a PARAGRAPH OF ROADMAP PROSE in place of a comment. Those lines carry no leading '#', so git would have read each as an IGNORE PATTERN. Nothing in the suite could have caught it - the file is valid ASCII, carries no identifier, and every test stayed green. Caught only because the verifying grep for the new text came back empty and the fallback sed printed the file. Restored with git checkout and redone; .gitignore now has 116 pattern lines and not one contains a space.
THE LESSON REPEATS LL-0064's: the arithmetic was sound and the READINGS were not. Zero errors were found in the concurrency measurement, the mutation results or the acceptance numbers. All three defects were about SCOPE - which files a filter touches, how many call sites exist, what tense a sentence is in.
AND THE SHAPE OF D1 IS THE ONE THIS PROJECT KEEPS PAYING FOR: a fix for one problem quietly widened a guard's blind spot. OPS-8 was about a guard going red for the wrong reason; the fix for it made a guard go GREEN for the wrong reason, which is strictly worse. A self-run pass had already mutated three ways and missed it, because every mutation asked 'does this still catch what it caught' and none asked 'does this now MISS something it used to catch'.

### LL-0066 - 2026-08-26 - OPS-8 closed - the suite is safe under concurrent pytest, and the mechanism filed for it was wrong about the dominant case

**Evidence:**
- MEASURED BEFORE ANY FIX, because a filed mechanism is a hypothesis: five concurrent FULL suites went red in 9 of 10 runs, across five different tests. NEITHER of the two tests OPS-8 named as its casualties failed even once. LL-0064 recorded 3-in-12 and 2-in-5; at 5-way concurrency it is far worse than that.
- THE DOMINANT MODE IS COLLISION, NOT OBSERVATION. Every guard probe was planted at a FIXED name at the repository root, so two suites planted the same file and the first to reach its finally unlinked the other's evidence mid-scan. test_no_pii.py's two pipeline probes were the top casualties at 8 of 10 runs each. The filed direction - one process's scan seeing another's probe - is real but rare; it showed up once, as test_the_scannable_view_is_a_superset_of_the_authored_view failing with a foreign probe appearing between its two walks.
- A THIRD FACE, Windows-only: finally-unlink raises PermissionError [WinError 32] while another process holds the same path open, because Python's open() does not share delete.
- FIX, with the probes still at the real repository root and neither guard weakened - only the NAME changed. tests/_tracked.py gains probe_path(stem) returning _guard_probe_<pid>_<stem>. .gitignore ignores _guard_probe_*, which is ONE lever for all THREE git-based walkers in this repo (tests/_tracked.py, ops/lanes.py, tests/test_lane_state.py) because each takes its untracked pass with --exclude-standard - patching them one at a time would have rebuilt the two-copies-of-a-rule trap tests/_tracked.py exists to prevent. _published() adds THIS process's own probes back so a probe is still scanned by the guard that planted it, and filters foreign probes on the non-git fallback walk that .gitignore cannot reach.
- ACCEPTANCE: 24 consecutive green runs at 6-way concurrency of the full suite, against the measured 9-of-10-red baseline. Sequential suite 1252 passed / 1252 collected on a clean tree with __pycache__ purged, ruff check clean, merge_gate.verify OK against a baseline of 1244 measured with --collect-only before any work was dispatched.
- THREE MUTATIONS, each watched going red on a DIFFERENT guard. _own_probes() returning [] kills 5 tests including BOTH original test_no_pii.py pipeline probes, so the migrated probes are still genuinely scanned. Deleting the .gitignore line kills only the test_lanes.py orphan test - correctly, since ops/lanes.py has no filter of its own and rests entirely on that rule.
- THE MUTATION THAT SURVIVED, and it mattered: _is_foreign_probe() returning False killed NOTHING. The fallback filter was decoration, because every test ran on the git path where the ignore rule had already removed the file. test_a_foreign_probe_is_filtered_on_the_non_git_fallback_path was written for it and the same mutation now dies. Found only by mutating; the suite was green either way.

THE TRAP THIS ITEM SET FOR ITS OWN FIX, and it is the sharpest thing here: the first version of the regression tests named their foreign probe _guard_probe_0_... - a FIXED path, on the reasoning that pid 0 is never a live process and so can never be mistaken for a real suite's. Six concurrent suites then fought over that one file and it died on WinError 32. 17 of 18 green, red for EXACTLY the bug under test, reproduced inside the test for it. Nothing sequential could have seen it. A foreign probe now carries <prefix><pid>other_ - foreign to every walker because it does not match <prefix><pid>_, and unique on disk.
SECOND-ORDER LESSON, consistent with LL-0064's: verification effort had again been aimed at the wrong layer. The filed mechanism's ARITHMETIC was never in question; its READING of which tests failed was wrong, and re-running the measurement rather than trusting the write-up is what corrected it. Point verification at the readings.
A WINDOWS TRAP RE-PAID: Python write_text turned all five edited files fully CRLF against a .gitattributes that mandates LF on disk. git diff --stat hid it because text=auto normalises the blob; only grep -c for CR showed it. Converted back with write_bytes. CLAUDE.md already names this and it still happened.
NEW OPEN ITEM OPS-12, filed rather than fixed: OPS-7 and OPS-8 EACH name two unrelated items. OPS-7 was spent on a fragment-path defect (LL-0039) and OPS-8 on a ledger-collision diagnosis (LL-0040), both closed 2026-08-12, then both ids were reallocated. OPS-1 to OPS-6 and OPS-9 to OPS-11 are used once, so numbering resumed from the highest OPEN id rather than the highest ever allocated. Renumbering is refused on LL-0040's own reasoning - it records one piece of work under two ids - so all four references are signposted instead and the acceptance is a test that fails when an already-spent OPS- id is allocated, deriving the spent set by walking the documents at run time rather than from a checked-in list.

### LL-0065 - 2026-08-26 - Capture pruned 4.5 GB -> 3.0 GB at the operator's request, by the downsample-record-delete method the frames/ deletion set as precedent

**Evidence:**
- LOSSLESS, 220 MB: 76 superseded log generations. The game appends within a session, so every deleted generation was verified a STRICT BYTE PREFIX of the one superseding it - and re-verified at the moment of deletion, not just in a survey pass. Plus one of two byte-identical backup copies.
- A MANIFEST.txt was written into each logs/ directory FIRST, carrying every original name, size, sha256 and mtime. LL-0056's measured negative is 'N generations at these timestamps, not one a *-backup-*.log' - that claim lives in the listing, so the listing was preserved even though the bytes were not.
- 278 MB: the 1,775 frames of 2026-08-25/panel2/ that duplicate 2026-08-25/panel/. Two simultaneous pollers on one HUD rectangle; panel/ runs to 19:51:31 and panel2/ starts 19:34:50. Near-simultaneous pairs were compared and showed identical meter content BEFORE deleting. panel/ was the copy kept because ROADMAP 7c names that exact path as its ground truth. panel2/'s unique window is untouched.
- 1,084 MB: 2026-08-25b/reanchor/ downsampled. All 320 full-screen frames were reduced to meter crops and half-scale JPEGs in reanchor_small/ before any original was removed. Verified afterwards that 143/10, 129/9, 42/3 and 28/2 - the four readings FINDINGS 13 rests on - remain legible in the derived crops.
- 24 frames kept at FULL resolution, chosen by a near-duplicate filter erring toward keeping: every distinct equipment view, including item tooltips with stat text and the Affix Details screen. Kept because equipment is SERVER-SIDE (13.1), making them the only record anywhere of the loadout behind that run.
- Final: 4.5 GB -> 3.0 GB. Nothing cited by any published finding was removed.

WHAT WAS DELIBERATELY NOT PRUNED, and why, since a future session will see the disk still at 96%: 2026-08-25/panel (1.1 GB) is named in ROADMAP 7c's acceptance; scene/ (301 MB) is the recorded independent variable for the ten-point curve; sheets/ (60 MB) is described as the contact sheets the numbers were read off; talents/ (244 MB) holds the tooltips behind the OBSERVED_IDS talent section. Deleting any of them destroys evidence behind a published claim.
WHAT A FUTURE SESSION CAN NO LONGER DO: re-crop the reanchor capture at a different rectangle, or read equipment text from a frame outside the 24 kept. Everything already published from it survives.
The method is the point and it is now twice-used: downsample first, write the record, verify the derived copy still carries the load-bearing readings, THEN delete. A raw survey said the log generations were redundant by size; the byte-prefix check is what made that safe to act on.

### LL-0064 - 2026-08-26 - FOUR INDEPENDENT refuters on LL-0056 through LL-0063 - the arithmetic held everywhere and eight filed READINGS and inferences did not

**Evidence:**
- Dispatched on disjoint slices, read-only, instructed to default to REFUTED. This is the out-of-domain check LL-0058 recorded as MISSING; it is now done and it found what a self-run pass could not.
- WHAT SURVIVED: LL-0056 and LL-0057 confirmed in full. A refuter re-derived the 1225 baseline from a worktree at 7661391^, got 1244 at HEAD, re-ran ALL FOUR mutations independently and observed 1/4/1/10 failures - an exact match to what was filed - green on restore. sha256 1c44235c..., 23 archived generations, span 18:38:20-20:28:25, gaps only 300/301, zero non-MistfallHunter.log entries, all re-derived. LL-0062's and LL-0063's arithmetic confirmed exactly: round-to-nearest empty at max-lower 257/18 vs min-upper 85/6; truncation empty at 43/3; 143/104 = 11/8; sum(s-1) over a 1,2,3,4,5,5,5,5,5,5 build = 30.
- REFUTED 1 - 'not a patch regression' (LL-0059). Every prior observation of requestEnterStandaloneLevel and of the transient save was on buildid 24619162; this run is 24813185. Build and mode are PERFECTLY CONFOUNDED and a log with no StandaloneLevel is exactly what a patch removing the call would produce. The claim is withdrawn in FINDINGS 12.1, heading included.
- REFUTED 2 - the DA_DungeonSettings_Classic binding. Verified directly: the string occurs EXACTLY TWICE in the whole log, 02:29:05 and 02:29:31 UTC, 27 minutes BEFORE this run's EnterBattle, and both sit inside 'Puerts: Error: call TsConstruct of DA_DungeonSettings_Classic(...)' - construction-failure lines. OBSERVED_IDS had filed them as 'the run's settings data asset, during the log, during the run' and named a whole section 'Classic dungeon run' off it. Both false. The run's settings asset is UNKNOWN.
- REFUTED 3 - the hit-2 'sampling gap' (LL-0062). Frames f0159 and f0160 both plainly read 28, 2 Hit. The dash and its 'two hits inside one 0.5 s interval' explanation were a fabricated justification for absent data that was not absent. Re-verified at 3x zoom. The recovered reading STRENGTHENS the contradiction: 28 at 2 hits forces v < 14.25 against the v >= 14.2778 that 129 at 9 hits forces.
- REFUTED 4 - the Progress Record 'corroboration'. It already read 42, 3 Hit in the reset frame at 22:55:17 beside 0, 0 Hit, before any hit of that run landed. It is the previous run's record row, so citing it as a second source for the same event was circular.
- REFUTED 5 - a delta transposition. Hits 3-10 were filed as 14,14,15,14,15,14,15,14; the truth is 14,15,14,14,15,14,15,14. BOTH SUM TO 115, so a check against the total would have passed it. A sum is not a check on an ordering.
- REFUTED 6 - the stack table (LL-0063). Nine ten-hit runs exist, not four. Re-derived: 1 -> 135, 135; 2 -> 135; 3 -> 136; 4 -> 136; 5 -> 137, 139, 139, 139. So '2 to 3 -> 136' is wrong for 2, a 4-stack run was missed entirely, and 139 replicates three times rather than once. Monotonicity SURVIVES and is cleaner - n=4 at five stacks.
- REFUTED 7 - 'bare icon = one stack'. Every bare observation sits at zero hits, which is equally consistent with 'no stacks yet'. Withdrawn as UNVERIFIABLE.
- REFUTED 8 - two ROADMAP 7c claims. 'x=190 lands in empty space in every frame examined' is false: 109 of 6,439 frames carry ink at x=190, with 45 orange and 61 white column runs straddling it. And the white hit-count row (432 glyphs, 0% matched) had been omitted from the match table, which flattered the result.
- Suite after every correction: 1244 passed, 1244 collected, ruff clean, observed on a clean tree with __pycache__ purged.

THE DEFECT THAT PROVES THE POINT: LL-0058 claimed it had corrected the creation-time over-claim. It corrected FINDINGS 11.12 and ROADMAP 4c and MISSED lanternlight/armwatch.py's module docstring, which still read 'has never changed' with no NTFS caveat - in the same commit. That is this repo's recorded failure mode, a fix applied in one of the two places the defect lived, landing on the very entry written to warn about it. A self-run pass could not see it; an independent one did.
THE SHAPE OF THE FINDINGS IS THE LESSON: not one arithmetic error was found in four passes. Every defect was a READING or an INFERENCE - a misread frame, an invented explanation for a gap that did not exist, a circular citation, a binding read off an error line, a conclusion that felt less exciting mistaken for a conclusion that was supported. Verification effort had been aimed at the arithmetic, which was already sound.
NEW OPEN ITEM OPS-8, filed rather than fixed: the suite is deterministic sequentially (five clean runs of 1244) but goes intermittently red when several pytest processes run at once, because tests/test_no_pii.py plants probe files at the repository root while tests/_tracked.py walks that root. It cost two refuters false failures. It matters because ops/merge_gate.py re-runs pytest and CLAUDE.md mandates a parallel multi-agent workflow, so the gate can redden for reasons unrelated to the work it gates.
COST AND VALUE: four refuters, roughly 480k subagent tokens, about 19 minutes wall clock. They overturned two published conclusions and six evidence rows before any of it hardened into the next session's ground truth.

### LL-0063 - 2026-08-25 - A stack buff the OPERATOR spotted explains the broken solves - and it means 11.7's 'constancy tracks the clamp' may be a rounding artifact

**Evidence:**
- OPERATOR FOUND IT, not the analysis: he reported an icon climbing to 5 while he keeps hitting the same target inside a time limit, with damage 'gently nudged' upward, and located it centre screen above the energy bar.
- CONFIRMED IN THE CAPTURE: cropping x 600-690, y 600-665 of the 1280x720 wide frame renders the icon and its stack count. Joining that crop to the meter crop by wall clock yields one row per hit carrying BOTH cumulative damage and stack count - the class-id frame join applied to two regions of one frame.
- READING RULE: the count runs 1 to 5 and holds at 5. At ONE stack no digit is rendered - the icon appears bare - so 'no number' means one, not zero.
- OPERATOR-DESIGNED EXPERIMENT: runs deliberately held to a maximum of 1, 2, 3, 4 and 5 stacks, slower cadence, no movement, letting the buff reset between. Ten-hit totals at one fixed floor distance - 1 stack: 135; 2-3 stacks: 136; 5 stacks: 137 and 139. Monotone in stack count.
- MAGNITUDE, and it is small: under damage = base*(1 + (s-1)c), a run building 1,2,3,4,5,5,5,5,5,5 totals (10+30c) against 10 pinned at one stack, so the observed ratios imply c ~ 0.5% to 1% per stack, about +2% to +4% at five.
- NO COEFFICIENT PUBLISHED. The spread is 135 to 139 on integer totals near 137, while same-distance run-to-run variation was already 137 against 138 in the same session. The signal is barely above the noise.
- Written up as docs/FINDINGS.md section 15; section 14.4's advice corrected in place.

14.4 WAS HALF WRONG AND IS CORRECTED: it proposed the floor as the decisive test because a clamp makes positional drift harmless. The drift reasoning holds; what it ignored is the display. At ~13.5 per hit a ~1%-per-stack effect is ~0.135 and rounds away, so the floor is INSENSITIVE rather than decisive - visible in the joined rows as stacks climbing 2,3,4,5 beside deltas flat on 14. The ceiling (~90 per hit, where 1% is 0.9) is the instrument.
THE CONSEQUENCE FOR 11.7, and it is not small: 11.7 reports a constant per-hit value fitting every FLOOR run and no off-floor run, and reads that as constancy being a property of the clamp. A ~1%-per-stack buff reproduces that split exactly WITHOUT any distance term - invisible at 10.35 per hit, visible at 55-69. The observation stands; the INTERPRETATION is now contested between the operator's positional variance and this buff. The ten-point curve itself is unaffected - those totals are measured.
WHETHER THE BUFF PREDATES TONIGHT IS UNMEASURED. Focus Fire was taken this session and its tooltip ('Rapid Arrows increase the Damage Multiplier with each hit on the same enemy') matches the shape - but the operator was NOT using Rapid Arrows: inter-hit intervals of 2.27-2.87 s are drawn shots, and Rapid Arrows is Volley. So either the talent's scope exceeds its tooltip, or this is a base mechanic that was always there and too small to see at 10.35 per hit. The logs that could settle it were destroyed before anything archived them.
NEXT MEASUREMENT: at the CEILING, ten hits pinned at one stack against ten allowed to reach five, without moving - the difference should be 3-4 display units per hit rather than a fraction of one. To separate talent from base mechanic, fire ten hits alternating between two targets; 'the same enemy' implies the stack resets per enemy.

### LL-0062 - 2026-08-25 - A re-anchor run after an item change REFUSED to solve constant, so it cannot attribute 143-vs-104 to gear - and equipment turns out to be server-side

**Evidence:**
- WHY IT WAS RUN: FINDINGS section 11 never records which loadout produced 10.35. It scopes its claims carefully ('the same weapon', and it disclaims other weapons/arrows/targets/builds) but the configuration itself was never written down, so the whole ten-point curve rested on an unstated baseline that an item change would silently invalidate.
- EQUIPMENT IS SERVER-SIDE, measured across the change: Deck.sav 7 generations all byte-identical INCLUDING after the change; CampData_<userId>.sav 8 generations all byte-identical despite the game rewriting the file; only Scav.sav changed content, at 21:31, and it flipped straight back. So a loadout baseline can only be pixels.
- THE RUN: meter reset observed at 22:55:17 (0, 0 Hit), ten body shots, panel captured at 2 fps. Series by hit count - 1:14, 2:(sampling gap), 3:42, 4:57, 5:71, 6:85, 7:100, 8:114, 9:129, 10:143.
- NO CONSTANT PER-HIT VALUE FITS, under either display model. Round-to-nearest is empty: 129 at 9 hits forces v >= 14.2778 while 42 at 3 hits forces v < 14.1667. Truncation is empty by a hairline, both bounds meeting at exactly 43/3.
- THE CONTRADICTION IS NOT A MISREAD: both binding readings (42 at 3, 129 at 9) were re-read individually at 3x zoom, and the solve was re-run against only the individually-verified readings, where the contradiction survives unchanged.
- THE DELTAS LOOK CONSTANT AND ARE NOT EVIDENCE - 14, 14, 15, 14, 15, 14, 15, 14, exactly the one-wobble a constant value produces through a rounding display. This is 11.7's trap and only the solve separates the cases.
- PANEL RECTANGLE LOCATED: the Total Damage value and hit count occupy x 2085-2330, y 468-520 at 2560x1440. A cropped poller costs about 150 KB a frame against 3.1 MB full-screen, a 20x saving.
- The Progress Record independently read '42, 3 Hit', corroborating the mid-run 42-at-3 from a second on-screen source.

WHAT IS DELIBERATELY NOT CLAIMED: that 143 vs 104 (ratio 1.375) is a gear effect. Constancy is the measured signature of the FLOOR (11.7), this run admits none, so it was fired from inside the floor breakpoint - distance is confounded with gear and NEITHER can be attributed. Reporting 1.375x as a gear multiplier would have been the exciting wrong answer.
TWO CANDIDATE CONFOUNDS, neither excluded: pacing drift (143 sits in the never-measured gap between 7 paces at 231 and 8 paces at 104), and an unfrozen target (the room can freeze bots; a moving target varies distance shot to shot and no such run can ever solve constant). The freeze state was not checked during this run.
NEXT ATTEMPT IS SPECIFIED: freeze the bot, stand clearly past the old breakpoint at 12-14 paces, fire ten body shots. Constant at ~10.35 means gear did not move the floor; constant at another value means it did, and that is a real finding; no solution again means the target was moving.
The run was still worth its disk: the loadout is on pixels for the first time, and the panel rectangle it located makes every future capture 20x cheaper.

### LL-0061 - 2026-08-25 - Blackarrow talents read at level 5 - six new nodes verbatim, a slot-state reading rule, and Battle-fed proven inert from the screen rather than assumed

**Evidence:**
- Method: tools/frame_poller.py at 2 s for a bounded 360 s while the operator hovered nodes; 164 frames, 244 MB, at C:/ll-captures/2026-08-25b/talents/, not committed (full-screen, shows the account panel). Every name and effect line read off a rendered tooltip.
- Level confirmed on screen: Lv. 5, three arrow slots bound (Z/X/C), three skills equipped.
- Archer's Arrow Enhancement 1, all with an Activate bar - Astound (knockback distance of fully drawn Concussive Arrows), Sepsis (Damage Multiplier of fully charged Splatter Arrow's splash), Lightning Spread (chaining range of lightning from a fully drawn Lightning Arrow).
- Mighty Archer, all with an Activate bar - Unstoppable Edge (Sky Piercer's Physical Damage partially converted to True Damage), Focus Fire (Rapid Arrows increase the Damage Multiplier with each hit on the same enemy), Powerful Scattershot (knockback into an obstruction Stuns; greater impact force means longer Stun).
- STRUCTURAL FINDING: Archer's Arrow Enhancement buffs specific ARROWS, Mighty Archer buffs specific SKILLS. A node's value therefore depends entirely on whether the named arrow or skill is owned - the same loadout gating that made the level-2 pick inert.
- SLOT-STATE READING RULE, three distinguishable states: gold border = owned AND equipped; dashed border with no padlock = owned but NOT equipped; padlock glyph = locked. Conflating the middle state with owned-and-active would overstate a loadout.
- BATTLE-FED IS INERT, and this time it is read off the screen rather than inferred: the Hunter's Arrow row shows 0 equipped, exactly 1 unlocked-not-equipped, and 4 locked, against a requirement of 'carrying at least 2 Hunter's Arrows'.
- Dodge Power Shot now renders an Activate bar where it rendered none at level 2, so it has become selectable in the interim.
- Rapid Arrows tooltip recorded verbatim - Volley mode, hold to fire up to 5 arrows, shooting during Volley does not reduce Movement Speed, dodging removes Volley.

WHAT IS DELIBERATELY NOT CLAIMED: three skill NAMES are now first-party - Rapid Arrows, Sky Piercer and Scattershot, the latter two because the Mighty Archer tooltips name them. That the operator OWNS Sky Piercer and Scattershot is NOT established; it is an inference from two equipped icons, and this repo does not bind a name to an icon. Only Rapid Arrows is confirmed both named and owned, by its own tooltip rendering.
NO MAGNITUDE APPEARS ON ANY NODE. 'Increases the Damage Multiplier' and 'Increases the knockback distance' carry no number, so no coefficient is recorded and the recommendation made to the operator was explicitly flagged as mechanical reasoning rather than measured math.
ROADMAP 4b's types-versus-charges question is now SEPARABLE for the first time: the operator holds exactly ONE Hunter's Arrow. Equipping it and taking Battle-fed distinguishes '2 equipped types' from '2 available charges', a case that could not exist at level 2 when he had 2 types and 3 charges simultaneously. Recorded as an experiment, not scheduled - it costs a talent point.

### LL-0060 - 2026-08-25 - ROADMAP 7c groundwork measured and the naive reader REFUTED - a draft that refused every real frame was removed rather than shipped

**Evidence:**
- Panel geometry measured off 6,439 crops (500x310 RGB): orange Total Damage digits at rows y 98-118, white Progress Record digits at y 255-273, value left-aligned near x=51, hit count near x=197 (orange) / x=200 (white), split at x=190 lands in empty space in every frame examined. Glyphs 10-12 px wide, 17-21 px tall, advance 12-13 px.
- Exact template matching is dead: ten digits produced 430 distinct exact bitmaps, because the plate is semi-transparent and the scene behind it moves.
- The shapes ARE separable and the templates exist: clustering normalised patches from the orange hit field gives EXACTLY 10 clusters, labelled two independent ways that agreed on all ten - by reading the rendered ASCII art, and by the counter itself, seven clusters first appearing at consecutive scan positions and reading 1,2,3,4,5,6,7 under the shape labelling.
- THE DEFECT: one template set cannot serve four fields. Matched within distance 0.12 - orange hit count (the source field) 367/367 = 100%; orange total 599 glyphs = 40%; white progress total 494 glyphs = 9%.
- Two fixes measured and both insufficient: normalised cross-correlation made it WORSE (orange total fell to 17%), and fixed-row normalisation + 3x3 blur + a +/-3 row shift search reached only 28% within 0.06 while the white fields sat at a stubbornly CONSISTENT 0.11-0.12 - the signature of a systematic rendering difference, not noise.
- ROOT CAUSE, found by dumping the glyph and the template as art side by side: in the value field the top stroke renders fainter, a hard colour threshold erodes it, and normalising to the glyph's own ink extent then rescales the whole glyph against a template built from an uneroded one.
- A per-field harvest was tried and is recorded because it shows what is left: at a fixed clustering distance of 0.05 the three fields gave 11, 13 and 7 clusters rather than 10, 10, 10, so the clustering threshold cannot be a constant across fields either.
- Also measured, and useful: a panel-DOWN frame has ZERO orange pixels while being BRIGHTER overall than a panel-up frame (bright fraction 0.0668 against 0.0153), so presence can never be decided on brightness - and zero orange pixels is itself a correct refusal trigger.

WHY NOTHING SHIPPED: the draft refused every real frame, and a reader that refuses everything is worse than no reader - it looks like a capability. It was removed from the repository rather than left in place behind a caveat. The draft, its validated templates and the calibration scripts are kept OUTSIDE the repo at C:/ll-captures/2026-08-25/meterread-wip/ so the next attempt starts from them.
The acceptance is unchanged and 7c stays READY. The refusal requirement now has measured teeth: a two-threshold design - accept below, reject above, REFUSE IN BETWEEN - is what stops a damaged glyph from silently truncating a number into a shorter one that would look perfectly valid.
The next attempt's shape is specified: one template set per field, labelled by mapping each field's clusters onto the labelled orange set by nearest neighbour and REQUIRING the assignment to be a bijection onto 0-9, which a wrong mapping would almost certainly fail.

### LL-0059 - 2026-08-25 - A full dungeon run wrote NO transient save - item 7's damage source is MODE-DEPENDENT, and it is not the patch that did it

**Evidence:**
- Captured live while the operator played, with 4c's watchers armed from session start. BP_Dungeon_GameMode on /Game/Project/Maps/Map_2/Whitewoods_Day, levelId=113, matchId=11114, solo - exactly one roleId anywhere in the log.
- Timeline UTC: InMatch 02:54:56, MatchSuccessful 02:55:57, EnterBattle 02:56:01, 'Welcomed by server' + LoadMap 02:56:19.
- NO StandaloneSlot_<roleId>.sav ever appeared. SaveGames/ was polled every 3 s for the whole run and StandaloneLevel/ stayed empty. A find across the entire Saved/ tree returned exactly three files touched in twenty minutes: CampData, the market cache, and the log.
- THE DISCRIMINATOR: the substring 'StandaloneLevel' occurs ZERO times in this run's log, against 'TS.Dungeon: StandaloneLevel requestEnterStandaloneLevel: match id 11111' opening the 2026-08-09 runs that DID write the save. So the transient save follows a standalone-level REQUEST, not 'being in a dungeon'.
- THE NEGATIVE WAS PATTERN-CHECKED BEFORE IT WAS BELIEVED, per this repo's own anti-pattern: the same grep returns 2 against tests/test_logparse.py, which contains the literal line. An empty grep is a claim about the pattern, so the pattern was shown to work first.
- Observed difference, recorded not concluded: the runs that wrote the save carried a four-axis map URL (levelId=119, roomModeId=0, matchType=1, matchId=11112). This run carries two - levelId=113, matchId=11114 - with no roomModeId and no matchType anywhere in the log.
- Also measured: AvgPrice_937566.ini went 37 -> 157 bytes at 02:56:21 UTC, two seconds after the dungeon finished loading. Both generations are archived. This is the first time anything has watched that file CHANGE rather than finding it already changed.
- Also recorded, uninterpreted: 'TS.UI: onPartEscape' and 'TS.Dungeon: getPartEscape', a third escape noun beside GroveSprite and FixEscapeBell/WindChime.
- Written up as docs/FINDINGS.md section 12; ROADMAP items 4 and 7 carry the consequence.

THE LOAD-BEARING CONSEQUENCE for Emberforge: a dungeon run is NOT a guarantee of damage data. A reader must treat a missing StandaloneSlot file as a NORMAL MODE rather than a parse failure, and any plan of the form 'play a dungeon and collect damage' is underspecified until the mode is named.
WHAT THIS DELIBERATELY DOES NOT CLAIM: not that the 2026-08-19 patch removed the surface. The simpler explanation - a second dungeon mode that never requests a standalone level - fits every observation, and blaming the patch would have been the exciting wrong answer. What selects the two behaviours is unmeasured, and the operator was not asked which mode he chose, so no mode name is filed.
A TENSION WORTH NOT SMOOTHING: ROADMAP item 4 filed the market-cache write as triggered by RETURNING TO CAMP, measured 0.975 s after a camp level-switch following an escape. This observation is the opposite direction - leaving camp, 2 s after the dungeon loaded. Both are n=1. The reading that fits both is a level transition in either direction; item 4's measurement is not amended and the hypothesis is filed as a hypothesis.
n = 1 run. Nothing here is a rule yet.

### LL-0058 - 2026-08-25 - Refutation pass on LL-0056 and LL-0057 while writing them - five defects, all mine, and the two worst were over-claims of continuity I never observed

**Evidence:**
- ROUND 1, three findings. (a) 'the live log has carried the same creation time THROUGHOUT' and 'has not moved since 2026-08-09' - both assert continuity across launches nobody watched. One launch was observed. Corrected in ROADMAP 4c and FINDINGS 11.12 to claim only what one launch shows. (b) The sha256 comparison had been made against the hand-off's prose ('1c44235c...') rather than against the archived file; re-run directly against C:/ll-captures/2026-08-25/logs/20260825-202825_5080313_MistfallHunter.log and it holds. (c) '23 listings' was asserted from wc -l without checking what was in them; re-derived - 23 files, span 18:38:20 to 20:28:25, gaps 300/301 s, zero entries not named *_MistfallHunter.log.
- ROUND 2, two findings, both in text that round 1 had already rewritten. (d) 'So one launch produced a backup and the launch before it did not' - an absence measured over a window, stated as an absence at an event. This is the round-2 defect that matters and it came from my own summary sentence, not from the data. (e) '11.8 was written from a directory listing at 18:34' invented a precision the source does not carry - 18:34:46 is the log's OPEN time, not the time anyone listed the directory.
- Also round 2: 'the day this project started reading it' was wrong about what 2026-08-09 08:18:56 marks. Saved/Config was created 2026-08-09 08:18:57, so it is the game's own first run on this machine, not a Lanternlight artifact.
- Claims re-verified rather than assumed: the refuted sentence's other homes were found by grep, not by memory - NEXT_SESSION_PROMPT.md lines 62 and 79 and WAKEUP_NOTES.md line 32 still carried it, and all three are corrected in the same commit as the finding.
- Suite after all corrections: 1244 passed, 1244 collected, ruff clean, ascii and no-PII guards green.

The severity curve, which the hand-off says matters more than the count: round 1 found unverified provenance and two over-claims; round 2 found one real logical error and one invented precision. Not yet cosmetic, so this is not where a pass stops.
CONFIRMING THE HAND-OFF'S OWN LESSON: every round-2 finding was in text round 1 had just rewritten. Acting on a refutation is where the next defect gets made, so a correction needs re-deriving as hard as the original did.
DEPARTURE FROM THE SESSION DEFAULT, recorded rather than hidden: this pass was self-run, not run by a distinct agent. CLAUDE.md requires an independent refuter, and this session's harness was instructed not to dispatch subagents unless asked. Agreement with myself is not evidence, so LL-0056 through LL-0058 have NOT had an out-of-domain check and the next session should give them one before building on them.

### LL-0057 - 2026-08-25 - ROADMAP 4c CLOSED - lanternlight/armwatch.py arms all four surfaces from one entry point, and it reimplements none of the copying

**Evidence:**
- lanternlight/armwatch.py + tests/test_armwatch.py, 19 tests. Suite 1225 -> 1244 collected, +19, exactly the tests added. Ruff clean. Measured on a clean tree with __pycache__ purged.
- ops/merge_gate.verify(claimed_paths=[armwatch.py, test_armwatch.py, ops/lanes.py], baseline=1225) -> 'merge gate: OK (1244 tests collected)'. Baseline measured this session with --collect-only before any work, not carried forward from a document.
- Acceptance 'one entry point': python -m lanternlight.armwatch --dest-root C:/ll-captures/<day>. Run for real against the live game directory, rc=0, and it captured all four surfaces including the backup log in one pass.
- Acceptance 'a test that the destination guard refuses a path inside a checkout': pinned three ways - a hand-built .git fixture, this actual checkout, and an assertion that the refusal happens BEFORE any destination directory is created. Confirmed live too: --dest-root C:/Lanternlight/captures returns rc=2 and C:/Lanternlight/captures does not exist afterwards.
- Acceptance 'a written note of what each interval is for': the rationale is a FIELD on WatchPlan, not a comment, and a test asserts every rationale cites at least one digit so it cannot decay into prose. SaveGames and StandaloneLevel 3 s (transient save appears 17 s after EnterBattle, 7 generations in about 70 s, 2190 -> 44517 bytes); Saved root 30 s (the market cache changes state, it does not grow); Logs 300 s (5,080,313 bytes in a session; 23 generations at that cadence).
- GUARDS PROVEN NON-VACUOUS - four mutations, each red in the right place, green on restore: LOG_POLL_S 300 -> 3 (1 failed); logs source changed from the directory to the file (4 failed, including the backup-capture test); a rationale stripped of its numbers (1 failed); arm() made to construct nothing (10 failed). __pycache__ cleared before each.
- Not one byte of copying was reimplemented - the module builds a plan and hands it to SaveWatcher, as the item demanded.

THE DESIGN DECISION WORTH CARRYING: watch the Logs/ DIRECTORY, never the log FILE. That is what picked up the 5,080,313-byte backup at 21:30:40, so arming at session start now recovers the PREVIOUS session as well as preserving the current one - a capability nobody knew existed before LL-0056.
It also makes LL-0056's open question self-measuring: because Logs/ is archived wholesale, every future launch records whether a backup appeared beside the log. Nobody has to run an experiment.
Armed and running against the live game for the rest of this session, dogfooding the documented command rather than the stopgap it replaced.

### LL-0056 - 2026-08-25 - FINDINGS 11.8's 'the game truncates its log on launch and keeps no backup' is REFUTED in its second half - a launch watched directly copied the whole log first

**Evidence:**
- The game exited 20:27:09 local and relaunched 21:28:59 (the live log's own first line, 'Log file open, 08/25/26 21:28:59'). Logs/ then held TWO files where 11.8 recorded one.
- MistfallHunter-backup-2026.08.26-01.27.09.log, 5,080,313 bytes, sha256 1c44235c962a89a32dc97fdbf24e2afc0952e5fe7418dd4b8ba51ad41dc8f050 - byte-identical to the previous session's final archived log at C:/ll-captures/2026-08-25/logs/20260825-202825_5080313_MistfallHunter.log, verified by sha256sum against the ARCHIVED FILE and not against the hand-off's prose quoting it.
- The backup was made BY the launch: creation time 2026-08-25 21:28:59 (the second the new log opened) while its content stops at 20:27:09. Its name encodes the previous log's close time in UTC - 2026.08.26-01.27.09 is 20:27:09 local, matching that log's own last line 'Log file closed, 08/25/26 20:27:09'.
- The previous run exited cleanly - 'LogExit: Exiting.' - so the backup is not a crash artifact.
- The first half of 11.8 SURVIVES: after the launch the live MistfallHunter.log still carries creation time 2026-08-09 08:18:56, the same minute Saved/Config was created, so this launch emptied the existing file rather than making a new one.
- CAVEAT WRITTEN INTO THE ARTIFACT, not just said: NTFS tunneling restores a creation time when a file is deleted and recreated under the same name inside about 15 seconds, so creation time alone does NOT separate truncate-in-place from delete-and-recreate. Nothing actionable changes; the document does not pretend the evidence settles it.
- MEASURED NEGATIVE bounding the claim: across 23 archived generations of Logs/ spanning 18:38:20 to 20:28:25 on 2026-08-25, gaps of 300 or 301 s, every one a copy of MistfallHunter.log and zero of anything else, NO *-backup-*.log existed at any point.
- Written up as docs/FINDINGS.md 11.12, with 11.8 left standing and marked rather than edited away.

WHAT THIS DOES NOT LICENSE, and the second refutation round is what caught it: the absence over 18:38:20-20:28:25 does NOT show the launch that began that session made no backup. Nobody was watching before 18:38:20, and a backup made at that launch and removed before the first listing is indistinguishable from here. An absence over a window is not an absence at a launch.
So the mechanism is real and the CONDITION is unmeasured. One launch left a backup; an entire earlier session had none. No rule is written from n=1 in either direction.

### LL-0055 - 2026-08-25 - Corrects LL-0054 - a line count it filed came from the refuter's report rather than from the file, which is the exact failure LL-0054 was written about

**Evidence:**
- LL-0054 said NEXT_SESSION_PROMPT.md was 'rewritten this session at 232 lines'. The file is 191 lines - `wc -l` says 191. 232 is the diff churn: `git show --numstat f9bf1d9` reports 135 added and 97 removed, and 135 + 97 = 232.
- PROVENANCE OF THE WRONG NUMBER, which is the point of this entry: it did not come from the repo. The fourth refutation pass wrote '232 lines' in its round-three report, having read the bar width off `git show --stat` without running `wc -l`, and it was copied into an append-only entry without being re-derived. The refuter identified and owned this itself in round four.
- Also corrected, in NEXT_SESSION_PROMPT.md which is editable so no entry is forced: it claimed the final log was 'archived four minutes before the operator quit'. The archive is stamped 20:28:25 and the live log's last write is 20:27:09, so the copy was taken about 76 seconds AFTER the log stopped growing - the clause pointed the wrong way and no quit time was ever established. The load-bearing half is true and now says how it is known: both files sha256 to 1c44235c962a89a3..., byte-identical.
- Suite: 1225 passed, 1225 collected, ruff clean, zero .py changed all session.

THE LESSON, and it is LL-0054's own lesson landing on LL-0054: a number handed to you by a verifier is still a filed count. It arrives wearing the authority of an adversarial check and it has not been checked. Re-derive numbers from the artifact even when - especially when - the source is the process you set up to catch you.
Four refutation rounds found 13, then 5, then 2, then 2. The severity curve is what matters more than the count: rounds 1-3 found invalid arithmetic, an inert correction and a wrong number wearing a fixed number's clothes; round 4 found a stale line count and an unsupported clause. That is where a pass is close to empty.

### LL-0054 - 2026-08-25 - Third refutation pass - the correction from the second pass was applied in both places and its arithmetic was still wrong, which reads as fixed and is worse

**Evidence:**
- LL-0053 replaced a false sentence in WAKEUP_NOTES.md with 'six of the ten distances were recorded by the wide-shot poller at capture time'. The six was taken to be {10, 8, 6, 4, 2, 0}. Four of those were fired BEFORE the poller existed: the scene capture's own first frame is s00000_19.32.34.jpg and the 6, 4, 2 and 0-pace runs were fired at 19:14:01, 19:14:38, 19:15:15 and 19:15:53.
- Re-derived from the poller window: SIX runs - 10, 9, 8, 7, 3, 1 paces - were fired while the wide shot was running, so 'six' was accidentally the right count attached to the wrong SET and to the wrong PROPERTY.
- The honest breakdown, now in the hand-off: two labels fixed by protocol before firing (the 11.11 re-run at 10 and 8 paces), eight assigned by clock order, six runs with the operator's position on film, and NO distance ever read off the wide shot - that measurement saturated twice.
- Also corrected: WAKEUP_NOTES.md filed the ledger range as LL-0049 through LL-0052, omitting LL-0053. Third wrong version of that one line - it previously said 'LL-0049' alone, then filed a commit count of fifteen against a command returning fourteen.
- Corrects two overstatements in LL-0053 itself, which is append-only: it said ROADMAP asserted item 4's watcher was still to build in 'three others' when two of the three sites asserted it and the third was a stale framing; and it called deduped frames 'distinct states' when the distinct readings in those windows are 4, 8 and 8.
- Suite after the corrections: 1225 passed, 1225 collected, ruff clean, zero .py changed all session.

THE LESSON, and it is a sharper one than LL-0053's: the second pass's failure mode was 'fixed in one of the two places it lived'. The third pass's was 'fixed in BOTH places, with a number nobody re-derived'. That is worse, because it now READS as corrected. When you act on a refutation, re-derive the arithmetic of the correction - do not just confirm the correction is present.
Three rounds found 13, then 5, then 2. Diminishing, and not yet empty. The pass is not a step you complete.
Not audited by any pass: NEXT_SESSION_PROMPT.md, rewritten this session at 232 lines. The refuter said so explicitly rather than implying coverage it did not have. A cold session should treat it as unreviewed.

### LL-0053 - 2026-08-25 - The wrap refutation was run a SECOND time on its own fixes and found five more - including that the first fix had been applied in one of the two places the defect lived

**Evidence:**
- Defect A, the worst: LL-0052 corrected the 'every distance was recorded at capture time' overclaim in the ledger, where append-only rules FORCED a correcting entry - and left the identical sentence standing in WAKEUP_NOTES.md, which is freely editable, was edited in the same commit, and is the first file a cold session reads. A correction filed only where the rules compel it is half a correction.
- Defect B: the hand-off filed a commit count of 'fifteen' when the command printed in the same sentence returns fourteen. The first draft said 'six'. No count is filed there now - the line names the command instead.
- Defect C: ROADMAP.md asserted in one place that item 4's acceptance was met by shipped code and in three others that its watcher was still to build, 895 lines apart. Item 4 is now CLOSED with the evidence attached, and item 4c named as the part genuinely left.
- Defect D: FINDINGS 11.7 claimed its solve was 're-runnable from this table alone'. It was not - the tie convention sat 300 lines away in 11.3, and the refuter taking the obvious reading got four different failure hits. The convention is now stated beside the table.
- Defect E: the 7b citation named LL-0049 and LL-0051 and omitted LL-0050.
- Flagged residual F, resolved by re-sourcing rather than by argument: the 9-pace and 8-pace rows are byte-identical including their gap positions, which is the shape of copied data. Re-tiled from panel2/ the three floor windows give 8, 9 and 12 distinct states and observed hits {6,7,8,10}, {1,2,4,5,7,8,10} and {1,2,4,5,7,8,10}, matching the table. A steady firing cadence sampled at 2 fps misses the same positions every time.
- Suite after all corrections, clean tree, __pycache__ purged: 1225 passed, 1225 collected, ruff clean. Still zero .py files changed all session.

THE LESSON: an adversarial pass is not a step you complete, it is a step you REPEAT until it comes back empty. The first pass found 13 defects; acting on them introduced one new contradiction and left one old defect half-fixed, and only re-running found that.
The corollary is sharper: the ONE defect the second pass called worst was the one where an append-only rule had forced a correction. The rule did its job in the ledger and nothing did its job in the editable file beside it. Being compelled to write something down is not the same as understanding why.

### LL-0052 - 2026-08-25 - Corrects LL-0050 and LL-0051 - the wrap refutation found two invalid arguments, an overstated discipline claim, and points invented to fill a gap in a run this project had just finished warning itself about

**Evidence:**
- docs/FINDINGS.md 11.10 argued for the WRONG mapping on two grounds and BOTH were arithmetically invalid: each compared head runs under mapping B against body runs under mapping A. Re-derived consistently - A gives ratios 1.183, 1.183, 1.133, 1.192, 1.163, 1.182 and B gives 1.183, 1.133, 1.192, 1.163, 1.182, 1.186. The '3.37x that makes nonsense of A' is the MIXED pairing, not A. Under consistent A both sweeps step 1.000x from 10 to 8 paces, which matches rather than conflicts.
- Mapping A was correct, so the reasoning pointed at the wrong answer and only re-running the measurement recovered it. Both arguments are now quoted in 11.10 and refuted in place rather than deleted.
- LL-0051 claimed 'every distance in this entry was recorded by the wide-shot poller at capture time'. FALSE for four of the ten: the 9, 7, 3 and 1-pace labels were assigned in clock order from the order the operator named them. The wide shot recorded the operator's POSITION, which is not the same as a distance being read off it - the attempt to read one saturated twice and is written up as failed in 11.11.
- The four inferred labels are nonetheless forced by monotonicity, and that check is recorded in docs/FINDINGS.md 11.6 rather than left implied.
- The 10-pace run was solved using the points (1,10) and (2,21), which BELONG TO THE 8-PACE RUN - its own early states were never captured. Re-solved on its four genuinely observed points the interval is unchanged at [10.3500, 10.3571], so no conclusion moves. docs/FINDINGS.md 11.7 now publishes every observed cumulative state per run, with dashes for uncaptured intermediates, so the solve is re-runnable from the artifact instead of asserted by it.
- LL-0049's note left the two-point 5.4x distance step OPEN. It is answered: the ten-point curve supersedes it and no two-point step is cited anywhere as current.
- Full suite after the corrections, clean tree, __pycache__ purged: see the wrap commit. Docs only - no code changed anywhere in this session.

THE PATTERN, and it is LL-0048's pattern again: a true conclusion is indistinguishable by reading from a sound one. Here it was worse - the argument was invalid AND pointed the wrong way, and the only thing that caught it was re-measuring. Had the invalid reasoning pointed at the right answer, nothing would have flagged it.
THE SECOND PATTERN: the session wrote two sections on the cost of inferring a variable instead of recording it, and then filled a gap in its own data by copying a neighbouring run's points. Writing the lesson down does not immunise you against it.
A ledger entry is append-only, so LL-0051's overstated sentence stands and this entry is the correction. Read them together.

### LL-0051 - 2026-08-25 - Both falloff breakpoints located - the curve is a clamped floor, about 1.3x per pace, and a clamped ceiling, and the floor is a step not a tangent

**Evidence:**
- Ten measured distances, ten body hits each, distance recorded in the capture at the time rather than recalled: 10, 9, 8, 7, 6, 4, 3, 2, 1, 0 paces read 104, 104, 104, 231, 309, 546, 687, 687, 689, 691.
- FLOOR breakpoint between 8 and 7 paces. Runs at 10, 9 and 8 all read exactly 104 and all solve to [10.3500, 10.3571]; 7 paces reads 231, a 2.221x step in one pace against 1.338x for the next.
- CEILING reached by 3 paces. Runs at 3, 2, 1 and 0 read 687, 687, 689, 691 - a four-distance plateau spanning 0.6% - while 4 paces reads 546.
- The slope is regular: per-pace factors 1.338 (7->6), 1.329 (6->4 as a geometric mean) and 1.258 (4->3).
- The floor is a STEP: extrapolating the slope outward from 7 paces predicts about 174 at 8 paces and it reads 104. Measured gap, unexplained cause.
- Constancy: every floor run admits a constant per-hit value and NO other run does, including all four ceiling runs whose totals agree to 0.6% while their individual hits do not.
- Full suite on a clean tree: 1225 passed, 1225 collected, ruff clean. Docs and measurement only.

Constancy is NOT a property of flat totals - the ceiling is flat and not constant. It is a property of the clamp, and the boundary of the constant set is exactly the 8-to-7 step.
NO FALLOFF FORMULA PUBLISHED. Four interior points sitting near a constant ratio fit many functions. The per-pace factor is recorded as a measurement, not named as a law.
Every distance in this entry was recorded by the wide-shot poller at capture time. The sweep that preceded it had to be re-run because its distances were inferred from clock order - see LL-0050.

### LL-0050 - 2026-08-25 - The distance curve is clamped at both ends, the far body value is exactly 10.35, and a label that was inferred rather than recorded nearly published a wrong floor

**Evidence:**
- Body sweep, ten hits per run at 10, 8, 6, 4, 2 and 0 paces: 104, 104, 309, 546, 687, 691. Head sweep at the same distances: 123, 123, 350, 651, 799, 817, 818.
- 10 and 8 paces give the IDENTICAL ten-hit total - a damage floor. 2 and 0 are within 0.6% - a ceiling. Ceiling is 6.64x the floor.
- The floor value is exactly 10.35: three runs give the same series, the only hit that ever disagreed (104 vs 103 on the tenth) is the ONLY cumulative landing on an exact .5 rounding tie, and searching every two- and three-decimal value that fits all three runs with ties free returns exactly one candidate.
- Solving round(n*v) == total_n per run: a constant value fits both floor runs and NO run on the slope. A delta wobbling by one is NOT evidence of variance - the floor runs wobble 10, 11, 10, 10, 11 at a constant 10.35.
- No head run admits a constant value, including the two on the floor where body is perfectly constant. Head totals reproduce (123 twice, 817 vs 818, 122/123/123 earlier) while individual hits do not.
- Full suite on a clean tree, __pycache__ purged: 1225 passed, 1225 collected, ruff clean. No code changed - measurement and docs only.

THE FAILURE WORTH KEEPING: both sweeps produced SEVEN runs, not six. Distances were assigned by clock order and committed. The operator then labelled the head runs and listed six, implying an uncounted first run - which would have shifted every body run and deleted the floor. Every total was measured exactly; the LABEL broke, silently, because clock order looked like an obvious ordering and nobody had said it was.
RESOLVED BY RE-RUNNING, not by argument or by asking the operator to remember harder. A wide-shot poller was armed (half-scale JPEG, 1 fps, ~140 KB a frame) and the ambiguous pair was redone: 10 paces and 8 paces, both 104. Record the independent variable in the same stream as the dependent one.
A MEASUREMENT THAT FAILED, written up as failed: turning apparent bot size into a distance number saturated twice, returning exactly the band height both times. A ratio of 1.000 from a saturated read is indistinguishable from a real null.
NO COEFFICIENT PUBLISHED. 10.35 is a floor value with its conditions attached - Blackarrow, right-click, standard arrow, this bot, buildid 24813185. A falloff formula from three interior points would be a story.

### LL-0049 - 2026-08-25 - ROADMAP 7b answered - the training ground is a PIXEL rig not a file rig, and the first outgoing damage measured is fractional and reproduced

**Evidence:**
- Game running first-party 2026-08-25, log opened 23:34:46 UTC; operator in /Game/Project/Maps/TrainingGround/Training from 23:38:16 UTC.
- 7b(a) EXISTS: LoadMap line, DA_DungeonSettings_Training, WBP_Level_Room_Setting, BP_Adventure_Bot_C - docs/OBSERVED_IDS.md, new section 'Training ground - 2026-08-25'.
- 7b(b) CLEAN NEGATIVE: no StandaloneSlot_<roleId>.sav after ~18 minutes in the room, Saved/StandaloneLevel/ empty, no EnterBattle and no onRequestMatch in the log, and 7 occurrences of the substring 'damage' in the whole log, none carrying a number. DamageCollectonDataSet is not written in the training ground.
- 7b(c) BODY YES: runs at 18:41:47 and 18:49:32 are identical hit for hit - 10 21 31 41 52 62 72 83 93 104 - eight minutes and four intervening runs apart, each from its own meter reset.
- Solving round(n*v) == total_n over the ten points gives v in [207/20, 145/14) = [10.3500, 10.3571) and NO integer lies in it, so the meter displays a rounded real-valued cumulative sum.
- 7b(c) HEAD NO: runs at 18:51:17 and 18:53:37 are identical to each other (sum 123) but the run at 18:45:47 is not (sum 122), and the identical pair fits floor() while the body runs fit round() - one meter cannot do both, so the single-value model is wrong for head.
- Corroboration from an unrelated surface: the transient save's damageValue is a float (17.356201171875), so two independent surfaces agree the engine quantity is real-valued.
- Build re-pinned: Steam buildid 24619162 -> 24813185, LastUpdated 1786281053 -> 1787126796 (2026-08-19T08:06:36Z), MistfallHunter.exe dated 2026-08-19. Every id in docs/OBSERVED_IDS.md predating that patch is now marked UNCONFIRMED on the current build.
- Full suite on a clean tree with __pycache__ purged: 1225 passed, 1225 collected, ruff clean. No code changed this entry - docs and measurement only, so the count is unchanged by design.

NO COEFFICIENT PUBLISHED. The body interval has its independent run and nothing more; the head numbers have not earned even that.
OPEN, recorded not answered: the operator halved the range and measured ~55.6 per body hit against ~10.35 far - a 5.4x step, attested as 'changed nothing'. Two points cannot show a falloff, two bots were in the room and neither far run pinned which was hit, and the far firing position was never recorded. Acceptance for turning it into a finding is in ROADMAP 7b.
The full-screen frame poller wrote 4.8 MB per frame - 3.2 GB in 12 minutes on a disk with 52 GB free. A panel-only poller cropping the HUD rectangle at capture time costs about 150 KB per frame, 20x less, and loses nothing this measurement used.

### LL-0048 - 2026-08-13 - Corrects LL-0047 - the over-determination evidence recited a placeholder enumeration that was false, and the derivation that replaces it kills a mutation the old test survived

**Evidence:**
- Suite 1225 passed, 1225 collected, up from a measured baseline of 1223. Two tests added, none removed. ruff clean, __pycache__ purged. EVERY COUNT IN THIS ENTRY IS A FULL-SUITE COUNT - see the mutation line for why that is stated rather than assumed.
- THE WRONG FACT: LL-0047's evidence line, the comment above _CDKEY_VALUE and the comment in test_an_existing_cdkey_placeholder_is_not_remasked all state that <PRODUCTUSERID> at 15 characters is the ONLY placeholder clearing _CDKEY_MIN_CHARS. FOUR clear it, measured this run by deriving them from RULES: <USER_UNIQUE_ID> (16), <PRODUCTUSERID> (15), <ACCOUNT_NAME> (14), <OWNER_ROLEID> (14). RULES emits 17 distinct placeholders, not the 21 an intermediate report claimed. The two extras are not placeholders: NAME_FIELD is a real label but its rule lives in DETECT_ONLY_RULES with an empty replacement, so it emits no bracketed token at all, and AUTHORED_NAME_MARKER is a module-level constant rather than a rule replacement. Both would still be blocked by class and digit if they ever reached the text, so neither changes the count. An earlier draft of this line asserted that the bracketed NAME_FIELD spelling "appears nowhere in the tree" - which the sentence itself then falsified by containing it. Recorded because it is the same shape as the defect this entry corrects: a claim about a corpus, written into the corpus.
- THE CONCLUSION SURVIVES, THE STATED REASON DID NOT. All four are digit-free, so the minimum blocker count over every placeholder is still 2 and no single edit exposes any of them. A safety claim that happens to hold is not evidence that the reasoning under it was true, and this one was false the day it was written.
- Exactly two placeholders carry a digit - <STEAMID64> (11) and <IPV4> (6) - and both fall below the floor. <STEAMID64> is ONE character short: lowering _CDKEY_MIN_CHARS to 11 leaves it resting on the character class alone.
- THE RECITAL IS REPLACED BY A DERIVATION. test_no_placeholder_rests_on_a_single_cdkey_condition takes _CDKEY_VALUE apart by surgery on the live pattern string and counts, for every placeholder RULES emits, how many of the three conditions independently reject it. It cannot go stale the way a typed list does, and it reddens if a future placeholder is ever both at the floor and digit-bearing.
- MUTATION RESULTS, FULL SUITE, anchors asserted applied and __pycache__ purged each run, baseline 1225 passed: floor 12 -> 11 -> 2 failed, 1223 passed (KILLED); widen the class and its lookahead to admit <>_ -> 4 failed, 1221 passed (KILLED); drop the digit requirement from the lookahead -> 6 failed, 1219 passed (KILLED); floor 12 -> 15 -> 1 failed, 1224 passed (KILLED). POSITIVE CONTROL for the derivation itself: renaming one rule's replacement from <ACTOR> to [ACTOR] -> 2 failed, 1223 passed, one of them the new test's own count control, so the enumeration is proven to be reading RULES rather than returning an empty mapping. The class-widening mutation is the one LL-0047 recorded as SURVIVING against test_an_existing_cdkey_placeholder_is_not_remasked. The derived test kills it.
- THIS ENTRY'S FIRST DRAFT SHIPPED THE DEFECT IT DOCUMENTS, and the refutation pass caught it. The mutation line above originally read "1 failed" for the class widening and "2 failed" for the digit drop. Those were SCOPED counts from a -k filtered run, published unqualified in a document whose neighbouring entries use full-suite counts. Re-measured full-suite they are 4 and 6. So an entry correcting a filed count was itself filed with two wrong counts - the fourth time in this module that a number written from memory of a narrower run turned out wrong. The counts above are now full-suite and say so.
- SCOPE GAP CLOSED, also found by the refutation: the derivation read RULES alone, while redact() also applies LOG_TEXT_RULES and DETECT_ONLY_RULES. No live gap - LOG_TEXT_RULES emits only <PERSONA>, which RULES already emits, and a detect-only rule has an empty replacement - but a future log-text-only placeholder that was long AND digit-bearing would have escaped the guard. _placeholders_rules_can_emit now scans all three collections. Re-derived across all three: still 17 distinct tokens, blocker histogram {3 blockers: 11, 2 blockers: 6}, minimum 2.
- THE FIX SHIPPED THE SAME DEFECT ONCE BEFORE PASSING. The first draft of _cdkey_blockers hard-coded "the class excludes '<'" as a Python assumption instead of reading the pattern, and the class-widening mutation SURVIVED it - the third consecutive session in which a claim about this rule was written as prose and refuted by its own mutation. Isolating each condition with the other two relaxed is what fixed it: read as it stands, the digit lookahead fails on a leading '<' because of the CLASS, which would have scored <STEAMID64> as digit-blocked while it plainly carries digits.
- SMALLER CORRECTION, verified rather than relayed: the comment on test_a_camelcase_mention_with_no_separator_is_not_a_cdkey said the test "pins NOTHING on its own". Its second half does pin that the rule fires - deleting the CDKEY rule from RULES reddens it. Measured this run, eleven tests redden under that deletion, so it is not the rule's backstop either, and the comment now says both.

THE LESSON IS THE SHAPE, NOT THE FACT. An enumeration written into a comment is a filed count, and this repository's own anti-pattern list already says a filed count is a hypothesis. The list was correct about the conditions and wrong about which placeholders they applied to, and nothing could have caught it, because prose has no failure mode. What makes the difference is not care - three sessions of care did not catch it - but moving the claim into something that runs.

AND THE SECOND LESSON, EARNED IN THE SAME ENTRY: A COUNT WITHOUT ITS SCOPE IS A WRONG COUNT. Both mis-filed numbers here came from reading a summary line off a `-k` filtered run and writing it into a document whose convention is full-suite. Neither was a guess and neither was careless - each was the true answer to a narrower question than the one the sentence appeared to be answering. State the scope beside the number, or re-run unfiltered before filing it. This is the failure mode the wrap refutation exists to catch, and it caught it twice in the entry written to correct it.

### LL-0047 - 2026-08-12 - Corrects LL-0046 - the wrap refutation found dead regex and two comments crediting the wrong condition, and fixing them took three wrong answers

**Evidence:**
- Suite 1223 passed, 1223 collected, ruff clean, __pycache__ purged. All three changed files verified 0 CR bytes and 0 non-ASCII.
- DEAD REGEX REMOVED: the placeholder lookahead in _CDKEY_VALUE could never fire, because [A-Za-z0-9] cannot match '<'. Deleting it left the suite green, which is what proved it dead. Removed rather than pinned - a guard that cannot fire is not made real by a test that cannot fail.
- IDEMPOTENCE IS OVER-DETERMINED, measured against every placeholder RULES can emit. The class excludes '<'; the digit lookahead rejects <CDKEY>, <PERSONA>, <ACTOR>, <LONG_ID>, <SAVE_SLOT> and <PRODUCTUSERID>; the floor rejects <IPV4> (6) and <STEAMID64> (11). <PRODUCTUSERID> at 15 is the only one clearing the floor and it carries no digit. So no single edit exposes any placeholder. A direct assertion on a long digit-bearing placeholder shape now pins the character class without needing a mutation: with class AND lookahead widened to admit angle brackets, 3 tests fail.
- MUTATION RESULTS, anchors asserted applied and __pycache__ purged each run: class+lookahead admit <> -> 3 failed (KILLED); drop the digit requirement -> 4 failed (KILLED); separator optional -> SURVIVED; drop the \b key boundaries -> SURVIVED; BOTH of those together -> SURVIVED.
- THE ANCHOR TEST WITH NO UNIQUE KILL IS NOW LABELLED AS SUCH. test_a_path_starting_with_g_but_not_game_is_not_a_map_url is subsumed by the trailing-slash test under every natural truncation. Kept, because it asserts a distinct property and a contrived anchor such as /G[a-z]*/ would separate them, but the test now says outright that it is not independent mutation coverage.

THREE WRONG ANSWERS IN A ROW, EACH REFUTED BY ITS OWN MUTATION, and the sequence is the lesson. Asked what keeps the CDKEY rule off a CamelCase mention such as a handler name, the integrator wrote (1) the \b word boundary - refuted, deleting both boundaries left the suite green; (2) the separator - refuted, making it optional left the suite green; (3) the two together - refuted, removing BOTH at once STILL left the suite green. The real answer is the VALUE SHAPE: the token after such a mention is four characters with no digit, nowhere near the floor. Every one of those comments would have shipped as confident prose explaining a mechanism that does not exist.
THE INTEGRATOR SHIPPED A DECORATION COMMENT WHILE FIXING A DECORATION COMMENT. The first correction asserted that widening the value class would redden the placeholder test. That mutation was run and SURVIVED. Writing the claim and then testing it is what caught it; writing it and moving on is what the original defect was. A note in a docstring is not a guard - the same lesson last session recorded, hit again by the person recording it.
PROCESS FAILURE, recorded rather than smoothed over. LL-0046 was merged to main and pushed BEFORE the wrap refutation returned a verdict, on the operator's explicit instruction. The pass later returned CONFIRMED on all six claims, so nothing unsafe landed, but the merge was unreviewed at the moment it happened and that is the exact failure the self-adversarial baseline exists to prevent. The pass also noted that at commit 43693b3 the roadmap still read READY and no ledger entry existed - 'item 9 CLOSED' was never a property of the commit that was merged; the docs landed separately in d029669.
IMPRECISION IN LL-0046's OWN EVIDENCE, corrected here rather than edited there. It records assert_clean as having 'certified 7 of 7' before the fix. That is true of REDACTED lines, which is what was measured, and FALSE of raw lines - at the parent commit assert_clean already refused 4 of the 5 token-bearing lines for unrelated labels. The vacuous-guard finding stands; the number needed its qualifier.

### LL-0046 - 2026-08-12 - ROADMAP 9 closed - a CDKEY detector for a gift code redact() could not see, and a /Game/ anchor test that turned out not to pin the anchor

**Evidence:**
- Suite 1222 passed, 1222 collected, ruff clean, measured by the integrator on main with __pycache__ purged; baseline before the work was 1196. ops.merge_gate.verify over all four claimed paths: OK.
- BEFORE, re-measured first-party against the live log: 7 lines match the key or its abbreviation, 5 carry a value, redact() masked 0 of 5, assert_clean certified 7 of 7. AFTER: 0 of 5 survive, assert_clean refuses all five token-bearing raw lines, idempotent on the whole 12.8 MB log, and the rule fires on 0 of 118 tracked files.
- Positive control: an injected code is masked in all four measured positions and assert_clean refuses the raw line in each. A clean result and a dead scanner are otherwise identical.
- CDKEY mutation proof, __pycache__ purged and the mutant asserted present on disk each run: delete the rule -> 9 failed; floor 12 to 20 -> 8; drop the digit requirement -> 4; drop the whitespace separator branch -> 3; delete DEVICE_ID -> 3; delete USER_UNIQUE_ID -> 3; add the abbreviation as a key -> 1. Restored green.
- THE FILED COUNT OF 9 IS REFUTED. It is 5, confirmed by two independent probes and reconciled by a third: the 9 came from a probe reading the ordinary word after a CamelCase mention of the key as a value - 5 real tokens plus 4 innocent neighbouring words. There are 4 positions and 5 occurrences, so the acceptance wording 'all 9 observed positions' was wrong on its face. One of the 7 lines is a false positive: a three-letter fragment inside binary garbage.
- THE /Game/ ANCHOR TEST EXISTED AND DID NOT PIN THE ANCHOR. Shipped in LL-0045 and looks exactly like the test the acceptance asked for. Before: bare-slash relaxation KILLED, re.IGNORECASE KILLED, but dropping the trailing slash SURVIVED, truncating to /G SURVIVED, widening the class to admit a hyphen SURVIVED - because the committed stand-in used a lowercase path, so only case was discriminating. Four cases added, each with a positive twin one character or one word away whose exact target is asserted. After: all five mutations KILLED.
- MECHANISM CORRECTED, and a test now pins it: MapUrl.target stops dead at the '?', so no MapUrl field would ever hold the key or the token - they would ride in the embedded LogLine.raw and .message. The hazard is a whole extra event on a secrets-bearing line, not a poisoned field.
- device_id / user_unique_id decision TAKEN, at token level rather than the weaker line-changed check: 202 and 198 tokens, one distinct value each, every one a 19-digit run, 0 surviving before any rule existed. Named as DEVICE_ID and USER_UNIQUE_ID _keyed_id rules - a renaming and not a widening, since each takes a digit run at LONG_ID's own floor.
- MEASURED NEGATIVE - OnRep_PlayStateTag needs no new rule: 0 of 20 PlayerName values survive, including all three distinct third-party names and the one non-ASCII value. The item widened its own scope onto a hazard already closed.
- MEASURED NEGATIVE - percent-encoding is a fourth encoding the module does not claim to reach, and it is clean here: 3 runs, 0 hiding a persona, and percent-decoding a REDACTED log brings back 0 of 12 personas. n=3, so a fact about this capture and not about the encoding. No rule added.
- Nothing leaked. No raw log excerpt, real code, real persona or real parameter name is committed. All four changed files verified LF-only and 7-bit ASCII.

A SLICE'S OWN CLAIM WAS REFUTED BY ITS OWN MUTATION, and the correction is the useful part. The slice wrote that the digit requirement was what kept the rule off prose. Dropping the digit left the tree scan GREEN, because the words following the key today are 3 to 9 characters and the LENGTH FLOOR stops them. But 'configuration', 'documentation' and 'implementation' all clear the floor, so the digit is load-bearing for a case the corpus does not happen to contain. Such words are now in the tests. A guard that is green only because the corpus is kind is not proven.
A SLICE INFERRED A LIVE GAME FROM A SIZE READING, for the second session running. It reported the log had grown to 12,899,997 bytes and the game was still running. The log was byte-identical and mtime-identical all session and no process was running: 12,899,997 RAW BYTES decode to 12,867,803 CHARACTERS, and the 32,194 difference is the multi-byte UTF-8 that SAF-4 already documents. A byte count and a character count are different quantities on this log because it is not ASCII. Had it been believed, item 7b would have been started against a game that is not running.
THE INTEGRATOR MEASURED A MOVING TREE AND GOT TWO DIFFERENT ANSWERS. A suite run during the wrap gave 1222 passed; a second, minutes later, gave 5 failed - because a slice was mid-mutation-probe with re.IGNORECASE spliced into the anchor. Neither reading was valid. Last session's own hand-off says to dispatch a refutation against a FROZEN ref rather than a live one; the same applies to the integrator's own measurements. The final numbers here were taken against a clean tree matching the commit exactly.
The integrator also handed a slice a claim it had not checked - that the credential on the redemption URL was 122 characters. It is 304. It was already masked, so the point the claim was making survived, but an unverified number handed to an agent as ground truth is worse than no number.
OPEN, unanswered on purpose: OPS-6, retire the global LL-NNNN id space for per-lane namespacing. It changes what 46 entries and every citing commit refer to, so it is an operator decision.

### LL-0045 - 2026-08-12 - ROADMAP 3 closed - the live log tail ships, with five recognisers the acceptance named, and a documented never-raise contract that main was already violating

**Evidence:**
- Suite 1196 passed, 1196 collected, ruff clean - measured by the integrator with __pycache__ purged. Baseline before the work was 1108, measured the same way with -o addopts= because pytest.ini's own -q makes a second -q suppress the summary line.
- merge_gate.verify(claimed_paths=[lanternlight/tail.py, tests/test_tail.py, lanternlight/logparse.py, tests/test_logparse.py], baseline=1108) -> OK.
- lanternlight/tail.py, tests/test_tail.py - 49 tests. Follows an appending file, holds back bytes not yet newline-terminated, survives in-place truncation and delete-and-recreate, holds no handle between polls, redacts before any sink. Port 8811 stays reserved and unbound.
- MEASURED, not assumed: st_ino is populated and stable on this machine, is PRESERVED across in-place truncation and CHANGES on delete-and-recreate. So identity cannot see a truncation and size cannot see replacement by a larger file - both checks are load-bearing and the size-only degradation on a zero ino is pinned by a test.
- The log carries 594 embedded control characters (98 VT, 106 FF, 113 FS, 85 GS, 97 RS, 95 NEL). bytes.splitlines() does NOT split on them; str.splitlines() does. Measured on b'A\x0bB\x0cC\x1cD\x85E\nF': bytes 2, str 6, split(nl) 2. The hazard is the decode-then-split ORDER, and the first mutant written against the method NAME survived.
- logparse gains WeaponConfigEvent (270 lines, previously 0 events), LevelSwitchEvent (44), MapUrlEvent (44), MatchIdEvent (23), SubLevelEvent (6) and a shared MapUrl carrying four axes. An axis the line did not write stays absent rather than defaulting to zero.
- MapTransitionEvent is not renamed or weakened; its docstring now says it is not a transition. All 4408 at-world lines are TS.UI widget lines. One user-visible map change emits FOUR LevelSwitchEvents - 11 switches, 4 verbs, 44 lines.
- test_logparse.py went 27 -> 59 test functions with git diff --numstat against main reading 582 0, so no pre-existing test lost an assertion.

THE INDEPENDENT REFUTATION PASS RETURNED 'not safe to merge as-is', and it was right on both blocking defects. Recorded because the green suite could not see either.
D1 - iter_events RAISED ValueError on a digit run over 4300, breaking a contract the module docstring and one of the slice's own tests both assert. Six conversion sites: three new, one in the header's own frame group so the bomb reached parse_line before any recogniser, and ONE PRE-EXISTING ON MAIN via _eqeq_fields. main already violated its own never-raise promise and nobody had noticed. _as_int is now the only integer conversion in the module.
D2 - the /Game/ anchor in the map-URL pattern was untested and load-bearing: relaxing it kept the suite green while admitting a LogUGiftAgent redemption URL carrying a cdkey and an access-token parameter into an event payload. Now pinned.
THE INTEGRATOR WAS WRONG THREE TIMES AND EACH IS RECORDED RATHER THAN EDITED AWAY. (1) '8 distinct shapes' was a method artifact - collapsing per digit CHARACTER counts id WIDTHS, not shapes; per-run gives 4 and the slice was right. (2) '101299 lines refuted' was wrong: 101198 LF + 101 lone CR = 101299 = exactly readlines() in text mode. The slice's INFERENCE that the log grows live is still wrong, since size and mtime were identical all session. (3) 'zero personas in URL query strings' came from a filter requiring /Game/ or http, which misses the producer that logs a query string alone - a broader probe found 72 lines with 26 carrying a persona. An empty grep is a claim about your pattern.
A MERGER VERIFICATION WAS ITSELF VACUOUS AND IS RECORDED AS SUCH. The first probe of the tailer's redaction reported 0 personas surviving while emitting 0 EVENTS. Re-run with a positive control - 4 lines fed, 4 events emitted, 4 personas in the raw text, 0 surviving - the property holds. But naive per-line redaction also scores 0 on those four and the tailer learned 0 personas, so the accumulation design is correct-but-not-yet-load-bearing on this log. The docstring says so rather than claiming credit.
Three mutant survivors this session exposed WEAK TESTS rather than weak code, including one the integrator's own finding created: writing the control-character note into a docstring produced a documented property with nothing behind it until it was pinned.
ROADMAP item 9 opened, safety lane: cdkey tokens survive redact() 9 of 9 and assert_clean CERTIFIES the line. Same vacuous-guard shape as item 0 and LL-0029. Also recorded there: a player-name parameter on 20 lines including third-party players, one non-ASCII, and device_id / user_unique_id needing a token-level rather than line-changed check. Nothing leaked and no raw excerpt is committed - what is broken is the protection.
Drafting item 9 tripped tests/test_no_pii.py TWICE on the integrator's own prose - once on an access-token literal, once because a player-name key is itself a keyed rule and matched its placeholder as a value. The prose was rewritten both times and the guard was not touched.
OPEN, deliberately not answered on the operator's behalf: OPS-6, retire the global LL-NNNN id space for per-lane namespacing.
ROADMAP 7b remains blocked on the client being open. No damage coefficient is published, and nothing beyond the 21 hits already proven TAKEN is labelled.

### LL-0044 - 2026-08-12 - The ops sweep was refuted - a catch-all claim made the orphan guard vacuous, and two of the pass's own findings did not reproduce

**Evidence:**
- SEVERE, AND SELF-INFLICTED THE SAME DAY: claim_path(lane, '**') matched every unowned path in the repository, so the orphan guard reported green with a genuinely orphaned file on disk. Reproduced by the integrator - unowned_paths(['some/random/unowned.txt']) returned [] under a catch-all claim. The sanctioned pressure valve opened all the way
- THE QUIETER HALF, also reproduced: capture claiming 'lanternlight/*.py' reaches lanternlight/redact.py, which safety owns and holds a veto over, and stale_claims() did not flag it because it compared the PATTERN as a path rather than what the pattern REACHES
- FIXED by overreach(), which walks the REAL TREE - two patterns can differ textually and still match one file, the same reason tests/test_lanes.py walks the tree instead of comparing globs. A claim is refused at write time AND reported stale if one is already on disk, so a claim smuggled in by hand is still caught
- A lane may still claim within its OWN slice; refusing that would make the mechanism useless to the lane most likely to need it
- ATOMICITY WAS UNTESTED IN THE FILE THAT CLAIMED TO TEST THE WRITER. Deleting tmp_path.replace(target) from the only sanctioned writer of docs/LEDGER.md left the suite at 1101 passed. Now covered by refusing the replace and asserting the ledger is BYTE-UNCHANGED: the same mutation gives 10 failed
- TWO VISIBILITY ASSERTIONS WERE 'is False' ONLY, so they would pass vacuously the moment the probe returned None - the same skip-vacuity this class was already caught by once. They now assert the probe answered at all
- python -m pytest -> '1108 passed in 25.35s' observed this run; 1101 before. python -m ruff check . -> All checks passed

TWO OF THE PASS'S FINDINGS DID NOT REPRODUCE, and this is recorded because a refutation pass is evidence, not authority. It reported that a four-backtick fence and an info string on a closing fence each MINT A PHANTOM ENTRY with no error. Probed directly, both returned the correct id list and neither produced a phantom. What IS real is smaller and points the other way: fence delimiter LENGTH was not tracked, so a longer or shorter inner run confused the scanner into a FALSE REFUSAL on legal Markdown - loud, not silent. Fixed properly by tracking (character, width) and requiring a closer to be the same character, at least as long, and free of an info string, per CommonMark. 'open4 inner3' now parses as ['LL-0001'] where it previously raised.
THE DIRECTION OF THAT ERROR MATTERS. A false refusal is the failure mode that gets a guard switched off, so it is worth fixing - but it is not the silent-loss class the pass claimed, and recording it as one would have overstated the danger in exactly the way this session has been correcting all day.
FOUR LESSER FINDINGS ARE ACCEPTED AND RECORDED RATHER THAN FIXED. OPS-10: the ledger writer's byte-preservation self-check is still deletable in silence, and LL-0042 over-claimed that it was covered - the behavioural tests cover the OUTCOME, and nothing forces the assertion path. OPS-11: a 4-space indented code block whose first token is id-shaped is falsely refused. The mistyped-fragment limit is now stated in the docstring in the PRESENT tense rather than only in the ledger, and classify_claim documents its precedence when a collision and an edit are both present.
THE PASS'S MERGE JUDGEMENT WAS 'safe to merge, but LL-0038 and LL-0042 both overstate scope'. The overstatements are corrected here rather than defended: each claimed to close a CLASS while a reachable instance of that class survived.

### LL-0043 - 2026-08-12 - Session close - the ops queue swept from seven open items to one, and every fix found a larger hole beside the one that was filed

**Evidence:**
- python -m pytest -> observed this run on the wrap branch with __pycache__ purged: 1101 passed. 953 at session start
- python -m ruff check . -> All checks passed
- A FRESH CLONE IS STILL GREEN, which is the property ROADMAP 2d bought earlier in this same session and the reason any of these counts mean anything outside this machine
- LL-0033 ROADMAP 2d, LL-0034 the heading P0, LL-0035 ROADMAP 7's shipped code, LL-0036 the first wrap, LL-0037 the wrap refutation's four holes, LL-0038 OPS-9, LL-0039 OPS-7, LL-0040 OPS-8, LL-0041 OPS-2, LL-0042 OPS-1/3/5
- ops lane open items went from OPS-1,2,3,5,6,7,8 plus OPS-9 opened mid-session, down to OPS-6 alone
- Pre-push redaction scan over the outgoing DIFF, not the tree, at every push this session: 0 plain findings and 0 encoded, each time with a positive control of 5 on the same text plus a planted id

THE PATTERN OF THE WHOLE SESSION, stated once so it is not rediscovered: EVERY defect closed today was TWO HALVES OF ONE THING DISAGREEING, or a guard that covered the instance rather than the class. The id race, the malformed heading, the unclosed fence, the guard-versus-parser split, absent-versus-unreadable, edited-versus-collided, and a path guard that pinned two known sources instead of the property. The fix each time was to delete the second opinion, never to teach it the same rules.
MUTATION TESTING FOUND WHAT READING DID NOT, four separate times. A surviving mutant exposed the unreadable-fragment path (OPS-7), the unpinned claim branch (OPS-2), the unpinned fence delimiter (LL-0037) and - the sharpest - a whole test class that SKIPPED instead of failing when its probe broke (OPS-3/5). That run read '1094 passed, 7 skipped', which looks green. A guard that stands down when the thing it guards breaks is not a guard.
THREE FILED COUNTS WERE WRONG THIS SESSION - '278 window readings', '11 shared ids', '46 hash lines'. The last is the instructive one: it grows with every entry, so FILING it was the error rather than mis-measuring it. It is now quoted nowhere.
HEREDOC BACKSLASH MANGLING BIT THREE TIMES and stale mutation anchors three times. Every one was refused by its own assertion rather than reported as a clean green - which is the entire argument for asserting the anchor before believing a survivor.
OPS-6 IS THE ONLY OPEN OPS ITEM AND IS NOT MINE TO TAKE: retiring the global LL-NNNN id space for per-lane namespacing changes what 43 entries and every citing roadmap item, branch and commit refer to. Detection makes it a considered decision rather than an urgent one.
NOTHING IN EMBERFORGE CHANGED and no damage coefficient was published. The 21 measured hits remain damage TAKEN; outgoing damage is four log samples. Item 7b, the training ground, is still the cheapest unblocker and still needs the client open.

### LL-0042 - 2026-08-12 - OPS-1, OPS-3 and OPS-5 closed - the ledger writer gets its own tests and the git-visibility guard stops skipping what is not on disk

**Evidence:**
- OPS-3/OPS-5 MEASURED FIRST: the visibility guard read 'rel not in acceptable AND Path(rel).exists()', so every path not yet on disk was SKIPPED. Fragments are created lazily, so it was checking 4 of 7 writing lanes and reporting green
- THE PROBE IS NOW ABOUT THE RULE, NOT THE LISTING: lanes.git_would_take asks git check-ignore, which answers for a path that does not exist, and also catches OPS-5's second half - an ignore rule added AFTER a file is tracked, which a listing-based probe cannot see
- THE DOCUMENTED TRAP WAS RE-MEASURED RATHER THAN TRUSTED: check-ignore exits 0 when any pattern matches INCLUDING A NEGATION. Confirmed live on tests/fixtures/gvas/standalone_slot.gvas.b64, which is re-included by '!tests/fixtures/**/*.gvas.b64' and still exits 0. So the exit code is not the answer - the matched PATTERN is, and a leading '!' means git would take the file
- OPS-1 CONFIRMED AS A REAL GAP: ops/loop/ledger.py, the only sanctioned writer of docs/LEDGER.md, had no test module. It was exercised incidentally by three other test files, which tests the CALLER's path rather than the module's promises
- tests/test_loop_ledger.py: 27 tests over validation, ASCII refusal at the field, rendering, newest-on-top, byte-for-byte preservation of everything below the marker, refusal without a marker, no write on a refusal, no temp file left behind, and LF endings asserted on BYTES
- NON-VACUITY, __pycache__ purged and every anchor asserted unique: ignore negations in check-ignore -> 1 failed; stop answering for an unmatched path -> 3 failed; drop the ASCII enforcement -> 4 failed; stop refusing a markerless ledger -> 2 failed; put the newest entry at the bottom -> 3 failed; restored -> 1101 passed
- python -m pytest -> '1101 passed in 22.23s' observed this run; 1069 before. python -m ruff check . -> All checks passed

A MUTANT EXPOSED VACUITY IN THE NEW TESTS THEMSELVES, and this is the most useful thing in the entry. The first version skipped whenever git_would_take returned None, so breaking the probe turned every test in the class from a FAILURE into a SKIP: the mutation run read '1094 passed, 7 skipped', which looks green. A guard that stands down when the thing it guards breaks is not a guard. Availability is now measured independently with 'git --version', so a None from the probe on a machine that has git is a real failure. Re-run, the same mutation gives '3 failed'.
THE OLD GUARD WAS POINTED AT THE NEW PROBE rather than left beside it. It kept its own notion of visibility - a set of listed paths - and two readers of one fact is the shape of OPS-9 and of every other defect in this module. There is now one answer to 'would git take this'.
OPS-1 WAS NOT MERELY A MISSING FILE. The module's one real promise - that every byte already below the marker survives an append - is self-checked in code and had NO test, so the check could have been deleted silently. That is exactly how integrate()'s reversed() was found to be decoration in an earlier session.

### LL-0041 - 2026-08-12 - OPS-2 closed - a lane adding a new file can go green on its own, without editing a roster it is forbidden to touch

**Evidence:**
- REPRODUCED FIRST: a fresh clone plus one new lanternlight/ module -> '1 failed, 34 passed', the orphan guard naming the file and telling the reader to declare it in ops/lanes.py, which only the OPS lane may edit. Any other lane is red for its whole session with no in-slice remedy
- END TO END AFTER THE FIX, same procedure on a clone of the branch: lane adds a file -> '1 failed, 38 passed'; lane calls claim_path('ingest', 'lanternlight/newthing.py') -> '39 passed'
- THE FAILING TESTS CAME FIRST: 12 failed in TestALaneCanClaimAPathItIsAdding before implementation
- A CLAIM IS A PROMISSORY NOTE, NOT A SECOND OWNERSHIP MAP, and three guards enforce that: lanes.owner_of() is untouched so the roster remains the source of truth; two claimants on one path is still a failure with its own live test; and a claim the roster has ALREADY absorbed is STALE and fails until released, so a redeemed note cannot linger
- lanes.path_matches() was made public so a claim is matched by exactly the roster's normalisation. Re-implementing it beside the roster is how the two would drift, and this repo has already paid for a separator bug there - lstrip('./') strips CHARACTERS and ate the leading dot of every dotfile
- NON-VACUITY, __pycache__ purged and every anchor asserted unique: accept any number of claimants -> 1 failed; ignore claims entirely, i.e. the pre-fix guard -> 1 failed; stop reporting stale claims -> 1 failed; make a claim never match -> 5 failed; restored -> 1069 passed
- python -m pytest -> '1069 passed in 22.14s' observed this run; 1050 before. python -m ruff check . -> All checks passed

NEITHER OPTION THE ITEM OFFERED ACTUALLY REMOVED THE FRICTION, which is why a third was built. 'ops declares ownership first' needs the filename known before the work starts, which is usually false - the name is a result of the design, not an input to it. 'The integrator declares it at merge' is how lanternlight/damage.py shipped earlier this same session and it does work, but only for an integrator spanning both lanes; a lane running alone still sits red for its whole session. That matters beyond convenience: a lane stuck red cannot use the suite as a signal, its merge-gate baseline is noise, and it is under exactly the pressure CLAUDE.md names when it says never weaken a guard to make a build pass.
THE GUARD'S INTERESTING HALF WAS UNPINNED AT FIRST, and only mutation testing would have shown it. The claim branch lived inside the test, and the real repository has no claimed path - so deleting that branch left the suite green. The predicate now lives in unowned_paths() where it can be exercised on a synthetic tree, and the mutation that ignores claims entirely goes red.
THE ASCII GUARD CAUGHT THE AUTHOR. A non-ASCII character was typed into one of the new tests to check that claims are validated; tests/test_ascii_hygiene.py failed the whole repository for it, correctly. It is now built with chr(0xEF) instead. The guard that fired is one this project wrote for itself.
A LANE MUST STILL RELEASE ITS CLAIM once the integrator writes the path into ops/lanes.py, and stale_claims() runs over the real state files on every suite run so a forgotten one cannot survive a merge.

### LL-0040 - 2026-08-12 - OPS-8 closed - an entry edited after integration is no longer misdiagnosed as an id collision, and the remedy was the opposite one

**Evidence:**
- REPRODUCED BEFORE ANY FIX, on a throwaway copy of the real ledger: integrate an entry, change one number in the integrated copy, re-run. It raised LedgerIdCollision saying the id was 'claimed twice by DIFFERENT entries' and instructed the reader to RENUMBER the fragment's entry by hand
- THAT REMEDY IS ACTIVELY WRONG FOR THIS CAUSE. Renumbering an edited entry records ONE piece of work under TWO ids - it corrupts the record while appearing to repair it. The two faults have opposite remedies and shared one message
- THE DISCRIMINATOR, and it is exact: two FRAGMENTS holding different content under one id means two lanes allocated it independently, because they branch from a common base and both get the same answer to 'what is the next free id'. One fragment differing from the LEDGER means the entry was integrated and a copy then changed, because nothing else could have put it there
- THE FAILING TESTS CAME FIRST: 4 failed before implementation, covering both classifications and both rendered remedies
- classify_claim() returns EDITED_AFTER_INTEGRATION or TWO_LANES_COLLIDED; format_duplicate_claims() prints the matching remedy and labels each source as ledger or fragment. Verified on the reproduction: 'classification: edited-after-integration', and the rendered report says 'Do NOT renumber it'
- integrate() sees ONE fragment and the ledger, so it genuinely CANNOT tell the two apart. It now NAMES BOTH CAUSES with their opposite remedies and points at duplicate_claims(), which can. Omit rather than guess, applied to a diagnosis
- NON-VACUITY, __pycache__ purged and every anchor asserted unique: call everything a collision (the pre-fix behaviour) -> 2 failed; call everything an edit (the opposite error) -> 1 failed; stop marking which claim came from the ledger -> 2 failed; restored -> 1050 passed
- python -m pytest -> '1050 passed in 26.58s' observed this run; 1043 before. python -m ruff check . -> All checks passed

THE DECISION OPS-8 ASKED FOR, TAKEN AND STATED RATHER THAN IMPLIED. The item offered two options: policy (an integrated entry is never edited) or code (reconcile the fragment automatically). POLICY STANDS. Auto-reconciliation would write to a lane fragment, which this module documents as append-only and never edited, so fixing a REPORTING defect would have broken a core invariant to do it. The append-only contract is also what this session already followed in practice - LL-0037 corrects LL-0031's claims by appending a new entry rather than editing the old one.
SO THE GUARD STILL GOES RED ON AN EDITED ENTRY, DELIBERATELY. That is not the defect. A durable record disagreeing with the lane's own copy is worth stopping for; what was broken was being told the wrong reason and the wrong remedy. The red is now self-explaining.
ONE OF THIS ENTRY'S OWN TESTS ASSERTED THE WRONG THING FIRST and is corrected rather than deleted: it asserted the word 'renumber' was ABSENT from the edited-entry report. The report legitimately contains it while FORBIDDING it. Asserting the absence of a word is not the same property as asserting the absence of an instruction, and only the second is what the reader needs.

### LL-0039 - 2026-08-12 - OPS-7 closed - a fragment path that is not a fragment now says so, and an existing-but-unreadable fragment no longer reads as absent

**Evidence:**
- THE FILED DEFECT: integrate('ops') - a lane ID where a fragment PATH belongs - reached a directory and surfaced a bare 'PermissionError: [Errno 13] Permission denied' on Windows. An errno is not a diagnosis
- THE FAILING TESTS CAME FIRST: 6 failed before implementation, across a bare lane id, a directory, all three entry points, and every writing lane id rather than only 'ops'
- THE FIX: one _fragment_text reader used by fragment_entry_ids, integrate and duplicate_claims. A bare lane id raises NotAFragment and NAMES THE PATH IT SHOULD HAVE BEEN; a directory raises naming it as one; a genuinely missing fragment still returns None so callers still read it as empty
- THE TOLERANCE THE FIX HAD TO PRESERVE IS ITSELF PINNED: fragments are created lazily on a lane's first entry, so absence is the NORMAL state for most lanes. A mutation making a missing fragment an error -> 5 failed, so the guard cannot quietly become over-strict
- A MUTANT SURVIVED AND FOUND ONE MORE SILENT PATH. Widening the catch back to a bare 'except OSError' left the suite at 1042 passed - nothing pinned what happens when a fragment EXISTS and cannot be read, so a lane with entries would have reported as a lane with none. That is the same silent-loss shape as every other defect in this module. Now covered: the read is monkeypatched to raise PermissionError and the call must raise rather than return []. Re-run, the same mutation -> 1 failed
- NON-VACUITY, __pycache__ purged and every anchor asserted unique: stop refusing a bare lane id -> 2 failed; stop refusing a directory -> 4 failed; swallow everything again -> 1 failed; make a missing fragment an error -> 5 failed; restored -> 1043 passed
- python -m pytest -> '1043 passed in 22.37s' observed this run; 1035 before. python -m ruff check . -> All checks passed

THE FILED ITEM UNDERSOLD ITSELF. OPS-7 was recorded as a cosmetic error-message complaint - 'caller error, but the error should name the mistake'. Following it properly surfaced a real silent-failure path that was not in the item at all. That is the third time in two sessions that fixing a small filed item exposed a larger one beside it, and the mechanism each time was mutation testing rather than reading.
WHY A FILENAME CONVENTION WAS NOT USED. The obvious stricter rule - demand that a fragment be named <lane_id>.LEDGER.md - was measured against the existing tests first and rejected: they legitimately pass paths like tmp_path/'LEDGER.md' and tmp_path/'nope.md'. Enforcing the convention would have failed real callers to catch a typo, which is the false-positive trade this module has already been burned by. The refusal is scoped to what cannot possibly be a fragment: a directory, or a bare lane id.
A MISSING FRAGMENT AND A MISTYPED ONE ARE STILL INDISTINGUISHABLE, and that is stated rather than hidden. integrate('lanes/opss.LEDGER.md') still returns [] silently. Closing that needs the naming convention rejected above, or a caller-supplied lane id - neither is free, and the lazy-creation behaviour is load-bearing. Not filed as a new open item because it is a known consequence of a deliberate design, recorded here so the next reader does not rediscover it as a bug.

### LL-0038 - 2026-08-12 - OPS-9 closed - the heading guard and the heading parser now share one fence scan, and a THIRD private reader turned up while closing it

**Evidence:**
- THE DEFECT: _assert_headings_parse skipped fenced lines while _blocks_below used _HEADING_RE.finditer over the whole entry region, which knows nothing about fences. So inside a code block a WELL-FORMED heading was parsed as a real entry while a MALFORMED one beside it was ignored - the guard protecting a region the parser read differently
- IT IS NOT HYPOTHETICAL: docs/LEDGER.md documents its own entry format with a fenced '### LL-0000 - ...' example, safe today only because it sits ABOVE the entries marker. Quoting an example entry below the marker, or in a lane fragment, minted a phantom entry with a real id
- THE FAILING TESTS CAME FIRST: 4 failed before implementation, including 'assert [LL-0900, LL-9999] == [LL-0900]'
- THE FIX: one _scan_entry_region walks the region once, tracks fences, and returns heading offsets, the first malformed-heading suspect, and any unclosed fence. The guard and the splitter both consume it, so there is no second opinion left to disagree with
- A THIRD PRIVATE READER WAS FOUND WHILE FIXING THE FIRST TWO: fragment_entry_ids had its own _HEADING_RE.finditer as well. It is now on the shared scan. Three readers meant three chances to disagree, and only two of them were in the filed defect
- _HEADING_RE is now referenced in exactly ONE place in the module - verified by grep, which also matched three docstring mentions, so the pattern was proven to match before the count was believed
- REAL-REPO PARITY AFTER THE CHANGE: docs/LEDGER.md still parses 37 entries LL-0037 down to LL-0001, and the fragments still parse safety 3, ingest 5, ops 6, research 1 - so the stricter parser changed no existing reading
- NON-VACUITY, __pycache__ purged and every anchor asserted unique: splitter reverted to its own finditer -> 3 failed; fragment_entry_ids reverted -> 1 failed; the scan stops tracking fences -> 5 failed; restored -> 1035 passed
- python -m pytest -> '1035 passed in 23.10s' observed this run; 1030 before. python -m ruff check . -> All checks passed

THE PATTERN, now four for four in this module: every bug here has been TWO HALVES OF ONE PARSER DISAGREEING. The id race (fragments merged cleanly, integrate skipped silently), the malformed heading (guard knew the shape, parser did not), the unclosed fence (toggle vs reality), and now the guard-versus-parser split. The fix each time is to delete the second opinion rather than to teach it the same rules.
A TEST FAILING FOR AN UNEXPECTED REASON IS WHAT FOUND THIS. OPS-9 was opened during the previous wrap because a tilde-fence test failed in a way its author had not predicted - the fence suppressed the guard but not the parser. Reading the failure rather than adjusting the assertion is what turned a confusing red into a filed defect.
ONE ASSERTION IN THIS ENTRY'S OWN TESTS WAS WRONG AND IS CORRECTED RATHER THAN DROPPED: the first draft asserted the phantom heading's TEXT never reaches the ledger. It does, and it should - it is part of its author's entry body, and an append-only record must not rewrite what was written. The property that matters is that the phantom id never becomes an ENTRY, so the assertion is now about the parsed ids rather than about the bytes.

### LL-0037 - 2026-08-12 - The wrap refutation pass holed LL-0034's own fix - a forgotten backtick disarmed the guard and returned SUCCESS while eating an entry

**Evidence:**
- THE WORST HOLE, reproduced by the integrator before any fix rather than relayed: the fence state was a bare toggle, so an entry that opened a code fence and never closed it left every following line counted as code and the guard stood down for the rest of the file. integrate() -> ['LL-0900'], NON-EMPTY, which reads as SUCCESS; LL-0901 never landed as its own entry; its text was absorbed into LL-0900's block; no exception. WORSE than the LL-0034 defect, which at least returned []
- SECOND HOLE: the id pattern was [A-Z]{2,6}-\d{3,}, i.e. today's ids. A malformed heading with any other shape failed the heading pattern AND the id pattern and fell through into silence - lowercase, mixed case, 1-letter and 7-letter prefixes, 2 digits, and no hyphen. OPS-7 and SAF-0001 both sit outside that pattern and both exist in this repository
- THIRD HOLE, against LL-0033: the 2d guards pin primary_checkout() and WORKTREE_ROOT specifically, not the class. The pass embedded Path.home() and regenerated - 1009 passed on this machine with C:\Users\Administrator committed into a contract, while a checkout under a different USERPROFILE measured '1 failed, 1008 passed'. The 2d symptom exactly, invisible here
- FOURTH HOLE, against LL-0035: gvas.parse omits an undecodable property from .properties and records it in .unknown_properties, so 'never written' and 'written but our reader failed' both answered None
- THE FAILING TESTS CAME FIRST: 12 failed before any implementation, across the unbalanced-fence class, seven id shapes, the absolute-path class guard and the unreadable-property case
- ALL SIX MUTANTS NOW RED, __pycache__ purged and every anchor asserted unique: id shape narrowed to LL-NNNN -> 7 failed; fence delimiters narrowed -> 2 failed; unbalanced-fence refusal deleted -> 6 failed; id matched anywhere instead of first-token -> 2 failed; Path.home() embedded in a contract -> 2 failed; undecodable property reading as absence -> 2 failed
- python -m pytest -> '1030 passed in 21.88s' observed this run; 1009 before this entry. python -m ruff check . -> All checks passed
- duplicate_claims over the real repository -> no id is claimed by two different entries, and no malformed heading

THE VERDICT IS ACCEPTED AS GIVEN. The pass returned LL-0034 as PARTIAL with 'it should not be recorded as closing the silent-entry-loss class'. That was correct and the claim is corrected in ROADMAP 2c rather than defended. Both refutation passes this session found real defects in work that had already been called done, and one of them found a defect in the FIX for the previous one.
A FILED COUNT WAS WRONG FOR THE FOURTH TIME IN TWO SESSIONS. LL-0034 cited '46 lines start with # below the marker'; it was 47 at that commit and 51 four commits later. The count grows with every entry, so filing it was the error rather than mis-measuring it. It is no longer quoted anywhere, including the docstring that recited it.
OPS-9 OPENED, DELIBERATELY NOT FIXED HERE. The heading GUARD respects code fences; the heading PARSER does not - _HEADING_RE.finditer runs over the whole entry region, so a WELL-FORMED heading inside a code block is parsed as a real entry while a malformed one beside it is ignored. Found while writing the tilde-fence test, when the test failed for a reason its author had not predicted. Two halves disagreeing is the shape of every bug in this entry, so it deserves a considered fix and not a quiet one during a wrap.
PROSE CORRECTIONS in lanternlight/damage.py, all re-measured: the window holds a mean of 1.06 records and 1.62 hits per generation over the 262 generations carrying the field, ranging 0-2 and 0-8, so 'roughly two monster entries' was wrong and it is closer to one; the six-value totalDamage series is a sampled subsequence, not consecutive generations; and the claim that the clock offset belongs to 'the machine that played' is now hedged, because a fixed -05:00 applied server-side would look identical on one machine's data. Separating them needs a capture from another zone or across a DST boundary.
A HEREDOC MANGLED BACKSLASHES A THIRD TIME this session, and a stale mutation anchor was caught a third time. Both were refused by their own assertions rather than reported as clean greens. The rule earned twice over: write the script to a file, and assert the anchor before believing any survivor.

### LL-0036 - 2026-08-12 - Session close - 2d and item 7's shipped half closed, a P0 found in the ledger machinery, and every prior test count reclassified

**Evidence:**
- python -m pytest -> '1009 passed in 27.02s', observed this run on main with __pycache__ purged; 1009 collected. 953 at session start
- python -m ruff check . -> All checks passed
- FRESH CLONE OF MAIN, the acceptance that matters: git clone of C:\Lanternlight into a scratch directory at a foreign path, then python -m pytest -> '1009 passed'. At 311cef8 the same procedure gave '1 failed, 952 passed'
- main 311cef8 -> 0d919c0, pushed. All NINE branches now on the remote; every one is fully merged into main (0 commits not reachable from it), so pushing them uploaded no new objects
- PRE-PUSH SAFETY, on the outgoing DIFF rather than the tree: 103,524 characters scanned through lanternlight.redact -> 0 plain findings and 0 encoded findings, with a POSITIVE CONTROL of 5 findings on the same text plus a planted id, so the zero is a real zero and not a dead scanner. No capture-derived filename reached a commit. 282 redaction/PII/ascii/walker tests green
- LL-0033 ROADMAP 2d, LL-0034 the heading P0, LL-0035 ROADMAP 7's shipped-code half - each with its own evidence and each integrated into docs/LEDGER.md through lane_state.integrate

THE RECLASSIFICATION IS THE DURABLE RESULT. Every 'N passed' recorded in this repository before 2026-08-12 - 927, 943, 953 and all their predecessors - was true IN PLACE and not in a clone, because the generated lane contracts embedded the generating machine's absolute paths and the drift guard compared them against a fresh render. 1009 is the first count measured from a fresh clone at a foreign path. README.md is corrected; it had told contributors the opposite.
TWO REFUTATION PASSES, OPPOSITE OUTCOMES, WHICH IS THE ARGUMENT FOR RUNNING THEM. 2b confirmed all eight of its claims including the 882/96/21 positive control and found no dead detector among 15. 2c returned a P0 - a heading one character off is not merely unparsed, it is INVISIBLE, so integrate() returns [] and the entry is gone. That is LL-0031's own defect through a different door, in the machinery closed to prevent it. Agreement between slices would have proved nothing; disagreement is what found this.
A SECOND TRIGGER OF 2d WAS IN NOBODY'S PLAN. worktree_path() does not derive from the checkout, so LL_WORKTREE_ROOT reddened the suite IN PLACE - where every other symptom of the item was invisible. The item was filed as path-dependence on the checkout; it was path-dependence on ANY absolute path the generator saw. The new guards are behavioural rather than substring checks for exactly that reason.
THE P0 FIX SHIPPED A SILENT BUG FIRST. A heredoc collapsed the backslashes in _ID_TOKEN_RE, turning \\b into a literal BACKSPACE byte; the regex compiled cleanly and matched nothing, so the new guard was entirely dead. Second heredoc mangling of the session - the first aborted a mutation probe on its anchor assertion, which is the only reason it did not read as 'the guard is vacuous'. Do not use a heredoc for anything containing a backslash.
ITEM 7's WALL-CLOCK JOIN FOUND MORE THAN IT WAS ASKED FOR: the save's timeStamp is not a Unix epoch, it encodes LOCAL wall clock as though it were UTC, confirmed on two independent surfaces. to_utc() now refuses without an explicit offset rather than shifting every hit by five hours.
OPEN AND DELIBERATELY UNANSWERED, both operator decisions: OPS-6 (retire the global LL-NNNN id space for per-lane namespacing) and OPS-8 (whether a ledger entry may be edited after integration). Item 7 also stays open on its coefficient question, which needs an INDEPENDENT run - one run cannot separate a coefficient from a lucky repeat.

### LL-0035 - 2026-08-12 - ROADMAP 7 - the damage series is shipped code, and the save's timeStamp turned out not to be a Unix epoch

**Evidence:**
- lanternlight/damage.py owned by ingest, tests/test_damage.py with 37 tests; ownership declared in ops/lanes.py and the eight lane contracts regenerated
- THE CLOCK TRAP, measured on TWO INDEPENDENT SURFACES. Surface 1, the capture files' own mtimes: the run ran 22:27:00 to 22:46:54 UTC (17:27 to 17:46 local, machine at UTC-5). Reading the hit timestamps as a Unix epoch renders them 17:28:10 to 17:45:11 'UTC' - five hours BEFORE the run started, which is impossible, and numerically equal to the run's LOCAL wall clock
- Surface 2, the log, which timestamps in real UTC and emits the same DamageCollectionComponent payload: across 5 readings at THREE separate times of day (14:48, 20:43, 22:36 UTC) the delta log-UTC minus timestamp-as-epoch is 18009.056 to 18014.747 seconds - 5.0025 to 5.0041 hours. Exactly the operator's UTC offset plus a few seconds of event-to-emission lag, and the lag is POSITIVE, which is the physically correct direction
- CONSEQUENCE IN THE API: as_local_naive() returns a NAIVE datetime because the save does not know a timezone, and to_utc() raises UnknownClockOffset rather than inventing one. The offset belongs to the machine that played, is absent from the save, and moves with daylight saving. test_reading_it_as_an_epoch_falls_OUTSIDE_that_window pins the wrong reading so that the right one is not vacuous
- END TO END over all 263 captures, the shipped module reproducing the scratchpad analysis exactly: 263 generations, 262 with a payload, 424 window readings, 21 distinct hits, span 1020.344 s, total 1284.835785, monsterIds (1005 1006 1014 1029 2003 2007 2017 2021), 9 instances, direction 'monster' only, nameId 0 only
- THE WALL-CLOCK JOIN WORKING: with the offset supplied the first and last hits land at 22:28:10.921 and 22:45:11.265 UTC, both inside the 22:27:00 to 22:46:54 window measured independently from file mtimes
- The COMMITTED fixture carries DamageCollectonDataSet (one record, one hit, 118.453857421875 at 1786297499.5909998, monsterId 2017), so the JSON shape is characterised against real game bytes and no out-of-repo data is needed to ship or test this
- python -m pytest -> '1009 passed in 27.41s' this run; 972 before. python -m ruff check . -> All checks passed

ABSENCE IS PRESERVED AS A FACT. damage_set_from_save returns None when the property is missing - measured on generation 1, 2,190 bytes, written at match start before combat - and () for a present-but-empty payload. Both are falsy, which is exactly the trap, so a test pins the distinction rather than trusting a caller to remember it.
THE DEDUPLICATION KEY IS THREE FIELDS ON PURPOSE. Damage here is deterministic and three values repeat exactly across the run, so collapsing on value would erase real hits; two sources can share a millisecond, so collapsing on time would too.
NOTHING IS LABELLED BEYOND WHAT IS PROVEN. No coefficient is computed. All 21 hits carry sourceType 1, so the module reports direction 'monster' for them and nothing else; source_of() returns None for any sourceType never observed rather than folding it into the nearer of the two. Item 7 stays open on the coefficient question, which needs an INDEPENDENT run - one run cannot separate a coefficient from a lucky repeat, however precise the float.
OPS-2 is exercised rather than merely recorded: its second option, the integrator declaring ownership at merge, is the one that works, because the orphan guard goes red the instant an unowned file exists and so file and ownership cannot land in separate commits.

### LL-0034 - 2026-08-12 - P0 - a malformed ledger heading was skipped in silence, which is the LL-0031 defect through a different door

**Evidence:**
- FOUND BY THE INDEPENDENT ADVERSARIAL PASS on ROADMAP 2c, which shipped without one. REPRODUCED BY THE INTEGRATOR BEFORE ANY FIX rather than relayed, on a throwaway copy of the real docs/LEDGER.md carrying a genuinely colliding LL-0018
- THE DEFECT: with heading '###  LL-0018 - ...' (one extra space) fragment_entry_ids -> [], duplicate_claims -> [], integrate -> [], ledger unchanged, entry absent. With the well-formed heading the same three calls give ['LL-0018'], ['LL-0018'] and a raised LedgerIdCollision. One character decides whether a collision is refused or an entry silently disappears
- WHY IT IS THE SAME BUG: integrate returning [] with no error is exactly what LL-0031 was written to end - the integrator reads [] as 'already done'. 2c closed the door and left the window open
- THE FAILING TESTS CAME FIRST: 15 tests in TestAMalformedHeadingIsRefusedNotSkipped over five malformed shapes (two spaces, no space, one hash short, one hash too many, colon for dash) -> '11 failed, 4 passed' before the fix
- THE FIX: _assert_headings_parse raises MalformedLedgerHeading naming file, line number and text. Scoped to NON-FENCED lines carrying an id-shaped token, because a rule that fires on ordinary prose gets switched off and then the real collision passes too
- SCOPE MEASURED BEFORE IT WAS CHOSEN: 46 lines start with '#' below the marker across docs/LEDGER.md and every lane fragment, and all 46 parse - so the strict rule refuses nothing legitimate today
- AFTER THE FIX all three entry points raise where all three previously returned empty, and the ledger is byte-unchanged
- NON-VACUITY, __pycache__ purged and every anchor asserted unique before each run: guard removed from _blocks_below -> 5 failed; removed from fragment_entry_ids -> 6 failed; id-token test forced always-false -> 11 failed; restored -> 84 passed
- python -m pytest -> '972 passed in 25.69s' this run; 957 before this change. python -m ruff check . -> All checks passed

THE FIX ITSELF SHIPPED A SILENT BUG FIRST, and it is recorded because the shape is the lesson. A heredoc collapsed the backslashes in _ID_TOKEN_RE, turning '\\b' into a literal BACKSPACE byte (0x08). The regex compiled without complaint and matched nothing, so the new guard was completely dead while the module imported cleanly. Caught only because the tests still failed. 'An empty grep is a claim about your pattern' applied to a guard - and the second heredoc backslash mangling this session, the first having aborted a mutation probe.
THREE CLAIMS IN LL-0031 ARE CORRECTED, not edited away. (1) '11 ids exist in both the ledger and a fragment' was wrong when written - re-derived as 13 today and 12 at the commit that wrote it; all still compare equal, so the conclusion survives but the number did not. (2) 'zero survivors' under mutation does not hold: flattening CRLF and stripping the final newline are both DEAD CODE, unreachable because read_text performs universal-newline translation, so only the per-line rstrip is load-bearing. That is the same vacuous-CRLF trap the item documents, hit again from the other side. (3) A real false positive exists - editing an entry already integrated into docs/LEDGER.md makes it differ from its fragment forever, so integrate raises and the live test stays red until reconciled by hand.
OPS-8 records that false positive rather than fixing it here. The right answer may be that an integrated entry is simply never edited, which is a policy decision about an append-only record and not a code change to make quietly.
The 2b refutation, run in parallel against the same frozen ref, CONFIRMED all eight of its claims including the 882/96/21 positive control and the LL-0029 P0 fix, and found no dead detector among 15. Two independent passes, opposite outcomes - which is the argument for running them at all rather than assuming a closed item is closed.

### LL-0033 - 2026-08-12 - ROADMAP 2d - a fresh clone now runs green, so a test count is a fact about the repo rather than about this machine

**Evidence:**
- THE DEFECT, MEASURED END TO END BEFORE ANY EDIT: git clone of 311cef8 into a scratch directory, then python -m pytest -> '1 failed, 952 passed in 29.55s', the failure being tests/test_lane_contract.py::TestOnDiskMatchesTheRoster::test_the_files_on_disk_equal_what_the_roster_renders with all eight lanes listed stale
- ROOT CAUSE: ops/lane_contract.py:_workspace_block interpolated lanes.primary_checkout() and lane.worktree_path() - both absolute - into text that is then COMMITTED, while the drift guard compares the committed file against a fresh render. The two agreed only at C:\Lanternlight
- THE FAILING TESTS CAME FIRST: four new guards in TestTheContractIsCheckoutIndependent, run before the fix -> '4 failed, 21 deselected in 0.47s'
- THE FIX AFTER: same clone procedure at 5725c03, cloned to a different path, python -m pytest -> '957 passed in 24.95s'
- grep for 'C:\', '/Lanternlight' and 'll-worktrees' over the CLONED .claude/commands/ -> NONE. The generated artifacts now name no absolute path at all
- NON-VACUITY, both halves, __pycache__ purged before each run and the anchor asserted before believing any survivor: re-embed the checkout path -> 3 failed (test_rendering_does_not_change_when_the_checkout_moves, test_no_contract_names_the_checkout_directory, and the drift guard); re-embed the worktree path -> 3 failed (the matching worktree pair, and the drift guard); restored -> 957 passed
- THE FIRST MUTATION PROBE ABORTED ON ITS OWN ANCHOR ASSERTION - a heredoc mangled the backslashes so the anchor did not match. Without that assertion it would have reported a clean GREEN and been read as proof the guard was vacuous. The mutation script was moved to a file
- A SECOND, INDEPENDENT TRIGGER OF THE SAME DEFECT was found and is also closed: LL_WORKTREE_ROOT=/some/other/place at 311cef8 fails IN PLACE -> '1 failed, 20 passed', so the suite was not merely path-dependent on the checkout. At 5725c03 the same command -> '957 passed'
- python -m pytest in the lane/ops worktree -> '957 passed in 24.79s'; baseline 953 measured with --collect-only before dispatching
- python -m ruff check . -> All checks passed
- ops.merge_gate.verify(claimed_paths=[ops/lane_contract.py, tests/test_lane_contract.py, .claude/commands/lane-ops.md], baseline=953) -> 'merge gate: OK (957 tests collected)'

ONE EXISTING TEST CHANGED SHAPE, stated rather than hidden: test_the_branch_and_worktree_are_named asserted str(lane.worktree_path()) in text, which cannot survive a relocated checkout. It was made STRONGER rather than relaxed - it now asserts the lane's own worktree DIRECTORY is named AND that no other lane's directory appears, which catches a lane pointed at a sibling's worktree. A test that is weakened to go green is invisible to an exit code, so the change is recorded here.
The new guards are BEHAVIOURAL, not substring checks: rendering must not change when the checkout moves, and must not change when the worktree root moves. That goes red for a path re-embedded later, including one nobody has thought of yet - which a grep for 'C:\Lanternlight' would not.
CONSEQUENCE FOR EVERY EARLIER COUNT: 927 in LL-0028, 943, 953 and every 'N passed' before this entry were true IN PLACE and not in a clone. 957 is the first number in this project's history measured from a fresh clone at a foreign path.
OPS-4 is closed by this entry. It was recorded in LL-0021 as 'path-dependent' and sat open through three sessions because the symptom looked cosmetic; what made it worth doing is that README.md tells a new contributor to clone and run pytest, so the documented first-run experience was a red suite.

### LL-0032 - 2026-08-11 - Session close - 2b and 2c closed, merged to main, and 2d handed to the next session

**Evidence:**
- python -m pytest -> '953 passed in 34.94s', observed this run in the primary checkout with __pycache__, .pytest_cache and .ruff_cache purged; 807 at session start
- python -m ruff check . -> All checks passed
- main is 814b1ea, pushed and verified by REF COMPARISON not exit code: local and origin/main identical; working tree clean, 0 ahead 0 behind
- public main scanned blob by blob by the integrator: 113 blobs, zero 15+ digit runs, zero 32-hex runs, zero CJK, zero detector hits
- commit hygiene across every commit added to main this session: zero non-ASCII, zero Co-Authored-By
- docs/LEDGER.md: 31 entries below the marker, LL-0001 to LL-0031, zero duplicates, strictly descending; lane_state.duplicate_claims() over the live repository returns NONE
- merge gate run by the integrator against every lane before merging: safety 829, ingest 860, fixture 927, safety P0 943, ops 953 - each against a baseline measured beforehand

ROADMAP 2b and 2c are CLOSED and on main. 2d is OPEN and is the next item by explicit operator direction.
REFUTATION COVERAGE, stated plainly rather than implied. One adversarial pass ran, pinned to 060d48d, and it covered the serialiser, the detectors, the research docs and the merger's own damage claims. It found a P0 and five corrections. TWO SLICES LANDED AFTER IT AND HAVE HAD NO INDEPENDENT PASS: the sanitised fixture, and the 2c ledger fix. Both are covered by the integrator's own before-and-after re-measurement on real data plus the lanes' mutation proofs, which is weaker evidence than a separate agent and is labelled as such. Next session should refute both against the frozen main.
THE 2c VERIFICATION IS THE LESSON, NOT THE FIX. The dangerous failure was never the collision - it was OVER-TIGHTENING, because a comparison that is too strict turns every legitimate re-run into a false collision, which gets a force flag bolted on, which disarms the guard for real collisions too. The integrator mutated the normaliser and probed it with CRLF; nothing changed, which read as proof the guard was one-sided. THE PROBE WAS VACUOUS - read_text performs universal-newline translation, so CRLF was gone before any comparison ran. Re-probed with trailing whitespace, which survives the read, the real code stays idempotent while a byte-exact comparison raises. This repository's own 'a mutation that fails to apply looks exactly like a passing test' was hit WHILE SPECIFICALLY WATCHING FOR IT, and the rule that caught it was the companion one: assert the mutation applied before believing the result.
TWO REMEDIATIONS OPENED THE HOLE THEY WERE CLEANING, in one session. Authoring the Blueprint GUIDs - which ROADMAP 2b REQUIRED - removes the PRODUCTUSERID false positive that was accidentally the only thing refusing a third party's display name. Then redact() itself, the only sanctioned redaction path, disarmed the NAME_FIELD guard written to close that hazard, because it rewrites the decoration to a placeholder containing angle brackets and the anchor required alphanumerics. Nothing leaked either time. Two instances is a pattern: CHECK WHAT YOUR FIX REMOVES, NOT ONLY WHAT IT ADDS.
OPEN AND NOT ANSWERED ON THE OPERATOR'S BEHALF: whether to retire the global LL-NNNN id space in favour of per-lane namespacing (OPS-6). SAF-NNNN is collision-free by construction, but retiring the global space changes what 31 existing entries and every citing roadmap item, branch and commit refer to.
STILL UNSETTLED AND BLOCKING FOR EMBERFORGE: whether a damage number is DEALT or TAKEN beyond the 21 hits now proven to be taken. Item 7b answers it in the training ground. Until then no number may be labelled either way.

### LL-0031 - 2026-08-11 - ROADMAP 2c - integrate() now tells a re-run from an id collision, and refuses the collision

**Evidence:**
- python -m pytest -> '953 passed in 30.59s', observed this run in the lane/ops worktree with __pycache__ purged; baseline 943 collected, measured before the change and re-measured as the sum of the --collect-only per-file counts
- python -m ruff check . -> All checks passed
- THE FAILING TEST CAME FIRST and reproduced the filed defect verbatim: tests/test_lane_state.py::TestTwoLanesClaimingOneId::test_the_second_lanes_entry_is_never_lost_without_a_word failed with 'SILENT DATA LOSS: the research lane's LL-0023 entry is gone. integrate returned [], raised nothing, and the heading is absent from the ledger'
- ops/lane_state.py: LedgerIdCollision, _normalise_block, _blocks_below, IdClaim, duplicate_claims, format_duplicate_claims; integrate() compares CONTENT per id instead of the id alone and writes nothing when it refuses
- SAME id SAME content is still a silent skip - idempotence is load-bearing and the pre-existing test_integration_is_idempotent still passes untouched
- six mutations, zero survivors, each anchor asserted to match exactly once, __pycache__ purged between every run, source restored and sha256-verified: M1 drop the raise -> 3 red; M2 never skip identical content -> test_integration_is_idempotent red; M3 byte-exact compare -> the CRLF test red; M4 make everything compare equal (the original bug) -> the loss test red; M5 duplicate_claims stops filtering identical claims -> 4 red; M6 duplicate_claims finds nothing -> 1 red
- the guard is proven to fire BOTH ways, which is the point: M1 and M4 prove a collision cannot pass, M2 and M3 prove a re-run is not mistaken for one
- docs/LEDGER.md preamble prose corrected, and the 83,718 bytes below the entries marker are byte-identical to HEAD - proven by comparison, not by intent
- duplicate_claims() over the real repository: 30 ledger entries, 11 fragment ids already integrated, zero clashes reported - so the same-content path is exercised against real data and the live-repository test is not vacuous

WHAT 'SAME CONTENT' MEANS, and why the choice matters more than it looks: line endings, per-line trailing whitespace, and leading/trailing blank lines are normalised away; nothing else is. Those three can change without an author touching a character - Windows write_text turns LF into CRLF, read_text hides it, and .gitattributes, a checkout on another platform and an editor each rewrite them. Interior blank lines and leading indentation are NOT normalised, because they carry meaning in Markdown. The two possible errors are not symmetric: too loose drops an entry, too STRICT calls a legitimate re-run a collision, blocks recovery after a partial merge, and gets a force flag bolted on - which disarms the guard for every real collision as well. Strictness was chosen with that asymmetry in mind.
PREVENTION BY ALLOCATION IS REFUTED and this is why it was not attempted: lanes branch from a common base, so two lanes asking 'what is the next free id?' get the same answer and both take it. That is exactly what happened with LL-0023. Detection is what can actually be guaranteed.
RECORDED, NOT DECIDED - open item OPS-6. The safety lane's accidental SAF-NNNN namespace is collision-free BY CONSTRUCTION, which the global LL-NNNN space is not, so per-lane namespacing is a real long-term answer. It is NOT implemented, deliberately: retiring the global space changes what 30 existing entries mean and what every roadmap item, branch name and commit message citing an LL id refers to. That is an operator decision, and the detection guard makes it a considered choice rather than an urgent one.
NOT DONE, and named rather than left implied: ROADMAP.md item 2c is not marked closed here, because ROADMAP.md is outside this lane's file set. The integrator closes it. Nor is duplicate_claims() wired into any wrap ritual or the merge gate - it is called by TestDuplicateClaimsSurfacesTheHazardEarly::test_the_live_repository_has_no_colliding_id, so a collision cannot reach a merge unnoticed even with the ritual skipped, but ops/loop/ and ops/merge_gate.py were not in this lane's file set this session.

### LL-0030 - 2026-08-11 - Refutation pass - a P0 in this session's own guard, and five corrections to LL-0028's claims

**Evidence:**
- python -m pytest -> '943 passed in 30.45s', observed this run in the primary checkout with __pycache__ purged; baseline 927 measured before dispatching the fix
- python -m ruff check . -> All checks passed
- THE DEFECT, reproduced by the integrator against the real 177,878-byte capture BEFORE the fix: iter_sensitive gave NAME_FIELD 3 on the raw bytes and {} after redact(), the 17-character third-party display name was still verbatim in the output, and assert_clean(redact(raw)) PASSED CLEAN
- AFTER the fix, same command, same bytes: NAME_FIELD 3 -> 3, and assert_clean REFUSES naming 'unredacted NAME_FIELD at offset 157746 (line 135)'. That before/after on identical real input is stronger evidence than any mutation
- satisfiability re-checked by the integrator so the rule is not merely always-on: the committed fixture scans EMPTY raw, EMPTY after redact(), EMPTY through the encoded pass, and assert_clean PASSES on it
- the safety lane reported 12 mutations with zero survivors, including the window-shrunk mutation reddening tests/test_no_pii.py - which proves the committed fixture is EVALUATED by this rule rather than passing beside it
- the pushed remote tree was scanned independently by the integrator at edf5698: 113 blobs, zero 15+ digit runs, zero 32-hex runs, zero CJK, zero detector hits. NOTHING LEAKED - this was a broken guard, not a spill

THE MECHANISM IS THE LESSON. redact() rewrites the Blueprint decoration to the placeholder <PRODUCTUSERID>. NAME_FIELD's anchor required [0-9A-Za-z], angle brackets are not alphanumeric, so the anchor died and the rule went quiet. REDACTING THE FILE IS WHAT BROKE THE GUARD - the sanctioned remediation path disarmed the protection, exactly as authoring the GUIDs was earlier measured to remove the false positive that was accidentally load-bearing. Two instances, one session, of a fix opening the hole it was cleaning.
AND THE TEST PASSED FOR THE WRONG REASON. test_the_name_field_survives_authoring_the_guid_away used a 32-character ALPHANUMERIC stand-in, which satisfies the anchor. The tested case was not the case the module's own redactor produces. This repository's most expensive recurring failure, hit again by the lane that exists to prevent it.
THE FIX IS NOT A WIDENED CHARACTER CLASS. The decoration is now a run of UNITS, each either one alphanumeric character or a whole placeholder matched by the module's own _PLACEHOLDER constant, and a test asserts every placeholder any rule emits conforms to it - so a placeholder added later is covered the day it lands rather than silently disarming the rule again.
TWO MORE HOLES CONFIRMED AND FIXED: the authored-marker check asked only whether the marker appeared within 64 bytes of the property NAME, so a file could SELF-AUTHORISE with a value of <AUTHORED_NAME> followed by a real name; it now demands the marker be a complete FString with its own length prefix and terminating NUL, anchored after the type token. And the rule covered only StrProperty, so NameProperty and TextProperty slipped past; NAME_BEARING_TYPES now names all three. NARROWED NOT CLOSED, and stated as such: two name-bearing properties within 48 bytes could still cross-authorise.
SAF-13 is honest about its own weakness: NameProperty and TextProperty were added by REASONING about the GVAS format, not by measurement - neither has been observed in any capture. A TextProperty value sits behind an FText header, so the 48-byte authored window is an assumption for that token, and that same window is what blocks neighbour cross-authorisation, so it cannot simply be widened.
FIVE CORRECTIONS TO LL-0028, all from the same pass, none of which change a committed artifact but all of which change what may be CLAIMED. (1) DIRECTION IS SETTLED, and it deflates the headline: PlayerData.Hp is sampled 262 times and its 13 drops total 1286 against the damage set's 1284.84, pairing individually - 108.53+83.74=192.27 against a 192 drop, 17.36+92.13=109.49 against a 110 drop. The 21 hits are damage TAKEN. Re-measured by the integrator. So they constrain survivability, NOT build math; Emberforge is unblocked by the LOG's four sourceType 0 payloads with ability attribution, not by the save's twenty-one. (2) 'a float to nine places' is wrong - the values are float32 and a repeat pins about 7 significant digits. (3) The five repeats of 9.745483398 ARE the 1.5s tick, so counting them as independent evidence double-counts one computation; the real evidence is 83.74041748 on two different instances. (4) 'the first timing constant this project has measured' is too strong at n=3 intervals from one encounter at a 1ms quantisation floor. (5) 'nameId and SkillNameId are the same id space, PROVEN, not inferred' was an over-claim: n=1 shared value, 6130007 never appears as a skillNameId, and 'from the same component family' was FLATLY WRONG - skillNameId comes from leaderRankScoreComponent, battleSnapUpdate and battleSettlement, never from DamageCollectionComponent.
MEASURED AND FILED AS ROADMAP 2d: the suite is only green IN PLACE. A fresh clone gives '1 failed, 926 passed' - test_lane_contract bakes the absolute REPO_ROOT into the rendered contract. Verified by the integrator with a real clone, and it fails at 548e5b6 too, so it predates this session. Every 'N passed' this project has recorded, including LL-0028's 927, is an in-place number. README.md tells a new contributor to clone and run pytest, so the documented first-run experience is a red suite.
WHAT THE PASS COULD NOT SETTLE, recorded rather than glossed: 'damage is deterministic' is now known to be a statement about INCOMING damage only - nothing measured here says anything about damage the player deals, which is what Emberforge actually needs.

### LL-0029 - 2026-08-11 - P0 - redact() disarmed my own NAME_FIELD guard, so redacting a file was what broke it - anchor rebuilt from the module's own placeholder shape

**Evidence:**
- full suite 943 passed, 943 collected from the lane worktree - baseline for this slice was 927 collected at edf5698, so no drop; ops.merge_gate.verify(claimed_paths=[lanternlight/redact.py, tests/test_redact.py], baseline=927) reported 'merge gate: OK (943 tests collected)'
- TDD: 11 new tests written first and watched fail. The headline failure read "AssertionError: assert 'NAME_FIELD' in set()" where the set was computed over redact()'s own output, which still carried the display name verbatim; the assert_clean half read "Failed: DID NOT RAISE <class 'lanternlight.redact.RedactionError'>"
- REPRODUCTION AFTER THE FIX, over the record shape the capture writes (three name-bearing StrProperty fields decorated with 32-char hex Blueprint GUIDs, invented display name): RAW {PRODUCTUSERID: 3, LONG_ID: 3, NAME_FIELD: 3} -> AFTER redact() {NAME_FIELD: 3}; the name is still verbatim in redact()'s output (True), and assert_clean now REFUSES with 'unredacted NAME_FIELD at offset 0'. Before the fix the same probe gave AFTER redact() {} and assert_clean PASSES CLEAN
- SATISFIABILITY RE-PROVEN on the same shape: with the three values authored, RAW {PRODUCTUSERID: 3, LONG_ID: 3} -> AFTER redact() {} and assert_clean passes clean
- COMMITTED FIXTURE UNAFFECTED: tests/fixtures/gvas/standalone_slot.gvas.b64 decoded (19867 bytes) gives {} before and after redact(), and assert_clean passes clean on both. The fixture was not touched
- NON-VACUITY, 12 mutations, zero survivors. Every mutation asserted its anchor matched EXACTLY ONCE before the run, and every __pycache__ in the tree was deleted before each run. RED: decoration tolerating no placeholder (5 tests); index tolerating no placeholder (1); the authored check being the bare marker rather than a whole FString (2); the authored check not anchored after the type token (2); the authored window widened to 400 so a neighbour can authorise (1); the authored window shrunk to 4 so nothing can be authored (6, including tests/test_no_pii.py, which proves the committed fixture really is evaluated by this rule); NameProperty dropped (1); TextProperty dropped (1); the type-token requirement deleted (3); the whole rule unregistered (18); the measured-only wording removed from the refusal (1); and the test file's own derived placeholder set forced empty (1)
- the placeholder set the tests run against is DERIVED from RULES and DETECT_ONLY_RULES at runtime rather than listed, and a separate test asserts every placeholder those rules emit matches redact._PLACEHOLDER - so a placeholder added tomorrow is covered on the day it is added
- both files 7-bit ASCII; no real identifier appears in any file or message - every fixture is assembled from fragments at runtime and the display name used throughout is invented

WHAT WENT WRONG, precisely. The anchor spelled the Blueprint decoration as (?:_\d+_[0-9A-Za-z]{1,64})?. redact() rewrites that GUID to <PRODUCTUSERID>, and an angle bracket is not alphanumeric, so after redaction the anchor no longer matched, NAME_FIELD went quiet, and assert_clean certified a record with a third party's display name still byte-for-byte in it. The project's only sanctioned redaction path was the thing that disarmed the guard against it.
WHY THE TEST DID NOT CATCH IT. test_the_name_field_survives_authoring_the_guid_away used NON_HEX_GUID - a 32-character ALPHANUMERIC string, which satisfies the old anchor. The tested case was not the case redact() actually produces, so the test passed for the wrong reason. That is this repository's most expensive recurring failure and it happened inside the lane that owns the guard, in the same commit that added it.
THE FIX IS NOT A WIDER CHARACTER CLASS. A class widened by hand to swallow angle brackets breaks again the next time a placeholder shape changes. The decoration is now a run of UNITS, each unit being either one alphanumeric character or a whole placeholder matched by _PLACEHOLDER - the same constant every rule in the module already replaces with. The tolerated shape is therefore derived from the module rather than kept in sync with it by memory.
HOLE (a) - CONFIRMED, and worse than reported. The authored check asked only whether the literal marker appeared within 64 bytes of the property NAME, so a file could authorise itself: a value of <AUTHORED_NAME> followed by a real display name silenced the rule and shipped the name. Fixed twice over. The check is now anchored AFTER the type token, and it demands the marker as a COMPLETE FString - its 4-byte little-endian length prefix, the marker, the terminating NUL - so the marker has to BE the value, not merely be near one or start it. The window is 48 bytes past the type token; the measured offset of the value FString is 9, confirmed against the committed fixture. NARROWED, NOT CLOSED: two name-bearing properties inside 48 bytes of each other, one authored and one not, could still cross-authorise. The measured record puts them about a hundred bytes apart and a test pins the neighbour case directly.
HOLE (b) - CONFIRMED and fixed. The rule anchored on the literal token StrProperty, so the same three property names written as NameProperty or TextProperty walked straight past it. NAME_BEARING_TYPES now names all three string-valued tokens. Non-string tokens stay out and a test pins that an IntProperty still does not fire, because a rule whose whole value is that it fires rarely must not fire on a field that cannot hold a name.
HOLE (c) - CONFIRMED, and it is a limit to publish rather than a defect to fix. The property list grows by measurement only, so it is now said in two places a reader actually meets: the module docstring's stated-limits section, and the RedactionError itself, which says the list is extended by measurement only and that the rule going quiet is not a certificate that the record carries no other person's name. Both are pinned by tests.
NO EXISTING RULE WAS WEAKENED and the committed fixture was not touched. The fixture was verified clean by direct scan and does not go through redact(), so nothing leaked - this was a broken GUARD, not a leak. Every change here makes the rule fire in strictly more places except the authored branch, which is the branch that keeps the rule satisfiable.
RECORDED AS SAF-13: NameProperty and TextProperty were added by reasoning about the format, not by measurement - neither appears in any captured save. A TextProperty's value sits behind an FText header rather than directly after the size and guid bytes, so the 48-byte authored window is an assumption for that token and must be re-measured if one is ever observed.

### LL-0028 - 2026-08-11 - Session wrap - ROADMAP 2b closed, a GVAS serialiser, and Emberforge unblocked by a field nobody had read

**Evidence:**
- python -m pytest -> '927 passed in 30.41s', observed this run with __pycache__, .pytest_cache and .ruff_cache purged; baseline measured at 807 before dispatching
- python -m ruff check . -> All checks passed
- merge gate run by the integrator against each lane before merging: safety OK at 829, ingest OK at 860, fixture slice OK at 927, every one against a baseline measured beforehand
- serialise(parse(raw)) == raw RE-MEASURED BY THE INTEGRATOR, not relayed: 276/276 byte-identical across 6 committed fixtures, 7 live saves and all 263 captured generations
- tests/fixtures/gvas/standalone_slot.gvas.b64 - 19,867 raw bytes from a 177,878-byte source, parses with undecoded_trailing b'', is_complete, zero unknown properties, 17 top-level properties, round-trips, sha256 collides with none of 7 live saves and none of 273 captures
- POSITIVE CONTROL re-run by the integrator: the pre-sanitised source scans 882 plain (PRODUCTUSERID 772, LONG_ID 100, OWNER_ROLEID 3, NAME_FIELD 3, SAVE_SLOT 2, ACTOR 2), 96 encoded, 21 on the base64 text; the fixture scans 0, 0, 0 under both FILE_SCAN_LABELS and the stricter ALL_LABELS
- docs/LEDGER.md verified after integration: 27 entries below the marker, LL-0001 to LL-0027, zero duplicates, strictly descending

THE BIGGEST RESULT IS A REFUTATION OF THIS REPOSITORY'S OWN ROADMAP. It said Emberforge could not be filled because no numbers existed, and named item 1 as the only unblocker. False for two days: the transient save writes per-hit damageValue with sub-millisecond Unix timestamps, and 263 generations were already captured. 21 distinct hits were extracted from 278 rolling-window readings. Three damage values repeat EXACTLY with distinct timestamps - 83.740417480 landed identically on two DIFFERENT instances of the same monster type - so damage is computed, not rolled. Three consecutive gaps of 1.501, 1.499, 1.499 seconds are the first timing constant this project has measured.
AND THE NAIVE READING OF THAT SERIES WOULD HAVE BEEN BACKWARDS. The log's DamageCollectionComponent emits the same structure with Key POPULATED where all 424 save readings had it empty, giving three first-party bindings - 6130017 NormalArrow, 6130007 ExplosionArrow, 6250000 MonsterDamage - and showing sourceType 0 = player is source with monsterId null, sourceType 1 = monster is source with monsterId populated. All 21 extracted hits are sourceType 1, so they are most likely damage TAKEN. Labelled an INFERENCE and not a measurement, because it rests on a single sourceType 1 payload and the save's empty Key is unexplained. No number is labelled dealt or taken until item 7b settles it.
nameId and SkillNameId ARE the same id space - 6130017 appears as both in the same log. So nameId 0 means UNSET, not absent.
THE SHARPEST SAFETY FINDING: a third party's display name sits in plaintext in the save (KillPlayerHistoryDatas.PlayerName, plus MsgSubChannelString and MsgAppearanceString) and NO content rule can reach it - GVAS writes key and value as separate length-prefixed strings, persona discovery returns zero candidates, and a display name has no shape. Worse, those bytes were refused today ONLY because a Blueprint GUID beside them tripped PRODUCTUSERID - a FALSE POSITIVE that was accidentally load-bearing. Authoring the GUIDs, which item 2b REQUIRED, removes the only thing that was standing between a stranger's name and a public repository. The answer was a structural detect-only rule, NAME_FIELD, not a content rule.
A PROVEN DEFECT IN THE CONTINUITY MACHINERY, found during this wrap and worked around rather than fixed - now ROADMAP 2c. Two lanes on separate branches both allocated LL-0023; git merged both cleanly because they wrote to different files. integrate() then SILENTLY DROPPED one, returning [] with no exception, because it skips ids already present. Reproduced against a throwaway copy of the real ledger. LL-0018's fragment design solved the TEXT race and left the ID race untouched, and the fragment design is what hides it. Ids were renumbered by hand and verified; the next multi-lane session hits this again.
FIVE CLAIMS BY THE MERGER WERE REFUTED BY ITS OWN LANES AND BY RE-MEASUREMENT: BattleId shares 12 leading digits with the roleId, not 14 - the merger's probe counted matching positions ANYWHERE rather than a leading prefix; the save has 17 top-level properties, not 19; LevelDetail is int-keyed and only DropItemMap is float-keyed; KillPlayerHistoryDatas is not an empty solo null but holds a 10-field record; and 61 supposed monster instance ids under MonsterData were GUID-INTERNAL DIGITS, not ids at all - only 38 of 100 LONG_ID hits are genuine identifiers.
THE ROUND-TRIP EARNED ITS KEEP ON THE FIRST RUN. Byte identity caught TextProperty's int32 FText flags word, read and discarded since the module was written, invisible to every existing test because they all check decoded values rather than bytes.
THIRD-PARTY SOURCES REVIEWED AND TIERED, so it is not re-done: questlog.gg is DATAMINED - it addresses monsters by numeric id in the same space the save uses and lists [Debug] and [Discarded] developer rows no player can see. gamerguides is HAND-MAPPED and says so, with a database whose first iteration was built on the DEMO. Opposite provenances, opposite failure modes. Neither may write an id into docs/OBSERVED_IDS.md. One cross-check held: their 1029 is Hallowgrove Woodling and this project independently measured 1029 on a Hallowgrove run whose internal map is Whitewoods_Day.
REFUTATION COVERAGE, stated honestly: an adversarial pass was dispatched against pinned commit 060d48d covering the serialiser, the detectors, the docs and the merger's own damage claims, and had NOT RETURNED when this entry was written. The fixture slice that landed afterwards has NOT been through an independent pass at all - it is covered by the integrator's own re-measurement of all nine acceptance criteria plus the lane's 8 of 8 mutation proofs, which is weaker evidence than a separate agent and is labelled as such. Any finding from that pass lands as a NEW entry, per this ledger's own correction rule.

### LL-0027 - 2026-08-11 - a third party's display name in the save is not reachable by any content rule - structural NAME_FIELD guard instead

**Evidence:**
- full suite 841 passed, 841 collected from the lane worktree - baseline for this slice was 829 collected, so no drop; tests/test_no_pii.py 42 passed
- REFUTED that any existing detector covers the field: on the real save discover_personas returns 0 candidates for the record region, redact() leaves the name byte-for-byte intact, and the keyed PlayerName persona rule cannot even match because the property is written PlayerName_19_<GUID> with no separator anywhere
- the new rule fires 3 times on the real capture, once per name-bearing property, at the three measured offsets
- THE COUPLING, measured: today the record is refused only because the Blueprint GUID beside it trips PRODUCTUSERID. Replacing every 32-hex run in the real save with a non-hex string - which is exactly what the fixture is required to do - takes PRODUCTUSERID to 0 and LONG_ID from 100 to 38, and NAME_FIELD still objects 3 times. Without it the remediated fixture would have had zero objections to shipping a third party's display name
- satisfiability proven on the real bytes too: inserting the authored marker beside each property takes NAME_FIELD from 3 findings to 0
- NON-VACUITY, 6 mutations, zero survivors after two rounds: deleting the rule, dropping the authored-marker lookahead, dropping the StrProperty anchor, letting redact() rewrite the detect-only rules, dropping DETECT_ONLY_RULES from the scanning path, and removing the remedy from the failure message all went RED
- EXISTING TREE UNAFFECTED: NAME_FIELD run over all 110 tracked files as they exist at HEAD gave 0 plain and 0 encoded findings
- ruff clean, both files 7-bit ASCII

THE HONEST ANSWER TO 'CAN A DETECTOR SEE THIS': no, and not for want of trying. A keyed rule cannot reach it because GVAS writes the property name and its value as two separate length-prefixed strings with a binary size between them - there is no '=' or ':' in the file. Persona discovery is blind for the same reason. A shape rule cannot work either, because unlike a save slot a display name HAS no shape. A rule that matched arbitrary strings inside a save would flag the whole file, and a guard that flags everything trains people to ignore it, which costs more than it saves. So the guard is STRUCTURAL: it recognises the PROPERTY, not the value, and requires an authored marker beside it. Copy the record and it fires; author the value and it goes quiet.
WHY IT IS DETECT-ONLY. A GVAS record is a chain of length-prefixed strings, so substituting a placeholder for the property name would change a byte count the format depends on and corrupt the blob, while leaving the value it was meant to protect exactly where it was - strictly worse than doing nothing. redact() therefore walks RULES only and the new DETECT_ONLY_RULES tuple is scanned but never substituted. The failure message carries the remedy, because the only party who can fix this is whoever builds the artifact.
TWO MUTATION SURVIVORS ON THE FIRST ROUND, both real defects in my own tests. The prose test passed on the NUL requirement alone and never pinned the StrProperty anchor, so that anchor was free to delete - fixed with a test proving an integer-valued property does not fire while a string-valued one does. Worse, the message test asserted 'author' in message.lower() and passed with the remedy branch disabled, because the fallback quotes the matched text and my own sentinel constant was named AUTHORED_GUID. An assertion satisfied by the fixture rather than by the behaviour is decoration; the constant is renamed and the assertion now pins the remedy wording.
CORRECTION TO SAF-9, filed last slice. 'The fixture authors its GUIDs' is not sufficient as written: the hex rule keys on shape and cannot tell an authored GUID from a real ProductUserId, so an authored GUID that is still 32 hex characters changes nothing at all. It has to stop being a hex run. Re-filed with that correction and pinned by a test.
SCOPE LIMIT, stated rather than hidden: NAME_BEARING_PROPERTIES lists the three properties MEASURED to carry free text. A fourth that exists but was not in this capture is not covered, and no pattern could find it - the list grows by measurement. SAF-12 records that nothing yet asserts the check ran against the fixture specifically, only against whatever is committed.

### LL-0026 - 2026-08-11 - ROADMAP 2b - name the save-file id shapes, and record the Blueprint-GUID false positive rather than silence it

**Evidence:**
- full suite 829 passed, 829 collected from the lane worktree - baseline before the work was 807 collected, so no drop
- TDD: 15 new tests written first and watched fail; one failure read 'assert <ACTOR> == <SAVE_SLOT>', which confirmed the rule-ordering hazard empirically instead of by inspection
- NON-VACUITY, 7 mutations, zero survivors: deleting each of BATTLEID, OWNER_ROLEID, ROLEID and SAVE_SLOT went RED; moving SAVE_SLOT after ACTOR with nothing else changed went RED; narrowing PRODUCTUSERID to lowercase hex went RED; raising the LONG_ID floor above the GUID-internal stretch went RED
- mutation harness asserted each anchor matched EXACTLY ONCE before believing a survivor, confirmed the targeted tests green BEFORE each mutation, cleared __pycache__ before every run, and restored the suite green afterwards
- EXISTING TREE UNAFFECTED: the four new labels run over all 109 tracked files as they exist at HEAD, read from git blobs rather than the working tree, gave 0 plain findings and 0 encoded findings; tests/test_no_pii.py passes
- the only file the new rules did flag was this lane's own new test source, which held a literal 17-digit run - split across two literals as that file already does for every other invented identifier
- ruff clean on lanternlight/redact.py and tests/test_redact.py, both 7-bit ASCII

WHY THE RULES ARE A RENAMING AND NOT A CHANGE OF COVERAGE. Each keyed detector takes a digit run at LONG_ID's own floor, which is now the single named constant _LONG_ID_MIN_DIGITS rather than a literal repeated in two places. Every value they decline is a value LONG_ID declines too, so nothing that was caught before stops being caught; what they add is the label. LONG_ID itself is untouched.
The digit floor is not stylistic. These rules run over every tracked file, and the tree already holds two innocent collisions: docs/FINDINGS.md records a generated bot's roleId (five digits, negative, naming no person) and ROADMAP.md discusses BattleId in ordinary English. A key=<anything> rule fires on both and turns tests/test_no_pii.py red on published files that are perfectly safe.
SAVE_SLOT is matched by SHAPE, not by key, because a .sav is GVAS - a key and its value are two separate length-prefixed strings with no separator between them, so there is no key=value on disk for a keyed rule to find. It must also precede ACTOR: StandaloneSlot_<19 digits> fits the actor-token shape exactly, and in the wrong order the slot name is reported as a player display name, which is a wrong answer rather than an imprecise one.
MEASURED, AND IT CORRECTS THE RECORD. BattleId is a StrProperty of 19 digits sharing 12 leading digits with the roleId, measured identically across all 250 captured generations - an earlier note recording 14 is REFUTED. The prefix is also the smaller half of the problem: the roleId appears VERBATIM 5 times (2 slot names, 3 ownerRoleId in ItemCell JSON) and 5 further distinct ids share 17 of its 19 digits. A fixture that masks the roleId alone still ships 17 of its 19 digits five times over. Re-scoped as SAF-8; SAF-3 closed, since its question - does the redactor cover this shape - is now answered and implemented.
FALSE POSITIVE RECORDED, NOT SILENCED. Unreal stores a Blueprint property name as Name_Index_<32 uppercase hex GUID>. That GUID trips PRODUCTUSERID 772 times (67 distinct: 65 Blueprint shapes, 2 monsterGuid values) and, through two GUIDs that happen to carry a 17- and a 16-digit decimal stretch, LONG_ID 62 times out of 100. One cause, two rules - a reader who knew only about the hex rule would conclude that keying or lowercasing it fixes this, and it does not.
OPTION (a) TAKEN, NEITHER RULE NARROWED. Case is not a safe discriminator: the same 32 characters identify the same account in either case, and any formatter in the path can change one without changing the other. Position is not safe either, because a real ProductUserId can sit in the same textual slot - the bare hex rule exists precisely to fire with no key in sight. A narrowing on either axis buys a quieter build log and sells a silent false negative, and the failure direction here is already the safe one: the guard refuses a commit rather than publishing an identity. A GUID is a format fact of the shipped asset, not a machine fact, so the fixture authors its own GUID suffixes and both classes clear at once without a detector being touched. SAF-9 carries that constraint to whoever builds the fixture, with a positive control in the tests proving a real-shaped identifier in the same textual position is still caught.

### LL-0025 - 2026-08-11 - Transient dungeon save decoded from its whole 263-generation lifetime - 8 filed claims re-measured, 2 refuted, 2 redaction false-positive classes named

**Evidence:**
- python -m pytest -> '807 passed in 26.70s', observed this run; baseline 807 collected, unchanged
- python -m pytest tests/test_no_pii.py tests/test_ascii_hygiene.py -> '46 passed in 19.28s', observed this run
- all 263 captured generations parse with lanternlight/gvas.py in strict mode, zero failures, undecoded_trailing empty on the largest
- independent PII sweep of both edited docs against 227 secret tokens harvested from the capture and the live log - zero hits; zero 15+ digit runs and zero 32-hex runs in either file
- docs/FINDINGS.md section 10 added (10.1 to 10.13); docs/OBSERVED_IDS.md gains the save-derived id section above the closing Rule
- capture bytes remain at C:\ll-captures\saves\, outside the repository, uncommitted

REFUTED - the largest generation holds 17 top-level properties, not the 19 filed. The filed claim listed 17 and counted 19; the list was right.
REFUTED - LevelDetail is int-keyed in all 1,102 key observations across the lifetime, not float-keyed. Only DropItemMap is float-keyed, in all 1,058 of its key observations.
REFUTED - LeaderRankScoreData.KillPlayerCount is 1 and KillPlayerHistoryDatas holds one entry, so the 'empty in a solo run' premise is false. The conclusion survives in corrected form: that structure is what would carry a real player's name in PvP, and it carries a bot's name here. The record asserts IsPlayer true AND IsBot true at once, so the save counts a bot kill as a player kill - FINDINGS 9.3.2's trap on a second surface.
REFUTED - BattleId shares the roleId's leading 12 digits, not 14, measured as the longest common prefix. 14 is shared by 5 of the 16 in-file long ids, not by BattleId.
CONFIRMED and sharpened - the PRODUCTUSERID rule fires 772 times, every hit a false positive; all uppercase against a lowercase real ProductUserId, and none of the 67 distinct 32-hex runs appears anywhere in the live log. The LONG_ID rule fires 100 times of which 62 sit inside two Blueprint property GUIDs. One 32-hex Blueprint GUID defeats a hex detector and a digit-length detector at once.
NEW and material for ROADMAP item 2b - the roleId is INSIDE the bytes, twice, as AutoSaveFinalSlot='StandaloneSlot_<roleId>' and AutoSaveTempSlot='StandaloneSlot_<roleId>_Temp'. Renaming the fixture file does not redact it, and the roadmap's fixture note says only that the filename embeds it.
NEW - the roadmap's '23-entry NumIdToUUID' is 23 in exactly 5 of 263 generations and 91 in the largest. A filed count is a hypothesis, hit again. CurrentNum is a high-water counter and disagrees with the map length in 123 generations, so it must never be used as a size.
MEASURED rather than asserted - the three-integer map key IS positional. Dead partitions Translation perfectly (39 living monsters carry a zero vector, 22 dead carry a real one), so the naive comparison across all 61 would have refuted the reading on a comparison artefact. Over the 22 meaningful records the per-axis correlations are +0.992, +0.941, +0.969 and key/100 sits 102 to 1,524 units from Translation. Which frame the key is in, and the physical unit, remain unmeasured.
NEW structure - PlayzoneData is a shrinking-circle mechanic in the game's own field names: DmgCircleLocation/Radius, SafeCircleLocation/Radius, FinialSafeCircleLocation (its spelling), ElapseTime. The circles are identical to the bit in the sampled generation, so this capture caught the zone before it moved. The Gyldenmist Tolerance talent is a plausible player-facing name and is recorded as UNBOUND, not as a binding.
NEW - enumerator names are unknowable from these bytes. E_DoorState and E_LockState serialise as Unreal's unrenamed NewEnumeratorN defaults. Observed over the whole lifetime: DoorState 1/2/3 and LockState 0/2. DoorState 0 never appears in 10,836 values and LockState 1 never appears in 12,137. The field named Opened holds a DoorState and the field named Locked holds a LockState - neither is a boolean.
NEW ids recorded in docs/OBSERVED_IDS.md with the method named, all UNBOUND: 19 monster config ids, 3 zone-name strings, container ids, 5 eight-digit assist-source ids, a bot AttributeId, LevelDetail keys, and 23 item cfgIds new to this project out of 39 distinct in the save. The new-id list was derived twice - the first version wrongly included one already-recorded id and wrongly omitted another, so it was recomputed by set difference.
OPEN, recorded not answered: no monster, container, zone or item id in this save is bound to a name. Nothing in the save carries a name string, so binding needs the wall-clock pixel join that bound the class ids.

### LL-0024 - 2026-08-11 - ROADMAP 2b - the sanitised StandaloneSlot fixture, authored with transform()+serialise() and refused by its own builder until clean

**Evidence:**
- tests/fixtures/gvas/standalone_slot.gvas.b64 - 19867 raw bytes from a 177878-byte source, 26841 bytes of base64, 349 lines, LF, 7-bit ASCII
- parse(): undecoded_trailing b'', is_complete True, unknown_properties (), key_profiles (), 17 top-level properties
- serialise(parse(fixture)) == fixture: True. Build is reproducible - the same source produces byte-identical output on a second run
- sha256 differs from all 7 live saves and from all 273 captured generations (271 distinct digests). No collision
- iter_sensitive over the raw fixture: 0 findings under FILE_SCAN_LABELS and 0 under the stricter ALL_LABELS
- iter_encoded_sensitive over the committed base64: 0. Plain scan of the base64 TEXT: 0
- POSITIVE CONTROL, same scans over the pre-sanitised bytes planted in a tmp dir: 882 plain findings (PRODUCTUSERID 772, LONG_ID 100, OWNER_ROLEID 3, NAME_FIELD 3, SAVE_SLOT 2, ACTOR 2), 96 through the encoded pass over its base64, and 21 on the base64 text itself. Fixture 0/0/0 - so the clean result is a distinction, not a no-op
- full suite 927 collected 927 passed against a baseline of 894 measured before the work; tests/test_gvas.py + tests/test_gvas_fixtures.py 273 passed; ops.merge_gate.verify OK at 927 against baseline 894
- TDD: the fixture was registered in FIXTURES first and 9 tests watched fail with FileNotFoundError on standalone_slot.gvas.b64
- 8 of 8 mutations turned a guard red, __pycache__ wiped between runs and each mutation asserting its anchor matched before being believed: unauthored PlayerName (4 red), 19-digit BattleId (3), 32-hex decoration (3), one shared door enumerator (1), both drop owners null (1), broken id-map inverse (1), a zeroed native payload restored (3), an 11-character decoration (3)
- ruff clean over tests/, lanternlight/ and ops/

AUTHORING A GUID THAT IS STILL HEX WOULD HAVE CHANGED NOTHING. PRODUCTUSERID is a bare 32-hex run and cannot tell an authored hex token from a real ProductUserId, so the 65 property-name decorations and the 2 monsterGuid values are replaced by an alphanumeric token that is not a hex run at all. That one decision also removes 62 of the 100 LONG_ID hits, which sat inside just two of those GUIDs as 16- and 17-digit decimal stretches. No detector was touched.
THE NAME FIELD WAS ONLY EVER GUARDED BY ACCIDENT. Before this fixture existed the KillPlayerHistoryDatas record was refused because the Blueprint GUID beside it tripped PRODUCTUSERID - a false positive that turned out to be load-bearing. Authoring the GUIDs removes it, so PlayerName, MsgSubChannelString and MsgAppearanceString are set to redact.AUTHORED_NAME_MARKER and the structural NAME_FIELD rule is now the only thing standing there. It was proven live rather than assumed: setting one value back to an ordinary string turns it red.
MEASURED, AND IT COST A REBUILD: 24 consecutive zero bytes encode to 32 'A' characters, 'A' is a hex digit, so a committed base64 blob of a save with a zeroed native struct trips PRODUCTUSERID on the FILE TEXT while the save it encodes is provably clean. Three native Vector payloads were entirely zero and no choice of entries avoids it - ExtraTreasureBoxCreated is false for all 61 monsters in the capture - so the builder authors those payloads and test_no_fixture_encodes_a_long_run_of_zero_bytes states the constraint for the next fixture. The format claim that was lost (an all-zero native payload round-trips verbatim) is pinned synthetically instead.
MEASURED LIMIT OF THE ENCODED SCAN, and the reason the authored decorations keep the source's 32-character width: iter_encoded_sensitive decodes each base64 RUN, and a fixture wrapped at 76 columns is a stack of runs each decoding to a 57-byte WINDOW. NAME_FIELD needs len(name)+17 bytes and goes quiet only if the marker follows within 64, so no 57-byte window can hold both - any name-bearing property whose head FITS in one window is reported. An 11-character decoration was built first and the builder's own gate refused it. 32 keeps the head out of reach with margin, and test_a_name_field_head_does_not_fit_one_base64_line pins the inequality with a positive control rather than leaving it to be rediscovered.
SIZE: 19867 bytes, not the under-10-KB target, and the reason is measured rather than a shortfall of effort. Of those bytes 12972 are tag overhead - 5046 of property names, 7311 of recursive TYPE names and 615 of size and flag fields across 123 tagged properties. The type names are the game's own struct identities and package paths and cannot be authored down without lying about what the game writes. The JSON payloads, which the spec expected to dominate, total 2964 bytes after truncation. Reaching 10 KB would mean dropping a container entirely, and the brief's own pruning targets were kept instead.
KEPT VERBATIM, stated rather than hidden: game config ids and counts inside the item JSON, the non-zero native struct payloads (world coordinates from the run), the in-run damage numbers and timestamps in DamageCollectonDataSet, and the LevelDetail and BotSpawnerData values. None is an identifier under any detector and all are game state rather than machine state, but a reader should know they were not authored.
SHAPES KEPT ON PURPOSE, one of each measured kind: two doors differing in BOTH E_DoorState and E_LockState; one live monster and one dead one, which are different shapes because a dead one carries a non-empty TreasurableItems blob; two dropped items, one naming an owner and one spelling 'nobody' as a JSON null rather than an empty string; all four native structs (Vector, Vector2D, Quat, Rotator); maps keyed by string, double and int; and all seven Inventory top-level keys.

### LL-0023 - 2026-08-10 - GVAS SERIALISER - serialise(parse(raw)) == raw on 276 files, so a sanitised fixture's lengths are right by construction

**Evidence:**
- ROUND-TRIP IDENTITY, all three corpora, measured this session: 6 committed fixtures 6 identical; 7 live saves 7 identical; 263 captured StandaloneSlot generations across 105 distinct sizes, largest 177878 bytes, 263 identical. 276 files, 276 byte-for-byte, 0 mismatched, 0 raised
- full suite 860 collected 860 passed against a baseline of 807 measured before dispatch; tests/test_gvas.py 159 -> 212; ops.merge_gate.verify OK at 860 against baseline 807
- TDD: the round-trip test was written first and watched fail with ImportError: cannot import name 'serialise' - the function did not exist
- 20 of 20 new guards proven non-vacuous by mutation, __pycache__ wiped before every run, each mutation asserting its anchor matched before applying
- ruff clean, both files 7-bit ASCII and LF, no roleId or userId in either file

THE READER WAS LOSSY AND ONLY IDENTITY FOUND IT. TextProperty's int32 FText flags word had been read and discarded since this module was written - worth 2 in all 276 files, and invisible to every existing assertion because they all check decoded VALUES. It is on TextValue now. Retained alongside it: the structured TypeName (render() is one-way and cannot be re-split), ArrayIndex, and the per-property GUID.
MEASURED NEGATIVES, from an independent scan of all 276 files: no property anywhere sets tag flag 0x01 (ArrayIndex) or 0x02 (property GUID) - only 0x00, 0x08 and 0x10 occur. Not one of the 671318 non-empty FStrings is UTF-16; all are ANSI. All 5701 empty FStrings are a bare length 0, never the length-1 lone-NUL form. FText flags is 2 and the culture-invariant flag is 1 in every occurrence. All 3223 doubles repack byte-identically. Those negatives are why the writer can be exact rather than heuristic.
The tag's FLAGS BYTE is deliberately NOT retained. Every bit is implied by data that is - 0x01 by array_index, 0x02 by property_guid, 0x08 by an UndecodedStruct value, 0x10 by a bool's value - and parse refuses every other bit. Storing it too would be a second copy of four facts, and an edit setting value=False beside a stale 0x10 would write a file saying True.
NAMED GAP, raised on rather than approximated: a non-ASCII string. The engine's negative-length UTF-16 FString branch is real and published and NOT ONE of the 671318 non-empty FStrings measured takes it, so writing one would be this module inventing an encoding. serialise raises GvasSerialiseError instead. Same policy for a save whose non-strict parse refused a property (those bytes are gone), a value that does not match its type name, a property named 'None' (it would read back as the terminator and silently truncate), and any length-bearing field of the wrong width.
THE CHEAT THIS COULD HAVE BEEN: GvasSave.trailing already holds every post-terminator byte verbatim, so emitting it would have passed every round-trip test and quietly made an edited key profile unwritable. The object section is rebuilt from the decoded objects instead, and two tests exist solely to catch that shortcut - poison trailing and the output must not move; edit a decoded mapping and it must. Mutating serialise into the cheat turns 6 tests red.
NO COMMITTED TEST POINTS AT C:\ll-captures. Those 263 files are machine-specific and outside the repo; they were the verification corpus and are cited as numbers only. The live-save round-trip test enumerates the save directory and SKIPS cleanly when it is absent, and reports only a failing file's NAME, never its bytes.
Also measured: not one fixture and not one live save contains an ArrayProperty, a StructProperty, a ByteProperty or a native struct - those live only in the uncommittable StandaloneSlot. Eight synthetic round-trip tests cover them, kept honest by the six real fixtures which would refuse to parse if the builders drifted.
ROADMAP 2b is now unblocked and its hardest part is gone: shortening an identifier or dropping map entries no longer needs any of the roughly one hundred enclosing Size fields patched by hand. transform() walks every property at every depth and rebuild() recomputes the derived views so GvasSave.properties can never describe a save that no longer exists.

### LL-0022 - 2026-08-09 - Session wrap - 1b closed, item 2 decoded, the transient save captured whole and pushed

**Evidence:**
- python -m pytest -> '807 passed in 23.52s', observed this run with __pycache__, .pytest_cache and .ruff_cache purged first; baseline before the session was 685
- python -m ruff check . -> All checks passed
- push verified by ref comparison, not by the command's exit code: local HEAD and origin/session/2026-08-09c-lane-state-and-capture both 3b5c3fb
- 13 commits, working tree empty, 109 tracked files, zero non-ASCII, no Co-Authored-By trailer in any commit message
- docs/LEDGER.md holds 21 real entries below the marker, LL-0001 to LL-0021, order intact
- PII sweep: the operator roleId and persona appear in zero tracked files; 263 capture files (27 MB) are held at C:\ll-captures\saves\, OUTSIDE the repository and uncommitted
- merge gate OK at 807 collected against a baseline of 685 measured before dispatching

REFUTATION COVERAGE, stated honestly rather than implied: the independent verifier ran against the ops slice and cleared it, finding two real holes. The final two commits - the fixes for those holes, and the README sync - were NOT covered by an independent pass. They are covered by three fresh mutation proofs and a full green suite, which is weaker evidence than a separate agent and is labelled as such.
THE SESSION'S BEST DECISION cost ten minutes and was made before reading the roadmap: arm a watcher against the save directory. Seventeen seconds later the transient save appeared, and it was caught whole - 263 generations, 2,190 bytes to 177,878, then self-deleted. The previous session lost it entirely by re-reading a document instead.
FOUR FILED CLAIMS REFUTED BY MEASUREMENT this session: the transient save is not 46 KB (it reaches ~178 KB); it is not append-only (it shrank 50s after a peak, so a single snapshot can be a torn read); it has no 13-minute timer (it lives exactly as long as the run does, created at match start and destroyed at run end); and 'only one escape type has ever been seen' is false (FixEscapeBell/WindChime alongside GroveSprite).
A ROADMAP ACCEPTANCE CRITERION WAS REFUTED, which is rarer and more useful than meeting one. Item 1 treated 'a non-zero matchId' as a proxy for 'a real matchmade raid'. Non-zero ids 11111 and 11112 both belong to SOLO explores, so the proxy proves nothing. The map URL offers four axes instead of one: levelId, roomModeId, matchType, matchId.
TWO SAFETY GUARDS WERE HONOURED RATHER THAN WEAKENED. lanes/capture/ was refused by .gitignore and by the pre-commit hook, both behaving correctly; the layout went flat instead, which also removes the collision class for logs, frames, private and tmp. Later the PII guard flagged this session's own open-item text and the wording changed, not the detector.
OPEN AND NAMED, not answered on the operator's behalf: which of ammoId 120510 or 120501 is Lightning Arrow. Both were equipped to destSlot 2 five seconds apart and the log names neither. An id-to-name binding without its method is exactly what docs/OBSERVED_IDS.md exists to prevent.

### LL-0021 - 2026-08-09 - Refutation pass on the ops slice - nothing refuted, two guarantees found narrower than their words

**Evidence:**
- verifier re-measured independently in pinned clones because the branch moved under it mid-run: 738 collected 738 passed at the pinned commit, ruff clean
- count regression check: base 685 to 738, per-file diff is a SINGLE added line, every pre-existing count identical, zero skips
- it reproduced the shared-ledger conflict standalone - CONFLICT (content), real markers, UU state - and killed its own vacuity hypothesis by making _commit_all a no-op, which failed BOTH tests
- idempotence re-checked against the REAL docs/LEDGER.md: integrate returns [] twice, difflib reports exactly one opcode, insert 3322 chars and zero deleted
- naive heading count 19 versus 18 real entries below the marker - the documented LL-0000 template off-by-one, confirmed independently
- no safety guard weakened: diff over .githooks, tools, scripts, .gitattributes, pytest.ini, ruff.toml, pyproject.toml and lanternlight is EMPTY, with a positive control over ops showing 788 insertions
- every blob in both commit trees scanned for any 16-20 digit run: zero, so the 19-digit roleId cannot be present
- guards proven live by the verifier itself: an em-dash in a lane STATE.json turns ascii hygiene red naming the byte offset, a SteamID64 turns test_no_pii red
- fixes verified after the fact: 807 collected, 807 passed, 0 failed, ruff clean, caches purged, observed this run

HOLE 1, now fixed: the read-only refusal lived only in state_path and fragment_path, so every path= route bypassed it. save(LaneState(lane_id='verify'), p) and append_fragment('verify', e, path=p) both WROTE FILES and load read one back. The gate now sits in save, load and append_fragment themselves, before any write.
HOLE 2, now fixed: integrate()'s reversed() had ZERO coverage - removing it left the entire suite green because every test used a single-entry fragment. A multi-entry fragment now pins the ordering and the guard goes red when reversed() is dropped.
THE METHOD LESSON: both holes were in code this session had already mutation-tested and called proven. An author's own mutation testing aims at the code that EXISTS - it does not aim at the route around it, and it cannot notice a promise nothing ever exercised. That is why the adversarial pass is a separate agent with a separate brief.
Also stale and now corrected: the merge test still built fragments at the NESTED lanes/<id>/LEDGER.md layout abandoned earlier the same session, so it had quietly stopped exercising the shape that ships. And the conflict assertion matched the bare word CONFLICT, which also matches git's advice text 'fix conflicts'.
RECORDED NOT FIXED, all pre-existing or out of lane: OPS-4, test_lane_contract is path-dependent because the contract text embeds primary_checkout(), reproduced at bfda016 so it predates this session; OPS-5, the git-visibility guard skips paths that do not exist; SAF-7, the pre-commit ASCII arm does not cover *.json - proven, a json em-dash gives HOOK EXIT 0 while the same bytes in a .md are BLOCKED, and lanes/*.STATE.json are the repo's first tracked agent-written json.
PROCESS: the verifier ran while the branch moved under it and handled that by re-anchoring to pinned clones. A refutation pass is cheaper and sharper against a frozen ref - dispatch it after the last commit of a slice, not during.

### LL-0020 - 2026-08-09 - ROADMAP 2 - StructProperty decoded, the transient save parses with zero undecoded bytes

**Evidence:**
- MERGER RE-MEASURED, not relayed: all 263 captured generations across 105 distinct sizes, up to 177,878 bytes, parse in strict mode with undecoded_trailing == b'' and zero unknown properties
- regression check by the merger: all 7 live saves still parse, trailing 0 and unknown 0 each - CampData, Deck, EnhancedInputUserSettings, LoginOptions, Notice, Scav, UserSettings_v1
- tests/test_gvas.py 159 collected 159 passed, up from a baseline of 122; merge gate OK at 801 collected against a baseline of 685
- a struct value is a nested tagged property list closed by 'None' - no epilogue, no inner length, bounded by the tag Size, and it landed exactly on that bound in every value of every generation
- new types recorded: ByteProperty<Enum> is an FString of the qualified enumerator and NOT a raw byte, plus ArrayProperty, generic MapProperty over element types, and StructProperty
- ruff clean, both files 7-bit ASCII, roleId absent from all tracked source

WHAT IS NOT DECODED, and is named rather than guessed: natively serialised structs carrying tag flag 0x08 - Vector (24 bytes), Rotator (24), Quat (32), Vector2D (16). They are handed back verbatim as UndecodedStruct(struct_name, struct_path, data). 401 such leaves, 10,600 bytes, in the largest capture. Vector and Rotator being the SAME WIDTH is the concrete argument against guessing: identical byte counts, different meanings, told apart only by name.
The reader RAISED on two genuinely new things mid-work rather than misreading them - a MapProperty keyed by DoubleProperty, and the Rotator native struct. That is the raise-on-unknown guard validated in the wild for the second time, which is better evidence than any test.
FIRST non-vacuity pass found THREE VACUOUS GUARDS in the lane's own new tests - a bare-position test rescued by an unrelated leftover-byte check, and two container-count tests that could not distinguish fast rejection from slow. Fixed with four new tests plus message assertions; second pass had 15 of 15 going red when broken. A guard that passes for the wrong reason is the failure mode this project keeps paying for.
NO FIXTURE COMMITTED, deliberately. It would need a rename (the filename embeds the operator roleId), plus scrubbing BattleId, AutoSaveTempSlot/FinalSlot, a 23-entry IdGeneratorData.NumIdToUUID map, and ownerRoleId inside the ItemCell JSON - several of which NO existing lanternlight.redact detector fires on. That is a safety-lane item, not an ingest one, and it is now on the roadmap.

### LL-0019 - 2026-08-09 - Save snapshotter - lanternlight/savewatch.py, every generation, never into the repo

**Evidence:**
- tests/test_savewatch.py: 26 collected, 26 passed, re-run independently by the merger
- identity is (name, size, mtime_ns), so a file that grows produces a snapshot per observed size rather than one on first sight
- refuses a destination inside ANY repo working directory, including a lane worktree - merger probed C:\Lanternlight\captures, the ingest worktree and lanes/capture/ and all three raised DestinationInsideRepoError
- end-to-end against the LIVE save directory by the merger: pass 1 took 7 snapshots, pass 2 took 0, source directory still 7 files and untouched
- survives the source being absent, and a file vanishing between listing and copying - the normal case here, since the target save deletes itself
- four guards proven non-vacuous by mutation with __pycache__ cleared between runs

This module exists because the previous session LOST the transient save entirely. A scratchpad poller armed at 17:27:14 this session - before the file existed - caught 263 generations of it, and the file then deleted itself. Arming before the event is the whole technique; the module is what makes it repeatable rather than a one-off script.

### LL-0018 - 2026-08-09 - ROADMAP 1b closed - per-lane on-disk state, and fragments instead of a ledger race

**Evidence:**
- ops/lane_state.py: lanes/<id>.STATE.json (mutable: sessions, resume note, open items) and lanes/<id>.LEDGER.md (append-only, evidence-carrying)
- all seven writing lanes seeded from ROADMAP.md - 15 open items distributed to the lane owning the files each would touch
- verify is REFUSED a state file and a fragment, not merely told not to use them - it owns nothing so it can grade others
- the lock option is REFUTED in writing: a lock serialises writes in time, but lanes are on different branches and git merges content, so serialised appends still conflict at the same anchor
- differential proof, real git merges: two branches appending to one shared ledger CONFLICT; two branches appending to their own fragments merge CLEAN
- this ledger entry itself was written to lanes/ops.LEDGER.md and moved here by lane_state.integrate() - the flow is exercised, not described
- integrate() is idempotent by item id and scans only BELOW the entries marker, so the LL-0000 template in the Format preamble cannot be mistaken for a real entry
- python -m pytest -> 738 collected, 738 passed, 0 failed, observed this run; python -m ruff check . -> All checks passed
- merge gate OK against a baseline of 685 measured before dispatching

LAYOUT IS FLAT, and that was measured rather than chosen. A directory per lane put lanes/capture/ in front of TWO independent PII guards - .gitignore's bare capture/ rule and the pre-commit hook's */capture/* rule - both behaving exactly as intended. The lane directory was a false positive against a correct rule. Weakening a veto-holding lane's guard for a naming convenience was the wrong trade; not creating a directory of that name was the right one. It also removes the whole collision class: logs, frames, private and tmp are blocked the same way, so a future lane named after any of them would have failed identically and nobody would have connected symptom to cause.
TWO TRAPS, both this repo's own documented anti-patterns, both hit anyway. The first .gitignore carve-out looked applied and was not: the negation lines were written with CRLF while the file was LF, so each pattern carried a trailing CR and matched nothing. The file read back as correct and only the byte count showed it. Second, git check-ignore is the WRONG probe - it exits 0 when any pattern matches INCLUDING a negation, so a correctly re-included file reports exactly like an excluded one. The guard now asks whether git would take the file.
THE ORPHAN GUARD COULD NOT HAVE CAUGHT THIS. tests/test_lanes.py walks git ls-files, so a path git is ignoring is invisible to the very check meant to notice an unowned file. The blind spot and the bug were the same shape, which is why the new guard asks git a different question rather than reusing that walker.
Roadmap point 3 - 'nobody has actually run a lane yet' - was ALREADY STALE when it was committed. Two lanes had run end to end before that line existed. A roadmap line describing the world is a measurement with a timestamp, and this one was never re-probed.
Eight guards proven non-vacuous by mutation: every anchor asserted present first, __pycache__ purged before every run, every restore confirmed byte-identical and green.

### LL-0017 - 2026-08-09 - CORRECTS LL-0016 - the no-numbers claim was false, and three quotes were paraphrases

**Evidence:**
- LL-0016 states 'NOT ONE NUMBER appears in any of the 36 talent tooltips or in the skills screen'. That is FALSE and this entry corrects it; per the append-only rule LL-0016 is left standing and this entry names it
- counterexample 1, independently re-read from frame f0030 by the merger: Pursuit Mark - 'Enemies hit by normal arrows have reduced Movement Speed for a period of time. This effect can stack up to 3 times.'
- counterexample 2 and 3: Measured Pace and Battle-fed both read 'When carrying at least 2 ... Arrows', and BOTH are quoted verbatim in docs/OBSERVED_IDS.md 155 lines above the sentence denying numbers exist
- the surviving narrower claim, now stated in the doc: no tooltip gives a MAGNITUDE of an effect - no damage figure, percentage, duration or radius. The numbers that appear are thresholds and caps, never the size of what happens
- three quotes labelled 'verbatim from the tooltip' were paraphrases and are now restored character-exact against their frames
- the most serious: Dodge Power Shot had the clause 'toward enemies near the crosshairs' DELETED - a targeting behaviour removed from text presented as the game's own words
- Dodge Rapid Shot had two sentences collapsed into one; Blood Infection dropped 'the target has' and 'dealt'
- cluster name corrected in two places: the screen reads 'Way of Gylden Hunt', the doc had invented 'Way of the Gylden Hunt'
- 'tooltip text captured only where noted' was false - essentially all 36 were captured, and that understatement is how Pursuit Mark's stack cap went unnoticed
- 'Steel Arrow' is operator-attested, not readable in any frame, and the name also appears in an established-outlet list in docs/CLASSES.md - now flagged rather than presented as a frame reading
- mutual exclusivity of Measured Pace and Battle-fed is operator-attested and NOT visible in any frame; the ring shows a branch from a shared root, which is a different fact
- python -m pytest 685 passed 0 failed with caches purged; python -m ruff check . clean

Found by the wrap's refutation pass, which was told to hunt specifically for a paraphrase wearing a verbatim label. It found one that had deleted a mechanic.
The pattern across all of it: a document whose entire value is that it does not invent things had invented a word in a name, deleted a clause from a quote, understated its own evidence, and asserted a universal negative contradicted by its own table. Screen-read documentation is a weaker evidence class than code and needs the same adversarial pass, not less.
A universal negative is the shape most likely to have a counterexample. 'No numbers anywhere' should have been written as the narrower claim from the start, because the narrower claim is the one that was actually measured and is the one that supports the project's doctrine.

### LL-0016 - 2026-08-09 - Blackarrow talent and skills screens measured by pixel capture; first talent point spent

**Evidence:**
- tools/frame_poller.py captured 217 frames at 2s intervals, 16:01:06 to 16:09:16 local, plus one skills-screen grab
- 36 talent nodes across 12 clusters recorded with names, unlock levels and - for the six selectable-tier nodes - verbatim tooltip text
- operator attested which frame showed which node, so every name is a rendered-text read joined to a human confirmation, not an icon guess
- skills screen: loadout structure (arrow slots Z/X/C, C at Lv. 3; skill slots Q/E, third at Lv. 5) and the Archer/Hunter pools as two separate five-slot rows
- Concussive Arrow tooltip and in-game hint captured verbatim
- python -m pytest 685 passed 0 failed with caches purged; python -m ruff check . clean

CORROBORATION worth more than the data: the in-game hint reads 'Use Concussive Arrows to knock back fast-approaching enemies', and the tooltip states an optimal band - inaccurate too far, hard to draw too close. That is the developer's own UI confirming two claims docs/CLASSES.md could previously support only from player testimony: that Blackarrow is hard-countered by gap-closers, and that it is not a sniper. Neither claim appeared in any guide site the research pass consulted.
Second corroboration: Measured Pace gates on Archer's Arrows and Battle-fed on Hunter's, and the skills screen renders the two families as separate rows. The Archer/Hunter ammo-family finding was previously adjudicated from contested published sources; it is now visible in the game's own UI.
NOT ONE NUMBER appears in any of the 36 talent tooltips or in the skills screen. Every effect is qualitative. The project's founding premise - that this game publishes no coefficients, so any source quoting one is fabricating - is now an observation rather than an inference.
TWO WRONG RECOMMENDATIONS were made before the right one, both from reading structure out of an image. First: Dodge Rapid Shot, which is not selectable, because the connecting lines between nodes are prerequisites and were read as decoration. Second: an argument from unlock ordering made while assuming no arrows were held. The operator's description of their actual loadout settled it. A screenshot shows what is on screen, not what the player has.
A safety claim was also retracted: the account panel's name is randomised by the game's own privacy setting, not a second identifier the redactor must learn. The residual point is sharper - capture safety depends on a toggle in the game menu, and nothing in this repository can detect its state.

### LL-0015 - 2026-08-09 - Fixtures made authored artifacts, orphaned files given owners, a seventh save reopened the GVAS item

**Evidence:**
- no committed fixture is byte-identical to any live save - merger re-derived by sha256 over all six fixtures against all live saves
- merger's own non-vacuity probe: planting a RAW live save as a fixture is CAUGHT by the guard; restore returns green
- all six fixtures parse with undecoded_trailing 0, zero unknown properties, and zero redactor findings under ALL_LABELS
- sanitisation preserved property names, type names, header and class paths - only values moved, asserted equal before each splice
- orphan guard added: every tracked file must be owned by exactly one lane or listed in CROSS_CUTTING, no third state
- 94 tracked files: 82 owned, 12 cross-cutting, 0 orphaned - was 10 orphaned
- orphan guard proven non-vacuous: removing one assignment turns it red naming exactly that file
- lane commit 60cf878 touched 7 files, ownership resolves all 7 to ingest - zero violations
- merged suite 685 passed 0 failed with caches purged, ruff clean

A SEVENTH save appeared mid-verification: StandaloneSlot_<roleId>.sav, 41,564 bytes at 15:39 and 46,619 minutes later while still being written - twenty times any other save, so very likely the real character and progression store.
It does NOT parse. It uses StructProperty<F_PlayzoneSaveData>, never measured here, and the reader RAISES rather than returning a partial parse. That is the raise-on-unknown guard validated in the wild by a genuinely new type - better evidence than any test. ROADMAP item 2 reopened with an acceptance criterion.
Its filename embeds the operator's roleId, the same name-level hazard as CampData. A fixture must be renamed, not merely redacted.
The ingest lane observed that the live UserSettings_v1.sav changed size mid-session because the operator is playing, so the byte-identical guard is a SNAPSHOT check that can go green on its own. That is the argument for sanitising rather than relying on the guard, and it is why both were done.
The save set is not fixed: four at first probe, five, six, then seven within a day. Any helper assuming a known list silently stops covering the surface.

### LL-0014 - 2026-08-09 - Session wrap - refutation pass held, two filed counts were wrong

**Evidence:**
- python -m pytest -> 643 passed 0 failed, observed this run with __pycache__, .pytest_cache and .ruff_cache purged first
- python -m ruff check . -> All checks passed
- default run still includes the slow tests: 610 not-slow + 33 slow = 643, so the marker cost no coverage
- independent refuter re-derived all ten wrap claims and CONFIRMED every substantive one
- redactor: 1455 raw occurrences across all 9 discovered persona candidates -> 0 after redaction; idempotent; assert_clean raises on the raw log
- raw UTF-16 LE and BE both caught by the real consumer; mutation of the wide-candidate call turned 7 tests red, restore returned byte-identical
- pre-commit hook refused 5 hazard shapes and permitted 2 legitimate ones via REAL commits, with HEAD compared before and after every single attempt
- dotfile ownership mutation (removeprefix -> lstrip) turned 5 tests red; 94 tracked files, zero with two owners
- independent PII sweep over all 94 files, decoding to depth 2 with ALL_LABELS plus 442 ground-truth strings from the live log: zero operator ids, zero in filenames, positive control fires
- anti-cheat boundary swept over the full 13,108-line session diff with a pattern proven against a positive control: zero code hits

CORRECTS two counts filed earlier this session. The ledger has THIRTEEN entries, not fourteen - the fourteenth '### LL-' header is the LL-0000 template in the Format section. And there are SIX .sav files, not five: Deck.sav appeared at 14:36 local during the mail-and-equip sequence. Both were caught by the refuter, and both are exactly what this repo means by 'a filed count is a hypothesis'.
Deck.sav parses cleanly with the existing reader - DeckDefaultOpenPage, a MapProperty<IntProperty,IntProperty>, zero undecoded - but no fixture pins it. The save set is NOT fixed; a reader must enumerate the directory.
OPEN RISK, unresolved: three GVAS fixtures are byte-identical to the operator's live saves by sha256. Clean today, but the repo is publishing raw game-state bytes on the assumption that the shapes the scanner knows are the only shapes that matter.
OPEN GAP: ten tracked files are neither lane-owned nor declared cross-cutting, including lanternlight/__init__.py, docs/ARCHITECTURE.md, tests/test_lane_launcher.py and tests/test_lane_contract.py. Nothing arbitrates a concurrent edit to them, and the no-two-owners test passes trivially over a file with zero owners.

### LL-0013 - 2026-08-09 - Raw UTF-16 gap closed, encoded saves blocked by path, merge_gate gained must_contain

**Evidence:**
- merger's own probe - the one that refuted this lane's previous claim - now reports raw UTF-16 LE and BE both caught, and base64-wrapped UTF-16 still caught
- the finding names the container ('a 25-character little-endian wide-character run') and never quotes the identifier
- rule is a paired (character, NUL) run collapse with a 15-pair floor, both endiannesses - NOT a whole-file NUL strip
- false-positive cost measured on a 22,110-file control corpus: the wide reading newly blocks 5 files, all compiled extension modules with uint16 tables; the rejected naive strip would have newly blocked 12 and fired on this project's own build artifacts
- merger spot-checked the hook with REAL commits: probe.sav, .sav.b64, .log.b64, .gvas.b64 and tests/fixtures/gvas/probe.sav.b64 all refused; a reviewed-location .gvas.b64 and an ordinary .py both committed; HEAD restored byte-identical
- lane's own commit cf3327b touched exactly 4 files and ownership resolves all 4 to safety - zero violations
- merged suite 643 passed 0 failed with caches cleared, ruff clean
- merge_gate.check_claimed_paths now accepts {'path':..., 'must_contain':[...]} and refutes a stub that exists but lacks the claimed content; proven additive by calling the documented string form unchanged

The lane went BROADER than instructed: outside tests/fixtures it now refuses bare .b64/.base64/.hex and the whole archive family (.gz/.zip/.7z/.tar/.bz2/.xz/.zst). Nothing tracked matches today, but it will block a future archive committed outside tests/fixtures. Flagged for the operator rather than narrowed unilaterally.
The tests/fixtures carve-out is a real widening of trust: anything there with an encoded suffix skips the path check, leaving only the content scan, which detects known shapes rather than proving cleanliness.
The wide reading sees ASCII inside UTF-16 and nothing more. A non-ASCII digit form is not reached.
Suite runtime 12.3s to 32.7s, almost entirely 33 hook tests spawning real git commits. A hook that merely exists is not a hook that fires, so the cost was accepted.
Mutation testing caught TWO of the lane's own tests passing for the wrong reason - a big-endian case the little-endian pattern reached anyway, and a log-companion branch only exercised where a generic branch already caught it.

### LL-0012 - 2026-08-09 - Both lanes merged into the session branch and verified together

**Evidence:**
- merged lane/ingest then lane/safety with no conflicts
- merged suite: 583 passed 0 failed, ruff clean, caches cleared before the run
- THE interaction that only the merge could test: safety's new encoded scanner now walks and decodes ingest's five base64 fixtures for the first time - all five CLEAN
- primary checkout was byte-identical throughout both lane runs: HEAD e2fe3e2 and tree ecf189f before and after, zero dirty files
- each lane touched only paths its own ops/lanes.py entry owns, confirmed by git diff --stat against its branch point

METHOD HAZARD found by the ingest lane and worth propagating: a same-length mutation written within one mtime tick leaves source size and mtime unchanged, so Python reuses a stale .pyc. That can fake a GREEN under mutation and therefore fake a non-vacuity proof outright. Clear __pycache__ before every mutation run.

### LL-0011 - 2026-08-09 - Ingest lane decoded the GVAS trailing block; save and log corroborate

**Evidence:**
- all 627 trailing bytes of EnhancedInputUserSettings.sav decode into a named nested object; GvasSave.undecoded_trailing is 0
- raw bytes are still kept in GvasSave.trailing for fidelity, so nothing is lost to the decode
- merger parsed all five REAL .sav files independently: 5/5 parse
- merger corrupted a property type in place: still raises UnknownPropertyTypeError rather than returning a partial parse
- decoded key profile cross-corroborates the game log: KB_Blackarrow_Major_Action -> RightMouseButton appears in BOTH the save bytes and the log's decode key mapping lines
- TextProperty history 0x00 added - measured, not speculative; grep of all five files yields only Bool, Double, Int, Map, Str, Text
- merger re-scanned all five fixtures decoded from base64 with ALL_LABELS: 0 findings, and 0 leaks of the real persona or userId
- tests/test_gvas.py 75 -> 111; commit b153d41 on lane/ingest, pushed; merged to the session branch

The 4 zero bytes after every tagged property list remain UNIDENTIFIED and are handed back as GvasSave.epilogue rather than named. An int32 zero, an empty FString and four zero flag bytes all fit and nothing observed separates them.
The save persists 3 key mappings while the log carries 81, suggesting the save stores only overrides. Recorded in docs/OBSERVED_IDS.md as a strong reading, not a proven one.

### LL-0010 - 2026-08-09 - Safety lane closed the base64 PII hole and stopped skipping binaries

**Evidence:**
- redact.iter_encoded_sensitive finds base64 and hex runs, decodes them, and re-runs the EXISTING structural rules - no new pattern that could fire alone
- the finding names the container ('in a 76-character base64 run') and never quotes the decoded value, so firing the guard does not itself publish the identifier
- merger's independent probe: a planted base64 SteamID64 + ProductUserId file makes tests/test_no_pii.py exit 1; removing it returns green
- merger poisoned a REAL committed fixture with a synthetic account-name key and id - the guard caught it at file:line:byte, fixture restored byte-identical, green after
- binary files are now scanned via _tracked.iter_scannable_files; merger confirmed a raw id inside a .png is CAUGHT where it was previously skipped by suffix
- false-positive rate measured by the lane: 0 findings over the Lanternlight tree; 15 findings over the CPython stdlib (20,077 files) all genuine 15+ digit runs
- lane found 2 of its own guards VACUOUS on the first mutation pass and fixed both; second pass 14 of 14 red
- commit 7fcf640 on lane/safety, pushed; merged to the session branch

GAP, measured by the merger and not claimed by the lane: raw UTF-16 in a file is MISSED. UTF-16 inside a base64 blob IS caught. The lane's report said 'UTF-16: a NUL-stripped second reading' without that qualifier.
OPEN QUESTION for whoever owns policy: .gitignore blocks *.sav but not *.sav.b64, and .githooks/pre-commit's PII_HAZARD regex is \.sav$ so it does not match either. An encoded save is content-scanned but not path-blocked. The safety lane deliberately did not add that rule because it would block already-verified fixtures - it is a cross-lane call.

### LL-0009 - 2026-08-09 - Lane architecture proven end to end by running the ingest lane

**Evidence:**
- ingest lane launched into C:/ll-worktrees/ll-lane-ingest on branch lane/ingest
- refusal guard proven three ways: refused from the primary checkout, allowed in its own worktree, refused for a different lane's worktree
- lane built ROADMAP item 2 (GVAS .sav reader) TDD: lanternlight/gvas.py, tests/test_gvas.py, 5 redacted base64 fixtures, 75 new tests
- primary checkout byte-identical throughout: HEAD a51c608 and tree f1ce3754 before and after, zero dirty files
- lane touched ONLY its owned paths - git diff --stat shows gvas.py, test_gvas.py and tests/fixtures/gvas/ and nothing else
- lane committed 73423fa to lane/ingest and pushed it; never merged to main
- fixtures independently re-scanned by the merger: all five decode to zero redactor hits
- DEFECT FOUND BY THE RUN: ops.lanes.REPO_ROOT is derived from __file__, so inside a worktree it equals that worktree and every not-the-primary-checkout assertion inverts - 6 tests failed from the worktree
- fixed with primary_checkout() via git rev-parse --git-common-dir, which answers identically from every worktree
- fix proven from a second lane worktree: 436 passed 0 failed running from C:/ll-worktrees/ll-lane-capture, where REPO_ROOT and primary_checkout() genuinely differ

Base64 fixtures are invisible to tests/test_no_pii.py - a planted SteamID64 is detected in raw text and not in its base64 form. tests/fixtures/gvas/ is covered only by the lane's own decode-then-scan test. This belongs to the safety lane.
git worktree remove exited 255 on Windows leaving the directory behind while unregistering it. Cleanup is not yet reliable and lane_launcher does not handle it.

### LL-0008 - 2026-08-09 - Lane launcher and generated per-lane contracts

**Evidence:**
- ops/lane_launcher.py creates a worktree per lane on lane/<id> and refuses to run in the primary checkout
- assert_in_lane_worktree tested against the real repo root, not a mock - a path-comparison bug is what a mock would hide
- integration test proves a lane commit leaves the primary checkout with an empty git status
- read-only lanes are refused a worktree outright rather than trusted to remember not to use one
- ops/lane_contract.py renders all 8 contracts FROM ops/lanes.py so the two cannot drift
- drift guard proven non-vacuous: widening one lane's globs without regenerating turned the test red, restore returned green
- tests/test_lane_launcher.py 16 passed, tests/test_lane_contract.py 21 passed, tests/test_lanes.py 23 passed
- python -m pytest 433 passed 0 failed; python -m ruff check . clean; per-file regression check reports NONE

First render shipped indented by 8 spaces: textwrap.dedent around an f-string does nothing once an interpolated block contributes zero-indent lines, which broke the YAML front matter. Template is now dedented before interpolation and the reason is in the module docstring.

### LL-0007 - 2026-08-09 - Hygiene guards were blind to every uncommitted file

**Evidence:**
- tests/_tracked.py walked git ls-files, which lists TRACKED paths only, so a new file was unscanned until after it was committed
- measured: docs/CLASSES.md, lanternlight/avgprice.py and every other file created this session were invisible to both guards
- two independent agents hit this the same day - one had 21 long-id hits in an unscanned draft
- walker now includes git ls-files --others --exclude-standard, so .gitignore stays authoritative and ops/runtime stays out
- tests/test_tracked_walker.py 8 passed, covering a new untracked file, a gitignored file, and no double-yield

A guard against leaked identifiers went blind at exactly the moment a new file is written, which is when it is needed.

### LL-0006 - 2026-08-09 - Single-source class reference and third-party ecosystem survey

**Evidence:**
- six independent research passes, one per class, adjudicated by a seventh agent that wrote none of them
- docs/CLASSES.md, 1996 lines: 13 genuine contradictions, 4 resolved and 9 left explicitly open
- 10 circulating fabrications routed to their own section, kept separate from 7 unpublished guide numbers and 9 unverified names
- the Sorcerer single-weapon question deliberately left OPEN as the repo requires
- docs/ECOSYSTEM.md records the third-party landscape, including two named tools that inject or hook and must never be imitated
- hygiene guards pass over both new documents

No tier list verifiably dated after the 2026-08-06 patch exists for any class, so every current-standing claim anywhere is inference.

### LL-0005 - 2026-08-09 - Dungeon recon from disk, and nine corrections to it after adversarial review

**Evidence:**
- no capture session was needed - the log had grown 567 KB to 6.1 MB over 3h44m and already held the data
- measured: dungeon lifecycle across two runs, escape-portal mechanic, Game.PlayState tag namespace, six inventory opcodes, four loot contexts, 35 TS.Inventory cfgIds
- the live holding- id space and the item cfgId space proven to be one space: 3020401 held 23 times AND priced at 31, anchored on 1269 of 1269 server_refreshKnightFeature lines
- vocabulary corrected: the words raid and extract appear ZERO times; the game says dungeon and escape
- an independent verifier was dispatched to REFUTE these findings and returned nine defects, all fixed
- most serious: a death filed as the operator's belongs to a second player - the operator has no Death tag at all
- scope defect: cfgId:(\d+) with no space silently dropped every TS.FTE line, 35 vs 45 distinct ids
- docs/FINDINGS.md section 9, docs/OBSERVED_IDS.md, ROADMAP.md updated with the corrections stated rather than silently edited

PvP moved from clean null to contact observed, mechanics unmeasured - pvp was never grepped before being filed absent.

### LL-0004 - 2026-08-09 - P0 - redactor left 684 of 686 persona occurrences in the log

**Evidence:**
- measured against the live log: 686 occurrences before, 0 after; second token of the two-word display name 28 to 0
- assert_clean previously returned cleanly on a persona-carrying line - the guard was vacuous for that shape
- two root causes: keyed rules stopped at whitespace so a two-token name was half masked, and the persona also appears with no key at all
- a second, scope-dependent defect was found on review and fixed: discovery returned empty on an ISOLATED excerpt, so the keyless shapes passed through and assert_clean approved them
- all six measured leak shapes re-verified IN ISOLATION by the merger, independently of the implementing agent: 0 still leaking
- assert_clean gained a cannot-certify path so it refuses to approve text it has no basis to approve
- tests/test_redact.py grew 23 to 140 passed; 8 mutation checks each turned it red and restored byte-identical

A third party's persona is also in the log and is non-ASCII. Discovery masks it, 16 occurrences.

### LL-0003 - 2026-08-09 - AvgPrice market cache parser, and a three-way path defect fixed

**Evidence:**
- AvgPrice_937566.ini filled: 37 bytes to 343, 30 cfgId=price rows, PriceTime epoch 1786285800 = 2026-08-09T14:30:00Z
- lanternlight/avgprice.py parses it; configparser verified to REJECT the keyless stamp line, and to silently misread it as a key under allow_no_value
- tests/fixtures/avgprice_sample.ini byte-identical to the live file, verified by sha256 and length
- lanternlight/paths.py pointed at Config/WindowsClient/AvgPrice.ini - wrong parent dir, wrong platform subdir (real is Windows) and wrong filename, so find_avg_price_ini returned None on a machine where the file existed
- tests/test_paths_avgprice.py 11 passed, including a live-install test that fails against the old implementation
- tests/test_avgprice.py 32 passed

The old 37-byte state was never an empty file: two section headers plus a 10-digit stamp is exactly 37 bytes under LF.

### LL-0002 - 2026-08-09 - Merge gate and the eight-lane specialist roster

**Evidence:**
- ops/merge_gate.py re-probes agent claims: file existence, real pytest summary parsing, per-file count regression
- per-file guard added after finding the global-total check is unsafe once lanes commit concurrently - a lane adding 20 tests masks a sibling deleting 15
- non-vacuity proven twice by mutation: disabling the total branch and the per-file branch each turned the guard red, restore returned green
- ops/lanes.py declares 8 lanes with path-based ownership; tests/test_lanes.py walks the real tree and asserts no file has two owners
- safety lane holds a veto; verify lane owns nothing and is read-only, both asserted
- tests/test_merge_gate.py 23 passed, tests/test_lanes.py 23 passed

Parsers built against MEASURED pytest output: CR-terminated lines, no trailing newline, and --collect-only prints no grand total.

### LL-0001 - 2026-08-09 - Repository scaffold and autonomy stack

**Evidence:**
- `ops/loop/state.py` persists cycle, directive, in-flight item, timestamp and completed ids to `ops/runtime/loop_state.json` through a temp-then-`Path.replace()` write
- `ops/loop/guard.py` takes an `O_CREAT | O_EXCL` lock carrying the owning pid, reclaims a lock whose pid is gone, and never terminates anything
- `ops/loop/ledger.py` inserts entries below the marker in this file, atomically, with a pre-write check that existing content is preserved byte for byte
- `tests/test_loop_state.py` and `tests/test_loop_guard.py` cover default-on-missing, round trip, corrupt-file recovery, write atomicity, acquire, refusal of a second acquire, stale reclaim and release
- `docs/HEADLESS.md` records the per-cycle procedure and the stop conditions the loop must never violate unattended
- `python -m ruff check ops tests` clean; `python -m pytest` green

**Notes:** the loop's continuity contract - git history, this ledger,
`ROADMAP.md` and the directive chain in `ops/runtime/loop_state.json` - is
stated in `ops/loop/__init__.py` and must hold for a session started with an
empty context.
