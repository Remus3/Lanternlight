"""Split the two continuity documents into a live head and a verbatim archive.

ROADMAP ``OPS-57``. ``ROADMAP.md`` and ``docs/LEDGER.md`` are the documents a
cold session reads to find out where it is, and both outgrew the size budgets
that were meant to be their tripwire. Raising the numbers was already recorded
as a deferral rather than a fix. The structural answer this module implements
is the non-destructive one: MOVE closed material into a dated archive that the
live document links to, so a cold session reaches every word in one hop and not
one character is deleted, edited, reordered or reflowed.

WHAT THIS MODULE IS, AND DELIBERATELY IS NOT. It is a library of pure
functions: each one takes text and returns text. Nothing here opens a file for
writing, and :func:`main` is a DRY RUN that prints a report. Applying a plan -
writing ``ROADMAP.md``, ``docs/LEDGER.md`` and the two archive files, and
re-deriving the size budgets afterwards - is a separate, deliberate act by
whoever owns those documents. That separation exists because this repository
has been bitten by tools that did more than their name promised, and because a
plan you can print, diff and re-run is a plan you can refuse.

CONSERVATION IS THE CONTRACT. ``OPS-57`` criterion 4 says no content is deleted
and no ledger entry is edited, reordered or reflowed. So both planning
functions carry an internal equality check over the FULL text - not a length
comparison, not a spot check - and raise :class:`ConservationError` rather than
returning a lossy plan. :func:`split_sections` is the foundation everything
rests on and its round-trip property is exact: ``preamble +
"".join(section.text ...) == text``. Offsets are returned alongside so a caller
can re-derive that property against the source without trusting this module.

HOW A ROADMAP HEADING IS CLASSIFIED, AND WHY IT IS NOT A SUBSTRING SEARCH. The
obvious rule - "the heading contains CLOSED or REFUTED" - is wrong on the real
file in both directions, and the counterexamples are already there:

* ``## OPS-15. `precommit_gate._block` fails OPEN when stderr is unusable -
  CLOSED 2026-08-30``. The word OPEN is prose in the TITLE, describing a
  failure mode, and it appears BEFORE the closure word. A "first keyword wins"
  rule over the whole heading files this closed item as open.
* ``## 4c. Archive the log and the market cache on every session - CLOSED
  2026-08-25b, successor 4d OPEN``. Here the trailing OPEN belongs to a
  DIFFERENT item, ``4d``. A "last keyword wins" rule files this closed item as
  open too.

So the rule implemented here reads the status out of the OUTCOME SEGMENT only -
the text after the LAST `` - `` separator on the heading line - and within that
segment the FIRST status keyword wins. That is the segment this repository
actually writes its outcomes into, and it puts the item's own status first even
when the same segment goes on to mention a successor. Measured against the real
``ROADMAP.md`` on 2026-09-08: the outcome segment carries a closure word for
exactly the same 65 headings that carry one anywhere in the line, so the
segment restriction costs nothing today and defends against the shape above.

The ambiguous case the rule is really for is an item whose own PREMISE was
refuted while the item itself stays open. Written the way this repo writes
status - ``- OPEN, its own premise was REFUTED`` - the leading OPEN wins and
the item stays in the live roadmap, which is the conservative answer: leaving a
closed item in the roadmap costs bytes, while archiving an open one hides work
from the next cold session, and that is the failure this whole design exists to
prevent. Two further headings are never archivable whatever they say:
``## Ordering note`` and ``## Deliberately not on this list`` are not items, and
neither is the ``## Archive index`` section this module generates - without
that last exclusion a second run would archive the index the first run created.

THE SECOND RUN IS NOT HYPOTHETICAL, SO IT HAS ITS OWN PARAMETER. This module
exists because a size budget fired, and a budget that fired once fires again, so
the splitter runs against a document it has already split. Without help, that
second run planned an archive holding ONLY the sections that run moved, under a
header reading "Sections in this archive: 1" - and applying it the way the first
plan was applied, by overwriting the archive file, would have DELETED everything
the first run put there. The tool built to guarantee that no word is lost had a
data-loss hazard in its own second use.

So both planning functions take an optional ``existing_archive``. Pass the
current archive text and the plan becomes additive: the new archive is every
section it already held plus the newly moved ones, and the roadmap ends up with
ONE ``## Archive index`` covering old and new rather than a fresh index section
per run. The roadmap archive grows by appending, which is the order items were
archived in rather than their original roadmap order; the ledger archive grows
by PREPENDING, because it is newest-first and each run moves entries newer than
everything already there. Omitting the argument keeps the original behaviour and
is correct only for a FIRST split, when no archive exists yet.

THE LEDGER IS A DIFFERENT PROBLEM AND GETS DIFFERENT CODE. It is append-only
and newest-first, so archiving it means cutting a contiguous TAIL - the OLDEST
entries, which live at the END of the file - and nothing else. Everything from
the start of the file through the insertion marker
``<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->`` is reproduced byte for byte,
because ``ops/loop/ledger.py`` appends directly below that marker and a
reflowed head would break the one automated writer this document has. Note the
trap the head contains: an ``### LL-0000 - YYYY-MM-DD`` FORMAT TEMPLATE sits
above the marker. It looks exactly like an entry to a naive scan and is not
one, so entries are only ever counted below the marker.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "REPO_ROOT",
    "LEDGER_MARKER",
    "INDEX_HEADING",
    "NON_ITEM_HEADINGS",
    "CLOSED_WORDS",
    "OPEN_WORDS",
    "DEFAULT_ROADMAP_ARCHIVE",
    "DEFAULT_LEDGER_ARCHIVE",
    "DEFAULT_LEDGER_KEEP",
    "ConservationError",
    "LedgerMarkerMissing",
    "Section",
    "RoadmapPlan",
    "LedgerPlan",
    "split_sections",
    "is_archivable",
    "extract_item_id",
    "anchor_for",
    "outcome_text",
    "stub_line",
    "plan_roadmap_split",
    "plan_ledger_split",
    "main",
]

#: Repository root, resolved from this file's location: tools/doc_archive.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The line ``ops/loop/ledger.py`` appends directly below. Never moved.
LEDGER_MARKER = "<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->"

#: Heading of the index section this module appends to the live roadmap.
INDEX_HEADING = "## Archive index"

#: Level-2 headings that are not roadmap ITEMS and are therefore never moved.
NON_ITEM_HEADINGS = (
    "Ordering note",
    "Deliberately not on this list",
    "Archive index",
)

#: Status words that mean the item is finished with.
CLOSED_WORDS = ("CLOSED", "REFUTED")

#: Status words that mean the item is still live. See the module docstring for
#: why these are matched only inside the outcome segment.
OPEN_WORDS = ("OPEN", "NEXT", "READY", "BLOCKED")

#: Repo-relative paths the dry run reports against. Nothing is written to them.
DEFAULT_ROADMAP_ARCHIVE = "docs/ROADMAP_ARCHIVE.md"
DEFAULT_LEDGER_ARCHIVE = "docs/LEDGER_ARCHIVE.md"

#: How many newest ledger entries the dry run keeps in the live document.
DEFAULT_LEDGER_KEEP = 60

_STATUS_RE = re.compile(
    r"\b(?P<closed>" + "|".join(CLOSED_WORDS) + r")\b|\b(?P<open>" + "|".join(OPEN_WORDS) + r")\b"
)

_ID_RE = re.compile(r"^(?:[A-Z]{2,}-)?[0-9]+[a-z]*(?:\s+[a-z][a-z-]*)*$")

_HASH_PREFIX_RE = re.compile(r"^#+[ \t]+")


class ConservationError(RuntimeError):
    """A plan would have lost, duplicated or reordered text. Refuse it.

    Raised from inside the planning functions rather than returned, because a
    lossy plan that is merely reported is a plan somebody applies anyway.
    """


class LedgerMarkerMissing(ValueError):
    """The ledger text carries no insertion marker, so its head is unknown."""


@dataclass(frozen=True)
class Section:
    """One heading and everything under it, verbatim.

    Attributes:
        heading: The heading line itself, without its trailing newline.
        text: The section's full text INCLUDING the heading line and whatever
            trailing blank lines separate it from the next heading. Slicing the
            source with ``[start:end]`` reproduces this exactly.
        start: Character offset of the heading's first ``#`` in the source.
        end: Character offset one past the section's last character.
    """

    heading: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class RoadmapPlan:
    """The two documents a roadmap split would produce, plus what moved."""

    roadmap_text: str
    archive_text: str
    archive_header: str
    kept: list[Section]
    archived: list[Section]


@dataclass(frozen=True)
class LedgerPlan:
    """The two documents a ledger split would produce, plus what moved."""

    ledger_text: str
    archive_text: str
    archive_header: str
    kept: list[Section]
    archived: list[Section]


def _strip_hashes(heading: str) -> str:
    """Return a heading line with its leading ``#`` run and one space removed."""
    return _HASH_PREFIX_RE.sub("", heading).rstrip("\n")


