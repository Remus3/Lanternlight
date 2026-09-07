"""No inbox test may write the OPERATOR'S live records - one named exception.

WHY THIS FILE EXISTS
--------------------
``ops/inbox_watch.py`` keeps its state under ``ops/runtime/``, which is the real
channel's real memory. A test that writes there is not merely untidy: an
acknowledgement written by a fixture marks the operator's actual backlog as
read, and the mail the next session was supposed to be handed is gone. A test
that writes fixture NAMES there corrupts the withdrawal baseline, so real
withdrawals get lost among invented ones.

That is not hypothetical here. When the reported record was added, every test in
this family injected a throwaway ``state`` path and none of them knew a second
record existed, so the reported path still defaulted to the live one. The first
run wrote 93 fixture names into ``ops/runtime/inbox_reported.json``. It was
caught only because one of those names then leaked into an unrelated assertion -
in other words, by luck. A record that is write-only until something finally
reads it fails silently for exactly as long as nobody reads it.

TWO DEFENCES, ON PURPOSE
------------------------
The module now derives the reported path from the state path when only the state
path is given, so a caller cannot split the two records across a scratch
directory and the live one by accident. That fix lives in ``scan`` with the
reason written beside it.

This file is the second defence and it is STATIC: it reads the source of every
``tests/test_inbox_*.py`` and refuses a call into the watcher that does not name
a state path. A runtime check would only catch the tests that ran; this catches
the test somebody writes next.

THE ONE EXCEPTION IS NAMED, NOT INFERRED
----------------------------------------
``test_the_sessionstart_hook_command_really_runs_and_prints_the_report`` runs the
real hook command as a subprocess, because the thing under test IS the real
command string. It is allowed to touch the live records and is required to
snapshot and restore every one of them.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

#: Watcher entrypoints that read or write state.
ENTRYPOINTS = frozenset({"scan", "acknowledge_inbox", "main"})

#: The single test allowed to use the live records, by name. Adding to this set
#: is a decision, not a convenience: whatever you add must snapshot and restore
#: every record the watcher writes.
LIVE_BY_DESIGN = frozenset(
    {"test_the_sessionstart_hook_command_really_runs_and_prints_the_report"}
)


def _inbox_test_files() -> list[Path]:
    """Every test module that reaches the watcher, not every module named after it.

    The selector used to be the ``test_inbox_*.py`` glob alone, and ``OPS-43``
    walked straight past it: ``tests/test_outbox.py`` calls ``scan`` and
    ``acknowledge_inbox`` several times and matches no ``test_inbox_`` prefix,
    so the guard would have had nothing to say about it. A naming convention is
    not a membership test - the question this file asks is which modules TOUCH
    the watcher, so that is what is selected, by reading each module for an
    import of it. The glob is kept as well, because a module that names the
    watcher only in a docstring is still worth checking and costs milliseconds.
    """
    files = set(TESTS_DIR.glob("test_inbox_*.py"))
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - a listed file we cannot read
            continue
        if "inbox_watch" in text:
            files.add(path)
    assert files, "no inbox test modules were found - this guard would pass vacuously"
    return sorted(files)


def _calls_with_enclosing_function(tree: ast.AST):
    """Yield ``(function name, names a state path, Call node)`` for each call.

    "Names a state path" is decided over the whole enclosing function, not over
    the call, because ``main`` takes an argv LIST that tests build once and pass
    several times. Reading only the call site reported four false offenders on
    the first run of this guard.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        argv_flag = any(
            isinstance(inner, ast.Constant) and inner.value == "--state"
            for inner in ast.walk(node)
        )
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                yield node.name, argv_flag, inner


def _is_watcher_call(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in ENTRYPOINTS:
        value = func.value
        if isinstance(value, ast.Name) and value.id == "inbox_watch":
            return func.attr
    return None


def _names_a_state_path(call: ast.Call, attr: str, argv_flag: bool) -> bool:
    if attr == "main":
        return argv_flag
    return any(kw.arg == "state" for kw in call.keywords)


def test_every_inbox_test_injects_a_throwaway_state_path() -> None:
    offenders: list[str] = []
    checked = 0
    for path in _inbox_test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for owner, argv_flag, call in _calls_with_enclosing_function(tree):
            attr = _is_watcher_call(call)
            if attr is None or owner in LIVE_BY_DESIGN:
                continue
            checked += 1
            if not _names_a_state_path(call, attr, argv_flag):
                offenders.append(f"{path.name}::{owner} line {call.lineno} -> {attr}()")

    assert checked > 20, (
        f"only {checked} watcher calls were examined - the matcher stopped "
        "recognising them, so a clean result here means nothing"
    )
    assert not offenders, (
        "these calls fall back to the operator's live records under ops/runtime/, "
        "which is how a fixture marks the real backlog as read or poisons the "
        "withdrawal baseline:\n  " + "\n  ".join(offenders)
    )


def test_the_named_exception_still_exists_and_still_restores_both_records() -> None:
    """An allowlist entry that no longer exists is a hole nobody notices."""
    source = (TESTS_DIR / "test_inbox_watch.py").read_text(encoding="utf-8")
    for name in LIVE_BY_DESIGN:
        assert f"def {name}(" in source, f"the allowlisted test {name} no longer exists"

    start = source.index("def test_the_sessionstart_hook_command_really_runs")
    body = source[start : source.index("\ndef ", start + 1)]
    assert "default_state_path()" in body
    assert "default_reported_path()" in body, (
        "the one test allowed near the live records does not snapshot the "
        "reported record, so it would leave fixture names in the operator's "
        "withdrawal baseline"
    )


def test_the_two_records_travel_together_when_only_a_state_path_is_given(
    tmp_path: Path,
) -> None:
    """The module-level half of the fix, measured end to end.

    If a caller names a state file and nothing else, the reported file is its
    SIBLING. Defaulting it to ``ops/runtime/`` independently is what put 93
    fixture names into the operator's live record, and every existing test in
    this family is exactly that caller.
    """
    from ops import inbox_watch

    live = inbox_watch.default_reported_path()
    before = live.read_bytes() if live.is_file() else None

    inbox = tmp_path / "moon_sync_inbox"
    inbox.mkdir()
    (inbox / "note.md").write_bytes(b"# From RC - hi\n\nsent to LL.\n")
    state = tmp_path / "runtime" / "inbox_seen.json"

    inbox_watch.scan(inbox=inbox, state=state)

    sibling = state.parent / inbox_watch.REPORTED_FILENAME
    assert sibling.is_file(), "the reported record did not follow the state path"
    assert "note.md" in sibling.read_text(encoding="utf-8")

    after = live.read_bytes() if live.is_file() else None
    assert after == before, (
        "a fixture wrote into the operator's live reported record - the two "
        "records must travel together, see the comment in scan()"
    )
