"""``docs/INVENTORY.md`` must name only real paths, and carry no operator PII.

This is the backstop for ``OPS-42`` question 2 (``ROADMAP.md``): the operator
ruled that Lanternlight joins the cross-project inventory exchange, and that
document is this project's outbound half. Two properties keep it honest
across every future edit, because a document that is right on the day it is
written and silently wrong a week later is worse than no document. ``OPS-69``
added a THIRD property running the other way, because both of the first two ask
only whether something the document names exists - nothing asked whether
something that exists is named:

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
3. **Every file its stated scope covers is named in it.** See ``_SCOPE`` and
   ``EXCLUDED_FROM_INVENTORY`` below for the scope and for what is excused.
   An inventory that has silently fallen behind the repository does not read
   as short - it reads as complete, and this document is Lanternlight's
   outbound half of the cross-project inventory exchange.
4. **Every ``tests/test_*.py`` is named in one of the document's two test
   TABLES**, and not merely somewhere in the file. This is narrower than
   property 3 on purpose, and it exists because the document makes that exact
   claim in its own voice ("Between the two tables, every ``tests/test_*.py``
   in the repository is named"). Property 3 was satisfied by a mention in
   prose, so on 2026-09-08 ``tests/test_inventory.py`` itself was named three
   times in prose, absent from both tables, and the sentence asserting
   otherwise was false while this file stayed green. A prose claim that no
   test enforces is a claim nobody is checking; a guard whose scope is looser
   than the sentence beside it does not enforce that sentence.

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
* Property 3 means named ANYWHERE in the document, and that is the deliberate
  reading, not an oversight. For ``commands``, ``agents`` and ``hooks`` the
  membership test is the file's own table, because those are named by BASENAME
  and a bare basename in prose would be too weak a claim. For ``tools``,
  ``tests`` and ``scripts`` the name is a full repo-relative path, which is
  unambiguous wherever it appears, so a mention in prose counts. The cost,
  measured on 2026-09-10 rather than reasoned about: deleting the Test-support
  row for ``tests/_tracked.py`` leaves this suite GREEN, because the scope
  prose above that table names the same path twice more. Removing every
  mention does turn it red - confirmed for ``tests/_tracked.py`` (3 mentions)
  and ``tests/conftest.py`` (2). Property 4 is the one place a table row is
  required of a path-spelled group, and it exists only because the document
  makes that claim about those two tables out loud.
* ``EXCLUDED_FROM_INVENTORY`` is EMPTY, so say plainly what that does and does
  not exercise, rather than leaving a reader to assume.
  :func:`test_every_exclusion_is_justified_and_still_real` runs its per-entry
  body ZERO times: the cap assertion at the top of it is the only statement
  that executes, and no reason string, no scope membership and no on-disk
  existence is checked by this suite as it stands. What IS exercised while the
  dict is empty is its effect on :func:`_in_scope`, which skips any path
  present in it - so an entry added there really does remove a file from the
  completeness check, which is precisely why the per-entry checks matter the
  moment one is added. Those checks were confirmed to fire on 2026-09-08 by
  injecting bogus entries (a nonexistent path, an out-of-scope path, a
  too-short reason, and a thirteenth entry to trip the cap) and watching each
  go red; that is a measurement of the code, not a property this suite asserts
  on every run.
"""

import re
import sys
from pathlib import Path

from lanternlight.redact import FILE_SCAN_LABELS, iter_sensitive

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "docs" / "INVENTORY.md"

# The repository's one file walker, shared with tests/test_ascii_hygiene.py and
# tests/test_no_pii.py and pinned by tests/test_tracked_walker.py. Reusing it is
# deliberate: a second way to enumerate this tree would be a second thing to
# keep in step, and the walker already answers the question that matters here -
# what would be PUBLISHED from this root.
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

import _tracked  # noqa: E402


def _text() -> str:
    return INVENTORY.read_text(encoding="utf-8")


