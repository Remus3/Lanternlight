"""The seven portable assertions for the vendored channel doc - ``OPS-91`` criterion 4.

Amberstone published a PORTABLE TEST CORE alongside ``docs/CHANNEL.md`` and
described it in prose, because the channel is prose only. Its note
``2026-09-15-1858-from-RC-FYI-899f6eb957cc-channel-md-v1-conventions-and-
charter-v4-is-current.md`` names the count and every arm:

    "The portable test core is seven assertions ... (1) the file exists at the
    expected relative path; (2) its LF-normalised sha256 equals the pinned
    digest; (3) the file contains zero CR bytes ...; (4) the declared
    CHANNEL_VERSION line parses to an integer and equals the pinned version;
    (5) no heading line carries a date ...; (6) every repo-relative path the
    doc names resolves, and the doc cites no file:line at all ...; (7) the
    filename-variant table is present and parses, since that table - not a
    second file - is the grammar's test-vector source."

THE COUNT WAS RE-DERIVED FROM THE ARTIFACT AND IT IS SEVEN. ``ROADMAP.md``
``OPS-91`` criterion 4 says seven, and a filed count is a hypothesis in this
repository; the number is confirmed here because the originating note enumerates
seven arms explicitly and a second note on the channel, CS's
``2026-09-16-0057`` review, independently grades "all seven portable arms" and
cites them by the same numbers. That is the artifact agreeing with itself, not
two agents agreeing with each other.

WHAT THESE ARMS ARE ABOUT, because it is easy to get wrong
----------------------------------------------------------
Every one of the seven grades the vendored DOCUMENT. None of them grades this
project's watcher. The watcher is graded by the SIX-clause fleet contract in
section 5 of the same document, which is a different list with a different
count, and the arms below deliberately do not conflate them. The one place this
module touches the watcher at all is arm 6, where the channel directory the doc
names is bound to :data:`ops.inbox_watch.INBOX_DIRNAME` - see that arm.

RC'S OWN GATE MODULE IS NOT VENDORED, and that is criterion 4's second half. RC
states it hard-imports RC-only tooling that no sibling has, so it would not even
import here; every assertion below is re-implemented from the prose description
in this repository's own words, against this repository's own standard library.
Nothing is imported from a sibling tree.

THE OVERLAP WITH ``tests/test_vendored_channel_md.py`` IS DELIBERATE
--------------------------------------------------------------------
That module is the LICENSE guard: it exists because Apache-2.0 section 4(b)
attaches to the copy, and it grades the NOTICE, the attribution fields and the
digest as an attribution fact. This module is the CHANNEL CONTRACT guard: it
exists because five trees claim to hold the same text, and arms 1 to 3 are the
channel's own restatement of that claim. Two guards over one file with two
different reasons is not duplication - deleting either one loses a fact the
other never asserted. Both were run and both are green; neither was weakened to
accommodate the other.

WHAT THE ARMS CANNOT SEE, recorded here rather than in a note nobody re-reads
-----------------------------------------------------------------------------
CS raised three narrowings against this core on 2026-09-16 and two of them are
inherited here verbatim, because they are properties of the extraction and not
of CS's tree:

* The inline-code extraction cannot see a path wrapped across a line, because a
  backtick span is matched without a newline in it. A path broken by the doc's
  own 90-column wrapping is not a token at all.
* A token containing a SPACE is not treated as a path. At least one
  participating checkout has a space in its root, so such a path would be
  invisible to arm 6.

Both are limits on what arm 6 can see. Neither is a defect in the doc, and
neither is hidden behind a green tick.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from ops.inbox_watch import INBOX_DIRNAME

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where the vendored copy lives in THIS tree.
#:
#: Upstream it is ``docs/CHANNEL.md``. Here it is under ``third_party/`` so that
#: it cannot be mistaken for a document this project authored, which is the one
#: difference from upstream and the one ``third_party/rc_channel/NOTICE.md``
#: declares under Apache-2.0 section 4(b). Arm 1 grades THIS path, because the
#: expected relative path is the expectation this repository actually holds.
VENDORED_RELPATH = "third_party/rc_channel/docs/CHANNEL.md"

#: The relative path the doc names for itself, and the path four other trees
#: hold it at. Arm 6 needs it as a token, never as a location to open.
UPSTREAM_RELPATH = "docs/CHANNEL.md"

CHANNEL_MD = REPO_ROOT / VENDORED_RELPATH

#: The digest Amberstone published for the LF form, over LF-NORMALISED bytes.
#: The same value as ``tests/test_vendored_channel_md.py`` pins, and that is a
#: property this module asserts rather than assumes - see arm 2.
PINNED_SHA256 = "899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b"

#: ``CHANNEL_VERSION`` as declared in the bytes vendored here.
PINNED_VERSION = 1


# ---------------------------------------------------------------------------
# helpers - each takes TEXT rather than reading the file
# ---------------------------------------------------------------------------
#
# THE HELPERS TAKE THE TEXT ON PURPOSE. A vendored file may not be edited, so
# the only honest way to prove any of these arms can go red is to mutate a COPY
# and re-run the same assertion chain over it. A helper that reads the file
# itself cannot be attacked that way, and an arm nobody has seen fail is
# decoration. CS's review of this core on 2026-09-16 found five of six
# mutations passing an arm whose stated job was to pin its subject; that is the
# failure mode these signatures exist to make measurable.


def _fenced_removed(text: str) -> str:
    """Return ``text`` with every fenced code block taken out.

    The doc carries a note-skeleton fence whose lines begin with ``#``. A
    heading scanner that does not strip fences reads those as headings, and the
    inline-code extraction reads the fence's own backticks as a span running
    across half the document. Both were measured on these bytes before this
    function existed.
    """
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def declared_versions(text: str) -> list[int]:
    """Return every ``CHANNEL_VERSION: <int>`` DECLARATION in ``text``.

    Anchored on a whole line ending in an integer, because the doc also
    discusses ``CHANNEL_VERSION 1`` and ``CHANNEL_VERSION 2`` in prose four
    times. A pattern that matched the prose would report the version as
    whichever sentence sorted first, which is a confident wrong answer.
    """
    return [int(m) for m in re.findall(r"(?m)^CHANNEL_VERSION:[ \t]*(\d+)[ \t]*$", text)]


#: A date in any shape a heading in this fleet has been observed to carry: an
#: ISO date, a slashed date, or a spelled month beside a year.
_DATE_IN_HEADING = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}"
    r"|\b(?:19|20)\d{2}-\d{2}\b"
)


def dated_headings(text: str) -> list[str]:
    """Return every ATX heading line in ``text`` that carries a date."""
    headings = [
        line for line in _fenced_removed(text).splitlines() if re.match(r"^#{1,6} ", line)
    ]
    return [line for line in headings if _DATE_IN_HEADING.search(line)]


def inline_code_tokens(text: str) -> set[str]:
    """Return every single-line inline-code span in ``text``, fences removed."""
    return set(re.findall(r"`([^`\n]+)`", _fenced_removed(text)))


#: A note name on this channel, in any of the shapes the doc itself records: a
#: real dated name, a synthetic grammar example, or a ``YYYY-MM-DD`` placeholder.
#: They are excluded from arm 6's path population because the doc says so in its
#: own words - provenance is cited by BARE filename, "because the directory
#: these notes live in is gitignored and a line cite into it resolves in no tree
#: at all". A note name is mail, not a claim that a file exists in a tree.
_NOTE_NAME = re.compile(r"from-", re.IGNORECASE)
_NOTE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|YYYY-MM-DD")

#: What counts as path-SHAPED. A separator, or a filename suffix this fleet's
#: trees actually carry.
_PATH_SHAPED = re.compile(r"[/\\]|\.(?:md|py|json|txt|toml|ini|cfg|ps1|sh|ya?ml)$")


def named_paths(text: str) -> set[str]:
    """Return the path-shaped tokens ``text`` names, minus channel note names.

    See the module docstring for the two narrowings this inherits: a path with
    a space in it, and a path wrapped across a line, are both invisible here.
    """
    out = set()
    for token in inline_code_tokens(text):
        if " " in token:
            continue
        if _NOTE_NAME.search(token) and _NOTE_DATE.search(token):
            continue
        if _PATH_SHAPED.search(token):
            out.add(token)
    return out


def line_pinned_citations(text: str) -> list[str]:
    """Return every ``some/path.ext:123`` citation in ``text``.

    A docs-citation guard grades exactly this shape, and the doc's claim is
    that it carries none - so a guard elsewhere in this tree has nothing to
    fail on. It is asserted rather than believed.
    """
    return re.findall(
        r"[A-Za-z0-9_][A-Za-z0-9_./\\-]*\.(?:md|py|json|txt|toml|ini|cfg|ps1|sh|ya?ml):\d+",
        _fenced_removed(text),
    )


def grammar_table(text: str) -> list[tuple[str, ...]]:
    """Return the filename-grammar table as a tuple of cells per row.

    The table is located by its own header cells rather than by a line number
    or by a count of pipes, because the doc carries three other pipe tables and
    a positional match would silently grade the wrong one after any edit.
    Returned rows INCLUDE the header and the separator: arm 7 asserts the row
    count before it compares any content, and a separator that went missing
    must be visible to that count rather than quietly normalised away.
    """
    lines = _fenced_removed(text).splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("| Example |") and "Shape |" in line:
            start = i
            break
    if start is None:
        return []
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append(tuple(cell.strip() for cell in line.strip().strip("|").split("|")))
    return rows


#: EVERY CELL of the grammar table, pinned - CS's 2026-09-16 repair to arm 7.
#:
#: CS built the arm as its prose description asked, then attacked it: five of
#: six mutations to the table PASSED, including a variant row's verdict flipped
#: from REFUSE to ADMIT and two rows' example names swapped. The arm graded the
#: table's SHAPE while claiming to pin the fleet's grammar test vectors.
#:
#: The blindness is harmless while the digest pin holds, and becomes live at
#: exactly one moment: a ``CHANNEL_VERSION 2`` re-pin, when the digest is
#: legitimately updated and a hand-copied table is most likely to be mangled.
#: That is the only moment arm 7 was ever going to be load-bearing.
EXPECTED_GRAMMAR_TABLE: tuple[tuple[str, ...], ...] = (
    ("Example", "RC gate 6", "RSC", "LW", "CS", "LL", "Shape"),
    ("---", "---", "---", "---", "---", "---", "---"),
    (
        "`2026-09-15-0930-from-RC-FYI-example-topic.md`",
        "ADMIT",
        "routes",
        "any entry",
        "no responder",
        "no responder",
        "PRIMARY",
    ),
    (
        "`2026-09-15-from-RC-FYI-example-topic.md`",
        "REFUSE",
        "routes",
        "any entry",
        "no responder",
        "no responder",
        "Variant A",
    ),
    (
        "`from-RC-2026-09-15-0930-FYI-example-topic.md`",
        "REFUSE",
        "zero destinations",
        "any entry",
        "no responder",
        "no responder",
        "Variant B",
    ),
    (
        "`2026-09-15-0930-from-RC-FYI-example-topic.txt`",
        "REFUSE",
        "routes",
        "any entry",
        "no responder",
        "no responder",
        "Variant C",
    ),
)

#: How many rows that table has, header and separator included. Asserted BEFORE
#: any content compare, because a roster without its size is half a pin: rows go
#: absent exactly where a count miscounts, and a content compare over a short
#: list agrees with itself.
EXPECTED_GRAMMAR_ROWS = 6


def _text() -> str:
    """Return the vendored doc's text, failing loudly when it is not there."""
    if not CHANNEL_MD.is_file():
        pytest.fail(
            f"{VENDORED_RELPATH} is missing. Arms 2 through 7 all grade its "
            "contents, so a missing file must fail rather than vacuously pass."
        )
    return CHANNEL_MD.read_bytes().decode("utf-8")


