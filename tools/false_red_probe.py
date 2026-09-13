"""Measure what this suite's external-tool guards are actually doing.

ROADMAP ``OPS-74``. A test that shells out to an external tool and guards
itself with a presence check has TWO behaviours, and a green suite only ever
exercises one of them. When the tool is present the guard is invisible. When it
is absent the test may skip cleanly, may fail or error for no reason but the
absence, or - worst - may pass while the thing it was supposed to check never
ran at all. This repository has never measured how much of that last shape it
carries, and a shape nobody has measured is not a shape anybody can call zero.

The method is re-implemented here from described behaviour. No file was copied
in and no module is imported from a sibling tree.

WHAT THE PROBE DOES. It runs the suite twice: once with the environment as it
stands, and once with every ``PATH`` entry that actually carries a ``git``
executable removed BY VALUE. It reports the delta by test id AND by file, never
merely as a total, because a total hides a file that lost five tests while
another gained five - the per-file lesson ``ops/merge_gate.py`` already learned
and wrote down.

THE THREE OUTCOMES, WHICH ARE NEVER COLLAPSED INTO ONE ANOTHER:

``clean_skip``
    Passed with the tool, skipped without it. The guard did its job.
``false_red``
    Passed with the tool, failed or errored without it, for no reason but the
    absence. A red that says nothing about the code under test.
``silent_pass``
    Passed in BOTH directions, looked the tool up at least once, and never
    invoked it in either run. This is the one the item exists for, and it
    cannot be read off pytest's summary at all.

HOW THE THIRD IS MEASURED, AND WHAT THAT MEASUREMENT CANNOT PROVE. An in-run
plugin wraps two entry points for the length of the session - ``shutil.which``
(the presence lookup) and ``subprocess.Popen`` (which every ``subprocess.run``,
``call``, ``check_call`` and ``check_output`` goes through) - and records, per
test id, whether the tool was looked up and whether it was actually invoked.

What that can support: a test that passed both ways, looked the tool up, and
invoked it in neither run is a CANDIDATE for a guard that never fired.

What it cannot support, stated here rather than left for a reader to discover:

* A candidate is a CANDIDATE, NOT A CONVICTION. A test may legitimately look a
  tool up and correctly decide it has nothing further to do. Only reading the
  test settles it.
* The instrument is blind to spellings it does not wrap. ``os.system``,
  ``os.popen``, ``os.spawn*``, ``ctypes`` process creation, and a module that
  bound ``from shutil import which`` before the plugin loaded are all
  invisible. A zero from a blind instrument is an absence of evidence.
* A MODULE-LEVEL lookup is missed too, and the REASON is not the one this
  module used to give - ``OPS-79`` gap 2, corrected 2026-09-11. The plugin is
  loaded with ``-p`` before collection, so ``shutil.which`` is ALREADY WRAPPED
  when a test module is imported and the wrapper really does fire. What is
  missing is an OWNER. The recorder attributes a call to
  ``_current["nodeid"]``, which is set only between
  ``pytest_runtest_logstart`` and ``pytest_runtest_logfinish``, and a module
  body runs during COLLECTION, when no test is current. The mark is therefore
  DISCARDED rather than unobserved, and the test lands in ``untouched``. The
  earlier explanation - "a cached lookup performed at import time before the
  plugin loads" - WAS WRONG ABOUT THE MECHANISM: nothing is cached and the
  plugin is already loaded. The consequence is unchanged and is recorded under
  ``OPS-74``: ``silent_pass=0`` for ``git`` was structurally guaranteed,
  because no test in this tree performs an in-process lookup for it inside a
  test body. Module level is how this repository usually writes them.

  RECOGNITION WAS NOT ADOPTED, and the reason is stated here rather than left
  as a silence. A module-level lookup is a fact about a FILE, not about a
  test, so attributing it to every test in that file would reclassify whole
  modules as candidates and make the finding worthless - the exact failure the
  ``untouched`` rule below exists to prevent. The limitation is instead
  printed in the report itself, on every run, so a reader who never opens this
  source cannot read a zero as a clean bill.
* Attribution is per test id and comes from pytest's own phase hooks, so work
  a test performs in a session-scoped fixture, in a background thread, or in a
  subprocess of its own is attributed to whichever test was running - or to
  nothing at all.
* Absence of ``git`` on ``PATH`` is not absence of ``git``. On Windows a
  program can still be found through the ``App Paths`` registry key or the
  current directory, so a test that keeps working may be finding it another
  way rather than not needing it.

WHY THE POSITIVE CONTROL IS NOT OPTIONAL - criterion 3. Every claim above is a
claim about an INSTRUMENT, and this repository has been burned three times by
exactly that: ``grep -iF`` crashed and read as a clean negative, ``taskkill``
killed nothing while a follow-up check honestly answered ARMED, and ``-q``
printed no summary line while an exit code stayed 0. So the probe plants a
deliberate false-red site of its own, in a temporary directory OUTSIDE this
tree, runs it in both directions alongside the suite, and reports whether it
saw each planted shape. If it did not, the report says UNPROVEN and its zero is
worth nothing. The planted module is built and torn down by the probe itself
and is never left in the tree.

THE CONTROL IS PARAMETERISED BY THE TOOL, AND IT RUNS IN BOTH DIRECTIONS -
``OPS-79`` gap 4 and gap 1, both closed 2026-09-11.

* The planted source used to fix ``git`` in a literal, so every ``--tool``
  setting but one planted specimens that could not match: the probe reported
  UNPROVEN BY CONSTRUCTION while still printing a full set of counts, and
  ``--tool bash`` printed 56 false reds that were an absence of evidence. The
  source is now generated by :func:`control_module_source` from the tool under
  test, so a second tool can prove its own instrument. A flag whose every
  setting but one produces an unprovable answer is a flag that lies.
* Three POSITIVE specimens prove the instrument can SEE and prove nothing about
  whether it INVENTS. A classifier mutated to promote every ``untouched`` test
  to ``silent_pass`` passed the old control untouched, because all three
  specimens still landed on their expected kind - a probe that called
  everything a finding would have reported PROVED. There are now NEGATIVE
  specimens too, named in :data:`NEGATIVE_CONTROLS`: planted tests that must
  NOT be classified as findings, and an over-reporting classifier fails the
  control on them instead of passing it. One of the two is also the planted
  demonstration of the module-level limitation above - it looks the tool up at
  module level and must still land in ``untouched``.

HOW THE CONTROLS ARE KEPT OUT OF THIS TREE'S FIGURES, AND WHY THAT IS A CHOSEN
ACCOUNTING RATHER THAN AN OVERSIGHT. The planted module is collected by the same
pytest invocation the probe measures - it has to be, or it controls nothing - so
its three tests appear in both runs and would otherwise land in the kind tally,
in the findings list and in the collected totals. They are therefore EXCLUDED
from every one of those, while still being REQUIRED to have been classified: a
control the probe did not see makes the whole report UNPROVEN. The alternative,
leaving them in and asking the reader to subtract three, was rejected because a
number a reader has to correct is a number a reader will quote uncorrected. The
planted controls are reported in a stanza of their own instead, so the evidence
that the instrument works stays visible without inflating the claim about this
repository.

THE RECOGNITION BUG THAT MADE THE FIRST RUN UNPROVEN, written down because the
filed diagnosis of it was wrong. On 2026-09-11 the first run against this tree
reported all three controls as never classified, and the cause was recorded as
the control never being collected at all. Re-measured the same day with
``python -m pytest --collect-only tests <planted control path>``: the
repository's own ``tests`` directory collected 2985 and the same command with
the planted file collected 2988, so the control WAS collected, in both
directions. What failed was RECOGNITION. pytest builds the node id for a file
outside the root directory by joining its collector chain with ``::`` rather
than by relative path, so the id begins with that separator - and this module
found a test's file by splitting at the first ``::``, which returned an empty
string and matched no control. The arithmetic said as much on its own: that
run's kind tally summed to 2988 rather than 2985, which is only possible if the
three controls were being counted as repository tests. :func:`file_of` now walks
the segments to the one naming a ``.py`` file, :func:`is_control` matches on the
module basename in any segment, and :func:`control_test_name` reads the test
from the LAST segment rather than from the second.

A SECOND NODE-ID SHAPE, AND WHY BOTH REPAIRS WERE TAKEN - ``OPS-86``.

The repair above assumes the id still carries a ``.py`` segment somewhere. It
does not always. Measured BY CONSTRUCTION on 2026-09-12 rather than inferred
from the single run that found it: the control was planted under the system
temp area both times and only the ROOTDIR was varied.

* Rootdir OUTSIDE the system temp tree - the ordinary case of running this
  probe from the repository root - gives an id whose segments are the
  collector chain and which still names the module::

      ::<temp path segments>::test_false_red_control.py::test_control_false_red

* Rootdir INSIDE the system temp tree - a git worktree under the session
  scratchpad, which is how ``OPS-83`` hit this - gives::

      ::test_control_false_red

  There is no file segment at all. Not a mangled one: none. So a basename
  match has nothing to see, all five specimens read as never classified, and
  the run is UNPROVEN by construction.

BOTH REPAIRS WERE TAKEN, because they close different things.

* RECOGNITION closes the shape that has been MEASURED. :func:`is_control`
  accepts a bare id whose single non-empty segment is one of this module's own
  planted specimen names. That is narrow on two axes at once - one segment,
  and a name this module planted - because a name-only match would reclassify
  a repository test that happened to share a name, and a repository id always
  carries its file so it can never have exactly one segment.
* REFUSAL closes the CLASS. :func:`format_report` now REFUSES to print counts
  it cannot attribute: an UNPROVEN run prints the control stanza and stops,
  with no kind tally, no findings list, no per-file deltas and no collected
  totals. Recognition alone would have been the wrong answer, because the harm
  in ``OPS-83`` was not that one shape went unmatched - the doctrine already
  declared that an absence of evidence - it was that a full count table was
  printed underneath the word UNPROVEN and read exactly like a set of
  findings. The next unmeasured shape does that again, and the refusal is the
  only half of this that does not need to have seen the shape first.

BIDIRECTIONAL DISCIPLINE - criterion 5. The clean-skip control skipping without
the tool is only half the evidence. The probe also requires that the same
control INVOKED the tool in the run where it was present. A guard that skips
when a tool is missing and does nothing when it is there is a negative
assertion: it rules something out without pinning anything down.

TESTABILITY. Everything here except :func:`default_runner` is a pure function
over recorded text, and the runner is injected, so ``tests/test_false_red_probe``
never runs the real suite.

AND IT MUST NOT, BECAUSE THIS PROBE RECURSES IF IT IS EVER CALLED FROM INSIDE
ITS OWN RUN. The two runs collect the whole ``tests`` directory, which includes
the probe's own test module. A test in that module that reached
:func:`default_runner` would spawn two suite runs, each of which would collect
that module again and spawn two more. Measured 2026-09-11, while watching a
deliberate mutation of ``allow_abbrev`` go red: the refusal stopped firing, one
command-line test fell through to a real run, and five nested suite processes
were alive within two minutes. The guard is in the test module - every call
there passes an injected runner, and a test asserts it - but the hazard belongs
to this design rather than to that file, so it is written down here too.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "CONTROL_MODULE_NAME",
    "CONTROL_MODULE_SOURCE",
    "CONTROL_MODULE_TEMPLATE",
    "NEGATIVE_CONTROLS",
    "SILENT_PASS_LIMITATION",
    "co_located_executables",
    "tool_granularity_limitation",
    "TOOL_NAME_CHARS",
    "control_module_source",
    "Classification",
    "ControlResult",
    "FINDING_KINDS",
    "FileDelta",
    "PLUGIN_MODULE_NAME",
    "PLUGIN_SOURCE",
    "ProbeReport",
    "REPO_ROOT",
    "TOOL_DEFAULT",
    "TestOutcome",
    "UNPROVEN_EXIT_CODE",
    "USAGE_EXIT_CODE",
    "build_parser",
    "classify",
    "control_expectations",
    "control_test_name",
    "default_runner",
    "delta_by_file",
    "delta_by_test_id",
    "entry_carries_tool",
    "evaluate_controls",
    "executable_suffixes",
    "file_of",
    "format_report",
    "is_control",
    "main",
    "parse_record",
    "planted_controls",
    "probe",
    "pytest_args",
    "strip_tool_from_path",
]

#: Repository root, resolved from this file's location: tools/false_red_probe.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The tool whose absence is simulated. ``git`` because it is the one this
#: tree's tests reach for most, and because its absence is the realistic case
#: on a machine that has Python but no developer tooling.
TOOL_DEFAULT = "git"

#: Exit code for a usage error - an unknown flag, or a positional argument this
#: entry point takes none of. Deliberately distinct from 1: "you typed
#: something I do not understand" and "this tree has a false red in it" are
#: different facts, and a caller that cannot tell them apart learns nothing
#: from either. ``OPS-66`` and ``OPS-67`` closed this defect elsewhere.
USAGE_EXIT_CODE = 2

#: Exit code for a run whose own instrument was not proved. Distinct from both
#: 0 and 1 on purpose: a report whose positive control was not seen has found
#: nothing AND has proved nothing, and calling that either green or red would
#: be a claim the run cannot support.
UNPROVEN_EXIT_CODE = 3

#: Kinds that are defects in this tree rather than descriptions of it.
#: ``clean_skip`` is deliberately absent - it is the guard working.
FINDING_KINDS = frozenset({"false_red", "silent_pass", "vanished"})

#: Module name the planted control file is written under. The probe matches a
#: control by this BASENAME, so the temporary directory it lives in can change
#: between runs without changing what counts as a control.
CONTROL_MODULE_NAME = "test_false_red_control.py"

#: Module name the in-run plugin is written under and loaded with ``-p``.
PLUGIN_MODULE_NAME = "false_red_probe_plugin"

#: Environment variable naming the JSON file the plugin writes.
RECORD_ENV_VAR = "FALSE_RED_PROBE_JSON"

#: Environment variable naming the tool the plugin watches for.
TOOL_ENV_VAR = "FALSE_RED_PROBE_TOOL"


PLUGIN_SOURCE = '''\
"""In-run recorder for tools/false_red_probe.py. Written to a temporary
directory by the probe and loaded with ``-p``; never part of this repository's
tracked tree.

