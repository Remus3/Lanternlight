"""No assertion in this repository may take the environment MAPPING as an operand.

WHY THIS GUARD EXISTS, and it is a measurement rather than a worry.

Clockspeed's 2026-09-20 1820 ACTION note reported a live-shaped provider API
key sitting in a world-readable scratch file, and traced it to a ``pytest``
assertion that rendered an environment mapping into a failure diff. Clockspeed
described the hazard as "an assertion whose operand is an environment mapping",
which reads like a warning about code that deliberately compares against
``os.environ``.

**Measured here 2026-09-20, and the real hazard is narrower and much easier to
miss than that description suggests.** The dangerous form is the one that names
a SINGLE variable and looks like the safest line in the file:

    assert "SOME_NAME" not in os.environ

A reader sees one environment variable named and concludes one environment
variable can be printed. ``pytest``'s assertion rewriting prints the whole
right-hand operand, so on failure that line renders EVERY variable and EVERY
value the process holds. Probed with a planted sentinel and a planted
admin-family key shape: the sentinel appeared three times in the failure
output, and the planted key was visible in the ``+ where`` line. The author
never wrote ``os.environ`` as a thing to be compared - they wrote a membership
test - and that is precisely why the form survives review.

The control probe in the same measurement:

    assert os.environ.get("SOME_NAME") == "expected"

rendered ONLY the retrieved value. The distinction is not "does the author
mention the environment", it is "does the MAPPING OBJECT reach an operand
position". So that is what this guard checks.

**The rule.** Inside an ``assert``, ``os.environ`` (or a bare ``environ``
imported from ``os``) may appear ONLY as the receiver of a ``.get(...)`` call
or as a subscript target. Anywhere else - a membership test, an equality, a
``len()``, a truthiness check - is refused, because every one of those puts the
mapping itself where the rewriter will print it.

**This guard is deliberately not a regex.** A line-oriented pattern is a claim
about line breaks, and this repository has already published a wrong answer
from one. The check parses the file and asks the tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests._tracked import REPO_ROOT, iter_scannable_files

#: Source files this guard reads. Python only - the hazard is an assertion
#: statement, which no other language in this tree has.
_SUFFIX = ".py"


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


def _aliases(tree: ast.AST) -> set[str]:
    """Names bound directly to the mapping, e.g. ``env = os.environ``.

    **An adversarial pass defeated this guard with two of these.** A check that
    knows only the spellings ``os.environ`` and ``environ`` is a check about
    SPELLING, and the rewriter does not care what the object is called - it is
    the same object and it renders identically. Collected per module rather
    than per function on purpose: an alias bound at module scope and used
    inside a test is the shape that would otherwise slip through.

    The honest limit, stated rather than discovered: this follows a direct
    binding only. An alias reached through a container, a function parameter,
    or a return value is not tracked, and no AST pass can do that soundly
    without type inference.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif (
            isinstance(node, ast.AnnAssign) and node.value is not None
        ) or isinstance(node, ast.NamedExpr):
            targets = [node.target]
        else:
            continue
        value = node.value
        if value is None or not _is_environ(value, frozenset()):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                found.add(target.id)
    return found


def _is_environ(node: ast.AST, aliases: frozenset[str] | set[str]) -> bool:
    """True for ``os.environ``, a bare ``environ``, or a known alias of either.

    All three reach the rewriter identically. ``from os import environ`` is not
    used in this tree today, and a guard that only knows the spelling currently
    in use is a guard that misses the first file written the other way.
    """
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    if isinstance(node, ast.Name):
        return node.id == "environ" or node.id in aliases
    return False


def _safe_parent(parent: ast.AST | None, child: ast.AST) -> bool:
    """True when this occurrence of the mapping cannot reach an operand.

    The two permitted shapes, and nothing else:

    - ``os.environ["NAME"]`` - a subscript, which yields one value.
    - ``os.environ.get(...)`` - an attribute access that is immediately called,
      which also yields one value.

    An attribute access that is NOT called - ``os.environ.copy`` passed as a
    callable, say - is refused, because the object still travels.

    **``.keys()`` WAS on this list for one commit and an adversarial pass took
    it off.** The reasoning that put it here was that a keys view yields no
    values. That reasoning was never measured, and it is wrong:
    ``os.environ.keys()`` reprs as ``KeysView(environ({...}))``, which carries
    every key AND every value. A planted key shape rendered four times through
    it - more than through the membership form this whole module exists to
    catch. The lesson is the repository's own: a safe-list entry admitted on
    reasoning rather than on a measurement is a hole with a comment over it.
    """
    if isinstance(parent, ast.Subscript) and parent.value is child:
        return True
    if isinstance(parent, ast.Attribute) and parent.value is child:
        return parent.attr == "get"
    return False


