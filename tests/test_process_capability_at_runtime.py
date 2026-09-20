"""A RUNTIME counterpart to the SEVERITY-1 guards over THE HARD BOUNDARY.

WHY THIS FILE EXISTS, AND WHY IT IS A SEPARATE MODULE. A static-guard census
run over this repository on 2026-09-20 found four guards whose subject is THE
HARD BOUNDARY - the rule whose stake is a permanent ban on the operator's real
account - and reported that NONE of them has a runtime counterpart:

1. ``tests/test_process_capability.py`` - a capability ALLOWLIST, but its
   SCOPE is decided by :func:`test_process_capability.names_a_process_handle_api`,
   which is a DENYLIST OF API NAMES. A new module spelling
   ``getattr(ctypes.WinDLL("kernel32"), "Open" + "Process")`` names no member
   of that denylist anywhere in its AST, so it never enters SCOPE and is never
   scanned at all. That is the worst of the four: the other three can be
   evaded, this one need not be.
2. ``tests/test_loop_watch.py::test_watch_exposes_no_termination_path`` -
   collects ``Call.func`` as a ``Name`` or an ``Attribute``.
   ``getattr(h, "Terminate" + "Process")()`` makes ``Call.func`` a ``Call``,
   which is neither, so nothing is recorded.
3. ``tests/test_loop_guard.py::test_guard_exposes_no_termination_path`` - same
   shape, and ``getattr(os, "kil" + "l")(pid, 9)`` additionally voids its
   literal-zero-signal arm, because that arm only inspects calls it collected
   a name for.
4. ``tests/test_loop_watch.py::test_no_in_scope_module_asks_for_a_wider_process_right``
   - a mask computed at run time (``_QUERY_LIMITED | (1 << 0)``) is not a
   structure a text check can evaluate, and it inherits 1's scope hole.

All four lose to the same move, and it is not hypothetical: on 2026-09-20 an
adversarial pass defeated this repository's three responder send-guards at once
with two lines that assembled a module name and an attribute name at run time,
and the suite stayed green. That is ``OPS-68`` and ledger ``LL-0278``.

A STATIC CHECK IS A CLAIM ABOUT SOURCE TEXT. This file makes a claim about a
RUN instead, and the two are complementary - neither replaces the other. The
architecture is the one already in this tree twice: ``tests/conftest.py``
(lines 117-133) plus :func:`ops.docguards.coverage_gap`, which is ``OPS-31``
and predates the responder arm, and
``tests/test_responder.py::TestTheRunnerCannotSendAtRUNTIME``, which is
``OPS-68``.

WHICH AUDIT EVENTS ACTUALLY FIRE, MEASURED RATHER THAN ASSUMED. The responder
slice found that ``importlib.import_module`` raises NO ``import`` event, which
would have made a guard built on that event vacuous, so nothing below is taken
on the documentation's word. Probed on this machine 2026-09-20, CPython 3.14,
by resolving and calling ``OpenProcess`` through an assembled name:

* ``ctypes.dlopen`` fires with ``('kernel32',)`` - the LIBRARY name, once per
  ``WinDLL`` construction.
* ``ctypes.dlsym`` fires with ``(<WinDLL ...>, 'OpenProcess')`` - the REAL
  symbol name, after the string has been assembled. ``"Open" + "Process"`` is
  a ``BinOp`` in the source and the literal ``OpenProcess`` appears nowhere in
  the text, yet the event carries it, because the hook sits below name
  resolution and the loader must be handed the finished name to do its job.
  This single measurement is what makes defeats 1, 2 and the ctypes half of 3
  visible.
* ``ctypes.call_function`` fires with ``(func_pointer, argument_tuple)`` -
  observed as ``(<pointer>, (4096, False, <pid>))``. 4096 is 0x1000, the ACCESS
  MASK, so the right an ``OpenProcess`` really asked for is readable at run
  time however it was computed. That is defeat 4.

  **The pointer and the pid are deliberately not written out here**, and the
  reason is a guard doing its job rather than an abundance of caution. The
  first draft of this docstring pasted the observed tuple verbatim and
  ``tests/test_no_pii.py`` refused it: a 15-digit run-time address matches
  ``LONG_ID``. It is not an operator identifier, but the guard cannot know that
  from the digits, and the honest answer to that red is to remove the number
  rather than to teach the redactor an exception. A pointer from one run is
  unreproducible anyway, so the literal carried no information that the shape
  does not.
* ``os.kill`` fires with ``(pid, signal)`` - the signal as a VALUE, so an
  assembled ``getattr(os, "kil" + "l")(pid, 9)`` is caught by its argument
  rather than by its spelling. That is the other half of defeat 3.
* ``import`` fires for an ``import`` statement, and is the cheap extra here
  rather than the load-bearing event, for the reason the responder file
  records.

A function POINTER is not a name, so the mask check correlates the two: the
probe resolves the vetted kernel32 entry points to addresses BEFORE installing
the hook, and matches ``ctypes.call_function``'s first argument against that
map. ``GetProcAddress`` answers with the same address for the same export in
the same process, so the correlation is exact rather than order-based.

NOTHING HERE TOUCHES A GAME PROCESS, AND THAT IS ENFORCED, NOT PROMISED. The
probe runs the repository's OWN liveness code against the probe interpreter's
OWN pid - a process this file created and nothing else can be. On top of that
the hook RAISES on a dangerous operation, and a raising audit hook ABORTS the
operation that raised it, so the event is recorded and the call never happens.
Measured 2026-09-20: ``os.kill(getpid(), 9)`` and an ``OpenProcess`` asking for
``0x1000 | 0x0001`` were both blocked, both recorded, and the interpreter
carried on and exited 0. That is what lets this file demonstrate a termination
spelling without any process being terminated.

WHAT THIS FILE IS BLIND TO. Stated in the artifact, because a caveat that lives
in a chat log is a lie in the artifact.

* **It is a claim about the runs it makes.** A branch no entry point below
  reaches is untested here, exactly as the responder arm's own docstring says
  of itself. The static allowlist is what covers the unreached branches, and it
  is why that file is not weakened by this one.
* **The NATIVE tier is what :data:`NATIVE_REACH_ROOTS` covers, not the SPAWN
  tier.** A module that imports ``subprocess`` can run ``taskkill`` without any
  ctypes at all. Fourteen published modules outside ``tests/`` import
  ``subprocess`` and are NOT pulled into scope here. That is a real, declared
  hole and it is not closed by this file.
* **The blocking hook protects THIS probe, not the repository.** It is a
  property of the harness, not a property of the shipped code.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import _tracked  # noqa: E402  (sits beside this file in tests/)
from test_process_capability import (  # noqa: E402  (sits beside this file in tests/)
    ALLOWED_LIBRARIES,
    ALLOWED_WIN32_FUNCTIONS,
    SCOPE,
    names_a_process_handle_api,
)

WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "the ctypes audit events this file measures are raised by the Windows "
        "probes in the modules under test; on any other platform those probes "
        "return a cannot-tell answer without loading a library, so a run here "
        "would pass while observing nothing"
    ),
)

# ---------------------------------------------------------------------------
# THE POSITIVE SCOPE. This is the root fix for census hole 1.
#
# ``test_process_capability.SCOPE`` is DERIVED, which was already an
# improvement on the hand-typed tuple it replaced, but it is derived by asking
# whether a module NAMES one of ten process-handle APIs. That question is a
# denylist wearing a derivation's clothes: a module that assembles the name is
# not refused, it is never asked about. Widening the name list one string at a
# time is this repository's ``.gl`` defect for the third time.
#
# So the question below is turned around. Not "does this module name a
# dangerous API" - which a module decides by how it spells things - but "can
# this module reach native code AT ALL", which a module decides by what it
# IMPORTS, and an import is a statement the interpreter must be handed in
# plain text before anything else can happen.
#
# The consequences of turning it around:
#
# - Every published ``.py`` outside ``tests/`` is a candidate. A file added
#   tomorrow is IN by default.
# - It leaves only if it is provably inert - it imports nothing that can reach
#   native code or manufacture an import - or if a human writes it into
#   :data:`NATIVE_SCOPE_EXCLUSIONS` WITH A REASON.
# - An assembled API name no longer helps: ``getattr(ctypes.WinDLL("kernel32"),
#   "Open" + "Process")`` still needs ``import ctypes``, and that import is what
#   puts the module in scope.
# ---------------------------------------------------------------------------

#: Import roots that grant a module reach into native code, or the ability to
#: manufacture an import and thereby reach one of the others without naming it.
#:
#: This IS an enumerated set, and saying otherwise would be the mis-stated
#: coverage ``tests/test_process_capability.py`` calls THE SECOND BUG. What
#: makes it a better enumeration than a list of API spellings: an API name is
#: chosen by the author and can be computed, while an import root must appear
#: as text in an ``import`` statement or arrive through machinery that is
#: itself in this set. ``importlib``, ``runpy``, ``eval``, ``exec`` and
#: ``__import__`` are here for exactly that closure reason and not because
#: anything in this repository uses them.
NATIVE_REACH_ROOTS = frozenset(
    {
        "_ctypes",
        "cffi",
        "ctypes",
        "importlib",
        "msvcrt",
        "multiprocessing",
        "psutil",
        "pywintypes",
        "runpy",
        "win32api",
        "win32con",
        "win32event",
        "win32gui",
        "win32process",
        "winreg",
    }
)

#: Builtin names that manufacture an import or a code object at run time. A
#: module that reaches one of these is not provably inert whatever it imports.
NATIVE_REACH_BUILTINS = frozenset({"__import__", "compile", "eval", "exec"})

#: Path prefixes the derivation does not walk, and why. The test tree is
#: excluded for the same reason ``test_process_capability.py`` excludes it -
#: these files quote every forbidden spelling as fixture source, and this very
#: module resolves ``OpenProcess`` in its own probe script.
DERIVATION_EXCLUDED_PREFIXES = ("tests/",)

#: Modules that CAN reach native code and are deliberately not put through the
#: capability allowlist, each with the reason a human gave. The value is read
#: by a test and must be non-empty: an exclusion with no reason is how a scope
#: quietly narrows, which is the failure this whole file exists against.
NATIVE_SCOPE_EXCLUSIONS: dict[str, str] = {
    "overlay/window.py": (
        "Reaches ctypes for user32 to make OUR OWN always-on-top window - the "
        "one thing CLAUDE.md's HARD BOUNDARY permits by name, an ordinary "
        "Windows window rather than an injected overlay. It acquires no handle "
        "to any other process: the runtime arm below would see a ctypes.dlopen "
        "naming a library outside ALLOWED_LIBRARIES if it ever did, but there "
        "is no entry point here that can be exercised without creating a real "
        "window, so this is a written exclusion rather than a measurement. "
        "Putting it through the capability allowlist instead would require "
        "widening ALLOWED_LIBRARIES to user32, which is a real loosening of a "
        "SEVERITY-1 guard for a module that is not the reason that guard "
        "exists."
    ),
}


def import_roots(source: str) -> set[str]:
    """Return the top-level module names ``source`` imports, anywhere.

    Relative imports are reported with their leading dots stripped and are
    first-party by construction, so they cannot name a native root.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Refuse what you cannot read: an unparsable module is treated as
        # reaching everything, so it lands in scope rather than slipping out.
        return set(NATIVE_REACH_ROOTS)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def reaches_native_code(source: str) -> bool:
    """True when ``source`` can reach native code or manufacture an import.

    Pure over its input, deliberately and for the reason
    ``test_process_capability.derive_scope`` gives: pinning the derivation then
    needs nothing but a list of strings, rather than a capability-bearing file
    planted in the tree this guard audits.
    """
    if import_roots(source) & NATIVE_REACH_ROOTS:
        return True
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True
    return any(
        isinstance(node, ast.Name) and node.id in NATIVE_REACH_BUILTINS
        for node in ast.walk(tree)
    )


