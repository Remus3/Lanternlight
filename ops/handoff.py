"""Write `LL-NEXT-SESSION.txt`, or refuse to - ROADMAP `OPS-32`.

Until this module existed, nothing wrote the hand-off. A session followed a
document, and the guarantee was "the ritual says to, and a test says the ritual
says to" - a real guarantee about the DOCUMENT and none at all about the FILE.

The hand-off is the highest-variance artifact in this tree. It is rewritten
every session, it is never reviewed before it is written, and it quotes freely
from whatever that session happened to touch: paths, error text, names, command
output. Since 2026-09-06 it is also TRACKED, and this repository is public, so
the distance between "hand-off written" and "hand-off world-readable" is one
push. The commit-time guards already scan it. What was missing is the refusal
BEFORE the bytes land.

THREE RULES, each one an acceptance criterion of `OPS-32`.

1. **The check runs before anything is written.** Not before the replace -
   before the temporary file exists. A refusal that leaves a partial file, or
   that truncates the previous hand-off, has not refused. The tests assert the
   target is absent or byte-unchanged afterwards, not merely that an exception
   came out.
2. **One engine.** The detectors come from :mod:`lanternlight.redact`, the only
   sanctioned path (`ADR-004`). No private copy of the patterns lives here, so a
   rule added to the scrubber starts guarding the hand-off the same day. Three
   passes, matching what the tracked-file guard does: plain, encoded, and the
   literal-joined operator pass.
3. **No exemption list, and no override argument either.** If a legitimate
   hand-off is refused, the hand-off is what changes. An exemption list is a
   gate disarmed one word at a time, and a ``force=True`` is the same thing in
   one word.

WHY ``IPV4`` IS NOT AMONG THE LABELS, stated because a silent exclusion is
indistinguishable from an oversight: a four-part version string is
indistinguishable from a dotted quad by pattern, and a hand-off is full of
version strings. This module scans with the same
:data:`lanternlight.redact.FILE_SCAN_LABELS` the repository-wide guard uses on
every other tracked file, so the hand-off is held to exactly the standard its
neighbours are, no looser and no tighter.

THE ASCII REFUSAL IS NOT PII AND IS DELIBERATE. The hand-off is tracked and this
repository is 7-bit ASCII everywhere, enforced at commit time. Refusing a
non-ASCII character here turns a commit-time failure into a write-time one, at
the moment the session still has the context to fix it.

WHICH TREE's HAND-OFF A WRAP WRITES - ROADMAP `OPS-65`, decided 2026-09-08
--------------------------------------------------------------------------
A wrap writes the hand-off of THE TREE IT IS WRAPPING, and it gets there by
omitting ``--target`` altogether: :data:`DEFAULT_TARGET` is resolved from this
module's own ``__file__``, so a git worktree - where lane sessions run - resolves
its own root and writes its own hand-off.

Measured in two real detached worktrees before the decision was made, because
all three candidate answers in `OPS-65` were defensible until something was
measured:

* Flagless, run from a lane worktree: that worktree's own ``LL-NEXT-SESSION.txt``
  changed, and ``git add LL-NEXT-SESSION.txt`` in that tree staged it, exit 0.
* With an absolute ``--target`` naming a SECOND worktree, run from the lane
  worktree: this writer exited 0 and said nothing, the other tree's tracked file
  changed, ``git status`` in the wrapping tree stayed CLEAN because there was
  nothing there to commit, and staging the written path from the wrapping tree
  failed with ``fatal: ... is outside repository``.

The second measurement is what settles it. The wrap ritual's own step 9 requires
the hand-off to be "rewritten in place, staged, and committed with the session's
other work", and a file living in another checkout cannot be staged by this
tree's index at all. So the absolute form is a defect rather than a deliberate
design, and "a lane wrap writes no hand-off" is refuted from the other side: a
cold session reads that file first, so a lane that hands nothing forward is
exactly the discontinuity this project's continuity design exists to prevent.

TWO CONSEQUENCES, both deliberately weaker than a refusal:

1. An out-of-tree ``--target`` is REPORTED on stderr by the CLI and still
   written. A refusal would need an exemption for the tests, which write to a
   temporary directory outside this tree on purpose, and rule 3 above forbids
   buying a guard with an exemption list. The failure being fixed is a SILENT
   cross-tree write, and a named one is not silent.
2. :func:`scan_instruction_sites` reports any TRACKED instruction that tells a
   wrap to pass an absolute ``--target``. That is the half a red test can hold,
   and it is scoped to the instruction sites - the slash commands, ``CLAUDE.md``
   and the hand-off itself - because `ROADMAP.md` and the ledger have to be able
   to quote the defect they record.

The absolute-path detector is borrowed from :mod:`tools.hook_command_guard`
(`OPS-61`), which already decides what an absolute root looks like in three
spellings and documents its blind spots. Same reason as rule 2: one engine.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    FILE_SCAN_LABELS,
    RedactionError,
    iter_encoded_sensitive,
    iter_literal_joined_operator_identifiers,
    iter_operator_identifiers,
    iter_sensitive,
    operator_git_identities,
)
from tools.hook_command_guard import (  # noqa: E402  (path bootstrap first)
    absolute_paths_in,
)

#: The one hand-off. There is exactly one per tree, rewritten every session, and
#: its git history is the record of what each session handed forward. Resolved
#: from this module's own location on purpose - see the `OPS-65` section above:
#: a worktree runs its own copy of this file and so gets its own hand-off.
DEFAULT_TARGET = REPO_ROOT / "LL-NEXT-SESSION.txt"

#: Where a wrap instruction can live. Positive list rather than an exclusion
#: list: `ROADMAP.md` and `docs/LEDGER.md` record the defect and must be able to
#: quote it, and a guard defined by what it SKIPS grows a skip every time it is
#: inconvenient.
INSTRUCTION_SITE_PATTERNS: tuple[str, ...] = (
    "CLAUDE.md",
    "LL-NEXT-SESSION.txt",
    ".claude/commands/*.md",
)

#: A ``--target`` argument, in either spelling the shell accepts.
#:
#: ``\s`` INCLUDING THE NEWLINE is the load-bearing detail, and it is why no
#: whitespace-collapsing pass is needed here. Prose in this tree hard wraps near
#: 80 columns, so a real instruction can carry the flag on one line and its value
#: on the next, and `CLAUDE.md` records that a line-oriented pattern is a claim
#: about the file's line breaks rather than about its text. Measured while
#: writing this: a collapsing pass was tried first and removing it changed no
#: result, because ``\s+`` already spans the wrap. It was deleted rather than
#: kept - a guard whose removal changes nothing is decoration, and it would have
#: brought a real false positive with it by joining a trailing flag on one
#: paragraph to an absolute path opening the next. What the wrap tolerance costs
#: instead is spelled out on :func:`absolute_target_findings`.
_TARGET_ARG_RE = re.compile(r"--target(?:=|\s+)(\S+)")


class HandoffRefused(RedactionError):
    """The hand-off was refused and NOTHING was written.

    A subclass of :class:`RedactionError` so that a caller catching the
    redactor's own exception catches this too - the refusal reasons are not all
    identifier findings (a non-ASCII character is one), but every one of them
    means the same thing to a caller: the file on disk was not touched.
    """


def operator_identities() -> tuple[str, ...]:
    """The derived git identities, for a test that must not write one down."""
    return operator_git_identities(REPO_ROOT)


def _ascii_findings(text: str) -> list[str]:
    """Every line carrying a character outside 7-bit ASCII, one finding a line.

    Walked CHARACTER BY CHARACTER over the whole string, counting only the
    newline as a line break. :meth:`str.splitlines` was the first
    implementation and it is wrong for this job in both directions: it CONSUMES
    U+0085, U+2028 and U+2029 as line terminators, so those three walked onto
    disk unexamined, and it treats a form feed as a break, so a reported line
    number could name a line the file does not have. The tree-wide guard scans
    bytes, and a pre-write check LOOSER than the commit-time gate it stands in
    front of is worse than none - it teaches the reader that passing here means
    passing there. Both found by this item's adversarial pass.
    """
    findings = []
    line = 1
    column = 0
    flagged = -1
    for char in text:
        if char == chr(10):
            line += 1
            column = 0
            continue
        column += 1
        if ord(char) > 127 and flagged != line:
            flagged = line
            findings.append(
                f"NON_ASCII at line {line}, column {column}: "
                f"code point U+{ord(char):04X}"
            )
    return findings


def check(text: str, identities: tuple[str, ...] | None = None) -> list[str]:
    """Return every reason this text may not be written. Empty means clean.

    The findings NAME the label and the position and never quote the matched
    value. A refusal that prints the identifier at the moment it fires has
    published it - into a traceback, a session summary, and quite possibly the
    next note out on the mail channel.

    ``identities`` supplies the operator values instead of deriving them from
    git, which is what a test uses so that no real one has to be written down -
    the same parameter, for the same reason, that
    :func:`lanternlight.redact.iter_operator_identifiers` carries. It exists
    because the VALUE half is otherwise untestable here: an ordinary address is
    already caught by the plain ``EMAIL`` rule, so a test that plants one
    proves nothing about this pass. Measured by mutation - deleting the pass
    entirely left every test green until this parameter existed.
    """
    findings: list[str] = []

    for label, _matched, offset in iter_sensitive(text, FILE_SCAN_LABELS):
        findings.append(f"{label} at offset {offset}")

    for label, _matched, offset in iter_encoded_sensitive(text, FILE_SCAN_LABELS):
        findings.append(f"{label} at offset {offset}, inside encoded content")

    for label, _matched, offset in iter_operator_identifiers(text, identities):
        findings.append(f"{label} at offset {offset}, an operator identifier")

    for label, _matched, _offset in iter_literal_joined_operator_identifiers(
        text, identities
    ):
        # No offset: joining shifts every position after the first join, so a
        # number taken from the joined text names a place that does not exist
        # in the file. Naming the wrong place is worse than naming none.
        findings.append(f"{label}, an operator identifier split across literals")

    findings.extend(_ascii_findings(text))
    return findings


def write_handoff(text: str, target: Path | str | None = None) -> Path:
    """Write the hand-off atomically, or raise and touch nothing.

    The check runs first, before the temporary file is created, so a refusal
    leaves the directory exactly as it found it. There is deliberately no way
    to write past a finding.
    """
    destination = Path(target) if target is not None else DEFAULT_TARGET
    findings = check(text)
    if findings:
        raise HandoffRefused(
            "hand-off REFUSED, nothing written: "
            + "; ".join(findings[:8])
            + (f" (and {len(findings) - 8} more)" if len(findings) > 8 else "")
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(destination)
    except OSError:
        # A write that did not land must leave NOTHING behind. The refusal
        # path was already clean; this is the OS-error path - a target that
        # is a directory, or read-only - which raised AFTER the temporary
        # existed and left a stray .tmp in the repository root. Found by
        # this item's adversarial pass. An untracked orphan there fails the
        # lane guard, so a write that never landed would redden the suite.
        tmp.unlink(missing_ok=True)
        raise
    return destination


def target_is_outside_tree(target: Path | str, root: Path | None = None) -> bool:
    """True when ``target`` does not live inside ``root`` (default: this tree).

    Resolved rather than compared textually, so a relative path, a different
    spelling of the same drive and a ``..`` segment all answer the same way.
    ``strict`` is left off because the interesting target usually does not exist
    yet - a check that required the file to be there would answer "outside" for
    every first write.
    """
    base = (root or REPO_ROOT).resolve()
    return not Path(target).resolve().is_relative_to(base)


def absolute_target_findings(text: str) -> list[tuple[str, str]]:
    """Return ``[(kind, matched_path)]`` for absolute ``--target`` values in text.

    ``kind`` is one of :mod:`tools.hook_command_guard`'s ``absolute-*`` strings.
    Only the value of a ``--target`` flag is examined: prose naming the hand-off
    by its absolute path is a statement about where the file lives, not an
    instruction to write another tree's copy, and reporting it would make the
    guard unfixable without rewriting sentences that are simply true.

    The accepted false positive, stated rather than left implicit: the pattern's
    whitespace run spans a line break, so a ``--target`` that ends one paragraph
    is joined to whatever token opens the next. That is the cost of surviving
    this tree's hard wrap, and it fails LOUD - a reported finding is read by a
    human, while a missed one is read by nobody.
    """
    findings: list[tuple[str, str]] = []
    for match in _TARGET_ARG_RE.finditer(text):
        findings.extend(absolute_paths_in(match.group(1)))
    return findings


def instruction_sites(root: Path | None = None) -> tuple[Path, ...]:
    """Every existing tracked instruction file, sorted, deduplicated.

    Missing files are dropped rather than reported, because a slash command this
    repository does not have is not a defect. The corpus being non-empty is a
    separate assertion, held by a test: a scan of nothing produces the same
    empty finding list as a clean tree, which is `OPS-61`'s lesson.
    """
    base = root or REPO_ROOT
    found: list[Path] = []
    for pattern in INSTRUCTION_SITE_PATTERNS:
        if any(character in pattern for character in "*?["):
            found.extend(sorted(base.glob(pattern)))
        else:
            found.append(base / pattern)
    return tuple(sorted({path for path in found if path.is_file()}))


def scan_instruction_sites(root: Path | None = None) -> list[str]:
    """Report every tracked instruction naming an absolute ``--target``.

    One string per finding, naming the file, the line and the spelling, so a fix
    does not have to be discovered one failure at a time. The line is located by
    searching the original text for the matched path; a value that was hard
    wrapped across two lines cannot be located that way and is reported as
    ``line unknown`` rather than as a line number that would be wrong.
    """
    base = root or REPO_ROOT
    findings: list[str] = []
    for site in instruction_sites(base):
        text = site.read_text(encoding="utf-8", errors="replace")
        for kind, matched in absolute_target_findings(text):
            index = text.find(matched)
            where = (
                f"line {text.count(chr(10), 0, index) + 1}"
                if index >= 0
                else "line unknown, the value is hard wrapped"
            )
            relative = site.relative_to(base).as_posix()
            findings.append(
                f"{relative}, {where}: {kind} passed to --target ({matched}). "
                "A wrap writes the hand-off of the tree it is wrapping; omit "
                "the flag and let the writer resolve its own root."
            )
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff",
        description=(
            "Write LL-NEXT-SESSION.txt through the redactor, or refuse. "
            "The ritual calls this rather than describing it."
        ),
    )
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        help="read the hand-off text from this file (use - for stdin)",
    )
    parser.add_argument(
        "--target",
        metavar="PATH",
        help=(
            "where to write it. OMIT IT when wrapping a session: the default "
            "follows the tree this script lives in, which is what makes a wrap "
            "from a worktree write its OWN hand-off (OPS-65). A target outside "
            f"that tree is reported on stderr. Default: {DEFAULT_TARGET}"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="report findings and write nothing, whatever the result",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.from_file:
        build_parser().print_help()
        return 2
    if args.from_file == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(args.from_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"could not read {args.from_file}: {exc}", file=sys.stderr)
            return 2

    target = Path(args.target) if args.target else DEFAULT_TARGET
    if args.target and target_is_outside_tree(target):
        # Reported, not refused - see consequence 1 in the module docstring.
        # Printed BEFORE the redaction findings so it is visible whichever way
        # this run ends, and on stderr so a wrap capturing stdout still sees it.
        print(
            "WARNING: --target names a path outside the tree this writer "
            f"belongs to ({REPO_ROOT}). A wrap writes the hand-off of the tree "
            "it is wrapping, and a hand-off written into another checkout "
            "cannot be staged or committed from this one. Omit --target.",
            file=sys.stderr,
        )
    findings = check(text)
    if findings:
        print("hand-off REFUSED, nothing written:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        print(
            "Fix the HAND-OFF. There is no exemption list, and adding one is "
            "how a gate gets disarmed a word at a time.",
            file=sys.stderr,
        )
        return 1
    if args.check_only:
        print(f"hand-off clean; {len(text)} characters; nothing written")
        return 0
    written = write_handoff(text, target)
    print(f"hand-off written to {written}, {len(text)} characters")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
