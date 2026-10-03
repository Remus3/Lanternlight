"""Tests for ops/headless_spawn.py - the one door every headless `claude` run
from this tree goes through. Operator ruling 2026-10-02 (LL-0317); since MAIN
ORDER 0955 section 2 step 4 the door is a thin wrapper around MAIN's fleet kit,
``ops/fleet_kit/fleet_headless.spawn``.

The contract under test:

* the proxy URL is read at spawn time by the KIT (registry first, a readable
  registry without the value is the kill switch), set as ANTHROPIC_BASE_URL in
  the CHILD's environment only, with credentials and provider switches removed;
* FAIL CLOSED - an unset variable, a non-loopback URL, or a proxy that refuses
  a TCP connection refuses the spawn, and our log says why; no fallback;
* ``--bare`` and ``--auto-fallback`` are refused by THIS door before the kit;
* a usage-limit refusal backs off and never retries another way (ours, the kit
  has none);
* the child runs with stdin closed, UTF-8 decoding and a whole-tree kill.

Nothing here talks to the real proxy, runs the real CLI or reads a real
environment variable's value: the kit's ``url_source``, ``connect``,
``exe_source`` and ``run`` seams are injected, and every root is a tmp dir.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ops import headless_spawn as hs
from ops.fleet_kit import fleet_headless as kit

URL = "http://localhost:18999/some-path"


class _Sock:
    def close(self):
        pass


def _ok_connect(addr, timeout=2.0):
    return _Sock()


def _refused_connect(addr, timeout=2.0):
    raise ConnectionRefusedError("no listener")


class _Runner:
    def __init__(self, rc=0, stdout="ok", stderr=""):
        self.calls = []
        self.rc, self.stdout, self.stderr = rc, stdout, stderr

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, self.rc, self.stdout, self.stderr)


def _spawn(tmp_path, prompt="x", *, url=URL, connect=_ok_connect, runner=None,
           now=None, extra=(), **kw):
    """One spawn through the REAL kit with every outward seam injected."""
    return hs.spawn(prompt, extra=extra, root=tmp_path, runtime=tmp_path / "rt", now=now,
                    url_source=lambda: url, connect=connect,
                    exe_source=lambda: "CLAUDE_EXE",
                    run=runner if runner is not None else _Runner(), **kw)


def _our_log(tmp_path):
    return (tmp_path / "rt" / hs.LOG_NAME).read_text(encoding="utf-8")


# --- resolution: the kit's, and the kill switch it gives us ------------------


def test_the_kit_reads_the_registry_before_the_process_env():
    got = kit.base_url(registry=lambda: (True, "http://127.0.0.1:18999/a"),
                       environ={kit.VAR: "http://127.0.0.1:18999/b"})
    assert got == "http://127.0.0.1:18999/a"


def test_a_readable_registry_without_the_value_is_the_kill_switch():
    """Our old resolver fell back to a stale inherited env copy here."""
    got = kit.base_url(registry=lambda: (True, None),
                       environ={kit.VAR: "http://127.0.0.1:18999/b"})
    assert got is None


def test_an_unreadable_registry_falls_back_to_the_process_env():
    got = kit.base_url(registry=lambda: (False, None),
                       environ={kit.VAR: "http://127.0.0.1:18999/b"})
    assert got == "http://127.0.0.1:18999/b"


def test_the_door_leaves_url_resolution_to_the_kit(tmp_path):
    seen = {}

    def kit_spawn(root, code, prompt, **kw):
        seen.update(kw)
        return {"rc": 0}

    hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", kit_spawn=kit_spawn,
             run=_Runner())
    assert "url_source" not in seen and "connect" not in seen


def test_the_variable_name_is_unchanged():
    assert kit.VAR == "CLAUDE_HEADLESS_BASE_URL"


# --- the gate ---------------------------------------------------------------


def test_unset_variable_refuses(tmp_path):
    runner = _Runner()
    res = _spawn(tmp_path, url=None, runner=runner)
    assert not res.spawned and "unset" in res.reason
    assert runner.calls == []


def test_refused_proxy_refuses(tmp_path):
    runner = _Runner()
    res = _spawn(tmp_path, connect=_refused_connect, runner=runner)
    assert not res.spawned and "REFUSED" in res.reason and "unreachable" in res.reason
    assert runner.calls == []


@pytest.mark.parametrize("bad", [
    "http://example.com:18999/x", "https://api.anthropic.com", "http://10.0.0.5:18999",
    "not a url", "http://localhost/x", "ftp://127.0.0.1:18999",
])
def test_non_loopback_or_malformed_url_refuses(tmp_path, bad):
    runner = _Runner()
    res = _spawn(tmp_path, url=bad, runner=runner)
    assert not res.spawned
    assert runner.calls == []


def test_probe_is_aimed_at_the_urls_host_and_port(tmp_path):
    aimed = []
    _spawn(tmp_path, url="http://localhost:18999/p",
           connect=lambda addr, timeout=2.0: aimed.append(addr) or _Sock())
    assert aimed == [("localhost", 18999)]


@pytest.mark.parametrize("prompt, extra", [
    ("x", ["--auto-fallback"]), ("teamclaude run --auto-fallback", []),
])
def test_auto_fallback_is_never_passed(tmp_path, prompt, extra):
    runner = _Runner()
    res = _spawn(tmp_path, prompt, extra=extra, runner=runner)
    assert not res.spawned and "auto-fallback" in res.reason
    assert runner.calls == []


def test_every_refusal_is_logged(tmp_path):
    _spawn(tmp_path, url=None)
    rec = json.loads(_our_log(tmp_path).splitlines()[-1])
    assert rec["spawned"] is False and "unset" in rec["reason"]


def test_the_log_never_carries_the_url(tmp_path):
    _spawn(tmp_path, connect=_refused_connect)
    _spawn(tmp_path)
    text = _our_log(tmp_path)
    assert "some-path" not in text and "18999" not in text


def test_a_malformed_port_is_a_refusal_not_a_crash(tmp_path):
    runner = _Runner()
    res = _spawn(tmp_path, url="http://localhost:99999999/x", runner=runner)
    assert not res.spawned and res.reason.startswith("REFUSED")
    assert runner.calls == []


# --- the child environment --------------------------------------------------


def test_url_reaches_the_child_env_and_not_ours(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    runner = _Runner()
    res = _spawn(tmp_path, runner=runner)
    assert res.spawned
    _argv, kw = runner.calls[0]
    child_value = kw["env"].get("ANTHROPIC_BASE_URL")
    assert child_value == URL
    inherited = os.environ.get("ANTHROPIC_BASE_URL")
    assert inherited is None


def test_child_env_overrides_an_inherited_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://elsewhere.invalid")
    runner = _Runner()
    _spawn(tmp_path, runner=runner)
    child_value = runner.calls[0][1]["env"].get("ANTHROPIC_BASE_URL")
    assert child_value == URL
    ours = os.environ.get("ANTHROPIC_BASE_URL")
    assert ours == "http://elsewhere.invalid"


def test_argv_is_the_kits_with_our_extra_last(tmp_path):
    runner = _Runner()
    _spawn(tmp_path, "reply ok", extra=["--permission-mode", "plan"], runner=runner)
    assert runner.calls[0][0] == [
        "CLAUDE_EXE", "-p", "reply ok", "--output-format", "json",
        "--no-session-persistence", "--model", "sonnet", "--effort", "medium",
        "--strict-mcp-config", "--setting-sources", "project,local",
        "--permission-mode", "plan"]


def test_child_gets_no_console_window_on_windows(tmp_path):
    runner = _Runner()
    _spawn(tmp_path, runner=runner)
    if os.name == "nt":
        assert runner.calls[0][1]["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_the_child_runs_in_the_root(tmp_path):
    runner = _Runner()
    _spawn(tmp_path, runner=runner)
    assert runner.calls[0][1]["cwd"] == str(tmp_path)


# --- usage-limit backoff ----------------------------------------------------


def test_usage_limit_sets_a_backoff_and_does_not_retry(tmp_path):
    runner = _Runner(rc=1, stdout="Claude AI usage limit reached|1760000000")
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    res = _spawn(tmp_path, runner=runner, now=now)
    assert res.spawned and res.usage_limited
    assert len(runner.calls) == 1
    state = json.loads((tmp_path / "rt" / hs.BACKOFF_NAME).read_text(encoding="utf-8"))
    assert datetime.fromisoformat(state["until"]) > now


def test_backoff_refuses_the_next_spawn(tmp_path):
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    _spawn(tmp_path, runner=_Runner(rc=1, stderr="rate_limit_error: usage limit"), now=now)
    runner = _Runner()
    res = _spawn(tmp_path, runner=runner, now=now + timedelta(minutes=5))
    assert not res.spawned and "BACKOFF" in res.reason
    assert runner.calls == []


def test_backoff_expires(tmp_path):
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    _spawn(tmp_path, runner=_Runner(rc=1, stdout="usage limit reached"), now=now)
    runner = _Runner()
    res = _spawn(tmp_path, runner=runner, now=now + timedelta(hours=7))
    assert res.spawned and len(runner.calls) == 1


def test_backoff_doubles_on_repeat_and_is_capped(tmp_path):
    t = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    spans = []
    for _ in range(6):
        _spawn(tmp_path, runner=_Runner(rc=1, stdout="usage limit"), now=t)
        until = datetime.fromisoformat(json.loads(
            (tmp_path / "rt" / hs.BACKOFF_NAME).read_text(encoding="utf-8"))["until"])
        spans.append(until - t)
        t = until + timedelta(seconds=1)
    assert spans[1] == 2 * spans[0]
    assert max(spans) <= hs.BACKOFF_MAX


def test_a_clean_run_clears_the_backoff_streak(tmp_path):
    t = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    _spawn(tmp_path, runner=_Runner(rc=1, stdout="usage limit"), now=t)
    _spawn(tmp_path, now=t + timedelta(hours=7))
    assert not (tmp_path / "rt" / hs.BACKOFF_NAME).exists()


def test_unreadable_backoff_file_fails_closed(tmp_path):
    (tmp_path / "rt").mkdir()
    (tmp_path / "rt" / hs.BACKOFF_NAME).write_text("{not json", encoding="utf-8")
    runner = _Runner()
    res = _spawn(tmp_path, runner=runner)
    assert not res.spawned and "BACKOFF" in res.reason
    assert runner.calls == []


def test_a_backoff_refusal_never_reaches_the_kit_budget(tmp_path):
    (tmp_path / "rt").mkdir()
    (tmp_path / "rt" / hs.BACKOFF_NAME).write_text("{not json", encoding="utf-8")
    _spawn(tmp_path)
    assert not (tmp_path / kit.BUDGET_REL).exists()


def test_a_timeout_is_reported_not_raised(tmp_path):
    def runner(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
    res = _spawn(tmp_path, runner=runner)
    assert res.spawned and res.returncode is None and "TIMEOUT" in res.reason


# --- the kit's probe, against a socket we own -------------------------------


def test_the_kit_probe_sees_a_listener_and_a_closed_port():
    import socket
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        kit.probe("127.0.0.1", port)
    finally:
        srv.close()
    with pytest.raises(kit.Refused):
        kit.probe("127.0.0.1", port)


# --- refutation pass 2026-10-02, LL-0317 - now held by the kit ---------------


@pytest.mark.parametrize("bad", [
    "http://evil.invalid\\@localhost:18999/x",
    "http://user@localhost:18999/x",
    "http://evil.invalid@127.0.0.1:18999",
    "http://localhost:18999\\@evil.invalid/x",
    "http://LOCALHOST:18999 /x",
])
def test_userinfo_and_backslash_tricks_refuse(tmp_path, bad):
    runner = _Runner()
    res = _spawn(tmp_path, url=bad, runner=runner)
    assert not res.spawned, bad
    assert runner.calls == []


@pytest.mark.parametrize("name", [
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
])
def test_credentials_and_provider_switches_never_reach_the_child(tmp_path, monkeypatch, name):
    monkeypatch.setenv(name, "parent-value")
    runner = _Runner()
    _spawn(tmp_path, runner=runner)
    present_in_child = name in runner.calls[0][1]["env"]
    assert present_in_child is False
    ours = os.environ.get(name)
    assert ours == "parent-value"


def test_the_url_is_resolved_on_every_spawn(tmp_path):
    asked = []

    def source():
        asked.append(1)
        return URL

    for _ in range(2):
        hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", url_source=source,
                 connect=_ok_connect, exe_source=lambda: "E", run=_Runner())
    assert asked == [1, 1]


def test_the_default_run_seam_closes_stdin_and_decodes_utf8(tmp_path, monkeypatch):
    """Since kit v4 the door's seam is the kit's own runner; the kit passes
    the UTF-8-with-replacement decode and its runner closes stdin."""
    seen = {}

    def fake_popen(argv, stdin=None, **kw):
        seen.update(kw, stdin=stdin)
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(kit.subprocess, "Popen", fake_popen)
    hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", url_source=lambda: URL,
             connect=_ok_connect, exe_source=lambda: "E")
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["encoding"] == "utf-8" and seen["errors"] == "replace"


def test_the_door_has_no_local_runner_copy():
    """MAIN 1204 s7 step 3: the local run_tree copy is deleted, not kept."""
    assert not hasattr(hs, "run_tree")
    assert "subprocess.Popen" not in Path(hs.__file__).read_text(encoding="utf-8")


def test_the_default_run_seam_is_used_when_none_is_given(tmp_path, monkeypatch):
    used = []
    monkeypatch.setattr(hs, "_kit_run",
                        lambda argv, **kw: used.append(argv) or subprocess.CompletedProcess(
                            argv, 0, "", ""))
    hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", url_source=lambda: URL,
             connect=_ok_connect, exe_source=lambda: "E")
    assert len(used) == 1


def test_a_cli_that_cannot_start_is_a_logged_refusal(tmp_path):
    def runner(argv, **kw):
        raise FileNotFoundError(argv[0])
    res = _spawn(tmp_path, runner=runner)
    assert not res.spawned and "could not start" in res.reason
    assert "could not start" in _our_log(tmp_path)


def test_a_missing_claude_is_a_refusal(tmp_path):
    def gone():
        raise kit.Refused("claude not found on PATH")
    res = hs.spawn("x", root=tmp_path, runtime=tmp_path / "rt", url_source=lambda: URL,
                   connect=_ok_connect, exe_source=gone, run=_Runner())
    assert not res.spawned and "not found" in res.reason


def test_a_malformed_streak_holds_closed(tmp_path):
    (tmp_path / "rt").mkdir()
    (tmp_path / "rt" / hs.BACKOFF_NAME).write_text(
        json.dumps({"until": "2000-01-01T00:00:00+00:00", "streak": "two"}), encoding="utf-8")
    runner = _Runner()
    res = _spawn(tmp_path, runner=runner)
    assert not res.spawned and "BACKOFF" in res.reason


def test_ipv6_loopback_is_probed_on_ipv6(tmp_path):
    aimed = []
    _spawn(tmp_path, url="http://[::1]:18999/p",
           connect=lambda addr, timeout=2.0: aimed.append(addr) or _Sock())
    assert aimed == [("::1", 18999)]


def test_the_default_runner_kills_the_whole_tree_on_timeout():
    import sys
    import time
    code = ("import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']);"
            "time.sleep(30)")
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        hs._kit_run([sys.executable, "-c", code], timeout=2, capture_output=True, text=True)
    assert time.monotonic() - t0 < 15


# --- setup-overhead cut, MAIN 0912, now added by the kit ---------------------
#
# The kit adds --strict-mcp-config, --setting-sources project,local and
# --no-session-persistence on every non-bare run. Dropping USER scope is only
# safe because every floor hook lives in PROJECT scope, so the first test below
# pins that fact: if a floor ever moves to user scope, this goes red before a
# headless child silently runs without it.

_LEAN_FLAGS = ["--strict-mcp-config", "--setting-sources", "project,local",
               "--no-session-persistence"]


def _project_hooks():
    root = hs.REPO_ROOT / ".claude"
    found = []
    for name in ("settings.json", "settings.local.json"):
        path = root / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for event, matchers in (data.get("hooks") or {}).items():
            for m in matchers:
                for h in m.get("hooks") or []:
                    found.append((event, m.get("matcher") or "", h.get("command") or ""))
    return found


def test_the_floor_hooks_live_in_project_scope_settings():
    hooks = _project_hooks()
    gate = [(ev, mt) for ev, mt, cmd in hooks
            if ev == "PreToolUse" and "tools/precommit_gate.py" in cmd]
    assert gate, "the PreToolUse precommit gate is not registered in project scope"
    matchers = {part for _ev, mt in gate for part in mt.split("|")}
    assert {"Bash", "PowerShell"} <= matchers
    ascii_floor = [cmd for ev, _mt, cmd in hooks
                   if ev == "PostToolUse" and "tools/ascii_check.py" in cmd]
    assert ascii_floor, "the ASCII floor hook is not registered in project scope"


def test_the_kit_adds_the_overhead_flags(tmp_path):
    runner = _Runner()
    _spawn(tmp_path, runner=runner)
    argv = runner.calls[0][0]
    for flag in _LEAN_FLAGS:
        assert flag in argv, flag
    assert argv[argv.index("--setting-sources") + 1] == "project,local"


@pytest.mark.parametrize("extra", [
    ["--mcp-config", "m.json"],
    ["--permission-mode", "acceptEdits", "--allowedTools", "Read"],
])
def test_a_callers_extra_follows_the_kits_flags_unchanged(tmp_path, extra):
    runner = _Runner()
    _spawn(tmp_path, extra=extra, runner=runner)
    argv = runner.calls[0][0]
    assert argv[-len(extra):] == extra


def test_the_runners_extra_repeats_no_flag_the_kit_adds():
    """The kit appends ``extra`` without de-duplicating, so ours must not repeat."""
    from ops import inbox_runner as ir
    extra = ir.session_args(["a.md"])["extra"]
    kit_argv = kit.build_argv("E", "p", "sonnet", "medium")
    flags = {a for a in kit_argv if a.startswith("--")}
    assert not flags & {a for a in extra if a.startswith("--")}


@pytest.mark.parametrize("prompt, extra", [
    ("x", ["--bare"]), ("x", ["-c", "--bare"]), ("use --bare please", []),
])
def test_bare_is_refused_because_it_skips_the_hook_floor(tmp_path, prompt, extra):
    runner = _Runner()
    res = _spawn(tmp_path, prompt, extra=extra, runner=runner)
    assert not res.spawned and "--bare" in res.reason and "hook" in res.reason
    assert runner.calls == []


# --- logging: our log is decisions only; the kit's file is the usage record --


def _last_log(tmp_path):
    return json.loads(_our_log(tmp_path).splitlines()[-1])


def test_usage_numbers_go_to_the_kits_usage_file_not_our_log(tmp_path):
    out = json.dumps({
        "type": "result", "result": "ok SECRET-OPERATOR-NAME", "session_id": "sess-123",
        "total_cost_usd": 0.0123, "num_turns": 1, "duration_ms": 4567,
        "usage": {"input_tokens": 4, "cache_creation_input_tokens": 1200,
                  "cache_read_input_tokens": 9000, "output_tokens": 5,
                  "service_tier": "standard"},
    })
    _spawn(tmp_path, runner=_Runner(stdout=out))
    usage = json.loads((tmp_path / kit.USAGE_REL).read_text(encoding="ascii").splitlines()[-1])
    assert usage["input_tokens"] == 4 and usage["output_tokens"] == 5
    assert usage["code"] == "LL" and usage["note"] == hs.NOTE_WORK
    text = _our_log(tmp_path)
    assert "SECRET-OPERATOR-NAME" not in text and "sess-123" not in text
    assert "standard" not in text and "input_tokens" not in text


def test_the_kit_usage_file_never_carries_model_output(tmp_path):
    out = json.dumps({"result": "ok SECRET-OPERATOR-NAME", "usage": {}})
    _spawn(tmp_path, runner=_Runner(stdout=out))
    assert "SECRET" not in (tmp_path / kit.USAGE_REL).read_text(encoding="ascii")


@pytest.mark.parametrize("out", ["ok", "", "{not json", json.dumps({"n": 1})])
def test_our_log_record_has_a_fixed_shape(tmp_path, out):
    res = _spawn(tmp_path, runner=_Runner(stdout=out))
    assert res.spawned and res.reason == "RAN"
    rec = _last_log(tmp_path)
    assert set(rec) == {"at", "spawned", "reason", "returncode", "stdout_chars",
                        "stderr_chars"}


@pytest.mark.parametrize("out", ["[1, 2]", '"text"', json.dumps({"usage": "nope"})])
def test_a_non_object_stdout_is_a_plain_run_since_kit_v4(tmp_path, out):
    """Kit v3 raised in usage_line on a non-object stdout after the child ran;
    v4 (MAIN 1204 s3 item 6) yields null fields instead. The door reports a
    plain run, and the status is not left running."""
    res = _spawn(tmp_path, runner=_Runner(stdout=out))
    assert res.spawned and res.reason == "RAN"
    assert res.returncode == 0
    status = json.loads((tmp_path / kit.STATUS_REL).read_text(encoding="ascii"))
    assert status["state"] == "idle"
