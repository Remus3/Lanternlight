"""Who has spent which ``OPS-`` id, derived from the documents at run time.

``OPS-12``. The ``OPS-`` namespace had no allocator. Unlike ``LL-`` ids, which
``ops/loop/ledger.py`` hands out and checks for collisions, an ``OPS-`` id was
picked by a human reading ``ROADMAP.md``. On 2026-08-26 that produced two
collisions at once: ``OPS-7`` and ``OPS-8`` each name two unrelated items,
because somebody resumed numbering from the highest id visible among the OPEN
items rather than the highest ever allocated. ``docs/LEDGER.md`` already knew
about ``LL-0039`` and ``LL-0040``; nothing asked it.

**Nothing here is checked in.** The spent set is recomputed from
``ROADMAP.md`` and ``docs/LEDGER.md`` on every call. A stored list of spent ids
would go stale the first time an item was added without touching it, and this
project's recorded failure mode is exactly that - a filed count that reads as
authoritative and is not.

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
Checked against the repository as it stood on 2026-08-27:

===========  ========  =============  ===============  ===========
id           closures  open headings  closed headings  allocations
===========  ========  =============  ===============  ===========
``OPS-9``    1         0              0                1
``OPS-12``   0         1              0                1
``OPS-7``    1         1              0                **2**
``OPS-8``    2         0              1                **2**
===========  ========  =============  ===============  ===========

Both real collisions are caught and no correctly-numbered item is flagged.

The count is deliberately allowed to UNDER-report. ``OPS-4`` was closed by a
ledger entry whose heading does not use the word "closed", so it scores 0 here.
Under-reporting costs a missed warning; over-reporting would make the guard red
on correct items, and a guard that cries wolf gets switched off. Given the
choice, this one stays quiet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

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
#: item heading from a sub-heading that merely cites an id in passing.
_ROADMAP_HEADING = re.compile(r"^## OPS-(\d+)\.[ \t]*(.*)$", re.MULTILINE)

#: A ledger entry heading: `### LL-0040 - 2026-08-12 - summary`.
_LEDGER_HEADING = re.compile(r"^### (LL-\d+)[ \t]*-[ \t]*\S+[ \t]*-[ \t]*(.*)$", re.MULTILINE)

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


@dataclass(frozen=True)
class RoadmapItem:
    """One ``## OPS-<n>.`` heading found in the roadmap.

    Attributes:
        item_id: The numeric part of the id.
        title: Heading text after the id, verbatim.
        closed: True when the heading carries the word ``CLOSED``.
    """

    item_id: int
    title: str
    closed: bool


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
    *, roadmap: Path | None = None, ledger: Path | None = None
) -> set[int]:
    """Return every ``OPS-`` id mentioned anywhere in the two documents.

    Deliberately wider than :func:`over_allocated`'s notion of allocation. For
    deciding whether an id is FREE, any mention at all is disqualifying - an id
    discussed in a ledger entry but never given a heading is still an id a
    reader will associate with that discussion.
    """
    roadmap = roadmap or default_roadmap_path()
    ledger = ledger or default_ledger_path()
    text = _read(roadmap) + "\n" + _read(ledger)
    return {int(match.group(1)) for match in _ANY_ID.finditer(text)}


def next_free_id(*, roadmap: Path | None = None, ledger: Path | None = None) -> int:
    """Return the lowest id above everything ever spent.

    Above the MAXIMUM, not the lowest gap. A gap in the sequence means an id
    was retired or reserved, and handing it out again re-creates precisely the
    confusion this module exists to prevent.
    """
    spent = spent_ids(roadmap=roadmap, ledger=ledger)
    return max(spent) + 1 if spent else 1


def roadmap_items(*, roadmap: Path | None = None) -> list[RoadmapItem]:
    """Return every ``## OPS-<n>.`` item heading in the roadmap, in file order."""
    text = _read(roadmap or default_roadmap_path())
    return [
        RoadmapItem(
            item_id=int(match.group(1)),
            title=match.group(2).strip(),
            closed=bool(_CLOSED_WORD.search(match.group(2))),
        )
        for match in _ROADMAP_HEADING.finditer(text)
    ]


def ledger_closures(*, ledger: Path | None = None) -> dict[int, list[str]]:
    """Map each id to the ledger entries whose HEADING announces its closure.

    Only entry headings are read, never entry bodies. A body mentions ids for
    all sorts of reasons - an open item filed in passing, a cross-reference, a
    lesson - and counting those would flag correct items.

    One heading may close several ids: ``LL-0042`` reads
    ``OPS-1, OPS-3 and OPS-5 closed - ...`` and credits all three.
    """
    text = _read(ledger or default_ledger_path())
    closures: dict[int, list[str]] = {}
    for match in _LEDGER_HEADING.finditer(text):
        entry_id, summary = match.group(1), match.group(2)
        if "closed" not in summary.lower():
            continue
        for found in _ANY_ID.finditer(summary):
            closures.setdefault(int(found.group(1)), []).append(entry_id)
    return closures


def over_allocated(
    *, roadmap: Path | None = None, ledger: Path | None = None
) -> dict[int, Collision]:
    """Return every id that names more than one item, with its evidence.

    See this module's docstring for the counting rule and for why it is allowed
    to under-report but never to over-report.
    """
    items = roadmap_items(roadmap=roadmap)
    closures = ledger_closures(ledger=ledger)

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

        sites = [f"ROADMAP.md: ## OPS-{item_id}. {item.title}" for item in headings]
        sites.extend(f"docs/LEDGER.md: {entry} closes OPS-{item_id}" for entry in closed_by)
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
