"""One presence guard for every test in this suite that needs an external tool.

ROADMAP ``OPS-78``. Measured 2026-09-11 by ``tools/false_red_probe.py`` with
its positive control PROVED: with ``git`` stripped from every ``PATH`` entry
that carries it, 187 tests across 17 files failed or errored that otherwise
pass, and only 22 skipped cleanly. ``CLAUDE.md`` tells a fresh clone to run
``python -m pytest`` as its second command and this repository is PUBLIC, so
the reader who meets 187 unexplained failures may not be the operator.

THE DECISION THIS MODULE IMPLEMENTS, AND THE TWO ALTERNATIVES THAT WERE
REJECTED. Three shapes were available and all three were defensible, so the
reasoning is written down here rather than left to be re-derived:

* A COLLECTION-TIME REFUSAL that names the missing tool and stops the run was
  rejected. It makes one absent tool block the ENTIRE suite, including the
  roughly 2800 tests that never touch it. A contributor without ``git`` could
  then run nothing at all, which is a worse outcome than the problem being
  fixed.
* A BARE SKIP was rejected on its own. A skip is invisible in a green summary,
  so 187 silent skips would let a real regression hide on a machine that had
  quietly lost the tool - the counter-argument ``OPS-78`` records, and the
  reason its criterion 3 exists.
* WHAT WAS CHOSEN: the affected tests skip cleanly, AND the run states plainly
  at the end that N tests were skipped because a named tool was absent. A
  reader who sees green must also see that line. The skipping half lives here;
  the announcing half is :func:`pytest_terminal_summary` below, which
  ``tests/conftest.py`` re-exports so pytest registers it.

WHY THE SKIP REASON IS A FIXED STRING RATHER THAN A SENTENCE. The end-of-run
statement has to count skips per TOOL, and it can only do that by reading the
reasons back off the reports pytest collected. A reason written freehand at
each call site would be prose to a human and noise to the counter, so every
reason this module produces begins with :data:`SKIP_REASON_PREFIX` and names
the tool immediately after it. :func:`tool_from_reason` is the inverse, and
``tests/test_toolguard.py`` pins the round trip.

BIDIRECTIONAL BY CONSTRUCTION - ``docs/OPERATIONS.md``. :func:`require` does
not return a boolean and it does not return ``None``. It returns the RESOLVED
ABSOLUTE PATH to the executable, so a call site that wants the guard has to
use that path to invoke the tool. That makes the present direction impossible
to leave unpinned by accident: a test that guards with :func:`require` and then
never uses what it returned is visibly doing nothing with it. A guard that
skips when a tool is missing and does nothing when it is there is a negative
assertion - it rules something out without pinning anything down.

WHAT THIS MODULE DOES NOT CLAIM. Absence from ``PATH`` is not absence from the
machine: on Windows a program can still be found through the ``App Paths``
registry key or the current directory, so :func:`find` answering ``None`` means
"not on ``PATH``" and nothing stronger. That is the honest scope of the
question, and it is the same question ``tools/false_red_probe.py`` simulates by
stripping ``PATH`` entries by value.

WHY ``shutil.which`` IS CALLED THROUGH THE MODULE AND NEVER IMPORTED BY NAME.
The probe's in-run recorder replaces ``shutil.which`` for the length of the
session to record which tests looked a tool up. A module that had bound
``from shutil import which`` at import time would hold the original function
and be invisible to that instrument, so the lookup here is written as an
attribute access on every call.

----------------------------------------------------------------------------

ROADMAP ``OPS-83`` - THE SECOND SHAPE, FOR A DEPENDENCY THAT IS A SET.

``OPS-78`` above solves a dependency that is ONE executable. 49 tests in four
files have a dependency that is not: they run a real ``git commit`` against
this repository's own ``.githooks/pre-commit``, whose shebang is ``#!/bin/sh``
and whose body calls ``grep``, ``head``, ``printf``, ``tr`` and ``wc``. Naming
one tool cannot describe that, so a second guard is added here rather than the
first one being stretched. Three shapes were available and the reasoning is
written down so it is not re-derived:

* GUARD ON ``sh`` ALONE was rejected. It is honest about the entry point and
  silent about every utility the hook body calls, so a machine carrying ``sh``
  and no ``tr`` still produces an unexplained red - which is the exact defect
  ``OPS-78`` exists to remove, relocated rather than fixed.
* GUARD ON A HAND-WRITTEN FULL SET was rejected on its own. It is precise the
  day it is written and stale the moment a hook gains a ``sed``. This
  repository already says so about itself: ``ops/docguards.py`` derives its
  selection at run time precisely because a list in a file is silently green
  over everything added after it was written.
* WHAT WAS CHOSEN: a NAMED CAPABILITY whose member set is DECLARED in one place
  - :data:`POSIX_USERLAND_TOOLS` - and whose completeness is CHECKED BY
  DERIVATION from the hook sources. ``tests/test_toolguard.py`` re-reads both
  hooks, extracts the utility names actually invoked in them, and fails in both
  directions: an invoked utility that is not declared, and a declared utility
  nothing invokes. The declaration keeps the precision; the drift test removes
  the staleness. Staleness then presents as a RED TEST on a machine that HAS
  the userland, where a reader can diagnose and fix it, instead of as a false
  red on a bare box where nobody can.

WHY THE CAPABILITY SKIP REASON IS A SEPARATE PREFIX, NOT A LONGER TOOL REASON.
:func:`tool_from_reason` searches for :data:`SKIP_REASON_PREFIX` ANYWHERE in
the text. A capability reason that contained that prefix - or was contained by
it - would be counted by BOTH counters, and the end-of-run statement would
report a missing tool that is sitting on ``PATH`` while doubling the total.
:data:`CAPABILITY_SKIP_REASON_PREFIX` is therefore chosen so that neither
string contains the other, and ``tests/test_toolguard.py`` asserts exactly that
rather than leaving it to whoever edits the text next.

AND THE REASON ENUMERATES THE MISSING MEMBERS. "posix-userland absent" tells a
reader that something is wrong and sends them hunting for which something. The
members are named in the reason, carried through the counter, and printed in
the banner, because the whole point of the banner is that the reader does not
have to go looking.

WHAT THE OPS-83 MEASUREMENT SLICE ESTABLISHED, measured in an isolated
worktree with 184 tests across the four files passing at baseline:

* ``sh`` IS THE GATE, not one member among equals. With ``sh`` off ``PATH``
  git cannot spawn the hook at all - it reports ``error: cannot spawn
  <repo>/.githooks/pre-commit: No such file or directory`` - and ZERO of the 49
  recover no matter which utilities are restored alongside it. Restoring ``sh``
  alone recovers 38 and leaves 11.
* THE MINIMAL SET that takes all four files green is ``sh`` + ``grep`` + ``tr``.
  ``head`` and ``wc`` are invoked by the hook but are not exercised by these
  particular tests, and they are declared anyway: this guard names the
  USERLAND the hooks require, not a snapshot of which hook branch one test run
  happened to take. A guard trimmed to the branches one run reached would go
  wrong the first time a test covered a different branch.
* THERE IS NO BINARY NAMED ``bash`` INVOLVED. ``shutil.which("bash")`` answers
  ``None`` on this machine while all 184 pass. That is a statement about a
  FILENAME and nothing more: ``usr/bin/sh.exe`` here IS bash, reporting
  ``BASH_VERSION`` 5.2.37. So "no binary named bash", never "no bash".

WHY ``printf`` IS NOT A MEMBER, even though both hooks call it constantly. It
is a POSIX shell BUILTIN, so the interpreter named in the shebang provides it
and it is not a ``PATH`` dependency at all. The same goes for ``test``,
``echo`` and the other names in :data:`SHELL_BUILTIN_UTILITIES`, which exists
as a named constant precisely so the drift test can SUBTRACT it and say so,
rather than hiding the exclusion inside a condition nobody reads.

WHY A NAME-ONLY PRESENCE PROBE IS NOT ENOUGH ON WINDOWS, measured. With Git's
``usr/bin`` stripped from ``PATH``, ``shutil.which("find")`` still answers
``C:\\Windows\\system32\\find.EXE`` - a Windows program wearing a POSIX name,
on a box with no POSIX userland on it at all. A guard that only asked whether
the name resolved would report the capability COMPLETE there and then hand the
tests 49 unexplained reds, which is the whole defect restated. So
:func:`resolve_member` treats a resolution under ``%SystemRoot%`` as ABSENT for
any member listed in :data:`WINDOWS_HOMONYMS`. None of the five declared
members is such a homonym today; this is armour for the next one added, and it
is why the capability cannot simply be ``which()`` over the tuple.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

__all__ = [
    "BANNER_TITLE",
    "CAPABILITY_BANNER_TITLE",
    "CAPABILITY_SKIP_REASON_PREFIX",
    "CapabilitySkips",
    "POSIX_USERLAND",
    "POSIX_USERLAND_TOOLS",
    "SHELL_BUILTIN_UTILITIES",
    "SKIP_REASON_PREFIX",
    "WINDOWS_HOMONYMS",
    "capability_from_reason",
    "capability_skip_reason",
    "count_absent_capability_skips",
    "count_absent_tool_skips",
    "find",
    "missing_tools",
    "reason_text",
    "require",
    "require_capability",
    "require_posix_userland",
    "requires",
    "resolve_member",
    "requires_capability",
    "skip_reason",
    "summary_lines",
    "tool_from_reason",
]

#: Every skip this module produces starts with exactly this text, and the tool
#: name is the next whitespace-delimited token. Machine-readable on purpose -
#: see the module docstring on why a freehand sentence would not do.
SKIP_REASON_PREFIX = "external tool absent on PATH: "

#: Heading of the end-of-run banner. A constant so the test asserting the
#: banner appears is matching on the same text the banner is built from.
BANNER_TITLE = "EXTERNAL TOOL ABSENT - TESTS WERE SKIPPED"

#: Every CAPABILITY skip starts with exactly this text. It deliberately shares
#: no substring relationship with :data:`SKIP_REASON_PREFIX` in either
#: direction - see the module docstring on why that is load-bearing and not a
#: matter of taste. ``tests/test_toolguard.py`` asserts the disjointness.
CAPABILITY_SKIP_REASON_PREFIX = "required capability incomplete: "

#: Heading of the capability section of the end-of-run banner.
CAPABILITY_BANNER_TITLE = "REQUIRED CAPABILITY INCOMPLETE - TESTS WERE SKIPPED"

#: The capability name. One whitespace-free token, because it is parsed back
#: out of a skip reason by taking the first token after the prefix.
POSIX_USERLAND = "posix-userland"

#: POSIX utilities that are SHELL BUILTINS, so the interpreter provides them
#: and their presence in a hook says nothing about ``PATH``. Subtracted by the
#: drift test in ``tests/test_toolguard.py``, which is why this is a named
#: constant and not a condition buried in that test: an exclusion nobody can
#: see is an exclusion nobody re-checks. ``printf`` is the one that matters
#: here - both hooks call it on nearly every line and it is deliberately NOT a
#: member of the capability.
SHELL_BUILTIN_UTILITIES = frozenset({"echo", "printf", "pwd", "test", "true", "false"})

#: Names that a POSIX utility and a Windows system program SHARE. Measured
#: 2026-09-12: every one of these exists under ``%SystemRoot%\\System32`` on
#: this machine, so ``shutil.which`` answers a path for all of them on a box
#: carrying no POSIX userland whatsoever. See the module docstring and
#: :func:`resolve_member`.
WINDOWS_HOMONYMS = frozenset(
    {"comp", "fc", "find", "forfiles", "more", "print", "sort", "timeout", "tree", "where"}
)

#: The declared members of :data:`POSIX_USERLAND`, settled by the OPS-83
#: measurement slice rather than by reading the ROADMAP entry's prose.
#:
#: The entry's own list said the hook body calls ``find``, ``mv`` and
#: ``printf`` as well. All three are wrong, and the entry's list was itself
#: produced by a naive word scan:
#:
#: * ``mv`` occurs ZERO times in either hook. It appears once as PROSE inside a
#:   pre-commit comment, ``git mv a.py b.py``.
#: * ``find`` occurs once, inside the git option ``--find-renames``. A hyphen
#:   is a word boundary, so a bare ``\\bfind\\b`` scan reads a git FLAG as a
#:   utility. The same scan also reports ``diff`` (from ``git diff``), ``tar``
#:   (from a ``*.tar`` filename glob) and ``sh`` (from a ``*.sh`` one).
#: * ``printf`` really is invoked, everywhere, and is excluded on purpose
#:   because it is a shell BUILTIN - see :data:`SHELL_BUILTIN_UTILITIES`.
#:
#: ``sh`` is a member because it is the interpreter every hook shebang names,
#: and because it is the GATE: without it git cannot spawn the hook at all. It
#: is derived from the shebang line rather than from the hook body, and the
#: drift test exempts it from the body check for that reason.
#:
#: The drift test in ``tests/test_toolguard.py`` re-derives the utilities that
#: sit in COMMAND POSITION in ``.githooks/pre-commit`` and
#: ``.githooks/commit-msg`` and fails in BOTH directions, so a member added
#: here that no hook invokes is a red test and not a quiet coverage loss.
POSIX_USERLAND_TOOLS = ("sh", "grep", "head", "tr", "wc")


class CapabilitySkips(NamedTuple):
    """How many tests a capability skipped, and which members were missing.

    A named tuple rather than a bare pair so the banner code reads as what it
    means, while still comparing equal to a plain ``(count, missing)`` tuple in
    a test - the assertion stays readable without importing this type.
    """

    #: Number of skipped tests attributed to this capability.
    count: int
    #: The UNION of the members named across those skips, sorted. A union
    #: rather than one skip's list because different call sites can ask for
    #: different member subsets, and the reader wants everything that is
    #: missing, not whatever the first skip happened to mention.
    missing: tuple[str, ...]


#: Parses a capability reason back out. The name is one whitespace-free token
#: and the members are inside the parentheses, so the closing paren terminates
#: the match and a ``skipif`` condition appended after it cannot bleed in.
_CAPABILITY_REASON_RE = re.compile(
    re.escape(CAPABILITY_SKIP_REASON_PREFIX) + r"(\S+) \(missing: ([^)]*)\)"
)


def skip_reason(tool: str) -> str:
    """The exact skip reason for a missing ``tool``.

    One function rather than a format string at each call site, so the shape
    the counter parses and the shape the guards emit cannot drift apart.
    """
    return SKIP_REASON_PREFIX + tool


def tool_from_reason(reason: object) -> str | None:
    """The tool named by a skip reason, or ``None`` when it names none.

    Tolerant of what pytest wraps around a reason. A skipped report's text
    arrives as ``"Skipped: <reason>"``, and a reason recorded through a
    ``skipif`` marker can arrive with the condition appended, so the prefix is
    searched for ANYWHERE in the text rather than required at position zero.

    Returning ``None`` for an unrelated skip is the load-bearing half: the
    suite skips for reasons that have nothing to do with an absent tool, and a
    counter that swept those in would announce a missing tool that is present.
    """
    if not isinstance(reason, str):
        return None
    index = reason.find(SKIP_REASON_PREFIX)
    if index < 0:
        return None
    tail = reason[index + len(SKIP_REASON_PREFIX) :].strip()
    if not tail:
        return None
    return tail.split()[0]


def find(tool: str) -> str | None:
    """The resolved path to ``tool`` on ``PATH``, or ``None``.

    A thin wrapper on purpose. It exists so there is ONE place the lookup
    happens, so the lookup is an attribute access on ``shutil`` rather than a
    bound name (see the module docstring), and so a test can monkeypatch the
    lookup in one spot instead of in every guard.
    """
    return shutil.which(tool)


def require(tool: str) -> str:
    """Return the resolved path to ``tool``, or skip this test naming it.

    THE RETURN VALUE IS THE POINT. Call sites invoke the returned path rather
    than the bare name, which pins the present direction as well as the absent
    one - ``docs/OPERATIONS.md``, bidirectional guard discipline.

    The skip is raised through :func:`pytest.skip`, whose exception derives
    from ``BaseException`` rather than ``Exception``. That matters here: this
    repository has fail-soft helpers carrying a bare ``except Exception``, and
    a skip built on ``Exception`` would be swallowed by one of them and turn
    into a pass that never ran anything.
    """
    found = find(tool)
    if found is None:
        pytest.skip(skip_reason(tool))
    return found


def requires(tool: str) -> pytest.MarkDecorator:
    """A ``skipif`` marker for a whole class or module that needs ``tool``.

    Use this ONLY where every test under it genuinely reaches the tool, and say
    why in the file. A module-level marker applied to make a number go down
    would skip tests that never needed the tool, which is a coverage loss
    wearing the costume of a fix.

    Prefer :func:`require` at the call site wherever the tool is actually
    invoked: this marker cannot return a path, so it pins only the absent
    direction.
    """
    return pytest.mark.skipif(find(tool) is None, reason=skip_reason(tool))


#: The Windows EXTENDED-LENGTH path prefixes. ``\\\\?\\C:\\x`` is the same file
#: as ``C:\\x`` and ``\\\\?\\UNC\\host\\share\\x`` is the same file as
#: ``\\\\host\\share\\x``, but ``pathlib`` gives the prefixed spelling its own
#: ANCHOR, so the plain ``%SystemRoot%`` is not among its ``parents`` and the
#: containment test silently misses. Only the backslash spelling exists:
#: Windows passes an extended-length path to the filesystem verbatim and does
#: not accept ``//?/``, so there is no forward-slash form to normalise.
_EXTENDED_LENGTH_UNC_PREFIX = "\\\\?\\UNC\\"
_EXTENDED_LENGTH_PREFIX = "\\\\?\\"


def _without_extended_length_prefix(path: str) -> str:
    """``path`` with any extended-length prefix removed, otherwise unchanged.

    The UNC form collapses back to ``\\\\host\\share\\...`` rather than to a
    drive letter, because that is what it means. It does not become resolvable
    against ``%SystemRoot%`` by doing so - see :func:`_under_system_root` - but
    the two spellings of one UNC path stop disagreeing, which is the part that
    can be settled without guessing.
    """
    if path.startswith(_EXTENDED_LENGTH_UNC_PREFIX):
        return "\\\\" + path[len(_EXTENDED_LENGTH_UNC_PREFIX) :]
    if path.startswith(_EXTENDED_LENGTH_PREFIX):
        return path[len(_EXTENDED_LENGTH_PREFIX) :]
    return path


def _under_system_root(path: str) -> bool:
    """Whether ``path`` sits inside ``%SystemRoot%``.

    Compared as resolved paths rather than as text, so a different casing or a
    short 8.3 component cannot make a system32 program read as a POSIX one.
    ``SystemRoot`` is read from the environment on every call - a module-level
    snapshot would be invisible to a test that sets it. Extended-length
    spellings are normalised first, because ``pathlib`` treats ``\\\\?\\C:\\``
    as a different anchor from ``C:\\`` and would otherwise answer ``False``
    for a system32 program.

    THE LIMIT, stated rather than implied. A UNC ADMINISTRATIVE SHARE -
    ``\\\\host\\C$\\Windows\\system32\\find.EXE`` - is NOT recognised and reads
    as a present POSIX utility. It names this machine's own system32 when
    ``host`` denotes this machine and another machine's when it does not, and
    nothing here can tell those apart without deciding which of a machine's
    many names - NetBIOS name, FQDN, ``localhost``, ``.``, a loopback literal,
    an address that resolves differently on a different network - is itself. A
    guess would be wrong in both directions: condemning a genuine remote
    userland, or admitting a system32 homonym. The honest answer is that the
    question is not settled here, and
    ``tests/test_toolguard.py`` pins the limit so it is a known hole with a
    test behind it rather than a silence. It is reachable only from a ``PATH``
    entry written in UNC form, which nothing this repository creates does.
    """
    # Upper case because ruff's SIM112 asks for it; harmless either way, since
    # os.environ is case-insensitive on Windows - it upper-cases both the keys
    # it stores and the key it is asked for.
    root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if not root:
        return False
    try:
        resolved_root = Path(_without_extended_length_prefix(root)).resolve()
        resolved_path = Path(_without_extended_length_prefix(path)).resolve()
        return resolved_root in resolved_path.parents
    except OSError:
        return False


def resolve_member(tool: str) -> str | None:
    """Resolve a CAPABILITY member, refusing a Windows program of the same name.

    :func:`find` answers the ``PATH`` question and nothing more, which is the
    right answer for the single-tool guard and the WRONG one for a member of
    :data:`WINDOWS_HOMONYMS`: measured 2026-09-12, with Git's ``usr/bin``
    stripped from ``PATH``, ``shutil.which("find")`` still returns
    ``C:\\Windows\\system32\\find.EXE``. Reporting the capability complete on
    the strength of that is how a guard hands back 49 unexplained reds while
    believing it did its job.

    Deliberately NOT folded into :func:`find`: the single-tool API's behaviour
    is pinned by ``OPS-78``'s tests and is not changed here.
    """
    found = find(tool)
    if found is None:
        return None
    if tool in WINDOWS_HOMONYMS and _under_system_root(found):
        return None
    return found


def missing_tools(tools: Iterable[str]) -> tuple[str, ...]:
    """The members of ``tools`` that are not usable on ``PATH``, order preserved.

    Order is preserved rather than sorted so the reason reads in the order the
    call site declared, which is the order a reader will compare it against.
    The lookup goes through :func:`resolve_member`, so a Windows homonym under
    ``%SystemRoot%`` counts as MISSING rather than as present.
    """
    return tuple(tool for tool in tools if resolve_member(tool) is None)


def capability_skip_reason(name: str, missing: Iterable[str]) -> str:
    """The exact skip reason for ``name`` with ``missing`` members absent.

    The members are enumerated on purpose. ``posix-userland absent`` would tell
    a reader that something is wrong and then send them hunting for which
    something, which is the failure mode the end-of-run banner exists to
    prevent rather than to reproduce.
    """
    return f"{CAPABILITY_SKIP_REASON_PREFIX}{name} (missing: {', '.join(missing)})"


def capability_from_reason(reason: object) -> tuple[str, tuple[str, ...]] | None:
    """The ``(name, missing)`` pair a capability skip reason carries, or ``None``.

    Tolerant of pytest's ``"Skipped: <reason>"`` wrapper in exactly the way
    :func:`tool_from_reason` is, and terminated by the closing parenthesis so a
    ``skipif`` condition rendered after the reason cannot be read as a member.

    Returning ``None`` for every other skip is the load-bearing half, for the
    same reason it is in :func:`tool_from_reason`: this suite skips for reasons
    that have nothing to do with a capability, and a counter that swept those
    in would announce a missing userland on a machine that has one.
    """
    if not isinstance(reason, str):
        return None
    match = _CAPABILITY_REASON_RE.search(reason)
    if match is None:
        return None
    members = tuple(part.strip() for part in match.group(2).split(",") if part.strip())
    if not members:
        return None
    return match.group(1), members


def require_capability(name: str, tools: Iterable[str]) -> dict[str, str]:
    """Return every member of ``name`` mapped to its path, or skip naming ``name``.

    THE RETURN VALUE IS THE POINT, exactly as it is in :func:`require`. A call
    site that guards with this and then invokes the bare names has pinned only
    the absent direction; one that invokes the returned paths has pinned both.

    The skip is raised through :func:`pytest.skip`, whose exception derives
    from ``BaseException`` rather than ``Exception``, so a fail-soft
    ``except Exception`` in this repository cannot swallow it and turn a skip
    into a pass that ran nothing.
    """
    declared = tuple(tools)
    resolved: dict[str, str] = {}
    absent: list[str] = []
    for tool in declared:
        found = resolve_member(tool)
        if found is None:
            absent.append(tool)
        else:
            resolved[tool] = found
    if absent:
        pytest.skip(capability_skip_reason(name, tuple(absent)))
    return resolved


def requires_capability(name: str, tools: Iterable[str]) -> pytest.MarkDecorator:
    """A ``skipif`` marker for a whole class or module that needs ``name``.

    HONEST LIMIT: this pins only the ABSENT direction. A marker cannot hand
    back the resolved paths, so it cannot make a call site prove it used them.
    For the four files ``OPS-83`` is about, the PRESENT direction is pinned by
    the test bodies themselves - they run a real ``git commit`` against this
    repository's own ``.githooks/pre-commit``, which fails outright if the
    userland is not really there. That is a stronger positive pin than any
    marker could supply, which is why the marker is acceptable here and would
    not be acceptable somewhere the tests merely imported something.

    Prefer :func:`require_capability` at the call site wherever the utilities
    are actually reached.
    """
    declared = tuple(tools)
    absent = missing_tools(declared)
    return pytest.mark.skipif(
        bool(absent), reason=capability_skip_reason(name, absent or declared)
    )


def require_posix_userland() -> dict[str, str]:
    """Require the POSIX userland the git hooks need. The one call-site name.

    A named function rather than the two arguments spelled out at each of the
    four files, so the capability a test declares and the capability the banner
    counts cannot drift apart by a typo.
    """
    return require_capability(POSIX_USERLAND, POSIX_USERLAND_TOOLS)


def reason_text(report: object) -> str:
    """The human text of a skipped report, however pytest happened to shape it.

    ``longrepr`` on a skipped report is normally a ``(path, lineno, reason)``
    triple, but a skip raised from a fixture or from collection can arrive as a
    plain string or as an object that only renders. All three are flattened to
    text here so the counter has exactly one thing to parse.
    """
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    if isinstance(longrepr, str):
        return longrepr
    if longrepr is not None:
        return str(longrepr)
    return ""


def count_absent_tool_skips(reports: Iterable[object]) -> dict[str, int]:
    """Count skipped ``reports`` per absent tool, ignoring every other skip.

    Pure over the reports it is handed, so the end-of-run statement can be
    tested without running a suite twice.
    """
    counts: dict[str, int] = {}
    for report in reports:
        tool = tool_from_reason(reason_text(report))
        if tool is None:
            continue
        counts[tool] = counts.get(tool, 0) + 1
    return counts


def count_absent_capability_skips(
    reports: Iterable[object],
) -> dict[str, CapabilitySkips]:
    """Count skipped ``reports`` per incomplete capability, and union the members.

    Pure over the reports it is handed, like :func:`count_absent_tool_skips`,
    so the end-of-run statement can be tested without running a suite twice.

    A capability reason never matches :data:`SKIP_REASON_PREFIX`, so a skip
    counted here is never also counted there. That is asserted directly in
    ``tests/test_toolguard.py`` rather than left as a property of two string
    constants nobody re-checks.
    """
    counts: dict[str, int] = {}
    members: dict[str, set[str]] = {}
    for report in reports:
        parsed = capability_from_reason(reason_text(report))
        if parsed is None:
            continue
        name, missing = parsed
        counts[name] = counts.get(name, 0) + 1
        members.setdefault(name, set()).update(missing)
    return {
        name: CapabilitySkips(count, tuple(sorted(members[name])))
        for name, count in counts.items()
    }


def summary_lines(
    counts: Mapping[str, int],
    capabilities: Mapping[str, tuple[int, tuple[str, ...]]] | None = None,
) -> list[str]:
    """The end-of-run statement, or NO LINES AT ALL when nothing was skipped.

    The empty case is deliberate and is the reason this is a function rather
    than an unconditional print. A line that appears on every run is a line
    nobody reads, and a banner that said "0 tests skipped for a missing tool"
    every time would be exactly that. Silence here means the question does not
    arise on this machine.

    Two sections, either of which may be absent. The single-tool section is
    unchanged from ``OPS-78``, wording included; the capability section is
    ``OPS-83`` criterion 2, and it names the missing members because a count
    without them sends the reader hunting. ``lines[0]`` is always a title, so
    the caller can render it as a separator without inspecting the text.
    """
    capabilities = capabilities or {}
    if not counts and not capabilities:
        return []
    lines: list[str] = []
    if counts:
        lines.append(BANNER_TITLE)
        for tool, count in sorted(counts.items()):
            lines.append(
                f"{count} test(s) were SKIPPED because the external tool '{tool}' "
                "was not found on PATH."
            )
    if capabilities:
        lines.append(CAPABILITY_BANNER_TITLE)
        for name, entry in sorted(capabilities.items()):
            count, missing = entry
            lines.append(
                f"{count} test(s) were SKIPPED because the capability "
                f"'{name}' is incomplete on PATH. Missing: "
                f"{', '.join(missing) if missing else '(none named)'}."
            )
    lines.append(
        "Those tests did NOT run. The pass/fail summary above says nothing "
        "about them, so a green run on this machine is narrower than a green "
        "run on one that has every tool. Install the named tool(s) and re-run "
        "to cover them."
    )
    return lines


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """State, at the end of the run, that tests were skipped for a missing tool.

    Registered by ``tests/conftest.py`` importing this name, which is what puts
    it in front of pytest's plugin manager; it is also directly loadable with
    ``-p _toolguard`` when this directory is on ``PYTHONPATH``, which is how
    ``tests/test_toolguard.py`` proves the statement really appears in a real
    run rather than only that a formatter returns a list.

    It writes NOTHING when no such skip happened - see :func:`summary_lines`.
    """
    skipped = list(terminalreporter.stats.get("skipped", []))
    counts = count_absent_tool_skips(skipped)
    capabilities = count_absent_capability_skips(skipped)
    lines = summary_lines(counts, capabilities)
    if not lines:
        return
    titles = {BANNER_TITLE, CAPABILITY_BANNER_TITLE}
    for line in lines:
        if line in titles:
            terminalreporter.write_sep("=", line, red=True, bold=True)
        else:
            terminalreporter.write_line(line)
