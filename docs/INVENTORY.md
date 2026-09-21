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
| `pre-commit` | (1) Staging a path that looks like game-derived PII - `frames/`, `captures/`/`screenshots/`, `logs/`, anything under a `Saved` tree or matching `*MistfallHunter*`, `*.sav`/`*.log` and their encoded/compressed derivatives (`*.sav.b64`, `*.log.gz`, etc.), except reviewed fixtures under `tests/fixtures/`. (2) Non-ASCII bytes in a staged authored text file (`*.py`, `*.md`, `*.toml`, `*.ini`, `*.txt`, `*.sh`, `*.yml`/`*.yaml`, `.githooks/*`) - checks the staged blob via `git show`, not the working-tree copy. (3) A staged `.md` whose content diverges from the working tree, or whose doc-guard selector (`ops/docguards.py`) cannot show the tests that read it were actually run against this tree, or whose selected tests fail. (4) A staged `.py` whose commit-ADDED lines carry a new ruff finding (via `tools/precommit_gate.py lint-staged`) - pre-existing findings elsewhere in the file do not block. (5) A staged file of any type whose staged blob carries a provider-credential shape (via `tools/precommit_gate.py secrets-staged`, `OPS-103`) - reported as class, count and path, never the value. |
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
| `tests/test_secret_scan.py` | A provider CREDENTIAL reaching a commit (`OPS-103`): an Anthropic key including the admin family, an OpenAI key, an AWS key id, a GitHub token or fine-grained PAT, a Google API key, a Slack token, a bearer token, a JWT, a private-key header, or an assigned secret literal. Every class carries an invented positive and a near-miss negative assembled at run time, so the module never carries a matching literal; the full tracked tree must scan to ZERO findings, which is the measured false-positive rate; the report is class, count and path and never any fragment of a value; and a staged synthetic key is proved to block a REAL commit through `.githooks/pre-commit` in a throwaway repository, with HEAD asserted unchanged. |
| `tests/test_secret_scan_outside.py` | The one control whose population is OUTSIDE this repository (`OPS-103`) going dark: `ops/outside_scan.py` scanning the top level of the Git for Windows install root and the system temp directory for credential-class and PII-class content. It runs the DECLARED `SessionStart` command out of `.claude/settings.json` as a real process, asserts a default root outside the repository, pins attribution by project marker and by blob identity with this repository's objects, proves remediation rewrites only attributed files in place and deletes nothing, and refuses to report clean when its own self-test is broken. |
| `tests/test_syntax_check_hook.py` | The post-edit syntax-check hook (`tools/syntax_check_hook.py`) failing to report a broken `.py` file, or wedging the session it runs in. |
| `tests/test_docguards.py` | The doc-guard selector (`ops/docguards.py`) failing to pick every test module that reads a staged Markdown file's content, or the coverage cross-check missing a module the selector did not pick. |
| `tests/test_doc_size_budget.py` | A tracked document growing past its size budget unnoticed. |
| `tests/test_source_register.py` | A module-ish token named in `docs/ECOSYSTEM.md` prose that is not actually registered as a source. |
| `tests/test_no_empty_orphan_dirs.py` | An EMPTY untracked, unignored directory anywhere in the tree - the class the 2026-09-19 machine stray-work sweep found two of. The point is not that they are harmful while empty; it is that **git does not report empty directories**, so `git status --ignored --porcelain`, `git status --untracked-files=all <path>` and an `os.walk` for files are all blind to them, and `git check-ignore -v` answers only about `.gitignore`. Measured here and recorded in the module docstring: `git ls-files --others --exclude-standard --directory` reported `.backtest/` and NOT the nested `.claude/worktrees/`, while the same command without `--exclude-standard` reported both - so the enumeration is `--others --directory` with `.gitignore` applied per path afterwards, rather than a flag whose behaviour differs between a top-level and a nested empty directory. The stake was `.claude/worktrees/`: `.claude/` is deliberately TRACKED here, so the first file a session wrote into it would have been an untracked orphan with no owning lane and a whole worktree one `git add -A` from publication in a PUBLIC repo. Scoped to EMPTY directories on purpose - failing on a directory of brand-new unstaged work is the false red that gets a guard deleted. Also pins the two orphans by name, asserts the `.gitignore` rule keeps its reason, asserts the probe-from-root paragraph in `docs/OPERATIONS.md` on a whitespace-collapsed copy, and proves the detection is not vacuous against a scratch repository that does have one. `OPS-96`. |
| `tests/test_gitignore_shadowing.py` | An IGNORE RULE that matches an ALREADY TRACKED path. Git keeps honouring the tracked entry, so nothing breaks and nothing warns - but an untracked sibling added beside it in the same directory is silently refused by `git add`, and the refusal looks like the file simply not mattering. Asks `git check-ignore --no-index`, which is the flag that makes git answer about a tracked path at all. Scope is whatever GIT honours, not the root `.gitignore` alone - a nested `.gitignore`, `.git/info/exclude` and a global `core.excludesFile` are all in, so the answer is MACHINE-CONFIG DEPENDENT and can differ between two clones of the same commit; the failure message names the source file and line, which is what makes that survivable. A NEGATED match is not a defect, it is a deliberate carve-out, and the sibling question is asked only of a tracked path that was already MATCHED - the case it catches is a negation NARROWER than the rule it rescues from, where the tracked file looks fine and its sibling is silently refused. `OPS-75`. |
| `tests/test_no_environ_mapping_assertions.py` | The environment mapping being reachable inside an `assert` by ANY route, in either half of the statement. This module has been WRONG TWICE about why, and the history is in its docstring because the shape of the mistake outlives the rule. First answer: the membership form is dangerous and `.get()` is safe - measured, `.get()` leaks too. Second answer: the axis is whether the MAPPING OBJECT reaches an operand, so a subscript or a `.get` receiver is safe - that produced a SAFE LIST and an adversarial pass defeated the module three times through entries on it (`.keys()`, an alias, a bound name). The MEASURED answer is about the OPERATOR, not the operand: pytest emits an `E + where` chain for some comparisons and not others, and when it does it reprs every sub-expression including the mapping, twice. Probed per form in its own pytest process, two sentinels placed at the TAIL of the insertion-ordered environment because `saferepr` elides the middle: `.get(ABSENT) == x` LEAKS while `.get(PRESENT) == x` is clean, so the same line is safe or unsafe depending on what is in the environment at run time. A rule that changes with runtime state is not a rule, so there is NO SAFE LIST - the only permitted shape binds the value out first and asserts on a local, which is clean STRUCTURALLY rather than by luck. 21 leaking specimens including alias chains, `from os import environ as e`, `getattr(os, "environ")`, `os.__dict__["environ"]` and the message half; 4 permitted shapes; an arm asserting no per-occurrence exemption helper has come back. Four live sites were found and rewritten. Blind to `unittest` assert methods, which are calls rather than `assert` statements and were measured to leak WORSE - this tree contains no `unittest.TestCase`, so the hole is unreachable here and is documented for a reader who is not us. |
| `tests/test_tmp_retention.py` | This suite leaving a PASSING test's `tmp_path` on the operator's disk. A session overlooking the machine reported a scheduled sweep deleting pytest run directories older than TWO DAYS and matching nothing on every run; re-measured here 2026-09-20 by walking the shared temp root, the oldest of 46 run directories was 1.22 days old, so a two-day cutoff removes ZERO of 46 - the sweep was correct in its own terms and never had a candidate. The same walk counted 266,336 files where the relayed figure was 192,202, already stale by ~74,000, two of this session's own suite runs included. The relayed diagnosis needed one correction that moves where the fix belongs: that base was said to be accumulating since 2026-04-22, and nothing in it is older than about 29 hours - the DIRECTORY dates from April, its CONTENTS do not. It is churn produced faster than any cutoff in days can match, so the suite is the only place it is fixable. Pins `tmp_path_retention_policy = failed` and `tmp_path_retention_count = 3` in `pytest.ini`: measured on the same 88 tests into isolated base directories, `all` left 589 files and 401 dirs against 175 and 236 for `failed`. `failed` keeps a FAILING test's directory because that is the evidence someone will want. The count equals the stock default and is pinned so a future pytest cannot quietly change what this repository leaves on disk. The load-bearing arm asks the LIVE `pytestconfig` rather than the file text, because an ini key the tool does not honour would sit there looking correct; proved not vacuous by flipping the policy to `all` and watching both the text arm and the live arm go red. The sweep script and the `pytest-substrate-*` bases belong to other trees and are reported on the channel, never edited. |
| `tests/test_capture_evidence_notice.py` | This repository asserting a measurement in PUBLIC whose evidence no longer exists, without saying so. `C:/ll-captures` was permanently deleted 2026-09-20 - 10.6 GB in 19,241 files, not to the Recycle Bin, no shadow copy, operator-confirmed unrecoverable. An enumeration over both separator spellings and a whitespace-collapsed copy of every file found 267 references in 32 files, 132 of them CITED EVIDENCE, with 86 of the 267 in the split archives - a live-half-only search would have been wrong by a third. The citations are deliberately NOT stripped: deleting them would destroy the record of how the readings were taken, which is the one thing still recoverable. Instead `docs/AFFIXES.md`, `docs/FINDINGS.md` and `docs/OBSERVED_IDS.md` carry a notice at the top and this guard keeps it honest. It fails in BOTH directions, and the second is the point: if the tree ever returns, the notice becomes a false claim that good evidence is missing, so it fails then too. Arms check the marker is in the HEAD of each document rather than buried, appears exactly once, dates the loss, and says it is unrecoverable so nobody hunts for a restore. `OPS-104`. |
| `tests/test_vendored_inventory_is_declared.py` | `CLAUDE.md` naming a different set of vendored works than `third_party/` actually holds, in either direction. The second vendoring exception in that file names the instances it covers, and after `third_party/rc_channel/` was vendored on 2026-09-20 the sentence still read "the one instance" for a day. The cost was measured rather than imagined: an analysis pass read it, saw four sibling projects correctly reporting the vendored `CHANNEL.md` in this tree, and concluded the siblings were fabricating - the document was stale and the world was right. Asks the FILESYSTEM for the directories under `third_party/` and the DOCUMENT for the `third_party/<name>/` paths its prose mentions, storing neither a count nor a list, for the reason `tests/test_source_register.py` gives one level down. A trailing slash is required so a sentence about the rule - `ruff.toml` excluding `third_party/` - does not read as a declaration, and an empty-population arm stops both directions going vacuously green if the tree is emptied. |
| `tests/test_no_hardcoded_home_path.py` | A live, user-facing surface hardcoding this machine's home directory or account name, which would silently never run (or run wrong) on a different account or a fresh clone. |
| `tests/test_ports.py` | A port named anywhere in the project falling outside its declared block (see Port block below). |
| `tests/test_process_capability.py` | An in-scope module reaching for a capability no human vetted - a library other than `kernel32`, a Win32 entry point outside the four allowed, an `os` attribute or an import that is not on the list, a subprocess whose `argv[0]` is not `sys.executable`, or `os.kill` with any signal but a literal `0`. In scope means every published non-test `.py` whose parsed source names a process-handle API (see `PROCESS_HANDLE_APIS`), derived from the tree rather than typed out - the hand-written roster missed `ops/lane_slot.py` on the day it landed, and a widened access mask went undetected. Two stated limits, because the guard's own docstring insists on them: it reads SOURCE and runs nothing, which is now HALF the guard - see `tests/test_process_capability_at_runtime.py` for the half that runs the code and watches the audit events, added 2026-09-20 because three of four recorded defeats leave this module green, and the discovery list is a denylist of API NAMES, which the runtime module replaces with a POSITIVE scope derived from the tracked listing, so a handle acquired through a spelling nobody listed is not refused, only unexamined. It is the mechanical backstop for the hard boundary against touching the game process, and it is necessary rather than sufficient. |
| `tests/test_repo_surfaces.py` | Regressions in the public-facing surfaces added 2026-09-06 (see `OPS-40`). |
| `tests/test_ops_ids.py` | An `OPS-` id naming more than one item, or the "next free id" question becoming unanswerable. Since `OPS-57` split the two continuity documents, "the documents" includes their archives: an id whose only mention went out with the archived ledger tail would otherwise read as FREE, which is the `OPS-12` bug with a new way in. |
| `tests/test_doc_archive.py` | `tools/doc_archive.py` losing a word while splitting `ROADMAP.md` or `docs/LEDGER.md` into their archives (`OPS-57`). The load-bearing property is CONSERVATION - every moved section present verbatim in the archive - and the ledger cut being a contiguous TAIL, which is how the append-only rule survives a reorganisation. |
| `tests/test_hook_command_roots.py` | An absolute repository root in `.claude/settings.json` - in a hook command (`OPS-61`) or, since `OPS-70`, in a permission rule under `permissions.allow`, `permissions.deny`, `permissions.ask` or `permissions.additionalDirectories`. The two are different defects and the module treats them as such. A hook script resolves its repo root from its own file location, so an absolute hook command makes a clone's or a worktree's hook FIRE, SUCCEED and answer about the original tree - measured, it also WROTE that tree's records. An absolute permission rule is believed to merely fail to match in any other tree, so the session prompts where it would not have: a nuisance, not a wrong answer. That second half rests on how the permission matcher is understood to anchor a rule, which the guard's own docstring marks as INFERRED from documentation and client source and NOT observed on this machine - settling it needs a session in default permission mode in a clone at a different path. The guard is `tools/hook_command_guard.py`. |
| `tests/test_probe_paks.py` | `tools/probe_paks.py` reading a command line it cannot understand as a pass, or printing a report that does not name the directory it read (`OPS-67`). The second is the one the old code lacked: output carried the container name only, so a report of the wrong scope was unfalsifiable. |
| `tests/test_archive_link_guard.py` | An item archived out of `ROADMAP.md` becoming unreachable from it (`OPS-57` criterion 6). Checks both directions: an archived heading with no stub, and a stub whose anchor resolves to no heading. Reports DID NOT RUN, distinctly from a pass, when the archive is absent - a file that exists and is unreferenced is the invisible-work failure this project's continuity design exists to prevent. |
| `tests/test_apply_doc_split.py` | `scripts/apply_doc_split.py` writing a split that does not reproduce its source (`OPS-80`). The load-bearing assertions are refusals: a plan mutated by one character, a reflowed kept section, an edited ledger entry, a modified ledger head and a duplicated entry must each be REFUSED with nothing written. It also pins the atomic write and its LF line endings, and asserts that `CLAUDE.md` still names the applying step - criterion 4, the half that stops the trap recurring. |
| `tests/test_merge_gate.py` | `ops/merge_gate.py` itself failing to catch a claimed-but-missing file, a claimed-but-empty file, or a collected-test-count drop (repo-wide or per-file). |
| `tests/test_handoff.py` | `ops/handoff.py` writing a hand-off it should have refused, or refusing one without leaving the file untouched. The refusal half is the load-bearing one, so the assertions are about the FILE - absent on a fresh target, byte-unchanged by SHA-256 where a previous hand-off exists - never merely that an exception was raised. It also pins the two rules that keep the gate from being disarmed: the detectors come from `lanternlight.redact` and not from a private copy, and there is no exemption list and no override argument (a test reads the signature and refuses `force`, `allow`, `skip_checks`, `exempt`, `ignore`). One test points the checker at the LIVE `LL-NEXT-SESSION.txt`, because a guard aimed only at fixtures is a guard about fixtures. |
| `tests/test_stop_audit.py` | `ops/stop_audit.py` failing to refute a closing claim it covers - a numeric suite result whose outcomes do not sum to what `pytest --collect-only` reports for the tree as it stands, or a file the session says it wrote that is missing or empty. It also pins the three properties that keep the auditor from being decoration: it returns 0 on every path (exit 2 on `Stop` refuses to let the session end), it reads main-agent turns only (`isSidechain` records belong to the merge gate), and it redacts every snippet before writing one. Two stated limits, both in the module's own docstring: it cannot tell a claim from a QUOTATION of one, so discussing a wrong number reads as making it, and the shapes in `NOT_CHECKED` are not checked at all. |
| `tests/test_spawn_no_window.py` | A subprocess spawn in `lanternlight/redact.py`, `tools/precommit_gate.py` or `ops/stop_audit.py` losing its `creationflags` keyword and flashing a Windows console window again. On Windows a console-subsystem CHILD of a windowless parent - a `pythonw` process, or a hook running under the Claude desktop harness - flashes a window unless the spawn carries `CREATE_NO_WINDOW`, and `tools/precommit_gate.py` runs as a `PreToolUse` hook so every git and ruff process it spawned flashed one on every tool call. The call sites are DERIVED from the AST and never counted here, because a filed count goes stale the moment a spawn is added and becomes a confident lie; a new spawn without the flag turns the module red instead of slipping under a number that still matches. It also refuses `creationflags=0`, which would satisfy a presence check while restoring the flash, asserts each module defines its own `_NO_WINDOW` rather than importing one (the redaction module stays dependency-free), and imports each module to confirm the constant EVALUATES to the platform's value rather than merely being written. Two stated limits: `ops/loop/watch.py`'s `Popen` and the rest of `ops/` are deliberately NOT covered, so an empty result here is a claim about three files only; and the guard reads source, so it cannot prove no window appeared - that was measured by sibling project RC with a positive control on 2026-09-15. |
| `tests/test_lanes.py` | The lane roster's invariants - disjoint file ownership between lanes, no orphaned tracked file, no file claimed by two lanes. |
| `tests/test_no_inbox_in_git.py` | A path under `moon_sync_inbox/` - the cross-project mail directory, including our own outgoing copies under its `_outbox/` - becoming tracked by git (`OPS-35` criterion 1). Those files are other projects' source, carry no license statement, and this repository is public and Apache-2.0, so one reaching a commit is a licensing failure that a push makes very hard to undo. The asserted property is that no tracked path RESOLVES inside the directory, asked of the git index rather than inferred from `.gitignore`, because `git add -f` overrides an ignore rule and a future edit can drop the line. The ignore rule is checked as well, by a separately named test, so losing it and gaining a tracked file are two distinguishable failures. Its stated limits: it reads one repository state - the current index - so it says nothing about history, other branches or stashes; and a directory junction is listed as unexamined rather than covered. |
| `tests/test_inbox_watch_subdirs.py` | The cross-project mail watcher (`ops/inbox_watch.py`) reporting only top-level `moon_sync_inbox/*.md` and missing a subdirectory drop - the `OPS-34` defect. |
| `tests/test_inventory.py` | THIS document going stale in either direction: naming a path that no longer exists, carrying an operator identifier, or falling behind the repository so that a file its stated scope covers is named nowhere. It also enforces the two-tables sentence below, and the sentence saying so - which is why it appears in this table rather than only in its own prose. It was itself the file missing from both tables on 2026-09-08, so a guard listed nowhere was checking a completeness claim that excluded it. |
| `tests/test_false_red_probe.py` | `tools/false_red_probe.py` losing its ability to tell the three outcomes of `OPS-74` apart - a clean skip, a false red, and a test that passed in BOTH directions while the guarded code never ran. It also pins the three properties that keep the probe from being decoration: the positive control must be planted outside the tree and torn down, a control the probe failed to see makes the whole report UNPROVEN rather than green, and `PATH` stripping happens BY VALUE so the interpreter's own directory survives. Nothing here runs the real suite; the runner is injected and every other part of the probe is a pure function over recorded pytest output. |
| `tests/test_vendored_write_tracer.py` | The Apache-2.0 obligations that came with `third_party/lw_write_tracer/` going unmet, and the vendored work drifting from the work that was licensed - `OPS-84`. Integrity is asserted in the form that survives this repository's line-ending policy: the vendored file is read, CRLF is restored, and the result must hash to the digest Legion Wallpaper PUBLISHED. Pinning the on-disk digest instead would bind the test to `.gitattributes` rather than to the licensed content, and a hash of a working file is not a hash of the commit. A second arm compares the two forms directly against the original drop, so the digest is not trusted to have been computed over the right bytes; it SKIPS when the drop is gone, because `moon_sync_inbox/` is gitignored live mail and a fresh clone has no copy. The attribution arms fail on a missing NOTICE, a missing license name, a missing upstream, or a missing statement of changes, because Apache-2.0 section 4(b) makes silence a breach rather than a style choice. The last arms run the plugin end to end through a real pytest subprocess and require its own positive control PROVED, its negative specimen clean, and the interpreter restored - vendoring a file that does not load would be a licensing exercise only. |
| `tests/test_vendored_channel_md.py` | The Apache-2.0 obligations that came with `third_party/rc_channel/` going unmet, and the vendored work drifting from the work that was licensed - `OPS-91`. It pins ONE digest where the write tracer's guard pins two, and the difference is measured rather than stylistic: that file arrived CRLF against a repository that stores LF, so its working-file hash and its git blob hash are different facts; this one arrived LF with zero CRLF pairs and zero non-ASCII bytes, so disk, blob and what Amberstone published are the same 20633 bytes. The line-ending arm is deliberately SEPARATE from the digest arm, so a text-mode copy on Windows reports as a line-ending rewrite rather than as an unexplained mismatch. The attribution arms fail on a missing NOTICE, a missing upstream, a missing license name, a missing commit or a missing statement of changes, and one further arm fails if the NOTICE ever names a `sha256` this module does not pin - a NOTICE quoting one hash while the guard pins another reads as two records corroborating each other when it is one record contradicting itself. |
| `tests/test_channel_contract.py` | The seven portable assertions over the vendored channel document going unchecked here - `OPS-91` criterion 4. They are written as OUR OWN module on the stdlib rather than vendored, because Amberstone states its gate module hard-imports RC-only tooling that no sibling has, so a copy would not run in this tree at all. They grade the DOCUMENT - its digest, its declared `CHANNEL_VERSION`, its undated headings, its named paths and its filename-grammar table - and are deliberately not conflated with the six-clause fleet contract inside that document, which grades a WATCHER. Arm 6 is the one to read before trusting the set: Amberstone's literal wording, that every repo-relative path in the file resolves, is FALSE here BY DESIGN, because this project relocated the document under `third_party/` and never vendored the charter it cites. That arm therefore pins the path SET and a recorded disposition per member, and says in its own text that the resolving half carries no independent evidence. |
| `tests/test_process_capability_at_runtime.py` | THE HARD BOUNDARY going unguarded against a name assembled at RUN TIME. Its sibling module reads SOURCE and concludes what the code will do; this one runs the code under `sys.addaudithook` and watches what it DOES, which is a different kind of claim rather than a stronger version of the same one. The measurement that makes it work, and that a future reader must not simplify away: `ctypes.dlsym` fires with the REAL symbol name after assembly, so `"Open" + "Process"` is a `BinOp` in the text and `OpenProcess` in the event; `ctypes.call_function` carries the folded ACCESS MASK, so a right computed at run time is still readable; and `os.kill` carries the signal as a VALUE. Its SCOPE is POSITIVE - every published module outside `tests/` is in by default and leaves only by importing nothing that can reach native code, or by a written exclusion with a reason that a test reddens on when it goes stale. The previous scope was a DENYLIST of module names, which is why a module importing `ctypes` had never been examined by any severity-1 guard at all. Three of the four recorded defeat sketches leave every static arm GREEN and redden this one. |
| `tests/test_caveman_dialect_record.py` | The DECLINE of the charter's caveman-wiring clause quietly becoming an adoption - `OPS-36` criterion 4(a). The dialect itself is defined in `CLAUDE.md`; the WIRING was refused on three grounds this repository already holds - unlicensed sibling source into a PUBLIC Apache-2.0 tree, an absolute repository root that `tools/hook_command_guard.py` forbids under `OPS-61`, and a second home for a rule `CLAUDE.md` already carries. A decline recorded only in prose is a decline that becomes an adoption the first time nobody re-reads it, so the record in `docs/OPERATIONS.md` is pinned: this module fails if the section is deleted, if the sentence saying the `CLAUDE.md` definition GOVERNS is weakened, if the word DECLINED softens, if the clauses are split across two sections, or if the dialect line leaves `CLAUDE.md`. |
| `tests/test_spawn_capability_at_runtime.py` | THE HARD BOUNDARY going unguarded on the SPAWN tier - `OPS-101`. Every other severity-1 guard reasons about NATIVE reach, and a subprocess needs no `ctypes` at all to reach a process: `taskkill /F /PID`, `wmic`, or a shelled `Stop-Process`. The events were MEASURED before anything was built on them, and two of the measurements contradict the shape the item's own acceptance criterion assumed: `subprocess.Popen` fires with `(executable, command_line, cwd, env)` where the first argument is `None` for an ordinary list call and the second is a single STRING because `list2cmdline` has already run - a guard indexing it as a vector reads one character - and **`shutil.which` raises no event at all**, so no runtime arm can watch it and the static tier is the only answer there. `multiprocessing` does not raise `subprocess.Popen` either, and `_winapi.CreateProcess` delivers its command line as a single control character, usable only as a creation counter. Assembly IS carried: `"task" + "kill"` appears as the literal in the command line, which is the property the static tier cannot have. The our-child line is a REGISTRY rather than kinship - the probe starts a sleeper before installing the hook and records its pid, and a control with identical source and flags differing only in the pid is refused against the probe's own pid and permitted against the sleeper, which really dies. Six things it cannot distinguish - pid reuse, image-name targets, pids computed inside the spawned program, grandchildren, and anything after creation - are written into a constant and asserted, because a limit that is not pinned drifts into a claim. |
| `tests/test_sibling_inbox_choke_point.py` | A note reaching a sibling inbox WITHOUT passing `ops.outbox.deliver` - the path that keeps a local copy and a manifest row BEFORE attempting delivery and refuses a payload carrying an operator identifier. `LL-0170` is the instance: a session quoted raw `git` output into four sibling directories, the redactor was never consulted because the string came from `git` rather than from a log parser, and no commit-time guard fired because the channel is gitignored. It asserts at RUN TIME, in a subprocess with fake inboxes under `tmp_path`, that the local record is written BEFORE any sibling write - the ORDER read off the event stream rather than from what exists afterwards - and that a refused note produces ZERO write events. What it cannot see is stated in its own docstring and is the honest limit: any run it does not make, and anything written outside this repository's Python, which is what `LL-0170` actually was. |
| `tests/test_toolguard.py` | The shared external-tool presence guard (`tests/_toolguard.py`) going one-directional or going silent - `OPS-78`. Three properties are pinned and each fails differently: a skip reason that no longer names the tool, which breaks the count that the end-of-run statement is built from; `require` returning something the caller cannot run, which would leave the present direction unpinned exactly as `docs/OPERATIONS.md` forbids; and the end-of-run statement failing to appear when a tool-absence skip happened, or appearing when none did. The last pair is checked by spawning a real `python -m pytest` over a generated file rather than by calling the formatter, because a formatter returning the right strings does not prove pytest ever calls it. Registration is asserted against pytest's own plugin manager, on the function object, so a conftest that imported a different function of the same name would still fail. |
| `tests/test_refutation_census.py` | The `OPS-87` refutation census going stale in the one direction that matters - a classified event outliving the ledger sentence it classifies. Every row in `docs/refutation_census.tsv` carries a verbatim quote as its anchor, and this module re-resolves all of them against `docs/LEDGER.md` and its archive at run time, so an edited or deleted sentence turns the classification red instead of leaving it reading as current. It also pins the parts of `ops/refutation_census.py` that would otherwise fail silently: a malformed row is refused with its line number rather than padded, an empty quote is refused because an empty anchor resolves against any text at all, anchor matching is case-sensitive and unnormalised, a tie for the largest bucket names every tied bucket rather than letting sort order answer the question, and the window is derived from the ledger's own dated headings so the format template's `YYYY-MM-DD` example is not counted as a session. Its stated limit, repeated in the report the tool prints: it cannot tell whether a bucket letter is the RIGHT letter, only that a human assigned one against a sentence that still exists. |
| `tests/test_preflight.py` | `ops/preflight.py` becoming a second suite, or a runner that quietly runs fewer checks than it names - `OPS-87`. Four properties are pinned and each fails differently: a module named in the set but absent from the tree is a failure rather than a skipped line, the set must stay under half the suite because the whole point is cost, the stated runtime must be the MEASUREMENT and not a constant (two different measurements must print two different numbers), and the report must say what it does NOT cover, because 60 of 135 census events were real defects no program here reaches. The untracked-file arm is pinned against real repositories in a temporary directory in all four states: untracked, staged, ignored, and not a repository at all. |
| `tests/test_suite_recorder.py` | The live suite-run recorder (`ops/suite_recorder.py`) miscounting what a cycle costs - `OPS-87` criterion 4. The load-bearing field is whether a run was a FULL suite or a filtered one, because an instrument that counts a three-second single-module run as a suite run makes the AFTER number look wonderful for a reason that is false, so eight narrowing switches are pinned one by one and the backstop is that every test module on disk was really entered. It also pins the two halves of fail-soft separately: the recorder RAISES and is driven directly, while the swallowing wrapper in `tests/conftest.py` is tested once with a spy that raises a private exception type and records that it was called - a raising spy is vacuous under a bare except, because an assertion error is an exception too. Stated limits, all in the module's own docstring: a deselect or an early exit that removes individual tests while leaving every module entered can still read as full, an option this repository has not listed has its value misread as a target path (which errs toward FILTERED on purpose), and a fast run cannot be told from a warm cache. |
| `tests/test_preflight_backtest.py` | `tools/preflight_backtest.py` crediting itself with a catch it did not earn - `OPS-87` criterion 3. A tree where the guard did not yet exist must classify NO-GUARD and never CAUGHT, a nonzero exit with no parsed failure is UNBUILDABLE rather than a catch, and the failing test names are carried out of the run rather than counted, so relatedness can be checked instead of assumed. It also pins the reconstruction helper that rebuilds the mid-session state, including the basename half of the match - a module named without its directory in a generated contract would otherwise leave the tree half-registered and the guard green for a reason the experiment did not intend. |
| `tests/test_cycle_cost.py` | `ops/cycle_cost.py` reporting a FLOOR as a count, or printing a caveat it did not derive - `OPS-87` criterion 4, the historical half. The suite-run figure is reconstructed from full-suite results QUOTED in commit messages, ledger entries and the hand-off, which can only ever be a lower bound, so the guards pin that a module-sized figure is not a suite run, that a collect-only figure is never counted as one, and that the threshold is a parameter rather than a fact. The report arms rewrite a row and require the printed total to MOVE, because the defect this module was written after was a caveat printed from string literals (`LL-0241`). Two over-counts its own first run produced are pinned as regressions: a ledger entry MOVED by the `OPS-57` split is not evidence the commit that moved it ran the suite, and one anchored pair shared by four cycles is one refutation sentence and not four. |

