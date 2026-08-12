# Lane ledger fragment - ops

Completed work by the `ops` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

