"""A RUNTIME arm over the SPAWN tier of THE HARD BOUNDARY.

WHY THIS FILE EXISTS. ``tests/test_process_capability_at_runtime.py`` landed on
2026-09-20 and gave the severity-1 guards a runtime counterpart, but every one
of them - old and new - reasons about NATIVE reach: ``ctypes``, ``winreg``,
``win32*``, and the access mask a process handle asks for. Its own docstring
declares the hole this file closes: a module that imports ``subprocess`` can
run ``taskkill`` without any ctypes at all, and those modules are NOT pulled
into the native scope. That is ``OPS-101``.

A subprocess needs no native reach to touch a process. ``taskkill /F /PID``,
``wmic``, ``tskill``, a shell carrying a process-stopping cmdlet, and any
launcher that starts or stops something are each one ``subprocess.run`` away,
and no guard in this repository could see one before this file.

WHAT IS NOT CLAIMED. No violation is alleged. Measured in this tree on
2026-09-20, fifteen published modules outside ``tests/`` import ``subprocess``,
and every one of them runs ``git``, ``pytest``, ``ruff`` or this repository's
own tools. ``ROADMAP.md`` says eighteen and the native arm's docstring says
fourteen; all three are readings of a moving tree, and a filed count is a
hypothesis. The claim here is about COVERAGE, not about a defect.

WHICH AUDIT EVENTS ACTUALLY FIRE, AND WHAT THEY CARRY. Measured on this
machine, CPython 3.14 on Windows, 2026-09-20, by running each operation under a
hook and printing what arrived. Nothing below is taken on the documentation's
word, for the reason the responder slice recorded when it found that
``importlib.import_module`` raises NO ``import`` event at all.

* ``subprocess.Popen`` fires once per spawn, BEFORE the process exists, with
  four arguments: ``(executable, command_line, cwd, env)``.

  **THE ARGUMENT VECTOR IS NOT A VECTOR ON WINDOWS, AND THIS MATTERS.**
  ``ROADMAP.md`` acceptance criterion 2 says the event carries "the executable
  and the full argument vector". Measured, the second argument is a single
  STRING: ``subprocess`` has already run ``list2cmdline`` over the list, so a
  four-element list arrives as one space-joined command line. A guard that
  indexes it like a list silently reads one CHARACTER. Everything below
  tokenises the string instead.

  The FIRST argument is ``None`` for the ordinary ``Popen([...])`` call, and is
  a path only when the caller passed ``executable=`` or ``shell=True``. So the
  program name is usually available ONLY from the command line, which is the
  second reason this file tokenises.

  ``subprocess.run`` raises the same event, because it is a thin wrapper.
  ``os.popen`` ALSO raises it and raises nothing of its own: the measured
  command line was the system shell with ``/c`` and the requested command
  quoted inside it. ``cwd`` is the third argument, a string when the caller
  passed one and ``None`` otherwise.

* ``os.system`` fires with ``(command,)``, the command as a single string.

* ``os.spawn`` fires for ``os.spawnv`` and its family with
  ``(mode, path, argv, env)``. Here ``argv`` really IS a list, unlike the
  ``subprocess.Popen`` case, so the two have to be normalised separately.

* ``os.exec`` fires for ``os.execv`` and its family with ``(path, argv, env)``,
  ``argv`` again a real list. Raising in the hook ABORTS it, which is what
  makes it safe to exercise at all.

* ``shutil.which`` raises NO AUDIT EVENT AT ALL. Probed directly and nothing
  arrived. ``ROADMAP.md`` names it as an in-scope import and it is one for the
  STATIC derivation below, but no runtime arm can watch it. Recorded here
  because an assumed event is a vacuous guard, and this is the one the
  acceptance criterion would have invited.

* ``multiprocessing`` does NOT raise ``subprocess.Popen``. On Windows a spawn
  context goes through ``_winapi.CreateProcess`` directly, and that is the only
  process-creating event it raises.

* ``_winapi.CreateProcess`` is the lowest-level event and fires under BOTH
  ``subprocess`` and ``multiprocessing``, with
  ``(application_name, command_line, current_directory)``. **Its command line
  is unusable.** Measured under both callers, the second argument arrived as a
  single control character rather than the command, so the one event that sees
  everything cannot say WHAT it saw. ``application_name`` is readable and is
  ``None`` under ``subprocess``. This file therefore uses it as a CORROBORATION
  COUNTER - it proves a process was created when a higher-level event claims
  one was - and never as the thing it classifies.

* An executable name assembled at run time is carried in full. Concatenating
  the two halves of a program name produces the finished literal in the command
  line, because the hook sits below the point where that string is handed to
  the loader. That single measurement is what makes acceptance criterion 4
  possible, and it is the same property the native arm measured for
  ``ctypes.dlsym``.

* A hook that RAISES on ``subprocess.Popen`` aborts the spawn. Measured: the
  exception propagated out of ``subprocess.run`` and no process was created.
  That is what lets this file write down a termination spelling without any
  process being terminated.

NOTHING HERE TOUCHES THE GAME PROCESS, AND THAT IS STRUCTURAL. Acceptance
criterion 5 is absolute. Every probe below runs in a child interpreter this
file created. The only process a PERMITTED termination names is a sleeper that
the probe itself starts and registers, and the only process a REFUSED
termination names is the probe interpreter's own pid. No pid from outside the
probe is ever read, resolved or handed to anything, and no module is asked for
a pid. There is no code path here that can name a process this file did not
create.

WHAT THIS FILE IS BLIND TO. Written in the artifact, because a caveat that
lives in a chat log is a lie in the artifact.

* **It is a claim about the runs it makes.** A branch no roster entry below
  reaches is untested here. The static tier covers the unreached branches and
  is not weakened by this file.
* **``shutil.which`` is unobservable**, as measured above.
* **The our-child line is REGISTRATION, not kinship.** See
  :data:`OWN_CHILD_LINE_LIMITS`, which states every case it cannot separate.
* **``_winapi.CreateProcess`` is a counter, not a classifier**, for the reason
  measured above, so a caller that reaches a process creation without going
  through one of the readable events is counted and not read.
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

WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "the spawn classification below reads a Windows command line produced "
        "by list2cmdline and names Windows process-control programs; on any "
        "other platform the event carries a real argument vector instead and a "
        "run here would pass while observing a different shape"
    ),
)

# ---------------------------------------------------------------------------
# THE POSITIVE SCOPE - acceptance criterion 1.
#
# Derived the way the native arm derives its own: not "does this module name a
# dangerous program", which the author controls and can compute away, but "can
# this module reach a spawn AT ALL", which the author declares in an import
# statement the interpreter must be handed as text.
#
# The criterion names ``subprocess``, ``os.system``, ``os.popen``, ``os.spawn*``,
# ``shutil.which`` and ``multiprocessing``. Three of those are ATTRIBUTES of
# ``os`` rather than imports, and reading them as "any module that imports os"
# puts almost every file in this repository in scope while saying nothing.
# Reading them as "any module that spells os.system" would be the name-matching
# defect the native arm exists to fix.
#
# So the rule below is both, and the third clause is what closes the hole:
#
#   A module is IN SCOPE if it imports a spawn-only root, OR names a spawning
#   attribute of ``os`` or ``shutil``, OR uses a DYNAMIC-REACH construct.
#
# A dynamic-reach construct is ``getattr``, ``eval``, ``exec``, ``compile`` or
# ``__import__``. Assembling a call to a spawning attribute requires one of
# them, and they are detected STRUCTURALLY - as a node in the tree - rather
# than by the name of whatever they are reaching for. A module cannot spell its
# way out of that the way it can spell its way out of an API denylist.
# ---------------------------------------------------------------------------

#: Import roots whose whole purpose is reaching another process, or which can
#: manufacture an import and thereby reach one of the others without naming it.
SPAWN_ONLY_ROOTS = frozenset(
    {
        "asyncio",
        "importlib",
        "multiprocessing",
        "pty",
        "runpy",
        "subprocess",
    }
)

#: Attributes of ``os`` that create or replace a process. The ``spawn`` and
#: ``exec`` families are matched by prefix because each family is large and
#: every member of it spawns.
OS_SPAWN_ATTRIBUTES = frozenset(
    {
        "fork",
        "forkpty",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "startfile",
        "system",
    }
)
OS_SPAWN_PREFIXES = ("spawn", "exec")

#: Builtins that manufacture a call or an import at run time. Their PRESENCE
#: puts a module in scope; what they reach for is deliberately not inspected,
#: because inspecting it would put the author back in charge of the answer.
DYNAMIC_REACH_BUILTINS = frozenset({"__import__", "compile", "eval", "exec", "getattr"})

#: Path prefixes the derivation does not walk. The test tree is excluded for
#: the same reason the native arm excludes it: these files quote every
#: forbidden spelling as fixture source, and this very module plants a
#: process-control command line as a string constant.
DERIVATION_EXCLUDED_PREFIXES = ("tests/",)


def spawn_surface(source: str) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Return ``(spawn-only roots, named spawn attributes, dynamic builtins)``.

    Pure over its input, for the reason the native arm gives: pinning the
    derivation then needs nothing but a list of strings, rather than a
    capability-bearing file planted in the tree this guard audits.

    An unparsable module is treated as reaching everything, so it lands in
    scope rather than slipping out of it.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset(SPAWN_ONLY_ROOTS), frozenset(), frozenset(DYNAMIC_REACH_BUILTINS)

    roots: set[str] = set()
    named: set[str] = set()
    dynamic: set[str] = set()

    def note(owner: str, attribute: str) -> None:
        if owner == "os" and (
            attribute in OS_SPAWN_ATTRIBUTES or attribute.startswith(OS_SPAWN_PREFIXES)
        ):
            named.add("os." + attribute)
        elif owner == "shutil" and attribute == "which":
            named.add("shutil.which")
        elif owner in SPAWN_ONLY_ROOTS:
            named.add(owner + "." + attribute)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in SPAWN_ONLY_ROOTS:
                    roots.add(root)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            root = node.module.split(".")[0]
            if root in SPAWN_ONLY_ROOTS:
                roots.add(root)
            for alias in node.names:
                note(root, alias.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            note(node.value.id, node.attr)
        elif isinstance(node, ast.Name) and node.id in DYNAMIC_REACH_BUILTINS:
            dynamic.add(node.id)

    return frozenset(roots), frozenset(named), frozenset(dynamic)


def reaches_a_spawn(source: str) -> bool:
    """True when ``source`` can reach another process, by any of the three routes."""
    roots, named, dynamic = spawn_surface(source)
    return bool(roots or named or dynamic)


def pinned_surface(source: str) -> tuple[str, ...]:
    """The module's spawn surface as a sorted tuple, for pinning in an exclusion.

    An exclusion that carries only prose is a promise. An exclusion that
    carries this is an OBSERVATION, and the test below reddens the moment the
    observation stops matching - which is what turns a written reason into a
    drift detector rather than a rubber stamp.
    """
    roots, named, dynamic = spawn_surface(source)
    return tuple(sorted({"import " + root for root in roots} | set(named) | set(dynamic)))


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


def spawn_universe() -> tuple[str, ...]:
    """Every published module outside ``tests/`` that can reach a spawn."""
    return tuple(
        sorted(relative for relative, source in _published_sources() if reaches_a_spawn(source))
    )


# ---------------------------------------------------------------------------
# The roster, and the exclusions that are the price of leaving it.
# ---------------------------------------------------------------------------

#: Entry points that make an in-scope module actually SPAWN. Each callable is
#: handed ``REPO_ROOT`` and must reach at least one process creation, which
#: :func:`test_every_roster_entry_actually_spawned_something` asserts rather
#: than assumes - a probe that observed nothing passes every negative check.
SPAWN_RUNTIME_ENTRY_POINTS: dict[str, tuple[tuple[str, str], ...]] = {
    "ops/docguards.py": (
        ("ops.docguards", "tracked_docs"),
        ("ops.docguards", "staged_docs"),
    ),
    "ops/lanes.py": (("ops.lanes", "primary_checkout"),),
    "ops/store_drift.py": (("ops.store_drift", "snapshot"),),
    # OPS-103. Lists this repository's staged set with one git call - a read.
    "tools/secret_scan.py": (("tools.secret_scan", "staged_paths"),),
    # OPS-106. Lists every object reachable from every ref with one git
    # rev-list - a read, and the first spawn the full-history scan makes.
    "scripts/history_scan.py": (("scripts.history_scan", "reachable_objects"),),
    # OPS-107. Lists this repository's published set with git - a read.
    "ops/scratch_path_guard.py": (("ops.scratch_path_guard", "population"),),
}

#: Modules that CAN reach a spawn and are deliberately not probed, each with
#: the reason a human gave and the spawn surface that reason was written
#: against. Both halves are checked: a bare reason is how a scope quietly
#: narrows, and an unpinned surface is how a module grows a new spawn under an
#: exclusion that still reads as a decision.
SPAWN_SCOPE_EXCLUSIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "lanternlight/damage.py": (
        "In scope only because it uses getattr, which is the structural "
        "dynamic-reach clause rather than an observed spawn. It imports no "
        "spawn root at all and names no spawning attribute, so there is no "
        "entry point here that could create a process and a probe would "
        "observe nothing. The pinned surface reddens the moment it gains one.",
        ("getattr",),
    ),
    "lanternlight/redact.py": (
        "NOT PROBED ON PURPOSE, and this is the exclusion that earns the map. "
        "Its subprocess calls read the operator's git identity, which ADR-004 "
        "and CLAUDE.md name as an operator identifier. A runtime probe records "
        "what it observed into a payload this test then formats into a failure "
        "message, so probing it would build a machine for printing that "
        "identity on any red. The static tier covers it instead.",
        ("getattr", "import subprocess", "subprocess.SubprocessError", "subprocess.run"),
    ),
    "ops/cycle_cost.py": (
        "Runs git over a commit range to cost the refutation cycle. Its only "
        "entry points take a range and a git executable and walk the whole "
        "history, which is a slow probe for a module whose spawn surface is a "
        "single subprocess.run of git that the pinned surface already watches.",
        ("import subprocess", "subprocess.run"),
    ),
    "ops/lane_launcher.py": (
        "This module's whole job is STARTING lane processes. Probing it would "
        "mean actually launching a lane from inside the suite, which is a real "
        "side effect on the operator's machine and on the lane governor, so it "
        "is excluded rather than run. Its spawn surface is pinned instead and "
        "the static tier reads its source.",
        ("import subprocess", "subprocess.run"),
    ),
    "ops/loop/watch.py": (
        "The one module here that uses subprocess.Popen rather than run, and "
        "it uses it to START the unattended loop. Probing it would start a "
        "loop. It is already on the NATIVE runtime roster in "
        "test_process_capability_at_runtime.py, where its process-handle "
        "behaviour is measured without launching anything.",
        ("getattr", "import subprocess", "subprocess.DEVNULL", "subprocess.Popen"),
    ),
    "ops/merge_gate.py": (
        "Its spawning entry point re-runs the entire pytest suite, which takes "
        "five to eight minutes in this repository. A probe of it would make "
        "this file the slowest module in the suite by an order of magnitude, "
        "and it would be running the suite from inside the suite.",
        ("import subprocess", "subprocess.run"),
    ),
    "ops/outside_scan.py": (
        "OPS-103. Its spawns are git calls whose INPUT is the population outside "
        "this repository - the Git for Windows install root and the system temp "
        "directory - and its only spawning entry points take that population "
        "rather than a repository root. A probe would hash every file in the "
        "operator's temp directory from inside the suite, and a failure message "
        "built from what it observed would print paths under the account's home "
        "directory. Its own tests drive it against a planted tmp_path bucket.",
        ("getattr", "import subprocess", "subprocess.SubprocessError", "subprocess.run"),
    ),
    "ops/preflight.py": (
        "Its spawning entry point is the pre-flight itself, measured at "
        "eighteen to twenty-nine seconds, and it is the thing a slice runs "
        "BEFORE claiming done. Probing it from inside the suite would run the "
        "guards recursively and would make the pre-flight part of what the "
        "pre-flight checks.",
        ("import subprocess", "subprocess.SubprocessError", "subprocess.run"),
    ),
    "ops/stop_audit.py": (
        "Audits this repository for the forbidden process-stopping cmdlet by "
        "running git over the history. It is the module whose SUBJECT is the "
        "rule this file enforces, so its source quotes the forbidden name "
        "throughout and a probe of it would classify its own fixture text. "
        "The static tier reads it instead.",
        ("getattr", "import subprocess", "subprocess.SubprocessError", "subprocess.run"),
    ),
    "scripts/install_hooks.py": (
        "Wires core.hooksPath into the local git config. Probing it would "
        "rewrite the operator's git configuration as a side effect of running "
        "the suite, which is a change to this machine rather than an "
        "observation of it. Its single subprocess.run is pinned instead.",
        ("import subprocess", "subprocess.run"),
    ),
    "tools/doc_size_budget.py": (
        "Its spawning entry point needs a document path and a git working "
        "directory rather than a repository root, so it does not fit the "
        "single-argument roster shape, and it spawns git twice to hash and "
        "size one blob. The pinned surface watches that pair for drift.",
        ("import subprocess", "subprocess.run"),
    ),
    "tools/false_red_probe.py": (
        "A harness that deliberately breaks and restores files in the working "
        "tree to prove a guard is not vacuous. Probing it from inside the "
        "suite would let it mutate the tree the suite is reading, which is the "
        "poisoned-bytecode failure this repository has already measured once.",
        ("import subprocess", "subprocess.run"),
    ),
    "tools/precommit_gate.py": (
        "The hook that refuses a forbidden command, so like ops/stop_audit.py "
        "its source is full of the spellings it exists to reject, and a probe "
        "would be classifying its fixture strings. It is also the gate this "
        "session's own shell commands pass through, so running it from inside "
        "the suite would nest the gate inside itself.",
        ("getattr", "import subprocess", "subprocess.SubprocessError", "subprocess.run"),
    ),
    "tools/preflight_backtest.py": (
        "Replays the pre-flight at the parent of historical commits, so a "
        "single call checks out old trees and runs the guards over each one. "
        "That is minutes of git and ruff per invocation and it rewrites the "
        "working tree, which makes it unprobeable from inside the suite.",
        ("import subprocess", "subprocess.CompletedProcess", "subprocess.run"),
    ),
    "ops/inbox_watch.py": (
        "In scope only through the structural dynamic-reach clause, because it "
        "uses getattr. It imports no spawn root and names no spawning "
        "attribute, so it can create no process today and a probe would "
        "observe nothing at all. The pinned surface is what watches that.",
        ("getattr",),
    ),
    "ops/suite_recorder.py": (
        "In scope only through the structural dynamic-reach clause, because it "
        "uses getattr. It records suite results that another module measured "
        "and imports no spawn root, so a probe of it would observe no process "
        "creation. The pinned surface is what watches that.",
        ("getattr",),
    ),
    "tools/syntax_check_hook.py": (
        "In scope only through the structural dynamic-reach clause, because it "
        "uses getattr. It compiles staged files in this interpreter rather "
        "than shelling out, so it imports no spawn root and a probe would "
        "observe nothing. The pinned surface is what watches that.",
        ("getattr",),
    ),
    "third_party/lw_write_tracer/lw_write_tracer.py": (
        "VENDORED, and CLAUDE.md forbids editing a vendored file. It is in "
        "scope only through the structural dynamic-reach clause and imports no "
        "spawn root. tests/test_vendored_write_tracer.py fails if its bytes "
        "change, so the pinned surface here is a second reading of the same "
        "frozen file rather than a claim about code we can alter.",
        ("getattr",),
    ),
}

#: What the our-child line CANNOT separate. Acceptance criterion 3 asks how the
#: line was drawn and what it cannot distinguish, and the answer belongs in the
#: artifact rather than in a hand-off.
#:
#: HOW THE LINE WAS DRAWN. The probe starts a sleeper of its own BEFORE it
#: installs the hook and records that pid in a registry. A process-control
#: command is permitted only when every numeric pid target on its command line
#: is in that registry. Everything else is refused, so the default is refuse
#: and a parse failure refuses too.
OWN_CHILD_LINE_LIMITS: tuple[str, ...] = (
    "The line is REGISTRATION, not kinship. A pid this probe did not record is "
    "foreign even when it really is related, which is exactly why the refused "
    "case below names the probe interpreter's own pid: that process is ours in "
    "every ordinary sense and the guard still refuses it.",
    "It cannot see pid REUSE. If the registered sleeper exits and the operating "
    "system hands its number to something else, a command naming that number "
    "reads as permitted.",
    "It cannot judge a target named by IMAGE NAME rather than by pid, because "
    "there is no number to check. Such a command is refused outright rather "
    "than guessed at, which is the conservative direction but is a refusal of "
    "something that might have been legitimate.",
    "It cannot evaluate a pid computed inside the spawned program. A shell "
    "command that resolves its own target at run time carries no literal for "
    "the hook to read, so it is refused.",
    "It cannot follow a GRANDCHILD. A process started by our sleeper is not in "
    "the registry and is refused.",
    "It reads the command LINE only. What a spawned script later decides to do "
    "is invisible to a hook that fires once, at creation.",
)

#: Programs an in-scope module may spawn. An ALLOWLIST, deliberately, because
#: the native tier's lesson is that a denylist of dangerous names is a list the
#: author of the dangerous call gets to route around. Adding a name here is a
#: visible loosening; assembling a name at run time is not, and does not help.
SPAWN_ALLOWED_PROGRAMS = frozenset({"git", "py", "pytest", "python", "pythonw", "ruff"})

#: Programs whose purpose includes reaching an EXISTING process, plus the
#: shells that can carry such a command inside a string. Membership here is not
#: a refusal; it routes the spawn through the our-child check instead, which is
#: acceptance criterion 3. ``taskkill`` is here rather than banned precisely
#: because CLAUDE.md names ``taskkill /F /PID`` as the sanctioned way to end a
#: process we started, and a guard that forbids both cases gets turned off.
SPAWN_PROCESS_CONTROL_PROGRAMS = frozenset(
    {
        "cmd",
        "kill",
        "killall",
        "powershell",
        "pskill",
        "pwsh",
        "sc",
        "taskkill",
        "tskill",
        "wmic",
    }
)

#: Shells, whose first argument after a command switch is the real program.
#: Unwrapped exactly one layer, so ``os.popen`` calling git classifies as git
#: rather than as a shell.
SPAWN_SHELL_PROGRAMS = frozenset({"cmd", "powershell", "pwsh"})
SPAWN_SHELL_SWITCHES = frozenset({"-c", "-command", "/c", "/k"})

#: Tokens CLAUDE.md forbids outright, whatever the target. The rule is "never
#: use it", not "never use it on someone else's process", so this is checked
#: before the our-child question is even asked.
SPAWN_FORBIDDEN_TOKENS = ("stop-process",)

#: Tokens that introduce a numeric pid target.
SPAWN_PID_SELECTORS = frozenset({"id", "pid", "processid"})

#: Tokens that introduce a NON-numeric target, which the our-child check cannot
#: evaluate and therefore refuses.
SPAWN_NAME_SELECTORS = frozenset({"im", "imagename", "name", "processname"})


RUNTIME_PROBE = r'''
import json
import os
import subprocess
import sys

REPO, EXTRA, MODULE, FUNC, ARGKIND = sys.argv[1:6]
ALLOWED = set(json.loads(sys.argv[6]))
CONTROL = set(json.loads(sys.argv[7]))
SHELLS = set(json.loads(sys.argv[8]))
SWITCHES = set(json.loads(sys.argv[9]))
FORBIDDEN = tuple(json.loads(sys.argv[10]))
PID_SELECTORS = set(json.loads(sys.argv[11]))
NAME_SELECTORS = set(json.loads(sys.argv[12]))

# The sleeper is started BEFORE the hook is installed, so its own creation is
# not recorded as the module under test's, and its pid is the ONLY pid this
# probe will ever call ours. It exits on end-of-file, so it is torn down by
# closing a pipe rather than by killing anything.
SLEEPER = subprocess.Popen(
    [sys.executable, "-c", "import sys; sys.stdin.read()"],
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
OWN_CHILDREN = {SLEEPER.pid}

SPAWNS = []
REFUSED = []
CREATED = [0]
AUDITED = [0]
RECORDING = [True]


def _strip_program(token):
    token = token.strip().strip('"').strip("'")
    token = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".com", ".ps1"):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
    return token


def _tokens(line):
    """Quote-aware split. Quoted chunks are kept AND re-split, so a command
    carried inside a shell string is read rather than hidden by its quotes."""
    out = []
    current = ""
    quote = ""
    for char in line:
        if quote:
            if char == quote:
                quote = ""
            else:
                current += char
        elif char in "\"'":
            quote = char
        elif char.isspace():
            if current:
                out.append(current)
            current = ""
        else:
            current += char
    if current:
        out.append(current)
    return out


def _effective_program(tokens):
    if not tokens:
        return ""
    program = _strip_program(tokens[0])
    if program in SHELLS:
        for index, token in enumerate(tokens[1:], start=1):
            if token.lower() in SWITCHES and index + 1 < len(tokens):
                return _strip_program(tokens[index + 1])
    return program


def _selector_targets(tokens):
    """Return (numeric pid targets, saw a non-numeric target selector)."""
    pids = []
    by_name = False
    flat = []
    for token in tokens:
        for piece in token.replace(":", " ").replace("=", " ").split():
            flat.append(piece)
    for index, piece in enumerate(flat):
        bare = piece.lstrip("-/").lower()
        if bare in PID_SELECTORS:
            if index + 1 < len(flat) and flat[index + 1].isdigit():
                pids.append(int(flat[index + 1]))
            else:
                by_name = True
        elif bare in NAME_SELECTORS:
            by_name = True
    return pids, by_name


def _classify(line):
    lowered = line.lower()
    for token in FORBIDDEN:
        if token in lowered:
            return "refuse", "forbidden-cmdlet"
    tokens = _tokens(line)
    program = _effective_program(tokens)
    if program in CONTROL:
        pids, by_name = _selector_targets(tokens)
        if by_name or not pids:
            return "refuse", "process-control-without-a-pid-target"
        if all(pid in OWN_CHILDREN for pid in pids):
            return "permit", "own-child-process-control"
        return "refuse", "process-control-outside-our-own-children"
    if program in ALLOWED:
        return "permit", "vetted-program"
    return "refuse", "unvetted-program"


def _hook(event, args):
    # This hook RAISES on a refused spawn, and a raising audit hook ABORTS the
    # operation that raised it, so the event is recorded and the process is
    # never created. Everything else is swallowed, for the reason
    # tests/conftest.py records: an exception escaping a hook aborts an
    # unrelated operation and the failure reads as a bug somewhere else.
    if not RECORDING[0]:
        return
    refusal = None
    try:
        AUDITED[0] += 1
        line = None
        if event == "subprocess.Popen":
            raw = args[1]
            line = raw if isinstance(raw, str) else subprocess.list2cmdline(list(raw or []))
        elif event == "os.system":
            line = args[0] if isinstance(args[0], str) else str(args[0])
        elif event in ("os.spawn", "os.posix_spawn"):
            line = subprocess.list2cmdline([str(one) for one in (args[2] or [])])
        elif event == "os.exec":
            line = subprocess.list2cmdline([str(one) for one in (args[1] or [])])
        elif event == "os.startfile":
            line = str(args[0])
        elif event == "_winapi.CreateProcess":
            # Counted, never classified: its command line arrives mangled on
            # this interpreter, so it can say a process was created and cannot
            # say what it was.
            CREATED[0] += 1
            return
        if line is None:
            return
        verdict, reason = _classify(line)
        SPAWNS.append([event, line[:400], verdict, reason])
        if verdict == "refuse":
            refusal = [event, reason, line[:400]]
    except Exception:
        return
    if refusal is not None:
        REFUSED.append(refusal)
        raise RuntimeError("refused by the Lanternlight runtime spawn probe")


sys.addaudithook(_hook)
sys.path.insert(0, REPO)
if EXTRA:
    sys.path.insert(0, EXTRA)

if ARGKIND == "root":
    ARGUMENT = REPO
elif ARGKIND == "sleeper":
    ARGUMENT = SLEEPER.pid
else:
    ARGUMENT = os.getpid()

_parts = MODULE.split(".")
_mod = __import__(MODULE)
for _part in _parts[1:]:
    _mod = getattr(_mod, _part)

try:
    RESULT = repr(getattr(_mod, FUNC)(ARGUMENT))[:120]
    ERROR = ""
except Exception as exc:
    RESULT = ""
    ERROR = type(exc).__name__ + ": " + str(exc)[:200]

RECORDING[0] = False
SLEEPER_ALIVE = SLEEPER.poll() is None
try:
    SLEEPER.stdin.close()
    SLEEPER.wait(timeout=10)
except Exception:
    pass
print(
    json.dumps(
        {
            "spawns": SPAWNS,
            "refused": REFUSED,
            "created": CREATED[0],
            "audited": AUDITED[0],
            "sleeper_alive_after": SLEEPER_ALIVE,
            "result": RESULT,
            "error": ERROR,
        }
    )
)
'''


def run_probe(
    tmp_path: Path,
    module: str,
    func: str,
    arg_kind: str = "root",
    extra_path: Path | None = None,
) -> dict:
    """Run ``module.func(argument)`` in a child under an audit hook.

    ``arg_kind`` decides what the entry point is handed, and every option names
    a process this file created or no process at all: ``root`` passes the
    repository path, ``sleeper`` passes the pid of a child the probe started,
    and ``self`` passes the probe interpreter's own pid. There is no option
    that reaches a process from outside the probe.
    """
    script = tmp_path / "spawn_probe.py"
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
            arg_kind,
            json.dumps(sorted(SPAWN_ALLOWED_PROGRAMS)),
            json.dumps(sorted(SPAWN_PROCESS_CONTROL_PROGRAMS)),
            json.dumps(sorted(SPAWN_SHELL_PROGRAMS)),
            json.dumps(sorted(SPAWN_SHELL_SWITCHES)),
            json.dumps(list(SPAWN_FORBIDDEN_TOKENS)),
            json.dumps(sorted(SPAWN_PID_SELECTORS)),
            json.dumps(sorted(SPAWN_NAME_SELECTORS)),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def _probe_cases() -> list[tuple[str, str, str]]:
    return [
        (relative, dotted, func)
        for relative in sorted(SPAWN_RUNTIME_ENTRY_POINTS)
        for dotted, func in SPAWN_RUNTIME_ENTRY_POINTS[relative]
    ]


PROBE_CASES = _probe_cases()
PROBE_IDS = [f"{relative}::{func}" for relative, _dotted, func in PROBE_CASES]


# ---------------------------------------------------------------------------
# The positive scope - acceptance criterion 1.
# ---------------------------------------------------------------------------


def test_every_module_that_can_reach_a_spawn_is_probed_or_excluded() -> None:
    """Default IN. Leaving needs a roster entry or a written exclusion."""
    unaccounted = [
        relative
        for relative in spawn_universe()
        if relative not in SPAWN_RUNTIME_ENTRY_POINTS and relative not in SPAWN_SCOPE_EXCLUSIONS
    ]
    assert unaccounted == [], (
        "these modules can reach a spawn but are neither on "
        "SPAWN_RUNTIME_ENTRY_POINTS nor written into SPAWN_SCOPE_EXCLUSIONS "
        f"with a reason: {unaccounted}"
    )


def test_the_positive_derivation_really_walked_the_repository() -> None:
    """A clean bill over an empty walk is not a clean bill.

    The walker can return nothing - git missing, a changed working directory, a
    recogniser that stops recognising - and every membership assertion above
    would then pass while judging nothing at all.
    """
    universe = spawn_universe()
    assert len(_published_sources()) > 20, "the published walk found almost nothing"
    assert len(universe) > 10, f"the spawn universe is implausibly small: {universe}"
    assert set(SPAWN_RUNTIME_ENTRY_POINTS) <= set(universe), (
        "a roster entry is not in the derived universe, so the roster and the "
        f"derivation disagree: {sorted(set(SPAWN_RUNTIME_ENTRY_POINTS) - set(universe))}"
    )


def test_every_exclusion_names_a_real_file_carries_a_reason_and_pins_its_surface() -> None:
    """A stale, bare or drifted exclusion reddens rather than silently widening scope."""
    for relative, (reason, surface) in SPAWN_SCOPE_EXCLUSIONS.items():
        path = REPO_ROOT / relative
        assert path.is_file(), f"{relative} is excluded but does not exist"
        assert len(reason.split()) >= 20, f"{relative} is excluded without a real reason"
        source = path.read_text(encoding="utf-8")
        assert reaches_a_spawn(source), (
            f"{relative} no longer reaches a spawn, so its exclusion is stale "
            "and is now hiding nothing while reading as a decision"
        )
        measured = pinned_surface(source)
        assert measured == surface, (
            f"{relative} pinned {surface} and now measures {measured}; the "
            "exclusion was written against a surface this module no longer has"
        )


def test_no_module_is_both_probed_and_excluded() -> None:
    """The two maps are alternatives, and an overlap means one of them is a lie."""
    both = sorted(set(SPAWN_RUNTIME_ENTRY_POINTS) & set(SPAWN_SCOPE_EXCLUSIONS))
    assert both == [], f"these modules are both on the roster and excluded: {both}"


def test_the_our_child_line_states_what_it_cannot_distinguish() -> None:
    """Acceptance criterion 3 asks for the limits in writing, so they are asserted."""
    assert len(OWN_CHILD_LINE_LIMITS) >= 5
    for limit in OWN_CHILD_LINE_LIMITS:
        assert len(limit.split()) >= 15, f"a stated limit says almost nothing: {limit}"


#: A module that reaches ``os.system`` without the literal appearing anywhere,
#: which is the static tier's blind spot written as source.
ASSEMBLED_SPAWN_MODULE = '''\
import os


def probe(pid):
    return getattr(os, "sys" + "tem")("cd .")
'''


def test_the_derivation_catches_a_spawn_assembled_at_import_time() -> None:
    """The spelling stops deciding whether the module is examined.

    ``os.system`` appears nowhere in this source, so a check that collects
    attribute names finds nothing. The dynamic-reach clause answers on the
    structure instead, and a module cannot compute away a ``getattr`` node.
    """
    _roots, named, dynamic = spawn_surface(ASSEMBLED_SPAWN_MODULE)
    assert named == frozenset(), "the control failed: the literal was visible after all"
    assert dynamic == frozenset({"getattr"})
    assert reaches_a_spawn(ASSEMBLED_SPAWN_MODULE) is True


def test_a_module_that_only_talks_about_spawning_stays_out_of_scope() -> None:
    """The mirror. A derivation that says yes to everything is not a derivation."""
    prose = '''\
"""Notes on taskkill, os.system and why this repository watches them."""

from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
'''
    assert reaches_a_spawn(prose) is False


# ---------------------------------------------------------------------------
# The runtime arm over the shipped modules.
# ---------------------------------------------------------------------------


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_every_roster_entry_actually_spawned_something(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """Non-vacuity, per roster entry and per run.

    Every negative assertion below is satisfied by a probe that observed
    nothing, so the roster's right to exist is that each entry really creates a
    process. ``_winapi.CreateProcess`` is the corroboration: it fires under the
    creation itself, so a readable event claiming a spawn with no creation
    behind it would show up as a mismatch.
    """
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    assert payload["spawns"], f"{relative}::{func} spawned nothing, so this file judged nothing"
    assert payload["created"] >= len(payload["spawns"]), (
        f"{relative}::{func} reported {len(payload['spawns'])} readable spawns "
        f"but only {payload['created']} process creations"
    )
    assert payload["audited"] > 0, "the hook recorded no events at all, so it was never installed"


@WINDOWS_ONLY
@pytest.mark.parametrize(("relative", "dotted", "func"), PROBE_CASES, ids=PROBE_IDS)
def test_every_program_spawned_at_runtime_is_on_the_allowlist(
    tmp_path: Path, relative: str, dotted: str, func: str
) -> None:
    """Every spawn observed ran a vetted program and none was refused."""
    payload = run_probe(tmp_path, dotted, func)
    assert payload["error"] == "", payload["error"]
    assert payload["refused"] == [], f"{relative}::{func} was refused: {payload['refused']}"
    verdicts = {reason for _event, _line, verdict, reason in payload["spawns"] if verdict}
    assert verdicts == {"vetted-program"}, (
        f"{relative}::{func} produced spawn classifications {sorted(verdicts)}"
    )


# ---------------------------------------------------------------------------
# The probe's own non-vacuity, over PLANTED modules rather than the shipped
# ones. A guard that has only ever been shown clean code is decoration. None of
# these reaches a process this file did not create, and every one that would
# have is ABORTED by the hook, which is why they can be written down at all.
# ---------------------------------------------------------------------------


def _plant(tmp_path: Path, name: str, source: str) -> Path:
    """Write a throwaway module outside the repository and return its directory."""
    package = tmp_path / "planted"
    package.mkdir(exist_ok=True)
    (package / f"{name}.py").write_text(source, encoding="ascii", newline="\n")
    return package


#: Acceptance criterion 4, as a module. The program name exists nowhere in this
#: source as a literal, and the audit event carries it in full anyway.
PLANTED_ASSEMBLED_PROCESS_CONTROL = '''\
import subprocess


def probe(pid):
    program = "task" + "kill"
    subprocess.run([program, "/F", "/PID", str(pid)], capture_output=True)
    return True
'''

#: The forbidden cmdlet, also assembled, carried inside a shell string. This is
#: the one CLAUDE.md refuses outright rather than conditionally.
PLANTED_FORBIDDEN_CMDLET = '''\
import subprocess


def probe(pid):
    verb = "Stop-" + "Process"
    subprocess.run(["powershell", "-c", verb + " -Id " + str(pid)], capture_output=True)
    return True
'''

#: An unvetted program reached through ``os.system``, which carries a plain
#: string rather than a list and therefore exercises the other normaliser. The
#: target is spelled ``processid=<n>`` rather than as a separate flag, which is
#: what the ``=`` and ``:`` splitting in the probe's selector scan is for.
PLANTED_OS_SYSTEM = '''\
import os


def probe(pid):
    return getattr(os, "sys" + "tem")("w" + "mic process where processid=" + str(pid) + " delete")
'''

#: The same program naming its target by NAME rather than by pid. There is no
#: number for the our-child check to evaluate, so it is refused rather than
#: guessed at - which is the third entry in :data:`OWN_CHILD_LINE_LIMITS`,
#: written as a run instead of as a sentence.
PLANTED_TARGET_BY_NAME = '''\
import subprocess


def probe(pid):
    program = "task" + "kill"
    subprocess.run([program, "/F", "/IM", "a-name-this-file-never-started"], capture_output=True)
    return True
'''

#: The mirror: a module doing the legitimate thing, so the hook is shown to be
#: discriminating rather than merely hostile.
PLANTED_LEGITIMATE = '''\
import subprocess


def probe(root):
    done = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root, capture_output=True)
    return done.returncode == 0
'''


@WINDOWS_ONLY
def test_an_assembled_process_control_program_is_refused_against_a_foreign_pid(
    tmp_path: Path,
) -> None:
    """Acceptance criterion 4, and the refusing half of criterion 3.

    The pid handed in is the PROBE INTERPRETER'S OWN, which this file created
    and which is not in the probe's registry of children. So the command is
    refused, the spawn is aborted before the process exists, and nothing is
    terminated. The program name was built from two halves and the event
    carried the finished literal.
    """
    package = _plant(tmp_path, "assembled_control", PLANTED_ASSEMBLED_PROCESS_CONTROL)
    payload = run_probe(tmp_path, "assembled_control", "probe", "self", package)
    assert "refused by the Lanternlight runtime spawn probe" in payload["error"]
    assert payload["result"] == ""
    reasons = [reason for _event, reason, _line in payload["refused"]]
    assert reasons == ["process-control-outside-our-own-children"], payload["refused"]
    # The control: the source really is free of the literal, so a check that
    # collects names from source text would have found nothing to collect.
    assert "taskkill" not in PLANTED_ASSEMBLED_PROCESS_CONTROL
    assert "taskkill" in payload["refused"][0][2]


@WINDOWS_ONLY
def test_the_same_command_is_permitted_against_a_child_this_probe_started(
    tmp_path: Path,
) -> None:
    """The PERMITTING half of criterion 3, and the reason this guard survives.

    Identical source, identical program, identical flags. The only thing that
    changed is the pid, and it now names the sleeper the probe started and
    registered. CLAUDE.md names this exact command as the sanctioned way to end
    a process we started, so a guard that refused it would be a guard someone
    turns off.

    The sleeper really is ended, which is what makes the permitted branch
    non-vacuous: it was alive when the hook stopped recording and gone by the
    time the probe finished.
    """
    package = _plant(tmp_path, "assembled_control", PLANTED_ASSEMBLED_PROCESS_CONTROL)
    payload = run_probe(tmp_path, "assembled_control", "probe", "sleeper", package)
    assert payload["error"] == "", payload["error"]
    assert payload["refused"] == [], payload["refused"]
    verdicts = [(verdict, reason) for _event, _line, verdict, reason in payload["spawns"]]
    assert ("permit", "own-child-process-control") in verdicts, verdicts
    assert payload["sleeper_alive_after"] is False, (
        "the permitted command did not actually reach the sleeper, so the "
        "permitting branch passed without doing anything"
    )


@WINDOWS_ONLY
def test_the_forbidden_cmdlet_is_refused_even_against_our_own_child(tmp_path: Path) -> None:
    """CLAUDE.md forbids it outright, so the our-child question is never reached.

    This is the arm that proves the two rules are ordered rather than merged. A
    guard that only asked "is this our child" would have permitted this one.
    """
    package = _plant(tmp_path, "forbidden_cmdlet", PLANTED_FORBIDDEN_CMDLET)
    payload = run_probe(tmp_path, "forbidden_cmdlet", "probe", "sleeper", package)
    assert "refused by the Lanternlight runtime spawn probe" in payload["error"]
    reasons = [reason for _event, reason, _line in payload["refused"]]
    assert reasons == ["forbidden-cmdlet"], payload["refused"]
    assert payload["sleeper_alive_after"] is True, (
        "the sleeper died, so the refusal did not abort the spawn"
    )


@WINDOWS_ONLY
def test_an_unvetted_program_through_os_system_is_refused(tmp_path: Path) -> None:
    """The other normaliser: ``os.system`` carries a string, not a list.

    The program name is assembled here too, and the pid arrives welded to its
    selector by an ``=`` rather than as a separate argument, which the probe's
    selector scan splits apart. That detail is not a guess: the first run of
    this file asserted the target would be unreadable and the probe read it,
    so the expectation was corrected to what was measured rather than the
    probe being loosened to match the expectation.
    """
    package = _plant(tmp_path, "os_system", PLANTED_OS_SYSTEM)
    payload = run_probe(tmp_path, "os_system", "probe", "self", package)
    assert "refused by the Lanternlight runtime spawn probe" in payload["error"]
    events = [event for event, _reason, _line in payload["refused"]]
    assert events == ["os.system"], payload["refused"]
    reasons = [reason for _event, reason, _line in payload["refused"]]
    assert reasons == ["process-control-outside-our-own-children"], payload["refused"]
    assert "wmic" not in PLANTED_OS_SYSTEM
    assert "wmic" in payload["refused"][0][2]


@WINDOWS_ONLY
def test_a_target_named_by_image_rather_than_by_pid_is_refused(tmp_path: Path) -> None:
    """The third stated limit, as a run.

    There is no number on this command line, so the our-child check has
    nothing to evaluate and refuses instead of guessing. The sleeper pid is
    handed in and ignored by the planted module, which is the point: being
    handed a legitimate target does not help a command that does not name it.
    """
    package = _plant(tmp_path, "target_by_name", PLANTED_TARGET_BY_NAME)
    payload = run_probe(tmp_path, "target_by_name", "probe", "sleeper", package)
    assert "refused by the Lanternlight runtime spawn probe" in payload["error"]
    reasons = [reason for _event, reason, _line in payload["refused"]]
    assert reasons == ["process-control-without-a-pid-target"], payload["refused"]
    assert payload["sleeper_alive_after"] is True, (
        "the sleeper died, so the refusal did not abort the spawn"
    )


@WINDOWS_ONLY
def test_the_hook_is_not_refusing_everything(tmp_path: Path) -> None:
    """The mirror for the three refusals above.

    A hook that raised on every event would make each of them pass while
    proving nothing. This pins the other direction on a PLANTED module doing
    the legitimate thing, so the point is made without leaning on the
    repository staying clean.
    """
    package = _plant(tmp_path, "legitimate", PLANTED_LEGITIMATE)
    payload = run_probe(tmp_path, "legitimate", "probe", "root", package)
    assert payload["error"] == "", payload["error"]
    assert payload["refused"] == [], payload["refused"]
    assert payload["result"] == "True", payload["result"]
    verdicts = {reason for _event, _line, _verdict, reason in payload["spawns"]}
    assert verdicts == {"vetted-program"}, verdicts
    assert payload["sleeper_alive_after"] is True