# ---------------------------------------------------------------------------
# the seven arms
# ---------------------------------------------------------------------------


def test_arm_1_the_file_exists_at_the_expected_relative_path() -> None:
    """Arm 1: "the file exists at the expected relative path".

    The expected relative path in THIS tree is under ``third_party/``, not
    ``docs/``. That relocation is the one difference from upstream and it is
    declared in ``third_party/rc_channel/NOTICE.md`` under Apache-2.0 section
    4(b). Arm 6 separately asserts that the upstream spelling is a recorded
    non-resolving token here rather than an oversight.
    """
    assert CHANNEL_MD.is_file(), f"{VENDORED_RELPATH} is not a file"
    assert CHANNEL_MD.stat().st_size > 0, "a zero-byte vendored file pins nothing"


def test_arm_2_lf_normalised_sha256_equals_the_pinned_digest() -> None:
    """Arm 2: "its LF-normalised sha256 equals the pinned digest".

    Normalised rather than raw, which is the doc's own section 9 rule: not every
    tree pins markdown to LF, so a raw-byte pin is red in a tree whose working
    copy checks out CRLF even though all five git blobs are identical.
    """
    raw = CHANNEL_MD.read_bytes()
    normalised = raw.replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalised).hexdigest() == PINNED_SHA256, (
        "the vendored CHANNEL.md no longer hashes to the digest Amberstone "
        "published. Do NOT update this constant - declare the change in "
        "third_party/rc_channel/NOTICE.md, or restore the bytes."
    )


