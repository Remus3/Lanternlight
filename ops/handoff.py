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
"""

from __future__ import annotations

import argparse
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

#: The one hand-off. There is exactly one, rewritten every session, and its git
#: history is the record of what each session handed forward.
DEFAULT_TARGET = REPO_ROOT / "LL-NEXT-SESSION.txt"


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
        help=f"where to write it (default: {DEFAULT_TARGET})",
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
