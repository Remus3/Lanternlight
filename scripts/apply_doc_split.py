"""Apply an OPS-57 continuity-document split, after re-proving it loses nothing.

ROADMAP ``OPS-80``. ``tools/doc_archive.py`` PLANS the split of ``ROADMAP.md``
and ``docs/LEDGER.md`` into their archives. It deliberately writes nothing:
every function in it takes text and returns text, and its ``main`` is a dry run
that prints a report. ``CLAUDE.md`` nevertheless told a session under a fired
size budget to re-run that module, which is a remedy that changes no file - so
the one session most likely to read the instruction was a cold one, under a
fired budget, sent to a tool that could not help it. This script is the missing
half.

WHY A SEPARATE SCRIPT AND NOT A ``--apply`` FLAG, recorded because ``OPS-80``
criterion 5 asks for the choice and its reasoning rather than just the result.
Three shapes were open: a flag on the existing tool, a separate script, or a
documented manual procedure.

* A manual procedure was rejected first. The failure being fixed is a cold
  session following a written instruction; replacing one paragraph of prose
  with a longer paragraph of prose leaves the remedy unexecutable and
  unverifiable, and nothing could be tested.
* A ``--apply`` flag on ``tools/doc_archive.py`` was rejected because it would
  make that module's central promise conditional. The promise is not "this
  module usually writes nothing" - it is "nothing here opens a file for
  writing", which is a property a reader can check by grepping the module for a
  write and which stops being checkable the moment one exists behind a flag.
  That module is also imported by its own test suite and by the dry-run path;
  a writer living in the same file is a writer one typo away from running.
* A separate script keeps the planner pure and makes the applying step a
  deliberate act with its own name, its own test module and its own default.
  The default here is still a report: writing requires ``--apply``, spelled
  out, because this repository's own history is of tools that did more than
  their name promised.

The cost of the split shape, stated rather than hidden: there are now two
entry points where a reader might have expected one, and someone who runs only
``python -m tools.doc_archive`` still gets a report and no change. That is why
the fix is only half done until ``CLAUDE.md`` names this script - criterion 4 -
and why ``tests/test_apply_doc_split.py`` asserts that it does.

THIS SCRIPT RE-DERIVES CONSERVATION; IT DOES NOT TRUST THE PLANNER. The
planning functions already raise :class:`tools.doc_archive.ConservationError`
on a lossy plan, and that is not enough on its own: a guard that reads its
expectation out of the thing it grades cannot fail. So :func:`verify_roadmap`
and :func:`verify_ledger` reassemble the ORIGINAL document out of the plan's
own sections, using the character offsets the planner reported, and demand
exact full-text equality against the source text this script read from disk.
Both would still fail if every assertion inside ``doc_archive`` were deleted.

WHAT IS CONSERVED, EXACTLY, INCLUDING THE ONE THING THAT IS NOT.

* The ledger property is total: ``live + moved_tail == original``, byte for
  byte, because the ledger cut is a contiguous tail of the oldest entries. The
  head through ``<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->`` is additionally
  compared on its own, because ``ops/loop/ledger.py`` appends directly below
  that marker and a reflowed head would break the document's only automated
  writer.
* The roadmap property excludes exactly one section, the generated
  ``## Archive index``. It is regenerated on every run so a single index covers
  old and new archived items, so the source is compared with its previous index
  section removed. Naming that exclusion here is the point; a conservation
  claim that silently drops an unnamed section is worth nothing. The index's
  own correctness - one stub per archived item, every stub resolving - is
  proved separately and in both directions by ``tools/archive_link_guard.py``,
  which is the other half of this guarantee and is run after any apply.
* APPLYING TWICE IS A STRICT FIXED POINT, in all four documents, byte for
  byte. It was not always: the planner used to append a blank line above the
  regenerated index whether or not the junction already had one, so every
  apply grew ``ROADMAP.md`` by exactly one newline at that one spot, forever.
  ROADMAP ``OPS-81`` fixed it in the PLANNER - ``doc_archive._index_separator``
  now tops the junction up to one blank line and can only ever append - so
  nothing here tolerates a whitespace difference any more, and
  ``tests/test_apply_doc_split.py`` compares whole documents.

NOTHING IS WRITTEN UNTIL EVERY DOCUMENT VERIFIES. Both plans are built and both
are verified before the first byte is published, so a roadmap plan that fails
cannot leave a written ledger behind it. Each publish is a temporary file plus
``Path.replace``, which is atomic on Windows for a same-directory rename, and
each is written with ``newline="\\n"`` because Python's text mode would
otherwise turn every ``\\n`` into ``\\r\\n`` on this platform and silently
rewrite the line endings of a document this script exists to leave unchanged.
After the writes, every document is read back off disk and verified again
against the in-memory originals, because a check that ran only against a plan
is a check about intent rather than about the files.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import doc_archive  # noqa: E402

__all__ = [
    "REPO_ROOT",
    "ROADMAP_REL",
    "LEDGER_REL",
    "WRITTEN_PATHS",
    "ApplyRefused",
    "DocumentChange",
    "ApplyReport",
    "write_atomic",
    "verify_roadmap",
    "verify_ledger",
    "plan_split",
    "apply_split",
    "main",
]

#: Repo-relative path of the live roadmap.
ROADMAP_REL = "ROADMAP.md"

#: Repo-relative path of the live ledger.
LEDGER_REL = "docs/LEDGER.md"

#: Every document an apply may rewrite, in a fixed order so a report and a test
#: can address them without re-deriving the list.
WRITTEN_PATHS = (
    ROADMAP_REL,
    doc_archive.DEFAULT_ROADMAP_ARCHIVE,
    LEDGER_REL,
    doc_archive.DEFAULT_LEDGER_ARCHIVE,
)

_H2 = re.compile(r"^## ", re.MULTILINE)
_LEDGER_ENTRY = re.compile(r"^### LL-", re.MULTILINE)


class ApplyRefused(RuntimeError):
    """A plan did not reproduce its source, so nothing was written.

    Raised rather than reported, for the same reason
    :class:`tools.doc_archive.ConservationError` is: a lossy plan that is merely
    printed is a lossy plan somebody applies anyway.
    """


@dataclass(frozen=True)
class DocumentChange:
    """One document's before and after size, in characters.

    Characters, never bytes, and the report says so: the size BUDGETS are
    derived from git blob bytes by ``tools/doc_size_budget.py``, and this
    repository has already been caught treating one number as the other.
    """

    path: str
    chars_before: int
    chars_after: int


@dataclass(frozen=True)
class ApplyReport:
    """What an apply did, or would have done when nothing was written."""

    written: bool
    changes: list[DocumentChange]
    roadmap_archived: int
    roadmap_kept: int
    ledger_archived: int
    ledger_kept: int

    def format(self) -> str:
        """Return the human-readable report, one line per document."""
        if self.written:
            head = "OPS-57 document split - APPLIED"
        else:
            head = "OPS-57 document split - PLAN ONLY, nothing was written"
        lines = [
            head,
            "",
            f"ROADMAP.md      sections kept {self.roadmap_kept}, "
            f"archived this run {self.roadmap_archived}",
            f"docs/LEDGER.md  entries kept {self.ledger_kept}, "
            f"archived this run {self.ledger_archived}",
            "",
        ]
        lines.extend(
            f"  {change.path:<26}{change.chars_before} -> {change.chars_after} chars"
            for change in self.changes
        )
        lines.extend(
            [
                "",
                "Character counts, not git blob bytes. Re-derive the budgets with",
                "python -m tools.doc_size_budget, and prove the index still resolves",
                "with python tools/archive_link_guard.py.",
            ]
        )
        return "\n".join(lines)


def write_atomic(target: Path, text: str) -> None:
    """Publish ``text`` at ``target`` without a reader ever seeing half of it.

    Writes a sibling temporary file and renames it over the target, which is
    the repository's standing rule for anything a reader might poll. The rename
    is the only moment the target changes, so a failure anywhere before it
    leaves the previous content exactly as it was.

    ``newline="\\n"`` is not decoration. Python's text mode translates ``\\n``
    to ``\\r\\n`` on Windows, so the default would rewrite the line endings of
    every document this script touches while ``read_text`` hid the change.

    Args:
        target: The document to publish.
        text: Its complete new content.
    """
    tmp = target.with_name(target.name + ".apply-tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    try:
        tmp.replace(target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _slices(pattern: re.Pattern[str], text: str) -> tuple[str, list[str]]:
    """Return the run-in before the first match and each match's own slice.

    Deliberately a second, local implementation rather than a call into
    ``doc_archive``: reassembling a document with the same code that took it
    apart cannot detect an error in that code.
    """
    starts = [match.start() for match in pattern.finditer(text)]
    if not starts:
        return text, []
    bounds = [*starts, len(text)]
    return text[: starts[0]], [text[starts[i] : bounds[i + 1]] for i in range(len(starts))]


def _body(pattern: re.Pattern[str], text: str) -> str:
    """Return an archive document's text from its first section onward."""
    return "".join(_slices(pattern, text)[1])