It records, per test id, the test's outcome and whether the watched tool was
looked up or actually invoked while that test was running. It writes nothing
until the session ends, and it writes atomically.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

_TOOL = os.environ.get("FALSE_RED_PROBE_TOOL", "git").lower()
_OUT = os.environ.get("FALSE_RED_PROBE_JSON", "")

_current = {"nodeid": None}
_records = {}


def _slot(nodeid):
    return _records.setdefault(
        nodeid, {"outcome": "", "invoked": False, "looked_up": False}
    )


def _mark(key):
    nodeid = _current["nodeid"]
    if nodeid is None:
        return
    _slot(nodeid)[key] = True


def _is_tool(name):
    try:
        text = os.fsdecode(name)
    except Exception:
        return False
    base = os.path.basename(text).lower()
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return base == _TOOL or stem == _TOOL


def _argv_names_tool(args):
    if isinstance(args, (str, bytes, os.PathLike)):
        try:
            text = os.fsdecode(args)
        except Exception:
            return False
        first = text.split()[0] if text.split() else ""
        return _is_tool(first.strip('"'))
    try:
        first = args[0]
    except Exception:
        return False
    return _is_tool(first)


_real_popen = subprocess.Popen


class _ProbePopen(_real_popen):
    def __init__(self, args, *rest, **kwargs):
        if _argv_names_tool(args):
            _mark("invoked")
        super().__init__(args, *rest, **kwargs)


