# Lane ledger fragment - ingest

Completed work by the `ingest` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

