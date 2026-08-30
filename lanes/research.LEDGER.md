# Lane ledger fragment - research

Completed work by the `research` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

### LL-0093 - 2026-08-30 - 188 full-screen frames nobody had ever opened - the game STATES the affix aggregation rule in a table, and the talent tree has a second page

**Evidence:**
- python -m pytest -> '1338 passed in 23.14s', observed this run in the research worktree
- python -m ruff check . -> 'All checks passed!', observed this run
- merge_gate.verify(['docs/AFFIXES.md'], baseline=1338) -> OK
- tests/test_ascii_hygiene.py + tests/test_no_pii.py -> 46 passed; 0 non-ASCII lines in docs/AFFIXES.md
- frames read directly: f0119_22.28.15 and f0000_22.23.53 in the 2026-08-25b talents capture, 2560x1440

THE CAPTURE EXISTED ALL ALONG. 164 frames at 2560x1440 from 2026-08-25, plus 24 more in a sibling directory, none ever opened. They were found by walking the capture tree - the same omission that produced the false 'only one capture is full-screen' claim withdrawn in LL-0088 had also hidden this. Correcting a false claim turned up real evidence, which is the argument for correcting them rather than quietly dropping them.
THE GAME STATES THE AGGREGATION RULE. There is an Affix Details screen rendering a Type header of nine equipment-slot icons and one row per active affix carrying a level and a per-slot count. On the frame read, EVERY affix's level equals the sum of its own row - Fervid Lv.2 = 1+1, Fervor Lv.2 = 1+1, Seeker Lv.1 = 1, Wealth Lv.1 = 1. Four independent matches on one screen.
THAT IS INDEPENDENT CORROBORATION, not a re-reading. AFFIXES.md derived 'one icon is one level, summed across gear' by COUNTING ICONS on a 2026-08-30 frame, as the replacement for a withdrawn claim. This is a different capture session, four days earlier, a different loadout, and a tabular statement rather than an icon count - and it shows exactly what the derivation predicted.
It also settles the withdrawn claim beyond argument: a row whose counts SUM to the level the same screen reports is plainly a per-character breakdown, not an eligibility table.
Seeker and Wealth are confirmed on a real loadout for the first time - previously Seeker existed only in the Auction House catalogue and Wealth only inside a gem tooltip.
THE NINE-SLOT COUNT AGREES WITH THE LOG. The Type header carries nine slot icons; OBSERVED_IDS binds nine equipment slots from the log alone by joining bot state data against equipment payloads on item cfgId. Two unrelated surfaces, one number.
NEW - the TALENTS screen has TWO PAGES. Two page indicators and a D-key arrow. Every prior reading of the talent tree covered page one only, and OBSERVED_IDS' description of it as 'complete for a level-2 character' should be read as complete for page one.
NEW talent nouns, quoted: the node Unstoppable Edge - 'Sky Piercer's Physical Damage is partially converted to True Damage' - plus the cluster Mighty Archer. Swift Shot at Lv.8 and Nimble Evade at Lv.7 match the 2026-08-30 frame exactly, four days apart.
TRUE DAMAGE is a damage type Emberforge has no representation for, and the conversion FRACTION is unstated - the tooltip says 'partially' and gives no number. Recorded as a named mechanic with an unmeasured coefficient, kept distinct from a measured zero.
NOT DONE - the numeric talent ids stay UNBOUND. Three gameplay tags and three ids exist and nothing joins them. Pairing HomingTarget with a node called Unstoppable Edge on a shared intuition would be the reasoning this project has withdrawn three times.
PER-SLOT ATTRIBUTIONS deliberately described by group rather than named. Several header glyphs are confusable at this resolution, and this document already withdrew one claim that rested on reading an icon instead of a label. The SUM rule needs no icon identification and is stated without hedging.
LANE COUPLING, recorded as a real property rather than an accident: this research finding could not be committed green without a SAFETY commit, because citing three new gameplay tags trips the source-register guard and that guard is safety-owned. The safety half was ordered first so neither branch was committed red.

### LL-0086 - 2026-08-30 - The four remaining affix ids are UNBINDABLE from data on disk - a measured null with a named cause each, plus a second binding method validated on a control

