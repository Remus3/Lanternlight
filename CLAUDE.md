# Lanternlight - Agent Context

Companion and analysis project for **Mistfall Hunter** (Steam appid 3282300, dev
Bellring Games, pub Skystone Games, Unreal Engine 5). Reads the game's own log
and save files plus passive screen capture, computes build and combat math in
**Emberforge**, and surfaces it in a separate window. Public repo, Apache-2.0,
upstream `github.com/Remus3/Lanternlight`.

**Standalone.** Lanternlight shares no code, no ports, no scheduled-task
namespace and no API keys with any other project on this machine. Sibling
projects exist locally and some of their patterns are worth reusing. If you find
yourself importing from one of them, stop - copy the idea, never the wire. A
shared import is a shared failure, and this repo is public while they may not
be.

> **Living docs, read at session start:** [`README.md`](README.md) -
> [`docs/FINDINGS.md`](docs/FINDINGS.md) - [`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) -
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - [`ROADMAP.md`](ROADMAP.md) -
> [`docs/HEADLESS.md`](docs/HEADLESS.md)
> **Decisions:** [`docs/adr/README.md`](docs/adr/README.md) - check here before
> re-litigating a past choice.
> **Ledger:** [`docs/LEDGER.md`](docs/LEDGER.md), append-only, newest first.
> Never put a ledger entry in this file.

## THE HARD BOUNDARY - read first, it defines the project

Mistfall Hunter ships **kernel-level anti-cheat** (Bellring). Lanternlight never
touches the game process. Never:

- inject a plugin, load a DLL into it, or open a handle to it
- read its memory
- capture or proxy its network traffic
- hook its swapchain, its Present, or its window
- synthesize keyboard or mouse input into it

Permitted: reading files the game writes into user-writable space, passive
screen capture of the operator's own display, and a **separate always-on-top
window** of our own (an ordinary Windows window, not an injected overlay).

The stake is a permanent ban on the operator's real account. There is no debug
flag or one-off experiment that makes any forbidden item acceptable. If a feature
requires one, the feature is rejected, not the rule.
[ADR-001](docs/adr/ADR-001-no-game-process-interaction.md).

Also measured, so nobody re-researches it: the game has **no Steam Workshop, no
level editor, no mod support**, and **all 15 pak chunks are AES-encrypted**, so
there is no asset extraction and no modding route regardless of the above.

## Session Default

**Every session is orchestrated, multi-agent, parallel, self-adjudicating and
self-adversarial. This is the baseline, not an escalation.** Choosing it needs no
justification; departing from it does.

- **Orchestrated** - one merger holds the plan and owns the merge. Work is
  decomposed into disjoint slices before any of it starts.
- **Multi-agent and parallel** - slices run concurrently on non-overlapping file
  sets. Give every agent an explicit file list and tell it to touch nothing else.
- **Self-adjudicating** - a distinct agent decides between competing outputs
  against stated criteria. The agent that produced a thing never grades it.
- **Self-adversarial** - every "done" claim and every finding gets an independent
  pass that is trying to REFUTE it, defaulting to refuted when uncertain.

**Agreement between two agents is not evidence.** Two agents can be wrong the
same way, and in this repo's own history two agents produced a real contradiction
about class weapon stances that only a specific official quote resolved. When
slices agree, that is a hypothesis, not a verification.

The only exception is genuinely trivial work - a one-line cosmetic edit, a doc
typo, a conversational answer. Substance decides, not file count.

### Never file a suggestion - do it, or write it down as an open item

**No agent in this project spawns a background task, a suggestion chip, or a
"someone should look at this" note.** If you find work worth doing: either do it
now, or add it to `ROADMAP.md` with an acceptance criterion, or add it to the
ledger as a recorded question. Those are the only three destinations.

A suggestion that lives outside `ROADMAP.md` and the ledger is invisible to the
next cold session, which is the one failure this project's whole continuity
design exists to prevent. It also quietly moves the work onto the operator, who
is playing the game and is the one person who cannot action it right now.

### Re-probe every subagent claim - `ops/merge_gate.py`

The recurring failure is not a subagent lying, it is a subagent being **skipped
or believed**. A green suite does not prove work landed: `pytest` exits 0 just
as happily on 181 tests as on 182, so an agent that deletes or weakens a test to
go green is invisible to an exit code.

Before relaying any agent's "done", run the gate:

```python
from ops import merge_gate
report = merge_gate.verify(
    claimed_paths=["the/files/it/said/it/wrote.py"],
    baseline=COUNT_MEASURED_BEFORE_DISPATCHING,
)
print(report.format())
```

It asks the filesystem whether the files exist and are non-empty, re-runs the
suite, parses the real summary line, and **fails if the collected test count
dropped below the baseline**. The baseline is a parameter, never a stored
constant - measure it with `python -m pytest --collect-only -q` before
dispatching work, because a count checked into a file goes stale and becomes a
confident lie.

The gate is necessary, not sufficient. It cannot tell you a claim is *true* -
only that the mechanical parts of it are not obviously false. A claim about what
the game does still needs re-measuring against the log.

### Keep the merger's context sane

The merger holds the plan, so the merger is the context that must not fill.

- Agents doing research or bulk analysis **write their full output to a file
  under the session scratchpad and return a short summary** - a few hundred
  words at most. Six 33 KB research documents must never be pasted back through
  chat.
- The merger reads those files only when it needs them, or hands them to a
  composing agent that reads them instead.
- Pick the model per slice rather than uniformly. Security-critical or subtle
  logic gets the strongest model; broad web research and mechanical sweeps do
  not need it.

## TDD - not optional

Every feature and every bugfix starts with a failing test.

1. Write the failing characterization or regression test first. Watch it fail.
2. Implement the minimum that makes it pass.
3. Run the full suite before committing: `python -m pytest` from the repo root.

**Prove your guards are not vacuous.** A green test proves nothing until you have
seen it go red. Before trusting a new guard, break the thing it guards, confirm
the test fails, restore, confirm green. Report what you saw. A guard that stays
green when you delete the behaviour it protects is not a test, it is decoration.

Related traps this repo has already hit or inherited:
- A mutation that fails to apply looks exactly like a passing test. Assert the
  anchor text matched before believing a survivor.
- A raising spy is vacuous under fail-soft code, because `AssertionError` is an
  `Exception` and a bare `except Exception` swallows it.
- A negative assertion rules something out without pinning anything down.

## Authoring rules

- **7-bit ASCII only, in every authored file** - code, comments, docstrings,
  Markdown, commit messages, chat output. No em-dashes, no en-dashes, no smart
  quotes. Use ` - ` for a clause break, `-` otherwise. Enforced by
  `tests/test_ascii_hygiene.py` and by `.githooks/pre-commit`.
- **Never add a `Co-Authored-By` trailer to a commit message**, and never file its
  absence as a defect. Operator policy. `.githooks/commit-msg` does not add one
  and does not strip one - the rule is simply that you do not write one.
- **Atomic writes only** for anything a reader might poll:
  `tmp.write_text(...); tmp.replace(target)`.
- **Never `Stop-Process`.** If a process genuinely must die, `taskkill /F /PID`.
  The loop guard never kills anything; it only refuses to start.
- **Redact before anything leaves the machine.** The game log carries the
  operator's SteamID64, Steam persona, GSDK openID and userId, an EOS
  ProductUserId, and IP-resolved geolocation. `lanternlight/redact.py` is the only
  sanctioned path, `tests/test_no_pii.py` is the backstop, and no raw log excerpt
  is ever committed. [ADR-004](docs/adr/ADR-004-redaction-is-mandatory.md).

## Ports

**This project's block is 8810-8819**, widened from 8810-8814 by the operator on
2026-08-27. Do not allocate outside it, and do not bind at import time.

The machine-wide registry, recorded here so nobody re-derives it by probing for
a free port:

| Block | Project |
|---|---|
| 8770-8789 | Red Moon (RM) |
| **8810-8819** | **Lanternlight (LL)** |
| 8860-8879 | Daemon Slayer (DS) |
| 8888-8895 and 2999 | Amberstone (RC) |
| 8900-8919 | LegionWallpaper (LW) |
| 8920-8939 | Clockspeed (CS) |

**Knowing a neighbour's block is not permission to talk to it.** The standalone
rule at the top of this file still holds: no shared code, no shared ports, no
shared keys. This table exists so an allocation avoids a collision, not so a
service can find a sibling.

| Port | Service | State |
|---|---|---|
| 8810 | Dashboard | not built |
| 8811 | Log-tail service | not built |
| 8812 | Vision / OCR service | reserved, not built |
| 8813 | Emberforge engine | library only, no service |
| 8814 | Overlay control channel | reserved, unbound |
| 8815-8819 | unallocated | free |

## Paths

- Project root: `C:\Lanternlight\`
- Python: `C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe`
- Game install: `C:\Program Files (x86)\Steam\steamapps\common\Mistfall Hunter`
- Game log: `%LOCALAPPDATA%\MistfallHunter\Saved\Logs\MistfallHunter.log`
- Game saves: `%LOCALAPPDATA%\MistfallHunter\Saved\SaveGames\*.sav` (plain GVAS)
- Loop runtime state: `ops/runtime/` (gitignored)

## Fresh clone - do this first

`core.hooksPath` is LOCAL config and is never cloned, so a fresh clone of this
repo runs **zero** git hooks until someone wires them. The tracked `.githooks/`
directory does nothing on its own.

```
python scripts/install_hooks.py
python -m pytest
```

Never treat a hook's presence as proof it fires. The only valid test is
end-to-end: stage a banned glyph, attempt a real commit, assert HEAD is unchanged.

## Verification discipline

- Re-verify against ground truth before calling anything green. The tool pipe can
  replay stale results.
- **Never trust a subagent's claim** about test counts, green CI, or file
  existence without an independent probe. Subagents have cited test files that do
  not exist. Confirm the file with a listing and re-run the suite yourself.
- Report the exact pass and fail counts you observed **this run**. Never carry a
  count forward from an earlier run or from an agent's report.
- Do not restate a suite count in this file. It goes stale and becomes a lie.
  Measure it with `python -m pytest --collect-only -q`.
- **Proving your change happened is not the same as proving it matters.** Diff the
  consumer's output, not just the line you edited.

## Measurement doctrine

Nobody has published cooldowns, damage coefficients or stealth durations for this
game. Any site quoting a second value is fabricating one. Emberforge exists to
measure what is unpublished, so:

- **Omit rather than guess.** A missing field is absent - not null, not `0`, not
  `-1`. A missing number is recoverable; a confident wrong one is not.
- Keep "unmeasured" distinguishable from "measured zero". They are different
  facts and conflating them is how a build engine starts lying.
- Every id-to-name binding is recorded in
  [`docs/OBSERVED_IDS.md`](docs/OBSERVED_IDS.md) at the moment it is observed,
  with the observation method named. An id learned later from a wiki is not the
  same fact as an id watched being emitted.
- Launch-window wiki sites for this game cross-copy each other verbatim.
  Agreement among them is not corroboration. Trust order: official Steam news and
  dev posts, then first-party player evidence, then established outlets, then
  those sites, and never cheat or boosting vendors.

## Working unattended

The operator plays the game while Claude works. Sessions must therefore
self-continue: continuity lives on disk - git history, `docs/LEDGER.md`,
`ROADMAP.md`, and the directive chain in `ops/loop/` - never in a context window.
A cleared or compacted session resumes from files alone.

- Do not block waiting for the operator. If you hit a genuine decision gate,
  record the question in the ledger and move to the next item.
- Read [`docs/HEADLESS.md`](docs/HEADLESS.md) before starting a loop, especially
  its STOP CONDITIONS.
- Commands: `/continue` resumes from disk, `/loop` runs unattended, `/done` wraps
  and pushes.

### Talking to the operator mid-game

The operator cannot read chat while playing. Use text-to-speech instead - it is
out of process and touches nothing:

```
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = -1
$s.Speak("your message")
```

## Vision, capture and OCR

Passive only. Reading pixels is always allowed; sending input never is.

- **Screen capture** via Pillow `ImageGrab`, or the frame poller in `tools/`.
  Frames carry local wall-clock in the filename.
- **The join that makes capture worth something:** the game log timestamps in
  **UTC** and capture filenames are **local** (UTC-5 here), so a screenshot can be
  matched to a log line by wall clock. That is how class names were bound to
  numeric ids - rendered text read off a frame, joined to `setClassGender
  inclassid` in the log. Prefer this over OCR guesswork.
- Beware render lag when joining: the ROLE panel lags the selection by about one
  frame while the sidebar highlight leads it. Read the panel for the outgoing
  state and the sidebar for the incoming one.
- **OBS** is available on this machine for recording a session for later review.
  Recording is passive capture and is fine. Do not use it to drive anything.
- Prefer text over pixels whenever a text path exists. Reading a number out of a
  log beats OCR-ing it off a screenshot every time.

## Memory recall

This machine runs **Perseus Vault**, a local semantic-recall store (one binary
plus a SQLite file under `~/.perseus-vault/`, no cloud, no API key), wired as the
`perseus-vault` MCP server. It exists because the recurring failure is not
ignorance, it is REDISCOVERY - redoing closed work, re-pitching a refuted idea,
or acting on a stale doc.

- The vault on this machine is currently scoped to a **different project**. Do
  not write Lanternlight facts into it and do not treat anything recalled from
  it as authority here - a hit from another project's vault is someone else's
  context wearing a confident tone.
- If a Lanternlight vault is stood up later, it is a **MIRROR, never the source
  of truth**. Source of truth stays this file, `docs/`, `ROADMAP.md` and the
  ledger. Never fix a fact only in the vault.
- Recall through a projection tool, not the raw MCP call - the raw call returns
  each hit's body twice and a mandatory step that costs thousands of tokens is a
  step that gets skipped.
- A `healthy` status is not proof recall works. Only `embedded == active` proves
  coverage; without it recall silently degrades to keyword matching.

## Third-party code - license gate

Before lifting anything from an external repo, check the license and say what it
is. Apache-2.0 here means GPL and AGPL are DO-NOT-VENDOR - vendoring them would
relicense this project.

Traps worth knowing, all previously measured:
- A repo can contradict itself - an MIT `LICENSE` file beside a
  `"license": "UNLICENSED"` manifest, or GPL-3 beside `"ISC"`.
- A `LICENSE` can name nobody, e.g. an unrendered template reading
  `Copyright (c) {{ year }} {{ organization }}`. Read the copyright LINE, not
  just the license name.
- The person who cleared it may not own it. A repo crediting prior authors has
  multiple copyright holders and its maintainer cannot unilaterally relicense it.
- BUSL-1.1 is source-available, not copyleft, and still DO-NOT-VENDOR.

Techniques and protocol facts are not copyrightable; source is. The always-legal
path is to re-implement from observed behaviour.

## Anti-patterns, learned the expensive way

- **A filed count is a hypothesis.** Every count re-derived from the artifact has
  been wrong at least once. Recompute tallies at merge time.
- **An empty grep is a claim about your pattern**, not about the codebase.
- **A caveat stated in chat but dropped from the artifact is a lie in the
  artifact.** If you hedged it out loud, write the hedge down.
- **A decline reason goes stale faster than the count does.** Re-check why
  something was rejected before citing the rejection.
- **A rendered field is not evidence of a producer.** Grep the writers.
- **`.claude/settings.json` containing single-backslash Windows paths is invalid
  JSON**, so it never parses, no hook registers, and nothing warns you. Use
  forward slashes and assert the file parses before trusting a negative.
- **Windows `write_text` turns LF into CRLF**, and `read_text` hides it. Byte
  counts lie. The `.githooks` scripts must stay LF or Git for Windows chokes on
  a CR in the shebang.