## Tools (`tools/`)

Standalone scripts. Two of them are wired as harness hooks, two are commit-time
gates, and the rest are run by hand.

| Tool | Purpose |
|---|---|
| `tools/archive_link_guard.py` | Proves every item archived out of `ROADMAP.md` is still reachable from it, in both directions (`OPS-57`). |
| `tools/ascii_check.py` | PostToolUse hook - warns the moment an Edit or Write lands a non-ASCII byte. Defence in depth under the pre-commit gate, which is the authoritative one. |
| `tools/preflight_backtest.py` | Stands the tree up as it was when a historical finding was filed and runs `ops/preflight.py` there, so criterion 3 of `OPS-87` is answered by measurement rather than by assertion. Two modes, because the first one returned a number that was an instrument defect: the parent-commit mode found 0 of 17, since a new module and its registration land in ONE commit and the state where the registration was missing was never committed at all; the reconstruction mode rebuilds that state from the fix commit's own additions and found 9 of 9. Four outcomes rather than two - CAUGHT, MISSED, NO-GUARD for a check that postdates the finding, and UNBUILDABLE for an experiment that did not happen. Worktrees are stood up OUTSIDE the repository, because one under the repo root shows up in every tracked-file walker in the suite. |
| `tools/false_red_probe.py` | Runs the suite twice - once normally, once with every `PATH` entry carrying a `git` executable removed by value - and reports the delta BY TEST ID AND BY FILE (`OPS-74`). It separates a clean skip from a false red from a test that passed both ways without the guarded code ever running, the last being measured by instrumenting the presence lookup and the subprocess entry points during the run rather than read off a summary line. It plants a deliberate false-red site of its own outside this tree, runs that positive control every time, tears it down again, and reports UNPROVEN - neither green nor red - when the control was not seen. An UNPROVEN run now STOPS at the control stanza and prints no counts, kinds, findings or per-file deltas at all, and the control is recognised in the second node-id shape as well - the one a rootdir inside the system temp tree produces, where the id loses its file segment entirely and reads as `::test_control_false_red` (`OPS-86`). The module docstring states what the third-outcome detector cannot prove: a candidate is not a conviction, and spellings it does not wrap - the `system` and `popen` helpers in the `os` module, or an import-time lookup - are invisible to it. |
| `tools/doc_archive.py` | Splits `ROADMAP.md` and `docs/LEDGER.md` into their archives without losing a word. Re-run it when a size budget fires; do not raise the number. |
| `tools/doc_size_budget.py` | Reports a watched document that has reached its byte budget, and the live-plus-archive PAIR budgets (`OPS-62`). Budgets are git BLOB bytes, not on-disk bytes. |
| `tools/frame_poller.py` | Passive desktop frame poller - timestamped PNGs of the operator's own display. Reads pixels only; no process access, no hooking, no input. |
| `tools/hook_command_guard.py` | Refuses an absolute repository root in `.claude/settings.json`, in two places under two different grammars. In a HOOK COMMAND (`OPS-61`) it reports three spellings - drive root, UNC root, POSIX root. In a PERMISSION RULE under `permissions.allow`/`deny`/`ask`/`additionalDirectories` (`OPS-70`) it splits `Tool(content)` and scans only the content, and looks for just two spellings, because the grammars disagree about a single leading slash: in a hook command a single leading slash is an absolute POSIX path and a defect, while in a permission rule it anchors at the settings source and is the portable form the fix recommends, so reusing the hook patterns there would report the recommended fix as the defect. A short list of permission rules is pinned BY EXACT STRING as operator-approved primary-checkout-only, and the cost of pinning by value is stated in the module rather than left implicit. The module's account of how the permission matcher anchors a rule is marked INFERRED rather than measured, in the docstring and in the finding text a reader is handed when the guard fires, so the two cannot drift apart. A scan of nothing is not a pass: a parse failure, and a settings file declaring no hook command at all, are distinct findings rather than silence. |
| `tools/precommit_gate.py` | The commit-time gate - a ruff finding on a line the commit ADDED, and the forbidden-cmdlet check, which since `OPS-22` matches COMMAND POSITION rather than any mention of the name. Since `OPS-103` it also runs the credential scan over the staged set (`secrets-staged`). |
| `tools/secret_scan.py` | Provider-credential detector (`OPS-103`). Reports class, line, count and path only - its finding type has no field that could carry a value. Separate from `lanternlight/redact.py` on purpose: a credential is a different class from an operator identifier. |
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
| `scripts/apply_doc_split.py` | APPLIES the `OPS-57` split of `ROADMAP.md` and `docs/LEDGER.md` into their archives - the step `tools/doc_archive.py` deliberately does not perform, since that module is a library of pure text-to-text functions that writes nothing. Re-derives every conservation property against the source text before any write, writes atomically with LF line endings, reads the documents back off disk and verifies again, and writes nothing at all without `--apply`. This is what `CLAUDE.md` names when a size budget fires; do not raise the number instead (`OPS-80`). |

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
| `tests/test_loop_lane.py` | `ops/loop/lane.py`, the session-scoped lane governor that arms `ops/lane_slot.py`. No test in it may write into the real machine-wide bucket, and a named test proves the isolation fixture actually moved the default root. |
| `tests/test_loop_ledger.py` | `ops/loop/ledger.py`, the only sanctioned writer of `docs/LEDGER.md`. |
| `tests/test_loop_state.py` | The on-disk loop state - an atomic write, and a load that never raises. |
| `tests/test_loop_watch.py` | The loop's session-watcher supervisor, so arming the watcher is not left to human memory. |
| `tests/test_outbox.py` | An outgoing note leaving a traceable copy in THIS tree (`OPS-43`). |
| `tests/test_overlay_anchors.py` | The nine overlay anchor positions, asserted as exact arithmetic rather than as inequalities. |
| `tests/test_overlay_render.py` | The overlay panel's no-reflow property - a missing value must not shift every row below it. |
| `tests/test_paths_avgprice.py` | The AvgPrice path resolution defect, measured against a live install. |
| `tests/test_precommit_gate.py` | The commit gate blocking even when it cannot say why (`OPS-15`). |
| `tests/test_responder.py` | The draft-only responder runner (`OPS-68`) - that it cannot reach a delivery path, that no draft carries a number absent from the note it answers, and that a human's edit is never overwritten. |
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
| `tests/_toolguard.py` | The repository's ONE external-tool presence guard (`OPS-78`), shared by every test module that shells out to `git`. `require("<tool>")` returns the tool's resolved absolute path or skips the test with a machine-readable reason naming it; returning the PATH rather than a boolean is what forces a call site to pin the present direction as well as the absent one. It also carries the `pytest_terminal_summary` hook that states, at the end of a run, how many tests were skipped and for which tool - re-exported by `tests/conftest.py`, which is what registers it with pytest. Silent when no such skip happened, because a line that always prints is a line nobody reads. Pinned by `tests/test_toolguard.py`. |
| `tests/_tracked.py` | The repository's ONE file walker, shared by `tests/test_ascii_hygiene.py`, `tests/test_no_pii.py` and `tests/test_inventory.py`, and pinned by `tests/test_tracked_walker.py`. It asks git what is tracked rather than guessing from extensions, includes untracked-but-not-ignored files so a guard does not go blind on a brand-new file, and falls back to a filesystem walk where git is unavailable. |
| `tests/conftest.py` | The pytest session hooks. Its main job is the doc-open recorder for `OPS-31`: a `sys.addaudithook` hook that records which test module really opened which tracked document, as a second and independent derivation of what `ops/docguards.py` computes statically. It writes its map only after a COMPLETE unfiltered run, under the gitignored `ops/runtime/`, and it never raises - which is why `tests/test_docguards.py` has to prove it is not decoration. Since `OPS-87` it also carries the thin fail-soft hooks that drive the suite-run recorder in `ops/suite_recorder.py`; every decision those hooks report is made in that module, which raises, so the swallow here hides nothing a test cannot reach. |

## Measurement write-ups (named beyond the declared scope)

The six sets named at the top of this document govern the COMPLETENESS check -
what must be named here or the guard fails. The single row below is an ADDITION
beyond that scope rather than a widening of it, and `docs/` as a whole stays out
for the reason already given. It is named because the document it points at was
written for readers outside this repository as much as inside it, and a sibling
project reading this inventory has no other way to discover that this project
publishes a measured figure for what its own review cycles cost.

| Document | What it records |
|---|---|
| `docs/CYCLE_COST.md` | What one refute-fix-refute cycle costs this repository in full-suite runs and wall clock - `OPS-87` criterion 4. It carries both halves and keeps them apart: a BEFORE half reconstructed from git history and from full-suite results QUOTED in ledger prose, whose run count is a floor and is written `>=` everywhere it appears, and an AFTER half counted from the records `ops/suite_recorder.py` writes for every pytest session, whose run count is exact. It states in its own voice that the two are not a ratio, what the cycle boundary is and what that boundary cannot distinguish - in particular that the record directory is shared between concurrent sessions, so a record proves some session in this tree ran a suite rather than that a particular cycle did. Re-derive every number in it with `python -m ops.cycle_cost`; none of them is filed here or there as a constant. |

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