**Evidence:**
- python -m pytest -> see the run recorded below; tests/test_ascii_hygiene.py + tests/test_no_pii.py -> 46 passed, observed
- every affixIds request in all three logs enumerated and converted to local time, then tested against every capture window: 41 requests, 4 touching a target id, 0 with capture coverage
- tooltip-open events (cfgid ==, note the space) cross-joined against capture windows: 1036 total, 317 inside a window, 0 of them on an item carrying 101, 209, 212 or 214 while a FULL-SCREEN capture ran
- frame sizes measured directly with PIL: 2026-08-25 captures are 500x310, 2026-08-25b are 540x360, only 2026-08-30 is 2560x1440
- no game video recording exists on the machine - a filesystem sweep found only clips of an unrelated title

MEASURED NULL, not a failure to look. 212 has two SINGLETON trade-filter requests - ideal join material - at 22:44 local on 2026-08-25, and the captures run 18:51-20:34 then 23:08-23:35. The frames sit either side of the gap and were never taken.
214 occurs exactly once in the entire corpus, inside [212,211,214], in that same uncaptured window, and has never been observed on an item. A 3-element array yields a SET; it resolves only if two members are known and only 211 is.
THE MOST INSTRUCTIVE FAILURE - 101 and 209 had their item tooltips opened INSIDE a running capture, at 19:54:35 and 19:54:03 local, and are still unrecoverable because that capture is a 500x310 crop of the HUD rectangle taken for the damage-meter work. The capture was running, the event fired inside it, and the binding is lost because the crop was chosen for a different purpose.
NEW METHOD, and it is validated rather than asserted. Item tooltips are a SECOND binding route, proven on a control with a known answer: the log records item 3060404 carrying affix cfgId 211, and frame f0636_00.45.07 shows that item's tooltip reading 'Ranged Lv.1'. 211=Ranged was established independently through the trade filter, so two unrelated methods agree.
READING RULE now proven, not assumed - the item's OWN affix is the row WITHOUT a gem icon. The same control tooltip shows Ranged with no gem icon and Fervor with one, and the log's affixes[] for that item holds 211 alone, so gem-granted affixes do not appear in affixes[].
STRUCTURAL - the two routes are COMPLEMENTARY and neither covers the id space. Filter-only: 201, 214. Item-only: 101, 209. Both: 208, 211, 212. So the tooltip route is not a fallback, it is the ONLY route to 101 and 209 - which is invisible while every binding so far came through the filter.
NOT DONE, deliberately - no arithmetic was attempted on the id space. Valor, Fervid and Ranged sit at catalogue positions 6, 9 and 11 with ids 201, 208 and 211, fitting no simple rule in either row-major or column-major order. Guessing a fourth id from three points is the reasoning this document has withdrawn twice.
OPEN - it is unknown whether 101 and 209 are filterable at all. Neither has ever appeared in a filter request, and the Affix Effects list is 16 entries under one gem type and demonstrably not the whole affix set, so an item-only affix may have no filter row.

### LL-0085 - 2026-08-30 - Affix ids BOUND to names from capture already on disk - plus the affix text surface the tooltip pass never opened, and two docs still carrying what AFFIXES.md had refuted

**Evidence:**
- python -m pytest -> '1327 passed in 26.38s', observed this run in the lane worktree; baseline 1327 collected, measured before dispatch
- merge_gate.verify(claimed_paths=[AFFIXES, OBSERVED_IDS, CLASSES, FINDINGS, research.STATE.json], baseline=1327) -> 'OK (1327 tests collected)'
- tests/test_ascii_hygiene.py + tests/test_no_pii.py -> 46 passed, observed; 0 non-ASCII lines in every edited doc
- the no-PII guard FIRED on my own lane-state wording and was fixed by rewording, never by weakening the rule - proof this run that the guard is not decoration
- 201=Valor and 211=Ranged read off frames f1816_01.09.42 and f1932_01.11.56 joined to [TradeCtrl] requests at 06.09.40 and 06.10.32 UTC; 208=Fervid by set difference from [208,211] at 06.09.22 with f1799_01.09.21
- equipment affix model re-derived independently: 8 affixed item cfgIds, each with exactly ONE affix triple, all 8 recurring across 2+ logs, 68/68 observations level:1 and fixed:true
- equipment slot binding re-derived: all 8 bot equipment cfgIds resolve to exactly one slot number, checked for ambiguity rather than assumed
- client patch verified directly: [Startup] Version: 1.0.14/20260818232428 in both backups, 1.0.15/20260826170036 in the live log, one hit per log

