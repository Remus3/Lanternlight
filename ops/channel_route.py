"""Discover a channel member's inbox at RUN TIME - ``ROADMAP.md`` ``OPS-109``.

Some channel members - MAIN first among them - ask that their path never be
published, and this repository is public. So their inbox is not a row in
the outbox module's tracked carrier map or in ``docs/REPLY_PATHS.md``; it is
FOUND, each
time a reply is sent, by the one-match rule ``OPS-108`` recorded:

- Look EXACTLY ONE directory level under the search root - by default the
  drive anchor of this repository, never a hardcoded sibling path - for
  ``<dir>/moon_sync_inbox/README.txt``.
- Keep the READMEs that declare ``Code on this channel: <CODE>.`` with the
  code as a whole, case-sensitive token, so ``MAIN`` does not match ``MAINX``
  or ``main``.
- Exclude this repository's own inbox.
- Exactly one match is the route. Zero or several is a REFUSAL, raised as
  :class:`RouteRefused` before anything is written. A guess is worse than
  silence here: a reply delivered to the wrong tree is a reply published to a
  reader it was not written for.

A refusal names COUNTS, never paths, so its text may be logged. A README that
exists but cannot be read is skipped and COUNTED, so a zero-match refusal says
how much it could not look at rather than claiming it looked everywhere.

The path this returns lives only in memory and in the gitignored outbox
manifest that ``ops.outbox.deliver`` already writes. It must never be written
to a tracked file; ``tests/test_channel_route.py`` fails if this module's own
source ever carries a drive-qualified path.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ops import outbox

__all__ = [
    "REPO_ROOT",
    "RouteRefused",
    "Scan",
    "default_search_root",
    "deliver_to",
    "find_inbox",
    "inboxes_for",
    "scan",
]

REPO_ROOT = Path(__file__).resolve().parents[1]

INBOX_DIRNAME = "moon_sync_inbox"
README_NAME = "README.txt"


class RouteRefused(LookupError):
    """Zero or several inboxes declared the code. Nothing was delivered."""


@dataclass(frozen=True)
class Scan:
    """What one pass over the search root saw. Paths stay in memory."""

    matches: tuple[Path, ...]
    readmes_read: int
    unreadable: int


def default_search_root() -> Path:
    """The drive anchor of this repository - computed, never written down."""
    return Path(REPO_ROOT.anchor)


def _declares(text: str, code: str) -> bool:
    pattern = r"Code on this channel: " + re.escape(code) + r"\."
    return re.search(pattern, text) is not None


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def scan(
    code: str,
    search_root: Path | str | None = None,
    *,
    own_repo: Path | str | None = None,
) -> Scan:
    """Every inbox one level under ``search_root`` that declares ``code``."""
    if not code or not code.strip() or code != code.strip():
        raise ValueError("a channel code must be a non-empty bare token")
    root = Path(search_root) if search_root is not None else default_search_root()
    own = Path(own_repo) if own_repo is not None else REPO_ROOT
    matches: list[Path] = []
    read = 0
    unreadable = 0
    try:
        children = sorted(root.iterdir())
    except OSError as exc:
        raise RouteRefused(
            f"cannot list the search root for code {code}: {type(exc).__name__}"
        ) from None
    for child in children:
        try:
            if not child.is_dir() or _same(child, own):
                continue
            readme = child / INBOX_DIRNAME / README_NAME
            if not readme.exists():
                continue
        except OSError:
            continue
        try:
            text = readme.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        read += 1
        if _declares(text, code):
            matches.append(child / INBOX_DIRNAME)
    return Scan(matches=tuple(matches), readmes_read=read, unreadable=unreadable)


def find_inbox(
    code: str,
    search_root: Path | str | None = None,
    *,
    own_repo: Path | str | None = None,
) -> Path:
    """The ONE inbox declaring ``code``, or :class:`RouteRefused`."""
    result = scan(code, search_root, own_repo=own_repo)
    n = len(result.matches)
    if n == 1:
        return result.matches[0]
    if n == 0:
        raise RouteRefused(
            f"no inbox declares code {code}: {result.readmes_read} README(s) "
            f"read, {result.unreadable} unreadable; refusing to guess"
        )
    raise RouteRefused(
        f"{n} inboxes declare code {code}; the route must be unique, "
        f"refusing to guess ({result.unreadable} unreadable)"
    )


def inboxes_for(
    codes: Iterable[str],
    search_root: Path | str | None = None,
    *,
    own_repo: Path | str | None = None,
) -> dict[str, str]:
    """An ``inboxes`` override for :func:`ops.outbox.deliver`.

    Every code must resolve by the one-match rule or the whole call raises,
    so a partial map is never handed to a delivery.
    """
    return {
        code: str(find_inbox(code, search_root, own_repo=own_repo))
        for code in codes
    }


def deliver_to(
    code: str,
    name: str,
    text: str,
    *,
    search_root: Path | str | None = None,
    own_repo: Path | str | None = None,
    root: Path | str | None = None,
    now: str | None = None,
    answers: list[str] | tuple[str, ...] | None = None,
) -> outbox.Delivery:
    """Discover ``code``'s inbox, then deliver through ``ops.outbox.deliver``.

    Discovery runs FIRST, so a refusal raises before our own copy, the manifest
    row or any sibling write exists.
    """
    mapping = inboxes_for([code], search_root, own_repo=own_repo)
    return outbox.deliver(
        name, text, [code], root=root, inboxes=mapping, now=now, answers=answers,
    )
