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
only knew the word ``<ACCOUNT>`` would pass cleanly the day someone commits
a path under a different account, which is precisely the day it matters.

HISTORICAL DOCUMENTS ARE FROZEN, NOT EDITED
-------------------------------------------
``docs/LEDGER.md`` is append-only by this project's own rule; ``ROADMAP.md``
item 2d, ``WAKEUP_NOTES.md`` and ``docs/OBSERVED_IDS.md`` quote measurements
that were TRUE ON THEIR DATE, and the quoted path is part of the evidence -
the 2d passage's whole point is that this exact string was found committed into
a contract. Rewriting them would destroy the record this project exists to keep.

They are therefore excluded from the clean-tree requirement and PINNED instead:
each may carry exactly the number of occurrences it carries today, and adding a
new one makes this file red. That closes the hole without editing history. A
pin that merely tolerated the documents would let the count grow forever.

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
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

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
HOME_SHAPED = re.compile(
    r"(?:[A-Za-z]:[\\/]Users[\\/]|/home/|/Users/)"
    r"(?![%$<~])"
    r"[A-Za-z0-9._~-]+"
    r"(?:[\\/]|\b)"
)

#: Documents that RECORD what was true on a date. See the module docstring.
#: Each maps to the number of occurrences it is permitted to carry. Raising a
#: number here is a deliberate act and should be justified in the commit.
FROZEN_HISTORICAL: dict[str, int] = {
    # Append-only by this project's own rule - entries are never edited.
    "docs/LEDGER.md": 2,
    # Item 2d quotes the path found committed into a rendered contract. The
    # string IS the evidence for the finding.
    "ROADMAP.md": 1,
    # Per-cycle historical log, describing what was true THEN.
    "WAKEUP_NOTES.md": 1,
    # Dated observation record - names the capture directory a 2026-08-09
    # frame set was read from.
    "docs/OBSERVED_IDS.md": 1,
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
#: This file's own count is SIX rather than the four planted needles: the two
#: extra are in the comment above, which names the pair it found in
#: ``test_lane_contract.py``. That was measured after the pin was first guessed
#: at four and went red - prose describing a needle is indistinguishable from
#: the needle, which is the same lesson ``docs/LEDGER.md`` records when
#: ``tests/test_no_pii.py`` refused an entry for spelling out its own search
#: shapes.
CONTROL_FIXTURES: dict[str, int] = {
    "tests/test_lane_contract.py": 2,
    "tests/test_no_hardcoded_home_path.py": 6,
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


def findings_in(rel: str) -> list[tuple[int, str]]:
    """Return ``[(line_number, matched_text)]`` for one tracked file."""
    path = REPO_ROOT / rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in HOME_SHAPED.finditer(line):
            hits.append((number, match.group(0)))
    return hits


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


class TestNoLiveSurfaceCarriesAHomePath:
    def test_every_tracked_file_outside_the_frozen_set_is_clean(self):
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
    def test_settings_json_parses_and_carries_no_backslashes(self):
        import json

        text = (REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
        json.loads(text)
        assert "\\" not in text, (
            "CLAUDE.md records that a single-backslash Windows path makes this "
            "file invalid JSON, so nothing parses, no hook registers, and "
            "nothing warns you"
        )

    def test_every_hook_command_names_a_script_that_exists(self):
        import json

        data = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        missing = []
        for entries in data.get("hooks", {}).values():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    for token in command.split():
                        if token.endswith(".py") and not Path(token).is_file():
                            missing.append(command)
        assert not missing, f"hook command names a script that does not exist: {missing}"


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
