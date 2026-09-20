"""The tracked record of where this repository's chat dialect is defined.

ROADMAP ``OPS-36`` criterion 4, the half that names the caveman-wiring clause.
The charter that this project's operator ruled ADOPT AS WRITTEN on 2026-09-07
carries, in its fourth version, a clause about wiring the CAVEMAN ULTRA dialect
into a session. Criterion 4 asks that the clause be "either implemented with a
test or recorded as already satisfied, naming the file".

WHY A TEST AND NOT A SENTENCE. The clause IS already satisfied here - every
session reads ``CLAUDE.md`` and ``CLAUDE.md`` states the dialect - but at the
moment this module was written, a case-insensitive search of the TRACKED tree
for the term returned only ``CLAUDE.md``'s own rule, the ``ROADMAP.md`` lines
that are the problem statement, and the ledger entry recording the problem.
"It fires by construction" is not a record. A record is a tracked file a cold
session can find, and a record with no guard over it is a paragraph that dies
the next time somebody tidies a document.

WHAT IS GUARDED, and each arm is one property criterion 4's acceptance names:

* the term is carried by at least one tracked file that is NOT the problem
  statement and is not the rule itself;
* that record names ``CLAUDE.md`` as the governing definition;
* it states that no user-level command is relied on - the advertised caveman
  command on this machine lives OUTSIDE this repository, so a fresh clone under
  a different account must lose nothing by not having it;
* it answers the charter clause with a DECLINE rather than an adoption, which
  is a session decision under THE ONE ASYMMETRY in ``CLAUDE.md`` and is not an
  adoption a session may not make;
* it carries no absolute path and no account-shaped path, because the one thing
  the record must NOT do is write the user-level command's location into a
  tracked file - that path carries an account name;
* and the pointer is not dangling: ``CLAUDE.md`` still carries the definition
  the record points at.

WHAT THIS IS BLIND TO, stated here because a caveat that lives only in a chat
log is a lie in the artifact:

* It asserts PROSE, so a record rewritten in different words goes red even
  though the fact survived. That is the intended trade: the alternative is a
  presence-only check, and a presence-only check is green over a record that
  says the opposite of what it should.
* It does not read the charter note. The notes under ``moon_sync_inbox/`` are
  gitignored MAIL and are not vendored, so nothing here can prove the clause
  was transcribed faithfully. That is the item's job, not this module's.
* ``NOT_A_RECORD`` is enumerated. A NEW continuity document that quotes the
  problem statement would satisfy the first arm without being a record. The
  later arms are what stop that from passing quietly, because a quotation of
  the problem statement does not contain the record's own sentences.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _tracked  # noqa: E402

#: The dialect's name, spelled as ``CLAUDE.md`` spells it.
TERM = "CAVEMAN ULTRA"

#: Files where the term appears for a reason that is NOT the record criterion 4
#: asks for. ``CLAUDE.md`` is the DEFINITION - a file cannot discharge "names
#: where the dialect is defined and states that the definition in CLAUDE.md
#: governs" by being that file. ``ROADMAP.md`` and the ledger carry the problem
#: statement and its history. This module itself names the term to test for it.
NOT_A_RECORD = frozenset(
    {
        "CLAUDE.md",
        "ROADMAP.md",
        "docs/ROADMAP_ARCHIVE.md",
        "docs/LEDGER.md",
        "docs/LEDGER_ARCHIVE.md",
        "tests/test_caveman_dialect_record.py",
    }
)

#: Sentences the record must carry. Each is one clause of criterion 4's
#: acceptance, matched on a WHITESPACE-COLLAPSED copy because prose in this
#: repository is hard-wrapped near 80 columns and a line-oriented match is a
#: claim about the file's line breaks rather than about its content.
REQUIRED = {
    "governing-definition": "the definition in `CLAUDE.md` governs",
    "no-user-level-command": "No user-level command is relied on",
    "decline": "DECLINED",
}

#: Shapes that would put an account name into a tracked file. The caveman
#: command on this machine is real and its location is deliberately unwritten.
ACCOUNT_SHAPED = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"\bUsers[\\/]"),
    re.compile(r"%USERPROFILE%", re.IGNORECASE),
    re.compile(r"%LOCALAPPDATA%\\Users", re.IGNORECASE),
)


def _collapse(text: str) -> str:
    """Whitespace-collapse ``text`` so a hard-wrapped sentence matches."""
    return re.sub(r"\s+", " ", text)


def _published_text() -> dict[str, str]:
    """Every published text file, keyed by its repo-relative POSIX path."""
    out: dict[str, str] = {}
    for path in _tracked.iter_authored_files(REPO_ROOT):
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:  # pragma: no cover - defensive
            continue
        try:
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover - defensive
            continue
    return out


def _sections(text: str) -> list[str]:
    """Split a Markdown body on its ``##``-level headings.

    A file with no such heading yields one section holding the whole body, so
    this works on a non-Markdown record too.
    """
    parts: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                parts.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


def _record_sections() -> dict[str, str]:
    """Every candidate record section, keyed by ``path#heading``.

    A candidate is a section of a published file that is not in
    :data:`NOT_A_RECORD` and whose collapsed text names :data:`TERM`.
    """
    found: dict[str, str] = {}
    for rel, text in _published_text().items():
        if rel in NOT_A_RECORD:
            continue
        if TERM not in _collapse(text):
            continue
        for section in _sections(text):
            if TERM not in _collapse(section):
                continue
            heading = section.splitlines()[0].strip() if section.splitlines() else ""
            found[f"{rel}#{heading}"] = section
    return found


@pytest.fixture(scope="module")
def records() -> dict[str, str]:
    return _record_sections()


class TestTheRecordExists:
    """Criterion 4(a): a tracked file that is not the problem statement."""

    def test_a_published_file_outside_the_problem_statement_carries_the_term(
        self, records: dict[str, str]
    ) -> None:
        assert records, (
            f"No published file outside {sorted(NOT_A_RECORD)} names {TERM!r}. "
            "ROADMAP OPS-36 criterion 4(a) asks for a tracked record naming "
            "where the dialect is defined; 'it fires by construction' is not "
            "a record."
        )

    def test_the_excluded_set_is_not_vacuous(self) -> None:
        """The exclusions must actually exclude something.

        If ``CLAUDE.md`` stopped naming the term, the first arm could pass on a
        record pointing at a definition that is no longer there - so this pins
        that the excluded files are the reason the first arm is not trivial.
        """
        published = _published_text()
        missing = [rel for rel in NOT_A_RECORD if rel not in published]
        assert not missing, (
            f"NOT_A_RECORD names files that are not published: {missing}. "
            "An exclusion for a file that does not exist excludes nothing."
        )
        carriers = [
            rel
            for rel in NOT_A_RECORD
            if rel != "tests/test_caveman_dialect_record.py"
            and TERM in _collapse(published[rel])
        ]
        assert carriers, (
            f"None of {sorted(NOT_A_RECORD)} names {TERM!r} any more, so the "
            "exclusion list is guarding nothing and the first arm has become "
            "a check that some file somewhere says the words."
        )


class TestTheRecordSaysWhatCriterionFourAsksFor:
    """Each arm is one clause of the acceptance written into ``OPS-36``."""

    @pytest.mark.parametrize("label", sorted(REQUIRED))
    def test_required_sentence_is_present(
        self, records: dict[str, str], label: str
    ) -> None:
        needle = REQUIRED[label]
        hits = [key for key, body in records.items() if needle in _collapse(body)]
        assert hits, (
            f"No caveman record carries the {label!r} clause {needle!r}. "
            f"Candidates examined: {sorted(records)}. ROADMAP OPS-36 "
            "criterion 4(a) names this clause in its acceptance."
        )

    def test_one_single_record_carries_every_required_clause(
        self, records: dict[str, str]
    ) -> None:
        """Spread across three files, the clauses are three unrelated remarks.

        A cold session reads ONE section. The record has to be one section.
        """
        complete = [
            key
            for key, body in records.items()
            if all(needle in _collapse(body) for needle in REQUIRED.values())
        ]
        assert complete, (
            "No single section carries all of "
            f"{sorted(REQUIRED.values())}. Candidates: {sorted(records)}."
        )


class TestTheRecordLeaksNothing:
    """The record must not write the user-level command's location down."""

    def test_no_absolute_or_account_shaped_path_in_any_record(
        self, records: dict[str, str]
    ) -> None:
        offenders: list[str] = []
        for key, body in records.items():
            for pattern in ACCOUNT_SHAPED:
                match = pattern.search(body)
                if match:
                    offenders.append(f"{key}: {pattern.pattern} matched")
        assert not offenders, (
            "A caveman record carries an absolute or account-shaped path: "
            f"{offenders}. The advertised caveman command lives outside this "
            "repository and its path carries an account name, which is why "
            "OPS-36 records the absence deliberately rather than by oversight."
        )


class TestThePointerIsNotDangling:
    """A record naming ``CLAUDE.md`` is worthless if ``CLAUDE.md`` moved on."""

    def test_claude_md_still_states_the_dialect_the_record_points_at(self) -> None:
        text = _collapse((REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
        assert f"{TERM} is the default chat dialect" in text, (
            "CLAUDE.md no longer declares the dialect, so every record that "
            "says 'the definition in `CLAUDE.md` governs' now points at "
            "nothing. Fix CLAUDE.md or move the definition and update the "
            "record - do not weaken this assertion."
        )