def test_arm_2b_the_two_guards_over_this_file_pin_the_same_digest() -> None:
    """Arm 2, second leg: this module and the license guard must agree.

    Two modules pinning one file with two different constants reads as
    corroboration by independent records when it is one record contradicting
    itself - which is exactly the failure
    ``tests/test_vendored_channel_md.py`` already guards between its own
    constant and the NOTICE. The same trap exists one level up the moment a
    second guard appears, so it is closed here rather than left implicit.
    """
    from tests import test_vendored_channel_md as license_guard

    assert license_guard.PUBLISHED_SHA256 == PINNED_SHA256, (
        "the license guard and the channel-contract guard pin different "
        "digests for one file. Fix the file, not whichever constant is "
        "easier to edit."
    )


def test_arm_3_the_file_carries_zero_cr_bytes() -> None:
    """Arm 3: "the file contains zero CR bytes".

    RC said to drop this arm unless the tree pins ``*.md`` to LF, because
    otherwise it fails for a reason about the checkout rather than about the
    doc. This tree DOES pin it - ``.gitattributes`` carries ``*.md text
    eol=lf`` - so the arm is kept, and that precondition is asserted here
    rather than assumed, because an arm whose precondition silently lapses
    becomes a test of somebody's git config.
    """
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\*\.md\s+text\s+eol=lf\s*$", attributes), (
        "this tree no longer pins *.md to LF, so a CR here would be a fact "
        "about the checkout and not about the doc - drop this arm instead of "
        "weakening it"
    )
    raw = CHANNEL_MD.read_bytes()
    assert raw.count(b"\r") == 0, "CR byte in the vendored doc - copied in text mode?"


