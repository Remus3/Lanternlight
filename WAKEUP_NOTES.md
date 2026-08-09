# Wakeup notes

Session hand-off. Newest session first. Keep the last two or three at full
fidelity and archive older ones rather than deleting them.

---

# Session 2026-08-09c - the lane machinery finished, and a save caught mid-flight

Orchestrated and multi-agent throughout. Branch
`session/2026-08-09c-lane-state-and-capture`, **merged to `main` at the
operator's instruction** and pushed - `main` is `58ff2e7`. Ledger `LL-0018`
through `LL-0022`. 685 tests at the start, **807** at the end, all green from
purged caches on `main` after the merge, ruff clean.

## The thing that mattered most, and it was luck plus ten minutes

The hand-off said `StandaloneSlot_<roleId>.sav` was PERISHABLE and that the
previous session had lost it. Ten minutes into this session, before touching
the roadmap, a crude poller was armed against the save directory. **Seventeen
seconds later the file appeared.**

It was caught whole: **263 generations, 105 distinct sizes, 2,190 bytes at
17:27:17 to 177,878 at 17:46:54**, and then it deleted itself. Every one of
those 263 generations now parses with zero undecoded bytes.

Three filed claims about that file were wrong, and only capturing it showed
that:

- **not 46 KB** - it ends near 178 KB, about 62x the next largest save. The old
  figure was a file read mid-write and mistaken for its size.
- **not append-only** - it measured *smaller* fifty seconds after a peak. It is
  rewritten in place, so one snapshot can be a torn read.
- **not a 13-minute life** - it was still being written 19m37s in.

The lesson is not about this file. It is that arming a watcher **before** the
event costs ten minutes and re-reading a document costs the whole observation.

## ROADMAP 1b is closed - and a lock was the wrong answer

Per-lane state is `lanes/<lane_id>.STATE.json`; the ledger race is solved by
`lanes/<lane_id>.LEDGER.md` fragments that only the integrator folds into
`docs/LEDGER.md`.

**The roadmap offered a lock as one of two options. A lock does not work**, and
that is now written down so nobody re-proposes it: a lock serialises writes in
*time*, but lanes are on different *branches*, and git merges *content*. Two
perfectly serialised appends still conflict. `tests/test_lane_state.py` proves
the point with real git merges - the shared-file shape is asserted to CONFLICT
and the fragment shape to merge clean. Proving only the second would have shown
the change happened without showing it mattered.

## The layout is flat because two safety guards said so

The first cut used `lanes/<id>/STATE.json`. `lanes/capture/` was then rejected
by **two independent PII guards** - `.gitignore`'s bare `capture/` rule and the
pre-commit hook's `*/capture/*` rule - both behaving exactly as designed. The
lane directory was a false positive against a correct rule.

Weakening a veto-holding lane's guard for a naming convenience was the wrong
trade. Flat files (`lanes/capture.STATE.json`) remove the whole collision class
rather than one instance: `logs`, `frames`, `private` and `tmp` are blocked the
same way, so a future lane named after any of them would have failed
identically and nobody would have connected symptom to cause.

## Three traps, all of them this repo's own documented anti-patterns

Hit anyway, which is the point of writing them down again:

1. **CRLF.** The first `.gitignore` carve-out looked applied and was not - the
   negation lines were written with CRLF while the file was LF, so each pattern
   carried a trailing CR and matched nothing. The file read back as correct.
   Only the byte count showed it.
2. **`git check-ignore` is the wrong probe.** It exits 0 when *any* pattern
   matches, **including a negation**, so a correctly re-included file reports
   exactly like an excluded one.
3. **The orphan guard could not have caught the hole it exists to catch.** It
   walks `git ls-files`, so a path git is *ignoring* is invisible to it. The
   blind spot and the bug were the same shape.

## Live operator attestation, and what the log said back

Mid-session the operator reported: at level 3, **Marksman** was the **only**
talent choice at that tier, and **Lightning Arrow** went into the **C** skill
slot. The log was checked immediately and yielded a previously unrecorded
shape:

    [SkillSlotView::OnRequestEquipAmmo]  Equip ammo: ammoId: <id>, destSlot: <n>

**Exactly two equip events exist in the entire log and both target
`destSlot: 2`, at level 3** - which independently corroborates from the log
what `LL-0016` read off the screen: the C arrow slot unlocks at Lv. 3 and is
the first slot a player must fill. Four ammoIds appear overall - 120501,
120502, 120508, 120510 - a 1205xx space distinct from item cfgIds.