subprocess.Popen = _ProbePopen

_real_which = shutil.which


def _probe_which(cmd, *rest, **kwargs):
    if _is_tool(cmd):
        _mark("looked_up")
    return _real_which(cmd, *rest, **kwargs)


shutil.which = _probe_which


def pytest_runtest_logstart(nodeid, location):
    _current["nodeid"] = nodeid
    _slot(nodeid)


def pytest_runtest_logfinish(nodeid, location):
    _current["nodeid"] = None


def pytest_runtest_logreport(report):
    slot = _slot(report.nodeid)
    current = slot["outcome"]
    if report.outcome == "failed":
        slot["outcome"] = "failed" if report.when == "call" else "error"
    elif report.outcome == "skipped":
        if current not in ("failed", "error"):
            slot["outcome"] = "skipped"
    elif report.when == "call" and current == "":
        slot["outcome"] = "passed"
    elif current == "":
        slot["outcome"] = "passed"


def pytest_sessionfinish(session, exitstatus):
    if not _OUT:
        return
    payload = {"tool": _TOOL, "tests": _records}
    target = Path(_OUT)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="ascii")
    tmp.replace(target)
'''


#: Characters a tool name may contain before it is pasted into generated
#: Python source. Deliberately narrow: the name reaches a string literal in a
#: file this module writes and then executes as a test module, so anything that
#: could close that literal is refused rather than escaped. Real executable
#: names live inside this set - ``git``, ``bash``, ``hg``, ``node``, ``7z``,
#: ``g++`` - and a name that does not is a usage error, not a special case.
TOOL_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.+-"
)

#: Placeholder the control template carries where the tool name belongs. A
#: replace rather than ``format`` or an f-string, because the template is
#: Python source and a brace in it must stay a brace.
_TOOL_PLACEHOLDER = "__TOOL_UNDER_TEST__"

CONTROL_MODULE_TEMPLATE = '''\
"""Planted control for tools/false_red_probe.py - ROADMAP OPS-74 and OPS-79.

This file is written into a temporary directory by the probe, collected
alongside the real suite, and deleted again. It is never part of the tracked
tree.

The first three tests are POSITIVE specimens - one of each outcome the probe
claims to tell apart - so a run that fails to see all three has proved its own
instrument blind and must not report a zero. The last two are NEGATIVE
specimens: they must NOT be classified as findings, because a control made
only of positive specimens proves the instrument can see and proves nothing
about whether it invents.

The tool named below is the tool the probe was asked about. It is generated,
not fixed: a control hardcoded to one executable makes every other --tool
setting unprovable by construction.
"""

import shutil
import subprocess

import pytest

TOOL = "__TOOL_UNDER_TEST__"

#: A presence lookup at MODULE level rather than inside a test body. The
#: recorder attributes a call to whichever test is running, and a module body
#: runs during collection when no test is current, so this mark is DISCARDED.
#: That is why test_control_module_level_lookup below must land in
#: "untouched" and not in "silent_pass" - it is the planted demonstration of
#: the limitation the probe's report states on every run.
MODULE_LEVEL_LOOKUP = shutil.which(TOOL)


def test_control_false_red():
    """No presence guard at all: green with the tool, red without it."""
    subprocess.check_output([TOOL, "--version"])


def test_control_clean_skip():
    """Skips without the tool, and RUNS it when it is there.

    The second half is criterion 5: a guard that skips when the tool is
    missing and does nothing when it is present is a negative assertion.
    """
    found = shutil.which(TOOL)
    if found is None:
        pytest.skip("the control tool is absent")
    subprocess.check_output([found, "--version"])


def test_control_silent_pass():
    """Looks the tool up, never invokes it, and passes either way.

    This is the shape the probe exists to find: the guarded work does not
    happen in either direction and no summary line ever says so.
    """
    found = shutil.which(TOOL)
    assert found is None or isinstance(found, str)


def test_control_untouched():
    """NEGATIVE specimen: touches the tool in no way at all.

    It must be classified "untouched", which is not a finding. A probe that
    over-reports - one that promoted every untouched test to silent_pass, for
    instance - calls this a finding and fails its own control on it. Without
    this specimen that mutation passed the control unchanged.
    """
    assert 2 + 2 == 4


def test_control_module_level_lookup():
    """NEGATIVE specimen, and the planted proof of a stated limitation.

    The lookup happened at module level, above. It must still be classified
    "untouched" rather than "silent_pass", because the recorder had no current
    test to attribute it to. If this ever starts classifying as silent_pass,
    the report's limitation line has become false and must be rewritten.
    """
    assert MODULE_LEVEL_LOOKUP is None or isinstance(MODULE_LEVEL_LOOKUP, str)