def split_sections(text: str, level: int = 2) -> tuple[str, list[Section]]:
    """Split ``text`` into a preamble and an ordered list of sections.

    A section starts at a line beginning with exactly ``level`` hashes followed
    by a space, and runs to the character before the next such line (or the end
    of the text). Deeper headings never split: ``### `` does not match a
    ``level=2`` scan, because the pattern requires a space after the hashes.

    The round-trip property is exact and is what every other function in this
    module relies on::

        preamble, sections = split_sections(text)
        assert preamble + "".join(s.text for s in sections) == text

    Args:
        text: The whole document.
        level: Heading depth to split on. 2 for ``## ``, 3 for ``### ``.

    Returns:
        ``(preamble, sections)``. The preamble is everything before the first
        matching heading and is ``text`` itself when there is no such heading.
    """
    prefix = "#" * level + " "
    pattern = re.compile("^" + re.escape(prefix), re.MULTILINE)
    starts = [match.start() for match in pattern.finditer(text)]
    if not starts:
        return text, []

    preamble = text[: starts[0]]
    bounds = [*starts, len(text)]
    sections: list[Section] = []
    for index, start in enumerate(starts):
        end = bounds[index + 1]
        body = text[start:end]
        sections.append(
            Section(heading=body.split("\n", 1)[0], text=body, start=start, end=end)
        )
    return preamble, sections


