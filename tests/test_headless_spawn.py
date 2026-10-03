"""Tests for ops/headless_spawn.py - the one door every headless `claude` run
from this tree goes through. Operator ruling 2026-10-02, recorded in CLAUDE.md
and LL-0317.

The contract under test, in the operator's terms:

* the base URL is read AT SPAWN TIME from the USER environment store first and
  the process environment second;
* it is set as ANTHROPIC_BASE_URL in the CHILD's environment only;
* FAIL CLOSED - an unset variable, a non-loopback URL, or a proxy that refuses a
  TCP connection refuses the spawn and logs why; there is no direct fallback;
* a usage-limit refusal backs off and never retries another way.

Nothing here talks to the real proxy or runs the real CLI: the registry
reader, the TCP probe and the runner are all injected.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta

import pytest

from ops import headless_spawn as hs

URL = "http://localhost:3456/some-path"


def _ok_probe(host, port):
    return True


def _refused_probe(host, port):
    return False


class _Runner:
    def __init__(self, rc=0, stdout="ok", stderr=""):
        self.calls = []
        self.rc, self.stdout, self.stderr = rc, stdout, stderr

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, self.rc, self.stdout, self.stderr)


# --- resolution -------------------------------------------------------------


def test_user_store_wins_over_process_env():
    got = hs.resolve_base_url(
        user_store=lambda name: "http://127.0.0.1:3456/a",
        environ={hs.HEADLESS_VAR: "http://127.0.0.1:3456/b"},
    )
    assert got == "http://127.0.0.1:3456/a"


def test_process_env_is_the_fallback_when_user_store_is_unset():
    got = hs.resolve_base_url(
        user_store=lambda name: None,
        environ={hs.HEADLESS_VAR: "http://127.0.0.1:3456/b"},
    )
    assert got == "http://127.0.0.1:3456/b"


def test_blank_values_count_as_unset():
    got = hs.resolve_base_url(user_store=lambda name: "   ", environ={hs.HEADLESS_VAR: ""})
    assert got is None


def test_user_store_reads_the_named_variable():
    seen = []
    hs.resolve_base_url(user_store=lambda name: seen.append(name), environ={})
    assert seen == ["CLAUDE_HEADLESS_BASE_URL"]


# --- the gate ---------------------------------------------------------------


def test_unset_variable_refuses(tmp_path):
    runner = _Runner()
    res = hs.spawn(["-p", "reply ok"], base_url=None, probe=_ok_probe, runner=runner,
                   runtime=tmp_path, user_store=lambda n: None, environ={})
    assert not res.spawned and "UNSET" in res.reason
    assert runner.calls == []


def test_refused_proxy_refuses(tmp_path):
    runner = _Runner()
    res = hs.spawn(["-p", "reply ok"], base_url=URL, probe=_refused_probe, runner=runner,
                   runtime=tmp_path)
    assert not res.spawned and "REFUSED" in res.reason
    assert runner.calls == []


@pytest.mark.parametrize("bad", [
    "http://example.com:3456/x", "https://api.anthropic.com", "http://10.0.0.5:3456",
    "not a url", "http://localhost/x", "ftp://127.0.0.1:3456",
])
def test_non_loopback_or_malformed_url_refuses(tmp_path, bad):
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=bad, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert not res.spawned
    assert runner.calls == []


def test_probe_is_aimed_at_loopback_on_the_urls_port(tmp_path):
    aimed = []
    hs.spawn(["-p", "x"], base_url="http://localhost:3456/p",
             probe=lambda h, p: aimed.append((h, p)) or True,
             runner=_Runner(), runtime=tmp_path)
    assert aimed == [("127.0.0.1", 3456)]


@pytest.mark.parametrize("argv", [
    ["--auto-fallback", "-p", "x"], ["-p", "teamclaude run --auto-fallback"],
])
def test_auto_fallback_is_never_passed(tmp_path, argv):
    runner = _Runner()
    res = hs.spawn(argv, base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert not res.spawned and "auto-fallback" in res.reason
    assert runner.calls == []


def test_every_refusal_is_logged(tmp_path):
    hs.spawn(["-p", "x"], base_url=None, probe=_ok_probe, runner=_Runner(), runtime=tmp_path,
             user_store=lambda n: None, environ={})
    lines = (tmp_path / hs.LOG_NAME).read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[-1])
    assert rec["spawned"] is False and "UNSET" in rec["reason"]


def test_the_log_never_carries_the_url(tmp_path):
    hs.spawn(["-p", "x"], base_url=URL, probe=_refused_probe, runner=_Runner(), runtime=tmp_path)
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=_Runner(), runtime=tmp_path)
    text = (tmp_path / hs.LOG_NAME).read_text(encoding="utf-8")
    assert "some-path" not in text and "3456" not in text


# --- the child environment --------------------------------------------------


def test_url_reaches_the_child_env_and_not_ours(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    runner = _Runner()
    res = hs.spawn(["-p", "reply ok"], base_url=URL, probe=_ok_probe, runner=runner,
                   runtime=tmp_path)
    assert res.spawned
    _argv, kw = runner.calls[0]
    child_value = kw["env"].get("ANTHROPIC_BASE_URL")
    assert child_value == URL
    inherited = os.environ.get("ANTHROPIC_BASE_URL")
    assert inherited is None


def test_child_env_overrides_an_inherited_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://elsewhere.invalid")
    runner = _Runner()
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    child_value = runner.calls[0][1]["env"].get("ANTHROPIC_BASE_URL")
    assert child_value == URL
    ours = os.environ.get("ANTHROPIC_BASE_URL")
    assert ours == "http://elsewhere.invalid"


def test_argv_starts_with_the_claude_executable(tmp_path):
    runner = _Runner()
    hs.spawn(["-p", "reply ok"], base_url=URL, probe=_ok_probe, runner=runner,
             runtime=tmp_path, claude="CLAUDE_EXE")
    assert runner.calls[0][0] == ["CLAUDE_EXE", "-p", "reply ok"]


def test_child_gets_no_console_window_on_windows(tmp_path):
    runner = _Runner()
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    if os.name == "nt":
        assert runner.calls[0][1]["creationflags"] & subprocess.CREATE_NO_WINDOW


# --- usage-limit backoff ----------------------------------------------------


def test_usage_limit_sets_a_backoff_and_does_not_retry(tmp_path):
    runner = _Runner(rc=1, stdout="Claude AI usage limit reached|1760000000")
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner,
                   runtime=tmp_path, now=now)
    assert res.spawned and res.usage_limited
    assert len(runner.calls) == 1
    state = json.loads((tmp_path / hs.BACKOFF_NAME).read_text(encoding="utf-8"))
    assert datetime.fromisoformat(state["until"]) > now


def test_backoff_refuses_the_next_spawn(tmp_path):
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe,
             runner=_Runner(rc=1, stderr="rate_limit_error: usage limit"),
             runtime=tmp_path, now=now)
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner,
                   runtime=tmp_path, now=now + timedelta(minutes=5))
    assert not res.spawned and "BACKOFF" in res.reason
    assert runner.calls == []


def test_backoff_expires(tmp_path):
    now = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe,
             runner=_Runner(rc=1, stdout="usage limit reached"), runtime=tmp_path, now=now)
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner,
                   runtime=tmp_path, now=now + timedelta(hours=7))
    assert res.spawned and len(runner.calls) == 1


def test_backoff_doubles_on_repeat_and_is_capped(tmp_path):
    t = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    spans = []
    for _ in range(6):
        hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe,
                 runner=_Runner(rc=1, stdout="usage limit"), runtime=tmp_path, now=t)
        until = datetime.fromisoformat(
            json.loads((tmp_path / hs.BACKOFF_NAME).read_text(encoding="utf-8"))["until"])
        spans.append(until - t)
        t = until + timedelta(seconds=1)
    assert spans[1] == 2 * spans[0]
    assert max(spans) <= hs.BACKOFF_MAX


def test_a_clean_run_clears_the_backoff_streak(tmp_path):
    t = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe,
             runner=_Runner(rc=1, stdout="usage limit"), runtime=tmp_path, now=t)
    t += timedelta(hours=7)
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=_Runner(), runtime=tmp_path, now=t)
    assert not (tmp_path / hs.BACKOFF_NAME).exists()


def test_unreadable_backoff_file_fails_closed(tmp_path):
    (tmp_path / hs.BACKOFF_NAME).write_text("{not json", encoding="utf-8")
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert not res.spawned and "BACKOFF" in res.reason


def test_a_timeout_is_reported_not_raised(tmp_path):
    def runner(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert res.spawned and res.returncode is None and "TIMEOUT" in res.reason


# --- real probe, against a socket we own ------------------------------------


def test_real_probe_sees_a_listener_and_a_closed_port():
    import socket
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert hs.tcp_probe("127.0.0.1", port) is True
    finally:
        srv.close()
    assert hs.tcp_probe("127.0.0.1", port) is False


# --- refutation pass 2026-10-02, LL-0317: each test below was red first ------


@pytest.mark.parametrize("bad", [
    "http://evil.invalid\\@localhost:3456/x",
    "http://user@localhost:3456/x",
    "http://evil.invalid@127.0.0.1:3456",
    "http://localhost:3456\\@evil.invalid/x",
    "http://LOCALHOST:3456 /x",
])
def test_userinfo_and_backslash_tricks_refuse(tmp_path, bad):
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=bad, probe=_ok_probe, runner=runner, runtime=tmp_path)
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
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    present_in_child = name in runner.calls[0][1]["env"]
    assert present_in_child is False
    ours = os.environ.get(name)
    assert ours == "parent-value"


def test_the_url_is_resolved_at_spawn_time_by_default(tmp_path):
    asked = []
    hs.spawn(["-p", "x"], probe=_ok_probe, runner=_Runner(), runtime=tmp_path,
             user_store=lambda n: asked.append(n) or None, environ={})
    assert asked == [hs.HEADLESS_VAR]


def test_the_real_user_store_reader_answers_none_for_an_absent_name():
    assert hs._user_store("LL_TEST_NO_SUCH_VARIABLE_0317") is None


def test_the_child_reads_no_stdin(tmp_path):
    runner = _Runner()
    hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert runner.calls[0][1]["stdin"] is subprocess.DEVNULL


def test_a_cli_that_cannot_start_is_a_logged_refusal(tmp_path):
    def runner(argv, **kw):
        raise FileNotFoundError(argv[0])
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert not res.spawned and "could not start" in res.reason


def test_a_malformed_streak_holds_closed(tmp_path):
    (tmp_path / hs.BACKOFF_NAME).write_text(
        json.dumps({"until": "2000-01-01T00:00:00+00:00", "streak": "two"}), encoding="utf-8")
    runner = _Runner()
    res = hs.spawn(["-p", "x"], base_url=URL, probe=_ok_probe, runner=runner, runtime=tmp_path)
    assert not res.spawned and "BACKOFF" in res.reason


def test_ipv6_loopback_is_probed_on_ipv6(tmp_path):
    aimed = []
    hs.spawn(["-p", "x"], base_url="http://[::1]:3456/p",
             probe=lambda h, p: aimed.append((h, p)) or True, runner=_Runner(), runtime=tmp_path)
    assert aimed == [("::1", 3456)]


def test_the_default_runner_kills_the_whole_tree_on_timeout():
    import sys
    import time
    code = ("import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']);"
            "time.sleep(30)")
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        hs.run_tree([sys.executable, "-c", code], timeout=2, capture_output=True, text=True,
                    stdin=subprocess.DEVNULL)
    assert time.monotonic() - t0 < 15
