"""Every headless ``claude`` from this tree goes through MAIN's fleet kit.

MAIN 0955 section 2 step 4 (operator order relayed, provenance-checked):
every spawn goes through ``ops/fleet_kit/fleet_headless.spawn``, and this
tree's own proxy, probe, budget, status and console code is deleted. Our
``ops/headless_spawn.spawn`` stays the ONE door our code calls, as a thin
wrapper keeping only what the kit cannot express:

* ``--bare`` and ``--auto-fallback`` are REFUSED before the kit is called -
  our floors live in a PreToolUse hook, which ``--bare`` skips, and the kit
  passes ``extra`` through unchecked;
* the kit is always called with ``bare=False``;
* usage-limit backoff (the kit has none);
* the run budget lives in the kit door, so its refusal surfaces as ours, and
  the CLI entry point - which used to bypass the runner's cap - gets it free;
* the CLI still refuses while ``ops/runtime/INBOX_RUNNER_HALT`` exists.

Nothing here starts a real ``claude``, touches the network or reads a real
environment variable's value: the kit's ``run``, ``url_source``, ``connect``
and ``exe_source`` seams are injected, or the kit's ``spawn`` is replaced.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ops import headless_spawn as hs, inbox_runner as ir
from ops.fleet_kit import fleet_headless as kit
from ops.inbox_watch import SCHEMA

URL = "http://localhost:18999/some-path"


class _KitSpy:
    """Stands in for ``fleet_headless.spawn`` and records how it was called."""

    def __init__(self, line=None, exc=None):
        self.calls = []
        self.line = line if line is not None else {"rc": 0, "result": None}
        self.exc = exc

    def __call__(self, root, code, prompt, **kw):
        self.calls.append((root, code, prompt, kw))
        if self.exc is not None:
            raise self.exc
        run = kw.get("run")
        if run is not None:
            run(["EXE", "-p", prompt], cwd=str(root), env={}, capture_output=True,
                text=True, timeout=kw.get("timeout"), creationflags=0)
        return dict(self.line)


def _ok_run(argv, **kw):
    return subprocess.CompletedProcess(argv, 0, "{}", "")


def _seams(run=_ok_run):
    return {"url_source": lambda: URL, "connect": lambda addr, timeout=2.0: _Sock(),
            "exe_source": lambda: "EXE", "run": run}


class _Sock:
    def close(self):
        pass


def test_spawn_goes_through_the_kit(tmp_path):
    spy = _KitSpy()
    res = hs.spawn("reply ok", root=tmp_path, runtime=tmp_path / "rt", kit_spawn=spy,
                   run=_ok_run)
    assert res.spawned and res.reason == "RAN"
    assert len(spy.calls) == 1
    root, code, prompt, kw = spy.calls[0]
    assert Path(root) == tmp_path and code == "LL" and prompt == "reply ok"
    assert kw["bare"] is False


def test_the_default_kit_entry_is_fleet_headless_spawn(tmp_path, monkeypatch):
    spy = _KitSpy()
    monkeypatch.setattr(kit, "spawn", spy)
    hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", run=_ok_run)
    assert len(spy.calls) == 1


@pytest.mark.parametrize("prompt, extra", [
    ("x", ["--bare"]),
    ("x", ["--model", "sonnet", "--bare"]),
    ("x", ["--auto-fallback"]),
    ("teamclaude run --auto-fallback", []),
])
def test_bare_and_auto_fallback_are_refused_before_the_kit(tmp_path, prompt, extra):
    spy = _KitSpy()
    res = hs.spawn(prompt, extra=extra, root=tmp_path, runtime=tmp_path / "rt",
                   kit_spawn=spy)
    assert not res.spawned and res.reason.startswith("REFUSED")
    assert spy.calls == []


def test_the_kit_is_never_asked_for_bare(tmp_path):
    spy = _KitSpy()
    hs.spawn("x", writes_code=True, root=tmp_path, runtime=tmp_path / "rt", kit_spawn=spy,
             run=_ok_run)
    assert spy.calls[0][3]["bare"] is False
    assert "rules_file" not in spy.calls[0][3] or spy.calls[0][3]["rules_file"] is None


def test_a_budget_refusal_from_the_kit_is_our_limit_refusal(tmp_path):
    budget = tmp_path / kit.BUDGET_REL
    budget.parent.mkdir(parents=True)
    import time
    now = time.time()
    budget.write_text(json.dumps({"starts": [now - 60 - i for i in range(kit.RUNS_CAP)]}),
                      encoding="ascii")
    ran = []
    res = hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt",
                   **_seams(run=lambda argv, **kw: ran.append(argv)))
    assert not res.spawned and res.reason.startswith("LIMIT:")
    assert "budget" in res.reason and ran == []
    status = json.loads((tmp_path / kit.STATUS_REL).read_text(encoding="ascii"))
    assert status["state"] == "limit"


def test_one_below_the_kit_budget_still_runs(tmp_path):
    budget = tmp_path / kit.BUDGET_REL
    budget.parent.mkdir(parents=True)
    import time
    now = time.time()
    budget.write_text(json.dumps({"starts": [now - 60 - i for i in range(kit.RUNS_CAP - 1)]}),
                      encoding="ascii")
    ran = []

    def run(argv, **kw):
        ran.append(argv)
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    res = hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", **_seams(run=run))
    assert res.spawned and len(ran) == 1


def test_another_kit_refusal_is_our_refused(tmp_path):
    res = hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt",
                   kit_spawn=_KitSpy(exc=kit.Refused("proxy unreachable: OSError")))
    assert not res.spawned and res.reason.startswith("REFUSED:")
    assert "proxy unreachable" in res.reason


def test_an_order_trigger_asks_the_kit_for_writes_code(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "2026-10-03-0955-from-MAIN-ORDER-ALL-x.md").write_text("do it", encoding="utf-8")
    state = tmp_path / "seen.json"
    state.write_text(json.dumps({"schema": SCHEMA, "seen": []}), encoding="utf-8")
    runtime = tmp_path / "rt"
    runtime.mkdir()
    spy = _KitSpy()

    def door(prompt, **kw):
        return hs.spawn(prompt, kit_spawn=spy, run=_ok_run, **kw)

    ir.run(inbox=inbox, state=state, runtime=runtime, spawn=door, root=tmp_path,
           tree_check=lambda: None)
    assert len(spy.calls) == 1
    kw = spy.calls[0][3]
    assert kw["writes_code"] is True
    assert kit.pick_model(kw["writes_code"]) == "opus"
    assert kit.pick_effort(kw["note"]) == "medium"


@pytest.mark.parametrize("note, effort", [(hs.NOTE_ACK, "low"), (hs.NOTE_WORK, "medium")])
def test_the_note_vocabulary_yields_the_intended_effort_in_the_kit(note, effort):
    assert kit.pick_effort(note) == effort
    # A fixed vocabulary, never channel text: the kit logs the note string.
    assert note.isascii() and "from" not in note.lower()


def test_the_cli_refuses_while_the_halt_file_exists(tmp_path, monkeypatch):
    runtime = tmp_path / "ops" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / hs.HALT_NAME).write_text("operator", encoding="utf-8")
    monkeypatch.setattr(hs, "REPO_ROOT", tmp_path)
    spy = _KitSpy()
    monkeypatch.setattr(kit, "spawn", spy)
    assert hs.main(["--", "reply ok"]) == 1
    assert spy.calls == []


def test_the_cli_routes_through_the_kit(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(hs, "_kit_run", _ok_run)
    spy = _KitSpy()
    monkeypatch.setattr(kit, "spawn", spy)
    assert hs.main(["--writes-code", "--", "reply ok", "--permission-mode", "plan"]) == 0
    _root, code, prompt, kw = spy.calls[0]
    assert code == "LL" and prompt == "reply ok"
    assert list(kw["extra"]) == ["--permission-mode", "plan"]
    assert kw["writes_code"] is True and kw["bare"] is False


def test_the_cli_cannot_smuggle_bare_past_the_door(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "REPO_ROOT", tmp_path)
    spy = _KitSpy()
    monkeypatch.setattr(kit, "spawn", spy)
    assert hs.main(["--", "x", "--bare"]) == 1
    assert spy.calls == []


def test_a_timeout_inside_the_kit_does_not_leave_status_running(tmp_path):
    def run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))

    res = hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", **_seams(run=run))
    assert res.spawned and res.returncode is None and "TIMEOUT" in res.reason
    status = json.loads((tmp_path / kit.STATUS_REL).read_text(encoding="ascii"))
    assert status["state"] == "idle"


def test_the_runner_does_not_use_the_kits_skip_for_damping(tmp_path):
    """Kit v3's ``should_skip`` matched TERMINAL anywhere in the head and damped
    a live ORDER that QUOTES the damping rule (LL-0339/LL-0340, reported to
    MAIN). v4 (MAIN 1204 s3 item 2) no longer damps it; our runner damps on
    marker LINES only and keeps its own check."""
    name = "2026-10-03-0845-from-MAIN-ORDER-ALL-x.md"
    body = ("Loop damping: never spawn on a note marked TERMINAL or no-reply.\n\n"
            "answered: n/a - a reply IS requested\n")
    assert kit.should_skip(name, "LL", body) is None
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / name).write_text(body, encoding="utf-8")
    state = tmp_path / "seen.json"
    state.write_text(json.dumps({"schema": SCHEMA, "seen": []}), encoding="utf-8")
    assert ir.trigger_names(inbox, state) == [name]
