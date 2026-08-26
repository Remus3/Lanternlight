# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`
(sections 11 to 15), `docs/OBSERVED_IDS.md`, `ROADMAP.md`, `docs/HEADLESS.md`,
`WAKEUP_NOTES.md` (top entry only), then `git log --oneline -15`.

**Before touching anything:**

```
python scripts/install_hooks.py
python -m pytest
```

A fresh clone runs zero git hooks until that first command runs. The tracked
`.githooks/` directory does nothing on its own.

## The three rules that are not negotiable

1. **Never touch the game process.** Kernel-level anti-cheat. No injection, no
   memory read, no packet capture, no swapchain hook, no synthetic input. The
   stake is a permanent ban on the operator's real account. Passive screen
   capture and reading files the game writes are fine. See ADR-001.
2. **7-bit ASCII everywhere**, and never add a `Co-Authored-By` trailer.
3. **Nothing log-derived is committed without passing the redactor**, and that
   includes other players' names, not only the operator's.

---

## Where the last session left it

**Suite 1244 passed / 1244 collected, ruff clean**, measured on a clean tree
with `__pycache__` purged - that is your merge-gate baseline, and re-measure it
yourself before dispatching work rather than trusting this line.

The session's ledger entries start at **`LL-0056`**. **Read `LL-0064` FIRST.**
It is an independent four-agent refutation pass and it **overturns claims the
earlier entries make**. Reading LL-0056 through LL-0063 without it will leave
you believing things that were withdrawn.

## Check the world before anything else

```
tasklist | grep -qi mistfall && echo "CLIENT OPEN" || echo "client closed"; stat -c '%y %s' "$LOCALAPPDATA/MistfallHunter/Saved/Logs/MistfallHunter.log"
```

That is Bash, not PowerShell - `grep` and `stat` do not exist in this repo's
default shell. Run it through the Bash tool.

**Then arm capture, whatever the answer. It is one command now:**

```
python -m lanternlight.armwatch --dest-root C:/ll-captures/<today>
```

That is ROADMAP 4c, closed last session. It arms all four surfaces at intervals
argued from measured triggers, and it **refuses a destination inside a git
working directory** rather than trusting you to remember. It watches the
`Logs/` DIRECTORY, not the log file, which is what catches a launch's
`MistfallHunter-backup-<UTC>.log` - so arming at session start recovers the
PREVIOUS session as well as preserving the current one. Whether a launch leaves
a backup at all is **unmeasured**: one did, an entire earlier session had none.

## NEXT: ROADMAP item 10 - the stack buff, measured AT THE CEILING

**This is the highest-value open question, because an existing headline finding
may be an artifact.**

The operator found a buff icon that climbs to **5** while he keeps hitting the
same target inside a time limit, centre screen above the energy bar. It is
readable in a half-scale wide shot at `x 600-690, y 600-665`, and joining that
crop to the meter crop on wall clock puts stack count and cumulative damage on
one row.

`FINDINGS` 11.7 says a constant per-hit value fits every FLOOR run and no
off-floor run, and reads that as constancy being a property of the clamp. **A
buff of ~1% per stack reproduces that split with no distance term at all** -
invisible at 10.35 per hit, visible at 55 to 69. The ten-point curve is
untouched; the inference is contested.

**Measure at the CEILING. The floor is insensitive** - at ~13.5 per hit the
whole five-stack bonus rounds away, which is why nine floor runs gave only a
4-count spread. At ~90 per hit it is several display units.

Acceptance is in ROADMAP 10, including the target-switch test that separates
`Focus Fire` from a base mechanic. **Do not attribute the buff to Focus Fire
without it**: the tooltip scopes that talent to `Rapid Arrows`, and 2.27-2.87 s
inter-hit intervals prove drawn shots, not Volley.

**If the client is shut:** work **OPS-8** (the suite reddens under concurrent
pytest runs, which breaks the merge gate this project depends on) or **7c**
(the meter reader needs one template set PER FIELD; the groundwork and the
failure modes are written up).

## Traps this session paid for

- **Point verification at the READINGS, not the arithmetic.** Four independent
  refuters found **zero** arithmetic errors and **eight** bad readings: a
  misread frame, an invented explanation for a sampling gap that did not exist,
  a circular citation, a binding read off a `Puerts: Error` line, a delta
  transposition that summed correctly either way.
- **A sum is not a check on an ordering.** A transposed delta list summed to the
  same total, so every total-based check passed it.
- **A self-run refutation cannot find a fix you applied in only one place.**
  LL-0058 corrected an over-claim in two files and missed a third in the same
  commit. An independent pass found it immediately.
- **"Which conclusion feels less exciting" is not evidence.** The mode-versus-
  patch call was made that way and was refuted; build and mode are perfectly
  confounded.
- **Quote the DELIVERED capture rate, not the requested one.** A poller asked
  for 2 fps delivered 1.19.
- **A full-screen PNG is ~3.1 MB; the panel crop is ~235 KB.** Crop at capture
  time. Disk sat at 95% all session.
- **`taskkill /F /PID` needs `//F //PID` from Git Bash**, or MSYS mangles the
  flags into paths. `Stop-Process` is forbidden.
- **An over-constrained grep gives a false negative.** One here did, and was
  caught only by re-checking with a positive control. Always prove the pattern
  on a file that DOES contain the string.

## Operator context worth having

Plays **Blackarrow** (classId 12), now **level 5**, second character at classId
13. Right-click is the primary attack (binds swapped). Counts distance in
**paces** - a full stride off the run-cycle animation loop reset, no crouch,
sprint or roll.

**He is the reason the best result of the session exists.** He spotted the stack
icon, then designed and ran the capped-stack experiment himself without being
asked. When he reports a mechanic, capture it and check it - do not explain it
away.

**He cannot read chat while playing.** Use text-to-speech for anything he needs
mid-game, keep it short, and never block waiting for an answer.

Capture evidence from the session is under `C:/ll-captures/2026-08-25b/` and
contains his account name and third-party player ids. **It must never be
committed.**