def _published_sources() -> list[tuple[str, str]]:
    """Every published ``.py`` outside the test tree, as ``(relative, source)``."""
    found: list[tuple[str, str]] = []
    for path in _tracked.iter_authored_files(REPO_ROOT):
        if path.suffix != ".py":
            continue
        try:
            relative = path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if relative.startswith(DERIVATION_EXCLUDED_PREFIXES):
            continue
        try:
            found.append((relative, path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return found


def native_reach_universe() -> tuple[str, ...]:
    """Every published module outside ``tests/`` that can reach native code."""
    return tuple(
        sorted(relative for relative, source in _published_sources() if reaches_native_code(source))
    )


# ---------------------------------------------------------------------------
# The runtime probe.
# ---------------------------------------------------------------------------

#: Entry points that make a module's process probe actually RUN. A module in
#: :data:`SCOPE` with no entry point here is a module this file cannot make a
#: claim about, and :func:`test_every_scope_module_has_a_runtime_entry_point`
#: reddens on one rather than letting the roster quietly shrink.
RUNTIME_ENTRY_POINTS: dict[str, tuple[tuple[str, str], ...]] = {
    "ops/lane_slot.py": (("ops.lane_slot", "_pid_alive"),),
    "ops/loop/guard.py": (("ops.loop.guard", "pid_is_alive"),),
    "ops/loop/watch.py": (
        ("ops.loop.watch", "process_creation_time"),
        ("ops.loop.watch", "pid_open_denied"),
    ),
}

#: Win32 entry points whose ADDRESS the probe resolves before it starts
#: recording, so a call through one can be matched by pointer. The vetted names
#: are here to correlate the access mask; the dangerous ones are here so a call
#: through them is blocked by the hook instead of being merely reported.
#:
#: ``ntdll`` is deliberately absent - pre-resolving its exports would mean
#: LOADING ntdll inside the probe, and a guard that loads the library it exists
#: to refuse is not a guard. An ntdll reach is caught by ``ctypes.dlopen``
#: naming a library outside :data:`ALLOWED_LIBRARIES` instead.
PRERESOLVED_KERNEL32 = (
    "OpenProcess",
    "GetProcessTimes",
    "GetExitCodeProcess",
    "CloseHandle",
    "TerminateProcess",
    "CreateRemoteThread",
    "WriteProcessMemory",
    "DebugActiveProcess",
)

#: Entry points the hook refuses to let a call through, by ADDRESS rather than
#: by name, so an assembled spelling is blocked exactly as a literal one is.
BLOCKED_KERNEL32 = frozenset(
    {
        "TerminateProcess",
        "CreateRemoteThread",
        "WriteProcessMemory",
        "DebugActiveProcess",
    }
)

#: The only access right an ``OpenProcess`` in this repository may ask for:
#: ``PROCESS_QUERY_LIMITED_INFORMATION``. It grants no power to affect the
#: process it names.
QUERY_LIMITED = 0x1000

#: ``GetLastError`` is resolved by ``ctypes.WinDLL(..., use_last_error=True)``
#: itself, before the module under test has asked for anything. It is not a
#: capability the module chose and it can affect nothing, so it is allowed
#: alongside the vetted set rather than added to it - widening
#: ALLOWED_WIN32_FUNCTIONS would weaken the static guard to suit this one.
CTOR_RESOLVED_SYMBOLS = frozenset({"GetLastError"})

RUNTIME_PROBE = r"""
import json
import sys

REPO, EXTRA, MODULE, FUNC = sys.argv[1:5]

# Resolve the addresses BEFORE the hook is installed, so these lookups are not
# recorded as the module under test's own and so the hook can refuse a call by
# ADDRESS. GetProcAddress answers with the same address for the same export in
# the same process, which is what makes the correlation exact.
KNOWN = {}
BLOCK = set()
try:
    import ctypes

    _k32 = ctypes.WinDLL("kernel32")
    for _name in json.loads(sys.argv[5]):
        try:
            KNOWN[_name] = ctypes.cast(getattr(_k32, _name), ctypes.c_void_p).value
        except Exception:
            pass
    for _name in json.loads(sys.argv[6]):
        if _name in KNOWN:
            BLOCK.add(KNOWN[_name])
except Exception:
    pass

QUERY_LIMITED = int(sys.argv[7])

DLOPEN = []
DLSYM = []
CALLS = []
REFUSED = []
OTHER = []
TOTAL = [0]
RECORDING = [True]


def _hook(event, args):
    # This hook RAISES on a dangerous operation, which aborts the operation
    # that raised it - that is what keeps the probe from performing the very
    # act it is here to detect. Everything else is swallowed, for the reason
    # tests/conftest.py records: an exception escaping a hook aborts an
    # unrelated operation and the failure reads as a bug somewhere else.
    if not RECORDING[0]:
        return
    refusal = None
    try:
        TOTAL[0] += 1
        if event == "ctypes.dlopen":
            DLOPEN.append(str(args[0]))
        elif event in ("ctypes.dlsym", "ctypes.dlsym/handle"):
            DLSYM.append(str(args[1]))
        elif event == "ctypes.call_function":
            pointer = int(args[0])
            rendered = [repr(one)[:80] for one in args[1]]
            CALLS.append([pointer, rendered])
            if pointer in BLOCK:
                refusal = ["blocked-entry-point", pointer, rendered]
            elif pointer == KNOWN.get("OpenProcess") and args[1]:
                first = args[1][0]
                if not isinstance(first, int) or first != QUERY_LIMITED:
                    refusal = ["wider-process-right", pointer, rendered]
        elif event == "os.kill":
            OTHER.append([event, repr(args)[:120]])
            if len(args) > 1 and args[1] != 0:
                refusal = ["os.kill-with-a-real-signal", 0, [repr(args)[:120]]]
        elif event in (
            "subprocess.Popen",
            "os.system",
            "os.exec",
            "os.posix_spawn",
            "os.spawn",
            "winreg.OpenKey",
        ):
            OTHER.append([event, repr(args)[:120]])
            refusal = [event, 0, [repr(args)[:120]]]
    except Exception:
        return
    if refusal is not None:
        REFUSED.append(refusal)
        raise RuntimeError("refused by the Lanternlight runtime capability probe")


sys.addaudithook(_hook)
sys.path.insert(0, REPO)
if EXTRA:
    sys.path.insert(0, EXTRA)

_parts = MODULE.split(".")
_mod = __import__(MODULE)
for _part in _parts[1:]:
    _mod = getattr(_mod, _part)

import os  # noqa: E402  (imported late so the import itself is audited)

try:
    RESULT = repr(getattr(_mod, FUNC)(os.getpid()))
    ERROR = ""
except Exception as exc:
    RESULT = ""
    ERROR = type(exc).__name__ + ": " + str(exc)

RECORDING[0] = False
print(
    json.dumps(
        {
            "dlopen": DLOPEN,
            "dlsym": DLSYM,
            "calls": CALLS,
            "refused": REFUSED,
            "other": OTHER,
            "known": KNOWN,
            "audited": TOTAL[0],
            "result": RESULT,
            "error": ERROR,
        }
    )
)
"""


def run_probe(
    tmp_path: Path,
    module: str,
    func: str,
    extra_path: Path | None = None,
) -> dict:
    """Run ``module.func(os.getpid())`` in a child under an audit hook.

    The pid handed in is the CHILD INTERPRETER'S OWN, so the only process any
    probe below can reach is one this test created. No game process, no
    operator process, and no process this file did not make.
    """
    script = tmp_path / "capability_probe.py"
    script.write_text(RUNTIME_PROBE, encoding="ascii", newline="\n")
    out = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            str(REPO_ROOT),
            str(extra_path) if extra_path is not None else "",
            module,
            func,
            json.dumps(list(PRERESOLVED_KERNEL32)),
            json.dumps(sorted(BLOCKED_KERNEL32)),
            str(QUERY_LIMITED),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def _probe_cases() -> list[tuple[str, str, str]]:
    """``(relative, dotted module, entry point)`` for every runtime probe."""
    return [
        (relative, dotted, func)
        for relative in sorted(RUNTIME_ENTRY_POINTS)
        for dotted, func in RUNTIME_ENTRY_POINTS[relative]
    ]


PROBE_CASES = _probe_cases()
PROBE_IDS = [f"{relative}::{func}" for relative, _dotted, func in PROBE_CASES]


# ---------------------------------------------------------------------------
# The positive scope - census hole 1, fixed at the root.
# ---------------------------------------------------------------------------


def test_every_module_that_can_reach_native_code_is_scanned_or_excluded() -> None:
    """Default IN. Leaving needs an allowlist pass or a written reason.

    This is the assertion the census asked for. ``SCOPE`` answers "does this
    module NAME a process API", which the author controls; this answers "can
    this module reach native code at all", which the author cannot compute
    away, because the import has to be spelled out for the interpreter.
    """
    universe = native_reach_universe()
    unaccounted = [
        relative
        for relative in universe
        if relative not in SCOPE and relative not in NATIVE_SCOPE_EXCLUSIONS
    ]
    assert unaccounted == [], (
        "these modules can reach native code but are neither in "
        "test_process_capability.SCOPE nor written into "
        f"NATIVE_SCOPE_EXCLUSIONS with a reason: {unaccounted}"
    )


def test_the_positive_derivation_really_walked_the_repository() -> None:
    """A clean bill over an empty walk is not a clean bill.

    The walker can return nothing - git missing, a changed working directory,
    a recogniser that stops recognising - and every membership assertion above
    would then pass while judging nothing at all.
    """
    universe = native_reach_universe()
    assert len(_published_sources()) > 20, "the published walk found almost nothing"
    assert set(SCOPE) <= set(universe), (
        "the positive derivation missed a module the name-based derivation "
        f"already found: {sorted(set(SCOPE) - set(universe))}"
    )


def test_every_exclusion_names_a_real_file_and_carries_a_reason() -> None:
    """A stale or bare exclusion reddens rather than silently widening scope."""
    for relative, reason in NATIVE_SCOPE_EXCLUSIONS.items():
        assert (REPO_ROOT / relative).is_file(), f"{relative} is excluded but does not exist"
        assert len(reason.split()) >= 20, f"{relative} is excluded without a real reason"
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert reaches_native_code(source), (
            f"{relative} no longer reaches native code, so its exclusion is "
            "stale and is now hiding nothing while reading as a decision"
        )


#: The census's defeat sketch for hole 1, as source rather than as a planted
#: file. The module reaches ``OpenProcess`` and the literal never appears.
ASSEMBLED_HANDLE_MODULE = '''\
import ctypes


def probe(pid):
    lib = ctypes.WinDLL("kernel32")
    return getattr(lib, "Open" + "Process")(0x0001, False, pid)
'''


def test_the_name_based_derivation_is_blind_to_the_assembled_spelling() -> None:
    """The hole itself, demonstrated rather than asserted.

    This is the control for the test below it. Without watching the OLD
    derivation answer False, the new one answering True proves only that two
    functions differ, not that one closes a gap the other leaves open.
    """
    assert names_a_process_handle_api(ASSEMBLED_HANDLE_MODULE) is False


def test_the_positive_derivation_catches_the_assembled_spelling() -> None:
    """Same source, the other question, the other answer.

    The module cannot reach ``WinDLL`` without ``import ctypes``, and that is a
    statement the interpreter must be handed as text. So the spelling of the
    entry point stops deciding whether the module is examined.
    """
    assert reaches_native_code(ASSEMBLED_HANDLE_MODULE) is True


def test_a_module_that_only_talks_about_the_boundary_stays_out_of_scope() -> None:
    """The mirror. A derivation that says yes to everything is not a derivation."""
    prose = '''\
"""Notes on OpenProcess, TerminateProcess and why this repo refuses them."""

from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
'''
    assert reaches_native_code(prose) is False


def test_every_scope_module_has_a_runtime_entry_point() -> None:
    """A module in SCOPE with no probe here is a module this file cannot judge.

    Written as an assertion rather than left to a reader, because the failure
    it prevents already happened once in this repository: ``ops/lane_slot.py``
    landed holding a process handle, nobody added it to the roster, and
    widening its access mask to ``PROCESS_ALL_ACCESS`` left three test modules
    green.
    """
    missing = [relative for relative in SCOPE if relative not in RUNTIME_ENTRY_POINTS]
    assert missing == [], (
        f"these modules are in SCOPE but have no runtime entry point here: {missing}"
    )


# ---------------------------------------------------------------------------
# The runtime arm over the shipped modules.
# ---------------------------------------------------------------------------


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_every_library_loaded_at_runtime_is_vetted(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """Every ``ctypes.dlopen`` names a library on the vetted list.

    This is the arm an ``ntdll`` reach fails, and it fails it whether the
    library name was a literal or assembled, because the event carries the
    name the loader was handed.
    """
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    loaded = sorted({name.lower() for name in payload["dlopen"]})
    assert loaded, (
        f"{relative}::{func} loaded no native library at all, so this check "
        "passed vacuously rather than by observing a load"
    )
    unvetted = [name for name in loaded if name not in ALLOWED_LIBRARIES]
    assert unvetted == [], f"{relative}::{func} loaded {unvetted}"


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_every_win32_symbol_resolved_at_runtime_is_vetted(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """Every ``ctypes.dlsym`` names an entry point on the vetted list.

    THIS IS THE ARM THAT ANSWERS CENSUS DEFEATS 1, 2 AND THE CTYPES HALF OF 3.
    ``getattr(handle, "Terminate" + "Process")`` produces a ``dlsym`` event
    carrying ``TerminateProcess``, so a spelling assembled at run time is
    exactly as visible as a literal one.
    """
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    resolved = sorted(set(payload["dlsym"]))
    assert "OpenProcess" in resolved, (
        f"{relative}::{func} resolved no process entry point, so this check "
        f"observed nothing; resolved={resolved}"
    )
    permitted = ALLOWED_WIN32_FUNCTIONS | CTOR_RESOLVED_SYMBOLS
    unvetted = [name for name in resolved if name not in permitted]
    assert unvetted == [], f"{relative}::{func} resolved {unvetted}"


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_every_openprocess_at_runtime_asks_only_for_the_query_limited_right(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """The access mask, read as the VALUE the kernel was handed.

    THIS IS THE ARM THAT ANSWERS CENSUS DEFEAT 4. A mask computed at run time -
    ``_PROCESS_QUERY_LIMITED_INFORMATION | (1 << 0)`` - is not a structure a
    text check can evaluate, and it does not need to be: by the time
    ``ctypes.call_function`` fires, the fold has happened and the event carries
    4097 rather than an expression.
    """
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    address = payload["known"].get("OpenProcess")
    assert address, "the probe could not resolve OpenProcess, so it correlated nothing"
    masks = [rendered[0] for pointer, rendered in payload["calls"] if pointer == address]
    assert masks, (
        f"{relative}::{func} never called OpenProcess, so this check passed "
        "vacuously rather than by reading a mask"
    )
    wider = [mask for mask in masks if mask != str(QUERY_LIMITED)]
    assert wider == [], (
        f"{relative}::{func} asked OpenProcess for {wider}, and the only "
        f"permitted right is PROCESS_QUERY_LIMITED_INFORMATION ({QUERY_LIMITED})"
    )


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_no_process_affecting_operation_is_audited_at_runtime(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """No signal, no spawn, no shell, and nothing the hook had to refuse.

    The per-run non-vacuity for this one is the ``refused`` list being EMPTY on
    a shipped module and NON-EMPTY on each planted defeat below. A negative
    assertion on its own rules something out without pinning anything down.
    """
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    assert payload["refused"] == [], f"{relative}::{func} was refused: {payload['refused']}"
    assert payload["other"] == [], f"{relative}::{func} audited {payload['other']}"
    assert payload["audited"] > 0, "the hook recorded no events at all, so it was never installed"


# ---------------------------------------------------------------------------
# The probe's own non-vacuity, over PLANTED modules rather than the shipped
# ones. A guard that has only ever been shown clean code is decoration; these
# are the four census defeat sketches, each written as a module the probe is
# then run against. None of them reaches a process this file did not create,
# and the two that would have - a termination call and a wider right - are
# ABORTED by the hook, which is why they can be written down at all.
# ---------------------------------------------------------------------------


def _plant(tmp_path: Path, name: str, source: str) -> Path:
    """Write a throwaway module outside the repository and return its directory."""
    package = tmp_path / "planted"
    package.mkdir(exist_ok=True)
    (package / f"{name}.py").write_text(source, encoding="ascii", newline="\n")
    return package


#: Census defeat 2, as a module. The symbol is RESOLVED and never called -
#: resolving an export touches no process - and the hook would abort the call
#: by address if it were.
PLANTED_ASSEMBLED_TERMINATE = '''\
import ctypes


def probe(pid):
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    return getattr(lib, "Terminate" + "Process") is not None
'''

#: Census defeat 3. ``os.kill`` with a real signal routes to
#: ``TerminateProcess`` on Windows, so it is the hook's refusal that keeps this
#: module honest rather than the module's own restraint.
PLANTED_ASSEMBLED_KILL = '''\
import os


def probe(pid):
    try:
        getattr(os, "kil" + "l")(pid, 9)
    except Exception:
        return False
    return True
'''

#: Census defeat 4. The fold happens before the call, so no text check can read
#: it and the audit event does not have to.
PLANTED_COMPUTED_MASK = '''\
import ctypes
from ctypes import wintypes

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def probe(pid):
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    lib.OpenProcess.restype = wintypes.HANDLE
    lib.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    lib.CloseHandle.argtypes = (wintypes.HANDLE,)
    mask = _PROCESS_QUERY_LIMITED_INFORMATION | (1 << 0)
    handle = lib.OpenProcess(mask, False, pid)
    if handle:
        lib.CloseHandle(handle)
    return bool(handle)
'''

#: Census defeat 1. A module that never enters the name-based SCOPE at all,
#: doing the thing that scope exists to examine.
PLANTED_UNSCANNED_MODULE = '''\
import ctypes
from ctypes import wintypes


def probe(pid):
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    opener = getattr(lib, "Open" + "Process")
    opener.restype = wintypes.HANDLE
    opener.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    closer = getattr(lib, "Close" + "Handle")
    closer.argtypes = (wintypes.HANDLE,)
    handle = opener(0x1000, False, pid)
    if handle:
        closer(handle)
    return bool(handle)
'''


@WINDOWS_ONLY
def test_the_probe_sees_a_termination_entry_point_resolved_under_an_assembled_name(
    tmp_path: Path,
) -> None:
    """Census defeat 2, caught. The symbol name is in the event, not the source."""
    package = _plant(tmp_path, "assembled_terminate", PLANTED_ASSEMBLED_TERMINATE)
    payload = run_probe(tmp_path, "assembled_terminate", "probe", extra_path=package)
    assert payload["error"] == "", payload["error"]
    assert "TerminateProcess" in payload["dlsym"], payload["dlsym"]
    permitted = ALLOWED_WIN32_FUNCTIONS | CTOR_RESOLVED_SYMBOLS
    assert [name for name in payload["dlsym"] if name not in permitted] == ["TerminateProcess"]
    # And the source really is free of the literal, so the static guards this
    # arm supplements would have had nothing to collect.
    assert "TerminateProcess" not in PLANTED_ASSEMBLED_TERMINATE


@WINDOWS_ONLY
def test_the_probe_sees_and_refuses_an_assembled_os_kill_with_a_real_signal(
    tmp_path: Path,
) -> None:
    """Census defeat 3, caught by the signal VALUE and stopped before it lands."""
    package = _plant(tmp_path, "assembled_kill", PLANTED_ASSEMBLED_KILL)
    payload = run_probe(tmp_path, "assembled_kill", "probe", extra_path=package)
    assert payload["error"] == "", payload["error"]
    kinds = [row[0] for row in payload["refused"]]
    assert "os.kill-with-a-real-signal" in kinds, payload["refused"]
    assert payload["result"] == "False", (
        "the planted module reported the signal was delivered; the hook was "
        "supposed to abort it"
    )


@WINDOWS_ONLY
def test_the_probe_sees_and_refuses_a_process_right_computed_at_runtime(
    tmp_path: Path,
) -> None:
    """Census defeat 4, caught by the folded VALUE the kernel was handed.

    This module catches nothing, so the hook's refusal propagates out of
    ``probe`` and the run reports it as an error. That is the shape asserted
    below, and it is the stronger evidence: the handle was never returned to
    the caller at all.
    """
    package = _plant(tmp_path, "computed_mask", PLANTED_COMPUTED_MASK)
    payload = run_probe(tmp_path, "computed_mask", "probe", extra_path=package)
    assert "refused by the Lanternlight runtime capability probe" in payload["error"]
    assert payload["result"] == "", payload["result"]
    kinds = [row[0] for row in payload["refused"]]
    assert "wider-process-right" in kinds, payload["refused"]
    address = payload["known"]["OpenProcess"]
    masks = [rendered[0] for pointer, rendered in payload["calls"] if pointer == address]
    assert masks == [str(QUERY_LIMITED | 0x0001)], masks


@WINDOWS_ONLY
def test_the_probe_reads_a_module_the_name_based_scope_would_never_have_scanned(
    tmp_path: Path,
) -> None:
    """Census defeat 1, caught - and the control that it really is unscannable.

    The planted source names no member of ``PROCESS_HANDLE_APIS`` anywhere, so
    ``names_a_process_handle_api`` says no and the capability allowlist never
    sees it. The run says otherwise about the same file.
    """
    assert names_a_process_handle_api(PLANTED_UNSCANNED_MODULE) is False
    assert reaches_native_code(PLANTED_UNSCANNED_MODULE) is True
    package = _plant(tmp_path, "unscanned", PLANTED_UNSCANNED_MODULE)
    payload = run_probe(tmp_path, "unscanned", "probe", extra_path=package)
    assert payload["error"] == "", payload["error"]
    assert "OpenProcess" in payload["dlsym"], payload["dlsym"]
    assert "CloseHandle" in payload["dlsym"], payload["dlsym"]


@WINDOWS_ONLY
def test_the_hook_is_not_refusing_everything(tmp_path: Path) -> None:
    """The mirror for the three refusals above.

    A hook that raised on every event would make each of them pass while
    proving nothing, and the shipped-module arms would all error out. This
    pins the other direction on a PLANTED module that does the legitimate
    thing, so the point is made without leaning on the repository staying
    clean.
    """
    legitimate = PLANTED_UNSCANNED_MODULE
    package = _plant(tmp_path, "legitimate", legitimate)
    payload = run_probe(tmp_path, "legitimate", "probe", extra_path=package)
    assert payload["refused"] == [], payload["refused"]
    assert payload["result"] == "True", payload