def outcome_text(heading: str) -> str:
    """Return the outcome segment of a heading - the text after the last " - ".

    A heading with no `` - `` separator has no separable outcome, so the whole
    heading text is returned. See the module docstring for why the status is
    read from this segment and not from the whole line.
    """
    body = _strip_hashes(heading)
    cut = body.rfind(" - ")
    return body if cut == -1 else body[cut + 3 :]


def is_archivable(heading: str) -> bool:
    """Return True when this roadmap heading names a finished item.

    The rule, stated in full because the ambiguous shapes are real and are in
    the file today: read the OUTCOME SEGMENT only - the text after the last
    `` - `` on the heading line - and let the FIRST status keyword in that
    segment decide. ``CLOSED`` and ``REFUTED`` mean archivable; ``OPEN``,
    ``NEXT``, ``READY`` and ``BLOCKED`` mean the item stays. A segment with no
    status keyword at all is not archivable, so ``MEASURED``, ``ANSWERED`` and
    ``DECODED`` items stay put.

    Reading only the outcome segment is what saves
    ``## OPS-15. ... fails OPEN when stderr is unusable - CLOSED 2026-08-30``,
    whose OPEN is prose in the title. Taking the FIRST keyword within it is what
    saves ``## 4c. ... - CLOSED 2026-08-25b, successor 4d OPEN``, whose OPEN
    belongs to a different item. Where both readings genuinely conflict - an
    item whose own premise was refuted but which is still open, written
    ``- OPEN, its own premise was REFUTED`` - the leading OPEN wins and the item
    stays live, because archiving an open item hides work from the next cold
    session and that is the expensive direction to be wrong in.

    The three headings in :data:`NON_ITEM_HEADINGS` are never archivable
    whatever they contain, including the index section this module generates.
    """
    body = _strip_hashes(heading)
    if body in NON_ITEM_HEADINGS:
        return False
    match = _STATUS_RE.search(outcome_text(heading))
    return bool(match and match.group("closed"))


