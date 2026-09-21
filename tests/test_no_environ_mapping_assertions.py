"""The environment mapping may not appear inside an ``assert`` AT ALL.

WHY THIS GUARD EXISTS, and every number below was measured on this machine.

Clockspeed's 2026-09-20 1820 ACTION note reported a live-shaped provider API
key sitting in a world-readable scratch file, and traced it to a ``pytest``
assertion that rendered an environment mapping into a failure diff.

THIS MODULE HAS NOW BEEN WRONG TWICE ABOUT WHY, and the second version was
published to five sibling projects before it was measured properly. The history
is kept here rather than tidied away, because the shape of the mistake is worth
more than the rule it produced.

**First answer, wrong:** "the dangerous form is ``assert "X" not in os.environ``
and ``os.environ.get(...)`` is safe." Measured with a planted sentinel and the
``.get`` form leaks too.

**Second answer, also wrong:** "the axis is whether the MAPPING OBJECT reaches
an operand position, so a subscript or a ``.get`` receiver is safe." That
produced a SAFE LIST, and an adversarial pass then defeated the module three
times through entries on it - ``.keys()``, an alias, and a bound name.

**The measured answer, and it is about the OPERATOR rather than the operand.**
``pytest`` emits an ``E + where`` explanation chain for some comparisons and
not others, and when it emits one it walks back through every sub-expression
and reprs each, including the mapping - twice. Probed per form, each in its own
pytest process, at this suite's real verbosity::

    assert "X" not in os.environ                  LEAKS
    assert os.environ.get("ABSENT") == "x"        LEAKS
    assert os.environ.get("PRESENT") is None      LEAKS
    assert "X" not in os.environ.keys()           LEAKS  (worst, 4 renderings)
    assert not os.environ                         LEAKS
    assert cond, os.environ                       LEAKS  (the message half)
    assert os.environ.get("PRESENT") == "x"       clean
    assert os.environ["PRESENT"] == "x"           clean

Look at the last three against the third. **The same expression is safe or
unsafe depending on what is IN the environment at run time**: ``.get`` on a
present key is clean, ``.get`` on an absent key leaks, because ``None`` sends
``pytest`` down the ``+ where`` path and a string comparison does not. A rule
that calls a line safe on Tuesday and unsafe on Wednesday is not a rule anyone
can follow, and a guard encoding it would be a guard encoding a coincidence.

**So there is NO SAFE LIST.** Inside an ``assert`` - the test half and the
message half - the environment mapping may not be reached by any route. The
only permitted shape binds first::

    value = os.environ.get("NAME")
    assert value == "expected"

Measured clean, and clean STRUCTURALLY rather than by luck: the assert
expression holds a local name and nothing else, so there is no sub-expression
for the explanation chain to walk back into. ``value = os.environ["NAME"]``
then asserting on ``value`` is equally clean.

**THE LESSON IS THE SAFE LIST ITSELF.** Three defects, three safe-list entries,
every one admitted because the reasoning sounded right and none of them
measured. Every POSITIVE specimen in the first version had been measured; not
one NEGATIVE specimen had. That asymmetry is where all three lived. A guard
with no exemptions cannot be defeated through its exemptions.

**This guard is deliberately not a regex.** A line-oriented pattern is a claim
about line breaks, and this repository has published a wrong answer from one.
The check parses the file and asks the tree.

WHAT THIS GUARD IS BLIND TO, stated in the artifact because a caveat that lives
only in a chat message is a lie in the artifact:

- **It walks ``assert`` STATEMENTS only.** A ``unittest`` style
  ``self.assertIn("X", os.environ)`` is a CALL, is not walked, and was measured
  to leak worse than a bare assert because ``unittest`` does not use
  ``saferepr`` and renders the mapping whole. This tree contains no
  ``unittest.TestCase`` at all, measured, so the hole is currently unreachable
  here - but it is a hole, and a sibling reading this module should know.
- **Alias tracking follows a DIRECT binding only**, including a chain of them.
  An alias reached through a container, a function parameter or a return value
  is not tracked, and no AST pass can do that soundly without type inference.
- It reasons about ``os.environ``. Any other object whose repr carries secrets -
  a parsed ``.env``, a config mapping, a credential dict - has exactly the same
  hazard and this guard says nothing about it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests._tracked import REPO_ROOT, iter_scannable_files

#: Source files this guard reads. Python only - the hazard is an assertion
#: statement, which no other language in this tree has.
_SUFFIX = ".py"

_ADVICE = (
    "the environment mapping is reachable inside an assert; pytest's "
    "'+ where' chain reprs every sub-expression, mapping included. Bind it "
    "first - value = os.environ.get(NAME) - and assert on the local."
)


def _python_sources(root: Path = REPO_ROOT):
    """Every published Python file, this guard's own file included.

    Vendored code is excluded because a vendored file may not be edited - the
    honest response to a finding there is a NOTICE entry, not a fix, and
    ``CLAUDE.md`` says so.
    """
    for path in iter_scannable_files(root):
        if path.suffix != _SUFFIX:
            continue
        if "third_party" in path.parts:
            continue
        yield path


def _binds_environ(value: ast.AST, aliases: set[str]) -> bool:
    """Does this expression evaluate TO the mapping itself?

    Covers the four routes measured to reach it: the attribute ``os.environ``,
    a bare ``environ`` from ``from os import environ``, an existing alias
    (so a chain ``a = os.environ; b = a`` is followed), and the two dynamic
    lookups ``getattr(os, "environ")`` and ``os.__dict__["environ"]``.
    """
    if isinstance(value, ast.Attribute) and value.attr == "environ":
        return isinstance(value.value, ast.Name) and value.value.id == "os"
    if isinstance(value, ast.Name):
        return value.id == "environ" or value.id in aliases
    if isinstance(value, ast.Call):
        func = value.func
        if (
            isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(value.args) >= 2
            and isinstance(value.args[1], ast.Constant)
            and value.args[1].value == "environ"
        ):
            return True
    if isinstance(value, ast.Subscript):
        target = value.value
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "__dict__"
            and isinstance(value.slice, ast.Constant)
            and value.slice.value == "environ"
        ):
            return True
    return False


def _aliases(tree: ast.AST) -> set[str]:
    """Names bound to the mapping, following chains to a fixed point.

    Per module rather than per function: an alias bound at module scope and
    used inside a test is the shape that would otherwise slip through. The
    fixed-point loop is what an adversarial pass required - one pass catches
    ``a = os.environ`` and misses ``b = a``.

    ``from os import environ as e`` is picked up here too, since that is also
    a binding of the name ``e`` to the mapping.
    """
    found: set[str] = set()
    for _ in range(8):  # a chain deeper than this is not real code
        before = len(found)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                for alias in node.names:
                    if alias.name == "environ":
                        found.add(alias.asname or alias.name)
                continue
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif (
                isinstance(node, ast.AnnAssign) and node.value is not None
            ) or isinstance(node, ast.NamedExpr):
                targets = [node.target]
            else:
                continue
            if node.value is None or not _binds_environ(node.value, found):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
        if len(found) == before:
            break
    return found


def find_violations(source: str, label: str = "<source>") -> list[str]:
    """Return one message per refused occurrence. Empty means clean.

    Exposed rather than inlined so the specimen arms below drive the REAL
    detector rather than a mock of it.
    """
    tree = ast.parse(source, filename=label)
    aliases = _aliases(tree)

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        # Both halves. The message half was measured to leak too, and it is
        # the half an author writes while trying to be helpful.
        for half in (node.test, node.msg):
            if half is None:
                continue
            for sub in ast.walk(half):
                if _binds_environ(sub, aliases):
                    found.append(f"{label}:{sub.lineno}: {_ADVICE}")
    return found


def test_no_published_python_file_reaches_the_environment_inside_an_assert():
    """The guard itself, over the real tree."""
    violations: list[str] = []
    scanned = 0
    for path in _python_sources():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        violations.extend(find_violations(source, rel))

    # A scan that reached nothing is not a pass. Floor measured well below the
    # real population so an added file never reds this, while a walker that
    # silently stops yielding does.
    assert scanned >= 50, (
        f"the walker yielded only {scanned} Python files - the scan did not "
        "run, so this guard has not testified about anything"
    )
    assert not violations, "\n".join(violations)


#: Every form MEASURED to render environment values into a pytest failure, plus
#: the evasions an adversarial pass found. Each was probed in its own pytest
#: process with two sentinels placed at the tail of the insertion-ordered
#: environment, because ``saferepr`` elides the middle and a badly placed
#: sentinel reports a real leak as clean.
_LEAKING = [
    'import os\n\n\ndef t():\n    assert "NAME" not in os.environ\n',
    'import os\n\n\ndef t():\n    assert "NAME" in os.environ\n',
    "import os\n\n\ndef t():\n    assert os.environ == {}\n",
    "import os\n\n\ndef t():\n    assert not os.environ\n",
    "import os\n\n\ndef t():\n    assert len(os.environ) > 0\n",
    "from os import environ\n\n\ndef t():\n    assert environ\n",
    "import os\n\n\ndef t():\n    assert os.environ.copy\n",
    'import os\n\n\ndef t():\n    assert "NAME" in os.environ.keys()\n',
    "import os\n\n\ndef t():\n    assert not os.environ.keys()\n",
    # Formerly on this module's own SAFE list. Both measured to leak.
    'import os\n\n\ndef t():\n    assert os.environ.get("NAME") == "x"\n',
    'import os\n\n\ndef t():\n    assert os.environ.get("NAME") is None\n',
    'import os\n\n\ndef t():\n    assert os.environ["NAME"] == "x"\n',
    # Aliases, including a CHAIN of them.
    'import os\n\n\ndef t():\n    env = os.environ\n    assert "N" in env\n',
    "import os\n\n\ndef t():\n    env = os.environ\n    assert not env\n",
    'import os\n\n\ndef t():\n    a = os.environ\n    b = a\n    assert "N" in b\n',
    'from os import environ as e\n\n\ndef t():\n    assert "N" in e\n',
    # Dynamic lookups.
    'import os\n\n\ndef t():\n    env = getattr(os, "environ")\n    assert not env\n',
    'import os\n\n\ndef t():\n    assert not getattr(os, "environ")\n',
    'import os\n\n\ndef t():\n    e = os.__dict__["environ"]\n    assert not e\n',
    # The MESSAGE half, measured to leak and easy to miss.
    "import os\n\n\ndef t():\n    assert False, os.environ\n",
    'import os\n\n\ndef t():\n    env = os.environ\n    assert False, f"{env}"\n',
]

#: The only shape this guard permits, and it is permitted STRUCTURALLY: the
#: assert expression holds a local name, so there is no sub-expression for
#: pytest's explanation chain to walk back into. Both were measured clean.
_SAFE = [
    'import os\n\n\ndef t():\n    value = os.environ.get("N")\n    assert value == "x"\n',
    'import os\n\n\ndef t():\n    value = os.environ["N"]\n    assert value == "x"\n',
    # Binding alone is not an assertion and is not this guard's business.
    "import os\n\n\ndef t():\n    env = os.environ\n    del env\n",
    # An unrelated assert in a module that happens to import os.
    'import os\n\n\ndef t():\n    assert os.sep == "/"\n',
]


@pytest.mark.parametrize("source", _LEAKING)
def test_every_leaking_form_is_flagged(source):
    assert find_violations(source, "probe.py"), source


@pytest.mark.parametrize("source", _SAFE)
def test_the_permitted_shapes_are_accepted(source):
    assert find_violations(source, "probe.py") == [], source


def test_the_detector_reports_the_line_and_the_fix():
    """A finding has to say where it is and what to do about it."""
    bad = 'import os\n\n\ndef t():\n    assert "NAME" not in os.environ\n'
    found = find_violations(bad, "probe.py")
    assert len(found) == 1, found
    assert "probe.py:5" in found[0], found
    assert "os.environ.get(NAME)" in found[0], found


def test_there_is_no_safe_list_to_attack():
    """The design claim, asserted so it cannot be softened back in.

    Three defects in this module came from safe-list entries. If a future
    change reintroduces one, this arm is the thing that should have to be
    deleted deliberately rather than eroded quietly.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    assert "_safe_parent" not in names, (
        "a per-occurrence exemption helper is back. Three separate defects in "
        "this module were entries on its safe list; the guard has none now, "
        "and reintroducing one needs a measurement, not a rationale."
    )


def test_the_detector_reaches_its_own_file():
    """The walker must actually yield this module.

    A guard absent from its own population is a guard nobody has proved is
    reachable at all.
    """
    here = Path(__file__).resolve()
    assert here in {p.resolve() for p in _python_sources()}
