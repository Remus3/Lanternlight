# Lane ledger fragment - research

Completed work by the `research` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

