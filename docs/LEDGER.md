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
