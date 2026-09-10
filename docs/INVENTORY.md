# Lanternlight inventory

Generated for the cross-project inventory exchange the operator authorised in
chat 2026-09-07 (`OPS-42` question 2, `ROADMAP.md`): "yes - and both ways ;
infer and use what can be used and insight or use as is after ensuring it
applies to your repo for file locations." This document is Lanternlight's
outbound half. The inbound half - what was read from sibling notes under
`moon_sync_inbox/` and what this project did with each item - is recorded in
`ROADMAP.md` under `OPS-42` question 2, not here.

**No stale counts.** This file names no test count as a number, because a
number written here rots the moment a test is added or removed. Every count
is given as a command to run instead. **No operator PII.** No account name, no
path carrying a username, no SteamID, no persona, no email. Every path below
is repo-relative or a placeholder.

`tests/test_inventory.py` is the backstop, and since `OPS-69` it runs in BOTH
directions. Forward: every path this document names must exist on disk, and
the file itself must carry no account-name-shaped string. Reverse: every file
this document's scope covers must be named here, so an inventory that has
quietly fallen behind the repository fails instead of reading as complete.

**The scope is stated, not implied.** It is exactly these six sets: every
`.claude/commands/*.md`, every `.claude/agents/*.md`, every `.githooks/*`,
every `tools/*.py`, every `tests/*.py`, and every `scripts/*.py` that this
repository would publish. Re-derive the list yourself - it is a command, never
a filed total:

```
git ls-files '.claude/commands/*.md' '.claude/agents/*.md' '.githooks/*' 'tools/*.py' 'tests/*.py' 'scripts/*.py'
```

and check it against this document with `python -m pytest tests/test_inventory.py`.

**What is deliberately OUT of scope, named rather than merely omitted**,
because an unmentioned directory is indistinguishable from an overlooked one:
`lanternlight/` (the library source), `ops/` (the continuity and orchestration
machinery), `docs/` itself, and `tests/fixtures/` - including the fixture
builder that lives there, which is an input to a test rather than a surface a
sibling project would look for. The six sets above are matched one directory
deep, so anything nested below them is out too. These are the repository's
harness and its test surface; a reader who wants the library should read
`docs/ARCHITECTURE.md`.

The `tests/` and `scripts/` sets were widened on 2026-09-10, from
`tests/test_*.py` and from nothing at all. The reason is recorded in
`tests/test_inventory.py` beside the scope constant: the narrower reading left
`tests/_tracked.py` - the shared walker the completeness check itself runs on -
and `tests/conftest.py` uninventoried, and left `scripts/` covered only by the
accident that the Git hooks section below happens to quote one of its two
files while nothing named the other.

## Commands (`.claude/commands/`)

This project defines no separate `.claude/skills/` directory. The eleven
files below are this repo's own slash commands; the harness that runs them
also surfaces them in a skills listing under the same names.

| Command | Purpose |
|---|---|
| `continue.md` | Resume Lanternlight from disk - read state, pick the next item, start work, ask nothing. |
| `done.md` | Wrap the session - full suite, commit, push, ledger the item, sync docs, print the next-session prompt. |
| `loop.md` | Start the unattended loop - self-continuing cycles, guarded against a second instance. |
| `lane-capture.md` | Capture and vision lane - passive screen capture and the frame-to-log wall-clock join. Never synthesises input. |
| `lane-emberforge.md` | Emberforge math engine lane - build and combat math. May not encode an unmeasured number. |
| `lane-ingest.md` | Data ingest lane - every reader of a surface the game writes: log parser/tail, GVAS save reader, market cache, path resolution. |
| `lane-ops.md` | Continuity and orchestration lane - the loop, lane machinery, merge gate, roadmap, ledger, wakeup notes, headless contract. |
| `lane-research.md` | Research and provenance lane - the measured record and class reference. Writes no code. |
| `lane-safety.md` | Safety and hygiene lane - redaction and every repository hygiene guard. |
| `lane-surface.md` | Operator-facing surface lane - the always-on-top window and any dashboard. An ordinary window, never an overlay. |
| `lane-verify.md` | Out-of-domain verification lane - independently REFUTE other lanes' done-claims. Owns no files on purpose. |

## Agents (`.claude/agents/`)

| Agent | Purpose |
|---|---|
| `uiux.md` | UI/UX work on any rendered surface. Runs a mandatory 5-phase audit (STRUCTURE / TYPOGRAPHY / HIT-TARGETS-READABILITY / ASCII / HIERARCHY) before a UI change can be called done. |
| `verifier.md` | Read-only ground-truth verification - independently re-runs the suite from a clean state, confirms cited files exist, tries to REFUTE an implementing agent's claims. |

