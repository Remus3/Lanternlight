"""Record which test module really opens which tracked document.

ROADMAP ``OPS-31``. ``ops/docguards.py`` derives that set STATICALLY, by
reading each module's source for a doc name or a doc-walking idiom. This file
derives it a second time and by a completely different route: a
:func:`sys.addaudithook` hook that watches real ``open`` events during the run.

Two derivations is the point. The static pass cannot see a path assembled at
run time and cannot see an idiom nobody enumerated; the audit hook cannot see a
module that was never run. Where they disagree, the pre-commit hook refuses -
:func:`ops.docguards.coverage_gap` is that comparison, and a non-empty result
means the selector has a hole rather than that the recorder is noisy.

WHAT IS WRITTEN, AND WHEN. At session finish, and only when the run was
COMPLETE - every ``tests/test_*.py`` on disk actually ran and no ``-k`` or
``-m`` filter narrowed it. A partial run leaves the previous map alone on
purpose: the pre-commit hook itself runs a SUBSET, and a subset that clobbered
the map would erase the very evidence the next commit is checked against. The
map lands under ``ops/runtime/``, which is gitignored, through
:func:`ops.docguards.write_observed` - a temporary plus ``replace``, so a hook
polling it never reads half a file.

COST. An audit hook cannot be removed once added and it fires on EVERY audited
event in the process, so the body is a string compare and an early return
before anything else happens. It was measured before it shipped, full suite,
both ways - see ``ROADMAP.md`` ``OPS-31`` and the ledger entry that landed it
for the two wall-clock numbers. Re-measure before adding anything to the body.

THE HOOK NEVER RAISES. An exception inside an audit hook aborts the operation
that triggered it, so a bug here would break every ``open`` in the process
rather than losing one record. The body therefore swallows everything - which
does mean a broken recorder is SILENT, and that is why
``tests/test_docguards.py`` opens a tracked document and asserts the recorder
noticed. Without that test this file would be indistinguishable from
decoration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import docguards  # noqa: E402


class DocOpenRecorder:
    """Real opens of tracked documents, attributed to the module in scope."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.installed = False
        self.current = docguards.SESSION_KEY
        self.observed: dict[str, set[str]] = {}
        self.modules_run: set[str] = set()
        # Absolute, lowercased, so a comparison is one dict lookup. Windows is
        # case-insensitive and pytest hands paths back in whatever case the
        # caller typed; lowercasing both sides is cheaper than asking the
        # filesystem what a path really is, on every open.
        self.docs = {
            str(root / rel).lower(): rel for rel in docguards.tracked_docs(root)
        }

    def note(self, path: str) -> None:
        rel = self.docs.get(str(Path(path).resolve()).lower())
        if rel is None:
            return
        self.observed.setdefault(self.current, set()).add(rel)

    def observed_for(self, module: str) -> set[str]:
        return set(self.observed.get(module, ()))

    def observed_modules(self) -> list[str]:
        return sorted(self.observed)

    def as_payload(self, complete: bool, exitstatus: int, args: list[str]) -> dict:
        return {
            "complete": complete,
            "exitstatus": int(exitstatus),
            "args": list(args),
            "root": str(self.root.resolve()),
            "modules": {
                name: sorted(docs) for name, docs in sorted(self.observed.items())
            },
            "modules_run": sorted(self.modules_run),
            "test_module_digests": docguards.test_module_digests(self.root),
        }


_RECORDER = DocOpenRecorder(REPO_ROOT)


def _audit(event: str, args: tuple) -> None:
    # Cheapest possible reject first. Every audited event in the process comes
    # through here, so anything above this line is a tax on the whole run.
    if event != "open":
        return
    try:
        path = args[0]
        if type(path) is not str or not path.endswith(".md"):
            return
        _RECORDER.note(path)
    except Exception:  # see the module docstring
        return


if not _RECORDER.installed:
    sys.addaudithook(_audit)
    _RECORDER.installed = True


@pytest.fixture
def docguard_recorder() -> DocOpenRecorder:
    """The live recorder, so a test can prove it is not decoration."""
    return _RECORDER


def pytest_collectstart(collector) -> None:
    nodeid = getattr(collector, "nodeid", "") or ""
    head = nodeid.split("::")[0]
    if head.endswith(".py"):
        _RECORDER.current = head


def pytest_runtest_logstart(nodeid, location) -> None:
    head = nodeid.split("::")[0]
    _RECORDER.current = head
    _RECORDER.modules_run.add(head)


def _run_was_complete(config) -> bool:
    """True only when every test module on disk ran, unfiltered.

    A run that was narrowed cannot say anything about the modules it skipped,
    and a map that claimed otherwise would be worse than no map.
    """
    option = config.option
    if getattr(option, "keyword", "") or getattr(option, "markexpr", ""):
        return False
    tests_dir = REPO_ROOT / "tests"
    on_disk = {
        path.relative_to(REPO_ROOT).as_posix() for path in tests_dir.glob("test_*.py")
    }
    return bool(on_disk) and on_disk <= _RECORDER.modules_run


def pytest_sessionfinish(session, exitstatus) -> None:
    try:
        if not _run_was_complete(session.config):
            return
        docguards.write_observed(
            _RECORDER.as_payload(
                complete=True,
                exitstatus=int(exitstatus),
                args=list(session.config.invocation_params.args),
            ),
            REPO_ROOT,
        )
    except Exception:
        # A failure to persist must not turn a green suite red. The pre-commit
        # hook refuses on an absent or stale map, so the consequence of losing
        # this write is a refused commit with a message naming the map - loud,
        # and in the place where it matters.
        return