def _fenceless(text: str) -> str:
    """``text`` with every fenced code block blanked out, line count preserved.

    A backtick-pair regex run over the raw document DESYNCHRONISES on a ```
    fence: the fence contributes three backticks, so every span after an odd
    fence pairs the wrong delimiters and the extracted tokens are garbage. That
    is not hypothetical - during ``OPS-69`` a naive sweep of this document
    reported "80 of 81 files missing", which is the shape a desynchronised
    extractor produces and not the shape a real regression does.

    Blank lines rather than deletion, so a line number quoted from the stripped
    text still points at the same line of the file. Measured on 2026-09-10 the
    stripped and unstripped path-claim sets for this document are IDENTICAL, so
    this changes nothing today; it is here so that the day a fence gains an odd
    backtick, the guard reports the document instead of reporting itself.
    """
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


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
    text = _fenceless(_text())
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
    text = _fenceless(_text())
    names = _TABLE_FILENAME.findall(_section(text, "## Commands (`.claude/commands/`)"))
    assert len(names) >= 5, "found too few rows in the commands table - did the heading move?"
    missing = [n for n in names if not (REPO_ROOT / ".claude" / "commands" / n).is_file()]
    assert not missing, f".claude/commands/ is missing: {missing}"


def test_every_agent_named_in_the_agents_table_exists():
    text = _fenceless(_text())
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
# Property 3 (``OPS-69``): every file the document's scope covers is NAMED.
#
# Properties 1 and 2 both run in the same direction - they take something the
# DOCUMENT says and ask the tree about it. Nothing asked the reverse, so on
# 2026-09-08 three modules created that session sat absent from the inventory
# while this file stayed green, and a human added them by hand. An inventory
# that is silently short does not read as short; it reads as complete, and this
# document is the outbound half of a cross-project exchange.
# ---------------------------------------------------------------------------

#: THE SCOPE, stated rather than assumed. Every file the walker would publish
#: from this root whose repo-relative path falls in one of these six sets must
#: be named in ``docs/INVENTORY.md``. Everything else in the tree -
#: ``lanternlight/``, ``ops/``, ``docs/``, ``tests/fixtures/``, and any file
#: nested deeper than the sets below - is OUT OF SCOPE, because this document
#: inventories the repository's harness and its test surface, not its library
#: source. Widening it is a decision to take deliberately, not by accident.
#:
#: WIDENED ON 2026-09-10, deliberately, with the reason recorded here rather
#: than inferred from a diff. The scope used to be ``tests/test_*.py`` and to
#: exclude ``scripts/`` outright. Both edges hid a load-bearing file:
#:
#: * ``tests/_tracked.py`` is the shared tracked-file walker that THIS module's
#:   own completeness check runs on, and ``tests/conftest.py`` decides what the
#:   whole suite can import. Neither is a ``test_*.py``, so the inventory did
#:   not name the two modules its own guard depends on. The set is now every
#:   ``tests/*.py``, one directory deep.
#: * ``scripts/install_hooks.py`` is the first command ``CLAUDE.md``'s
#:   fresh-clone instructions tell a reader to run, and a sibling reading this
#:   document "as is after ensuring it applies to your repo" would expect to
#:   find it. It happened to be named already, in prose, by accident of that
#:   instruction being quoted - while ``scripts/write_lane_contracts.py`` beside
#:   it was named nowhere. A directory half-covered by luck is the worst of the
#:   three states, so ``scripts/*.py`` is now in scope in full.
#:
#: ``tests/fixtures/`` stays OUT, and the document says so explicitly rather
#: than omitting it: a fixture builder is an input to a test, not a surface a
#: sibling project would look for, and an unmentioned directory is
#: indistinguishable from an overlooked one.
_SCOPE = ("commands", "agents", "hooks", "tools", "tests", "scripts")

#: "Published" here means what :func:`_tracked.iter_authored_files` yields:
#: tracked files PLUS untracked-but-not-ignored ones. Including the untracked
#: half is the point of this property - the modules that went missing were new
#: that session, and a guard that waits for a commit goes blind at exactly the
#: moment it is needed. It is the same choice, for the same reason, that
#: ``tests/test_tracked_walker.py`` pins for the hygiene guards.
_SCOPE_SUMMARY = (
    ".claude/commands/*.md, .claude/agents/*.md, .githooks/*, tools/*.py, "
    "tests/*.py, scripts/*.py"
)