## Git hooks (`.githooks/`)

Wired via `core.hooksPath`, which is local config and is never cloned. A
fresh clone must run `python scripts/install_hooks.py` before either hook is
active - see `README.md` fresh-clone instructions. Both hooks are tracked at
index mode `100755` (verified 2026-09-07 with `git ls-files -s .githooks/`),
guarded against silent regression to `100644` by `tests/test_hook_file_mode.py`.

| Hook | Refuses |
|---|---|
| `pre-commit` | (1) Staging a path that looks like game-derived PII - `frames/`, `captures/`/`screenshots/`, `logs/`, anything under a `Saved` tree or matching `*MistfallHunter*`, `*.sav`/`*.log` and their encoded/compressed derivatives (`*.sav.b64`, `*.log.gz`, etc.), except reviewed fixtures under `tests/fixtures/`. (2) Non-ASCII bytes in a staged authored text file (`*.py`, `*.md`, `*.toml`, `*.ini`, `*.txt`, `*.sh`, `*.yml`/`*.yaml`, `.githooks/*`) - checks the staged blob via `git show`, not the working-tree copy. (3) A staged `.md` whose content diverges from the working tree, or whose doc-guard selector (`ops/docguards.py`) cannot show the tests that read it were actually run against this tree, or whose selected tests fail. (4) A staged `.py` whose commit-ADDED lines carry a new ruff finding (via `tools/precommit_gate.py lint-staged`) - pre-existing findings elsewhere in the file do not block. |
| `commit-msg` | A commit message containing an em-dash, en-dash, or smart quote (UTF-8 or the CP1252 single-byte form of the same glyphs), per the repo's 7-bit-ASCII authoring rule. Does not touch a `Co-Authored-By` trailer either way. |

Both hooks are shell (`sh`), print a `BLOCKED`/`REFUSED` reason to stderr, and
exit non-zero to refuse the commit. Neither hook has a documented bypass.

## Guards (tests enforcing an invariant, not just a feature)

"Guard" here means a test module whose job is to catch a specific class of
regression, as distinct from a test module that specifies a feature's
behaviour. No collected count is recorded below, for the reason given under
Test count - re-derive one per file with
`python -m pytest --collect-only tests/<file>` and read the last line.

