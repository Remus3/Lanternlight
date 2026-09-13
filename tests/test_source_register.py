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

HOW IT WORKS. Extract every host-shaped token from every document in
:func:`scanned_documents` with a TLD-AGNOSTIC pattern, subtract the tokens that
are this repository's own FILENAMES, subtract an enumerated denylist of further
tokens a
human has vetted as not-an-external-source, and require every survivor to
appear in the register section. A leading ``www.`` is normalised away, because
``www.twitch.tv`` and ``twitch.tv`` are one source and a guard that reported
the first as missing would be crying wolf.

THE FILENAME SUBTRACTION - ``OPS-44``, option 2, landed 2026-09-07. Before it,
every one of this project's own filenames quoted in ``docs/`` had to be added
to :data:`KNOWN_NON_HOSTS` by hand, because ``.py`` is Paraguay's TLD and
``.md``, ``.gz``, ``.js`` and friends all parse as host-shaped tails. Six
successive waves of that had put 109 of our own filenames in the denylist and
the count was still climbing, because this project has begun writing documents
whose whole job is to list its own files. :func:`is_repo_filename` now asks
``git ls-files`` AT TEST TIME whether a token is one of them.

The check is deliberately narrow, because auto-exemption is the exact failure
``LL-0079`` is about - a heuristic that quietly excused a live external source:

* It is asked ONLY about filenames. Dotted module and API paths -
  ``ops.outbox.deliver``, ``json.loads``, ``Path.iterdir`` - are not resolved
  and stay in the denylist where a human vetted them.
* It compares against the BASENAME of a tracked path, never the whole path.
* The extractor TRUNCATES - ``tests/test_inbox_watch_subdirs.py`` is emitted as
  ``subdirs.py`` - so a basename that merely ENDS with the token counts, but
  only when the character immediately before the token is ``_``, ``-`` or
  ``.``. A bare tail match would let a token be excused by any file whose name
  happens to end in those letters. See
  :func:`test_the_boundary_rule_is_what_does_the_work` for what that buys and
  what it deliberately does not.
* The listing is asked of ``git`` on every run and is never stored in this
  file. A committed list of filenames goes stale the moment a file is renamed
  and then reads as a confident lie.
* If ``git`` fails, is absent, or returns nothing, the check exempts NOTHING.
  The guard gets NOISIER when its input is missing, never quieter - a check
  that silently excuses everything when its data source breaks is worse than no
  check at all. Pinned by
  :func:`test_an_empty_tracked_listing_exempts_nothing`.

WHAT THIS GUARD IS BLIND TO. Stated here, in the artifact, because a caveat
that lives only in conversation is a lie in the artifact:

* **The denylist is A trusted part, and since ``OPS-44`` it is no longer the
  only one.** A real source wrongly added to :data:`KNOWN_NON_HOSTS` is hidden
  from this check exactly the way ``.gl`` was hidden by the old allowlist.
  Review additions to that set.
* **The tracked-file listing is now trusted too, and that is the price of
  ``OPS-44``.** Anything ``git ls-files`` reports is believed, so committing a
  file whose name collides with a real external source - a file literally named
  ``th.gl``, or any name ending ``_th.gl`` - would excuse that source from the
  register silently. Nothing in this guard would say so. The trade accepted in
  ``OPS-44`` is that this failure needs a deliberate, committed, reviewed file
  addition, where the old failure needed only a distracted denylist edit during
  a wave that was already red; and the boundary rule keeps the collision from
  being accidental. It is a smaller surface, not a closed one, and it is
  written down here rather than left in a chat log.
* It checks that a host STRING is present in the register section. It does not
  check that the row next to it says anything true, or that the tier is right.
* It reads DOCUMENTS, never CODE. Every tracked ``*.md`` and ``*.txt`` in the
  repository is in scope since `OPS-63` - see :func:`scanned_documents` for the
  scope decision and the one enumerated exclusion - but a source cited from a
  ``*.py`` docstring, a ``*.ps1``, ``*.toml`` or ``*.yml`` is still unchecked.
  That is a deliberate line and not an oversight: a Python file is dense with
  dotted attribute access, so scanning code would multiply the denylist without
  finding a citation, and this project cites its sources in prose.
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

THE UNDERSCORE TRUNCATION - MEASURED, AND DELIBERATELY KEPT. ``OPS-63``
criterion 3, 2026-09-08. This is written down because the item's own hypothesis
was REFUTED by measuring it, and a refutation that lives only in a chat log gets
re-derived by the next session that reads the denylist and has the same idea.

The hypothesis: most of :data:`KNOWN_NON_HOSTS` is truncation debris that a
pattern permitting ``_`` inside a label would retire wholesale, so the denylist
is treating a pattern defect. Measured against the pre-``OPS-63`` scope, with
267 entries of which 266 were actually emitted by the extractor somewhere
(``19.18.28.701.png`` was already dead weight):

* the underscore-tolerant pattern retires **45** of the 266, not most of them -
  16.9 per cent;
* and it introduces **52** brand-new red tokens in the same scope, because the
  longer form it now emits is not in the denylist either. Net 267 to 274. The
  change makes the thing it was supposed to shrink BIGGER.
* **Zero** of those 52 longer forms are covered by :func:`is_repo_filename`.
  That is the whole explanation, and it is that ``OPS-44`` already harvested
  this win: the truncations whose long form IS one of our tracked filenames were
  the 109 entries ``OPS-44`` deleted. What is left is dominated by names no
  filename check can ever excuse - gitignored runtime records
  (``inbox_reported.json``, ``loop_state.json``), captured frame filenames
  (``f0566_00.43.29.png``), a sibling's files, and dotted module paths carrying
  an underscore mid-chain (``ops.merge_gate.verify``, ``ops.lane_state.claim``),
  which this module deliberately does not resolve at all.

**THE UNTRACKED-BY-DESIGN SUB-CASE, which is the part worth carrying forward.**
``reported.json`` does retire under the wider pattern - and ``inbox_reported.json``
appears in its place, cited by ``docs/LEDGER.md``, still unexcusable because the
file is gitignored ON PURPOSE. The pattern change RENAMES the entry; it does not
retire it. So the answer to "what happens to the names of files this project
writes about but deliberately does not track" is: they land here under whichever
name the extractor emits, and no pattern can change that. The only mechanisms
that could are to resolve tokens against ``.gitignore`` - which would make any
gitignored path auto-excusing and is ``LL-0079``'s auto-exemption failure with a
new data source - or a human reading each one, which is what this set is.

**A second FP reduction was measured and also rejected: skipping fenced code
blocks.** It works, in the narrow sense - it cuts the ``OPS-63`` widening's 52
new tokens to 34, and in the existing scope it drops 10 tokens of which ZERO are
registered external sources, so it costs no coverage on today's tree. It is
rejected because it creates an UNBOUNDED and UNREVIEWED blind spot: any host
inside any code fence in any document becomes invisible, in a guard whose
founding defect was a silent exemption. The denylist is at least a list somebody
has to read. A fence is not.

REGENERATING THE DENYLIST, rewritten for ``OPS-44``. A new token that reddens
this guard now falls into one of three cases, and only the third ends here:

1. It is one of THIS repository's own tracked filenames. Do nothing. The
   filename subtraction already covers it, and adding it to the denylist would
   be dead weight that outlives the file.
2. It is one of our own files that is not tracked yet - created in the same
   uncommitted wave as the document citing it. Stage the file and re-run; the
   subtraction picks it up. Do not add it here to get green sooner, because the
   entry will still be here long after anyone remembers why.
3. It is anything else - a dotted module or API path, a gameplay tag, a config
   key, a gitignored runtime artefact, a SIBLING project's filename, or a
   version string. Look at it, then add it to :data:`KNOWN_NON_HOSTS` with a
   comment saying what it actually is.

