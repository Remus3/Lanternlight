# Lane ledger fragment - research

Completed work by the `research` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

### LL-0023 - 2026-08-11 - Transient dungeon save decoded from its whole 263-generation lifetime - 8 filed claims re-measured, 2 refuted, 2 redaction false-positive classes named

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

