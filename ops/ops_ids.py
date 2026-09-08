"""Who has spent which ``OPS-`` id, derived from the documents at run time.

``OPS-12``. The ``OPS-`` namespace had no allocator. Unlike ``LL-`` ids, which
``ops/loop/ledger.py`` hands out and checks for collisions, an ``OPS-`` id was
picked by a human reading ``ROADMAP.md``. On 2026-08-26 that produced two
collisions at once: ``OPS-7`` and ``OPS-8`` each name two unrelated items,
because somebody resumed numbering from the highest id visible among the OPEN
items rather than the highest ever allocated. ``docs/LEDGER.md`` already knew
about ``LL-0039`` and ``LL-0040``; nothing asked it.

**Nothing here is checked in.** The spent set is recomputed on every call from
``ROADMAP.md``, ``docs/LEDGER.md`` and the two archives those were split into
by ``OPS-57``. A stored list of spent ids would go stale the first time an item
was added without touching it, and this project's recorded failure mode is
exactly that - a filed count that reads as authoritative and is not.

Four documents, and EVERY reader here reads all of them
-------------------------------------------------------

``OPS-57`` split the two documents into four: ``ROADMAP.md`` kept its open
sections and an archive index of stubs, ``docs/LEDGER.md`` kept its 60 newest
entries, and the rest moved verbatim into ``docs/ROADMAP_ARCHIVE.md`` and
``docs/LEDGER_ARCHIVE.md``.

**The repair for that split was applied to two of this module's five readers
and it is worth knowing exactly how that looked, because it looked fine.**
:func:`spent_ids` and :func:`next_free_id` learned about the archives;
:func:`roadmap_items`, :func:`ledger_closures` and :func:`over_allocated` did
not. The suite stayed green. The visible result was that :func:`over_allocated`
returned ``{}`` - a clean bill of health for a repository carrying two known
collisions, because ``OPS-7`` and ``OPS-8`` are closed items whose every piece
of evidence had moved into the archives. A detector that answers "nothing is
wrong" because it stopped looking cannot be told apart from one that works.

The general lesson, since a sixth reader will be added one day: when a module
changes WHERE it reads from, that is a change to every reader in it, not to the
ones whose tests happened to be red. ``tests/test_ops_ids.py`` therefore
enumerates the module's public document readers by signature and holds each one
to the archive rule, rather than testing them one at a time.

What counts as ALLOCATING an id
-------------------------------

An id is mentioned in prose constantly; that is not allocation. An id is
*allocated* at one of two places, and only these two are counted:

- a top-level ``## OPS-<n>. <title>`` heading in ``ROADMAP.md``
- a ledger ENTRY heading that announces a closure, e.g.
  ``### LL-0040 - 2026-08-12 - OPS-8 closed - ...``

One item normally produces both over its life: a heading when it is opened, a
closure when it is finished. So a heading marked CLOSED is understood to be
the same item as its closure rather than a second one::

    allocations = closures
                + open_headings
                + max(0, closed_headings - closures)

That formula is what separates the normal lifecycle from a real collision.
Re-derive it rather than trusting a table here; this docstring carried one that
its own commit invalidated, because closing ``OPS-12`` moved that row the
moment ``LL-0068`` was written. What holds is the shape:

- an id closed once, with no roadmap heading, scores 1
- an id with an open heading and no closure scores 1
- an id with a CLOSED heading and its one closure scores 1
- a closure PLUS an open heading scores 2 - a second item took a spent id
- two closures score 2 - an item is closed once

How far this guard can see
--------------------------

**It is blind to four ids that are genuinely in use, and that set is measured,
not estimated - re-derive it rather than trusting the sentence after this one,
which named "4 of the 12 ids in use" and was left behind by a namespace now 63
ids deep.** Re-measured 2026-09-08 across all four documents, the blind set is
unchanged: ``OPS-4``, ``OPS-6``, ``OPS-10`` and ``OPS-11`` all score 0,
because each was opened or closed only in ledger BODY prose - never in an entry
heading and never as a roadmap item heading. ``OPS-6`` is called "THE ONLY OPEN
OPS ITEM" in ``docs/LEDGER.md`` and this module cannot see it at all. A second
``OPS-6`` would not be flagged.

That is the deliberate direction of the error. Reading entry bodies would catch
those four and flag a great many correct items besides, because a body mentions
ids for every reason there is - a cross-reference, a lesson, an open item filed
in passing. Over-reporting makes the guard red on correct work, and a guard
that cries wolf is one people learn to override; that is the argument ``OPS-8``
made about the merge gate, and it applies here.

The blind spot is narrower than it sounds, for one reason worth stating.
:func:`next_free_id` uses :func:`spent_ids`, which counts **any mention
anywhere**, so all four invisible ids are still disqualified from being handed
out. The allocator is what prevents a collision; this detector only catches one
that has already happened because somebody did not use the allocator.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ops import mdscan

__all__ = [
    "Collision",
    "RoadmapItem",
    "default_ledger_path",
    "default_roadmap_path",
    "ledger_closures",
    "next_free_id",
    "over_allocated",
    "roadmap_items",
    "spent_ids",
]

#: Repository root, resolved from this file's location: ops/ops_ids.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Any mention of an id at all. Used for the SPENT set, not for allocation.
_ANY_ID = re.compile(r"\bOPS-(\d+)\b")

#: A top-level roadmap item heading. The trailing dot is what distinguishes an
#: item heading from a sub-heading that merely cites an id in passing. Matched
#: against ONE line at a time, out of :mod:`ops.mdscan`, so a fenced example is
#: never seen - see :func:`roadmap_items`.
_ROADMAP_HEADING = re.compile(r"^## OPS-(\d+)\.[ \t]*(.*)$")

#: A ledger entry heading: `### LL-0040 - 2026-08-12 - summary`. Also matched
#: one unfenced line at a time; `docs/LEDGER.md` carries a fenced entry
#: TEMPLATE in its preamble that this pattern matches perfectly.
_LEDGER_HEADING = re.compile(r"^### (LL-\d+)[ \t]*-[ \t]*\S+[ \t]*-[ \t]*(.*)$")

#: A closure ANNOUNCEMENT: the summary opens with the id, or a list of them,
#: and then the word "closed". Every real closure in `docs/LEDGER.md` follows
#: that convention, including `LL-0042`'s three-id heading.
#:
#: Anchored at the start on purpose. Accepting an id anywhere in a heading that
#: contained "closed" anywhere read `LL-0069`'s summary - "the same bug OPS-9
#: closed, rebuilt in a module written the day after" - as a second closure of
#: `OPS-9`, and reported a collision that does not exist. A heading that TALKS
#: about an id has not allocated it.
_CLOSURE_ANNOUNCEMENT = re.compile(
    r"^((?:OPS-\d+[,\s]*(?:and[ \t]+)?)+)closed\b", re.IGNORECASE
)

#: The status word that marks a roadmap heading as finished. The status
#: vocabulary is uppercase by convention (`NEXT`, `READY`, `BLOCKED`, `OPEN`),
#: so a case-sensitive match will not trip over the word "closed" in prose.
_CLOSED_WORD = re.compile(r"\bCLOSED\b")


def default_roadmap_path() -> Path:
    """Return the path of the roadmap."""
    return REPO_ROOT / "ROADMAP.md"


def default_ledger_path() -> Path:
    """Return the path of the ledger."""
    return REPO_ROOT / "docs" / "LEDGER.md"


def default_archive_paths() -> list[Path]:
    """Return the archive documents that carry ids moved out by ``OPS-57``.

    **Why these are read at all, given that erring wide is this module's whole
    posture.** The split moves closed roadmap sections and the oldest ledger
    entries into archives. The roadmap half is self-protecting: every archived
    section leaves a stub line naming its id, and :func:`spent_ids` matches any
    mention rather than only headings. The LEDGER half leaves nothing behind,
    so an id discussed in an entry but never given a roadmap heading - the case
    :func:`spent_ids` names in its own docstring - goes out with the tail.

    Measured on the split of 2026-09-08: the spent set fell from 60 ids to 55
    without this, losing ``OPS-1``, ``OPS-3``, ``OPS-4``, ``OPS-5`` and
    ``OPS-9``. :func:`next_free_id` was unaffected on that day because it takes
    the maximum and the maximum was recent, which makes this a live hole in
    :func:`spent_ids` and a dormant one in the allocator.

    **That measurement has since gone stale, and the correction is the
    interesting part.** Re-measured 2026-09-08 after the ledger entry recording
    the split was written: the spent set is 63 ids WITH the archives and 63
    WITHOUT, because that entry discusses the very ids the split moved. So the
    archive read is today a DORMANT guard in :func:`spent_ids` - it will matter
    again the moment an old id stops being mentioned live - and a LIVE one in
    :func:`over_allocated`, which loses both known collisions without it.
    Do not re-derive the 60-to-55 figure from this docstring; it is a record of
    one day's documents, not a property of the code.

    A path that does not exist is not an error: a fresh clone has no archive
    until a budget fires, and :func:`_read` already answers a missing file with
    empty text.
    """
    return [
        REPO_ROOT / "docs" / "ROADMAP_ARCHIVE.md",
        REPO_ROOT / "docs" / "LEDGER_ARCHIVE.md",
    ]


def _resolve_archives(
    archives: Sequence[Path] | None, *documents: Path | None
) -> list[Path]:
    """Decide which archives a call meant, from what else it named.

    **This closes an API footgun rather than documenting one.** ``archives=None``
    used to mean "the real repository's archives" unconditionally, so a caller
    who handed the module a fixture ``roadmap`` and ``ledger`` and omitted
    ``archives`` silently measured a THIRD tree - two fixture files plus the
    live repository. The wrong answer looked exactly like a right one: the
    module was asked about a fixture and answered about the repository.

    The rule, in the order it is applied:

    - an explicit ``archives`` sequence is used verbatim, ``[]`` included
    - otherwise, if any document path was named explicitly, NO archives, because
      a caller who scoped the scan to their own tree meant their own tree
    - otherwise the repository defaults, which is what every real caller gets

    A caller who genuinely wants fixture documents beside the real archives can
    still say so with ``archives=default_archive_paths()``. That is one explicit
    line, and it is visible in the call rather than hidden in a default.
    """
    if archives is not None:
        return list(archives)
    if any(document is not None for document in documents):
        return []
    return default_archive_paths()


def _cite(path: Path) -> str:
    """Return a short label for ``path``, for use in a citation.

    Repository-relative where possible so a reader can open the file named. A
    site that says ``ROADMAP.md`` for a heading which now lives in
    ``docs/ROADMAP_ARCHIVE.md`` sends the reader to a file that does not contain
    the line, and the reader concludes the DETECTOR is broken rather than the
    citation.
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