def extract_item_id(heading: str) -> str | None:
    """Return the item id at the start of a roadmap heading, or None.

    The id is the label before the heading's first ``". "`` - ``0``, ``1b``,
    ``OPS-15`` - and it is returned only when that label actually looks like an
    id. ``## Ordering note`` therefore yields None rather than a stray phrase.

    The label deliberately includes a trailing lowercase qualifier, so
    ``## OPS-33 follow-up. ...`` yields ``OPS-33 follow-up`` and not ``OPS-33``.
    Both sections exist in ``ROADMAP.md`` and both are closed; collapsing them
    to one id would put two archived items behind a single index key.
    """
    body = _strip_hashes(heading)
    cut = body.find(". ")
    if cut == -1:
        return None
    label = body[:cut]
    return label if _ID_RE.match(label) else None


def anchor_for(heading: str) -> str:
    """Return the GitHub-style in-page anchor for a heading.

    Lowercase, spaces become hyphens, and every character that is not
    alphanumeric or a hyphen is dropped. Backticks, periods, commas and
    parentheses all vanish; the `` - `` clause separators this repo writes turn
    into a run of three hyphens, which is what GitHub itself produces.
    """
    body = _strip_hashes(heading).lower()
    out: list[str] = []
    for char in body:
        if char.isalnum() and char.isascii():
            out.append(char)
        elif char in " \t-":
            out.append("-")
    return "".join(out)


def stub_line(section: Section, archive_path: str) -> str:
    """Return the one-line roadmap index entry for an archived section.

    Carries the item id, the heading's outcome text, and a relative link to the
    heading's own anchor inside the archive document, so a cold session reaches
    the full text in one hop. The rest of the heading is kept between them
    because the index is also what somebody greps.
    """
    item_id = extract_item_id(section.heading)
    body = _strip_hashes(section.heading)
    if item_id is not None and body.startswith(item_id + ". "):
        rest = body[len(item_id) + 2 :]
    else:
        rest = body
    label = item_id if item_id is not None else body
    anchor = anchor_for(section.heading)
    return f"- **{label}** - {rest} - [full text]({archive_path}#{anchor})"


def _archive_body(sections: list[Section]) -> str:
    """Concatenate section texts verbatim, in the order given.

    Deliberately trivial and deliberately a module-level function: it is the
    single choke point every moved byte passes through, which makes it the one
    place a test can break to prove the conservation guards are not decoration.
    """
    return "".join(section.text for section in sections)


def _roadmap_archive_header(archived: list[Section], source: str) -> str:
    """Return the archive document's header - what it is and how to read it."""
    return (
        "# Lanternlight roadmap archive\n"
        "\n"
        f"Closed and refuted items moved out of [`{source}`](../{source}) so that\n"
        "the live roadmap stays short enough for a cold session to actually READ.\n"
        "Filed under ROADMAP `OPS-57`.\n"
        "\n"
        "Nothing here was edited, summarised or reflowed. Every section below is\n"
        "the original text, verbatim, in its original order, and the live roadmap\n"
        "carries a one-line stub linking to each one. If an item here turns out to\n"
        "matter again, move the section back rather than rewriting it.\n"
        "\n"
        f"Sections in this archive: {len(archived)}.\n"
        "\n"
        "---\n"
        "\n"
    )