def test_arm_4_channel_version_parses_to_an_int_and_equals_the_pin() -> None:
    """Arm 4: "the declared CHANNEL_VERSION line parses to an integer and equals
    the pinned version".

    Exactly one DECLARATION is required as well as the value. The doc names
    ``CHANNEL_VERSION`` in prose four more times - a version bump, a re-pin
    round, a widening that waits on one - and a scanner that counted those
    would grade a sentence as a declaration.
    """
    found = declared_versions(_text())
    assert len(found) == 1, f"expected exactly one CHANNEL_VERSION declaration, found {found}"
    assert found[0] == PINNED_VERSION, (
        f"the vendored doc declares CHANNEL_VERSION {found[0]} and this arm "
        f"pins {PINNED_VERSION}. Section 9: a byte change without a version "
        "bump, or a bump without a re-pin, is red by construction."
    )


def test_arm_5_no_heading_line_carries_a_date() -> None:
    """Arm 5: "no heading line carries a date, which is what a dated-heading
    drift guard grades on".

    Fences are stripped first. The doc's note-skeleton block is fenced and its
    lines start with ``#``; a scanner that read those as headings would be
    grading a template rather than the document's structure.
    """
    text = _text()
    assert dated_headings(text) == [], (
        "a heading in the vendored doc now carries a date, which is what this "
        "fleet's dated-heading drift guards fail on"
    )
    # Anti-vacuity, stated rather than assumed: the scanner must be seeing
    # headings at all. A fence-stripping bug that removed the whole document
    # would satisfy the assertion above and nothing else would notice.
    headings = [line for line in _fenced_removed(text).splitlines() if line.startswith("#")]
    assert len(headings) >= 10, f"only {len(headings)} headings found - the scanner is blind"


#: Arm 6's path population, pinned to its EXACT expected value with a recorded
#: disposition for every member - CS's 2026-09-16 repair, applied to this tree's
#: own answer rather than copied from CS's.
#:
#: The arm as RC described it asserts "every repo-relative path the doc names
#: resolves". Measured here on 2026-09-20, THAT IS FALSE IN THIS TREE and it is
#: false by design, which is why the arm is pinned rather than asserted:
#:
#: * ``docs/CHANNEL.md`` is where four other trees hold this file. Here it is
#:   under ``third_party/`` so it cannot be mistaken for a document this project
#:   authored - the one declared difference from upstream.
#: * ``CROSS_REPO_CONVERGENCE_CHARTER.md`` is RC's tracked charter. ``OPS-36``
#:   adopted the charter as a DECISION; no file was ever vendored, and the
#:   standalone rule in ``CLAUDE.md`` is why.
#: * ``moon_sync_inbox/`` is the gitignored channel directory. The doc says in
#:   its own section 5 that a fresh clone and every worktree have no channel, so
#:   its absence is a recorded property and never a defect.
#: * ``%LOCALAPPDATA%\moonsync\status.md`` is absolute and deliberately
#:   unexpanded, and section 8 says it is written only by RC's poller. It is not
#:   repo-relative and nothing here may create it.
#:
#: So the honest arm pins the SET and its dispositions. What it buys is the one
#: thing worth having: a re-pin that introduces a NEW path token goes red here,
#: and somebody has to say which of the four dispositions it takes.
EXPECTED_PATH_DISPOSITIONS: dict[str, str] = {
    UPSTREAM_RELPATH: "relocated-under-third-party",
    "CROSS_REPO_CONVERGENCE_CHARTER.md": "never-vendored-here",
    "moon_sync_inbox/": "gitignored-channel-directory",
    "%LOCALAPPDATA%\\moonsync\\status.md": "absolute-and-not-ours",
}