| Guard | Defect class it catches |
|---|---|
| `tests/test_no_pii.py` | Any of the operator's identifiers (SteamID64, persona, GSDK/EOS ids, IP-derived location) reaching a tracked or about-to-be-tracked file. |
| `tests/test_ascii_hygiene.py` | Non-7-bit-ASCII bytes (em-dash, en-dash, smart quotes, non-breaking space) in any authored text file the repo would publish. |
| `tests/test_tracked_walker.py` | The two guards above going blind on a brand-new file that exists on disk but has not yet been `git add`-ed - their shared walker used to enumerate only `git ls-files` output. Fixed and pinned 2026-08-09. |
| `tests/test_hook_file_mode.py` | A tracked `.githooks/*` file losing its executable bit in the git index, which makes a POSIX clone's hook silently stop firing with no warning, no non-zero exit, no log line. |
| `tests/test_precommit_gate_lint.py` | The commit-time lint gate (`tools/precommit_gate.py lint-staged`) firing on lines a commit did not add, or failing to fire on lines it did. |
| `tests/test_syntax_check_hook.py` | The post-edit syntax-check hook (`tools/syntax_check_hook.py`) failing to report a broken `.py` file, or wedging the session it runs in. |
| `tests/test_docguards.py` | The doc-guard selector (`ops/docguards.py`) failing to pick every test module that reads a staged Markdown file's content, or the coverage cross-check missing a module the selector did not pick. |
| `tests/test_doc_size_budget.py` | A tracked document growing past its size budget unnoticed. |
| `tests/test_source_register.py` | A module-ish token named in `docs/ECOSYSTEM.md` prose that is not actually registered as a source. |
| `tests/test_no_hardcoded_home_path.py` | A live, user-facing surface hardcoding this machine's home directory or account name, which would silently never run (or run wrong) on a different account or a fresh clone. |
| `tests/test_ports.py` | A port named anywhere in the project falling outside its declared block (see Port block below). |
| `tests/test_process_capability.py` | An in-scope module reaching for a capability no human vetted - a library other than `kernel32`, a Win32 entry point outside the four allowed, an `os` attribute or an import that is not on the list, a subprocess whose `argv[0]` is not `sys.executable`, or `os.kill` with any signal but a literal `0`. In scope means every published non-test `.py` whose parsed source names a process-handle API (see `PROCESS_HANDLE_APIS`), derived from the tree rather than typed out - the hand-written roster missed `ops/lane_slot.py` on the day it landed, and a widened access mask went undetected. Two stated limits, because the guard's own docstring insists on them: it reads SOURCE and runs nothing, and the discovery list is a denylist of API NAMES, so a handle acquired through a spelling nobody listed is not refused, only unexamined. It is the mechanical backstop for the hard boundary against touching the game process, and it is necessary rather than sufficient. |
| `tests/test_repo_surfaces.py` | Regressions in the public-facing surfaces added 2026-09-06 (see `OPS-40`). |
| `tests/test_ops_ids.py` | An `OPS-` id naming more than one item, or the "next free id" question becoming unanswerable. Since `OPS-57` split the two continuity documents, "the documents" includes their archives: an id whose only mention went out with the archived ledger tail would otherwise read as FREE, which is the `OPS-12` bug with a new way in. |
| `tests/test_doc_archive.py` | `tools/doc_archive.py` losing a word while splitting `ROADMAP.md` or `docs/LEDGER.md` into their archives (`OPS-57`). The load-bearing property is CONSERVATION - every moved section present verbatim in the archive - and the ledger cut being a contiguous TAIL, which is how the append-only rule survives a reorganisation. |
| `tests/test_hook_command_roots.py` | An absolute repository root in `.claude/settings.json` - in a hook command (`OPS-61`) or, since `OPS-70`, in a permission rule under `permissions.allow`, `permissions.deny`, `permissions.ask` or `permissions.additionalDirectories`. The two are different defects and the module treats them as such. A hook script resolves its repo root from its own file location, so an absolute hook command makes a clone's or a worktree's hook FIRE, SUCCEED and answer about the original tree - measured, it also WROTE that tree's records. An absolute permission rule is believed to merely fail to match in any other tree, so the session prompts where it would not have: a nuisance, not a wrong answer. That second half rests on how the permission matcher is understood to anchor a rule, which the guard's own docstring marks as INFERRED from documentation and client source and NOT observed on this machine - settling it needs a session in default permission mode in a clone at a different path. The guard is `tools/hook_command_guard.py`. |
| `tests/test_probe_paks.py` | `tools/probe_paks.py` reading a command line it cannot understand as a pass, or printing a report that does not name the directory it read (`OPS-67`). The second is the one the old code lacked: output carried the container name only, so a report of the wrong scope was unfalsifiable. |
| `tests/test_archive_link_guard.py` | An item archived out of `ROADMAP.md` becoming unreachable from it (`OPS-57` criterion 6). Checks both directions: an archived heading with no stub, and a stub whose anchor resolves to no heading. Reports DID NOT RUN, distinctly from a pass, when the archive is absent - a file that exists and is unreferenced is the invisible-work failure this project's continuity design exists to prevent. |
| `tests/test_merge_gate.py` | `ops/merge_gate.py` itself failing to catch a claimed-but-missing file, a claimed-but-empty file, or a collected-test-count drop (repo-wide or per-file). |
| `tests/test_handoff.py` | `ops/handoff.py` writing a hand-off it should have refused, or refusing one without leaving the file untouched. The refusal half is the load-bearing one, so the assertions are about the FILE - absent on a fresh target, byte-unchanged by SHA-256 where a previous hand-off exists - never merely that an exception was raised. It also pins the two rules that keep the gate from being disarmed: the detectors come from `lanternlight.redact` and not from a private copy, and there is no exemption list and no override argument (a test reads the signature and refuses `force`, `allow`, `skip_checks`, `exempt`, `ignore`). One test points the checker at the LIVE `LL-NEXT-SESSION.txt`, because a guard aimed only at fixtures is a guard about fixtures. |
| `tests/test_stop_audit.py` | `ops/stop_audit.py` failing to refute a closing claim it covers - a numeric suite result whose outcomes do not sum to what `pytest --collect-only` reports for the tree as it stands, or a file the session says it wrote that is missing or empty. It also pins the three properties that keep the auditor from being decoration: it returns 0 on every path (exit 2 on `Stop` refuses to let the session end), it reads main-agent turns only (`isSidechain` records belong to the merge gate), and it redacts every snippet before writing one. Two stated limits, both in the module's own docstring: it cannot tell a claim from a QUOTATION of one, so discussing a wrong number reads as making it, and the shapes in `NOT_CHECKED` are not checked at all. |
| `tests/test_lanes.py` | The lane roster's invariants - disjoint file ownership between lanes, no orphaned tracked file, no file claimed by two lanes. |
| `tests/test_inbox_watch_subdirs.py` | The cross-project mail watcher (`ops/inbox_watch.py`) reporting only top-level `moon_sync_inbox/*.md` and missing a subdirectory drop - the `OPS-34` defect. |
| `tests/test_inventory.py` | THIS document going stale in either direction: naming a path that no longer exists, carrying an operator identifier, or falling behind the repository so that a file its stated scope covers is named nowhere. It also enforces the two-tables sentence below, and the sentence saying so - which is why it appears in this table rather than only in its own prose. It was itself the file missing from both tables on 2026-09-08, so a guard listed nowhere was checking a completeness claim that excluded it. |

