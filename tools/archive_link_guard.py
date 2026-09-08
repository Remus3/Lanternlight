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

KNOWN, DELIBERATE DIVERGENCE FROM GITHUB'S OWN SLUGGER, recorded here rather
than left as a surprise: GitHub keeps underscores in an anchor, and the rule
above drops them, so a heading containing ``_dead_pid()`` yields ``deadpid``
here and ``_dead_pid`` on github.com. The rule implemented here is the one
OPS-57's dispatch specified and the one this repository's own stubs are written
against, and the guard's job is to match how the link is ACTUALLY WRITTEN. If
the archive is ever browsed on github.com and an underscore heading is found
not to jump, that is a real defect - fix it by changing this function and
re-deriving the stubs together, not by loosening the comparison, since a fuzzy
match here would make the dangling-link check unable to fail.

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

Nothing here returns early on the first problem. Every unreachable heading,
every dangling anchor and every ambiguous duplicate in one run is collected
into a single :class:`Report`, since a scan that stopped at the first bad item
would hide every problem after it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ARCHIVE_REL_PATH",
    "REPO_ROOT",
    "ROADMAP_REL_PATH",
    "Finding",
    "Report",
    "anchor_for",
    "check_repo",
    "check_texts",
    "iter_headings",
    "main",
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

    Lowercase, spaces to hyphens, then drop every character that is not
    ``a-z``, ``0-9`` or ``-``. Hyphen runs are preserved - see the module
    docstring for why collapsing them would disagree with every real stub in
    this repository, and for the deliberate divergence from GitHub over
    underscores.

    ``heading`` is the heading TEXT, without its leading ``## ``.
    """
    lowered = heading.strip().lower().replace(" ", "-")
    return "".join(ch for ch in lowered if ch.isascii() and (ch.isalnum() or ch == "-"))


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
) -> Report:
    """Check reachability between a roadmap text and an archive text.

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
                    f"{archive_rel_path} does not exist and {ROADMAP_REL_PATH} "
                    "links to no anchor in it - the split has not happened yet, "
                    "so there is nothing to check. This is NOT a pass."
                ),
            )
        findings = (
            Finding(
                kind="archive_missing",
                detail=(
                    f"{archive_rel_path}: MISSING, but the roadmap carries "
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

    # Direction 1: every archived heading needs a stub that resolves to it.
    # Built as a list of (anchor, heading) pairs rather than a dict so a
    # duplicate anchor is visible instead of being silently overwritten.
    seen: dict[str, str] = {}
    anchor_set = set(anchors)
    for heading in headings:
        anchor = anchor_for(heading)
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
        if anchor not in anchor_set:
            findings.append(
                Finding(
                    kind="unreachable",
                    detail=(
                        f"archived item has no stub in {ROADMAP_REL_PATH}: "
                        f"{heading} (expected a link to "
                        f"{archive_rel_path}#{anchor})"
                    ),
                    heading=heading,
                    anchor=anchor,
                )
            )

    # Direction 2: every stub must resolve to a heading that exists.
    heading_anchors = {anchor_for(h) for h in headings}
    reported: set[str] = set()
    for anchor in anchors:
        if anchor in heading_anchors or anchor in reported:
            continue
        reported.add(anchor)
        findings.append(
            Finding(
                kind="dangling",
                detail=(
                    f"stub in {ROADMAP_REL_PATH} links to "
                    f"{archive_rel_path}#{anchor}, which matches no '## ' "
                    "heading in the archive"
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
    )


def main() -> int:
    """Run the real check and print a human report.

    Exit code is 1 only for a check that RAN and FAILED. A did-not-run report
    exits 0 - it has found no defect and must not block work on a tree where
    the split has simply not happened yet - but it says DID NOT RUN in its
    output, so a reader is never told OK by something that checked nothing.
    """
    report = check_repo()
    print(report.format())
    return 0 if (not report.ran or report.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