def _roadmap_index_section(archived: list[Section], archive_path: str) -> str:
    """Return the index section appended to the live roadmap."""
    lines = [
        INDEX_HEADING,
        "",
        "Every closed and refuted item is still here, one hop away, in",
        f"[`{archive_path}`]({archive_path}). Nothing was deleted. Each line below",
        "links to that item's full original text.",
        "",
    ]
    lines.extend(stub_line(section, archive_path) for section in archived)
    lines.append("")
    return "\n".join(lines)


def plan_roadmap_split(
    text: str, archive_path: str, existing_archive: str = ""
) -> RoadmapPlan:
    """Plan the roadmap split. Returns new text for both documents; writes none.

    The new roadmap is the preamble, then every surviving section verbatim, then
    a generated ``## Archive index`` section carrying one stub per archived
    item. The archive is a short header naming its source, then the archived
    sections verbatim in their original order.

    Args:
        text: The current roadmap document.
        archive_path: Repo-relative path the stubs should link to, e.g.
            ``docs/ROADMAP_ARCHIVE.md``. Used only to build links.
        existing_archive: The archive document as it stands today, when there is
            one. Supplying it makes the plan ADDITIVE - the returned archive
            carries every section already archived, followed by the ones this
            run moves, and the returned roadmap carries a single regenerated
            index covering both. Omitting it is correct only for a first split;
            see the module docstring for the data-loss hazard that motivated it.

    Returns:
        A :class:`RoadmapPlan`. ``archived`` lists only the sections THIS run
        moves; the sections carried over from ``existing_archive`` are in
        ``archive_text`` but not in ``archived``.

    Raises:
        ConservationError: If the split would not preserve every byte of every
            moved section, in order, exactly once, or if a section already in
            ``existing_archive`` would be lost.
    """
    preamble, sections = split_sections(text)
    if preamble + "".join(s.text for s in sections) != text:
        raise ConservationError("split_sections did not round-trip the roadmap")

    prior: list[Section] = []
    if existing_archive:
        _, prior = split_sections(existing_archive)
        if not prior:
            raise ConservationError(
                "the existing archive text carries no sections to carry forward"
            )

    archived = [s for s in sections if is_archivable(s.heading)]
    survivors = [s for s in sections if not is_archivable(s.heading)]
    if len(survivors) + len(archived) != len(sections):
        raise ConservationError("a section was neither kept nor archived")

    # The index is generated, not authored, so it is regenerated rather than
    # carried - but only when the caller handed us the whole archive, because
    # only then do we know every item the regenerated index has to cover.
    index_name = _strip_hashes(INDEX_HEADING)
    kept = (
        [s for s in survivors if _strip_hashes(s.heading) != index_name]
        if prior
        else survivors
    )

    all_archived = prior + archived
    header = _roadmap_archive_header(all_archived, "ROADMAP.md")
    body = _archive_body(all_archived)
    if body != "".join(s.text for s in all_archived):
        raise ConservationError(
            "the archive body is not the archived sections, verbatim and in order"
        )
    archive_text = header + body

    roadmap_text = preamble + "".join(s.text for s in kept)
    if all_archived:
        if not roadmap_text.endswith("\n"):
            roadmap_text += "\n"
        roadmap_text += "\n" + _roadmap_index_section(all_archived, archive_path)

    for section in all_archived:
        if section.text not in archive_text:
            raise ConservationError(
                f"archived section is missing from the archive: {section.heading}"
            )
    for section in kept:
        if section.text not in roadmap_text:
            raise ConservationError(f"surviving section was damaged: {section.heading}")

    return RoadmapPlan(
        roadmap_text=roadmap_text,
        archive_text=archive_text,
        archive_header=header,
        kept=kept,
        archived=archived,
    )


