"""Prove every archived roadmap item is still reachable from ``ROADMAP.md``.

ROADMAP ``OPS-57`` criterion 6. ``ROADMAP.md`` is being split: its CLOSED and
REFUTED sections move verbatim into an archive document, and the roadmap keeps
a one-line stub per archived item that links into the archive. Criterion 6
says a test must prove the entry point actually RESOLVES rather than asserting
only that the archive file exists, because "a file that exists and is
unreferenced is the invisible-work failure" - an archive nobody is told about
is that failure wearing a tidy filename.

REACHABILITY IS CHECKED IN BOTH DIRECTIONS, because each direction fails in a
different way and neither implies the other:

1. Every ``## `` heading in the ARCHIVE must have a stub in the ROADMAP that
   links to it. An archived item with no stub is unreachable in one hop from
   the roadmap, which is the exact failure the criterion names.
2. Every stub link in the ROADMAP must resolve to a heading that actually
   exists in the archive. A stub pointing at a heading that is not there is a
   dangling entry point, and it is the more dangerous of the two: the stub line
   is present, so a human skimming the archived-items list reads full coverage,
   and the link lands nowhere.

THE ANCHOR RULE, STATED EXACTLY, BECAUSE A NEAR-MISS IS THE WHOLE BUG.
:func:`anchor_for` lowercases the heading, replaces each space with a hyphen,
and then drops every character that is not ``a-z``, ``0-9`` or ``-``. Runs of
hyphens are PRESERVED, never collapsed: this repository's headings are written
as ``OPS-49. ... - CLOSED 2026-09-07``, so the `` - `` clause break becomes
``---`` and a rule that collapsed it would disagree with every real link.

THE DIVERGENCE FROM GITHUB THAT USED TO BE RECORDED HERE IS GONE - ``OPS-117``
item 2. This rule once dropped underscores, so ``_dead_pid()`` slugged to
``deadpid`` here and ``_dead_pid`` on github.com, and this paragraph said that
if an underscore heading were ever found not to jump on github.com, the fix was
to change this function and re-derive the stubs together. On 2026-10-03 the
rendered archive was read and every underscore stub, plus one whose heading
carried ``<a date that has passed>`` (rendered as an HTML tag and dropped), was
a dead link there. Both slug functions now keep ``_`` and drop raw HTML tags,
the stubs were re-derived in the same commit, and
``tests/test_archive_link_guard.py`` pins both functions to anchors read off
the rendered page.

DUPLICATE SLUGS ARE MODELED THE WAY GITHUB NUMBERS THEM - ``OPS-118`` item 3.
GitHub anchors EVERY heading level in document order and renders the second
heading whose slug is ``S`` as ``S-1``. :func:`rendered_headings` reproduces
that assignment, and the check judges stubs by where an anchor really lands:
a ``## `` item whose slug the title or a ``### `` sub-part already took is
``shadowed`` (a stub to the bare slug would land on the other heading while
reading as fine), and a stub that relies on an ``S-1`` suffix is
``duplicate_suffix``, because it reaches its item only by position.

WHAT COUNTS AS A STUB. Only a Markdown link whose target is the archive path
AND carries a ``#fragment`` is a stub. A fragment-less link to the archive as a
whole is a pointer to the document, not an entry point to an item, and counting
it as one would let a single "see the archive" sentence satisfy reachability
for every archived item at once.

DID NOT RUN IS A THIRD ANSWER, NEVER A PASS. Before the split has happened the
archive file does not exist, and :func:`check_repo` reports ``ran=False`` with
an explicit reason instead of returning an empty finding list that a caller
would read as green. That escape hatch is deliberately narrow: if the roadmap
already carries stub links to the archive and the archive is missing, the guard
RUNS and reports ``archive_missing`` as a hard failure, because at that point
the entry point is dangling for real.

THE COMMAND LINE REFUSES WHAT IT DOES NOT UNDERSTAND - ROADMAP ``OPS-64``.
:func:`main` used to take no parameters and read ``sys.argv`` not at all, so
a flag naming a scratch file was not rejected - it was never seen, and the
guard printed a green line about the REAL documents. The refutation pass
that filed OPS-64 was misled by exactly that. Two changes answer it, and
both are needed: the options ``--repo-root``, ``--roadmap`` and ``--archive``
are REAL, in that each one changes which documents are read, and anything
else is a usage error with its own exit code. Every run also prints the
scope it read, so a verdict cannot be mistaken for an answer about a
different pair of documents.

Nothing here returns early on the first problem. Every unreachable heading,
every dangling anchor and every ambiguous duplicate in one run is collected
into a single :class:`Report`, since a scan that stopped at the first bad item
would hide every problem after it.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ARCHIVE_REL_PATH",
    "REPO_ROOT",
    "ROADMAP_REL_PATH",
    "USAGE_EXIT_CODE",
    "Finding",
    "Report",
    "anchor_for",
    "build_parser",
    "check_repo",
    "check_texts",
    "iter_headings",
    "main",
    "rendered_headings",
    "stub_anchors",
]

#: Repository root, resolved from this file's location: tools/archive_link_guard.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Repo-relative path of the document that must carry the stubs.
ROADMAP_REL_PATH = "ROADMAP.md"

#: Repo-relative path the split is expected to write. It does not exist yet;
#: see the module docstring on the DID-NOT-RUN answer. If the split lands under
#: a different name, change this constant - do not add a second guessed path,
#: because a guard that searches for its own input can never say "missing".
ARCHIVE_REL_PATH = "docs/ROADMAP_ARCHIVE.md"

#: A fenced-code delimiter: three or more backticks or tildes, optionally
#: indented. Fenced regions are skipped by every scan here - a `## ` line
#: inside a shell block is a comment, not a heading, and a link inside one is
#: not a live link.
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

#: A top-level (`## `) Markdown heading. `###` and deeper are sub-parts of an
#: item, not items.
_H2_RE = re.compile(r"^##\s+(\S.*?)\s*$")

#: An ATX heading of ANY level, `#` to `######`. GitHub assigns an anchor to
#: every one of them, which is what the duplicate-suffix model below needs.
#: Same shape as :data:`_H2_RE` on purpose (no indent, no closing-`#` strip),
#: so the level-2 subset of this scan is exactly :func:`iter_headings`.
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")

#: A trailing GitHub duplicate-heading suffix: `-1`, `-2`, ...
_SUFFIX_RE = re.compile(r"^(.+)-([1-9][0-9]*)$")

#: An inline Markdown link target: the `(...)` half of `[text](target)`.
_LINK_RE = re.compile(r"\]\(\s*([^()\s]+)\s*\)")


@dataclass(frozen=True)
class Finding:
    """One reachability problem found in a single run.

    ``kind`` is one of:

    ``"unreachable"``
        An archive heading with no roadmap stub linking to its anchor. This is
        the failure OPS-57 criterion 6 names directly.
    ``"dangling"``
        A roadmap stub whose anchor matches no archive heading. Reads as
        coverage from the roadmap side and resolves to nothing.
    ``"ambiguous"``
        Two or more archive headings that derive the SAME anchor. One stub
        appears to satisfy both, so reachability counts stop meaning anything.
    ``"shadowed"``
        An archive ``## `` heading whose slug an EARLIER heading of another
        level (the ``# `` title, a ``### `` sub-part) already took, so GitHub
        renders it with a ``-1`` style suffix and a stub to the bare slug lands
        on the other heading. ``OPS-118`` item 3; the silent case.
    ``"duplicate_suffix"``
        A stub whose anchor is a GitHub duplicate-heading suffix (``S-1``). It
        resolves today, but only by position among duplicates.
    ``"archive_missing"``
        The roadmap links into an archive file that is not on disk.
    ``"roadmap_missing"``
        The roadmap itself could not be read.

    ``heading`` is set when the finding is about a specific archive heading and
    ``anchor`` when it is about a specific anchor; each is ``None`` when it does
    not apply, rather than an empty string, so "no heading involved" stays
    distinguishable from "a heading that is empty".
    """

    kind: str
    detail: str
    heading: str | None = None
    anchor: str | None = None


@dataclass(frozen=True)
class Report:
    """The composed verdict over one roadmap/archive pair.

    ``ran`` says whether the check was able to execute at all; ``ok`` says
    whether it passed. They are separate on purpose. A report with
    ``ran=False`` has ``ok=False`` and no findings - "did not run" is never a
    pass, and a caller inspecting only ``findings`` would otherwise read it as
    one. ``archive_headings`` and ``stub_anchors`` carry what was actually seen,
    so a green verdict over an empty archive is visible as "0 of 0" instead of
    hiding behind the word OK.
    """

    ran: bool
    ok: bool
    findings: tuple[Finding, ...]
    archive_headings: tuple[str, ...] = ()
    stub_anchors: tuple[str, ...] = ()
    reason: str = ""

    def format(self) -> str:
        """Render the report for a human, one finding per line."""
        if not self.ran:
            return f"archive link guard: DID NOT RUN - {self.reason}"
        if self.ok:
            return (
                "archive link guard: OK "
                f"({len(self.archive_headings)} archived heading(s), "
                f"{len(self.stub_anchors)} stub link(s))"
            )
        lines = [
            f"archive link guard: {len(self.findings)} finding(s) "
            f"over {len(self.archive_headings)} archived heading(s) and "
            f"{len(self.stub_anchors)} stub link(s)"
        ]
        lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        return "\n".join(lines)


def anchor_for(heading: str) -> str:
    """Derive the link anchor for a Markdown heading's text.

    GitHub's rule, measured against its rendered page (``OPS-117`` item 2):
    drop raw inline HTML tags, lowercase, spaces to hyphens, then drop every
    character that is not ``a-z``, ``0-9``, ``-`` or ``_``. Hyphen runs are
    preserved - see the module docstring for why collapsing them would
    disagree with every real stub in this repository.

    ``heading`` is the heading TEXT, without its leading ``## ``.
    """
    # Tags are markup only OUTSIDE a code span; inside one GitHub renders the
    # characters literally. Even pieces of a backtick split are outside.
    pieces = heading.strip().split("`")
    text = "".join(
        _RAW_HTML_TAG.sub("", piece) if index % 2 == 0 else piece
        for index, piece in enumerate(pieces)
    )
    lowered = text.lower().replace(" ", "-")
    return "".join(
        ch for ch in lowered if ch.isascii() and (ch.isalnum() or ch in "-_")
    )


#: A raw inline HTML tag as CommonMark recognises one - ``<name attr attr>`` or
#: ``</name>`` - which GitHub renders as markup and then drops, text and all.
#: Measured 2026-10-03: "archiving into <a date that has passed>" anchors as
#: ``archiving-into--`` on github.com. ``OPS-117`` item 2.
_RAW_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s+[^<>]*)?>")


def _uncoded_lines(text: str) -> list[str]:
    """Return ``text``'s lines with fenced-code regions removed.

    An unterminated fence swallows the rest of the document, which is what a
    Markdown renderer does too - matching the renderer is the point, since the
    guard is reasoning about links a reader would actually be able to follow.
    """
    kept: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)[0]
                continue
            kept.append(line)
        elif match and match.group(1)[0] == fence:
            fence = None
    return kept


def iter_headings(text: str) -> list[str]:
    """Return the text of every top-level ``## `` heading, in document order.

    Headings inside fenced code are skipped, and ``###`` or deeper is not a
    top-level item - see :data:`_H2_RE`.
    """
    headings: list[str] = []
    for line in _uncoded_lines(text):
        match = _H2_RE.match(line)
        if match:
            headings.append(match.group(1))
    return headings


def rendered_headings(text: str) -> list[tuple[int, str, str]]:
    """Return ``(level, text, anchor)`` for every heading, as GitHub renders it.

    ``OPS-118`` item 3. GitHub slugs EVERY heading level in document order and
    de-duplicates the result the way github-slugger does: the first heading
    whose slug is ``S`` gets ``S``, and each later one gets ``S-1``, ``S-2``
    and so on, skipping any ``S-n`` an earlier heading already holds - a
    heading literally named ``Foo-1`` takes that slot, and the next ``Foo``
    becomes ``foo-2``. :func:`anchor_for` is the per-heading slug; this is the
    per-DOCUMENT assignment, and only this one says where a link really lands.

    Fenced code is skipped, as everywhere here. NOT modeled, each measured
    absent from both real documents on 2026-10-03: setext headings (every
    ``---`` line there follows a blank line, so it is a thematic break),
    indented or blockquoted ATX headings, and closing ``#`` sequences. Any of
    those appearing would shift the numbering and this function would not
    know.
    """
    occurrences: dict[str, int] = {}
    out: list[tuple[int, str, str]] = []
    for line in _uncoded_lines(text):
        match = _ANY_HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2)
        base = anchor_for(heading)
        result = base
        while result in occurrences:
            occurrences[base] += 1
            result = f"{base}-{occurrences[base]}"
        occurrences[result] = 0
        out.append((len(match.group(1)), heading, result))
    return out


def stub_anchors(text: str, archive_rel_path: str = ARCHIVE_REL_PATH) -> list[str]:
    """Return the ``#fragment`` of every link in ``text`` into the archive.

    A link only counts as a stub when its target names ``archive_rel_path``
    AND carries a fragment; see the module docstring on what counts as a stub.
    A leading ``./`` and Windows-style backslashes are normalized away, since
    both are the same path to a reader and neither should change the verdict.
    Order is preserved and duplicates are kept - two stubs to one anchor is
    information, not noise.
    """
    wanted = archive_rel_path.replace("\\", "/").removeprefix("./")
    found: list[str] = []
    for line in _uncoded_lines(text):
        for target in _LINK_RE.findall(line):
            normalized = target.replace("\\", "/")
            if normalized.startswith("./"):
                normalized = normalized[2:]
            path, sep, fragment = normalized.partition("#")
            if not sep or not fragment:
                continue
            if path == wanted or path.endswith("/" + wanted) or path == wanted.rsplit("/", 1)[-1]:
                found.append(fragment)
    return found


def check_texts(
    roadmap_text: str,
    archive_text: str | None,
    archive_rel_path: str = ARCHIVE_REL_PATH,
    roadmap_rel_path: str = ROADMAP_REL_PATH,
) -> Report:
    """Check reachability between a roadmap text and an archive text.

    ``roadmap_rel_path`` is used for MESSAGES ONLY - the roadmap's text is
    already a parameter, so this is the name the findings should call it by.
    It exists because :func:`main` can be pointed at another roadmap
    (``OPS-64``), and a finding that named the default document while reporting
    about a different one would be the same "true answer to a different
    question" defect one level down, inside the message a reader acts on.

    ``archive_text`` is ``None`` when the archive file does not exist. That is
    the DID-NOT-RUN case only while the roadmap carries NO stub links into the
    archive; once it does, a missing archive is a dangling entry point and a
    hard failure. See the module docstring.

    Never returns early: every problem in both directions is collected.
    """
    anchors = stub_anchors(roadmap_text, archive_rel_path)

    if archive_text is None:
        if not anchors:
            return Report(
                ran=False,
                ok=False,
                findings=(),
                reason=(
                    f"{archive_rel_path} does not exist and {roadmap_rel_path} "
                    "links to no anchor in it - the split has not happened yet, "
                    "so there is nothing to check. This is NOT a pass."
                ),
            )
        findings = (
            Finding(
                kind="archive_missing",
                detail=(
                    f"{archive_rel_path}: MISSING, but {roadmap_rel_path} carries "
                    f"{len(anchors)} stub link(s) into it - every one of those "
                    "entry points is dangling"
                ),
            ),
        )
        return Report(
            ran=True,
            ok=False,
            findings=findings,
            archive_headings=(),
            stub_anchors=tuple(anchors),
        )

    headings = iter_headings(archive_text)
    findings: list[Finding] = []

    # Where GitHub really puts each anchor, over EVERY heading level in
    # document order - OPS-118 item 3. `by_anchor` maps a rendered anchor to
    # the heading that holds it; `items` is the `## ` subset, in order, and is
    # the same list as `headings` because both scans share one line shape.
    rendered = rendered_headings(archive_text)
    by_anchor = {anchor: (level, text) for level, text, anchor in rendered}
    items = [(text, anchor) for level, text, anchor in rendered if level == 2]

    # Direction 1: every archived heading needs a stub that resolves to it.
    # Built as a list of (anchor, heading) pairs rather than a dict so a
    # duplicate anchor is visible instead of being silently overwritten.
    seen: dict[str, str] = {}
    anchor_set = set(anchors)
    for heading, rendered_anchor in items:
        anchor = anchor_for(heading)
        holder_level, holder_text = by_anchor.get(anchor, (2, heading))
        if rendered_anchor != anchor and holder_level != 2:
            # The silent case: a stub to #anchor resolves - to the WRONG
            # heading - so neither direction below would object on its own.
            findings.append(
                Finding(
                    kind="shadowed",
                    detail=(
                        f"archive heading '## {heading}' renders as "
                        f"#{rendered_anchor} on GitHub, because the earlier "
                        f"heading '{'#' * holder_level} {holder_text}' already "
                        f"took #{anchor} - a stub to #{anchor} lands on that "
                        "heading, not on this item"
                    ),
                    heading=heading,
                    anchor=rendered_anchor,
                )
            )
        if anchor in seen:
            findings.append(
                Finding(
                    kind="ambiguous",
                    detail=(
                        f"two archive headings derive the same anchor "
                        f"'{anchor}': {seen[anchor]!r} and {heading!r} - one "
                        "stub would appear to satisfy both"
                    ),
                    heading=heading,
                    anchor=anchor,
                )
            )
        else:
            seen[anchor] = heading
        if rendered_anchor not in anchor_set:
            findings.append(
                Finding(
                    kind="unreachable",
                    detail=(
                        f"archived item has no stub in {roadmap_rel_path}: "
                        f"{heading} (expected a link to "
                        f"{archive_rel_path}#{rendered_anchor})"
                    ),
                    heading=heading,
                    anchor=rendered_anchor,
                )
            )

    # Direction 2: every stub must resolve to a `## ` heading that exists,
    # judged by where GitHub RENDERS each anchor rather than by the slug alone.
    item_by_anchor = {anchor: heading for heading, anchor in items}
    reported: set[str] = set()
    for anchor in anchors:
        if anchor in reported:
            continue
        if anchor in item_by_anchor:
            heading = item_by_anchor[anchor]
            base = anchor_for(heading)
            if anchor == base:
                continue
            reported.add(anchor)
            findings.append(
                Finding(
                    kind="duplicate_suffix",
                    detail=(
                        f"stub in {roadmap_rel_path} links to "
                        f"{archive_rel_path}#{anchor}, a GitHub duplicate-"
                        f"heading suffix of #{base}: it reaches {heading!r} "
                        "only by its POSITION among headings sharing that "
                        "slug, so adding or removing an earlier duplicate "
                        "silently moves it"
                    ),
                    heading=heading,
                    anchor=anchor,
                )
            )
            continue
        reported.add(anchor)
        if anchor in by_anchor:
            level, text = by_anchor[anchor]
            why = (
                f"which GitHub renders on the heading '{'#' * level} {text}' - "
                "not an archived '## ' item"
            )
        else:
            why = "which matches no '## ' heading in the archive"
            suffix = _SUFFIX_RE.match(anchor)
            if suffix and suffix.group(1) in by_anchor:
                why += (
                    f" - it ends in a GitHub duplicate-heading suffix of "
                    f"#{suffix.group(1)}, but the archive renders no such "
                    "duplicate"
                )
        findings.append(
            Finding(
                kind="dangling",
                detail=(
                    f"stub in {roadmap_rel_path} links to "
                    f"{archive_rel_path}#{anchor}, {why}"
                ),
                anchor=anchor,
            )
        )

    return Report(
        ran=True,
        ok=not findings,
        findings=tuple(findings),
        archive_headings=tuple(headings),
        stub_anchors=tuple(anchors),
    )


def check_repo(
    repo_root: Path = REPO_ROOT,
    roadmap_rel_path: str = ROADMAP_REL_PATH,
    archive_rel_path: str = ARCHIVE_REL_PATH,
) -> Report:
    """Run the check against real files under ``repo_root``.

    A missing roadmap is DID-NOT-RUN with its own reason: without the roadmap
    there is no side to check reachability FROM, and reporting an empty pass
    would be the vacuous answer this module exists to avoid.
    """
    roadmap_path = repo_root / roadmap_rel_path
    if not roadmap_path.is_file():
        return Report(
            ran=False,
            ok=False,
            findings=(),
            reason=f"{roadmap_rel_path} does not exist under {repo_root}",
        )
    archive_path = repo_root / archive_rel_path
    archive_text = (
        archive_path.read_text(encoding="utf-8") if archive_path.is_file() else None
    )
    return check_texts(
        roadmap_text=roadmap_path.read_text(encoding="utf-8"),
        archive_text=archive_text,
        archive_rel_path=archive_rel_path,
        roadmap_rel_path=roadmap_rel_path,
    )


#: Exit code for a usage error - a flag this guard does not understand, or a
#: positional argument it takes none of. Deliberately NOT 1: 1 means the check
#: ran and the documents are wrong, and a caller that cannot tell "you typed
#: something I do not understand" from "reachability is broken" learns nothing
#: from either. Matches ``argparse``'s own choice and the sibling guard's.
USAGE_EXIT_CODE = 2


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for :func:`main`.

    THE OPTIONS ARE REAL, WHICH IS THE POINT OF ``OPS-64``. Each one is passed
    straight through to :func:`check_repo`, so it changes which files are read
    and which link target counts as a stub. A flag that were accepted and
    ignored would be worse than one refused, because the resulting verdict is
    true about a corpus the caller did not ask about.

    ``--roadmap`` and ``--archive`` are REPO-RELATIVE paths, resolved under
    ``--repo-root``, matching :func:`check_repo`'s own parameters. The archive
    path is also the string a roadmap link must name to count as a stub, so
    changing it changes the reachability question and not only the file opened.
    An absolute path given to either still resolves - :class:`pathlib.Path`
    joining prefers the absolute right-hand side - but then the stub matcher is
    comparing link targets against an absolute string, which is unlikely to be
    how any real document is written. Point ``--repo-root`` at the tree instead.

    ABBREVIATION IS DISABLED ON PURPOSE. ``argparse`` accepts any unambiguous
    prefix by default, so ``--arch`` would silently mean ``--archive``. That is
    the same class of defect this item was filed against - a caller getting an
    answer about something other than what they typed - one level down, so only
    exact spellings are accepted here.
    """
    parser = argparse.ArgumentParser(
        prog="archive_link_guard",
        description=(
            "Prove every archived roadmap item is still reachable from the "
            "roadmap, in both directions. Reads two documents and writes nothing."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        metavar="PATH",
        help="tree the two documents are read from (default: this repository)",
    )
    parser.add_argument(
        "--roadmap",
        default=ROADMAP_REL_PATH,
        metavar="REL_PATH",
        help=(
            "document that must carry the stubs, relative to --repo-root "
            f"(default: {ROADMAP_REL_PATH})"
        ),
    )
    parser.add_argument(
        "--archive",
        default=ARCHIVE_REL_PATH,
        metavar="REL_PATH",
        help=(
            "archive the stubs must link into, relative to --repo-root, and the "
            "path a link must name to count as a stub "
            f"(default: {ARCHIVE_REL_PATH})"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the check and print a human report. ``ROADMAP.md`` ``OPS-64``.

    ``argv`` is the argument list WITHOUT the program name; ``None`` means read
    ``sys.argv[1:]``, which is what the module's own ``__main__`` block relies
    on. An in-process caller - a test, most often - should pass an explicit
    list, because a test runner's ``sys.argv`` is not this guard's and would now
    be refused rather than ignored.

    EXIT CODES, KEPT DISTINCT BECAUSE THEY ARE DIFFERENT FACTS:

    ``0``
        The check ran and passed, OR it reported DID NOT RUN, OR ``--help`` was
        asked for. A did-not-run report exits 0 because it has found no defect
        and must not block work on a tree where the split has simply not
        happened yet - but it prints DID NOT RUN, so a reader is never told OK
        by something that checked nothing.
    ``1``
        The check ran and found a reachability defect.
    ``2``
        A usage error: an unknown flag, or a positional argument. See
        :data:`USAGE_EXIT_CODE`.

    WHY ``argparse``'S ``SystemExit`` IS CAUGHT AND TURNED BACK INTO A RETURN
    VALUE. ``parse_args`` exits the process on a usage error, which would make
    every in-process caller wrap this function in ``pytest.raises`` and would
    make the return type a lie. Catching it keeps the contract "``main``
    returns an int, always" - and the code is taken FROM the exception rather
    than replaced, so ``--help``'s 0 stays 0 while an error's 2 stays 2.
    ``argparse`` has already written its own message, naming the offending
    argument, to stderr by then; the ``str`` branch below exists only for the
    documented case where ``SystemExit`` carries a message instead of a code.

    EVERY RUN PRINTS ITS OWN SCOPE. That is the OPS-64 defect stated
    positively: the refutation pass that filed this item was misled by a green
    line that named nothing, so the verdict now says which root, roadmap and
    archive produced it. A verdict that cannot be mistaken for an answer about
    a different corpus is the whole deliverable here.
    """
    args_list = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return USAGE_EXIT_CODE

    repo_root = Path(args.repo_root)
    print(
        f"archive link guard: scope {args.roadmap} vs {args.archive} "
        f"under {repo_root}"
    )
    report = check_repo(
        repo_root=repo_root,
        roadmap_rel_path=args.roadmap,
        archive_rel_path=args.archive,
    )
    print(report.format())
    return 0 if (not report.ran or report.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
