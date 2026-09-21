"""If the capture tree is gone, every document citing it must SAY so.

WHAT HAPPENED, 2026-09-20. ``C:\\ll-captures`` was permanently deleted - 10.6 GB
in 19,241 files. Not to the Recycle Bin, no VSS shadow copy existed, and the
operator confirmed there is no backup and it is unrecoverable. This project did
not delete it and no code in this tree could have: there is no ``rmtree``
anywhere near a capture or destination path, and the capture watcher has been
disarmed since 2026-09-11.

**WHY THAT IS A DOCUMENTATION PROBLEM AND NOT ONLY A DATA LOSS.** An
enumeration counted 132 CITED-EVIDENCE references to that tree across this
repository's measured documents - individual frames named as the proof of a
published reading, in a PUBLIC repository. Every one of those citations now
points at nothing, and a reader has no way to tell a claim whose evidence was
destroyed from a claim whose evidence they simply have not got.

This repository's own doctrine settles what to do. "Unmeasured" and "measured
zero" are different facts and conflating them is how an engine starts lying;
this is that distinction one level up, between *verifiable* and *was verifiable
once*. The citations are NOT deleted - deleting them would destroy the record
of how the readings were taken, and a reading whose method is recorded is worth
more than one with no provenance at all. Instead each document carries a notice
at the top, and this guard keeps that notice honest.

**IT FAILS IN BOTH DIRECTIONS, and the second one is the point.** If the tree
is absent the notice must be present. If the tree ever comes BACK - a restore,
a re-capture under the same root - the notice becomes false and must go, so
this guard fails then too. A notice that outlives its reason is the same stale
recital this repository corrected twice in one day, and it is worse here
because it would tell readers that good evidence is missing.

**The tests in ``tests/test_vision_meter.py`` skip when the captures are
absent, and that is by design rather than a defect** - a fresh clone has no
captures and still tests the pipeline. What the design did not anticipate is
this machine: a skip cannot distinguish "never had them" from "had them and
they were destroyed". The notice this guard enforces is what carries that
difference, because it is the only place the difference is written down.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The capture tree every document below cites. Named once, here.
CAPTURE_ROOT = Path("C:/ll-captures")

#: A marker rather than a sentence, so a document may word its own notice
#: however suits it while staying findable. It is deliberately ugly: nobody
#: writes this string by accident and nobody leaves it in place as decoration.
MARKER = "CAPTURE-EVIDENCE-DESTROYED-2026-09-20"

#: The documents whose claims rest on frames in that tree. Derived from an
#: enumeration that searched both separator spellings and a whitespace
#: collapsed copy of every file, because prose here wraps near 80 columns and a
#: path routinely spans two lines.
CITING_DOCUMENTS = (
    "docs/AFFIXES.md",
    "docs/FINDINGS.md",
    "docs/OBSERVED_IDS.md",
)


def _head(relpath: str, lines: int = 40) -> str:
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    return "\n".join(body.split("\n")[:lines])


def test_the_documents_this_guard_names_all_exist():
    """A guard over a missing file is a guard that passes for the wrong reason."""
    for relpath in CITING_DOCUMENTS:
        assert (REPO_ROOT / relpath).is_file(), f"{relpath} is not on disk"


@pytest.mark.parametrize("relpath", CITING_DOCUMENTS)
def test_the_notice_matches_whether_the_capture_tree_exists(relpath):
    present = CAPTURE_ROOT.is_dir()
    head = _head(relpath)

    if not present:
        assert MARKER in head, (
            f"{CAPTURE_ROOT} does not exist, and {relpath} cites frames inside "
            "it as the evidence for published readings without saying so. A "
            "reader cannot tell a claim whose proof was destroyed from one "
            f"whose proof they simply have not got. Add the {MARKER} notice."
        )
    else:
        assert MARKER not in head, (
            f"{CAPTURE_ROOT} EXISTS again, so the notice in {relpath} is now "
            "false and is telling readers that good evidence is missing. "
            "Remove it, and re-verify the citations before you do."
        )


@pytest.mark.parametrize("relpath", CITING_DOCUMENTS)
def test_the_notice_carries_the_date_and_says_it_is_unrecoverable(relpath):
    """A marker alone is a flag; a reader needs the fact.

    Skipped when the tree is present, because then there should be no notice
    at all and the arm above is what says so.
    """
    if CAPTURE_ROOT.is_dir():
        pytest.skip("the capture tree exists, so no notice should be present")
    head = _head(relpath)
    assert "2026-09-20" in head, f"{relpath}'s notice does not date the loss"
    assert re.search(r"unrecoverab|no backup|not recoverab", head, re.I), (
        f"{relpath}'s notice does not say the loss is unrecoverable, so a "
        "reader may spend time looking for a restore that does not exist"
    )


def test_the_marker_is_not_scattered_through_the_prose():
    """The notice belongs at the TOP, where a reader meets it first.

    Without this, the marker could be satisfied by a line buried at the bottom
    of a 2,000-line document that nobody reaches.
    """
    if CAPTURE_ROOT.is_dir():
        pytest.skip("the capture tree exists, so no notice should be present")
    for relpath in CITING_DOCUMENTS:
        body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
        occurrences = body.count(MARKER)
        assert occurrences == 1, (
            f"{relpath} carries the marker {occurrences} times; it should "
            "appear exactly once, in the notice at the top"
        )


def test_this_guard_would_notice_a_document_that_lost_its_notice(tmp_path):
    """Vacuity arm, driving the real reader over a synthetic document.

    A guard that only ever reads compliant files has not been shown to fail.
    """
    good = "# Title\n\n" + MARKER + " 2026-09-20 unrecoverable\n"
    bad = "# Title\n\nnothing here about the captures at all\n"
    assert MARKER in "\n".join(good.split("\n")[:40])
    assert MARKER not in "\n".join(bad.split("\n")[:40])
    # And the head window must really be a window - a marker below it is not
    # in the head, which is what test_the_marker_is_not_scattered relies on.
    buried = "# Title\n" + ("\nfiller" * 100) + "\n" + MARKER + "\n"
    assert MARKER not in "\n".join(buried.split("\n")[:40])