def _ledger_archive_header(archived: list[Section], source: str) -> str:
    """Return the ledger archive's header - what it is and how to read it."""
    oldest = archived[-1].heading if archived else "none"
    newest = archived[0].heading if archived else "none"
    return (
        "# Lanternlight ledger archive\n"
        "\n"
        f"The OLDEST entries of [`{source}`]({Path(source).name}), moved out whole so\n"
        "the live ledger stays readable. Filed under ROADMAP `OPS-57`.\n"
        "\n"
        "The ledger is append-only and newest-first. Nothing here was edited,\n"
        "reordered or reflowed: this file is a contiguous TAIL of the original\n"
        "document, verbatim, still newest-first within itself. The live ledger\n"
        "continues to hold the newest entries and points here for the rest.\n"
        "\n"
        f"Entries in this archive: {len(archived)}.\n"
        f"Newest archived: {_strip_hashes(newest)}\n"
        f"Oldest archived: {_strip_hashes(oldest)}\n"
        "\n"
        "---\n"
        "\n"
    )


def _ledger_entries(text: str, base: int = 0) -> tuple[str, list[Section]]:
    """Split ledger text into the run-in before the first entry and the entries.

    Used for the live document below its marker and, unchanged, for an existing
    archive document below its header. Offsets are reported relative to ``base``
    so a caller scanning a slice can still address the original.
    """
    pattern = re.compile(r"^### LL-", re.MULTILINE)
    starts = [match.start() for match in pattern.finditer(text)]
    gap = text[: starts[0]] if starts else text
    bounds = [*starts, len(text)]
    entries = [
        Section(
            heading=text[start : bounds[index + 1]].split("\n", 1)[0],
            text=text[start : bounds[index + 1]],
            start=base + start,
            end=base + bounds[index + 1],
        )
        for index, start in enumerate(starts)
    ]
    return gap, entries


def plan_ledger_split(
    text: str, keep_entries: int, existing_archive: str = ""
) -> LedgerPlan:
    """Plan the ledger split. Returns new text for both documents; writes none.

    The live ledger keeps everything from the start of the file through the
    insertion marker byte for byte, then the newest ``keep_entries`` entries.
    The archive takes the remaining OLDEST entries, verbatim, in their original
    order. Entries are only ever counted BELOW the marker, so the
    ``### LL-0000 - YYYY-MM-DD`` format template that sits above it in the head
    is never mistaken for an entry.

    Args:
        text: The current ledger document.
        keep_entries: How many of the newest entries stay in the live document.
            A value at or above the entry count archives nothing.
        existing_archive: The ledger archive as it stands today, when there is
            one. Supplying it makes the plan ADDITIVE: the entries this run
            moves are PREPENDED to the ones already archived, because the
            archive is newest-first and this run's entries are the newer ones.
            Omitting it is correct only for a first split.

    Returns:
        A :class:`LedgerPlan`. ``archived`` lists only the entries THIS run
        moves; entries carried over from ``existing_archive`` are in
        ``archive_text`` but not in ``archived``.

    Raises:
        LedgerMarkerMissing: If ``text`` carries no insertion marker.
        ValueError: If ``keep_entries`` is negative.
        ConservationError: If the split would not reproduce the original text
            when the live document and the archived tail are concatenated.
    """
    if keep_entries < 0:
        raise ValueError("keep_entries must not be negative")

    marker_at = text.find(LEDGER_MARKER)
    if marker_at == -1:
        raise LedgerMarkerMissing(
            "no insertion marker in the ledger text: " + LEDGER_MARKER
        )
    cut = marker_at + len(LEDGER_MARKER)
    head, tail = text[:cut], text[cut:]

    gap, entries = _ledger_entries(tail, base=cut)
    if head + gap + "".join(e.text for e in entries) != text:
        raise ConservationError("entry scan did not round-trip the ledger")

    prior: list[Section] = []
    if existing_archive:
        _, prior = _ledger_entries(existing_archive)
        if not prior:
            raise ConservationError(
                "the existing archive text carries no entries to carry forward"
            )

    kept = entries[:keep_entries]
    archived = entries[keep_entries:]

    body = _archive_body(archived)
    ledger_text = head + gap + "".join(e.text for e in kept)
    if ledger_text + body != text:
        raise ConservationError(
            "the live ledger plus the archived tail does not reproduce the original"
        )
    if ledger_text[:cut] != text[:cut]:
        raise ConservationError("the ledger head through the marker was modified")

    all_archived = archived + prior
    header = _ledger_archive_header(all_archived, "docs/LEDGER.md")
    archive_text = header + _archive_body(all_archived)
    for entry in all_archived:
        if entry.text not in archive_text:
            raise ConservationError(
                f"archived entry is missing from the archive: {entry.heading}"
            )

    return LedgerPlan(
        ledger_text=ledger_text,
        archive_text=archive_text,
        archive_header=header,
        kept=kept,
        archived=archived,
    )


