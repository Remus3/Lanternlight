"""Tests for ops/inbox_runner.py - the ARMED inbox runner. Operator ruling
2026-10-02, LL-0317.

It decides one thing - is there unread mail - and when there is, hands the
whole job to ONE headless session through ops.headless_spawn, the only door.
Everything is injected: no real inbox, no real lock, no real CLI.
"""

from __future__ import annotations

import json

from ops import headless_spawn as hs, inbox_runner as ir
from ops.inbox_watch import SCHEMA, digest_of


class _Spawn:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or hs.SpawnResult(True, "RAN", 0, "done", "")

    def __call__(self, args, **kw):
        self.calls.append((list(args), kw))
        return self.result


def _setup(tmp_path, notes=(), seen=()):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for name, body in notes:
        (inbox / name).write_text(body, encoding="utf-8")
    state = tmp_path / "seen.json"
    rows = [[n, digest_of((inbox / n).read_bytes())] for n in seen]
    state.write_text(json.dumps({"schema": SCHEMA, "seen": rows}), encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    return inbox, state, runtime


def _run(tmp_path, inbox, state, runtime, spawn):
    return ir.run(inbox=inbox, state=state, runtime=runtime, spawn=spawn)


def test_no_unread_mail_spawns_nothing(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")], seen=["a.md"])
    sp = _Spawn()
    res = _run(tmp_path, inbox, state, runtime, sp)
    assert sp.calls == [] and res.unread == 0 and not res.spawned


def test_unread_mail_spawns_exactly_one_session(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x"), ("b.md", "y")], seen=["a.md"])
    sp = _Spawn()
    res = _run(tmp_path, inbox, state, runtime, sp)
    assert res.unread == 1 and res.spawned
    assert len(sp.calls) == 1
    args, kw = sp.calls[0]
    assert args[0] == "-p" and ir.PROMPT in args
    assert kw["cwd"] == ir.REPO_ROOT


def test_an_edited_note_is_unread_again(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")], seen=["a.md"])
    (inbox / "a.md").write_text("x, corrected", encoding="utf-8")
    sp = _Spawn()
    assert _run(tmp_path, inbox, state, runtime, sp).unread == 1


def test_our_own_outbox_and_drafts_are_not_mail(tmp_path):
    inbox, state, runtime = _setup(tmp_path)
    (inbox / "_drafts").mkdir()
    (inbox / "_drafts" / "d.md").write_text("draft", encoding="utf-8")
    (inbox / "_outbox").mkdir()
    (inbox / "_outbox" / "z.md").write_text("ours", encoding="utf-8")
    sp = _Spawn()
    assert _run(tmp_path, inbox, state, runtime, sp).unread == 0
    assert sp.calls == []


def test_halt_file_stops_the_runner_before_anything(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    (runtime / ir.HALT_NAME).write_text("operator", encoding="utf-8")
    sp = _Spawn()
    res = _run(tmp_path, inbox, state, runtime, sp)
    assert sp.calls == [] and "HALT" in res.reason


def test_a_second_instance_declines(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    from ops.loop import guard
    guard.acquire(runtime / ir.LOCK_NAME, label="test-holder")
    sp = _Spawn()
    res = _run(tmp_path, inbox, state, runtime, sp)
    assert sp.calls == [] and "BUSY" in res.reason


def test_the_lock_is_released_after_a_run(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _run(tmp_path, inbox, state, runtime, _Spawn())
    assert not (runtime / ir.LOCK_NAME).exists()


def test_the_lock_is_released_when_the_spawn_raises(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])

    def boom(args, **kw):
        raise RuntimeError("x")

    res = _run(tmp_path, inbox, state, runtime, boom)
    assert not (runtime / ir.LOCK_NAME).exists()
    assert not res.spawned and "ERROR" in res.reason


def test_a_refused_spawn_is_reported_and_logged(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    sp = _Spawn(hs.SpawnResult(False, "REFUSED: the proxy refused"))
    res = _run(tmp_path, inbox, state, runtime, sp)
    assert not res.spawned and "REFUSED" in res.reason
    rec = json.loads((runtime / ir.LOG_NAME).read_text(encoding="utf-8").splitlines()[-1])
    assert rec["unread"] == 1 and "REFUSED" in rec["reason"]


def test_the_log_carries_no_note_names(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("secret-subject.md", "x")])
    _run(tmp_path, inbox, state, runtime, _Spawn())
    assert "secret-subject" not in (runtime / ir.LOG_NAME).read_text(encoding="utf-8")


def test_prompt_names_the_floors_it_must_keep():
    p = ir.PROMPT
    for must in ("CLAUDE.md", "HARD BOUNDARY", "ops.outbox.deliver", "answers=",
                 "full", "acknowledge", "MAIN", "SHA-256"):
        assert must in p, must
    assert p.isascii()


def test_the_session_is_not_given_bypass_permissions():
    joined = " ".join(ir.session_args())
    assert "bypassPermissions" not in joined
    assert "dangerously" not in joined
    assert "--allowedTools" in joined


def test_main_returns_zero_on_a_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(ir, "run", lambda **kw: ir.RunnerResult(1, False, "REFUSED: x"))
    assert ir.main([]) == 0


# --- refutation pass 2026-10-02, LL-0317 ------------------------------------


def test_a_non_markdown_top_level_note_is_mail(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("note.txt", "x")])
    sp = _Spawn()
    assert _run(tmp_path, inbox, state, runtime, sp).unread == 1


def test_a_new_subdirectory_drop_is_mail(tmp_path):
    inbox, state, runtime = _setup(tmp_path)
    (inbox / "from-XX-drop").mkdir()
    (inbox / "from-XX-drop" / "a.py").write_text("x = 1\n", encoding="utf-8")
    sp = _Spawn()
    assert _run(tmp_path, inbox, state, runtime, sp).unread == 1


def test_main_exits_zero_even_when_run_raises(monkeypatch):
    def boom(**kw):
        raise RuntimeError("x")
    monkeypatch.setattr(ir, "run", boom)
    assert ir.main([]) == 0
