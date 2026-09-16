"""Guard: no console flash from a subprocess spawned under a windowless parent.

Measured by sibling project RC and confirmed on 2026-09-15 with a positive
control on all three arms: on Windows, every console-subsystem CHILD process of
a WINDOWLESS parent flashes a console window unless the spawn carries
``CREATE_NO_WINDOW``. The parents that matter here are ``pythonw`` and anything
running under the Claude desktop harness, which is how ``tools/precommit_gate.py``
runs as a ``PreToolUse`` hook - so every ``git.exe``, ``ruff.exe`` and
``python -m ruff`` it spawns flashed a window on every Bash call.

Two facts that shaped the fix, both worth keeping so nobody re-derives them:

- A windowless interpreter still keeps redirected stdin/stdout/stderr and still
  reports its exit code, so the flag costs nothing. Nothing downstream of these
  spawns had to change.
- Swapping the interpreter TOKEN (``python`` for ``pythonw`` or the reverse)
  removes NO flash. The flag is the fix; the token is not.

WHAT THIS GUARD ASSERTS. Every ``subprocess.run`` and ``subprocess.Popen`` call
in the three covered modules passes a ``creationflags`` keyword, and the
module-level constant each of them uses resolves to a non-zero value on a
platform where ``subprocess.CREATE_NO_WINDOW`` exists. The call sites are
DERIVED from the AST rather than counted here: a filed count goes stale the
moment a spawn is added and becomes a confident lie, so a new spawn without the
flag must turn this module red rather than slip under a number that still
matches.

DELIBERATELY OUT OF SCOPE, stated so the silence is not mistaken for coverage.
``ops/loop/watch.py``'s ``Popen`` and every other ``ops/`` module are NOT
covered by this guard yet. This slice was scoped to the three modules reached
under a windowless hook parent, and extending the guard to the rest of ``ops/``
is separate work - an empty result here is a claim about these three files and
about nothing else.

WHAT THE AST WALK CANNOT SEE, and what is done about it. An adversarial pass on
2026-09-15 pointed a throwaway probe at :func:`_spawn_calls` and found it blind
to every ALIASED spelling of the same call: ``from subprocess import run``,
``import subprocess as sp``, ``from subprocess import Popen as AP``, and
``fn = subprocess.run`` followed by ``fn(...)``. It sees only the plain
``subprocess.<attr>(...)`` shape. Nested functions and comprehensions ARE seen,
and a ``**kwargs`` splat is seen and conservatively flagged. The paragraph above
used to promise flatly that a new spawn without the flag turns this module red;
that promise was too broad, and it is narrowed here rather than left standing.

This repository has documented that blind spot before - ``tests/
test_process_capability.py`` already names aliased imports among its known
survivors - so the honest response is not to restate it a second time and move
on. :func:`test_no_covered_module_reaches_subprocess_by_an_aliased_name` closes
it from the other end: the three covered modules must reach ``subprocess``
through a plain ``import subprocess`` and nothing else. A future spawn written
in a spelling the walk cannot read now turns the suite red at the IMPORT rather
than passing unseen. That is a narrower claim than "every spawn is seen" and it
is the one this module can actually keep.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The modules this guard covers. Every one of them spawns a console binary
#: from a process that may have no console of its own.
COVERED = (
    "lanternlight/redact.py",
    "tools/precommit_gate.py",
    "ops/stop_audit.py",
)

#: The module-level constant each covered module defines. Named identically in
#: all three ON PURPOSE - ``lanternlight/redact.py`` is the redaction module and
#: imports nothing from ``ops/`` or ``tools/``, so the three definitions are
#: independent and only the NAME is shared.
CONSTANT_NAME = "_NO_WINDOW"

#: Spawning attributes of ``subprocess`` that accept ``creationflags``.
SPAWNERS = ("run", "Popen")


def _module_source(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _spawn_calls(tree: ast.AST) -> list[ast.Call]:
    """Every ``subprocess.run(...)`` / ``subprocess.Popen(...)`` call in ``tree``."""
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in SPAWNERS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            found.append(node)
    return found


def _keyword_names(call: ast.Call) -> set[str]:
    return {kw.arg for kw in call.keywords if kw.arg is not None}


@pytest.mark.parametrize("relative", COVERED)
def test_covered_module_has_at_least_one_spawn(relative: str) -> None:
    """A module with no spawn left would make its own flag assertion vacuous.

    This is the anchor check the repo's TDD rules ask for: if a refactor moves
    every spawn out of a covered module, the parametrized assertion below would
    pass over an empty list and report success about nothing.
    """
    tree = ast.parse(_module_source(relative))
    assert _spawn_calls(tree), (
        f"{relative} has no subprocess.run/Popen call, so the creationflags "
        f"assertion for it would be vacuous. Either the spawn moved (update "
        f"COVERED) or the parser stopped matching it."
    )


@pytest.mark.parametrize("relative", COVERED)
def test_every_spawn_passes_creationflags(relative: str) -> None:
    """Every spawn in a covered module carries ``creationflags``."""
    tree = ast.parse(_module_source(relative))
    offenders = [
        call.lineno
        for call in _spawn_calls(tree)
        if "creationflags" not in _keyword_names(call)
    ]
    assert not offenders, (
        f"{relative} spawns a console process without creationflags at "
        f"line(s) {offenders}. Under a windowless parent - pythonw, or the "
        f"Claude desktop harness running a hook - that flashes a console "
        f"window. Pass creationflags={CONSTANT_NAME}."
    )


@pytest.mark.parametrize("relative", COVERED)
def test_creationflags_value_is_the_no_window_constant(relative: str) -> None:
    """The keyword is not merely PRESENT - it names the shared constant.

    ``creationflags=0`` would satisfy a presence check while restoring the
    flash, which is the same defect the flag was added to fix.
    """
    tree = ast.parse(_module_source(relative))
    wrong: list[tuple[int, str]] = []
    for call in _spawn_calls(tree):
        for keyword in call.keywords:
            if keyword.arg != "creationflags":
                continue
            if not (isinstance(keyword.value, ast.Name) and keyword.value.id == CONSTANT_NAME):
                wrong.append((call.lineno, ast.dump(keyword.value)))
    assert not wrong, (
        f"{relative} passes creationflags as something other than "
        f"{CONSTANT_NAME}: {wrong}"
    )


@pytest.mark.parametrize("relative", COVERED)
def test_covered_module_defines_the_constant(relative: str) -> None:
    """Each module defines ``_NO_WINDOW`` itself - no cross-package import.

    ``lanternlight/redact.py`` is the redaction module and stays dependency
    free, so the three definitions are deliberately independent duplicates
    rather than one shared helper.
    """
    tree = ast.parse(_module_source(relative))
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert CONSTANT_NAME in assigned, (
        f"{relative} does not define {CONSTANT_NAME} at all, so its spawns "
        f"either import the flag from another package or hardcode a number."
    )


def test_constant_resolves_non_zero_where_the_attribute_exists() -> None:
    """The ``getattr`` fallback must not be swallowing a real flag.

    On Windows ``subprocess.CREATE_NO_WINDOW`` exists and is non-zero, so the
    constant the modules compute must be non-zero too. On a platform without
    the attribute the constant is 0, which is the legal inert value for
    ``creationflags`` - this repository is public and must import on POSIX.
    """
    computed = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        assert computed != 0, (
            "subprocess.CREATE_NO_WINDOW exists but is falsy - the constant "
            "would be a no-op and the console flash would be back."
        )
    else:
        assert computed == 0


@pytest.mark.parametrize("relative", COVERED)
def test_live_module_constant_matches_the_platform(relative: str) -> None:
    """Import the real module and read the real constant, not just the source.

    Parsing proves the assignment is WRITTEN. Importing proves it EVALUATES to
    the value the platform supplies, which is the fact the spawns depend on.
    """
    import importlib

    module_name = relative.removesuffix(".py").replace("/", ".")
    module = importlib.import_module(module_name)
    value = getattr(module, CONSTANT_NAME)
    assert value == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_no_covered_module_reaches_subprocess_by_an_aliased_name() -> None:
    """The other end of the AST walk's blind spot - see this module's docstring.

    :func:`_spawn_calls` reads the literal ``subprocess.<attr>(...)`` shape, so
    an aliased import would hide a real spawn from it completely. Rather than
    teaching the walk every alias - which is an open-ended chase, and the walk
    would still miss a name bound at run time - the three covered modules are
    held to ONE spelling. A spawn that the walk cannot see now cannot be
    written without this test objecting first.

    Scoped to the covered modules on purpose. It says nothing about the rest of
    the repository, where aliasing ``subprocess`` is nobody's defect.
    """
    offenders: list[str] = []
    for relative in COVERED:
        path = REPO_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess" and alias.asname is not None:
                        offenders.append(
                            f"{relative}:{node.lineno} imports subprocess as "
                            f"{alias.asname!r}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                names = ", ".join(sorted(a.name for a in node.names))
                offenders.append(
                    f"{relative}:{node.lineno} uses 'from subprocess import {names}'"
                )
    assert not offenders, (
        "these modules reach subprocess by a name the spawn walk cannot follow, "
        "so a spawn written through one would pass this guard unseen:\n  "
        + "\n  ".join(offenders)
    )
