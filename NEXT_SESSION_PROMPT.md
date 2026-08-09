# Next session - start here

Paste the block below into a fresh session opened at `C:\Lanternlight`.

---

You are working on **Lanternlight**, a companion and analysis project for the
Steam game Mistfall Hunter. Repo root `C:\Lanternlight`, public at
`github.com/Remus3/Lanternlight`, Apache-2.0.

**Read first, in this order:** `CLAUDE.md`, `README.md`, `docs/FINDINGS.md`,
`docs/OBSERVED_IDS.md`, `ROADMAP.md`, `docs/HEADLESS.md`, then `git log`.

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
3. **Redact before anything leaves the machine.** The game log carries the
   operator's SteamID64, persona, GSDK and EOS ids, and IP geolocation.

## How this session should run

Orchestrated, multi-agent, parallel, self-adjudicating, self-adversarial - the
default, not an escalation. Decompose into disjoint slices, give each agent an
explicit file list, adjudicate competing outputs with a distinct agent, and gate
every "done" claim through the `verifier` subagent, which is trying to refute
it. Agreement between two agents is not evidence.

TDD: failing test first, and prove the guard is not vacuous by watching it go
red before you trust it green.

The operator will usually be playing the game and unable to read chat. Do not
block on them. Use text-to-speech if you genuinely need to reach them:

```
Add-Type -AssemblyName System.Speech
(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("message")
```

## State as of 2026-08-09

- Two commits, suite green at 182, ruff clean, 61 of 61 tracked files scanned by
  both hygiene guards.
- Emberforge computes nothing on purpose. No cooldowns or damage coefficients
  are published for this game by anyone; inventing them is the one failure mode
  this project exists to avoid.
- Character: Blackarrow (classId 12), body type 2, slot 1. Shadowstrix reserved
  for slot 2 at roughly hour 20. Slot 3 free.

## The highest-value thing to do next

**The raid recon pass.** Every measurement so far comes from camp and character
creation. Nobody has entered a raid, so loot names, extraction events and match
results are *unmeasured, not absent*. Until that is settled, the shape of the
whole data model is a guess.

Concretely: while the operator plays one raid, run `tools/frame_poller.py` and
afterwards diff the new log lines against the known categories. Look for
`TS.Dungeon`, `TS.Inventory` and match-state transitions carrying real payloads.
Record findings in `docs/OBSERVED_IDS.md` with the observation method named.

Then, in rough priority order from `ROADMAP.md`: the GVAS `.sav` reader, the
live log tail, the `AvgPrice` market watcher, the Sorcerer single-weapon
question, and the stance-toggle probe that produced no distinguishable event.

## Two open questions nobody has answered

- Is Sorcerer genuinely a single-weapon class, or was its second weapon simply
  not surfaced during the creation walk? Until this is settled, **do not write
  "Blackarrow is the only single-weapon class" anywhere.**
- Does an always-on-top non-injected overlay draw cleanly over this game in
  windowed-fullscreen, and does the anti-cheat tolerate it? Judged low risk and
  accepted knowingly, but unproven in practice. See `docs/OVERLAY.md` section 2.