def find_violations(source: str, label: str = "<source>") -> list[str]:
    """Return one message per refused occurrence. Empty means clean.

    Exposed rather than inlined so the vacuity arms below can drive the real
    detector over synthetic sources instead of over a mock of it.
    """
    tree = ast.parse(source, filename=label)
    aliases = _aliases(tree)

    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for sub in ast.walk(node):
            if not _is_environ(sub, aliases):
                continue
            parent = parents.get(id(sub))
            # An attribute access that is called is safe only when the CALL is
            # what the assertion consumes; ``.get`` bare would still travel.
            if isinstance(parent, ast.Attribute) and _safe_parent(parent, sub):
                grandparent = parents.get(id(parent))
                if isinstance(grandparent, ast.Call) and grandparent.func is parent:
                    continue
            elif _safe_parent(parent, sub):
                continue
            found.append(
                f"{label}:{sub.lineno}: the environment MAPPING reaches an "
                "assert operand; pytest will render every variable and every "
                "value on failure. Use os.environ.get(NAME) instead."
            )
    return found


def test_no_published_python_file_asserts_on_the_environment_mapping():
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


def test_the_detector_flags_the_membership_form():
    """Vacuity arm: the exact form that was measured to leak.

    Without this, a detector that silently matched nothing would look identical
    to a clean tree.
    """
    bad = 'import os\n\n\ndef t():\n    assert "NAME" not in os.environ\n'
    found = find_violations(bad, "probe.py")
    assert len(found) == 1, found
    assert "probe.py:5" in found[0], found


@pytest.mark.parametrize(
    "source",
    [
        'import os\n\n\ndef t():\n    assert "NAME" in os.environ\n',
        "import os\n\n\ndef t():\n    assert os.environ == {}\n",
        "import os\n\n\ndef t():\n    assert not os.environ\n",
        "import os\n\n\ndef t():\n    assert len(os.environ) > 0\n",
        "from os import environ\n\n\ndef t():\n    assert environ\n",
        "import os\n\n\ndef t():\n    assert os.environ.copy\n",
        # ADVERSARIAL, 2026-09-20. ``.keys()`` was on this guard's OWN safe
        # list for one commit, on the reasoning that a keys view yields no
        # values. MEASURED and wrong: ``KeysView`` reprs as
        # ``KeysView(environ({...}))``, which carries keys AND values, and a
        # planted key shape rendered four times. That is WORSE than the form
        # this guard was built to catch, and the guard was permitting it.
        'import os\n\n\ndef t():\n    assert "NAME" in os.environ.keys()\n',
        "import os\n\n\ndef t():\n    assert not os.environ.keys()\n",
        # An ALIAS defeats any check that only knows two spellings. It is the
        # same object and the rewriter renders it identically.
        'import os\n\n\ndef t():\n    env = os.environ\n    assert "N" in env\n',
        "import os\n\n\ndef t():\n    env = os.environ\n    assert not env\n",
        'import os\n\n\ndef t():\n    e = os.environ\n    assert "N" in e.keys()\n',
        # This one was in the SAFE list until the alias arm above was added,
        # on the reasoning that binding the mapping outside an assert does not
        # render it. Half right: the BINDING does not, and the assertion does.
        # Measured - `seen = os.environ` then `assert seen is None` rendered a
        # planted sentinel twice. A second safe-list entry admitted on
        # reasoning rather than on a measurement, found the same day as the
        # first.
        "import os\n\n\ndef t():\n    seen = os.environ\n    assert seen is not None\n",
    ],
)
def test_the_detector_flags_every_operand_shape(source):
    assert find_violations(source, "probe.py"), source


@pytest.mark.parametrize(
    "source",
    [
        'import os\n\n\ndef t():\n    assert os.environ.get("NAME") == "x"\n',
        'import os\n\n\ndef t():\n    assert os.environ.get("NAME") is None\n',
        'import os\n\n\ndef t():\n    assert os.environ["NAME"] == "x"\n',
        # Binding the mapping is fine; it is reaching an assert OPERAND that is
        # not. Here the alias is subscripted, so one value is rendered.
        'import os\n\n\ndef t():\n    env = os.environ\n    assert env["N"] == "x"\n',
        'import os\n\n\ndef t():\n    env = os.environ\n    assert env.get("N") is None\n',
    ],
)
def test_the_detector_accepts_the_safe_shapes(source):
    assert find_violations(source, "probe.py") == [], source


def test_the_detector_reaches_its_own_file():
    """The walker must actually yield this module.

    A guard absent from its own population is a guard nobody has proved is
    reachable at all.
    """
    here = Path(__file__).resolve()
    assert here in {p.resolve() for p in _python_sources()}
