"""Pytest plugin - name the TEST that wrote a path in the operator's live tree.

Load it with `-p lw_write_tracer` (this file's directory on `PYTHONPATH`), then
say what counts as live and where the report goes::

    pytest tests/ -p lw_write_tracer --trace-roots "ops/runtime;logs" \
        --trace-out trace.json

`LW_TRACE_ROOTS` and `LW_TRACE_OUT` are accepted as a fallback for a runner
that cannot add flags. Roots are separated by `os.pathsep`, or the option may
be repeated. Importing this module patches nothing; all patching happens in
`pytest_configure` and is undone in `pytest_unconfigure`.

WHY NOT A BEFORE-AND-AFTER SNAPSHOT DIFF
----------------------------------------
Because it does not work on a machine like this one, and it fails in the
direction that produces confident wrong answers. Measured 2026-09-11: an IDLE
control of 300 seconds with NO suite running anywhere showed four candidate
files changing regardless - a heartbeat daemon holding one of them open, and
other sessions working the same trees. A file that changed during a suite run
has at least two plausible authors, so the diff attributes NOTHING. Two of the
first three conclusions drawn that way had to be withdrawn.

This plugin is PROCESS-LOCAL. If an event is recorded here, THIS pytest process
performed it, and no daemon or parallel session can contaminate that.

THE FOUR ROUTES, AND WHY ALL FOUR ARE NEEDED
--------------------------------------------
`builtins.open`  - the ordinary write.
`io.open`        - a SEPARATE binding. `builtins.open is io.open` is true, yet
                   `pathlib` calls `io.open(...)` by attribute lookup, so
                   patching only `builtins` misses every `Path.write_text`,
                   `Path.write_bytes` and `Path.open`. That was a real hole in
                   the first version of this tracer.
`os.replace` and
`os.rename`      - the tmp-then-replace route. An open() wrapper is blind to it
                   because the only open it sees carries the TMP name, and a
                   codebase that mandates atomic writes uses this route for
                   exactly the state files worth protecting.

BYTES, NOT OPENS. Opening a file for append is not writing to it: a logging
`FileHandler` opens on construction and may emit nothing. Those land in
`opened_for_write_only` instead, because reporting them as writes overstates
the defect, and an overstated finding gets dismissed whole.

KNOWN LIMIT - SUBPROCESS WRITES ARE NOT SEEN
--------------------------------------------
Only this interpreter is instrumented. A test that shells out to a child which
writes a live path is invisible here, so any number this produces is a LOWER
BOUND for a suite that spawns processes. The limit is asserted by an arm in
`tests/test_lw_write_tracer.py` rather than merely written down, so that
closing it forces this paragraph to be updated instead of quietly outliving
the truth.
"""
from __future__ import annotations

import builtins
import io
import json
import os
import shutil
import tempfile
from pathlib import Path

LIMITS = {
    "subprocess": "writes performed by a child process are NOT seen; a suite "
                  "that shells out yields a LOWER BOUND",
    "c_level": "a write issued through a C extension that bypasses open() and "
               "os.replace() is not seen",
}

_state: dict = {}


def pytest_addoption(parser):
    group = parser.getgroup("lw_write_tracer")
    group.addoption("--trace-roots", action="append", default=None,
                    help="live directories to watch; os.pathsep-separated, repeatable")
    group.addoption("--trace-out", default=None,
                    help="where to write the JSON report")


def _roots(config) -> list[Path]:
    raw = config.getoption("--trace-roots") or []
    if not raw:
        env = os.environ.get("LW_TRACE_ROOTS", "")
        raw = [env] if env else []
    out = []
    for chunk in raw:
        for part in str(chunk).split(os.pathsep):
            if part.strip():
                out.append(Path(part.strip()).resolve())
    return out


def _watched(target) -> str | None:
    try:
        p = Path(target).resolve()
    except (OSError, ValueError, TypeError):
        return None
    for root in _state["roots"]:
        if p == root or root in p.parents:
            return str(p)
    return None


def _blame(path: str) -> None:
    _state["written_by"].setdefault(path, set()).add(_state["nodeid"])


def _count(path: str, data) -> None:
    _state["bytes"][path] = _state["bytes"].get(path, 0) + len(data or "")
    _blame(path)


class _TracedFile:
    """A handle on a watched path, counting the bytes that pass through it."""

    def __init__(self, fh, path):
        self._fh, self._path = fh, path

    def write(self, data):
        _count(self._path, data)
        return self._fh.write(data)

    def writelines(self, lines):
        chunks = list(lines)
        for chunk in chunks:
            _count(self._path, chunk)
        return self._fh.writelines(chunks)

    def __getattr__(self, name):
        return getattr(self._fh, name)

    def __enter__(self):
        self._fh.__enter__()
        return self

    def __exit__(self, *exc):
        return self._fh.__exit__(*exc)

    def __iter__(self):
        return iter(self._fh)


def _make_open(real):
    def _open(file, mode="r", *a, **k):
        fh = real(file, mode, *a, **k)
        if any(m in mode for m in ("w", "a", "x", "+")):
            hit = _watched(file)
            if hit:
                _state["opened"].setdefault(hit, set()).add(_state["nodeid"])
                return _TracedFile(fh, hit)
        return fh
    return _open