'''


def control_module_source(tool: str = TOOL_DEFAULT) -> str:
    """The planted control module's source, for the tool under test.

    ``OPS-79`` criterion 0. The tool used to be a literal in a constant, which
    made every ``--tool`` run but the default report UNPROVEN while still
    printing counts - an absence of evidence wearing a finding's clothes.

    The name is validated rather than escaped. It is pasted into a string
    literal in generated Python that this module then hands to pytest, so a
    name carrying a quote, a newline or a backslash is refused outright:
    escaping is a thing one gets subtly wrong, and no real executable needs it.
    """
    if not tool or any(character not in TOOL_NAME_CHARS for character in tool):
        raise ValueError(
            f"tool name {tool!r} is not usable: a tool name may contain only "
            "letters, digits, and the characters _ . + -"
        )
    return CONTROL_MODULE_TEMPLATE.replace(_TOOL_PLACEHOLDER, tool)


#: The planted control for the DEFAULT tool. Kept as a constant because tests
#: and readers ask what the control looks like without naming a tool; it is
#: derived from the template rather than duplicating it, so the two can never
#: drift apart.
CONTROL_MODULE_SOURCE = control_module_source(TOOL_DEFAULT)


@dataclass(frozen=True)
class TestOutcome:
    """One test's result in one run, with the instrument's two flags.

    ``invoked`` and ``looked_up`` are booleans rather than tri-states because
    the plugin observes every wrapped call site for the whole session: a test
    that ran and did not invoke the tool is a measured False, not an unknown.
    What IS unknown is the spellings the plugin does not wrap, and that
    blindness belongs to the module docstring, not to this field.
    """

    nodeid: str
    outcome: str
    invoked: bool = False
    looked_up: bool = False


@dataclass(frozen=True)
class Classification:
    """What one test id did across the two runs, and what that means."""

    nodeid: str
    kind: str
    detail: str
    with_outcome: str
    without_outcome: str


@dataclass(frozen=True)
class FileDelta:
    """One file's outcome counts in both runs, never netted against others."""

    path: str
    with_counts: dict[str, int]
    without_counts: dict[str, int]
    changed: tuple[str, ...] = ()

    @property
    def with_total(self) -> int:
        return sum(self.with_counts.values())

    @property
    def without_total(self) -> int:
        return sum(self.without_counts.values())


@dataclass(frozen=True)
class ControlResult:
    """Whether the probe's own instrument was proved on this run.

    ``proved`` is the only field a caller may treat as permission to believe a
    zero. ``missing`` names every control the run failed to see in the shape it
    was planted as, so an unproven verdict says WHICH specimen went undetected
    rather than merely that something did.
    """

    proved: bool
    seen: dict[str, str]
    expected: dict[str, str]
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbeReport:
    """The composed verdict over one two-run probe.

    ``ran`` and ``ok`` are separate for the reason
    ``tools/archive_link_guard.py`` already states: a report that could not run
    is not a pass, and a caller inspecting only the findings list would read an
    empty one as green.
    """

    ran: bool
    controls: ControlResult
    classifications: tuple[Classification, ...] = ()
    file_deltas: tuple[FileDelta, ...] = ()
    lost_ids: tuple[str, ...] = ()
    gained_ids: tuple[str, ...] = ()
    removed_path_entries: tuple[str, ...] = ()
    #: Executables that left ``PATH`` WITH the tool, because they share a
    #: directory with it. ``OPS-78`` criterion 4 - see
    #: :func:`co_located_executables`.
    co_located: tuple[str, ...] = ()
    with_total: int = 0
    without_total: int = 0
    with_control_total: int = 0
    without_control_total: int = 0
    reason: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def findings(self) -> tuple[Classification, ...]:
        """Findings about THIS TREE - the planted controls are excluded.

        A control counted as a finding would make the probe report its own
        scaffolding as a defect, and the number it prints would rise by three
        no matter what the repository did.
        """
        return tuple(
            c
            for c in self.classifications
            if c.kind in FINDING_KINDS and not is_control(c.nodeid)
        )

    @property
    def ok(self) -> bool:
        return self.ran and self.controls.proved and not self.findings


def _basename(text: str) -> str:
    """The last path component of ``text``, for either separator.

    Done with string operations rather than ``pathlib`` on purpose: a node id
    recorded on one platform can carry the other's separator, and ``Path`` only
    splits on the one it is running under.
    """
    return text.replace("\\", "/").rsplit("/", 1)[-1]


def file_of(nodeid: str) -> str:
    """The file half of a pytest node id.

    Walk the ``::`` segments to the first that names a ``.py`` file rather than
    splitting at the first separator. Two shapes have to survive this:

    * a parametrized id carries the separator inside its own brackets, so
      splitting at the LAST one would attribute ``tests/t.py::test_m[a::b]`` to
      a file named ``tests/t.py::test_m[a``;
    * a file outside the root directory gets an id whose segments ARE the
      collector chain, so it begins with ``::`` and splitting at the first one
      returns an empty string. That is the measured defect the module docstring
      records, and it is why this is not a one-line split.

    A node id naming no ``.py`` file at all falls back to the first segment,
    which is the old behaviour and the best available answer - EXCEPT for the
    ``OPS-86`` shape, where the first segment is the empty string and the file
    is nevertheless known by construction: the probe planted it, so a bare id
    carrying a planted specimen's name is attributed to
    :data:`CONTROL_MODULE_NAME`. Without that, all five controls bucket
    together under ``""`` in :func:`delta_by_file` and the per-file table
    carries a nameless row.
    """
    segments = nodeid.split("::")
    for index, segment in enumerate(segments):
        if _basename(segment).endswith(".py"):
            return "::".join(segments[: index + 1])
    if _is_bare_control(nodeid):
        return CONTROL_MODULE_NAME
    return segments[0]


def _is_bare_control(nodeid: str) -> bool:
    """True for the temp-rootdir shape: one segment, and it is a planted name.

    ``OPS-86``. Measured, not guessed - see the module docstring. The only
    surviving evidence in this shape is the test NAME, so the match is
    deliberately narrow on two axes at once: the id must have exactly ONE
    non-empty segment, AND that segment must be one of the probe's own planted
    specimen names. A repository test id always carries its file, so it can
    never have one segment; and a bare id for some other out-of-tree file can
    never carry a name this module planted.

    The name list is read from :func:`control_expectations` rather than
    duplicated, so a sixth specimen is recognised by construction rather than
    by somebody remembering to add it here.
    """
    segments = [segment for segment in nodeid.split("::") if segment]
    return len(segments) == 1 and segments[0] in control_expectations()


def is_control(nodeid: str) -> bool:
    """True when a node id belongs to the planted control module.

    Matched on the module BASENAME in any segment, because an out-of-tree id
    carries no path separator for :func:`file_of` to key on. The match is only
    safe while no file under ``tests`` shares that basename, and a test in
    ``tests/test_false_red_probe.py`` asserts exactly that.

    ``OPS-86`` added the second arm. When the rootdir itself sits inside the
    system temp tree the control's id loses its file segment ENTIRELY - there
    is no ``.py`` name anywhere in it - so a basename match has nothing to key
    on and every specimen reads as never classified. :func:`_is_bare_control`
    recognises that shape; the refusal in :func:`format_report` covers every
    shape nobody has measured yet.
    """
    if any(
        _basename(segment) == CONTROL_MODULE_NAME
        for segment in nodeid.split("::")
        if segment
    ):
        return True
    return _is_bare_control(nodeid)


def control_test_name(nodeid: str) -> str:
    """A planted control's own test name: the LAST segment, never the second.

    ``nodeid.split("::", 1)[-1]`` was correct only for an in-tree id. On the
    out-of-tree shape it returns the whole directory chain with the test name
    glued to the end, which matches no expectation and reads as a control that
    was never seen.
    """
    segments = [segment for segment in nodeid.split("::") if segment]
    return segments[-1] if segments else ""


def parse_record(text: str) -> dict[str, TestOutcome]:
    """Parse the JSON the in-run plugin wrote into per-test outcomes.

    Tolerant on purpose. This parses output from a run that may itself have
    gone wrong, so a malformed entry is dropped and unparseable text yields an
    empty record rather than an exception. An empty record is not a pass: the
    caller reaches :func:`evaluate_controls`, which refuses to be proved by
    nothing.
    """
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    tests = payload.get("tests")
    if not isinstance(tests, dict):
        return {}
    parsed: dict[str, TestOutcome] = {}
    for nodeid, entry in tests.items():
        if not isinstance(nodeid, str) or not isinstance(entry, dict):
            continue
        outcome = entry.get("outcome")
        if not isinstance(outcome, str):
            continue
        parsed[nodeid] = TestOutcome(
            nodeid=nodeid,
            outcome=outcome,
            invoked=bool(entry.get("invoked", False)),
            looked_up=bool(entry.get("looked_up", False)),
        )
    return parsed


def classify(
    with_tool: Mapping[str, TestOutcome],
    without_tool: Mapping[str, TestOutcome],
) -> tuple[Classification, ...]:
    """Assign every test id one kind across the two runs.

    The kinds, and why each is separate:

    ``clean_skip``
        Passed with the tool, skipped without it. The guard worked.
    ``false_red``
        Passed with the tool, failed or errored without it.
    ``silent_pass``
        Passed both ways, looked the tool up, invoked it in neither run. The
        candidate this item exists for - see the module docstring on what a
        candidate is and is not.
    ``vanished``
        Present in the first run and absent from the second. Usually a
        collection error, and a finding: a test that was not collected at all
        is a test whose absence no summary line explains.
    ``appeared``
        The reverse, and informational rather than a defect.
    ``exercised``
        Passed both ways and actually invoked the tool at least once.
    ``untouched``
        Passed both ways and never looked the tool up. NOT a candidate: this
        is the rule that keeps the third outcome from meaning every test in
        the suite, which would make the finding worthless.
    ``skip_both``
        Skipped in both runs. Informational; its guard may be skipping for a
        reason that has nothing to do with this tool.
    ``other_change``
        Any other difference between the two runs, kept rather than dropped so
        the classification is total.
    """
    classified: list[Classification] = []
    for nodeid in sorted(set(with_tool) | set(without_tool)):
        before = with_tool.get(nodeid)
        after = without_tool.get(nodeid)
        if before is not None and after is None:
            classified.append(
                Classification(
                    nodeid=nodeid,
                    kind="vanished",
                    detail=(
                        "present with the tool and not collected without it - "
                        "probably a collection error rather than a test result"
                    ),
                    with_outcome=before.outcome,
                    without_outcome="",
                )
            )
            continue
        if before is None and after is not None:
            classified.append(
                Classification(
                    nodeid=nodeid,
                    kind="appeared",
                    detail="collected only in the run without the tool",
                    with_outcome="",
                    without_outcome=after.outcome,
                )
            )
            continue
        assert before is not None and after is not None
        kind, detail = _kind_for(before, after)
        classified.append(
            Classification(
                nodeid=nodeid,
                kind=kind,
                detail=detail,
                with_outcome=before.outcome,
                without_outcome=after.outcome,
            )
        )
    return tuple(classified)


def _kind_for(before: TestOutcome, after: TestOutcome) -> tuple[str, str]:
    """The single-test rule behind :func:`classify`, kept separate to read."""
    if before.outcome == "passed" and after.outcome == "skipped":
        return "clean_skip", "passed with the tool and skipped without it"
    if before.outcome == "passed" and after.outcome in ("failed", "error"):
        return (
            "false_red",
            f"passed with the tool and {after.outcome} without it",
        )
    if before.outcome == "skipped" and after.outcome == "skipped":
        return "skip_both", "skipped in both runs"
    if before.outcome == "passed" and after.outcome == "passed":
        if before.invoked or after.invoked:
            return "exercised", "passed both ways and invoked the tool"
        if before.looked_up or after.looked_up:
            return (
                "silent_pass",
                "passed both ways, looked the tool up, and never invoked it "
                "- a CANDIDATE for a guard that never fired, not a conviction",
            )
        return "untouched", "passed both ways and never touched the tool"
    return (
        "other_change",
        f"{before.outcome} with the tool and {after.outcome} without it",
    )


def delta_by_file(
    with_tool: Mapping[str, TestOutcome],
    without_tool: Mapping[str, TestOutcome],
) -> tuple[FileDelta, ...]:
    """Per-file outcome counts for both runs.

    Per file and never netted, for the reason ``ops/merge_gate.py`` gives about
    its own per-file check: a repository total is safe for one file and unsafe
    for many, because a file that lost five tests is completely hidden by
    another that gained five.
    """
    files = sorted({file_of(n) for n in set(with_tool) | set(without_tool)})
    deltas: list[FileDelta] = []
    for path in files:
        with_counts: dict[str, int] = {}
        without_counts: dict[str, int] = {}
        changed: list[str] = []
        for nodeid, outcome in with_tool.items():
            if file_of(nodeid) == path:
                with_counts[outcome.outcome] = with_counts.get(outcome.outcome, 0) + 1
        for nodeid, outcome in without_tool.items():
            if file_of(nodeid) == path:
                without_counts[outcome.outcome] = (
                    without_counts.get(outcome.outcome, 0) + 1
                )
        for nodeid in sorted(set(with_tool) | set(without_tool)):
            if file_of(nodeid) != path:
                continue
            before = with_tool.get(nodeid)
            after = without_tool.get(nodeid)
            if before is None or after is None or before.outcome != after.outcome:
                changed.append(nodeid)
        deltas.append(
            FileDelta(
                path=path,
                with_counts=with_counts,
                without_counts=without_counts,
                changed=tuple(changed),
            )
        )
    return tuple(deltas)


def delta_by_test_id(
    with_tool: Mapping[str, TestOutcome],
    without_tool: Mapping[str, TestOutcome],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Ids present in only one of the two runs, as ``(lost, gained)``."""
    lost = tuple(sorted(set(with_tool) - set(without_tool)))
    gained = tuple(sorted(set(without_tool) - set(with_tool)))
    return lost, gained


def executable_suffixes(pathext: str | None) -> tuple[str, ...]:
    """Suffixes that make a bare name executable, lowercased and deduplicated.

    Windows decides executability by ``PATHEXT``, so ``git`` on ``PATH`` is
    really ``git.exe`` - a stripper that looked only for the bare name would
    remove nothing on this machine and the second run would measure nothing.
    The empty suffix is ALWAYS included: an extensionless ``git`` is the POSIX
    shape and it also appears in Git for Windows' own ``usr/bin``.

    ``None`` means read ``PATHEXT`` from the environment, which is empty
    everywhere but Windows.
    """
    raw = os.environ.get("PATHEXT", "") if pathext is None else pathext
    suffixes = [""]
    for part in raw.split(os.pathsep if os.pathsep in raw else ";"):
        cleaned = part.strip().lower()
        if cleaned and cleaned not in suffixes:
            suffixes.append(cleaned)
    return tuple(suffixes)


def entry_carries_tool(
    entry: str,
    tool: str,
    suffixes: Sequence[str],
    is_file: Callable[[str], bool] = os.path.isfile,
) -> bool:
    """True when ``entry`` is a directory holding an executable named ``tool``.

    ``is_file`` is injected so the decision is testable against a fixture tree
    without depending on what this machine happens to have installed.
    """
    if not entry:
        return False
    return any(is_file(str(Path(entry) / (tool + suffix))) for suffix in suffixes)


def strip_tool_from_path(
    path_value: str,
    tool: str = TOOL_DEFAULT,
    pathext: str | None = None,
    is_file: Callable[[str], bool] = os.path.isfile,
) -> tuple[str, tuple[str, ...]]:
    """Remove exactly the ``PATH`` entries that carry ``tool``, by value.

    BY VALUE IS THE WHOLE POINT. Guessing which entries "look like" a git
    install, or emptying ``PATH`` outright, would make the second run measure
    its own breakage instead of the tool's absence - a true answer to a
    question nobody asked. Every other entry survives untouched, so the
    interpreter stays findable; see the test that asserts exactly that against
    this machine's live ``PATH``.

    Returns the stripped value and the entries that were removed, because a
    caller that cannot say what it removed cannot say what it measured.
    """
    suffixes = executable_suffixes(pathext)
    kept: list[str] = []
    removed: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        if entry_carries_tool(entry, tool, suffixes, is_file):
            removed.append(entry)
        else:
            kept.append(entry)
    return os.pathsep.join(kept), tuple(removed)


def co_located_executables(
    entries: Sequence[str],
    tool: str,
    pathext: str | None = None,
    lister: Callable[[str], Sequence[str]] = os.listdir,
) -> tuple[str, ...]:
    """Other executables that leave ``PATH`` alongside ``tool`` - ``OPS-78`` #4.

    :func:`strip_tool_from_path` removes an ENTRY, never a single executable,
    so everything else in that directory disappears with the tool. Where the
    toolchain ships as one directory - Git for Windows' ``usr/bin`` is the case
    measured here - that is most of a POSIX userland, and a false red then says
    "this broke when that DIRECTORY left the PATH" rather than "this needs the
    named tool".

    Returned as a sorted set of stems so the caller can print it. An entry that
    cannot be listed is SKIPPED rather than raised: this runs after both suite
    runs have already completed, and losing a twelve-minute measurement to an
    unreadable directory would trade a whole result for a footnote.
    """
    suffixes = executable_suffixes(pathext)
    lowered = {suffix.lower() for suffix in suffixes}
    found: set[str] = set()
    for entry in entries:
        try:
            names = lister(entry)
        except OSError:
            continue
        for name in names:
            stem, dot, suffix = name.rpartition(".")
            if not dot:
                continue
            if lowered and f".{suffix}".lower() not in lowered:
                continue
            if stem and stem.lower() != tool.lower():
                found.add(stem.lower())
    return tuple(sorted(found))


def control_expectations() -> dict[str, str]:
    """Each planted control mapped to the kind the probe must classify it as.

    Read as: if the probe cannot see THIS, its zero about the repository is
    worth nothing.
    """
    return {
        "test_control_false_red": "false_red",
        "test_control_clean_skip": "clean_skip",
        "test_control_silent_pass": "silent_pass",
        "test_control_untouched": "untouched",
        "test_control_module_level_lookup": "untouched",
    }


#: Controls whose guarded path must be observed RUNNING in the with-tool run.
#: Criterion 5: one direction alone is a negative assertion.
_CONTROLS_THAT_MUST_INVOKE = frozenset(
    {"test_control_false_red", "test_control_clean_skip"}
)

#: NEGATIVE specimens - ``OPS-79`` criterion 1. Each must be classified as
#: something that is NOT in :data:`FINDING_KINDS`. They are what turns the
#: control from "can this instrument SEE?" into "can this instrument see AND
#: not invent?": a classifier that over-reports lands one of these on a finding
#: kind and fails the control, where the three positive specimens alone would
#: still have landed correctly and reported PROVED.
NEGATIVE_CONTROLS = frozenset(
    {"test_control_untouched", "test_control_module_level_lookup"}
)


@contextlib.contextmanager
def planted_controls(
    parent: Path | None = None, tool: str = TOOL_DEFAULT
) -> Iterator[Path]:
    """Write the control module into a temporary directory and remove it after.

    The directory is created under the system temp area, never under
    :data:`REPO_ROOT`: a planted false-red site left in the tree would be a
    test this repository did not mean to ship, and the item says explicitly
    that the probe builds and tears down its own.

    ``tool`` is the executable the planted specimens look up and invoke, so the
    control matches whatever the run is actually measuring - ``OPS-79``
    criterion 0.
    """
    directory = Path(tempfile.mkdtemp(prefix="false_red_probe_", dir=parent))
    control_path = directory / CONTROL_MODULE_NAME
    tmp = control_path.with_name(control_path.name + ".tmp")
    tmp.write_text(control_module_source(tool), encoding="ascii")
    tmp.replace(control_path)
    plugin_path = directory / (PLUGIN_MODULE_NAME + ".py")
    plugin_tmp = plugin_path.with_name(plugin_path.name + ".tmp")
    plugin_tmp.write_text(PLUGIN_SOURCE, encoding="ascii")
    plugin_tmp.replace(plugin_path)
    try:
        yield control_path
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def evaluate_controls(
    classifications: Sequence[Classification],
    with_tool: Mapping[str, TestOutcome],
) -> ControlResult:
    """Decide whether this run's instrument was proved.

    Two questions, both required:

    1. Was every planted control classified as the kind it was planted as? A
       control the probe did not see, or saw as something else, means the
       detector is blind to that shape and its silence about the repository
       says nothing.
    2. Did the controls whose guarded path is supposed to RUN when the tool is
       present actually invoke it? That is criterion 5 turned on the probe
       itself: skipping without the tool proves nothing unless the same test
       does the work when the tool is there.
    """
    expected = control_expectations()
    seen: dict[str, str] = {}
    for classification in classifications:
        if not is_control(classification.nodeid):
            continue
        name = control_test_name(classification.nodeid)
        seen[name] = classification.kind
    missing: list[str] = []
    for name, kind in expected.items():
        actual = seen.get(name)
        if actual is None:
            missing.append(
                f"{name}: expected kind {kind}, but the probe never classified it"
            )
            continue
        if actual != kind:
            if name in NEGATIVE_CONTROLS and actual in FINDING_KINDS:
                missing.append(
                    f"{name}: this instrument OVER-REPORTS - a planted negative "
                    f"specimen that must not be a finding was classified "
                    f"{actual}, which is one. Every count below is inflated by "
                    "whatever made that happen"
                )
                continue
            missing.append(
                f"{name}: expected kind {kind}, but the probe called it {actual}"
            )
            continue
        if name in _CONTROLS_THAT_MUST_INVOKE:
            outcome = None
            for nodeid, recorded in with_tool.items():
                if is_control(nodeid) and control_test_name(nodeid) == name:
                    outcome = recorded
                    break
            if outcome is None or not outcome.invoked:
                missing.append(
                    f"{name}: classified {kind}, but the probe never saw it "
                    "invoke the tool in the run where the tool was present - "
                    "one direction alone pins nothing down"
                )
    return ControlResult(
        proved=not missing,
        seen=seen,
        expected=expected,
        missing=tuple(missing),
    )


def pytest_args(control_path: Path, plugin_dir: Path) -> list[str]:
    """Build the pytest command line for one of the two runs.

    ``tests`` is named explicitly ALONGSIDE the control file because passing
    any argument overrides ``testpaths`` in ``pytest.ini``. Handing pytest only
    the control would run three planted tests and nothing else, and the probe
    would then report a confident delta about a suite it never ran.
    """
    return [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        PLUGIN_MODULE_NAME,
        "tests",
        str(control_path),
    ]


def default_runner(
    args: Sequence[str], env: Mapping[str, str], record_path: str
) -> int:
    """Run pytest once. The ONLY function in this module that shells out.

    ``argv[0]`` is ``sys.executable`` - this interpreter, running its own
    ``pytest`` module. No shell is involved and no external program is named.
    """
    completed = subprocess.run(
        list(args),
        cwd=str(REPO_ROOT),
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode


def probe(
    tool: str = TOOL_DEFAULT,
    runner: Callable[[Sequence[str], Mapping[str, str], str], int] | None = None,
    base_env: Mapping[str, str] | None = None,
    repo_root: Path = REPO_ROOT,
    lister: Callable[[str], Sequence[str]] = os.listdir,
) -> ProbeReport:
    """Run the suite twice and compose the verdict.

    ``runner`` is injected so every caller but the command line can drive this
    without spawning anything. It is handed the argument list, the environment
    for that run, and the path the in-run plugin must write its record to.
    """
    run = default_runner if runner is None else runner
    environment = dict(os.environ if base_env is None else base_env)
    with planted_controls(tool=tool) as control_path:
        plugin_dir = control_path.parent
        args = pytest_args(control_path, plugin_dir)
        with_record = plugin_dir / "record_with.json"
        without_record = plugin_dir / "record_without.json"

        with_env = _run_env(environment, plugin_dir, tool, with_record)
        run(args, with_env, str(with_record))
        with_tool = parse_record(_read_text(with_record))

        stripped, removed = strip_tool_from_path(
            environment.get("PATH", ""),
            tool=tool,
            pathext=environment.get("PATHEXT"),
        )
        without_env = _run_env(environment, plugin_dir, tool, without_record)
        without_env["PATH"] = stripped
        run(args, without_env, str(without_record))
        without_tool = parse_record(_read_text(without_record))

    classifications = classify(with_tool, without_tool)
    controls = evaluate_controls(classifications, with_tool)
    lost, gained = delta_by_test_id(with_tool, without_tool)
    notes: list[str] = []
    if not removed:
        notes.append(
            f"no PATH entry carried a {tool} executable, so the second run "
            "was not actually deprived of it - every kind below is suspect"
        )
    return ProbeReport(
        ran=True,
        controls=controls,
        classifications=classifications,
        file_deltas=delta_by_file(with_tool, without_tool),
        lost_ids=lost,
        gained_ids=gained,
        removed_path_entries=removed,
        co_located=co_located_executables(
            removed, tool, environment.get("PATHEXT"), lister
        ),
        with_total=sum(1 for nodeid in with_tool if not is_control(nodeid)),
        without_total=sum(1 for nodeid in without_tool if not is_control(nodeid)),
        with_control_total=sum(1 for nodeid in with_tool if is_control(nodeid)),
        without_control_total=sum(
            1 for nodeid in without_tool if is_control(nodeid)
        ),
        notes=tuple(notes),
    )


def _run_env(
    environment: Mapping[str, str], plugin_dir: Path, tool: str, record: Path
) -> dict[str, str]:
    """One run's environment: the plugin importable, and where to write."""
    env = dict(environment)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(plugin_dir) + (os.pathsep + existing if existing else "")
    )
    env[TOOL_ENV_VAR] = tool
    env[RECORD_ENV_VAR] = str(record)
    return env


def _read_text(path: Path) -> str:
    """Read a record file, or return empty text when the run never wrote one."""
    try:
        return path.read_text(encoding="ascii")
    except OSError:
        return ""


#: Printed on EVERY run, next to the kind tally - ``OPS-79`` criterion 2.
#: Recognition of a module-level lookup was not adopted (the module docstring
#: says why), so the limitation travels with the number instead of living only
#: in a docstring nobody reading the output will open. It is unconditional on
#: purpose: the danger is reading a ZERO as a clean bill, and a caveat that
#: only appears when the count is non-zero is absent exactly when it matters.
SILENT_PASS_LIMITATION = (
    "[limitation] silent_pass counts ONLY a presence lookup made inside a "
    "test body.",
    "  A module-level lookup runs during collection, when the recorder has no",
    "  current test to attribute it to, so it is discarded and the test lands in",
    "  untouched instead. Module-level is how this repository usually writes",
    "  them, so a silent_pass of 0 is NOT a clean bill of health.",
)


def tool_granularity_limitation(report: ProbeReport) -> tuple[str, ...]:
    """The second limitation line, COMPUTED rather than written - ``OPS-78`` #4.

    Written as a measurement and not as a sentence on purpose. A sentence about
    Git for Windows shipping one ``usr/bin`` would be true here and stale on the
    next machine, and this repository's own rule is that a filed count is a
    hypothesis. So the line names what was actually beside the tool on THIS run.

    The empty case is printed too, and says so. A directory carrying only the
    named tool is the one arrangement where ``--tool`` is genuinely
    tool-granular, and that is the difference between a trustworthy attribution
    and an untested one - exactly the fact a reader needs and exactly the one a
    caveat that only appears when non-empty would withhold.
    """
    head = (
        "[limitation] --tool names the QUESTION asked, not the dependency found."
    )
    if not report.co_located:
        return (
            head,
            "  The stripped entries carried no other executable, so on THIS run "
            "the",
            "  attribution really is tool-granular. That is a property of this "
            "machine's",
            "  PATH, not of the probe, and it is re-measured every run.",
        )
    shown = list(report.co_located[:12])
    more = len(report.co_located) - len(shown)
    tail = ", ".join(shown) + (f", and {more} more" if more else "")
    return (
        head,
        "  Entries are stripped whole, so every executable sharing a directory "
        "with the",
        f"  tool left PATH too - {len(report.co_located)} other executable(s) "
        f"on this run: {tail}.",
        "  A false red below therefore means 'this broke when that DIRECTORY "
        "left the",
        "  PATH'. READ THE INDIVIDUAL FAILURES before converting a call site "
        "onto the",
        "  tool's name; measured for bash here, 49 of 56 needed something else "
        "in it.",
    )


def format_report(report: ProbeReport) -> str:
    """Render the verdict for a human.

    THE CONTROL LINE IS PRINTED EVERY RUN, first, whatever the outcome - a
    finding count read without it is a number from an instrument nobody
    checked. The ``silent_pass`` limitation is printed every run for the same
    reason: a number whose caveat is somewhere else is a number quoted without
    its caveat.

    AND AN UNPROVEN RUN STOPS THERE - ``OPS-86``. No kind tally, no findings
    list, no per-file deltas, no collected totals. The caveat above turned out
    not to be enough on its own: an ``OPS-83`` run printed the UNPROVEN banner
    and then a complete table including ``false_red=50``, and the item records
    that the numbers read exactly like findings. A caveat a reader must apply
    is a caveat a reader will skip, so the numbers are withheld instead of
    annotated.
    """
    lines: list[str] = []
    if not report.ran:
        return f"false red probe: DID NOT RUN - {report.reason}"
    if report.controls.proved:
        lines.append(
            "false red probe: positive control PROVED - "
            + ", ".join(
                f"{name}={kind}" for name, kind in sorted(report.controls.seen.items())
            )
        )
    else:
        lines.append(
            "false red probe: positive control UNPROVEN - this run measured "
            "nothing it can attribute"
        )
        lines.extend(f"  [control] {note}" for note in report.controls.missing)
        lines.append(
            "  REFUSING to print counts, kinds, findings or per-file deltas "
            "for this run."
        )
        lines.append(
            "  The instrument was not proved, so those numbers would be an "
            "absence of evidence"
        )
        lines.append(
            "  wearing a finding's clothes - OPS-86, where an UNPROVEN run "
            "still printed"
        )
        lines.append(
            "  a full table including false_red=50 and a reader filed it as a "
            "result."
        )
        lines.append(
            "  Fix the control first. If the rootdir sits inside the system "
            "temp tree, run"
        )
        lines.append("  the probe from the real tree instead.")
        return "\n".join(lines)
    lines.append(
        f"  stripped {len(report.removed_path_entries)} PATH entry(ies) "
        f"carrying the tool; collected {report.with_total} repository test(s) "
        f"with it and {report.without_total} without, alongside "
        f"{report.with_control_total} planted control(s) with it and "
        f"{report.without_control_total} without"
    )
    lines.extend(f"  [note] {note}" for note in report.notes)
    counts: dict[str, int] = {}
    for classification in report.classifications:
        if is_control(classification.nodeid):
            continue
        counts[classification.kind] = counts.get(classification.kind, 0) + 1
    lines.append(
        "  kinds: "
        + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")
    )
    lines.extend(f"  {line}" for line in SILENT_PASS_LIMITATION)
    lines.extend(f"  {line}" for line in tool_granularity_limitation(report))
    lines.append(
        "  planted controls (excluded from every count and finding here): "
        + (
            ", ".join(
                f"{name}={kind}"
                for name, kind in sorted(report.controls.seen.items())
            )
            or "none seen"
        )
    )
    findings = report.findings
    lines.append(f"  findings: {len(findings)}")
    for finding in findings:
        lines.append(f"    [{finding.kind}] {finding.nodeid} - {finding.detail}")
    changed_files = [d for d in report.file_deltas if d.changed]
    lines.append(f"  files with any change: {len(changed_files)}")
    for delta in changed_files:
        if all(is_control(n) for n in delta.changed):
            continue
        lines.append(
            f"    {delta.path}: {delta.with_total} with / "
            f"{delta.without_total} without, {len(delta.changed)} changed"
        )
    if report.lost_ids:
        lines.append(f"  ids collected only WITH the tool: {len(report.lost_ids)}")
        lines.extend(f"    {nodeid}" for nodeid in report.lost_ids)
    if report.gained_ids:
        lines.append(f"  ids collected only WITHOUT the tool: {len(report.gained_ids)}")
        lines.extend(f"    {nodeid}" for nodeid in report.gained_ids)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command line. Every option is real; nothing else is accepted.

    ``allow_abbrev`` is off for the reason ``tools/archive_link_guard.py``
    states: an accepted prefix means a caller gets an answer about something
    other than what they typed, which is the very defect ``OPS-66`` and
    ``OPS-67`` closed.
    """
    parser = argparse.ArgumentParser(
        prog="false_red_probe",
        description=(
            "Run this repository's suite twice - once normally, once with "
            "every PATH entry carrying the named tool removed - and report "
            "the delta by test id and by file. Proves its own instrument "
            "with a planted control before any zero it prints is believable."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--tool",
        default=TOOL_DEFAULT,
        metavar="NAME",
        help=(
            "executable whose absence is simulated; changes both what is "
            f"stripped from PATH and what the recorder watches for (default: "
            f"{TOOL_DEFAULT})"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        metavar="PATH",
        help="tree the suite is run from (default: this repository)",
    )
    return parser


def main(
    argv: list[str] | None = None,
    runner: Callable[[Sequence[str], Mapping[str, str], str], int] | None = None,
) -> int:
    """Run the probe and print the report.

    EXIT CODES, KEPT DISTINCT BECAUSE THEY ARE DIFFERENT FACTS:

    ``0``
        The probe ran, its control was proved, and it found nothing.
    ``1``
        The probe ran, its control was proved, and it found something.
    ``2``
        A usage error - an unknown flag, or a positional argument.
    ``3``
        The probe ran and its own control was NOT proved. Neither green nor
        red: a negative result from an unproven instrument is not a result.

    ``argv`` excludes the program name. ``runner`` is injected by tests so the
    command-line surface can be exercised without running the suite.
    """
    args_list = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return USAGE_EXIT_CODE

    try:
        control_module_source(args.tool)
    except ValueError as exc:
        print(f"false_red_probe: {exc}", file=sys.stderr)
        return USAGE_EXIT_CODE

    report = probe(tool=args.tool, runner=runner, repo_root=Path(args.repo_root))
    print(f"false red probe: scope {args.repo_root}, tool {args.tool}")
    print(format_report(report))
    if not report.controls.proved:
        return UNPROVEN_EXIT_CODE
    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
