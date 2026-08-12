# Lane ledger fragment - ops

Completed work by the `ops` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

