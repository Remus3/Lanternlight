"""PostToolUse hook: say so at once when an edit leaves a .py unparseable.

ROADMAP ``OPS-37`` criterion 1.

WHY THIS EXISTS. A hook in this repository runs under a windowless interpreter,
so an edit that leaves a Python file syntactically broken produces no signal of
any kind. Nothing complains until some later ``python -m pytest`` trips over the
file, by which time the context that produced the breakage - which edit, to
which line, and what it was trying to do - is gone. Compiling the file the
moment it is written moves that discovery back to where it is cheap.

WHAT IT IS NOT. It is not a linter, not a type check, and not a gate. It parses
the file and reports; it decides nothing. ``python -m pytest`` and the
``.githooks`` scripts remain the authoritative checks.

IT ALWAYS EXITS 0. A ``PostToolUse`` hook that exits non-zero breaks the session
it runs in, and an advisory check that wedges the operator is strictly worse
than no check at all - it gets disabled, and then nothing is checked. This is
the same fail-soft contract ``tools/ascii_check.py`` and ``ops/inbox_watch.py``
already carry: report on stderr, return 0, and swallow every surprise. Note the
consequence and do not file it as a defect later: a hook that fails is silent
about its own failure by design, so this file must stay simple enough that its
failure modes are the interpreter's rather than its own.

THE SAFETY NET MUST NOT ITSELF BE ABLE TO RAISE. A refutation pass measured
this file exiting 1 on ``<payload> | python tools/syntax_check_hook.py 2>&-``:
the reporting write failed because closing a standard fd before the
interpreter starts makes ``sys.stderr`` ``None`` (measured with
``python -c "print(repr(sys.stderr))" 2>&-``) rather than a live-but-erroring
stream object, and the ``except Exception`` handler that exists to make
failure safe then tried to write ITS OWN diagnostic to that same ``None`` and
raised ``AttributeError`` doing it, uncaught. ``pythonw.exe`` - which runs the
sibling hooks in this same settings file - leaves ``sys.stderr`` exactly the
same ``None`` for a different reason (no console attached), so this is not a
closed-fd-only concern. A stderr wired to a PIPE whose reader has already
exited is a THIRD, distinct failure mode: the stream is live and valid right
up until the write, which raises only then.

Two changes close all three. First, ``emit_report`` is the only thing in this
file that touches ``sys.stderr``, and it treats ``None``, a closed stream, and
a broken pipe as equally routine - it never raises, by construction, not by
accident. Second, the process terminates via ``os._exit(0)`` in a ``finally``,
not ``sys.exit(0)``. Measured directly: a script that writes to a stderr PIPE
whose reader has already exited, guards that write in try/except, and then
calls ``sys.exit(0)`` still exits **120**, not 0 - normal interpreter shutdown
(``Py_FinalizeEx``) performs its OWN unconditional flush of stdout/stderr, and
a failure in THAT flush, not in this module's own code, is what sets the exit
status regardless of what was passed to ``sys.exit``. ``os._exit(0)`` skips
that shutdown sequence entirely, which is the only way this file can actually
keep its "always exits 0" promise when the dead stream is a broken pipe rather
than a closed descriptor. The cost - no atexit handlers run, nothing left
buffered gets flushed - is accepted deliberately: ``emit_report`` already
flushes explicitly, so a healthy stream still gets the report before exit.

IT NEVER WRITES BESIDE THE SOURCE. ``py_compile`` drops a ``.pyc`` into a
``__pycache__`` next to the file it compiled unless told otherwise, and a hook
that litters the repository on every edit would be reverted within the day. The
compile target is therefore a temporary directory that is removed on the way
out, whatever the outcome.

Standard library only. A hook the harness runs on every edit is not the place
to acquire a dependency.
"""

from __future__ import annotations

import json
import os
import py_compile
import sys
import tempfile
from pathlib import Path

#: Keys a PostToolUse payload may carry the edited path under. Write and Edit
#: use ``file_path``; the notebook editor uses ``notebook_path``. Reading both
#: costs nothing and means a payload shape we did not anticipate degrades to
#: silence rather than to a wrong answer about some other file.
PATH_KEYS = ("file_path", "notebook_path")