#: EXCLUSIONS, one line of reason each. **This mapping is empty on purpose.**
#: Every file in scope is currently named in the document, so nothing needs
#: excusing, and an empty exclusion list is the only one with no place to hide.
#: If an entry is ever added it must carry a reason a cold session can weigh,
#: and the list must stay short: ``tests/test_source_register.py``'s own
#: docstring calls its ``KNOWN_NON_HOSTS`` "the one place a real source can
#: hide", and that list grew by four entries in a single session. Past a dozen
#: here, the SCOPE above was wrong and the fix belongs there, not in this dict.
EXCLUDED_FROM_INVENTORY: dict[str, str] = {}

#: Floors, not counts. A floor well under the real figure catches a discovery
#: pass that has collapsed - a walker that returns nothing makes every
#: membership check below pass vacuously - without restating a number that goes
#: stale the day a file is added. No total is written to the document either;
#: the comparison is derived on every run. See the document's own preamble.
_SCOPE_FLOORS = {
    "commands": 5,
    "agents": 2,
    "hooks": 2,
    "tools": 3,
    "tests": 20,
    "scripts": 2,
}


def _group_of(rel: str) -> str | None:
    """Which scope set ``rel`` (a repo-relative posix path) belongs to, if any."""
    parent, _, name = rel.rpartition("/")
    if parent == ".claude/commands" and name.endswith(".md"):
        return "commands"
    if parent == ".claude/agents" and name.endswith(".md"):
        return "agents"
    if parent == ".githooks":
        return "hooks"
    if parent == "tools" and name.endswith(".py"):
        return "tools"
    # Every ``tests/*.py`` one directory deep, not only ``test_*.py``. The
    # ``parent ==`` comparison is what keeps ``tests/fixtures/`` out, which is
    # the documented boundary rather than an accident of the pattern.
    if parent == "tests" and name.endswith(".py"):
        return "tests"
    if parent == "scripts" and name.endswith(".py"):
        return "scripts"
    return None


def _in_scope() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {name: [] for name in _SCOPE}
    for path in _tracked.iter_authored_files(REPO_ROOT):
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:  # pragma: no cover - the walker roots at REPO_ROOT
            continue
        group = _group_of(rel)
        if group is not None and rel not in EXCLUDED_FROM_INVENTORY:
            groups[group].append(rel)
    return {name: sorted(set(paths)) for name, paths in groups.items()}


def _backtick_tokens(text: str) -> set[str]:
    """Every whitespace-separated token inside a backtick span."""
    return {token for span in _BACKTICK.findall(text) for token in span.split()}


def test_every_file_the_scope_covers_is_named_in_the_inventory():
    text = _fenceless(_text())
    groups = _in_scope()

    # Tools and test modules are always spelled as full repo-relative paths in
    # this document, so they are checked against the same extractor property 1
    # uses. Commands, agents and hooks are named by BASENAME inside their own
    # table, exactly as the three forward tests above read them - so the two
    # directions agree on what "named" means instead of each inventing it.
    claims = set(_file_path_claims(text))
    by_basename = {
        "commands": set(
            _TABLE_FILENAME.findall(_section(text, "## Commands (`.claude/commands/`)"))
        ),
        "agents": set(
            _TABLE_FILENAME.findall(_section(text, "## Agents (`.claude/agents/`)"))
        ),
        "hooks": _backtick_tokens(_section(text, "## Git hooks (`.githooks/`)")),
    }

    missing: list[str] = []
    for group, paths in groups.items():
        for rel in paths:
            if group in by_basename:
                if rel.rpartition("/")[2] not in by_basename[group]:
                    missing.append(rel)
            elif rel not in claims:
                missing.append(rel)

    assert not missing, (
        "docs/INVENTORY.md does not name a file its own scope covers ("
        + _SCOPE_SUMMARY
        + "): "
        + ", ".join(sorted(missing))
        + " - add a row rather than widening EXCLUDED_FROM_INVENTORY"
    )


# ---------------------------------------------------------------------------
# Property 4 (``OPS-69`` repair): the document's own two-tables sentence.
# ---------------------------------------------------------------------------

#: The two headings between which the document claims every ``tests/test_*.py``
#: is named. They are matched by PREFIX because each heading carries a
#: parenthetical the wording of which is not load-bearing; the section boundary
#: is the next ``## ``, which is what :func:`_section` already uses.
_TEST_TABLE_HEADINGS = (
    "## Guards (tests enforcing an invariant",
    "## Every other test module",
)

