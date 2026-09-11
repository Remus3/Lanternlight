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
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Mapping

import pytest

__all__ = [
    "BANNER_TITLE",
    "SKIP_REASON_PREFIX",
    "count_absent_tool_skips",
    "find",
    "reason_text",
    "require",
    "requires",
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


def summary_lines(counts: Mapping[str, int]) -> list[str]:
    """The end-of-run statement, or NO LINES AT ALL when nothing was skipped.

    The empty case is deliberate and is the reason this is a function rather
    than an unconditional print. A line that appears on every run is a line
    nobody reads, and a banner that said "0 tests skipped for a missing tool"
    every time would be exactly that. Silence here means the question does not
    arise on this machine.
    """
    if not counts:
        return []
    lines = [BANNER_TITLE]
    for tool, count in sorted(counts.items()):
        lines.append(
            f"{count} test(s) were SKIPPED because the external tool '{tool}' "
            "was not found on PATH."
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
    counts = count_absent_tool_skips(terminalreporter.stats.get("skipped", []))
    lines = summary_lines(counts)
    if not lines:
        return
    terminalreporter.write_sep("=", lines[0], red=True, bold=True)
    for line in lines[1:]:
        terminalreporter.write_line(line)