def _make_move(real):
    def _move(src, dst, **k):
        hit = _watched(dst)
        if hit:
            _blame(hit)
        return real(src, dst, **k)
    return _move


def pytest_configure(config):
    _state.update(
        roots=_roots(config),
        out=Path(config.getoption("--trace-out")
                 or os.environ.get("LW_TRACE_OUT", "lw_write_trace.json")),
        # Anything before the first test: collection, import-time side effects
        # and a session fixture's setup. Named rather than dropped, because an
        # import-time write is one of the shapes this exists to find.
        nodeid="<collection or import time>",
        bytes={}, written_by={}, opened={},
        real=(builtins.open, io.open, os.replace, os.rename),
    )
    builtins.open = _make_open(_state["real"][0])
    io.open = _make_open(_state["real"][1])
    os.replace = _make_move(_state["real"][2])
    os.rename = _make_move(_state["real"][3])
    _state["control"] = _run_control()


def _run_control() -> dict:
    """Plant a specimen through every patched route and say what came back.

    ADOPTED FROM LL, 2026-09-11, and it is their point rather than LW's: an
    instrument that prints a zero with no self-check attached reports an
    absence of evidence dressed as evidence of absence. Their own probe printed
    188 findings beside "positive control UNPROVEN", and that admission is the
    only reason the 188 was worth reading.

    POSITIVE specimens prove the tracer can SEE. A NEGATIVE one - a write
    outside every watched root - proves it does not INVENT, which is LL's
    second point: a control made only of positives still passes when the
    classifier is mutated to promote everything.

    The specimens live in a private temp root that is watched only for the
    duration of this function, so the control never writes a real tree, and
    every trace of it is scrubbed before the report is built.
    """
    broken = os.environ.get("LW_TRACE_BREAK_CONTROL", "")
    # RESOLVED, and the control is what caught the need. On Windows
    # `mkdtemp` hands back the 8.3 short form (`ADMINI~1`) while `_watched`
    # resolves the file it is asked about to the long form, so an unresolved
    # root matched nothing and all three routes reported false on a tracer that
    # was working perfectly. An unproved control on the first run is exactly
    # the outcome LL described, arriving immediately.
    home = Path(tempfile.mkdtemp(prefix="lw_tracer_control_")).resolve()
    outside = Path(tempfile.mkdtemp(prefix="lw_tracer_outside_")).resolve()
    _state["roots"].append(home)
    try:
        if broken != "open":
            with builtins.open(home / "via_open.log", "a", encoding="utf-8") as fh:
                fh.write("x")
        if broken != "io_open":
            (home / "via_pathlib.json").write_text("{}", encoding="utf-8")
        if broken != "replace":
            src = outside / "scratch.tmp"
            src.write_text("x", encoding="utf-8")
            os.replace(src, home / "via_replace.json")

        seen = set(_state["written_by"])
        routes = {
            "open": str(home / "via_open.log") in seen,
            "io_open": str(home / "via_pathlib.json") in seen,
            "replace": str(home / "via_replace.json") in seen,
        }
        # The negative specimen: written outside every watched root on purpose.
        (outside / "must_not_appear.txt").write_text("x", encoding="utf-8")
        negative_clean = not any(str(outside) in k for k in _state["written_by"])
    finally:
        _state["roots"].remove(home)
        for path in (home, outside):
            shutil.rmtree(path, ignore_errors=True)

    # Scrub every specimen, or the control would manufacture a finding in each
    # tree it ran against - the over-reporting failure it exists to rule out.
    for bucket in ("bytes", "written_by", "opened"):
        for key in [k for k in _state[bucket] if "lw_tracer_control_" in k
                    or "lw_tracer_outside_" in k]:
            del _state[bucket][key]

    return {"proved": all(routes.values()) and negative_clean,
            "routes": routes, "negative_clean": negative_clean}


def pytest_runtest_logstart(nodeid, location):
    _state["nodeid"] = nodeid


def pytest_unconfigure(config):
    if not _state:
        return
    real_open, real_io_open, real_replace, real_rename = _state["real"]
    builtins.open, io.open = real_open, real_io_open
    os.replace, os.rename = real_replace, real_rename
    restored = (builtins.open is real_open and io.open is real_io_open
                and os.replace is real_replace and os.rename is real_rename)
    report = {
        "roots": [str(r) for r in _state["roots"]],
        "wrote_bytes": {k: _state["bytes"][k] for k in sorted(_state["bytes"])},
        "written_by": {k: sorted(v) for k, v in sorted(_state["written_by"].items())},
        "opened_for_write_only": {k: sorted(v) for k, v in sorted(_state["opened"].items())
                                  if k not in _state["bytes"]},
        "control": _state["control"],
        "limits": LIMITS,
        "restored": restored,
    }
    _state["out"].parent.mkdir(parents=True, exist_ok=True)
    with real_open(_state["out"], "w", encoding="utf-8") as fh:
        fh.write(json.dumps(report, indent=2))