BOUND, a first for this project - 201=Valor, 208=Fervid, 211=Ranged. No new capture was needed: log and frames were both already on disk and the wall-clock join had never been run on the trade filter.
REFUTED, my own reasoning, by an independent adversarial pass that confirmed all three conclusions while breaking two of my arguments. 'Array order is selection order' was unsupported - Fervid sits directly above Ranged, so display order and selection order predict the same array. And 'the results are all named Ranged...' was invalid because gem names map to affixes by SYNONYM: this document's own evidence shows Ranged Ward is the gem-name form of Distant Ward, not of Ranged. Both rewritten; the withdrawn versions recorded in place.
REFUTED, a sub-agent's claim that the dropdown logs all affix names on open. Zero occurrences of every catalogue name across all three logs; the 4 Ranged hits are the RangedAttackIndicator UI module. Two sub-agents disagreed and the measurement settled it - the frame join is the ONLY route to these bindings.
REFUTED, my own itemType/itemSubType pairing. The live log shows a perfect one-to-one match across 18 payloads; the backups show ARMOR taking seven subtypes and OTHER six. A clean pattern in a small sample is not a rule.
REFUTED, two of three PII carriers a sub-agent reported. Re-probing the real redactor showed the player-name field and the CampData filename are already masked; only the roleInfo device field is a genuine gap, filed as RES-20. Relaying it unchecked would have sent the safety lane after two non-problems.
REFUTED, a sub-agent's diagnosis of the setClassGender pattern. It is broken, but the doubled space is between inclassid and ==, not after setClassGender, and only the quoted log line was wrong - the grep instruction lower in the same section always worked. Corrected in OBSERVED_IDS.md.
NEW - the Auction House Affix Effects dropdown is a CATALOGUE, the thing AFFIXES.md said it did not have. 16 entries, bounded by two frames showing the first and last rows flush. It is NOT the whole affix set: Focused, Elusive and Curse are on the character and absent from it, so an argument from absence is refused in advance. 22 affix names now known, ten of them new.
NEW - the game PUBLISHES COOLDOWNS, 10s and 60s verbatim in a gem tooltip. The blanket 'no cooldowns are published for this game' is false as written; it stays true for class abilities, which nothing here touched.
NEW - a client patch runs through the corpus, 1.0.14 to 1.0.15. Every 2026-08-25 row in OBSERVED_IDS is provisional by that file's own rule. Consequences recorded both ways: the eight-item affix stability result gets STRONGER because six items survive the patch unchanged, while the missing GA_Affix_HitSwiftness now has two competing explanations - rotation or removal - which the document refuses to choose between.
NEW - equipment slots 0 to 6 and 11 bound to the game's own slot nouns by a two-surface join on item cfgId, no pixels needed. weapon1 deliberately left UNBOUND because the log never emits it with a cfgId; slot 10 by elimination is an inference, not a join.
CORRECTED, three of my own counts before they shipped: a '3,756 affix hits' figure that added two LINE counts, an escaped-form count of 25 that is 17, and an id-211 total of 31 that is 37. A second pass re-derived every published number and caught all three.
CORRECTED across documents - CLASSES.md still claimed the community affix names were 'almost certainly gem effects wearing legacy ARPG vocabulary' three weeks after AFFIXES.md refuted it, because the whole affix workstream touched only one file. All seven guide names are real game vocabulary. Recorded as C14 with the wrong Emberforge schema guidance it produced.
OPEN, recorded not answered: the refutation pass reported the dropdown holding 22 affixes across 11 rows and named a row 'Ethereal'. Neither is reproducible from any frame examined here, and two frames bound the list at 8 rows. Written down rather than resolved in the count's favour.

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

