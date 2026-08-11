# Lane ledger fragment - safety

Completed work by the `safety` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

### SAF-0001 - 2026-08-11 - ROADMAP 2b - name the save-file id shapes, and record the Blueprint-GUID false positive rather than silence it

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

