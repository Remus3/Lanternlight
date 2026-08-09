# Lane ledger fragment - ops

Completed work by the `ops` lane, newest first, each entry
carrying its acceptance evidence. **Append-only** - entries are never
edited, reordered or deleted.

This file exists so that eight lanes on eight branches never all append
to `docs/LEDGER.md` and conflict at merge. Only this lane writes here.
The integrator folds these entries into `docs/LEDGER.md` on `main`, with
`ops.lane_state.integrate`, which is idempotent and safe to re-run.

<!-- LANE ENTRIES BELOW - NEWEST FIRST -->

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