#: The sentence in the document that property 4 exists to make true. Held here
#: as the whitespace-collapsed form because this repository hard-wraps prose
#: near 80 columns, so the claim spans two lines on disk and a line-oriented
#: search for it returns a false clean bill - a failure mode ``CLAUDE.md``
#: records happening twice in one session.
_TWO_TABLE_CLAIM = (
    "Between the two tables, every `tests/test_*.py` in the repository is named"
)

#: A table row naming a test module by its full repo-relative path.
_TEST_TABLE_ROW = re.compile(
    r"^\|\s*`(tests/test_[A-Za-z0-9_]+\.py)`\s*\|", re.MULTILINE
)


def _named_in_test_tables(text: str) -> set[str]:
    named: set[str] = set()
    for heading in _TEST_TABLE_HEADINGS:
        named.update(_TEST_TABLE_ROW.findall(_section(text, heading)))
    return named


def test_the_two_table_claim_is_still_the_sentence_this_guard_enforces():
    # A guard that enforces a sentence the document no longer makes is
    # enforcing nothing a reader can see. If the wording is edited, this test
    # is the place that has to notice, so the pair cannot drift apart silently.
    collapsed = " ".join(_fenceless(_text()).split())
    assert _TWO_TABLE_CLAIM in collapsed, (
        "docs/INVENTORY.md no longer carries the completeness sentence this "
        "guard was written to enforce: " + _TWO_TABLE_CLAIM
    )


def test_every_test_module_is_named_in_one_of_the_two_tables():
    text = _fenceless(_text())
    named = _named_in_test_tables(text)
    # Not vacuous: the two tables together carry a row per test module, so a
    # collapsed extractor would be caught here rather than reporting a clean
    # document. The floor is well under the real figure on purpose - no count
    # is filed, in this file or in the document.
    assert len(named) >= 40, (
        f"the two test tables yielded only {len(named)} row(s) - the row "
        "pattern or a heading broke, and the membership check below would "
        "have passed vacuously"
    )
    in_tree = [
        rel
        for rel in _in_scope()["tests"]
        if rel.rpartition("/")[2].startswith("test_")
    ]
    missing = sorted(rel for rel in in_tree if rel not in named)
    assert not missing, (
        "docs/INVENTORY.md claims in its own voice that between its two test "
        "tables every tests/test_*.py is named, but these appear in neither "
        "(a mention in prose does not satisfy the sentence): "
        + ", ".join(missing)
    )
    stale = sorted(rel for rel in named if not (REPO_ROOT / rel).is_file())
    assert not stale, (
        "a test table names a module that does not exist on disk: "
        + ", ".join(stale)
    )


def test_the_scope_discovery_is_not_vacuous():
    groups = _in_scope()
    thin = {
        name: len(groups[name])
        for name, floor in _SCOPE_FLOORS.items()
        if len(groups[name]) < floor
    }
    assert not thin, (
        "the scope walk found fewer files than the floor for: "
        f"{thin} - the walker or the group predicates broke, and every "
        "membership check above would have passed on an empty set"
    )


def test_every_exclusion_is_justified_and_still_real():
    # WHILE ``EXCLUDED_FROM_INVENTORY`` IS EMPTY, ONLY THE CAP BELOW RUNS.
    # The loop body executes zero times, so this test asserts nothing about
    # any reason string, scope membership or on-disk existence as the tree
    # stands - it asserts only that nobody has added thirteen exclusions. Said
    # here as well as in the module docstring because the person about to add
    # the first entry reads the test, not the header. The per-entry assertions
    # were watched failing against injected bogus entries; that measurement is
    # not a property this run re-establishes.
    assert len(EXCLUDED_FROM_INVENTORY) <= 12, (
        "the exclusion list has grown past a dozen entries, which means the "
        "SCOPE is wrong rather than the list - fix _SCOPE, do not keep adding"
    )
    for rel, reason in sorted(EXCLUDED_FROM_INVENTORY.items()):
        assert _group_of(rel) is not None, (
            f"{rel} is excluded from a scope it was never in - a stale "
            "exclusion is the place a real file hides"
        )
        assert (REPO_ROOT / rel).is_file(), (
            f"{rel} is excluded but does not exist - see the line above"
        )
        assert len(reason.strip()) >= 20, (
            f"{rel} is excluded without a reason a cold session can weigh"
        )


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