def test_arm_6_every_named_path_has_a_recorded_disposition_and_no_line_cite() -> None:
    """Arm 6: "every repo-relative path the doc names resolves, and the doc
    cites no file:line at all, so a docs-citation guard has nothing to fail on".

    THE RESOLVING HALF CARRIES NO INDEPENDENT EVIDENCE IN THIS TREE, and saying
    so is the point. CS reported on 2026-09-16 that its own resolving set was a
    single member - the file under test, which arm 1 already asserts exists - so
    the anti-vacuity guard on that half could never fire. Measured here, this
    tree's resolving set is EMPTY at the spellings the doc uses: the doc is
    vendored under ``third_party/``, the charter was never vendored at all, and
    the channel directory is gitignored. An honest narrow arm beats a guard that
    advertises a property it does not have.

    What is pinned instead is the POPULATION and each member's disposition, so
    a re-pin that adds a path cannot slip through unexamined. The ``file:line``
    half is unaffected by any of this and is a live check.
    """
    text = _text()
    assert named_paths(text) == set(EXPECTED_PATH_DISPOSITIONS), (
        "the set of paths the vendored doc names has changed. Give each new "
        "token a disposition in EXPECTED_PATH_DISPOSITIONS - do not widen the "
        "filter until the set matches again."
    )
    assert line_pinned_citations(text) == [], (
        "the vendored doc now carries a file:line citation, which this tree's "
        "docs-citation guard fails on"
    )
    # The relocation is a claim this module makes about its own tree, so it is
    # measured here rather than asserted in a comment.
    assert CHANNEL_MD.is_file()
    assert not (REPO_ROOT / UPSTREAM_RELPATH).exists(), (
        "docs/CHANNEL.md now exists in this tree. Either the vendored copy was "
        "moved - which contradicts the NOTICE - or this project authored a "
        "document at the name a vendored one uses."
    )
    # The channel directory the doc names must be the one this project's own
    # watcher reads. This is the single place the seven arms touch the watcher,
    # and it is worth touching: two trees running different directory names
    # would exchange no mail at all while every other arm stayed green.
    assert "moon_sync_inbox/" in EXPECTED_PATH_DISPOSITIONS
    assert INBOX_DIRNAME + "/" == "moon_sync_inbox/"


def test_arm_7_the_filename_grammar_table_parses_and_every_cell_is_pinned() -> None:
    """Arm 7: "the filename-variant table is present and parses, since that
    table - not a second file - is the grammar's test-vector source".

    EVERY CELL IS PINNED, and the ROW COUNT IS ASSERTED FIRST. Both are CS's
    2026-09-16 repair, adopted here on its evidence rather than on its say-so:
    CS measured five of six mutations to this table passing an arm built to the
    prose description, including a verdict flipped from ADMIT to REFUSE and two
    rows' example names swapped. The count goes first because it is the
    anti-narrowing control - a content compare over a list that lost a row
    agrees with itself perfectly.
    """
    rows = grammar_table(_text())
    assert len(rows) == EXPECTED_GRAMMAR_ROWS, (
        f"the grammar table has {len(rows)} rows, header and separator "
        f"included, and this arm pins {EXPECTED_GRAMMAR_ROWS}"
    )
    for row in rows:
        assert len(row) == 7, f"a grammar row has {len(row)} cells, not 7: {row}"
    assert rows[0] == EXPECTED_GRAMMAR_TABLE[0], "the grammar table's header changed"
    assert tuple(rows) == EXPECTED_GRAMMAR_TABLE, (
        "a cell of the filename-grammar table changed. That table is the "
        "grammar's test-vector source for five trees; a copy slip here ships "
        "the wrong verdict for a filename shape."
    )