def _without_index(text: str) -> str:
    """Return roadmap text with any generated ``## Archive index`` section gone."""
    preamble, sections = _slices(_H2, text)
    return preamble + "".join(
        section for section in sections if not section.startswith(doc_archive.INDEX_HEADING)
    )


def _check_offsets(source: str, sections: list[doc_archive.Section], what: str) -> None:
    """Refuse when a section's text is not what the source holds at its offsets."""
    for section in sections:
        if source[section.start : section.end] != section.text:
            raise ApplyRefused(
                f"{what} does not match its source offsets: {section.heading}"
            )


def verify_roadmap(
    source: str, prior_archive: str, plan: doc_archive.RoadmapPlan
) -> None:
    """Refuse a roadmap plan that does not reproduce ``source``.

    The checks, each of which fails on its own:

    1. Every kept and archived section is byte-identical to the source text at
       the offsets the planner reported.
    2. Those sections, sorted back into source order and prefixed by the
       source's preamble, reproduce the source exactly - with the source's
       previous ``## Archive index`` section removed, that being the one
       section a split regenerates rather than conserves.
    3. The new live document is the preamble and the kept sections verbatim,
       followed by nothing except the regenerated index. The newline run
       between the two is the planner's generated separator; check 3 accepts
       any length of it because the kept-sections prefix is already required
       to be byte-identical, and ROADMAP ``OPS-81`` made the planner emit a
       settled one blank line rather than one more per run.
    4. The new archive is its header, then everything the archive already held,
       then this run's sections, verbatim and in that order.

    Args:
        source: The roadmap text as read from disk.
        prior_archive: The archive text as read from disk, or ``""``.
        plan: The plan to check.

    Raises:
        ApplyRefused: On any failure above. Nothing is written.
    """
    ordered = sorted([*plan.kept, *plan.archived], key=lambda section: section.start)
    if not ordered:
        raise ApplyRefused("the roadmap plan carries no sections at all")
    _check_offsets(source, ordered, "a roadmap section")

    preamble = source[: ordered[0].start]
    rebuilt = preamble + "".join(section.text for section in ordered)
    expected = _without_index(source)
    if rebuilt != expected:
        raise ApplyRefused(
            "the kept and archived sections do not reproduce the source roadmap"
        )

    prefix = preamble + "".join(section.text for section in plan.kept)
    if not plan.roadmap_text.startswith(prefix):
        raise ApplyRefused("the new roadmap does not open with its kept sections verbatim")
    rest = plan.roadmap_text[len(prefix) :]
    if rest.strip() and not rest.lstrip("\n").startswith(doc_archive.INDEX_HEADING):
        raise ApplyRefused("the new roadmap carries text after the kept sections")

    carried = _body(_H2, prior_archive) if prior_archive else ""
    moved = "".join(section.text for section in plan.archived)
    if plan.archive_text != plan.archive_header + carried + moved:
        raise ApplyRefused(
            "the new roadmap archive is not its header, then what it held, then what moved"
        )


