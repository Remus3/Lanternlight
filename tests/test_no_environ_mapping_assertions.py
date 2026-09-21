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


def _is_environ(node: ast.AST) -> bool:
    """True for ``os.environ`` and for a bare ``environ`` name.

    Both reach the rewriter identically. ``from os import environ`` is not used
    in this tree today, and a guard that only knows the spelling currently in
    use is a guard that misses the first file written the other way.
    """
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return isinstance(node, ast.Name) and node.id == "environ"


def _safe_parent(parent: ast.AST | None, child: ast.AST) -> bool:
    """True when this occurrence of the mapping cannot reach an operand.

    The two permitted shapes, and nothing else:

    - ``os.environ["NAME"]`` - a subscript, which yields one value.
    - ``os.environ.get(...)`` - an attribute access that is immediately called,
      which also yields one value.

    An attribute access that is NOT called - ``os.environ.copy`` passed as a
    callable, say - is refused, because the object still travels.
    """
    if isinstance(parent, ast.Subscript) and parent.value is child:
        return True
    if isinstance(parent, ast.Attribute) and parent.value is child:
        return parent.attr in {"get", "keys"}
    return False


def find_violations(source: str, label: str = "<source>") -> list[str]:
    """Return one message per refused occurrence. Empty means clean.

    Exposed rather than inlined so the vacuity arms below can drive the real
    detector over synthetic sources instead of over a mock of it.
    """
    tree = ast.parse(source, filename=label)

    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for sub in ast.walk(node):
            if not _is_environ(sub):
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
        # Outside an assert the mapping is not rendered by the rewriter.
        "import os\n\n\ndef t():\n    seen = os.environ\n    assert seen is not None\n",
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
