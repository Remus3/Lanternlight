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


# --- MAIN orders 2026-10-03: budget, damping, status file, routing ----------
#
# MAIN 0855 (daily run budget), MAIN 0845 s3 (loop damping), MAIN 0915 s1
# (status file), MAIN 0912 C/D/E (headless flags and model routing). Every test
# below injects the clock and the status path; none writes into this tree.

from datetime import UTC, datetime, timedelta  # noqa: E402

_T0 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)


class _Clock:
    def __init__(self, at=_T0):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at = self.at + timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def _status_in_tmp(tmp_path, monkeypatch):
    """No test may write the real ops/loop/control/inbox_status.json."""
    target = tmp_path / "control" / "inbox_status.json"
    monkeypatch.setattr(ir, "_default_status_path", lambda: target)
    return target


def _status(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_runs(runtime, times, spawned=True):
    with (runtime / ir.LOG_NAME).open("a", encoding="utf-8", newline="\n") as fh:
        for t in times:
            fh.write(json.dumps({"at": t.isoformat(), "spawned": spawned,
                                 "unread": 1, "reason": "RAN"}) + "\n")


def _crun(inbox, state, runtime, spawn, clock=None, status=None, **kw):
    return ir.run(inbox=inbox, state=state, runtime=runtime, spawn=spawn,
                  now=clock or _Clock(), status_path=status, **kw)


# --- item 1: daily run budget ----------------------------------------------


def test_budget_constants_are_exported():
    assert ir.RUNS_CAP == 120 and ir.WINDOW_S == 86400
    assert "RUNS_CAP" in ir.__all__ and "WINDOW_S" in ir.__all__


def test_the_daily_budget_refuses_a_run_at_the_cap(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _write_runs(runtime, [_T0 - timedelta(minutes=10 + i) for i in range(120)])
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert sp.calls == [] and not res.spawned
    assert res.reason.startswith("LIMIT:") and "120" in res.reason
    rec = json.loads((runtime / ir.LOG_NAME).read_text(encoding="utf-8").splitlines()[-1])
    assert rec["reason"].startswith("LIMIT:") and rec["spawned"] is False


def test_one_below_the_cap_still_spawns(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _write_runs(runtime, [_T0 - timedelta(minutes=10 + i) for i in range(119)])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned and len(sp.calls) == 1


def test_runs_older_than_the_window_do_not_count(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _write_runs(runtime, [_T0 - timedelta(seconds=ir.WINDOW_S + 1 + i) for i in range(200)])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


def test_unspawned_records_do_not_count(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _write_runs(runtime, [_T0 - timedelta(minutes=i) for i in range(200)], spawned=False)
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


def test_an_unparseable_log_line_neither_crashes_nor_lowers_the_count(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _write_runs(runtime, [_T0 - timedelta(minutes=10 + i) for i in range(60)])
    with (runtime / ir.LOG_NAME).open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write(json.dumps({"at": "yesterday-ish", "spawned": True}) + "\n")
        fh.write("[1, 2]\n")
    _write_runs(runtime, [_T0 - timedelta(minutes=100 + i) for i in range(60)])
    budget = ir.runs_in_window(runtime, _T0)
    assert budget.count == 120 and budget.unparseable == 3
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert sp.calls == [] and res.reason.startswith("LIMIT:")


# --- item 2: loop damping --------------------------------------------------


def test_our_own_note_does_not_trigger_a_spawn(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("2026-10-03-from-LL-to-RC.md", "x")])
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert sp.calls == [] and not res.spawned
    assert res.reason == "NO TRIGGER: 1 unread, all self or terminal"
    assert ir.unread_count(inbox, state) == 1  # semantics kept for other callers


def test_a_terminal_filename_does_not_trigger_a_spawn(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("2026-10-03-from-RC-TERMINAL-ack.md", "x")])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).reason.startswith("NO TRIGGER")
    assert sp.calls == []


@pytest.mark.parametrize("name", ["terminal-notes.md", "TERMINALS.md", "xTERMINAL.md"])
def test_terminal_in_a_filename_must_be_the_uppercase_word(tmp_path, name):
    inbox, state, runtime = _setup(tmp_path, [(name, "body")])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


@pytest.mark.parametrize("body", [
    "# Note\n\nanswered: n/a (FYI, no reply requested)\n",
    "Done.\n\nanswered: n/a (ANSWER, no reply requested beyond the question above)\n",
    "Done.\n\nanswered: MAIN 0830 (partial), MAIN 0855\n(collision). A reply is not requested.\n",
    "Done.\n\nanswered: n/a - TERMINAL\n",
    "    FROM      RC\n    CLASS     TERMINAL. Nothing is asked.\n\nBody.\n",
    "CLASS: no-reply\n\nBody.\n",
])
def test_a_terminal_or_no_reply_marker_does_not_trigger(tmp_path, body):
    inbox, state, runtime = _setup(tmp_path, [("2026-10-03-from-RC-note.md", body)])
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert sp.calls == [] and res.reason.startswith("NO TRIGGER")


# Refutation pass 2026-10-03: a body-wide scan damped MAIN 0845 and 0855, live
# ORDERS whose prose QUOTES the damping rule. Only the marker lines - the
# ``answered:`` trailer and a ``CLASS`` header - may declare a note terminal.
@pytest.mark.parametrize("body", [
    "## 3. What does NOT change\n\n- Loop damping: never spawn on your OWN notes,"
    " never spawn on a note marked TERMINAL or no-reply.\n\n"
    "answered: n/a - a reply IS requested (section 4)\n",
    "kill switch and every safety floor are untouched, and every tree must\n"
    "TERMINAL or no-reply.\n\nanswered: n/a - a reply IS requested (section 4)\n",
    "Status: no-reply is what LW added.\n\nPlease answer.\n",
    "Thanks.\n\nNo reply requested from RC; LL please answer section 2.\n",
])
def test_a_note_that_quotes_the_damping_rule_still_triggers(tmp_path, body):
    inbox, state, runtime = _setup(
        tmp_path, [("2026-10-03-0845-from-MAIN-ORDER-ALL-x.md", body)])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


def test_a_sibling_note_quoting_an_ll_note_in_its_name_still_triggers(tmp_path):
    inbox, state, runtime = _setup(
        tmp_path, [("2026-10-03-2311-from-RSC-AUTO-REPLY-to-2026-10-03-from-LL-x.md", "y")])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


def test_a_live_note_beside_a_terminal_one_still_spawns(tmp_path):
    inbox, state, runtime = _setup(
        tmp_path, [("a-TERMINAL.md", "x"), ("b.md", "please answer")])
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert res.spawned and res.unread == 2


def test_damped_notes_are_not_acknowledged(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("x-from-LL-y.md", "x")])
    before = state.read_bytes()
    _crun(inbox, state, runtime, _Spawn())
    assert state.read_bytes() == before


def test_a_drop_still_triggers_beside_only_self_notes(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("x-from-LL-y.md", "x")])
    (inbox / "from-XX-drop").mkdir()
    (inbox / "from-XX-drop" / "a.py").write_text("x = 1\n", encoding="utf-8")
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned


def test_the_no_trigger_log_carries_no_note_names(tmp_path):
    inbox, state, runtime = _setup(tmp_path, [("secret-from-LL-subject.md", "x")])
    _crun(inbox, state, runtime, _Spawn())
    assert "secret" not in (runtime / ir.LOG_NAME).read_text(encoding="utf-8")


# --- item 3: status file ---------------------------------------------------

_KEYS = {"schema", "code", "updated", "state", "task", "task_started", "task_eta_s",
         "next_tick", "runs_in_window", "runs_cap", "window_s", "cap_frees_at"}


def test_an_idle_tick_writes_the_exact_schema(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")], seen=["a.md"])
    _crun(inbox, state, runtime, _Spawn())
    st = _status(_status_in_tmp)
    assert set(st) == _KEYS
    assert st["schema"] == 1 and st["code"] == "LL"
    assert st["state"] == "idle" and st["task"] == "Idle"
    assert st["runs_cap"] == 120 and st["window_s"] == 86400
    assert st["runs_in_window"] == 0 and st["cap_frees_at"] is None
    nxt = datetime.fromisoformat(st["next_tick"])
    assert nxt.utcoffset() is not None
    assert nxt == _T0 + timedelta(seconds=ir.CADENCE_S)
    assert datetime.fromisoformat(st["updated"]).utcoffset() is not None
    assert datetime.fromisoformat(st["task_started"]).utcoffset() is not None


def test_the_cadence_is_the_scheduled_task_interval():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "arm_inbox_runner", ir.REPO_ROOT / "scripts" / "arm_inbox_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert ir.CADENCE_S == mod.INTERVAL_MINUTES * 60


def test_the_status_is_running_session_while_the_spawn_runs(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    inside = []

    def spawn(args, **kw):
        inside.append(_status(_status_in_tmp))
        return hs.SpawnResult(True, "RAN", 0, "", "")

    _crun(inbox, state, runtime, spawn)
    assert inside[0]["state"] == "running" and inside[0]["task"] == "Running Session"
    assert inside[0]["next_tick"] is None
    assert _status(_status_in_tmp)["state"] == "idle"


def test_the_status_is_checking_inbox_while_the_inbox_is_read(
        tmp_path, monkeypatch, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")], seen=["a.md"])
    seen_states = []
    real = ir.unread_count

    def spy(*a, **kw):
        seen_states.append(_status(_status_in_tmp))
        return real(*a, **kw)

    monkeypatch.setattr(ir, "unread_count", spy)
    _crun(inbox, state, runtime, _Spawn())
    assert seen_states and seen_states[0]["state"] == "running"
    assert seen_states[0]["task"] == "Checking Inbox"


def test_a_halted_tick_writes_halted_and_reads_no_inbox(
        tmp_path, monkeypatch, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    (runtime / ir.HALT_NAME).write_text("operator", encoding="utf-8")

    def forbidden(*a, **kw):
        raise AssertionError("the inbox was read under HALT")

    monkeypatch.setattr(ir, "unread_count", forbidden)
    monkeypatch.setattr(ir, "trigger_names", forbidden)
    res = _crun(inbox, state, runtime, _Spawn())
    assert "HALT" in res.reason
    st = _status(_status_in_tmp)
    assert st["state"] == "halted" and st["task"] == "Halted"


def test_a_limit_tick_reports_when_the_cap_frees(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    times = [_T0 - timedelta(minutes=10 + i) for i in range(121)]
    _write_runs(runtime, times)
    _crun(inbox, state, runtime, _Spawn())
    st = _status(_status_in_tmp)
    assert st["state"] == "limit" and st["task"] == "Turn Limit Reached"
    assert st["runs_in_window"] == 121
    # 121 counted against a cap of 120: the cap frees when TWO have aged out,
    # i.e. when the second-oldest leaves the window.
    second_oldest = sorted(times)[1]
    assert datetime.fromisoformat(st["cap_frees_at"]) == second_oldest + timedelta(
        seconds=ir.WINDOW_S)


def test_a_backoff_refusal_is_backing_off(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    sp = _Spawn(hs.SpawnResult(False, "REFUSED: BACKOFF after a usage limit, until x"))
    _crun(inbox, state, runtime, sp)
    st = _status(_status_in_tmp)
    assert st["state"] == "backoff" and st["task"] == "Backing Off"


def test_another_refusal_is_refused_and_idle(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    sp = _Spawn(hs.SpawnResult(False, "REFUSED: the local proxy refused a TCP connection"))
    _crun(inbox, state, runtime, sp)
    st = _status(_status_in_tmp)
    assert st["state"] == "refused" and st["task"] == "Idle"


def test_a_busy_tick_leaves_the_holders_status_alone(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    from ops.loop import guard
    guard.acquire(runtime / ir.LOCK_NAME, label="test-holder")
    _status_in_tmp.parent.mkdir(parents=True)
    _status_in_tmp.write_text('{"state": "running"}', encoding="utf-8")
    _crun(inbox, state, runtime, _Spawn())
    assert _status(_status_in_tmp) == {"state": "running"}


def test_the_eta_is_null_until_three_runs_then_the_median(tmp_path, _status_in_tmp):
    clock = _Clock()
    inside = []

    def make_spawn(duration):
        def spawn(args, **kw):
            inside.append(_status(_status_in_tmp)["task_eta_s"])
            clock.advance(duration)
            return hs.SpawnResult(True, "RAN", 0, "", "")
        return spawn

    shared = tmp_path / "shared_rt"
    for i, d in enumerate((100, 600, 200, 50)):
        sub = tmp_path / f"r{i}"
        sub.mkdir()
        inbox, state, _rt = _setup(sub, [("a.md", "x")])
        _crun(inbox, state, shared, make_spawn(d), clock=clock)
        clock.advance(900)
    assert inside == [None, None, None, 200]


def test_the_task_history_is_kept_to_ten(tmp_path):
    runtime = tmp_path / "rt"
    for d in range(15):
        ir._record_duration(runtime, "Running Session", float(d))
    data = json.loads((runtime / ir.HISTORY_NAME).read_text(encoding="utf-8"))
    assert data["tasks"]["Running Session"] == [float(d) for d in range(5, 15)]
    assert ir._eta(runtime, "Running Session") == 10  # median of 5..14 is 9.5
    assert ir._eta(runtime, "Idle") is None


def test_a_status_write_failure_is_logged_and_the_runner_continues(
        tmp_path, monkeypatch):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])

    def boom(path, payload):
        raise PermissionError("locked")

    monkeypatch.setattr(ir, "_write_status_file", boom)
    sp = _Spawn()
    res = _crun(inbox, state, runtime, sp)
    assert res.spawned and len(sp.calls) == 1
    logged = (runtime / ir.LOG_NAME).read_text(encoding="utf-8")
    assert "STATUS WRITE FAILED: PermissionError" in logged


def test_the_status_write_is_atomic_and_leaves_no_temp(tmp_path, _status_in_tmp):
    inbox, state, runtime = _setup(tmp_path, [("a.md", "x")])
    _crun(inbox, state, runtime, _Spawn())
    assert [p.name for p in _status_in_tmp.parent.iterdir()] == [_status_in_tmp.name]


def test_every_task_name_is_from_the_ordered_set():
    assert set(ir.TASK_NAMES) == {
        "Idle", "Checking Inbox", "Running Session", "Delivering Notes",
        "Committing", "Backing Off", "Halted", "Turn Limit Reached"}
    assert all(len(t) <= 24 for t in ir.TASK_NAMES)


# --- item 4: the status file is not tracked --------------------------------


def test_the_status_path_is_gitignored():
    import subprocess
    done = subprocess.run(
        ["git", "check-ignore", "-q", "ops/loop/control/inbox_status.json"],
        cwd=str(ir.REPO_ROOT), capture_output=True)
    assert done.returncode == 0


# --- item 5: headless flags and model routing ------------------------------


def _flag(args, name):
    return args[args.index(name) + 1]


def test_output_format_is_json_and_no_bare():
    args = ir.session_args()
    assert _flag(args, "--output-format") == "json"
    assert "--bare" not in args


@pytest.mark.parametrize("names, model, effort", [
    (["2026-from-MAIN-ORDER-x.md"], "opus", "medium"),
    (["a-ACK-b.md", "c-FIX-d.md"], "opus", "medium"),
    (["a-RULING-b.md"], "opus", "medium"),
    (["a-ACK-b.md", "c-ANSWER-d.md", "e-INFORMATION-f.md"], "sonnet", "low"),
    (["a-TERMINAL-b.md", "c-CORRECTION-d.md"], "sonnet", "low"),
    (["a-ACK-b.md", "plain.md"], "sonnet", "medium"),
    (["plain.md"], "sonnet", "medium"),
    ([], "sonnet", "medium"),
    (None, "sonnet", "medium"),
])
def test_session_args_route_the_model(names, model, effort):
    args = ir.session_args(names)
    assert _flag(args, "--model") == model and _flag(args, "--effort") == effort
    assert args[0] == "-p" and ir.PROMPT in args


def test_the_spawn_receives_the_routed_model(tmp_path):
    inbox, state, runtime = _setup(
        tmp_path, [("x-from-MAIN-ORDER-y.md", "do it"), ("z-from-LL-FIX-q.md", "ours")])
    sp = _Spawn()
    _crun(inbox, state, runtime, sp)
    assert _flag(sp.calls[0][0], "--model") == "opus"


def test_a_self_note_does_not_route_the_model(tmp_path):
    inbox, state, runtime = _setup(
        tmp_path, [("a-ACK-b.md", "ok"), ("z-from-LL-ORDER-q.md", "ours")])
    sp = _Spawn()
    _crun(inbox, state, runtime, sp)
    args = sp.calls[0][0]
    assert _flag(args, "--model") == "sonnet" and _flag(args, "--effort") == "low"


def test_an_order_is_never_damped_by_its_trailer(tmp_path):
    # An ORDER needs acting on whether or not it wants a reply (SS
    # made the same exemption); only its NAME, never its trailer, can damp it.
    inbox, state, runtime = _setup(tmp_path, [(
        "2026-10-03-0900-from-MAIN-ORDER-ALL-x.md",
        "Do the thing.\n\nanswered: n/a - no reply requested\n")])
    sp = _Spawn()
    assert _crun(inbox, state, runtime, sp).spawned