**Which id is Lightning Arrow is deliberately NOT recorded.** Two were equipped
to that slot five seconds apart and the log names neither. That binding needs
the operator or a frame, and inventing it would poison exactly the file whose
value is that it does not invent things.

**Measured negative, worth as much as a positive:** the equipped loadout is in
**no local save**. All seven saves plus the largest capture were searched for
those ids as ASCII, int32, int64 and float64 - zero hits. The log is the only
local surface carrying a loadout, so Emberforge cannot read one from disk.

## Two safety findings, routed to the lane holding the veto

- **`SAF-3`** - inventory instance ids share a **12-digit prefix** with the
  operator's roleId. Masking the roleId alone does not mask them, and each one
  leaks that prefix.
- **`SAF-4`** - some `TS.UI` lines carry **CJK text**, so a raw log excerpt is
  neither ASCII nor single-byte.

## The refutation pass earned its keep, twice over

An independent verifier was told to REFUTE this session's own claims and to
default to refuted when uncertain. It refuted nothing - but it found **two
guarantees that were narrower than the words describing them**, and both were
in code this session had already mutation-tested and called proven:

1. **The read-only refusal was bypassable.** It lived only in `state_path()`
   and `fragment_path()`, so every default route raised and every route taking
   an explicit `path=` walked straight past it. `save(LaneState(lane_id=
   "verify"), p)` wrote a file. "Eight entry points raise" is not the same
   property as "verify writes nothing, ever" - and only the second is what
   lets a read-only lane grade other lanes' work.
2. **`integrate()`'s `reversed()` had zero coverage.** Removing it left the
   whole suite green, because every test used a single-entry fragment. The
   docstring promise that newest lands on top was decoration.

**The lesson is about the method, not the bugs.** An author's own mutation
testing aims at the code that exists; it does not aim at the route around it,
and it cannot notice a promise nothing ever exercised. That is precisely why
the adversarial pass is a separate agent with a separate brief, and why
"agreement is not evidence" is written the way it is.

It also caught two stale things worth knowing: the merge test was still
building fragments at the **nested** `lanes/<id>/LEDGER.md` layout abandoned
earlier the same session, so it had stopped exercising what ships; and the
conflict assertion matched the bare word `CONFLICT`, which also matches git's
own advice text "fix conflicts".

One process note for next time: the verifier ran while the branch was moving
under it, and it handled that correctly by re-anchoring to pinned clones. But
a refutation pass is cheaper and sharper against a frozen ref - dispatch it
after the last commit of a slice, not during.

## Where to start next

**Item 2b** - the sanitised fixture for the transient save. It is safety-lane
work and it is specified. Read `lanes/safety.STATE.json` first; every lane now
carries its own queue, so read the state file of the lane that owns the files
rather than re-reading the whole roadmap.