Do NOT add a token you have not looked at, and never add a real host to make a
red run green - that is how a guard stops working.
"""

import functools
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

import _toolguard

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

#: Characters that may sit immediately before a token inside a longer basename
#: and still leave the token a whole NAME PART rather than a coincidental tail.
#: The extractor truncates at ``_``, so ``tests/test_inbox_watch_subdirs.py``
#: reaches this file as ``subdirs.py`` and a suffix match is unavoidable - but
#: an UNBOUNDED suffix match is the auto-exemption `LL-0079` is about.
_NAME_PART_BOUNDARY = frozenset("_-.")


@functools.lru_cache(maxsize=8)
def _tracked_paths_for(root: str) -> tuple[str, ...]:
    """Ask ``git ls-files`` about one root, cached PER ROOT.

    THE CACHE KEY IS THE ROOT, and that is not a micro-optimisation. A cache
    with no key was the first version of this and the full suite caught it
    within the hour: ``tests/test_docguards.py`` monkeypatches
    :data:`REPO_ROOT` to a temporary tree to plant a token, which made the
    FIRST call of the run answer for a directory that is not a repository. The
    empty answer was then cached for the process, every subsequent call in the
    real tree got it, and the guard reported 104 of this project's own files as
    unregistered sources. Passing alone and failing in the suite is exactly the
    shape of an unkeyed process-wide cache.
    """
    try:
        done = subprocess.run(
            [_toolguard.require("git"), "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if done.returncode != 0:
        return ()
    return tuple(line.strip() for line in done.stdout.splitlines() if line.strip())


def tracked_paths(root: Path | str | None = None) -> tuple[str, ...]:
    """Every path ``git ls-files`` reports for ``root``, asked LIVE.

    ``root`` defaults to :data:`REPO_ROOT` read AT CALL TIME rather than bound
    at definition time, so a test that repoints the module sees its own tree.

    Cached per root because the suite calls it repeatedly, and never written
    down anywhere: a committed list of filenames goes stale on the first rename
    and then reads as a confident lie about the tree.

    Returns an EMPTY tuple on any failure - git missing, a non-zero exit, a
    timeout, no output, or a root that is not a repository. Every caller treats
    empty as "exempt nothing", so a broken listing makes this guard noisier
    rather than quieter.
    """
    return _tracked_paths_for(str(REPO_ROOT if root is None else root))


def is_repo_filename(token: str, paths: Iterable[str] | None = None) -> bool:
    """True when ``token`` is the name, or a bounded name-part tail, of a
    tracked file.

    ``paths`` exists so tests can drive this with an injected listing instead
    of creating files. Passing an EMPTY listing must exempt nothing; that is
    the fail-closed direction and it is pinned by a test.

    The rule, and nothing looser: the BASENAME of some tracked path either
    equals the token, or ends with it with ``_``, ``-`` or ``.`` immediately
    before. Matching is case-sensitive, which is the noisier direction.
    """
    if not token:
        return False
    if paths is None:
        paths = tracked_paths()
    cut = len(token)
    for path in paths:
        base = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if base == token:
            return True
        if len(base) > cut and base.endswith(token) and base[-cut - 1] in _NAME_PART_BOUNDARY:
            return True
    return False


#: Tokens that are host-SHAPED and are not external sources: dotted code
#: identifiers, module paths, Unreal gameplay tags, version strings, gitignored
#: runtime artefacts, SIBLING projects' filenames, the GSDK package name and the
#: Windows-MCP extension id. Every member was read before it was added. See the
#: module docstring before extending it.
#:
#: `OPS-44` REMOVED 109 ENTRIES FROM THIS SET on 2026-09-08 - every token that
#: :func:`is_repo_filename` now covers, which is to say every one of THIS
#: repository's own tracked filenames.
#:
#: TWO WERE ADDED IN THE SAME WAVE, and this sentence exists because the first
#: version of this comment said "nothing else was touched" while the same
#: commit added them. An adversarial pass caught the discrepancy between this
#: comment and `LL-0176`, which recorded both numbers correctly. The two are
#: `lanternlight.redact.iter` and `user.email`, the NINTH trip of this guard;
#: neither is a filename, so neither is a token the new check covers. Net
#: 371 to 264.
#:
#: Some comment blocks below therefore describe tokens that are no longer
#: listed under them, and one or two now head no entries at all. That prose is
#: kept deliberately: it is the six-wave record `OPS-44` was filed against, and
#: deleting it would erase the evidence for the change while keeping the
#: change.
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
        "slots.py",
        "sys.addaudithook",
        "GateReport.notes",
        # STANDARD LIBRARY CALLABLES quoted by `OPS-82`, which describes which
        # write routes an external write tracer patched and which route this
        # repository's own atomic writers take. Each is a dotted Python name
        # the extractor reads as a domain; none is a host and none resolves
        # anywhere. `path.write` is the truncated tail the extractor emits for
        # `Path.write_bytes`, lowercased, and is listed in the form the failure
        # message actually names rather than the form the prose uses.
        "builtins.open",
        "os.rename",
        "os.replace",
        "path.write",
        # QUOTED BY `OPS-84`, the vendored write tracer and its Apache-2.0
        # obligations. `NOTICE.md` and `tracer.py` are deliberately NOT listed
        # here: both are now TRACKED files, so the live tracked-file check
        # covers them, and the guard below refuses a denylist entry that the
        # live check has absorbed - a hardcoded name that git already answers
        # for is the stale list this module exists to avoid.
        #
        # These two are not tracked and so are not covered by it.
        # `observed.json` is the extractor's tail of the `docguard_observed`
        # recorder named in the trace result, which writes into the gitignored
        # `ops/runtime/`. `tracer.py.from` is the tail of
        # `moon_sync_inbox/lw_write_tracer.py.from-lw`, the ORIGINAL DROP, which
        # lives in the gitignored mail directory and will never be tracked -
        # `.from` is not a TLD but the host-shaped pattern cannot know that.
        # Neither is an external source; both were looked at before being added.
        "observed.json",
        "tracer.py.from",
        # A JSON FIELD PATH quoted by the reply draft to LW, naming the key the
        # vendored tracer writes its self-check under. `.proved` is not a TLD
        # and resolves nowhere; the host-shaped pattern cannot tell a dotted
        # field path from a domain. Not an external source.
        "control.proved",
        # WINDOWS EXECUTABLE BASENAMES quoted by `OPS-83` and `LL-0235`, which
        # record where each program resolved when Git for Windows' POSIX
        # userland was stripped from `PATH`. `.EXE` is not a TLD, but the
        # host-shaped pattern reads `find.EXE` exactly as it reads a domain.
        # Each was looked at before being added, per the regenerating note
        # above, and each is listed in the CASE the failure message names
        # rather than the case the prose uses - the same reason `path.write` is
        # listed lowercased.
        #
        # None is an external source and none is a file in this tree.
        # `git.exe` and `sh.exe` ship with Git for Windows, `find.EXE` and
        # `sort.EXE` are the Windows programs in `%SystemRoot%\system32` that
        # wear POSIX names - which is the measured trap `OPS-83` exists to
        # defend against, not a citation of anything. The same class as
        # `python.exe`, `pythonw.exe` and `cmd.exe` already registered below.
        "find.EXE",
        "git.exe",
        "sh.exe",
        "sort.EXE",
        # GITIGNORED RUNTIME FILENAMES quoted by the hand-off, naming where the
        # capture watcher's arming record and heartbeat were moved when the
        # operator had the headless lane disarmed on 2026-09-11. Both live under
        # `ops/runtime/`, which is gitignored, so neither is tracked and the live
        # tracked-file check cannot cover them. `.json` is not a TLD, but the
        # dated stem puts a dot-separated tail in front of it and the host-shaped
        # pattern reads the whole thing as a domain. The second is the tail the
        # extractor emits for `armwatch_heartbeat.disarmed-...`, not a separate
        # file. Neither is an external source.
        "armwatch.disarmed-2026-09-11.json",
        "heartbeat.disarmed-2026-09-11.json",
        # TEST MODULE FILENAMES quoted by `LL-0159`, the entry closing the
        # `OPS-33` follow-up. Each is a file in THIS tree - `git ls-files`
        # matches `tests/test_inbox_acknowledge.py` and its three siblings -
        # and the host-shaped pattern reads the dotted tail as a domain
        # because `.py` is a real TLD, Paraguay's. Looked at before adding,
        # per the regenerating note above: these are our own test modules,
        # not sources. The tokens are the tails the extractor emits, not the
        # full paths, which is what any failure message would name.
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
        "outbox.replies",
        # OPS-78, 2026-09-11. Four tokens the host-shaped pattern lifts out of
        # the new "What this suite does when an external tool is missing"
        # section of `docs/OPERATIONS.md`. Each was looked at before being
        # added, per the regenerating note above, and none is a source:
        # `toolguard.require` and `toolguard.requires` are the tails the
        # extractor emits for `_toolguard.require` and `_toolguard.requires`,
        # two functions in this repository's own `tests/_toolguard.py`;
        # `subprocess.run` is a Python standard-library call and
        # `completed.stdout` an attribute of what it returns, both quoted in
        # that section's worked example.
        #
        # The FILENAME `toolguard.py` is deliberately NOT in this set. It is
        # resolved against `git ls-files` at test time by `is_repo_filename`,
        # which is the whole point of `OPS-44`, and it stops being reported the
        # moment the file is staged. Adding it here by hand would put a
        # filename back in the denylist that the live listing already answers
        # for, which is the growth `OPS-44` was filed to stop.
        "toolguard.require",
        "toolguard.requires",
        "subprocess.run",
        "completed.stdout",
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
        # `OPS-57`, 2026-09-08. All three are the SAME truncation the entries
        # above describe: an underscore is not a host character, so the pattern
        # keeps only the tail after it. `ids.default` is the tail of
        # `ops.ops_ids.default_archive_paths` and `ops.ops` of `ops.ops_ids` -
        # dotted module paths, which the filename subtraction deliberately does
        # not resolve, so they belong here where a human vetted them.
        #
        # `ROADMAP-ARCHIVE.md` is kept for a different reason. It is a real
        # historical string: `LL-0197` records that the splitter and the link
        # guard defaulted to DIFFERENT filenames, and quoting the rejected
        # hyphen form is that entry's evidence. It is host-shaped precisely
        # because it has a hyphen where the name actually shipped has an
        # underscore - a small demonstration of why `docs/` uses underscores.
        #
        # TWO MORE WERE ADDED HERE AND THEN REMOVED, which is worth recording
        # because the module's own guidance above predicted it as case 2.
        # `ARCHIVE.md` (from `docs/ROADMAP_ARCHIVE.md`) and `archive.py` (from
        # `tools/doc_archive.py`) looked like denylist material while those
        # files were still untracked. The moment they were STAGED,
        # `is_repo_filename` covered them and
        # `test_the_filename_check_covers_our_own_files_and_the_denylist_does_not`
        # went red demanding their removal - which is the guard doing exactly
        # its job. The full suite could not see it: it ran against the working
        # tree, and the fact only exists once `git ls-files` reports the files.
        # The pre-commit hook, which runs against the STAGED tree, caught it and
        # refused the commit.
        "ROADMAP-ARCHIVE.md",
        "ids.default",
        "ops.ops",
        # `reported.json`, the underscore truncation of `inbox_reported.json`,
        # cited by `LL-0202` as evidence for `OPS-61`. It is a RUNTIME record
        # under gitignored `ops/runtime/`, and that is a sub-case worth naming
        # for `OPS-63`: `is_repo_filename` asks `git ls-files`, so a file this
        # project legitimately writes about but deliberately does not track can
        # never be auto-excused and lands here by construction rather than by
        # anyone's oversight. Staging it is not the escape hatch case 2
        # describes, because the whole point of the file is that it is not
        # committed. `OPS-63`'s criterion 3 counts entries that a pattern which
        # stopped truncating at underscores would retire; this is one of them.
        "reported.json",
        # `NOPE.md` and `sys.argv`, both introduced 2026-09-08 by `OPS-64`'s and
        # `OPS-66`'s own closure prose - `docs/NOPE.md` is the deliberately
        # absent archive the link guard was pointed at to make it report DID NOT
        # RUN, and `sys.argv` is a Python attribute. This is `LL-0199`'s shape
        # once more: writing a measurement down changed the tree the measurement
        # was about, and here it did so through a guard that had just been
        # widened to read the document doing the writing. Expect more of these
        # per session now that `ROADMAP.md` is in scope - that cost is stated in
        # `OPS-63`'s outcome rather than discovered again each time.
        "NOPE.md",
        "sys.argv",
        # `PairGrowthModel.splits`, the truncation of
        # `PairGrowthModel.splits_measured`, introduced 2026-09-08 by `OPS-62`'s
        # closure prose. Third of three tokens this session's own closures added
        # to this set, after `NOPE.md` and `sys.argv`. The rate is the cost
        # `OPS-63` measured and stated: with `ROADMAP.md` and `docs/LEDGER.md` in
        # scope, a session that writes about its own code contributes a few of
        # these, and vetting them is the price of reading the documents where
        # this project actually cites its sources.
        "PairGrowthModel.splits",
        # `path.name`, a pathlib attribute, cited by `LL-0205` where it quotes
        # what `tools/probe_paks.py` used to print. Fourth of four tokens this
        # session's own closure prose added to this set. The running count is
        # the point rather than the token: `OPS-63` widened the scope to the
        # documents where this project writes about its own code, and four per
        # session is what that costs. If a later session finds itself adding ten
        # in one pass, that is the signal to revisit the extractor rather than
        # to keep typing - `OPS-63`'s criterion 3 measured the alternative and
        # refuted it at 45 retired against 52 introduced, so the answer is not
        # simply "stop truncating at underscores".
        "path.name",
        # `check.main` (the truncation of `ascii_check.main`) and
        # `permissions.allow` (a settings.json key), both from the WRAP prose of
        # 2026-09-08 - `LL-0206` and `OPS-70`. Fifth and sixth this session, and
        # the last two arrived from the REFUTATION pass rather than from a
        # closure: describing a defect accurately requires naming the thing that
        # has it. `OPS-63`'s cost paragraph says this rate is the price of
        # reading the documents where this project writes about its own code,
        # and six in one session is the first real datum for that rate.
        "check.main",
        "permissions.allow",
        # THE SAME settings.json KEY FAMILY, three more of it, added
        # 2026-09-10 while closing `OPS-70`. `tools/hook_command_guard.py` was
        # widened to read the whole `permissions` object rather than
        # `hooks.*` alone, and `docs/INVENTORY.md` now describes it doing so -
        # which means naming the keys. Each was looked at: all three are keys
        # in `.claude/settings.json`, none is a host, and none resolves to
        # anything. `.deny`, `.ask` and `.additionalDirectories` simply parse
        # as TLD-shaped tails the way `.allow` above does.
        #
        # The rate this set is growing at is the thing to watch rather than
        # these three entries. `OPS-63`'s cost paragraph predicted it: a
        # project that writes documents about its own configuration keeps
        # minting host-shaped tokens that are not hosts. The defect is the
        # extractor's, and the denylist is absorbing it one wave at a time.
        "permissions.deny",
        "permissions.ask",
        "permissions.additionalDirectories",
        # `settings.local.json`, added 2026-09-10 while closing `OPS-70`,
        # whose guard names it as a blind spot it deliberately does not read.
        # Looked at: it is Claude Code's per-machine settings file, sitting
        # beside the tracked `.claude/settings.json`. It is not a host.
        #
        # THE INTERESTING PART IS WHY THE TRACKED-FILE ORACLE DID NOT ABSORB IT
        # THE WAY IT ABSORBS EVERY OTHER FILENAME WE WRITE DOWN. `is_repo_filename`
        # trusts `git ls-files`, and this file is GITIGNORED, so it is a real
        # filename in this repository that the oracle cannot see. Any gitignored
        # filename this project describes in prose lands here for the same reason -
        # `OPS-44` bought the tracked listing's trust, and this is the edge of it.
        "settings.local.json",
        # `git.py` WAS ADDED HERE AND THEN REMOVED IN THE SAME HOUR, and the
        # sequence is worth more than the entry would have been.
        #
        # It is the truncation of `tests/test_no_inbox_in_git.py`, cut at the
        # underscore. It was registered while that file was still UNTRACKED,
        # and a full green suite agreed it was needed. The moment the file was
        # STAGED, `test_the_filename_check_covers_our_own_files_and_the_denylist_does_not`
        # refused the commit: `is_repo_filename` had begun covering the
        # fragment, so the denylist entry was now redundant, and a redundant
        # entry in this set is exactly the hiding place this module's docstring
        # warns about.
        #
        # THE LESSON IS ABOUT WHEN A MEASUREMENT IS TAKEN, NOT ABOUT THIS
        # TOKEN. `git ls-files` answers differently before and after staging,
        # so a guard that consults it gives a different verdict at suite time
        # than at commit time. The pre-commit hook caught what a green full
        # suite could not, which is the reason that hook runs the doc-reading
        # subset against the STAGED tree rather than the working one.
        # `Path.is`, added 2026-09-10 in the same hour as `git.py` above and
        # for the same reason one level over: it is the truncation of
        # `Path.is_symlink`, cut at the underscore, and `.is` is Iceland's
        # TLD. Looked at: a `pathlib` method name, not a host and not a file.
        #
        # SIX ENTRIES WENT INTO THIS SET IN ONE SESSION - three
        # `permissions.*` keys, `settings.local.json`, `git.py` and this one -
        # against the four the previous session added. The rate is now the
        # finding rather than any single entry, and it has an identifiable
        # cause: `OPS-69` widened `docs/INVENTORY.md` to name every module in
        # the repository and `OPS-70` widened a guard to name configuration
        # keys, so this project now writes more prose ABOUT ITS OWN FILES than
        # it ever has, and every dotted fragment in that prose parses as
        # host-shaped. The denylist is absorbing an extractor defect, which is
        # exactly what this module's docstring warns is the one place a real
        # source can hide. `OPS-63` measured the pattern-level fix and refuted
        # it at 45 retired against 52 introduced; that measurement is two
        # sessions old and the input has changed since.
        "Path.is",
        # `slot.STALE`, added 2026-09-10 while re-measuring `OPS-35`. Looked
        # at: the truncation of `lane_slot.STALE_SECONDS` at its underscore,
        # leaving a tail whose `.STALE` parses as a TLD-shaped label. It is a
        # module constant, not a host and not a file.
        #
        # Unlike `git.py`, which the tracked-file oracle absorbed the moment
        # its file was staged, this fragment matches no tracked filename and
        # so cannot be retired that way. It is the durable half of the same
        # defect.
        "slot.STALE",
        # THE LANE-SLOT WIRE NAMES, added 2026-09-10 when `ADR-008` joined the
        # shared bucket and had to write the protocol's filenames down. Looked
        # at, all four: three are LOCK FILENAMES in the cross-project bucket
        # and one is truncation debris.
        #
        # `0.lock`, `1.lock` and `reserved-ll.lock` are files that exist on a
        # shared machine-wide directory rather than in this repository, so
        # `is_repo_filename` cannot absorb them no matter what we stage - the
        # tracked-file oracle only knows OUR files. `.lock` parses as a
        # TLD-shaped tail. These are the wire and they have to appear verbatim
        # in a document whose whole job is to let a cold session interoperate.
        #
        # `slot.default` is the truncation of `lane_slot.default_root` at its
        # underscore, the same shape as `slot.STALE` directly above.
        #
        # A NOTE ON THE ONE THAT IS NOT HERE. `ADR-008-join-the-shared-bucket.md`
        # was refused by this same check and is deliberately absent: it is a
        # real file in this repository, and STAGING it made
        # `is_repo_filename` cover it. That is the `git.py` sequence from
        # earlier the same day, applied on purpose rather than learned again -
        # stage a new file first, then decide what is genuinely left over.
        "0.lock",
        "1.lock",
        "2.lock",
        "reserved-ll.lock",
        # `reserved-ds.lock` is the same family, quoted in `OPS-73` as the
        # example of a widening this project's key set cannot currently see.
        "reserved-ds.lock",
        # `slot.REPO` is the truncation of `lane_slot.REPO_KEYS`, the third in
        # this module's `lane_slot.*` set after `slot.STALE` and `slot.default`.
        "slot.REPO",
        # `slot.reap` and `slot.holders` are the fourth and fifth of that same
        # `lane_slot.*` set, added 2026-09-11 when `docs/HEADLESS.md` gained the
        # operator instructions for a BUSY bucket. Looked at, both: they are the
        # truncations of `ops.lane_slot.reap` and `ops.lane_slot.holders` at the
        # underscore in `lane_slot`, leaving a tail whose final label parses as
        # TLD-shaped. Both are first-party functions in this repository's own
        # `ops/lane_slot.py`, neither is a host and neither is a file.
        #
        # They are registered rather than reworded because they sit in the same
        # numbered list as `ops.lane_slot.STALE_SECONDS`, which is already here
        # as `slot.STALE`. Paraphrasing two of the three module paths in one
        # list while the third stays dotted would make the prose read worse to
        # buy nothing - the third would still need this entry. Dotted module
        # and API paths are the category this module's docstring says stays in
        # the denylist after a human vets them, and these were vetted.
        "slot.reap",
        "slot.holders",
        # THE LANE WIRING'S OWN TWO, added 2026-09-11 when `ops/loop/lane.py`
        # wired the loop to the bucket at session scope. Looked at, both:
        # neither is a host, and neither can be retired by staging, because the
        # tracked-file oracle answers about FILENAMES and these are attribute
        # chains.
        #
        # `lane.session` is the truncation of `lane.session_lane()` and
        # `slot.status` the truncation of `slot.status_line()`, both cut at
        # their underscore. Both appear inside the FENCED PYTHON BLOCK that
        # `.claude/commands/loop.md` and `docs/HEADLESS.md` each carry to show a
        # session how to take the three governors in one `with` statement. That
        # block is code a reader copies, and `CLAUDE.md` is explicit that
        # rewording never applies to byte-exact content - the same reasoning
        # already recorded for `tools.doc` further down this list.
        #
        # The prose mentions around those fences WERE reworded rather than
        # denylisted, which is why `slot.held` and `slot.reason` are not here:
        # they were attributes of the example's local variable and read as well
        # or better named bare. Only the fence is irreducible.
        "lane.session",
        "slot.status",
        # `tools.doc` is the truncation of the module path in the command
        # `python -m tools.doc_size_budget`, cut at the underscore. Looked at:
        # not a host. It is registered rather than reworded because the string
        # is a COMMAND a reader types - CLAUDE.md's terseness rule explicitly
        # exempts byte-exact content, and paraphrasing a command to satisfy a
        # guard would break the thing the guard is protecting.
        "tools.doc",
        # OPS-87. Three more module-path truncations, each cut at the first
        # underscore of a COMMAND a reader types: `python -m tools.preflight_backtest`
        # and `python -m ops.preflight`, plus `backtest.strip_mentions` where a
        # document names the function by its imported alias. Looked at, one at a
        # time: none is a host. Registered rather than reworded for the reason
        # given directly above - paraphrasing a command to satisfy a guard breaks
        # the thing the guard protects.
        "tools.preflight",
        "backtest.strip",
        "slot.default",
        # A git CONFIG KEY, quoted by `LL-0169` and `OPS-49`. `core.filemode`
        # is not a host and not a file; `.filemode` simply parses as a TLD-
        # shaped tail. Looked at before adding, per the regenerating note.
        #
        # THE OTHER TWO TOKENS THIS SAME RUN REFUSED ARE NOT NAMED HERE, ARE
        # NOT IN THIS DENYLIST, AND MUST NEVER BE EITHER. They were the two
        # halves of the operator's own email address, quoted into a ledger
        # entry by mistake, and this guard is the only thing in the tree that
        # noticed. Naming them in order to say they must not be named is the
        # same defect one level down, and it was live in this file from
        # 2026-09-07 until `LL-0173` removed it: the two halves sat 26
        # characters apart on adjacent lines, in the reverse order, so every
        # whole-address sweep in this repository went on reporting the tree
        # clean. See `LL-0170`, `LL-0173` and `OPS-50`. Adding a real host to
        # this denylist to make a red run green is how a guard stops working.
        "core.filemode",
        # OPS-86. The truncation of the module the false-red probe PLANTS
        # outside this tree and tears down again, whose basename ends in
        # `control.py`. It is not a tracked filename, so the git ls-files
        # subtraction cannot excuse it, and ROADMAP.md quotes the pytest node
        # id verbatim because the whole finding is about the SHAPE of that
        # id. Looked at, per the note above: not a host.
        "control.py",
        # The NINTH trip, on the ledger entries a concurrent lane wrote while
        # `OPS-44` was being landed. Both are case 3 of the regenerating note
        # above and were read in context before being added.
        #
        # `lanternlight.redact.iter` is the truncation of
        # `lanternlight.redact.iter_operator_identifiers`, our own function -
        # the shorter `redact.iter` was already listed, and the extractor emits
        # the longer chain when the module prefix is written out.
        # `user.email` is the GIT CONFIG KEY, the same class of token as
        # `core.filemode` above. It is the key's NAME, never a value.
        "lanternlight.redact.iter",
        "user.email",
        # A GIT CONFIG KEY quoted by `OPS-75` and `LL-0236`, naming the third
        # source of ignore rules that `git check-ignore` honours beside a
        # `.gitignore` and `.git/info/exclude`. Same class as `core.filemode`
        # and `user.email` above: it is the key's NAME, it is not a host, and
        # `.excludesFile` simply parses as a TLD-shaped tail. Looked at before
        # adding, per the regenerating note. The PATH such a key points at is
        # machine-local and is deliberately never quoted anywhere in this tree.
        "core.excludesFile",
        # THREE MORE FROM `OPS-75` AND `LL-0236`, all looked at in context.
        #
        # `env.pop` is a PYTHON METHOD CALL on a dict, quoted while recording
        # that `_clean_env` losing it lets git's exported hook environment leak
        # into a throwaway repository. Same class as `builtins.open` and
        # `os.replace` above: a dotted attribute chain the extractor reads as a
        # domain. It resolves nowhere.
        #
        # `keep.log` and `notes.txt` are SPECIMEN FILENAMES inside throwaway
        # repositories the tests build in `tmp_path`. Neither is a file in this
        # tree - `git ls-files` matches zero paths for either - and neither is a
        # host; `.log` and `.txt` merely parse as TLD-shaped tails. They are
        # quoted because naming the specimen is what makes the reasoning
        # checkable, and paraphrasing them to satisfy this guard would remove
        # the only detail that lets a reader rebuild the case.
        "env.pop",
        "keep.log",
        "notes.txt",
        # The EIGHTH trip, on `LL-0171` and `LL-0172`. `json.loads` is a
        # PYTHON STDLIB CALL, not a host; `.loads` merely parses as a TLD-shaped
        # tail. `trigger.json` is the tail of
        # `ops/runtime/inbox_prompt_trigger.json`, the bounded invocation trace
        # `OPS-41` writes - gitignored runtime state, never committed, and
        # `git ls-files` matches zero paths for it by design. Both looked at
        # before adding, per the regenerating note above.
        "json.loads",
        "trigger.json",
        "contract.write",
        "ops.outbox.SIBLING",
        "ops.outbox.backfill",
        "log.gz",
        # CAPTURE FILENAMES quoted by `LL-0149`. A frame is stamped
        # `f0566_00.43.29.png` and a fixture `panel_total_1443_hits_28.png`,
        # and the host-shaped pattern reads the dotted tails as domains. An
        # entry that records which frame a committed fixture came from - which
        # is the whole provenance claim - cannot avoid naming it.
        "00.43.29.png",
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
        "MANIFEST.sha",
        # MODULE AND TEST FILENAMES quoted by `LL-0156`, every one arriving
        # TRUNCATED at the last label pair: `tools/doc_size_budget.py` as
        # `budget.py`, `tools/syntax_check_hook.py` as `hook.py`,
        # `tests/test_precommit_gate_lint.py` as `lint.py`. `m.py` is the
        # throwaway fixture module from the lint gate's own probe transcript,
        # quoted because the probe's exact output is the evidence.
        "m.py",
        # `tests/test_no_hardcoded_home_path.py`, quoted by `LL-0157`,
        # truncated to `path.py` by the host-shaped pattern.
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
        "sys.meta",
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
        "pytest.cacheprovider.json.dumps",
        "00.42.52.png",
        "19.02.51.472.png",
        "19.02.52.028.png",
        "19.18.28.701.png",
        "19.32.34.jpg",
        "32.34.jpg",
        "3282300.acf",
        "937566.ini",
        "AvgPrice.ini",
        "BotData.TreasurableItems",
        "Deck.sav",
        "Engine.ini",
        "EnhancedInput.EnhancedPlayerMappableKe",
        "EnhancedInputUserSettings.sav",
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
        "HH.MM.SS.png",
        "IdGeneratorData.NumIdToUUID",
        "IdGeneratorData.UUIDToNumId",
        "Inventory.equipments",
        "ItemCell.cfgId",
        "KillPlayerHistoryDatas.PlayerName",
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
        "Next.js",
        "Notice.sav",
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
        "SEscapePortalSpawner.initialize",
        "SOUL.md",
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
        "ant.dir.cursortouch.windows",
        "armwatch.err",
        "armwatch.json",
        "armwatch.main",
        "armwatch.log",
        "ast.Attribute",
        "bottle-0.13.4.data",
        "bytes.splitlines",
        "channel.steam",
        "child.pid",
        "com.hermes.pstgame",
        "config.json",
        "core.hooksPath",
        "ctypes.windll",
        "current.item",
        "cycle34.csv",
        "dir.mkdir",
        "dataclasses.replace",
        "filecmp.cmp",
        "gate.check",
        "gate.verify",
        "global.ucas",
        "global.utoc",
        "gp.dll",
        "gpHackerProc.dll",
        "gpShell.dll",
        "gpm.dll",
        "gpmperf.dll",
        "gsdk.dll",
        "guard.released",
        "gvas.parse",
        "heartbeat.json",
        "hb.record",
        "heartbeat.record",
        "hydra.dll",
        "icd.json",
        "ids.next",
        "infos.json",
        "kernel32.TerminateProcess",
        "lane.worktree",
        "lanes.git",
        "lanes.owner",
        "lanes.path",
        "lanes.primary",
        "lanternlight.armwatch",
        "lanternlight.damage",
        "lanternlight.gvas",
        "lanternlight.logparse",
        "lanternlight.paths",
        "lanternlight.redact",
        "lanternlight.redact.RedactionError",
        "lanternlight.savewatch",
        "lanternlight.tail",
        "libcef.dll",
        "log.db",
        "loop.lock",
        "mcp.json",
        "mcp.json.bak",
        "message.lower",
        "meter.read",
        "newthing.py",
        "non-MistfallHunter.log",
        "nope.md",
        "notes.md",
        "ops.lane",
        "ops.lanes.REPO",
        "ops.lanes.owner",
        "ops.loop",
        "ops.loop.watch",
        "ops.merge",
        "ops.preflight",
        "ops.refutation",
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
        "parfait.dll",
        "path.replace",
        "payload.rows",
        "probe.sav",
        "python.exe",
        "pythonw.exe",
        "re.IGNORECASE",
        "redact.AUTHORED",
        "redact.assert",
        "redact.iter",
        "render.Payload",
        "render.render",
        "render.waiting",
        "rolling.record",
        "seen.add",
        "serena.exe",
        "shutil.copy",
        "slot.gvas",
        "sscronet.dll",
        "state.advance",
        "state.claim",
        "state.credit",
        "state.duplicate",
        "state.integrate",
        "state.json",
        "state.save",
        "state.stale",
        "str.splitlines",
        "subprocess.Popen",
        "sys.executable",
        "sys.exit",
        "sys.stderr",
        "sys.stderr.write",
        "sys.stdin",
        "textwrap.dedent",
        "tgrpdownloader.dll",
        "target.replace",
        "tracked.iter",
        "unowned.txt",
        "user.json",
        "uv.exe",
        "v1.7.1.dev",
        "v1.sav",
        "version.txt",
        "victimPlayerState.name",
        "watch.session",
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
        "winmutex.py",
        # `OPS-63`, 2026-09-08 - THE SCOPE WIDENING. 48 entries, the largest
        # single wave this set has ever taken, and the reason is not a new defect
        # but a scope that was finally stated: see :func:`scanned_documents`.
        # Every tracked `*.md` and `*.txt` is now read, so 52 host-shaped tokens
        # that had sat unread for the life of this guard arrived at once. All 52
        # were read in context before anything was written here, and they sorted
        # into four kinds:
        #
        # 1. FOUR ARE REAL HOSTS AND ARE NOT IN THIS SET. `docs.github.com` and
        #    `contributor-covenant.org` are genuine unregistered external sources
        #    this widening FOUND, cited by `CODE_OF_CONDUCT.md` and
        #    `SECURITY.md` in a public repository with no register row at all;
        #    `x.com` and `t.co` are named in `ROADMAP.md` only as the fragments
        #    hiding inside `gamingpromax.com` and `grindnstrat.com` in the
        #    `OPS-57` substring passage. All four got register rows in
        #    `docs/ECOSYSTEM.md` instead. A real host never goes in this set,
        #    whatever the sentence around it says it is - the register has rows
        #    for a host that is deliberately unused and for one that is
        #    deliberately unassessed, and those are the sanctioned homes.
        # 2. DOTTED PYTHON PATHS AND ATTRIBUTES, truncated at an underscore by
        #    :data:`HOST_SHAPED` exactly as the entries above record.
        #    `before.values` is `before.values()`, `report.format` is
        #    `report.format()`, `gate.collect` and `gate.parse` are
        #    `merge_gate.collect_output` and `merge_gate.parse_collect_counts`,
        #    `launcher.assert` and `launcher.ensure` are
        #    `lane_launcher.assert_in_lane_worktree` and `ensure_worktree`,
        #    `lanes.by` is `lanes.by_id`, `state.*` and `ops.loop.state.*` are
        #    `ops/loop/state.py` calls, `guard.owner` is `guard.owner_of`,
        #    `guard.read` is `guard.read_owner`, `watch.check` is
        #    `watch.check_watcher`, `armed.armed` is a field of the arm-watch
        #    result, `render.line` and `window.*` are `lanternlight/overlay`
        #    calls, `lanternlight.avgprice` and `lanternlight.vision` are our own
        #    modules, `ops.outbox.replies` is `ops.outbox.replies_to`,
        #    `ops.lanes.WORKTREE` and `ops.lanes.primary` are
        #    `WORKTREE_ROOT` and `primary_checkout`, and `tmp.write` and
        #    `tmp.replace` are the atomic-write recipe in `CLAUDE.md` itself.
        #    `wrote.py` is the tail of the placeholder path
        #    `files/the/agent/said/it/wrote.py` in nine dispatch prompts, and
        #    `word.word` is a toy name in a `WAKEUP_NOTES.md` passage about THIS
        #    guard reading a dotted identifier as a hostname.
        # 3. WINDOWS AND POWERSHELL API NAMES, none of them a host and none of
        #    them ours. `WScript.Shell` is the COM class the `/done` shortcut
        #    recipe instantiates, `ws.CreateShortcut` and `lnk.Save`,
        #    `lnk.TargetPath`, `lnk.WorkingDirectory` are its members,
        #    `System.Speech` and `System.Speech.Synthesis.SpeechSynthesizer` are
        #    the .NET assembly and type behind the text-to-speech recipe, with
        #    `s.Rate` and `s.Speak` its members, and `cmd.exe` is the Windows
        #    shell - the same class as `python.exe` and `pythonw.exe` above.
        # 4. FILENAMES AND URL PATH TAILS. `LL-NEXT-SESSION.lnk` is the Desktop
        #    shortcut `/done` writes, which is on the Desktop and therefore
        #    never tracked. `RSC-NEXT-SESSION.txt` is a SIBLING project's
        #    hand-off, named in the shared-surface warning - the same situation
        #    as `slots.py` and `winmutex.py` above, and `git ls-files` matches
        #    zero paths for it. `Lanternlight.git` and `badge.svg` are PATH
        #    TAILS of two URLs whose HOST is `github.com`, which is registered
        #    and is extracted separately because `/` ends a host token; neither
        #    tail is a host. `Hit.Light` and
        #    `StandaloneLevelCtrl.battleSnapUpdate` are the GAME's own log field
        #    and producer symbol, the same class as the `Game.PlayState` and
        #    `Status.Talent` tags above. `inventory.equipments` is a save-file
        #    property path.
        "Hit.Light",
        "LL-NEXT-SESSION.lnk",
        "Lanternlight.git",
        "RSC-NEXT-SESSION.txt",
        "StandaloneLevelCtrl.battleSnapUpdate",
        "System.Speech",
        "System.Speech.Synthesis.SpeechSynthesizer",
        "WScript.Shell",
        "armed.armed",
        "badge.svg",
        "before.values",
        "cmd.exe",
        "gate.collect",
        "gate.parse",
        "guard.owner",
        "guard.read",
        "inventory.equipments",
        "lanes.by",
        "lanternlight.avgprice",
        "lanternlight.vision",
        "launcher.assert",
        "launcher.ensure",
        "lnk.Save",
        "lnk.TargetPath",
        "lnk.WorkingDirectory",
        "ops.lanes.WORKTREE",
        "ops.lanes.primary",
        "ops.loop.ledger.append",
        "ops.loop.state.advance",
        "ops.loop.state.load",
        "ops.outbox.replies",
        "render.line",
        "report.format",
        "s.Rate",
        "s.Speak",
        "state.dispatch",
        "state.in",
        "state.load",
        "state.retire",
        "tmp.replace",
        "tmp.write",
        "watch.check",
        "window.color",
        "window.font",
        "window.geometry",
        "word.word",
        "wrote.py",
        "ws.CreateShortcut",
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


#: The ONE document in scope that this scan does NOT read, with the reason.
#: Since `OPS-63` stated the scope - see :func:`scanned_documents` - this is the
#: whole of the enumerated-exclusion half of that decision, and a second entry
#: here needs its own reason written down beside it.
#:
#: **`OPS-57`, 2026-09-08.** `ROADMAP.md` lives at the repository ROOT, and this
#: guard has always read ``docs/**/*.md`` only - its own module docstring says
#: so, and names `README.md` as an example of a file it does not cover. Then
#: the `OPS-57` split moved 65 closed roadmap sections, 475,473 bytes of them,
#: into ``docs/ROADMAP_ARCHIVE.md`` - and 57 tokens that had sat unread for
#: weeks were suddenly in scope.
#:
#: **Archiving a document must not silently change what guards apply to it.**
#: The words did not change; only their path did. Excluding the archive keeps
#: this guard measuring exactly what it measured the day before the split.
#:
#: All 57 were checked by hand, and every one is a false positive - Python
#: attributes (`subprocess.run`, `watch.armed`), our own filenames
#: (`trace.jsonl`, `utf16.bin`) and toy names from worked examples (`foo.py`).
#: **Including the two that are host-shaped.** `x.com` and `t.co` appear inside
#: a passage about a SUBSTRING-matching defect, quoted as the fragments hiding
#: inside `gamingpromax.com` and `grindnstrat.com`. They are not citations, and
#: nothing real is being hidden by this exclusion.
#:
#: The alternative was 57 entries in :data:`KNOWN_NON_HOSTS`, which this
#: module's own docstring calls the one place a real source can hide. Adding
#: 57 lines of noise there to absorb a path change is the worse trade.
#:
#: **What this exclusion did NOT fix, and it was filed rather than absorbed:**
#: `ROADMAP.md` itself was still unread by this guard, so a real source cited
#: there was invisible after the split exactly as it was before. That gap was
#: older than the split and was `OPS-63`, which CLOSED IT - `ROADMAP.md` is read
#: now, and `x.com` and `t.co` therefore reached this guard from the live
#: `ROADMAP.md` rather than from the archive. They were registered in
#: `docs/ECOSYSTEM.md` as fragments-not-sources rather than denylisted, because
#: they are real hosts.
#:
#: **The archive stays excluded, and `OPS-63` did not change that.** Its reason
#: is the one above and is untouched by the scope decision: a document must not
#: acquire or lose a guard by being moved. Note what that now means precisely -
#: the words of every closed roadmap section are unread HERE, and the guard's
#: coverage of them ended when they were archived rather than when the scope
#: widened. That is the trade `OPS-57` chose deliberately and `OPS-63` re-read
#: without reversing.
UNSCANNED_DOCS = frozenset({"docs/ROADMAP_ARCHIVE.md"})

#: The file extensions :func:`scanned_documents` reads. Prose only - see the
#: "reads DOCUMENTS, never CODE" bullet in the module docstring for why a
#: ``*.py`` is deliberately not in this tuple.
SCAN_SUFFIXES = ("md", "txt")


def scanned_documents() -> tuple[str, ...]:
    """Every document this guard reads, as repo-relative POSIX paths.

    **THE SCOPE DECISION, `OPS-63`, 2026-09-08. Stated because "it happens to
    read ``docs/``" was never a scope.** This guard read ``docs/**/*.md`` and
    nothing else from the day it was written, which meant a real source cited in
    ``ROADMAP.md``, ``CLAUDE.md``, ``README.md``, ``WAKEUP_NOTES.md``,
    ``BACKLOG.md``, a lane ledger, a community-standards document, an agent
    prompt under ``.claude/`` or the tracked hand-off was invisible. The scope is
    now EVERY TRACKED DOCUMENT, with one enumerated exclusion:

    * every path ``git ls-files`` reports whose extension is in
      :data:`SCAN_SUFFIXES`, which is 46 documents at the time of writing;
    * PLUS every ``*.md`` present under ``docs/`` whether tracked or not, which
      is exactly what this guard read before `OPS-63` and is kept verbatim so
      that a document written in the current uncommitted wave is covered the
      moment it exists rather than only once it is staged;
    * MINUS :data:`UNSCANNED_DOCS`, which is the single exclusion and carries its
      own reason on that constant.

    **Why an enumerated set of directories was rejected.** The cheaper option was
    "every tracked ``*.md`` except ``.claude/**``", which measured 29 new
    false-positive tokens against 52 for the full set - the 13 agent-prompt files
    under ``.claude/`` are dense with Python call recipes (the merge-gate snippet
    appears verbatim in nine of them) and cite no external source today. It was
    rejected anyway, on this repository's own doctrine that a stored list goes
    stale: see :func:`tracked_paths`, which refuses to write down a filename
    listing for exactly that reason. A scope defined as "every tracked document"
    covers a document nobody has thought of yet; a scope defined as a directory
    exclusion list has to be re-litigated every time someone adds a directory,
    and the next cold session would find the list rather than the reason.

    **What the widening actually cost and bought, measured BEFORE the change**
    because the item required the count first. 52 previously-unread host-shaped
    tokens entered scope. 50 are false positives - dotted Python attribute paths
    (``report.format``, ``before.values``), PowerShell COM and .NET names
    (``WScript.Shell``, ``System.Speech``), Windows binaries (``cmd.exe``), URL
    path tails (``badge.svg``), the game's own log symbols (``Hit.Light``) and a
    sibling project's hand-off filename (``RSC-NEXT-SESSION.txt``). TWO ARE REAL
    EXTERNAL SOURCES that had been cited in a public repository with no register
    row at all: ``docs.github.com``, cited by ``CODE_OF_CONDUCT.md`` and
    ``SECURITY.md``, and ``contributor-covenant.org``, cited by
    ``CODE_OF_CONDUCT.md``. Both were registered while closing `OPS-63`. The
    `OPS-57` archive exclusion was decided against a measured cost of 57 tokens
    and a measured yield of ZERO real sources; this widening is the same trade
    with a non-zero yield, which is why it went the other way.

    Returns paths, not text, so a caller can report WHICH document cited a token.
    """
    listed = {
        path
        for path in tracked_paths()
        if path.rsplit(".", 1)[-1].lower() in SCAN_SUFFIXES and "." in path
    }
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.is_dir():
        for path in docs_dir.rglob("*.md"):
            listed.add(path.relative_to(REPO_ROOT).as_posix())
    return tuple(sorted(listed - UNSCANNED_DOCS))


def cited_hosts(root: Path | None = None) -> dict[str, set[str]]:
    """Map every host-shaped token in scope to the documents citing it.

    With ``root`` omitted - which is how every check in this module calls it -
    the scope is :func:`scanned_documents`. Passing an explicit ``root`` keeps
    the pre-`OPS-63` behaviour of walking ``*.md`` beneath that directory, which
    is how ``tests/test_docguards.py`` plants a token in a temporary tree
    without writing to the append-only real ledger.

    Skips :data:`UNSCANNED_DOCS` on both paths; read that constant for why one
    document is excluded and what the exclusion costs.
    """
    if root is None:
        rels: tuple[str, ...] = scanned_documents()
    else:
        rels = tuple(
            rel
            for rel in sorted(
                path.relative_to(REPO_ROOT).as_posix() for path in root.rglob("*.md")
            )
            if rel not in UNSCANNED_DOCS
        )
    hits: dict[str, set[str]] = {}
    for rel in rels:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for match in HOST_SHAPED.finditer(text):
            hits.setdefault(match.group(0), set()).add(rel)
    return hits


def external_sources(root: Path | None = None) -> dict[str, set[str]]:
    """:func:`cited_hosts` minus this repo's own filenames and the vetted
    non-hosts.

    The filename subtraction runs FIRST, which is the whole of `OPS-44` option
    2: a host-shaped token is treated as a repo-internal filename candidate
    before it is treated as an external source, and only falls through to the
    denylist and then to the register requirement when it is not one.
    """
    return {
        token: files
        for token, files in cited_hosts(root).items()
        if not is_repo_filename(token) and token not in KNOWN_NON_HOSTS
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
    assert raw, "the extractor found no host-shaped tokens in any scanned document"
    assert len(raw) - len(kept) > 0, (
        "the denylist subtracted NOTHING, which means the extractor is no "
        "longer matching the dotted code identifiers these documents are "
        "full of. A "
        "checker that reports zero non-host noise is misconfigured rather "
        "than clean"
    )


def test_a_real_external_source_is_still_caught_when_a_same_named_file_exists():
    """`OPS-44` criterion 2, and the exact `LL-0079` regression.

    The risk `OPS-44` names is that a filename heuristic auto-exempts a real
    two-letter TLD being used as a live external source. ``th.gl`` is the host
    that was actually invisible in 2026-08, so it is the host used here.

    The injected listing is built so the exemption WOULD fire if the boundary
    rule were wrong: ``fourth.gl`` ends with ``th.gl``, and a bare
    ``str.endswith`` would excuse the source on the strength of it. The
    character before the token is ``r``, which is not a name-part boundary, so
    the correct rule refuses. Driven with an injected listing rather than by
    creating files, because a guard that needs a file on disk to prove itself
    is a guard nobody re-runs.
    """
    listing = ("docs/fourth.gl", "tools/fifth.gl", "notes/nth.gl")
    assert not is_repo_filename("th.gl", listing), (
        "th.gl - the LL-0079 host - was auto-exempted by a tracked file that "
        "merely ENDS with it. The boundary rule is not holding, and OPS-44 has "
        "reintroduced the exact failure it promised not to"
    )
    # And the positive control, so this is not passing because nothing matches:
    # the same rule DOES exempt th.gl when a real name part says so.
    assert is_repo_filename("th.gl", ("docs/some_th.gl",))


def test_a_real_external_source_is_still_caught_when_no_such_file_exists():
    """`OPS-44` criterion 2, the other half - no same-named tracked file.

    Against the LIVE listing, not an injected one: these are hosts this
    repository genuinely cites, and if any of them were ever excused the
    register would stop being the single entry point it exists to be.
    """
    for host in ("th.gl", "twitch.tv", "gyldforge.com", "steamcommunity.com"):
        assert not is_repo_filename(host), (
            f"{host!r} was treated as one of this repository's own filenames. "
            "It is an external source and must stay subject to the register "
            "requirement"
        )


def test_an_empty_tracked_listing_exempts_nothing():
    """Fail-CLOSED. A broken listing must make this guard noisier, not quieter.

    If ``git`` is missing, exits non-zero, or prints nothing,
    :func:`tracked_paths` returns an empty tuple. Every token then falls
    through to the denylist and the register requirement, which is the loud
    direction. The opposite - exempting everything when the data source breaks
    - would turn a broken subprocess into a silently green guard, which is the
    failure mode this whole module was written against.

    Driven by passing the empty listing directly, because that is the value the
    failure path produces and the value the caller has to survive.
    """
    for token in ("README.md", "redact.py", "subdirs.py", "th.gl", "CLAUDE.md"):
        assert not is_repo_filename(token, ()), (
            f"{token!r} was exempted against an EMPTY tracked listing. The "
            "check has a default-allow path and a failed git call would "
            "silence this guard"
        )


def test_the_listing_cache_is_keyed_on_the_root_it_asked_about():
    """A process-wide cache with no key made this guard lie for a whole run.

    `OPS-44`, found by the full suite and not by this file alone.
    ``tests/test_docguards.py`` monkeypatches :data:`REPO_ROOT` to a temporary
    tree in order to plant a token, and it runs BEFORE this module. With an
    unkeyed cache the first answer of the run was the empty one that temporary
    tree deserves, and every later call in the real repository inherited it -
    104 of this project's own files were reported as unregistered sources
    while `python -m pytest tests/test_source_register.py` stayed green.

    So the two roots must not share an answer, and the real one must be
    non-empty.
    """
    empty_root = REPO_ROOT / "no" / "such" / "directory"
    assert tracked_paths(empty_root) == (), (
        "a directory that is not a repository answered with paths"
    )
    assert tracked_paths(REPO_ROOT), (
        "the real repository answered with NOTHING right after a non-repository "
        "was asked - the listing cache is shared across roots, and this guard "
        "will report our own filenames as unregistered sources for the rest of "
        "the run"
    )
    # Order reversed, because a cache poisoned in one direction is still poison.
    assert tracked_paths(empty_root) == ()
    assert tracked_paths(REPO_ROOT)


def test_the_boundary_rule_is_what_does_the_work():
    """What the boundary buys, and the case it DELIBERATELY does not block.

    THE DECISION, made explicitly rather than by accident. ``example.py`` IS
    exempted by a tracked ``test_example.py``, because ``_`` is a name-part
    boundary. That is not an oversight and it is not a leak: :data:`HOST_SHAPED`
    excludes ``_`` from a label, so a tracked file named ``test_example.py``
    is emitted BY THIS MODULE'S OWN EXTRACTOR as the token ``example.py``.
    Refusing the exemption would mean the check could never cover the
    truncation case that `OPS-44` exists to solve - ``subdirs.py`` from
    ``tests/test_inbox_watch_subdirs.py`` is the same shape and is the largest
    single family in the denylist this change removed. A rule that cannot
    excuse our own file under the only name the guard ever sees it by is not a
    narrower rule, it is a broken one.

    What the boundary DOES block is the coincidental tail: a token that starts
    part-way through a name part. ``ple.py`` is not excused by
    ``test_example.py``, and ``th.gl`` is not excused by ``fourth.gl``. The
    cost of the decision is bounded and stated in the module docstring: to
    excuse a real source someone must commit a file whose name part IS that
    source's name.
    """
    listing = ("tests/test_example.py", "docs/REPLY_PATHS.md", "README.md")
    # Exact basename equality.
    assert is_repo_filename("README.md", listing)
    # Bounded tail: `_` and the truncation case OPS-44 is about.
    assert is_repo_filename("example.py", listing)
    assert is_repo_filename("PATHS.md", listing)
    # Coincidental tails, starting part-way through a name part, are refused.
    assert not is_repo_filename("ple.py", listing)
    assert not is_repo_filename("THS.md", listing)
    # A token LONGER than any basename is refused rather than crashing.
    assert not is_repo_filename("very_long_test_example.py", listing)


def test_neither_half_of_an_email_address_is_treated_as_a_filename():
    """`LL-0170`, `LL-0173`, `OPS-50`. An address is not two filenames.

    This guard is the only thing in the tree that has ever noticed an operator
    email address reaching a committed document, and it noticed by refusing
    both halves as unregistered hosts. `OPS-44` adds an exemption path, so the
    exemption must be proven not to swallow them.

    No real address appears here or anywhere in this file, and the FIRST
    version of this test broke that rule while asserting it. It built the two
    halves of the operator's real address out of four string literals joined by
    ``+``, and described them as synthetic. They were not: Python joins them
    back together at import time, and a reader joins them by eye. That form is
    invisible to every sweep in this repository INCLUDING the split check
    `LL-0173` had just added, because no half is contiguous in the bytes. It is
    the `LL-0170` defect for the third time in as many days, each time one
    level further down, and each time inside the guard that exists to prevent
    it. The probes below are genuinely unrelated to any real identity.

    The injected listing carries the near-misses a looser rule would fall for:
    a basename ending in the domain half, and one ending in the local half,
    neither preceded by a name-part boundary.
    """
    local = "zaphodbee"
    domain = "somecompany.example"
    near_misses = ("docs/not" + domain, "tools/en" + local + ".py")
    for probe in (local, domain):
        assert not is_repo_filename(probe, near_misses), (
            "half of an email address was treated as one of this repository's "
            "own filenames on the strength of a coincidental tail - the "
            "address would be exempted from the register check and nothing "
            "else in this tree would notice"
        )
        assert not is_repo_filename(probe), (
            "half of an email address matched a REAL tracked filename in this "
            "repository. Rename that file; an address must never be excusable"
        )
        assert probe not in KNOWN_NON_HOSTS, (
            "half of an email address is in the denylist. See LL-0173 - "
            "naming them in order to exclude them is the same defect one "
            "level down"
        )


def test_the_filename_check_covers_our_own_files_and_the_denylist_does_not():
    """`OPS-44` landed: our filenames are checked LIVE, not enumerated.

    The denylist must no longer carry a token that :func:`is_repo_filename`
    already covers. A stale duplicate is dead weight that outlives the file it
    names, and the six waves of exactly that are why this item was filed.
    """
    absorbed = sorted(t for t in KNOWN_NON_HOSTS if is_repo_filename(t))
    assert not absorbed, (
        f"{len(absorbed)} denylist entries are now covered by the live "
        "tracked-file check and should be deleted from KNOWN_NON_HOSTS: "
        + ", ".join(absorbed)
    )
    # Positive control - the check is not answering False to everything.
    assert is_repo_filename("register.py"), (
        "this very file's own tail is not recognised as a tracked filename, "
        "so the live listing is empty or the rule is broken"
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
            f"{len(missing)} host(s) cited in this repository's documents "
            "are ABSENT from the "
            "source register in docs/ECOSYSTEM.md:\n"
            + "\n".join(lines)
            + "\n\nEither add each one to the register with its provenance, "
            "tier and basis, or - if it is not an external source - add it to "
            "KNOWN_NON_HOSTS in this file after looking at it."
        )


def test_the_scan_reads_every_tracked_document_and_names_its_exclusions():
    """`OPS-63` positive control on the SCOPE, and the fail-loud path for it.

    A scope that widens without a control is a scope that might not have widened
    at all, so this names documents that were unreadable by this guard for its
    entire life before `OPS-63` and requires them to be in scope now.

    IT IS ALSO THE FAIL-LOUD MECHANISM for a broken listing. If ``git ls-files``
    fails, is absent or returns nothing, :func:`tracked_paths` returns an empty
    tuple and :func:`scanned_documents` degrades to the pre-`OPS-63`
    ``docs/**/*.md`` walk - silently, because a narrower scan raises nothing and
    finds nothing. Every path asserted below except the ``docs/`` one is outside
    that walk, so the degradation reddens this test instead of passing quietly.
    That is the same fail-closed direction as
    :func:`test_an_empty_tracked_listing_exempts_nothing`, applied to the scope
    rather than to the exemption.
    """
    scanned = set(scanned_documents())
    for rel in (
        "README.md",
        "ROADMAP.md",
        "CLAUDE.md",
        "BACKLOG.md",
        "WAKEUP_NOTES.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "LL-NEXT-SESSION.txt",
        "lanes/safety.LEDGER.md",
        ".claude/commands/done.md",
        "docs/ECOSYSTEM.md",
    ):
        assert rel in scanned, (
            f"{rel} is not in this guard's scope. Either the tracked listing is "
            "empty - in which case every document outside docs/ has silently "
            "stopped being checked - or the OPS-63 scope has been narrowed "
            "without its reason being written into scanned_documents()"
        )
    assert len(scanned) >= 40, (
        f"the scan covers only {len(scanned)} documents, which is implausibly "
        "few for this repository - the listing is probably empty"
    )
    # It reads DOCUMENTS, never code. A stray suffix here would multiply the
    # denylist without ever finding a citation.
    offenders = sorted(
        rel for rel in scanned if rel.rsplit(".", 1)[-1].lower() not in SCAN_SUFFIXES
    )
    assert not offenders, f"non-document paths entered the scan: {offenders}"
    # An exclusion for a document that no longer exists narrows the scope
    # forever and reads as deliberate. Every one must still be a real file.
    for rel in sorted(UNSCANNED_DOCS):
        assert (REPO_ROOT / rel).is_file(), (
            f"{rel} is excluded from the scan by UNSCANNED_DOCS but does not "
            "exist. Delete the exclusion rather than leaving a stale one"
        )
        assert rel not in scanned, f"{rel} is excluded and was scanned anyway"


def test_the_widened_scope_is_actually_being_read():
    """`OPS-63` criterion 4 as a PERMANENT control, not a one-off mutation.

    The mutation proof - plant a fabricated host in a newly-covered document,
    watch this module go red, remove it - was run when `OPS-63` landed and is
    recorded in the ledger. A mutation nobody re-runs proves the scope widened
    once. These assertions prove it is still widened on every run.

    ``docs.github.com`` is the load-bearing case: it is a REAL external source
    that this repository cited in two public community-standards documents with
    no register row at all, and it was invisible until `OPS-63`. Finding it is
    what the widening bought.
    """
    hits = cited_hosts()
    seen_in = hits.get("docs.github.com", set())
    assert {"CODE_OF_CONDUCT.md", "SECURITY.md"} <= seen_in, (
        "the guard no longer sees the citation in CODE_OF_CONDUCT.md and "
        "SECURITY.md that OPS-63 was closed on. Those documents are out of "
        f"scope again. saw: {sorted(seen_in)}"
    )
    for rel in ("ROADMAP.md", "CLAUDE.md", "LL-NEXT-SESSION.txt"):
        assert any(rel in files for files in hits.values()), (
            f"not one host-shaped token was extracted from {rel}, so it is "
            "either unread or empty. Before OPS-63 it was unread"
        )


def test_the_extractor_truncates_at_underscores_deliberately():
    """`OPS-63` criterion 3: the truncation is MEASURED, not unexamined.

    A future session will read :data:`KNOWN_NON_HOSTS`, notice that many entries
    are truncations made at an underscore, and reach for a pattern that permits
    ``_`` inside a label. That was measured on 2026-09-08 and refuted: it retires
    45 of 266 load-bearing entries and introduces 52 new ones, net 267 to 274,
    because `OPS-44` already deleted the 109 whose long form is a tracked
    filename and what remains is gitignored runtime records, frame filenames, a
    sibling's files and dotted module paths with an underscore mid-chain. The
    full numbers are in this module's docstring.

    This test pins the behaviour so the change cannot be made silently. If a
    later session has a better answer, it must delete this test and say why.
    """
    assert HOST_SHAPED.search("inbox_reported.json").group(0) == "reported.json", (
        "the extractor no longer truncates at an underscore. That is a real "
        "decision with a measured cost - read the OPS-63 section of this "
        "module's docstring before keeping the change"
    )
    # And the underscore splits ONE identifier into TWO tokens, which is why
    # `ops.merge` and `gate.verify` are both separate denylist entries.
    assert HOST_SHAPED.findall("ops.merge_gate.verify") == ["ops.merge", "gate.verify"]
    # And the truncated form is what a failure message names, which is why the
    # denylist has to carry the truncation rather than the real identifier.
    assert "reported.json" in KNOWN_NON_HOSTS
    assert "inbox_reported.json" not in KNOWN_NON_HOSTS
