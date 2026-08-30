"""Append-only writer for the per-item ledger at ``docs/LEDGER.md``.

The ledger is the loop's durable memory of what it actually finished. A cleared
or compacted session reads the top of this file and knows the last few items
without needing a single line of the conversation that produced them.

Three rules make that trustworthy.

**Append-only.** This module inserts new text and never edits, reflows or
reorders what is already there. A writer that can rewrite history is a writer
whose output cannot be trusted as a record, and an unattended loop is precisely
the actor you least want holding that power.

**Newest first.** New entries go directly below the marker line near the top of
the file, so "the last three things that happened" is the first thing a reader
sees. An append-to-the-bottom ledger makes the most useful information the
hardest to reach, which in a context-constrained session means it goes unread.

**Atomic.** Same reasoning as :mod:`ops.loop.state` - write a temporary file in
the same directory, then :meth:`pathlib.Path.replace` it onto the target. A
reader, or a crash, never observes a half-written ledger.

Every entry carries acceptance evidence. "Done" with no evidence line is the
failure mode this project exists to avoid: it reads as progress and cannot be
checked. Evidence is a test name, a file path, a command and its result -
something a later session can re-run.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "ENTRIES_MARKER",
    "LedgerEntry",
    "MarkerMissingError",
    "append_entry",
    "default_ledger_path",
    "render_entry",
]

#: Repository root, resolved from this file's location: ops/loop/ledger.py.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The line new entries are inserted immediately below. It is an HTML comment
#: so it renders as nothing, and it is matched exactly - a fuzzy match would
#: eventually hit a line of prose that merely mentions the marker.
ENTRIES_MARKER = "<!-- LEDGER ENTRIES BELOW - NEWEST FIRST -->"

#: Prefix for temporary files created here, so a stray one is identifiable.
TEMP_PREFIX = ".ledger-"


class MarkerMissingError(RuntimeError):
    """Raised when the ledger has no insertion marker.

    Deliberately fatal. The alternatives - appending to the end, or guessing an
    insertion point - would either bury the newest entry or risk writing into
    the middle of the preamble. A missing marker means the file is not the file
    this writer was built for, and the honest move is to stop.
    """


def default_ledger_path() -> Path:
    """Return the path of the repository ledger."""
    return REPO_ROOT / "docs" / "LEDGER.md"


def _today() -> str:
    """Return today's UTC date as ``YYYY-MM-DD``."""
    return datetime.now(UTC).date().isoformat()


def _require_ascii(label: str, text: str) -> None:
    """Raise unless ``text`` is pure 7-bit ASCII.

    The repository is ASCII-only by rule and by test (see
    ``tests/test_ascii_hygiene.py``). Catching a smart quote here, at the point
    it is written, names the offending field. Catching it later, in the hygiene
    test, only names the file - and by then the loop has already committed.
    """
    if not text.isascii():
        bad = next(ch for ch in text if not ch.isascii())
        raise ValueError(
            f"{label} contains non-ASCII character {ch_repr(bad)}; this repository is "
            "7-bit ASCII only - use ' - ' for a clause break and plain quotes"
        )


def ch_repr(char: str) -> str:
    """Render a character with its codepoint, for an actionable error."""
    return f"{char!r} (U+{ord(char):04X})"