The capture bytes are at `C:\ll-captures\saves\`, **outside the repo, not
committed**, and the filename embeds the operator's roleId.

One caveat worth keeping: a lane that adds a **new** file cannot go green
alone, because ownership is declared in `ops/lanes.py`, which the ops lane
owns. Measured on `lane/ingest`. Open as `OPS-2`.

# Session 2026-08-09b - recon, redaction P0, and the lane architecture

The second session, and much longer than the first. It ran orchestrated and
multi-agent throughout: roughly a dozen parallel agents, two persistent lanes in
their own git worktrees, and an adversarial verifier that returned nine defects
in this session's own findings.

Work is on branch `session/2026-08-09-recon-redaction-lanes`, pushed, **not
merged to `main`**. Ledger entries LL-0002 through LL-0012.

## The thing that mattered most

**The redactor was leaking.** Running it over the live log left **684 of 686**
occurrences of the operator's persona in place, and `assert_clean()` returned
cleanly on a leaking line - so the guard was vacuous for that shape. Two root
causes: keyed rules stopped their value match at whitespace, half-masking a
two-token display name; and the persona also appears with **no key at all**, as
a positional comma-separated field and after verbs like `PlayerOpenTreasureBox`.

Then a second, subtler defect surfaced on review: persona discovery returned
empty on an **isolated excerpt** - which is exactly what a test fixture is - so
the keyless shapes passed through and `assert_clean` approved them. Fixed, and
`assert_clean` gained a **cannot-certify** state so it refuses to approve text it
has no basis to approve. That distinction - "I could not determine this is safe"
is not "this is safe" - is the omit-rather-than-guess doctrine applied to a
guard, and it is worth keeping.

This blocked the raid-recon acceptance criterion outright, because that criterion
requires committing a redacted log excerpt.

## The recon nobody needed to capture

ROADMAP item 1 was written as "do a deliberate capture session". It was not
needed. The operator had played 3h44m and the log had grown 567 KB to 6.1 MB -
the data was already on disk. Re-probing live state instead of trusting the
document is the single highest-value habit this project has.

Measured: the dungeon lifecycle across two runs, the escape-portal mechanic, the
`Game.PlayState.*` namespace, six inventory opcodes, four loot contexts, 35
item cfgIds, and the join proving **the live `holding-` id space and the item
cfgId space are one space** (`3020401` is both the equipped weapon and a
tradeable item priced at 31).

Also: the game's nouns are **dungeon** and **escape**. `raid` and `extract`
appear **zero** times.

## Nine defects, in our own findings, from one adversarial pass

An independent verifier was dispatched to REFUTE the recon and returned nine.
The instructive ones:

- A death was attributed to the operator that belonged to somebody else.
- A scope label said "`cfgId:` anywhere in the log" and measured a pattern that
  silently dropped an entire subsystem, because `TS.FTE` writes `cfgId: 123`
  **with a space** and the pattern required none. 35 versus 45 ids.
- "SEscapePortalSpawner places a portal" - it placed nothing; all six of its
  lines are failures to find a config. A producer inferred from a name.

Then the **operator's own attestation** ("I had one death, in the tutorial")
corrected the correction. The log had been read wrong twice: `WaitSpiritual` is
the death state and `Spiritual` the resurrection state, the operator's death is
recorded by `OnPlayerDead` and **not** by a `Game.PlayState.Death` tag, and the
"second player" is a **bot** the operator killed. PvP is a clean null after all.

Lesson worth carrying: three passes, three different wrong answers, settled by
one sentence from the person who was there.

## The lane architecture

Eight persistent specialist lanes, each owning a disjoint file set, each in its
own git worktree on its own branch, none merging to `main`. Operator-chosen
shape. `ops/lanes.py` declares the roster and `tests/test_lanes.py` enforces the
invariants **mechanically** - no repo file has two owners (walked over the real
tree, not compared as pattern strings), cross-cutting files like `CLAUDE.md` are
owned by nobody, `safety` holds a veto, `verify` owns nothing and is read-only.

Contracts in `.claude/commands/lane-*.md` are **generated** from the roster, so
ownership and prose cannot drift; the drift guard is proven by mutation.

**Running a lane end to end found two defects that reading the code never would**,
both in the same family: a path derived from `__file__` is not a fact about the
repository. `lanes.REPO_ROOT` resolves to the *worktree* inside a worktree, so
every "this is not the primary checkout" assertion inverted; and
`ensure_worktree` defaulted to it, so creating one lane's worktree from inside
another's forked the new branch off the wrong HEAD, silently importing another
lane's work. Both fixed via `primary_checkout()`, which asks
`git rev-parse --git-common-dir`.

## Two lanes actually ran

`ingest` built the GVAS `.sav` reader (ROADMAP item 2) and then finished it -
all 627 trailing bytes of `EnhancedInputUserSettings.sav` decode, and the result
**cross-corroborates the log**: save and log independently agree that
`KB_Blackarrow_Major_Action` is bound to `RightMouseButton`. Published GVAS
parsers do not work on this build; UE 5.4+ replaced the property tag with a
recursive type name plus a flags byte.

`safety` closed a hole the ingest lane's own fixtures had exposed: base64
defeated the PII guard completely. It also stopped the guards skipping binaries
by suffix. Merging the two was the real test - each was green alone and only the
merge could show whether the new scanner could see into the fixtures. It can,
and they are clean.

## Traps found the expensive way, all now written down

- **The hygiene guards were blind to every uncommitted file.** They walked
  `git ls-files`, which lists tracked paths only, so a new file was unscanned
  until after it was committed - the exact moment the guard stops mattering. Two
  separate agents hit this in one day.
- **A same-length mutation inside one mtime tick leaves a stale `.pyc`.** Python
  reuses the old bytecode, which can fake a GREEN under mutation and therefore
  fake a non-vacuity proof outright. Clear `__pycache__` before every mutation
  run. This one undermines the technique the whole project relies on.
- **`pytest -q` on top of `pytest.ini`'s own `-q` becomes `-qq`**, which
  suppresses the summary line. A wait-loop grepping for "N passed" could never
  match and spun to its timeout.
- **`git check-ignore -v` prints the matching pattern even for a NEGATION.**
  Treating "any output" as "blocked" reads a carve-out as a refusal.
- **Some settings never touch local storage.** `InvertCameraYAxis` exists in the
  log and in no save file at all, so a settings reader built on `.sav` alone is
  silently incomplete.

## Where it stands

Suite green. The primary checkout was byte-identical throughout both lane runs.
ROADMAP item 0 (redactor P0) closed, item 2 (GVAS) closed, item 4's parser
closed. Item 1's remainder needs a real matchmade raid, which needs the operator
to enter one - everything measured so far is the Prologue at `matchId=0`.

---

# Session 2026-08-09 - project inception

The first session. Lanternlight went from "does a companion tool for this game
even make sense" to a scaffolded public repo with a measured foundation, in one
sitting. Nothing was built on an assumption that was not probed first, and two
of the session's conclusions reversed earlier conclusions from the same session.

## Starting point

Precedent was `C:\RedMoon` (Red Moon, V Rising) - an established architecture
with a live-state half and a static-extraction half. The question was whether
that architecture transfers to Mistfall Hunter (Steam appid 3282300, UE5, 41.6
GB, buildid `24619162`, client version string `0.2.0.0` on the title screen).

The answer is no, in both halves, and the reason had to be measured before
anything could be designed. That measurement is `docs/FINDINGS.md`.

## The feasibility probe and its negative results

Three findings, all of them blockers, all of them permanent.

**Kernel anti-cheat.** The Steam store page discloses "Uses Kernel Level
Anti-Cheat", named Bellring Anti-Cheat, behind a third-party EULA gate. The
shipped binary set corroborates it heavily - `gpHackerProc.dll` at 5.7 MB,
`gpShell.dll`, `sscronet.dll`, plus a full publisher SDK stack under
`GSDK_US\Steam\` (`gsdk.dll`, `parfait.dll`, `bmf_hydra.dll`), GSDK version
string `3.23.0.0`, package `com.hermes.pstgame`, app_id `937566`, and an
embedded CEF browser.

This kills the entire RedMoon live-state half permanently: no injected plugin,
no process memory read, no packet capture, no swapchain-hooked overlay, no
synthetic input into the game window. The stake is a ban on the operator's real
account, and several of those are plainly outside the EULA. This became
ADR-001 and it is the defining constraint of the whole project.

**All paks encrypted.** `MistfallHunter\Content\Paks` holds `global.utoc` /
`global.ucas` plus 15 chunks. Headers were read directly - 144 bytes per file,
read-only, no process touched, script now at `scratchpad/probe_paks.py`. Every
content chunk carries `flags=Compressed|Encrypted|Indexed`; 101,500 entries
across all TOCs; every legacy `.pak` sidecar reports `pakver=12
encrypted_index=True`. `keyguid=ZERO` means one global AES key, not per-chunk
named keys, and that key is not on disk in plaintext. Recovering it means either
dumping it from the running process (forbidden by the above) or statically
reverse-engineering a binary shipping with kernel anti-cheat. Neither is
acceptable. This became ADR-002.

**No loose game data.** A sweep of the whole 41.6 GB install for `*.ini *.json
*.csv *.uasset *.cfg` returned exactly three files: a zero-byte
`StagedBuild_MistfallHunter.ini`, and two GSDK config files next to the
anti-cheat binaries. None of them game data. RedMoon's extractor half is dead
too.

At this point the honest read was that there might be no project here at all.

## The post-launch sweep that reversed them

The pre-launch sweep of `%LOCALAPPDATA%` found nothing, and that negative was
nearly recorded as final. It was wrong for a boring reason: **the game had never
been run on this machine, so it had not yet written its Saved tree.**

The operator launched the game at 08:18. A second read-only sweep found
`%LOCALAPPDATA%\MistfallHunter\Saved\` created 08:18:56, containing:

| Artifact | Size | Value |
|---|---|---|
| `Logs\MistfallHunter.log` | 567 KB after 10 min, live-appending | the primary surface |
| `SaveGames\*.sav` (4) | 2-2.7 KB each | plain UE GVAS, magic `47 56 41 53`, NOT encrypted |
| `Config\Windows\GameUserSettings.ini` | 1398 B | settings only |
| `Config\Windows\Engine.ini` | 7228 B | plugin roster only |
| `AvgPrice_937566.ini` | 37 B | market / trade-price cache, currently empty |

The log turned out to be rich: map and sublevel transitions with ms timestamps,
`match state changed to <state>`, a `match id` field, `setClassGender inclassid
==NN`, weapon config ids via `OnRep_WeaponCfgId`, equipment asset paths,
`seasonId`, server region, gateway hostname, `roleLimit:3`. Categories are
namespaced (`LogStk`, `TS.Avatar`, `TS.Dungeon`, `TS.Camp`, `TS.Inventory`,
`TS.Network`, `Puerts`). The GVAS saves parse with any GVAS reader.

**Process lesson worth keeping: the negative was a measurement of the wrong
world state, not of the game.** The sweep was correct and its conclusion was
false. Anything probed before the game had ever run needs re-probing after.

Two boundaries were set at the same time and both hold. `GSDKCache\
accountList.json`, `user.json`, `user_infos.json` and `gsdk_app_log.db` sit
under the install dir beside the anti-cheat binaries - they were **listed, never
opened**, and are treated as out of bounds. And the registry sweep was capped at
depth 2 and found nothing, which is recorded as non-exhaustive rather than as a
clean negative.

The log also carries the operator's SteamID64, Steam persona, GSDK openID and
userId, an EOS ProductUserId, and an IP-resolved city, state and country. On a
public repo that is not a style concern. It became ADR-004: a tested redactor
gates every fixture, and it sits between any capture and any committable
artifact - not at review time, and not as a habit.

## Class research and the Blackarrow decision

Two independent research agents ran, one per class, and were adjudicated by a
merger that graded neither its own output nor allowed either agent to grade its
own. Written up in `docs/CLASS_RESEARCH.md`.

The player profile weighted against: League mains Tristana and Vayne - ranged
sustained auto-attack DPS, spacing and kiting, target selection, high mechanical
ceiling, historically vulnerable to being collapsed on. New to extraction games.

**One cross-agent conflict, resolved on specificity.** The Shadowstrix agent
reported from Steam store copy that every class carries two stances. The
Blackarrow agent found an official launch announcement saying the Blackarrow's
new weapon launches in a future season. The store copy is generic marketing; the
specific official statement wins. Blackarrow is bow-only at launch, and its
"Archer" and "Hunter" are ammo and playstyle families on one weapon, not two
stances.

Substance on each: Blackarrow was nerfed 2026-08-06 (impact effect removed from
uncharged shots, fully charged impact slightly reduced) after being officially
acknowledged as overperforming in solo - so any tier list stamped only "August
2026" is probably pre-nerf and cannot be placed. Its speed stat is Charging
Speed, not attack speed. Effective heavy-shot range is roughly two dodge-lengths
per player testimony, absent from every guide site - it is not a sniper. It is
gear-hungry and dies to gap-closers in tight terrain. Shadowstrix has two real
stances, stealth is Dagger-only, Element of Surprise makes a backstab out of
stealth an automatic crit, it is the squishiest class in the game, and it is
**untouched by every patch since launch** - which is why it tops the post-nerf
tier lists and also why it is the likeliest next nerf target.

**Operator decision: Blackarrow now, Shadowstrix committed for slot 2 at
approximately hour 20, slot 3 left free.** The log shows `roleLimit:3` so slots
are not scarce. Blackarrow is the direct transfer of the existing skillset, and
its failure mode is one the player already understands from the other side of
it. Taking Shadowstrix first would put the squishiest body in the game, with a
one-opener-one-escape kit, into an unfamiliar extraction loop where a lost fight
also loses the kit. The timing asymmetry was recorded honestly: building a main
around an untouched outlier eleven days after launch is building on sand.

Purpose is "both" - this is the real main account, and Lanternlight harvests
whatever the log yields rather than the class being picked as an instrument.

Consequence for Emberforge, and it is a design constraint not a note:
**two-class coverage is scheduled rather than accidental, so the data model must
not hard-code a single class shape.**

The most load-bearing thing both agents agreed on: **no cooldown numbers, damage
coefficients or stealth durations are published anywhere as of 2026-08-09**, and
any site quoting one is fabricating. That is exactly the gap the engine exists to
fill. Also agreed: gems replaced random gear affix rolls, so mid-game power comes
from sockets; and the launch-window wiki farms cross-copy each other verbatim, so
**agreement among them is not corroboration** - one invented an SS tier nobody
else uses, another invented an August 5 nerf that does not exist.

## The pixel-to-log id join

The best piece of method from the session, and the reason `docs/OBSERVED_IDS.md`
is a first-party table rather than a wiki transcription.

The log emits `setClassGender inclassid ==NN` with a UTC timestamp and **never a
class name string**. So the ids alone are meaningless. A passive desktop poller
captured the screen every 3 seconds with local-time filenames; local is UTC-5,
so the two streams join on wall clock. Reading the class name off the ROLE panel
in the frame closing each dwell window gives name-to-id directly. No process
access, no OCR guesswork - the name is rendered text read off a screenshot.

Result, complete and ascending, matching the in-game sidebar order top to
bottom: **10 Mercenary, 11 Sorcerer, 12 Blackarrow, 13 Shadowstrix, 14 Seer, 15
Withered Knight.** Class 12 is doubly established - pixel-joined and
operator-attested, because the committed character logged `classId 12`. Class 15
is the weakest row: established by elimination plus sidebar order, because its
ROLE panel was never captured.

**The wrinkle that made the join trustworthy rather than lucky:** the ROLE
description panel lags the selection by about one frame while the left sidebar
highlight leads it. In the frame at the instant class 13 is set, the panel still
reads Blackarrow (12) and the sidebar has already moved to Shadowstrix. Both
halves agree with the log from opposite directions. Read the panel for the
outgoing class and the sidebar for the incoming one.

The same method yielded weapon config ids from `server_refreshKnightFeature:
<actor> class-NN holding-NNNNN`. Four classes show two ids, two show one.
Because the pair counts line up with the published weapon kits (Mercenary hammer
plus sword-and-shield, Shadowstrix dagger plus dual blades), **pairs are the two
weapon stances, and the gender-variant hypothesis is refuted** - gender variants
would apply uniformly across all six classes, and they do not. Blackarrow's
single id independently corroborates the official future-season statement, which
is worth more than the statement alone because it was measured here.

Three things left open on purpose:

- **Sorcerer also shows a single id and the official line does not account for
  it.** Nothing anywhere may say "Blackarrow is the only single-weapon class"
  until this is settled.
- **The stance-toggle probe produced no distinguishable event.** Step 4 of the
  capture plan - hold on one class, cycle the toggle, watch `holding-` - simply
  did not fire. The pair evidence comes from the carousel instead, which is
  weaker for the stance question specifically. Re-run deliberately.
- The id space is **not** class-ordered (Withered Knight sits at 304xx with
  Mercenary while the middle four sit at 305xx), and creation previews use
  5-digit ids (`30504`) while the live character uses 7-digit (`3010401`).
  Different id spaces. Do not join them without evidence, and do not infer class
  from an id range.

## Also settled this session

Licensing and posture: Apache-2.0, public from the first commit, copyright
Moonbeam 2026, with a Bellring Games / Skystone Games non-affiliation notice and
a no-redistributed-assets statement that is trivially true because nothing is
extractable anyway. That became ADR-006.

Names: the project is **Lanternlight**, the math engine is **Emberforge**. Repo
at `github.com/Remus3/Lanternlight`. Reserved local ports, none built: dashboard
8810, log-tail service 8811, Emberforge 8813.

The overall shape is the inverse of RedMoon: Emberforge plus a build planner is
roughly 90 percent of the project and live state is close to zero. The hard
problem is not extraction, it is **provenance** - proving where every number came
from and refusing to emit one that has no source.

---

## Next session starts here

1. **Read `docs/FINDINGS.md` and `docs/OBSERVED_IDS.md` first.** They are the
   source of truth. Nothing else in the repo outranks them, and where a
   recollection disagrees with them, they win.
2. **Do the raid recon pass (ROADMAP item 1).** It is the top item and the only
   one that can invalidate the design of the others. Loot, extraction events,
   match results and death states are unmeasured, not absent. Run one raid to a
   successful extraction and one to a death, with the frame poller running and
   the wall-clock of entry noted.
3. **Fold in the two cheap open questions while the game is open** - the Sorcerer
   second-weapon check (ROADMAP 5) and a deliberate stance-toggle re-run (ROADMAP
   6). Both need the client and neither deserves its own session.
4. **Every id observed gets written into `docs/OBSERVED_IDS.md` at the moment it
   is observed, with the method named.** An id learned from a wiki six weeks
   later is not the same fact.
5. **Nothing gets committed until it has been through the redactor**, including
   anything captured in step 2. The log carries a SteamID64, a persona, SDK and
   EOS ids, and an IP-resolved location.
6. Do not open anything under `GSDKCache\`. Listed, never opened, stays that way.