## Tools (`tools/`)

Standalone scripts. Two of them are wired as harness hooks, two are commit-time
gates, and the rest are run by hand.

| Tool | Purpose |
|---|---|
| `tools/archive_link_guard.py` | Proves every item archived out of `ROADMAP.md` is still reachable from it, in both directions (`OPS-57`). |
| `tools/ascii_check.py` | PostToolUse hook - warns the moment an Edit or Write lands a non-ASCII byte. Defence in depth under the pre-commit gate, which is the authoritative one. |
| `tools/doc_archive.py` | Splits `ROADMAP.md` and `docs/LEDGER.md` into their archives without losing a word. Re-run it when a size budget fires; do not raise the number. |
| `tools/doc_size_budget.py` | Reports a watched document that has reached its byte budget, and the live-plus-archive PAIR budgets (`OPS-62`). Budgets are git BLOB bytes, not on-disk bytes. |
| `tools/frame_poller.py` | Passive desktop frame poller - timestamped PNGs of the operator's own display. Reads pixels only; no process access, no hooking, no input. |
| `tools/hook_command_guard.py` | Refuses an absolute repository root in `.claude/settings.json`, in two places under two different grammars. In a HOOK COMMAND (`OPS-61`) it reports three spellings - drive root, UNC root, POSIX root. In a PERMISSION RULE under `permissions.allow`/`deny`/`ask`/`additionalDirectories` (`OPS-70`) it splits `Tool(content)` and scans only the content, and looks for just two spellings, because the grammars disagree about a single leading slash: in a hook command a single leading slash is an absolute POSIX path and a defect, while in a permission rule it anchors at the settings source and is the portable form the fix recommends, so reusing the hook patterns there would report the recommended fix as the defect. A short list of permission rules is pinned BY EXACT STRING as operator-approved primary-checkout-only, and the cost of pinning by value is stated in the module rather than left implicit. The module's account of how the permission matcher anchors a rule is marked INFERRED rather than measured, in the docstring and in the finding text a reader is handed when the guard fires, so the two cannot drift apart. A scan of nothing is not a pass: a parse failure, and a settings file declaring no hook command at all, are distinct findings rather than silence. |
| `tools/precommit_gate.py` | The commit-time gate - a ruff finding on a line the commit ADDED, and the forbidden-cmdlet check, which since `OPS-22` matches COMMAND POSITION rather than any mention of the name. |
| `tools/probe_paks.py` | Reports the game's pak chunks and names the directory it read them from (`OPS-67`), so a report of the wrong scope is falsifiable. |
| `tools/syntax_check_hook.py` | PostToolUse hook - reports a `.py` file left syntactically broken by an edit, without wedging the session it runs in. |

## Scripts (`scripts/`)

Run by hand, not by the harness and not by the suite. In scope since
2026-09-10 - the directory used to be excluded outright, which left one of its
two files named only by the accident of being quoted in the Git hooks section
above and the other named nowhere at all.

| Script | Purpose |
|---|---|
| `scripts/install_hooks.py` | Points `core.hooksPath` at the tracked `.githooks/` directory. `core.hooksPath` is LOCAL config and is never cloned, so a fresh clone runs zero hooks until this is run - silently, with `git commit` succeeding as normal. This is the first command a fresh clone runs. |
| `scripts/write_lane_contracts.py` | Regenerates the per-lane contract files from the roster in `ops/lanes.py`. Run it after any roster change; `tests/test_lane_contract.py` fails when the files and the roster disagree, so forgetting is caught by the build rather than by a lane acting on a stale contract. |