def verify_ledger(source: str, prior_archive: str, plan: doc_archive.LedgerPlan) -> None:
    """Refuse a ledger plan that does not reproduce ``source``.

    The ledger is append-only and newest-first, so its property is stronger
    than the roadmap's and is stated as a single equality: the live document
    followed by the moved tail must BE the original, byte for byte. The head
    through the insertion marker is compared separately as well, because that
    is the one region another program writes into.

    Args:
        source: The ledger text as read from disk.
        prior_archive: The ledger archive as read from disk, or ``""``.
        plan: The plan to check.

    Raises:
        ApplyRefused: On any failure. Nothing is written.
    """
    _check_offsets(source, [*plan.kept, *plan.archived], "a ledger entry")

    marker_at = source.find(doc_archive.LEDGER_MARKER)
    if marker_at == -1:
        raise ApplyRefused("the source ledger carries no insertion marker")
    cut = marker_at + len(doc_archive.LEDGER_MARKER)
    if plan.ledger_text[:cut] != source[:cut]:
        raise ApplyRefused("the ledger head through the insertion marker was modified")

    moved = "".join(entry.text for entry in plan.archived)
    if plan.ledger_text + moved != source:
        raise ApplyRefused(
            "the live ledger plus the moved tail does not reproduce the source ledger"
        )

    carried = _body(_LEDGER_ENTRY, prior_archive) if prior_archive else ""
    if plan.archive_text != plan.archive_header + moved + carried:
        raise ApplyRefused(
            "the new ledger archive is not its header, then what moved, then what it held"
        )


