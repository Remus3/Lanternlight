# Lane ledger fragment - ingest

Completed work by the `ingest` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