## Every other test module

The Guards table above is a CURATED subset: a human decided which modules guard
an invariant rather than specify a feature. This section is the mechanical
remainder, so that no module can be missing from this document merely because
nobody classified it. Between the two tables, every `tests/test_*.py` in the
repository is named, and `tests/test_inventory.py` fails if one is named in
neither.

That last sentence is a claim about the two TABLES, not about the file, and it
is enforced as such. Until 2026-09-10 the guard behind it asked only whether a
module was named ANYWHERE in this document, which is a looser property than
the sentence states - and `tests/test_inventory.py` itself was named three
times in prose, absent from both tables, with the sentence reading as true and
the suite green. Two modules named here are also named in prose elsewhere
(`tests/test_hook_file_mode.py` in the Git hooks section,
`tests/test_ports.py` under Port block); the table check is deliberately blind
to those mentions, so deleting either row is red even though the name survives
in the document.

Modules under `tests/` that are not `test_*.py` are named in Test-support
modules below instead; they are in scope, but they are not what this sentence
is about.

| Module | What it covers |
|---|---|
| `tests/test_armwatch.py` | The one entry point that arms a session's save watcher, so arming stops being something a human has to remember. |
| `tests/test_avgprice.py` | The market cache reader, against a byte-for-byte fixture of the file the game writes. |
| `tests/test_damage.py` | The per-hit damage series reader and the clock trap sitting underneath it. |
| `tests/test_gvas.py` | The plain-GVAS save reader, against fixtures derived from the game's real save files. |
| `tests/test_gvas_fixtures.py` | A GVAS fixture staying an authored artifact rather than a raw dump of the operator's live save. |
| `tests/test_inbox_acknowledge.py` | Reporting the cross-project inbox never acknowledging it - looking must not consume mail. |
| `tests/test_inbox_entirety.py` | The watcher covering the entirety of the inbox folder, per the operator's ruling of 2026-09-07. |
| `tests/test_inbox_keys.py` | The inbox keys being CONTENT digests, not a size or mtime that an edit can leave unchanged. |
| `tests/test_inbox_live_state.py` | No inbox test writing the operator's live records under `ops/runtime/`, with one named exception. |
| `tests/test_inbox_trigger.py` | The automatic acknowledge trigger tied to the operator's own turn (`OPS-41`). |
| `tests/test_inbox_watch.py` | The cross-project inbox watcher itself (`OPS-33`), driven against synthetic notes and against the real directory. |
| `tests/test_inbox_withdrawals.py` | A note or drop that VANISHES being reported, rather than silently leaving the seen set. |
| `tests/test_lane_contract.py` | The generated lane contracts staying in step with `ops/lanes.py`, which is the fact they restate. |
| `tests/test_lane_launcher.py` | Every lane running in its own working directory - eight lanes sharing one is the unrecoverable failure. |
| `tests/test_lane_slot.py` | The reserved-floor lane governor (`ops/lane_slot.py`), re-implemented from a wire protocol rather than vendored. |
| `tests/test_lane_state.py` | Per-lane on-disk state, and the reason lanes never share one ledger file. |
| `tests/test_logparse.py` | The log parser, against log lines copied byte-for-byte from a real capture. |
| `tests/test_loop_guard.py` | The single-instance loop guard - refuse a second loop, and never terminate anything. |
| `tests/test_loop_ledger.py` | `ops/loop/ledger.py`, the only sanctioned writer of `docs/LEDGER.md`. |
| `tests/test_loop_state.py` | The on-disk loop state - an atomic write, and a load that never raises. |
| `tests/test_loop_watch.py` | The loop's session-watcher supervisor, so arming the watcher is not left to human memory. |
| `tests/test_outbox.py` | An outgoing note leaving a traceable copy in THIS tree (`OPS-43`). |
| `tests/test_overlay_anchors.py` | The nine overlay anchor positions, asserted as exact arithmetic rather than as inequalities. |
| `tests/test_overlay_render.py` | The overlay panel's no-reflow property - a missing value must not shift every row below it. |
| `tests/test_paths_avgprice.py` | The AvgPrice path resolution defect, measured against a live install. |
| `tests/test_precommit_gate.py` | The commit gate blocking even when it cannot say why (`OPS-15`). |
| `tests/test_precommit_hook_globbing.py` | The pre-commit hook not letting the shell rewrite a staged path (`OPS-56`), end to end through a real commit. |
| `tests/test_provenance.py` | Provenance travelling with the ROW and not only with the document (`OPS-28`), because a consumer lifts a table. |
| `tests/test_redact.py` | `lanternlight/redact.py`. Every identifier in it is invented and assembled at run time, never pasted from a log. |
| `tests/test_savewatch.py` | The save-file generation snapshotter, for the save file the game writes transiently. |
| `tests/test_store_drift.py` | The shared-worktree object-store drift detector (`OPS-54`). |
| `tests/test_tail.py` | The live log tailer, against a synthetic appending file - no game, no client, no real log. |
| `tests/test_vision_meter.py` | The meter reader reading a real capture, and refusing when it cannot. |