def plan_split(
    repo_root: Path, keep_entries: int
) -> tuple[dict[str, str], doc_archive.RoadmapPlan, doc_archive.LedgerPlan]:
    """Read the four documents, plan both splits, and verify both plans.

    Args:
        repo_root: The tree to read. A copy of the repository works as well as
            the repository, which is how the tests exercise this without ever
            making the real documents the subject.
        keep_entries: How many newest ledger entries stay live.

    Returns:
        ``(sources, roadmap_plan, ledger_plan)``, where ``sources`` maps each
        repo-relative path to the text read from it - ``""`` for an archive
        that does not exist yet.

    Raises:
        ApplyRefused: If either plan fails verification. Nothing is written by
            this function under any circumstances.
    """
    sources = {path: _read_if_present(repo_root / path) for path in WRITTEN_PATHS}
    roadmap_plan = doc_archive.plan_roadmap_split(
        sources[ROADMAP_REL],
        doc_archive.DEFAULT_ROADMAP_ARCHIVE,
        existing_archive=sources[doc_archive.DEFAULT_ROADMAP_ARCHIVE],
    )
    ledger_plan = doc_archive.plan_ledger_split(
        sources[LEDGER_REL],
        keep_entries,
        existing_archive=sources[doc_archive.DEFAULT_LEDGER_ARCHIVE],
    )
    verify_roadmap(
        sources[ROADMAP_REL], sources[doc_archive.DEFAULT_ROADMAP_ARCHIVE], roadmap_plan
    )
    verify_ledger(
        sources[LEDGER_REL], sources[doc_archive.DEFAULT_LEDGER_ARCHIVE], ledger_plan
    )
    return sources, roadmap_plan, ledger_plan


def _read_if_present(path: Path) -> str:
    """Return ``path``'s text, or ``""`` when the file does not exist yet."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def apply_split(
    repo_root: Path = REPO_ROOT,
    keep_entries: int = doc_archive.DEFAULT_LEDGER_KEEP,
    *,
    write: bool = True,
) -> ApplyReport:
    """Plan, verify, write, then read back and verify again.

    Args:
        repo_root: The tree to act on.
        keep_entries: How many newest ledger entries stay live.
        write: When False, everything is planned and verified and no file is
            touched. That is the command line's default.

    Returns:
        An :class:`ApplyReport` describing what changed, or would have.

    Raises:
        ApplyRefused: If either plan fails verification before the writes, or
            if the documents read back off disk afterwards do not verify
            against the originals this call started from.
    """
    sources, roadmap_plan, ledger_plan = plan_split(repo_root, keep_entries)
    results = {
        ROADMAP_REL: roadmap_plan.roadmap_text,
        doc_archive.DEFAULT_ROADMAP_ARCHIVE: roadmap_plan.archive_text,
        LEDGER_REL: ledger_plan.ledger_text,
        doc_archive.DEFAULT_LEDGER_ARCHIVE: ledger_plan.archive_text,
    }

    report = ApplyReport(
        written=write,
        changes=[
            DocumentChange(path, len(sources[path]), len(results[path]))
            for path in WRITTEN_PATHS
        ],
        roadmap_archived=len(roadmap_plan.archived),
        roadmap_kept=len(roadmap_plan.kept),
        ledger_archived=len(ledger_plan.archived),
        ledger_kept=len(ledger_plan.kept),
    )
    if not write:
        return report

    for path in WRITTEN_PATHS:
        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(target, results[path])

    # READ BACK. Everything above was a statement about a plan; this is the
    # only statement about the files. A publish that half-succeeded, a stray
    # editor, or a newline translation would all show up here and nowhere else.
    for path in WRITTEN_PATHS:
        if (repo_root / path).read_text(encoding="utf-8") != results[path]:
            raise ApplyRefused(f"the document on disk is not what was published: {path}")
    verify_roadmap(
        sources[ROADMAP_REL], sources[doc_archive.DEFAULT_ROADMAP_ARCHIVE], roadmap_plan
    )
    verify_ledger(
        sources[LEDGER_REL], sources[doc_archive.DEFAULT_LEDGER_ARCHIVE], ledger_plan
    )
    return report


def main(argv: list[str] | None = None) -> int:
    """Report the split, and write it only when ``--apply`` says so.

    The default is deliberately the harmless one. ``tools/doc_archive.py``
    cannot write at all; this script can, so the writing case is the one a
    reader has to type out.
    """
    parser = argparse.ArgumentParser(
        prog="apply_doc_split",
        description=(
            "Apply the OPS-57 split of ROADMAP.md and docs/LEDGER.md into their "
            "archives. Verifies conservation against the source first, and "
            "writes nothing without --apply."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="tree to act on (default: this repository)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=doc_archive.DEFAULT_LEDGER_KEEP,
        help=f"newest ledger entries to keep live (default {doc_archive.DEFAULT_LEDGER_KEEP})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write the four documents; without it nothing is written",
    )
    args = parser.parse_args(argv)

    report = apply_split(args.repo_root.resolve(), args.keep, write=args.apply)
    print(report.format())
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
