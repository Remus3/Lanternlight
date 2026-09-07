"""``docs/INVENTORY.md`` must name only real paths, and carry no operator PII.

This is the backstop for ``OPS-42`` question 2 (``ROADMAP.md``): the operator
ruled that Lanternlight joins the cross-project inventory exchange, and that
document is this project's outbound half. Two properties keep it honest
across every future edit, because a document that is right on the day it is
written and silently wrong a week later is worse than no document:

1. **Every path it names exists.** The inventory would otherwise rot the
   first time a referenced test file is renamed or a command is removed, and
   a sibling project reading it "as is after ensuring it applies to your repo
   for file locations" - the operator's own condition - would be trusting a
   claim nobody re-checked.
2. **It carries no account-name-shaped string, email-shaped string, or
   game-identifier-shaped string.** This repository is PUBLIC and purged
   exactly this class of leak from its own history earlier in the session
   this file was written in (``OPS-40``). A document produced specifically to
   be read by other machines is exactly the wrong place to reintroduce it.

WHAT THIS GUARD IS BLIND TO, stated here because a caveat that lives only in
conversation is a lie in the artifact:

* The path-existence check only understands backtick-quoted spans that look
  like a file path (contains ``/`` and ends in a short extension, with no
  glob or placeholder character). A path named in plain prose without
  backticks is invisible to it.
* The PII check is structural (a path shape, an email shape, the game's own
  identifier shapes via :mod:`lanternlight.redact`), not a list of literal
  names. It cannot catch a leak that matches none of those shapes - which is
  the same limit ``tests/test_no_hardcoded_home_path.py`` documents for its
  own home-path pattern, and for the same reason: a guard that only knew this
  machine's literal account name would pass cleanly the day a DIFFERENT
  account name was committed.
"""

import re
from pathlib import Path

from lanternlight.redact import FILE_SCAN_LABELS, iter_sensitive

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "docs" / "INVENTORY.md"


def _text() -> str:
    return INVENTORY.read_text(encoding="utf-8")


def test_the_file_exists_and_is_not_empty():
    assert INVENTORY.is_file(), "docs/INVENTORY.md is missing"
    assert len(_text().strip()) > 0, "docs/INVENTORY.md is empty"


# ---------------------------------------------------------------------------
# Property 1: every path this document names must exist on disk.
# ---------------------------------------------------------------------------

_BACKTICK = re.compile(r"`([^`]*)`")

#: Extensions this repo actually uses for the kind of file this document
#: names. Kept narrow on purpose - a bare word like a version number or a
#: mode string ("100755") must never be mistaken for a path.
_PATH_TOKEN = re.compile(r"^[A-Za-z0-9_./-]+/[A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,6}$")


def _file_path_claims(text: str):
    """Yield every backtick-quoted token that claims to be a real file path.

    A markdown span can hold a whole shell command ("git ls-files -s
    .githooks/"), a glob ("*.py", ".githooks/*"), a placeholder
    ("tests/<file>"), or a bare flag ("-q"). None of those name a file that
    must exist. Each span is split on whitespace and a token only counts as a
    path claim if it contains a "/", ends in a short extension, and carries
    no glob or placeholder character.
    """
    for span in _BACKTICK.findall(text):
        for token in span.split():
            if "*" in token or "<" in token or ">" in token:
                continue
            if _PATH_TOKEN.match(token):
                yield token


def test_every_backtick_quoted_file_path_exists():
    text = _text()
    claims = sorted(set(_file_path_claims(text)))
    # A guard that finds nothing to check is not exercising the property it
    # claims to guard. This document names dozens of real paths; if the
    # extractor ever finds none, the pattern itself broke, not the document.
    assert len(claims) >= 20, (
        f"the path extractor found only {len(claims)} candidate(s) in "
        "docs/INVENTORY.md - the extraction pattern likely broke"
    )
    missing = [c for c in claims if not (REPO_ROOT / c).is_file()]
    assert not missing, (
        "docs/INVENTORY.md names a path that does not exist on disk: "
        + ", ".join(missing)
    )


def _section(text: str, heading: str) -> str:
    """Return the text of one '## heading' section, up to the next '## '."""
    start = text.index(heading)
    rest = text[start + len(heading):]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


_TABLE_FILENAME = re.compile(r"^\|\s*`([A-Za-z0-9_.-]+\.md)`\s*\|", re.MULTILINE)


def test_every_command_named_in_the_commands_table_exists():
    text = _text()
    names = _TABLE_FILENAME.findall(_section(text, "## Commands (`.claude/commands/`)"))
    assert len(names) >= 5, "found too few rows in the commands table - did the heading move?"
    missing = [n for n in names if not (REPO_ROOT / ".claude" / "commands" / n).is_file()]
    assert not missing, f".claude/commands/ is missing: {missing}"


def test_every_agent_named_in_the_agents_table_exists():
    text = _text()
    names = _TABLE_FILENAME.findall(_section(text, "## Agents (`.claude/agents/`)"))
    assert len(names) >= 2, "found too few rows in the agents table - did the heading move?"
    missing = [n for n in names if not (REPO_ROOT / ".claude" / "agents" / n).is_file()]
    assert not missing, f".claude/agents/ is missing: {missing}"


def test_the_declared_directories_exist():
    # Real, tracked directories the document's prose refers to by name.
    # Deliberately excludes the PII-hazard path PATTERNS the hooks section
    # quotes ("frames/", "captures/", "logs/", ...) - those describe what the
    # hook refuses, and asserting they exist would invert the guard's point.
    for rel in (".claude/commands", ".claude/agents", ".githooks"):
        assert (REPO_ROOT / rel).is_dir(), f"expected directory missing: {rel}"


# ---------------------------------------------------------------------------
# Property 2: no operator PII, in any of the shapes this project has
# measured leaking before.
# ---------------------------------------------------------------------------

#: Same shape as tests/test_no_hardcoded_home_path.py's HOME_SHAPED pattern,
#: kept independent rather than imported so this guard does not depend on
#: another lane's internals to do its own job. Matches a Windows or POSIX
#: home directory followed by an account name, while still exempting an
#: actual placeholder ("<user>", "$HOME", "~").
_ACCOUNT_PATH_SHAPED = re.compile(
    r"(?:[A-Za-z]:[\\/]Users[\\/]|/home/|/Users/)"
    r"(?![%$<~])"
    r"[A-Za-z0-9._~-]+",
    re.IGNORECASE,
)

#: A generic email shape. Not tied to any real domain on purpose - the point
#: is to catch the SHAPE, not one known address.
_EMAIL_SHAPED = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def test_no_account_shaped_path():
    hits = _ACCOUNT_PATH_SHAPED.findall(_text())
    assert not hits, f"docs/INVENTORY.md carries an account-name-shaped path: {hits}"


def test_no_email_shaped_string():
    hits = _EMAIL_SHAPED.findall(_text())
    assert not hits, f"docs/INVENTORY.md carries an email-shaped string: {hits}"


def test_no_game_identifier_survives_the_sanctioned_scanner():
    # The same mechanism tests/test_no_pii.py uses to scan an arbitrary file
    # for the game's own identifier shapes (SteamID64, persona, EOS
    # ProductUserId, ...) - FILE_SCAN_LABELS is the set that mechanism uses
    # for exactly this purpose: a plain-text file, not a keyed log line.
    hits = list(iter_sensitive(_text(), labels=FILE_SCAN_LABELS))
    assert not hits, (
        "docs/INVENTORY.md carries a game-identifier-shaped string: "
        + ", ".join(sorted({label for label, _, _ in hits}))
    )
