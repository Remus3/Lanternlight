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
