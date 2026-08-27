"""The one Markdown fence scan every reader in this repository shares.

This module exists because the repository has already paid for the alternative,
twice. ``OPS-9`` (ledger ``LL-0038``) was the ledger heading GUARD and the
heading PARSER disagreeing, because only one of them tracked code fences: a
well-formed heading inside a code block became a real entry while a malformed
one beside it was ignored. Its conclusion was that there must be exactly one
scan and every reader must use it.

``ops/ops_ids.py`` was then written in 2026-08-27 with its own private line
matching and no fence tracking at all - a third reader, making the same
mistake, in a repository whose own ledger records why not to. An independent
refuter built the false positive it allows: a fenced worked example of a
``## OPS-13.`` heading, beside a genuine one, reports ``OPS-13`` as
over-allocated. The documents this scans are documents that *document their own
format*, so fenced examples of headings are not a hypothetical.

The rule implemented here is CommonMark's, not a toggle:

- a fence opens on a run of at least three ``` or ~~~ characters
- it closes only on the SAME character, a run at least as long, and no info
  string - an opening fence may carry one (```python), a closing one may not
- a fence that never closes is REPORTED rather than silently ending the span,
  because an unbalanced fence swallowing the rest of a file is the failure that
  reads as success

Tracking only the fence character - which the first version of this logic did -
makes a longer inner run look like a close and a shorter one look like a close
too. Neither minted a phantom entry, but both produced a FALSE REFUSAL on legal
Markdown, and a guard that cries wolf on correct input is a guard that gets
switched off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

__all__ = ["FenceScan", "Line", "scan_unfenced"]

#: The two Markdown fence characters. A fence is a run of at least three, and
#: what may close it depends on the character, the run length and the absence of
#: an info string - see :func:`_fence_marker`.
FENCE_MARKS = ("`", "~")


class Line(NamedTuple):
    """One line living outside every code fence.

    Attributes:
        number: 1-based line number in the source text.
        offset: Character offset of the line's first character.
        text: The line without its trailing newline.
    """

    number: int
    offset: int
    text: str


@dataclass(frozen=True)
class FenceScan:
    """The result of one walk over a Markdown document.

    Attributes:
        lines: Every line OUTSIDE a fence, in document order.
        open_fence_at: Line number of a fence that never closes, or 0. Callers
            that must refuse a malformed document check this; callers that only
            want the unfenced lines may ignore it.
    """

    lines: tuple[Line, ...]
    open_fence_at: int


def _fence_marker(stripped: str) -> tuple[str, int, str] | None:
    """Return ``(char, width, info)`` when ``stripped`` is a fence line.

    ``width`` is the run length, which decides what can close it, and ``info``
    is whatever follows.
    """
    for char in FENCE_MARKS:
        if not stripped.startswith(char * 3):
            continue
        width = len(stripped) - len(stripped.lstrip(char))
        return char, width, stripped[width:].strip()
    return None


def scan_unfenced(text: str) -> FenceScan:
    """Walk ``text`` once and return every line outside a code fence.

    One pass, one notion of what a fence is. A caller that wants headings, ids,
    closures or anything else applies its own patterns to
    :attr:`FenceScan.lines` rather than re-deciding what a fence is.
    """
    fence: tuple[str, int] | None = None
    fence_opened_at = 0
    offset = 0
    kept: list[Line] = []

    for number, raw in enumerate(text.splitlines(keepends=True), 1):
        line = raw.rstrip("\n").rstrip("\r")
        stripped = line.lstrip()
        marker = _fence_marker(stripped)
        if marker is not None:
            char, width, info = marker
            if fence is None:
                fence, fence_opened_at = (char, width), number
            elif char == fence[0] and width >= fence[1] and not info:
                fence = None
            offset += len(raw)
            continue
        if fence is None:
            kept.append(Line(number=number, offset=offset, text=line))
        offset += len(raw)

    return FenceScan(
        lines=tuple(kept),
        open_fence_at=fence_opened_at if fence is not None else 0,
    )