def _read_if_present(path: Path) -> str:
    """Return ``path``'s text, or ``""`` when it does not exist yet.

    A missing archive and an empty one mean the same thing to the planners -
    there is nothing to carry forward - so this deliberately does NOT
    distinguish them. That is safe here and only here: everywhere else in this
    repository a missing file and an empty one are different facts.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main(argv: list[str] | None = None) -> int:
    """Print a DRY RUN report for both documents. Writes nothing, ever.

    Applying a plan is a separate, deliberate act - see the module docstring.
    """
    parser = argparse.ArgumentParser(
        prog="doc_archive",
        description="Report what an OPS-57 continuity-document split would move. Writes nothing.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_LEDGER_KEEP,
        help=f"newest ledger entries to keep live (default {DEFAULT_LEDGER_KEEP})",
    )
    args = parser.parse_args(argv)

    roadmap_path = REPO_ROOT / "ROADMAP.md"
    ledger_path = REPO_ROOT / "docs/LEDGER.md"
    roadmap = roadmap_path.read_text(encoding="utf-8")
    ledger = ledger_path.read_text(encoding="utf-8")

    # READ THE ARCHIVES THAT ALREADY EXIST, and pass them in. Planning without
    # them describes a split that REPLACES the archive rather than adding to
    # it: measured 2026-09-08, the report claimed an archive of 15,502
    # characters while the real one held 475,473 across 65 sections.
    #
    # This is the only report anyone reads before deciding, and both
    # `ROADMAP.md` and `tools/doc_size_budget.py` tell the next session to
    # RE-RUN this split when a budget fires. So re-running is the documented
    # path, and describing the destructive plan on that path is worse than
    # printing nothing. A missing archive reads as empty, which is exactly the
    # first-split case.
    roadmap_plan = plan_roadmap_split(
        roadmap,
        DEFAULT_ROADMAP_ARCHIVE,
        existing_archive=_read_if_present(REPO_ROOT / DEFAULT_ROADMAP_ARCHIVE),
    )
    ledger_plan = plan_ledger_split(
        ledger,
        args.keep,
        existing_archive=_read_if_present(REPO_ROOT / DEFAULT_LEDGER_ARCHIVE),
    )

    print("OPS-57 document split - DRY RUN, nothing was written")
    print("")
    print("ROADMAP.md")
    print(f"  sections            {len(roadmap_plan.kept) + len(roadmap_plan.archived)}")
    print(f"  kept                {len(roadmap_plan.kept)}")
    print(f"  archived            {len(roadmap_plan.archived)}")
    print(f"  chars now           {len(roadmap)}")
    print(f"  chars after         {len(roadmap_plan.roadmap_text)}")
    print(f"  {DEFAULT_ROADMAP_ARCHIVE:<24}{len(roadmap_plan.archive_text)}")
    print("")
    print("docs/LEDGER.md")
    print(f"  entries             {len(ledger_plan.kept) + len(ledger_plan.archived)}")
    print(f"  kept                {len(ledger_plan.kept)}")
    print(f"  archived            {len(ledger_plan.archived)}")
    print(f"  chars now           {len(ledger)}")
    print(f"  chars after         {len(ledger_plan.ledger_text)}")
    print(f"  {DEFAULT_LEDGER_ARCHIVE:<24}{len(ledger_plan.archive_text)}")
    print("")
    print("Character counts, not git blob bytes. Re-derive budgets from blob")
    print("bytes with tools/doc_size_budget.py after any split is applied.")
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
