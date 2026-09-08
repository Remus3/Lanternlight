"""Guard the completeness of the source register in ``docs/ECOSYSTEM.md``.

ROADMAP ``OPS-13``, opened by ledger ``LL-0079``.

WHY THIS EXISTS. The register is the single entry point for "can I cite this,
and for what". It was proven complete on 2026-08-29 by a checker that lived in
a session scratchpad and is now gone, so the completeness claim was true on its
date and had no mechanism to stay true. The next document that cites a new
domain silently makes the register wrong, and the failure is invisible - a
register that omits a source reads exactly like one that covers everything.

THE BUG THIS IS WRITTEN AGAINST, and the reason there is no allowlist below.
The original checker filtered bare domains through a HARDCODED TLD ALLOWLIST
(``com|org|net|gg|io|app|...``). ``.gl`` was not in it, so ``th.gl`` was cited
twice in ``docs/ECOSYSTEM.md`` and was invisible to the check, which reported a
confident "62 of 62, 0 missing" while a cited source was absent. The green
result was a claim about the pattern, not about ``docs/``.

That checker HAD been proven non-vacuous - delete a host, watch it go red,
restore, watch it go green - and the proof was worthless against this bug.
**A guard proven non-vacuous on one input is not a guard proven correct.** So
ask separately what it is blind to, which is why this module says so out loud
below rather than leaving the caveat in a chat log.

HOW IT WORKS. Extract every host-shaped token from every ``*.md`` under
``docs/`` with a TLD-AGNOSTIC pattern, subtract an enumerated denylist of
tokens a human has vetted as not-an-external-source, and require every survivor
to appear in the register section. A leading ``www.`` is normalised away,
because ``www.twitch.tv`` and ``twitch.tv`` are one source and a guard that
reported the first as missing would be crying wolf.

WHAT THIS GUARD IS BLIND TO. Stated here, in the artifact, because a caveat
that lives only in conversation is a lie in the artifact:

* **The denylist is the trusted part.** A real source wrongly added to
  :data:`KNOWN_NON_HOSTS` is hidden from this check exactly the way ``.gl`` was
  hidden by the old allowlist. Review additions to that set, not this logic.
* It checks that a host STRING is present in the register section. It does not
  check that the row next to it says anything true, or that the tier is right.
* It reads ``docs/**/*.md`` only. A source cited from ``README.md``,
  ``ROADMAP.md`` or code is out of scope and unchecked.
* Presence is matched against the lowercased section text. It now requires a
  host BOUNDARY - see :func:`_present_in_register` - so a tail match no longer
  counts. Before `LL-0081` it did, and that was not hypothetical:
  ``grandwiki.com`` was cited standalone and unregistered, and passed on the
  strength of the neighbouring ``mistfallhunter.grandwiki.com`` row.
* Presence still says nothing about CORRECTNESS. A host with a register row is
  accepted whatever that row claims, and a sentence inside the section that
  merely NAMES a host - even one saying it has not been assessed - satisfies
  the check. The guard proves a source was written down, not that it was
  judged.
* IPv4 and IPv6 literals are invisible - :data:`HOST_SHAPED` emits no token for
  them at all, so a source cited by bare address is unchecked and silent.
* Underscores and punycode truncate rather than fail. ``mistfall_hunter.wiki``
  is seen as ``hunter.wiki`` and ``example.xn--p1ai`` as ``example.xn``,
  because the label pattern excludes ``_`` and stops at the first hyphenated
  suffix. The truncated form is what any failure message will name.

REGENERATING THE DENYLIST after a legitimate new non-host token appears - a new
module path quoted in a ledger entry, say - run :func:`cited_hosts` over
``docs/``, subtract the register, and add the genuinely-not-a-source leftovers
here. Do NOT add a token you have not looked at.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
ECOSYSTEM = DOCS / "ECOSYSTEM.md"

#: The register section is delimited by these two headings.
REGISTER_START = "## Source register"
REGISTER_END = "## 1. Item / loot databases"

#: A host-shaped token: one or more dot-separated labels, last label 2-24
#: LETTERS. Deliberately TLD-AGNOSTIC - see the module docstring. Never add a
#: list of permitted final labels here; that is the defect this file exists to
#: stop recurring.
HOST_SHAPED = re.compile(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,24}")

#: Tokens that are host-SHAPED and are not external sources: dotted code
#: identifiers, module paths, filenames, Unreal gameplay tags, version strings,
#: the GSDK package name and the Windows-MCP extension id. Every member was
#: read before it was added. See the module docstring before extending it.
KNOWN_NON_HOSTS = frozenset(
    {
        # MODULE FILENAMES and dotted PYTHON PATHS quoted by `LL-0148` and
        # `LL-0152`. Registered while closing `OPS-31`, and the sequence is
        # the point: the entry recording that closure was itself refused by
        # this guard on the first post-edit run, which is exactly the defect
        # `OPS-31` exists to catch, caught before the commit rather than
        # after the push. `slots.py` is a SIBLING project's module named in
        # an entry about misdirected inbox mail - Lanternlight has no such
        # file, and `git ls-files` matches zero paths for it.
        "conftest.py",
        "docguards.py",
        "slots.py",
        "sys.addaudithook",
        "GateReport.notes",
        # TEST MODULE FILENAMES quoted by `LL-0159`, the entry closing the
        # `OPS-33` follow-up. Each is a file in THIS tree - `git ls-files`
        # matches `tests/test_inbox_acknowledge.py` and its three siblings -
        # and the host-shaped pattern reads the dotted tail as a domain
        # because `.py` is a real TLD, Paraguay's. Looked at before adding,
        # per the regenerating note above: these are our own test modules,
        # not sources. The tokens are the tails the extractor emits, not the
        # full paths, which is what any failure message would name.
        "acknowledge.py",
        "entirety.py",
        "keys.py",
        "withdrawals.py",
        # OUR OWN FILENAMES quoted by `docs/INVENTORY.md` and `ADR-007`,
        # registered while closing `OPS-42` questions 1 and 2. Every one was
        # checked against `git ls-files` before being added here, per the
        # regenerating note above, and each is a tail the extractor emits
        # rather than the full path it came from.
        #
        # Two resolved to zero tracked paths at the moment of checking and are
        # listed anyway, because both are files created in the same uncommitted
        # wave as the documents citing them: `inventory.py` is the tail of
        # `tests/test_inventory.py` and `slot.py` of `ops/lane_slot.py` and
        # `tests/test_lane_slot.py`. A future sweep re-deriving this list will
        # find them tracked.
        #
        # `log.gz` is NOT a file at all. It is the tail of the glob `*.log.gz`
        # inside a sentence describing what the pre-commit hook refuses to
        # stage. It is kept for the same reason as the rest: it is ours, and
        # `.gz` parses as a two-letter TLD.
        #
        # THE COUNT IS THE WARNING. This denylist took four entries in one wave
        # and thirteen in the next, all of them our own filenames, because the
        # register guard reads every dotted token in `docs/` and this project
        # has begun writing documents whose whole job is to list its own files.
        # The right answer is probably not a longer denylist, but changing it
        # is a decision about the guard rather than about these tokens, and the
        # docstring above is explicit that additions are reviewed here and the
        # LOGIC is left alone. Recorded as `OPS-44` rather than acted on.
        # OUR OWN OUTGOING-MAIL MACHINERY, quoted by `docs/REPLY_PATHS.md`,
        # registered while landing `OPS-43`. The hand-off written at the
        # previous wrap predicted this trip - it is the FIFTH - and named the
        # sanctioned move: vet the token, add it here, leave the LOGIC alone
        # because `OPS-44` still holds that decision unmade.
        #
        # Vetted before adding, per the regenerating note above. `outbox.py`
        # and the two dotted paths are `ops/outbox.py` and functions inside it;
        # at the moment of checking `git ls-files` matched zero paths for them
        # because the file was created in the same uncommitted wave as the
        # document citing it, and `git status` shows it as `?? ops/outbox.py`.
        # A future sweep re-deriving this list will find it tracked, the same
        # note already recorded for `inventory.py` and `slot.py`.
        #
        # `DELIVERIES.json` is not source at all: it is the delivery record
        # this project writes under `moon_sync_inbox/_outbox/`, which is
        # gitignored in full and never committed. `.json` is not a TLD, but the
        # host-shaped pattern reads the dotted token anyway.
        "DELIVERIES.json",
        "ops.outbox.deliver",
        "outbox.py",
        "outbox.replies",
        # The SIXTH trip, on `LL-0168` itself - the entry recording the fifth.
        # Same shape as the `OPS-31` sequence noted above: the entry that
        # closes an item is refused by this guard, which is the defect being
        # recorded happening again while it is being written down.
        #
        # `PATHS.md` is the tail of `docs/REPLY_PATHS.md`, which `git ls-files`
        # will match once this wave is committed and `git status` currently
        # shows as untracked. `contract.write` is the tail of
        # `ops.lane_contract.write_all`, `ops.outbox.SIBLING` of
        # `ops.outbox.SIBLING_INBOXES`, and `ops.outbox.backfill` of the
        # function of that name - all three are truncations the host-shaped
        # pattern makes, not names anything in this project actually uses.
        "PATHS.md",
        # A git CONFIG KEY, quoted by `LL-0169` and `OPS-49`. `core.filemode`
        # is not a host and not a file; `.filemode` simply parses as a TLD-
        # shaped tail. Looked at before adding, per the regenerating note.
        #
        # The other two tokens this same run refused - `gmail.com` and
        # `close.benham` - were NOT added here and must never be. They were the
        # operator's own email address, quoted into a ledger entry by mistake,
        # and this guard is the only thing in the tree that noticed. See
        # `LL-0170` and `OPS-50`. Adding a real host to this denylist to make a
        # red run green is how a guard stops working.
        "core.filemode",
        "contract.write",
        "ops.outbox.SIBLING",
        "ops.outbox.backfill",
        "continue.md",
        "inventory.py",
        "lane-capture.md",
        "lane-emberforge.md",
        "lane-ingest.md",
        "lane-research.md",
        "lane-surface.md",
        "lane-verify.md",
        "log.gz",
        "mode.py",
        "slot.py",
        "uiux.md",
        "verifier.md",
        # CAPTURE FILENAMES quoted by `LL-0149`. A frame is stamped
        # `f0566_00.43.29.png` and a fixture `panel_total_1443_hits_28.png`,
        # and the host-shaped pattern reads the dotted tails as domains. An
        # entry that records which frame a committed fixture came from - which
        # is the whole provenance claim - cannot avoid naming it.
        "00.43.29.png",
        "28.png",
        # `ops/runtime/inbox_seen.json`, quoted by `LL-0153`. Truncated to
        # `seen.json` by the host-shaped pattern.
        "seen.json",
        # STANDARD LIBRARY API NAMES, a TEST FILENAME and a SIBLING's file,
        # all quoted by `LL-0154`, and every one of them arrives here
        # TRUNCATED - which is the form the failure message named and
        # therefore the only form that works. `Path.write_text` is seen as
        # `Path.write` and `tests/test_inbox_watch_subdirs.py` as
        # `subdirs.py`. `MANIFEST.sha256`, seen as `MANIFEST.sha`, is a file
        # inside a SIBLING project's drop into our gitignored inbox -
        # Lanternlight has no such file and `git ls-files` matches zero paths
        # for it, exactly as the `slots.py` note above records.
        #
        # This block is the third consecutive cycle in which the ledger entry
        # recording a closure was itself refused by this guard on the first
        # post-edit run. That is `OPS-31` working, not `OPS-31` recurring.
        "Path.iterdir",
        "Path.write",
        "subdirs.py",
        "MANIFEST.sha",
        # MODULE AND TEST FILENAMES quoted by `LL-0156`, every one arriving
        # TRUNCATED at the last label pair: `tools/doc_size_budget.py` as
        # `budget.py`, `tools/syntax_check_hook.py` as `hook.py`,
        # `tests/test_precommit_gate_lint.py` as `lint.py`. `m.py` is the
        # throwaway fixture module from the lint gate's own probe transcript,
        # quoted because the probe's exact output is the evidence.
        "budget.py",
        "hook.py",
        "lint.py",
        "m.py",
        # `tests/test_no_hardcoded_home_path.py`, quoted by `LL-0157`,
        # truncated to `path.py` by the host-shaped pattern.
        "path.py",
        # A standard-library API name quoted by `LL-0157`. The
        # host-shaped pattern reads the dotted call as a domain, the
        # same way it reads `Path.iterdir` above.
        "shutil.which",
        # Quoted by `LL-0158`. `guards.md` is the tail of an ATTACKER-CHOSEN
        # filename the entry has to reproduce, because the injected name IS
        # the finding. `result.groups` is a dotted Python attribute in the
        # render-path condition the same entry quotes.
        "guards.md",
        "result.groups",
        # The host-shaped pattern truncates at the first label pair, so
        # `per_file.values()` is seen as `file.values` - the TRUNCATED form
        # is what the failure message names and therefore what must be here.
        "file.values",
        # Filenames and config KEYS quoted by `LL-0139`, not sources. The
        # host-shaped pattern cannot tell `attribution.commit` from a
        # domain, and a ledger entry that names the file it added should
        # not have to avoid saying its name.
        "CITATION.cff",
        # Dotted PYTHON PATHS quoted by `LL-0141`. The host-shaped pattern
        # truncates at the first label pair, so `guard.pid_is_alive` is seen
        # as `guard.pid` and `watch.ensure_armed` as `watch.ensure` - the
        # TRUNCATED form is what any failure message names, and therefore
        # what has to be listed here.
        "guard.REPO",
        "guard.pid",
        "watch.ensure",
        # Module paths, filenames and an API name quoted by `LL-0140`.
        "pytest.importorskip",
        "surfaces.py",
        "sys.meta",
        "tests.yml",
        # Dotted PYTHON ATTRIBUTES quoted by `LL-0147`, truncated by the
        # host-shaped pattern the same way the `LL-0141` block above records:
        # `lanes.REPO_ROOT` is seen as `lanes.REPO`. Both name attributes of
        # this repo's own modules - `ops/lanes.py` and `merge_gate`'s
        # `SummaryResult` - and neither is a source. `LL-0147` is the entry
        # that FOUND this failure mode, so it reddening the tree by naming its
        # own evidence is the defect demonstrating itself; see `OPS-31`.
        "lanes.REPO",
        "summary.passed",
        "attribution.commit",
        "attribution.pr",
        "config.yml",
        "observation.yml",
        # Filenames and a JS LIBRARY quoted by the `OPS-29` re-survey, none a
        # source. Every one was read in context before being added here.
        #
        # `THREE.js` is the 3D library, named only to identify a
        # confirmed-UNRELATED same-word game the search turned up.
        # `gaBeObJKBcWTfZ.yml` is a GitHub Actions workflow FILENAME inside a
        # surveyed repository, quoted as evidence of a fake-commit-activity
        # job.
        #
        # `helper.py` and `manager.py` are the TRUNCATED forms of
        # `mistfall_helper.py` and `mistfall_build_manager.py`, two source
        # files fetched and read during the licence and ADR-001 gate. The
        # module docstring already warns that `_` is excluded from a label so
        # an underscored name truncates at the last dotted pair - these are
        # that behaviour, and the truncated form is what the failure names
        # and therefore what has to be listed.
        "THREE.js",
        "gaBeObJKBcWTfZ.yml",
        "helper.py",
        "manager.py",
        # Dotted CODE IDENTIFIERS and FILENAMES quoted by `LL-0142` through
        # `LL-0145`, none a source. This is the FOURTH time this guard has
        # fired on a ledger entry naming the things the entry is about, which
        # is the guard working: an entry that closed a defect in
        # `merge_gate` and shipped a provenance emitter cannot describe
        # either without writing their dotted names down.
        #
        # `LoopState.item` is a dataclass field, `build.buildid` a JSON field
        # path inside the emitted record, `proc.returncode` a subprocess
        # attribute, and `pytest.cacheprovider.json.dumps` the truncated form
        # of `_pytest.cacheprovider.json.dumps` - truncated because a label
        # excludes the leading `_`. `provenance.py` and `provenance.json` are
        # this repo's own new files.
        "LoopState.item",
        "build.buildid",
        "proc.returncode",
        "provenance.json",
        "provenance.py",
        "pytest.cacheprovider.json.dumps",
        "00.42.52.png",
        "10.png",
        "19.02.51.472.png",
        "19.02.52.028.png",
        "19.18.28.701.png",
        "19.32.34.jpg",
        "32.34.jpg",
        "3282300.acf",
        "937566.ini",
        "ADR-001-no-game-process-interaction.md",
        "ADR-002-no-asset-extraction.md",
        "ADR-003-log-is-primary-surface.md",
        "ADR-004-redaction-is-mandatory.md",
        "ADR-005-omit-rather-than-guess.md",
        "ADR-006-apache-2-and-public.md",
        "ADR-007-lane-slot-root-is-ours.md",
        "AFFIXES.md",
        "ARCHITECTURE.md",
        "AvgPrice.ini",
        "BACKLOG.md",
        "BotData.TreasurableItems",
        "CLASSES.md",
        "CLAUDE.md",
        "Deck.sav",
        "ECOSYSTEM.md",
        "Engine.ini",
        "EnhancedInput.EnhancedPlayerMappableKe",
        "EnhancedInputUserSettings.sav",
        "FINDINGS.md",
        "FTE.Event.ChangeWeapon",
        "Game.EscapeType.GroveSprite",
        "Game.Net.Online",
        "Game.PlayState",
        "Game.PlayState.Death",
        "Game.PlayState.Escape",
        "Game.PlayState.Gaming",
        "Game.PlayState.Spiritual",
        "Game.PlayState.WaitSpiritual",
        "GameUserSettings.ini",
        "GameplayCue.Damage.BeDamaged",
        "GameplayCue.NumberPops.DamageCrit",
        "GvasSave.epilogue",
        "GvasSave.properties",
        "GvasSave.trailing",
        "GvasSave.undecoded",
        "HEADLESS.md",
        "HH.MM.SS.png",
        "IDS.md",
        "IdGeneratorData.NumIdToUUID",
        "IdGeneratorData.UUIDToNumId",
        "Inventory.equipments",
        "ItemCell.cfgId",
        "KillPlayerHistoryDatas.PlayerName",
        "LEDGER.md",
        "LeaderRankScoreData.KillPlayerCount",
        "LeaderRankScoreData.KillPlayerHistoryDatas",
        "LogLine.raw",
        "LoginOptions.sav",
        "LoopState.from",
        "MANIFEST.txt",
        "MapUrl.target",
        "MistfallHunter-backup-2026.08.26-01.27.09.log",
        "MistfallHunter.exe",
        "MistfallHunter.ini",
        "MistfallHunter.log",
        "NOTES.md",
        "Next.js",
        "Notice.sav",
        "OPERATIONS.md",
        "OVERLAY.md",
        "OverlayWindow.apply",
        "OverlayWindow.current",
        "PROMPT.md",
        "Path.home",
        "Path.replace",
        "PlayerData.Hp",
        "PlayerData.Inventory",
        "PlayerData.Transform",
        "Process.OtherOperationCount",
        "RE.finditer",
        "README.md",
        "RESEARCH.md",
        "ROADMAP.md",
        "SECURITY.md",
        "SEscapePortalSpawner.initialize",
        "SOUL.md",
        "STATE.json",
        "Scav.sav",
        "SaveWatcher.consecutive",
        "Status.Talent",
        "Status.Talent.Scout.Bow.ContinuouseShoot",
        "Status.Talent.Scout.Bow.DrawEnhanced",
        "Status.Talent.Scout.Bow.HomingTarget",
        "TS.AI",
        "TS.Ability",
        "TS.Avatar",
        "TS.Camp",
        "TS.Default",
        "TS.Dungeon",
        "TS.FTE",
        "TS.Inventory",
        "TS.NPC",
        "TS.Network",
        "TS.SDK",
        "TS.Settings",
        "TS.UI",
        "TS.Utils",
        "Talent.Scout.Bow.ContinuouseShoot",
        "Talent.Scout.Bow.DrawEnhanced",
        "Talent.Scout.Bow.HomingTarget",
        "TeamKillMonsterData.Normal",
        "accountList.json",
        "alias.TerminateProcess",
        "anchors.place",
        "anchors.py",
        "ant.dir.cursortouch.windows",
        "armwatch.err",
        "armwatch.json",
        "armwatch.main",
        "armwatch.log",
        "armwatch.py",
        "ast.Attribute",
        "avgprice.py",
        "bottle-0.13.4.data",
        "bytes.splitlines",
        "capability.py",
        "channel.steam",
        "child.pid",
        "check.py",
        "com.hermes.pstgame",
        "config.json",
        "contract.py",
        "contracts.py",
        "core.hooksPath",
        "ctypes.windll",
        "current.item",
        "cycle34.csv",
        "damage.py",
        "dir.mkdir",
        "dataclasses.replace",
        "done.md",
        "filecmp.cmp",
        "fixtures.py",
        "gate.check",
        "gate.py",
        "gate.verify",
        "global.ucas",
        "global.utoc",
        "gp.dll",
        "gpHackerProc.dll",
        "gpShell.dll",
        "gpm.dll",
        "gpmperf.dll",
        "gsdk.dll",
        "guard.py",
        "guard.released",
        "gvas.parse",
        "gvas.py",
        "heartbeat.json",
        "hb.record",
        "heartbeat.record",
        "hooks.py",
        "hydra.dll",
        "hygiene.py",
        "icd.json",
        "ids.next",
        "ids.py",
        "infos.json",
        "ingest.LEDGER.md",
        "kernel32.TerminateProcess",
        "lane-ops.md",
        "lane-safety.md",
        "lane.worktree",
        "lanes.git",
        "lanes.owner",
        "lanes.path",
        "lanes.primary",
        "lanes.py",
        "lanternlight.armwatch",
        "lanternlight.damage",
        "lanternlight.gvas",
        "lanternlight.logparse",
        "lanternlight.paths",
        "lanternlight.redact",
        "lanternlight.redact.RedactionError",
        "lanternlight.savewatch",
        "lanternlight.tail",
        "launcher.py",
        "ledger.py",
        "libcef.dll",
        "log.db",
        "logparse.py",
        "loop.lock",
        "loop.md",
        "mcp.json",
        "mcp.json.bak",
        "mdscan.py",
        "message.lower",
        "meter.py",
        "meter.read",
        "newthing.py",
        "non-MistfallHunter.log",
        "nope.md",
        "notes.md",
        "ops.LEDGER.md",
        "ops.lane",
        "ops.lanes.REPO",
        "ops.lanes.owner",
        "ops.loop",
        "ops.loop.watch",
        "ops.merge",
        "opss.LEDGER.md",
        "os.abort",
        "os.kill",
        "os.killpg",
        "os.system",
        "overlay.anchors",
        "overlay.render",
        "overlay.window",
        "overlay.window.CONTROL",
        "package.json",
        "pakchunk0-Windows.utoc",
        "pakchunk2-Windows.utoc",
        "pakchunk4-Windows.utoc",
        "pakchunk6-Windows.utoc",
        "pakchunk8-Windows.utoc",
        "pakchunk9-Windows.utoc",
        "paks.py",
        "parfait.dll",
        "path.replace",
        "paths.py",
        "payload.rows",
        "pii.py",
        "poller.py",
        "ports.py",
        "probe.sav",
        "pyproject.toml",
        "pytest.ini",
        "python.exe",
        "pythonw.exe",
        "re.IGNORECASE",
        "redact.AUTHORED",
        "redact.assert",
        "redact.iter",
        "redact.py",
        "register.py",
        "render.Payload",
        "render.py",
        "render.render",
        "render.waiting",
        "rolling.record",
        "research.STATE.json",
        "ruff.toml",
        "safety.LEDGER.md",
        "safety.STATE.json",
        "sample.ini",
        "savewatch.py",
        "seen.add",
        "serena.exe",
        "settings.json",
        "shutil.copy",
        "slot.gvas",
        "sscronet.dll",
        "state.advance",
        "state.claim",
        "state.credit",
        "state.duplicate",
        "state.integrate",
        "state.json",
        "state.py",
        "state.save",
        "state.stale",
        "str.splitlines",
        "subprocess.Popen",
        "sys.executable",
        "sys.exit",
        "sys.stderr",
        "sys.stderr.write",
        "sys.stdin",
        "tail.py",
        "textwrap.dedent",
        "tgrpdownloader.dll",
        "target.replace",
        "tracked.iter",
        "tracked.py",
        "unowned.txt",
        "user.json",
        "uv.exe",
        "v1.7.1.dev",
        "v1.sav",
        "version.txt",
        "victimPlayerState.name",
        "walker.py",
        "watch.py",
        "watch.session",
        "window.py",
        # A FIFTH wave of our own and a sibling's filenames, quoted by
        # `LL-0164`, the entry recording the 2026-09-07 inbox review. Both
        # arrive as the tail the extractor emits, and both were probed with
        # `git ls-files` before being added, per the regenerating note above.
        #
        # `LL-NEXT-SESSION.txt` is OURS - `git ls-files` matches it exactly
        # once, at the repository root - and `.txt` parses as a three-letter
        # TLD. The entry names it because the operator's own complaint about
        # the hand-off shape was written into that file.
        #
        # `winmutex.py` is a SIBLING project's module, named in RC's note
        # about which files in its public history carry sibling names.
        # Lanternlight has no such file and `git ls-files` matches zero paths
        # for it, exactly as the `slots.py` and `MANIFEST.sha` notes above
        # record for the same situation.
        #
        # THIS IS THE FOURTH TIME the denylist has absorbed this project's own
        # filenames in the sequence `OPS-44` is tracking, and the second time
        # it has absorbed a sibling's. The count is still the warning and the
        # decision is still deferred: additions are reviewed here, the LOGIC is
        # left alone, and `OPS-44` holds the choice.
        "LL-NEXT-SESSION.txt",
        "winmutex.py",
        }
)


def _register_section(text: str | None = None) -> str:
    """Return the register section of ``ECOSYSTEM.md``, lowercased."""
    body = ECOSYSTEM.read_text(encoding="utf-8") if text is None else text
    start = body.find(REGISTER_START)
    end = body.find(REGISTER_END)
    if start < 0 or end < 0 or end <= start:
        raise AssertionError(
            "cannot locate the register section in docs/ECOSYSTEM.md between "
            f"{REGISTER_START!r} and {REGISTER_END!r} - the headings moved or "
            "were renamed, and this guard cannot check what it cannot find"
        )
    return body[start:end].lower()


def _normalise(token: str) -> str:
    """Lowercase, and drop a leading ``www.`` - one source, two spellings."""
    lowered = token.lower()
    return lowered[4:] if lowered.startswith("www.") else lowered


#: A character that can continue a host label to the LEFT of a match. A dot is
#: included so that ``grandwiki.com`` does not match inside
#: ``mistfallhunter.grandwiki.com`` - that is a different host, not this one.
_CONTINUES_LEFT = re.compile(r"[A-Za-z0-9.-]")
#: ...and to the RIGHT. A trailing dot is only a continuation when a label
#: actually follows it, so a host at the end of a sentence still counts.
_CONTINUES_RIGHT = re.compile(r"[A-Za-z0-9-]|\.[A-Za-z0-9]")


def _present_in_register(host: str, section: str) -> bool:
    """True when ``host`` appears in ``section`` as a WHOLE host token.

    **`LL-0081`, and the reason a bare substring test is not good enough.** The
    first version of this guard asked ``host in section``. That let
    ``grandwiki.com`` pass on the strength of a row for
    ``mistfallhunter.grandwiki.com``, and would let ``x.com`` pass inside
    ``gamingpromax.com``. A registry entry for a subdomain says nothing about
    its parent, and vice versa - they are separate sources with separate
    operators, and conflating them is how an unvetted source gets cited.

    Both callers lowercase before reaching here.
    """
    for match in re.finditer(re.escape(host), section):
        before = section[match.start() - 1] if match.start() else ""
        if before and _CONTINUES_LEFT.match(before):
            continue
        if _CONTINUES_RIGHT.match(section[match.end() : match.end() + 2]):
            continue
        return True
    return False


def cited_hosts(root: Path = DOCS) -> dict[str, set[str]]:
    """Map every host-shaped token under ``root`` to the files citing it."""
    hits: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT).as_posix()
        for match in HOST_SHAPED.finditer(text):
            hits.setdefault(match.group(0), set()).add(rel)
    return hits


def external_sources(root: Path = DOCS) -> dict[str, set[str]]:
    """:func:`cited_hosts` minus the vetted non-hosts."""
    return {
        token: files
        for token, files in cited_hosts(root).items()
        if token not in KNOWN_NON_HOSTS
    }


def test_the_register_section_is_locatable_and_substantial():
    """Positive control - a guard that cannot find its target proves nothing."""
    section = _register_section()
    assert len(section) > 2000, (
        f"the register section is implausibly short at {len(section)} "
        "characters - if the headings moved, fix the constants; do not let "
        "this guard pass against an empty slice"
    )
    assert "gyldforge.com" in section, (
        "a known register member is absent from the located section, so the "
        "slice is not the register"
    )


def test_the_denylist_actually_subtracts_something():
    """A checker reporting zero non-host noise is misconfigured, not clean.

    ``docs/`` is full of dotted code identifiers - ``str.splitlines``,
    ``lanternlight.redact``, ``ops.loop``. If the extractor stops matching
    them it has stopped matching host-shaped tokens generally, and this guard
    would then pass by seeing nothing at all.
    """
    raw = cited_hosts()
    kept = external_sources()
    assert raw, "the extractor found no host-shaped tokens anywhere in docs/"
    assert len(raw) - len(kept) > 0, (
        "the denylist subtracted NOTHING, which means the extractor is no "
        "longer matching the dotted code identifiers docs/ is full of. A "
        "checker that reports zero non-host noise is misconfigured rather "
        "than clean"
    )


def test_the_extractor_is_tld_agnostic():
    """The exact LL-0079 regression - a rare TLD must not be invisible.

    ``.gl`` was missing from the old hardcoded allowlist, which is how a cited
    source went unseen. Any final label of 2-24 letters must match, including
    ones nobody thought of.
    """
    for probe in ("th.gl", "example.gl", "some-site.quux", "a.b.zw"):
        assert HOST_SHAPED.fullmatch(probe), (
            f"{probe!r} is host-shaped and the extractor did not match it - "
            "a TLD allowlist has crept back in"
        )


def test_a_www_prefix_normalises_to_the_bare_domain():
    """``www.twitch.tv`` and ``twitch.tv`` are one source, not two."""
    assert _normalise("www.twitch.tv") == "twitch.tv"
    assert _normalise("WWW.Twitch.TV") == "twitch.tv"
    assert _normalise("twitch.tv") == "twitch.tv"
    # Not over-eager: only a LEADING www. is dropped.
    assert _normalise("wwwfoo.com") == "wwwfoo.com"


def test_presence_requires_a_host_BOUNDARY_not_a_substring():
    """`LL-0081`. A tail match is not a register entry.

    REFUTED BY THE ADVERSARIAL PASS ON `LL-0080`, and it was live in the tree
    rather than hypothetical. ``grandwiki.com`` is cited standalone in
    ``docs/ECOSYSTEM.md`` - "grandwiki.com hosts wikis for many titles under
    the same subdomain pattern" - and had no register row of its own. The
    guard passed anyway, because the string is a TAIL of the neighbouring row
    for ``mistfallhunter.grandwiki.com``. The green was luck, not coverage.

    The same defect swallows the two most plausible first-party sources a
    future session would reach for: ``x.com`` sits inside ``gamingpromax.com``
    and ``t.co`` inside ``grindnstrat.com``, both already in the register. A
    two-label host will pass against almost any register that ever grows.

    This is `LL-0079`'s lesson for the third time. The extractor was fixed to
    be TLD-agnostic and was proven non-vacuous; the PRESENCE half was never
    examined, so the guard remained blind somewhere nobody had looked.
    """
    section = (
        "| `mistfallhunter.grandwiki.com` | wiki farm | t4 |\n"
        "| `gamingpromax.com` | outlet | t4 |\n"
        "| `grindnstrat.com` | outlet | t4 |\n"
    )
    # A tail of a longer host is NOT a register entry.
    assert not _present_in_register("grandwiki.com", section)
    assert not _present_in_register("x.com", section)
    assert not _present_in_register("t.co", section)
    # The whole tokens still register - the fix must not break the positive case.
    assert _present_in_register("mistfallhunter.grandwiki.com", section)
    assert _present_in_register("gamingpromax.com", section)
    assert _present_in_register("grindnstrat.com", section)
    # A longer host must not be satisfied by a shorter row either.
    assert not _present_in_register("grandwiki.com.au", section)


def test_every_cited_external_source_appears_in_the_register():
    """The item's acceptance criterion.

    Fails naming the host AND the file that cites it - a failure that does not
    name the host is not actionable, and this repository has already shipped
    one guard whose red state told nobody what was wrong.
    """
    section = _register_section()
    missing = {
        token: files
        for token, files in external_sources().items()
        if not _present_in_register(_normalise(token), section)
    }
    if missing:
        lines = [
            f"  {token}  cited by: {', '.join(sorted(files))}"
            for token, files in sorted(missing.items())
        ]
        raise AssertionError(
            f"{len(missing)} host(s) cited in docs/ are ABSENT from the "
            "source register in docs/ECOSYSTEM.md:\n"
            + "\n".join(lines)
            + "\n\nEither add each one to the register with its provenance, "
            "tier and basis, or - if it is not an external source - add it to "
            "KNOWN_NON_HOSTS in this file after looking at it."
        )
