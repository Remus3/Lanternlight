"""Tests for ops/inbox_runner.py - the ARMED inbox runner. Operator ruling
2026-10-02, LL-0317.

It decides one thing - is there unread mail - and when there is, hands the
whole job to ONE headless session through ops.headless_spawn, the only door.
Everything is injected: no real inbox, no real lock, no real CLI.
"""

from __future__ import annotations

import json

import pytest

from ops import headless_spawn as hs, inbox_runner as ir
from ops.inbox_watch import SCHEMA, digest_of


@pytest.fixture(autouse=True)
def _no_real_tree(monkeypatch):
    """OPS-116: the default tree check runs git in THIS repository; no test may."""
    monkeypatch.setattr(ir, "_default_tree_check", lambda: None)


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


def test_the_prompt_hook_refuses_while_the_spawned_session_runs(tmp_path):
    """OPS-115: the child's own prompt hook must not ack the mail it was sent for.

    End to end against the real hook function: inside the spawn, with the seen
    set in the runner's runtime directory as it is in the real tree.
    """
    from ops import inbox_watch
    inbox, _state, runtime = _setup(tmp_path, [("a.md", "x")])
    state = runtime / "seen.json"
    state.write_text(json.dumps({"schema": SCHEMA, "seen": []}), encoding="utf-8")
    seen_inside = []

    def spawn(args, **kw):
        seen_inside.append(inbox_watch.on_prompt_submit(
            json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "child"}),
            inbox=inbox, state=state, reported=runtime / "rep.json",
            trace=runtime / "trace.json",
        ))
        return hs.SpawnResult(True, "RAN", 0, "", "")

    _run(tmp_path, inbox, state, runtime, spawn)
    assert seen_inside == [inbox_watch.TRIGGER_RUNNER_SESSION]


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


def test_main_exits_zero_even_when_run_raises(monkeypatch, tmp_path):
    def boom(**kw):
        raise RuntimeError("x")
    monkeypatch.setattr(ir, "run", boom)
    monkeypatch.setattr(ir, "REPO_ROOT", tmp_path)
    assert ir.main([]) == 0
    logged = (tmp_path / "ops" / "runtime" / ir.LOG_NAME).read_text(encoding="utf-8")
    assert "ERROR" in logged


# --- OPS-116: a session that returns rc 0 with its work uncommitted ---------
#
# LL-0320 and LL-0321 were each left staged-not-committed by a runner session
# that returned rc 0, and the runner logged RAN both times. The runner must
# measure the tree AFTER the session and refuse to call that RAN.


def test_a_dirty_tree_after_a_clean_exit_is_not_logged_ran(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    res = ir.run(inbox=inbox, state=state, runtime=runtime, spawn=_Spawn(),
                 tree_check=lambda: "2 uncommitted paths")
    assert res.spawned
    assert not res.reason.startswith("RAN"), res.reason
    assert "UNCOMMITTED" in res.reason
    rec = json.loads((runtime / ir.LOG_NAME).read_text(encoding="utf-8").splitlines()[-1])
    assert not rec["reason"].startswith("RAN") and "UNCOMMITTED" in rec["reason"]


def test_a_clean_tree_after_a_clean_exit_stays_ran(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    res = ir.run(inbox=inbox, state=state, runtime=runtime, spawn=_Spawn(),
                 tree_check=lambda: None)
    assert res.reason == "RAN"


def test_the_tree_is_not_measured_when_nothing_ran(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    calls = []
    res = ir.run(inbox=inbox, state=state, runtime=runtime,
                 spawn=_Spawn(hs.SpawnResult(False, "REFUSED: x")),
                 tree_check=lambda: calls.append(1) or "dirty")
    # Measured once BEFORE the spawn, for attribution only; a non-RAN result is
    # never re-measured or re-labelled.
    assert calls == [1] and res.reason == "REFUSED: x"


def test_a_tree_check_that_raises_is_not_ran(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])

    def boom():
        raise OSError("git missing")

    res = ir.run(inbox=inbox, state=state, runtime=runtime, spawn=_Spawn(),
                 tree_check=boom)
    assert not res.reason.startswith("RAN") and "UNVERIFIED" in res.reason
    assert not (runtime / ir.LOCK_NAME).exists()


def test_tree_problem_names_staged_and_unpushed_work(tmp_path):
    """The real measurement, against a throwaway repository - never this one."""
    import subprocess

    def git(*a, cwd):
        subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)

    remote = tmp_path / "remote.git"
    git("init", "--bare", "-q", str(remote), cwd=tmp_path)
    repo = tmp_path / "repo"
    git("init", "-q", str(repo), cwd=tmp_path)
    for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"),
                 ("core.hooksPath", str(tmp_path / "nohooks"))):
        git("config", k, v, cwd=repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt", cwd=repo)
    git("commit", "-q", "-m", "a", cwd=repo)
    git("remote", "add", "origin", str(remote), cwd=repo)
    git("push", "-q", "-u", "origin", "HEAD", cwd=repo)
    assert ir._tree_problem(repo) is None

    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git("add", "b.txt", cwd=repo)
    assert "uncommitted" in ir._tree_problem(repo)

    git("commit", "-q", "-m", "b", cwd=repo)
    assert "unpushed" in ir._tree_problem(repo)

    git("push", "-q", cwd=repo)
    assert ir._tree_problem(repo) is None


def test_prompt_tells_the_session_to_outlast_the_commit_hook():
    p = ir.PROMPT
    assert "600000" in p
    assert "HEAD" in p


def test_a_tree_already_dirty_before_the_session_is_attributed(tmp_path):
    """Refutation pass 2026-10-03: an attended session's uncommitted work must
    not be reported as if the runner session alone left it."""
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    answers = iter(["2 uncommitted paths", "2 uncommitted paths"])
    res = ir.run(inbox=inbox, state=state, runtime=runtime, spawn=_Spawn(),
                 tree_check=lambda: next(answers))
    assert res.reason.startswith("UNCOMMITTED")
    assert "already had 2 uncommitted paths before it started" in res.reason


def test_prompt_gives_a_recovery_step_when_head_did_not_move():
    assert "HEAD did not move" in ir.PROMPT