@dataclass(frozen=True)
class RoadmapItem:
    """One ``## OPS-<n>.`` heading found in the roadmap.

    Attributes:
        item_id: The numeric part of the id.
        title: Heading text after the id, verbatim.
        closed: True when the heading carries the word ``CLOSED``.
        source: Label of the document the heading was read from, for citing.
            Defaults to empty so a caller constructing one by hand - a test
            fixture, say - is not forced to invent a provenance it does not
            have. Every heading this module produces carries a real one.
    """

    item_id: int
    title: str
    closed: bool
    source: str = ""


@dataclass(frozen=True)
class Collision:
    """One over-allocated id, with the evidence that says so.

    A bare "id 8 is wrong" is not actionable and cannot be checked by a reader,
    so every flagged id carries the sites that were counted.
    """

    item_id: int
    allocations: int
    sites: tuple[str, ...] = field(default=())


def _read(path: Path) -> str:
    """Return ``path`` as text, or an empty string when it is unreadable.

    Empty rather than raising: this module is consulted by a guard, and a guard
    that explodes on a missing file is a guard that gets removed. An empty read
    reports no ids, which the callers' own positive controls will catch.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def spent_ids(
    *,
    roadmap: Path | None = None,
    ledger: Path | None = None,
    archives: Sequence[Path] | None = None,
) -> set[int]:
    """Return every ``OPS-`` id mentioned anywhere in the documents.

    ``archives`` follows the documents: name a ``roadmap`` or a ``ledger``
    explicitly and it defaults to NONE, name nothing and it defaults to
    :func:`default_archive_paths`. See :func:`_resolve_archives` for why, and
    :func:`default_archive_paths` for why an archive is read at all.

    Deliberately wider than :func:`over_allocated`'s notion of allocation, and
    it does not skip fenced lines either. For deciding whether an id is FREE,
    any mention at all is disqualifying - an id discussed in a ledger entry but
    never given a heading is still an id a reader will associate with that
    discussion, and erring this way can only ever SKIP an id, never reissue one.

    The practical consequence, met immediately: **writing a worked example with
    a real number in it spends that number.** Documenting the fence fix with a
    concrete ``OPS-13`` in ``ROADMAP.md`` pushed this function's answer to 14
    and would have left a future reader hunting for an item that never existed.
    Write examples with a placeholder, not a digit.
    """
    paths = [roadmap or default_roadmap_path(), ledger or default_ledger_path()]
    paths.extend(_resolve_archives(archives, roadmap, ledger))
    text = "\n".join(_read(path) for path in paths)
    return {int(match.group(1)) for match in _ANY_ID.finditer(text)}


def next_free_id(
    *,
    roadmap: Path | None = None,
    ledger: Path | None = None,
    archives: Sequence[Path] | None = None,
) -> int:
    """Return the lowest id above everything ever spent.

    Above the MAXIMUM, not the lowest gap. A gap in the sequence means an id
    was retired or reserved, and handing it out again re-creates precisely the
    confusion this module exists to prevent.

    ``archives`` follows the documents - see :func:`_resolve_archives`.
    """
    spent = spent_ids(roadmap=roadmap, ledger=ledger, archives=archives)
    return max(spent) + 1 if spent else 1


def roadmap_items(
    *, roadmap: Path | None = None, archives: Sequence[Path] | None = None
) -> list[RoadmapItem]:
    """Return every ``## OPS-<n>.`` item heading found, in file order.

    Reads the roadmap AND the archives, because ``OPS-57`` moved 65 closed
    sections out of ``ROADMAP.md`` into ``docs/ROADMAP_ARCHIVE.md`` and an
    allocation does not stop being an allocation when it is filed away. The
    first repair for that split taught only :func:`spent_ids` about the
    archives, which left this function reading half the roadmap; see
    :func:`over_allocated` for what that cost.

    ``archives`` follows the document - see :func:`_resolve_archives`.

    Fenced lines are skipped, via the one shared scan in :mod:`ops.mdscan`. The
    roadmap documents its own id format - the preamble shows how to allocate one
    and the ``OPS-12`` closure quotes the heading form - so a worked example
    inside a code block is a real hazard here, not a hypothetical. Counting one
    would report a live item as over-allocated against itself.
    """
    paths = [roadmap or default_roadmap_path()]
    paths.extend(_resolve_archives(archives, roadmap))
    items = []
    for path in paths:
        label = _cite(path)
        for line in mdscan.scan_unfenced(_read(path)).lines:
            match = _ROADMAP_HEADING.match(line.text)
            if match is None:
                continue
            items.append(
                RoadmapItem(
                    item_id=int(match.group(1)),
                    title=match.group(2).strip(),
                    closed=bool(_CLOSED_WORD.search(match.group(2))),
                    source=label,
                )
            )
    return items


def _closure_sites(
    ledger: Path | None, archives: Sequence[Path] | None
) -> dict[int, list[tuple[str, str]]]:
    """Map each id to ``(entry_id, source_label)`` pairs announcing its closure.

    The private half of :func:`ledger_closures`, which keeps the public return
    shape it already had. The label is needed only so :func:`over_allocated` can
    cite the file an entry was actually read from.
    """
    paths = [ledger or default_ledger_path()]
    paths.extend(_resolve_archives(archives, ledger))
    closures: dict[int, list[tuple[str, str]]] = {}
    for path in paths:
        label = _cite(path)
        for line in mdscan.scan_unfenced(_read(path)).lines:
            match = _LEDGER_HEADING.match(line.text)
            if match is None:
                continue
            entry_id, summary = match.group(1), match.group(2)
            announcement = _CLOSURE_ANNOUNCEMENT.match(summary.strip())
            if announcement is None:
                continue
            for found in _ANY_ID.finditer(announcement.group(1)):
                closures.setdefault(int(found.group(1)), []).append((entry_id, label))
    return closures


def ledger_closures(
    *, ledger: Path | None = None, archives: Sequence[Path] | None = None
) -> dict[int, list[str]]:
    """Map each id to the ledger entries whose HEADING announces its closure.

    Reads the ledger AND the archives. ``OPS-57`` moved the oldest 135 entries
    into ``docs/LEDGER_ARCHIVE.md``, which is where both known collisions'
    closures now live - so without this, the two entries that PROVE ``OPS-7``
    and ``OPS-8`` were each spent twice are invisible.

    ``archives`` follows the document - see :func:`_resolve_archives`.

    Only entry headings are read, never entry bodies. A body mentions ids for
    all sorts of reasons - an open item filed in passing, a cross-reference, a
    lesson - and counting those would flag correct items.

    One heading may close several ids: ``LL-0042`` reads
    ``OPS-1, OPS-3 and OPS-5 closed - ...`` and credits all three.
    """
    return {
        item_id: [entry for entry, _ in sites]
        for item_id, sites in _closure_sites(ledger, archives).items()
    }


def over_allocated(
    *,
    roadmap: Path | None = None,
    ledger: Path | None = None,
    archives: Sequence[Path] | None = None,
) -> dict[int, Collision]:
    """Return every id that names more than one item, with its evidence.

    See this module's docstring for the counting rule and for why it is allowed
    to under-report but never to over-report.

    **Why the archives are not optional here.** ``OPS-57`` moved every closed
    roadmap section and the oldest ledger entries into archives, and both of
    this repository's known collisions - ``OPS-7`` and ``OPS-8`` - are closed
    items whose evidence went with them. Reading only the live documents, this
    function returned ``{}``: a clean bill of health for a repository that has
    carried two collisions for weeks. That is the vacuous guard this project
    fears most, and it arrived not as a bug but as a fix applied to two of the
    module's five readers and not the other three. When a module changes where
    it reads from, every reader in it changes; a half-migrated module reports
    confidently about the half it can still see.

    ``archives`` follows the documents - see :func:`_resolve_archives`.
    """
    items = roadmap_items(roadmap=roadmap, archives=archives)
    closures = _closure_sites(ledger, archives)

    found: dict[int, Collision] = {}
    for item_id in sorted({*(item.item_id for item in items), *closures}):
        headings = [item for item in items if item.item_id == item_id]
        open_headings = [item for item in headings if not item.closed]
        closed_headings = [item for item in headings if item.closed]
        closed_by = closures.get(item_id, [])

        allocations = (
            len(closed_by)
            + len(open_headings)
            + max(0, len(closed_headings) - len(closed_by))
        )
        if allocations <= 1:
            continue

        # Each site names the file it was READ from, never a hardcoded
        # `ROADMAP.md`. After OPS-57 most of this evidence lives in an archive,
        # and a citation pointing at a file that does not contain the line
        # teaches the reader to distrust the detector instead of the citation.
        sites = [
            f"{item.source}: ## OPS-{item_id}. {item.title}" for item in headings
        ]
        sites.extend(
            f"{label}: {entry} closes OPS-{item_id}" for entry, label in closed_by
        )
        found[item_id] = Collision(
            item_id=item_id, allocations=allocations, sites=tuple(sites)
        )
    return found


def format_report(report: dict[int, Collision]) -> str:
    """Render :func:`over_allocated` for a human, newest concern first."""
    if not report:
        return "no OPS- id names more than one item"
    lines = []
    for item_id in sorted(report):
        collision = report[item_id]
        lines.append(f"OPS-{item_id}: {collision.allocations} allocations")
        lines.extend(f"    {site}" for site in collision.sites)
    return "\n".join(lines)
