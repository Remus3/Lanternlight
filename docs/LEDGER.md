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

`LL-NNNN`, allocated in order, never reused. An id that appears in a roadmap
item, a branch name, a commit message and a ledger entry is what ties those
four records to each other.

<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->

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