@dataclass
class LedgerEntry:
    """One ledger row.

    Attributes:
        item_id: Stable identifier, for example ``LL-0007``. This is what a
            later session greps for.
        summary: One line. If it needs two, the item was two items.
        evidence: Acceptance evidence - test names, file paths, commands and
            their observed results. At least one is required.
        date: ISO 8601 date. Defaults to today in UTC.
        notes: Optional extra lines, including a recorded decision gate the
            loop declined to answer on the operator's behalf.
    """

    item_id: str
    summary: str
    evidence: Sequence[str]
    date: str = field(default_factory=_today)
    notes: Sequence[str] = field(default_factory=tuple)

    def validate(self) -> None:
        """Raise :class:`ValueError` if this entry is not fit to be written."""
        if not self.item_id.strip():
            raise ValueError("item_id is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if "\n" in self.summary:
            raise ValueError("summary must be a single line")
        if not list(self.evidence):
            raise ValueError(
                f"{self.item_id}: at least one evidence line is required - an entry with "
                "no acceptance evidence is a claim, not a record"
            )
        _require_ascii("item_id", self.item_id)
        _require_ascii("summary", self.summary)
        _require_ascii("date", self.date)
        for line in self.evidence:
            _require_ascii("evidence", line)
        for line in self.notes:
            _require_ascii("notes", line)


def render_entry(entry: LedgerEntry) -> str:
    """Return the Markdown block for ``entry``, without surrounding blank lines."""
    entry.validate()
    lines = [f"### {entry.item_id} - {entry.date} - {entry.summary.strip()}", ""]
    lines.append("**Evidence:**")
    lines.extend(f"- {line.strip()}" for line in entry.evidence)
    if entry.notes:
        lines.append("")
        lines.extend(line.strip() for line in entry.notes)
    return "\n".join(lines)


def _compose(head: str, block: str, preserved: str) -> str:
    """Compose the updated ledger text: header, new entry, then everything else.

    **Extracted for `OPS-10`, and the extraction is the whole point.** The
    preservation check in :func:`append_entry` guards the one promise this
    module makes - that every byte already below the marker survives an append.
    While the composition was an inline expression, that check could not fail
    for any input: the result ended with ``preserved`` by construction. Deleting
    the ``raise`` left the suite green, so the guard was decoration, and
    `LL-0042` over-claimed that it was covered.

    A defensive check with no reachable trigger is worth keeping only if it can
    be proven to fire, because the risk it actually covers is a FUTURE edit to
    this composition rather than any input. Giving the composition a name is
    what makes that provable: a test substitutes a composer that drops the tail
    and asserts the append is refused with the target untouched. See
    `TestThePreservationCheckIsReachable`.

    Keep this a pure function of its three arguments. If it grows a branch on
    anything else, the check above stops meaning what it says.
    """
    return head + "\n\n" + block + "\n\n" + preserved


def append_entry(entry: LedgerEntry, path: Path | None = None) -> Path:
    """Insert ``entry`` at the top of the ledger, atomically.

    Args:
        entry: The entry to record.
        path: Ledger file. Defaults to :func:`default_ledger_path`.

    Returns:
        The path written.

    Raises:
        MarkerMissingError: The ledger has no :data:`ENTRIES_MARKER` line.
        ValueError: The entry is incomplete or carries non-ASCII text.
        AssertionError: The composed file would not have preserved the existing
            entries byte for byte. This is a self-check on the one promise this
            module makes, and it fires before anything is written.
    """
    target = Path(path) if path is not None else default_ledger_path()
    block = render_entry(entry)

    original = target.read_text(encoding="utf-8")
    marker_index = original.find(ENTRIES_MARKER)
    if marker_index < 0:
        raise MarkerMissingError(
            f"{target} has no line reading {ENTRIES_MARKER!r}; refusing to guess where a "
            "new entry belongs"
        )

    split_at = marker_index + len(ENTRIES_MARKER)
    head = original[:split_at]
    preserved = original[split_at:].lstrip("\n")

    updated = _compose(head, block, preserved)

    # The one promise this module makes, checked before anything is written:
    # every byte that was already below the marker is still there, unchanged.
    if not updated.endswith(preserved):
        raise AssertionError(
            f"{target}: ledger append would have ALTERED existing content; "
            "refusing to write. The composed text does not end with the "
            f"{len(preserved)} bytes that were already below the marker, so "
            "an append would have truncated or rewritten existing entries. "
            "This file is append-only; fix the composition, do not relax "
            "this check."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        prefix=f"{TEMP_PREFIX}{target.name}-",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(updated)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    return target