#: Printed at the head of every report. The file name and the line number are
#: NOT enough on their own to prove this hook spoke: ``py_compile`` prints its
#: own message containing both when it is not raising. ``tests/`` asserts this
#: marker for exactly that reason - see that module's docstring.
MARKER = "SYNTAX ERROR"


def read_payload(stream) -> dict:
    """The hook payload as a dict, or an empty one for anything unusable.

    Unparseable stdin, an empty stream and well-formed JSON that simply is not
    an object all land here as ``{}``. Every one of them is a normal thing for
    a harness to hand a hook, and none of them is worth a word on stderr.
    """
    try:
        payload = json.load(stream)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def target_path(payload: dict) -> Path | None:
    """The edited file named by ``payload``, or None when it names none."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for key in PATH_KEYS:
        raw = tool_input.get(key)
        if isinstance(raw, str) and raw.strip():
            return Path(raw)
    return None


def describe(path: Path) -> str | None:
    """A one-line report for an unparseable ``path``, or None when it compiles.

    The compile target is a temporary directory rather than the default
    ``__pycache__`` beside the source, so nothing is left in the tree. An
    ``OSError`` - the file was moved, renamed or deleted after the edit - is not
    a syntax error and draws no report.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="ll_syntax_check_") as tmpdir:
            cfile = Path(tmpdir) / "checked.pyc"
            py_compile.compile(str(path), cfile=str(cfile), doraise=True)
    except py_compile.PyCompileError as err:
        return format_error(path, err)
    except OSError:
        return None
    return None


def format_error(path: Path, err: py_compile.PyCompileError) -> str:
    """Name the file, the line and the compiler's own words, on one line."""
    cause = getattr(err, "exc_value", None)
    lineno = getattr(cause, "lineno", None)
    message = getattr(cause, "msg", None) or str(cause) or "could not be compiled"
    where = f"line {lineno}" if isinstance(lineno, int) else "line unknown"
    return (
        f"{MARKER} in {path}: {where}: {message}. "
        "The file as written will not import and will fail collection. "
        "Fix it now, while the edit that caused it is still in view."
    )


def emit_report(message: str) -> None:
    """Write ``message`` to stderr. Never raises, whatever stderr turns out to be.

    By the time this runs, ``sys.stderr`` is whatever the process that spawned
    us decided it should be: a live console, ``None`` (no console attached -
    ``pythonw.exe``, or any interpreter started with a standard handle the OS
    already considered invalid before it started), a stream object whose
    underlying descriptor has since been closed, or a stream wired to a pipe
    whose reader has already gone. Every one of those is ordinary, not
    exotic, and none of them is allowed to turn an advisory report into a
    crash. The one thing this function does NOT swallow is a healthy write
    succeeding - the report still reaches a stream that works; only the ways
    it can fail are hidden.
    """
    try:
        stream = sys.stderr
        if stream is None:
            return
        stream.write(message)
        stream.flush()
    except Exception:
        pass


def main() -> int:
    """Report on stderr and return 0. It returns 0 on every path, deliberately."""
    path = target_path(read_payload(sys.stdin))
    if path is None:
        return 0
    if path.suffix.lower() != ".py":
        return 0
    report = describe(path)
    if report is None:
        return 0
    emit_report(report + "\n")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # an advisory hook must never wedge the session
        emit_report(f"syntax_check_hook soft-failed: {exc}\n")
    finally:
        # os._exit, not sys.exit: sys.exit(0) still runs normal interpreter
        # shutdown, which performs its OWN unconditional flush of
        # stdout/stderr - and if that stream is a broken pipe, THAT flush
        # failure is what decides the exit status, regardless of what
        # sys.exit was given. Measured: a script that writes to a broken
        # stderr pipe, guards the write in try/except, and then calls
        # sys.exit(0) still exits 120, not 0. os._exit(0) skips the shutdown
        # sequence entirely, so it is the only one of the two that actually
        # delivers "always exits 0" here. There is deliberately no special
        # case for SystemExit above: whatever happens in the try or except
        # block, this finally is the one place that decides the process
        # exit status, and it always decides 0.
        os._exit(0)
