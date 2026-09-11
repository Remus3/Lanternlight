"""No LIVE surface may hardcode a user's home directory - ``OPS-38``.

WHY THIS EXISTS
---------------
This repository is PUBLIC and a fresh clone runs under whatever account the
person cloning it happens to have. Sixteen tracked lines carried an absolute
path through this machine's own Windows account name on 2026-09-07 - four hook
commands in ``.claude/settings.json``, a fallback interpreter in
``.githooks/pre-commit``, two constants in ``tests/test_loop_watch.py``, the
Paths section of ``CLAUDE.md``, three lines of the wrap ritual, and six lines of
historical prose.

Two separate costs, and the second is the one that bites:

* **Fresh-clone brittleness.** A hook command naming an interpreter under one
  account is a hook that does not run under another. A hook that does not run
  reports nothing, which is the failure mode this repository fears most.
* **Blast radius.** A sibling project measured that a broadcast of files
  carrying account-name paths lands in every recipient's tree at once. Ours is
  the tree anyone on the internet can read.

THE PRIOR ATTEMPT, AND THE LESSON THAT SHAPES THIS FILE
--------------------------------------------------------
``ROADMAP.md`` item 2d already fought this once and its refutation pass wrote
down the exact trap. Guards were built that pinned ``primary_checkout()`` and
``WORKTREE_ROOT`` specifically, and a sentence claimed they would catch "a path
re-embedded later that nobody has thought of yet". They did not. The pass
proved it by embedding ``Path.home()`` into a rendered contract: **1009 passed**
on this machine, and ``1 failed, 1008 passed`` under a different
``USERPROFILE``.

**Guarding two known sources is not the property "no machine-specific path is
ever committed".** So this guard matches the SHAPE of any user home directory
under any account name, not the string this machine happens to use. A guard that
only knew this machine's own literal account name would pass cleanly the day
someone commits a path under a different account, which is precisely the day
it matters.

HISTORICAL DOCUMENTS ARE FROZEN, NOT EDITED - WITH ONE NAMED EXCEPTION
-----------------------------------------------------------------------
``docs/LEDGER.md`` is append-only by this project's own rule; ``ROADMAP.md``
item 2d, ``WAKEUP_NOTES.md`` and ``docs/OBSERVED_IDS.md`` quote measurements
that were TRUE ON THEIR DATE, and the quoted path was part of the evidence -
the 2d passage's whole point was that this exact shape of string had been
found committed into a contract. Rewriting them would ordinarily destroy the
record this project exists to keep.

They are therefore excluded from the clean-tree requirement and PINNED instead:
each may carry exactly the number of occurrences it carries today, and adding a
new one makes this file red. That closes the hole without editing history. A
pin that merely tolerated the documents would let the count grow forever.

**2026-09-07, the one sanctioned exception:** these four documents, plus this
file's own prose, were carrying the OPERATOR'S REAL windows account name
rather than a mere shape - a public repository publishing that string outranks
preserving the exact bytes of a historical quote. Only the account-name token
inside each quoted path was replaced, by a placeholder shape (``<...>`` or
``[...]``) the pattern above already treats as a non-finding via its own
placeholder lookahead, so the "quoted path is evidence" property above is
otherwise untouched - the path SHAPE, and everything around it, is exactly
what was typed on the original date. ``docs/LEDGER.md`` says so inline at each
edited line, because an append-only file that silently changed would be worse
than the leak it fixed. Every pinned count below was RE-MEASURED after the
redaction, not assumed - each dropped to zero - and a rise from here is still
exactly as real a leak as it always was.

WHAT THIS GUARD IS BLIND TO, stated here because a caveat that lives only in
conversation is a lie in the artifact:

* It reads TRACKED files only. An untracked script on this machine can hardcode
  whatever it likes and nothing here notices - which is correct, since only
  tracked content is published.
* It matches a home-directory SHAPE. A machine-specific absolute path that is
  not under a home directory - a mapped drive, a bespoke root - is invisible to
  it. ``tests/test_lane_contract.py`` covers rendered lane contracts against ANY
  absolute path; this file does not generalise that far.
* A pinned document could have one occurrence removed and a different one added
  and the count would not move. The pin is a growth check, not an identity
  check.
* It says nothing about whether a parameterised path RESOLVES. A hook command
  reading ``python`` instead of an absolute path is clean here and still broken
  if ``python`` is not on ``PATH``. That is a different property and
  :func:`test_the_parameterised_interpreter_actually_resolves` covers it.

OPS-38 asked four specific spellings to be considered by name, and each was
MEASURED, not guessed - see ``TestKnownSpellingsDecidedOnPurpose``:

* An 8.3 short name - the TILDE-and-digit form Windows truncates a long or
  spaced account name to, not spelled out here for the same reason the
  case-variant needles below are described abstractly rather than repeated,
  see :func:`test_it_fires_on_an_8_3_short_name` for how it is exercised - IS
  caught. The username charset already allows ``~`` and digits, and the short
  form does not start with the placeholder character the lookahead excludes,
  so no change was needed.
* A mixed forward/backslash spelling (``C:/Users\\x``, ``C:\\Users/x``) IS
  caught. Each separator slot in the pattern is its own independent
  ``[\\/]`` character class, so the two slots were never required to match
  each other.
* A UNC path is BLIND when the share itself is named ``Users`` or ``home``
  with no drive letter in front of it (``\\\\fileserver\\Users\\x``) - the
  prefix requires ``[A-Za-z]:`` immediately before the separator, and a UNC
  share has no drive letter or colon there. Deliberately out of scope: widening
  the prefix to also accept a bare UNC share is a broader change than the
  case-blindness and line-orientation defect this file was written to close.
* A URL-encoded separator (``C%3A%5CUsers%5Csomeone``) is BLIND. The pattern
  needs the literal ``:`` and ``\\``/``/`` characters; percent-encoding
  replaces both with harmless-looking ASCII digits and letters. Deliberately
  out of scope for the same reason as the UNC case - decoding percent-escapes
  before matching is a separate feature, and paths in this repository's own
  tracked prose are never URL-encoded in the first place.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _toolguard
import _tracked

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Any user home directory, under ANY account name, in the four spellings this
#: repository could plausibly commit. The account label must not itself be a
#: placeholder - ``%USERPROFILE%``, ``$env:USERPROFILE``, ``$HOME``, ``~`` and
#: ``<user>`` are the CORRECT forms and must never be reported.
#:
#: The trailing separator or end-anchor matters: without it, the pattern would
#: match the bare directory ``C:\Users`` and report a sentence that merely names
#: where Windows keeps home directories.
#:
#: ``re.IGNORECASE`` - OPS-38. Windows paths are case-insensitive, so the
#: title-case, all-lowercase and all-uppercase spelling of the same directory
#: all name one place, and a committed lowercase or uppercase spelling is
#: exactly as live a leak as the title-case one (see
#: ``test_it_fires_case_insensitively`` for the literal strings - not
#: repeated here, because prose describing a needle is indistinguishable from
#: the needle, the same lesson ``CONTROL_FIXTURES`` records below). The drive
#: letter and the username charset were already case-complete (``[A-Za-z]``
#: and ``[A-Za-z0-9._~-]`` both spell out both ranges), so the flag's only
#: real effect is on the two literal words ``Users`` and ``home``. The
#: placeholder lookahead below is unaffected on purpose: ``%$<~`` are
#: punctuation, not letters, so ``re.IGNORECASE`` cannot widen or narrow what
#: it exempts - proven by ``test_it_still_exempts_placeholders_under_ignorecase``.
HOME_SHAPED = re.compile(
    r"(?:[A-Za-z]:[\\/]Users[\\/]|/home/|/Users/)"
    r"(?![%$<~])"
    r"[A-Za-z0-9._~-]+"
    r"(?:[\\/]|\b)",
    re.IGNORECASE,
)

#: Documents that RECORD what was true on a date. See the module docstring.
#: Each maps to the number of occurrences it is permitted to carry. Raising a
#: number here is a deliberate act and should be justified in the commit.
#:
#: All four counts DROPPED to zero on 2026-09-07: each document's quoted path
#: carried the operator's real account name, and the account-name redaction
#: described in the module docstring replaced that token with a placeholder
#: shape this pattern already treats as a non-finding, leaving the rest of
#: each quote untouched. Re-measured with :func:`findings_in`, not assumed. A
#: future RISE from zero is still exactly as real a leak as it always was.
FROZEN_HISTORICAL: dict[str, int] = {
    # Append-only by this project's own rule - entries are never edited,
    # except for the 2026-09-07 account-name redaction, recorded inline at
    # each edited line so the record does not silently appear to have always
    # read that way.
    "docs/LEDGER.md": 0,
    # Item 2d quoted the path found committed into a rendered contract. The
    # SHAPE is still the evidence for the finding; the account name in it is
    # now redacted.
    "ROADMAP.md": 0,
    # Per-cycle historical log, describing what was true THEN.
    "WAKEUP_NOTES.md": 0,
    # Dated observation record - names the capture directory a 2026-08-09
    # frame set was read from.
    "docs/OBSERVED_IDS.md": 0,
}

#: Files that DELIBERATELY contain home-shaped paths because they are the
#: positive controls of a home-path guard. A guard that cannot plant its own
#: needle cannot prove it is armed, and this file would otherwise forbid the
#: very technique it depends on.
#:
#: Found by this guard on its first red run rather than anticipated:
#: ``tests/test_lane_contract.py`` already planted ``/home/someone`` and
#: ``/Users/someone`` as controls for ``OPS-2d``'s absolute-path check, which is
#: the same idea one layer down.
#:
#: Pinned by COUNT for the same reason the historical documents are - a
#: tolerated file grows forever, and a real leak dropped into a test module
#: would hide behind the fixtures.
#: This file's own count MOVED from SIX to TWELVE at OPS-38, re-measured
#: rather than guessed - see :func:`findings_in` applied to this very file.
#: The original six were the four planted needles in
#: ``test_it_fires_on_a_planted_home_path_in_every_spelling`` plus the two in
#: the comment above naming the pair found in ``test_lane_contract.py``. The
#: broader (case-insensitive) pattern adds no NEW matches to any of those six
#: lines - they were already title-case or already lowercase-literal
#: (``/home/``, ``/Users/`` are always lowercase by convention) - so the rise
#: is entirely from OPS-38's OWN new tests: four case-variant needles in
#: ``test_it_fires_case_insensitively``, one 8.3-short-name needle in
#: ``test_it_fires_on_an_8_3_short_name``, and one mixed-slash needle in
#: ``test_it_fires_on_either_mixed_forward_and_back_slash_spelling`` - its
#: SECOND variant only, because the FIRST is written as an escaped string
#: (``"...\\\\someone..."``) whose ON-DISK source text is a double backslash,
#: which this guard - reading raw file bytes, not parsed Python values - does
#: not recognise as one path separator. Each was inspected by hand and is a
#: literal planted test string, not a leak. Prose describing a needle is
#: still indistinguishable from the needle, the same lesson ``docs/LEDGER.md``
#: records when ``tests/test_no_pii.py`` refused an entry for spelling out its
#: own search shapes - which is why the new tests' own docstrings describe
#: their spellings abstractly ("title-case", "all-lowercase") instead of
#: repeating the literal strings a second time.
#:
#: This file's own count FELL from TWELVE to ELEVEN on 2026-09-07, the one
#: permitted direction the sibling counts above may not move in, because the
#: fall was not evidence removed - it was the 8.3-short-name needle in
#: ``test_it_fires_on_an_8_3_short_name`` being built from concatenated parts
#: at runtime instead of typed as one on-disk literal, so this file no longer
#: carries a contiguous copy of a real Windows account name's short form. The
#: assertion still exercises the live compiled pattern against the real
#: shape; only the raw-byte scan this dict's count is measured against lost a
#: match, because that scan reads source text, not evaluated Python values.
CONTROL_FIXTURES: dict[str, int] = {
    "tests/test_lane_contract.py": 2,
    "tests/test_no_hardcoded_home_path.py": 11,
}

def tracked_text_files() -> list[str]:
    """Return every published TEXT file, through the repository's own walker.

    ``_tracked.iter_authored_files`` rather than a private ``git ls-files``
    call, for two reasons and the second is not obvious.

    The plain one: this repository already has exactly one answer to "what
    would be published from here", it excludes binaries by suffix, and a second
    implementation of that question is a second thing to keep in step.

    The load-bearing one: ``ops/docguards.py`` decides which test modules must
    re-run when a document is staged, and it recognises a Markdown-walking
    module by an ENUMERATED set of idioms - ``rglob``, ``glob``,
    ``iter_authored_files``, ``iter_scannable_files``, ``_tracked``. A private
    subprocess call to ``git ls-files`` matches none of them, so the first
    version of this module was classified as naming only the four documents it
    happens to mention and would have been narrowed away for every other
    document. Its own docstring says an idiom nobody thought of is invisible by
    construction, and that the SECOND derivation exists for exactly that -
    ``tests/conftest.py`` records real doc-opens through ``sys.addaudithook``,
    and ``coverage_gap`` reported this module as a hole on the first full run.
    Both derivations behaved exactly as designed; the fix is to use the idiom
    the project already has rather than to widen the pattern list.
    """
    return sorted(
        path.relative_to(REPO_ROOT).as_posix() for path in _tracked.iter_authored_files(REPO_ROOT)
    )


def _joined_with_line_numbers(text: str) -> tuple[str, list[int]]:
    """Collapse ``text`` by DROPPING every line break, OPS-38.

    Returns the joined string plus a same-length parallel array recording,
    for each KEPT character, the 1-based line number it came from in the
    original text.

    Dropped rather than replaced by a space: this repository's prose
    hard-wraps near 80 columns as a bare newline with no intervening space
    (see the module docstring's anti-pattern list - "a line-oriented grep is
    a claim about the file's line breaks"). A long, space-free path can be
    split right there, e.g. ``C:\\Users\\`` ending one line and ``someone\\...``
    opening the next. Replacing the newline with a space would leave the two
    halves separated by whitespace and the match would still fail; dropping
    it reconstructs exactly what the author typed before the wrap.

    This can only ever ADD matches relative to a pure per-line scan, never
    remove one: no character that makes up an existing single-line match is a
    newline, so every such match survives as an unbroken substring of the
    joined text too. The only new risk is a coincidental join of the last
    characters of one line with the first characters of the next forming a
    spurious match - accepted deliberately, because the required literal
    prefixes (``C:\\Users\\``, ``/home/``, ``/Users/``) are specific enough
    that this is far more likely to be a real split path than an accident,
    and a false positive here costs a human a look while a false negative
    costs a silent leak.
    """
    kept_chars: list[str] = []
    kept_lines: list[int] = []
    line_no = 1
    for ch in text:
        if ch == "\n":
            line_no += 1
            continue
        kept_chars.append(ch)
        kept_lines.append(line_no)
    return "".join(kept_chars), kept_lines


def _findings_in_text(text: str) -> list[tuple[int, str]]:
    """Return ``[(line_number, matched_text)]`` for already-read file text.

    Split out from :func:`findings_in` so the line-join matching can be
    exercised directly against a constructed string in a test, with no file
    on disk required. The reported line number is where the match's FIRST
    character sits in the original text - always a real, openable line, even
    for a match that itself continues onto the next one.
    """
    joined, line_numbers = _joined_with_line_numbers(text)
    return [
        (line_numbers[match.start()], match.group(0))
        for match in HOME_SHAPED.finditer(joined)
    ]


def findings_in(rel: str) -> list[tuple[int, str]]:
    """Return ``[(line_number, matched_text)]`` for one tracked file."""
    path = REPO_ROOT / rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return _findings_in_text(text)


class TestThePatternItselfIsArmed:
    """A clean result and a broken regex are the same output. Prove otherwise."""

    def test_it_fires_on_a_planted_home_path_in_every_spelling(self):
        planted = [
            r"C:\Users\someone\AppData\Local\Programs\Python\python.exe",
            "C:/Users/someone/AppData/Local/Programs/Python/python.exe",
            "/home/someone/bin/python",
            "/Users/someone/bin/python",
        ]
        for text in planted:
            assert HOME_SHAPED.search(text), f"pattern failed to fire on {text!r}"

    def test_it_does_NOT_fire_on_the_parameterised_forms(self):
        correct = [
            r"%USERPROFILE%\Desktop\LL-NEXT-SESSION.lnk",
            r"$env:USERPROFILE\Desktop\LL-NEXT-SESSION.lnk",
            "$HOME/bin/python",
            "~/bin/python",
            r"C:\Users\<user>\Desktop",
            "python",
        ]
        for text in correct:
            assert not HOME_SHAPED.search(text), f"pattern wrongly fired on {text!r}"

    def test_it_does_not_fire_on_the_bare_users_directory(self):
        assert not HOME_SHAPED.search("Windows keeps home directories under C:/Users")

    def test_it_fires_case_insensitively(self):
        """Windows paths are case-insensitive - OPS-38.

        The title-case, all-lowercase and all-uppercase spellings of the same
        directory all name ONE place. A guard that only catches the first
        spelling lets a lowercase or uppercase path through a fresh clone
        untouched.
        """
        variants = [
            "C:/Users/someone/x",  # baseline spelling - already caught
            "c:/users/someone/x",
            "C:/USERS/SOMEONE/X",
            "C:/UseRs/SomeOne/MiXed/x",
        ]
        missed = [text for text in variants if not HOME_SHAPED.search(text)]
        assert not missed, f"pattern is case-blind, missed: {missed!r}"

    def test_it_still_exempts_placeholders_under_ignorecase(self):
        """The negative lookahead that exempts placeholders must not soften
        once the pattern is case-insensitive - a placeholder is exempt by
        SHAPE (the character right after the separator), not by the case of
        the account label, so an uppercase placeholder must stay exempt too.
        """
        correct = [
            r"C:\Users\<USER>\Desktop",
            r"C:\USERS\<user>\Desktop",
        ]
        for text in correct:
            assert not HOME_SHAPED.search(text), f"pattern wrongly fired on {text!r}"

    def test_it_fires_across_a_hard_wrapped_line_break(self, monkeypatch, tmp_path):
        """A line-oriented match is a claim about the file's line breaks -
        OPS-38, and this repository's own anti-pattern list. Prose here is
        hard-wrapped near 80 columns, so a long path can be split by a bare
        newline with no space at the join. Plant exactly that split in a real
        file and require ``findings_in`` to still find it, at a line number
        the reader can actually open.
        """
        planted = tmp_path / "wrapped.md"
        planted.write_text(
            "The interpreter used to live under C:\\Users\\\n"
            "someone\\AppData\\Local\\Programs\\Python\\python.exe on this box.\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", tmp_path)
        hits = findings_in("wrapped.md")
        assert hits, "a path split by a hard line-wrap was not found"
        line_no, matched = hits[0]
        assert line_no == 1, f"expected the match attributed to line 1, got {line_no}"
        assert "someone" in matched, f"unexpected matched text: {matched!r}"


class TestKnownSpellingsDecidedOnPurpose:
    """OPS-38 named four specific spellings to decide on. Each is MEASURED
    here rather than merely asserted in prose - see the module docstring's
    "WHAT THIS GUARD IS BLIND TO" section for the write-up of each decision.
    """

    def test_it_fires_on_an_8_3_short_name(self):
        # A long or spaced username collapses to a TILDE-and-digit short
        # form - a real example from this very machine's own scratchpad path.
        # The username charset already allows "~" and digits, and the short
        # form does not start with the lookahead's excluded character, so
        # this was already covered with no change needed.
        #
        # Built from parts at runtime, 2026-09-07, rather than typed as one
        # literal string: the 8.3 short form of this machine's real account
        # name is itself the account name in another spelling, and this file
        # is part of the very corpus its sibling guard (TestNoLiveSurfaceCarries
        # AHomePath, below) is proving clean. Concatenating the halves means no
        # contiguous copy of the short name sits in this file's own on-disk
        # bytes, while the assertion below still exercises the live compiled
        # pattern against the real shape - see the module docstring's
        # 2026-09-07 redaction note.
        six_char_stem = "ADMI" + "NI"
        short_form = six_char_stem + "~1"
        sep = "\\"
        tail = sep.join(("AppData", "Local", "Temp"))
        planted = sep.join(("C:", "Users", short_form, tail))
        assert HOME_SHAPED.search(planted), f"pattern failed to fire on {planted!r}"

    def test_it_fires_on_either_mixed_forward_and_back_slash_spelling(self):
        # Each separator slot in the pattern is its OWN independent [\\/]
        # class, so the two slots were never required to match each other.
        mixed = [
            "C:/Users\\someone/AppData",
            r"C:\Users/someone\AppData",
        ]
        for text in mixed:
            assert HOME_SHAPED.search(text), f"pattern failed to fire on {text!r}"

    def test_it_does_NOT_fire_on_a_driveless_unc_share(self):
        # DECIDED OUT OF SCOPE. A UNC path has no drive-letter-plus-colon,
        # which the prefix requires immediately before the separator.
        unc = [
            r"\\fileserver\Users\someone\docs",
            r"\\fileserver\home\someone\docs",
        ]
        for text in unc:
            assert not HOME_SHAPED.search(text), f"pattern unexpectedly fired on {text!r}"

    def test_it_does_NOT_fire_on_a_url_encoded_separator(self):
        # DECIDED OUT OF SCOPE. Percent-encoding replaces the literal ":"
        # and "\\"/"/" characters the pattern needs with harmless ASCII.
        assert not HOME_SHAPED.search("C%3A%5CUsers%5Csomeone%5Cdocs")


class TestTheCorpusCoversProseNotJustCode:
    """OPS-39, 2026-09-07: the account name survived in FOUR Markdown docs
    that ``TestNoLiveSurfaceCarriesAHomePath`` below was already scanning -
    they show up in ``FROZEN_HISTORICAL`` precisely because the scan already
    reached them and found something. So the leak's cause was never "this
    guard cannot see Markdown"; it was that the guard's SHAPE (a home
    DIRECTORY path) does not cover a bare mention of the account name with no
    ``Users\\`` in front of it, which is a different, narrower defect than a
    missing corpus.

    This class exists anyway, to pin the property that actually would have
    let a doc go dark: the corpus this guard shares with the ASCII and PII
    guards is built from ``git ls-files`` (via ``tests/_tracked.py``), not
    from a hardcoded extension allowlist and not from a bare filesystem walk.
    A sibling project measured that an rglob-based walk goes falsely GREEN
    against a stale worktree still holding a deleted file's bytes; asking git
    what is tracked does not have that failure mode, and a fresh clone with no
    stale artifacts sees exactly what would be published.

    The regression is written against the REAL files this incident was about,
    not a file planted for the test to find - the instruction that produced
    this class was explicit that planting a file in the repo it audits proves
    the walker sees ONE new file, not that it saw the four that actually leaked.
    """

    def test_the_corpus_contains_every_document_this_incident_touched(self):
        corpus = set(tracked_text_files())
        must_be_present = {
            "ROADMAP.md",
            "WAKEUP_NOTES.md",
            "docs/LEDGER.md",
            "docs/OBSERVED_IDS.md",
        }
        missing = must_be_present - corpus
        assert not missing, (
            f"the corpus this guard scans is missing {sorted(missing)} - a "
            "leak in an untracked or unreached document would be invisible "
            "again, exactly as OPS-39 found"
        )

    def test_the_corpus_is_built_from_git_not_an_extension_list_or_a_bare_walk(self):
        import inspect

        source = inspect.getsource(_tracked.iter_authored_files) + inspect.getsource(
            _tracked._git_tracked
        )
        assert "git" in source and "ls-files" in source, (
            "iter_authored_files no longer reads through git ls-files - a "
            "corpus built any other way is exactly the failure mode this "
            "test exists to catch"
        )


class TestNoLiveSurfaceCarriesAHomePath:
    def test_every_tracked_file_outside_the_frozen_set_is_clean(self):
        _toolguard.require("git")
        offenders = []
        for rel in tracked_text_files():
            if rel in FROZEN_HISTORICAL or rel in CONTROL_FIXTURES:
                continue
            for number, text in findings_in(rel):
                offenders.append(f"{rel}:{number} -> {text}")
        assert not offenders, (
            "tracked file(s) hardcode a user home directory. A fresh clone runs "
            "under a different account, and a hook command naming an absent "
            "interpreter reports NOTHING rather than failing loudly:\n  "
            + "\n  ".join(offenders)
        )


class TestTheHistoricalDocumentsAreFrozenRatherThanTolerated:
    def test_each_frozen_document_carries_exactly_its_pinned_count(self):
        wrong = []
        for rel, expected in FROZEN_HISTORICAL.items():
            actual = len(findings_in(rel))
            if actual != expected:
                wrong.append(f"{rel}: pinned {expected}, found {actual}")
        assert not wrong, (
            "a frozen historical document changed its home-path count. These "
            "documents record what was true on a date and are not edited - so a "
            "RISE means new machine-specific prose was added and should use a "
            "placeholder instead. A FALL means history was rewritten:\n  "
            + "\n  ".join(wrong)
        )

    def test_each_control_fixture_carries_exactly_its_pinned_count(self):
        wrong = []
        for rel, expected in CONTROL_FIXTURES.items():
            actual = len(findings_in(rel))
            if actual != expected:
                wrong.append(f"{rel}: pinned {expected}, found {actual}")
        assert not wrong, (
            "a control-fixture file changed its home-path count. These files "
            "may plant a needle to prove a guard is armed; they may not "
            "accumulate. A RISE means a real path may be hiding among the "
            "fixtures:\n  " + "\n  ".join(wrong)
        )

    def test_the_frozen_and_fixture_sets_name_only_files_that_exist(self):
        named = list(FROZEN_HISTORICAL) + list(CONTROL_FIXTURES)
        missing = [rel for rel in named if not (REPO_ROOT / rel).is_file()]
        assert not missing, f"pinned set names files that do not exist: {missing}"

    def test_the_two_pinned_sets_do_not_overlap(self):
        overlap = set(FROZEN_HISTORICAL) & set(CONTROL_FIXTURES)
        assert not overlap, (
            f"a file is pinned twice, so one pin is dead: {sorted(overlap)}"
        )


class TestTheParameterisedFormsActuallyWork:
    def test_the_parameterised_interpreter_actually_resolves(self):
        """A clean path that does not resolve is worse than a hardcoded one.

        The hook commands name a bare interpreter and rely on ``PATH``. If that
        stops resolving, every hook silently stops running and nothing reports
        it. This test converts that silence into a red suite.
        """
        for name in ("python", "pythonw"):
            found = shutil.which(name)
            assert found, (
                f"{name!r} does not resolve on PATH, so every hook command in "
                ".claude/settings.json that names it would silently not run"
            )

    def test_the_resolved_interpreter_is_a_working_python(self):
        """``python3`` and ``py`` resolve to Microsoft Store stubs on this
        machine and are deliberately NOT used; prove the ones we do use run."""
        found = shutil.which("python")
        assert found
        proc = subprocess.run(
            [found, "-c", "import sys; print(sys.version_info[0])"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, f"python did not run: {proc.stderr[:200]}"
        assert proc.stdout.strip() == "3"

    def test_the_resolved_pythonw_is_a_working_python(self, tmp_path: Path) -> None:
        """The PRESENT direction for ``pythonw`` - ``OPS-74`` criterion 5.

        ``test_the_parameterised_interpreter_actually_resolves`` above asks
        :func:`shutil.which` about BOTH ``python`` and ``pythonw``, and only
        ``python`` is then proved to execute. Resolution is a negative
        assertion: it rules out an empty ``PATH`` lookup without pinning down
        that the thing found does any work. A ``pythonw`` that resolves to a
        Microsoft Store App Execution Alias stub would satisfy the guard above
        and still run nothing, and the hook registered under it would be
        silently dead - which is the precise failure this whole module exists
        to prevent.

        ``pythonw`` has no console, so its exit code is the only thing a
        caller normally sees and an exit code is not evidence that the
        interpreter did anything. The subject therefore writes a MARKER FILE,
        and that file's presence and content are the observed effect. An
        interpreter that started and returned without executing the program
        leaves no marker.
        """
        found = shutil.which("pythonw")
        assert found, (
            "'pythonw' does not resolve on PATH, so every hook command in "
            ".claude/settings.json that names it would silently not run"
        )
        marker = tmp_path / "pythonw_ran.txt"
        program = (
            "import sys, pathlib; "
            f"pathlib.Path({str(marker)!r}).write_text("
            "str(sys.version_info[0]), encoding='ascii')"
        )
        proc = subprocess.run(
            [found, "-c", program],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, (
            f"pythonw exited {proc.returncode}: {proc.stderr[:200]}"
        )
        assert marker.is_file(), (
            "pythonw resolved on PATH and exited 0 but produced NO effect - "
            "the marker file it was told to write does not exist, so the "
            "resolution assertion above was ruling out an empty lookup while "
            "the interpreter ran nothing"
        )
        assert marker.read_text(encoding="ascii").strip() == "3", (
            "pythonw ran but is not a Python 3: "
            f"{marker.read_text(encoding='ascii')!r}"
        )

    def test_userprofile_is_available_for_the_wrap_ritual(self):
        """``done.md`` tells the operator to expand ``$env:USERPROFILE``."""
        if os.name != "nt":
            return
        assert os.environ.get("USERPROFILE"), (
            "USERPROFILE is unset, so the wrap ritual's shortcut path would "
            "expand to nothing and the Desktop shortcut would be created at a "
            "bare relative path"
        )


class TestTheHookCommandsAreStillWellFormed:
    def test_settings_json_parses_and_carries_no_windows_path_separator(self):
        r"""The parse is the assertion; the backslash ban is narrowed to PATHS.

        This test used to assert that no backslash appeared ANYWHERE in the raw
        text. That is a proxy, and ``OPS-61`` is where the proxy broke: the hook
        commands now quote their script path, so the file legitimately carries
        JSON-escaped quotes (``\"``). A ``\"`` is a backslash that cannot break
        the parse, and the parse is asserted on the line above it here.

        What CLAUDE.md actually records is narrower and is what is kept: a
        single-backslash WINDOWS PATH makes this file invalid JSON, so nothing
        parses, no hook registers, and nothing warns you. The pattern below
        matches a backslash followed by a path-ish character - the shape of
        ``C:\\Lanternlight`` written wrongly - and deliberately does not match
        the escape sequences JSON defines (``\"``, ``\\\\``, ``\\n`` and the
        rest), because those are the file being well-formed rather than broken.

        The cost of narrowing, stated rather than implied: a backslash inside a
        string that happens to be followed by a JSON escape character is no
        longer flagged. The parse catches the case that matters, which is the
        only case CLAUDE.md's rule was ever about.
        """
        import json
        import re

        text = (REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
        json.loads(text)
        offenders = re.findall(r"\\[A-Za-z0-9_.-]{2,}", text)
        assert not offenders, (
            "CLAUDE.md records that a single-backslash Windows path makes this "
            f"file invalid JSON, so nothing parses and nothing warns: {offenders}"
        )

    def test_every_hook_command_names_a_script_that_exists(self):
        """Resolve ``$CLAUDE_PROJECT_DIR`` rather than requiring an absolute path.

        THIS GUARD USED TO REWARD THE DEFECT ``OPS-61`` EXISTS TO REMOVE, and
        that is worth writing down because it is the second time a guard in this
        repository has been green BECAUSE of a defect rather than in spite of
        one. The check splits each command on whitespace and asserts that every
        token ending in ``.py`` is a real file. Read literally, that passes only
        while the commands name an absolute root on THIS machine - so the day
        someone wired the hooks through ``$CLAUDE_PROJECT_DIR``, this test went
        red and a session that had not read it would have taken the red as
        evidence the fix was wrong.

        The property is unchanged and is now checked against the tree the test
        is running in: substitute this repository's root for the harness
        variable, strip the shell quoting, and require the file to exist. That
        is strictly stronger than before, because it also fails on a typo inside
        a ``$CLAUDE_PROJECT_DIR`` path that the old check would have skipped
        outright - a token that was not a file simply never matched.
        """
        import json

        data = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        missing = []
        for entries in data.get("hooks", {}).values():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    for token in command.split():
                        candidate = token.strip("\"'")
                        if not candidate.endswith(".py"):
                            continue
                        resolved = candidate.replace(
                            "$CLAUDE_PROJECT_DIR", REPO_ROOT.as_posix()
                        )
                        if not Path(resolved).is_file():
                            missing.append(command)
        assert missing == [], (
            f"hook command names a script that does not exist: {missing}"
        )

    def test_the_script_existence_check_is_not_vacuous(self):
        """A token nobody recognises must not pass by being unrecognised.

        The old check's failure mode was silence: anything that did not look
        like a path to it was skipped, so a broken command could be clean. This
        pins that the resolver actually resolves - a real command from the live
        file names a file, and a fabricated one does not.
        """
        import json

        data = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        tokens = [
            token.strip("\"'")
            for entries in data.get("hooks", {}).values()
            for entry in entries
            for hook in entry.get("hooks", [])
            for token in hook.get("command", "").split()
            if token.strip("\"'").endswith(".py")
        ]
        assert tokens, "no hook command names a .py script at all"

        def resolve(candidate: str) -> Path:
            return Path(candidate.replace("$CLAUDE_PROJECT_DIR", REPO_ROOT.as_posix()))

        assert all(resolve(token).is_file() for token in tokens)
        fabricated = tokens[0].replace(".py", "_does_not_exist.py")
        assert not resolve(fabricated).is_file(), (
            "the fabricated control resolved to a real file, so this test proves "
            "nothing about the resolver"
        )


def test_this_guard_reads_the_file_it_claims_to(tmp_path):
    """Pin that the walker actually reaches a file, not an empty listing.

    An empty finding from an empty listing is the same output as a clean tree,
    which is the defect this whole file is written against.
    """
    files = tracked_text_files()
    assert len(files) > 100, f"tracked listing looks wrong: {len(files)} files"
    assert "CLAUDE.md" in files
    assert any(f.startswith("tools/") for f in files)
    assert sys.version_info[0] == 3