## Test-support modules (`tests/`, not `test_*.py`)

Neither table above covers these: they collect no tests, so a reader scanning
for `test_*.py` never meets them, and the completeness guard did not either
until the scope was widened on 2026-09-10. Both are load-bearing, and the
first is the sharpest case - `tests/test_inventory.py` performs its own
completeness walk through `tests/_tracked.py`, so this document did not name
the module its own guard runs on.

These two rows are a convenience for a reader, not the thing the guard checks:
outside the two test tables above, "named" means named ANYWHERE in this file,
because a full repo-relative path in backticks is unambiguous wherever it
appears. Measured 2026-09-10 - deleting either row alone leaves the suite
green, since the scope prose near the top names both paths as well. Removing
every mention is what turns it red.

| Module | What it is |
|---|---|
| `tests/_tracked.py` | The repository's ONE file walker, shared by `tests/test_ascii_hygiene.py`, `tests/test_no_pii.py` and `tests/test_inventory.py`, and pinned by `tests/test_tracked_walker.py`. It asks git what is tracked rather than guessing from extensions, includes untracked-but-not-ignored files so a guard does not go blind on a brand-new file, and falls back to a filesystem walk where git is unavailable. |
| `tests/conftest.py` | The pytest session hooks. Its main job is the doc-open recorder for `OPS-31`: a `sys.addaudithook` hook that records which test module really opened which tracked document, as a second and independent derivation of what `ops/docguards.py` computes statically. It writes its map only after a COMPLETE unfiltered run, under the gitignored `ops/runtime/`, and it never raises - which is why `tests/test_docguards.py` has to prove it is not decoration. |

## Test count

**No number is recorded here on purpose** - CLAUDE.md forbids restating a
suite count in a file where it goes stale. Re-derive it yourself:

- Full run, from the repo root, bare (not `-q` - `pytest.ini` already carries
  `-q` in `addopts`, and a second `-q` on the command line stacks to `-qq`,
  which prints no summary line at all and still exits 0):
  ```
  python -m pytest
  ```
  Read the last line of output for the pass/fail/skip counts.
- Collected-count report, matching what `.github/workflows/tests.yml` runs
  before the suite itself:
  ```
  python -m pytest --collect-only 2>&1 | tail -3
  ```
- Per-file collected counts (what `ops/merge_gate.py` parses for its
  per-file baseline gate - the doubled `-q` here is deliberate and gives a
  `path: N` line per file with no grand total, which is what a per-file
  baseline needs):
  ```
  python -m pytest --collect-only -q
  ```

This project's suite runs un-parallelised - no `pytest-xdist` or other
third-party pytest plugin is declared or assumed; `pytest.ini` says so
explicitly, because a plugin option in an ini file is a hard collection
error on a fresh clone that lacks the plugin. `.github/workflows/tests.yml`
carries no `paths-ignore` filter, so every push (including a docs-only one)
runs the full suite.

## Port block

Lanternlight's declared block is **8810-8819** (widened from 8810-8814 by the
operator on 2026-08-27), enforced by `tests/test_ports.py`. Nothing in this
project may bind or name a port outside it.

| Port | Service | State |
|---|---|---|
| 8810 | Dashboard | not built |
| 8811 | Log-tail service | not built |
| 8812 | Vision / OCR service | reserved, not built |
| 8813 | Emberforge engine | library only, no service |
| 8814 | Overlay control channel | reserved, unbound |
| 8815-8819 | unallocated | free |

The machine-wide block registry each sibling project reserves against is
recorded in `CLAUDE.md` rather than duplicated here, to avoid two copies
drifting apart. Knowing a neighbour's block is not permission to talk to it -
the standalone rule in `CLAUDE.md` still holds: no shared code, no shared
ports, no shared keys.

