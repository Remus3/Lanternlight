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

`tests/test_inventory.py` is the backstop: every path this document names must
exist on disk, and the file itself must carry no account-name-shaped string.

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
| `tests/test_ops_ids.py` | An `OPS-` id naming more than one item, or the "next free id" question becoming unanswerable. |
| `tests/test_merge_gate.py` | `ops/merge_gate.py` itself failing to catch a claimed-but-missing file, a claimed-but-empty file, or a collected-test-count drop (repo-wide or per-file). |
| `tests/test_stop_audit.py` | `ops/stop_audit.py` failing to refute a closing claim it covers - a numeric suite result whose outcomes do not sum to what `pytest --collect-only` reports for the tree as it stands, or a file the session says it wrote that is missing or empty. It also pins the three properties that keep the auditor from being decoration: it returns 0 on every path (exit 2 on `Stop` refuses to let the session end), it reads main-agent turns only (`isSidechain` records belong to the merge gate), and it redacts every snippet before writing one. Two stated limits, both in the module's own docstring: it cannot tell a claim from a QUOTATION of one, so discussing a wrong number reads as making it, and the shapes in `NOT_CHECKED` are not checked at all. |
| `tests/test_lanes.py` | The lane roster's invariants - disjoint file ownership between lanes, no orphaned tracked file, no file claimed by two lanes. |
| `tests/test_inbox_watch_subdirs.py` | The cross-project mail watcher (`ops/inbox_watch.py`) reporting only top-level `moon_sync_inbox/*.md` and missing a subdirectory drop - the `OPS-34` defect. |

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

